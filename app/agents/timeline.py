"""Case-level Timeline and Limitation Analysis Agents for Indian legal proceedings.

Follows Requirement:
1. TimelineAgent:
   - Build a chronological list of events from facts across all documents (incidents,
     FIR registration, statement recording, arrests, filings, hearings, orders).
   - Normalize all date formats (dd/mm/yyyy, Hindi month names, "dated 5th of March").
   - Mark importance (high/medium/low) using a rules + LLM scoring step; high = the
     incident itself, arrest, FIR, chargesheet, victim/witness statements, bail/orders.
   - Flag date conflicts (same event with different dates in different docs).
   - Output Timeline with SourceRefs. Provide an API-ready JSON shape for a UI timeline
     (id, date, title, description, importance, doc_refs).

Follows Hard Rule 1: One class, typed Pydantic input/output, run() method, no hidden global state.
Follows Hard Rule 2: Every event backed by SourceRef.
Follows Hard Rule 3: Output carries confidence and needs_human_review.
"""

import json
import re
from typing import List, Literal, Optional, Dict, Any, Union, Tuple, Set
from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.schemas.common import BaseAgentInput
import logging

logger = logging.getLogger(__name__)
from app.schemas.source import SourceRef
from app.schemas.facts import ExtractedFacts, FactItem, DateItem, IncidentItem, StatementItem
from app.schemas.timeline import (
    ImportanceLevel,
    TimelineEvent,
    Timeline,
    DateConflictItem,
    UITimelineItem,
    LimitationCheck,
    TimelineAnalysisInput,
    TimelineAnalysisOutput,
)
from app.ingestion.date_normalizer import normalize_legal_date, format_display_date
from app.llm.client import LLMClient


class TimelineInput(BaseAgentInput):
    """Input for TimelineAgent operating at case level."""
    case_id: str
    db_session: Optional[Any] = None
    facts: Optional[List[Any]] = None
    extracted_facts: Optional[ExtractedFacts] = None
    document_id: Optional[str] = None


class _LLMScoredEventItem(BaseModel):
    event_id: str
    title: str
    description: str
    importance: ImportanceLevel = "MEDIUM"
    is_cause_of_action: bool = False


class _LLMTimelineScoringPayload(BaseModel):
    events: List[_LLMScoredEventItem] = Field(default_factory=list)
    confidence: float = 0.90


