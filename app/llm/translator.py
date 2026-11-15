"""Multilingual Translation Subsystem for LexAgent (Phase B).

Provides the abstract Translator interface and concrete implementations:
- LocalLLMTranslator: Uses local LLM (Qwen/DeepSeek) with glossary constraints and protected token safety
- IndicTransTranslator: Adapter stub for IndicTrans2/NLLB neural translation models
- FakeTranslator: Deterministic mock translator for offline testing
"""

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from app.config import get_settings
from app.llm.client import LLMClient, get_llm_client
from app.llm.router import ModelRouter, TaskType

logger = logging.getLogger(__name__)


class Translator(ABC):
    """Abstract interface for local multilingual translation."""

    @abstractmethod
    def translate(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "hi",
        glossary_hints: Optional[Dict[str, str]] = None,
    ) -> str:
        """Translate a single block of text preserving protected placeholders."""
        pass

    def translate_sentences(
        self,
        sentences: List[str],
        source_lang: str = "en",
        target_lang: str = "hi",
        glossary_hints: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """Translate a list of sentences while maintaining 1-to-1 correspondence."""
        return [
            self.translate(s, source_lang=source_lang, target_lang=target_lang, glossary_hints=glossary_hints)
            for s in sentences
        ]


class LocalLLMTranslator(Translator):
    """Translates legal text using a local LLM with prompt constraints and glossary adherence."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.client = llm_client or get_llm_client()
        self.router = ModelRouter(llm_client=self.client)
        self.settings = get_settings()

    def translate(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "hi",
        glossary_hints: Optional[Dict[str, str]] = None,
    ) -> str:
        if not text or not text.strip():
            return ""

        # Language name mapping
        lang_names = {
            "en": "English",
            "hi": "Hindi",
            "mr": "Marathi",
            "ta": "Tamil",
            "te": "Telugu",
            "bn": "Bengali",
            "gu": "Gujarati",
            "kn": "Kannada",
            "ml": "Malayalam",
            "pa": "Punjabi",
        }
        s_name = lang_names.get(source_lang.lower(), source_lang)
        t_name = lang_names.get(target_lang.lower(), target_lang)

        glossary_instruction = ""
        if glossary_hints:
            glossary_lines = [f"- {k} -> {v}" for k, v in list(glossary_hints.items())[:30]]
            glossary_instruction = (
                "\nSTRICT GLOSSARY ADHERENCE (you must use these exact legal translations):\n"
                + "\n".join(glossary_lines)
            )

        system_prompt = (
            f"You are a specialized legal translator for Indian judicial and statutory documents.\n"
            f"Your task is to translate court text accurately from {s_name} to {t_name}.\n"
            f"RULES:\n"
            f"1. DO NOT translate, change, or remove any protected tokens wrapped in double brackets "
            f"like [[PROT_0]], [[PROT_1]], etc. Keep every [[PROT_X]] token exactly where it belongs.\n"
            f"2. Retain formal Indian legal register and terminology.\n"
            f"{glossary_instruction}\n"
            f"3. Return ONLY the translation. Do NOT provide preamble, explanations, notes, or quotes."
        )

        user_prompt = f"Translate the following text to {t_name}:\n\n{text}"

        try:
            client = self.router.get_client_for_task(TaskType.TRANSLATION)
            response = client.chat(user_prompt, system=system_prompt)
            cleaned = response.strip()
            # Strip enclosing markdown quotes if any
            if cleaned.startswith("```") and cleaned.endswith("```"):
                cleaned = re.sub(r"^```[a-zA-Z]*\n?|```$", "", cleaned).strip()
            return cleaned
        except Exception as e:
            logger.error("LocalLLMTranslator execution failed: %s", e)
            return text


class IndicTransTranslator(Translator):
    """Adapter for offline IndicTrans2 or NLLB models via Transformers/CTranslate2."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self._initialized = False
        self._fallback = LocalLLMTranslator()

    def translate(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "hi",
        glossary_hints: Optional[Dict[str, str]] = None,
    ) -> str:
        # If neural weights are present in local environment, load pipeline; otherwise fallback to local LLM
        if not self._initialized:
            # Check for local weights or fallback
            return self._fallback.translate(text, source_lang, target_lang, glossary_hints)
        return text


class FakeTranslator(Translator):
    """Deterministic mock translator for testing and verification without running LLM inference.
    
    Preserves protected tokens [[PROT_...]], substitutes glossary words if present,
    and supports back-translation or deliberate divergence simulation.
    """

    def __init__(self, simulate_divergence: bool = False, glossary_path: Optional[str] = None):
        self.simulate_divergence = simulate_divergence
        self.glossary: Dict[str, Dict[str, str]] = {}
        self._load_glossary(glossary_path)

    def _load_glossary(self, path: Optional[str]):
        default_path = os.path.join("data", "glossary", "legal_terms.json")
        target_path = path or default_path
        if os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("terms", []):
                        eng = item.get("english", "").lower()
                        self.glossary[eng] = {
                            "hi": item.get("hindi", ""),
                            "mr": item.get("marathi", ""),
                        }
                        for alias in item.get("aliases", []):
                            self.glossary[alias.lower()] = self.glossary[eng]
            except Exception as e:
                logger.warning("Could not load glossary in FakeTranslator: %s", e)

    def translate(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "hi",
        glossary_hints: Optional[Dict[str, str]] = None,
    ) -> str:
        if not text or not text.strip():
            return ""

        if self.simulate_divergence:
            # Produce garbled text to trigger low similarity and back-translation failure
            return f"[GARBLED] Irrelevant non-legal commentary {text[:10]}"

        # If translating back from target to English (back-translation check)
        if target_lang == "en" and source_lang in ("hi", "mr"):
            # If text has prefix [HI] or [MR], strip it
            cleaned = re.sub(r"^\[(HI|MR|TA|BN)\]\s*", "", text)
            # Reverse glossary substitutions sorted longest foreign term first
            sorted_rev = sorted(
                self.glossary.items(),
                key=lambda x: len(x[1].get(source_lang, "")),
                reverse=True,
            )
            for eng, trans in sorted_rev:
                foreign = trans.get(source_lang)
                if foreign and foreign in cleaned:
                    cleaned = cleaned.replace(foreign, eng)
            return cleaned

        # Forward translation
        translated = text

        # Apply glossary hints first if provided (sorted longest first to match phrases before words)
        if glossary_hints:
            sorted_hints = sorted(glossary_hints.items(), key=lambda x: len(x[0]), reverse=True)
            for k, v in sorted_hints:
                pattern = re.compile(rf"\b{re.escape(k)}\b", re.IGNORECASE)
                translated = pattern.sub(v, translated)
        else:
            # Apply default glossary sorted longest-term first
            sorted_terms = sorted(self.glossary.items(), key=lambda x: len(x[0]), reverse=True)
            for eng, trans in sorted_terms:
                foreign = trans.get(target_lang)
                if foreign and len(eng) > 1:
                    pattern = re.compile(rf"\b{re.escape(eng)}\b", re.IGNORECASE)
                    translated = pattern.sub(foreign, translated)

        # Prefix with target language tag to identify translated text clearly
        return f"[{target_lang.upper()}] {translated}"


def get_translator(
    backend: Optional[str] = None,
    llm_client: Optional[LLMClient] = None,
) -> Translator:
    """Factory creating configured Translator instance."""
    backend = backend or os.environ.get("TRANSLATION_BACKEND", "llm").lower()
    if backend == "fake":
        return FakeTranslator()
    elif backend == "indictrans":
        return IndicTransTranslator()
    return LocalLLMTranslator(llm_client=llm_client)
