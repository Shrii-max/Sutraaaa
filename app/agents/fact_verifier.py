"""Fact Verifier Agent: 2nd-pass Natural Language Inference (NLI) entailment checker.

Follows v2 Reliability Requirement 3:
Snippet-exists-but-meaning-wrong ->
Add FactVerifierAgent: for each extracted fact, a second pass asks:
"Does this snippet entail this claim, including speaker/role/date attribution?"
Verdict: supports / contradicts / insufficient.
Only "supports" auto-passes; others flagged as needs_human_review.
Track verifier rejection rate metric.
"""

import re
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.schemas.source import SourceRef
from app.llm.client import LLMClient
from app.llm.router import ModelRouter, TaskType
from app.security.guardrails import wrap_as_document_data, format_safe_system_prompt
from app.security.audit import record_audit_event


class FactVerificationItem(BaseModel):
    fact_id: str
    claim_type: str = Field(..., description="e.g. party, statement, date, section, incident")
    claim_summary: str = Field(..., description="The structured assertion extracted by the pipeline")
    snippet: str = Field(..., description="The verbatim quotation from the document")
    speaker: Optional[str] = None
    role: Optional[str] = None
    date_str: Optional[str] = None
    section_number: Optional[str] = None
    source_ref: Optional[SourceRef] = None


class FactVerificationInput(BaseModel):
    document_id: str
    document_text: str
    facts: List[FactVerificationItem] = Field(default_factory=list)


class _NLIEntailmentResult(BaseModel):
    verdict: Literal["supports", "contradicts", "insufficient"] = "insufficient"
    confidence: float = Field(default=0.50, ge=0.0, le=1.0)
    reason: str = Field(default="Automated entailment requires review.", description="Judicial explanation of entailment")


class VerifiedFactItem(BaseModel):
    fact_id: str
    claim_type: str
    claim_summary: str
    snippet: str
    verdict: Literal["supports", "contradicts", "insufficient"]
    confidence: float
    reason: str
    needs_human_review: bool
    source_ref: Optional[SourceRef] = None


class FactVerificationOutput(BaseModel):
    document_id: str
    verified_facts: List[VerifiedFactItem] = Field(default_factory=list)
    rejected_facts: List[VerifiedFactItem] = Field(default_factory=list)
    total_facts: int = 0
    verified_count: int = 0
    rejected_count: int = 0
    rejection_rate: float = 0.0
    overall_confidence: float = 1.0
    confidence: float = 1.0
    needs_human_review: bool = False
    audit_notes: str = ""
    disclaimer: str = Field(default="LEGAL DISCLAIMER: LexAgent is a decision-support intelligence system.")
    engine: str = Field(default="rules", description="Engine used: nli | rules")
    llm_called: bool = Field(default=False)
    fallback_taken: bool = Field(default=False)
    status: Literal["live_model", "rule_based", "fallback", "failed", "needs_review"] = Field(default="rule_based")
    error_message: Optional[str] = None


