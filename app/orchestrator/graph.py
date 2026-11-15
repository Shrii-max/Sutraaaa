"""LangGraph multi-agent orchestrator for legal intelligence workflows.

Orchestrates FactExtractionAgent, LimitationTimelineAgent, PrecedentAnalysisAgent,
and LegalRiskAgent using state transitions while enforcing Hard Rules 1-5, 9, 10.
"""

import uuid
from typing import Optional
from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, START, END

from app.orchestrator.state import LegalIntelligenceState
from app.agents.fact_extraction import FactExtractionAgent
from app.agents.timeline import LimitationTimelineAgent
from app.agents.precedent import PrecedentAnalysisAgent
from app.agents.legal_risk import LegalRiskAgent
from app.schemas.facts import DocumentExtractionInput
from app.schemas.timeline import TimelineAnalysisInput
from app.schemas.precedent import PrecedentSearchInput
from app.schemas.risks import RiskAnalysisInput
from app.schemas.dossier import LegalIntelligenceReport
from app.security.audit import record_audit_event
from app.config import get_settings


def create_agent_nodes(db_session: Session, llm_client=None):
    """Factory creating individual node functions bound to session and LLM client."""
    fact_agent = FactExtractionAgent(llm_client=llm_client)
    timeline_agent = LimitationTimelineAgent(llm_client=llm_client)
    precedent_agent = PrecedentAnalysisAgent(db_session=db_session, llm_client=llm_client)
    risk_agent = LegalRiskAgent(llm_client=llm_client)

    def extract_facts_node(state: LegalIntelligenceState) -> LegalIntelligenceState:
        doc_id = state["document_id"]
        inp = DocumentExtractionInput(
            document_id=doc_id,
            filename=state.get("filename", "unknown.pdf"),
            text_content=state["raw_text"],
            request_id=doc_id,
        )
        extraction = fact_agent.run(inp)
        state["extraction_output"] = extraction
        return state

    def analyze_timeline_node(state: LegalIntelligenceState) -> LegalIntelligenceState:
        extraction = state.get("extraction_output")
        facts = extraction.facts if extraction else []
        inp = TimelineAnalysisInput(
            document_id=state["document_id"],
            facts=facts,
            request_id=state["document_id"],
        )
        timeline = timeline_agent.run(inp)
        state["timeline_output"] = timeline
        return state

    def retrieve_precedents_node(state: LegalIntelligenceState) -> LegalIntelligenceState:
        extraction = state.get("extraction_output")
        timeline = state.get("timeline_output")

        # Build targeted legal issue search query
        query_parts = []
        if timeline and timeline.cause_of_action_identified:
            query_parts.append(timeline.cause_of_action_identified)
        if extraction:
            for f in extraction.facts[:3]:
                query_parts.append(f.statement)
        query_text = " ".join(query_parts) or state["raw_text"][:200]

        inp = PrecedentSearchInput(
            query_text=query_text,
            top_k=3,
            request_id=state["document_id"],
        )
        precedents = precedent_agent.run(inp)
        state["precedent_output"] = precedents
        return state

    def evaluate_risks_node(state: LegalIntelligenceState) -> LegalIntelligenceState:
        extraction = state.get("extraction_output")
        timeline = state.get("timeline_output")
        facts = extraction.facts if extraction else []

        inp = RiskAnalysisInput(
            document_id=state["document_id"],
            facts=facts,
            timeline_analysis=timeline,
            request_id=state["document_id"],
        )
        risks = risk_agent.run(inp)
        state["risk_output"] = risks
        return state

    def synthesize_dossier_node(state: LegalIntelligenceState) -> LegalIntelligenceState:
        settings = get_settings()
        extraction = state["extraction_output"]
        timeline = state["timeline_output"]
        precedents = state["precedent_output"]
        risks = state["risk_output"]

        # Calculate composite confidence
        conf_scores = [
            extraction.confidence,
            timeline.confidence,
            precedents.confidence,
            risks.confidence,
        ]
        composite_conf = sum(conf_scores) / len(conf_scores)

        # Flag human review if any agent flagged it or if overall confidence < threshold
        needs_review = (
            extraction.needs_human_review
            or timeline.needs_human_review
            or precedents.needs_human_review
            or risks.needs_human_review
            or (composite_conf < settings.CONFIDENCE_THRESHOLD)
        )

        # Generate actionable strategic recommendations for counsel
        recommendations = []
        if risks.procedural_defects_found:
            recommendations.append("Address identified procedural defects before filing or next listed hearing.")
        if timeline.has_limitation_risk:
            recommendations.append(
                "Prepare Section 5 Limitation Act condonation of delay application with supporting affidavit."
            )
        if risks.evidence_defects_found:
            recommendations.append(
                "Procure Section 65B Indian Evidence Act / Section 63 BSA certificate for electronic communications."
            )
        if precedents.matches:
            top_case = precedents.matches[0].case
            recommendations.append(f"Rely on binding ratio in {top_case.case_title} ({top_case.citation}).")
        else:
            recommendations.append("Local database returned 'not found' for exact matching precedents; expand query.")

        audit_id = str(uuid.uuid4())
        summary_text = (
            f"Matter concerning {', '.join(extraction.parties_plaintiff) or 'Claimants'} v. "
            f"{', '.join(extraction.parties_defendant) or 'Opposite Parties'} in "
            f"{extraction.court_name or 'appropriate jurisdiction'}. "
            f"Identified {len(extraction.facts)} verifiable factual claims with primary cause of action "
            f"'{timeline.cause_of_action_identified or 'unspecified'}'. Overall risk evaluated as {risks.overall_risk_level}."
        )

        final_report = LegalIntelligenceReport(
            case_summary=summary_text,
            document_extraction=extraction,
            timeline_analysis=timeline,
            precedents=precedents,
            risk_assessment=risks,
            strategic_recommendations=recommendations,
            audit_trace_id=audit_id,
            confidence=round(composite_conf, 2),
            needs_human_review=needs_review,
            disclaimer=settings.DISCLAIMER_TEXT,
            audit_notes=f"Synthesized from 4 agents with composite confidence {composite_conf:.2f}.",
        )
        state["final_report"] = final_report
        state["audit_trace_id"] = audit_id

        # Hard Rule 5: Append-only audit record for overall orchestration
        record_audit_event(
            event_type="ORCHESTRATION_SYNTHESIS",
            actor="orchestrator:LegalOrchestrator",
            resource_id=state["document_id"],
            input_payload={"filename": state.get("filename"), "doc_id": state["document_id"]},
            output_payload={"audit_trace_id": audit_id, "confidence": composite_conf, "needs_review": needs_review},
            confidence=composite_conf,
            needs_human_review=needs_review,
            status="SUCCESS",
        )
        return state

    return (
        extract_facts_node,
        analyze_timeline_node,
        retrieve_precedents_node,
        evaluate_risks_node,
        synthesize_dossier_node,
    )


