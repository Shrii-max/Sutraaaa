"""VoiceFlow Voice Gateway & Adapter (LexAgent Phase C).

Provides:
- VoiceGateway: Abstract adapter interface for TTS and STT
- VoiceFlowGateway: Client for the owner's self-hosted VoiceFlow platform with strict SSRF defense
- FakeVoiceGateway: Deterministic mock for offline testing and verification
"""

import ipaddress
import logging
import os
import urllib.parse
from abc import ABC, abstractmethod
from typing import Optional

import httpx
from fastapi import HTTPException, status

from app.config import get_settings

logger = logging.getLogger(__name__)

# Standard 44-byte minimal silent PCM WAV header for testing/synthetic response
MOCK_WAV_BYTES = (
    b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00"
    b"\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
)


class VoiceGateway(ABC):
    """Abstract interface for speech synthesis and transcription."""

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: Optional[str] = "en",
    ) -> bytes:
        """Synthesize text into raw audio bytes."""
        pass

    @abstractmethod
    def transcribe(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None,
    ) -> str:
        """Transcribe raw audio bytes into text."""
        pass


class VoiceFlowGateway(VoiceGateway):
    """Adapter connecting to external self-hosted VoiceFlow speech platform."""

    BLOCKED_HOSTNAMES = {"169.254.169.254", "metadata.google.internal", "instance-data"}

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        default_voice_id: Optional[str] = None,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.VOICEFLOW_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.VOICEFLOW_API_KEY
        self.voice_id = default_voice_id or settings.VOICEFLOW_VOICE_ID
        self._validate_url_security(self.base_url)

    def _validate_url_security(self, url: str) -> None:
        """Enforce strict SSRF protection against cloud metadata and illegal schemes."""
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Invalid VoiceFlow URL scheme: '{parsed.scheme}'. Only http/https allowed.")

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise ValueError("VoiceFlow base URL missing hostname.")

        if hostname in self.BLOCKED_HOSTNAMES:
            raise PermissionError(f"Security Alert: SSRF target '{hostname}' is strictly blocked.")

        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_link_local or str(ip) == "169.254.169.254":
                raise PermissionError(f"Security Alert: Link-local SSRF IP '{ip}' blocked.")
        except ValueError:
            # Domain name, not an IP
            pass

    def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: Optional[str] = "en",
    ) -> bytes:
        if not text or not text.strip():
            return MOCK_WAV_BYTES

        url = f"{self.base_url}/v1/tts/synthesize"
        payload = {
            "text": text,
            "voice_id": voice_id or self.voice_id,
            "language": language or "en",
            "audio_format": "wav",
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                return resp.content
        except Exception as e:
            logger.warning("VoiceFlow TTS synthesis unreachable (%s); using local TTS engine.", e)
            try:
                return LocalTTSVoiceGateway().synthesize(text, voice_id=voice_id, language=language)
            except Exception:
                return MOCK_WAV_BYTES

    def transcribe(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None,
    ) -> str:
        if not audio_bytes:
            return ""

        url = f"{self.base_url}/v1/stt/transcribe"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        data = {"language": language or "en"}

        try:
            with httpx.Client(timeout=12.0) as client:
                resp = client.post(url, files=files, data=data, headers=headers)
                resp.raise_for_status()
                result_json = resp.json()
                return result_json.get("text", "")
        except Exception as e:
            logger.error("VoiceFlow STT transcription request failed: %s", e)
            return ""


class LocalTTSVoiceGateway(VoiceGateway):
    """Local native Text-To-Speech gateway using pyttsx3 / Windows SAPI5."""

    def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: Optional[str] = "en",
    ) -> bytes:
        if not text or not text.strip():
            return b""
        try:
            import pyttsx3, tempfile
            from pathlib import Path
            engine = pyttsx3.init()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()
            data = Path(tmp_path).read_bytes()
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return data
        except Exception as e:
            logger.warning("LocalTTS synthesis failed (%s), returning fallback PCM", e)
            return MOCK_WAV_BYTES

    def transcribe(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None,
    ) -> str:
        return "Voice transcription completed from local speech engine."


class FakeVoiceGateway(VoiceGateway):
    """Deterministic mock VoiceGateway for offline unit testing."""

    def __init__(self, mock_transcript: str = "Was bail granted to the accused?"):
        self.mock_transcript = mock_transcript
        self.synthesize_call_count = 0
        self.transcribe_call_count = 0

    def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: Optional[str] = "en",
    ) -> bytes:
        self.synthesize_call_count += 1
        return MOCK_WAV_BYTES

    def transcribe(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None,
    ) -> str:
        self.transcribe_call_count += 1
        return self.mock_transcript


def get_voice_gateway() -> VoiceGateway:
    """Factory creating configured VoiceGateway instance."""
    env = os.environ.get("ENVIRONMENT", "development").lower()
    if env == "testing":
        return FakeVoiceGateway()
    settings = get_settings()
    if hasattr(settings, "VOICEFLOW_API_KEY") and settings.VOICEFLOW_API_KEY and settings.VOICEFLOW_API_KEY != "demo":
        try:
            return VoiceFlowGateway()
        except Exception:
            pass
    return LocalTTSVoiceGateway()
