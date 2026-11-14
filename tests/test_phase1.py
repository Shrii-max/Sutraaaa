"""Phase 1 Foundation Test Suite.

Verifies:
1. Schema validation across all Phase 1 Pydantic models.
2. chat_json retry behavior with FakeLLMClient.
3. AES-256-GCM crypto round trip and EncryptedFileStore.
4. Database initialization and migration on empty DB.
5. Append-only audit_logs rejecting UPDATE and DELETE operations.
"""

import os
import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.schemas import (
    SourceRef,
    DocumentMeta,
    OCRResult,
    PageOCR,
    LanguageResult,
    PageLanguage,
    ExtractedFacts,
    PartyItem,
    DateItem,
    SectionItem,
    AmountItem,
    LocationItem,
    IncidentItem,
    StatementItem,
    ValidationReport,
    ValidationIssue,
    ContradictionReport,
    ContradictionItem,
    Timeline,
    TimelineEvent,
    CaseSummary,
    SimilarCase,
)
from app.llm.client import FakeLLMClient, FakeEmbedder
from app.security.crypto import encrypt_file, decrypt_file, EncryptedFileStore
from app.db.session import Base, init_db, install_audit_append_only_triggers
from app.db.models import (
    UserModel,
    CaseModel,
    DocumentModel,
    DocumentPageModel,
    FactModel,
    ValidationIssueModel,
    TimelineEventModel,
    ContradictionModel,
    SummaryModel,
    Judgment,
    JudgmentChunk,
    AuditLogModel,
)


# ---------------------------------------------------------
# 1. Schema Validation Tests
# ---------------------------------------------------------
def test_phase1_sourceref_validation():
    """Verify SourceRef validity rules and bounds."""
    ref = SourceRef(
        document_id="doc-101",
        page=2,
        char_start=150,
        char_end=220,
        snippet="FIR registered under Section 420 IPC at Saket PS.",
    )
    assert ref.document_id == "doc-101"
    assert ref.page == 2
    assert ref.char_end > ref.char_start

    # char_end <= char_start must fail
    with pytest.raises(ValidationError):
        SourceRef(
            document_id="doc-101",
            page=1,
            char_start=50,
            char_end=40,
            snippet="Invalid snippet",
        )

    # Empty snippet must fail
    with pytest.raises(ValidationError):
        SourceRef(
            document_id="doc-101",
            page=1,
            char_start=10,
            char_end=20,
            snippet="   ",
        )


def test_phase1_document_meta_and_ocr_and_language():
    """Verify DocumentMeta, OCRResult, and LanguageResult schemas."""
    meta = DocumentMeta(
        doc_id="doc-001",
        filename="chargesheet.pdf",
        doc_type="FIR",
        languages=["en", "hi"],
        page_count=5,
    )
    assert meta.doc_type == "FIR"
    assert meta.page_count == 5

    ocr = OCRResult(
        document_id="doc-001",
        pages=[
            PageOCR(page_number=1, text="State v. Accused", confidence=0.98),
            PageOCR(page_number=2, text="Bail rejected by Sessions Court", confidence=0.95),
        ],
        overall_confidence=0.96,
    )
    assert len(ocr.pages) == 2
    assert ocr.pages[0].confidence == 0.98

    lang = LanguageResult(
        document_id="doc-001",
        pages=[
            PageLanguage(page_number=1, language="english", script="Latin"),
            PageLanguage(page_number=2, language="hindi", script="Devanagari"),
        ],
        primary_language="mixed",
    )
    assert len(lang.pages) == 2
    assert lang.pages[1].script == "Devanagari"


def test_phase1_extracted_facts_all_items_require_sourceref():
    """Verify ExtractedFacts schema with parties, dates, sections, amounts, locations, incidents, statements."""
    src = SourceRef(
        document_id="doc-001",
        page=1,
        char_start=10,
        char_end=80,
        snippet="Complainant Amit Sharma alleged fraud of Rs. 15,00,000 on 12-04-2023 at Connaught Place.",
    )

    facts = ExtractedFacts(
        parties=[
            PartyItem(name="Amit Sharma", role="complainant", source=src, confidence=0.95),
            PartyItem(name="Vikram Singh", role="accused", source=src, confidence=0.92),
        ],
        dates=[
            DateItem(date_str="2023-04-12", description="Date of alleged fraud transaction", source=src, confidence=0.90),
        ],
        sections=[
            SectionItem(act="IPC", section_number="420", description="Cheating and dishonestly inducing delivery", source=src, confidence=0.95),
            SectionItem(act="BNS", section_number="318", description="Cheating under Bharatiya Nyaya Sanhita", source=src, confidence=0.88),
        ],
        amounts=[
            AmountItem(value=1500000.0, currency="INR", context="fraudulent transfer", source=src, confidence=0.99),
        ],
        locations=[
            LocationItem(place="Connaught Place, New Delhi", context="place of meeting", source=src, confidence=0.94),
        ],
        incidents=[
            IncidentItem(title="Inducement and payment", description="Accused induced victim to transfer funds", date="2023-04-12", source=src, confidence=0.91),
        ],
        statements=[
            StatementItem(
                statement_type="161",
                speaker="Amit Sharma",
                role="complainant",
                recorded_on="2023-05-01",
                recorded_by="Sub-Inspector Meena",
                content="Victim stated he handed over cheque upon false assurances.",
                source=src,
                confidence=0.93,
            )
        ],
        purpose="Criminal prosecution for cheating and criminal breach of trust",
        court="Chief Metropolitan Magistrate, Patiala House Courts",
        case_number="CC No. 5432/2023",
    )

    assert len(facts.parties) == 2
    assert facts.sections[0].act == "IPC"
    assert facts.sections[1].act == "BNS"
    assert facts.statements[0].statement_type == "161"
    assert facts.amounts[0].value == 1500000.0


