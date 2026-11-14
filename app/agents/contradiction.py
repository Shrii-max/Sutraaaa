"""Case-level Contradiction Analysis Agent for Indian legal proceedings.

Follows Requirement:
3. ContradictionAgent:
   - Compare statements and facts across documents: witness vs witness, statement vs
     FIR, FIR vs chargesheet, same person's statements at different times.
   - Step 1: candidate pair generation by embeddings (same entity/event topic).
   - Step 2: LLM judges each pair: consistent / contradictory / unclear, with the two
     quoted snippets and a reason.
   - Step 3: verify both snippets exist in source text; drop otherwise.
   - Output ContradictionReport sorted by severity.

Follows Hard Rule 1: Typed Pydantic input and output, run() method, no hidden global state.
Follows Hard Rule 2: Every contradiction backed by verified SourceRefs on both sides.
Follows Hard Rule 3: Output carries confidence and needs_human_review.
Follows Hard Rule 8: Fully mockable LLM and Embedder interfaces.
"""

import json
import math
import re
from typing import List, Optional, Dict, Any, Tuple, Literal
from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.schemas.source import SourceRef
from app.schemas.contradiction import (
    ContradictionSeverity,
    ContradictionItem,
    ContradictionReport,
    ContradictionInput,
)
from app.schemas.facts import StatementItem, FactItem
from app.llm.client import LLMClient, Embedder, get_llm_client, LocalEmbeddingClient