def build_legal_intelligence_graph(db_session: Session, llm_client=None):
    """Constructs and compiles the LangGraph StateGraph pipeline."""
    nodes = create_agent_nodes(db_session=db_session, llm_client=llm_client)
    extract_n, timeline_n, precedent_n, risk_n, synth_n = nodes

    workflow = StateGraph(LegalIntelligenceState)

    workflow.add_node("extract_facts", extract_n)
    workflow.add_node("analyze_timeline", timeline_n)
    workflow.add_node("retrieve_precedents", precedent_n)
    workflow.add_node("evaluate_risks", risk_n)
    workflow.add_node("synthesize_dossier", synth_n)

    # Graph edge flow
    workflow.add_edge(START, "extract_facts")
    workflow.add_edge("extract_facts", "analyze_timeline")
    workflow.add_edge("analyze_timeline", "retrieve_precedents")
    workflow.add_edge("retrieve_precedents", "evaluate_risks")
    workflow.add_edge("evaluate_risks", "synthesize_dossier")
    workflow.add_edge("synthesize_dossier", END)

    return workflow.compile()


class LegalOrchestrator:
    """Entry point for executing the LangGraph legal intelligence pipeline."""

    def __init__(self, db_session: Session, llm_client=None):
        self.session = db_session
        self.llm_client = llm_client
        self.app = build_legal_intelligence_graph(db_session=db_session, llm_client=llm_client)

    def analyze_document(
        self,
        document_id: str,
        raw_text: str,
        filename: str = "document.pdf",
    ) -> LegalIntelligenceReport:
        """Execute full multi-agent pipeline on an ingested legal document."""
        initial_state: LegalIntelligenceState = {
            "document_id": document_id,
            "filename": filename,
            "raw_text": raw_text,
            "errors": [],
        }

        result_state = self.app.invoke(initial_state)
        report = result_state.get("final_report")
        if not report:
            raise RuntimeError(f"Orchestration failed to produce report: {result_state.get('errors')}")
        return report