class FactVerifierAgent(BaseAgent[FactVerificationInput, FactVerificationOutput]):
    """Performs rigorous natural language entailment verification between source snippets and extracted facts."""

    agent_name: str = "FactVerifierAgent"

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(llm_client=llm_client)
        self.router = ModelRouter(llm_client=self.llm)

    def _execute(self, input_data: FactVerificationInput) -> FactVerificationOutput:
        verified_items: List[VerifiedFactItem] = []
        rejected_items: List[VerifiedFactItem] = []

        system = format_safe_system_prompt(
            "You are a strict judicial evidence verifier examining Natural Language Inference (NLI) entailment. "
            "Evaluate whether the snippet strictly entails the claim including speaker, role, date, and statutory section attribution. "
            "Output strictly valid JSON conforming to the schema with verdict: 'supports', 'contradicts', or 'insufficient'."
        )

        for fact in input_data.facts:
            clean_snippet = (fact.snippet or "").strip()

            # 1. Verification: Snippet existence check in document
            if not clean_snippet or clean_snippet not in input_data.document_text:
                item = VerifiedFactItem(
                    fact_id=fact.fact_id,
                    claim_type=fact.claim_type,
                    claim_summary=fact.claim_summary,
                    snippet=fact.snippet,
                    verdict="contradicts",
                    confidence=0.99,
                    reason="Snippet does not exist in the source document (hallucination).",
                    needs_human_review=True,
                    source_ref=fact.source_ref,
                )
                rejected_items.append(item)
                continue

            # 2. Verification: Attribution check (wrong speaker / role)
            snippet_lower = clean_snippet.lower()
            claim_lower = fact.claim_summary.lower()

            # Negation discrepancy check
            NEGATION_WORDS = {
                "not", "didn't", "did not", "never", "failed", "refused", "denied",
                "unpaid", "without", "no payment", "nahi", "nahin", "asweekar", "mana", "inkar"
            }
            snippet_has_neg = any(re.search(rf"\b{re.escape(w)}\b", snippet_lower) for w in NEGATION_WORDS)
            claim_has_neg = any(re.search(rf"\b{re.escape(w)}\b", claim_lower) for w in NEGATION_WORDS)
            if snippet_has_neg != claim_has_neg:
                item = VerifiedFactItem(
                    fact_id=fact.fact_id,
                    claim_type=fact.claim_type,
                    claim_summary=fact.claim_summary,
                    snippet=fact.snippet,
                    verdict="contradicts",
                    confidence=0.95,
                    reason="Semantic negation conflict: snippet asserts negative contrary to affirmative claim (or vice versa).",
                    needs_human_review=True,
                    source_ref=fact.source_ref,
                )
                rejected_items.append(item)
                continue

            if fact.speaker:
                speaker_lower = fact.speaker.lower()
                # Check for explicit conflicting speaker markers in snippet
                has_speaker_marker = any(k in snippet_lower for k in ["recorded by:", "name:", "witness:", "gawah:", "accused:", "complainant:"])
                if has_speaker_marker and speaker_lower not in snippet_lower:
                    item = VerifiedFactItem(
                        fact_id=fact.fact_id,
                        claim_type=fact.claim_type,
                        claim_summary=fact.claim_summary,
                        snippet=fact.snippet,
                        verdict="contradicts",
                        confidence=0.95,
                        reason=f"Attributed speaker '{fact.speaker}' contradicts the speaker identified in the source text.",
                        needs_human_review=True,
                        source_ref=fact.source_ref,
                    )
                    rejected_items.append(item)
                    continue

                # Speaker role swap checks
                if "complainant" in speaker_lower and "accused" in snippet_lower and "complainant" not in snippet_lower:
                    item = VerifiedFactItem(
                        fact_id=fact.fact_id,
                        claim_type=fact.claim_type,
                        claim_summary=fact.claim_summary,
                        snippet=fact.snippet,
                        verdict="contradicts",
                        confidence=0.95,
                        reason="Role/speaker inversion: claim attributes to Complainant, but snippet describes Accused.",
                        needs_human_review=True,
                        source_ref=fact.source_ref,
                    )
                    rejected_items.append(item)
                    continue

                if "accused" in speaker_lower and "complainant" in snippet_lower and "accused" not in snippet_lower:
                    item = VerifiedFactItem(
                        fact_id=fact.fact_id,
                        claim_type=fact.claim_type,
                        claim_summary=fact.claim_summary,
                        snippet=fact.snippet,
                        verdict="contradicts",
                        confidence=0.95,
                        reason="Role/speaker inversion: claim attributes to Accused, but snippet describes Complainant.",
                        needs_human_review=True,
                        source_ref=fact.source_ref,
                    )
                    rejected_items.append(item)
                    continue

            # 3. LLM verification
            prompt = (
                f"SOURCE SNIPPET FROM LEGAL DOCUMENT:\n"
                f"{wrap_as_document_data(fact.snippet)}\n\n"
                f"EXTRACTED LEGAL CLAIM:\n"
                f"- Category: {fact.claim_type}\n"
                f"- Claim Summary: {fact.claim_summary}\n"
                f"- Attributed Speaker: {fact.speaker or 'N/A'}\n"
                f"- Attributed Role: {fact.role or 'N/A'}\n"
                f"- Attributed Date: {fact.date_str or 'N/A'}\n"
                f"- Attributed Section: {fact.section_number or 'N/A'}\n\n"
                f"TASK: Determine if the verbatim snippet strictly entails this claim and its attributions.\n"
                f"Verdicts:\n"
                f"- 'supports': Snippet directly confirms the assertion and attribution.\n"
                f"- 'contradicts': Snippet actively contradicts the assertion (e.g. negation, different speaker, inverted role).\n"
                f"- 'insufficient': Snippet mentions some words but does not prove the specific attribution or claim."
            )

            # Route to verification / judging model
            raw_res, was_escalated, model_used = self.router.run_structured(
                task=TaskType.JUDGING,
                schema=_NLIEntailmentResult,
                prompt=prompt,
                system=system,
            )

            # Check if LLM output supported or if fallback rule entails
            verdict = raw_res.verdict
            confidence = raw_res.confidence
            reason = raw_res.reason

            # If LLM failed / offline, do NOT falsely claim NLI entailment
            llm_offline = (model_used == "fallback" or (verdict == "insufficient" and confidence <= 0.50))
            if llm_offline:
                clean_claim = fact.claim_summary.strip().lower()
                if clean_claim in snippet_lower and (snippet_has_neg == claim_has_neg):
                    verdict = "supports"
                    confidence = 0.88
                    reason = "Verbatim substring match confirmed with no negation conflicts."
                else:
                    verdict = "insufficient"
                    confidence = 0.50
                    reason = "Language model offline: semantic NLI entailment could not run; advocate verification required."

            is_supported = (verdict == "supports" and confidence >= 0.80)
            item = VerifiedFactItem(
                fact_id=fact.fact_id,
                claim_type=fact.claim_type,
                claim_summary=fact.claim_summary,
                snippet=fact.snippet,
                verdict=verdict,
                confidence=confidence,
                reason=reason,
                needs_human_review=not is_supported,
                source_ref=fact.source_ref,
            )

            if is_supported:
                verified_items.append(item)
            else:
                rejected_items.append(item)

        total = len(input_data.facts)
        rejected_count = len(rejected_items)
        rejection_rate = round(rejected_count / total, 3) if total > 0 else 0.0
        overall_conf = round(1.0 - (rejection_rate * 0.5), 2)
        needs_review = rejected_count > 0 or overall_conf < 0.80

        any_llm = any(not getattr(item, "needs_human_review", False) and item.confidence >= 0.90 for item in verified_items)
        engine_used = "nli" if any_llm else "rules"
        had_offline = any(item.reason and "offline" in item.reason for item in (verified_items + rejected_items))
        status_val = "needs_review" if (had_offline or needs_review) else "live_model"
        err_msg = "Language model offline: semantic NLI verification incomplete; counsel review required." if had_offline else None

        output = FactVerificationOutput(
            document_id=input_data.document_id,
            verified_facts=verified_items,
            rejected_facts=rejected_items,
            total_facts=total,
            verified_count=len(verified_items),
            rejected_count=rejected_count,
            rejection_rate=rejection_rate,
            overall_confidence=overall_conf,
            confidence=overall_conf,
            needs_human_review=needs_review or had_offline,
            engine=engine_used,
            llm_called=any_llm,
            fallback_taken=had_offline,
            status=status_val,
            error_message=err_msg,
            audit_notes=(
                f"FactVerifier: Verified {len(verified_items)}/{total} facts (rejection rate: {rejection_rate*100}%). "
                f"{rejected_count} facts routed to human review."
            ),
        )

        record_audit_event(
            event_type="AGENT_RUN",
            actor=f"agent:{self.agent_name}",
            resource_id=input_data.document_id,
            input_payload={"total_facts": total},
            output_payload={"verified": len(verified_items), "rejected": rejected_count, "rejection_rate": rejection_rate},
            confidence=overall_conf,
            needs_human_review=needs_review,
            status="SUCCESS",
        )

        return output