# -----------------------------------------------------------------------------
# Component 1: TimelineAgent (Case-Level Reasoning)
# -----------------------------------------------------------------------------
class TimelineAgent(BaseAgent[TimelineInput, Timeline]):
    """Constructs cross-document chronological timelines with date normalization, importance scoring, and conflict detection."""

    agent_name: str = "TimelineAgent"

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(llm_client=llm_client)

    def _execute(self, input_data: TimelineInput) -> Timeline:
        raw_events: List[Dict[str, Any]] = []

        # 1. Ingest facts from database session if provided
        if input_data.db_session is not None:
            raw_events.extend(self._load_facts_from_db(input_data.db_session, input_data.case_id))

        # 2. Ingest facts from direct arguments if provided
        if input_data.facts:
            raw_events.extend(self._extract_from_facts_list(input_data.facts, input_data.case_id))

        if input_data.extracted_facts:
            raw_events.extend(self._extract_from_extracted_facts(input_data.extracted_facts, input_data.case_id, input_data.document_id))

        # Fallback if no events provided
        if not raw_events:
            return Timeline(
                case_id=input_data.case_id,
                events=[],
                ui_timeline=[],
                date_conflicts=[],
                confidence=0.50,
                needs_human_review=True,
                audit_notes="No facts or dated events found for this case.",
            )

        # 3. Normalize all dates and score initial rule importance
        normalized_events: List[Dict[str, Any]] = []
        for idx, ev in enumerate(raw_events):
            raw_date = ev.get("date_str", "")
            norm_date, dt_obj = normalize_legal_date(raw_date)

            rule_imp = self._score_rule_importance(
                title=ev.get("title", ""),
                desc=ev.get("description", ""),
                category=ev.get("category", ""),
            )

            normalized_events.append({
                "event_id": ev.get("event_id") or f"EV-{idx + 1:03d}",
                "date_str": raw_date or (norm_date or "Undated"),
                "normalized_date": norm_date,
                "dt_obj": dt_obj,
                "title": ev.get("title", "Legal Event"),
                "description": ev.get("description", ""),
                "category": ev.get("category", "incident"),
                "importance": rule_imp,
                "source": ev.get("source"),
                "document_id": ev.get("document_id") or (ev.get("source").document_id if ev.get("source") else None),
            })

        # 4. LLM Refinement & Title Polishing Step
        refined_events, llm_called, fallback_taken = self._refine_events_with_llm(normalized_events)

        # 5. Sort chronologically (earliest first, undated at end)
        refined_events.sort(key=lambda x: (x["normalized_date"] is None, x["normalized_date"] or "9999-99-99"))

        # 6. Flag date conflicts (same event type with different dates across different docs)
        conflicts, conflict_event_ids, conflict_notes_map = self._detect_date_conflicts(refined_events)

        # 7. Build Pydantic models for TimelineEvent and UITimelineItem
        final_events: List[TimelineEvent] = []
        ui_items: List[UITimelineItem] = []

        for ev in refined_events:
            ev_id = ev["event_id"]
            norm_d = ev["normalized_date"]
            display_d = format_display_date(norm_d) if norm_d else ev["date_str"]
            is_conf = ev_id in conflict_event_ids
            c_note = conflict_notes_map.get(ev_id)

            t_ev = TimelineEvent(
                event_id=ev_id,
                date_str=ev["date_str"],
                normalized_date=norm_d,
                event_title=ev["title"],
                description=ev["description"],
                importance=ev["importance"],
                is_important=(ev["importance"] == "HIGH"),
                is_cause_of_action=bool(ev.get("is_cause_of_action", False)),
                document_id=ev["document_id"],
                source=ev["source"],
                confidence=0.90 if norm_d else 0.75,
            )
            final_events.append(t_ev)

            doc_refs = [ev["document_id"]] if ev["document_id"] else []
            snippet_list = [ev["source"].snippet] if (ev["source"] and ev["source"].snippet) else []

            ui_items.append(
                UITimelineItem(
                    id=ev_id,
                    date=norm_d or ev["date_str"],
                    display_date=display_d,
                    title=ev["title"],
                    description=ev["description"],
                    importance=ev["importance"],
                    doc_refs=doc_refs,
                    source_snippets=snippet_list,
                    is_conflict=is_conf,
                    conflict_notes=c_note,
                )
            )

        conf = 0.90 if not conflicts else 0.78
        needs_review = len(conflicts) > 0 or any(e.normalized_date is None for e in final_events)

        engine_used = "llm" if llm_called and not fallback_taken else "rules"
        status_val = "live_model" if engine_used == "llm" else "rule_based"
        err_msg = "Language model unreachable: events timeline constructed using rule-based date normalization." if fallback_taken else None

        logger.info(
            "AGENT_EXECUTION agent=TimelineAgent engine=%s llm_called=%s fallback_taken=%s",
            engine_used,
            llm_called,
            fallback_taken,
        )

        return Timeline(
            case_id=input_data.case_id,
            events=final_events,
            ui_timeline=ui_items,
            date_conflicts=conflicts,
            has_conflicts=len(conflicts) > 0,
            confidence=conf,
            needs_human_review=needs_review,
            engine=engine_used,
            llm_called=llm_called,
            fallback_taken=fallback_taken,
            status=status_val,
            error_message=err_msg,
            audit_notes=(
                f"Generated case timeline with {len(final_events)} chronological events; "
                f"flagged {len(conflicts)} date conflicts across documents."
            ),
        )

    @staticmethod
    def _score_rule_importance(title: str, desc: str, category: str) -> ImportanceLevel:
        """Deterministic importance scoring rule:

        HIGH: incident itself, arrest, FIR, chargesheet, witness/victim statements, bail/orders.
        MEDIUM: demand notice, summons, complaint filing, inspection, seizure.
        LOW: routine adjournment, administrative entry, diary entry.
        """
        combined = f"{title} {desc} {category}".lower()

        # HIGH importance keywords
        high_patterns = [
            r"\b(?:incident|occurrence|offence|theft|murder|fraud|cheating|assault|accident|robbery|dacoity)\b",
            r"\b(?:arrest|custody|remand|detention)\b",
            r"\b(?:fir|first\s+information\s+report|0142/\d+)\b",
            r"\b(?:chargesheet|charge\s*sheet|chalan)\b",
            r"\b(?:161\s*crpc|164\s*crpc|180\s*bnss|183\s*bnss|statement|deposition|bayan)\b",
            r"\b(?:bail|order|judgment|decree|cognizance|discharge|framing\s+of\s+charge)\b",
            r"(?:घटना|वारदात|धोखाधड़ी|गिरफ्तारी|हिरासत|प्राथमिकी|प्रथम\s*सूचना\s*रिपोर्ट|चालान|आरोप\s*पत्र|बयान|आदेश|जमानत)",
        ]
        if any(re.search(pat, combined) for pat in high_patterns):
            return "HIGH"

        # MEDIUM importance keywords
        medium_patterns = [
            r"\b(?:notice|demand\s+notice|summons|warrant|search|seizure|panchnama|site\s+plan|filing|complaint)\b",
            r"(?:सम्मन|वारंट|नोटिस|दायर|परिवाद|जब्ती|मौका\s*मुआयना)",
        ]
        if any(re.search(pat, combined) for pat in medium_patterns):
            return "MEDIUM"

        # LOW importance
        return "LOW"

    def _refine_events_with_llm(self, events: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool, bool]:
        """Optionally polish event titles and refine importance using LLM."""
        if not events:
            return events, False, False

        summary_lines = [
            f"- ID: {e['event_id']} | Date: {e['normalized_date'] or e['date_str']} | "
            f"RuleImportance: {e['importance']} | Title: {e['title']} | Desc: {e['description'][:100]}"
            for e in events[:15]
        ]
        prompt = (
            "Review the following legal case events, confirm or adjust importance (HIGH, MEDIUM, LOW), "
            "and provide concise judicial titles:\n\n"
            + "\n".join(summary_lines)
        )
        system = (
            "You are an Indian judicial clerk creating a master court timeline. "
            "Mark HIGH for the core incident, arrest, FIR, chargesheet, statements, and bail/orders. "
            "Return valid JSON matching the schema."
        )

        llm_called = False
        fallback_taken = True
        try:
            res, review_needed = self.llm.generate_structured(prompt=prompt, schema=_LLMTimelineScoringPayload, system=system)
            if not review_needed and res and getattr(res, "events", None):
                llm_called = True
                fallback_taken = False
                llm_map = {item.event_id: item for item in res.events}
                for ev in events:
                    if ev["event_id"] in llm_map:
                        item = llm_map[ev["event_id"]]
                        if item.importance == "HIGH" or ev["importance"] == "HIGH":
                            ev["importance"] = "HIGH"
                        else:
                            ev["importance"] = item.importance
                        if item.title:
                            ev["title"] = item.title
                        ev["is_cause_of_action"] = item.is_cause_of_action
        except Exception:
            llm_called = False
            fallback_taken = True

        return events, llm_called, fallback_taken

    def _detect_date_conflicts(
        self, events: List[Dict[str, Any]]
    ) -> Tuple[List[DateConflictItem], set, Dict[str, str]]:
        """Detect when the same event topic is assigned conflicting dates across different document records."""
        conflicts: List[DateConflictItem] = []
        conflict_event_ids = set()
        conflict_notes: Dict[str, str] = {}

        # Classify events into topical buckets
        def get_topic(e: Dict[str, Any]) -> str:
            text = f"{e['title']} {e['description']} {e.get('category', '')}".lower()
            if any(k in text for k in ["incident", "occurrence", "offence", "वारदात", "घटना", "cheating", "theft"]):
                return "OCCURRENCE"
            if any(k in text for k in ["arrest", "गिरफ्तारी", "custody"]):
                return "ARREST"
            if any(k in text for k in ["fir", "प्राथमिकी", "first information"]):
                return "FIR_REGISTRATION"
            if any(k in text for k in ["chargesheet", "चालान", "charge sheet"]):
                return "CHARGESHEET"
            return "GENERAL"

        grouped_by_topic: Dict[str, List[Dict[str, Any]]] = {}
        for ev in events:
            if ev.get("normalized_date"):
                t = get_topic(ev)
                if t != "GENERAL":
                    grouped_by_topic.setdefault(t, []).append(ev)

        # Check for cross-document date mismatch in each topical cluster
        for topic, ev_list in grouped_by_topic.items():
            if len(ev_list) < 2:
                continue
            for i in range(len(ev_list)):
                for j in range(i + 1, len(ev_list)):
                    e1 = ev_list[i]
                    e2 = ev_list[j]
                    doc1 = e1.get("document_id") or "doc_1"
                    doc2 = e2.get("document_id") or "doc_2"
                    d1 = e1["normalized_date"]
                    d2 = e2["normalized_date"]

                    # Conflict if different dates from different documents
                    if d1 != d2 and doc1 != doc2:
                        conflict_event_ids.add(e1["event_id"])
                        conflict_event_ids.add(e2["event_id"])
                        desc = (
                            f"Chronological conflict for '{topic}': Document '{doc1}' records date as {d1}, "
                            f"whereas Document '{doc2}' records date as {d2}."
                        )
                        conflict_notes[e1["event_id"]] = f"Discrepancy: {d2} in {doc2}"
                        conflict_notes[e2["event_id"]] = f"Discrepancy: {d1} in {doc1}"

                        conflicts.append(
                            DateConflictItem(
                                event_topic=topic,
                                event_title=e1["title"],
                                date_a=d1,
                                date_b=d2,
                                doc_id_a=doc1,
                                doc_id_b=doc2,
                                source_a=e1["source"],
                                source_b=e2["source"],
                                description=desc,
                            )
                        )

        return conflicts, conflict_event_ids, conflict_notes

    @staticmethod
    def _load_facts_from_db(session: Any, case_id: str) -> List[Dict[str, Any]]:
        """Load facts from SQLAlchemy session for the given case."""
        from app.db.models import FactModel
        items = []
        try:
            records = session.query(FactModel).filter(FactModel.case_id == case_id).all()
            for r in records:
                try:
                    data = json.loads(r.item_data)
                    s_data = json.loads(r.source_ref)
                    src = SourceRef(**s_data)
                    date_val = data.get("date_str") or data.get("date") or data.get("recorded_on")
                    if date_val:
                        items.append({
                            "event_id": f"DB-FACT-{r.id[:8]}",
                            "date_str": date_val,
                            "title": data.get("title") or f"{r.category.title()} Event",
                            "description": data.get("description") or data.get("statement") or data.get("content") or "",
                            "category": r.category,
                            "source": src,
                            "document_id": r.document_id,
                        })
                except Exception:
                    continue
        except Exception:
            pass
        return items

    @staticmethod
    def _extract_from_facts_list(facts_list: List[Any], case_id: str) -> List[Dict[str, Any]]:
        items = []
        for idx, f in enumerate(facts_list):
            if hasattr(f, "date_mentioned") and f.date_mentioned:
                items.append({
                    "event_id": getattr(f, "fact_id", f"EV-{idx+1:03d}"),
                    "date_str": f.date_mentioned,
                    "title": getattr(f, "category", "Fact"),
                    "description": getattr(f, "statement", ""),
                    "category": getattr(f, "category", "fact"),
                    "source": getattr(f, "source", None),
                    "document_id": getattr(f.source, "document_id", None) if getattr(f, "source", None) else None,
                })
            elif isinstance(f, dict):
                d_str = f.get("date_str") or f.get("date") or f.get("date_mentioned")
                if d_str:
                    src = f.get("source")
                    if isinstance(src, dict):
                        src = SourceRef(**src)
                    items.append({
                        "event_id": f.get("event_id", f"EV-{idx+1:03d}"),
                        "date_str": d_str,
                        "title": f.get("title") or f.get("category", "Event"),
                        "description": f.get("description") or f.get("statement", ""),
                        "category": f.get("category", "event"),
                        "source": src,
                        "document_id": f.get("document_id") or (src.document_id if src else None),
                    })
        return items

    @staticmethod
    def _extract_from_extracted_facts(ef: ExtractedFacts, case_id: str, doc_id: Optional[str]) -> List[Dict[str, Any]]:
        items = []
        for idx, d in enumerate(ef.dates):
            items.append({
                "event_id": f"DATE-{idx+1:03d}",
                "date_str": d.date_str,
                "title": "Date of Record",
                "description": d.description,
                "category": "date",
                "source": d.source,
                "document_id": doc_id or d.source.document_id,
            })
        for idx, inc in enumerate(ef.incidents):
            if inc.date:
                items.append({
                    "event_id": f"INC-{idx+1:03d}",
                    "date_str": inc.date,
                    "title": inc.title,
                    "description": inc.description,
                    "category": "incident",
                    "source": inc.source,
                    "document_id": doc_id or inc.source.document_id,
                })
        for idx, st in enumerate(ef.statements):
            if st.recorded_on:
                items.append({
                    "event_id": f"ST-{idx+1:03d}",
                    "date_str": st.recorded_on,
                    "title": f"Statement of {st.speaker} ({st.statement_type})",
                    "description": f"Recorded by {st.recorded_by or 'IO'}: {st.content[:150]}",
                    "category": "statement",
                    "source": st.source,
                    "document_id": doc_id or st.source.document_id,
                })
        return items