# =============================================================================
# Phase 5: ProcessingOrchestrator (Multi-Agent Document & Case Orchestration)
# =============================================================================
import time
import json
import logging
from typing import TypedDict, Dict, Any, List
from sqlalchemy import select

from app.llm.client import get_llm_client
from app.agents.ocr import OCRAgent
from app.agents.language_detection import LanguageDetectionAgent
from app.agents.document_classifier import DocumentClassifierAgent, DocumentClassifierInput
from app.agents.fact_extraction import FactExtractionAgent, DocumentExtractionInput
from app.agents.validation import ValidationAgent, ValidationInput
from app.agents.summary import SummaryAgent, SummaryInput
from app.agents.timeline import TimelineAgent, TimelineInput
from app.agents.contradiction import ContradictionAgent, ContradictionInput
from app.agents.similar_case import SimilarCaseAgent, SimilarCaseInput
from app.schemas.document import PageOCR, OCRResult, LanguageResult, DocumentMeta
from app.schemas.facts import ExtractedFacts, FactItem, StatementItem
from app.schemas.validation import ValidationReport
from app.schemas.summary import CaseSummary
from app.db.models import (
    DocumentModel,
    DocumentPageModel,
    FactModel,
    ValidationIssueModel,
    SummaryModel,
    TimelineEventModel,
    ContradictionModel,
    ProcessingStepModel,
)
from app.security.crypto import decrypt_bytes

logger = logging.getLogger(__name__)


class DocumentProcessingState(TypedDict, total=False):
    """Execution state for Document Processing LangGraph pipeline."""
    document_id: str
    case_id: Optional[str]
    filename: str
    file_bytes: Optional[bytes]
    raw_text: Optional[str]
    ocr_result: Optional[Dict[str, Any]]
    language_result: Optional[Dict[str, Any]]
    classifier_result: Optional[Dict[str, Any]]
    facts_result: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]
    summary_result: Optional[Dict[str, Any]]
    confidence: float
    needs_human_review: bool
    status: str
    errors: List[str]


