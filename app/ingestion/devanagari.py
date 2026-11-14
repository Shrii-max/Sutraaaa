"""Devanagari, Hindi, English, and Hinglish linguistic processing.

Follows Hard Rule 7: Mixed Hindi / English / Hinglish documents must work. Handle Devanagari properly.
"""

import unicodedata
import re
from typing import List, Tuple

# Devanagari Unicode Block: U+0900 to U+097F
DEVANAGARI_RANGE = re.compile(r"[\u0900-\u097F]")
LATIN_RANGE = re.compile(r"[a-zA-Z]")

# Common Hindi legal and procedural keywords transliterated into English (Hinglish)
HINGLISH_LEGAL_KEYWORDS = {
    "vakalatnama", "vakeel", "advocate", "adalat", "faisla", "bayaan", "dastavej",
    "khatoni", "khasra", "patta", "fir", "chalan", "tahsil", "patwari", "talak",
    "aaropi", "fariyadi", "gawah", "saboot", "munsif", "peshi", "tareekh", "tarikh",
    "bailable", "non-bailable", "zamanat", "parwana", "hukamnama", "haq", "kabza"
}


def normalize_devanagari_text(text: str) -> str:
    """Normalize text into Unicode NFC form.
    
    Ensures combining characters, nuktas, and matras do not distort character offset counting.
    """
    if not text:
        return ""
    # NFC normalizes canonically composed characters
    normalized = unicodedata.normalize("NFC", text)
    # Replace non-standard carriage returns while preserving indices
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    return normalized


def detect_language_mix(text: str) -> str:
    """Detect whether text is predominantly English, Hindi (Devanagari), Hinglish, or mixed."""
    if not text:
        return "unknown"

    devanagari_chars = len(DEVANAGARI_RANGE.findall(text))
    latin_chars = len(LATIN_RANGE.findall(text))
    total_letters = devanagari_chars + latin_chars

    if total_letters == 0:
        return "neutral"

    tokens = {t.lower() for t in re.findall(r"\b[a-zA-Z]{3,}\b", text)}
    hinglish_matches = tokens.intersection(HINGLISH_LEGAL_KEYWORDS)

    if devanagari_chars > 0 and latin_chars > 0:
        return "mixed"
    elif devanagari_chars > 0 and latin_chars == 0:
        return "hindi"
    elif len(hinglish_matches) > 0:
        return "hinglish"
    else:
        return "english"


def split_hindi_english_sentences(text: str) -> List[Tuple[int, int, str]]:
    """Splits text into sentences recognizing both English and Devanagari sentence terminators.
    
    Recognizes:
      - Period '.'
      - Question mark '?'
      - Exclamation mark '!'
      - Devanagari Danda '।' (\u0964)
      - Devanagari Double Danda '॥' (\u0965)
      - Double newlines '\n\n'
      
    Returns:
        List[Tuple[char_start, char_end, sentence_text]]
    """
    normalized = normalize_devanagari_text(text)
    pattern = re.compile(r"([^।॥.!?\n]+[।॥.!?\n]*|\n+)")
    
    spans: List[Tuple[int, int, str]] = []
    for match in pattern.finditer(normalized):
        sentence = match.group(0).strip()
        if sentence:
            spans.append((match.start(), match.end(), sentence))
    return spans
