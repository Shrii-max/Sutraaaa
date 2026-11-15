"""Fact Extraction Agent with strict anti-hallucination offset and snippet verification.

Follows Requirement:
4. FactExtractionAgent: chunk pages with page and offset tracking, extract the ExtractedFacts
   schema via chat_json. Must extract victim/witness statements with recorded date,
   recorded_by and statement type (e.g., Section 161 CrPC / 164 CrPC / BNSS equivalents).
   Verify every returned snippet actually exists in the page text at the given offsets;
   drop or flag items that fail this check (anti-hallucination check).
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from app.agents.base import BaseAgent
from app.schemas.source import SourceRef
from app.schemas.facts import (
    ExtractedFacts,
    PartyItem,
    DateItem,
    SectionItem,
    AmountItem,
    LocationItem,
    IncidentItem,
    StatementItem,
    FactItem,
    DocumentExtractionInput,
    DocumentExtractionOutput,
)
from app.ingestion.devanagari import normalize_devanagari_text, detect_language_mix
from app.security.guardrails import wrap_as_document_data, format_safe_system_prompt
from app.agents.deterministic_extractors import (
    extract_dates_deterministic,
    extract_sections_deterministic,
    extract_parties_deterministic,
    extract_amounts_deterministic,
    extract_court_and_case_deterministic,
    extract_statements_deterministic,
    extract_incidents_deterministic,
    check_chronological_order,
    check_fuzzy_name_variants,
)
from app.llm.router import ModelRouter, TaskType


class _CandidateFactItem(BaseModel):
    fact_id: Optional[str] = None
    category: Optional[str] = None
    statement: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    date_str: Optional[str] = None
    description: Optional[str] = None
    act: Optional[str] = "other"
    section_number: Optional[str] = None
    value: Optional[float] = None
    currency: Optional[str] = "INR"
    context: Optional[str] = None
    place: Optional[str] = None
    title: Optional[str] = None
    statement_type: Optional[str] = "other"
    speaker: Optional[str] = None
    recorded_on: Optional[str] = None
    recorded_by: Optional[str] = None
    content: Optional[str] = None
    page: Optional[int] = 1
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    snippet: Optional[str] = None
    confidence: float = 0.85


class _RawExtractedFactsPayload(BaseModel):
    parties: List[_CandidateFactItem] = Field(default_factory=list)
    dates: List[_CandidateFactItem] = Field(default_factory=list)
    sections: List[_CandidateFactItem] = Field(default_factory=list)
    amounts: List[_CandidateFactItem] = Field(default_factory=list)
    locations: List[_CandidateFactItem] = Field(default_factory=list)
    incidents: List[_CandidateFactItem] = Field(default_factory=list)
    statements: List[_CandidateFactItem] = Field(default_factory=list)
    candidate_facts: List[_CandidateFactItem] = Field(default_factory=list)
    parties_plaintiff: List[str] = Field(default_factory=list)
    parties_defendant: List[str] = Field(default_factory=list)
    court_name: Optional[str] = None
    purpose: Optional[str] = None
    court: Optional[str] = None
    case_number: Optional[str] = None


class FactExtractionAgent(BaseAgent[DocumentExtractionInput, DocumentExtractionOutput]):
    """Extracts facts, statutory sections, and witness statements with strict anti-hallucination validation."""

    agent_name: str = "FactExtractionAgent"

    def _execute(self, input_data: DocumentExtractionInput) -> DocumentExtractionOutput:
        normalized_text = normalize_devanagari_text(input_data.text_content)
        detected_lang = detect_language_mix(normalized_text)

        # Build page map (if form feed \x0c is present or single page)
        raw_pages = normalized_text.split("\x0c") if "\x0c" in normalized_text else [normalized_text]
        page_text_map: Dict[int, str] = {idx + 1: p for idx, p in enumerate(raw_pages)}

        prompt = (
            f"Analyze the following legal document and extract structured facts:\n"
            f"1. Parties involved (plaintiff, defendant, accused, complainant, victim, witnesses)\n"
            f"2. Significant dates (incident date, filing date, notice date, dishonour date)\n"
            f"3. Statutory sections invoked (IPC, BNS, CrPC, BNSS, NI Act, etc.)\n"
            f"4. Monetary amounts involved (loan amount, cheque amount, damages)\n"
            f"5. Key locations (places of occurrence, jurisdictions, police stations)\n"
            f"6. Factual incidents\n"
            f"7. Victim/witness statements: MUST capture statement_type ('161', '164', 'complaint', 'deposition', 'other'), "
            f"speaker, role, recorded_on date, recorded_by officer/magistrate, and content.\n\n"
            f"ANTI-HALLUCINATION RULE: Every single item MUST provide 'page', 'snippet' (exact verbatim quote from text), "
            f"'char_start', and 'char_end'. Do NOT invent facts or snippets not present in the text.\n\n"
            f"Document Text:\n"
            f"{wrap_as_document_data(normalized_text[:7000])}"
        )

        system = format_safe_system_prompt(
            "You are a judicial research assistant extracting legally verifiable facts. "
            "Output strictly valid JSON conforming to the schema. Verbatim provenance is mandatory."
        )

        # Enforce Hard Rule 9: Call chat_json with retry logic
        raw_payload, review_needed = self.llm.generate_structured(
            prompt=prompt,
            schema=_RawExtractedFactsPayload,
            system=system,
        )

        # ------------------------------------------------------------------
        # Deterministic Rule-First Extraction (Full Entity Suite)
        # ------------------------------------------------------------------
        det_dates = extract_dates_deterministic(page_text_map, input_data.document_id)
        det_sections = extract_sections_deterministic(page_text_map, input_data.document_id)
        det_parties = extract_parties_deterministic(page_text_map, input_data.document_id)
        det_amounts = extract_amounts_deterministic(page_text_map, input_data.document_id)
        det_statements = extract_statements_deterministic(page_text_map, input_data.document_id)
        det_incidents = extract_incidents_deterministic(page_text_map, input_data.document_id)
        det_court, det_case_no = extract_court_and_case_deterministic(page_text_map)

        # ------------------------------------------------------------------
        # Anti-Hallucination Provenance Verification Layer
        # ------------------------------------------------------------------
        rejected_count = 0

        def verify_and_build_source(item: _CandidateFactItem) -> Optional[SourceRef]:
            nonlocal rejected_count
            snippet = (item.snippet or "").strip()
            if not snippet:
                rejected_count += 1
                return None

            page_num = item.page if (item.page and item.page in page_text_map) else 1
            page_text = page_text_map[page_num]

            start = item.char_start
            end = item.char_end

            # Check if snippet matches exact slice at given offsets
            if start is not None and end is not None and 0 <= start < end <= len(page_text):
                if page_text[start:end].strip() == snippet:
                    return SourceRef(
                        document_id=input_data.document_id,
                        page=page_num,
                        char_start=start,
                        char_end=end,
                        snippet=snippet,
                    )

            # Relocate snippet verbatim in page_text if offsets drifted
            loc = page_text.find(snippet)
            if loc != -1:
                return SourceRef(
                    document_id=input_data.document_id,
                    page=page_num,
                    char_start=loc,
                    char_end=loc + len(snippet),
                    snippet=snippet,
                )

            # Search across any page if page index was wrong
            for p_num, p_text in page_text_map.items():
                loc = p_text.find(snippet)
                if loc != -1:
                    return SourceRef(
                        document_id=input_data.document_id,
                        page=p_num,
                        char_start=loc,
                        char_end=loc + len(snippet),
                        snippet=snippet,
                    )

            # FAILED ANTI-HALLUCINATION CHECK: Snippet does not exist in document
            rejected_count += 1
            return None

        # Build ExtractedFacts
        verified_parties: List[PartyItem] = []
        for p in raw_payload.parties:
            src = verify_and_build_source(p)
            if src and p.name:
                verified_parties.append(PartyItem(name=p.name, role=p.role or "party", source=src, confidence=p.confidence))

        # Merge deterministic parties
        existing_party_names = {p.name.strip().lower() for p in verified_parties}
        for dp in det_parties:
            if dp.name.strip().lower() not in existing_party_names:
                verified_parties.append(dp)
                existing_party_names.add(dp.name.strip().lower())

        verified_dates: List[DateItem] = []
        for d in raw_payload.dates:
            src = verify_and_build_source(d)
            if src and d.date_str:
                verified_dates.append(DateItem(date_str=d.date_str, description=d.description or "Date mentioned", source=src, confidence=d.confidence))

        # Merge deterministic dates
        existing_date_keys = {d.date_str for d in verified_dates}
        for dd in det_dates:
            if dd.date_str not in existing_date_keys:
                verified_dates.append(dd)
                existing_date_keys.add(dd.date_str)

        verified_sections: List[SectionItem] = []
        for s in raw_payload.sections:
            src = verify_and_build_source(s)
            if src and s.section_number:
                act_str = (s.act or "").upper()
                if act_str == "IPC":
                    act_norm = "IPC"
                elif act_str == "BNS":
                    act_norm = "BNS"
                elif act_str == "CRPC":
                    act_norm = "CrPC"
                elif act_str == "BNSS":
                    act_norm = "BNSS"
                else:
                    act_norm = "other"
                verified_sections.append(SectionItem(act=act_norm, section_number=s.section_number, description=s.description or "Statutory section", source=src, confidence=s.confidence))

        # Merge deterministic sections
        existing_sec_keys = {(s.act, s.section_number) for s in verified_sections}
        for ds in det_sections:
            if (ds.act, ds.section_number) not in existing_sec_keys:
                verified_sections.append(ds)
                existing_sec_keys.add((ds.act, ds.section_number))

        verified_amounts: List[AmountItem] = []
        for a in raw_payload.amounts:
            src = verify_and_build_source(a)
            if src and a.value is not None:
                verified_amounts.append(AmountItem(value=float(a.value), currency=a.currency or "INR", context=a.context or "Transaction", source=src, confidence=a.confidence))

        # Merge deterministic amounts
        existing_amt_vals = {round(a.value, 2) for a in verified_amounts}
        for da in det_amounts:
            if round(da.value, 2) not in existing_amt_vals:
                verified_amounts.append(da)
                existing_amt_vals.add(round(da.value, 2))

        verified_locations: List[LocationItem] = []
        for loc_item in raw_payload.locations:
            src = verify_and_build_source(loc_item)
            if src and loc_item.place:
                verified_locations.append(LocationItem(place=loc_item.place, context=loc_item.context or "Location mentioned", source=src, confidence=loc_item.confidence))

        verified_incidents: List[IncidentItem] = []
        for inc in raw_payload.incidents:
            src = verify_and_build_source(inc)
            if src and inc.description:
                verified_incidents.append(IncidentItem(title=inc.title or "Incident", description=inc.description, date=inc.date_str, source=src, confidence=inc.confidence))

        # Merge deterministic incidents
        existing_inc_keys = {(inc.date, inc.description[:30].lower()) for inc in verified_incidents if inc.date}
        for dinc in det_incidents:
            key = (dinc.date, dinc.description[:30].lower())
            if key not in existing_inc_keys:
                verified_incidents.append(dinc)
                existing_inc_keys.add(key)

        legacy_facts: List[FactItem] = []
        for idx, cf in enumerate(raw_payload.candidate_facts):
            src = verify_and_build_source(cf)
            if src:
                verified_incidents.append(IncidentItem(
                    title=cf.category or "Fact",
                    description=cf.statement or cf.description or "",
                    date=cf.date_str,
                    source=src,
                    confidence=cf.confidence,
                ))
                legacy_facts.append(FactItem(
                    fact_id=cf.fact_id or f"FACT-{idx+1:03d}",
                    category=cf.category or "TRANSACTION",
                    statement=cf.statement or cf.description or "",
                    date_mentioned=cf.date_str,
                    source=src,
                ))

        verified_statements: List[StatementItem] = []
        for st in raw_payload.statements:
            src = verify_and_build_source(st)
            if src and st.content:
                st_type = st.statement_type if st.statement_type in ["161", "164", "complaint", "deposition", "other"] else "other"
                verified_statements.append(StatementItem(
                    statement_type=st_type,
                    speaker=st.speaker or "Witness",
                    role=st.role or "witness",
                    recorded_on=st.recorded_on,
                    recorded_by=st.recorded_by,
                    content=st.content,
                    source=src,
                    confidence=st.confidence,
                ))

        # Merge deterministic statements
        existing_stmt_keys = {(st.speaker.lower(), st.statement_type) for st in verified_statements}
        for dst in det_statements:
            s_key = (dst.speaker.lower(), dst.statement_type)
            if s_key not in existing_stmt_keys:
                verified_statements.append(dst)
                existing_stmt_keys.add(s_key)

        extracted_facts_obj = ExtractedFacts(
            parties=verified_parties,
            dates=verified_dates,
            sections=verified_sections,
            amounts=verified_amounts,
            locations=verified_locations,
            incidents=verified_incidents,
            statements=verified_statements,
            purpose=raw_payload.purpose,
            court=raw_payload.court,
            case_number=raw_payload.case_number,
        )

        # Backward-compatible list of generic FactItems
        if not legacy_facts:
            for idx, inc in enumerate(verified_incidents):
                legacy_facts.append(FactItem(
                    fact_id=f"FACT-INC-{idx+1:03d}",
                    category="INCIDENT",
                    statement=inc.description,
                    date_mentioned=inc.date,
                    source=inc.source,
                ))
            for idx, st in enumerate(verified_statements):
                legacy_facts.append(FactItem(
                    fact_id=f"FACT-ST-{idx+1:03d}",
                    category=f"STATEMENT_{st.statement_type}",
                    statement=f"{st.speaker} ({st.role}): {st.content}",
                    date_mentioned=st.recorded_on,
                    source=st.source,
                ))
            for idx, p in enumerate(verified_parties):
                legacy_facts.append(FactItem(
                    fact_id=f"FACT-PTY-{idx+1:03d}",
                    category="PARTY",
                    statement=f"{p.name} ({p.role})",
                    source=p.source,
                ))

        total_extracted = (
            len(verified_parties) + len(verified_dates) + len(verified_sections)
            + len(verified_amounts) + len(verified_locations) + len(verified_incidents)
            + len(verified_statements)
        )

        confidence = 0.90
        if rejected_count > 0:
            confidence = max(0.40, confidence - (0.08 * min(rejected_count, 5)))
            review_needed = True

        if total_extracted == 0:
            confidence = 0.20
            review_needed = True

        plaintiffs = [p.name for p in verified_parties if p.role.lower() in ["plaintiff", "complainant", "petitioner"]]
        if not plaintiffs and raw_payload.parties_plaintiff:
            plaintiffs = raw_payload.parties_plaintiff

        defendants = [p.name for p in verified_parties if p.role.lower() in ["defendant", "accused", "respondent"]]
        if not defendants and raw_payload.parties_defendant:
            defendants = raw_payload.parties_defendant

        court_val = raw_payload.court or raw_payload.court_name or det_court
        case_no_val = raw_payload.case_number or det_case_no

        engine_used = "rules" if review_needed else "llm"
        fallback_taken = review_needed
        status_val = "needs_review" if review_needed else "live_model"
        err_msg = "Language model unreachable: results incomplete (Rule-based extraction only)." if review_needed else None

        return DocumentExtractionOutput(
            document_id=input_data.document_id,
            detected_language=detected_lang,
            parties_plaintiff=plaintiffs,
            parties_defendant=defendants,
            court_name=court_val,
            case_number=case_no_val,
            facts=legacy_facts,
            extracted_facts=extracted_facts_obj,
            rejected_facts_count=rejected_count,
            confidence=round(confidence, 2),
            needs_human_review=review_needed,
            engine=engine_used,
            llm_called=not review_needed,
            fallback_taken=fallback_taken,
            status=status_val,
            error_message=err_msg,
            audit_notes=(
                f"Extracted {total_extracted} verified items across 7 categories via {engine_used}; "
                f"rejected {rejected_count} items failing anti-hallucination snippet checks."
            ),
        )
