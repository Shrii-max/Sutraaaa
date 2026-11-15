"""Documents router: Per-document intelligence inspections.

Endpoints:
  GET /documents/{id}/status
  GET /documents/{id}/summary
  GET /documents/{id}/facts
  GET /documents/{id}/validation
"""

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import UserModel
from app.security.jwt import require_lawyer
from app.services.document_manager import DocumentManager
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/documents", tags=["Document Intelligence"])


@router.get("/{id}/pdf")
def get_document_pdf(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Serve the original PDF to an authorized case owner."""
    from app.db.models import DocumentModel
    from app.security.crypto import decrypt_file

    document = db.get(DocumentModel, id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    DocumentManager(db)._verify_document_access(document, current_user.id, current_user.role == "admin")
    if not document.filename.lower().endswith(".pdf") or not document.encrypted_content:
        raise HTTPException(status_code=404, detail="Original PDF is unavailable.")
    try:
        content = decrypt_file(document.encrypted_content)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="The saved PDF could not be decrypted.") from exc
    if b"%PDF-" not in content[:1024]:
        raise HTTPException(status_code=415, detail="Original document does not contain a PDF.")
    return Response(content, media_type="application/pdf", headers={
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })


@router.post("/{id}/retry", status_code=202)
def retry_document(
    id: str,
    background_tasks: BackgroundTasks,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    return DocumentManager(db).retry_document(id, current_user.id, current_user.role == "admin", background_tasks)


@router.get("/{id}/status")
def get_document_status(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Get per-step execution status (pending, running, done, failed, needs_review) and crash recovery state."""
    manager = DocumentManager(db)
    is_admin = (current_user.role == "admin")
    return manager.get_status(document_id=id, user_id=current_user.id, is_admin=is_admin)


@router.get("/{id}/summary")
def get_document_summary(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Get concise executive summary and key points with SourceRefs."""
    manager = DocumentManager(db)
    is_admin = (current_user.role == "admin")
    return manager.get_summary(document_id=id, user_id=current_user.id, is_admin=is_admin)


@router.get("/{id}/facts")
def get_document_facts(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Get extracted facts with mandatory provenance (document_id, page, offsets, snippet) and review state."""
    manager = DocumentManager(db)
    is_admin = (current_user.role == "admin")
    return manager.get_facts(document_id=id, user_id=current_user.id, is_admin=is_admin)


@router.get("/{id}/validation")
def get_document_validation(
    id: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Get statutory validation defects, chronological anomalies, and missing verification issues."""
    manager = DocumentManager(db)
    is_admin = (current_user.role == "admin")
    return manager.get_validation(document_id=id, user_id=current_user.id, is_admin=is_admin)


# -----------------------------------------------------------------------------
# OCR v2 Side-by-Side Inspection & Advocate Correction Endpoints
# -----------------------------------------------------------------------------
from pydantic import BaseModel, Field
from app.schemas.translation import TranslatedDocument


class TranslationRequest(BaseModel):
    target_language: str = Field(default="hi", description="Target ISO language code (e.g. hi, mr, ta, bn)")
    source_language: str = Field(default="en", description="Source ISO language code (e.g. en, hi, mr)")
    engine: Literal["configured", "local_llm", "grok"] = "configured"
    allow_external_translation: bool = False
    first_page: int | None = Field(default=None, ge=1)
    last_page: int | None = Field(default=None, ge=1)


class OCRCorrectionRequest(BaseModel):
    corrected_text: str = Field(..., description="Advocate-verified textual content for the page")
    retrigger_pipeline: bool = Field(default=True, description="Whether to re-run fact extraction with corrected text")


@router.get("/{id}/pages/{page_num}/ocr-inspect")
def get_page_ocr_inspection(
    id: str,
    page_num: int,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Side-by-side inspection API returning page image thumbnail, extracted text, and confidences."""
    manager = DocumentManager(db)
    is_admin = (current_user.role == "admin")
    return manager.get_ocr_inspection(document_id=id, page_number=page_num, user_id=current_user.id, is_admin=is_admin)


@router.get("/{id}/pages/{page_num}/image")
def get_page_image(
    id: str,
    page_num: int,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Returns page image data for frontend side-by-side verification."""
    manager = DocumentManager(db)
    is_admin = (current_user.role == "admin")
    data = manager.get_ocr_inspection(document_id=id, page_number=page_num, user_id=current_user.id, is_admin=is_admin)
    return {"document_id": id, "page_number": page_num, "image_base64": data["image_base64"]}


@router.post("/{id}/pages/{page_num}/ocr-correct")
def correct_page_ocr(
    id: str,
    page_num: int,
    payload: OCRCorrectionRequest,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Advocate corrections for smudged or misrecognized OCR pages."""
    manager = DocumentManager(db)
    is_admin = (current_user.role == "admin")
    return manager.correct_ocr_text(
        document_id=id,
        page_number=page_num,
        corrected_text=payload.corrected_text,
        user_id=current_user.id,
        retrigger=payload.retrigger_pipeline,
        is_admin=is_admin,
    )


# -----------------------------------------------------------------------------
# Multilingual Translation Endpoints (Phase B)
# -----------------------------------------------------------------------------
@router.post("/{id}/translate", response_model=TranslatedDocument)
def translate_document(
    id: str,
    payload: TranslationRequest,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Translate all pages of a document into target language preserving sentence-level SourceRefs."""
    manager = DocumentManager(db)
    is_admin = (current_user.role == "admin")
    return manager.translate_document(
        document_id=id,
        engine=payload.engine,
        allow_external_translation=payload.allow_external_translation,
        first_page=payload.first_page,
        last_page=payload.last_page,
        target_language=payload.target_language,
        source_language=payload.source_language,
        user_id=current_user.id,
        is_admin=is_admin,
    )


@router.get("/{id}/translations/{lang}", response_model=TranslatedDocument)
def get_document_translation(
    id: str,
    lang: str,
    current_user: UserModel = Depends(require_lawyer),
    db: Session = Depends(get_db),
):
    """Fetch previously computed translation for a document in a target language."""
    manager = DocumentManager(db)
    is_admin = (current_user.role == "admin")
    return manager.get_document_translation(
        document_id=id,
        target_language=lang,
        user_id=current_user.id,
        is_admin=is_admin,
    )



