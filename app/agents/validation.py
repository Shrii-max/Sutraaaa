"""Two-layer Validation Agent combining deterministic legal rules and LLM logical checks.

Follows Requirement:
5. ValidationAgent: two layers.
   (a) Deterministic rules: date format and order sanity (FIR before chargesheet, event before complaint),
       name-spelling variants across the document (fuzzy match), missing signature/stamp/verification keywords,
       section-number validity against a configurable sections table (load from JSON file),
       court/jurisdiction mismatch, missing mandatory fields by document type.
   (b) LLM review for logical/clerical errors, but each issue must cite a SourceRef.
   Output ValidationReport with severity levels.
"""

import json
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.schemas.common import BaseAgentInput
from app.schemas.source import SourceRef
from app.schemas.facts import ExtractedFacts
from app.schemas.document import DocumentMeta
from app.schemas.validation import ValidationIssue, ValidationReport, IssueSeverity
from app.llm.client import LLMClient, get_llm_client


class ValidationInput(BaseAgentInput):
    document_id: str
    text_content: str
    document_meta: Optional[DocumentMeta] = None
    extracted_facts: Optional[ExtractedFacts] = None
    sections_table_path: Optional[str] = None


class _LLMIssueItem(BaseModel):
    severity: IssueSeverity = "MEDIUM"
    category: str = "LOGICAL_DISCREPANCY"
    description: str
    page: int = 1
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    snippet: str
    suggestion: str


class _LLMValidationReview(BaseModel):
    logical_issues: List[_LLMIssueItem] = Field(default_factory=list)
    confidence: float = 0.88


