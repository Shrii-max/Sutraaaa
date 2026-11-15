"""Document Manager Service.

Handles secure upload with AES-256-GCM encryption, document processing execution,
fact review/correction workflows, and audit tracking.
"""

import hashlib
import json
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models import (
    CaseModel,
    DocumentModel,
    DocumentPage as DocumentPageModel,
    DocumentTranslationModel,
    FactModel,
    ValidationIssueModel,
    SummaryModel,
    ProcessingStepModel,
)
from app.agents.translation import TranslationAgent
from app.schemas.translation import (
    TranslationInput,
    TranslatedDocument,
    TranslatedPage,
    SentenceAlignment,
    TranslationIssue,
)
from app.security.crypto import encrypt_file
from app.security.guardrails import validate_file_upload, mask_pii
from app.security.audit import record_audit_event
from app.config import get_settings
from app.orchestrator.graph import ProcessingOrchestrator


class DocumentManager:
    """Manages document uploads, lifecycle states, and human-in-the-loop review."""

    def __init__(self, db_session: Session):
        self.session = db_session
        self.settings = get_settings()

    def _verify_document_access(self, doc: DocumentModel, user_id: str, is_admin: bool = False) -> DocumentModel:
        """Enforce tenant isolation on document access through parent case."""
        if not is_admin:
            if doc.case and doc.case.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: You do not have permission to access document '{doc.id}'.",
                )
        return doc

    def upload_document(
        self,
        case_id: str,
        user_id: str,
        filename: str,
        content: bytes,
        background_tasks: Optional[BackgroundTasks] = None,
        is_admin: bool = False,
    ) -> DocumentModel:
        """Upload, encrypt at rest (AES-256-GCM), and initiate processing pipeline."""
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded document is empty.",
            )

        # Enforce file size guardrail (Phase 6)
        validate_file_upload(content)

        # Verify case ownership
        case = self.session.get(CaseModel, case_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case with ID '{case_id}' was not found.",
            )
        if not is_admin and case.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You cannot upload documents to a case you do not own.",
            )

        sha256_hash = hashlib.sha256(content).hexdigest()
        encrypted_bytes = encrypt_file(content)

        doc = DocumentModel(
            case_id=case.id,
            filename=filename,
            encrypted_content=encrypted_bytes,
            sha256_hash=sha256_hash,
            status="pending",
        )
        self.session.add(doc)
        self.session.commit()
        self.session.refresh(doc)

        record_audit_event(
            event_type="DOCUMENT_UPLOADED",
            actor=f"user:{user_id}",
            resource_id=doc.id,
            input_payload={"filename": filename, "sha256": sha256_hash, "size": len(content)},
            output_payload={"document_id": doc.id, "case_id": case.id, "status": "pending"},
            status="SUCCESS",
        )

        # Kick off processing pipeline
        def _run_pipeline(doc_id: str, case_id_val: str, raw_content: bytes, fname: str):
            orchestrator = ProcessingOrchestrator(db_session=self.session)
            orchestrator.process_document(
                document_id=doc_id,
                file_bytes=raw_content,
                filename=fname,
                case_id=case_id_val,
            )

        if background_tasks:
            background_tasks.add_task(_run_pipeline, doc.id, case.id, content, filename)
        else:
            # Synchronous processing if no background runner supplied
            _run_pipeline(doc.id, case.id, content, filename)
            self.session.refresh(doc)

        return doc

    def get_status(self, document_id: str, user_id: str, is_admin: bool = False) -> Dict[str, Any]:
        """Retrieve execution and lifecycle status for a document."""
        doc = self.session.get(DocumentModel, document_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found.")
        self._verify_document_access(doc, user_id, is_admin)

        stmt = (
            select(ProcessingStepModel)
            .where(ProcessingStepModel.document_id == doc.id)
            .order_by(ProcessingStepModel.created_at.asc())
        )
        steps = self.session.execute(stmt).scalars().all()

        return {
            "document_id": doc.id,
            "filename": doc.filename,
            "status": doc.status,
            "doc_type": doc.doc_type,
            "detected_language": doc.detected_language,
            "page_count": doc.page_count,
            "steps": [
                {
                    "step_name": s.step_name,
                    "status": s.status,
                    "attempt": s.attempt,
                    "error_message": s.error_message,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                }
                for s in steps
            ],
            "disclaimer": self.settings.DISCLAIMER_TEXT,
        }

    def get_summary(self, document_id: str, user_id: str, is_admin: bool = False) -> Dict[str, Any]:
        """Retrieve executive summary and key points for a document."""
        doc = self.session.get(DocumentModel, document_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found.")
        self._verify_document_access(doc, user_id, is_admin)

        stmt = select(SummaryModel).where(SummaryModel.document_id == doc.id).order_by(SummaryModel.created_at.desc())
        summary = self.session.execute(stmt).scalars().first()
        if not summary:
            return {
                "document_id": doc.id,
                "summary": None,
                "message": "Summary processing has not completed yet or is pending.",
                "disclaimer": self.settings.DISCLAIMER_TEXT,
            }

        key_issues = []
        if summary.key_issues:
            try:
                key_issues = json.loads(summary.key_issues)
            except Exception:
                key_issues = []

        return {
            "document_id": doc.id,
            "summary": summary.summary_text,
            "key_issues": key_issues,
            "relief_sought": summary.relief_sought,
            "confidence": summary.confidence,
            "needs_human_review": summary.needs_human_review,
            "disclaimer": self.settings.DISCLAIMER_TEXT,
        }

    def get_facts(self, document_id: str, user_id: str, is_admin: bool = False) -> Dict[str, Any]:
        """Retrieve extracted facts with provenance and verification status."""
        doc = self.session.get(DocumentModel, document_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found.")
        self._verify_document_access(doc, user_id, is_admin)

        stmt = select(FactModel).where(FactModel.document_id == doc.id).order_by(FactModel.created_at.asc())
        facts = self.session.execute(stmt).scalars().all()

        formatted_facts = []
        for f in facts:
            item_dict = {}
            source_dict = {}
            correction_dict = None
            try:
                item_dict = json.loads(f.item_data)
            except Exception:
                pass
            try:
                source_dict = json.loads(f.source_ref)
            except Exception:
                pass
            if f.correction_data:
                try:
                    correction_dict = json.loads(f.correction_data)
                except Exception:
                    pass

            formatted_facts.append({
                "fact_id": f.id,
                "category": f.category,
                "confidence": f.confidence,
                "is_reviewed": f.is_reviewed,
                "reviewed_by": f.reviewed_by,
                "review_action": f.review_action,
                "correction_data": correction_dict,
                "item_data": item_dict,
                "source_ref": source_dict,
            })

        return {
            "document_id": doc.id,
            "total_facts": len(formatted_facts),
            "facts": formatted_facts,
            "disclaimer": self.settings.DISCLAIMER_TEXT,
        }

    def get_validation(self, document_id: str, user_id: str, is_admin: bool = False) -> Dict[str, Any]:
        """Retrieve validation issues, chronological defects, and procedural flags."""
        doc = self.session.get(DocumentModel, document_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found.")
        self._verify_document_access(doc, user_id, is_admin)

        stmt = select(ValidationIssueModel).where(ValidationIssueModel.document_id == doc.id)
        issues = self.session.execute(stmt).scalars().all()

        formatted_issues = []
        for i in issues:
            s_refs = []
            try:
                s_refs = json.loads(i.source_refs)
            except Exception:
                pass
            formatted_issues.append({
                "id": i.id,
                "severity": i.severity,
                "category": i.category,
                "description": i.description,
                "suggestion": i.suggestion,
                "source_refs": s_refs,
            })

        return {
            "document_id": doc.id,
            "total_issues": len(formatted_issues),
            "issues": formatted_issues,
            "disclaimer": self.settings.DISCLAIMER_TEXT,
        }

    def review_fact(
        self,
        fact_id: str,
        user_id: str,
        action: str,
        correction_data: Optional[Dict[str, Any]] = None,
        is_admin: bool = False,
    ) -> Dict[str, Any]:
        """Lawyer approves or corrects an extracted fact; stores the correction and audit trail."""
        valid_actions = ["approved", "corrected", "rejected"]
        if action.lower() not in valid_actions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid review action '{action}'. Must be one of: {valid_actions}",
            )

        fact = self.session.get(FactModel, fact_id)
        if not fact:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Fact '{fact_id}' not found.")

        # Check tenant access via document or case
        if fact.document:
            self._verify_document_access(fact.document, user_id, is_admin)
        elif fact.case_id and not is_admin:
            case = self.session.get(CaseModel, fact.case_id)
            if case and case.user_id != user_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

        fact.is_reviewed = True
        fact.reviewed_by = user_id
        fact.review_action = action.lower()
        if correction_data:
            fact.correction_data = json.dumps(correction_data)

        self.session.commit()

        record_audit_event(
            event_type="FACT_REVIEWED",
            actor=f"user:{user_id}",
            resource_id=fact.id,
            input_payload={"action": action, "correction": correction_data},
            output_payload={"fact_id": fact.id, "status": "reviewed"},
            status="SUCCESS",
        )

        return {
            "fact_id": fact.id,
            "is_reviewed": True,
            "reviewed_by": user_id,
            "review_action": fact.review_action,
            "correction_data": correction_data,
            "disclaimer": self.settings.DISCLAIMER_TEXT,
        }

    def get_ocr_inspection(self, document_id: str, page_number: int, user_id: str, is_admin: bool = False) -> Dict[str, Any]:
        """Retrieve page image thumbnail and OCR text for side-by-side inspection."""
        from app.db.models import DocumentPageModel
        doc = self.session.get(DocumentModel, document_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found.")
        self._verify_document_access(doc, user_id, is_admin)

        page_stmt = select(DocumentPageModel).where(
            DocumentPageModel.document_id == document_id,
            DocumentPageModel.page_number == page_number,
        )
        page = self.session.scalar(page_stmt)
        if not page:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Page {page_number} not found for document '{document_id}'.")

        word_confs = []
        if page.word_confidences_json:
            try:
                word_confs = json.loads(page.word_confidences_json)
            except Exception:
                pass

        # Generate lightweight placeholder image if none stored
        img_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        return {
            "document_id": document_id,
            "page_number": page.page_number,
            "text": page.text,
            "confidence": page.confidence,
            "has_handwriting": getattr(page, "has_handwriting", False),
            "has_stamp": getattr(page, "has_stamp", False),
            "has_signature": getattr(page, "has_signature", False),
            "word_confidences": word_confs,
            "is_corrected": getattr(page, "is_corrected", False),
            "corrected_text": getattr(page, "corrected_text", None),
            "image_base64": img_b64,
            "needs_review": page.confidence < self.settings.OCR_CONFIDENCE_THRESHOLD,
            "disclaimer": self.settings.DISCLAIMER_TEXT,
        }

    def correct_ocr_text(
        self,
        document_id: str,
        page_number: int,
        corrected_text: str,
        user_id: str,
        retrigger: bool = True,
        is_admin: bool = False,
    ) -> Dict[str, Any]:
        """Advocate correction of OCR errors; re-triggers downstream fact extraction."""
        from app.db.models import DocumentPageModel
        doc = self.session.get(DocumentModel, document_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found.")
        self._verify_document_access(doc, user_id, is_admin)

        page_stmt = select(DocumentPageModel).where(
            DocumentPageModel.document_id == document_id,
            DocumentPageModel.page_number == page_number,
        )
        page = self.session.scalar(page_stmt)
        if not page:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Page {page_number} not found.")

        old_text = page.text
        page.text = corrected_text
        page.corrected_text = corrected_text
        page.is_corrected = True
        page.confidence = 1.0  # Advocate confirmed
        self.session.commit()

        record_audit_event(
            event_type="OCR_CORRECTION",
            actor=f"user:{user_id}",
            resource_id=f"{document_id}#p{page_number}",
            input_payload={"old_len": len(old_text), "new_len": len(corrected_text)},
            output_payload={"status": "corrected", "page": page_number},
            confidence=1.0,
            needs_human_review=False,
            status="SUCCESS",
        )

        if retrigger:
            try:
                orchestrator = ProcessingOrchestrator(self.session)
                orchestrator.process_document(document_id=document_id)
            except Exception as e:
                pass

        return {
            "document_id": document_id,
            "page_number": page_number,
            "status": "corrected",
            "is_corrected": True,
            "retriggered": retrigger,
            "disclaimer": self.settings.DISCLAIMER_TEXT,
        }

    def translate_document(
        self,
        document_id: str,
        target_language: str,
        user_id: str,
        source_language: str = "en",
        is_admin: bool = False,
    ) -> TranslatedDocument:
        """Translate all pages of a document preserving sentence-level SourceRef provenance."""
        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        doc = self.session.scalar(stmt)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{document_id}' not found.",
            )

        self._verify_document_access(doc, user_id, is_admin)

        # Collect page texts in order
        page_stmt = (
            select(DocumentPageModel)
            .where(DocumentPageModel.document_id == document_id)
            .order_by(DocumentPageModel.page_number.asc())
        )
        pages = list(self.session.scalars(page_stmt))

        pages_data = []
        if pages:
            for p in pages:
                txt = p.corrected_text if p.is_corrected and p.corrected_text else p.text
                pages_data.append({"page_number": p.page_number, "text": txt})
        else:
            pages_data = [{"page_number": 1, "text": ""}]

        agent = TranslationAgent()
        inp = TranslationInput(
            document_id=document_id,
            case_id=doc.case_id,
            pages_data=pages_data,
            source_language=source_language,
            target_language=target_language,
            preserve_glossary=True,
            verify_backtranslation=True,
        )
        result = agent.run(inp)

        # Persist to document_translations table
        alignments_list = []
        for p in result.pages:
            for al in p.alignments:
                alignments_list.append(al.model_dump())

        issues_list = [iss.model_dump() for iss in result.issues]

        record = DocumentTranslationModel(
            document_id=doc.id,
            case_id=doc.case_id,
            content_hash=result.content_hash or hashlib.sha256(result.full_translated_text.encode()).hexdigest(),
            source_language=source_language,
            target_language=target_language,
            translation_type="document",
            translated_text=result.full_translated_text,
            alignments_json=json.dumps(alignments_list, ensure_ascii=False),
            issues_json=json.dumps(issues_list, ensure_ascii=False),
            confidence=result.confidence,
            needs_human_review=result.needs_human_review,
            disclaimer=result.disclaimer,
        )
        self.session.add(record)
        self.session.commit()

        return result

    def get_document_translation(
        self,
        document_id: str,
        target_language: str,
        user_id: str,
        is_admin: bool = False,
    ) -> TranslatedDocument:
        """Fetch previously computed translation for a document in a target language."""
        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        doc = self.session.scalar(stmt)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{document_id}' not found.",
            )

        self._verify_document_access(doc, user_id, is_admin)

        trans_stmt = (
            select(DocumentTranslationModel)
            .where(
                DocumentTranslationModel.document_id == document_id,
                DocumentTranslationModel.target_language == target_language.lower(),
                DocumentTranslationModel.translation_type == "document",
            )
            .order_by(DocumentTranslationModel.created_at.desc())
        )
        record = self.session.scalars(trans_stmt).first()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No translation found for document '{document_id}' in language '{target_language}'.",
            )

        # Reconstruct TranslatedDocument
        alignments_data = json.loads(record.alignments_json) if record.alignments_json else []
        issues_data = json.loads(record.issues_json) if record.issues_json else []

        # Group alignments by page
        page_alignments_map: Dict[int, List[SentenceAlignment]] = {}
        for item in alignments_data:
            al = SentenceAlignment.model_validate(item)
            p_num = al.source_ref.page
            if p_num not in page_alignments_map:
                page_alignments_map[p_num] = []
            page_alignments_map[p_num].append(al)

        # Build pages
        pages = []
        if page_alignments_map:
            for p_num in sorted(page_alignments_map.keys()):
                als = page_alignments_map[p_num]
                s_text = " ".join([a.source_sentence for a in als])
                t_text = " ".join([a.target_sentence for a in als])
                pages.append(
                    TranslatedPage(
                        page_number=p_num,
                        source_text=s_text,
                        translated_text=t_text,
                        alignments=als,
                    )
                )
        else:
            pages.append(
                TranslatedPage(
                    page_number=1,
                    source_text="",
                    translated_text=record.translated_text,
                    alignments=[],
                )
            )

        issues = [TranslationIssue.model_validate(iss) for iss in issues_data]

        return TranslatedDocument(
            document_id=document_id,
            source_language=record.source_language,
            target_language=record.target_language,
            pages=pages,
            full_translated_text=record.translated_text,
            issues=issues,
            content_hash=record.content_hash,
            confidence=record.confidence or 0.90,
            needs_human_review=record.needs_human_review or False,
            disclaimer=record.disclaimer,
        )



