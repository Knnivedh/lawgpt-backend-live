import os
import time
import threading
from pathlib import Path
from openai import OpenAI
import logging
from typing import List, Any, Dict
from dotenv import load_dotenv

try:
    from config.config import Config
except Exception:
    Config = None

# ── Resilience policy knobs ───────────────────────────────────────────────────
# Every value is env-tunable (Azure App Settings) with a safe hard ceiling, so a
# typo in a setting can never reintroduce the unbounded hang that produced the
# 67 s average latency.
def _per_call_timeout(default: float = 60.0) -> float:
    """Bounded per-request timeout, hard-capped by LLM_CLIENT_TIMEOUT_MAX."""
    try:
        t = float(os.getenv("LLM_CLIENT_TIMEOUT_SECONDS", default))
    except (TypeError, ValueError):
        t = default
    try:
        cap = float(os.getenv("LLM_CLIENT_TIMEOUT_MAX", "90"))
    except (TypeError, ValueError):
        cap = 90.0
    return max(1.0, min(t, cap))


def _per_call_deadline() -> float:
    """Total wall-clock budget for ONE logical LLM call including all failover.

    This is the knob that actually bounds latency. A per-request timeout alone
    is not a latency bound: the retry cascade in agentic_rag_engine._llm_call
    issues up to 2 models x 2 attempts, so N x timeout seconds is the real
    worst case. Once the deadline is spent the cascade stops trying more
    vendors and returns the last error instead of stacking another 30 s.
    """
    try:
        return max(5.0, float(os.getenv("LLM_REQUEST_BUDGET_SECONDS", "75")))
    except (TypeError, ValueError):
        return 75.0


def _build_openai_client(api_key: str, base_url: str) -> OpenAI:
    """Create OpenAI-compatible client with SDK-retry disabled when supported.

    We disable SDK retries so upstream callers can apply key-rotation logic
    immediately on 429 responses instead of waiting for internal backoff.
    A hard request timeout is mandatory: without it the SDK default (600s)
    lets a hung connection stall the whole query past the platform gateway.
    """
    timeout_s = _per_call_timeout()
    try:
        return OpenAI(api_key=api_key, base_url=base_url, max_retries=0, timeout=timeout_s)
    except TypeError:
        try:
            return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s)
        except TypeError:
            return OpenAI(api_key=api_key, base_url=base_url)

# ── Robust .env Loading ───────────────────────────────────────────────────────
# Azure App Service: env vars come from App Settings (already in os.environ).
# Local dev: keys live in config/.env relative to project root.
# We probe four likely paths in priority order so neither deployment mode fails.
def _load_env_files() -> None:
    _this_file = Path(__file__).resolve()

    # Candidate .env paths from most-specific to most-generic
    _candidates = [
        _this_file.parent.parent.parent / "config" / ".env",   # project_root/config/.env
        _this_file.parent.parent.parent / ".env",               # project_root/.env
        Path("/home/site/wwwroot/config/.env"),                  # Azure App Service path
        Path("/home/site/wwwroot/.env"),                         # Azure fallback
    ]
    for _path in _candidates:
        if _path.exists():
            load_dotenv(str(_path), override=False)  # override=False: App Service env wins

_load_env_files()
logger = logging.getLogger(__name__)

def _reasoning_token_floor() -> int:
    """Configurable reasoning-token floor (was a hard-coded 12288).

    On the 1 GB F1 container a 12288 floor meant generating up to 12k tokens per
    answer, which drove peak memory, latency and the synthesis 500 rate. Set
    TOKENROUTER_MAX_TOKENS_FLOOR to tune or restore the old value.
    """
    try:
        return max(256, int(os.getenv("TOKENROUTER_MAX_TOKENS_FLOOR", "4096")))
    except (TypeError, ValueError):
        return 4096


def _dahl_reasoning_effort() -> str:
    """reasoning_effort to send to the Dahl model, or "" for none at all.

    MEASURED on deepseek-ai/DeepSeek-V4-Flash-0731 (2026-10-05). Sending an
    explicit value is actively harmful - it switches the hidden reasoning trace
    ON and makes the model slower AND shorter:

        (nothing)  ->  0-192 reasoning tokens,  0.5-8.9s, 1199 chars   USE THIS
        low        -> 970 reasoning tokens,   14.5s,  222 chars
        minimal    -> 448 reasoning tokens,    8.3s, 2435 chars
        none       ->   0 reasoning tokens,   45.5s, 3543 chars

    Contrast zai-org/GLM-5.3-Flash, which is the OPPOSITE: it returns EMPTY
    content at every budget unless reasoning_effort is set. So the value is
    model-specific and must be left empty by default.

    Also note DeepSeek returns real content even at max_tokens=3, so unlike
    GLM there is NO token floor to enforce - none is applied here.
    """
    return (os.getenv("DAHL_REASONING_EFFORT") or "").strip()


