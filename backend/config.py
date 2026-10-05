"""
config.py - Centralised configuration management.

Single source of truth for all environment variables.
history_dir is removed — conversation state now lives in PostgreSQL.
"""

import os
import json
from typing import Annotated, List, Optional
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
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
    # Text put in front of a question before it is embedded. Some models are
    # trained with one; BAAI/bge-*-en-v1.5 use
    # "Represent this sentence for searching relevant passages: ".
    # Documents are embedded without it.
    embedding_query_prefix: str = Field(default="", env="EMBEDDING_QUERY_PREFIX")

    # ── Query translation (any language → English, used for retrieval only) ───
    translation_model: str = Field(default="google/gemma-3-4b-it", env="TRANSLATION_MODEL")
    enable_query_translation: bool = Field(default=False, env="ENABLE_QUERY_TRANSLATION")
    # Inference providers tried in order for the translation model; "auto" lets
    # Hugging Face choose. A second entry is the fallback when the first refuses.
    # "ollama" calls ollama_translation_model through Ollama instead of Hugging
    # Face, e.g. TRANSLATION_PROVIDERS=ollama,auto.
    translation_providers: Annotated[List[str], NoDecode] = Field(
        default=["auto"], env="TRANSLATION_PROVIDERS"
    )
    ollama_translation_model: str = Field(default="gemma4:31b-cloud", env="OLLAMA_TRANSLATION_MODEL")
    # A local Ollama app signed in to ollama.com serves cloud models at the
    # default URL with no key. On a server with no Ollama app, set
    # OLLAMA_BASE_URL=https://ollama.com and OLLAMA_API_KEY.
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_api_key: Optional[str] = Field(default=None, env="OLLAMA_API_KEY")
    # Optional rollout allowlist of detected_language codes. Empty = every
    # non-English query. Note langdetect mislabels code-mixed text (Hinglish
    # often comes back as "fi"/"es"), so an allowlist skips those queries.
    translation_enabled_languages: Annotated[List[str], NoDecode] = Field(
        default=[], env="TRANSLATION_ENABLED_LANGUAGES"
    )
    # Rewrite every question (English included) into a short neutral search
    # query before retrieval. Done in the same model call as the translation.
    # Off by default: on the 36-query retrieval set it did not beat hybrid
    # search alone, and it costs one model call per English question.
    enable_query_rewrite: bool = Field(default=False, env="ENABLE_QUERY_REWRITE")
    # Merge BM25 keyword ranking with the vector ranking (no API calls).
    enable_hybrid_search: bool = Field(default=True, env="ENABLE_HYBRID_SEARCH")
    # Weight of each ranking in the merge. On the 200-question retrieval set
    # the keyword ranking alone found more relevant documents than the vector
    # ranking, so it counts for more. 0 switches a ranking off.
    retrieval_keyword_weight: float = Field(default=2.0, env="RETRIEVAL_KEYWORD_WEIGHT")
    retrieval_vector_weight: float = Field(default=1.0, env="RETRIEVAL_VECTOR_WEIGHT")
    # Skip off-topic documents and return one document per subject
    # (see corpus_curation.py).
    enable_corpus_curation: bool = Field(default=True, env="ENABLE_CORPUS_CURATION")

    # What the citation guard does with a citation it cannot find in the
    # retrieved context: "strict" removes the sentence for any kind; "mixed"
    # removes for sections, act+section mismatches and case names but only
    # flags bare act names; "flag" removes for sections only. See citation_guard.py.
    citation_guard_mode: str = Field(default="mixed", env="CITATION_GUARD_MODE")

    # ── RAG ───────────────────────────────────────────────────────────────────
    retrieval_top_k: int = Field(default=5,   env="RETRIEVAL_TOP_K")
    retrieval_cases_top_k: int = Field(default=5, env="RETRIEVAL_CASES_TOP_K")
    retrieval_laws_top_k: int = Field(default=5, env="RETRIEVAL_LAWS_TOP_K")
    retrieval_laws_large_context_top_k: int = Field(default=5, env="RETRIEVAL_LAWS_LARGE_CONTEXT_TOP_K")
    llm_context_window: int = Field(default=8192, env="LLM_CONTEXT_WINDOW")
    large_context_window_threshold: int = Field(default=16000, env="LARGE_CONTEXT_WINDOW_THRESHOLD")
    # Actual Milvus category values (verified against the live collection):
    # "family_law" = Kaanoon-style case Q&A, "family_law_2" = statute/case-law
    # summaries. The previous defaults here ("legal_cases", "acts", etc.)
    # never matched anything in the data, so the case/law category split
    # silently did nothing and both searches fell through to their unfiltered
    # fallback every time.
    retrieval_case_categories: Annotated[List[str], NoDecode] = Field(
        default=["family_law"],
        env="RETRIEVAL_CASE_CATEGORIES",
    )
    retrieval_law_categories: Annotated[List[str], NoDecode] = Field(
        default=["family_law_2"],
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
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:3000", "http://localhost:3001"],
        env="CORS_ORIGINS",
    )

    # ── Features ──────────────────────────────────────────────────────────────
    enable_streaming:  bool = Field(default=True, env="ENABLE_STREAMING")
    enable_multi_turn: bool = Field(default=True, env="ENABLE_MULTI_TURN")

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")

    # ── ASR (Speech-to-Text) — routed to HuggingFace Spaces ─────────────────
    enable_asr: bool = Field(default=True, env="ENABLE_ASR")
    # BCP-47 / ISO-639-1 language code used when the client doesn't specify one
    # Common codes: hi=Hindi, ta=Tamil, te=Telugu, bn=Bengali, mr=Marathi
    asr_default_language: str = Field(default="hi", env="ASR_DEFAULT_LANGUAGE")
    asr_max_audio_seconds: int = Field(default=60, env="ASR_MAX_AUDIO_SECONDS")
    asr_rate_limit_per_minute: int = Field(default=20, env="ASR_RATE_LIMIT_PER_MINUTE")
    # IndicConformer covers only these scheduled Indian languages — anything
    # outside this set (chiefly "en") is routed to the Whisper Space instead.
    asr_indic_languages: Annotated[List[str], NoDecode] = Field(
        default=[
            "hi", "bn", "te", "mr", "ta", "gu", "kn", "ml", "pa", "or", "as",
            "ur", "ne", "sa", "sd", "ks", "mai", "kok", "mni", "doi", "bho", "raj",
        ],
        env="ASR_INDIC_LANGUAGES",
    )

    # ── HuggingFace Space URLs (model microservices) ──────────────────────────
    # Whisper small Space — handles English + audio-based language ID
    whisper_space_url: str = Field(
        default="rverma0631/Whisper",
        env="WHISPER_SPACE_URL",
    )
    # IndicConformer 600M Space — handles 22 Indian languages
    indic_asr_space_url: str = Field(
        default="rverma0631/MultilingualASR",
        env="INDIC_ASR_SPACE_URL",
    )
    # IndicParler-TTS Space — multilingual TTS
    indic_tts_space_url: str = Field(
        default="R910/IndicParler_TTS",
        env="INDIC_TTS_SPACE_URL",
    )

    tts_fallback_space_url: str = Field(
        default="rverma0631/TTS_Sanskrit",
        env="TTS_FALLBACK_SPACE_URL",
    )

    tts_english_speaker: str = Field(default="Mary", env="TTS_ENGLISH_SPEAKER")

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
            value = v.strip()
            if value.startswith("["):
                return json.loads(value)
            return [o.strip() for o in value.split(",") if o.strip()]
        return v

    @field_validator("asr_indic_languages", mode="before")
    @classmethod
    def parse_asr_indic_languages(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("translation_enabled_languages", "translation_providers", mode="before")
    @classmethod
    def parse_translation_enabled_languages(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("retrieval_case_categories", "retrieval_law_categories", mode="before")
    @classmethod
    def parse_retrieval_categories(cls, v):
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
