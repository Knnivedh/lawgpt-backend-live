"""
Configuration file for Legal Chatbot RAG System
"""
import os
from dotenv import load_dotenv

# Load environment variables from config/.env
load_dotenv("config/.env")

from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

class Config:
    """Main configuration class"""
    
    # ==================== API CONFIGURATION ====================
    # Cerebras API (PRIMARY - FREE 1M tokens/day, VERY FAST)
    CEREBRAS_API_KEY = os.getenv("cerebras_api") or os.getenv("CEREBRAS_API_KEY")
    CEREBRAS_BASE_URL = os.getenv("CEREBRAS_BASE_URL") or "https://api.cerebras.ai/v1"
    CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL") or "llama-3.3-70b"  # Very fast inference
    
    # Groq API (BACKUP - FREE, ULTRA FAST)
    GROQ_API_KEY = os.getenv("groq_api") or os.getenv("GROQ_API_KEY")
    GROQ_BASE_URL = os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1"
    GROQ_MODEL = os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile"  # Single best model for accuracy
    
    # Web Search Configuration
    BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
    SERPER_API_KEY = os.getenv("SERPER_API_KEY")
    
    # NVIDIA API Keys (FALLBACK)
    NVIDIA_API_KEY = os.getenv("nvidia_api") or os.getenv("NVIDIA_API_KEY")
    NVIDIA_API_KEY_2 = os.getenv("nvidia_api_2") or os.getenv("NVIDIA_API_KEY_2")
    NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL = os.getenv("NVIDIA_MODEL_NAME") or "meta/llama-3.1-70b-instruct"

    # OpenRouter API Keys (additional free-model RPM pool)
    OPENROUTER_API_KEY = os.getenv("openrouter_api") or os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_API_KEY_2 = os.getenv("openrouter_api_2") or os.getenv("OPENROUTER_API_KEY_2")
    OPENROUTER_API_KEY_3 = os.getenv("openrouter_api_3") or os.getenv("OPENROUTER_API_KEY_3")
    OPENROUTER_API_KEY_4 = os.getenv("openrouter_api_4") or os.getenv("OPENROUTER_API_KEY_4")
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL") or "nousresearch/hermes-3-llama-3.1-405b:free"

    # Dahl inference gateway — THE SINGLE LLM PROVIDER.
    #
    # Measured against the live endpoint (2026-10): 12/12 calls succeeded on both
    # keys, p50 0.82 s, no rate-limit headers, no 429s under a 100M free-token
    # allowance. LLM_SINGLE_PROVIDER (below) therefore restricts the client pool
    # to Dahl alone -- the multi-vendor rotation is retained in code but disabled
    # by default, because rotating between providers that all work costs latency
    # and buys nothing.
    DAHL_API_KEY = os.getenv("dahl_api") or os.getenv("DAHL_API_KEY")
    DAHL_BASE_URL = os.getenv("DAHL_BASE_URL") or "https://inference.dahl.global/v1"
    # THE single model for every LLM call in the system.
    #
    # MEASURED against the live endpoint on this key (2026-10-05):
    #   deepseek-ai/DeepSeek-V4-Flash-0731, NO reasoning_effort
    #     max_tokens   3 -> 273 chars   3.7s
    #     max_tokens  64 -> 273 chars   0.7s
    #     max_tokens 256 -> 708 chars   8.7s
    #     max_tokens 512 -> 973 chars   0.6s
    #     max_tokens 1500 -> 1199 chars  0.5-8.9s, deterministic
    #   It returns real content at EVERY budget tested, including max_tokens=3.
    #
    # DO NOT send reasoning_effort to this model. Measured, it is actively
    # harmful:
    #     eff=low      -> 970 reasoning tokens,  14.5s,  222 chars
    #     eff=minimal  -> 448 reasoning tokens,   8.3s, 2435 chars
    #     eff=none     ->  0 reasoning tokens,  45.5s, 3543 chars
    # Every explicit value made it slower and produced less usable output than
    # sending nothing at all. See DAHL_REASONING_EFFORT below.
    DAHL_MODEL = os.getenv("DAHL_MODEL") or "deepseek-ai/DeepSeek-V4-Flash-0731"

    # ---------------------------------------------------------------------
    # WHY A DEFAULT SYSTEM PROMPT IS REQUIRED (not a nicety)
    # ---------------------------------------------------------------------
    # MEASURED: this model runs a long HIDDEN reasoning trace by default. On a
    # hard legal question ("Explain res judicata under Section 11 CPC") the
    # trace reached 6974 characters and consumed the ENTIRE max_tokens budget,
    # so the response came back as:
    #
    #     content=''   finish_reason='length'   usage.completion_tokens=1500
    #     message.reasoning = <6974 chars>       <-- the whole budget went here
    #     usage.reasoning_tokens = 0             <-- AND MIS-REPORTED AS ZERO
    #
    # That last part is a vendor reporting bug: the trace is real and visible in
    # message.reasoning, but usage reports zero reasoning tokens, so any
    # client that trusts `usage` sees a clean "used all 1500 tokens on the
    # answer" and cannot tell the answer was never written.
    #
    # Sweeping the remedies (all on the hard question):
    #   reasoning_effort=low      -> 5/5 EMPTY   (unreliable, do NOT rely on it)
    #   reasoning_effort=minimal  -> works but 55.2s
    #   max_tokens 3000, no effort -> works, 44.8s
    #   max_tokens 6000, no effort -> works, 45.9s
    #   temperature 0             -> works, 112.4s
    #   CONCISE SYSTEM PROMPT     -> works, 5.0s   <-- the fix
    #
    # Validated on 8 real legal questions WITH retrieved context:
    #   8/8 non-empty, min 2.2s, avg 7.1s, max 16.1s.
    # So the client sends this unless the caller supplies its own system message.
    DAHL_DEFAULT_SYSTEM_PROMPT = os.getenv("DAHL_DEFAULT_SYSTEM_PROMPT") or (
        "You are a concise Indian legal assistant. Answer directly in under 200 "
        "words. Do not write a reasoning trace; do not think step by step. Cite "
        "only sections you are certain of."
    )
    # Empty by default ON PURPOSE - see the measurements above.
    # Set to a non-empty value only for a different model that requires it
    # (e.g. zai-org/GLM-5.3-Flash needs "low", and returns EMPTY content without
    # it). DeepSeek-V4-Flash must be left empty.
    DAHL_REASONING_EFFORT = os.getenv("DAHL_REASONING_EFFORT", "")

    # Single-provider mode. When true, GroqClientManager loads ONLY Dahl keys
    # and never rotates between vendors. Set false to restore multi-vendor
    # failover (still useful if the free-token allowance is ever exhausted).
    LLM_SINGLE_PROVIDER = str(
        os.getenv("LLM_SINGLE_PROVIDER", "true")
    ).strip().lower() in ("1", "true", "yes", "on")

    # CodeCraft API (clarification gap-analysis model — OpenAI-compatible gateway)
    # Drives the ClarificationEngine's question planner: it reads the user's actual
    # scenario, identifies the legal issues, and derives scenario-specific data gaps.
    CODECRAFT_API_KEY = os.getenv("codecraft_api") or os.getenv("CODECRAFT_API_KEY")
    CODECRAFT_BASE_URL = os.getenv("CODECRAFT_BASE_URL") or "https://codecraftapi.com/v1"
    CODECRAFT_MODEL = os.getenv("CODECRAFT_MODEL") or "deepseek-v4-flash-0731"
    # Optional override for the gap-analysis call only; falls back to CODECRAFT_MODEL.
    CLARIFICATION_GAP_MODEL = os.getenv("CLARIFICATION_GAP_MODEL") or CODECRAFT_MODEL
    # Gap-analysis kill switch and budget. The clarification engine always falls
    # back to its deterministic planner when this is disabled or the call fails.
    CLARIFICATION_GAP_ENABLED = (
        os.getenv("CLARIFICATION_GAP_ENABLED", "true").strip().lower()
        not in ("0", "false", "no", "off")
    )
    # Bounded so a clarification turn still fits the 240s API gateway window. The
    # gap model is a reasoning model and spends part of its budget on hidden
    # reasoning, so the token ceiling must leave room for the visible JSON.
    CLARIFICATION_GAP_TIMEOUT_SECONDS = float(
        os.getenv("CLARIFICATION_GAP_TIMEOUT_SECONDS") or 60
    )
    CLARIFICATION_GAP_MAX_TOKENS = int(
        os.getenv("CLARIFICATION_GAP_MAX_TOKENS") or 4000
    )
    # Hidden-reasoning budget hint ("minimal" keeps the turn fast). If the gateway
    # or model rejects the parameter, the engine retries once without it.
    CLARIFICATION_GAP_REASONING_EFFORT = (
        os.getenv("CLARIFICATION_GAP_REASONING_EFFORT", "minimal") or ""
    ).strip()

    # TokenRouter API (PRIMARY brain — OpenAI-compatible gateway, GLM-5.3 reasoning model)
    # Replaces Llama as the main synthesis/debate model. Groq/Cerebras/NVIDIA/OpenRouter
    # remain as rotation fallbacks when TokenRouter returns 429 or errors.
    TOKENROUTER_API_KEY = os.getenv("tokenrouter_api") or os.getenv("TOKENROUTER_API_KEY")
    TOKENROUTER_BASE_URL = os.getenv("TOKENROUTER_BASE_URL") or "https://api.tokenrouter.com/v1"
    TOKENROUTER_MODEL = os.getenv("TOKENROUTER_MODEL", "z-ai/glm-5.3-free")

    # ==================== LLM MODEL REGISTRY (single source of truth) ====================
    # SINGLE-MODEL MODE (measured 2026-10)
    # -----------------------------
    # The account has a 100M free-token allowance on Dahl, which measured 12/12
    # success at p50 0.82 s with no 429s. A second provider/model therefore adds
    # latency and failover complexity with no reliability benefit, so both
    # registry tiers resolve to the SAME model: zai-org/GLM-5.3-Flash on Dahl.
    #
    # The two-tier structure is kept (many call sites reference FAST_LLM_MODEL /
    # MAIN_LLM_MODEL) but both values are identical, so there is exactly one
    # model in the system. Set LLM_SINGLE_PROVIDER=false to restore the previous
    # split rig with Groq/Cerebras/TokenRouter failover.
    if LLM_SINGLE_PROVIDER:
        MAIN_LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("MAIN_LLM_MODEL") or DAHL_MODEL
        # Flash requests used to bypass to a Groq qwen client. That bypass is
        # disabled in single-provider mode (see client_manager) so a "fast"
        # query does not silently hit a second provider.
        FAST_LLM_MODEL = os.getenv("FAST_LLM_MODEL") or MAIN_LLM_MODEL
    else:
        MAIN_LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("MAIN_LLM_MODEL") or GROQ_MODEL
        FAST_LLM_MODEL = os.getenv("FAST_LLM_MODEL") or "qwen/qwen3.8-27b"
    CLARIFICATION_MODEL = os.getenv("GROQ_CLARIFICATION_MODEL") or FAST_LLM_MODEL
    
    # LLM Configuration
    TEMPERATURE = 0.15  # Low temperature for precise legal answers
    MAX_TOKENS = 4000  # Increased for comprehensive legal responses
    
    # Provider Priority (1=highest)
    LLM_PROVIDERS = [
        {"name": "tokenrouter", "priority": 0, "speed": "reasoning"},
        {"name": "openrouter", "priority": 1, "speed": "free_pool"},
        {"name": "cerebras", "priority": 2, "speed": "very_fast"},
        {"name": "groq", "priority": 3, "speed": "ultra_fast"},
        {"name": "nvidia", "priority": 4, "speed": "moderate"}
    ]
    
    # ==================== DATA PATHS ====================
    DATA_DIR = str(PROJECT_ROOT / "DATA")
    CHROMA_DB_DIR = str(PROJECT_ROOT / "chroma_db")
    COLLECTION_NAME = "legal_db_full"
    
    # Domain Paths
    DOMAIN_PATHS = {
        "case_studies": "Indian_Case_Studies_50K ORG/Indian_Case_Studies_50K ORG.json",
        "indian_express": "indianexpress_property_law_qa/indianexpress_property_law_qa.json",
        "kanoon": "kanoon.com/kanoon.com/kanoon_data.json",
        "legallyin": "legallyin.com/legallyin.com.json",
        "ndtv": "ndtv_legal_qa_data/ndtv_legal_qa_data.json",
        "hindu": "thehindu/thehindu.json",
        "wikipedia": "wikipedia.org/wikipedia.org.json"
    }
    
    # ==================== RAG SETTINGS ====================
    # Embedding Model
    EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"  # Small, fast, accurate
    
    # Retrieval Settings
    TOP_K_RESULTS = 5           # Number of documents to retrieve
    SIMILARITY_THRESHOLD = 0.5  # Minimum similarity score
    
    # Chunking Settings (if needed)
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    
    # ==================== PROCESSING SETTINGS ====================
    BATCH_SIZE = 1000           # Batch size for loading data
    MAX_WORKERS = 4             # Parallel processing threads
    
    # ==================== API SETTINGS ====================
    API_HOST = "0.0.0.0"
    API_PORT = 8000
    API_RELOAD = True           # Auto-reload on code changes
    
    # ==================== UI SETTINGS ====================
    UI_TITLE = "⚖️ Indian Legal Assistant"
    UI_SUBTITLE = "156K+ Legal Records • NVIDIA Llama 3.1 70B • Free & Fast"
    
    # Categories for filtering
    LEGAL_CATEGORIES = [
        "All",
        "Property Law",
        "Criminal Law",
        "Family Law",
        "Corporate Law",
        "Corruption",
        "Murder",
        "Rape",
        "Fraud",
        "Terrorism"
    ]
    
    # ==================== SYSTEM SETTINGS ====================
    DEBUG = True
    LOG_LEVEL = "INFO"
    CACHE_ENABLED = True
    CACHE_SIZE = 1000
    
    # ==================== VALIDATION ====================
    @classmethod
    def get_llm_config(cls, provider: str = "cerebras"):
        """Get LLM configuration for specified provider"""
        configs = {
            "cerebras": {
                "api_key": cls.CEREBRAS_API_KEY,
                "base_url": cls.CEREBRAS_BASE_URL,
                "model": cls.CEREBRAS_MODEL,
                "name": "Cerebras"
            },
            "groq": {
                "api_key": cls.GROQ_API_KEY,
                "base_url": cls.GROQ_BASE_URL,
                "model": cls.GROQ_MODEL,
                "name": "Groq"
            },
            "nvidia": {
                "api_key": cls.NVIDIA_API_KEY,
                "base_url": cls.NVIDIA_BASE_URL,
                "model": cls.NVIDIA_MODEL,
                "name": "NVIDIA"
            },
            "openrouter": {
                "api_key": cls.OPENROUTER_API_KEY,
                "base_url": cls.OPENROUTER_BASE_URL,
                "model": cls.OPENROUTER_MODEL,
                "name": "OpenRouter"
            },
            "tokenrouter": {
                "api_key": cls.TOKENROUTER_API_KEY,
                "base_url": cls.TOKENROUTER_BASE_URL,
                "model": cls.TOKENROUTER_MODEL,
                "name": "TokenRouter"
            },
            "codecraft": {
                "api_key": cls.CODECRAFT_API_KEY,
                "base_url": cls.CODECRAFT_BASE_URL,
                "model": cls.CODECRAFT_MODEL,
                "name": "CodeCraft"
            }
        }
        return configs.get(provider, configs["tokenrouter"])
    
    @classmethod
    def get_available_provider(cls):
        """Get first available LLM provider"""
        if cls.TOKENROUTER_API_KEY:
            return "tokenrouter"
        elif cls.OPENROUTER_API_KEY:
            return "openrouter"
        elif cls.CEREBRAS_API_KEY:
            return "cerebras"
        elif cls.GROQ_API_KEY:
            return "groq"
        elif cls.NVIDIA_API_KEY:
            return "nvidia"
        return None
    
    @classmethod
    def get_nvidia_api_key(cls, use_backup: bool = False):
        """Get NVIDIA API key with failover support (deprecated, use get_llm_config)"""
        if use_backup and cls.NVIDIA_API_KEY_2:
            return cls.NVIDIA_API_KEY_2
        return cls.NVIDIA_API_KEY
    
    @classmethod
    def validate(cls):
        """Validate configuration"""
        errors = []
        
        if not cls.NVIDIA_API_KEY:
            errors.append("NVIDIA_API_KEY (nvidia_api) not set in config/.env")
        
        if not os.path.exists(cls.DATA_DIR):
            errors.append(f"DATA directory not found: {cls.DATA_DIR}")
        
        if errors:
            raise ValueError("Configuration errors:\n" + "\n".join(errors))
        
        return True
    
    @classmethod
    def print_config(cls):
        """Print current configuration"""
        print("="*60)
        print("LEGAL CHATBOT CONFIGURATION")
        print("="*60)
        print(f"NVIDIA API Key 1: {cls.NVIDIA_API_KEY[:20] if cls.NVIDIA_API_KEY else 'NOT SET'}...")
        print(f"NVIDIA API Key 2: {cls.NVIDIA_API_KEY_2[:20] if cls.NVIDIA_API_KEY_2 else 'NOT SET'}...")
        print(f"NVIDIA Model: {cls.NVIDIA_MODEL}")
        print(f"NVIDIA Base URL: {cls.NVIDIA_BASE_URL}")
        print(f"Temperature: {cls.TEMPERATURE}")
        print(f"Max Tokens: {cls.MAX_TOKENS}")
        print(f"Data Directory: {cls.DATA_DIR}")
        print(f"ChromaDB Directory: {cls.CHROMA_DB_DIR}")
        print(f"Embedding Model: {cls.EMBEDDING_MODEL}")
        print(f"Top K Results: {cls.TOP_K_RESULTS}")
        print("="*60)


# Validate on import
if __name__ != "__main__":
    try:
        Config.validate()
    except ValueError as e:
        print(f"WARNING - Configuration: {e}")