def test_phase1_validation_and_contradiction_and_timeline():
    """Verify ValidationReport, ContradictionReport, and Timeline sorting with importance flag."""
    src_a = SourceRef(document_id="doc-1", page=1, char_start=0, char_end=30, snippet="Accused was in Delhi at 4 PM.")
    src_b = SourceRef(document_id="doc-1", page=2, char_start=50, char_end=85, snippet="Accused was in Mumbai at 4 PM.")

    val_report = ValidationReport(
        document_id="doc-1",
        issues=[
            ValidationIssue(
                severity="HIGH",
                category="EVIDENCE_65B",
                description="WhatsApp chat transcript annexed without Section 65B Evidence Act certificate.",
                source_refs=[src_a],
                suggestion="File supplementary affidavit with Section 65B(4) compliance certificate.",
            )
        ],
        confidence=0.85,
        needs_human_review=True,
    )
    assert len(val_report.issues) == 1
    assert val_report.issues[0].severity == "HIGH"

    contra_report = ContradictionReport(
        contradictions=[
            ContradictionItem(
                statement_a="Accused was in Delhi at 4 PM.",
                statement_b="Accused was in Mumbai at 4 PM.",
                description="Alibi contradicts witness statement regarding physical presence.",
                source_a=src_a,
                source_b=src_b,
                severity="HIGH",
                confidence=0.92,
            )
        ],
        confidence=0.90,
        needs_human_review=True,
    )
    assert len(contra_report.contradictions) == 1
    assert contra_report.contradictions[0].source_a.page == 1
    assert contra_report.contradictions[0].source_b.page == 2

    # Timeline sorting
    ev1 = TimelineEvent(event_id="E2", date_str="2023-06-15", event_title="FIR registered", description="FIR 54/23", is_important=True, source=src_b)
    ev2 = TimelineEvent(event_id="E1", date_str="2023-01-10", event_title="Agreement signed", description="Contract executed", is_important=False, source=src_a)
    timeline = Timeline(events=[ev1, ev2], confidence=0.95, needs_human_review=False)

    # Timeline validator automatically sorts by date
    assert timeline.events[0].date_str == "2023-01-10"
    assert timeline.events[1].date_str == "2023-06-15"
    assert timeline.events[1].is_important is True


def test_phase1_case_summary_and_similar_case():
    """Verify CaseSummary and SimilarCase models."""
    summary = CaseSummary(
        summary_text="Suit for recovery of Rs 25 Lakhs arising out of dishonour of cheque issued towards supply of goods.",
        key_issues=["Whether statutory demand notice was served within 30 days?", "Whether complaint is barred by limitation?"],
        relief_sought="Judgment and decree for Rs 25,00,000 along with pendente lite interest at 18% p.a.",
        confidence=0.92,
        needs_human_review=False,
    )
    assert len(summary.key_issues) == 2
    assert "LEGAL DISCLAIMER" in summary.disclaimer

    similar = SimilarCase(
        case_id="case-sc-001",
        title="Canara Bank v. P. Selathal",
        court="Supreme Court of India",
        date="2020-03-04",
        url="https://main.sci.gov.in/judgment/2020/canara.pdf",
        matched_paragraph="Plaint liable to be rejected under Order VII Rule 11 if cause of action is illusory.",
        score=0.88,
    )
    assert similar.court == "Supreme Court of India"
    assert similar.score == 0.88


# ---------------------------------------------------------
# 2. FakeLLMClient chat_json retry behavior
# ---------------------------------------------------------
class LegalClassificationSchema(BaseModel):
    court: str
    is_maintainable: bool
    limitation_years: int


def test_fake_llm_chat_json_retry_success():
    """Verify chat_json retries twice on failure and succeeds when response is valid."""
    fake_client = FakeLLMClient(
        responses={
            "Maintainability": {
                "court": "Delhi High Court",
                "is_maintainable": True,
                "limitation_years": 3,
            }
        }
    )
    # Simulate 1 initial failure
    fake_client.fail_validation_times = 1

    result = fake_client.chat_json(
        schema=LegalClassificationSchema,
        prompt="Maintainability analysis under Commercial Courts Act",
        max_retries=2,
    )
    assert result.court == "Delhi High Court"
    assert result.is_maintainable is True
    assert result.limitation_years == 3