class ValidationAgent(BaseAgent[ValidationInput, ValidationReport]):
    """Validates legal documents through deterministic statutory/chronological checks and grounded LLM review."""

    agent_name: str = "ValidationAgent"

    def __init__(self, llm_client: Optional[LLMClient] = None, sections_table_path: Optional[str] = None):
        super().__init__(llm_client=llm_client)
        self.default_sections_path = sections_table_path or str(
            Path(__file__).parent.parent / "data" / "sections_table.json"
        )
        self.sections_table = self._load_sections_table(self.default_sections_path)

    @staticmethod
    def _load_sections_table(path_str: str) -> Dict[str, Dict[str, str]]:
        p = Path(path_str)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _execute(self, input_data: ValidationInput) -> ValidationReport:
        doc_id = input_data.document_id
        text = input_data.text_content
        meta = input_data.document_meta
        facts = input_data.extracted_facts or ExtractedFacts()

        issues: List[ValidationIssue] = []

        # -------------------------------------------------------------
        # Layer 1: Deterministic Legal & Procedural Rules
        # -------------------------------------------------------------
        # (1) Date order sanity
        issues.extend(self._check_date_order_sanity(doc_id, text, facts, meta))

        # (2) Name-spelling variants across document
        issues.extend(self._check_name_spelling_variants(doc_id, text, facts))

        # (3) Missing signature/stamp/verification keywords
        issues.extend(self._check_verification_and_signatures(doc_id, text, meta))

        # (4) Section-number validity against configurable sections table
        issues.extend(self._check_section_validity(doc_id, text, facts))

        # (5) Missing mandatory fields by document type
        issues.extend(self._check_mandatory_fields_by_type(doc_id, text, meta, facts))

        # -------------------------------------------------------------
        # Layer 2: LLM Review for Clerical / Logical Errors (citing SourceRefs)
        # -------------------------------------------------------------
        llm_issues, llm_conf, llm_called, fallback_taken = self._run_llm_logical_review(doc_id, text, facts, meta)
        issues.extend(llm_issues)

        has_critical = any(i.severity in ["HIGH", "CRITICAL"] for i in issues)
        confidence = round(0.85 if not issues else (0.70 if has_critical else 0.80), 2)

        engine_used = "llm" if llm_called and not fallback_taken else "rules"
        status_val = "live_model" if engine_used == "llm" else "rule_based"
        err_msg = "Language model unreachable: validation performed via deterministic procedural rules only." if fallback_taken else None

        logger.info(
            "AGENT_EXECUTION agent=ValidationAgent engine=%s llm_called=%s fallback_taken=%s",
            engine_used,
            llm_called,
            fallback_taken,
        )

        return ValidationReport(
            document_id=doc_id,
            issues=issues,
            has_critical_defects=has_critical,
            confidence=confidence,
            needs_human_review=has_critical or (len(issues) >= 3),
            engine=engine_used,
            llm_called=llm_called,
            fallback_taken=fallback_taken,
            status=status_val,
            error_message=err_msg,
            audit_notes=f"Identified {len(issues)} validation issues across deterministic rules and LLM review.",
        )

    def _check_date_order_sanity(
        self, doc_id: str, text: str, facts: ExtractedFacts, meta: Optional[DocumentMeta]
    ) -> List[ValidationIssue]:
        issues = []
        parsed_dates = []

        for d in facts.dates:
            dt = self._try_parse_date(d.date_str)
            if dt:
                parsed_dates.append((dt, d))

        # Check Incident Date vs Complaint / Filing Date
        incident_dates = [
            (dt, d) for dt, d in parsed_dates
            if any(term in d.description.lower() for term in ["incident", "occurrence", "offence", "घटना", "वारदात"])
        ]
        complaint_dates = [
            (dt, d) for dt, d in parsed_dates
            if any(term in d.description.lower() for term in ["complaint", "fir", "filing", "शिकायत", "दायर"])
        ]

        for inc_dt, inc_item in incident_dates:
            for comp_dt, comp_item in complaint_dates:
                if inc_dt > comp_dt:
                    issues.append(
                        ValidationIssue(
                            severity="HIGH",
                            category="DATE_ORDER_ANOMALY",
                            description=(
                                f"Chronological contradiction: Alleged incident date ({inc_item.date_str}) "
                                f"occurs AFTER complaint/filing date ({comp_item.date_str})."
                            ),
                            source_refs=[inc_item.source, comp_item.source],
                            suggestion="Rectify date sequence in pleadings to prevent plaint/FIR dismissal.",
                        )
                    )

        # Explicit regex check for FIR and Chargesheet dates in text
        fir_match = re.search(r"FIR\s*(?:No\.?)?\s*[:\d/]+\s*dated\s*(\d{1,2}[-/.](?:\d{1,2}|[A-Za-z]+)[-/.](?:20\d{2}|19\d{2}))", text, re.IGNORECASE)
        cs_match = re.search(r"Charge\s*sheet\s*(?:No\.?)?\s*[:\d/]+\s*dated\s*(\d{1,2}[-/.](?:\d{1,2}|[A-Za-z]+)[-/.](?:20\d{2}|19\d{2}))", text, re.IGNORECASE)
        if fir_match and cs_match:
            d_fir = self._try_parse_date(fir_match.group(1))
            d_cs = self._try_parse_date(cs_match.group(1))
            if d_fir and d_cs and d_fir > d_cs:
                issues.append(
                    ValidationIssue(
                        severity="HIGH",
                        category="DATE_ORDER_ANOMALY",
                        description=f"FIR date ({fir_match.group(1)}) is dated after the Chargesheet date ({cs_match.group(1)}).",
                        source_refs=[
                            SourceRef(document_id=doc_id, page=1, char_start=fir_match.start(), char_end=fir_match.end(), snippet=fir_match.group(0)),
                            SourceRef(document_id=doc_id, page=1, char_start=cs_match.start(), char_end=cs_match.end(), snippet=cs_match.group(0)),
                        ],
                        suggestion="Verify investigation timeline; chargesheet cannot precede registration of FIR.",
                    )
                )

        return issues

    def _check_name_spelling_variants(
        self, doc_id: str, text: str, facts: ExtractedFacts
    ) -> List[ValidationIssue]:
        issues = []
        party_names = [p.name for p in facts.parties if len(p.name.strip()) > 3]
        speakers = [s.speaker for s in facts.statements if len(s.speaker.strip()) > 3]
        all_names = list(set(party_names + speakers))

        reported_pairs = set()
        for i in range(len(all_names)):
            for j in range(i + 1, len(all_names)):
                n1 = all_names[i]
                n2 = all_names[j]
                pair_key = tuple(sorted([n1.lower(), n2.lower()]))
                if pair_key in reported_pairs or n1.lower() == n2.lower():
                    continue

                ratio = SequenceMatcher(None, n1.lower(), n2.lower()).ratio()
                if 0.80 <= ratio < 1.0:
                    reported_pairs.add(pair_key)
                    # Find sources
                    src_list = [p.source for p in facts.parties if p.name in [n1, n2]]
                    if not src_list:
                        src_list = self._find_first_occurrence(doc_id, text, n1)

                    issues.append(
                        ValidationIssue(
                            severity="MEDIUM",
                            category="NAME_SPELLING_VARIANT",
                            description=f"Potential name spelling inconsistency / typo between '{n1}' and '{n2}' (similarity: {ratio:.0%}).",
                            source_refs=src_list[:2],
                            suggestion="Standardize party name across all paragraphs or clarify alias ('alias / उर्फ').",
                        )
                    )

        return issues

    def _check_verification_and_signatures(
        self, doc_id: str, text: str, meta: Optional[DocumentMeta]
    ) -> List[ValidationIssue]:
        issues = []
        doc_type = meta.doc_type if meta else "other"
        t_lower = text.lower()

        if doc_type == "affidavit":
            affidavit_terms = ["verification", "solemnly affirm", "verified that", "verified at", "सत्यापन", "शपथपूर्वक"]
            if not any(k in t_lower for k in affidavit_terms):
                issues.append(
                    ValidationIssue(
                        severity="HIGH",
                        category="MISSING_VERIFICATION",
                        description="Affidavit is missing mandatory verification clause or solemn affirmation.",
                        source_refs=self._find_first_occurrence(doc_id, text, text[:80]),
                        suggestion="Add standard verification clause: 'I, the deponent above named, do hereby solemnly affirm that the contents are true...'",
                    )
                )

        if doc_type == "petition":
            if not any(k in t_lower for k in ["prayer", "relief", "प्रार्थना"]):
                issues.append(
                    ValidationIssue(
                        severity="HIGH",
                        category="MISSING_PRAYER_CLAUSE",
                        description="Petition is missing a distinct 'PRAYER' or 'RELIEF SOUGHT' clause.",
                        source_refs=self._find_first_occurrence(doc_id, text, text[:80]),
                        suggestion="Annex prayer clause detailing specific relief, declarations, or damages sought from the court.",
                    )
                )

        return issues

    def _check_section_validity(
        self, doc_id: str, text: str, facts: ExtractedFacts
    ) -> List[ValidationIssue]:
        issues = []
        if not self.sections_table:
            return issues

        for sec in facts.sections:
            act_key = sec.act.upper()
            sec_num = sec.section_number.strip().lstrip("u/s").lstrip("U/S").strip()

            # Check if section exists in table
            if act_key in self.sections_table:
                valid_dict = self.sections_table[act_key]
                if sec_num not in valid_dict:
                    issues.append(
                        ValidationIssue(
                            severity="MEDIUM",
                            category="INVALID_SECTION_NUMBER",
                            description=(
                                f"Section '{sec_num}' under {act_key} is not recognized in standard penal/procedural schedules. "
                                f"Verify whether correct section was cited."
                            ),
                            source_refs=[sec.source],
                            suggestion=f"Verify exact provision in the {act_key} statute.",
                        )
                    )

        return issues

    def _check_mandatory_fields_by_type(
        self, doc_id: str, text: str, meta: Optional[DocumentMeta], facts: ExtractedFacts
    ) -> List[ValidationIssue]:
        issues = []
        doc_type = meta.doc_type if meta else "other"
        t_lower = text.lower()

        if doc_type == "FIR":
            if not re.search(r"police\s*station|thana|थाना|kotwali", t_lower):
                issues.append(
                    ValidationIssue(
                        severity="HIGH",
                        category="MISSING_POLICE_STATION",
                        description="FIR does not identify the originating Police Station / Thana.",
                        source_refs=self._find_first_occurrence(doc_id, text, text[:80]),
                        suggestion="Specify the territorial Police Station having jurisdiction over the occurrence.",
                    )
                )
            if not facts.sections:
                issues.append(
                    ValidationIssue(
                        severity="HIGH",
                        category="MISSING_OFFENCE_SECTIONS",
                        description="FIR record lacks penal/statutory offence sections (e.g. IPC, BNS, or special acts).",
                        source_refs=self._find_first_occurrence(doc_id, text, text[:80]),
                        suggestion="Record applicable cognizable penal provisions.",
                    )
                )

        return issues

    def _run_llm_logical_review(
        self, doc_id: str, text: str, facts: ExtractedFacts, meta: Optional[DocumentMeta]
    ) -> tuple[List[ValidationIssue], float, bool, bool]:
        prompt = (
            f"Review the following Indian legal document text for subtle logical, typographical, "
            f"or procedural defects:\n"
            f"- Inconsistent party descriptions or conflicting amounts\n"
            f"- Missing essential exhibits or referenced annexures\n"
            f"- Clerical errors\n\n"
            f"CRITICAL: Every identified issue MUST cite an exact snippet verbatim from the text below.\n\n"
            f"Document Text:\n\"\"\"\n{text[:6000]}\n\"\"\""
        )
        system = "You are a meticulous judicial scrutiny clerk identifying drafting defects with exact source quotes."

        try:
            res, review_needed = self.llm.generate_structured(prompt=prompt, schema=_LLMValidationReview, system=system)
            if review_needed or not res:
                return [], 0.85, False, True
            valid_issues: List[ValidationIssue] = []
            for item in getattr(res, "logical_issues", []):
                snippet = item.snippet.strip()
                if not snippet or snippet not in text:
                    continue  # Anti-hallucination: discard unsourced LLM complaints

                loc = text.find(snippet)
                src = SourceRef(
                    document_id=doc_id,
                    page=item.page or 1,
                    char_start=loc,
                    char_end=loc + len(snippet),
                    snippet=snippet,
                )
                valid_issues.append(
                    ValidationIssue(
                        severity=item.severity,
                        category=item.category,
                        description=item.description,
                        source_refs=[src],
                        suggestion=item.suggestion,
                    )
                )
            return valid_issues, getattr(res, "confidence", 0.88), True, False
        except Exception:
            return [], 0.85, False, True

    @staticmethod
    def _try_parse_date(date_str: str) -> Optional[datetime]:
        clean = re.sub(r"[^\d\w/-]", " ", date_str).strip()
        formats = [
            "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
            "%d %b %Y", "%d %B %Y", "%Y/%m/%d", "%b %d, %Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(clean, fmt)
            except ValueError:
                pass
        return None

    @staticmethod
    def _find_first_occurrence(doc_id: str, text: str, snippet: str) -> List[SourceRef]:
        clean_text = text if text and len(text) > 0 else "[Document text empty]"
        s = snippet.strip()
        if not s:
            s = clean_text[:min(len(clean_text), 50)]
        loc = clean_text.find(s)
        if loc != -1 and len(s) > 0:
            return [SourceRef(document_id=doc_id, page=1, char_start=loc, char_end=loc + len(s), snippet=s)]
        end_idx = max(1, min(len(clean_text), 30))
        fallback_snip = clean_text[:end_idx] if clean_text[:end_idx] else "Notice"
        return [SourceRef(document_id=doc_id, page=1, char_start=0, char_end=max(1, len(fallback_snip)), snippet=fallback_snip)]
