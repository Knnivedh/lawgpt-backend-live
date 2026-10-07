"""
COURT DEBATE ENGINE — LAW-GPT | Indian Legal Assistant
=======================================================
Features:
  ✅ Phase 1  — Complexity gate (auto-triggers debate offer)
  ✅ Phase 2  — 7-Level integrated deliberation (1 LLM call, fast)
  ✅ Phase 3  — Modular 3-agent debate: Advocate A + B + Judge (3 calls)
  ✅ Memory   — Auto-loads prior chat history from ShortTermMemory
  ✅ Streaming — SSE generator yields Level 1→7 progressively
  ✅ Zilliz   — Pulls evidence from Main + Statute cloud collections
  ✅ LLM chain — Cerebras → Groq → NVIDIA fallback (mirrors config.py)
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import dataclass
import json
import logging
import os
import re
import sys
import threading
import time
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path bootstrap (mirrors main.py pattern)
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
for _p in [_HERE, _BACKEND_ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import rag_config
except ModuleNotFoundError:
    from kaanoon_test import rag_config  # type: ignore

try:
    from kaanoon_test.authority_resolver import AuthorityResolver, normalize_authority_display_name
except ModuleNotFoundError:
    from authority_resolver import AuthorityResolver, normalize_authority_display_name  # type: ignore

try:
    from config.config import Config
except Exception:
    Config = None  # type: ignore

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")

_ADVISORY_QUALITY_FLAGS = {"uncertain_quote_style"}
_FATAL_QUALITY_FLAGS = {"llm_generation_failed", "llm_generation_timeout"}
_BLOCKING_QUALITY_FLAGS = {
    "too_thin",
    "missing_major_framed_issues",
    "missing_exact_retrieval_status",
    "missing_required_authority_reference",
    "missing_authority_packet_shape",
    "missing_support_strength_labels",
    "missing_authority_anchor",
    "missing_explicit_authority_gap",
    "missing_locked_blueprint_coverage",
}
_STREAM_EVIDENCE_TIMEOUT_SECONDS = float(os.getenv("COURT_DEBATE_STREAM_EVIDENCE_TIMEOUT_SECONDS", "12"))
_CARD_TIMEOUT_SECONDS = {
    # GLM-5.3 reasons for 15-60s per section; the old 25-45s values forced
    # Advocates into fallback filler. Env overrides still win.
    "l2": float(os.getenv("COURT_DEBATE_CARD_L2_TIMEOUT_SECONDS", "100")),
    "l3": float(os.getenv("COURT_DEBATE_CARD_L3_TIMEOUT_SECONDS", "100")),
    "l5": float(os.getenv("COURT_DEBATE_CARD_L5_TIMEOUT_SECONDS", "80")),
    "l6": float(os.getenv("COURT_DEBATE_CARD_L6_TIMEOUT_SECONDS", "100")),
    "l7": float(os.getenv("COURT_DEBATE_CARD_L7_TIMEOUT_SECONDS", "80")),
    "l8": float(os.getenv("COURT_DEBATE_CARD_L8_TIMEOUT_SECONDS", "60")),
}

# ---------------------------------------------------------------------------
# Singleton short-term memory (shared with main RAG pipeline)
# ---------------------------------------------------------------------------
_stm = None  # lazy-loaded


def _get_stm():
    global _stm
    if _stm is None:
        try:
            from kaanoon_test.system_adapters.persistent_memory import ShortTermMemory
            _stm = ShortTermMemory(max_turns=10)
            logger.info("[CourtDebate] ShortTermMemory initialised")
        except Exception as e:
            logger.warning(f"[CourtDebate] ShortTermMemory unavailable: {e}")
            _stm = None
    return _stm


# ===========================================================================
# LLM CLIENT  (Cerebras → Groq → NVIDIA — mirrors config.py priority)
# ===========================================================================

class LegacyLawGPTLLMClient:
    """Thin wrapper around the existing provider chain with live-ping failover."""

    def __init__(self):
        self._client = None
        self._model: str = ""
        self.provider: str = "none"
        self._candidates = []  # Store all candidates for mid-session failover
        self._exhausted_keys = set()  # Track rate-limited keys
        self._setup()

    def _setup(self):
        cfg = Config
        _env = os.getenv

        # Collect all available keys
        cerebras_key = _env("cerebras_api") or _env("CEREBRAS_API_KEY") or (
            getattr(cfg, "CEREBRAS_API_KEY", None) if cfg else None)

        # Collect ALL Groq keys (primary + numbered variants)
        groq_keys = []
        for k in ["groq_api", "GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3",
                   "GROQ_API_KEY_4", "GROQ_API_KEY_5"]:
            val = _env(k) or (getattr(cfg, k, None) if cfg else None)
            if val and val not in groq_keys:
                groq_keys.append(val)

        nvidia_key = _env("nvidia_api") or _env("NVIDIA_API_KEY") or (
            getattr(cfg, "NVIDIA_API_KEY", None) if cfg else None)

        # Build candidate list: (key, base_url, [models_to_try], provider_name)
        candidates = []
        if cerebras_key:
            candidates.append((
                cerebras_key,
                "https://api.cerebras.ai/v1",
                ["llama-4-scout-17b-16e-instruct", "llama-3.3-70b", "llama3.1-70b",
                 "qwen-3-32b", "deepseek-r1-distill-llama-70b"],
                "cerebras",
            ))
        for gk in groq_keys:
            candidates.append((
                gk,
                "https://api.groq.com/openai/v1",
                ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile",
                 "llama3-70b-8192", "llama-3.1-8b-instant"],
                "groq",
            ))
        if nvidia_key:
            candidates.append((
                nvidia_key,
                "https://integrate.api.nvidia.com/v1",
                ["meta/llama-3.1-70b-instruct", "meta/llama-3.1-8b-instruct"],
                "nvidia",
            ))

        self._candidates = candidates  # Save for mid-session failover

        # Try each candidate with a live ping
        self._try_candidates(candidates)

    def _try_candidates(self, candidates):
        """Test candidate providers and select the first working one."""
        for key, base_url, models, name in candidates:
            if key in self._exhausted_keys:
                logger.debug(f"[CourtDebate] Skipping exhausted key for {name}")
                continue
            try:
                from openai import OpenAI
                client = OpenAI(api_key=key, base_url=base_url)
                for model in models:
                    try:
                        resp = client.chat.completions.create(
                            model=model,
                            messages=[{"role": "user", "content": "Reply with OK"}],
                            max_tokens=3,
                            temperature=0,
                        )
                        reply = (resp.choices[0].message.content or "").strip()
                        if reply:
                            self._client = client
                            self._model = model
                            self.provider = name
                            logger.info(f"[CourtDebate] LLM ready: {name} / {model}")
                            return True
                    except Exception as model_err:
                        err_str = str(model_err)
                        if "429" in err_str or "rate_limit" in err_str.lower():
                            logger.warning(f"[CourtDebate] {name}/{model} rate-limited during ping, marking exhausted")
                            self._exhausted_keys.add(key)
                            break
                        logger.debug(f"[CourtDebate] {name}/{model} ping failed: {model_err}")
                        continue
            except Exception as e:
                logger.warning(f"[CourtDebate] {name} client init failed: {e}")

        logger.error("[CourtDebate] No LLM provider available after testing all candidates.")
        return False

    def _failover_on_429(self, current_key=None):
        """When a 429 hits mid-session, mark the current key exhausted and try the next provider."""
        if current_key:
            self._exhausted_keys.add(current_key)
        logger.warning(f"[CourtDebate] 429 rate limit hit on {self.provider}. Attempting failover...")

        # Get current key to mark it
        remaining = [c for c in self._candidates if c[0] not in self._exhausted_keys]
        if remaining:
            return self._try_candidates(remaining)
        logger.error("[CourtDebate] All provider keys exhausted (429). No fallback available.")
        return False

    def _get_current_key(self):
        """Get the API key of the current client for exhaustion tracking."""
        if self._client and hasattr(self._client, "api_key"):
            return self._client.api_key
        return None

    def generate(self, prompt: str, max_tokens: int = 3000, temperature: float = 0.2) -> str:
        if not self._client:
            return "[ERROR] No LLM provider configured."
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            err_str = str(e)
            # If it's a 429 rate limit, try failover and retry once
            if "429" in err_str or "rate_limit" in err_str.lower():
                logger.warning(f"[CourtDebate] 429 on generate ({self.provider}), attempting failover...")
                current_key = self._get_current_key()
                if self._failover_on_429(current_key):
                    logger.info(f"[CourtDebate] Failover successful → {self.provider}/{self._model}. Retrying...")
                    try:
                        resp = self._client.chat.completions.create(
                            model=self._model,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=max_tokens,
                            temperature=temperature,
                        )
                        return resp.choices[0].message.content or ""
                    except Exception as retry_err:
                        logger.error(f"[CourtDebate] Retry after failover also failed: {retry_err}")
                        return f"[LLM ERROR] All providers exhausted. Last error: {retry_err}"
            logger.error(f"[CourtDebate] LLM error ({self.provider}): {e}")
            return f"[LLM ERROR] {e}"

    def stream(self, prompt: str, max_tokens: int = 3000, temperature: float = 0.2) -> Generator[str, None, None]:
        """Yield text chunks for streaming responses."""
        if not self._client:
            yield "[ERROR] No LLM provider configured."
            return
        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str.lower():
                logger.warning(f"[CourtDebate] 429 on stream ({self.provider}), attempting failover...")
                current_key = self._get_current_key()
                if self._failover_on_429(current_key):
                    logger.info(f"[CourtDebate] Stream failover → {self.provider}/{self._model}. Retrying...")
                    try:
                        stream = self._client.chat.completions.create(
                            model=self._model,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=max_tokens,
                            temperature=temperature,
                            stream=True,
                        )
                        for chunk in stream:
                            delta = chunk.choices[0].delta.content if chunk.choices else None
                            if delta:
                                yield delta
                        return
                    except Exception as retry_err:
                        yield f"[STREAM ERROR] Failover failed: {retry_err}"
                        return
            logger.error(f"[CourtDebate] Stream error ({self.provider}): {e}")
            yield f"[STREAM ERROR] {e}"


class LawGPTLLMClient:
    """Round-robin LLM router with cooldowns for bad or rate-limited keys."""

    _lock = threading.Lock()
    _clients: Dict[Tuple[str, str], Any] = {}
    _cooldowns: Dict[str, float] = {}
    _health: Dict[str, Dict[str, Any]] = {}
    _rr_index: int = 0
    _rr_by_group: Dict[str, int] = {}
    _last_candidates_sig: str = ""

    _PLACEHOLDER_MARKERS = (
        "__set_in_env__",
        "__set_in_azure_env__",
        "your_",
        "changeme",
        "replace_me",
        "none",
        "null",
    )

    def __init__(self):
        self.provider: str = "none"
        self._model: str = ""
        self._candidate_id: str = ""
        self._candidates = self._build_candidates()
        if self._candidates:
            logger.info(
                "[CourtDebate] LLM router loaded %s candidate key(s): %s",
                len(self._candidates),
                ", ".join(f"{c['provider']}:{c['name']}" for c in self._candidates),
            )
        else:
            logger.error("[CourtDebate] No usable LLM API keys found after filtering placeholders.")

    @classmethod
    def _is_real_key(cls, value: Optional[str]) -> bool:
        if not value:
            return False
        cleaned = str(value).strip().strip('"').strip("'")
        if len(cleaned) < 20:
            return False
        lower = cleaned.lower()
        return not any(marker in lower for marker in cls._PLACEHOLDER_MARKERS)

    @staticmethod
    def _mask_key(value: str) -> str:
        return f"{value[:6]}...{value[-4:]}" if len(value) > 12 else "***"

    @classmethod
    def _dedupe_append(cls, values: List[Tuple[str, str]], name: str, value: Optional[str]) -> None:
        if not cls._is_real_key(value):
            return
        cleaned = str(value).strip().strip('"').strip("'")
        if cleaned not in [v for _, v in values]:
            values.append((name, cleaned))

    def _collect_named_keys(self, provider_prefix: str, canonical_names: List[str]) -> List[Tuple[str, str]]:
        cfg = Config
        values: List[Tuple[str, str]] = []
        for name in canonical_names:
            self._dedupe_append(values, name, os.getenv(name))
            if cfg is not None:
                self._dedupe_append(values, name, getattr(cfg, name, None))

        env_pattern = re.compile(rf"^(?:{provider_prefix.upper()}_API_KEY(?:_\d+)?|{provider_prefix.lower()}_api(?:_\d+)?)$")
        for name in sorted(os.environ):
            if env_pattern.match(name):
                self._dedupe_append(values, name, os.getenv(name))
        return values

    def _build_candidates(self) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        cfg = Config
        tokenrouter_keys = self._collect_named_keys("tokenrouter", ["tokenrouter_api", "TOKENROUTER_API_KEY"])
        cerebras_keys = self._collect_named_keys("cerebras", ["cerebras_api", "CEREBRAS_API_KEY"])
        groq_keys = self._collect_named_keys(
            "groq",
            ["groq_api", "GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3", "GROQ_API_KEY_4", "GROQ_API_KEY_5"],
        )
        nvidia_keys = self._collect_named_keys("nvidia", ["nvidia_api", "NVIDIA_API_KEY", "nvidia_api_2", "NVIDIA_API_KEY_2"])
        openrouter_keys = self._collect_named_keys(
            "openrouter",
            [
                "openrouter_api", "OPENROUTER_API_KEY",
                "openrouter_api_2", "OPENROUTER_API_KEY_2",
                "openrouter_api_3", "OPENROUTER_API_KEY_3",
                "openrouter_api_4", "OPENROUTER_API_KEY_4",
            ],
        )

        glm_model = os.getenv("TOKENROUTER_MODEL", "z-ai/glm-5.3-free")
        for idx, (name, key) in enumerate(tokenrouter_keys, start=1):
            candidates.append({
                "id": f"tokenrouter:{idx}:{self._mask_key(key)}",
                "provider": "tokenrouter",
                "name": name,
                "key": key,
                "base_url": (cfg.TOKENROUTER_BASE_URL if cfg else os.getenv("TOKENROUTER_BASE_URL", "https://api.tokenrouter.com/v1")),
                "models": {
                    "fast": [glm_model],
                    "debate": [glm_model],
                },
            })
        for idx, (name, key) in enumerate(cerebras_keys, start=1):
            candidates.append({
                "id": f"cerebras:{idx}:{self._mask_key(key)}",
                "provider": "cerebras",
                "name": name,
                "key": key,
                "base_url": cfg.CEREBRAS_BASE_URL if cfg else "https://api.cerebras.ai/v1",
                "models": {
                    "fast": ["qwen-3-32b", "llama-3.3-70b"],
                    "debate": ["llama-3.3-70b", "qwen-3-32b", "deepseek-r1-distill-llama-70b"],
                },
            })
        for idx, (name, key) in enumerate(groq_keys, start=1):
            candidates.append({
                "id": f"groq:{idx}:{self._mask_key(key)}",
                "provider": "groq",
                "name": name,
                "key": key,
                "base_url": cfg.GROQ_BASE_URL if cfg else "https://api.groq.com/openai/v1",
                "models": {
                    "fast": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"],
                    "debate": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"],
                },
            })
        for idx, (name, key) in enumerate(nvidia_keys, start=1):
            candidates.append({
                "id": f"nvidia:{idx}:{self._mask_key(key)}",
                "provider": "nvidia",
                "name": name,
                "key": key,
                "base_url": cfg.NVIDIA_BASE_URL if cfg else "https://integrate.api.nvidia.com/v1",
                "models": {
                    "fast": ["meta/llama-3.1-8b-instruct", "meta/llama-3.1-70b-instruct"],
                    "debate": ["meta/llama-3.1-8b-instruct", "meta/llama-3.1-70b-instruct"],
                },
            })
        for idx, (name, key) in enumerate(openrouter_keys, start=1):
            candidates.append({
                "id": f"openrouter:{idx}:{self._mask_key(key)}",
                "provider": "openrouter",
                "name": name,
                "key": key,
                "base_url": cfg.OPENROUTER_BASE_URL if cfg else "https://openrouter.ai/api/v1",
                "models": {
                    "fast": [
                        "openai/gpt-oss-20b:free",
                        "openai/gpt-oss-120b:free",
                        "tencent/hy3-preview:free",
                        "nvidia/nemotron-3.5-lightning:free",
                        "z-ai/glm-5.2:free",
                        "minimax/minimax-m3:free",
                        "nvidia/nemotron-3-super-120b-a12b:free",
                    ],
                    "debate": [
                        "openai/gpt-oss-120b:free",
                        "nousresearch/hermes-3-llama-3.1-405b:free",
                        "z-ai/glm-5.2:free",
                        "nvidia/nemotron-3-ultra-550b-a55b:free",
                        "nvidia/nemotron-3-super-120b-a12b:free",
                        "minimax/minimax-m3:free",
                    ],
                },
            })

        sig = "|".join(c["id"] for c in candidates)
        with self._lock:
            if sig != self.__class__._last_candidates_sig:
                self.__class__._cooldowns.clear()
                self.__class__._health.clear()
                self.__class__._last_candidates_sig = sig
        return candidates

    @classmethod
    def _cooldown(cls, key: str, seconds: int, reason: str) -> None:
        with cls._lock:
            cls._cooldowns[key] = time.time() + seconds
            health = cls._health.setdefault(key, {})
            health["cooldown_until"] = cls._cooldowns[key]
            health["last_failure_reason"] = reason
        logger.warning("[CourtDebate] LLM candidate cooldown: %s for %ss (%s)", key, seconds, reason)

    @classmethod
    def _is_available(cls, key: str) -> bool:
        return cls._cooldowns.get(key, 0) <= time.time()

    @classmethod
    def _record_health(cls, key: str, event: str, reason: str = "") -> None:
        with cls._lock:
            health = cls._health.setdefault(
                key,
                {
                    "success_count": 0,
                    "empty_response_count": 0,
                    "timeout_count": 0,
                    "rate_limit_count": 0,
                    "error_count": 0,
                    "last_failure_reason": "",
                    "cooldown_until": 0,
                },
            )
            if event == "success":
                health["success_count"] = int(health.get("success_count", 0)) + 1
                return
            if event == "empty":
                health["empty_response_count"] = int(health.get("empty_response_count", 0)) + 1
            elif event == "timeout":
                health["timeout_count"] = int(health.get("timeout_count", 0)) + 1
            elif event == "rate_limited":
                health["rate_limit_count"] = int(health.get("rate_limit_count", 0)) + 1
            else:
                health["error_count"] = int(health.get("error_count", 0)) + 1
            health["last_failure_reason"] = reason[:180]
            health["cooldown_until"] = cls._cooldowns.get(key, 0)

    @classmethod
    def provider_health_snapshot(cls) -> Dict[str, Any]:
        now = time.time()
        with cls._lock:
            return {
                key: {
                    **value,
                    "cooldown_remaining_seconds": max(0, round(float(value.get("cooldown_until", 0)) - now, 1)),
                }
                for key, value in sorted(cls._health.items())
            }

    @classmethod
    def _client_for(cls, candidate: Dict[str, Any]):
        from openai import OpenAI

        cache_key = (candidate["provider"], candidate["key"])
        with cls._lock:
            client = cls._clients.get(cache_key)
            if client is None:
                timeout_seconds = float(os.getenv("COURT_DEBATE_LLM_TIMEOUT_SECONDS", "60"))
                if candidate["provider"] == "tokenrouter":
                    # GLM section reasoning: bound to 60s so the whole 8-section
                    # debate fits the F1 platform request window; timeouts
                    # cascade to the fallback pool instead of stalling.
                    timeout_seconds = max(timeout_seconds, 60.0)
                default_headers = None
                if candidate["provider"] == "openrouter":
                    default_headers = {
                        "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://lawgpt-backend2024.azurewebsites.net"),
                        "X-Title": os.getenv("OPENROUTER_APP_TITLE", "LAW-GPT Court Debate"),
                    }
                client = OpenAI(
                    api_key=candidate["key"],
                    base_url=candidate["base_url"],
                    timeout=timeout_seconds,
                    max_retries=0,  # 429s rotate to the next key instead of silently stalling minutes
                    default_headers=default_headers,
                )
                cls._clients[cache_key] = client
            return client

    @classmethod
    def _rotate_group(cls, key: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(candidates) <= 1:
            return candidates
        start = cls._rr_by_group.get(key, 0) % len(candidates)
        cls._rr_by_group[key] = start + 1
        return candidates[start:] + candidates[:start]

    def _ordered_candidates(self, purpose: str) -> List[Dict[str, Any]]:
        if not self._candidates:
            return []
        # GLM-5.3 (TokenRouter) is the debate brain: every Court Clash section
        # reasons with full GLM depth first (user directive). Groq is the
        # emergency fallback when GLM rate-limits; OpenRouter free pool after.
        provider_priority = {"groq": 0, "tokenrouter": 1, "openrouter": 2, "nvidia": 3, "cerebras": 4}
        ordered: List[Dict[str, Any]] = []
        with self._lock:
            for provider, _priority in sorted(provider_priority.items(), key=lambda item: item[1]):
                group = [candidate for candidate in self._candidates if candidate["provider"] == provider]
                ordered.extend(self.__class__._rotate_group(f"{purpose}:{provider}", group))
            remaining = [
                candidate
                for candidate in self._candidates
                if candidate["provider"] not in provider_priority
            ]
            ordered.extend(self.__class__._rotate_group(f"{purpose}:other", remaining))
        return ordered

    @staticmethod
    def _purpose_for(max_tokens: int, purpose: Optional[str]) -> str:
        if purpose in ("fast", "debate"):
            return purpose
        return "fast" if max_tokens <= 1000 else "debate"

    @staticmethod
    def _error_category(exc: Exception) -> str:
        msg = str(exc).lower()
        if "401" in msg or "unauthorized" in msg or "invalid api key" in msg:
            return "unauthorized"
        if "429" in msg or "rate_limit" in msg or "rate limit" in msg:
            return "rate_limited"
        if "404" in msg or "not found" in msg:
            return "not_found"
        if "timed out" in msg or "timeout" in msg:
            return "timeout"
        return "error"

    def generate(
        self,
        prompt: str,
        max_tokens: int = 3000,
        temperature: float = 0.2,
        purpose: Optional[str] = None,
    ) -> str:
        if not self._candidates:
            return "[ERROR] No LLM provider configured."

        route_purpose = self._purpose_for(max_tokens, purpose)
        last_error = ""
        for candidate in self._ordered_candidates(route_purpose):
            candidate_id = candidate["id"]
            if not self._is_available(candidate_id):
                continue
            client = self._client_for(candidate)
            models = candidate["models"].get(route_purpose) or candidate["models"]["debate"]
            for model in models:
                model_key = f"{candidate_id}:{model}"
                if not self._is_available(model_key):
                    continue
                # GLM-5.3 reasons before answering and thinking cannot be
                # disabled; small budgets are consumed by the reasoning trace
                # and yield empty content. Raise tokenrouter calls to a
                # purpose-aware floor and cap reasoning effort on fast calls.
                request_max_tokens = max_tokens
                extra_params: Dict[str, Any] = {}
                if candidate["provider"] == "tokenrouter":
                    if route_purpose == "debate":
                        # Deep-thinking section: real headroom for the reasoning
                        # trace, effort medium keeps each section inside the
                        # client timeout (full "high" thinking ran minutes per
                        # section and starved the whole debate stream).
                        request_max_tokens = max(max_tokens, 6144)
                        extra_params["reasoning_effort"] = os.getenv(
                            "COURT_DEBATE_GLM_EFFORT", "medium"
                        )
                    else:
                        # Reasoning length is highly variable; 4096 always
                        # leaves room for the answer (max_tokens is only a cap).
                        request_max_tokens = max(max_tokens, 4096)
                        extra_params["reasoning_effort"] = os.getenv("TOKENROUTER_REASONING_EFFORT", "low")
                elif candidate["provider"] == "groq":
                    request_max_tokens = max(max_tokens, 6144)
                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=request_max_tokens,
                        temperature=temperature,
                        **extra_params,
                    )
                    self.provider = candidate["provider"]
                    self._model = model
                    self._candidate_id = candidate_id
                    logger.info("[CourtDebate] LLM route: %s/%s purpose=%s", candidate["provider"], model, route_purpose)
                    content = (resp.choices[0].message.content or "").strip()
                    if not content:
                        raise ValueError("empty LLM response")
                    self._record_health(model_key, "success")
                    return content
                except Exception as exc:  # noqa: BLE001
                    category = self._error_category(exc)
                    last_error = str(exc)
                    if "empty llm response" in last_error.lower():
                        self._record_health(model_key, "empty", "empty LLM response")
                        self._cooldown(model_key, 10 * 60, "empty response")
                        continue
                    if category == "unauthorized":
                        self._record_health(candidate_id, "error", "unauthorized")
                        self._cooldown(candidate_id, 24 * 60 * 60, "unauthorized")
                        break
                    if category == "rate_limited":
                        self._record_health(model_key, "rate_limited", "rate limited")
                        self._cooldown(model_key, 30 * 60, "rate limited")
                        continue
                    if category == "not_found":
                        self._record_health(model_key, "error", "model not found")
                        self._cooldown(model_key, 24 * 60 * 60, "model not found")
                        continue
                    if category == "timeout":
                        self._record_health(model_key, "timeout", "timeout")
                        self._cooldown(model_key, 10 * 60, "timeout")
                        continue
                    logger.warning("[CourtDebate] LLM call failed on %s/%s: %s", candidate["provider"], model, exc)
                    self._record_health(model_key, "error", category)
                    self._cooldown(model_key, 60, "provider error")
                    continue

        logger.error("[CourtDebate] All LLM routes failed. Last error: %s", last_error)
        return f"[LLM ERROR] All configured LLM routes failed or are cooling down. Last error: {last_error}"

    def stream(self, prompt: str, max_tokens: int = 3000, temperature: float = 0.2) -> Generator[str, None, None]:
        text = self.generate(prompt, max_tokens=max_tokens, temperature=temperature)
        yield text


# ===========================================================================
# ZILLIZ EVIDENCE RETRIEVER
# ===========================================================================

class ZillizEvidenceRetriever:
    """Pulls statutes + judgments from Zilliz Cloud for Level 4 evidence."""

    def __init__(self):
        self.main_store = None
        self.statute_store = None
        self._connect()

    def _connect(self):
        if not getattr(rag_config, "CLOUD_MODE_ENABLED", False):
            logger.warning("[CourtDebate] Zilliz disabled — evidence in knowledge-only mode.")
            return
        try:
            from rag_system.core.milvus_store import CloudMilvusStore
            self.main_store = CloudMilvusStore(
                endpoint=rag_config.ZILLIZ_CLUSTER_ENDPOINT,
                token=rag_config.ZILLIZ_TOKEN,
                collection_name=rag_config.ZILLIZ_COLLECTION_NAME,
            )
            statute_col = os.getenv("ZILLIZ_STATUTE_COLLECTION", "legal_rag_statutes")
            self.statute_store = CloudMilvusStore(
                endpoint=rag_config.ZILLIZ_CLUSTER_ENDPOINT,
                token=rag_config.ZILLIZ_TOKEN,
                collection_name=statute_col,
            )
            logger.info("[CourtDebate] Zilliz: Main + Statute collections ready.")
        except Exception as e:
            logger.error(f"[CourtDebate] Zilliz connect error: {e}")

    def retrieve(self, query: str, n: int = 5) -> List[Dict]:
        raw_results: List[Dict] = []
        if self.main_store and getattr(self.main_store, "is_connected", False):
            try:
                raw_results += self.main_store.hybrid_search(query, n_results=max(n * 3, 8))
            except Exception as e:
                logger.warning(f"[CourtDebate] Zilliz main search error: {e}")
        if self.statute_store and getattr(self.statute_store, "is_connected", False):
            try:
                raw_results += self.statute_store.hybrid_search(query, n_results=max(n * 3, 8))
            except Exception as e:
                logger.warning(f"[CourtDebate] Zilliz statute search error: {e}")

        # Local BM25 fallback via Laya System 1 fast gate
        if not raw_results or len(raw_results) < n:
            try:
                from kaanoon_test.system_adapters.vectorless_bm25_store import get_global_bm25_store
                from kaanoon_test.system_adapters.laya_triage_adapter import triage_query
                triage = triage_query(query)
                act_filter = triage.get("statute") if triage.get("is_supported_statute") else None
                sec_filter = triage.get("suggested_sections")
                bm25_store = get_global_bm25_store()
                if bm25_store:
                    bm25_hits = bm25_store.retrieve(
                        query=query,
                        top_k=max(n * 3, 8),
                        act_filter=act_filter,
                        section_filter=sec_filter,
                    )
                    for hit in bm25_hits:
                        meta = hit.get("metadata") or {}
                        raw_results.append({
                            "text": hit.get("text", ""),
                            "score": float(hit.get("score") or 1.0),
                            "metadata": {
                                **meta,
                                "title": meta.get("title") or meta.get("section_title") or meta.get("act") or hit.get("source", "Statutory Provision"),
                                "source": hit.get("source", "statute_chunks"),
                                "source_store": "local_bm25_statutes",
                                "authority_level": "statute",
                            },
                            "source": hit.get("source", "local_statute_bm25"),
                        })
            except Exception as e:
                logger.warning(f"[CourtDebate] Local BM25 fallback retrieval error: {e}")

        query_tokens = {tok for tok in re.findall(r"[a-z0-9]{4,}", query.lower())}
        deduped: Dict[str, Dict[str, Any]] = {}
        for item in raw_results:
            meta = item.get("metadata") or {}
            key = "|".join(
                [
                    str(meta.get("case_id", "")),
                    str(meta.get("title", "") or meta.get("section_number", "")),
                    str(meta.get("source", "")),
                    str(meta.get("year", "")),
                ]
            ).strip("|") or _slug((item.get("text") or "")[:80])
            existing = deduped.get(key)
            if existing is None or float(item.get("score") or 0) > float(existing.get("score") or 0):
                deduped[key] = item

        def weight(doc: Dict[str, Any]) -> float:
            meta = doc.get("metadata") or {}
            text = " ".join(
                [
                    str(meta.get("title", "")),
                    str(meta.get("source", "")),
                    str(meta.get("case_name", "")),
                    str(doc.get("text", ""))[:400],
                ]
            ).lower()
            overlap = len(query_tokens & {tok for tok in re.findall(r"[a-z0-9]{4,}", text)})
            court = str(meta.get("court", "")).lower()
            source_store = str(meta.get("source_store", "")).lower()
            authority_bonus = 0.0
            if "supreme" in court:
                authority_bonus += 4.0
            elif "high court" in court:
                authority_bonus += 2.0
            if "statute" in source_store or "act" in text[:120]:
                authority_bonus += 3.0
            if "sc_judgments_full" in str(meta.get("authority_level", "")).lower():
                authority_bonus += 3.0
            return float(doc.get("score") or 0) + overlap + authority_bonus

        ranked = sorted(deduped.values(), key=weight, reverse=True)
        return ranked[:n]

    def format_for_prompt(self, query: str, n: int = 5, domain: str = "") -> str:
        """Format evidence for prompt, optionally domain-filtered."""
        # If domain is known, augment query for better retrieval relevance
        augmented = query
        if domain and domain != "general":
            domain_boost = {
                "corporate": "Companies Act 2013 SEBI LODR director shareholder",
                "labour": "Industrial Disputes Act 1947 employee termination workmen",
                "constitutional": "Constitution Article 14 19 21 fundamental rights PIL",
                "environmental": "Environment Protection Act 1986 NGT hazardous waste pollution",
                "insolvency": "IBC 2016 CIRP NCLT resolution plan moratorium",
                "citizenship": "Citizenship Act 1955 OCI NRI passport immigration",
                "consumer": "Consumer Protection Act 2019 RERA unfair trade practice",
                "criminal": "IPC CrPC FIR cognizable offence bail",
            }
            boost = domain_boost.get(domain, "")
            if boost:
                augmented = f"{query} {boost}"
                logger.info(f"[CourtDebate] Domain-boosted query for '{domain}': +{len(boost)} chars")
        docs = self.retrieve(augmented, n=n)
        if not docs:
            return "(No evidence retrieved — proceeding with general Indian law knowledge.)"
        lines = ["### Authoritative Legal Evidence (Verified Statute & Precedent Store)\n"]
        for i, d in enumerate(docs, 1):
            meta = d.get("metadata") or {}
            title  = meta.get("title") or meta.get("section_title") or meta.get("act") or meta.get("source") or "Statutory Provision"
            sec = meta.get("section_number", "")
            if sec and sec not in title:
                title = f"{sec}: {title}"
            court  = meta.get("court", "")
            year   = meta.get("year", "")
            score  = d.get("score", "")
            text   = (d.get("text") or "")[:600]
            header_parts = [title]
            if court:
                header_parts.append(court)
            if year:
                header_parts.append(str(year))
            lines.append(
                f"**[{i}]** {' | '.join(header_parts)} | Score: {score}\n"
                f"```\n{text}\n```\n"
            )
        return "\n".join(lines)


# ===========================================================================
# LEGAL DOMAIN CLASSIFIER
# ===========================================================================

def classify_legal_domain(query: str) -> str:
    """Classify the legal domain of a query for smarter evidence retrieval.
    
    Returns one of: corporate, labour, constitutional, environmental,
    insolvency, citizenship, consumer, criminal, real_estate, or general.
    """
    domains = {
        "medical": [
            "medical negligence", "hospital", "surgeon", "surgery",
            "doctor", "patient", "bolam", "res ipsa loquitur",
            "clinical", "misdiagnosis", "anesthesia", "consent",
            "medical records", "treatment", "laparoscopic", "discharge summary",
        ],
        "corporate": [
            "director", "companies act", "related party", "sebi", "lodr",
            "board meeting", "agm", "egm", "shareholder", "dividend",
            "oppression", "mismanagement", "section 241", "section 242",
            "section 169", "minority stake", "audit committee",
        ],
        "labour": [
            "termination", "whistleblower", "industrial disputes",
            "employee", "employer", "retrenchment", "unfair labour",
            "section 25-f", "workmen", "standing orders", "gratuity",
            "provident fund", "esi", "wages", "sexual harassment",
        ],
        "constitutional": [
            "article 14", "article 19", "article 21", "pil",
            "fundamental rights", "writ petition", "constitutional",
            "dpdp", "data protection", "privacy", "right to life",
            "habeas corpus", "mandamus", "certiorari",
        ],
        "environmental": [
            "environment protection", "ngt", "hazardous waste",
            "pollution", "effluent", "green tribunal", "epa",
            "forest conservation", "wildlife", "buffer zone",
            "environmental clearance", "eia",
        ],
        "insolvency": [
            "ibc", "cirp", "nclt", "resolution plan", "moratorium",
            "insolvency", "liquidation", "nclat", "creditor",
            "corporate debtor", "committee of creditors", "sfio",
        ],
        "citizenship": [
            "oci", "citizenship act", "nri", "passport", "immigration",
            "foreigner", "visa", "deportation", "dual citizenship",
            "overseas citizen",
        ],
        "consumer": [
            "consumer protection", "rera", "flat buyer", "home buyer",
            "deficiency of service", "unfair trade", "consumer forum",
            "ncdrc", "real estate regulatory",
        ],
        "criminal": [
            "ipc", "crpc", "fir", "section 420", "cheating",
            "forgery", "criminal breach", "pmla", "money laundering",
            "ed investigation", "enforcement directorate",
        ],
        "real_estate": [
            "rera", "real estate", "flat buyer", "home buyer",
            "builder", "developer", "possession", "construction",
            "carpet area", "super built-up",
        ],
        "family_law": [
            "divorce", "custody", "maintenance", "alimony", "domestic violence",
            "live-in", "live in relationship", "shared household",
            "relationship in the nature of marriage", "personal law",
            "family court", "matrimonial", "cohabitation",
        ],
        "personal_relationships": [
            "interfaith", "inter-faith", "special marriage act", "love jihad",
            "adult choice of spouse", "choice of partner", "cohabitation",
            "married willingly", "family interference",
        ],
        "domestic_violence": [
            "domestic violence act", "shared household", "protection order",
            "residence order", "economic abuse", "domestic relationship",
        ],
        "maintenance": [
            "maintenance", "section 125", "section 144 bnss", "alimony",
            "monthly support", "financial support",
        ],
        "cohabitation": [
            "live-in", "live in relationship", "cohabitation",
            "relationship in the nature of marriage", "holding out", "shared household",
        ],
        "marriage_and_autonomy": [
            "special marriage act", "interfaith marriage", "adult autonomy",
            "choice of spouse", "habeas corpus", "family threat",
        ],
    }
    
    query_lower = query.lower()
    # Score each domain by keyword matches (multi-domain queries get best match)
    scores = {}
    for domain, keywords in domains.items():
        score = sum(1 for kw in keywords if kw in query_lower)
        if score > 0:
            scores[domain] = score

    if not scores:
        return "general"

    # Return highest scoring domain
    best = max(scores, key=scores.get)
    logger.info(f"[CourtDebate] Domain classified: {best} (score={scores[best]}, all={scores})")
    return best


_ISSUE_KEYWORDS: List[Tuple[str, List[str], str]] = [
    ("constitutional_privacy", ["article 21", "privacy", "fundamental rights", "constitutional"], "Constitutional privacy and proportionality"),
    ("data_protection", ["data protection", "dpdp", "consent", "data sharing", "personal data", "breach"], "Data protection, consent, and disclosure duties"),
    ("consumer_liability", ["consumer", "deficiency", "unfair trade", "service", "commission"], "Consumer protection liability and remedies"),
    ("contractual_fairness", ["arbitration", "terms", "privacy policy", "clause", "consent"], "Contractual fairness, consent, and standard terms"),
    ("public_law_maintainability", ["pil", "writ", "high court", "maintainable", "article 226"], "Maintainability of writ/PIL and public law review"),
    ("cybersecurity", ["breach", "hack", "cyber", "security", "phishing"], "Cybersecurity safeguards and negligence"),
    ("algorithmic_decision", ["algorithm", "credit scoring", "automated", "transparency"], "Algorithmic decision-making and explainability"),
    ("jurisdiction_procedure", ["jurisdiction", "arbitration", "forum", "maintainability", "limitation"], "Forum, jurisdiction, and procedural objections"),
]


def _clean_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    return slug or "authority"


@dataclass(frozen=True)
class CourtAuthoritySeed:
    id: str
    domain: str
    query_terms: Tuple[str, ...]
    display_name: str
    issue_triggers: Tuple[str, ...]


@dataclass(frozen=True)
class CourtScenarioFamily:
    key: str
    domain: str
    trigger_terms: Tuple[str, ...]
    issue_checklist: Tuple[Dict[str, str], ...]
    required_statutes: Tuple[str, ...]
    required_cases: Tuple[str, ...]
    forbidden_carryover_terms: Tuple[str, ...]
    retrieval_query_hints: Tuple[str, ...]
    forum_questions: Tuple[str, ...]


@dataclass(frozen=True)
class CardContract:
    section_id: str
    max_words: int
    timeout_seconds: float
    required_issue_coverage: bool = True
    deterministic_fallback: bool = True


COURT_AUTHORITY_SEEDS: Tuple[CourtAuthoritySeed, ...] = (
    CourtAuthoritySeed(
        "privacy_puttaswamy",
        "privacy / surveillance / Article 21",
        ("puttaswamy", "privacy", "surveillance", "article 21", "personal liberty"),
        "Justice K.S. Puttaswamy (Retd.) v. Union of India",
        ("privacy", "surveillance", "article 21", "autonomy", "personal liberty"),
    ),
    CourtAuthoritySeed(
        "adult_marriage_shafin_jahan",
        "adult marriage / habeas / autonomy",
        ("shafin jahan", "hadiya", "adult marriage", "habeas corpus", "choice of partner"),
        "Shafin Jahan v. Asokan K.M. / Hadiya line",
        ("interfaith", "marriage", "habeas", "adult", "choice", "autonomy"),
    ),
    CourtAuthoritySeed(
        "adult_choice_lata_singh",
        "adult choice / family opposition",
        ("lata singh", "adult marriage", "family opposition", "choice of partner"),
        "Lata Singh v. State of U.P.",
        ("interfaith", "marriage", "family", "adult", "choice"),
    ),
    CourtAuthoritySeed(
        "autonomy_laxmibai_chandaragi",
        "adult autonomy / police protection / family interference",
        ("laxmibai chandaragi", "choice of partner", "police protection", "family interference"),
        "Laxmibai Chandaragi B. v. State of Karnataka",
        ("interfaith", "marriage", "family", "protection", "autonomy", "choice"),
    ),
    CourtAuthoritySeed(
        "cohabitation_shambhu_kharwar",
        "adult relationship / state non-interference",
        ("shambhu kharwar", "adult relationship", "live-in", "state interference"),
        "Shambhu Kharwar v. State of Uttar Pradesh",
        ("adult", "relationship", "marriage", "autonomy", "state", "coercion"),
    ),
    CourtAuthoritySeed(
        "religion_bijoe_emmanuel",
        "religious expression / education",
        ("bijoe emmanuel", "freedom of conscience", "education", "religious expression"),
        "Bijoe Emmanuel v. State of Kerala",
        ("religion", "education", "school", "college", "expression", "conscience"),
    ),
    CourtAuthoritySeed(
        "religion_shirur_mutt",
        "Article 25 / essential religious practice",
        ("shirur mutt", "essential religious practice", "article 25"),
        "Commissioner, Hindu Religious Endowments v. Sri Lakshmindra Thirtha Swamiar (Shirur Mutt)",
        ("article 25", "essential", "religious practice", "religion"),
    ),
    CourtAuthoritySeed(
        "religion_sabarimala",
        "Article 25 / Article 14 / equality",
        ("sabarimala", "indian young lawyers", "article 25", "article 14", "equality"),
        "Indian Young Lawyers Association v. State of Kerala (Sabarimala)",
        ("article 25", "article 14", "equality", "religion", "essential"),
    ),
    CourtAuthoritySeed(
        "hijab_aishat_shifa_resham",
        "hijab / school uniform / split verdict",
        ("aishat shifa", "resham", "karnataka hijab", "school uniform", "hijab"),
        "Aishat Shifa / Resham hijab litigation",
        ("hijab", "uniform", "headscarf", "education", "religious identifiers"),
    ),
    CourtAuthoritySeed(
        "proportionality_modern_dental",
        "proportionality / Article 14",
        ("proportionality", "modern dental", "least restrictive", "manifest arbitrariness"),
        "Modern Dental College proportionality line",
        ("proportionality", "least restrictive", "article 14", "arbitrary", "restriction"),
    ),
    CourtAuthoritySeed(
        "criminal_process_lalita_kumari",
        "FIR / criminal process",
        ("lalita kumari", "fir", "section 154", "criminal process", "quashing"),
        "Lalita Kumari v. Government of Uttar Pradesh",
        ("fir", "criminal", "cheating", "conspiracy", "coercion", "conversion"),
    ),
)


COURT_SCENARIO_FAMILIES: Tuple[CourtScenarioFamily, ...] = (
    CourtScenarioFamily(
        key="interfaith_marriage_autonomy",
        domain="marriage_and_autonomy",
        trigger_terms=(
            "special marriage act", "love jihad", "interfaith", "inter-faith",
            "adult woman", "choice of spouse", "married willingly",
            "fears for her safety", "family files a police complaint",
        ),
        issue_checklist=(
            {"id": "constitutional_article21_autonomy", "bucket": "constitutional", "label": "Article 21 autonomy and adult choice of spouse", "question": "Whether the adult woman's autonomy, dignity, and choice of spouse under Article 21 should prevail absent concrete evidence of coercion."},
            {"id": "statutory_sma_conversion_second_marriage", "bucket": "statutory", "label": "Special Marriage Act validity, later conversion, and second marriage interaction", "question": "Whether the Special Marriage Act marriage remains valid after later conversion and what legal relevance, if any, a second personal-law ceremony has."},
            {"id": "statutory_forced_conversion_scrutiny", "bucket": "statutory", "label": "Forced conversion and state anti-conversion law scrutiny", "question": "Whether the conversion timing and surrounding pressure justify a lawful inquiry under the applicable state anti-conversion law without presuming invalid consent."},
            {"id": "criminal_kidnapping_confinement", "bucket": "procedural", "label": "Kidnapping, wrongful confinement, and police investigation limits", "question": "Whether criminal allegations justify detention or investigation when the adult woman appears before a court and denies illegal confinement."},
            {"id": "evidence_court_statement_vs_digital", "bucket": "evidence", "label": "Burden of proof and in-court statement versus WhatsApp and digital communications", "question": "Which party bears the burden to prove coercion, and what evidentiary weight should be given to the woman's magistrate statement compared with prior digital communications showing confusion or emotional pressure."},
            {"id": "procedural_habeas_parental_claim", "bucket": "procedural", "label": "Habeas corpus, parental concern, and psychological captivity claim", "question": "Whether habeas corpus remains maintainable where an adult appears in court and states she is acting voluntarily, despite parental claims of psychological captivity."},
            {"id": "regulatory_love_jihad_label", "bucket": "regulatory", "label": "Legal relevance of the 'love jihad' allegation", "question": "Whether the label 'love jihad' has any independent legal standing, or whether only provable coercion, fraud, unlawful confinement, or forced conversion can matter in law."},
            {"id": "constitutional_state_protection", "bucket": "constitutional", "label": "State duty, family threat, and media or political pressure", "question": "Whether the state must protect the adult woman's independent choice while conducting any lawful investigation without yielding to parental, media, or political pressure."},
        ),
        required_statutes=("Special Marriage Act, 1954", "Applicable state anti-conversion law", "Criminal procedure / habeas corpus framework"),
        required_cases=(
            "Shafin Jahan v. Asokan K.M. / Hadiya line",
            "Lata Singh v. State of U.P.",
            "Laxmibai Chandaragi B. v. State of Karnataka",
        ),
        forbidden_carryover_terms=("indra sarma", "velusamy", "chanmuniya", "domestic violence act"),
        retrieval_query_hints=("interfaith marriage", "adult autonomy", "special marriage act", "forced conversion", "habeas corpus", "digital evidence", "coercion proof", "police protection"),
        forum_questions=("criminal complaint", "habeas/protection", "magistrate statement", "family court", "annulment", "anti-conversion inquiry"),
    ),
    CourtScenarioFamily(
        key="live_in_relationship_maintenance",
        domain="family_law",
        trigger_terms=(
            "live-in", "live in relationship", "relationship in the nature of marriage",
            "domestic violence act", "domestic violence protection", "maintenance rights",
            "section 125", "section 144 bnss", "without marriage", "cohabitation", "shared household",
            "dv protection", "dv act", "maintenance", "lives together", "lived together",
            "domestic violence", "maintenance claim", "maintenance rights", "protection",
        ),
        issue_checklist=(
            {"id": "statutory_relationship_in_nature_of_marriage", "bucket": "statutory", "label": "Relationship in the nature of marriage", "question": "Whether the live-in relationship satisfies the Indian-law test for a relationship in the nature of marriage."},
            {"id": "statutory_dv_act_section_2f", "bucket": "statutory", "label": "Domestic relationship under the Protection of Women from Domestic Violence Act", "question": "Whether the claimant falls within the domestic relationship and shared household protections under the Protection of Women from Domestic Violence Act, 2005."},
            {"id": "statutory_maintenance_route", "bucket": "statutory", "label": "Maintenance route without formal marriage", "question": "Whether maintenance can be claimed despite the absence of formal marriage, and through which legal route."},
            {"id": "evidence_cohabitation_and_holding_out", "bucket": "evidence", "label": "Proof of cohabitation, holding out, and shared household", "question": "What facts must show duration, exclusivity, public representation, financial arrangements, and shared household for marriage-like recognition."},
            {"id": "procedural_forum_selection", "bucket": "procedural", "label": "Forum fit for DV protection and maintenance", "question": "How the court should separate or combine Domestic Violence Act relief, maintenance proceedings, and any other family-law route."},
            {"id": "regulatory_cultural_norms", "bucket": "regulatory", "label": "Cultural norms versus statutory recognition", "question": "Whether cultural disapproval should affect legal recognition where statutory protection and precedent recognize qualifying live-in relationships."},
        ),
        required_statutes=(
            "Protection of Women from Domestic Violence Act, 2005",
            "Section 2(f), Protection of Women from Domestic Violence Act, 2005",
        ),
        required_cases=(
            "Indra Sarma v. V.K.V. Sarma",
            "Velusamy v. D. Patchaiammal",
            "Chanmuniya v. Virendra Kumar Singh Kushwaha",
        ),
        forbidden_carryover_terms=("special marriage act", "love jihad", "hadiya", "choice of spouse", "article 21 adult woman"),
        retrieval_query_hints=("live in relationship", "relationship in the nature of marriage", "domestic violence act section 2(f)", "maintenance", "shared household"),
        forum_questions=("domestic violence act", "maintenance", "family court", "magistrate"),
    ),
)


# ===========================================================================
# PROMPT TEMPLATES
# ===========================================================================

_PHASE1 = """\
You are LawGPT's Query Router for Indian law.