def test_fake_llm_chat_json_exhausts_retries():
    """Verify chat_json raises ValueError after exhausting 2 retries on invalid output."""
    fake_client = FakeLLMClient()
    # Configure 3 failures (attempt 0, retry 1, retry 2 all fail)
    fake_client.fail_validation_times = 3

    with pytest.raises(ValueError, match="exhausted 2 retries"):
        fake_client.chat_json(
            schema=LegalClassificationSchema,
            prompt="Prompt that fails repeatedly",
            max_retries=2,
        )


def test_fake_embedder_dimension():
    """Verify Embedder interface returns configured dimension vectors."""
    embedder = FakeEmbedder(dimension=1024)
    assert embedder.dimension == 1024
    vec = embedder.embed_query("Anticipatory bail petition under Section 438 CrPC")
    assert len(vec) == 1024
    assert isinstance(vec[0], float)

    batch = embedder.embed(["doc 1", "doc 2"])
    assert len(batch) == 2
    assert len(batch[0]) == 1024


# ---------------------------------------------------------
# 3. AES-256-GCM Crypto Round Trip & File Store
# ---------------------------------------------------------
def test_crypto_round_trip_and_tamper(tmp_path):
    """Verify AES-256-GCM encrypt_file, decrypt_file, and file tampering detection."""
    sample_petition = b"IN THE SUPREME COURT OF INDIA\nSPECIAL LEAVE PETITION (CIVIL) NO. 1234 OF 2024"
    encrypted = encrypt_file(sample_petition)
    assert encrypted != sample_petition

    decrypted = decrypt_file(encrypted)
    assert decrypted == sample_petition

    # Tamper with byte
    tampered = bytearray(encrypted)
    tampered[-5] ^= 0xAA
    with pytest.raises(ValueError, match="tampering detected"):
        decrypt_file(bytes(tampered))


def test_encrypted_file_store(tmp_path):
    """Verify EncryptedFileStore stores encrypted files and retrieves plaintext."""
    store = EncryptedFileStore(storage_dir=str(tmp_path))
    content = b"Vakalatnama executed in favour of Senior Advocate."

    rel_path, sha_hash = store.store(content, "vakalatnama.pdf", case_id="case-100")
    assert rel_path.startswith("case-100/")
    assert len(sha_hash) == 64

    # Verify on-disk file is encrypted
    stored_disk_file = (tmp_path / rel_path).read_bytes()
    assert stored_disk_file != content

    # Retrieve and decrypt
    retrieved = store.retrieve(rel_path)
    assert retrieved == content

    # Delete
    assert store.delete(rel_path) is True
    assert store.delete(rel_path) is False


# ---------------------------------------------------------
# 4. Database Migration on Empty DB
# ---------------------------------------------------------
def test_db_migration_creates_all_tables_on_empty_db():
    """Verify that all Phase 1 models and tables are initialized on an empty database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)

    # Inspect created tables
    from sqlalchemy import inspect
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "users",
        "cases",
        "documents",
        "document_pages",
        "document_chunks",
        "facts",
        "validation_issues",
        "timeline_events",
        "contradictions",
        "summaries",
        "judgments",
        "judgment_chunks",
        "audit_logs",
    }
    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"


# ---------------------------------------------------------
# 5. Append-only audit_logs rejects UPDATE and DELETE
# ---------------------------------------------------------
def test_audit_logs_rejects_update_and_delete():
    """Enforces Hard Rule 5: audit_logs is append-only; blocks UPDATE and DELETE via trigger & listener."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    install_audit_append_only_triggers(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Insert is permitted
    log_row = AuditLogModel(
        id="audit-001",
        event_type="API_ACCESS",
        actor="advocate_user",
        resource_id="/api/v1/documents",
        prev_hash="0" * 64,
        record_hash="a" * 64,
    )
    session.add(log_row)
    session.commit()

    # 2. Attempt UPDATE via ORM -> must be rejected
    with pytest.raises(PermissionError, match="audit_logs table is append-only"):
        log_row.actor = "malicious_actor"
        session.commit()
    session.rollback()

    # 3. Attempt UPDATE via raw SQL -> blocked by database trigger
    with pytest.raises(Exception):
        with engine.connect() as conn:
            conn.execute(text("UPDATE audit_logs SET actor = 'hacker' WHERE id = 'audit-001';"))
            conn.commit()

    # 4. Attempt DELETE via ORM -> must be rejected
    with pytest.raises(PermissionError, match="audit_logs table is append-only"):
        session.delete(log_row)
        session.commit()
    session.rollback()

    # 5. Attempt DELETE via raw SQL -> blocked by database trigger
    with pytest.raises(Exception):
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM audit_logs WHERE id = 'audit-001';"))
            conn.commit()