# -----------------------------------------------------------------------------
# Limitation Timeline Agent (Backward Compatible)
# -----------------------------------------------------------------------------
class _LLMLimitationResponse(BaseModel):
    cause_of_action_identified: Optional[str] = None
    events: List[dict] = Field(default_factory=list)
    limitation_assessments: List[dict] = Field(default_factory=list)
    has_limitation_risk: bool = False
    confidence: float = 0.85


class LimitationTimelineAgent(BaseAgent[TimelineAnalysisInput, TimelineAnalysisOutput]):
    """Analyzes chronological events, causes of action, and statutory limitation under Indian law."""

    agent_name: str = "LimitationTimelineAgent"

    def _execute(self, input_data: TimelineAnalysisInput) -> TimelineAnalysisOutput:
        facts_summary = "\n".join([
            f"- [{f.fact_id}] Date: {f.date_mentioned or 'Undated'} | Category: {f.category} | Statement: {f.statement}"
            for f in input_data.facts
        ])

        prompt = (
            f"Analyze the following verified facts from document {input_data.document_id} to construct:\n"
            f"1. A chronological sequence of legally significant events\n"
            f"2. Identification of the primary cause of action date\n"
            f"3. Statutory limitation analysis under Indian laws (e.g., Limitation Act 1963, "
            f"Section 138 NI Act, Commercial Courts Act 2015)\n\n"
            f"Verified Facts:\n{facts_summary or 'No verified facts provided.'}\n"
        )

        system = (
            "You are a specialized Indian legal procedure expert evaluating statutory limitation periods. "
            "Analyze limitation strictly under the Indian Limitation Act 1963 and relevant special statutes."
        )

        llm_response, review_needed = self.llm.generate_structured(
            prompt=prompt,
            schema=_LLMLimitationResponse,
            system=system,
        )

        timeline_events: List[TimelineEvent] = []
        fact_by_id = {f.fact_id: f for f in input_data.facts}

        for idx, ev in enumerate(getattr(llm_response, "events", []) or []):
            ref_fact_id = ev.get("fact_id")
            source = None
            if ref_fact_id and ref_fact_id in fact_by_id:
                source = fact_by_id[ref_fact_id].source
            elif input_data.facts:
                source = input_data.facts[min(idx, len(input_data.facts) - 1)].source

            if source:
                timeline_events.append(
                    TimelineEvent(
                        event_id=ev.get("event_id", f"EV-{idx + 1:03d}"),
                        date_str=ev.get("date_str", "Undated"),
                        event_title=ev.get("event_title", "Legal Event"),
                        description=ev.get("description", ""),
                        is_cause_of_action=bool(ev.get("is_cause_of_action", False)),
                        source=source,
                    )
                )

        # Deterministic chronological event construction if LLM did not provide events
        if not timeline_events and input_data.facts:
            for idx, f in enumerate(input_data.facts):
                d_str = getattr(f, "date_mentioned", None) or "Undated"
                is_coa = idx == 0 or "incident" in (getattr(f, "category", "") or "").lower()
                timeline_events.append(
                    TimelineEvent(
                        event_id=getattr(f, "fact_id", f"EV-{idx+1:03d}"),
                        date_str=d_str,
                        event_title=getattr(f, "category", "Legal Event"),
                        description=getattr(f, "statement", ""),
                        is_cause_of_action=is_coa,
                        source=f.source,
                    )
                )

        limitation_checks: List[LimitationCheck] = []
        has_risk = getattr(llm_response, "has_limitation_risk", False) or False
        coa_identified = getattr(llm_response, "cause_of_action_identified", None)

        for lim in getattr(llm_response, "limitation_assessments", []) or []:
            try:
                check = LimitationCheck(
                    statute=lim.get("statute", "Limitation Act 1963"),
                    section_or_article=lim.get("section_or_article", "Article 55"),
                    prescribed_period=lim.get("prescribed_period", "3 years"),
                    cause_of_action_date=lim.get("cause_of_action_date"),
                    limitation_expiry_date=lim.get("limitation_expiry_date"),
                    is_time_barred=bool(lim.get("is_time_barred", False)),
                    delay_condonation_applicable=bool(lim.get("delay_condonation_applicable", True)),
                    legal_basis=lim.get("legal_basis", "Statutory period calculated from cause of action date."),
                )
                limitation_checks.append(check)
            except Exception:
                continue

        # Deterministic Limitation Act 1963 assessment if not generated
        if not limitation_checks and timeline_events:
            coa_event = next((e for e in timeline_events if e.is_cause_of_action and e.date_str != "Undated"), None)
            if not coa_event:
                coa_event = next((e for e in timeline_events if e.date_str != "Undated"), None)

            if coa_event:
                norm_iso, dt_obj = normalize_legal_date(coa_event.date_str)
                if not coa_identified:
                    coa_identified = norm_iso or coa_event.date_str
                if dt_obj:
                    from datetime import datetime, timedelta
                    expiry_dt = dt_obj + timedelta(days=3 * 365)
                    now_dt = datetime.now()
                    is_barred = now_dt > expiry_dt
                    delay_days = (now_dt - expiry_dt).days if is_barred else 0
                    if is_barred:
                        has_risk = True
                    limitation_checks.append(
                        LimitationCheck(
                            statute="Limitation Act 1963",
                            section_or_article="Article 55 (Breach of Contract / Civil Wrong)",
                            prescribed_period="3 years from cause of action",
                            cause_of_action_date=norm_iso or coa_event.date_str,
                            limitation_expiry_date=expiry_dt.strftime("%Y-%m-%d"),
                            is_time_barred=is_barred,
                            delay_condonation_applicable=True,
                            legal_basis=(
                                f"Limitation period of 3 years under Limitation Act 1963 computed from {norm_iso or coa_event.date_str}. "
                                f"{f'Action is time-barred by {delay_days} days; Section 5 condonation application required.' if is_barred else 'Action is within statutory limitation.'}"
                            ),
                        )
                    )

        reported_conf = float(getattr(llm_response, "confidence", 0.85) or 0.85)
        llm_called = not review_needed
        fallback_taken = review_needed
        engine_used = "llm" if llm_called else "rules"
        status_val = "live_model" if llm_called else "needs_review"
        err_msg = "Language model unreachable: statutory limitation evaluated using rule-based heuristics only." if fallback_taken else None

        logger.info(
            "AGENT_EXECUTION agent=LimitationTimelineAgent engine=%s llm_called=%s fallback_taken=%s",
            engine_used,
            llm_called,
            fallback_taken,
        )

        return TimelineAnalysisOutput(
            document_id=input_data.document_id,
            events_chronological=timeline_events,
            cause_of_action_identified=coa_identified,
            limitation_assessments=limitation_checks,
            has_limitation_risk=has_risk,
            confidence=round(reported_conf, 2),
            needs_human_review=review_needed or has_risk,
            engine=engine_used,
            llm_called=llm_called,
            fallback_taken=fallback_taken,
            status=status_val,
            error_message=err_msg,
        )