class _LLMPairContradictionResult(BaseModel):
    judgment: Literal["consistent", "contradictory", "unclear"] = "consistent"
    severity: ContradictionSeverity = "MEDIUM"
    category: str = Field(default="FACTUAL_DISCREPANCY", description="e.g. ALIBI_CONFLICT, WEAPON_DISCREPANCY, TIME_DISCREPANCY, IDENTITY_CONFLICT")
    reason: str = Field(default="", description="Precise judicial explanation of why these statements contradict each other")
    quote_a: str = Field(default="", description="Exact verbatim quote from Statement A showing the contradiction")
    quote_b: str = Field(default="", description="Exact verbatim quote from Statement B showing the contradiction")
    confidence: float = Field(default=0.88, ge=0.0, le=1.0)


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class ContradictionAgent(BaseAgent[ContradictionInput, ContradictionReport]):
    """Detects and validates cross-document factual contradictions across witness testimonies, FIRs, and pleadings."""

    agent_name: str = "ContradictionAgent"

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        embedder: Optional[Embedder] = None,
        similarity_threshold: float = 0.40,
    ):
        super().__init__(llm_client=llm_client)
        self.embedder = embedder or LocalEmbeddingClient()
        self.similarity_threshold = similarity_threshold

    def _execute(self, input_data: ContradictionInput) -> ContradictionReport:
        case_id = input_data.case_id
        doc_text_map: Dict[str, str] = input_data.documents or {}

        # Collect evidentiary comparison items
        items: List[Dict[str, Any]] = []

        # 1. Ingest from DB session if provided
        if input_data.db_session is not None:
            items.extend(self._load_from_db(input_data.db_session, case_id))

        # 2. Ingest from direct statements list
        if input_data.statements:
            items.extend(self._extract_from_statements(input_data.statements))

        # 3. Ingest from facts list (FIRs, incidents, claims)
        if input_data.facts:
            items.extend(self._extract_from_facts(input_data.facts))

        if len(items) < 2:
            return ContradictionReport(
                case_id=case_id,
                contradictions=[],
                has_severe_contradictions=False,
                candidate_pairs_evaluated=0,
                contradictions_count=0,
                confidence=0.90,
                needs_human_review=False,
                audit_notes="Fewer than 2 statements/facts provided; no cross-document pairs to compare.",
            )

        # ---------------------------------------------------------------------
        # Step 1: Candidate pair generation by embeddings (same entity/topic)
        # ---------------------------------------------------------------------
        texts_to_embed = [it["text"] for it in items]
        try:
            vectors = self.embedder.embed(texts_to_embed)
        except Exception:
            vectors = [[0.0] * 1024 for _ in texts_to_embed]

        candidate_pairs: List[Tuple[Dict[str, Any], Dict[str, Any], str, float]] = []
        n = len(items)

        for i in range(n):
            for j in range(i + 1, n):
                item_a = items[i]
                item_b = items[j]

                comp_type = self._determine_comparison_type(item_a, item_b)
                if not comp_type:
                    continue

                # Compute semantic similarity
                sim = cosine_similarity(vectors[i], vectors[j])

                # Check entity or keyword topic overlap
                has_topic_overlap = self._check_topical_overlap(item_a["text"], item_b["text"])

                if n <= 10 or sim >= self.similarity_threshold or has_topic_overlap:
                    candidate_pairs.append((item_a, item_b, comp_type, sim))

        # ---------------------------------------------------------------------
        # Step 2: LLM judges each pair (consistent / contradictory / unclear)
        # ---------------------------------------------------------------------
        verified_contradictions: List[ContradictionItem] = []
        dropped_hallucinated_count = 0

        for item_a, item_b, comp_type, sim in candidate_pairs:
            prompt = (
                f"Compare the following two evidentiary statements/assertions from the same legal case ({case_id}):\n\n"
                f"--- Statement A ---\n"
                f"Speaker / Source: {item_a['speaker']} ({item_a['doc_type']})\n"
                f"Document ID: {item_a['document_id']}\n"
                f"Content: \"\"\"{item_a['text']}\"\"\"\n\n"
                f"--- Statement B ---\n"
                f"Speaker / Source: {item_b['speaker']} ({item_b['doc_type']})\n"
                f"Document ID: {item_b['document_id']}\n"
                f"Content: \"\"\"{item_b['text']}\"\"\"\n\n"
                f"Comparison Context: {comp_type}\n\n"
                f"Instructions:\n"
                f"1. Determine whether Statement A and Statement B are: 'consistent', 'contradictory', or 'unclear'.\n"
                f"2. If contradictory:\n"
                f"   - severity: 'HIGH' (direct conflict on alibi, identity of assailant, weapon used, time of incident by hours, presence at crime scene);\n"
                f"               'MEDIUM' (discrepancy in monetary amount, sequence of events, vehicle color or make);\n"
                f"               'LOW' (minor peripheral or clerical variation)\n"
                f"   - category: e.g. 'ALIBI_CONFLICT', 'WEAPON_DISCREPANCY', 'TIME_DISCREPANCY', 'IDENTITY_CONFLICT', 'AMOUNT_DISCREPANCY'\n"
                f"   - reason: Precise judicial reason explaining the contradiction.\n"
                f"   - quote_a: EXACT verbatim excerpt from Statement A that contradicts Statement B.\n"
                f"   - quote_b: EXACT verbatim excerpt from Statement B that contradicts Statement A.\n\n"
                f"CRITICAL ANTI-HALLUCINATION RULE: quote_a MUST appear verbatim in Statement A and quote_b MUST appear verbatim in Statement B."
            )

            system = (
                "You are an Indian Senior Advocate analyzing evidence for cross-examination in trial court. "
                "Only flag genuine factual contradictions where both assertions cannot simultaneously be true. "
                "Verbatim provenance is strictly mandatory."
            )

            try:
                res, _ = self.llm.generate_structured(
                    prompt=prompt,
                    schema=_LLMPairContradictionResult,
                    system=system,
                )
            except Exception:
                continue

            if res.judgment != "contradictory":
                continue

            quote_a = (res.quote_a or "").strip()
            quote_b = (res.quote_b or "").strip()

            # -----------------------------------------------------------------
            # Step 3: Anti-hallucination snippet verification (Hard Rule 2)
            # -----------------------------------------------------------------
            # Verify quote_a in text of A or full document A
            text_a = item_a["text"]
            full_doc_a = doc_text_map.get(item_a["document_id"], "")
            loc_a = text_a.find(quote_a) if quote_a else -1
            if loc_a == -1 and full_doc_a and quote_a:
                loc_a = full_doc_a.find(quote_a)

            # Verify quote_b in text of B or full document B
            text_b = item_b["text"]
            full_doc_b = doc_text_map.get(item_b["document_id"], "")
            loc_b = text_b.find(quote_b) if quote_b else -1
            if loc_b == -1 and full_doc_b and quote_b:
                loc_b = full_doc_b.find(quote_b)

            # If either quote fails verification in source text -> DROP IT!
            if not quote_a or not quote_b or loc_a == -1 or loc_b == -1:
                dropped_hallucinated_count += 1
                continue

            # Build exact SourceRefs
            src_a = self._build_source_ref(item_a, quote_a, loc_a, full_doc_a)
            src_b = self._build_source_ref(item_b, quote_b, loc_b, full_doc_b)

            verified_contradictions.append(
                ContradictionItem(
                    statement_a=quote_a,
                    statement_b=quote_b,
                    description=res.reason or f"Factual contradiction between {item_a['speaker']} and {item_b['speaker']}.",
                    source_a=src_a,
                    source_b=src_b,
                    severity=res.severity,
                    category=res.category,
                    comparison_type=comp_type,
                    confidence=res.confidence,
                )
            )

        # ---------------------------------------------------------------------
        # Output: ContradictionReport sorted by severity
        # ---------------------------------------------------------------------
        severity_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        verified_contradictions.sort(key=lambda c: severity_rank.get(c.severity, 1))

        has_severe = any(c.severity == "HIGH" for c in verified_contradictions)

        return ContradictionReport(
            case_id=case_id,
            contradictions=verified_contradictions,
            has_severe_contradictions=has_severe,
            candidate_pairs_evaluated=len(candidate_pairs),
            contradictions_count=len(verified_contradictions),
            confidence=0.88 if not verified_contradictions else (0.82 if has_severe else 0.85),
            needs_human_review=has_severe or (len(verified_contradictions) > 0),
            audit_notes=(
                f"Evaluated {len(candidate_pairs)} candidate pairs by embedding similarity; "
                f"verified {len(verified_contradictions)} genuine contradictions; "
                f"dropped {dropped_hallucinated_count} items failing anti-hallucination snippet checks."
            ),
        )

    @staticmethod
    def _determine_comparison_type(item_a: Dict[str, Any], item_b: Dict[str, Any]) -> Optional[str]:
        spk_a = (item_a.get("speaker") or "").strip().lower()
        spk_b = (item_b.get("speaker") or "").strip().lower()
        doc_a = (item_a.get("doc_type") or "").strip().lower()
        doc_b = (item_b.get("doc_type") or "").strip().lower()

        # Case 4: Same person at different times / different documents
        if spk_a and spk_b and spk_a == spk_b:
            if item_a.get("document_id") != item_b.get("document_id") or item_a.get("date_str") != item_b.get("date_str"):
                return "same_person_different_times"
            return None  # Skip identical item

        # Case 2: Statement vs FIR
        if ("fir" in doc_a and "statement" in doc_b) or ("statement" in doc_a and "fir" in doc_b):
            return "statement_vs_fir"

        # Case 3: FIR vs Chargesheet
        if ("fir" in doc_a and "chargesheet" in doc_b) or ("chargesheet" in doc_a and "fir" in doc_b):
            return "fir_vs_chargesheet"

        # Case 1: Witness vs Witness
        if ("statement" in doc_a or "witness" in doc_a) and ("statement" in doc_b or "witness" in doc_b):
            return "witness_vs_witness"

        # General cross-document fact comparison
        if item_a.get("document_id") != item_b.get("document_id"):
            return "cross_document_fact"

        return "statement_vs_statement"

    @staticmethod
    def _check_topical_overlap(t1: str, t2: str) -> bool:
        """Check whether two texts discuss common forensic or legal topics or share entities."""
        common_legal_terms = {
            "weapon", "knife", "pistol", "gun", "revolver", "lathi", "iron rod", "car", "vehicle",
            "bike", "honda", "scooter", "color", "red", "black", "silver", "white", "money",
            "cash", "rupees", "lakh", "crore", "cheque", "time", "pm", "am", "morning", "evening",
            "night", "assault", "stabbed", "shot", "threatened", "bribe", "property", "plot",
            "accused", "complainant", "victim", "witness", "police", "fir", "alleged", "incident",
            "दुकान", "रुपये", "लाख", "गाड़ी", "कार", "चाकू", "पिस्तौल", "गोली", "हथियार", "धमकी", "अभियुक्त"
        }
        words1 = {w.lower() for w in re.findall(r"\b\w{3,}\b", t1)}
        words2 = {w.lower() for w in re.findall(r"\b\w{3,}\b", t2)}
        shared = words1.intersection(words2)
        if shared.intersection(common_legal_terms):
            return True
        if len(shared) >= 2:
            return True
        return False

    @staticmethod
    def _build_source_ref(item: Dict[str, Any], snippet: str, offset: int, full_doc: str) -> SourceRef:
        doc_id = item.get("document_id") or "doc_unknown"
        page = 1
        base_src = item.get("source")
        if base_src and hasattr(base_src, "page"):
            page = base_src.page

        return SourceRef(
            document_id=doc_id,
            page=page,
            char_start=offset,
            char_end=offset + len(snippet),
            snippet=snippet,
        )

    @staticmethod
    def _load_from_db(session: Any, case_id: str) -> List[Dict[str, Any]]:
        from app.db.models import FactModel
        items = []
        try:
            records = session.query(FactModel).filter(FactModel.case_id == case_id).all()
            for r in records:
                try:
                    data = json.loads(r.item_data)
                    s_data = json.loads(r.source_ref)
                    src = SourceRef(**s_data)
                    text = data.get("content") or data.get("statement") or data.get("description") or ""
                    if text:
                        items.append({
                            "item_id": f"DB-{r.id[:8]}",
                            "text": text,
                            "speaker": data.get("speaker") or "Witness",
                            "doc_type": r.category,
                            "date_str": data.get("recorded_on") or data.get("date"),
                            "document_id": r.document_id,
                            "source": src,
                        })
                except Exception:
                    continue
        except Exception:
            pass
        return items

    @staticmethod
    def _extract_from_statements(statements_list: List[Any]) -> List[Dict[str, Any]]:
        items = []
        for idx, s in enumerate(statements_list):
            if isinstance(s, StatementItem):
                items.append({
                    "item_id": f"ST-{idx + 1:03d}",
                    "text": s.content,
                    "speaker": s.speaker,
                    "doc_type": f"statement_{s.statement_type}",
                    "date_str": s.recorded_on,
                    "document_id": s.source.document_id if s.source else "doc-st",
                    "source": s.source,
                })
            elif isinstance(s, dict):
                src = s.get("source") or s.get("source_ref")
                if isinstance(src, dict):
                    src = SourceRef(**src)
                items.append({
                    "item_id": s.get("statement_id", f"ST-{idx + 1:03d}"),
                    "text": s.get("content", ""),
                    "speaker": s.get("speaker", "Witness"),
                    "doc_type": s.get("statement_type", "statement"),
                    "date_str": s.get("recorded_on"),
                    "document_id": s.get("document_id") or (src.document_id if src else "doc-st"),
                    "source": src,
                })
        return items

    @staticmethod
    def _extract_from_facts(facts_list: List[Any]) -> List[Dict[str, Any]]:
        items = []
        for idx, f in enumerate(facts_list):
            if isinstance(f, FactItem):
                items.append({
                    "item_id": f.fact_id,
                    "text": f.statement,
                    "speaker": "Complainant / Record",
                    "doc_type": f.category,
                    "date_str": f.date_mentioned,
                    "document_id": f.source.document_id if f.source else "doc-fact",
                    "source": f.source,
                })
            elif isinstance(f, dict):
                src = f.get("source")
                if isinstance(src, dict):
                    src = SourceRef(**src)
                items.append({
                    "item_id": f.get("fact_id", f"FACT-{idx + 1:03d}"),
                    "text": f.get("statement") or f.get("description", ""),
                    "speaker": f.get("speaker", "Record"),
                    "doc_type": f.get("category", "incident"),
                    "date_str": f.get("date_mentioned") or f.get("date"),
                    "document_id": f.get("document_id") or (src.document_id if src else "doc-fact"),
                    "source": src,
                })
        return items
