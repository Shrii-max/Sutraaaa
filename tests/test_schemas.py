"""Tests for Pydantic v2 schemas and Hard Rules 2, 3, 10."""

import pytest
from pydantic import ValidationError
from app.schemas.source import SourceReference
from app.schemas.facts import FactItem, DocumentExtractionOutput
from app.schemas.common import BaseAgentOutput


def test_source_reference_valid():
    """Verify valid source reference instantiation."""
    src = SourceReference(
        document_id="doc-123",
        page=1,
        char_start=10,
        char_end=50,
        snippet="Defendant issued cheque dated 10-02-2023",
    )
    assert src.page == 1
    assert src.char_start == 10
    assert src.char_end == 50


def test_source_reference_invalid_ranges():
    """Verify rejection when char_end <= char_start or snippet is empty."""
    with pytest.raises(ValidationError):
        SourceReference(
            document_id="doc-1",
            page=1,
            char_start=50,
            char_end=40,  # char_end less than char_start
            snippet="Some snippet",
        )

    with pytest.raises(ValidationError):
        SourceReference(
            document_id="doc-1",
            page=1,
            char_start=10,
            char_end=20,
            snippet="   ",  # empty snippet
        )


def test_fact_requires_source_reference():
    """Enforces Hard Rule 2: Every fact MUST carry a source reference. Missing = rejected."""
    # Attempting to create fact without source must fail
    with pytest.raises(ValidationError):
        FactItem(
            fact_id="FACT-001",
            category="PAYMENT",
            statement="Cheque dishonoured for insufficient funds",
            # missing source
        )


def test_document_extraction_output_source_integrity():
    """Enforce that DocumentExtractionOutput validates all facts have SourceReference."""
    src = SourceReference(
        document_id="doc-001",
        page=1,
        char_start=0,
        char_end=25,
        snippet="Verifiable factual text",
    )
    fact = FactItem(
        fact_id="F-1",
        category="BREACH",
        statement="Verifiable factual text",
        source=src,
    )
    output = DocumentExtractionOutput(
        document_id="doc-001",
        detected_language="english",
        facts=[fact],
        confidence=0.9,
        needs_human_review=False,
    )
    assert len(output.facts) == 1
    assert output.facts[0].source.char_end == 25


def test_base_agent_output_safety_fields():
    """Enforces Hard Rule 3 and 10: confidence (0-1), needs_human_review (bool), disclaimer."""
    # Valid output
    out = BaseAgentOutput(confidence=0.85, needs_human_review=False)
    assert 0.0 <= out.confidence <= 1.0
    assert out.needs_human_review is False
    assert "LEGAL DISCLAIMER" in out.disclaimer

    # Invalid confidence (< 0 or > 1)
    with pytest.raises(ValidationError):
        BaseAgentOutput(confidence=1.5, needs_human_review=False)
    with pytest.raises(ValidationError):
        BaseAgentOutput(confidence=-0.1, needs_human_review=False)

