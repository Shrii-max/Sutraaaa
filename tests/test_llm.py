"""Tests for LLM Client, structured JSON validation, and retry logic."""

from pydantic import BaseModel
from app.llm.client import MockLLMClient, OpenAICompatibleLLMClient, extract_json_from_text
from app.llm.embedding import MockEmbeddingClient, LocalEmbeddingClient


class SampleExtractionSchema(BaseModel):
    court_name: str
    is_maintainable: bool
    confidence: float


def test_extract_json_from_markdown():
    """Verify clean JSON extraction from code blocks and surrounding text."""
    raw = 'Here is the response:\n```json\n{"court_name": "Delhi High Court", "is_maintainable": true, "confidence": 0.9}\n```\nHope this helps.'
    clean = extract_json_from_text(raw)
    assert clean.startswith("{") and clean.endswith("}")
    assert '"court_name": "Delhi High Court"' in clean


def test_mock_llm_client_structured():
    """Verify mock LLM returns validated Pydantic model."""
    client = MockLLMClient(
        responses={
            "TestQuery": {
                "court_name": "Supreme Court of India",
                "is_maintainable": True,
                "confidence": 0.95,
            }
        }
    )
    result, needs_review = client.generate_structured(
        prompt="TestQuery: Check jurisdiction",
        schema=SampleExtractionSchema,
    )
    assert result.court_name == "Supreme Court of India"
    assert result.is_maintainable is True
    assert needs_review is False


def test_hard_rule_9_retry_and_human_review_flag():
    """Enforces Hard Rule 9:
    Retry up to 2 times on validation failure, then flag needs_human_review.
    """
    client = MockLLMClient()
    # Configure mock client to fail validation 3 times (exceeding default 2 retries)
    client.fail_validation_times = 3

    model, needs_review = client.generate_structured(
        prompt="Any prompt",
        schema=SampleExtractionSchema,
        max_retries=2,
    )
    # Retries exhausted -> needs_human_review must be set to True
    assert needs_review is True


def test_embedding_client_dimension():
    """Verify embedding client provides configured vector dimension (default 1024)."""
    embed_client = MockEmbeddingClient(dimension=1024)
    assert embed_client.dimension == 1024

    vec = embed_client.embed_query("Suit for permanent injunction under Specific Relief Act 1963")
    assert len(vec) == 1024
    assert isinstance(vec[0], float)

    batch_vecs = embed_client.embed_documents(["doc 1", "doc 2"])
    assert len(batch_vecs) == 2
    assert len(batch_vecs[0]) == 1024
