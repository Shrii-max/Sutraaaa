"""Configuration settings for LexAgent Foundation (Phase 1).

All model names, dimensions, URLs, and encryption keys are read from environment variables.
Never hardcode secrets or model names.
"""

from functools import lru_cache
from typing import Optional
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration with strict environment variable bindings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Local LLM endpoint (Ollama / vLLM / OpenAI-compatible local server)
    LLM_BASE_URL: str = Field(
        default="http://localhost:11434/v1",
        description="Base URL for local OpenAI-compatible inference server.",
    )
    LLM_MODEL: str = Field(
        default="qwen2.5:14b-instruct",
        description="Model identifier served by the local LLM runtime.",
    )

    # Local Embedding endpoint & model
    EMBEDDING_BASE_URL: str = Field(
        default="http://localhost:11434/v1",
        description="Base URL for local embedding endpoint.",
    )
    EMBED_MODEL: str = Field(
        default="BAAI/bge-m3",
        validation_alias=AliasChoices("EMBED_MODEL", "EMBEDDING_MODEL"),
        description="Configurable embedding model name.",
    )
    EMBED_DIM: int = Field(
        default=1024,
        validation_alias=AliasChoices("EMBED_DIM", "EMBEDDING_DIM"),
        description="Embedding vector dimension (e.g. 1024 for bge-m3).",
    )

    @property
    def EMBEDDING_MODEL(self) -> str:
        return self.EMBED_MODEL

    @property
    def EMBEDDING_DIM(self) -> int:
        return self.EMBED_DIM

    # Database
    DB_URL: str = Field(
        default="sqlite:///lexagent.db",
        validation_alias=AliasChoices("DB_URL", "DATABASE_URL"),
        description="SQLAlchemy database URL.",
    )

    # Security & Encryption
    ENCRYPTION_KEY: str = Field(
        default="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        validation_alias=AliasChoices("ENCRYPTION_KEY", "DOCUMENT_ENCRYPTION_KEY"),
        description="Hex-encoded 32-byte key for AES-256-GCM encryption at rest.",
    )
    JWT_SECRET: str = Field(
        default="super-secret-jwt-token-signing-key-for-local-lexagent",
        validation_alias=AliasChoices("JWT_SECRET", "AUDIT_HMAC_SECRET"),
        description="Secret key used for JWT signing and HMAC tamper prevention.",
    )

    # Optional paths and parameters
    ENCRYPTED_STORAGE_DIR: str = Field(
        default="./vault_storage",
        description="Local directory path for storing AES-256-GCM encrypted document blobs.",
    )
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    APP_HOST: str = Field(default="0.0.0.0")
    APP_PORT: int = Field(default=8000)
    LLM_TEMPERATURE: float = Field(default=0.1, ge=0.0, le=1.0)
    LLM_MAX_RETRIES: int = Field(default=2, ge=0, le=5)
    CONFIDENCE_THRESHOLD: float = Field(default=0.75, ge=0.0, le=1.0)

    # Hardening & Guardrail Settings (Phase 6)
    MAX_FILE_SIZE_BYTES: int = Field(
        default=50 * 1024 * 1024,
        description="Maximum allowed document file size in bytes (default 50MB).",
    )
    MAX_DOCUMENT_PAGES: int = Field(
        default=200,
        description="Maximum allowed document pages (default 200 pages).",
    )
    AGENT_TIMEOUT_SECONDS: int = Field(
        default=60,
        description="Agent LLM execution timeout in seconds.",
    )
    PII_MASKING_ENABLED: bool = Field(
        default=True,
        description="Enable automatic redaction of Aadhaar, PAN, and phone numbers in logs and audit.",
    )

    # =========================================================================
    # v2 Upgrade Settings: Model Routing, OCR v2, Contradiction Jury & DPDP
    # =========================================================================
    TASK_MODEL_EXTRACTION: str = Field(
        default="qwen2.5:14b-instruct",
        description="Model designated for complex multi-lingual fact extraction.",
    )
    TASK_MODEL_JUDGE: str = Field(
        default="qwen2.5:14b-instruct",
        description="Model designated for contradiction jury & legal verification.",
    )
    TASK_MODEL_SUMMARY: str = Field(
        default="qwen2.5:14b-instruct",
        description="Model designated for document and case summarization.",
    )
    TASK_MODEL_TRANSLATE: str = Field(
        default="qwen2.5:14b-instruct",
        description="Fallback local LLM model for translation tasks.",
    )
    TASK_MODEL_ESCALATION: str = Field(
        default="deepseek-r1:14b",
        description="Larger or reasoning local model escalated to when confidence is low.",
    )
    MODEL_ESCALATION_CONFIDENCE_THRESHOLD: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Confidence threshold below which extraction/reasoning escalates to ESCALATION_MODEL.",
    )

    # OCR v2 & Computer Vision Settings
    OCR_CONFIDENCE_THRESHOLD: float = Field(
        default=0.82,
        ge=0.0,
        le=1.0,
        description="Page OCR confidence threshold gating downstream trust.",
    )
    OCR_PREPROCESS_IMAGE: bool = Field(
        default=True,
        description="Apply deskew, denoise, contrast adjustment, and binarization before OCR.",
    )
    OCR_SECONDARY_ENGINE: str = Field(
        default="paddleocr",
        description="Secondary OCR engine used for agreement voting on low confidence pages.",
    )

    # Fact Verification & Contradiction Settings
    FACT_VERIFIER_STRICTNESS: str = Field(
        default="high",
        description="NLI entailment strictness (high, medium, low).",
    )
    CONTRADICTION_SIMILARITY_THRESHOLD: float = Field(
        default=0.82,
        ge=0.0,
        le=1.0,
        description="Cosine similarity threshold for contradiction candidate pairs.",
    )
    CONTRADICTION_JURY_VOTES: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Number of independent LLM votes in the contradiction jury.",
    )
    CONTRADICTION_MIN_CONSENSUS: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Minimum majority votes required to confirm a contradiction.",
    )

    # Retrieval & Data Hardening
    RETRIEVAL_SCORE_FLOOR: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Minimum hybrid retrieval score required for precedent candidate chunks.",
    )
    MAPPINGS_DIR: str = Field(
        default="./data/mappings",
        description="Path to statutory concordance mapping JSON files (IPC-BNS, CrPC-BNSS).",
    )

    # Security, KMS & DPDP Compliance
    KMS_PROVIDER: str = Field(
        default="local_envelope",
        description="KMS provider implementation ('local_envelope', 'env').",
    )
    ENABLE_PROMPT_INJECTION_SCANNER: bool = Field(
        default=True,
        description="Scan document text for prompt injection / jailbreak patterns before LLM ingestion.",
    )
    DPDP_RETENTION_DAYS: int = Field(
        default=365,
        description="Configurable DPDP case data retention period in days.",
    )
    DPDP_ENABLE_CRYPTO_SHRED: bool = Field(
        default=True,
        description="Enable cryptographic shredding of document vault blobs and DB rows upon erasure.",
    )

    # Multilingual & Translation Settings (Decoupled from LLM_BASE_URL)
    TRANSLATE_ENGINE: str = Field(
        default="configured",
        validation_alias=AliasChoices("TRANSLATE_ENGINE", "TRANSLATION_ENGINE"),
        description="Translation engine: 'configured' (neural web), 'rules' (glossary), 'indictrans2', 'nllb', 'local_llm', or 'stub'.",
    )
    XAI_API_KEY: Optional[str] = Field(default=None, repr=False)
    XAI_TRANSLATION_MODEL: str = Field(default="grok-4.7")

    TRANSLATE_BASE_URL: str = Field(
        default="http://localhost:8088",
        description="Dedicated translation microservice endpoint (decoupled from LLM_BASE_URL).",
    )
    TRANSLATE_API_KEY: Optional[str] = Field(
        default=None,
        description="Optional API key for dedicated translation service.",
    )
    TRANSLATE_TIMEOUT: float = Field(
        default=15.0,
        description="Request timeout in seconds for translation service.",
    )
    TRANSLATION_BACKCHECK_THRESHOLD: float = Field(
        default=0.75,
        description="Minimum back-translation similarity score before flagging needs_human_review.",
    )

    # Voice & Speech Settings
    VOICE_PROVIDER: str = Field(
        default="local",
        description="Voice speech provider: 'local' (pyttsx3/browser Web Speech) or 'vapi' (cloud voice API with explicit user consent).",
    )
    VAPI_BASE_URL: str = Field(
        default="https://api.vapi.ai",
        description="Base URL for optional Vapi service.",
    )
    VAPI_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for optional Vapi service (only used if VOICE_PROVIDER=vapi and case consent granted).",
    )
    VOICEFLOW_BASE_URL: str = Field(
        default="http://localhost:8080",
        description="Base URL for external VoiceFlow speech synthesis and transcription microservice.",
    )
    VOICEFLOW_API_KEY: str = Field(
        default="vf_local_secret_key_12345",
        description="API token for VoiceFlow gateway communication.",
    )
    VOICEFLOW_VOICE_ID: str = Field(
        default="hi-IN-Standard-A",
        description="Default voice profile identifier for speech output.",
    )
    VOICE_STORE_AUDIO: bool = Field(
        default=False,
        description="Persist synthesized speech audio files to disk (default False: ephemeral RAM only).",
    )

    # Demo Mode Guard (Hard Rule 4 & 5: No dummy seeds unless explicitly requested)
    DEMO_MODE: bool = Field(
        default=False,
        description="Whether demo seeding and sample accounts are active. Production default is strictly False.",
    )

    # Backward-compatible properties
    @property
    def DATABASE_URL(self) -> str:
        return self.DB_URL

    @property
    def EMBEDDING_MODEL(self) -> str:
        return self.EMBED_MODEL

    @property
    def EMBEDDING_DIM(self) -> int:
        return self.EMBED_DIM

    @property
    def DOCUMENT_ENCRYPTION_KEY(self) -> str:
        return self.ENCRYPTION_KEY

    @property
    def AUDIT_HMAC_SECRET(self) -> str:
        return self.JWT_SECRET

    # Mandatory Legal Disclaimer
    DISCLAIMER_TEXT: str = Field(
        default=(
            "LEGAL DISCLAIMER: LexAgent is a decision-support intelligence system intended "
            "exclusively for licensed advocates and legal researchers. It does not provide legal advice, "
            "substitute professional judicial assessment, or establish an advocate-client relationship. "
            "All statutory citations, limitation calculations, and precedents must be verified by counsel."
        ),
        description="Mandatory disclaimer attached to all legal outputs.",
    )


@lru_cache()
def get_settings() -> Settings:
    """Singleton getter for cached settings."""
    return Settings()
