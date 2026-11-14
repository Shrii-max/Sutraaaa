"""Test package initialization."""
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENVIRONMENT"] = "testing"
os.environ["LLM_BASE_URL"] = "http://localhost:11434/v1"
os.environ["LLM_MODEL"] = "qwen2.5:14b-instruct"
os.environ["EMBEDDING_BASE_URL"] = "http://localhost:11434/v1"
os.environ["EMBEDDING_MODEL"] = "BAAI/bge-m3"
os.environ["EMBEDDING_DIM"] = "1024"
os.environ["DOCUMENT_ENCRYPTION_KEY"] = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
os.environ["AUDIT_HMAC_SECRET"] = "test-audit-hmac-secret-123456789012"

from app.config import get_settings
get_settings.cache_clear()