def _is_empty_or_budget_failure(exc: Exception) -> bool:
    """True when a failure looks like 'reasoning model ran out of budget'."""
    msg = str(exc or "").lower()
    return any(token in msg for token in (
        "empty", "length", "max_tokens", "max tokens", "no content", "content filter",
    ))


def _classify_failure(exc: Exception) -> str:
    """Map an exception to a failure class that drives breaker/rotation policy.

    Mirrors the taxonomy already used by court_debate_engine.LawGPTLLMClient so
    both LLM paths in this repo classify failures identically.
    """
    status = getattr(exc, "status_code", None)
    text = f"{exc}".lower()
    if status == 429 or "429" in text or "rate limit" in text or "otpm" in text:
        return "rate_limited"
    if status == 401 or "401" in text or "invalid api key" in text or "unauthorized" in text:
        return "unauthorized"
    if status == 404 or "404" in text or "model not found" in text or "no available channel" in text:
        return "not_found"
    if status == 503 or "503" in text or "service unavailable" in text:
        return "unavailable"
    if isinstance(exc, TimeoutError) or "timeout" in text or "timed out" in text:
        return "timeout"
    return "error"


# Per-failure-class cooldown, in seconds. Mirrors court_debate_engine:
#   unauthorized -> effectively dead credential, park for the day
#   rate_limited -> an org/minute ceiling, park for 30 min so the next real
#                  user request does not immediately re-trip it
#   not_found    -> the model/channel is gone from that vendor; parking avoids a
#                  guaranteed-failing call on every request
#   timeout      -> the vendor is too slow to be useful inside our budget
_COOLDOWNS = {
    "unauthorized": 24 * 60 * 60,
    "rate_limited": 30 * 60,
    "not_found": 24 * 60 * 60,
    "unavailable": 5 * 60,
    "timeout": 10 * 60,
    "error": 60,
}


def _cooldown_for(category: str) -> float:
    try:
        override = float(os.getenv("LLM_VENDOR_COOLDOWN_SECONDS", "0") or 0)
    except (TypeError, ValueError):
        override = 0.0
    return override if override > 0 else float(_COOLDOWNS.get(category, 60))
