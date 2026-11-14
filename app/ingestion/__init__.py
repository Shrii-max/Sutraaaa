"""Ingestion module for multilingual Indian legal documents."""
from app.ingestion.devanagari import normalize_devanagari_text, detect_language_mix, split_hindi_english_sentences
from app.ingestion.chunker import OffsetPreservingChunker, TextChunk
from app.ingestion.pipeline import DocumentIngestor, IngestedDocumentResult

__all__ = [
    "normalize_devanagari_text",
    "detect_language_mix",
    "split_hindi_english_sentences",
    "OffsetPreservingChunker",
    "TextChunk",
    "DocumentIngestor",
    "IngestedDocumentResult",
]

