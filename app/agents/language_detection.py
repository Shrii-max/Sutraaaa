"""Language and Script Detection Agent for multilingual Indian legal records.

Follows Requirement:
2. LanguageDetectionAgent: per-page language and script detection (Hindi, English,
   Hinglish, other Indic). Heuristics on Unicode script ratio plus langid fallback.
"""

import re
from typing import List, Optional
from app.schemas.document import OCRResult, PageOCR, PageLanguage, LanguageResult
from app.ingestion.devanagari import normalize_devanagari_text
from app.security.audit import record_audit_event

# Unicode script ranges
UNICODE_SCRIPTS = {
    "Devanagari": re.compile(r"[\u0900-\u097F]"),
    "Gurmukhi": re.compile(r"[\u0A00-\u0A7F]"),
    "Gujarati": re.compile(r"[\u0A80-\u0AFF]"),
    "Bengali": re.compile(r"[\u0980-\u09FF]"),
    "Tamil": re.compile(r"[\u0B80-\u0BFF]"),
    "Telugu": re.compile(r"[\u0C00-\u0C7F]"),
    "Kannada": re.compile(r"[\u0C80-\u0CFF]"),
    "Malayalam": re.compile(r"[\u0D00-\u0D7F]"),
    "Odia": re.compile(r"[\u0B00-\u0B7F]"),
    "Latin": re.compile(r"[a-zA-Z]"),
}

HINGLISH_KEYWORDS = {
    "vakalatnama", "vakeel", "advocate", "adalat", "faisla", "bayaan", "dastavej",
    "khatoni", "khasra", "patta", "fir", "chalan", "tahsil", "patwari", "talak",
    "aaropi", "fariyadi", "gawah", "saboot", "munsif", "peshi", "tareekh", "tarikh",
    "bailable", "non-bailable", "zamanat", "parwana", "hukamnama", "haq", "kabza",
    "thana", "daroga", "kotwali", "tehsil", "muqadma", "shikayat", "bayan"
}


class LanguageDetectionAgent:
    """Classifies script and language per page with Indic script heuristics and langid fallback."""

    agent_name: str = "LanguageDetectionAgent"

    def __init__(self):
        try:
            import langid
            self.langid = langid
        except ImportError:
            self.langid = None

    def detect_page(self, text: str, page_number: int = 1) -> PageLanguage:
        normalized = normalize_devanagari_text(text)
        if not normalized.strip():
            return PageLanguage(page_number=page_number, language="unknown", script="None")

        counts = {script: len(pattern.findall(normalized)) for script, pattern in UNICODE_SCRIPTS.items()}
        total_letters = sum(counts.values())

        if total_letters == 0:
            return PageLanguage(page_number=page_number, language="neutral", script="Symbols/Numerals")

        devanagari = counts["Devanagari"]
        latin = counts["Latin"]

        # Check Hinglish vocabulary
        words = {w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", normalized)}
        hinglish_hits = words.intersection(HINGLISH_KEYWORDS)

        # 1. Check Indic scripts other than Devanagari
        for script_name in ["Gurmukhi", "Gujarati", "Bengali", "Tamil", "Telugu", "Kannada", "Malayalam", "Odia"]:
            if counts[script_name] / total_letters > 0.40:
                lang_name = script_name.lower()
                if script_name == "Gurmukhi":
                    lang_name = "punjabi"
                elif script_name == "Odia":
                    lang_name = "odia"
                return PageLanguage(page_number=page_number, language=lang_name, script=script_name)

        # 2. Devanagari & Hindi checks
        if devanagari / total_letters > 0.60:
            return PageLanguage(page_number=page_number, language="hindi", script="Devanagari")

        # 3. Mixed Hindi + English
        if devanagari > 10 and latin > 10:
            return PageLanguage(page_number=page_number, language="mixed", script="Devanagari+Latin")

        # 4. Hinglish (Latin script with Hindi phonetic phrasing)
        if len(hinglish_hits) >= 2 or (latin > 0 and len(hinglish_hits) >= 1 and len(words) < 25):
            return PageLanguage(page_number=page_number, language="hinglish", script="Latin")

        # 5. English dominant
        if latin / total_letters > 0.80:
            return PageLanguage(page_number=page_number, language="english", script="Latin")

        # 6. Fallback to langid
        if self.langid is not None:
            try:
                lang_code, _ = self.langid.classify(normalized)
                if lang_code == "hi":
                    return PageLanguage(page_number=page_number, language="hindi", script="Devanagari")
                elif lang_code == "en":
                    return PageLanguage(page_number=page_number, language="english", script="Latin")
            except Exception:
                pass

        return PageLanguage(page_number=page_number, language="mixed", script="Mixed")

    def run(self, ocr_result: OCRResult) -> LanguageResult:
        page_results: List[PageLanguage] = []

        for p in ocr_result.pages:
            res = self.detect_page(p.text, p.page_number)
            page_results.append(res)

        # Determine primary language
        lang_counts = {}
        for pr in page_results:
            lang_counts[pr.language] = lang_counts.get(pr.language, 0) + 1

        primary = max(lang_counts.items(), key=lambda x: x[1])[0] if lang_counts else "english"

        result = LanguageResult(
            document_id=ocr_result.document_id,
            pages=page_results,
            primary_language=primary,
        )

        record_audit_event(
            event_type="AGENT_RUN",
            actor=f"agent:{self.agent_name}",
            resource_id=ocr_result.document_id,
            input_payload={"page_count": len(ocr_result.pages)},
            output_payload={"primary_language": primary, "details": [p.model_dump() for p in page_results]},
            status="SUCCESS",
        )

        return result

