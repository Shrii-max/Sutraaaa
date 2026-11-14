"""Chunker that guarantees exact page number and character start/end offsets.

Follows Hard Rule 2: Every extracted fact MUST carry a source reference:
{document_id, page, char_start, char_end, snippet}.
"""

from typing import List
from pydantic import BaseModel
from app.ingestion.devanagari import normalize_devanagari_text, split_hindi_english_sentences


class TextChunk(BaseModel):
    """Chunk of text preserving exact provenance indices."""
    chunk_index: int
    page_number: int
    char_start: int
    char_end: int
    text: str


class OffsetPreservingChunker:
    """Splits document pages into semantic chunks while maintaining precise character offsets."""

    def __init__(self, target_chunk_size: int = 600, overlap_size: int = 100):
        self.target_chunk_size = target_chunk_size
        self.overlap_size = overlap_size

    def chunk_page(self, page_text: str, page_number: int, start_chunk_idx: int = 0) -> List[TextChunk]:
        """Chunks a single page text into index-preserving slices."""
        normalized = normalize_devanagari_text(page_text)
        if not normalized.strip():
            return []

        sentences = split_hindi_english_sentences(normalized)
        if not sentences:
            # Fallback to single chunk
            return [
                TextChunk(
                    chunk_index=start_chunk_idx,
                    page_number=page_number,
                    char_start=0,
                    char_end=len(normalized),
                    text=normalized.strip(),
                )
            ]

        chunks: List[TextChunk] = []
        current_sentences: List[tuple[int, int, str]] = []
        current_len = 0
        chunk_counter = start_chunk_idx

        for start, end, s_text in sentences:
            s_len = len(s_text)
            if current_len + s_len > self.target_chunk_size and current_sentences:
                # Emit chunk
                c_start = current_sentences[0][0]
                c_end = current_sentences[-1][1]
                c_text = normalized[c_start:c_end].strip()
                chunks.append(
                    TextChunk(
                        chunk_index=chunk_counter,
                        page_number=page_number,
                        char_start=c_start,
                        char_end=c_end,
                        text=c_text,
                    )
                )
                chunk_counter += 1

                # Keep last sentence for overlap if available
                if len(current_sentences) > 1 and len(current_sentences[-1][2]) <= self.overlap_size:
                    current_sentences = [current_sentences[-1]]
                    current_len = len(current_sentences[0][2])
                else:
                    current_sentences = []
                    current_len = 0

            current_sentences.append((start, end, s_text))
            current_len += s_len

        # Flush remaining sentences
        if current_sentences:
            c_start = current_sentences[0][0]
            c_end = current_sentences[-1][1]
            c_text = normalized[c_start:c_end].strip()
            chunks.append(
                TextChunk(
                    chunk_index=chunk_counter,
                    page_number=page_number,
                    char_start=c_start,
                    char_end=c_end,
                    text=c_text,
                )
            )

        return chunks