Evaluate the complexity of this legal question on a scale of 1–10:
- Multiple conflicting legal interpretations
- High-stakes outcomes (financial, liberty, reputation)
- Complex interplay of Indian statutes + SC/HC precedents + policy
- Would benefit from adversarial reasoning (positive vs. negative)

Previous conversation context (if any):
{conversation_history}

User Question:
{user_query}

RULES:
- Score ≥ 8 → reply with EXACTLY this block (no extra text):

This legal question appears highly complex and involves multiple perspectives, competing arguments, and significant legal analysis.

Would you like me to activate **Court Debate Mode**?

In this mode I will:
- Simulate a full courtroom-style debate with multiple lawyer agents
- Present strong positive and negative arguments at multiple levels
- Weigh evidence, precedents, risks, and policy like senior lawyers do
- Deliver a final reasoned conclusion with transparent step-by-step reasoning

Reply **YES** to switch to Court Debate Mode, or continue with normal analysis.

- Score < 8 → give a direct helpful legal answer. Do NOT mention Court Debate Mode.
"""

_PHASE2 = """\
You are now in **Court Debate Mode v2** — LAW-GPT's highest-level analysis for Indian law.

### Core Rules
- Follow the 7-Level Deliberation Process exactly using the headings below.
- Cite Indian statutes: Companies Act 2013, Industrial Disputes Act 1947,
  Whistle Blowers Protection Act 2014, IPC, CrPC, Contract Act 1872, etc.
- Cite Supreme Court / High Court precedents where possible.
- Advocate A must build the STRONGEST possible case.
- Advocate B must be RUTHLESS and AGGRESSIVE in attacking Advocate A. Do NOT be polite.
- Show genuinely opposing arguments — NOT restated versions of each other.

### Legal Domain
{legal_domain}

### Agents
1. **Advocate A (Positive)** — strongest case for favourable outcome
2. **Advocate B (Negative)** — ruthless devil's advocate, destroys A's arguments
3. **Evidence Retriever** — cites Zilliz Cloud statutes + judgments
4. **Judge Agent** — neutral synthesis + final verdict

---
### Zilliz Cloud Evidence (for Level 4)
{zilliz_evidence}
---

### Previous Chat Context
{conversation_history}

### User Query
{user_query}

---
Begin now. Use EXACTLY these headings:

## Level 1: Issue Framing
## Level 2: Advocate A – Positive Case
## Level 3: Advocate B – Counter-Arguments
## Level 4: Evidence & Precedent Cross-Examination
## Level 5: Multi-Factor Judicial Weighing
## Level 6: Final Synthesis & Conclusion
## Level 7: Risks & Alternative Outcomes
## Level 8: Deep Analysis & Summarized Outcome

After Level 8, add this EXACTLY:

## Independent Evaluation (Scored by Judge Agent)
- Positive Advocate Strength: __/10
- Negative Advocate Strength (Aggressiveness & Quality): __/10
- True Balance Between Sides: __/10
- Quality of Final Conclusion & Strategy: __/10
- Evidence Integration: __/10
- Overall Production Usefulness: __/10

**Final Grade:** __/10
"""

_ADVOCATE_A = """\
You are Advocate A — senior corporate lawyer defending the company under Indian law.
Level: {level} | Query: {user_query}
Prior context: {previous_context}
Zilliz Evidence: {zilliz_evidence}

Build the STRONGEST positive case. Cite Companies Act 2013, Industrial Disputes Act 1947,
Contract Act 1872, and Supreme Court precedents. Be persuasive and accurate.
Output bullet-point arguments only.
"""

_ADVOCATE_B = """\
You are Advocate B — a highly aggressive, ruthless Devil's Advocate and opposing counsel.

Your job is to **destroy** Advocate A's arguments as much as possible.

Current Level: {level}
User Query: {user_query}
Legal Domain: {legal_domain}

Advocate A's Arguments (ATTACK THESE):
{advocate_a_output}

Zilliz Evidence: {zilliz_evidence}

Instructions:
- Be extremely critical and attack EVERY weak point in Advocate A's position
- Use Indian law, Supreme Court precedents, and procedural technicalities aggressively
- Highlight risks, contradictions, logical flaws, and missing considerations
- Point out where Advocate A has misapplied or cherry-picked statutes
- Challenge the burden of proof, limitation periods, and procedural bars
- Do NOT be polite or balanced — your role is to WIN for the opposing side
- If Advocate A cited a case, distinguish it or show why it does not apply