class VendorCircuitBreaker:
    """Per-VENDOR circuit breaker with failure thresholds.

    WHY PER-VENDOR AND NOT PER-KEY
    ------------------------------
    The measured Groq failure is an ORG-level ceiling ("OTPM: Limit 1000,
    Used 992") shared by all eight gsk_* keys. Rotating gsk_A -> gsk_B inside
    one exhausted org cannot succeed; it only spends another request against a
    ceiling that is already full, and multiplies latency because each attempt
    pays a full timeout first. A per-key breaker therefore never trips here --
    every key is individually "fresh".

    A per-VENDOR breaker trips on the pattern that actually indicates an
    exhausted org: N consecutive rate-limit/timeout failures within a window.
    While open, that vendor is skipped entirely and the chain moves to a
    DIFFERENT vendor; after a cooldown it becomes half-open (trial calls) so a
    recovered vendor is picked back up automatically.

    Concurrency: one lock covers the failure counters and the open timestamps,
    so a burst of 429s from parallel requests cannot interleave and corrupt it.
    """

    def __init__(self, threshold: int = 3, window: float = 60.0,
                 half_open_successes_to_close: int = 2):
        try:
            threshold = max(1, int(os.getenv("LLM_BREAKER_THRESHOLD", threshold)))
        except (TypeError, ValueError):
            threshold = 3
        try:
            window = max(1.0, float(os.getenv("LLM_BREAKER_WINDOW_SECONDS", window)))
        except (TypeError, ValueError):
            window = 60.0
        self.threshold = threshold
        self.window = window
        self.half_open_successes_to_close = half_open_successes_to_close
        self._lock = threading.Lock()
        self._failures = {}       # vendor -> [timestamps]
        self._open_until = {}     # vendor -> epoch seconds
        self._half_open_hits = {}  # vendor -> success streak
        self._last_reason = {}

    def is_open(self, vendor: str) -> bool:
        """True when the vendor must be skipped right now."""
        with self._lock:
            until = self._open_until.get(vendor, 0.0)
            if until <= time.time():
                if until:  # cooldown elapsed -> breaker is half-open again
                    self._open_until.pop(vendor, None)
                    self._half_open_hits.pop(vendor, None)
                return False
            return True

    def open_until(self, vendor: str) -> float:
        with self._lock:
            return self._open_until.get(vendor, 0.0)

    def state(self):
        now = time.time()
        with self._lock:
            return {
                v: {
                    "open": self._open_until.get(v, 0.0) > now,
                    "cooldown_remaining_seconds": max(
                        0.0, round(self._open_until.get(v, 0.0) - now, 1)
                    ),
                    "recent_failures": len(
                        [t for t in self._failures.get(v, []) if now - t <= self.window]
                    ),
                    "last_failure_reason": self._last_reason.get(v, ""),
                }
                for v in sorted(set(self._failures) | set(self._open_until))
            }

    def record_failure(self, vendor: str, category: str, reason: str = "") -> bool:
        """Record a failure; return True if this failure opened the breaker."""
        now = time.time()
        with self._lock:
            hits = [t for t in self._failures.get(vendor, []) if now - t <= self.window]
            hits.append(now)
            self._failures[vendor] = hits
            self._last_reason[vendor] = (reason or category)[:200]
            # A dead credential or a vanished model opens the breaker at once:
            # there is no value retrying it inside this window.
            immediate = category in ("unauthorized", "not_found")
            opened = bool(immediate or len(hits) >= self.threshold)
            if opened:
                self._open_until[vendor] = now + _cooldown_for(category)
                self._half_open_hits.pop(vendor, None)
        if opened:
            logger.warning(
                "🔌 CIRCUIT OPEN: provider '%s' parked %ss after %s (%s)",
                vendor, int(self.open_until(vendor) - now), category, (reason or "")[:100],
            )
        return opened

    def record_success(self, vendor: str) -> None:
        """Clear failure history and close a half-open breaker on success."""
        now = time.time()
        with self._lock:
            self._failures.pop(vendor, None)
            if vendor in self._open_until:
                if self._open_until[vendor] > now:
                    # Still cooling down: a success means it recovered early.
                    self._open_until.pop(vendor, None)
                    self._half_open_hits.pop(vendor, None)
                    logger.info("✅ CIRCUIT CLOSED: provider '%s' recovered early", vendor)
                    return
                # Half-open trial succeeded; require a short success streak.
                hits = self._half_open_hits.get(vendor, 0) + 1
                if hits >= self.half_open_successes_to_close:
                    self._open_until.pop(vendor, None)
                    self._half_open_hits.pop(vendor, None)
                    logger.info("✅ CIRCUIT CLOSED: provider '%s' recovered", vendor)
                else:
                    self._half_open_hits[vendor] = hits
                return
            self._half_open_hits.pop(vendor, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()
            self._open_until.clear()
            self._half_open_hits.clear()
            self._last_reason.clear()


class SmartCompletionsProxy:
    """Intercepts completion calls to handle provider-specific nuances (Model Mapping)"""
    def __init__(self, completions_interface, provider_type: str,
                 flash_client=None, flash_model: str = "",
                 breaker=None, owner=None, flash_provider: str = "groq",
                 single_provider: bool = False):
        self.interface = completions_interface
        self.provider_type = provider_type
        self.flash_client = flash_client
        self.flash_model = flash_model
        self.breaker = breaker
        self.owner = owner
        # The flash rig is a specific vendor's client (Groq in production), so
        # its breaker key must be that vendor, not the generic "flash" label.
        self.flash_provider = flash_provider or "groq"
        self.single_provider = single_provider

    def create(self, **kwargs):
        # FLASH RIG BYPASS: requests for the fast model go straight to the
        # separate flash client. DISABLED in single-provider mode, because the
        # flash client is a different vendor and a "fast" query must not
        # silently leave the one provider we have.
        _flash_requested = (
            self.flash_client is not None
            and self.flash_model
            and not getattr(self, "single_provider", False)
            and str(kwargs.get("model", "")) == self.flash_model
        )
        if _flash_requested:
            kwargs.pop("reasoning_effort", None)
            try:
                _resp = self.flash_client.chat.completions.create(**kwargs)
                if self.breaker is not None:
                    self.breaker.record_success("flash")
                return _resp
            except Exception as exc:
                logger.warning(f"⚡ Flash client failed ({exc}); falling back to primary provider")
                if self.breaker is not None:
                    self.breaker.record_failure(
                        "flash", _classify_failure(exc), str(exc))

        # DYNAMIC MODEL MAPPING
        # Groq uses "llama-3.3-70b-versatile", Cerebras uses "llama3.1-70b"
        if self.provider_type == "cerebras":
            original_model = kwargs.get("model", "")
            if "llama" in original_model.lower() and "70b" in original_model.lower():
                # Map to Cerebras equivalent
                kwargs["model"] = os.getenv("CEREBRAS_MODEL", "llama3.1-70b")
                # logger.info(f"  [🔀 BRIDGE] Mapped model '{original_model}' -> 'llama3.1-70b' for Cerebras")

        if self.provider_type == "openrouter":
            original_model = kwargs.get("model", "")
            if not original_model or "llama" in original_model.lower() or "versatile" in original_model.lower() or "instant" in original_model.lower() or "qwen" in original_model.lower():
                kwargs["model"] = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3.5-lightning:free")

        # Dahl serves the single configured model (deepseek-ai/DeepSeek-V4-Flash-0731
        # by default) regardless of the model string a call site requested, so
        # call sites keep their legacy names.
        if self.provider_type == "dahl":
            kwargs["model"] = os.getenv(
                "DAHL_MODEL", "deepseek-ai/DeepSeek-V4-Flash-0731")
            # reasoning_effort is model-specific and defaults to NOT SENT.
            # Measured on this model, every explicit value made it slower and
            # produced less output; see _dahl_reasoning_effort for the numbers.
            _effort = _dahl_reasoning_effort()
            if _effort:
                kwargs["reasoning_effort"] = _effort
            else:
                # A call site may carry a stale value from an earlier model.
                kwargs.pop("reasoning_effort", None)
            # NO token floor: DeepSeek returns real content even at
            # max_tokens=3, so clamping a small budget would only waste tokens.
            kwargs.pop("thinking", None)

            # Inject the concise system prompt ONLY when the caller sent no
            # system message. This is load-bearing, not cosmetic: without it
            # this model's hidden reasoning trace consumes the whole max_tokens
            # budget and the answer comes back as content='' with
            # finish_reason='length'. Measured 5/5 empty on a hard legal
            # question. See Config.DAHL_DEFAULT_SYSTEM_PROMPT for the full
            # remedy sweep (reasoning_effort=low was 5/5 empty too).
            if not any(
                str(m.get("role") or "").strip().lower() == "system"
                for m in (kwargs.get("messages") or [])
                if isinstance(m, dict)
            ):
                _sys = (os.getenv("DAHL_DEFAULT_SYSTEM_PROMPT") or "").strip()
                if not _sys and Config is not None:
                    # Fall back to the Config default. Without this, a deployment
                    # with no DAHL_DEFAULT_SYSTEM_PROMPT in App Settings AND no
                    # config/.env would silently lose the guard against empty
                    # answers, which is a 200-with-no-content failure.
                    _sys = str(
                        getattr(Config, "DAHL_DEFAULT_SYSTEM_PROMPT", "") or "").strip()
                if _sys:
                    kwargs["messages"] = [
                        {"role": "system", "content": _sys}
                    ] + list(kwargs.get("messages") or [])
            # vLLM does no hidden chat-template thinking here, so any
            # reasoning-only param a caller passes is stripped to avoid a 400.
            kwargs.pop("thinking", None)

        # TokenRouter always serves the configured GLM model regardless of the
        # requested Llama name — every call site keeps its Groq-era model string.
        if self.provider_type == "tokenrouter":
            kwargs["model"] = os.getenv("TOKENROUTER_MODEL", "z-ai/glm-5.3-free")
            # GLM-5.3 is a reasoning model and thinking cannot be disabled: the
            # reasoning trace is billed against max_tokens, so tiny budgets
            # (probes/pings use 3 tokens) would return empty content. Reasoning
            # scales with prompt complexity (observed >4k on planner prompts with
            # document context), so raise any sub-12k request to a floor that
            # always leaves room for the answer. max_tokens is only a cap.
            # The floor is now configurable and much lower by default. A 12288
            # floor on a 1 GB F1 container generated up to 12k tokens per answer,
            # which drove peak memory and contributed to the ~50% synthesis 500
            # rate and the 114 s latency measured live. Most answers need 1-3k
            # tokens. If a response comes back empty at the reduced floor, the
            # generation path retries once at the legacy budget, so lowering the
            # floor cannot silently truncate answers.
            try:
                requested = int(kwargs.get("max_tokens") or 0)
            except (TypeError, ValueError):
                requested = 0
            _floor = _reasoning_token_floor()
            if requested < _floor:
                kwargs["max_tokens"] = _floor
            if not kwargs.get("reasoning_effort"):
                kwargs["reasoning_effort"] = os.getenv("TOKENROUTER_REASONING_EFFORT", "low")

        try:
            _resp = self.interface.create(**kwargs)
            if self.breaker is not None:
                self.breaker.record_success(self.provider_type)
            return _resp
        except Exception as exc:
            # A reasoning model given too small a budget can return empty content
            # rather than raising a clear error. Retry once at the legacy budget
            # before degrading, so lowering the floor cannot silently truncate.
            if (
                _is_empty_or_budget_failure(exc)
                and self.provider_type == "tokenrouter"
                and int(kwargs.get("max_tokens") or 0) < 12288
            ):
                logger.warning(
                    "Retry at legacy token budget after budget-like failure (%s)", exc)
                try:
                    _retry_kwargs = dict(kwargs)
                    _retry_kwargs["max_tokens"] = 12288
                    return self.interface.create(**_retry_kwargs)
                except Exception as retry_exc:
                    logger.warning("Legacy-budget retry also failed (%s)", retry_exc)
                    exc = retry_exc
            # Primary provider unavailable (TokenRouter 503 gateway overload,
            # connection stalls, timeouts). Degrade to the flash rig instead of
            # burning the caller's retry budget -- but only if the flash vendor's
            # breaker is still closed. The flash rig is a Groq client, and the
            # measured outage is an ORG-level Groq ceiling, so falling back into
            # a tripped Groq circuit only stacks another guaranteed failure and
            # another full timeout onto the request.
            self._record_failure(exc)
            if (
                not _flash_requested
                and self.flash_client is not None
                and self.flash_model
                and self._flash_usable()
            ):
                logger.warning(
                    "⚡ Primary provider failed (%s); serving via flash rig %s",
                    str(exc)[:120], self.flash_model,
                )
                retry_kwargs = dict(kwargs)
                retry_kwargs["model"] = self.flash_model
                retry_kwargs.pop("reasoning_effort", None)
                retry_kwargs.pop("thinking", None)
                try:
                    _resp = self.flash_client.chat.completions.create(**retry_kwargs)
                    if self.breaker is not None:
                        self.breaker.record_success(self.flash_provider)
                    return _resp
                except Exception as flash_exc:
                    logger.warning("⚡ Flash rig also failed (%s)", str(flash_exc)[:120])
                    if self.breaker is not None:
                        self.breaker.record_failure(
                            self.flash_provider, _classify_failure(flash_exc), str(flash_exc))
                    raise
            raise

    def _record_failure(self, exc: Exception) -> None:
        """Feed the vendor breaker. Kept separate so every exit path reports."""
        if self.breaker is not None:
            self.breaker.record_failure(
                self.provider_type, _classify_failure(exc), str(exc))

    def _flash_usable(self) -> bool:
        if self.breaker is None:
            return True
        return not self.breaker.is_open(self.flash_provider)

class SmartChatProxy:
    """Wraps the chat interface"""
    def __init__(self, chat_interface, provider_type: str,
                 flash_client=None, flash_model: str = "",
                 breaker=None, owner=None, flash_provider: str = "groq",
                 single_provider: bool = False):
        self.chat_interface = chat_interface
        self.provider_type = provider_type
        self.flash_client = flash_client
        self.flash_model = flash_model
        self.completions = SmartCompletionsProxy(
            chat_interface.completions, provider_type,
            flash_client=flash_client, flash_model=flash_model,
            breaker=breaker, owner=owner, flash_provider=flash_provider,
            single_provider=single_provider,
        )

class GroqClientManager:
    """
    Multi-vendor LLM client pool with vendor-aware failover.

    "The 29-Step Loop": switches keys every 29 requests.

    G5 FAILOVER POLICY (what changed and why)
    -----------------------------------------
    The old loop rotated `(index + 1) % len(clients)` over a FLAT list. Because
    every key of a vendor is adjacent in that list, a 429 while on gsk_N walked
    to gsk_(N+1) -- the SAME Groq org, which shares one OTPM ceiling. Measured
    result: 6 rotations inside one exhausted org, every one paying a full
    timeout first. That is the 67 s average latency.

    Rotation is now vendor-crossing: on a 429/timeout the manager moves to the
    next client belonging to a DIFFERENT vendor, and skips any vendor whose
    circuit breaker is open. Keys of the same vendor are only tried again after
    that vendor's cooldown expires and a trial call succeeds.
    """

    def __init__(self, request_limit: int = 29):
        self.request_limit = request_limit
        self.request_count = 0
        self.current_key_index = 0
        self._lock = threading.Lock()  # Thread-safe rotation
        # One breaker per VENDOR (not per key): see VendorCircuitBreaker docstring.
        self.breaker = VendorCircuitBreaker()
        self._vendor_of_index: list[str] = []
        self._flash_provider = "groq"

        # SINGLE-PROVIDER MODE.
        # The Dahl account carries a 100M free-token allowance and measured
        # 12/12 success at p50 0.82 s with no 429s, so there is nothing to fail
        # over to. Loading the other vendors would mean a "fast" query could
        # silently hit a second provider, and a 429 would bounce a request off a
        # healthy Dahl onto a slower one. In this mode we load Dahl keys ONLY
        # and pin every call to them.
        self.single_provider = str(
            os.getenv("LLM_SINGLE_PROVIDER", "true")
        ).strip().lower() in ("1", "true", "yes", "on")

        # Load (key, provider_hint) pairs in priority order.
        self._key_sources: list[tuple[str, str]] = []  # (key, provider_hint)

        # Dahl — primary. Supports the standard + numbered naming styles.
        for var in ["dahl_api", "DAHL_API_KEY", "DAHL_API_KEY_1"]:
            v = os.getenv(var)
            if v and all(v != k for k, _ in self._key_sources):
                self._key_sources.append((v, "dahl"))
                break
        for i in range(2, 6):
            for var in [f"dahl_api_{i}", f"DAHL_API_KEY_{i}"]:
                v = os.getenv(var)
                if v and all(v != k for k, _ in self._key_sources):
                    self._key_sources.append((v, "dahl"))
                    break

        # Everything below is FAILOVER POOL. In single-provider mode it is
        # skipped entirely: one provider, one model, no rotation.
        if not self.single_provider:
            self._load_failover_keys()
        elif len(self._key_sources) == 0:
            raise ValueError(
                "LLM_SINGLE_PROVIDER is on but no Dahl key is configured. Set "
                "dahl_api / DAHL_API_KEY in Azure App Settings or config/.env, or "
                "set LLM_SINGLE_PROVIDER=false to use the multi-vendor pool."
            )
        else:
            logger.info(
                "  -> SINGLE PROVIDER mode: %d Dahl key(s), no vendor rotation "
                "(set LLM_SINGLE_PROVIDER=false to re-enable failover)",
                len(self._key_sources),
            )

        # Materialise the clients in BOTH modes.
        self._build_clients()

    def _load_failover_keys(self) -> None:
        """Load TokenRouter / Groq / Cerebras / OpenRouter / NVIDIA keys.

        Only called when LLM_SINGLE_PROVIDER is false. Extracted so the
        single-provider path above cannot accidentally pull these in.
        """
        # TokenRouter — deep-reasoning fallback. Standard + numbered naming styles.
        for var in ["tokenrouter_api", "TOKENROUTER_API_KEY", "TOKENROUTER_API_KEY_1"]:
            v = os.getenv(var)
            if v and all(v != k for k, _ in self._key_sources):
                self._key_sources.append((v, "tokenrouter"))
                break
        for i in range(2, 6):
            for var in [f"tokenrouter_api_{i}", f"TOKENROUTER_API_KEY_{i}"]:
                v = os.getenv(var)
                if v and all(v != k for k, _ in self._key_sources):
                    self._key_sources.append((v, "tokenrouter"))
                    break

        # Load Keys — supports two naming styles:
        # Style A (standard): GROQ_API_KEY, GROQ_API_KEY_2 ... GROQ_API_KEY_5
        # Style B (legacy):   GROQ_API_KEY1, GROQ_API_KEY2  ... GROQ_API_KEY5
        # Style A — Key 1
        for var in ["GROQ_API_KEY", "groq_api", "GROQ_API_KEY1"]:
            v = os.getenv(var)
            if v and all(v != k for k, _ in self._key_sources):
                self._key_sources.append((v, None))
                break

        # Style A — Keys 2-5  |  Style B — Keys 2-5
        for i in range(2, 6):
            for var in [f"GROQ_API_KEY_{i}", f"GROQ_API_KEY{i}"]:
                v = os.getenv(var)
                if v and all(v != k for k, _ in self._key_sources):
                    self._key_sources.append((v, None))
                    break

        # Cerebras key (optional, ultra-fast inference) — both naming styles
        cerebras_key = os.getenv("CEREBRAS_API_KEY") or os.getenv("cerebras_api") or ""
        if cerebras_key and all(cerebras_key != k for k, _ in self._key_sources):
            self._key_sources.append((cerebras_key, "cerebras"))

        # ── G5: OpenRouter + NVIDIA were configured but NEVER reachable here.
        # They were loaded by config.py and used by court_debate_engine, but the
        # main synthesis path (this manager) skipped them entirely. That left
        # the failover pool with only dahl/tokenrouter/groq/cerebras, and made a
        # Groq org-wide 429 much harder to route around. These are existing,
        # already-configured providers -- nothing invented.
        if str(os.getenv("LLM_ENABLE_OPENROUTER_FALLBACK", "true")).lower() in (
            "1", "true", "yes", "on",
        ):
            for var in ["openrouter_api", "OPENROUTER_API_KEY"]:
                v = os.getenv(var)
                if v and all(v != k for k, _ in self._key_sources):
                    self._key_sources.append((v, "openrouter"))
                    break
            for i in range(2, 5):
                for var in (f"openrouter_api_{i}", f"OPENROUTER_API_KEY_{i}"):
                    v = os.getenv(var)
                    if v and all(v != k for k, _ in self._key_sources):
                        self._key_sources.append((v, "openrouter"))
                        break

        if str(os.getenv("LLM_ENABLE_NVIDIA_FALLBACK", "true")).lower() in (
            "1", "true", "yes", "on",
        ):
            for i in range(1, 3):
                for var in (f"nvidia_api_{i}" if i > 1 else "nvidia_api",
                            f"NVIDIA_API_KEY_{i}" if i > 1 else "NVIDIA_API_KEY"):
                    v = os.getenv(var)
                    if v and all(v != k for k, _ in self._key_sources):
                        self._key_sources.append((v, "nvidia"))
                        break

    def _build_clients(self) -> None:
        """Materialise OpenAI clients + vendor labels. Runs in BOTH modes."""
        self.api_keys = [k for k, _ in self._key_sources]

        if not self.api_keys:
            raise ValueError(
                "No LLM API keys found. With LLM_SINGLE_PROVIDER=true set "
                "dahl_api / DAHL_API_KEY; otherwise set TOKENROUTER_API_KEY, "
                "GROQ_API_KEY or CEREBRAS_API_KEY in Azure App Settings or in "
                "config/.env for local development."
            )

        logger.info(f"⚡ ClientManager initialized with {len(self.api_keys)} keys. Rotation Limit: {self.request_limit}")

        # Initialize Clients & Types
        self.clients = []
        self.client_types = []

        for k, hint in self._key_sources:
            if hint == "dahl" or k.startswith("dahl_"):
                # DAHL (OpenAI-compatible gateway, vLLM-served DeepSeek-V4-Flash)
                self.clients.append(_build_openai_client(
                    k, os.getenv("DAHL_BASE_URL", "https://inference.dahl.global/v1")))
                self.client_types.append("dahl")
                logger.info("  -> Loaded DAHL Client (DeepSeek primary)")
            elif hint == "tokenrouter" or k.startswith("tr-"):
                # TOKENROUTER (OpenAI-compatible gateway)
                self.clients.append(_build_openai_client(
                    k, os.getenv("TOKENROUTER_BASE_URL", "https://api.tokenrouter.com/v1")))
                self.client_types.append("tokenrouter")
                logger.info("  -> Loaded TOKENROUTER Client (GLM primary)")
            elif hint == "cerebras" or k.startswith("csk-"):
                # CEREBRAS
                self.clients.append(_build_openai_client(
                    k, os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")))
                self.client_types.append("cerebras")
                logger.info("  -> Loaded CEREBRAS Client")
            elif hint == "openrouter" or k.startswith("sk-or-"):
                # OPENROUTER (already configured in App Settings + config.py)
                self.clients.append(_build_openai_client(
                    k, os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")))
                self.client_types.append("openrouter")
                logger.info("  -> Loaded OPENROUTER Client (cross-vendor fallback)")
            elif hint == "nvidia" or k.startswith("nvapi-"):
                # NVIDIA (already configured in App Settings + config.py)
                self.clients.append(_build_openai_client(
                    k, os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")))
                self.client_types.append("nvidia")
                logger.info("  -> Loaded NVIDIA Client (cross-vendor fallback)")
            else:
                # GROQ (Default)
                self.clients.append(_build_openai_client(
                    k, os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")))
                self.client_types.append("groq")
                logger.info("  -> Loaded GROQ Client")

        # Gateway primaries (Dahl / GLM) stay sticky instead of burning through
        # the 29-request count loop, which would spread traffic across paid/limited
        # fallback keys for no reason. Count-based rotation stays active for
        # setups with only Groq/Cerebras keys; 429-driven force_rotation always works.
        if "dahl" in self.client_types or "tokenrouter" in self.client_types:
            self.request_limit = 1_000_000_000
            primary = "Dahl" if "dahl" in self.client_types else "TokenRouter"
            logger.info(f"  -> Sticky primary mode: {primary} stays active until a 429 forces failover")

        # FLASH RIG client: the first Groq key serves the fast model for
        # simple queries (the old architecture's fast path). Falls back to
        # None when no Groq key exists — everything then rides the primary.
        self.flash_model = Config.FAST_LLM_MODEL if Config else os.getenv("FAST_LLM_MODEL", "qwen/qwen3.8-27b")
        self.flash_client = None
        groq_index = next((i for i, t in enumerate(self.client_types) if t == "groq"), None)
        if groq_index is not None:
            self.flash_client = self.clients[groq_index]
            self._flash_provider = "groq"
            logger.info(f"  -> FLASH RIG ready: {self.flash_model} on Groq (sub-second simple queries)")

        # Vendor label per client index -- the basis for vendor-crossing rotation.
        self._vendor_of_index = list(self.client_types)
        distinct: List[str] = []
        for v in self.client_types:
            if v not in distinct:
                distinct.append(v)
        logger.info("  -> FAILOVER CHAIN (vendor-crossing): %s", " -> ".join(distinct))

    def get_client(self):
        """Returns the current active client, rotating if necessary (thread-safe)"""
        with self._lock:
            self.request_count += 1
            if self.request_count >= self.request_limit:
                self._rotate_key()
            # If the active vendor's breaker is open, move off it immediately
            # instead of paying another guaranteed failure.
            current_vendor = self.client_types[self.current_key_index]
            if self.breaker.is_open(current_vendor):
                self._rotate_key(reason=f"circuit open for {current_vendor}",
                                 allow_same_vendor=False)
        return self.clients[self.current_key_index]

    def get_current_provider_type(self):
        return self.client_types[self.current_key_index]

    def _vendor(self, index: int) -> str:
        if 0 <= index < len(self.client_types):
            return self.client_types[index]
        return "unknown"

    def _find_next_index(self, start: int, *, allow_same_vendor: bool,
                         skip_tripped: bool = True) -> int:
        """Index of the next usable client, preferring a DIFFERENT vendor.

        skip_tripped=False is used when every vendor is exhausted, so the caller
        degrades to a least-bad option instead of looping forever.
        """
        n = len(self.clients)
        cur_vendor = self._vendor(start)
        for offset in range(1, n + 1):
            idx = (start + offset) % n
            vendor = self._vendor(idx)
            if not allow_same_vendor and vendor == cur_vendor:
                continue
            if skip_tripped and self.breaker.is_open(vendor):
                continue
            return idx
        # No different vendor available. Fall back to any usable client; if every
        # circuit is open, stay put so the caller sees a real upstream error
        # rather than a rotation loop.
        for offset in range(1, n + 1):
            idx = (start + offset) % n
            if not skip_tripped or not self.breaker.is_open(self._vendor(idx)):
                return idx
        return start

    def _rotate_key(self, *, reason: str = "count", allow_same_vendor: bool = False):
        """Switch to the next usable client (call inside _lock).

        Default is vendor-crossing: this is the G5 fix for the org-ceiling
        outage, where (index+1) kept landing on another key of the same
        exhausted vendor.
        """
        old_index = self.current_key_index
        old_vendor = self._vendor(old_index)
        self.current_key_index = self._find_next_index(
            old_index, allow_same_vendor=allow_same_vendor)
        self.request_count = 0
        new_vendor = self._vendor(self.current_key_index)
        crossed = "CROSS-VENDOR" if new_vendor != old_vendor else "same-vendor"
        logger.info(
            "🔄 ROTATING API KEY (%s): %d -> %d [%s -> %s], reason=%s, total=%d keys",
            crossed, old_index, self.current_key_index, old_vendor, new_vendor,
            reason, len(self.clients),
        )

    @property
    def chat(self):
        """Proxy for chat completions to allow seamless drop-in replacement with model mapping"""
        current_client = self.get_client()
        provider_type = self.get_current_provider_type()
        return SmartChatProxy(
            current_client.chat, provider_type,
            flash_client=self.flash_client, flash_model=self.flash_model,
            breaker=self.breaker, owner=self, flash_provider=self._flash_provider,
            single_provider=self.single_provider,
        )

    def get_active_key(self) -> str:
        """Returns the currently active API Key string"""
        return self.api_keys[self.current_key_index]

    def force_rotation(self, reason: str = "Unknown", *, record_failure: bool = True):
        """Failover to a different vendor — thread-safe.

        record_failure=True (default)
            Call this when an ACTUAL upstream failure occurred (429/401/5xx).
            The failure is recorded on the CURRENT vendor's breaker, which is
            what stops a single 429 from re-testing the same exhausted org on
            the next request. The breaker opens after LLM_BREAKER_THRESHOLD
            failures inside the window.

        record_failure=False
            Call this for a PROACTIVE rotation, i.e. moving off a vendor before
            anything failed. advanced_rag_api_server.py does this
            ("pre-thinking-trace") up to 3x for every answer over 400 chars.
            Recording those would slowly poison every healthy circuit: measured
            90 proactive rotations opened ALL SIX vendor circuits on a system
            where nothing had ever errored, taking the whole LLM pool down.

        Defaulting to True keeps every existing error-driven call site correct
        without edits; the one proactive call site opts out explicitly.

        SINGLE-PROVIDER MODE: with LLM_SINGLE_PROVIDER=true there is exactly one
        vendor, so there is nothing to fail over to. The failure is still
        recorded on the breaker (that signal is what an operator needs), but
        the active key is left in place instead of being rotated away.
        """
        with self._lock:
            current_vendor = self._vendor(self.current_key_index)
            if record_failure:
                category = _classify_failure(RuntimeError(reason))
                opened = self.breaker.record_failure(
                    current_vendor, category, reason)
                note = ", circuit opened" if opened else ""
            else:
                note = " (proactive, not counted as a failure)"
            if self.single_provider:
                logger.warning(
                    "⚠️ LLM FAILURE (single-provider mode, not rotating): %s "
                    "(vendor=%s%s)",
                    reason, current_vendor, note,
                )
                return
            logger.warning(
                "⚠️ FORCED FAILOVER: %s (vendor=%s%s)",
                reason, current_vendor, note,
            )
            self._rotate_key(reason=reason[:60], allow_same_vendor=False)

    def vendor_chain(self) -> List[str]:
        """Distinct vendors in failover order, deduplicated."""
        chain: List[str] = []
        for t in self.client_types:
            if t not in chain:
                chain.append(t)
        return chain

    def provider_health(self) -> Dict[str, Any]:
        """Vendor breaker snapshot for /api/metrics and operator triage."""
        health = self.breaker.state()
        for vendor in set(self.client_types):
            health.setdefault(vendor, {
                "open": False,
                "cooldown_remaining_seconds": 0.0,
                "recent_failures": 0,
                "last_failure_reason": "",
            })
        for vendor, info in health.items():
            info["keys_configured"] = sum(1 for t in self.client_types if t == vendor)
            info["is_active"] = (self._vendor(self.current_key_index) == vendor)
        health["_active"] = self._vendor(self.current_key_index)
        health["_rotation_limit"] = self.request_limit
        health["_vendor_chain"] = self.vendor_chain()
        return health

    def key_count(self) -> int:
        """Returns number of loaded API keys"""
        return len(self.clients)
