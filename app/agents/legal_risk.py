"""Legal and Procedural Risk Assessment Agent for Indian Courts.

Follows Hard Rule 1: One class, typed Pydantic input/output, run() method, no hidden global state.
Follows Hard Rule 3: Output carries confidence and needs_human_review.
"""

import logging
from typing import List
from pydantic import BaseModel, Field
from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)
from app.schemas.risks import (
    LegalRiskItem,
    RiskAnalysisInput,
    RiskAnalysisOutput,
)


class _LLMRiskResponse(BaseModel):
    risks: List[dict] = Field(default_factory=list)
    overall_risk_level: str = "MEDIUM"
    procedural_defects_found: bool = False
    evidence_defects_found: bool = False
    confidence: float = 0.85


class LegalRiskAgent(BaseAgent[RiskAnalysisInput, RiskAnalysisOutput]):
    """Analyzes procedural defects, jurisdictional bars, and evidentiary requirements under Indian law."""

    agent_name: str = "LegalRiskAgent"

    def _execute(self, input_data: RiskAnalysisInput) -> RiskAnalysisOutput:
        facts_summary = "\n".join([
            f"- [{f.fact_id}] {f.statement}"
            for f in input_data.facts
        ])

        limitation_summary = ""
        if input_data.timeline_analysis:
            limitation_summary = (
                f"Limitation Risk: {input_data.timeline_analysis.has_limitation_risk}\n"
                f"Cause of Action: {input_data.timeline_analysis.cause_of_action_identified}\n"
            )

        prompt = (
            f"Evaluate potential legal and procedural risks for the following Indian litigation matter:\n\n"
            f"Facts:\n{facts_summary or 'No facts extracted.'}\n\n"
            f"{limitation_summary}\n"
            f"Check specifically for:\n"
            f"1. Order VII Rule 11 CPC rejection grounds (cause of action, barred by law, valuation)\n"
            f"2. Section 65B Indian Evidence Act / Section 63 BSA certificate for electronic evidence\n"
            f"3. Statutory pre-suit notice (Section 80 CPC, Section 138(b) NI Act)\n"
            f"4. Stamp duty deficiency under Indian Stamp Act 1899\n"
            f"5. Pecuniary / Territorial Jurisdiction\n"
        )

        system = (
            "You are an Indian Senior Advocate's chamber junior specializing in civil & criminal procedure, "
            "identifying jurisdictional risks, evidentiary hurdles, and maintainability defects."
        )

        llm_response, review_needed = self.llm.generate_structured(
            prompt=prompt,
            schema=_LLMRiskResponse,
            system=system,
        )

        risk_items: List[LegalRiskItem] = []
        for idx, r in enumerate(llm_response.risks):
            risk_items.append(
                LegalRiskItem(
                    risk_id=r.get("risk_id", f"RISK-{idx + 1:03d}"),
                    category=r.get("category", "PROCEDURAL_DEFECT"),
                    severity=r.get("severity", "MEDIUM").upper(),
                    statutory_provision=r.get("statutory_provision", "Code of Civil Procedure, 1908"),
                    issue_description=r.get("issue_description", "Procedural check required"),
                    mitigation_strategy=r.get("mitigation_strategy", "Cure defect prior to hearing"),
                )
            )

        # Automated heuristics check: if electronic evidence mentioned without 65B/63 certificate
        text_corpus = " ".join([f.statement for f in input_data.facts]).lower()
        if any(term in text_corpus for term in ["whatsapp", "email", "sms", "call recording", "website printout"]):
            if not any("65b" in r.statutory_provision.lower() or "63" in r.statutory_provision.lower() for r in risk_items):
                risk_items.append(
                    LegalRiskItem(
                        risk_id=f"RISK-{len(risk_items) + 1:03d}",
                        category="EVIDENTIARY_DEFECT",
                        severity="HIGH",
                        statutory_provision="Section 65B Indian Evidence Act / Section 63 Bharatiya Sakshya Adhiniyam",
                        issue_description="Electronic records referenced in facts without explicit Section 65B / 63 compliance certificate.",
                        mitigation_strategy="Procure and file mandatory electronic certificate under Section 65B(4) / Section 63 at the time of leading evidence.",
                    )
                )

        if input_data.timeline_analysis and getattr(input_data.timeline_analysis, "has_limitation_risk", False):
            if not any("limitation" in r.statutory_provision.lower() for r in risk_items):
                coa = getattr(input_data.timeline_analysis, "cause_of_action_identified", None) or "earliest date"
                risk_items.append(
                    LegalRiskItem(
                        risk_id=f"RISK-{len(risk_items) + 1:03d}",
                        category="LIMITATION_BAR",
                        severity="HIGH",
                        statutory_provision="Limitation Act, 1963",
                        issue_description=f"Action appears barred by statutory limitation from cause of action date ({coa}).",
                        mitigation_strategy="File formal Application for Condonation of Delay under Section 5 Limitation Act with sufficient cause affidavit.",
                    )
                )

        has_high_risk = any(r.severity == "HIGH" for r in risk_items)
        if has_high_risk:
            review_needed = True

        confidence = llm_response.confidence
        llm_called = not review_needed
        fallback_taken = review_needed
        engine_used = "llm" if llm_called else "rules"
        status_val = "live_model" if llm_called else "needs_review"
        err_msg = "Language model unreachable: risk assessment based on statutory heuristics only." if fallback_taken else None

        logger.info(
            "AGENT_EXECUTION agent=LegalRiskAgent engine=%s llm_called=%s fallback_taken=%s",
            engine_used,
            llm_called,
            fallback_taken,
        )

        return RiskAnalysisOutput(
            document_id=input_data.document_id,
            risks=risk_items,
            overall_risk_level="HIGH" if has_high_risk else llm_response.overall_risk_level,
            procedural_defects_found=bool(risk_items),
            evidence_defects_found=any(r.category == "EVIDENTIARY_DEFECT" for r in risk_items),
            confidence=round(confidence, 2),
            needs_human_review=review_needed,
            engine=engine_used,
            llm_called=llm_called,
            fallback_taken=fallback_taken,
            status=status_val,
            error_message=err_msg,
            audit_notes=f"Identified {len(risk_items)} legal risk factors.",
        )