Output ONLY sharp, bullet-point counter-arguments. Minimum 10 strong points.
"""

_JUDGE = """\
You are the neutral Judge Agent for Indian law.
User Query: {user_query}
Legal Domain: {legal_domain}
Full Debate:
{full_debate_summary}

Deliver the final verdict in EXACTLY this format:

## Level 5: Multi-Factor Judicial Weighing
- Legal Strength: X/10 — (reason)
- Factual Support: X/10 — (reason)
- Client Risk: X/10 — (reason)
- Policy Alignment: X/10 — (reason)
- Ethics: X/10 — (reason)

## Level 6: Final Synthesis & Conclusion
**Final Recommendation**: [clear strategic advice]
**Confidence Score**: X%
**Key Reasoning**:
- Point 1
- Point 2
- Point 3

## Level 7: Risks & Alternative Outcomes
- Major Risk 1: ...
- Major Risk 2: ...
- Alternative scenario: ...

## Independent Evaluation (Scored by Judge Agent)
- Positive Advocate Strength: X/10
- Negative Advocate Strength (Aggressiveness & Quality): X/10
- True Balance Between Sides: X/10
- Quality of Final Conclusion & Strategy: X/10
- Evidence Integration: X/10
- Overall Production Usefulness: X/10

**Final Grade:** X/10
"""

# Streaming phase prompts — each level as a separate prompt
_STREAM_LEVELS = [
    ("## Level 1: Issue Framing",
     "You are a senior Indian legal analyst.\n"
     "Query: {user_query}\nContext: {conversation_history}\n"
     "Write ONLY Level 1 Issue Framing: break this into clear legal sub-issues "
     "under Indian law (Companies Act 2013, Industrial Disputes Act 1947, etc.). "
     "Use bullet points. 150 words max."),

    ("## Level 2: Advocate A – Positive Case",
     "You are Advocate A (senior corporate counsel, Indian law).\n"
     "Query: {user_query}\nZilliz: {zilliz_evidence}\n"
     "Write ONLY the strongest positive arguments for the company. "
     "Cite relevant Indian statutes and SC precedents. Bullet points, 200 words max."),

    ("## Level 3: Advocate B – Counter-Arguments",
     "You are Advocate B — a highly aggressive, ruthless Devil's Advocate.\n"
     "Your job is to DESTROY the positive case. Be extremely critical.\n"
     "Query: {user_query}\nZilliz: {zilliz_evidence}\n"
     "Attack every weak point using Indian law, SC precedents, and procedural technicalities. "
     "Do NOT be polite. Highlight risks, contradictions, and flaws. "
     "Bullet points, minimum 8 counter-arguments. 250 words max."),

    ("## Level 4: Evidence & Precedent Cross-Examination",
     "You are the Evidence Retriever.\n"
     "Query: {user_query}\nZilliz Evidence: {zilliz_evidence}\n"
     "Write ONLY the most relevant Indian statutes, Supreme Court cases, and HC judgments "
     "that apply here. Format: Act/Case → brief impact. 200 words max."),

    ("## Level 5: Multi-Factor Judicial Weighing",
     "You are the Judge Agent.\n"
     "Query: {user_query}\n"
     "Score each factor X/10 with a brief reason:\n"
     "- Legal Strength\n- Factual Support\n- Client Risk\n- Policy Alignment\n- Ethics\n"
     "100 words max."),

    ("## Level 6: Final Synthesis & Conclusion",
     "You are the Judge Agent delivering the final verdict.\n"
     "Query: {user_query}\n"
     "Write: Final Recommendation, Confidence Score (%), and 3 Key Reasoning points. "
     "150 words max."),

    ("## Level 7: Risks & Alternative Outcomes",
     "You are the Judge Agent.\n"
     "Query: {user_query}\n"
     "Write 2 major risks and 1 alternative scenario if key assumptions change. "
     "100 words max."),

    ("## Level 8: Deep Analysis & Summarized Outcome",
     "You are the Lead Strategist.\n"
     "Query: {user_query}\n"
     "Provide a deep analysis of the entire debate, culminating in a highly actionable, executive-level summarized outcome. Outline the absolute best path forward for the user. "
     "150 words max."),

    ("## Independent Evaluation (Scored by Judge Agent)",
     "You are an independent evaluator scoring this debate objectively.\n"
     "Query: {user_query}\n"
     "Score each dimension X/10 with NO self-bias:\n"
     "- Positive Advocate Strength\n- Negative Advocate Strength (Aggressiveness & Quality)\n"
     "- True Balance Between Sides\n- Quality of Final Conclusion & Strategy\n"
     "- Evidence Integration\n- Overall Production Usefulness\n"
     "End with: **Final Grade:** X/10\n"
     "80 words max."),
]


# ===========================================================================
# MAIN ENGINE
# ===========================================================================

class CourtDebateEngine:
    """
    Full Court Debate Mode pipeline.

    Quick start:
        engine = CourtDebateEngine()
        result = engine.run(user_query, session_id="abc123")
    """

    def __init__(self):
        self.llm = LawGPTLLMClient()
        self._retriever: Optional[ZillizEvidenceRetriever] = None

    @property
    def retriever(self) -> ZillizEvidenceRetriever:
        if self._retriever is None:
            self._retriever = ZillizEvidenceRetriever()
        return self._retriever

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------
    def _load_history(self, session_id: Optional[str], provided_history: str) -> str:
        """Return conversation history: prefer provided, else load from ShortTermMemory."""
        if provided_history.strip():
            return provided_history.strip()
        if not session_id:
            return ""
        stm = _get_stm()
        if stm is None:
            return ""
        ctx = stm.get_context(session_id, last_n=5)
        if ctx:
            logger.info(f"[CourtDebate] Loaded {len(ctx)} chars of history from STM ({session_id[:12]})")
        return ctx

    def _save_to_memory(self, session_id: Optional[str], query: str, debate_text: str):
        """Persist the debate turn into ShortTermMemory for future context."""
        if not session_id:
            return
        stm = _get_stm()
        if stm is None:
            return
        try:
            stm.add(session_id, "user", query, {"source": "court_debate"})
            summary = debate_text[:800] + ("..." if len(debate_text) > 800 else "")
            stm.add(session_id, "assistant", summary, {"source": "court_debate_response"})
            logger.info(f"[CourtDebate] Saved debate turn to STM ({session_id[:12]})")
        except Exception as e:
            logger.warning(f"[CourtDebate] STM save failed: {e}")

    # ------------------------------------------------------------------
    # Phase 1 — complexity gate
    # ------------------------------------------------------------------
    def check_complexity(self, user_query: str, session_id: Optional[str] = None,
                         history: str = "") -> Dict:
        conv_history = self._load_history(session_id, history)
        prompt = _PHASE1.format(user_query=user_query, conversation_history=conv_history or "None")
        response = self.llm.generate(prompt, max_tokens=500, temperature=0.1, purpose="fast")
        return {
            "is_complex": "Court Debate Mode" in response,
            "response": response,
            "history_used": bool(conv_history),
        }

    # ------------------------------------------------------------------
    # Phase 2 — integrated 7-level debate (1 LLM call, fast)
    # ------------------------------------------------------------------
    def run_debate_integrated(self, user_query: str, session_id: Optional[str] = None,
                              history: str = "", max_tokens: int = 2600) -> str:
        conv_history = self._load_history(session_id, history)
        domain = classify_legal_domain(user_query)
        evidence = self.retriever.format_for_prompt(user_query, domain=domain)
        prompt = _PHASE2.format(
            user_query=user_query,
            conversation_history=conv_history or "None",
            zilliz_evidence=evidence,
            legal_domain=f"Classified Domain: **{domain.upper()}**",
        )
        result = self.llm.generate(prompt, max_tokens=max_tokens, temperature=0.2, purpose="debate")
        self._save_to_memory(session_id, user_query, result)
        return result

    # ------------------------------------------------------------------
    # Phase 3 — modular 3-agent debate (3 LLM calls, highest quality)
    # ------------------------------------------------------------------
    def run_debate_modular(self, user_query: str, session_id: Optional[str] = None,
                           history: str = "") -> Dict:
        conv_history = self._load_history(session_id, history)
        domain = classify_legal_domain(user_query)
        evidence = self.retriever.format_for_prompt(user_query, domain=domain)
        domain_label = f"Classified Domain: **{domain.upper()}**"

        logger.info(f"[CourtDebate] Domain: {domain} | Dispatching Advocate A & B in parallel ...")
        prompt_a = _ADVOCATE_A.format(
            level="2",
            user_query=user_query,
            previous_context=conv_history or "None",
            zilliz_evidence=evidence,
        )
        prompt_b = _ADVOCATE_B.format(
            level="3",
            user_query=user_query,
            advocate_a_output="(Concurrent adversarial submissions on claimant positions)",
            legal_domain=domain_label,
            zilliz_evidence=evidence,
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut_a = executor.submit(self.llm.generate, prompt_a, 1400)
            fut_b = executor.submit(self.llm.generate, prompt_b, 1800)
            a_out = fut_a.result()
            b_out = fut_b.result()

        debate_summary = (
            f"### Legal Domain: {domain.upper()}\n\n"
            f"### Level 1: Issue Framing\n(See integrated output)\n\n"
            f"### Level 2–3: Advocate A\n{a_out}\n\n"
            f"### Level 3: Advocate B (Aggressive Counter)\n{b_out}\n\n"
            f"### Level 4: Zilliz Evidence\n{evidence}"
        )

        logger.info("[CourtDebate] Judge Agent + Independent Evaluation ...")
        judge_out = self.llm.generate(
            _JUDGE.format(user_query=user_query,
                          legal_domain=domain_label,
                          full_debate_summary=debate_summary),
            max_tokens=2000,
        )

        full_text = f"{debate_summary}\n\n{judge_out}"
        self._save_to_memory(session_id, user_query, full_text)

        return {
            "level_2_advocate_a": a_out,
            "level_3_advocate_b": b_out,
            "level_4_evidence": evidence,
            "level_5_7_judge": judge_out,
            "legal_domain": domain,
        }

    # ------------------------------------------------------------------
    # Streaming — yields Level 1→7 as SSE-ready JSON chunks
    # ------------------------------------------------------------------
    def stream_debate(
        self,
        user_query: str,
        session_id: Optional[str] = None,
        history: str = "",
    ) -> Generator[str, None, None]:
        """
        Sync generator. Yields newline-delimited JSON strings suitable for
        Server-Sent Events (SSE). Each chunk:
            {"level": "Level N: Title", "chunk": "...text..."}
        Final chunk:
            {"level": "done", "chunk": ""}
        """
        conv_history = self._load_history(session_id, history)
        domain = classify_legal_domain(user_query)
        full_output_parts: List[str] = []

        for heading, prompt_tpl in _STREAM_LEVELS:
            # Connect RAG as required per layer
            evidence = ""
            if "{zilliz_evidence}" in prompt_tpl:
                search_query = user_query
                if "Advocate A" in heading:
                    search_query += " defense positive legal grounds exceptions"
                elif "Advocate B" in heading:
                    search_query += " liability penalties opposing violations"
                elif "Evidence" in heading:
                    search_query += " statutes judgments precedent"
                
                evidence = self.retriever.format_for_prompt(search_query, n=3, domain=domain)
                
            prompt = prompt_tpl.format(
                user_query=user_query,
                conversation_history=conv_history or "None",
                zilliz_evidence=evidence,
            )
            # Emit the heading marker
            yield json.dumps({"level": heading, "chunk": f"\n{heading}\n"}) + "\n"

            level_text_parts: List[str] = []
            for chunk in self.llm.stream(prompt, max_tokens=600, temperature=0.2):
                level_text_parts.append(chunk)
                yield json.dumps({"level": heading, "chunk": chunk}) + "\n"

            full_output_parts.append(heading + "\n" + "".join(level_text_parts))

        yield json.dumps({"level": "done", "chunk": ""}) + "\n"

        # Save memory after the client-visible completion marker. A slow memory
        # backend must not leave the UI waiting after the debate has rendered.
        try:
            self._save_to_memory(session_id, user_query, "\n\n".join(full_output_parts))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[CourtDebate] Memory save skipped after stream completion: {exc}")

    async def astream_debate(
        self,
        user_query: str,
        session_id: Optional[str] = None,
        history: str = "",
    ) -> AsyncGenerator[str, None]:
        """Async wrapper around stream_debate for FastAPI StreamingResponse."""
        loop = asyncio.get_event_loop()
        gen = self.stream_debate(user_query, session_id, history)
        while True:
            try:
                chunk = await loop.run_in_executor(None, next, gen)
                yield chunk
            except StopIteration:
                break

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def run(
        self,
        user_query: str,
        conversation_history: str = "",
        modular: bool = False,
        session_id: Optional[str] = None,
        force_debate: bool = False,
    ) -> Dict:
        """
        Full pipeline: Phase 1 check → (if complex) Phase 2 or 3 debate.

        Returns dict with keys:
            mode, phase1_response, debate_output, zilliz_used, provider,
            indian_law_focus, memory_used
        """
        phase1 = (
            {"is_complex": True, "response": "Court Debate Mode forced by endpoint.", "history_used": bool(conversation_history)}
            if force_debate
            else self.check_complexity(user_query, session_id, conversation_history)
        )

        if not phase1["is_complex"]:
            return {
                "mode": "normal",
                "phase1_response": phase1["response"],
                "debate_output": None,
                "zilliz_used": False,
                "provider": self.llm.provider,
                "memory_used": phase1["history_used"],
            }

        logger.info(f"[CourtDebate] {'Modular' if modular else 'Integrated'} debate starting ...")

        if modular:
            debate_output = self.run_debate_modular(user_query, session_id, conversation_history)
        else:
            debate_output = self.run_debate_integrated(user_query, session_id, conversation_history)

        # Extract domain from modular output if available
        legal_domain = "general"
        if isinstance(debate_output, dict) and "legal_domain" in debate_output:
            legal_domain = debate_output["legal_domain"]

        return {
            "mode": "court_debate",
            "phase1_response": phase1["response"],
            "debate_output": debate_output,
            "legal_domain": legal_domain,
            "indian_law_focus": (
                "Companies Act 2013 | Industrial Disputes Act 1947 | "
                "Whistle Blowers Protection Act 2014 | SC/HC precedents"
            ),
            "zilliz_used": True,
            "provider": self.llm.provider,
            "memory_used": phase1["history_used"],
        }


# ===========================================================================
# Public helper — called from advanced_rag_api_server.py
# ===========================================================================
_COURT_REASONING_LEAK_RE = re.compile(
    r"^\s*(?:here'?s a thinking process|let me (?:plan|analyze|analyse|think|work)|okay,? (?:the user|I need|so the user)|I need to (?:be|output|produce|deconstruct)|first,? (?:I|let me))",
    re.I,
)

def _looks_like_reasoning_leak(text: str) -> bool:
    """Detect GLM chain-of-thought leaking into the section body instead of the answer."""
    head = (text or "").strip()[:400]
    if not head:
        return False
    if _COURT_REASONING_LEAK_RE.match(head):
        return True
    low = head.lower()
    if "thinking process" in low and ("user" in low or "output" in low or "section" in low):
        return True
    return False

_COURT_KEYPOINT_LINE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+")

def _extract_key_points(body: str, limit: int = 6) -> List[str]:
    """Distill a section's prose into 3-6 crisp key points for the debate UI."""
    src = str(body or "").replace("\r", "")
    if not src.strip():
        return []
    bullets = []
    for line in src.splitlines():
        if _COURT_KEYPOINT_LINE.match(line):
            clean = _COURT_KEYPOINT_LINE.sub("", line).strip()
            clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean)
            clean = re.sub(r"\s+", " ", clean)
            meta_markers = (
                "follows the locked issue blueprint", "prepared for the bench",
                "below is the", "scenario family", "required by the court",
                "this fallback is used", "quick-look table",
            )
            if any(m in clean.lower() for m in meta_markers):
                continue
            if len(clean) > 14:
                bullets.append(clean[:240])
    if len(bullets) >= 3:
        return bullets[:limit]
    flat = re.sub(r"#+\s*", "", src)
    flat = re.sub(r"\*\*([^*]+)\*\*", r"\1", flat)
    flat = re.sub(r"\s+", " ", flat).strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", flat) if len(s.strip()) > 45]
    return [s[:240] for s in sentences[:limit]]


_COURT_THOUGHT_STANCE = {
    "l2": "I press the elements that must be proved and keep the burden on their side of the table.",
    "l3": "I hold the procedural line and make them point to a concrete statutory violation before the bench.",
    "l4": "I keep every authority honest - unverified citations are leads, not anchors.",
    "l5": "I test the missing element each side hopes the bench overlooks.",
    "l6": "I weigh liberty against proof quality and keep the remedy as narrow as the record allows.",
    "l7": "I tie the likely outcome to the strongest authority actually on record.",
    "l8": "I flag exactly what must be verified before anyone relies on this advice.",
}

def _build_section_thought(section_id: str, role: str, body: str, key_points: List[str]) -> str:
    """Short hidden internal-strategy note for the lawyer card."""
    stance = _COURT_THOUGHT_STANCE.get(section_id, "I keep my case tied to provable elements.")
    lead = (key_points[0] if key_points else "").strip()
    if not lead:
        lead = re.sub(r"\s+", " ", str(body or "").strip())[:200]
    opener = "My strongest ground" if section_id in ("l2", "l3") else "My focus"
    return f"Hidden note: {opener} - {lead} {stance}"




_DOMAIN_AUTHORITY_SEEDS = {
    "medical": [
        {"kind": "case", "name": "Indian Medical Association v. V.P. Shantha (1995) 6 SCC 651", "issue": "medical services as 'service' under consumer law", "expectation": "retrieved_or_explicit_gap"},
        {"kind": "case", "name": "Jacob Mathew v. State of Punjab (2005) 6 SCC 1", "issue": "Bolam standard for criminal medical negligence", "expectation": "retrieved_or_explicit_gap"},
        {"kind": "case", "name": "Achutrao Haribhau Khodwa v. State of Maharashtra (1996) 2 SCC 634", "issue": "res ipsa loquitur and vicarious liability for retained foreign objects", "expectation": "retrieved_or_explicit_gap"},
        {"kind": "case", "name": "V. Kishan Rao v. Nikhil Super Speciality Hospital (2010) 5 SCC 513", "issue": "expert evidence not always required in medical negligence", "expectation": "retrieved_or_explicit_gap"},
        {"kind": "statute", "name": "Bharatiya Nyaya Sanhita, 2023 (Section 106(1) proviso)", "issue": "reduced punishment for registered medical practitioners", "expectation": "retrieved_or_explicit_gap"},
        {"kind": "statute", "name": "Consumer Protection Act, 2019 (Sections 35, 38, 39)", "issue": "complaint forum, pecuniary jurisdiction and compensation", "expectation": "retrieved_or_explicit_gap"},
    ],
    "consumer": [
        {"kind": "case", "name": "Indian Medical Association v. V.P. Shantha (1995) 6 SCC 651", "issue": "medical services as 'service' under consumer law", "expectation": "retrieved_or_explicit_gap"},
        {"kind": "case", "name": "Jacob Mathew v. State of Punjab (2005) 6 SCC 1", "issue": "Bolam standard for criminal medical negligence", "expectation": "retrieved_or_explicit_gap"},
        {"kind": "case", "name": "Achutrao Haribhau Khodwa v. State of Maharashtra (1996) 2 SCC 634", "issue": "res ipsa loquitur and vicarious liability for retained foreign objects", "expectation": "retrieved_or_explicit_gap"},
        {"kind": "statute", "name": "Consumer Protection Act, 2019 (Sections 35, 38, 39)", "issue": "complaint forum, pecuniary jurisdiction and compensation", "expectation": "retrieved_or_explicit_gap"},
    ],
    "labour": [
        {"kind": "statute", "name": "Industrial Disputes Act, 1947 (Section 25-F)", "issue": "retrenchment conditions for workmen", "expectation": "retrieved_or_explicit_gap"},
        {"kind": "case", "name": "Workmen v. American Express Bank (1985) 4 SCC 71", "issue": "managerial vs workman status", "expectation": "retrieved_or_explicit_gap"},
        {"kind": "case", "name": "Binny Ltd v. Sadasivan (2005) 6 SCC 657", "issue": "writ maintainability against private employers", "expectation": "retrieved_or_explicit_gap"},
    ],
    "criminal": [
        {"kind": "statute", "name": "Bharatiya Nyaya Sanhita, 2023", "issue": "offence ingredients and punishment", "expectation": "retrieved_or_explicit_gap"},
        {"kind": "case", "name": "Arnesh Kumar v. State of Bihar (2014) 8 SCC 273", "issue": "arrest safeguards for offences under 7 years", "expectation": "retrieved_or_explicit_gap"},
        {"kind": "case", "name": "Lalita Kumari v. Government of Uttar Pradesh (2014) 2 SCC 1", "issue": "FIR registration for cognizable offences", "expectation": "retrieved_or_explicit_gap"},
    ],
    "family": [
        {"kind": "statute", "name": "Hindu Marriage Act, 1955 (Section 13)", "issue": "divorce grounds", "expectation": "retrieved_or_explicit_gap"},
        {"kind": "case", "name": "Githa Hariharan v. Reserve Bank of India (1999) 2 SCC 228", "issue": "guardianship and welfare of the child", "expectation": "retrieved_or_explicit_gap"},
    ],
    "property": [
        {"kind": "statute", "name": "Real Estate (Regulation and Development) Act, 2016 (Sections 18, 31)", "issue": "allottee refund, interest and complaint", "expectation": "retrieved_or_explicit_gap"},
        {"kind": "statute", "name": "Transfer of Property Act, 1882 (Section 54)", "issue": "sale of immovable property", "expectation": "retrieved_or_explicit_gap"},
    ],
}


