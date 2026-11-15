"""Document Classification and Purpose Extraction Agent.

Follows Requirement:
3. DocumentClassifierAgent: LLM + rules to classify document type and state the PURPOSE
   of the document in 2-3 lines (who is filing, before which court, what relief is sought).
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from app.agents.base import BaseAgent
from app.schemas.common import BaseAgentInput, BaseAgentOutput
from app.schemas.document import DocumentType, DocumentMeta
from app.llm.client import LLMClient, get_llm_client
from app.security.guardrails import wrap_as_document_data, format_safe_system_prompt


class ClassificationResultSchema(BaseModel):
    doc_type: DocumentType = Field(..., description="FIR, petition, judgment, affidavit, witness_statement, order, other")
    purpose: str = Field(..., description="2-3 line statement: who is filing, before which court, what relief is sought")
    filing_party: Optional[str] = Field(default=None, description="Party filing the document")
    opposite_party: Optional[str] = Field(default=None, description="Opposite party / respondent / accused")
    court_named: Optional[str] = Field(default=None, description="Court or police station")
    relief_sought: Optional[str] = Field(default=None, description="Specific prayer or remedy requested")
    confidence: float = Field(default=0.88, ge=0.0, le=1.0)


class DocumentClassifierInput(BaseAgentInput):
    document_id: str
    text_content: str
    filename: str = "document.pdf"
    page_count: int = 1
    detected_languages: List[str] = Field(default_factory=lambda: ["en"])


class DocumentClassifierOutput(BaseAgentOutput):
    document_meta: DocumentMeta
    purpose: str
    filing_party: Optional[str] = None
    opposite_party: Optional[str] = None
    court_named: Optional[str] = None
    relief_sought: Optional[str] = None


class DocumentClassifierAgent(BaseAgent[DocumentClassifierInput, DocumentClassifierOutput]):
    """Classifies Indian legal document type and articulates legal purpose via rules and LLM."""

    agent_name: str = "DocumentClassifierAgent"

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(llm_client=llm_client)

    def _execute(self, input_data: DocumentClassifierInput) -> DocumentClassifierOutput:
        text_sample = input_data.text_content[:4000]

        # Rule heuristics
        rule_type = self._detect_rule_type(text_sample, input_data.filename)

        prompt = (
            f"Analyze the following legal text excerpt from '{input_data.filename}' and provide:\n"
            f"1. Document Type: Choose strictly from 'FIR', 'petition', 'judgment', 'affidavit', "
            f"'witness_statement', 'order', 'other'. (Hint from rules: '{rule_type}')\n"
            f"2. Purpose: State the PURPOSE of the document in 2-3 lines (who is filing, before which court, what relief is sought).\n"
            f"3. Specific filing party, court, and relief.\n\n"
            f"Document Excerpt:\n"
            f"{wrap_as_document_data(text_sample)}"
        )

        system = format_safe_system_prompt(
            "You are an Indian Senior Advocate's chamber junior specializing in document categorization. "
            "Accurately determine the document category and formulate a concise 2-3 line purpose statement."
        )

        llm_response, review_needed = self.llm.generate_structured(
            prompt=prompt,
            schema=ClassificationResultSchema,
            system=system,
        )

        # Fallback to rule_type if LLM produced 'other', None, or failed
        final_doc_type = llm_response.doc_type if hasattr(llm_response, "doc_type") and llm_response.doc_type else rule_type
        if (final_doc_type == "other" or not final_doc_type) and rule_type != "other":
            final_doc_type = rule_type
        if not final_doc_type:
            final_doc_type = "other"

        # Ensure purpose is formulated accurately
        purpose_str = (
            llm_response.purpose
            if hasattr(llm_response, "purpose") and llm_response.purpose
            else f"Document filed by {getattr(llm_response, 'filing_party', None) or 'complainant/petitioner'} "
                 f"before {getattr(llm_response, 'court_named', None) or 'the judicial forum'} "
                 f"seeking {getattr(llm_response, 'relief_sought', None) or 'appropriate legal remedy'}."
        )

        reported_conf = float(getattr(llm_response, "confidence", 0.80) or 0.80)
        if review_needed:
            reported_conf = min(reported_conf, 0.70)

        doc_meta = DocumentMeta(
            doc_id=input_data.document_id,
            filename=input_data.filename,
            doc_type=final_doc_type,
            languages=input_data.detected_languages,
            page_count=input_data.page_count,
        )

        return DocumentClassifierOutput(
            document_meta=doc_meta,
            purpose=purpose_str,
            filing_party=getattr(llm_response, "filing_party", None),
            opposite_party=getattr(llm_response, "opposite_party", None),
            court_named=getattr(llm_response, "court_named", None),
            relief_sought=getattr(llm_response, "relief_sought", None),
            confidence=round(reported_conf, 2),
            needs_human_review=review_needed or (reported_conf < 0.75),
            audit_notes=f"Classified document as '{final_doc_type}' with confidence {reported_conf:.2f}.",
        )

    @staticmethod
    def _detect_rule_type(text: str, filename: str) -> DocumentType:
        t = text.lower()
        f = filename.lower()

        # Check witness statement first if filename or text explicitly denotes witness statement
        if (
            "witness" in f
            or "statement" in f
            or "pw" in f
            or "dw" in f
            or "statement of witness" in t
            or "under section 161" in t
            or "section 161" in t
            or "161 cr" in t
            or "section 164" in t
            or "बयान धारा 161" in t
            or "examination-in-chief" in t
            or "cross-examination" in t
        ):
            return "witness_statement"

        if "fir" in f or "first information report" in t or "प्रथम सूचना रिपोर्ट" in t or ("u/s" in t and "police station" in t):
            return "FIR"
        if "affidavit" in t or "solemnly affirm" in t or "deponent" in t or "शपथ पत्र" in t:
            return "affidavit"
        if "judgment" in t or "coram:" in t or "bench:" in t or "appeal dismissed" in t or "appeal allowed" in t:
            return "judgment"
        if "petition" in t or "suit for" in t or "writ petition" in t or "special leave petition" in t or "prayer" in t or "परिवाद" in t:
            return "petition"
        if "interim order" in t or "notice returnable" in t or "court order" in t:
            return "order"
        return "other"

