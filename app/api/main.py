"""FastAPI main application for LexAgent.

Exposes REST APIs for document ingestion, multi-agent analysis, precedent management,
and append-only audit trails.
"""

import os
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.config import get_settings
from app.db.session import get_db, init_db
from app.db.models import DocumentModel, PrecedentCaseModel, DocumentChunkModel
from app.api.middleware import AuditAndDisclaimerMiddleware
from app.ingestion.pipeline import DocumentIngestor
from app.orchestrator.graph import LegalOrchestrator
from app.security.encryption import decrypt_bytes
from app.security.audit import AuditLogger, record_audit_event
from app.schemas.dossier import LegalIntelligenceReport
from app.llm.embedding import get_embedding_client
from app.api.routers.auth import router as auth_router
from app.api.routers.cases import router as cases_router
from app.api.routers.documents import router as documents_router
from app.api.routers.facts import router as facts_router
from app.api.routers.research import router as research_router
from app.api.routers.audit import router as audit_router
from app.api.routers.contradictions import router as contradictions_router
from app.api.routers.voice import router as voice_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("AUTO_INIT_DB", "false").lower() == "true":
        try:
            init_db()
        except Exception:
            pass
    yield


app = FastAPI(
    title="LexAgent API",
    description="Fully LOCAL, privacy-first multi-agent legal document intelligence system for Indian lawyers.",
    version="1.0.0",
    lifespan=lifespan,
)

# Attach CORS middleware for HTTP client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach audit and disclaimer middleware
app.add_middleware(AuditAndDisclaimerMiddleware)