class ProcessingOrchestrator:
    """Production LangGraph orchestrator for legal document intelligence.

    Pipeline:
      upload -> OCR -> LanguageDetection -> Classifier -> FactExtraction -> Validation ->
      (parallel) [Summary, per-document persistence] -> case-level: Timeline ->
      Contradiction -> SimilarCase.

    Enforces:
      - Per-step status & DB persistence (pending/running/done/failed/needs_review)
      - Resume after crash from last successful step
      - Retries with backoff
      - Step failure does not kill other documents in the case
      - Audit log entry per step (Hard Rule 5)
      - human_review interrupt node on low confidence or HIGH validation issues
    """

    def __init__(self, db_session: Session, llm_client=None, embedder=None):
        self.session = db_session
        self.llm = llm_client or get_llm_client()
        self.embedder = embedder
        self.settings = get_settings()

        # Initialize pipeline agents
        self.ocr_agent = OCRAgent()
        self.lang_agent = LanguageDetectionAgent()
        self.classifier_agent = DocumentClassifierAgent(llm_client=self.llm)
        self.fact_agent = FactExtractionAgent(llm_client=self.llm)
        self.validation_agent = ValidationAgent(llm_client=self.llm)
        self.summary_agent = SummaryAgent(llm_client=self.llm)
        self.timeline_agent = TimelineAgent(llm_client=self.llm)
        self.contradiction_agent = ContradictionAgent(llm_client=self.llm, embedder=embedder)
        self.similar_case_agent = SimilarCaseAgent(db_session=db_session, llm_client=self.llm, embedder=embedder)

        # Build compiled LangGraph app
        self.graph = self._build_graph()

    # -------------------------------------------------------------------------
    # DB Step Persistence & Crash Recovery Helpers
    # -------------------------------------------------------------------------
    def _get_cached_step(self, document_id: str, step_name: str) -> Optional[Dict[str, Any]]:
        """Check if step has already succeeded in DB (for crash recovery)."""
        stmt = (
            select(ProcessingStepModel)
            .where(
                ProcessingStepModel.document_id == document_id,
                ProcessingStepModel.step_name == step_name,
                ProcessingStepModel.status == "done",
            )
            .order_by(ProcessingStepModel.created_at.desc())
        )
        rec = self.session.execute(stmt).scalars().first()
        if rec and rec.state_payload:
            try:
                return json.loads(rec.state_payload)
            except Exception:
                return None
        return None

    def _record_step(
        self,
        document_id: str,
        case_id: Optional[str],
        step_name: str,
        status: str,
        attempt: int = 1,
        payload: Optional[Any] = None,
        error: Optional[str] = None,
    ):
        """Persist per-step execution status and output in DB."""
        stmt = (
            select(ProcessingStepModel)
            .where(
                ProcessingStepModel.document_id == document_id,
                ProcessingStepModel.step_name == step_name,
            )
            .order_by(ProcessingStepModel.created_at.desc())
        )
        rec = self.session.execute(stmt).scalars().first()
        serialized_payload = None
        engine = getattr(payload, "engine", None) if payload is not None else None
        fallback_taken = bool(getattr(payload, "fallback_taken", False)) if payload is not None else False
        if isinstance(payload, dict):
            engine = payload.get("engine", engine)
            fallback_taken = bool(payload.get("fallback_taken", fallback_taken))

        if payload is not None:
            if hasattr(payload, "model_dump"):
                serialized_payload = json.dumps(payload.model_dump(), default=str)
            elif isinstance(payload, dict):
                serialized_payload = json.dumps(payload, default=str)
            else:
                serialized_payload = str(payload)

        if rec:
            rec.status = status
            rec.attempt = attempt
            if engine:
                rec.engine = engine
            rec.fallback_taken = fallback_taken
            if serialized_payload is not None:
                rec.state_payload = serialized_payload
            if error:
                rec.error_message = error
        else:
            rec = ProcessingStepModel(
                document_id=document_id,
                case_id=case_id,
                step_name=step_name,
                status=status,
                engine=engine or "rules",
                fallback_taken=fallback_taken,
                attempt=attempt,
                state_payload=serialized_payload,
                error_message=error,
            )
            self.session.add(rec)
        self.session.commit()

    def _execute_with_retry(
        self,
        step_name: str,
        document_id: str,
        case_id: Optional[str],
        fn,
        *args,
        **kwargs,
    ):
        """Execute step logic with retries and exponential backoff."""
        cached = self._get_cached_step(document_id, step_name)
        if cached is not None:
            logger.info("Resuming cached step '%s' for document %s", step_name, document_id)
            return cached

        max_retries = 2
        last_err = None
        for attempt in range(1, max_retries + 2):
            self._record_step(document_id, case_id, step_name, status="running", attempt=attempt)
            try:
                res = fn(*args, **kwargs)
                self._record_step(document_id, case_id, step_name, status="done", attempt=attempt, payload=res)
                record_audit_event(
                    event_type=f"STEP_{step_name.upper()}",
                    actor="orchestrator:ProcessingOrchestrator",
                    resource_id=document_id,
                    input_payload={"step": step_name, "attempt": attempt},
                    output_payload={"status": "done"},
                    status="SUCCESS",
                )
                return res
            except Exception as e:
                last_err = e
                logger.warning(
                    "Step '%s' failed on attempt %d for doc %s: %s",
                    step_name,
                    attempt,
                    document_id,
                    str(e),
                )
                if attempt <= max_retries:
                    time.sleep(0.05 * (2 ** (attempt - 1)))
                    continue

        self._record_step(document_id, case_id, step_name, status="failed", attempt=max_retries + 1, error=str(last_err))
        record_audit_event(
            event_type=f"STEP_{step_name.upper()}_FAILED",
            actor="orchestrator:ProcessingOrchestrator",
            resource_id=document_id,
            input_payload={"step": step_name, "error": str(last_err)},
            status="FAILED",
        )
        raise last_err

    # -------------------------------------------------------------------------
    # LangGraph Node Callbacks
    # -------------------------------------------------------------------------
    def _ocr_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        doc_id = state["document_id"]
        file_bytes = state.get("file_bytes")
        raw_text = state.get("raw_text")

        def _do_ocr():
            inp = file_bytes if file_bytes else (raw_text.encode("utf-8") if raw_text else b"")
            return self.ocr_agent.run(file_input=inp, filename=state.get("filename", "doc.pdf"), document_id=doc_id)

        ocr_res = self._execute_with_retry("ocr", doc_id, state.get("case_id"), _do_ocr)
        if isinstance(ocr_res, dict):
            state["ocr_result"] = ocr_res
        else:
            state["ocr_result"] = ocr_res.model_dump()
        return state

    def _language_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        doc_id = state["document_id"]
        ocr_data = state["ocr_result"]
        ocr_obj = OCRResult(**ocr_data) if isinstance(ocr_data, dict) else ocr_data

        def _do_lang():
            return self.lang_agent.run(ocr_obj)

        lang_res = self._execute_with_retry("language_detection", doc_id, state.get("case_id"), _do_lang)
        if isinstance(lang_res, dict):
            state["language_result"] = lang_res
        else:
            state["language_result"] = lang_res.model_dump()
        return state

    def _classifier_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        doc_id = state["document_id"]
        ocr_data = state["ocr_result"]
        pages = ocr_data.get("pages", []) if isinstance(ocr_data, dict) else ocr_data.pages
        full_text = "\n\n".join([p["text"] if isinstance(p, dict) else p.text for p in pages])
        state["raw_text"] = full_text

        def _do_class():
            inp = DocumentClassifierInput(
                document_id=doc_id,
                filename=state.get("filename", "doc.pdf"),
                text_content=full_text,
                page_count=len(pages),
                detected_languages=[state.get("language_result", {}).get("primary_language", "en")],
            )
            return self.classifier_agent.run(inp)

        class_res = self._execute_with_retry("classifier", doc_id, state.get("case_id"), _do_class)
        if isinstance(class_res, dict):
            state["classifier_result"] = class_res
        else:
            state["classifier_result"] = class_res.model_dump()
        return state

    def _fact_extraction_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        doc_id = state["document_id"]
        full_text = state.get("raw_text", "")

        def _do_facts():
            inp = DocumentExtractionInput(
                document_id=doc_id,
                filename=state.get("filename", "doc.pdf"),
                text_content=full_text,
                request_id=doc_id,
            )
            return self.fact_agent.run(inp)

        facts_res = self._execute_with_retry("fact_extraction", doc_id, state.get("case_id"), _do_facts)
        if isinstance(facts_res, dict):
            state["facts_result"] = facts_res
        else:
            state["facts_result"] = facts_res.model_dump()
        return state

    def _validation_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        doc_id = state["document_id"]
        full_text = state.get("raw_text", "")
        facts_data = state.get("facts_result", {})
        extracted_facts_raw = facts_data.get("extracted_facts") or {}
        extracted_facts_obj = (
            ExtractedFacts(**extracted_facts_raw) if extracted_facts_raw else ExtractedFacts(document_id=doc_id)
        )
        classifier_data = state.get("classifier_result", {})
        meta_dict = classifier_data.get("document_meta") or {}
        meta_obj = DocumentMeta(**meta_dict) if meta_dict else None

        def _do_val():
            inp = ValidationInput(
                document_id=doc_id,
                text_content=full_text,
                document_meta=meta_obj,
                extracted_facts=extracted_facts_obj,
            )
            return self.validation_agent.run(inp)

        val_res = self._execute_with_retry("validation", doc_id, state.get("case_id"), _do_val)
        if isinstance(val_res, dict):
            state["validation_result"] = val_res
        else:
            state["validation_result"] = val_res.model_dump()

        # Compute composite confidence & human review flag
        ocr_conf = float(state.get("ocr_result", {}).get("overall_confidence", 0.90))
        facts_conf = float(state.get("facts_result", {}).get("confidence", 0.85))
        val_conf = float(state["validation_result"].get("confidence", 0.88))
        composite_conf = round((ocr_conf + facts_conf + val_conf) / 3.0, 2)
        state["confidence"] = composite_conf

        issues = state["validation_result"].get("issues", [])
        has_high_issue = any(i.get("severity") in ["HIGH", "CRITICAL"] for i in issues)
        needs_review = (
            has_high_issue
            or (composite_conf < self.settings.CONFIDENCE_THRESHOLD)
            or state["validation_result"].get("needs_human_review", False)
            or facts_data.get("needs_human_review", False)
        )
        state["needs_human_review"] = needs_review
        return state

    def _route_after_validation(self, state: DocumentProcessingState) -> str:
        """Route to human_review if low confidence or high severity defect exists."""
        if state.get("needs_human_review", False):
            return "human_review"
        return "summary"

    def _human_review_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """Interrupt / safety node marking document as needing lawyer review."""
        doc_id = state["document_id"]
        case_id = state.get("case_id")
        self._record_step(doc_id, case_id, "human_review", status="needs_review")
        state["status"] = "needs_review"

        # Update Document record in DB
        doc = self.session.get(DocumentModel, doc_id)
        if doc:
            doc.status = "needs_review"
            self.session.commit()

        record_audit_event(
            event_type="STEP_HUMAN_REVIEW_FLAGGED",
            actor="orchestrator:ProcessingOrchestrator",
            resource_id=doc_id,
            input_payload={"confidence": state.get("confidence")},
            output_payload={"status": "needs_review"},
            confidence=state.get("confidence"),
            needs_human_review=True,
            status="NEEDS_REVIEW",
        )
        return state

    def _summary_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        doc_id = state["document_id"]
        full_text = state.get("raw_text", "")
        facts_data = state.get("facts_result", {})
        extracted_facts_raw = facts_data.get("extracted_facts") or {}
        extracted_facts_obj = (
            ExtractedFacts(**extracted_facts_raw) if extracted_facts_raw else None
        )

        def _do_summary():
            inp = SummaryInput(
                document_id=doc_id,
                text_content=full_text,
                extracted_facts=extracted_facts_obj,
            )
            return self.summary_agent.run(inp)

        summ_res = self._execute_with_retry("summary", doc_id, state.get("case_id"), _do_summary)
        if isinstance(summ_res, dict):
            state["summary_result"] = summ_res
        else:
            state["summary_result"] = summ_res.model_dump()
        return state

    def _persistence_node(self, state: DocumentProcessingState) -> DocumentProcessingState:
        """Persist extracted entities, pages, validation issues, and summaries to DB."""
        doc_id = state["document_id"]
        case_id = state.get("case_id")

        # 1. Update Document metadata
        doc = self.session.get(DocumentModel, doc_id)
        if doc:
            class_data = state.get("classifier_result", {})
            meta = class_data.get("document_meta") or {}
            doc.doc_type = meta.get("doc_type") or doc.doc_type or "other"
            doc.detected_language = state.get("language_result", {}).get("primary_language", "en")
            doc.page_count = len(state.get("ocr_result", {}).get("pages", [1]))
            if not state.get("needs_human_review", False):
                doc.status = "done"

        # 2. Persist Document Pages
        ocr_pages = state.get("ocr_result", {}).get("pages", [])
        for p in ocr_pages:
            p_num = p.get("page_number", 1)
            p_text = p.get("text", "")
            p_conf = p.get("confidence", 1.0)
            existing_page = self.session.execute(
                select(DocumentPageModel).where(
                    DocumentPageModel.document_id == doc_id,
                    DocumentPageModel.page_number == p_num,
                )
            ).scalars().first()
            if not existing_page:
                dp = DocumentPageModel(
                    document_id=doc_id,
                    page_number=p_num,
                    text=p_text,
                    confidence=p_conf,
                    language=state.get("language_result", {}).get("primary_language", "en"),
                )
                self.session.add(dp)

        # 3. Persist Extracted Facts with Provenance
        facts_data = state.get("facts_result", {})
        extracted_facts = facts_data.get("extracted_facts") or {}
        # Collect all items
        fact_items = []
        for cat in ["parties", "dates", "sections", "amounts", "locations", "incidents", "statements"]:
            for item in extracted_facts.get(cat, []):
                fact_items.append((cat, item))

        for cat, item in fact_items:
            s_ref = item.get("source") or {}
            fact_rec = FactModel(
                document_id=doc_id,
                case_id=case_id,
                category=cat,
                item_data=json.dumps(item),
                source_ref=json.dumps(s_ref),
                confidence=float(item.get("confidence", 0.90)),
            )
            self.session.add(fact_rec)

        # 4. Persist Validation Issues
        val_issues = state.get("validation_result", {}).get("issues", [])
        for issue in val_issues:
            v_rec = ValidationIssueModel(
                document_id=doc_id,
                severity=issue.get("severity", "MEDIUM"),
                category=issue.get("category", "VALIDATION_DEFECT"),
                description=issue.get("description", ""),
                source_refs=json.dumps(issue.get("source_refs", [])),
                suggestion=issue.get("suggestion", ""),
            )
            self.session.add(v_rec)

        # 5. Persist Summary
        summ_data = state.get("summary_result")
        if summ_data:
            s_text = summ_data.get("summary_text") or summ_data.get("summary") or ""
            s_rec = SummaryModel(
                case_id=case_id,
                document_id=doc_id,
                summary_text=s_text,
                key_issues=json.dumps([kp.get("point") for kp in summ_data.get("key_points", [])]),
                relief_sought=summ_data.get("relief_sought") or "",
                confidence=float(summ_data.get("confidence", 0.90)),
                needs_human_review=state.get("needs_human_review", False),
                disclaimer=self.settings.DISCLAIMER_TEXT,
            )
            self.session.add(s_rec)

        self.session.commit()
        self._record_step(doc_id, case_id, "persistence", status="done")
        if not state.get("needs_human_review", False):
            state["status"] = "done"
        return state

    # -------------------------------------------------------------------------
    # Graph Construction
    # -------------------------------------------------------------------------
    def _build_graph(self):
        workflow = StateGraph(DocumentProcessingState)

        workflow.add_node("ocr", self._ocr_node)
        workflow.add_node("language_detection", self._language_node)
        workflow.add_node("classifier", self._classifier_node)
        workflow.add_node("fact_extraction", self._fact_extraction_node)
        workflow.add_node("validation", self._validation_node)
        workflow.add_node("human_review", self._human_review_node)
        workflow.add_node("summary", self._summary_node)
        workflow.add_node("persistence", self._persistence_node)

        # Sequence flow
        workflow.add_edge(START, "ocr")
        workflow.add_edge("ocr", "language_detection")
        workflow.add_edge("language_detection", "classifier")
        workflow.add_edge("classifier", "fact_extraction")
        workflow.add_edge("fact_extraction", "validation")

        workflow.add_conditional_edges(
            "validation",
            self._route_after_validation,
            {
                "human_review": "human_review",
                "summary": "summary",
            },
        )
        workflow.add_edge("human_review", "summary")
        workflow.add_edge("summary", "persistence")
        workflow.add_edge("persistence", END)

        return workflow.compile()

    # -------------------------------------------------------------------------
    # Public Execution & Crash-Resume APIs
    # -------------------------------------------------------------------------
    def process_document(
        self,
        document_id: str,
        file_bytes: Optional[bytes] = None,
        filename: str = "doc.pdf",
        case_id: Optional[str] = None,
        raw_text: Optional[str] = None,
    ) -> DocumentProcessingState:
        """Run or resume LangGraph document intelligence pipeline for one document."""
        doc = self.session.get(DocumentModel, document_id)
        if not file_bytes and doc and doc.encrypted_content:
            try:
                file_bytes = decrypt_bytes(doc.encrypted_content)
            except Exception:
                file_bytes = b""
        if doc and not case_id:
            case_id = doc.case_id

        initial_state: DocumentProcessingState = {
            "document_id": document_id,
            "case_id": case_id,
            "filename": filename,
            "file_bytes": file_bytes,
            "raw_text": raw_text or "",
            "confidence": 1.0,
            "needs_human_review": False,
            "status": "running",
            "errors": [],
        }

        # Set doc status to running
        if doc:
            doc.status = "running"
            self.session.commit()

        final_state = self.graph.invoke(initial_state)
        return final_state

    def resume_document_processing(self, document_id: str) -> DocumentProcessingState:
        """Resume document processing from last successful step after a crash."""
        doc = self.session.get(DocumentModel, document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")
        return self.process_document(
            document_id=doc.id,
            filename=doc.filename,
            case_id=doc.case_id,
        )

    def process_case(self, case_id: str) -> Dict[str, Any]:
        """Process all documents in a case and run case-level reasoning (Timeline, Contradiction, SimilarCase).

        Guarantees that step failure on one document does not kill other documents.
        """
        stmt = select(DocumentModel).where(DocumentModel.case_id == case_id)
        documents = self.session.execute(stmt).scalars().all()

        doc_results = {}
        for doc in documents:
            try:
                state = self.process_document(
                    document_id=doc.id,
                    filename=doc.filename,
                    case_id=case_id,
                )
                doc_results[doc.id] = {"status": state.get("status", "done"), "confidence": state.get("confidence", 1.0)}
            except Exception as e:
                logger.error("Document %s failed during case %s processing: %s", doc.id, case_id, str(e))
                doc.status = "failed"
                self.session.commit()
                doc_results[doc.id] = {"status": "failed", "error": str(e)}

        # ---------------------------------------------------------------------
        # Case-Level Synthesis: Timeline, Contradictions, and Similar Cases
        # ---------------------------------------------------------------------
        # 1. Timeline
        timeline_res = None
        try:
            inp_tl = TimelineInput(case_id=case_id, db_session=self.session)
            timeline_res = self.timeline_agent.run(inp_tl)
            for ev in timeline_res.events:
                s_ref_dict = ev.source.model_dump() if ev.source else {}
                t_date = ev.normalized_date or getattr(ev, "date_str", getattr(ev, "raw_date", "Unknown"))
                t_title = getattr(ev, "event_title", getattr(ev, "title", "Legal Event"))
                t_event = TimelineEventModel(
                    case_id=case_id,
                    event_date=t_date,
                    title=t_title,
                    description=ev.description,
                    is_important=(ev.importance == "HIGH"),
                    source_ref=json.dumps(s_ref_dict),
                    confidence=ev.confidence,
                )
                self.session.add(t_event)
            self.session.commit()
            self._record_step("case-level", case_id, "timeline", status="done")
        except Exception as e:
            logger.error("Case-level timeline failed for case %s: %s", case_id, str(e))

        # 2. Contradictions
        contradiction_res = None
        try:
            inp_ct = ContradictionInput(case_id=case_id, db_session=self.session)
            contradiction_res = self.contradiction_agent.run(inp_ct)
            for c in contradiction_res.contradictions:
                sa = c.source_a.model_dump() if c.source_a else {}
                sb = c.source_b.model_dump() if c.source_b else {}
                c_mod = ContradictionModel(
                    case_id=case_id,
                    statement_a=c.statement_a,
                    statement_b=c.statement_b,
                    description=c.reason,
                    source_a=json.dumps(sa),
                    source_b=json.dumps(sb),
                    severity=c.severity,
                    confidence=c.confidence,
                )
                self.session.add(c_mod)
            self.session.commit()
            self._record_step("case-level", case_id, "contradiction", status="done")
        except Exception as e:
            logger.error("Case-level contradiction failed for case %s: %s", case_id, str(e))

        # 3. Similar Cases (Hard Rule 4: zero hallucination, DB-verified only)
        similar_cases_res = None
        try:
            inp_sc = SimilarCaseInput(case_id=case_id, db_session=self.session)
            similar_cases_res = self.similar_case_agent.run(inp_sc)
            self._record_step("case-level", case_id, "similar_case", status="done")
        except Exception as e:
            logger.error("Case-level similar cases failed for case %s: %s", case_id, str(e))

        return {
            "case_id": case_id,
            "document_results": doc_results,
            "timeline_events_count": len(timeline_res.events) if timeline_res else 0,
            "contradictions_count": len(contradiction_res.contradictions) if contradiction_res else 0,
            "similar_cases_count": len(similar_cases_res.similar_cases) if similar_cases_res else 0,
            "disclaimer": self.settings.DISCLAIMER_TEXT,
        }


