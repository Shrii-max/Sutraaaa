"""Local LLM and Embedder Client interfaces and implementations.

Follows Hard Rule 8: LLM calls are mockable through an LLMClient interface.
Follows Hard Rule 9: Structured LLM output: always JSON validated against Pydantic;
retry up to 2 times on validation failure.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Type, TypeVar, Optional, List, Tuple, Any, Dict, Union
import httpx
from pydantic import BaseModel, ValidationError
from app.config import get_settings

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


def extract_json_from_text(text: str) -> str:
    """Extract raw JSON substring from LLM markdown code blocks or raw text."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1].strip()
    
    return text


class LLMClient(ABC):
    """Abstract interface for LLM communication."""

    @abstractmethod
    def chat(self, messages: Union[List[Dict[str, str]], str], system: Optional[str] = None) -> str:
        """Send chat messages or text prompt to the local LLM and return text response."""
        pass

    @abstractmethod
    def chat_json(
        self,
        schema: Type[T],
        prompt: Union[List[Dict[str, str]], str],
        system: Optional[str] = None,
        max_retries: int = 2,
    ) -> T:
        """Request structured JSON, validate against Pydantic schema, retry twice on failure."""
        pass

    # Aliases for existing agents
    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        return self.chat(prompt, system=system)

    def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system: Optional[str] = None,
        max_retries: Optional[int] = None,
    ) -> Tuple[T, bool]:
        """Wrapper returning (model, needs_human_review)."""
        retries = max_retries if max_retries is not None else get_settings().LLM_MAX_RETRIES
        try:
            res = self.chat_json(schema=schema, prompt=prompt, system=system, max_retries=retries)
            return res, False
        except Exception:
            return schema.model_construct(), True


class OpenAICompatClient(LLMClient):
    """Connects to local OpenAI-compatible endpoint (Ollama, vLLM, LMStudio)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL
        self.timeout = timeout
        self._unavailable = False
        self.client = httpx.Client(timeout=httpx.Timeout(timeout, connect=0.5))

    def chat(
        self, messages: Union[List[Dict[str, str]], str], system: Optional[str] = None,
        *, reasoning_effort: Optional[str] = None, max_tokens: Optional[int] = None,
    ) -> str:
        if self._unavailable:
            raise httpx.ConnectError("The local model already failed during this processing run.")
        url = f"{self.base_url}/chat/completions"
        msg_payload = []
        if system:
            msg_payload.append({"role": "system", "content": system})

        if isinstance(messages, str):
            msg_payload.append({"role": "user", "content": messages})
        else:
            msg_payload.extend(messages)

        payload = {
            "model": self.model,
            "messages": msg_payload,
            "temperature": get_settings().LLM_TEMPERATURE,
            "stream": False,
        }
        if reasoning_effort is not None:
            payload["reasoning_effort"] = reasoning_effort
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        headers = {"Content-Type": "application/json"}

        try:
            response = self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        except (httpx.NetworkError, httpx.TimeoutException):
            self._unavailable = True
            raise
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def chat_json(
        self,
        schema: Type[T],
        prompt: Union[List[Dict[str, str]], str],
        system: Optional[str] = None,
        max_retries: int = 2,
    ) -> T:
        schema_json_spec = json.dumps(schema.model_json_schema(), indent=2)
        format_instruction = (
            f"\n\nCRITICAL INSTRUCTION: Return ONLY valid JSON adhering strictly to this JSON Schema:\n"
            f"```json\n{schema_json_spec}\n```\n"
            f"Do not include any commentary or preamble outside the JSON."
        )

        base_prompt = prompt if isinstance(prompt, str) else "\n".join([m.get("content", "") for m in prompt])
        current_prompt = base_prompt + format_instruction
        current_system = system or "You are a legal AI assistant. Output exclusively valid JSON."
        last_error = ""

        for attempt in range(max_retries + 1):
            try:
                raw = self.chat(current_prompt, system=current_system, reasoning_effort="none", max_tokens=4096)
                clean_json = extract_json_from_text(raw)
                parsed = json.loads(clean_json)
                return schema.model_validate(parsed)
            except (json.JSONDecodeError, ValidationError, Exception) as err:
                last_error = str(err)
                if isinstance(err, (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException, OSError)) or (isinstance(err, httpx.HTTPStatusError) and err.response.status_code in (404, 502, 503)):
                    logger.info("Local LLM server connection unavailable; proceeding to deterministic fallback.")
                    raise err
                logger.warning(f"chat_json attempt {attempt + 1}/{max_retries + 1} failed: {err}")
                if attempt < max_retries:
                    current_prompt = (
                        f"{base_prompt}{format_instruction}\n\n"
                        f"CORRECTION REQUIRED: Your previous JSON output was invalid. Error: {last_error}\n"
                        f"Please output strictly valid JSON conforming to the schema."
                    )

        raise ValueError(
            f"Failed to obtain valid JSON for schema '{schema.__name__}' after {max_retries} retries: {last_error}"
        )


class FakeLLMClient(LLMClient):
    """Test fake for LLMClient supporting canned responses, retry simulation, and call logs."""

    def __init__(self, responses: Optional[Dict[str, Any]] = None):
        self.responses = responses or {}
        self.call_history: List[Dict[str, Any]] = []
        self.fail_validation_times: int = 0
        self._current_failures: int = 0

    def chat(self, messages: Union[List[Dict[str, str]], str], system: Optional[str] = None) -> str:
        text = messages if isinstance(messages, str) else json.dumps(messages)
        self.call_history.append({"messages": messages, "system": system})

        text_lower = text.lower()
        for key, resp in self.responses.items():
            if key.lower() in text_lower:
                return resp if isinstance(resp, str) else json.dumps(resp)

        return json.dumps({"status": "mock_response", "text": "deterministic test output"})

    def chat_json(
        self,
        schema: Type[T],
        prompt: Union[List[Dict[str, str]], str],
        system: Optional[str] = None,
        max_retries: int = 2,
    ) -> T:
        text = prompt if isinstance(prompt, str) else json.dumps(prompt)
        self.call_history.append({"prompt": prompt, "system": system, "schema": schema.__name__})

        for attempt in range(max_retries + 1):
            if self._current_failures < self.fail_validation_times:
                self._current_failures += 1
                continue

            # 1. Match by schema name first
            schema_name_lower = schema.__name__.lower()
            for key, resp in self.responses.items():
                k_lower = key.lower()
                if k_lower == schema_name_lower or k_lower in schema_name_lower:
                    if isinstance(resp, dict):
                        try:
                            return schema.model_validate(resp)
                        except ValidationError:
                            pass
                    elif isinstance(resp, str):
                        try:
                            clean = extract_json_from_text(resp)
                            return schema.model_validate(json.loads(clean))
                        except Exception:
                            pass

            # 2. Match by prompt substring
            text_lower = text.lower()
            for key, resp in self.responses.items():
                if key.lower() in text_lower:
                    if isinstance(resp, dict):
                        try:
                            return schema.model_validate(resp)
                        except ValidationError:
                            continue
                    elif isinstance(resp, str):
                        try:
                            clean = extract_json_from_text(resp)
                            return schema.model_validate(json.loads(clean))
                        except Exception:
                            continue
            try:
                return schema()
            except Exception:
                try:
                    return schema.model_construct()
                except Exception:
                    pass

        raise ValueError(f"FakeLLMClient exhausted {max_retries} retries for schema {schema.__name__}")


# Embedder Interface & Implementations
class Embedder(ABC):
    """Abstract interface for local text embeddings."""

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Compute embedding vectors for a batch of texts."""
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Compute embedding vector for a single query text."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        pass