# Mount Phase 5 Core Intelligence Routers
app.include_router(auth_router)
app.include_router(cases_router)
app.include_router(documents_router)
app.include_router(facts_router)
app.include_router(contradictions_router)
app.include_router(voice_router)
app.include_router(research_router)
app.include_router(audit_router)
app.include_router(research_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(cases_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(facts_router, prefix="/api/v1")
app.include_router(contradictions_router, prefix="/api/v1")
app.include_router(voice_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")


# ---------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------
class HealthResponse(BaseModel):
    status: str
    environment: str
    llm_model: str
    embedding_model: str
    embedding_dimension: int
    local_only_mode: bool = True
    telemetry_enabled: bool = False
    disclaimer: str


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    sha256_hash: str
    page_count: int
    detected_language: str
    chunks_count: int
    status: str = "encrypted_and_stored"
    disclaimer: str


class AnalyzeRequest(BaseModel):
    document_id: Optional[str] = None
    raw_text: Optional[str] = None
    filename: Optional[str] = "brief.pdf"


class SeedCaseItem(BaseModel):
    case_title: str
    citation: str
    court: str
    judgment_date: str
    bench: Optional[str] = None
    summary: str
    ratio_decidendi: str
    full_text: Optional[str] = None


class SeedCaseResponse(BaseModel):
    seeded_count: int
    cases: List[dict]
    disclaimer: str


# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------
@app.get("/api/v1/health", response_model=HealthResponse)
def health_check():
    """System health check and privacy assurance."""
    return HealthResponse(
        status="healthy",
        environment=settings.ENVIRONMENT,
        llm_model=settings.LLM_MODEL,
        embedding_model=settings.EMBEDDING_MODEL,
        embedding_dimension=settings.EMBEDDING_DIM,
        local_only_mode=True,
        telemetry_enabled=False,
        disclaimer=settings.DISCLAIMER_TEXT,
    )


@app.post("/api/v1/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload and ingest a legal document (PDF or text).
    
    Encrypts at rest using AES-256-GCM, chunks with character offsets, embeds,
    and writes append-only audit trail.
    """
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    ingestor = DocumentIngestor()
    result = ingestor.ingest(
        raw_bytes=content,
        filename=file.filename or "document.pdf",
        db_session=db,
    )

    return DocumentUploadResponse(
        document_id=result.document_id,
        filename=result.filename,
        sha256_hash=result.sha256_hash,
        page_count=result.page_count,
        detected_language=result.detected_language,
        chunks_count=result.chunks_count,
        disclaimer=settings.DISCLAIMER_TEXT,
    )


@app.post("/api/v1/analyze", response_model=LegalIntelligenceReport)
def analyze_document(
    request: AnalyzeRequest,
    db: Session = Depends(get_db),
):
    """Run full LangGraph multi-agent legal intelligence pipeline.
    
    Coordinates fact extraction (with source references), timeline/limitation analysis,
    database-verified precedent retrieval, and risk assessment.
    """
    document_id = request.document_id
    text_content = request.raw_text
    filename = request.filename or "legal_matter.pdf"

    if document_id:
        doc_record = db.get(DocumentModel, document_id)
        if not doc_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {document_id} not found in database",
            )
        filename = doc_record.filename
        # Decrypt content at rest using AES-256-GCM
        decrypted_bytes = decrypt_bytes(doc_record.encrypted_content)
        # Extract text from chunks or decrypted payload
        chunks = (
            db.execute(
                select(DocumentChunkModel)
                .where(DocumentChunkModel.document_id == document_id)
                .order_by(DocumentChunkModel.chunk_index)
            )
            .scalars()
            .all()
        )
        if chunks:
            text_content = "\n\n".join([c.text for c in chunks])
        else:
            text_content = decrypted_bytes.decode("utf-8", errors="replace")

    elif not text_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'document_id' or 'raw_text' must be provided",
        )
    else:
        # Ephemeral document ID for direct text analysis
        import uuid
        document_id = str(uuid.uuid4())

    orchestrator = LegalOrchestrator(db_session=db)
    report = orchestrator.analyze_document(
        document_id=document_id,
        raw_text=text_content,
        filename=filename,
    )
    return report


@app.post("/api/v1/cases/seed", response_model=SeedCaseResponse)
def seed_precedents(
    cases: List[SeedCaseItem],
    db: Session = Depends(get_db),
):
    """Seed verified Indian court precedents into local database for retrieval.
    
    Enforces Hard Rule 4: LLM may only summarize text that retrieval returned from DB.
    """
    embed_client = get_embedding_client()
    seeded = []

    for item in cases:
        # Check if citation already exists
        existing = db.execute(
            select(PrecedentCaseModel).where(PrecedentCaseModel.citation == item.citation)
        ).scalars().first()
        
        if existing:
            continue

        # Compute embedding
        case_corpus = f"{item.case_title} {item.summary} {item.ratio_decidendi}"
        emb = embed_client.embed_query(case_corpus)

        record = PrecedentCaseModel(
            case_title=item.case_title,
            citation=item.citation,
            court=item.court,
            judgment_date=item.judgment_date,
            bench=item.bench,
            summary=item.summary,
            ratio_decidendi=item.ratio_decidendi,
            full_text=item.full_text or item.summary,
            embedding=emb,
        )
        db.add(record)
        db.flush()
        seeded.append({
            "id": record.id,
            "case_title": record.case_title,
            "citation": record.citation,
            "court": record.court,
        })

    db.commit()

    record_audit_event(
        event_type="PRECEDENTS_SEEDED",
        actor="system_admin",
        input_payload={"cases_received": len(cases)},
        output_payload={"cases_seeded": len(seeded)},
    )

    return SeedCaseResponse(
        seeded_count=len(seeded),
        cases=seeded,
        disclaimer=settings.DISCLAIMER_TEXT,
    )


@app.get("/api/v1/precedents")
@app.get("/precedents")
def list_precedents(
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """List verified precedents stored in the local database."""
    records = db.execute(select(PrecedentCaseModel).limit(limit)).scalars().all()
    return {
        "count": len(records),
        "cases": [
            {
                "id": str(r.id),
                "case_title": r.case_title,
                "citation": r.citation,
                "court": r.court,
                "judgment_date": r.judgment_date,
                "ratio_decidendi": r.ratio_decidendi,
            }
            for r in records
        ],
        "disclaimer": settings.DISCLAIMER_TEXT,
    }


@app.get("/api/v1/audit/logs")
def get_audit_trail():
    """Retrieve append-only audit log trail for compliance and safety verification."""
    records = AuditLogger.get_records()
    return {
        "total_records": len(records),
        "records": [r.model_dump() for r in records[-50:]],
        "disclaimer": settings.DISCLAIMER_TEXT,
    }


@app.get("/api/v1/audit/verify")
def verify_audit_integrity():
    """Cryptographically verify HMAC SHA-256 hash chain integrity of the audit log."""
    is_valid = AuditLogger.verify_integrity()
    return {
        "integrity_verified": is_valid,
        "hash_chain_status": "INTACT" if is_valid else "CORRUPTED_OR_TAMPERED",
        "disclaimer": settings.DISCLAIMER_TEXT,
    }


# ---------------------------------------------------------
# Static Frontend Mounting (SUTRA UI)
# ---------------------------------------------------------
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_dist_path = Path(__file__).resolve().parents[4] / "SUTRA da UIUX" / "dist"
if _dist_path.exists():
    if (_dist_path / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(_dist_path / "assets")), name="static-assets")

    @app.middleware("http")
    async def spa_fallback_middleware(request: Request, call_next):
        accept = request.headers.get("accept", "")
        path = request.url.path
        if (
            request.method == "GET"
            and "text/html" in accept
            and not path.startswith(("/api", "/auth", "/docs", "/openapi.json", "/redoc", "/assets"))
            and not (_dist_path / path.lstrip("/")).is_file()
        ):
            return FileResponse(_dist_path / "index.html")
        return await call_next(request)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Don't intercept API or docs routes
        if full_path.startswith(("api/", "auth/", "docs", "openapi.json", "redoc")):
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = _dist_path / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_dist_path / "index.html")
