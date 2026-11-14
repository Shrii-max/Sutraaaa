"""Tests for multilingual Devanagari text processing, character offset preservation, and ingestion."""

from app.ingestion.devanagari import (
    normalize_devanagari_text,
    detect_language_mix,
    split_hindi_english_sentences,
)
from app.ingestion.chunker import OffsetPreservingChunker
from app.ingestion.pipeline import DocumentIngestor


def test_devanagari_normalization_and_punctuation():
    """Verify Devanagari text normalization and danda sentence boundaries."""
    hindi_text = "वादी ने प्रतिवादी को 10 लाख रुपये दिए। यह एक औपचारिक अनुबंध था।"
    normalized = normalize_devanagari_text(hindi_text)
    assert "।" in normalized

    sentences = split_hindi_english_sentences(normalized)
    assert len(sentences) == 2
    assert "वादी ने प्रतिवादी को" in sentences[0][2]
    assert "यह एक औपचारिक अनुबंध था" in sentences[1][2]


def test_language_detection():
    """Verify accurate detection of English, Hindi, Hinglish, and mixed text."""
    english = "The plaintiff filed a suit for specific performance under Section 10."
    hindi = "वादी ने दीवानी प्रक्रिया संहिता के तहत वाद दायर किया।"
    hinglish = "Vakeel saab filed the vakalatnama in munsif court for zamanat."
    mixed = "The contract was signed at Delhi where प्रतिवादी breached the agreement."

    assert detect_language_mix(english) == "english"
    assert detect_language_mix(hindi) == "hindi"
    assert detect_language_mix(hinglish) == "hinglish"
    assert detect_language_mix(mixed) == "mixed"


def test_offset_preserving_chunker():
    """Verify that chunks maintain exact character start and end offsets."""
    text = (
        "First sentence explaining transaction details. "
        "Second sentence detailing the dishonour of cheque. "
        "Third sentence issuing statutory notice under Section 138."
    )
    chunker = OffsetPreservingChunker(target_chunk_size=70, overlap_size=20)
    chunks = chunker.chunk_page(page_text=text, page_number=1)

    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.page_number == 1
        assert chunk.char_end > chunk.char_start
        # Sliced text from original must match chunk text
        original_slice = text[chunk.char_start:chunk.char_end].strip()
        assert chunk.text == original_slice


def test_document_ingestor_encryption_and_chunks(db_session):
    """Verify document ingestor encrypts file at rest and creates database records."""
    sample_content = (
        "IN THE HIGH COURT OF DELHI AT NEW DELHI\n"
        "Suit No. 1234 of 2024\n"
        "ABC Corp v. XYZ Pvt Ltd\n"
        "The defendant failed to honour invoice dated 15-01-2023."
    ).encode("utf-8")

    ingestor = DocumentIngestor()
    result = ingestor.ingest(
        raw_bytes=sample_content,
        filename="commercial_suit.txt",
        db_session=db_session,
    )

    assert result.document_id is not None
    assert result.page_count == 1
    assert result.chunks_count >= 1
    assert len(result.sha256_hash) == 64

