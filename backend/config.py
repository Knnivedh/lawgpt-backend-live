"""
config.py - Centralised configuration management.

Single source of truth for all environment variables.
history_dir is removed — conversation state now lives in PostgreSQL.
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── External API Keys ─────────────────────────────────────────────────────
    huggingface_api_key: str = Field(..., env="HUGGINGFACE_API_KEY")

    # ── Database ──────────────────────────────────────────────────────────────
    # Must be asyncpg driver:
    #   postgresql+asyncpg://user:pass@host:5432/dbname
    database_url: str = Field(..., env="DATABASE_URL")

    # ── Milvus ────────────────────────────────────────────────────────────────
    milvus_host: str            = Field(default="localhost",         env="MILVUS_HOST")
    milvus_port: str            = Field(default="19530",             env="MILVUS_PORT")
    milvus_collection_name: str = Field(default="family_law_cases",  env="MILVUS_COLLECTION_NAME")

    # ── Models ────────────────────────────────────────────────────────────────
    # Indian Law Specific Models
    llm_model: str        = Field(default="meta-llama/Llama-3.1-8B-Instruct", env="LLM_MODEL")
    embedding_model: str  = Field(default="bhavyagiri/InLegal-Sbert", env="EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=768, env="EMBEDDING_DIMENSION")

    # ── RAG ───────────────────────────────────────────────────────────────────
    retrieval_top_k: int = Field(default=5,   env="RETRIEVAL_TOP_K")
    retrieval_cases_top_k: int = Field(default=5, env="RETRIEVAL_CASES_TOP_K")
    retrieval_laws_top_k: int = Field(default=3, env="RETRIEVAL_LAWS_TOP_K")
    retrieval_laws_large_context_top_k: int = Field(default=5, env="RETRIEVAL_LAWS_LARGE_CONTEXT_TOP_K")
    llm_context_window: int = Field(default=8192, env="LLM_CONTEXT_WINDOW")
    large_context_window_threshold: int = Field(default=16000, env="LARGE_CONTEXT_WINDOW_THRESHOLD")
    retrieval_case_categories: list[str] = Field(
        default=["legal_cases", "case_law", "cases", "judgments", "precedents"],
        env="RETRIEVAL_CASE_CATEGORIES",
    )
    retrieval_law_categories: list[str] = Field(
        default=["law_cases", "acts", "statutes", "bare_acts", "laws"],
        env="RETRIEVAL_LAW_CATEGORIES",
    )
    chunk_size: int      = Field(default=800, env="CHUNK_SIZE")
    chunk_overlap: int   = Field(default=100, env="CHUNK_OVERLAP")

    # ── Data Directories (embeddings / chunked data only, no chat history) ───
    data_dir:     str = Field(default="./data",            env="DATA_DIR")
    chunked_dir:  str = Field(default="./data/chunked",    env="CHUNKED_DIR")
    embeddings_dir: str = Field(default="./data/embeddings", env="EMBEDDINGS_DIR")

    # ── Server ────────────────────────────────────────────────────────────────
    api_host: str       = Field(default="0.0.0.0", env="API_HOST")
    api_port: int       = Field(default=8000,       env="API_PORT")
    milvus_uri: str
    milvus_token: str
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"],
        env="CORS_ORIGINS",
    )

    # ── Features ──────────────────────────────────────────────────────────────
    enable_streaming:  bool = Field(default=True, env="ENABLE_STREAMING")
    enable_multi_turn: bool = Field(default=True, env="ENABLE_MULTI_TURN")

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")

    # ── ASR (Speech-to-Text) — AI4Bharat IndicConformer ─────────────────────
    enable_asr: bool = Field(default=True, env="ENABLE_ASR")
    # HuggingFace model repo ID for the ASR model
    asr_model_name: str = Field(
        default="ai4bharat/indic-conformer-600m-multilingual",
        env="ASR_MODEL_NAME",
    )
    # torch device: "cpu" or "cuda"
    asr_device: str = Field(default="cpu", env="ASR_DEVICE")
    # Decoding strategy: "ctc" (faster) or "rnnt" (streaming-friendly)
    asr_strategy: str = Field(default="ctc", env="ASR_STRATEGY")
    # BCP-47 / ISO-639-1 language code used when the client doesn't specify one
    # Common codes: hi=Hindi, ta=Tamil, te=Telugu, bn=Bengali, mr=Marathi
    asr_default_language: str = Field(default="hi", env="ASR_DEFAULT_LANGUAGE")
    asr_max_audio_seconds: int = Field(default=60, env="ASR_MAX_AUDIO_SECONDS")
    asr_rate_limit_per_minute: int = Field(default=20, env="ASR_RATE_LIMIT_PER_MINUTE")
    # IndicConformer covers only these scheduled Indian languages — it has no
    # English label, and forcing it to "transcribe as English" just produces
    # garbage. Anything outside this set (chiefly "en") is routed to
    # faster-whisper instead. Used both to validate an explicit `language` and,
    # after Whisper's language-ID pass in auto mode, to pick the engine.
    asr_indic_languages: List[str] = Field(
        default=[
            "hi", "bn", "te", "mr", "ta", "gu", "kn", "ml", "pa", "or", "as",
            "ur", "ne", "sa", "sd", "ks", "mai", "kok", "mni", "doi", "bho", "raj",
        ],
        env="ASR_INDIC_LANGUAGES",
    )

    # ── ASR — faster-whisper (English + audio-based language ID) ────────────
    # Used for (a) a fast single-pass language-ID on the raw audio when the
    # client omits `language`, and (b) transcribing English (or any other
    # non-Indic language), which IndicConformer cannot handle at all.
    whisper_model_size: str = Field(default="small", env="WHISPER_MODEL_SIZE")
    whisper_device: str = Field(default="cpu", env="WHISPER_DEVICE")
    whisper_compute_type: str = Field(default="int8", env="WHISPER_COMPUTE_TYPE")

    # ── Auth / JWT ────────────────────────────────────────────────────────────
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str  = Field(default="HS256", env="JWT_ALGORITHM")

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # ── Validators ────────────────────────────────────────────────────────────
    @field_validator("huggingface_api_key")
    @classmethod
    def validate_hf_key(cls, v: str) -> str:
        if not v or v == "your_key_here":
            raise ValueError("HUGGINGFACE_API_KEY must be set")
        return v

    @field_validator("database_url")
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        if not v:
            raise ValueError("DATABASE_URL must be set")
        if "asyncpg" not in v:
            raise ValueError(
                "DATABASE_URL must use the asyncpg driver: "
                "postgresql+asyncpg://user:pass@host:5432/dbname"
            )
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",")]
        return v

    @field_validator("asr_indic_languages", mode="before")
    @classmethod
    def parse_asr_indic_languages(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    def create_data_directories(self):
        """Create data directories (embeddings, chunks). No history dir needed."""
        for path in [self.data_dir, self.chunked_dir, self.embeddings_dir]:
            os.makedirs(path, exist_ok=True)
            logger.info(f"Ensured directory: {path}")


# ── Singleton ─────────────────────────────────────────────────────────────────
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        try:
            _settings = Settings()
            _settings.create_data_directories()
            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    return _settings


settings = get_settings()
