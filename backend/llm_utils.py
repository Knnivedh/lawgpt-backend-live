"""
llm_utils.py - Small helpers for cleaning chat-model output.

MiniMax (the fallback model) wraps its reasoning in <think>...</think>. When it
runs out of tokens mid-thought the closing tag never arrives, and a plain
non-greedy regex leaves the whole half-finished thought in the text the user
sees. DeepSeek sometimes prefixes JSON with a sentence or wraps it in a fence.
"""

import contextvars
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any, Callable, List, Optional, Tuple

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

_THINK_RE = re.compile(r"<think>.*?(?:</think>|$)", flags=re.DOTALL)

# OpenAI-compatible endpoints the chain can use. Dahl's comes from settings.
PROVIDER_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

# Calls that blow their deadline keep running here until httpx gives up;
# their results are discarded.
_LLM_EXECUTOR = ThreadPoolExecutor(max_workers=16, thread_name_prefix="llm-call")


def invoke_with_deadline(llm, messages, deadline: float):
    """
    Run `llm.invoke(messages)` with a hard wall-clock limit.

    The client's `timeout` is per network read. Dahl sometimes returns
    "200 OK" headers and then stalls the body, which held a consultation turn
    open for minutes. The call runs in a copied context so LangChain callbacks
    (and LangGraph token streaming) still see it.
    """
    ctx = contextvars.copy_context()
    future = _LLM_EXECUTOR.submit(ctx.run, llm.invoke, messages)
    try:
        return future.result(timeout=deadline)
    except FutureTimeout:
        future.cancel()
        raise TimeoutError(f"LLM call exceeded {deadline:.0f}s deadline")


# Some models (a free reasoning model on OpenRouter) print their working as the reply
# without <think> tags: "The user wants me to rewrite the DRAFT ... Let me analyze ...".
_REASONING_LEAK_RE = re.compile(
    r"\b(?:the user (?:wants|asks|is asking|has asked|provided)|i need to (?:check|analy[sz]e|rewrite|delete|verify|follow|consider)|"
    r"let me (?:analy[sz]e|check|draft|rewrite|think|go through|verify)|the draft (?:says|states|claims|is)|"
    r"rewrite the draft|edit rules|verified statute notes|following strict editing rules)\b",
    re.IGNORECASE,
)


def looks_like_reasoning(text: Optional[str]) -> bool:
    """True when a reply reads like the model narrating its task instead of answering."""
    return bool(_REASONING_LEAK_RE.search(text or ""))


def strip_think(text: Optional[str]) -> str:
    """Remove <think> blocks, including one left unclosed at the end."""
    return _THINK_RE.sub("", text or "").strip()


_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def extract_json(text: Optional[str]) -> Any:
    """
    Parse the first JSON object in a model reply.

    Accepts bare JSON, ```json fenced JSON, or JSON with prose around it.
    Raises json.JSONDecodeError when there is no parseable object.
    """
    cleaned = strip_think(text)
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        if start == -1:
            raise
        # raw_decode stops at the end of the first object, so prose after it,
        # or the whole object repeated (seen from Dahl DeepSeek), is ignored.
        # strict=False accepts raw newlines inside strings, which models often leave in.
        decoder = json.JSONDecoder(strict=False)
        candidate = cleaned[start:]
        try:
            obj, _ = decoder.raw_decode(candidate)
        except json.JSONDecodeError:
            # a comma left before a closing brace or bracket is the other common slip
            obj, _ = decoder.raw_decode(_TRAILING_COMMA_RE.sub(r"\1", candidate))
        return obj


# ── Provider chain ────────────────────────────────────────────────────────────

def parse_chain(spec: Optional[str]) -> List[Tuple[str, str]]:
    """'groq:openai/gpt-oss-120b,openrouter:x/y:free' -> [(provider, model), ...]"""
    chain = []
    for item in (spec or "").split(","):
        provider, _, model = item.strip().partition(":")
        if provider and model:
            chain.append((provider.strip().lower(), model.strip()))
    return chain


def _provider_keys(provider: str, settings) -> List[str]:
    if provider == "groq":
        raw = settings.groq_api_key
    elif provider == "openrouter":
        raw = settings.openrouter_api_keys
    elif provider == "dahl":
        raw = ",".join(k for k in (settings.dahl_api_key, settings.dahl_api_key_2) if k)
    else:
        raw = ""
    return [k.strip() for k in (raw or "").split(",") if k.strip()]


def _is_rate_limit(exc: Exception) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return any(s in text for s in ("429", "ratelimit", "rate limit", "rate_limit", "concurrency", "quota"))


# A rate limit that clears in a few seconds is worth waiting out: dropping to the
# next (usually weaker) model on every burst made answer quality depend on load.
MAX_RATE_LIMIT_WAIT = 8.0
# If the whole chain is rate-limited and one provider frees up within this many seconds,
# wait for it and try the chain once more before giving up.
SECOND_PASS_MAX_WAIT = 25.0


def _retry_after_seconds(exc: Exception) -> Optional[float]:
    """Seconds the provider asks us to wait, from the Retry-After header or the message."""
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if headers is not None:
        try:
            value = headers.get("retry-after")
            if value:
                return float(value)
        except (TypeError, ValueError):
            pass
    match = re.search(r"try again in ([\d.]+)\s*(ms|s)\b", str(exc), flags=re.IGNORECASE)
    if match:
        seconds = float(match.group(1))
        return seconds / 1000.0 if match.group(2).lower() == "ms" else seconds
    return None