class OpenAICompatEmbedder(Embedder):
    """Local OpenAI-compatible embedder with fallback vector generator."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        dimension: Optional[int] = None,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.EMBED_MODEL
        self._dim = dimension or settings.EMBED_DIM
        self.client = httpx.Client(timeout=30.0)

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        url = f"{self.base_url}/embeddings"
        try:
            res = self.client.post(url, json={"model": self.model, "input": texts})
            res.raise_for_status()
            data = res.json()
            records = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
            return [r["embedding"] for r in records]
        except Exception:
            return [FakeEmbedder.deterministic_vector(t, self._dim) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        res = self.embed([text])
        return res[0] if res else [0.0] * self._dim


class FakeEmbedder(Embedder):
    """Deterministic fake embedder for pytest and offline environments."""

    def __init__(self, dimension: Optional[int] = None):
        self._dim = dimension or get_settings().EMBED_DIM

    @property
    def dimension(self) -> int:
        return self._dim

    @staticmethod
    def deterministic_vector(text: str, dim: int) -> List[float]:
        import hashlib, math
        seed_bytes = hashlib.sha256(text.encode("utf-8")).digest()
        vec = []
        for i in range(dim):
            byte_val = seed_bytes[i % len(seed_bytes)]
            val = math.sin((i + 1) * (byte_val + 1))
            vec.append(val)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [round(x / norm, 6) for x in vec]

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [self.deterministic_vector(t, self._dim) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self.deterministic_vector(text, self._dim)


# Global instances and aliases
OpenAICompatibleLLMClient = OpenAICompatClient
MockLLMClient = FakeLLMClient
LocalEmbeddingClient = OpenAICompatEmbedder
MockEmbeddingClient = FakeEmbedder

_CLIENT_OVERRIDE: Optional[LLMClient] = None
_EMBED_OVERRIDE: Optional[Embedder] = None


def set_llm_client(client: LLMClient) -> None:
    global _CLIENT_OVERRIDE
    _CLIENT_OVERRIDE = client


def get_llm_client() -> LLMClient:
    global _CLIENT_OVERRIDE
    if _CLIENT_OVERRIDE is not None:
        return _CLIENT_OVERRIDE
    return OpenAICompatClient()


def set_embedding_client(client: Embedder) -> None:
    global _EMBED_OVERRIDE
    _EMBED_OVERRIDE = client


def get_embedding_client() -> Embedder:
    global _EMBED_OVERRIDE
    if _EMBED_OVERRIDE is not None:
        return _EMBED_OVERRIDE
    return OpenAICompatEmbedder()
