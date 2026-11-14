"""Pytest fixtures and test environment setup for LexAgent."""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Configure test environment variables before importing app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LLM_BASE_URL"] = "http://localhost:11434/v1"
os.environ["LLM_MODEL"] = "qwen2.5:14b-instruct"
os.environ["EMBEDDING_BASE_URL"] = "http://localhost:11434/v1"
os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
os.environ["EMBEDDING_DIM"] = "1024"
os.environ["DOCUMENT_ENCRYPTION_KEY"] = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
os.environ["AUDIT_HMAC_SECRET"] = "test-audit-hmac-secret-123456789012"
os.environ["ENVIRONMENT"] = "testing"

from app.config import get_settings
get_settings.cache_clear()
from app.db.session import reset_engine
reset_engine()
from app.db.session import Base
from app.db.models import DocumentModel, DocumentChunkModel, PrecedentCaseModel, AuditLogModel
from app.llm.client import MockLLMClient, set_llm_client
from app.llm.embedding import MockEmbeddingClient, set_embedding_client
from app.api.main import app
from app.db.session import get_db


from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="session")
def test_engine():
    """Create in-memory SQLite engine with StaticPool so all sessions share the tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db_session(test_engine):
    """Provide a clean isolated DB session per test."""
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        # Clean tables between tests without dropping schema
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


@pytest.fixture(autouse=True)
def setup_mock_clients():
    """Inject mock LLM and embedding clients for all unit tests."""
    mock_llm = MockLLMClient()
    mock_embed = MockEmbeddingClient(dimension=1024)
    set_llm_client(mock_llm)
    set_embedding_client(mock_embed)
    yield mock_llm, mock_embed


@pytest.fixture
def client(db_session):
    """FastAPI test client with database dependency override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