REASONING_MIN_TOKENS = 4000       # token cap for non-Groq (reasoning) fallback models
SLOW_PROVIDER_MIN_DEADLINE = 60.0  # they need 20-30 s for a long JSON reply, Groq needs one

CHAIN_SETTING = {"fast": "llm_chain_fast", "analyze": "llm_chain_analyze", "review": "llm_chain_review"}


def invoke_llm(messages, *, purpose: str = "main", max_tokens: int = 1024,
               temperature: float = 0.1, deadline: float = 45.0,
               validate: Optional[Callable[[str], Any]] = None,
               budget: Optional[float] = None):
    """
    Call the first provider in the configured chain that answers.

    purpose picks the chain: "main" = LLM_CHAIN (final legal answer, reasoning),
    "analyze" = LLM_CHAIN_ANALYZE (finding the gaps in the client's story),
    "fast" = LLM_CHAIN_FAST (follow-up questions and answer extraction). The
    chains start on different Groq models so a burst of users spreads over
    several rate limits.

    A short rate limit is waited out once; a longer one rotates to the same
    provider's next key; any other failure moves on to the next provider/model.
    `validate`, if given, is called on the cleaned reply; if it raises (e.g.
    unparseable JSON) that provider counts as failed and the chain moves on.
    `budget` caps the total seconds spent across the whole chain: once it is
    used up no further provider is tried (a slow fallback cascade can otherwise
    take minutes when every provider is rate-limited).
    """
    from config import get_settings
    settings = get_settings()
    spec = getattr(settings, CHAIN_SETTING.get(purpose, "llm_chain"))
    failures = []
    rate_waits = []  # seconds each rate-limited provider asked us to wait
    started_all = time.time()

    def out_of_time() -> bool:
        return budget is not None and time.time() - started_all > budget

    for chain_pass in (1, 2):
        for provider, model in parse_chain(spec):
            if out_of_time():
                failures.append(f"time budget of {budget:.0f}s used up")
                break
            base_url = settings.dahl_base_url if provider == "dahl" else PROVIDER_BASE_URLS.get(provider)
            keys = _provider_keys(provider, settings)
            if not base_url or not keys:
                if chain_pass == 1:
                    failures.append(f"{provider}:{model} not configured")
                continue
            # gpt-oss reasons before answering; low effort keeps intake calls quick
            # and leaves max_tokens for the answer itself.
            extra = {"reasoning_effort": "low"} if "gpt-oss" in model else {}
            # The fallback models (Nemotron, DeepSeek V4, GLM) think for thousands of tokens before
            # the answer; at the 1,500 the Groq calls use they run out mid-thought and return nothing
            # (measured on the intake prompt: empty at 1,500, a good reply at 4,000). Groq alone
            # counts max_tokens against its per-minute limit, so only it keeps the small cap.
            if provider == "groq":
                call_max_tokens, call_deadline = max_tokens, deadline
            else:
                call_max_tokens = max(max_tokens * 3, REASONING_MIN_TOKENS)
                call_deadline = max(deadline, SLOW_PROVIDER_MIN_DEADLINE)
            for idx, key in enumerate(keys, 1):
                llm = ChatOpenAI(model=model, api_key=key, base_url=base_url, max_tokens=call_max_tokens,
                                 temperature=temperature, timeout=call_deadline, max_retries=0, **extra)
                waited = False
                text = ""
                while True:
                    started = time.time()
                    try:
                        response = invoke_with_deadline(llm, messages, call_deadline)
                        text = strip_think(response.content)
                        if not text:
                            raise ValueError("empty reply")
                        if validate is not None:
                            validate(text)
                        usage = (getattr(response, "response_metadata", None) or {}).get("token_usage") or {}
                        tokens = f" [{usage.get('prompt_tokens', '?')}+{usage.get('completion_tokens', '?')} tokens]" if usage else ""
                        logger.info(f"🤖 LLM[{purpose}] answered by {provider}:{model} in {time.time() - started:.1f}s{tokens}")
                        return response
                    except Exception as exc:
                        limited = _is_rate_limit(exc)
                        wait = _retry_after_seconds(exc) if limited else None
                        if wait is not None:
                            rate_waits.append(wait)
                        if limited and not waited and wait is not None and wait <= MAX_RATE_LIMIT_WAIT:
                            waited = True
                            logger.info(f"⏳ LLM[{purpose}] {provider}:{model} rate-limited; waiting {wait:.1f}s then retrying")
                            time.sleep(wait + 0.25)
                            continue
                        failures.append(f"{provider}:{model}#{idx} {type(exc).__name__}")
                        logger.warning(
                            f"⚡ LLM[{purpose}] {provider}:{model} key#{idx} failed after "
                            f"{time.time() - started:.1f}s ({type(exc).__name__}: {str(exc)[:450]})"
                            + (f" | reply began: {text[:160]!r}" if text and not limited else "")
                        )
                        break
                if not limited:
                    break  # the model/provider is the problem; another key won't help

        # Every provider failed. If they were mostly rate-limited and one frees up soon,
        # wait for it and run the chain once more instead of giving up (a burst of users
        # rate-limits every model at the same moment).
        if chain_pass == 1 and rate_waits and min(rate_waits) <= SECOND_PASS_MAX_WAIT and not out_of_time():
            pause = min(rate_waits) + 0.5
            logger.info(f"⏳ LLM[{purpose}] every provider failed; waiting {pause:.1f}s and trying the chain again")
            time.sleep(pause)
            rate_waits.clear()
            continue
        break

    raise RuntimeError("All LLM providers failed: " + "; ".join(failures))