class CourtDebateEngineV2(CourtDebateEngine):
    """Evidence-first court debate engine with issue decomposition and quality gates."""

    _authority_resolver: Optional[AuthorityResolver] = None

    @property
    def authority_resolver(self) -> AuthorityResolver:
        if self.__class__._authority_resolver is None:
            self.__class__._authority_resolver = AuthorityResolver()
        return self.__class__._authority_resolver

    def _infer_sides(self, user_query: str) -> Tuple[str, str]:
        q = (user_query or "").lower()
        family = self._scenario_family(user_query)
        if family and family.key == "interfaith_marriage_autonomy":
            return (
                "Family / complainant side seeking proof-based coercion inquiry or protective forum control",
                "Adult woman and spouse defending autonomy, Special Marriage Act validity, and state protection",
            )
        if family and family.key == "live_in_relationship_maintenance":
            return (
                "Woman claimant seeking marriage-like recognition, maintenance route, and Domestic Violence Act protection",
                "Man respondent denying formal marriage and contesting proof, automatic obligations, and remedy scope",
            )
        if "best options for the company" in q or "strategy for the company" in q or "company wants to" in q:
            return (
                "Company / respondent / defending party",
                "Employee / complainant / petitioner / challenger",
            )
        if any(term in q for term in ("pil", "consumer commission", "violate", "breach", "deficiency", "unfair trade")):
            return (
                "Users / consumers / petitioners / challengers",
                "Company / respondent / defending party",
            )
        return (
            "Claimant / challenger / petitioner side",
            "Respondent / defence side",
        )

    def _complexity_signal(self, user_query: str) -> int:
        q = (user_query or "").lower()
        score = 0
        score += min(4, len(user_query.split()) // 80)
        for marker in (
            "article", "constitution", "pil", "habeas", "fir", "criminal",
            "interfaith", "religion", "privacy", "public order", "fundamental rights",
            "multiple", "high court", "special marriage act",
        ):
            if marker in q:
                score += 1
        return score

    def _should_run_elite(self, user_query: str, elite: bool = False, quality_target: Optional[str] = None) -> bool:
        if elite:
            return True
        if str(quality_target or "").strip().lower() in {"court_85", "elite", "human_level"}:
            return True
        return self._complexity_signal(user_query) >= 9

    def _matched_authority_seeds(self, user_query: str, issues: List[Dict[str, str]]) -> List[CourtAuthoritySeed]:
        haystack = " ".join(
            [user_query]
            + [issue.get("label", "") + " " + issue.get("question", "") for issue in issues]
        ).lower()
        matched: List[CourtAuthoritySeed] = []
        for seed in COURT_AUTHORITY_SEEDS:
            if any(trigger in haystack for trigger in seed.issue_triggers):
                matched.append(seed)
        return matched

    def _seed_authority_rows(self, user_query: str, issues: List[Dict[str, str]]) -> Tuple[List[Dict[str, Any]], str]:
        rows: List[Dict[str, Any]] = []
        retrieve_seeds = os.getenv("COURT_DEBATE_ELITE_SEED_RETRIEVAL", "true").strip().lower() in {
            "1", "true", "yes", "on"
        }
        resolver = self.authority_resolver
        for seed in self._matched_authority_seeds(user_query, issues):
            query = f"{user_query} {' '.join(seed.query_terms)}"
            docs = []
            if retrieve_seeds:
                try:
                    docs = self.retriever.retrieve(query, n=1)
                except Exception as exc:
                    logger.warning(f"[CourtDebateElite] Seed retrieval failed for {seed.id}: {exc}")
            best_doc = docs[0] if docs else {}
            if best_doc:
                _hay = " ".join([
                    str(best_doc.get("text") or ""),
                    str((best_doc.get("metadata") or {}).get("title") or ""),
                    str((best_doc.get("metadata") or {}).get("case_name") or ""),
                ]).lower()
                _name_key = (seed.query_terms[0] if seed.query_terms else seed.display_name).lower()
                if _name_key not in _hay:
                    # Retrieved text does not actually name this authority — not real support.
                    best_doc = {}
            meta = best_doc.get("metadata") or {}

            # Check canonical authority pack resolver for verified citation
            canonical_rec = None
            if resolver:
                for rec in resolver.records:
                    if rec.authority_id == seed.id or seed.id in rec.authority_id or any(alias in seed.display_name.lower() for alias in rec.aliases):
                        canonical_rec = rec
                        break

            if best_doc:
                support_text = _truncate(best_doc.get("text") or "", 360)
                status = "retrieved"
                title = meta.get("title") or meta.get("case_name") or seed.display_name
                court = meta.get("court", "")
                year = str(meta.get("year", ""))
                source = meta.get("source") or best_doc.get("source", "")
                source_store = meta.get("source_store", "retrieved_statutes")
                source_tier = meta.get("source_tier", "primary_precedent")
            elif canonical_rec:
                support_text = _truncate(f"{canonical_rec.holding_summary} | {canonical_rec.limits_or_cautions}", 360)
                status = "canonical"
                title = canonical_rec.canonical_name
                court = canonical_rec.court
                year = str(canonical_rec.year)
                source = canonical_rec.source_locator or "Canonical Landmark Pack"
                source_store = "canonical_authority_pack"
                source_tier = "primary_precedent"
            else:
                support_text = ""
                status = "required_but_not_retrieved"
                title = seed.display_name
                court = ""
                year = ""
                source = ""
                source_store = ""
                source_tier = ""

            rows.append(
                {
                    "id": seed.id,
                    "display_name": seed.display_name,
                    "domain": seed.domain,
                    "status": status,
                    "title": title,
                    "court": court,
                    "year": year,
                    "source": source,
                    "source_store": source_store,
                    "source_tier": source_tier,
                    "case_id": meta.get("case_id", ""),
                    "issue_link": seed.domain,
                    "use_in_debate": (
                        "Use as a verified authority anchor."
                        if status in {"retrieved", "canonical"}
                        else "Mention as a required authority to verify; do not claim retrieved support."
                    ),
                    "extract": support_text,
                }
            )
        lines = []
        for row in rows:
            lines.append(
                f"- {row['display_name']} | {row['domain']} | {row['status']} | "
                f"{row.get('court', '')} {row.get('year', '')}"
            )
            if row.get("extract"):
                lines.append(f"  Extract: {row['extract']}")
            elif row["status"] != "retrieved":
                lines.append("  Extract: not retrieved; treat as authority gap requiring verification.")
        return rows, "\n".join(lines) or "- No mandatory authority seed matched this query."

    def _authority_rows_from_issue_packets(self, issue_packets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for packet in issue_packets:
            for doc in packet.get("docs", []):
                title = normalize_authority_display_name(
                    doc.get("title", ""),
                    case_name=doc.get("case_name", ""),
                    fallback=packet.get("label", "Unknown authority"),
                )
                rows.append(
                    {
                        "id": _slug(f"{packet.get('issue_id', '')}_{title}_{doc.get('year', '')}")[:80],
                        "display_name": title,
                        "domain": packet.get("label", ""),
                        "status": "retrieved",
                        "court": doc.get("court", ""),
                        "year": doc.get("year", ""),
                        "source": doc.get("authority_level", ""),
                        "case_id": doc.get("case_id", ""),
                        "case_name": doc.get("case_name", ""),
                        "source_store": doc.get("source_store", ""),
                        "source_tier": doc.get("source_tier", ""),
                        "filename": doc.get("filename", ""),
                        "url": doc.get("url", ""),
                        "score": doc.get("score", ""),
                        "issue_link": packet.get("label", ""),
                        "extract": doc.get("text", ""),
                    }
                )
        return rows

    @staticmethod
    def _format_authority_table(rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return "| Issue | Authority | Status | Why it matters |\n| --- | --- | --- | --- |\n"
        lines = ["| Issue | Authority | Status | Why it matters |", "| --- | --- | --- | --- |"]
        for row in rows[:24]:
            authority = row.get("display_name") or row.get("title") or "Authority"
            court_year = " ".join(str(row.get(k, "")).strip() for k in ("court", "year")).strip()
            if court_year:
                authority = f"{authority} ({court_year})"
            lines.append(
                f"| {row.get('issue_link') or row.get('domain') or '-'} "
                f"| {authority} | {row.get('status', 'retrieved')} "
                f"| {row.get('use_in_debate') or _truncate(row.get('extract', ''), 140) or 'Authority anchor'} |"
            )
        return "\n".join(lines)

    def _elite_clarification_questions(self, user_query: str, issue_map: str) -> str:
        if os.getenv("COURT_DEBATE_ELITE_STATIC_CLARIFICATIONS", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }:
            return "\n".join(
                [
                    "1. What exact order, circular, policy, FIR, or petition text is before the court?",
                    "2. What evidence supports coercion, public order risk, discrimination, or selective enforcement?",
                    "3. What interim and final relief has each party sought?",
                    "4. What forum posture is active: writ, PIL, habeas corpus, criminal investigation, or appeal?",
                    "5. What facts show the lived impact on dignity, education, liberty, safety, or institutional discipline?",
                ]
            )
        prompt = f"""
You are a senior Indian court strategist preparing a High Court matter.
Generate EXACTLY 5 clarification questions that materially change the legal outcome.

Rules:
- Ask only fact-sensitive questions.
- Cover law, evidence, procedural posture, relief, and human/public-order stakes.
- Do not answer the merits.
- Number them 1 to 5.

Issue map:
{issue_map}

User query:
{user_query}
"""
        raw = self.llm.generate(prompt, max_tokens=500, temperature=0.1, purpose="fast")
        questions = [line.strip() for line in raw.splitlines() if "?" in line][:5]
        if len(questions) < 5:
            fallbacks = [
                "1. What exact order, circular, policy, FIR, or petition text is before the court?",
                "2. What evidence supports coercion, public order risk, discrimination, or selective enforcement?",
                "3. What interim and final relief has each party sought?",
                "4. What forum posture is active: writ, PIL, habeas corpus, criminal investigation, or appeal?",
                "5. What facts show the lived impact on dignity, education, liberty, safety, or institutional discipline?",
            ]
            questions = (questions + fallbacks)[:5]
        normalized = []
        for idx, question in enumerate(questions[:5], start=1):
            normalized.append(re.sub(r"^\s*(?:[-*]|\d+[\).:])\s*", f"{idx}. ", question))
        return "\n".join(normalized)

    def _persuasion_guardrail_report(self, sections: Dict[str, str]) -> Dict[str, Any]:
        full_text = "\n\n".join(sections.values()).lower()
        forbidden_patterns = {
            "communal_stereotyping": r"\ball\s+(muslims|hindus|christians|interfaith couples)\b",
            "family_consent_required": r"family(?:'s)?\s+(?:consent|approval)\s+is\s+required",
            "blanket_surveillance": r"all\s+interfaith\s+(?:marriages|couples)\s+should\s+be\s+monitored",
            "love_jihad_proved": r"love jihad\s+is\s+(?:proved|established|real)",
        }
        flags = [
            name
            for name, pattern in forbidden_patterns.items()
            if re.search(pattern, full_text, flags=re.IGNORECASE)
        ]
        positive_signals = [
            signal for signal in (
                "dignity", "autonomy", "chilling effect", "public order",
                "institutional discipline", "human impact", "proportionality",
            )
            if signal in full_text
        ]
        return {
            "flags": flags,
            "ethical_persuasion_signals": positive_signals,
            "passed": not flags and len(positive_signals) >= 3,
        }

    def _elite_quality_report(
        self,
        user_query: str,
        issues: List[Dict[str, str]],
        sections: Dict[str, str],
        evidence_packet_text: str,
        authority_table: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        base = self._quality_report(user_query, issues, sections, evidence_packet_text)
        persuasion = self._persuasion_guardrail_report(sections)
        full_text = "\n\n".join(sections.values())
        full_lower = full_text.lower()
        flags = list(base.get("flags", []))
        supported_statuses = {"retrieved", "canonical"}
        if len([row for row in authority_table if row.get("status") in supported_statuses]) < max(2, len(issues) // 2):
            flags.append("thin_authority_table")
        if any(row.get("status") == "required_but_not_retrieved" for row in authority_table):
            flags.append("mandatory_authority_gap")
        for expected in ("rebuttal", "sur-rebuttal", "bench question", "human impact", "remedy"):
            if expected not in full_lower:
                flags.append(f"missing_{expected.replace(' ', '_')}")
        if not persuasion["passed"]:
            flags.append("persuasion_guardrail_or_signal_failure")
        score = max(0.0, 1.0 - (0.08 * len(set(flags))))
        return {
            **base,
            "score": round(score, 2),
            "court_human_percentage": round(score * 100, 1),
            "elite_gate_passed": score >= 0.85 and not persuasion["flags"] and base.get("ungrounded_case_citations", 0) == 0,
            "flags": sorted(set(flags)),
            "persuasion": persuasion,
            "retrieved_authority_count": len([row for row in authority_table if row.get("status") == "retrieved"]),
            "canonical_authority_count": len([row for row in authority_table if row.get("status") == "canonical"]),
            "authority_gap_count": len([row for row in authority_table if row.get("status") not in supported_statuses]),
        }

    @staticmethod
    def _extract_elite_section(text: str, heading: str) -> str:
        pattern = re.compile(
            rf"(?:^|\n)##\s+{re.escape(heading)}\s*\n(?P<body>.*?)(?=\n##\s+|\Z)",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(text or "")
        if match and match.group("body").strip():
            return match.group("body").strip()

        lvl_match = re.match(r"Level\s+(\d+)", heading, re.IGNORECASE)
        if lvl_match:
            lvl_num = lvl_match.group(1)
            flex_pattern = re.compile(
                rf"(?:^|\n)##\s+Level\s+{lvl_num}\b[^\n]*\n(?P<body>.*?)(?=\n##\s+|\Z)",
                re.IGNORECASE | re.DOTALL,
            )
            flex = flex_pattern.search(text or "")
            if flex and flex.group("body").strip():
                return flex.group("body").strip()
        elif "independent evaluation" in heading.lower():
            eval_pattern = re.compile(
                r"(?:^|\n)##\s+[^\n]*independent\s+evaluation[^\n]*\n(?P<body>.*?)(?=\n##\s+|\Z)",
                re.IGNORECASE | re.DOTALL,
            )
            ev = eval_pattern.search(text or "")
            if ev and ev.group("body").strip():
                return ev.group("body").strip()
        return ""

    def _build_elite_response(
        self,
        *,
        user_query: str,
        session_id: Optional[str],
        domain: str,
        issues: List[Dict[str, str]],
        issue_packets: List[Dict[str, Any]],
        evidence_packet: str,
        seed_packet: str,
        authority_table: List[Dict[str, Any]],
        authority_table_text: str,
        clarification_questions: str,
        sections: Dict[str, str],
        generation_strategy: str,
        authority_bundle: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        quality_report = self._elite_quality_report(
            user_query=user_query,
            issues=issues,
            sections=sections,
            evidence_packet_text=evidence_packet + "\n\n" + seed_packet,
            authority_table=authority_table,
        )
        unsupported_authorities = [
            row for row in authority_table if row.get("status") not in {"retrieved", "canonical"}
        ]
        output_order = [
            ("## Level 1: Issue Framing and Clarification Gate", sections["level_1_issue_framing"]),
            ("## Level 2: Authority Table and Source Discipline", sections["level_2_authority_table"]),
            ("## Level 3: Petitioner / Claimant Submissions", sections["level_3_petitioner_submissions"]),
            ("## Level 4: Respondent / Defence Submissions", sections["level_4_respondent_submissions"]),
            ("## Level 5: Rebuttal and Sur-Rebuttal", sections["level_5_rebuttal_sur_rebuttal"]),
            ("## Level 6: Bench Questions and Cross-Examination", sections["level_6_bench_questions"]),
            ("## Level 7: Ethical Persuasion and Human-Impact Analysis", sections["level_7_persuasion_analysis"]),
            ("## Level 8: Final Bench Ruling, Remedies, and Alternative Outcomes", sections["level_8_final_ruling"]),
            ("## Independent Evaluation (Scored by Judge Agent)", sections["independent_evaluation"]),
        ]
        full_text = "\n\n".join(f"{heading}\n{body}".strip() for heading, body in output_order)
        self._save_to_memory(session_id, user_query, full_text)
        return {
            **sections,
            "debate_output": full_text,
            "quality_mode": "elite",
            "quality_target": "court_85",
            "generation_strategy": generation_strategy,
            "legal_domain": domain,
            "issue_map": issues,
            "issue_packets": issue_packets,
            "authority_table": authority_table,
            "authority_table_markdown": authority_table_text,
            "authority_bundle": authority_bundle or {},
            "judge_questions": sections["level_6_bench_questions"],
            "persuasion_analysis": sections["level_7_persuasion_analysis"],
            "quality_report": quality_report,
            "unsupported_authorities": unsupported_authorities,
            "clarification_questions": clarification_questions,
            "level_5_7_judge": "\n\n".join(
                [
                    sections["level_6_bench_questions"],
                    sections["level_7_persuasion_analysis"],
                    sections["level_8_final_ruling"],
                    sections["independent_evaluation"],
                ]
            ),
        }

    def _fallback_issue_map(self, user_query: str) -> List[Dict[str, str]]:
        query_lower = (user_query or "").lower()
        family = self._scenario_family(user_query)
        if family:
            return [dict(issue) for issue in family.issue_checklist]
        buckets: List[Dict[str, str]] = []
        for issue_id, keywords, label in _ISSUE_KEYWORDS:
            if any(k in query_lower for k in keywords):
                buckets.append(
                    {
                        "id": issue_id,
                        "bucket": issue_id.split("_", 1)[0],
                        "label": label,
                        "question": f"Whether {label.lower()} is legally sustainable on these facts.",
                    }
                )
        if not buckets:
            buckets = [
                {
                    "id": "core_issues",
                    "bucket": "statutory",
                    "label": "Core legal issues and remedies",
                    "question": "What are the main legal issues, strongest arguments on both sides, and likely outcome?",
                }
            ]
        return buckets[:8]

    @staticmethod
    def _is_interfaith_autonomy_case(user_query: str) -> bool:
        q = (user_query or "").lower()
        markers = (
            "special marriage act",
            "love jihad",
            "interfaith",
            "inter-faith",
            "adult woman",
            "choice of spouse",
            "family files a police complaint",
            "married willingly",
            "fears for her safety from her own family",
            "coerced into marriage",
        )
        return sum(1 for marker in markers if marker in q) >= 2

    @staticmethod
    def _is_live_in_relationship_case(user_query: str) -> bool:
        q = (user_query or "").lower()
        markers = (
            "live-in",
            "live in relationship",
            "relationship in the nature of marriage",
            "domestic violence act",
            "shared household",
            "maintenance rights",
            "without marriage",
            "cohabitation",
        )
        return sum(1 for marker in markers if marker in q) >= 2

    # Distinctive domain anchors: a family template may only engage when at
    # least one of these appears in the query. Generic legal words alone
    # ("police complaint", "protection", "maintenance", "arrest") previously
    # pulled wholly unrelated cases into the wrong family blueprint.
    _FAMILY_ANCHOR_TERMS = {
        "interfaith_marriage_autonomy": (
            "special marriage act", "love jihad", "interfaith", "inter-faith",
            "choice of spouse", "conversion",
        ),
        "live_in_relationship_maintenance": (
            "live-in", "live in relationship", "lives together", "without marriage", "cohabitation",
            "relationship in the nature of marriage",
        ),
    }

    def _scenario_family(self, user_query: str) -> Optional[CourtScenarioFamily]:
        q = (user_query or "").lower()
        best: Optional[CourtScenarioFamily] = None
        best_score = 0
        for family in COURT_SCENARIO_FAMILIES:
            score = sum(1 for term in family.trigger_terms if term in q)
            if score > best_score:
                best = family
                best_score = score
        if best is None or best_score < 2:
            return None
        anchors = self._FAMILY_ANCHOR_TERMS.get(best.key)
        if anchors and not any(anchor in q for anchor in anchors):
            # Score came only from generic terms — refuse the family template.
            logger.warning(
                "[CourtDebate] scenario family '%s' rejected: no anchor term in query (score=%s)",
                best.key, best_score,
            )
            return None
        return best

    def _build_preplan(self, user_query: str, session_id: Optional[str], conversation_history: str) -> Dict[str, Any]:
        family = self._scenario_family(user_query)
        # Fast Gate via Laya System 1 Triage (<0.1ms)
        laya_triage: Dict[str, Any] = {}
        try:
            from kaanoon_test.system_adapters.laya_triage_adapter import triage_query
            laya_triage = triage_query(user_query)
        except Exception as laya_err:
            logger.debug(f"[CourtDebate] Laya triage fallback: {laya_err}")

        domain = family.domain if family else (laya_triage.get("domain") or classify_legal_domain(user_query))
        issues = [dict(issue) for issue in family.issue_checklist] if family else self._decompose_issues(user_query, domain, conversation_history)
        side_a, side_b = self._infer_sides(user_query)
        authority_matrix = self._required_authority_matrix(user_query)
        if not authority_matrix and not family:
            # Domain-seeded anchors: without a family template, give the debate
            # real, domain-correct authorities instead of cross-domain leftovers.
            for row in _DOMAIN_AUTHORITY_SEEDS.get(domain, []):
                authority_matrix.append(dict(row))
            # Seed authority matrix with Laya's suggested statutory anchors
            for sec in laya_triage.get("suggested_sections", []):
                statute_name = laya_triage.get("statute", "Statute").upper()
                authority_matrix.append({
                    "name": f"{statute_name} {sec}",
                    "status": "canonical",
                    "relevance": f"Key statutory provision under {statute_name}",
                })
        forum_matrix = list(family.forum_questions) if family else []
        retrieval_hints = list(family.retrieval_query_hints) if family else []
        forum_posture = self._forum_posture_from_matrix(forum_matrix, family.key if family else "generic_complex")
        return {
            "request_id": session_id or f"court_{int(time.time())}",
            "scenario_family": family.key if family else "generic_complex",
            "legal_domain": domain,
            "issue_map": issues,
            "authority_matrix": authority_matrix,
            "forum_matrix": forum_matrix,
            "forum_posture": forum_posture,
            "side_labels": {"a": side_a, "b": side_b},
            "retrieval_query_hints": retrieval_hints,
            "forbidden_carryover_terms": list(family.forbidden_carryover_terms) if family else [],
            "issue_blueprint": "",
            "issue_coverage": {},
            "authority_requirements": authority_matrix,
            "evidence_questions": [],
            "side_theories": {"a": side_a, "b": side_b},
            "quality_flags": [],
            "card_contracts": self._build_card_contracts(family.key if family else "generic_complex", issues, authority_matrix, forum_matrix),
        }

    def _build_card_contracts(
        self,
        scenario_family: str,
        issues: List[Dict[str, str]],
        authority_matrix: List[Dict[str, str]],
        forum_matrix: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        ordered_issue_ids = [issue.get("id", "") for issue in issues]
        required_authorities = [row.get("name", "") for row in authority_matrix]
        base = {
            "ordered_issue_ids": ordered_issue_ids,
            "required_authority_anchors": required_authorities,
            "forum_tracks": forum_matrix,
            "evidence_questions": [issue.get("question", "") for issue in issues],
            "outcome_questions": self._scenario_debate_contract_from_family(scenario_family).get("outcome_questions", ""),
        }
        contracts = {
            "l1": CardContract("l1", 1200, float(os.getenv("COURT_DEBATE_ISSUE_BLUEPRINT_LLM_TIMEOUT_SECONDS", "30"))),
            "l2": CardContract("l2", 900, _CARD_TIMEOUT_SECONDS["l2"]),
            "l3": CardContract("l3", 900, _CARD_TIMEOUT_SECONDS["l3"]),
            "l4": CardContract("l4", 900, 0, deterministic_fallback=True),
            "l5": CardContract("l5", 650, _CARD_TIMEOUT_SECONDS["l5"]),
            "l6": CardContract("l6", 900, _CARD_TIMEOUT_SECONDS["l6"]),
            "l7": CardContract("l7", 650, _CARD_TIMEOUT_SECONDS["l7"]),
            "l8": CardContract("l8", 550, _CARD_TIMEOUT_SECONDS["l8"]),
        }
        return {
            section_id: {
                **base,
                "section_id": contract.section_id,
                "max_words": contract.max_words,
                "timeout_seconds": contract.timeout_seconds,
                "required_issue_coverage": contract.required_issue_coverage,
                "deterministic_fallback": contract.deterministic_fallback,
            }
            for section_id, contract in contracts.items()
        }

    def _scenario_debate_contract_from_family(self, scenario_family: str) -> Dict[str, str]:
        if scenario_family == "interfaith_marriage_autonomy":
            return {
                "outcome_questions": (
                    "1. Can the marriage be challenged or annulled on allegation without concrete evidence?\n"
                    "2. How should the court treat later conversion and a second personal-law marriage after an SMA marriage?\n"
                    "3. What is the evidentiary weight of the adult woman's in-court statement versus prior WhatsApp / digital communications?\n"
                    "4. Does 'love jihad' have independent legal standing?\n"
                    "5. Should habeas / state action prioritize parental concern or the adult woman's autonomy under Article 21?"
                )
            }
        return {"outcome_questions": "Answer each explicit debatable question in the user's prompt directly and separately."}

    @staticmethod
    def _forum_posture_from_matrix(forum_matrix: List[str], scenario_family: str) -> Dict[str, Any]:
        if scenario_family == "interfaith_marriage_autonomy":
            return {
                "primary_tracks": [
                    "habeas/protection",
                    "criminal complaint / investigation",
                    "SMA validity or matrimonial challenge",
                    "state anti-conversion scrutiny if pleaded",
                ],
                "discipline": (
                    "Keep adult liberty and protection distinct from criminal investigation; "
                    "parental concern can justify inquiry but cannot override an adult's in-court choice without proof."
                ),
                "forum_questions": forum_matrix,
            }
        return {
            "primary_tracks": forum_matrix or ["civil / writ / statutory forum to be identified from pleadings"],
            "discipline": "Identify the active forum before predicting remedy or evidentiary burden.",
            "forum_questions": forum_matrix,
        }

    def _decompose_issues(self, user_query: str, domain: str, conversation_history: str = "") -> List[Dict[str, str]]:
        prompt = f"""
You are an Indian legal issue-framing specialist.
Return ONLY valid JSON as a list of objects with keys: id, bucket, label, question.

Rules:
- Return between 3 and 6 issues: one for EVERY distinct legal problem in the facts
  (statutory + constitutional + procedural + evidence). Never collapse a multi-issue
  scenario into a single academic issue.
- Each issue must be tied to the specific facts given (parties, dates, amounts, forums).
- Buckets must be chosen from: constitutional, statutory, contractual, procedural, regulatory, evidence.
- Include forum-split issues if the query involves multiple forums.
- Maximum 8 issues.

Conversation history:
{conversation_history or 'None'}

Detected legal domain:
{domain}

User query:
{user_query}
"""
        try:
            raw = self.llm.generate(prompt, max_tokens=1600, temperature=0.1, purpose="fast")
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
                cleaned = re.sub(r"```$", "", cleaned).strip()
            parsed = json.loads(cleaned)
            issues: List[Dict[str, str]] = []
            for idx, item in enumerate(parsed if isinstance(parsed, list) else [], start=1):
                if not isinstance(item, dict):
                    continue
                label = _clean_ws(str(item.get("label", "")))
                question = _clean_ws(str(item.get("question", "")))
                if not label or not question:
                    continue
                issues.append(
                    {
                        "id": _clean_ws(str(item.get("id", f"issue_{idx}"))).lower().replace(" ", "_"),
                        "bucket": _clean_ws(str(item.get("bucket", "statutory"))).lower(),
                        "label": label,
                        "question": question,
                    }
                )
            if len(issues) >= 2:
                return issues[:8]
            # Degenerate single-issue output (quota-stress) — enrich with the
            # keyword/family map so the debate never locks onto one thin issue.
            enriched = issues + [i for i in self._fallback_issue_map(user_query)
                                 if i.get("id") not in {x.get("id") for x in issues}]
            if len(enriched) >= 2:
                logger.warning("[CourtDebateV2] Degenerate decomposition enriched to %s issues", len(enriched))
                return enriched[:8]
        except Exception as exc:
            logger.warning(f"[CourtDebateV2] Issue decomposition fallback: {exc}")
        return self._fallback_issue_map(user_query)

    def _format_issue_map(self, issues: List[Dict[str, str]]) -> str:
        return "\n".join(f"- [{item['bucket']}] {item['label']}: {item['question']}" for item in issues)

    @staticmethod
    def _issue_label_tokens(issue: Dict[str, str]) -> List[str]:
        words = re.findall(r"[a-z0-9]+", (issue.get("label", "") + " " + issue.get("question", "")).lower())
        stop = {
            "whether", "should", "under", "with", "from", "into", "what", "which",
            "party", "legal", "issue", "court", "state", "proof", "given", "after",
        }
        return [word for word in words if len(word) >= 5 and word not in stop][:8]

    def _issue_coverage_map(self, text: str, issues: List[Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
        body = (text or "").lower()
        coverage: Dict[str, Dict[str, Any]] = {}
        for issue in issues:
            tokens = self._issue_label_tokens(issue)
            hits = [token for token in tokens if token in body]
            issue_id = issue.get("id", "unknown")
            coverage[issue_id] = {
                "label": issue.get("label", ""),
                "covered": bool(hits) and len(hits) >= max(1, min(2, len(tokens))),
                "hits": hits,
            }
        return coverage

    def _missing_major_issue_ids(self, text: str, issues: List[Dict[str, str]]) -> List[str]:
        coverage = self._issue_coverage_map(text, issues)
        return [issue_id for issue_id, data in coverage.items() if not data["covered"]]

    def _issue_authority_status_rows(
        self,
        *,
        issues: List[Dict[str, str]],
        issue_packets: List[Dict[str, Any]],
        authority_matrix: List[Dict[str, str]],
        user_query: str = "",
    ) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        docs_by_issue = {packet.get("issue_id"): packet.get("docs", []) for packet in issue_packets}
        canonical_by_issue: Dict[str, List[Dict[str, Any]]] = {}
        if user_query:
            try:
                resolver_docs = []
                for packet in issue_packets:
                    resolver_docs.extend(packet.get("docs", []))
                bundle = self.authority_resolver.build_bundle(user_query, issues, resolver_docs)
                matrix = bundle.get("issue_authority_matrix") or []
                verified = {
                    row.get("display_name"): row
                    for row in bundle.get("verified_authorities", [])
                    if row.get("display_name")
                }
                for item in matrix:
                    canonical_by_issue[str(item.get("issue_id", ""))] = [
                        verified[name]
                        for name in item.get("authorities", [])
                        if name in verified
                    ]
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"[CourtDebateStream] canonical authority merge skipped: {exc}")
        for issue in issues:
            docs = docs_by_issue.get(issue.get("id"), [])
            status = "authority_gap"
            authority = "Authority gap - verify before relying"
            if docs:
                first = docs[0]
                status = first.get("retrieval_status") or "retrieved"
                if status == "suggested-but-unverified":
                    status = "suggested_but_unverified"
                if status not in {"retrieved", "suggested_but_unverified", "authority_gap"}:
                    status = "retrieved" if first.get("text") else "authority_gap"
                authority = first.get("title") or first.get("case_name") or authority
            elif canonical_by_issue.get(issue.get("id", "")):
                first = canonical_by_issue[issue.get("id", "")][0]
                authority = first.get("display_name") or first.get("title") or authority
                status = "suggested_but_unverified"
            else:
                matching = [
                    row.get("name", "")
                    for row in authority_matrix
                    if self._authority_row_matches_issue(row, issue)
                ]
                if matching:
                    authority = matching[0]
            rows.append(
                {
                    "issue_id": issue.get("id", ""),
                    "issue": issue.get("label", ""),
                    "authority": authority,
                    "status": status,
                }
            )
        return rows

    @staticmethod
    def _authority_row_matches_issue(row: Dict[str, str], issue: Dict[str, str]) -> bool:
        haystack = f"{issue.get('id', '')} {issue.get('label', '')} {issue.get('question', '')}".lower()
        terms = re.findall(r"[a-z0-9]+", f"{row.get('issue', '')} {row.get('name', '')}".lower())
        meaningful = [term for term in terms if len(term) >= 5][:5]
        return bool(meaningful and any(term in haystack for term in meaningful))

    @staticmethod
    def _authority_status_counts(rows: List[Dict[str, str]]) -> Dict[str, int]:
        counts = {"retrieved": 0, "suggested_but_unverified": 0, "authority_gap": 0}
        for row in rows:
            status = row.get("status", "authority_gap")
            if status not in counts:
                status = "authority_gap"
            counts[status] += 1
        return counts

    @staticmethod
    def _rows_by_issue(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        return {row.get("issue_id", ""): row for row in rows}

    def _render_evidence_authority_card(
        self,
        *,
        issues: List[Dict[str, str]],
        authority_status_rows: List[Dict[str, str]],
        evidence_timed_out: bool = False,
    ) -> str:
        by_issue = self._rows_by_issue(authority_status_rows)
        lines = [
            "This authority packet is generated from the locked issue blueprint, not from advocacy prose.",
            "",
            "| Issue | Authority / Statute | Proposition | Support Strength | Forum Relevance | Retrieval Status |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for issue in issues:
            row = by_issue.get(issue.get("id", ""), {})
            status = row.get("status") if row.get("status") in {"retrieved", "suggested_but_unverified", "authority_gap"} else "authority_gap"
            authority = row.get("authority") or "Authority gap - verify before relying"
            strength = "Source retrieved" if status == "retrieved" else ("Canonical hint; verify source text" if status == "suggested_but_unverified" else "Gap-labeled")
            forum = "High: this row controls the framed issue's proof, forum, or remedy posture"
            proposition = issue.get("question", "")
            lines.append(
                f"| {issue.get('label', '')} | {authority} | {proposition} | {strength} | {forum} | {status} |"
            )
        lines.extend(
            [
                "",
                "Discipline: use retrieved rows as source anchors; use suggested_but_unverified rows only as research leads; treat authority_gap rows as lower-confidence and verify before relying.",
            ]
        )
        if evidence_timed_out:
            lines.append("Retrieval note: live retrieval timed out, so unresolved rows are deliberately labelled authority_gap.")
        return "\n".join(lines)

    def _render_advocate_fallback(
        self,
        *,
        side: str,
        side_theory: str,
        issues: List[Dict[str, str]],
        authority_status_rows: List[Dict[str, str]],
    ) -> str:
        rows = self._rows_by_issue(authority_status_rows)
        lines = [
            f"{side} follows the locked issue blueprint. This fallback is used to keep the debate complete and disciplined.",
            "",
            "| Issue | Position | Proof Burden | Authority Status | Vulnerability |",
            "| --- | --- | --- | --- | --- |",
        ]
        for issue in issues:
            row = rows.get(issue.get("id", ""), {})
            status = row.get("status", "authority_gap")
            authority = row.get("authority", "Authority gap - verify before relying")
            position = f"{side_theory} The court should answer this issue through the facts tied to: {issue.get('question', '')}"
            burden = "The party asserting coercion, invalidity, offence ingredients, or forum control must prove it with concrete evidence."
            vulnerability = "The submission weakens if the record lacks corroboration or if it asks the court to replace adult choice with suspicion."
            lines.append(f"| {issue.get('label', '')} | {position} | {burden} | {authority} / {status} | {vulnerability} |")
        return "\n".join(lines)

    def _render_cross_exam_fallback(
        self,
        *,
        issues: List[Dict[str, str]],
        authority_status_rows: List[Dict[str, str]],
    ) -> str:
        rows = self._rows_by_issue(authority_status_rows)
        lines = ["Cross-examination tests both sides against the locked issues.", ""]
        for issue in issues:
            row = rows.get(issue.get("id", ""), {})
            lines.append(f"### {issue.get('label', '')}")
            lines.append("- Overreach: does either side convert suspicion, family concern, media pressure, or a label into legal proof?")
            lines.append("- Missing Assumption: what fact must be proved before the court can act on this issue?")
            lines.append("- Weak Forum Fit: should this be decided in habeas/protection, criminal investigation, matrimonial challenge, or statutory conversion inquiry?")
            lines.append(f"- Unsupported Proposition: authority anchor is {row.get('authority', 'authority gap - verify before relying')} / {row.get('status', 'authority_gap')}.")
        return "\n".join(lines)

    def _render_bench_fallback(
        self,
        *,
        issues: List[Dict[str, str]],
        authority_status_rows: List[Dict[str, str]],
    ) -> str:
        rows = self._rows_by_issue(authority_status_rows)
        lines = ["The bench answers the locked issues in order and separates liberty, investigation, evidence, and remedy.", ""]
        for issue in issues:
            row = rows.get(issue.get("id", ""), {})
            label = issue.get("label", "")
            lower = f"{label} {issue.get('question', '')}".lower()
            if "love jihad" in lower:
                result = "The label has no independent legal force; the court asks only whether provable offences such as coercion, fraud, confinement, or forced conversion are made out."
            elif "habeas" in lower:
                result = "A habeas court should verify present free will and custody; parental concern alone should not override an adult's in-court statement."
            elif "special marriage" in lower or "second marriage" in lower:
                result = "The SMA marriage should be treated as subsisting unless a competent forum finds a statutory ground; later conversion or ceremony is a separate legal question."
            elif "conversion" in lower:
                result = "A focused anti-conversion inquiry is permissible only on evidence of force, fraud, allurement, or coercion, not on communal suspicion."
            elif "whatsapp" in lower or "digital" in lower:
                result = "The magistrate statement carries strong present-consent value, while chats may create inquiry points only after authentication and contextual assessment."
            elif "kidnapping" in lower or "confinement" in lower:
                result = "Investigation may continue if offence ingredients exist, but detention cannot rest on allegation once an adult denies confinement without contrary material."
            else:
                result = (
                    "The bench decides this issue strictly on the pleaded facts and the governing statute: "
                    "the burden rests on the party alleging the violation, and the remedy follows the proved elements."
                )
            lines.append(f"### {label}")
            lines.append(f"Bench answer: {result}")
            lines.append(f"Authority anchor: {row.get('authority', 'authority gap - verify before relying')} / {row.get('status', 'authority_gap')}.")
        return "\n".join(lines)

    def _render_outcome_fallback(
        self,
        *,
        user_query: str,
        issues: List[Dict[str, str]],
        authority_status_rows: List[Dict[str, str]],
    ) -> str:
        rows = self._rows_by_issue(authority_status_rows)
        lines = [
            "Likely outcome: each framed issue is resolved below on the governing statute and the strongest authority actually on record. Where an authority row reads suggested_but_unverified or authority_gap, treat the answer as provisional and verify before relying.",
            "",
            "Issue-by-issue outcome:",
        ]
        for issue in issues:
            row = rows.get(issue.get("id", ""), {})
            lines.append(f"- {issue.get('label', '')}: answer with lower confidence where {row.get('status', 'authority_gap')} appears; authority anchor {row.get('authority', 'authority gap - verify before relying')}.")
        return "\n".join(lines)

    def _render_risks_fallback(
        self,
        *,
        issues: List[Dict[str, str]],
        authority_status_rows: List[Dict[str, str]],
    ) -> str:
        rows = self._rows_by_issue(authority_status_rows)
        lines = [
            "Risks and next steps stay tied to the locked issue blueprint.",
            "",
            "- Legal uncertainty: exact statutory provisions and current criminal-code equivalents must be verified before relying on section numbers.",
            "- Evidence uncertainty: authenticate records (agreements, receipts, digital communications), preserve metadata, and separate allegation from proof.",
            "- Forum uncertainty: keep each available forum (statutory authority, consumer/tribunal, civil suit, criminal complaint) separate and choose by remedy and limitation period.",
            "- Immediate steps: preserve all documents and communications, send any statutory notice within its limitation window, and avoid media-driven findings.",
            "",
            "Authority gap register:",
        ]
        for issue in issues:
            row = rows.get(issue.get("id", ""), {})
            if row.get("status") != "retrieved":
                lines.append(f"- {issue.get('label', '')}: {row.get('authority', 'authority gap - verify before relying')} / {row.get('status', 'authority_gap')}.")
        return "\n".join(lines)

    def _fallback_for_section(
        self,
        *,
        section_id: str,
        user_query: str,
        issues: List[Dict[str, str]],
        authority_status_rows: List[Dict[str, str]],
        debate_contract: Dict[str, str],
        evidence_timed_out: bool = False,
    ) -> str:
        if section_id == "l2":
            return self._render_advocate_fallback(
                side=debate_contract.get("advocate_a_title", "Advocate A"),
                side_theory=debate_contract.get("advocate_a_theory", "Press the legally sustainable challenge."),
                issues=issues,
                authority_status_rows=authority_status_rows,
            )
        if section_id == "l3":
            return self._render_advocate_fallback(
                side=debate_contract.get("advocate_b_title", "Advocate B"),
                side_theory=debate_contract.get("advocate_b_theory", "Defend the legally sustainable response."),
                issues=issues,
                authority_status_rows=authority_status_rows,
            )
        if section_id == "l4":
            return self._render_evidence_authority_card(
                issues=issues,
                authority_status_rows=authority_status_rows,
                evidence_timed_out=evidence_timed_out,
            )
        if section_id == "l5":
            return self._render_cross_exam_fallback(issues=issues, authority_status_rows=authority_status_rows)
        if section_id == "l6":
            return self._render_bench_fallback(issues=issues, authority_status_rows=authority_status_rows)
        if section_id == "l7":
            return self._render_outcome_fallback(user_query=user_query, issues=issues, authority_status_rows=authority_status_rows)
        if section_id == "l8":
            return self._render_risks_fallback(issues=issues, authority_status_rows=authority_status_rows)
        return "authority gap - verify before relying."

    def _complex_interfaith_required_terms(self, user_query: str = "") -> List[Tuple[str, Tuple[str, ...]]]:
        q = (user_query or "").lower()
        terms: List[Tuple[str, Tuple[str, ...]]] = [
            ("article21_autonomy", ("article 21", "autonomy", "adult choice")),
            ("special_marriage_act", ("special marriage act", "sma")),
            ("love_jihad_legal_status", ("love jihad", "uniform statutory", "independent legal")),
            ("state_protection", ("state duty", "investigate", "protect", "family threat", "safety")),
            ("parental_concern_adult_liberty", ("parental concern", "adult liberty", "family concern")),
            ("burden_or_proof", ("burden", "proof", "evidence")),
        ]
        if any(marker in q for marker in ("convert", "conversion", "islam", "anti-conversion", "religious conversion")):
            terms.append(("conversion_scrutiny", ("conversion", "anti-conversion", "forced conversion")))
            terms.append(("second_marriage_interaction", ("second marriage", "personal law", "conversion")))
        if any(marker in q for marker in ("habeas", "custody", "psychological captivity")):
            terms.append(("habeas_posture", ("habeas", "psychological captivity", "custody")))
        if any(marker in q for marker in ("whatsapp", "chat", "digital", "communications")):
            terms.append(("digital_evidence", ("whatsapp", "digital", "communications", "electronic")))
        if any(marker in q for marker in ("kidnapping", "wrongful confinement", "detain", "police")):
            terms.append(("criminal_process", ("kidnapping", "wrongful confinement", "police", "detention")))
        if any(marker in q for marker in ("media", "political")):
            terms.append(("media_pressure", ("media", "political", "public pressure")))
        return terms

    def _issue_blueprint_quality_flags(
        self,
        *,
        user_query: str,
        text: str,
        issues: List[Dict[str, str]],
        authority_matrix: List[Dict[str, str]],
    ) -> List[str]:
        body = (text or "").strip().lower()
        flags: List[str] = []
        if len(re.sub(r"\W+", "", body)) < 900:
            flags.append("issue_blueprint_too_thin")
        if "core legal issues and remedies" in body:
            flags.append("generic_issue_framing")
        if "authority gap" not in body and "retrieved" not in body and authority_matrix:
            flags.append("missing_authority_status_discipline")
        for issue_id in self._missing_major_issue_ids(text, issues):
            flags.append(f"missing_issue_{issue_id}")
        family = self._scenario_family(user_query)
        if family and family.key == "interfaith_marriage_autonomy":
            for flag, synonyms in self._complex_interfaith_required_terms(user_query):
                if not any(term in body for term in synonyms):
                    flags.append(f"missing_{flag}")
        if family and family.key == "live_in_relationship_maintenance":
            for phrase in ("relationship in the nature of marriage", "domestic violence", "maintenance", "shared household", "cultural"):
                if phrase not in body:
                    flags.append(f"missing_{phrase.replace(' ', '_')}")
        return sorted(set(flags))

    def _fallback_issue_blueprint(
        self,
        *,
        user_query: str,
        preplan: Dict[str, Any],
        guardrails: str,
        authority_hints: str,
        authority_matrix_text: str,
        evidence_packet: str,
    ) -> str:
        issues = preplan["issue_map"]
        family_key = preplan.get("scenario_family", "generic_complex")
        issue_lines = [
            f"{idx}. [{issue['bucket']}] {issue['label']}: {issue['question']}"
            for idx, issue in enumerate(issues, start=1)
        ]
        evidence_questions = [
            f"- {issue['label']}: What facts prove or weaken this issue, and which party carries practical proof risk?"
            for issue in issues
        ]
        return "\n".join(
            [
                "The court first frames a locked issue blueprint before hearing the advocates.",
                "",
                "## Locked Scenario Classification",
                f"- Scenario family: {family_key}",
                f"- Legal domain: {preplan['legal_domain']}",
                "- Blueprint rule: later advocates must argue within this issue map and may not replace it with a different frame.",
                "",
                "## Locked Decision Issues",
                *issue_lines,
                "",
                "## Forum Posture",
                "- Separate criminal investigation from matrimonial validity, habeas/protection relief, and any statutory conversion inquiry.",
                "- Treat parental concern as a trigger for lawful fact-checking, not as proof against adult liberty.",
                f"- Forum discipline: {preplan.get('forum_posture', {}).get('discipline', 'Identify the active forum before selecting remedy.')}",
                "- The state duty is to investigate provable offences without overriding Article 21 autonomy or present adult choice.",
                "",
                "## Evidence Questions",
                *evidence_questions,
                "",
                "## Authority Discipline",
                authority_matrix_text,
                "- Evidence status labels must be one of: retrieved, suggested_but_unverified, or authority_gap.",
                "- If an authority or statutory extract is not retrieved, mark it as authority gap - verify before relying.",
                "- 'Love jihad' is not a uniform statutory label or standalone offence; translate it into provable offences such as coercion, fraud, unlawful confinement, or forced conversion.",
                "",
                "## Current-Law Guardrails",
                guardrails,
                "",
                "## Authority Hints",
                authority_hints,
                "",
                "## Evidence Packet Status",
                evidence_packet or "No strong retrieval returned; authority gap - verify before relying.",
            ]
        )

    def _build_issue_blueprint(
        self,
        *,
        user_query: str,
        preplan: Dict[str, Any],
        guardrails: str,
        authority_hints: str,
        authority_matrix_text: str,
        evidence_packet: str,
    ) -> Tuple[str, List[str], int]:
        issues = preplan["issue_map"]
        fallback = self._fallback_issue_blueprint(
            user_query=user_query,
            preplan=preplan,
            guardrails=guardrails,
            authority_hints=authority_hints,
            authority_matrix_text=authority_matrix_text,
            evidence_packet=evidence_packet,
        )
        fallback_flags = self._issue_blueprint_quality_flags(
            user_query=user_query,
            text=fallback,
            issues=issues,
            authority_matrix=preplan["authority_matrix"],
        )
        known_family = preplan.get("scenario_family") not in {"", "generic_complex", None}
        polish_known = os.getenv("COURT_DEBATE_L1_LLM_POLISH_KNOWN_FAMILIES", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }
        if known_family and not polish_known:
            return fallback, fallback_flags, 0
        prompt = f"""You are the Issue Framing Bench for an Indian-law courtroom debate.
Create the first visible card as a deep legal blueprint, not a conclusion and not advocacy.
The blueprint will bind Advocate A, Advocate B, Evidence, Bench Analysis, Likely Outcome, and Risks.

Mandatory requirements:
- Use the locked issue checklist and preserve its order.
- Distinguish constitutional, statutory, criminal/procedural, evidence, regulatory, and remedy/forum questions.
- Identify what each side must prove, but do not decide the outcome.
- Mark missing support as "authority gap - verify before relying".
- Do not use confident quote-style wording unless the extract appears in the evidence packet.
- For interfaith conversion/habeas facts, expressly cover Article 21 autonomy, Special Marriage Act validity, later conversion and second marriage, state anti-conversion scrutiny, kidnapping/wrongful confinement posture, habeas corpus maintainability, in-court statement versus WhatsApp/digital communications, love-jihad legal-status discipline, parental concern versus adult liberty, and state investigation limits.

User query:
{user_query}

Scenario family: {preplan['scenario_family']}
Legal domain: {preplan['legal_domain']}

Locked issue checklist:
{self._format_issue_map(issues)}

Required authority matrix:
{authority_matrix_text}

Current-law guardrails:
{guardrails}

Authority hints:
{authority_hints}

Evidence packet:
{evidence_packet}

Output with these headings:
## Locked Scenario Classification
## Locked Decision Issues
## Forum Posture
## Evidence Questions
## Authority Discipline
## Debate Path
"""
        attempts = 0
        best_text = fallback
        best_flags = fallback_flags
        while attempts < 2:
            attempts += 1
            generated = ""
            blueprint_timeout = float(os.getenv("COURT_DEBATE_ISSUE_BLUEPRINT_LLM_TIMEOUT_SECONDS", "8"))
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = executor.submit(
                self.llm.generate,
                prompt,
                1900,
                0.08,
                "fast",
            )
            try:
                generated = (future.result(timeout=blueprint_timeout) or "").strip()
            except concurrent.futures.TimeoutError:
                future.cancel()
                logger.warning(
                    "[CourtDebateStream] issue_blueprint_llm_timeout seconds=%.1f; using deterministic blueprint",
                    blueprint_timeout,
                )
                break
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
            if generated and not generated.lower().startswith("[llm error]"):
                best_text = generated
            best_flags = self._issue_blueprint_quality_flags(
                user_query=user_query,
                text=best_text,
                issues=issues,
                authority_matrix=preplan["authority_matrix"],
            )
            blocking_flags = [flag for flag in best_flags if flag not in _ADVISORY_QUALITY_FLAGS]
            if not blocking_flags:
                break
            prompt = (
                f"{prompt}\n\n"
                "Quality repair required for Issue Framing.\n"
                f"Current flags: {', '.join(blocking_flags)}.\n"
                "Rewrite the blueprint. Preserve the issue checklist order and include all missing legal buckets.\n"
                f"Current draft:\n{best_text}"
            )
        if any(flag.startswith("missing_") or flag in {"generic_issue_framing", "issue_blueprint_too_thin"} for flag in best_flags):
            if len(fallback_flags) < len(best_flags):
                return fallback, fallback_flags, attempts
        return best_text, best_flags, attempts

    def _build_evidence_packet(self, user_query: str, issues: List[Dict[str, str]], n_per_issue: int = 3) -> Tuple[List[Dict[str, Any]], str]:
        packets: List[Dict[str, Any]] = []
        family = self._scenario_family(user_query)
        shared_hints = " ".join(family.retrieval_query_hints) if family else ""
        for issue in issues:
            issue_query = f"{user_query} {issue['label']} {issue['question']} {shared_hints}".strip()
            docs = self.retriever.retrieve(issue_query, n=n_per_issue)
            packet_docs = []
            for doc in docs[:n_per_issue]:
                meta = doc.get("metadata") or {}
                court = meta.get("court", "")
                authority_level = meta.get("authority_level") or meta.get("doc_type") or meta.get("source", "")
                retrieval_status = "retrieved"
                if not doc.get("text"):
                    retrieval_status = "authority_gap"
                elif "unknown" in str(meta.get("source", "")).lower():
                    retrieval_status = "suggested_but_unverified"
                packet_docs.append(
                    {
                        "title": meta.get("title") or meta.get("source") or "Unknown authority",
                        "case_name": meta.get("case_name", ""),
                        "case_id": meta.get("case_id", ""),
                        "court": court,
                        "year": str(meta.get("year", "")),
                        "authority_level": authority_level,
                        "source_store": meta.get("source_store", ""),
                        "source_tier": meta.get("source_tier", ""),
                        "filename": meta.get("filename", ""),
                        "url": meta.get("url") or doc.get("url", ""),
                        "score": doc.get("score", ""),
                        "retrieval_status": retrieval_status,
                        "text": _truncate(doc.get("text") or "", 420),
                    }
                )
            packets.append({"issue_id": issue["id"], "label": issue["label"], "question": issue["question"], "docs": packet_docs})
        lines = []
        for idx, packet in enumerate(packets, start=1):
            lines.append(f"### Issue {idx}: {packet['label']}")
            lines.append(packet["question"])
            if not packet["docs"]:
                lines.append("- authority_gap | No strong retrieval returned for this issue. Treat conclusions as lower-confidence and verify before relying.")
                continue
            for j, doc in enumerate(packet["docs"], start=1):
                lines.append(f"- [{idx}.{j}] {doc['title']} | {doc['court']} | {doc['year']} | {doc['authority_level']} | score={doc['score']} | {doc['retrieval_status']}")
                lines.append(f"  Holding / extract: {doc['text']}")
        return packets, "\n".join(lines)

    def _build_stream_evidence_packet(self, user_query: str, issues: List[Dict[str, str]]) -> Tuple[List[Dict[str, Any]], str, bool]:
        """Bound RAG retrieval for live SSE so slow vector stores cannot freeze card reveal."""
        def fallback_authority_table(reason: str) -> str:
            matrix = self._required_authority_matrix(user_query)
            lines = [
                reason,
                "Proceed using the required authority matrix and mark uncited propositions as 'authority gap - verify before relying'.",
                "",
                "| Issue | Authority / Statute | Proposition | Support Strength | Forum Relevance | Retrieval Status |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
            if matrix:
                for row in matrix:
                    lines.append(
                        f"| {row.get('issue', 'Framed issue')} | {row.get('name', 'Required authority')} | "
                        f"Use only as a required anchor unless retrieved. | Gap-labeled | High | authority_gap |"
                    )
            else:
                for issue in issues:
                    lines.append(
                        f"| {issue['label']} | Authority gap - verify before relying | "
                        f"No strong retrieval returned for this framed issue. | Weak | Depends on forum | authority_gap |"
                    )
            return "\n".join(lines)

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self._build_evidence_packet, user_query, issues)
        try:
            packets, evidence_packet = future.result(timeout=_STREAM_EVIDENCE_TIMEOUT_SECONDS)
            return packets, evidence_packet, False
        except concurrent.futures.TimeoutError:
            future.cancel()
            logger.warning(
                "[CourtDebateStream] evidence_timeout seconds=%.1f; continuing with authority matrix gaps",
                _STREAM_EVIDENCE_TIMEOUT_SECONDS,
            )
            return [], fallback_authority_table("Evidence retrieval timed out for the live stream."), True
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[CourtDebateStream] evidence_error; continuing with authority gaps: {exc}")
            return [], fallback_authority_table("Evidence retrieval failed for the live stream."), True
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _critique_and_rewrite(self, role: str, draft_prompt: str, rewrite_context: str, max_tokens: int = 1400) -> str:
        draft = self.llm.generate(draft_prompt, max_tokens=max_tokens, temperature=0.25)
        if draft.startswith("[ERROR]") or draft.startswith("[LLM ERROR]"):
            return draft
        critique = self.llm.generate(
            f"You are a strict quality reviewer for Indian legal analysis.\nReview the following {role} draft.\nReturn ONLY short bullets under exactly these labels:\n- Missing Issues:\n- Unsupported Risk:\n- Style / Human Quality:\n\nDraft:\n{draft}\n\nReviewer context:\n{rewrite_context}",
            max_tokens=350,
            temperature=0.1,
        )
        improved = self.llm.generate(
            f"Rewrite the following {role} section from scratch using the critique below. Keep the strongest reasoning. Remove generic filler. Tie important claims to the evidence packet. Sound like polished human legal writing.\n\nOriginal draft:\n{draft}\n\nCritique:\n{critique}\n\nContext:\n{rewrite_context}\n\nOutput only the rewritten section.",
            max_tokens=max_tokens,
            temperature=0.2,
        )
        return improved if improved and not improved.startswith("[LLM ERROR]") else draft

    def _quality_report(self, user_query: str, issues: List[Dict[str, str]], sections: Dict[str, str], evidence_packet_text: str) -> Dict[str, Any]:
        full_text = "\n\n".join(v for v in sections.values() if v)
        flags: List[str] = []
        missing_issues = []
        for issue in issues:
            label_tokens = [tok for tok in re.findall(r"[a-z]{5,}", issue["label"].lower())[:3]]
            if label_tokens and not any(tok in full_text.lower() for tok in label_tokens):
                missing_issues.append(issue["label"])
        if missing_issues:
            flags.append("missing_issue_coverage")
        if len(full_text.split()) < 500:
            flags.append("too_short_for_complex_debate")
        if "uncertain" not in full_text.lower() and "likely" not in full_text.lower():
            flags.append("no_uncertainty_language")
        if "consumer" in user_query.lower() and "high court" in user_query.lower():
            if "consumer commission" not in full_text.lower() or "high court" not in full_text.lower():
                flags.append("forum_split_not_explicit")
        grounding_hits = sum(1 for marker in ("article", "section", "act", "court", "commission") if marker in full_text.lower())
        if grounding_hits < 6:
            flags.append("weak_grounding_signal")
        if "privacy" in user_query.lower() or "data" in user_query.lower():
            stale_ref = "personal data protection bill"
            stale_idx = full_text.lower().find(stale_ref)
            stale_context = full_text.lower()[max(0, stale_idx - 120): stale_idx + 120] if stale_idx >= 0 else ""
            stale_warning_context = any(marker in stale_context for marker in ("stale law", "superseded", "historical background"))
            if stale_idx >= 0 and not stale_warning_context:
                flags.append("outdated_data_law_reference")
            if "dpdp" not in full_text.lower() and "digital personal data protection act" not in full_text.lower():
                flags.append("missing_current_data_law")
        ungrounded_cases = 0
        try:
            from kaanoon_test.system_adapters.citation_extractor import CitationExtractor
            extractor = CitationExtractor()
            extracted = extractor.extract_citations(full_text)
            validation = extractor.validate_citations(extracted, [{"text": evidence_packet_text}])
            ungrounded_cases = sum(1 for item in validation.get("missing_from_context", []) if item.get("type") == "Case Law")
            if ungrounded_cases:
                flags.append("ungrounded_case_citations")
        except Exception as exc:
            logger.debug(f"[CourtDebateV2] Citation validation skipped: {exc}")
        score = max(0.0, 1.0 - (0.12 * len(flags)))
        return {"score": round(score, 2), "flags": flags, "missing_issues": missing_issues, "ungrounded_case_citations": ungrounded_cases}

    def _current_law_guardrails(self, user_query: str) -> str:
        q = (user_query or "").lower()
        notes = []
        family = self._scenario_family(user_query)
        if family and family.key == "interfaith_marriage_autonomy":
            notes.append("- Treat the marriage as an adult-choice and personal-liberty dispute first; do not let family objection substitute for legal proof.")
            notes.append("- Address the Special Marriage Act validity / challenge framework expressly and separate later conversion or a personal-law ceremony from proof of invalidity.")
            notes.append("- For forced-conversion allegations, identify the applicable state anti-conversion law and its proof posture; do not imply a uniform national 'love jihad' offence.")
            notes.append("- Treat WhatsApp or other digital communications as evidence to be weighed against the adult's in-court statement, not as automatic displacement of present consent.")
            notes.append("- For habeas corpus, distinguish illegal detention/custody from parental concern or psychological-captivity allegations after the adult appears before court.")
            notes.append("- Do not treat 'love jihad' as an independent legal ground. Analyze only concrete allegations such as coercion, fraud, unlawful confinement, or forced conversion if supported by evidence.")
            notes.append("- Distinguish criminal complaint, protection / habeas relief, and matrimonial annulment as separate procedural tracks.")
            notes.append("- Do not use quote-style wording for a case unless the underlying proposition is retrieved or clearly identified as an authority gap.")
        if family and family.key == "live_in_relationship_maintenance":
            notes.append("- Do not assume formal marriage is required for every remedy. Analyze the relationship-in-the-nature-of-marriage test and the Domestic Violence Act separately from maintenance routes.")
            notes.append("- Distinguish domestic violence protection from maintenance entitlement; they overlap factually but are not identical legal questions.")
            notes.append("- Do not let cultural disapproval substitute for statutory analysis.")
            notes.append("- Name the Domestic Violence Act domestic-relationship framework expressly and identify any maintenance-route authority gap directly.")
        if "privacy" in q or "data" in q or "breach" in q:
            notes.append("- Treat Digital Personal Data Protection Act, 2023 as the current primary personal-data statute in India; do not fall back to the old Personal Data Protection Bill, 2019 except as historical background.")
            notes.append("- Pair DPDP Act analysis with IT Act section 43A / SPDI Rules where relevant.")
            notes.append("- If consumer arbitration appears, address the consumer-forum non-ouster line of authority and do not assume arbitration automatically defeats consumer jurisdiction.")
        if "pil" in q or "high court" in q or "article 226" in q:
            notes.append("- Distinguish direct Article 21 enforcement from Article 226 maintainability against private bodies; analyze public function / public law duty carefully.")
        return "\n".join(notes) or "- Use the current governing law and identify stale-law risk where relevant."

    def _authority_hints(self, user_query: str) -> str:
        q = (user_query or "").lower()
        hints = []
        family = self._scenario_family(user_query)
        if family and family.key == "interfaith_marriage_autonomy":
            hints.append("- Adult choice of spouse and interfaith marriage: Shafin Jahan v. Asokan K.M. / Hadiya line should be addressed expressly.")
            hints.append("- Adult choice despite family opposition: Lata Singh v. State of U.P. should be addressed expressly.")
            hints.append("- Police protection against family interference: Laxmibai Chandaragi B. v. State of Karnataka should be addressed expressly.")
            hints.append("- State non-interference with voluntary adult relationship choices: Shambhu Kharwar v. State of Uttar Pradesh should be considered where factually relevant.")
            hints.append("- Statutory anchor: Special Marriage Act, 1954, especially validity after later conversion, relief, and challenge framework, must be named directly.")
            hints.append("- If forced conversion is alleged, identify the applicable state anti-conversion law as a retrieval requirement or authority gap; do not assume a generic national statute.")
            hints.append("- If WhatsApp or chats are central, treat them as electronic evidence requiring admissibility/weight analysis, not automatic proof of coercion.")
            hints.append("- If habeas corpus is filed, address maintainability after an adult's in-court statement and distinguish custody from protection.")
        if family and family.key == "live_in_relationship_maintenance":
            hints.append("- Relationship in the nature of marriage: Indra Sarma v. V.K.V. Sarma should be addressed expressly.")
            hints.append("- Marriage-like live-in criteria: Velusamy v. D. Patchaiammal should be addressed expressly.")
            hints.append("- Maintenance route without formal marriage: Chanmuniya v. Virendra Kumar Singh Kushwaha should be addressed expressly.")
            hints.append("- Statutory anchor: Protection of Women from Domestic Violence Act, 2005, especially section 2(f), must be named directly.")
        if "privacy" in q or "data" in q or "breach" in q:
            hints.append("- Privacy / informational autonomy: Justice K.S. Puttaswamy (Retd.) v. Union of India.")
            hints.append("- Data-security negligence: IT Act section 43A and SPDI Rules should be considered alongside the DPDP Act, 2023.")
        if "consumer" in q and "arbitration" in q:
            hints.append("- Consumer jurisdiction despite arbitration: Emaar MGF / Aftab Singh line of authority should be considered expressly.")
        if "pil" in q or "high court" in q or "maintainability" in q:
            hints.append("- Writ/PIL against private bodies: public-function/public-duty analysis, including Binny Ltd. principles, should be addressed expressly.")
        return "\n".join(hints) or "- Use the strongest named authorities reasonably suggested by the issue map and evidence packet."

    def _required_authority_matrix(self, user_query: str) -> List[Dict[str, str]]:
        family = self._scenario_family(user_query)
        if family and family.key == "interfaith_marriage_autonomy":
            return [
                {
                    "kind": "case",
                    "name": "Shafin Jahan v. Asokan K.M. / Hadiya line",
                    "issue": "adult autonomy and interfaith marriage",
                    "expectation": "retrieved_or_explicit_gap",
                },
                {
                    "kind": "case",
                    "name": "Lata Singh v. State of U.P.",
                    "issue": "adult choice despite family opposition",
                    "expectation": "retrieved_or_explicit_gap",
                },
                {
                    "kind": "case",
                    "name": "Laxmibai Chandaragi B. v. State of Karnataka",
                    "issue": "police protection and family interference",
                    "expectation": "retrieved_or_explicit_gap",
                },
                {
                    "kind": "statute",
                    "name": "Special Marriage Act, 1954",
                    "issue": "SMA marriage validity, later conversion, and annulment framework",
                    "expectation": "retrieved_or_explicit_gap",
                },
                {
                    "kind": "statute",
                    "name": "Applicable state anti-conversion law",
                    "issue": "forced conversion inquiry and proof threshold",
                    "expectation": "explicit_gap_if_state_not_identified",
                },
                {
                    "kind": "case",
                    "name": "Lalita Kumari v. Government of Uttar Pradesh",
                    "issue": "FIR / criminal investigation posture for cognizable allegations",
                    "expectation": "retrieved_or_explicit_gap",
                },
                {
                    "kind": "statute",
                    "name": "Evidence Act / Bharatiya Sakshya Adhiniyam digital evidence framework",
                    "issue": "WhatsApp and electronic communications evidentiary treatment",
                    "expectation": "retrieved_or_explicit_gap",
                },
                {
                    "kind": "concept",
                    "name": "burden of proof for coercion or fraud",
                    "issue": "challenge to the marriage",
                    "expectation": "must_be_explained",
                },
            ]
        if family and family.key == "live_in_relationship_maintenance":
            return [
                {
                    "kind": "case",
                    "name": "Indra Sarma v. V.K.V. Sarma",
                    "issue": "relationship in the nature of marriage",
                    "expectation": "retrieved_or_explicit_gap",
                },
                {
                    "kind": "case",
                    "name": "Velusamy v. D. Patchaiammal",
                    "issue": "marriage-like live-in criteria",
                    "expectation": "retrieved_or_explicit_gap",
                },
                {
                    "kind": "case",
                    "name": "Chanmuniya v. Virendra Kumar Singh Kushwaha",
                    "issue": "maintenance route without formal marriage",
                    "expectation": "retrieved_or_explicit_gap",
                },
                {
                    "kind": "statute",
                    "name": "Protection of Women from Domestic Violence Act, 2005",
                    "issue": "domestic relationship and protection framework",
                    "expectation": "must_be_named",
                },
                {
                    "kind": "statute",
                    "name": "Section 2(f), Protection of Women from Domestic Violence Act, 2005",
                    "issue": "domestic relationship definition",
                    "expectation": "must_be_named",
                },
            ]
        return []

    @staticmethod
    def _format_required_authority_matrix(rows: List[Dict[str, str]]) -> str:
        if not rows:
            return "- No scenario-specific required authority matrix."
        return "\n".join(
            f"- [{row['kind']}] {row['name']} -> {row['issue']} ({row['expectation']})"
            for row in rows
        )

    def _section_catalog(self, user_query: str = "") -> List[Dict[str, str]]:
        contract = self._scenario_debate_contract(user_query)
        return [
            {"section_id": "l1", "title": "Issue Framing", "role": "Issue Framing Bench"},
            {"section_id": "l2", "title": contract["advocate_a_title"], "role": contract["advocate_a_role"]},
            {"section_id": "l3", "title": contract["advocate_b_title"], "role": contract["advocate_b_role"]},
            {"section_id": "l4", "title": "Evidence & Authorities", "role": "Authority Packet Editor"},
            {"section_id": "l5", "title": "Cross-Examination", "role": "Neutral Cross-Examiner"},
            {"section_id": "l6", "title": "Bench Analysis", "role": "The Bench"},
            {"section_id": "l7", "title": "Likely Outcome", "role": "Outcome Bench"},
            {"section_id": "l8", "title": "Risks & Next Steps", "role": "Strategic Advisory Bench"},
        ]

    def _scenario_debate_contract(self, user_query: str) -> Dict[str, str]:
        family = self._scenario_family(user_query)
        if family and family.key == "interfaith_marriage_autonomy":
            return {
                "advocate_a_title": "Advocate A - Family Challenge / Coercion Inquiry",
                "advocate_a_role": "Family-Side Challenger",
                "advocate_b_title": "Advocate B - Adult Autonomy / Marriage Defence",
                "advocate_b_role": "Adult-Autonomy Defence",
                "advocate_a_theory": (
                    "the family-side challenger pressing only legally sustainable points: "
                    "a narrow coercion/fraud inquiry, safety verification, forum control, and proof-based relief. "
                    "Do not treat family objection or communal labels as proof."
                ),
                "advocate_b_theory": (
                    "the adult woman/couple defending autonomy, Special Marriage Act validity, burden of proof, "
                    "and state protection against family interference."
                ),
                "issue_instruction": (
                    "For this interfaith-marriage autonomy scenario, explicitly cover Article 21 autonomy, "
                    "adult-choice jurisprudence, Special Marriage Act validity, later conversion and any second marriage, "
                    "anti-conversion law scrutiny, kidnapping / wrongful confinement allegations, burden of proof, "
                    "in-court statement versus WhatsApp or other digital communications, habeas corpus maintainability, "
                    "legal relevance of 'love jihad', and state duty where the woman fears her family."
                ),
                "outcome_questions": (
                    "1. Can the marriage be challenged or annulled on allegation without concrete evidence?\n"
                    "2. How should the court treat later conversion and a second personal-law marriage after an SMA marriage?\n"
                    "3. What is the evidentiary weight of the adult woman's in-court statement versus prior WhatsApp / digital communications?\n"
                    "4. Does 'love jihad' have independent legal standing?\n"
                    "5. Should habeas / state action prioritize parental concern or the adult woman's autonomy under Article 21?"
                ),
            }
        if family and family.key == "live_in_relationship_maintenance":
            return {
                "advocate_a_title": "Advocate A - Woman / Marriage-Like Relationship Claim",
                "advocate_a_role": "Woman Claimant",
                "advocate_b_title": "Advocate B - No Formal Marriage / Proof-Limits Defence",
                "advocate_b_role": "Respondent Defence",
                "advocate_a_theory": (
                    "the woman claimant arguing that a five-year cohabitation can qualify as a relationship "
                    "in the nature of marriage, supporting Domestic Violence Act protection and any defensible "
                    "maintenance route. Distinguish DV relief from maintenance."
                ),
                "advocate_b_theory": (
                    "the respondent arguing that there was no formal marriage, that marriage-like recognition "
                    "requires proof of cohabitation, holding out, shared household, age/capacity, and legal eligibility, "
                    "and that remedies cannot be granted automatically."
                ),
                "issue_instruction": (
                    "For this live-in relationship scenario, explicitly cover relationship in the nature of marriage, "
                    "Protection of Women from Domestic Violence Act section 2(f), shared household, maintenance route "
                    "without formal marriage, evidence of duration/exclusivity/holding out, forum fit, and cultural "
                    "norms versus statutory protection."
                ),
                "outcome_questions": (
                    "1. Can a live-in relationship be treated as marriage-like under Indian law?\n"
                    "2. How does the Protection of Women from Domestic Violence Act, 2005 apply to a qualifying live-in relationship?\n"
                    "3. Should cultural norms influence legal recognition of such relationships?"
                ),
            }
        return {
            "advocate_a_title": "Advocate A - Claimant / Challenger Case",
            "advocate_a_role": "Claimant / Challenger",
            "advocate_b_title": "Advocate B - Respondent / Defence Case",
            "advocate_b_role": "Respondent / Defence",
            "advocate_a_theory": "the claimant or challenger pressing the strongest legally sustainable case.",
            "advocate_b_theory": "the respondent or defence answering the claimant and pressing the strongest legally sustainable defence.",
            "issue_instruction": "Frame the decisive statutory, constitutional, evidentiary, procedural, forum, and remedy issues raised by the user's exact question.",
            "outcome_questions": "Answer each explicit debatable question in the user's prompt directly and separately.",
        }

    @staticmethod
    def _lineup_prompt_text(catalog: List[Dict[str, str]]) -> str:
        return "\n".join(f"- {item['section_id']}: {item['title']} [{item['role']}]" for item in catalog)

    @staticmethod
    def _count_retrieved_authorities(evidence_packet: str) -> int:
        return evidence_packet.count("score=")

    @staticmethod
    def _quote_warning_flag(text: str) -> bool:
        quote_count = text.count('"')
        return quote_count >= 4 and "extract:" not in text.lower() and "holding / extract:" not in text.lower()

    @staticmethod
    def _overlap_ratio(text_a: str, text_b: str) -> float:
        tokens_a = {tok for tok in re.findall(r"[a-z]{5,}", (text_a or "").lower())}
        tokens_b = {tok for tok in re.findall(r"[a-z]{5,}", (text_b or "").lower())}
        if not tokens_a or not tokens_b:
            return 0.0
        return len(tokens_a & tokens_b) / max(1, min(len(tokens_a), len(tokens_b)))

    def _section_quality_flags(
        self,
        *,
        section_id: str,
        text: str,
        user_query: str,
        issues: List[Dict[str, str]],
        prior_sections: Dict[str, str],
        authority_matrix: List[Dict[str, str]],
        evidence_packet: str,
    ) -> List[str]:
        body = (text or "").strip().lower()
        flags: List[str] = []
        if body.startswith("[llm error]") or body.startswith("[error]"):
            return ["llm_generation_failed"]
        if len(re.sub(r"\W+", "", body)) < 120:
            flags.append("too_thin")
        if self._quote_warning_flag(text):
            flags.append("uncertain_quote_style")
        family = self._scenario_family(user_query)
        if family and any(term in body for term in family.forbidden_carryover_terms if term not in (user_query or "").lower()):
            flags.append("scenario_contamination")
        if section_id == "l1" and family and family.key == "interfaith_marriage_autonomy":
            for phrase in ("article 21", "special marriage act", "coercion", "burden", "love jihad"):
                if phrase not in body:
                    flags.append(f"missing_{phrase.replace(' ', '_')}")
            if "police" not in body and "fir" not in body and "habeas" not in body and "family court" not in body:
                flags.append("missing_forum_split")
            flags.extend(
                self._issue_blueprint_quality_flags(
                    user_query=user_query,
                    text=text,
                    issues=issues,
                    authority_matrix=authority_matrix,
                )
            )
        if section_id == "l1" and family and family.key == "live_in_relationship_maintenance":
            for phrase in ("relationship in the nature of marriage", "domestic violence", "maintenance", "shared household"):
                if phrase not in body:
                    flags.append(f"missing_{phrase.replace(' ', '_')}")
            if "cultural" not in body and "social norms" not in body:
                flags.append("missing_cultural_norms_issue")
        locked_blueprint_present = bool(
            prior_sections.get("level_1_issue_framing")
            or prior_sections.get("l1")
            or "locked issue blueprint" in "\n\n".join(prior_sections.values()).lower()
        )
        if locked_blueprint_present and section_id in {"l2", "l3", "l4", "l6", "l7", "l8"}:
            missing_issue_ids = self._missing_major_issue_ids(text, issues)
            if missing_issue_ids:
                flags.append("missing_major_framed_issues")
                flags.extend(f"missing_framed_issue_{issue_id}" for issue_id in missing_issue_ids[:4])
        if section_id == "l2":
            if family and family.key == "interfaith_marriage_autonomy":
                if "coercion" not in body and "fraud" not in body and "inquiry" not in body:
                    flags.append("missing_challenge_theory")
                if "family" not in body and "complaint" not in body:
                    flags.append("missing_family_side_position")
            if family and family.key == "live_in_relationship_maintenance":
                if "relationship in the nature of marriage" not in body and "marriage-like" not in body:
                    flags.append("missing_marriage_like_claim")
                if "domestic violence" not in body and "section 2(f)" not in body:
                    flags.append("missing_dv_claim")
                if "maintenance" not in body:
                    flags.append("missing_maintenance_claim")
        if section_id == "l3":
            if family and family.key == "interfaith_marriage_autonomy":
                if "article 21" not in body and "autonomy" not in body and "choice" not in body:
                    flags.append("missing_autonomy_theory")
                if "special marriage act" not in body:
                    flags.append("missing_sma_anchor")
                if "protect" not in body and "safety" not in body:
                    flags.append("missing_protection_frame")
            if family and family.key == "live_in_relationship_maintenance":
                if "no formal marriage" not in body and "no legal marriage" not in body and "not automatic" not in body and "proof" not in body:
                    flags.append("missing_non_marriage_defence")
                if "relationship in the nature of marriage" not in body and "marriage-like" not in body:
                    flags.append("missing_marriage_like_test")
        if section_id == "l4":
            if "|" not in text and "issue ->" not in body:
                flags.append("missing_authority_packet_shape")
            if "support strength" not in body and "retrieved" not in body and "authority gap" not in body:
                flags.append("missing_support_strength_labels")
            if not any(status in body for status in ("retrieved", "suggested_but_unverified", "authority_gap")):
                flags.append("missing_exact_retrieval_status")
        if section_id == "l5" and ("overreach" not in body or "missing assumption" not in body):
            flags.append("missing_cross_exam_axes")
        if section_id == "l6" and "authority anchor" not in body:
            flags.append("missing_authority_anchor")
        if section_id == "l7":
            if family and family.key == "interfaith_marriage_autonomy":
                for phrase in ("annul", "love jihad", "article 21"):
                    if phrase not in body:
                        flags.append(f"missing_direct_answer_{phrase.replace(' ', '_')}")
            if family and family.key == "live_in_relationship_maintenance":
                for phrase in ("marriage-like", "domestic violence", "cultural norms"):
                    if phrase not in body:
                        flags.append(f"missing_direct_answer_{phrase.replace(' ', '_')}")
        if section_id == "l8" and ("uncertainty" not in body and "next step" not in body and "risk" not in body):
            flags.append("missing_risk_next_step")
        if authority_matrix:
            authority_names = [row["name"].lower() for row in authority_matrix if row["kind"] in {"case", "statute"}]
            if section_id in {"l1", "l4", "l6", "l7"} and not any(name.split(" v.")[0].lower() in body or name.lower() in body for name in authority_names):
                flags.append("missing_required_authority_reference")
        if "l2" in prior_sections and section_id == "l3":
            if self._overlap_ratio(prior_sections["l2"], text) > 0.72:
                flags.append("too_similar_to_advocate_a")
        if section_id in {"l6", "l7"} and evidence_packet and "no strong retrieval returned" in evidence_packet.lower() and "authority gap" not in body:
            flags.append("missing_explicit_authority_gap")
        if family and family.key == "interfaith_marriage_autonomy" and section_id in {"l6", "l7"}:
            expected = self._complex_interfaith_required_terms(user_query)
            covered = sum(1 for _, synonyms in expected if any(term in body for term in synonyms))
            if covered < max(4, len(expected) // 2):
                flags.append("missing_locked_blueprint_coverage")
        return sorted(set(flags))

    @staticmethod
    def _blocking_section_flags(flags: List[str], section_id: str) -> List[str]:
        blocking: List[str] = []
        for flag in flags:
            if flag in _ADVISORY_QUALITY_FLAGS:
                continue
            if flag in _FATAL_QUALITY_FLAGS or flag in _BLOCKING_QUALITY_FLAGS:
                blocking.append(flag)
                continue
            if flag.startswith("missing_framed_issue_"):
                blocking.append(flag)
                continue
            if section_id in {"l6", "l7"} and flag.startswith("missing_direct_answer_"):
                blocking.append(flag)
                continue
            if section_id == "l1" and (flag.startswith("missing_") or flag == "generic_issue_framing"):
                blocking.append(flag)
        return sorted(set(blocking))

    def _generate_section_with_guardrails(
        self,
        *,
        section_id: str,
        title: str,
        role: str,
        base_prompt: str,
        user_query: str,
        issues: List[Dict[str, str]],
        prior_sections: Dict[str, str],
        authority_matrix: List[Dict[str, str]],
        evidence_packet: str,
        max_tokens: int,
        temperature: float,
        fallback: str = "",
        timeout_seconds: Optional[float] = None,
    ) -> Tuple[str, List[str], int]:
        attempts = 0
        best_text = fallback.strip()
        best_flags = ["empty_generation"]
        prompt = base_prompt
        max_attempts = 2 if fallback else 3
        while attempts < max_attempts:
            attempts += 1
            generated = ""
            if timeout_seconds and timeout_seconds > 0:
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                future = executor.submit(self.llm.generate, prompt, max_tokens, temperature)
                try:
                    generated = (future.result(timeout=timeout_seconds) or "").strip()
                except concurrent.futures.TimeoutError:
                    future.cancel()
                    best_flags = ["llm_generation_timeout"]
                    logger.warning("[CourtDebateStream] section_timeout section_id=%s seconds=%.1f", section_id, timeout_seconds)
                    break
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)
            else:
                generated = (self.llm.generate(prompt, max_tokens=max_tokens, temperature=temperature) or "").strip()
            if generated and _looks_like_reasoning_leak(generated):
                logger.warning("[CourtDebateStream] reasoning_leak section_id=%s attempt=%s - treating as empty", section_id, attempts)
                generated = ""
            if generated:
                best_text = generated
            flags = self._section_quality_flags(
                section_id=section_id,
                text=best_text,
                user_query=user_query,
                issues=issues,
                prior_sections=prior_sections,
                authority_matrix=authority_matrix,
                evidence_packet=evidence_packet,
            )
            best_flags = flags
            blocking_flags = self._blocking_section_flags(flags, section_id)
            if not blocking_flags:
                break
            if fallback:
                fallback_flags = self._section_quality_flags(
                    section_id=section_id,
                    text=fallback,
                    user_query=user_query,
                    issues=issues,
                    prior_sections=prior_sections,
                    authority_matrix=authority_matrix,
                    evidence_packet=evidence_packet,
                )
                if not self._blocking_section_flags(fallback_flags, section_id):
                    return fallback.strip(), fallback_flags, attempts
            prompt = (
                f"{base_prompt}\n\n"
                f"Quality repair for section {section_id} [{role}] required.\n"
                f"Current flags: {', '.join(blocking_flags)}.\n"
                "Rewrite from scratch. Do not repeat the previous side's position. "
                "Name the required authorities directly where relevant. "
                "If support is missing, say 'authority gap - verify before relying' instead of sounding certain.\n"
                f"Current draft to repair:\n{best_text}"
            )
        if fallback and self._blocking_section_flags(best_flags, section_id):
            fallback_flags = self._section_quality_flags(
                section_id=section_id,
                text=fallback,
                user_query=user_query,
                issues=issues,
                prior_sections=prior_sections,
                authority_matrix=authority_matrix,
                evidence_packet=evidence_packet,
            )
            if self._blocking_section_flags(fallback_flags, section_id):
                fallback_flags = [flag for flag in fallback_flags if flag not in self._blocking_section_flags(fallback_flags, section_id)]
            return fallback.strip(), sorted(set(fallback_flags)), attempts
        return (best_text or fallback).strip(), best_flags, attempts

    def _render_integrated_output(self, sections: Dict[str, str]) -> str:
        ordered = [
            ("## Level 1: Issue Framing", sections.get("level_1_issue_framing", "")),
            ("## Level 2: Advocate A - Claimant / Challenger Case", sections.get("level_2_advocate_a", "")),
            ("## Level 3: Advocate B - Respondent / Defence Case", sections.get("level_3_advocate_b", "")),
            ("## Level 4: Evidence & Authority Packet", sections.get("level_4_evidence", "")),
            ("## Level 5: Cross-Examination", sections.get("level_5_cross_examination", "")),
            ("## Level 6: Bench Analysis", sections.get("level_6_final_verdict", "")),
            ("## Level 7: Likely Outcome", sections.get("level_7_likely_outcome", "")),
            ("## Level 8: Open Uncertainties & Strategic Next Steps", sections.get("level_8_deep_analysis", "")),
            ("## Independent Evaluation (Scored by Judge Agent)", sections.get("independent_evaluation", "")),
        ]
        return "\n\n".join(f"{heading}\n{body}".strip() for heading, body in ordered if body)

    def run_debate_integrated(self, user_query: str, session_id: Optional[str] = None, history: str = "", max_tokens: int = 2600) -> str:
        conv_history = self._load_history(session_id, history)
        domain = classify_legal_domain(user_query)
        issues = self._decompose_issues(user_query, domain, conv_history)
        issue_map = self._format_issue_map(issues)
        _, evidence_packet = self._build_evidence_packet(user_query, issues)
        prompt = f"You are in Court Debate Mode for Indian law. Use the issue map and evidence packet. Produce serious, evidence-led legal analysis. Do not fabricate authorities or dates.\n\nIssue map:\n{issue_map}\n\nEvidence packet:\n{evidence_packet}\n\nPrevious context:\n{conv_history or 'None'}\n\nUser query:\n{user_query}\n\nUse exactly these headings:\n## Level 1: Issue Framing\n## Level 2: Advocate A – Claimant / Challenger Case\n## Level 3: Advocate B – Respondent / Defence Case\n## Level 4: Evidence & Authority Packet\n## Level 5: Cross-Examination\n## Level 6: Bench Analysis\n## Level 7: Likely Outcome\n## Level 8: Open Uncertainties & Strategic Next Steps\n## Independent Evaluation (Scored by Judge Agent)"
        result = self.llm.generate(prompt, max_tokens=max_tokens, temperature=0.2, purpose="debate")
        self._save_to_memory(session_id, user_query, result)
        return result

    def run_debate_modular(self, user_query: str, session_id: Optional[str] = None, history: str = "") -> Dict:
        conv_history = self._load_history(session_id, history)
        preplan = self._build_preplan(user_query, session_id, conv_history)
        domain = preplan["legal_domain"]
        side_a = preplan["side_labels"]["a"]
        side_b = preplan["side_labels"]["b"]
        issues = preplan["issue_map"]
        issue_map = self._format_issue_map(issues)
        issue_packets, evidence_packet = self._build_evidence_packet(user_query, issues)
        guardrails = self._current_law_guardrails(user_query)
        authority_hints = self._authority_hints(user_query)
        authority_matrix = self._required_authority_matrix(user_query)
        authority_matrix_text = self._format_required_authority_matrix(authority_matrix)
        debate_contract = self._scenario_debate_contract(user_query)
        shared_context = (
            f"User query:\n{user_query}\n\n"
            f"Scenario family:\n{preplan['scenario_family']}\n\n"
            f"Detected legal domain:\n{domain.upper()}\n\n"
            f"Issue map:\n{issue_map}\n\n"
            f"Evidence packet:\n{evidence_packet}\n\n"
            f"Required authority matrix:\n{authority_matrix_text}\n\n"
            f"Current-law guardrails:\n{guardrails}\n\n"
            f"Authority hints:\n{authority_hints}\n\n"
            f"Conversation history:\n{conv_history or 'None'}"
        )
        lineup = self._lineup_prompt_text(self._section_catalog(user_query))
        sections: Dict[str, str] = {}
        section_flags: Dict[str, List[str]] = {}
        section_attempts: Dict[str, int] = {}

        level_1, section_flags["l1"], section_attempts["l1"] = self._generate_section_with_guardrails(
            section_id="l1",
            title="Issue Framing",
            role="Issue Framing Bench",
            base_prompt=(
                "You are the court's issue-framing bench in an Indian-law courtroom simulation.\n"
                "Output only the Issue Framing section.\n"
                "Group issues under clear headings such as constitutional, statutory, evidence, procedural, and remedy.\n"
                f"{debate_contract['issue_instruction']}\n\n"
                f"{shared_context}\n\nCourtroom lineup:\n{lineup}"
            ),
            user_query=user_query,
            issues=issues,
            prior_sections=sections,
            authority_matrix=authority_matrix,
            evidence_packet=evidence_packet,
            max_tokens=900,
            temperature=0.12,
            fallback=issue_map,
        )
        sections["level_1_issue_framing"] = level_1

        prompt_a = (
            "You are Advocate A in a serious Indian-law court debate.\n"
            f"Side represented: {side_a}. In this case class, that means {debate_contract['advocate_a_theory']}\n"
            "Follow the LOCKED ISSUE BLUEPRINT in order. Do not invent a different issue map.\n"
            "Do not argue the respondent's side except to anticipate and answer it.\n"
            "Use actual legal thresholds, not rhetoric. If support is missing, say 'authority gap - verify before relying'.\n"
            "For each major issue include: position, best point, vulnerability, authority anchor.\n\n"
            f"{shared_context}"
        )

        prompt_b = (
            "You are Advocate B in a serious Indian-law court debate.\n"
            f"Side represented: {side_b}. In this case class, that means {debate_contract['advocate_b_theory']}\n"
            "Follow the LOCKED ISSUE BLUEPRINT in order. Do not invent a different issue map.\n"
            "Directly rebut and defend against the petitioner/claimant case theory without collapsing into it.\n"
            "Use named statutory anchors and leading authorities for this exact scenario family.\n"
            "For each major issue include: position, best point, vulnerability, authority anchor.\n\n"
            f"{shared_context}"
        )

        logger.info("[CourtDebateV2] Dispatching Advocate A and Advocate B in parallel ...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut_a = executor.submit(
                self._generate_section_with_guardrails,
                section_id="l2",
                title=debate_contract["advocate_a_title"],
                role=debate_contract["advocate_a_role"],
                base_prompt=prompt_a,
                user_query=user_query,
                issues=issues,
                prior_sections=sections,
                authority_matrix=authority_matrix,
                evidence_packet=evidence_packet,
                max_tokens=1400,
                temperature=0.18,
            )
            fut_b = executor.submit(
                self._generate_section_with_guardrails,
                section_id="l3",
                title=debate_contract["advocate_b_title"],
                role=debate_contract["advocate_b_role"],
                base_prompt=prompt_b,
                user_query=user_query,
                issues=issues,
                prior_sections=sections,
                authority_matrix=authority_matrix,
                evidence_packet=evidence_packet,
                max_tokens=1500,
                temperature=0.18,
            )
            a_out, section_flags["l2"], section_attempts["l2"] = fut_a.result()
            b_out, section_flags["l3"], section_attempts["l3"] = fut_b.result()

        sections["level_2_advocate_a"] = a_out
        sections["level_3_advocate_b"] = b_out

        evidence_section, section_flags["l4"], section_attempts["l4"] = self._generate_section_with_guardrails(
            section_id="l4",
            title="Evidence & Authorities",
            role="Authority Packet Editor",
            base_prompt=(
                "You are the authority packet editor for an Indian-law courtroom debate.\n"
                "Output only a compact Markdown table with columns: Issue | Authority / Statute | Proposition | Support Strength | Forum Relevance | Retrieval Status.\n"
                "Use the locked decision issues as the table rows where possible.\n"
                "Mark each row as retrieved, suggested-but-unverified, or authority gap. Do not use quote-style wording unless the extract is actually retrieved.\n\n"
                f"{shared_context}"
            ),
            user_query=user_query,
            issues=issues,
            prior_sections=sections,
            authority_matrix=authority_matrix,
            evidence_packet=evidence_packet,
            max_tokens=1200,
            temperature=0.08,
            fallback=evidence_packet,
        )
        sections["level_4_evidence"] = evidence_section

        cross_exam, section_flags["l5"], section_attempts["l5"] = self._generate_section_with_guardrails(
            section_id="l5",
            title="Cross-Examination",
            role="Neutral Cross-Examiner",
            base_prompt=(
                "You are the neutral cross-examiner in an Indian legal dispute.\n"
                "Output only the cross-examination section.\n"
                "For Advocate A and Advocate B separately, use these exact axes: Overreach, Missing Assumption, Weak Forum Fit, Unsupported Proposition.\n"
                "Tie each critique back to the evidence packet or authority matrix.\n\n"
                f"{shared_context}\n\nAdvocate A:\n{a_out}\n\nAdvocate B:\n{b_out}"
            ),
            user_query=user_query,
            issues=issues,
            prior_sections=sections,
            authority_matrix=authority_matrix,
            evidence_packet=evidence_packet,
            max_tokens=950,
            temperature=0.12,
        )
        sections["level_5_cross_examination"] = cross_exam

        bench_analysis, section_flags["l6"], section_attempts["l6"] = self._generate_section_with_guardrails(
            section_id="l6",
            title="Bench Analysis",
            role="The Bench",
            base_prompt=(
                "You are the bench in an Indian legal dispute.\n"
                "Resolve each major issue separately. For each issue, state which side is stronger and why.\n"
                "Use the same issue order as the LOCKED ISSUE BLUEPRINT.\n"
                "Under each issue include an explicit line starting with 'Authority anchor:'.\n"
                "If the evidence packet is thin, say so directly instead of sounding certain.\n\n"
                f"{shared_context}\n\nAdvocate A:\n{a_out}\n\nAdvocate B:\n{b_out}\n\nCross-examination:\n{cross_exam}"
            ),
            user_query=user_query,
            issues=issues,
            prior_sections=sections,
            authority_matrix=authority_matrix,
            evidence_packet=evidence_packet,
            max_tokens=1350,
            temperature=0.12,
        )
        sections["level_6_final_verdict"] = bench_analysis

        likely_outcome, section_flags["l7"], section_attempts["l7"] = self._generate_section_with_guardrails(
            section_id="l7",
            title="Likely Outcome",
            role="Outcome Bench",
            base_prompt=(
                "You are the outcome bench in an Indian legal dispute.\n"
                "Answer these questions directly and explicitly:\n"
                f"{debate_contract['outcome_questions']}\n"
                "Then answer the locked issue blueprint in order, especially any conversion, criminal-process, evidence, and habeas issues.\n"
                "Then state likely forum outcome and short remedy path.\n\n"
                f"{shared_context}\n\nBench analysis:\n{bench_analysis}"
            ),
            user_query=user_query,
            issues=issues,
            prior_sections=sections,
            authority_matrix=authority_matrix,
            evidence_packet=evidence_packet,
            max_tokens=900,
            temperature=0.12,
        )
        sections["level_7_likely_outcome"] = likely_outcome

        uncertainties, section_flags["l8"], section_attempts["l8"] = self._generate_section_with_guardrails(
            section_id="l8",
            title="Risks & Next Steps",
            role="Strategic Advisory Bench",
            base_prompt=(
                "You are the strategic advisory bench in an Indian legal dispute.\n"
                "Output only the risks and next steps section.\n"
                "Use the locked issue blueprint to separate legal uncertainty, evidence uncertainty, forum uncertainty, and authority gaps.\n"
                "State unresolved uncertainty, what could change the answer, and the most defensible immediate next legal steps.\n\n"
                f"{shared_context}\n\nBench analysis:\n{bench_analysis}\n\nLikely outcome:\n{likely_outcome}"
            ),
            user_query=user_query,
            issues=issues,
            prior_sections=sections,
            authority_matrix=authority_matrix,
            evidence_packet=evidence_packet,
            max_tokens=750,
            temperature=0.12,
        )
        sections["level_8_deep_analysis"] = uncertainties
        independent_evaluation = self.llm.generate(
            f"You are an internal evaluator scoring this debate objectively.\nUser query: {user_query}\nIssue map:\n{issue_map}\nAdvocate A:\n{a_out}\nAdvocate B:\n{b_out}\nBench analysis:\n{bench_analysis}\nEvidence section:\n{evidence_section}\nReturn only these lines:\n- Positive Advocate Strength: X/10\n- Negative Advocate Strength: X/10\n- True Balance Between Sides: X/10\n- Quality of Final Conclusion & Strategy: X/10\n- Evidence Integration: X/10\n- Overall Production Usefulness: X/10\n**Final Grade:** X/10",
            max_tokens=500,
            temperature=0.1,
        )

        sections = {
            "level_1_issue_framing": level_1.strip(),
            "level_2_advocate_a": a_out.strip(),
            "level_3_advocate_b": b_out.strip(),
            "level_4_evidence": evidence_section.strip() or evidence_packet,
            "level_5_cross_examination": cross_exam.strip(),
            "level_6_final_verdict": bench_analysis.strip(),
            "level_7_likely_outcome": likely_outcome.strip(),
            "level_8_deep_analysis": uncertainties.strip(),
            "independent_evaluation": independent_evaluation.strip() or "Internal evaluation unavailable.",
        }
        quality_report = self._quality_report(user_query, issues, sections, evidence_packet)
        quality_report["section_flags"] = section_flags
        quality_report["section_attempts"] = section_attempts
        quality_report["required_authority_matrix"] = authority_matrix

        full_text = self._render_integrated_output(sections)
        self._save_to_memory(session_id, user_query, full_text)
        return {
            **sections,
            "level_5_7_judge": "\n\n".join(s for s in [sections["level_5_cross_examination"], sections["level_6_final_verdict"], sections["level_7_likely_outcome"], sections["level_8_deep_analysis"], sections["independent_evaluation"]] if s),
            "legal_domain": domain,
            "scenario_family": preplan["scenario_family"],
            "issue_map": issues,
            "issue_packets": issue_packets,
            "quality_report": quality_report,
        }
    def _stream_modular_sections(self, user_query: str, session_id: Optional[str] = None, history: str = "") -> Generator[str, None, None]:
        """Generate each court-debate layer independently and yield completed section packets."""
        conv_history = self._load_history(session_id, history)
        preplan = self._build_preplan(user_query, session_id, conv_history)
        domain = preplan["legal_domain"]
        side_a = preplan["side_labels"]["a"]
        side_b = preplan["side_labels"]["b"]
        issues = preplan["issue_map"]
        issue_map = self._format_issue_map(issues)
        guardrails = self._current_law_guardrails(user_query)
        authority_hints = self._authority_hints(user_query)
        authority_matrix = self._required_authority_matrix(user_query)
        authority_matrix_text = self._format_required_authority_matrix(authority_matrix)
        sections: Dict[str, str] = {}
        debate_contract = self._scenario_debate_contract(user_query)
        section_catalog = self._section_catalog(user_query)
        request_id = session_id or f"cd_stream_{int(time.time())}"
        stream_started = time.time()
        hard_budget_seconds = float(os.getenv("COURT_DEBATE_STREAM_HARD_BUDGET_SECONDS", "360"))
        section_flags_by_id: Dict[str, List[str]] = {}
        section_elapsed_by_id: Dict[str, float] = {}
        fallback_by_id: Dict[str, bool] = {}
        authority_status_counts: Dict[str, int] = {"retrieved": 0, "suggested_but_unverified": 0, "authority_gap": 0}

        def emit_packet(
            section_id: str,
            title: str,
            role: str,
            body: str,
            quality_flags: List[str],
            authority_count: int,
            *,
            fallback_used: bool = False,
        ) -> str:
            status = "error" if "llm_generation_failed" in quality_flags else "complete"
            card_index = next(
                (idx for idx, item in enumerate(section_catalog, start=1) if item["section_id"] == section_id),
                0,
            )
            return json.dumps(
                {
                    "event_type": "complete",
                    "section_id": section_id,
                    "title": title,
                    "role": role,
                    "status": status,
                    "body": body.strip(),
                    "quality_flags": quality_flags,
                    "authority_count": authority_count,
                    "authority_status_counts": authority_status_counts,
                    "elapsed_seconds": round(time.time() - stream_started, 3),
                    "fallback_used": fallback_used,
                    "card_index": card_index,
                    "card_total": len(section_catalog),
                    "request_id": request_id,
                    "scenario_family": preplan["scenario_family"],
                    "legal_domain": domain,
                    "level": f"## {title}",
                    "chunk": body.strip(),
                    "key_points": _extract_key_points(body),
                    "thought": _build_section_thought(section_id, role, body, _extract_key_points(body)),
                }
            ) + "\n"

        def emit_status(section_id: str, title: str, role: str, message: str) -> str:
            return json.dumps(
                {
                    "event_type": "working",
                    "section_id": section_id,
                    "title": title,
                    "role": role,
                    "status": "working",
                    "body": "",
                    "quality_flags": [],
                    "authority_count": 0,
                    "request_id": request_id,
                    "scenario_family": preplan["scenario_family"],
                    "legal_domain": domain,
                    "message": message,
                    "elapsed_seconds": round(time.time() - stream_started, 3),
                }
            ) + "\n"

        def emit_quality_warning(section_id: str, title: str, role: str, flags: List[str], fallback_used: bool) -> str:
            return json.dumps(
                {
                    "event_type": "quality_warning",
                    "section_id": section_id,
                    "title": title,
                    "role": role,
                    "status": "quality_warning",
                    "quality_flags": flags,
                    "fallback_used": fallback_used,
                    "request_id": request_id,
                    "message": "Quality guardrail used a safe deterministic fallback." if fallback_used else "Quality guardrail noted non-blocking warnings.",
                    "elapsed_seconds": round(time.time() - stream_started, 3),
                }
            ) + "\n"

        def log_section(section_id: str, title: str, started_at: float, body: str, quality_flags: List[str], authority_count: int, attempts: int) -> None:
            section_flags_by_id[section_id] = quality_flags
            section_elapsed_by_id[section_id] = round(time.time() - started_at, 3)
            logger.info(
                "[CourtDebateStream] section_complete request_id=%s scenario_family=%s section_id=%s title=%s elapsed=%.2fs chars=%s authority_count=%s attempts=%s flags=%s",
                request_id,
                preplan["scenario_family"],
                section_id,
                title,
                time.time() - started_at,
                len(body or ""),
                authority_count,
                attempts,
                ",".join(quality_flags) if quality_flags else "none",
            )

        shared_context_base = (
            f"User query:\n{user_query}\n\n"
            f"Scenario family:\n{preplan['scenario_family']}\n\n"
            f"Detected legal domain:\n{domain.upper()}\n\n"
            f"Issue map:\n{issue_map}\n\n"
            f"Required authority matrix:\n{authority_matrix_text}\n\n"
            f"Current-law guardrails:\n{guardrails}\n\n"
            f"Authority hints:\n{authority_hints}\n\n"
            f"RECORD FACTS (treat as admitted; never contradict or silently correct them):\n\n"
            f"- Use the exact timelines, amounts, dates and durations stated in the user query (e.g. if production took 36 hours, the section must address the 24-hour rule violation, not assume compliance).\n\n"
            f"- If a stated fact establishes a statutory violation, the section must say so explicitly and cite the provision.\n\n"
            f"- If a stated fact removes an offence ingredient (e.g. voluntary adult marriage negating kidnapping), the section must say so.\n\n\n\n"
            f"Conversation history:\n{conv_history or 'None'}"
        )

        issue_packets: List[Dict[str, Any]]
        yield emit_status("l1", "Issue Framing", "Issue Framing Bench", "Classifying scenario family")
        yield emit_status("l1", "Issue Framing", "Issue Framing Bench", "Building issue blueprint")
        yield emit_status("l1", "Issue Framing", "Issue Framing Bench", "Checking statutes and forums")
        issue_packets, evidence_packet, evidence_timed_out = self._build_stream_evidence_packet(user_query, issues)
        authority_count = self._count_retrieved_authorities(evidence_packet)
        authority_status_rows = self._issue_authority_status_rows(
            issues=issues,
            issue_packets=issue_packets,
            authority_matrix=authority_matrix,
            user_query=user_query,
        )
        authority_status_counts = self._authority_status_counts(authority_status_rows)
        preplan["authority_status_rows"] = authority_status_rows
        if evidence_timed_out:
            authority_count = 0
        yield emit_status("l1", "Issue Framing", "Issue Framing Bench", "Validating Issue Framing")

        started_at = time.time()
        level_1, l1_blueprint_flags, l1_attempts = self._build_issue_blueprint(
            user_query=user_query,
            preplan=preplan,
            guardrails=guardrails,
            authority_hints=authority_hints,
            authority_matrix_text=authority_matrix_text,
            evidence_packet=evidence_packet,
        )
        preplan["issue_blueprint"] = level_1
        preplan["issue_coverage"] = self._issue_coverage_map(level_1, issues)
        preplan["authority_requirements"] = authority_matrix
        preplan["evidence_questions"] = [issue["question"] for issue in issues]
        preplan["quality_flags"] = l1_blueprint_flags
        sections["level_1_issue_framing"] = level_1
        l1_flags = sorted(
            set(
                l1_blueprint_flags
                + self._section_quality_flags(
                    section_id="l1",
                    text=level_1,
                    user_query=user_query,
                    issues=issues,
                    prior_sections=sections,
                    authority_matrix=authority_matrix,
                    evidence_packet=evidence_packet,
                )
            )
        )
        log_section("l1", section_catalog[0]["title"], started_at, level_1, l1_flags, authority_count, l1_attempts)
        if l1_flags:
            yield emit_quality_warning("l1", section_catalog[0]["title"], section_catalog[0]["role"], l1_flags, False)
        yield emit_packet("l1", section_catalog[0]["title"], section_catalog[0]["role"], level_1, l1_flags, authority_count)

        shared_context = (
            f"{shared_context_base}\n\n"
            f"LOCKED ISSUE BLUEPRINT - all later cards must follow this frame and issue order:\n{level_1}\n\n"
            f"Per-issue authority status rows (use exactly these status labels):\n{json.dumps(authority_status_rows, ensure_ascii=False)}\n\n"
            f"Evidence packet:\n{evidence_packet}"
        )

        def generate_streamed(section_index: int, prompt: str, max_tokens: int, temperature: float, fallback: str = "") -> str:
            section = section_catalog[section_index]
            started = time.time()
            section_id = section["section_id"]
            deterministic_fallback = fallback or self._fallback_for_section(
                section_id=section_id,
                user_query=user_query,
                issues=issues,
                authority_status_rows=authority_status_rows,
                debate_contract=debate_contract,
                evidence_timed_out=evidence_timed_out,
            )
            if section_id == "l4":
                text = deterministic_fallback
                flags = self._section_quality_flags(
                    section_id=section_id,
                    text=text,
                    user_query=user_query,
                    issues=issues,
                    prior_sections=sections,
                    authority_matrix=authority_matrix,
                    evidence_packet=evidence_packet,
                )
                attempts = 0
                fallback_used = True
            elif time.time() - stream_started >= hard_budget_seconds:
                text = deterministic_fallback
                flags = []
                attempts = 0
                fallback_used = True
                logger.warning("[CourtDebateStream] hard_budget_fallback section_id=%s budget=%.1fs", section_id, hard_budget_seconds)
            else:
                text, flags, attempts = self._generate_section_with_guardrails(
                    section_id=section_id,
                    title=section["title"],
                    role=section["role"],
                    base_prompt=prompt,
                    user_query=user_query,
                    issues=issues,
                    prior_sections=sections,
                    authority_matrix=authority_matrix,
                    evidence_packet=evidence_packet,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    fallback=deterministic_fallback,
                    timeout_seconds=_CARD_TIMEOUT_SECONDS.get(section_id),
                )
                fallback_used = text.strip() == deterministic_fallback.strip()
            key = {
                "l2": "level_2_advocate_a",
                "l3": "level_3_advocate_b",
                "l4": "level_4_evidence",
                "l5": "level_5_cross_examination",
                "l6": "level_6_final_verdict",
                "l7": "level_7_likely_outcome",
                "l8": "level_8_deep_analysis",
            }[section_id]
            sections[key] = text
            blocking = self._blocking_section_flags(flags, section_id)
            if blocking and deterministic_fallback.strip() != text.strip():
                text = deterministic_fallback
                sections[key] = text
                flags = [
                    flag for flag in self._section_quality_flags(
                        section_id=section_id,
                        text=text,
                        user_query=user_query,
                        issues=issues,
                        prior_sections=sections,
                        authority_matrix=authority_matrix,
                        evidence_packet=evidence_packet,
                    )
                    if flag not in self._blocking_section_flags(
                        self._section_quality_flags(
                            section_id=section_id,
                            text=text,
                            user_query=user_query,
                            issues=issues,
                            prior_sections=sections,
                            authority_matrix=authority_matrix,
                            evidence_packet=evidence_packet,
                        ),
                        section_id,
                    )
                ]
                fallback_used = True
            fallback_by_id[section_id] = fallback_used
            log_section(section_id, section["title"], started, text, flags, authority_count, attempts)
            return emit_packet(section_id, section["title"], section["role"], text, flags, authority_count, fallback_used=fallback_used)

        yield emit_status(section_catalog[1]["section_id"], section_catalog[1]["title"], section_catalog[1]["role"], "Drafting Advocate A's completed submission.")
        yield generate_streamed(
            1,
            (
                "You are Advocate A in a serious Indian-law court debate.\n"
                f"Side represented: {side_a}. In this case class, that means {debate_contract['advocate_a_theory']}\n"
                "Do not argue the respondent's side except to anticipate and answer it.\n"
                "Use actual legal thresholds, not rhetoric. If support is missing, say 'authority gap - verify before relying'.\n"
                "For each major issue include: position, best point, vulnerability, authority anchor.\n\n"
                f"{shared_context}"
            ),
            1400,
            0.18,
        )
        a_out = sections["level_2_advocate_a"]

        yield emit_status(section_catalog[2]["section_id"], section_catalog[2]["title"], section_catalog[2]["role"], "Drafting Advocate B's completed rebuttal.")
        yield generate_streamed(
            2,
            (
                "You are Advocate B in a serious Indian-law court debate.\n"
                f"Side represented: {side_b}. In this case class, that means {debate_contract['advocate_b_theory']}\n"
                "Directly rebut Advocate A's strongest case without collapsing into it.\n"
                "Use named statutory anchors and leading authorities for this exact scenario family.\n"
                "For each major issue include: position, best point, vulnerability, authority anchor.\n\n"
                f"{shared_context}\n\nAdvocate A draft to rebut:\n{a_out}"
            ),
            1500,
            0.18,
        )
        b_out = sections["level_3_advocate_b"]

        yield emit_status(section_catalog[3]["section_id"], section_catalog[3]["title"], section_catalog[3]["role"], "Building the authority packet.")
        yield generate_streamed(
            3,
            (
                "You are the authority packet editor for an Indian-law courtroom debate.\n"
                "Output only a compact Markdown table with columns: Issue | Authority / Statute | Proposition | Support Strength | Forum Relevance | Retrieval Status.\n"
                "Map every framed issue in the locked order. Retrieval Status must be exactly one of: retrieved, suggested_but_unverified, authority_gap.\n"
                "Do not use quote-style wording unless the extract is actually retrieved.\n\n"
                f"{shared_context}"
            ),
            1200,
            0.08,
            "",
        )

        yield emit_status(section_catalog[4]["section_id"], section_catalog[4]["title"], section_catalog[4]["role"], "Testing both sides through cross-examination.")
        yield generate_streamed(
            4,
            (
                "You are the neutral cross-examiner in an Indian legal dispute.\n"
                "Output only the cross-examination section.\n"
                "For Advocate A and Advocate B separately, use these exact axes: Overreach, Missing Assumption, Weak Forum Fit, Unsupported Proposition.\n"
                "Tie each critique back to the evidence packet or authority matrix.\n\n"
                f"{shared_context}\n\nAdvocate A:\n{a_out}\n\nAdvocate B:\n{b_out}"
            ),
            950,
            0.12,
        )
        cross_exam = sections["level_5_cross_examination"]

        yield emit_status(section_catalog[5]["section_id"], section_catalog[5]["title"], section_catalog[5]["role"], "Preparing the bench analysis.")
        yield generate_streamed(
            5,
            (
                "You are the bench in an Indian legal dispute.\n"
                "Resolve each major issue separately. For each issue, state which side is stronger and why.\n"
                "Under each issue include an explicit line starting with 'Authority anchor:'.\n"
                "If the evidence packet is thin, say so directly instead of sounding certain.\n\n"
                f"{shared_context}\n\nAdvocate A:\n{a_out}\n\nAdvocate B:\n{b_out}\n\nCross-examination:\n{cross_exam}"
            ),
            1350,
            0.12,
        )
        bench_analysis = sections["level_6_final_verdict"]

        yield emit_status(section_catalog[6]["section_id"], section_catalog[6]["title"], section_catalog[6]["role"], "Writing the likely outcome.")
        yield generate_streamed(
            6,
            (
                "You are the outcome bench in an Indian legal dispute.\n"
                "Answer these questions directly and explicitly:\n"
                f"{debate_contract['outcome_questions']}\n"
                "Then state likely forum outcome and short remedy path.\n\n"
                f"{shared_context}\n\nBench analysis:\n{bench_analysis}"
            ),
            900,
            0.12,
        )
        likely_outcome = sections["level_7_likely_outcome"]

        yield emit_status(section_catalog[7]["section_id"], section_catalog[7]["title"], section_catalog[7]["role"], "Finalizing risks and next steps.")
        yield generate_streamed(
            7,
            (
                "You are the strategic advisory bench in an Indian legal dispute.\n"
                "Output only the risks and next steps section.\n"
                "State unresolved uncertainty, what could change the answer, and the most defensible immediate next legal steps.\n\n"
                f"{shared_context}\n\nBench analysis:\n{bench_analysis}\n\nLikely outcome:\n{likely_outcome}"
            ),
            750,
            0.12,
        )

        full_text = self._render_integrated_output(
            {
                "level_1_issue_framing": level_1,
                **sections,
                "independent_evaluation": "",
            }
        )
        completed_section_keys = {
            "level_1_issue_framing",
            "level_2_advocate_a",
            "level_3_advocate_b",
            "level_4_evidence",
            "level_5_cross_examination",
            "level_6_final_verdict",
            "level_7_likely_outcome",
            "level_8_deep_analysis",
        }
        completed_count = sum(1 for key in completed_section_keys if key in sections)
        all_flags = [flag for flags in section_flags_by_id.values() for flag in flags]
        blocking_left = [
            flag
            for section_id, flags in section_flags_by_id.items()
            for flag in self._blocking_section_flags(flags, section_id)
        ]
        self._last_stream_quality_summary = {
            "completed_count": completed_count,
            "card_total": len(section_catalog),
            "section_flags": section_flags_by_id,
            "section_elapsed_seconds": section_elapsed_by_id,
            "fallback_used": fallback_by_id,
            "authority_status_counts": authority_status_counts,
            "elapsed_seconds": round(time.time() - stream_started, 3),
            "gate_passed": completed_count == len(section_catalog) and not blocking_left,
            "estimated_quality_score": max(0, round(10 - (0.6 * len(blocking_left)) - (0.15 * len(all_flags)), 1)),
        }
        self._save_to_memory(session_id, user_query, full_text)

    def run_debate_elite(self, user_query: str, session_id: Optional[str] = None, history: str = "") -> Dict:
        conv_history = self._load_history(session_id, history)
        domain = classify_legal_domain(user_query)
        strategy = os.getenv("COURT_DEBATE_ELITE_STRATEGY", "compact").strip().lower()
        side_a, side_b = self._infer_sides(user_query)
        issues = (
            self._fallback_issue_map(user_query)
            if strategy != "sequential"
            else self._decompose_issues(user_query, domain, conv_history)
        )
        if strategy != "sequential":
            issues = issues[: int(os.getenv("COURT_DEBATE_ELITE_COMPACT_MAX_ISSUES", "5"))]
        issue_map = self._format_issue_map(issues)
        issue_packets, evidence_packet = self._build_evidence_packet(
            user_query,
            issues,
            n_per_issue=(1 if strategy != "sequential" else 4),
        )
        retrieved_rows = self._authority_rows_from_issue_packets(issue_packets)
        resolver_docs = []
        for packet in issue_packets:
            resolver_docs.extend(packet.get("docs", []))
        authority_bundle = self.authority_resolver.build_bundle(user_query, issues, resolver_docs)
        seed_rows, seed_packet = self._seed_authority_rows(user_query, issues)
        canonical_rows = authority_bundle.get("verified_authorities", [])
        seen_authority_ids = set()
        authority_table: List[Dict[str, Any]] = []
        for row in canonical_rows + retrieved_rows + seed_rows:
            row_id = row.get("id") or row.get("case_id") or row.get("display_name")
            if row_id in seen_authority_ids:
                continue
            seen_authority_ids.add(row_id)
            authority_table.append(row)
        authority_table_text = self._format_authority_table(authority_table)
        guardrails = self._current_law_guardrails(user_query)
        authority_hints = self._authority_hints(user_query)
        clarification_questions = self._elite_clarification_questions(user_query, issue_map)

        elite_context = f"""
User query:
{user_query}

Conversation history:
{conv_history or 'None'}

Legal domain:
{domain}

Issue map:
{issue_map}

Retrieved evidence packet:
{evidence_packet}

Mandatory authority seed packet:
{seed_packet}

Authority table:
{authority_table_text}

Issue-authority matrix:
{json.dumps(authority_bundle.get("issue_authority_matrix", []), ensure_ascii=False)}

Remedy-authority matrix:
{json.dumps(authority_bundle.get("remedy_authority_matrix", []), ensure_ascii=False)}

Current-law guardrails:
{guardrails}

Authority hints:
{authority_hints}

Ethical persuasion rules:
- Use empathy, dignity, fear, institutional consequences, and equities as lawful advocacy only.
- Do not stereotype any community.
- Do not treat family objection as evidence of coercion.
- If an authority is marked required_but_not_retrieved, identify it as an authority gap, not as retrieved proof.
"""

        if strategy != "sequential":
            compact_prompt = f"""You are a senior Indian High Court bench simulator and courtroom strategy editor.
Produce a complete Court Debate Elite answer in ONE response. This endpoint runs behind Azure App Service, so be dense and precise while preserving court quality.

Mandatory output headings, exactly as written:
## Level 1: Issue Framing and Clarification Gate
## Level 2: Authority Table and Source Discipline
## Level 3: Petitioner / Claimant Submissions
## Level 4: Respondent / Defence Submissions
## Level 5: Rebuttal and Sur-Rebuttal
## Level 6: Bench Questions and Cross-Examination
## Level 7: Ethical Persuasion and Human-Impact Analysis
## Level 8: Final Bench Ruling, Remedies, and Alternative Outcomes
## Independent Evaluation (Scored by Judge Agent)

Non-negotiable requirements:
- In Level 1, format as a clean numbered list (1 through 5) reproducing exactly these 5 clarification questions and no extra clarification questions:
{clarification_questions}
- Frame issues in constitutional, statutory, procedural, evidentiary, remedy, and public-order buckets.
- In Level 3 and 4 submissions and Level 8 ruling, clearly maintain the procedural distinction between:
  (A) The College Dress-Code Writ (Articles 14, 19, 21, 25, essential religious practice, and institutional discipline under Aishat Shifa).
  (B) The Adult Interfaith Marriage & Anti-Conversion Challenge (SMA validity, Article 21 personal autonomy, quashing surveillance under Puttaswamy, and dismissing parent-initiated Habeas Corpus under Shafin Jahan and Laxmibai Chandaragi).
- Use the authority table. If an authority is marked required_but_not_retrieved, label it as "authority gap - verify before relying"; do not pretend it was retrieved.
- Include petitioner/claimant submissions, respondent/state/defence submissions, rebuttal, and sur-rebuttal.
- Bench questions must test facts, law, proportionality, remedies, maintainability, public order, and institutional consequences.
- Human-impact analysis must cover dignity, autonomy, fear, education/liberty impact, public-order anxiety, institutional discipline, chilling effect, and practical consequences where relevant.
- Use emotional framing only as ethical lawful advocacy; no communal stereotyping, manipulation, or unsupported character attack.
- Strict constitutional accuracy: Cite genuine Indian constitutional provisions accurately (Article 14 for non-arbitrariness/reasonable classification, Article 19(1)(a) for expression, Article 21 for autonomy and dignity, Article 25(1) for religious conscience; never cite non-existent clauses such as Article 14(1)(a)).
- In Level 6 Bench Questions, precisely distinguish party counsel (e.g. 'To Counsel for Petitioner-Students', 'To Counsel for Complainant-Parents', 'To Counsel for the State/College').
- Final ruling must state confidence, specific remedies (interim protection, circular amendment, surveillance quashing), alternative outcomes if facts differ (such as split-bench reference or demonstrated disorder), and unsupported authority/citation risk.
- Do not output internal thinking or planning traces. Begin your response directly with the heading '## Level 1: Issue Framing and Clarification Gate'.

Context:
{elite_context}
"""
            compact_text = self.llm.generate(
                compact_prompt,
                max_tokens=int(os.getenv("COURT_DEBATE_ELITE_COMPACT_MAX_TOKENS", "3800")),
                temperature=0.12,
                purpose=os.getenv("COURT_DEBATE_ELITE_COMPACT_PURPOSE", "fast"),
            )
            if compact_text.startswith("[ERROR]") or compact_text.startswith("[LLM ERROR]"):
                compact_text = "\n\n".join(
                    [
                        "## Level 1: Issue Framing and Clarification Gate\n"
                        f"{clarification_questions}\n\n"
                        "Decision Issues: constitutional rights, statutory authority, criminal-process safeguards, "
                        "habeas maintainability, evidence, public order, and remedies remain contested.",
                        "## Level 2: Authority Table and Source Discipline\n"
                        f"{authority_table_text}\n\n"
                        "The LLM route failed; treat every non-retrieved authority as an authority gap.",
                        "## Level 3: Petitioner / Claimant Submissions\n"
                        "LLM generation failed before legal submissions could be produced.",
                        "## Level 4: Respondent / Defence Submissions\n"
                        "LLM generation failed before respondent submissions could be produced.",
                        "## Level 5: Rebuttal and Sur-Rebuttal\n"
                        "LLM generation failed before rebuttal and sur-rebuttal could be produced.",
                        "## Level 6: Bench Questions and Cross-Examination\n"
                        "Bench question: what evidence, statutory basis, proportionality analysis, and remedy record exists?",
                        "## Level 7: Ethical Persuasion and Human-Impact Analysis\n"
                        "Human impact, dignity, autonomy, public order, institutional discipline, and chilling effect require analysis.",
                        "## Level 8: Final Bench Ruling, Remedies, and Alternative Outcomes\n"
                        "No merits ruling should be treated as reliable because generation failed.",
                        "## Independent Evaluation (Scored by Judge Agent)\n"
                        "Overall Court-Level Quality: 0/100 due LLM/provider failure.",
                    ]
                )

            clean_compact_text = compact_text
            clean_compact_text = re.sub(r"(?is)Here's a thinking process:.*?(?=\n##\s+Level|\Z)", "", clean_compact_text)
            clean_compact_text = re.sub(r"(?is)<think>.*?</think>", "", clean_compact_text)
            heading_map = {
                "level_1_issue_framing": "Level 1: Issue Framing and Clarification Gate",
                "level_2_authority_table": "Level 2: Authority Table and Source Discipline",
                "level_3_petitioner_submissions": "Level 3: Petitioner / Claimant Submissions",
                "level_4_respondent_submissions": "Level 4: Respondent / Defence Submissions",
                "level_5_rebuttal_sur_rebuttal": "Level 5: Rebuttal and Sur-Rebuttal",
                "level_6_bench_questions": "Level 6: Bench Questions and Cross-Examination",
                "level_7_persuasion_analysis": "Level 7: Ethical Persuasion and Human-Impact Analysis",
                "level_8_final_ruling": "Level 8: Final Bench Ruling, Remedies, and Alternative Outcomes",
                "independent_evaluation": "Independent Evaluation (Scored by Judge Agent)",
            }
            sections = {
                key: self._extract_elite_section(clean_compact_text, heading).strip()
                for key, heading in heading_map.items()
            }
            for key, heading in heading_map.items():
                if not sections[key]:
                    sections[key] = clean_compact_text.strip() if key == "level_1_issue_framing" else f"{heading}: not separately generated."
            return self._build_elite_response(
                user_query=user_query,
                session_id=session_id,
                domain=domain,
                issues=issues,
                issue_packets=issue_packets,
                evidence_packet=evidence_packet,
                seed_packet=seed_packet,
                authority_table=authority_table,
                authority_table_text=authority_table_text,
                clarification_questions=clarification_questions,
                sections=sections,
                generation_strategy="compact_single_call",
                authority_bundle=authority_bundle,
            )

        level_1 = self.llm.generate(
            f"""You are a senior High Court briefing counsel.
Write Level 1 only.

Required structure:
- Five Clarification Questions: reproduce exactly these 5 questions:
{clarification_questions}
- Decision Issues: group by constitutional, statutory, procedural, evidentiary, remedy, and public-order issues.
- Burden / Standard: identify who must prove what.
- What the bench will care about: 5 crisp points.

Context:
{elite_context}
""",
            max_tokens=1100,
            temperature=0.12,
            purpose="debate",
        )

        authority_section = self.llm.generate(
            f"""You are the authority-table editor for an Indian High Court bench.
Write Level 2 only: Authority Table & Source Discipline.

Rules:
- Use the authority table below.
- Map each authority to a specific issue.
- If a required authority is not retrieved, call it "Authority gap - verify before relying".
- Separate retrieved support from argument/inference.

Context:
{elite_context}
""",
            max_tokens=1300,
            temperature=0.08,
            purpose="debate",
        )

        prompt_petitioner = f"""You are Advocate A in an Indian High Court.
Side represented: {side_a}.
Write Level 3 only: Petitioner / Claimant Submissions.

Requirements:
- Argue issue-by-issue using authority anchors.
- Include best human story, legal vulnerability, and bench concern likely to matter.
- Address proportionality, remedies, interim relief, and factual proof.
- No unsupported stereotypes or overclaims.

Context:
{elite_context}
Authority section:
{authority_section}
"""

        prompt_respondent = f"""You are Advocate B in an Indian High Court.
Side represented: {side_b}.
Write Level 4 only: Respondent / Defence Submissions.

Requirements:
- Directly defend against and counter Petitioner / Claimant positions on each locked issue.
- Argue issue-by-issue using authority anchors.
- Include best human/institutional story, legal vulnerability, and bench concern likely to matter.
- Address public order, institutional discipline, maintainability, evidence, and remedies.
- No unsupported stereotypes or overclaims.

Context:
{elite_context}
Authority section:
{authority_section}
"""
        logger.info("[CourtDebateElite] Dispatching Advocate A and Advocate B in parallel ...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut_pet = executor.submit(
                self.llm.generate,
                prompt_petitioner,
                max_tokens=1700,
                temperature=0.18,
                purpose="debate",
            )
            fut_resp = executor.submit(
                self.llm.generate,
                prompt_respondent,
                max_tokens=1700,
                temperature=0.18,
                purpose="debate",
            )
            petitioner = fut_pet.result()
            respondent = fut_resp.result()

        rebuttal = self.llm.generate(
            f"""You are preparing oral rejoinder in a High Court.
Write Level 5 only: Rebuttal and Sur-Rebuttal.

Requirements:
- First, petitioner's rebuttal to respondent.
- Second, respondent's sur-rebuttal.
- Each side gets strongest 5 points only.
- Include one concession that improves credibility for each side.
- Identify which fact, if proved, changes the result.

Context:
{elite_context}
Advocate A:
{petitioner}

Advocate B:
{respondent}
""",
            max_tokens=1300,
            temperature=0.16,
            purpose="debate",
        )

        bench_questions = self.llm.generate(
            f"""You are a skeptical Indian High Court bench.
Write Level 6 only: Bench Questions and Cross-Examination.

Requirements:
- Ask hard questions to each side.
- Test factual assumptions, statutory basis, proportionality, public order evidence, maintainability, and remedy design.
- Include questions about human impact and institutional consequences.
- Identify weak assumptions and authority gaps.

Context:
{elite_context}
Advocate A:
{petitioner}

Advocate B:
{respondent}

Rebuttal:
{rebuttal}
""",
            max_tokens=1300,
            temperature=0.14,
            purpose="debate",
        )

        persuasion = self.llm.generate(
            f"""You are an ethical courtroom strategy analyst.
Write Level 7 only: Ethical Persuasion and Human-Impact Analysis.

Requirements:
- Discuss dignity, autonomy, education access, safety, public-order anxiety, institutional discipline, chilling effect, and practical consequences where relevant.
- For each side: best human story, legal vulnerability, bench concern likely to matter.
- Distinguish empathy from proof.
- State what emotional framing is legitimate and what would be improper.

Context:
{elite_context}
Bench questions:
{bench_questions}
""",
            max_tokens=1200,
            temperature=0.16,
            purpose="debate",
        )

        final_ruling = self.llm.generate(
            f"""You are the final High Court bench.
Write Level 8 only: Final Bench Ruling, Remedies, and Alternative Outcomes.

Requirements:
- Decide each issue separately.
- State likely winner and confidence percentage.
- Give remedy design: declaration, mandamus, stay, quashing/protection, monitoring limits, investigation safeguards, or remand as appropriate.
- Explain what changes if key facts differ.
- Include no case citation unless supported by the authority table or labelled as an authority gap.
- End with a concise "Court-Level Quality Self-Score" out of 100.

Context:
{elite_context}
Advocate A:
{petitioner}

Advocate B:
{respondent}

Rebuttal:
{rebuttal}

Bench questions:
{bench_questions}

Persuasion analysis:
{persuasion}
""",
            max_tokens=1800,
            temperature=0.12,
            purpose="debate",
        )

        independent_evaluation = self.llm.generate(
            f"""You are an independent evaluator. Score the elite court debate objectively.
Return only the scoring block.

Rubric:
- Authority Accuracy: X/10
- Adversarial Depth: X/10
- Factual Sensitivity: X/10
- Judicial Realism: X/10
- Remedy Precision: X/10
- Ethical Persuasion / Human Impact: X/10
- Hallucination Control: X/10
- Overall Court-Level Quality: X/100

Context:
{elite_context}
Sections:
{level_1}
{authority_section}
{petitioner}
{respondent}
{rebuttal}
{bench_questions}
{persuasion}
{final_ruling}
""",
            max_tokens=700,
            temperature=0.08,
            purpose="debate",
        )

        sections = {
            "level_1_issue_framing": level_1.strip(),
            "level_2_authority_table": authority_section.strip(),
            "level_3_petitioner_submissions": petitioner.strip(),
            "level_4_respondent_submissions": respondent.strip(),
            "level_5_rebuttal_sur_rebuttal": rebuttal.strip(),
            "level_6_bench_questions": bench_questions.strip(),
            "level_7_persuasion_analysis": persuasion.strip(),
            "level_8_final_ruling": final_ruling.strip(),
            "independent_evaluation": independent_evaluation.strip(),
        }
        quality_report = self._elite_quality_report(
            user_query=user_query,
            issues=issues,
            sections=sections,
            evidence_packet_text=evidence_packet + "\n\n" + seed_packet,
            authority_table=authority_table,
        )
        unsupported_authorities = [
            row for row in authority_table if row.get("status") not in {"retrieved", "canonical"}
        ]
        output_order = [
            ("## Level 1: Issue Framing and Clarification Gate", sections["level_1_issue_framing"]),
            ("## Level 2: Authority Table and Source Discipline", sections["level_2_authority_table"]),
            ("## Level 3: Petitioner / Claimant Submissions", sections["level_3_petitioner_submissions"]),
            ("## Level 4: Respondent / Defence Submissions", sections["level_4_respondent_submissions"]),
            ("## Level 5: Rebuttal and Sur-Rebuttal", sections["level_5_rebuttal_sur_rebuttal"]),
            ("## Level 6: Bench Questions and Cross-Examination", sections["level_6_bench_questions"]),
            ("## Level 7: Ethical Persuasion and Human-Impact Analysis", sections["level_7_persuasion_analysis"]),
            ("## Level 8: Final Bench Ruling, Remedies, and Alternative Outcomes", sections["level_8_final_ruling"]),
            ("## Independent Evaluation (Scored by Judge Agent)", sections["independent_evaluation"]),
        ]
        full_text = "\n\n".join(f"{heading}\n{body}".strip() for heading, body in output_order)
        self._save_to_memory(session_id, user_query, full_text)
        return {
            **sections,
            "debate_output": full_text,
            "quality_mode": "elite",
            "quality_target": "court_85",
            "legal_domain": domain,
            "issue_map": issues,
            "issue_packets": issue_packets,
            "authority_table": authority_table,
            "authority_table_markdown": authority_table_text,
            "judge_questions": sections["level_6_bench_questions"],
            "persuasion_analysis": sections["level_7_persuasion_analysis"],
            "quality_report": quality_report,
            "unsupported_authorities": unsupported_authorities,
            "clarification_questions": clarification_questions,
            "level_5_7_judge": "\n\n".join(
                [
                    sections["level_6_bench_questions"],
                    sections["level_7_persuasion_analysis"],
                    sections["level_8_final_ruling"],
                    sections["independent_evaluation"],
                ]
            ),
        }

    def run(
        self,
        user_query: str,
        conversation_history: str = "",
        modular: bool = False,
        session_id: Optional[str] = None,
        force_debate: bool = False,
        elite: bool = False,
        quality_target: Optional[str] = None,
    ) -> Dict:
        phase1 = (
            {"is_complex": True, "response": "Court Debate Mode forced by endpoint.", "history_used": bool(conversation_history)}
            if force_debate
            else self.check_complexity(user_query, session_id, conversation_history)
        )

        if not phase1["is_complex"]:
            return {
                "mode": "normal",
                "phase1_response": phase1["response"],
                "debate_output": None,
                "zilliz_used": False,
                "provider": self.llm.provider,
                "memory_used": phase1["history_used"],
            }

        if self._should_run_elite(user_query, elite=elite, quality_target=quality_target):
            logger.info("[CourtDebateElite] Elite debate starting ...")
            elite_output = self.run_debate_elite(user_query, session_id=session_id, history=conversation_history)
            return {
                "mode": "court_debate_elite",
                "phase1_response": phase1["response"],
                "debate_output": elite_output.get("debate_output"),
                "legal_domain": elite_output.get("legal_domain", "general"),
                "indian_law_focus": "Elite Indian court debate | SC/HC precedents | statutes | remedies | ethical persuasion",
                "zilliz_used": True,
                "provider": self.llm.provider,
                "memory_used": phase1["history_used"],
                **elite_output,
            }

        return super().run(
            user_query=user_query,
            conversation_history=conversation_history,
            modular=modular,
            session_id=session_id,
            force_debate=True,
        )

    def stream_debate(self, user_query: str, session_id: Optional[str] = None, history: str = "") -> Generator[str, None, None]:
        self._last_stream_quality_summary = {}
        for packet in self._stream_modular_sections(user_query, session_id=session_id, history=history):
            clean_packet = (packet or "").strip()
            if not clean_packet:
                continue
            yield clean_packet + "\n"
        summary = getattr(self, "_last_stream_quality_summary", {}) or {}
        yield json.dumps(
            {
                "event_type": "done",
                "level": "done",
                "chunk": "",
                "status": "done",
                "quality_summary": summary,
                "completed_count": summary.get("completed_count"),
                "elapsed_seconds": summary.get("elapsed_seconds"),
            }
        ) + "\n"


_court_debate_engine_singleton: Optional[CourtDebateEngineV2] = None
_court_debate_engine_lock = threading.Lock()


def _get_court_debate_engine() -> CourtDebateEngineV2:
    global _court_debate_engine_singleton
    if _court_debate_engine_singleton is None:
        with _court_debate_engine_lock:
            if _court_debate_engine_singleton is None:
                _court_debate_engine_singleton = CourtDebateEngineV2()
    return _court_debate_engine_singleton


def get_court_debate_response(
    user_query: str,
    conversation_history: str = "",
    modular: bool = False,
    session_id: Optional[str] = None,
    force_debate: bool = False,
    elite: bool = False,
    quality_target: Optional[str] = None,
) -> Dict:
    """
    Drop-in for FastAPI route handler.
    Automatically loads session history from ShortTermMemory if session_id provided.
    """
    engine = _get_court_debate_engine()
    return engine.run(
        user_query,
        conversation_history,
        modular,
        session_id,
        force_debate=force_debate,
        elite=elite,
        quality_target=quality_target,
    )


def get_court_debate_stream_generator(
    user_query: str,
    conversation_history: str = "",
    session_id: Optional[str] = None,
) -> Generator[str, None, None]:
    """
    Returns a sync generator of SSE-ready JSON lines.
    Use with FastAPI StreamingResponse (media_type='text/event-stream').
    """
    engine = _get_court_debate_engine()
    return engine.stream_debate(user_query, session_id, conversation_history)


# ===========================================================================
# CLI test runner
# ===========================================================================

if __name__ == "__main__":
    TEST_QUERY = (
        "A company wants to terminate an employee for alleged misconduct, "
        "but the employee claims it is retaliation for whistleblowing on "
        "financial irregularities. The employment contract contains an "
        "arbitration clause. The employee is also threatening to file a "
        "complaint with the Labour Commissioner. What are the legal risks, "
        "options, and best strategy for the company under Indian law?"
    )
    TEST_SESSION = "cli_test_session_001"

    print("\n" + "=" * 70)
    print("LAW-GPT | Court Debate Engine — CLI Test (all 3 features)")
    print("=" * 70)

    engine = CourtDebateEngine()

    print("\n>>> Phase 1: Complexity Check + Memory")
    p1 = engine.check_complexity(TEST_QUERY, session_id=TEST_SESSION)
    print(p1["response"])
    print(f"Complex: {p1['is_complex']} | History used: {p1['history_used']}")

    if p1["is_complex"]:
        print("\n>>> Phase 2: Integrated Debate (single LLM call)")
        debate = engine.run_debate_integrated(TEST_QUERY, session_id=TEST_SESSION)
        print(debate[:2000], "...[truncated]")

        print("\n>>> Streaming test (first 3 chunks)")
        count = 0
        for chunk in engine.stream_debate(TEST_QUERY, session_id=TEST_SESSION + "_stream"):
            print(chunk, end="")
            count += 1
            if count >= 12:
                print("\n...[stream truncated for CLI test]")
                break
