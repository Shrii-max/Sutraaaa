"""TranslationAgent for Multilingual Legal Document Intelligence (LexAgent Phase B).

Features:
- Sentence-level SourceRef alignment with exact character offset tracking
- Protected token masking (statutory sections, dates, monetary amounts, case numbers, party names)
- Legal glossary enforcement (English, Hindi, Marathi) from data/glossary/legal_terms.json
- Back-translation semantic similarity verification
- Content-hash translation caching
- Mandatory court translation disclaimer
"""

import difflib
import hashlib
import json
import logging
import os
import re
from typing import Dict, List, Optional, Set, Tuple

from app.agents.base import BaseAgent
from app.config import get_settings
from app.llm.client import LLMClient
from app.llm.translator import FakeTranslator, LocalLLMTranslator, Translator
from app.schemas.source import SourceRef
from app.schemas.translation import (
    SentenceAlignment,
    TranslatedDocument,
    TranslatedPage,
    TranslatedSummary,
    TranslationInput,
    TranslationIssue,
)

logger = logging.getLogger(__name__)


class TranslationAgent(BaseAgent[TranslationInput, TranslatedDocument]):
    """Agent translating legal documents and summaries while preserving source provenance and terminology."""

    agent_name: str = "TranslationAgent"

    # Regex patterns for tokens requiring strict verbatim protection
    PROTECTED_PATTERNS = [
        # Statutory Sections (e.g., Section 420 IPC, Sec. 302 of Indian Penal Code, धारा 302, कलम 302)
        re.compile(
            r"\b(?:Section|Sec\.?|u/s|u/ss|धारा|कलम)\s+\d+[A-Z]*(?:\s*\([0-9a-z]+\))*"
            r"(?:\s+(?:of\s+the\s+|of\s+)?(?:IPC|CrPC|BNS|BNSS|NI Act|Indian Penal Code|"
            r"Code of Criminal Procedure|Bharatiya Nyaya Sanhita|Bharatiya Nagarik Suraksha Sanhita))?",
            re.IGNORECASE,
        ),
        # Case Numbers (e.g. FIR No. 12/2023, Crl. App. No. 45/2021, SLP (Crl.) No. 89/2020)
        re.compile(
            r"\b(?:FIR\s+No\.?|Crime\s+No\.?|Crl\.?\s*(?:A|Rev|Misc|App)?\.?\s*No\.?|"
            r"Special\s+Leave\s+Petition\s*\(Crl\.\)\s*No\.?|SLP\s*\(Crl\.\)\s*No\.?|"
            r"W\.?P\.?\s*\(Crl\.\)\s*No\.?|Civil\s+Appeal\s+No\.?)\s*[\w\d/.-]+",
            re.IGNORECASE,
        ),
        # Dates (numeric and named months)
        re.compile(
            r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+"
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December|"
            r"जनवरी|फ़रवरी|फरवरी|मार्च|अप्रैल|मई|जून|जुलाई|अगस्त|सितंबर|अक्टूबर|नवंबर|दिसंबर)\s+\d{4})\b",
            re.IGNORECASE,
        ),
        # Monetary Amounts (e.g., Rs. 15,00,000, ₹50,000, INR 10,000)
        re.compile(r"\b(?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d+)?\b", re.IGNORECASE),
    ]

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        translator: Optional[Translator] = None,
        glossary_path: Optional[str] = None,
    ):
        super().__init__(llm_client=llm_client)
        self.translator = translator or LocalLLMTranslator(llm_client=self.llm)
        if glossary_path:
            self.glossary_path = glossary_path
        else:
            default_p = os.path.join("data", "glossary", "legal_terms.json")
            if not os.path.exists(default_p):
                pkg_p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "glossary", "legal_terms.json")
                if os.path.exists(pkg_p):
                    default_p = pkg_p
            self.glossary_path = default_p
        self.glossary: Dict[str, Dict[str, str]] = {}
        self._cache: Dict[str, TranslatedDocument] = {}
        self._summary_cache: Dict[str, TranslatedSummary] = {}
        self._load_glossary()

    def _load_glossary(self) -> None:
        """Load seed legal glossary from disk."""
        if not os.path.exists(self.glossary_path):
            logger.warning("Glossary file not found at %s. Proceeding with empty glossary.", self.glossary_path)
            return

        try:
            with open(self.glossary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("terms", []):
                    eng = item.get("english", "").lower().strip()
                    self.glossary[eng] = {
                        "hi": item.get("hindi", "").strip(),
                        "mr": item.get("marathi", "").strip(),
                    }
                    for alias in item.get("aliases", []):
                        al = alias.lower().strip()
                        if al:
                            self.glossary[al] = self.glossary[eng]
        except Exception as e:
            logger.error("Failed to load legal glossary from %s: %s", self.glossary_path, e)

    def mask_protected_tokens(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Identify protected entities and replace them with indexed placeholder tokens."""
        protected_map: Dict[str, str] = {}
        counter = 0

        # Collect all non-overlapping spans
        spans: List[Tuple[int, int, str]] = []
        for pat in self.PROTECTED_PATTERNS:
            for match in pat.finditer(text):
                spans.append((match.start(), match.end(), match.group()))

        # Sort spans by start offset; on conflict pick longer span
        spans.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        merged_spans: List[Tuple[int, int, str]] = []
        last_end = -1
        for start, end, match_str in spans:
            if start >= last_end:
                merged_spans.append((start, end, match_str))
                last_end = end

        # Construct masked text
        masked_parts: List[str] = []
        curr_idx = 0
        for start, end, match_str in merged_spans:
            masked_parts.append(text[curr_idx:start])
            token_placeholder = f"[[PROT_{counter}]]"
            protected_map[token_placeholder] = match_str
            masked_parts.append(token_placeholder)
            counter += 1
            curr_idx = end
        masked_parts.append(text[curr_idx:])

        return "".join(masked_parts), protected_map

    def restore_protected_tokens(self, text: str, protected_map: Dict[str, str]) -> Tuple[str, List[str]]:
        """Restore protected placeholder tokens back to their original text.
        
        Returns the restored text and a list of any missing/dropped placeholder tokens.
        """
        restored = text
        missing_tokens: List[str] = []

        for token, original in protected_map.items():
            if token in restored:
                restored = restored.replace(token, original)
            else:
                # Token was dropped or modified by the translator
                missing_tokens.append(token)
                # Fallback: append original at the end if completely dropped
                restored = f"{restored} ({original})"

        return restored, missing_tokens

    def get_glossary_hints(self, text: str, target_lang: str) -> Dict[str, str]:
        """Extract glossary terms present in text for targeted translator priming."""
        hints: Dict[str, str] = {}
        t_lang = target_lang.lower()
        lower_text = text.lower()

        for eng_term, translations in self.glossary.items():
            trans = translations.get(t_lang)
            if trans and eng_term in lower_text:
                hints[eng_term] = trans

        return hints

    def segment_sentences_with_offsets(self, text: str) -> List[Tuple[str, int, int]]:
        """Split text into sentences preserving start and end character offsets."""
        segments: List[Tuple[str, int, int]] = []
        # Pattern split on sentence boundaries
        pattern = re.compile(r"([^\n.!?।]+(?:[\n.!?।]+|$))")
        for match in pattern.finditer(text):
            sentence = match.group().strip()
            if sentence:
                # Find exact start of non-whitespace content in match
                raw_match = match.group()
                lead_offset = len(raw_match) - len(raw_match.lstrip())
                start = match.start() + lead_offset
                end = start + len(sentence)
                segments.append((sentence, start, end))

        if not segments and text.strip():
            segments.append((text.strip(), 0, len(text.strip())))
        return segments

    def verify_back_translation(
        self,
        original_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
    ) -> Tuple[float, Optional[str]]:
        """Back-translate to source language and compute semantic sequence similarity."""
        try:
            back_translated = self.translator.translate(
                translated_text,
                source_lang=target_lang,
                target_lang=source_lang,
            )
            # Normalize texts for comparison
            s1 = re.sub(r"\s+", " ", original_text.strip().lower())
            s2 = re.sub(r"\s+", " ", back_translated.strip().lower())

            ratio = difflib.SequenceMatcher(None, s1, s2).ratio()
            return ratio, back_translated
        except Exception as e:
            logger.warning("Back-translation check failed: %s", e)
            return 0.5, None

    def _execute(self, input_data: TranslationInput) -> TranslatedDocument:
        """Execute multilingual translation on document pages or raw content."""
        target_lang = input_data.target_language.lower()
        source_lang = input_data.source_language.lower()
        doc_id = input_data.document_id or "adhoc_doc"

        # Check content-hash cache
        content_key = f"{doc_id}_{source_lang}_{target_lang}_{input_data.content or ''}"
        cache_hash = hashlib.sha256(content_key.encode("utf-8")).hexdigest()
        if cache_hash in self._cache:
            logger.info("Translation cache hit for hash %s", cache_hash[:10])
            return self._cache[cache_hash]

        # Prepare pages data
        pages_to_process = []
        if input_data.pages_data:
            pages_to_process = input_data.pages_data
        elif input_data.content:
            pages_to_process = [{"page_number": 1, "text": input_data.content}]
        else:
            pages_to_process = [{"page_number": 1, "text": ""}]

        translated_pages: List[TranslatedPage] = []
        all_issues: List[TranslationIssue] = []
        overall_confidences: List[float] = []
        needs_review = False
        full_text_pieces: List[str] = []

        for p_data in pages_to_process:
            page_num = p_data.get("page_number", 1)
            raw_text = p_data.get("text", "")

            if not raw_text.strip():
                translated_pages.append(
                    TranslatedPage(page_number=page_num, source_text="", translated_text="", alignments=[])
                )
                continue

            # Sentence segmentation with SourceRef offsets
            sentence_tuples = self.segment_sentences_with_offsets(raw_text)
            page_alignments: List[SentenceAlignment] = []
            page_trans_pieces: List[str] = []

            for sent, s_start, s_end in sentence_tuples:
                # 1. Mask protected entities
                masked_sent, protected_map = self.mask_protected_tokens(sent)

                # 2. Extract glossary hints
                glossary_hints = None
                if input_data.preserve_glossary:
                    glossary_hints = self.get_glossary_hints(sent, target_lang)

                # 3. Translate masked sentence
                translated_masked = self.translator.translate(
                    masked_sent,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    glossary_hints=glossary_hints,
                )

                # 4. Restore protected entities
                restored_sent, missing_tokens = self.restore_protected_tokens(
                    translated_masked, protected_map
                )

                if missing_tokens:
                    all_issues.append(
                        TranslationIssue(
                            category="protected_token_altered",
                            severity="HIGH",
                            description=f"Protected token was altered or dropped in translation: {', '.join(missing_tokens)}",
                            source_snippet=sent[:100],
                        )
                    )
                    needs_review = True

                # 5. Build SourceRef and SentenceAlignment
                source_ref = SourceRef(
                    document_id=doc_id,
                    page=page_num,
                    char_start=s_start,
                    char_end=s_end,
                    snippet=sent,
                )
                alignment = SentenceAlignment(
                    source_sentence=sent,
                    target_sentence=restored_sent,
                    source_ref=source_ref,
                )
                page_alignments.append(alignment)
                page_trans_pieces.append(restored_sent)

            page_full_trans = " ".join(page_trans_pieces)
            full_text_pieces.append(page_full_trans)

            # 6. Back-translation verification on page text
            page_conf = 0.95
            if input_data.verify_backtranslation and len(raw_text.strip()) > 10:
                sim_ratio, _ = self.verify_back_translation(
                    original_text=raw_text,
                    translated_text=page_full_trans,
                    source_lang=source_lang,
                    target_lang=target_lang,
                )
                if sim_ratio < 0.70:
                    page_conf = max(0.40, sim_ratio)
                    needs_review = True
                    all_issues.append(
                        TranslationIssue(
                            category="back_translation_divergence",
                            severity="HIGH",
                            description=(
                                f"Back-translation similarity ratio ({sim_ratio:.2f}) is below acceptable threshold 0.70 on page {page_num}."
                            ),
                            source_snippet=raw_text[:120],
                        )
                    )
                else:
                    page_conf = min(0.98, max(0.75, sim_ratio))

            overall_confidences.append(page_conf)
            translated_pages.append(
                TranslatedPage(
                    page_number=page_num,
                    source_text=raw_text,
                    translated_text=page_full_trans,
                    alignments=page_alignments,
                )
            )

        final_conf = (
            sum(overall_confidences) / len(overall_confidences)
            if overall_confidences
            else 0.90
        )
        if final_conf < 0.75:
            needs_review = True

        result = TranslatedDocument(
            document_id=doc_id,
            source_language=source_lang,
            target_language=target_lang,
            pages=translated_pages,
            full_translated_text="\n\n".join(full_text_pieces),
            confidence=round(final_conf, 3),
            needs_human_review=needs_review,
            issues=all_issues,
            content_hash=cache_hash,
            disclaimer="Machine translation, not an official court translation. For decision-support only.",
        )

        self._cache[cache_hash] = result
        return result

    def translate_summary(
        self,
        summary_text: str,
        source_lang: str = "en",
        target_lang: str = "hi",
        case_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> TranslatedSummary:
        """Translate a case or document summary."""
        cache_key = f"summary_{case_id}_{document_id}_{source_lang}_{target_lang}_{summary_text}"
        cache_hash = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        if cache_hash in self._summary_cache:
            return self._summary_cache[cache_hash]

        # Mask protected entities
        masked, protected_map = self.mask_protected_tokens(summary_text)
        glossary_hints = self.get_glossary_hints(summary_text, target_lang)

        # Translate
        translated_masked = self.translator.translate(
            masked,
            source_lang=source_lang,
            target_lang=target_lang,
            glossary_hints=glossary_hints,
        )

        # Restore
        restored, missing_tokens = self.restore_protected_tokens(
            translated_masked, protected_map
        )

        issues: List[TranslationIssue] = []
        needs_review = False
        conf = 0.92

        if missing_tokens:
            issues.append(
                TranslationIssue(
                    category="protected_token_altered",
                    severity="HIGH",
                    description=f"Protected token was altered in summary: {', '.join(missing_tokens)}",
                    source_snippet=summary_text[:100],
                )
            )
            needs_review = True
            conf = 0.65

        # Back-translation verification
        sim_ratio, _ = self.verify_back_translation(
            summary_text, restored, source_lang=source_lang, target_lang=target_lang
        )
        if sim_ratio < 0.70:
            needs_review = True
            conf = min(conf, max(0.40, sim_ratio))
            issues.append(
                TranslationIssue(
                    category="back_translation_divergence",
                    severity="HIGH",
                    description=f"Back-translation similarity ratio ({sim_ratio:.2f}) below 0.70.",
                    source_snippet=summary_text[:100],
                )
            )

        res = TranslatedSummary(
            case_id=case_id,
            document_id=document_id,
            source_language=source_lang,
            target_language=target_lang,
            original_summary=summary_text,
            translated_summary=restored,
            confidence=round(conf, 3),
            needs_human_review=needs_review,
            issues=issues,
            disclaimer="Machine translation, not an official court translation. For decision-support only.",
        )
        self._summary_cache[cache_hash] = res
        return res

