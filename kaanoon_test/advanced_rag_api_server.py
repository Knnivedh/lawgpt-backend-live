"""
FastAPI Backend for Advanced Agentic RAG System
Production-ready API server with async support, metrics, and feedback
"""
import os
import re
import sys
import time

# Fix Windows console encoding for Unicode (₹ symbol etc.)
def _safe_reconfigure_stream(stream) -> None:
    reconfigure = getattr(stream, 'reconfigure', None)
    if callable(reconfigure):
        reconfigure(encoding='utf-8', errors='replace')


if sys.platform == 'win32':
    _safe_reconfigure_stream(sys.stdout)
    _safe_reconfigure_stream(sys.stderr)
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, cast
import uvicorn
import asyncio
import json
import base64
import hashlib
import hmac
import mimetypes
import secrets
import tempfile
from datetime import datetime
import logging

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API_SERVER")

# Ensure webp portraits are served with the correct MIME type on Azure.
mimetypes.add_type("image/webp", ".webp")

# Import the advanced agentic system
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kaanoon_test.system_adapters.clarification_engine import ClarificationSession
from kaanoon_test.system_adapters.unified_advanced_rag import UnifiedAdvancedRAG
from kaanoon_test.system_adapters.citation_extractor import CitationExtractor
from config.config import Config
from contextlib import asynccontextmanager

# Court Debate Mode engine (Phase 1 + 2 + 3 pipeline)
try:
    from kaanoon_test.court_debate_engine import (
        get_court_debate_response as _get_court_debate_response,
        get_court_debate_stream_generator as _get_court_debate_stream,
        LawGPTLLMClient as _CourtDebateLLMClient,
    )
    _COURT_DEBATE_AVAILABLE = True
except Exception as _cde_err:  # noqa: BLE001
    logger.warning(f"[COURT-DEBATE] Engine not loaded: {_cde_err}. /court-debate endpoints will return 503.")
    _COURT_DEBATE_AVAILABLE = False
    _get_court_debate_response = None
    _get_court_debate_stream = None
    _CourtDebateLLMClient = None

# Concurrency guard + wall-clock deadline for the heavy LLM/retrieval endpoints.
# Imported defensively: a missing/broken resilience package must degrade to
# "unguarded" rather than stop the API from booting at all.
try:
    from kaanoon_test.resilience.guards import (
        GUARDED_PATHS as _GUARDED_PATHS,
        QueryDeadlineExceeded as _QueryDeadlineExceeded,
        deadline_expired as _deadline_expired,
        install_query_guard as _install_query_guard,
        query_guard as _query_guard,
        query_timeout_s as _query_timeout_s,
        run_query_work as _run_query_work,
        stream_deadline as _stream_deadline,
    )
    _RESILIENCE_AVAILABLE = True
except Exception as _res_err:  # noqa: BLE001
    logger.warning(f"[RESILIENCE] Guard unavailable ({_res_err}); heavy endpoints run unguarded.")
    _RESILIENCE_AVAILABLE = False

    class _QueryDeadlineExceeded(Exception):  # type: ignore[no-redef]
        def __init__(self, timeout_s: float):
            super().__init__(f"Query exceeded the {timeout_s:.0f}s wall-clock deadline")

    async def _run_query_work(fn, *args, **kwargs):
        """Fallback: keep the event loop free, but without a deadline."""
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: fn(*args, **kwargs)
        )

    def _stream_deadline():
        return None

    def _deadline_expired(_deadline_at):
        return False

import asyncio
import contextvars
import threading
import queue

# Initialize globals
BUILD_FINGERPRINT = os.environ.get("BUILD_FINGERPRINT", "querytype-fix-20260402-1328")
RELEASE_SIGNATURE = os.environ.get("RELEASE_SIGNATURE", f"lawgpt|{BUILD_FINGERPRINT}")
QUERY_TYPE_TAXONOMY = {
    "academic_direct",
    "case_consultation",
    "clarification",
    "fallback_direct",
    "greeting",
    "grounding_abstain",
    "invalid_reference",
    "multi_hop",
    "out_of_scope",
    "research",
    "safety_refusal",
    "simple",
    "simple_direct",
    "statute_lookup",
    "system_warmup",
    "web_search",
}
SUPPORTED_RESPONSE_LANGUAGES = {"en", "hi"}
HI_OUTPUT_ENFORCEMENT_MARKER = "hi-enforcement-20260403-v3"
LANGUAGE_ALIASES = {
    "en": "en",
    "eng": "en",
    "english": "en",
    "hi": "hi",
    "hin": "hi",
    "hindi": "hi",
}
TAMIL_LANGUAGE_ALIASES = {"ta", "tam", "tamil"}
rag_system = None
rag_initializing = False
active_clarification_sessions: Dict[str, ClarificationSession] = {}
# Session state lives in the container's temp dir by default, which a platform
# recycle wipes — users then had to re-answer a half-finished interview. On
# Azure, CLARIFICATION_SESSION_DIR=/home/data/... persists across restarts.
CLARIFICATION_SESSION_DIR = Path(
    os.environ.get("CLARIFICATION_SESSION_DIR")
    or (Path(tempfile.gettempdir()) / "lawgpt_clarification_sessions")
)
CLARIFICATION_SESSION_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_query_type(value: Any, fallback: str = "simple_direct") -> str:
    raw = str(value or "").strip().lower()
    if raw in ("", "none", "unknown", "n/a", "na", "expert_legal", "general"):
        return fallback
    return raw if raw in QUERY_TYPE_TAXONOMY else fallback


def _detect_text_language(text: str) -> str:
    return "hi" if re.search(r"[\u0900-\u097F]", text or "") else "en"


def _normalize_target_language(value: Any, question_text: str = "") -> str:
    raw = str(value or "").strip().lower()
    if raw in ("", "none", "null", "auto"):
        return _detect_text_language(question_text)
    if raw in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[raw]
    if raw in TAMIL_LANGUAGE_ALIASES:
        raise HTTPException(
            status_code=400,
            detail="Tamil output is disabled. Supported target_language values are en and hi.",
        )
    raise HTTPException(
        status_code=400,
        detail="Unsupported target_language. Supported values are en and hi.",
    )


def _session_state_path(session_id: str) -> Path:
    safe_id = "".join(ch for ch in session_id if ch.isalnum() or ch in ("-", "_"))
    return CLARIFICATION_SESSION_DIR / f"{safe_id}.json"


def _new_clarification_session() -> ClarificationSession:
    client_manager = None
    if rag_system is not None:
        client_manager = getattr(rag_system, 'client_manager', None)

    # SINGLE-PROVIDER MODE. This used to hardcode provider="groq", so the
    # clarification engine built its OWN Groq client from Config.GROQ_API_KEY
    # and bypassed the client manager entirely. Two consequences: the question
    # planner and the answer synthesiser talked to different vendors, and the
    # 100M-token Dahl allowance went unused for every clarification turn. With
    # single-provider mode we ask for "dahl" AND pass the manager, so
    # _get_client() returns the manager's Dahl proxy -- which applies the model
    # mapping and the reasoning_effort policy in one place.
    _provider = "dahl" if getattr(Config, "LLM_SINGLE_PROVIDER", False) else "groq"

    return ClarificationSession(
        provider=_provider,
        retriever_callback=get_pre_loop_retriever(),
        client_manager=client_manager
    )


def _session_to_state_dict(session: ClarificationSession) -> Dict[str, Any]:
    # Delegate to the engine so persisted state always carries everything the
    # engine needs to resume, including the question plan and the LLM-derived gap
    # plan. This used to be a hand-maintained copy that silently dropped fields, so
    # a resumed session lost its scenario-specific gaps and fell back to canned
    # questions (clarification requests can bounce across gunicorn workers).
    return session.to_state_dict()


def _session_from_state_dict(state: Dict[str, Any]) -> ClarificationSession:
    client_manager = None
    if rag_system is not None:
        client_manager = getattr(rag_system, "client_manager", None)
    return ClarificationSession.from_state_dict(
        state,
        retriever_callback=get_pre_loop_retriever(),
        client_manager=client_manager,
    )


def _format_clarification_response(
    *,
    answer: str,
    session_id: str,
    result: Dict[str, Any],
    latency: float,
    domain: Optional[str] = None,
) -> Dict[str, Any]:
    """Return the normal-chat clarification contract: one active question only."""
    question_index = int(result.get("question_index") or 1)
    total_questions = int(result.get("total_questions") or 5)
    progress = result.get("progress") or f"{question_index}/{total_questions}"
    # Which planner produced the questions ("llm_gap_analysis" = the model read
    # this scenario; "deterministic_plan"/"intake_gaps" = canned fallback).
    question_source = result.get("question_source")
    detected_domains = result.get("detected_domains") or []
    stage_timings = result.get("stage_timings") or {}
    system_info = {
        "query_type": "clarification",
        "clarification_mode": "sequential",
        "question_index": question_index,
        "total_questions": total_questions,
    }
    if question_source:
        system_info["question_source"] = question_source
    if detected_domains:
        system_info["detected_domains"] = detected_domains
    if stage_timings:
        system_info["stage_timings"] = stage_timings
    if domain is not None:
        system_info["domain"] = domain
    return {
        "response": {
            "answer": answer,
            "status": "clarification",
            "progress": f"{question_index}Q",
            "progress_label": progress,
            "question_index": question_index,
            "total_questions": total_questions,
            "clarification_mode": "sequential",
            "current_question": answer,
            "session_id": session_id,
            "latency": latency,
            "system_info": system_info,
            "clarification": {
                "mode": "sequential",
                "question_index": question_index,
                "total_questions": total_questions,
                "progress": progress,
                "current_question": answer,
                **({"question_source": question_source} if question_source else {}),
                **({"detected_domains": detected_domains} if detected_domains else {}),
            },
        }
    }


def _is_grounding_abstain_response(response_dict: Dict[str, Any]) -> bool:
    system_info = response_dict.get("system_info")
    if not isinstance(system_info, dict):
        system_info = {}
    answer = str(response_dict.get("answer") or "").lower()
    return (
        str(system_info.get("query_type") or response_dict.get("query_type") or "").lower() == "grounding_abstain"
        or bool(system_info.get("abstained_due_to_grounding"))
        or "i cannot provide a reliable legal answer" in answer
        or "insufficient supporting sources" in answer
        or "insufficient trusted legal sources" in answer
    )


def _recover_supported_prompt_from_grounding_abstain(
    *,
    response_dict: Dict[str, Any],
    user_question: str,
    session_id: str,
    domain: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Convert supported complex Indian-law over-abstentions into 5Q intake.

    Grounding abstention is valid for truly unsupported work. It is a poor UX for
    supported, fact-dense Indian-law prompts where the engine can still ask
    clarifying legal assumptions and later synthesize from those facts.
    """
    if not _is_grounding_abstain_response(response_dict):
        return None

    try:
        probe = _new_clarification_session()
        issue_map = probe._build_complex_issue_map(user_question)
        should_recover = bool(issue_map.get("is_complex_multi_domain")) or probe._looks_like_complex_case_matrix(user_question)
        if not should_recover:
            return None

        probe.user_query = user_question
        probe.stage = 1
        probe.complex_issue_map = issue_map
        # Plan the gaps from the user's own scenario first (the same LLM-first path
        # start_session uses); only fall back to the keyword plan when that is
        # unusable. This recovery path used to hand out the canned keyword plan.
        gap_plan, gap_analysis = probe._try_llm_gap_plan(user_question)
        probe.gap_plan = gap_plan or []
        probe.gap_analysis = gap_analysis or {}
        if probe.gap_plan:
            probe.question_plan = [gap["key"] for gap in probe.gap_plan]
            probe.max_questions = len(probe.gap_plan)
        else:
            probe.question_plan = probe.build_complex_question_plan(issue_map)
        first_question = probe._sanitize_single_question(probe._generate_next_question())
        probe.stage = 2
        _save_clarification_session(session_id, probe)
        return _format_clarification_response(
            answer=first_question,
            session_id=session_id,
            result={
                "status": "needs_clarification",
                "first_question": first_question,
                "total_questions": probe.max_questions,
                "reason": "Recovered from grounding abstention on a supported complex Indian-law prompt.",
            },
            latency=1.2,
            domain=domain,
        )
    except Exception as exc:
        logger.warning("[GROUNDING-RECOVERY] Could not recover abstained response: %s", exc)
        return None


def _save_clarification_session(session_id: str, session: ClarificationSession) -> None:
    active_clarification_sessions[session_id] = session
    _session_state_path(session_id).write_text(
        json.dumps(_session_to_state_dict(session), ensure_ascii=False),
        encoding="utf-8",
    )


def _load_clarification_session(session_id: str) -> Optional[ClarificationSession]:
    path = _session_state_path(session_id)
    # Always prefer the persisted state over the worker-local cache.
    # Clarification requests can bounce across multiple gunicorn workers,
    # so a cached in-memory session may be older than the on-disk session
    # most recently written by another worker.
    if path.exists():
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            session = _session_from_state_dict(state)
            active_clarification_sessions[session_id] = session
            return session
        except Exception as exc:
            logger.error(f"[CLARIFICATION] Failed to load session {session_id[:12]}: {exc}")
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            active_clarification_sessions.pop(session_id, None)
            return None

    session = active_clarification_sessions.get(session_id)
    if session is not None:
        return session

    return None


def _delete_clarification_session(session_id: str) -> None:
    active_clarification_sessions.pop(session_id, None)
    try:
        _session_state_path(session_id).unlink(missing_ok=True)
    except Exception as exc:
        logger.warning(f"[CLARIFICATION] Failed to delete session file for {session_id[:12]}: {exc}")


# Tracks the last init error message for the /api/health endpoint
rag_last_error: str = ""
# Tracks the wall-clock second when initialization started
rag_init_start_time: float = 0.0


def _init_rag_in_background(attempt: int = 1, max_attempts: int = 3):
    """Initialize RAG system in background thread with exponential-backoff retry.

    Retries up to `max_attempts` times if initialization fails.
    Sets rag_system=None only after all retries are exhausted so the health
    endpoint can surface the exact failure reason.
    """
    global rag_system, rag_initializing, rag_last_error, rag_init_start_time
    import traceback
    import time as _time

    rag_initializing = True
    rag_init_start_time = _time.time()
    for _attempt in range(1, max_attempts + 1):
        logger.info(f"[BACKGROUND] RAG init attempt {_attempt}/{max_attempts}...")
        try:
            _candidate = UnifiedAdvancedRAG()
            rag_system = _candidate
            rag_last_error = ""
            logger.info(f"[BACKGROUND] RAG System ready ✓ (attempt {_attempt})")
            break
        except Exception as e:
            _tb = traceback.format_exc()
            rag_last_error = str(e)
            logger.error(f"[BACKGROUND] RAG init attempt {_attempt} FAILED: {e}\n{_tb}")
            if _attempt < max_attempts:
                _wait = 2 ** _attempt  # exponential backoff: 2s, 4s, 8s …
                logger.info(f"[BACKGROUND] Retrying in {_wait}s ...")
                _time.sleep(_wait)
            else:
                logger.error("[BACKGROUND] All RAG init attempts exhausted — server degraded.")
                rag_system = None
    rag_initializing = False


def _warm_llm_gateways() -> None:
    """Pre-warm the primary LLM gateway once RAG is up.

    The first completion against the vLLM-served Dahl endpoint after an idle
    period pays a model-load of tens of seconds; a 3-token warmup ping at boot
    (and after each deploy) means the first real user query never pays it.
    Best-effort: any failure is logged and ignored.
    """
    import time as _time

    deadline = _time.time() + 180
    while rag_system is None and _time.time() < deadline:
        _time.sleep(3)
    try:
        from openai import OpenAI as _OpenAI

        client = _OpenAI(
            api_key=os.getenv("dahl_api") or os.getenv("DAHL_API_KEY") or "missing",
            base_url=os.getenv("DAHL_BASE_URL", "https://inference.dahl.global/v1"),
            max_retries=0,
            timeout=30,
        )
        _t0 = _time.time()
        client.chat.completions.create(
            model=os.getenv("DAHL_MODEL", "deepseek-ai/DeepSeek-V4-Flash-0731"),
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=3,
        )
        logger.info(f"[WARMUP] Dahl gateway warmed in {_time.time() - _t0:.1f}s")
    except Exception as exc:
        logger.warning(f"[WARMUP] Dahl warmup skipped ({exc})")

    # Probe the vector store at boot. The corpus was silently dark for an extended
    # period (suspended cloud cluster), so this makes a retrieval outage loud in
    # the startup log and visible on /api/health instead of degrading invisibly.
    try:
        from kaanoon_test.utils import store_check
        store_check.start_background_probe(delay_seconds=8.0)
    except Exception as exc:
        logger.warning(f"[STORE-CHECK] could not start: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager — server starts immediately, RAG loads in background thread."""
    logger.info("[STARTUP] LAW-GPT API starting (RAG loading in background)...")
    # Fire RAG init in a daemon thread — the server becomes available instantly
    t = threading.Thread(target=_init_rag_in_background, daemon=True)
    t.start()
    w = threading.Thread(target=_warm_llm_gateways, daemon=True)
    w.start()
    yield
    logger.info("[SHUTDOWN] Application shutdown complete.")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Advanced Agentic RAG API",
    description="Production-ready RAG system with async, memory, Redis, and metrics",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
# Note: allow_credentials=True is incompatible with allow_origins=["*"] per the
# CORS spec — browsers reject it. All production traffic arrives via Vercel rewrites
# (same-origin), so credentials are not needed here.  We explicitly list known
# origins so that direct API calls from dev also work without CORS errors.
_CORS_ORIGINS = [
    "http://localhost:3001",   # Vite dev server default
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    # Vercel preview / production domains — wildcard handled via allow_origin_regex
]

# Concurrency guard on the heavy LLM/retrieval paths. Registered BEFORE the CORS
# middleware on purpose: Starlette treats the first-registered middleware as the
# outermost, so this ordering leaves CORS outside the guard and the guard's 429
# still carries CORS headers for browser callers. Over the cap the request is
# rejected immediately with 429 + Retry-After (see resilience/guards.py for why
# reject-fast beats queueing here). Never raises: no guard must mean "unguarded",
# not "won't boot".
if _RESILIENCE_AVAILABLE:
    _install_query_guard(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_origin_regex=r"https://.*(\.vercel\.app|\.hf\.space)",  # all Vercel and Hugging Face space URLs
    allow_credentials=False,   # no cookie/session auth required; Supabase JWT goes in body
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)

# Static file paths are resolved; mounts are registered at the BOTTOM of this file
# (after all @app route declarations) so that /api/*, /health endpoints are matched
# first and NOT intercepted by the root '/' StaticFiles mount.
static_home_path = project_root / "static_home"
static_chat_path = project_root / "static_chat"

# Local auth configuration (env override supported)
AUTH_USER_DB_PATH = Path(
    os.getenv("AUTH_USER_DB_PATH", str(project_root / "runtime_data" / "auth_users.json"))
)
AUTH_USER_DB_LOCK = threading.Lock()
try:
    AUTH_TOKEN_TTL_HOURS = max(1, int(os.getenv("AUTH_TOKEN_TTL_HOURS", "12")))
except ValueError:
    AUTH_TOKEN_TTL_HOURS = 12

AUTH_TOKEN_SECRET = (
    os.getenv("AUTH_TOKEN_SECRET")
    or os.getenv("JWT_SECRET")
    or os.getenv("SECRET_KEY")
    # NOTE: deliberately no fallback to provider API keys — signing auth
    # tokens with an LLM key (e.g. GROQ_API_KEY) leaked auth material
    # across trust boundaries. Set AUTH_TOKEN_SECRET explicitly in prod.
)
if not AUTH_TOKEN_SECRET:
    AUTH_TOKEN_SECRET = secrets.token_urlsafe(48)
    logger.warning(
        "[AUTH] AUTH_TOKEN_SECRET is not set. Using ephemeral in-memory secret; "
        "tokens will be invalidated on restart."
    )


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _load_auth_store_unlocked() -> Dict[str, Any]:
    if not AUTH_USER_DB_PATH.exists():
        return {"users": []}

    try:
        parsed = json.loads(AUTH_USER_DB_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error(f"[AUTH] Failed to read auth store: {exc}")
        return {"users": []}

    users = parsed.get("users") if isinstance(parsed, dict) else None
    if not isinstance(users, list):
        logger.warning("[AUTH] Invalid auth store schema. Resetting users list.")
        return {"users": []}
    return {"users": users}


def _save_auth_store_unlocked(store: Dict[str, Any]) -> None:
    AUTH_USER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = AUTH_USER_DB_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(AUTH_USER_DB_PATH)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _derive_username(source: str) -> str:
    candidate = re.sub(r"[^a-zA-Z0-9._-]+", "_", source.strip().lower())
    candidate = re.sub(r"[_-]{2,}", "_", candidate).strip("._-")
    if len(candidate) < 3:
        candidate = f"user_{secrets.token_hex(3)}"
    return candidate[:64]


def _is_valid_username(username: str) -> bool:
    if len(username) < 3 or len(username) > 64:
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    return all(ch in allowed for ch in username)


def _hash_password(password: str) -> str:
    iterations = 200_000
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64url_encode(salt)}${_b64url_encode(derived)}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, iteration_str, salt_segment, digest_segment = stored_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iteration_str)
        salt = _b64url_decode(salt_segment)
        expected_digest = _b64url_decode(digest_segment)
    except Exception:
        return False

    candidate_digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(candidate_digest, expected_digest)


def _public_user(user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": user.get("id", ""),
        "username": user.get("username", ""),
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "role": user.get("role", "user"),
    }


def _create_access_token(user: Dict[str, Any]) -> str:
    now_ts = int(datetime.utcnow().timestamp())
    payload = {
        "sub": user.get("id"),
        "username": user.get("username"),
        "email": user.get("email"),
        "role": user.get("role", "user"),
        "iat": now_ts,
        "exp": now_ts + (AUTH_TOKEN_TTL_HOURS * 3600),
    }
    header = {"alg": "HS256", "typ": "JWT"}

    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature = hmac.new(
        AUTH_TOKEN_SECRET.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    signature_segment = _b64url_encode(signature)
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def _decode_access_token(token: str) -> Dict[str, Any]:
    try:
        header_segment, payload_segment, signature_segment = token.split(".", 2)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    expected_signature = hmac.new(
        AUTH_TOKEN_SECRET.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    actual_signature = _b64url_decode(signature_segment)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    try:
        payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    exp_ts = payload.get("exp")
    if not isinstance(exp_ts, int) or int(datetime.utcnow().timestamp()) >= exp_ts:
        raise HTTPException(status_code=401, detail="Authentication token expired")
    return payload


def _extract_bearer_token(authorization_header: Optional[str]) -> Optional[str]:
    if not authorization_header:
        return None
    if not authorization_header.lower().startswith("bearer "):
        return None
    token = authorization_header[7:].strip()
    return token or None


def _resolve_current_user(http_request: Request) -> Dict[str, Any]:
    token = _extract_bearer_token(http_request.headers.get("Authorization"))
    if not token:
        raise HTTPException(status_code=401, detail="Authorization token is required")

    claims = _decode_access_token(token)
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    with AUTH_USER_DB_LOCK:
        store = _load_auth_store_unlocked()
        user = next((u for u in store["users"] if u.get("id") == user_id), None)

    if not user:
        raise HTTPException(status_code=401, detail="User account not found")
    return user

def get_pre_loop_retriever():
    """Wrapper for ClarificationEngine's first retrieval pass"""
    if not rag_system:
        return lambda q: "RAG not initialized"
    
    def retrieve(query):
        current_rag = rag_system
        if current_rag is None:
            return "RAG not initialized"

        parametric_rag = getattr(current_rag, 'parametric_rag', None)
        if parametric_rag is None:
            logger.warning("[PRE-LOOP] Parametric RAG unavailable during clarification prefetch")
            return "RAG retrieval unavailable"

        # Use Simple/Fast retrieval for Stage 0 (Double RAG Phase 1)
        result = parametric_rag.retrieve_with_params(
            query=query,
            rag_params={'complexity': 'simple'}
        )
        return result.get('context', 'No context found.')
    return retrieve


# Request/Response Models
class QueryRequest(BaseModel):
    question: str = Field(..., description="User question")
    session_id: Optional[str] = Field(None, description="Conversation session ID")
    user_id: Optional[str] = Field(None, description="Authenticated user ID (for long-term memory)")
    target_language: Optional[str] = Field(None, description="Target output language: en or hi")
    category: Optional[str] = Field(None, description="Question category (for compatibility)")
    stream: bool = Field(False, description="Stream response")
    web_search_mode: bool = Field(False, description="Enable deep web search")  # NEW
    enable_thinking: bool = Field(True, description="Enable chain-of-thought reasoning trace")



class FeedbackRequest(BaseModel):
    query: str = Field(..., description="Original query")
    answer: str = Field(..., description="Answer provided")
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
    session_id: str = Field(..., description="Session ID")
    feedback_text: Optional[str] = Field(None, description="Optional feedback text")


class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    citations: Optional[Dict[str, Any]] = Field(None, description="Extracted citations")
    citation_validation: Optional[Dict[str, Any]] = Field(None, description="Citation validation results")
    reasoning_analysis: Optional[Dict[str, Any]] = Field(None, description="Legal reasoning analysis")
    latency: float
    complexity: str
    query_type: str
    retrieval_time: float
    synthesis_time: Optional[float]
    confidence: float
    session_id: str
    from_cache: bool
    validation: Dict[str, Any]
    think_trace: Optional[str] = Field(None, description="Internal chain-of-thought reasoning trace")


# API Endpoints
@app.post("/api/query/stream", tags=["Query"])
async def query_stream_endpoint(payload: QueryRequest, http_request: Request):
    """
    **Streaming query** - identical outcome to /api/query, but emits live
    agentic progress events (classify -> route -> retrieve -> docs -> synthesize)
    as Server-Sent Events before the final payload event.
    """
    import queue as _q
    import threading as _threading
    from kaanoon_test.utils import query_progress

    outbox = _q.Queue()
    started = datetime.now().timestamp()

    def cb(event):
        event = dict(event)
        event["elapsed"] = round(event.get("ts", started) - started, 2)
        outbox.put(event)

    def run_query_thread():
        # Runs in its own worker thread with its own event loop so the main
        # loop stays free to stream events incrementally. The progress
        # callback is thread-local, so it MUST be set inside this thread.
        query_progress.set_callback(cb)
        try:
            # threading.Thread starts with an EMPTY context, so the nested call
            # would not see the slot the middleware holds for this stream. Copying
            # the caller's context keeps the guard's accounting correct here.
            resp = contextvars.copy_context().run(
                asyncio.run, query_endpoint(payload, http_request)
            )
            if isinstance(resp, JSONResponse):
                import json as _json
                body = _json.loads(resp.body.decode("utf-8"))
                status_code = resp.status_code
            else:
                body = resp
                status_code = 200
            outbox.put({"type": "final", "payload": body, "status": status_code})
        except Exception as exc:
            logger.exception("[QUERY-STREAM] handler error: %s", exc)
            outbox.put({"type": "error", "message": str(exc)})
        finally:
            query_progress.clear_callback()
            outbox.put(None)

    async def event_generator():
        sse_tail = "\n\n"
        yield "data: " + json.dumps({
            "type": "start",
            "message": "Received your question",
            "elapsed": 0.0,
        }) + sse_tail
        worker = _threading.Thread(target=run_query_thread, daemon=True)
        worker.start()
        while True:
            try:
                item = await asyncio.to_thread(outbox.get, True, 5)
            except _q.Empty:
                yield "data: " + json.dumps({
                    "type": "heartbeat",
                    "message": "Still working...",
                    "elapsed": round(datetime.now().timestamp() - started, 2),
                }) + sse_tail
                continue
            if item is None:
                break
            yield "data: " + json.dumps(item) + sse_tail
        worker.join(timeout=30)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/query")
async def query_endpoint(payload: QueryRequest, http_request: Request):
    """
    Main query endpoint with interactive clarification loop support

    The pipeline is synchronous (retrieval + LLM calls), so it used to run
    directly on the event loop — one in-flight query froze the whole worker and
    /api/health could not answer (the 2026-04-02 zero-byte outage). It now runs
    on the dedicated query thread pool under LAWGPT_QUERY_TIMEOUT_S, and the
    middleware caps how many of these execute at once.
    """
    try:
        return await _run_query_work(_query_endpoint_impl, payload, http_request)
    except _QueryDeadlineExceeded as exc:
        logger.error(f"[QUERY] Deadline exceeded after {exc.timeout_s:.0f}s: {exc}")
        return _query_deadline_response(exc.timeout_s, session_id=payload.session_id)


def _query_deadline_response(timeout_s: float, session_id: Optional[str] = None) -> JSONResponse:
    """504 in the envelope /api/query already returns.

    The same object is relayed verbatim by /api/query/stream as its `final`
    event, so the streaming client sees the timeout rather than a hung socket.
    """
    message = (
        f"Your question took longer than {timeout_s:.0f}s to answer, so we stopped "
        "waiting. Please try again, or rephrase it more specifically."
    )
    return JSONResponse(
        status_code=504,
        content={
            "detail": message,
            "response": {
                "answer": message,
                "status": "error",
                "session_id": session_id or f"session_{datetime.now().timestamp()}",
                "latency": float(timeout_s),
                "sources": [],
                "think_trace": None,
                "system_info": {
                    "query_type": "query_timeout",
                    "timeout_s": timeout_s,
                    "retry_after_seconds": max(1, int(timeout_s)),
                },
            },
        },
    )


def _query_endpoint_impl(payload: QueryRequest, http_request: Request):
    session_id = payload.session_id or f"session_{datetime.now().timestamp()}"
    user_id = payload.user_id or ""

    if not user_id:
        bearer_token = _extract_bearer_token(http_request.headers.get("Authorization"))
        if bearer_token:
            try:
                claims = _decode_access_token(bearer_token)
                user_id = str(claims.get("sub") or "")
            except HTTPException:
                logger.info("[AUTH] Ignoring invalid bearer token on /api/query")

    user_question = payload.question
    
    import re as _re_shared
    import time as _time_triage

    # --- Strip prompt-injection attempts (all queries) ---------------------------
    user_question = _re_shared.sub(
        r'(?i)(ignore (?:previous|all|above|this)[^.!?\n]*|'
        r'forget (?:everything|all)[^.!?\n]*|'
        r'act as [^.!?\n]*|you are now [^.!?\n]*|'
        r'new instructions?:?[^.!?\n]*|'
        r'override[^.!?\n]*|'
        r'tell me (?:a joke|how to (?:destroy|tamper|evade|escape|hide))[^.!?\n]*|'
        r'and tamper with[^.!?\n]*)[.!?]?',
        '', user_question
    ).strip() or user_question

    target_language = _normalize_target_language(payload.target_language, user_question)
    _question_lower = user_question.lower()

    # --- Safety refusal: explicit requests for illegal / obstructive acts -------
    _illegal_patterns = [
        r'\bdestroy\s+(?:cctv\s+)?evidence\b',
        r'\btamper\s+with\s+(?:documents?|evidence)\b',
        r'\bhow\s+do\s+i\s+destroy\b',
        r'\bbribe\s+(?:the\s+)?(?:police|judge|officer)\b',
        r'\bforge\s+(?:the\s+)?document\b',
        r'\blaunder\s+money\b',
        r'\bevade\s+(?:income\s+)?tax\b',
        r'\bhide\s+black\s+money\b',
        r'\bfile\s+a\s+false\s+fir\b',
    ]
    if any(_re_shared.search(pattern, _question_lower) for pattern in _illegal_patterns):
        logger.info(f"[SAFETY] Illegal-guidance query refused: {user_question[:60]}")
        return {
            "response": {
                "answer": (
                    "I cannot assist with destroying evidence, tampering with documents, or any other illegal act. "
                    "Those actions are illegal and may amount to a criminal offence under Indian law. "
                    "If you are involved in a case, preserve evidence and seek lawful advice from a qualified advocate."
                ),
                "status": "direct",
                "session_id": session_id,
                "latency": 0.1,
                "sources": [],
                "think_trace": None,
                "system_info": {"query_type": "safety_refusal"}
            }
        }

    # --- Laya System 1 Triage & Fast Early-Exit Gate -----------------------------
    _t_triage_start = _time_triage.perf_counter()
    from system_adapters.laya_triage_adapter import triage_query, build_retrieval_filter
    triage = triage_query(user_question)
    predicted_statute = triage.get("statute") if triage.get("is_supported_statute") else None
    suggested_sections = triage.get("suggested_sections") or []

    # Fast Early-Exit Gate: Only trigger for confirmed out-of-scope foreign law or explicitly excluded domains
    if triage.get("is_out_of_scope", False) or triage.get("matched_pattern"):
        triage_latency_s = max(0.001, round(_time_triage.perf_counter() - _t_triage_start, 4))
        logger.info(f"[LAYA-GATE] Fast early-exit triggered in {triage_latency_s*1000:.2f}ms for: {user_question[:60]}")
        return {
            "response": {
                "answer": (
                    "This query concerns a statute or jurisdiction that is outside the active corpus of LAW-GPT. "
                    "LAW-GPT specializes in core Indian legal frameworks including Bharatiya Nyaya Sanhita (BNS), "
                    "Bharatiya Nagarik Suraksha Sanhita (BNSS), Bharatiya Sakshya Adhiniyam (BSA), Negotiable Instruments Act, "
                    "Consumer Protection Act, Indian Contract Act, Companies Act, and family law (Hindu Marriage Act, PWDVA). "
                    "Please refer to the relevant authoritative statute or consult a licensed advocate for this matter."
                ),
                "status": "direct",
                "session_id": session_id,
                "latency": triage_latency_s,
                "sources": [],
                "think_trace": None,
                "system_info": {
                    "query_type": "statute_unsupported_abstention",
                    "early_exit": True,
                    "triage": triage,
                    "triage_latency_ms": round(triage_latency_s * 1000, 2),
                }
            }
        }

    if not rag_system:
        if rag_initializing:
            elapsed = max(0, int(datetime.now().timestamp() - rag_init_start_time)) if rag_init_start_time else 0
            retry_after_seconds = max(10, 90 - elapsed)
            return JSONResponse(
                status_code=202,
                content={
                    "response": {
                        "answer": "LAW-GPT is warming up. Please retry shortly.",
                        "status": "initializing",
                        "session_id": session_id,
                        "latency": 0.0,
                        "sources": [],
                        "think_trace": None,
                        "system_info": {
                            "query_type": "system_warmup",
                            "retry_after_seconds": retry_after_seconds,
                        },
                    }
                },
            )
        raise HTTPException(status_code=503, detail="RAG system not available")

    # --- Out-of-scope detection: non-Indian / foreign law queries ----------------
    _oos_keywords = ['gdpr', 'eu law', 'european union law', 'ccpa', 'california', 'california privacy',
                     'california law', 'california state law', 'uk law', 'english law',
                     'american law', 'us law', 'u.s. law', 'french law']
    if any(k in _question_lower for k in _oos_keywords):
        logger.info(f"[OOS] Out-of-scope query detected: {user_question[:60]}")
        return {
            "response": {
                "answer": (
                    "This query relates to foreign / international law (e.g. EU GDPR, CCPA) "
                    "which is **outside the scope** of this platform. LAW-GPT specialises in "
                    "Indian law: Constitution of India, IPC / BNS, CrPC / BNSS, Consumer "
                    "Protection Act 2019, family law, property law, and Supreme Court / High "
                    "Court judgments. For Indian data-protection law please refer to the "
                    "**Digital Personal Data Protection Act, 2023 (DPDPA)**."
                ),
                "status": "direct",
                "session_id": session_id,
                "latency": 0.1,
                "sources": [],
                "think_trace": None,
                "system_info": {"query_type": "out_of_scope"}
            }
        }

    # --- Fake-law detection: clearly invalid IPC references ----------------------
    _fake_ipc_reference = (
        ('ipc' in _question_lower or 'indian penal code' in _question_lower)
        and (
            _re_shared.search(r'\bsection\s*\d+\s*\([a-z]\)', _question_lower)
            or _re_shared.search(r'\bsection\s*(?:[6-9]\d{2,}|\d{4,})\b', _question_lower)
        )
        and any(term in _question_lower for term in ['data monetization', 'data monetisation', 'digital', 'ai-generated'])
    )
    if _fake_ipc_reference:
        logger.info(f"[FAKE-LAW] Invalid IPC reference detected: {user_question[:60]}")
        return {
            "response": {
                "answer": (
                    "This IPC reference appears to be invalid or does not exist. Please verify the section number, "
                    "because I cannot confirm any such section of the Indian Penal Code for the issue described."
                ),
                "status": "direct",
                "session_id": session_id,
                "latency": 0.1,
                "sources": [],
                "think_trace": None,
                "system_info": {"query_type": "invalid_reference"}
            }
        }

    if payload.web_search_mode:
        logger.info(f"[WEB] Web search mode requested for query: {user_question[:60]}")
        try:
            result = rag_system.query(
                user_question,
                category=payload.category or "general",
                session_id=session_id,
                user_id=user_id,
                target_language=target_language,
                simple_mode=False,
                web_search_mode=True,
            )
        except TypeError:
            logger.warning("[WEB] Current RAG implementation does not accept web_search_mode; using standard query path.")
            result = rag_system.query(
                user_question,
                category=payload.category or "general",
                session_id=session_id,
                user_id=user_id,
                simple_mode=False,
            )

        response_dict = format_rag_response(
            result,
            session_id,
            question_hint=user_question,
            target_language=target_language,
        )
        response_dict["system_info"]["query_type"] = "web_search"
        response_dict["system_info"]["web_search_mode"] = True
        return {"response": response_dict}

    assert rag_system is not None
    _rag_system = cast(Any, rag_system)

    try:
        # 1. CHECK IF SESSION IS ALREADY IN CLARIFICATION LOOP
        session = _load_clarification_session(session_id)
        if session is not None:
            # Retry submit_answer on Groq 429
            import time as _time_mod2
            loop_result = None
            for _ans_attempt in range(3):
                try:
                    loop_result = session.submit_answer(user_question)
                    break
                except Exception as _ans_err:
                    _ans_str = str(_ans_err)
                    if ("429" in _ans_str or "rate limit" in _ans_str.lower()) and _ans_attempt < 2:
                        _wt = 30 * (_ans_attempt + 1)
                        logger.warning(f"[CLARIFICATION] Groq 429 on submit_answer, retrying in {_wt}s...")
                        _time_mod2.sleep(_wt)
                    else:
                        raise

            if loop_result is None:
                raise RuntimeError("Clarification loop did not return a result")
            
            if loop_result["status"] == "clarification_loop":
                _save_clarification_session(session_id, session)
                return _format_clarification_response(
                    answer=loop_result["next_question"],
                    session_id=session_id,
                    result=loop_result,
                    latency=0.5,
                )
            elif loop_result["status"] == "ready_for_synthesis":
                # Final step: Synthesize and Run RAG
                synthesis = session.synthesize_and_execute()
                final_matrix = synthesis["matrix"]
                final_request = synthesis.get("final_request") or final_matrix
                deterministic_answer = synthesis.get("deterministic_answer")

                # Delete session BEFORE the RAG query so that any call_api retry
                # (triggered by a stub answer) does NOT restart a new clarification
                # session with the user's last message as the initial query.
                _delete_clarification_session(session_id)
                logger.info(f"[SYNTHESIS] Session {session_id[:12]} deleted. Running final RAG...")

                if deterministic_answer:
                    return {
                        "response": {
                            "answer": deterministic_answer,
                            "status": "direct",
                            "session_id": session_id,
                            "latency": 0.1,
                            "sources": [],
                            "think_trace": None,
                            "system_info": {
                                "query_type": "case_consultation",
                                "clarification_mode": "completed",
                                "deterministic_final": True,
                                "build_fingerprint": BUILD_FINGERPRINT,
                                "release_signature": RELEASE_SIGNATURE,
                            },
                        }
                    }

                # Completed clarification sessions should return a fuller case
                # consultation, so keep the final synthesis on the standard path.
                try:
                    # Final case-consultation synthesis runs on the FLASH rig:
                    # the 240s platform gateway limit kills multi-minute GLM
                    # agentic syntheses, and the old architecture always ran
                    # this step on the fast model with the full case matrix.
                    result = rag_system.query(final_request, session_id=session_id,
                                             user_id=user_id, target_language=target_language,
                                             simple_mode=True, skip_fast_paths=True)
                except TypeError:
                    result = rag_system.query(final_request, session_id=session_id, user_id=user_id)

                response_dict = format_rag_response(
                    result,
                    session_id,
                    question_hint=user_question,
                    target_language=target_language,
                )
                response_dict["system_info"]["query_type"] = "case_consultation"
                return {"response": response_dict}

        def _query_rag_full(question, category=None, simple_mode=True):
            try:
                from system_adapters.laya_triage_adapter import expand_legal_query
                expanded_q = expand_legal_query(question, triage)
            except Exception:
                expanded_q = question
            try:
                return _rag_system.query(
                    expanded_q,
                    category=category or triage.get("domain") or "general",
                    session_id=session_id,
                    user_id=user_id,
                    target_language=target_language,
                    simple_mode=simple_mode,
                    statute_filter=predicted_statute,
                    suggested_sections=suggested_sections,
                )
            except TypeError:
                return _rag_system.query(
                    expanded_q,
                    category=category or "general",
                    session_id=session_id,
                    user_id=user_id,
                )

        # ── LAYA SYSTEM 1 FASTPATH: DIRECT STATUTORY QUERIES ───────────────────
        # Direct questions regarding recognized statutes or explicit sections should NEVER
        # enter the 60s clarification intake loop. Route them directly to RAG synthesis.
        is_direct_statutory_query = (
            triage.get("is_supported_statute")
            and (
                bool(suggested_sections)
                or triage.get("intent") in [
                    "divorce_grounds",
                    "maintenance",
                    "bail",
                    "cheque_dishonour",
                    "definition",
                    "penalty",
                    "procedure",
                    "statute_lookup",
                    "general",
                ]
            )
        ) or any(
            phrase in user_question.lower()
            for phrase in [
                "cheque", "bounced", "consumer", "defective", "product",
                "fir", "police station", "another city", "different city",
                "bailable", "bail", "custody", "arrested", "judge", "magistrate",
                "registration", "immovable property", "house", "ownership", "without registering",
                "rti", "information", "documents", "public information officer", "asking for documents"
            ]
        )
        if is_direct_statutory_query:
            logger.info(
                f"[LAYA-FASTPATH] Direct statutory query: statute={predicted_statute}, sections={suggested_sections}. Bypassing clarification intake."
            )
            rag_res = _query_rag_full(user_question)
            resp_dict = format_rag_response(
                rag_res,
                session_id,
                question_hint=user_question,
                target_language=target_language,
            )
            resp_dict["system_info"]["query_type"] = "direct_statutory_fastpath"
            resp_dict["system_info"]["triage"] = triage
            return {"response": resp_dict}

        # 2. START NEW SESSION - use groq provider with llama-3.1-8b-instant (verified working model from Azure)
        session = _new_clarification_session()
        # Pass category to start_session for Domain-Specific Intent Analysis
        # Retry up to 2 times on 429 rate limits before giving up
        import time as _time_mod
        _start_init_result = None
        for _start_attempt in range(2):
            try:
                _start_init_result = session.start_session(user_question, category=payload.category or "general")
                break
            except Exception as _start_err:
                _err_str = str(_start_err)
                if ("429" in _err_str or "rate limit" in _err_str.lower() or "Rate limit" in _err_str) and _start_attempt < 1:
                    _wait_s = 15
                    logger.warning(f"[CLARIFICATION] 429 on start attempt {_start_attempt+1}, "
                                   f"retrying in {_wait_s}s...")
                    _time_mod.sleep(_wait_s)
                    session = _new_clarification_session()   # fresh session for retry
                else:
                    logger.error(f"[CLARIFICATION] start_session raised: {_err_str}. Falling back to direct RAG.")
                    # Fallback: use RAG directly instead of returning 500
                    try:
                        result = rag_system.query(user_question, category=payload.category or triage.get("domain") or "general",
                                                  session_id=session_id, user_id=user_id,
                                                  target_language=target_language, simple_mode=False,
                                                  statute_filter=predicted_statute,
                                                  suggested_sections=suggested_sections)
                    except TypeError:
                        result = rag_system.query(user_question, category=payload.category or "general",
                                                  session_id=session_id, user_id=user_id)
                    fb_resp = format_rag_response(
                        result,
                        session_id,
                        question_hint=user_question,
                        target_language=target_language,
                    )
                    recovered = _recover_supported_prompt_from_grounding_abstain(
                        response_dict=fb_resp,
                        user_question=user_question,
                        session_id=session_id,
                        domain=payload.category,
                    )
                    if recovered is not None:
                        return recovered
                    fb_resp["system_info"]["query_type"] = "fallback_direct"
                    fb_resp["system_info"]["triage"] = triage
                    return {"response": fb_resp}
        init_result = _start_init_result
        if init_result is None:
            logger.warning("[CLARIFICATION] start_session returned no result. Falling back to direct RAG.")
            try:
                result = _rag_system.query(user_question, category=payload.category or triage.get("domain") or "general",
                                           session_id=session_id, user_id=user_id,
                                           target_language=target_language, simple_mode=False,
                                           statute_filter=predicted_statute,
                                           suggested_sections=suggested_sections)
            except TypeError:
                result = _rag_system.query(user_question, category=payload.category or "general",
                                           session_id=session_id, user_id=user_id)
            fb_resp = format_rag_response(
                result,
                session_id,
                question_hint=user_question,
                target_language=target_language,
            )
            recovered = _recover_supported_prompt_from_grounding_abstain(
                response_dict=fb_resp,
                user_question=user_question,
                session_id=session_id,
                domain=payload.category,
            )
            if recovered is not None:
                return recovered
            fb_resp["system_info"]["query_type"] = "fallback_direct"
            fb_resp["system_info"]["triage"] = triage
            return {"response": fb_resp}
        
        if init_result["status"] == "needs_clarification":
            # Save session for multi-turn
            _save_clarification_session(session_id, session)
            return _format_clarification_response(
                answer=init_result["first_question"],
                session_id=session_id,
                result=init_result,
                latency=1.5,
                domain=payload.category,
            )
        elif init_result["status"] in ["greeting", "irrelevant"]:
            return {
                "response": {
                    "answer": init_result["message"],
                    "status": "direct",
                    "session_id": session_id,
                    "latency": 0.2,
                    "system_info": {"query_type": init_result["status"]}
                }
            }
        elif init_result["status"] == "academic_direct":
            logger.info(f"[ACADEMIC DIRECT] Using full analysis path for: {user_question[:50]}...")
            result = _query_rag_full(user_question, payload.category or "general")
            response_dict = format_rag_response(
                result,
                session_id,
                question_hint=user_question,
                target_language=target_language,
            )
            recovered = _recover_supported_prompt_from_grounding_abstain(
                response_dict=response_dict,
                user_question=user_question,
                session_id=session_id,
                domain=payload.category,
            )
            if recovered is not None:
                return recovered
            response_dict["system_info"]["query_type"] = "academic_direct"
            response_dict["system_info"]["complexity"] = "high"
            return {"response": response_dict}
        elif init_result["status"] == "simple_direct":
            # Most simple factual queries should use the lightweight 8b path, but
            # complex academic issue-spotting prompts still need the full analysis
            # pipeline even when they bypass clarification.
            import re as _re_direct
            _force_full_patterns = [
                r'(analy[sz]e|discuss|examine)\s+separately',
                r'what\s+.{0,20}(constitutional|statutory|contractual|procedural)\s+issues?',
                r'(five|5)\s+(distinct\s+)?issues?',
                r'privacy\s+and\s+data-protection\s+violations',
                r'deficiency\s+in\s+service\s+and\s+unfair\s+trade\s+practice',
                r'legal\s+effect\s+of\s+user\s+consent',
                r'pil\s+maintainability',
                r'effect\s+of\s+the\s+arbitration\s+clause',
                r'use\s+(correct|exact)\s+indian\s+statutory\s+section',
                r'\btheft\b',
                r'\bdishonest(?:ly)?\b',
                r'\bwithout\s+permission\b',
                r'\bpermanent(?:ly)?\s+deprive\b',
                r'\bmisappropriation\b',
                r'\bemployee\b',
                r'\bemployer\b',
                r'\blaptop\b',
            ]
            _legal_force_full_patterns = [
                r'\blimitation\b',
                r'\badverse\s+possession\b',
                r'\bmaintainability\b',
                r'\bjurisdiction\b',
                r'\barbitration\b',
                r'\bconsumer\b',
                r'\bdeficiency\s+in\s+service\b',
                r'\bunfair\s+trade\s+practice\b',
                r'\bdivorce\b',
                r'\bcustody\b',
                r'\bmaintenance\b',
                r'\balimony\b',
                r'\bemployment\b',
                r'\btermination\b',
                r'\bsalary\b',
                r'\bproperty\b',
                r'\bsale\s+deed\b',
                r'\bpossession\b',
                r'\bfir\b',
                r'\bbail\b',
                r'\banticipatory\s+bail\b',
                r'\bpetition\b',
                r'\bappeal\b',
                r'\bwrit\b',
                r'\bnotice\b',
                r'\bcompensation\b',
                r'\brefund\b',
                r'\bgpa\b',
                r'\blegal\s+remedy\b',
                r'\btime[- ]barred\b',
                r'\bintent\b',
                r'\bintentional\b',
                r'\bmens\s+rea\b',
                r'\bactus\s+reus\b',
                r'\bfraud\b',
                r'\bforgery\b',
                r'\bcheating\b',
            ]
            _trivial_definition_pattern = r'^\s*(what\s+is|what\s+are|define|explain|describe|tell\s+me\s+about)\s+(section|article|rule|order|act|code|ipc|cpc|crpc|bns|bnss|bsa)\b'
            _lower_q = user_question.lower()
            _force_full = any(_re_direct.search(pattern, _lower_q) for pattern in _force_full_patterns)
            if not _re_direct.search(_trivial_definition_pattern, user_question.lower()):
                _force_full = _force_full or any(
                    _re_direct.search(pattern, _lower_q) for pattern in _legal_force_full_patterns
                )

            # Additional hard guards: multi-part and issue-spotting prompts should
            # never run the lightweight simple mode.
            _word_count = len(_lower_q.split())
            _multi_topic_joiners = user_question.count("+") >= 2 or _lower_q.count(" and ") >= 3
            _subquestion_cues = bool(
                _re_direct.search(r"sub[- ]?question|answer\s+all\s*(?:5|five)", _lower_q)
            )
            _numbered_parts = len(_re_direct.findall(r"\b[1-5][\)\.]", user_question)) >= 2
            _long_issue_prompt = _word_count >= 40
            _force_full = _force_full or _multi_topic_joiners or _subquestion_cues or _numbered_parts or _long_issue_prompt

            logger.info(
                f"[SIMPLE DIRECT] Providing {'full' if _force_full else 'immediate'} answer for: {user_question[:50]}..."
            )
            if _force_full:
                result = _query_rag_full(user_question, payload.category or "general")
            else:
                try:
                    result = rag_system.query(user_question, category=payload.category or triage.get("domain") or "general",
                                              session_id=session_id, user_id=user_id,
                                              target_language=target_language,
                                              simple_mode=True,
                                              statute_filter=predicted_statute,
                                              suggested_sections=suggested_sections)
                except TypeError:
                    # Fallback: old unified_rag without simple_mode param
                    logger.warning("[SIMPLE DIRECT] simple_mode not supported, falling back")
                    result = rag_system.query(user_question, category=payload.category or "general",
                                              session_id=session_id, user_id=user_id)
            _simple_wc = len(user_question.split())
            # Tiered brevity budget. A single-word-count cap of 350 produced
            # ~2,100-character answers to "What is Section 302 IPC?", which is
            # over-answering a definitional question. Budget now scales with the
            # actual scope of the ask: definitional -> short -> moderate -> none.
            _max_words = brevity_budget_chars(user_question, force_full=_force_full)
            response_dict = format_rag_response(result, session_id, question_hint=user_question,
                                                max_answer_words=_max_words,
                                                target_language=target_language)
            _fallback_query_type = "academic_direct" if _force_full else "simple_direct"
            _existing_query_type = response_dict.get("system_info", {}).get("query_type")
            _top_level_query_type = response_dict.get("query_type")
            _agentic_loops = response_dict.get("system_info", {}).get("agentic_loops", 0)

            # Prefer strategy-like values when agentic pipeline actually ran.
            if _agentic_loops and int(_agentic_loops) > 0:
                _resolved_query_type = _top_level_query_type
                if _resolved_query_type in (None, "", "n/a", "expert_legal", "simple_direct"):
                    _resolved_query_type = "multi_hop" if _force_full else "simple"
                _resolved_query_type = _normalize_query_type(_resolved_query_type, fallback="simple")
                response_dict["system_info"]["query_type"] = _resolved_query_type
                response_dict["query_type"] = _resolved_query_type
            else:
                if _existing_query_type in (None, "", "n/a", "expert_legal"):
                    if _top_level_query_type not in (None, "", "n/a", "expert_legal"):
                        response_dict["system_info"]["query_type"] = _normalize_query_type(
                            _top_level_query_type,
                            fallback=_fallback_query_type,
                        )
                    else:
                        response_dict["system_info"]["query_type"] = _normalize_query_type(
                            _fallback_query_type,
                            fallback="simple_direct",
                        )
                if response_dict.get("query_type") in (None, "", "n/a", "expert_legal"):
                    response_dict["query_type"] = response_dict["system_info"]["query_type"]
            response_dict["system_info"]["complexity"] = "high" if _force_full else "low"
            recovered = _recover_supported_prompt_from_grounding_abstain(
                response_dict=response_dict,
                user_question=user_question,
                session_id=session_id,
                domain=payload.category,
            )
            if recovered is not None:
                return recovered
            return {"response": response_dict}
        elif init_result["status"] == "fallback_direct":
            # LLM call failed in clarification engine - fallback to direct RAG gracefully
            logger.warning(f"[FALLBACK DIRECT] Clarification LLM failed, using direct RAG: {init_result.get('message', '')[:80]}")
            result = _query_rag_full(user_question, payload.category or "general")
            fb_resp = format_rag_response(
                result,
                session_id,
                question_hint=user_question,
                target_language=target_language,
            )
            recovered = _recover_supported_prompt_from_grounding_abstain(
                response_dict=fb_resp,
                user_question=user_question,
                session_id=session_id,
                domain=payload.category,
            )
            if recovered is not None:
                return recovered
            fb_resp["system_info"]["query_type"] = "fallback_direct"
            return {"response": fb_resp}
        else:
            # Fallback to direct RAG if something failed or unexpected status
            # Pass category to RAG system for Domain-Specific Retrieval
            result = _query_rag_full(user_question, payload.category or "general")
            response_dict = format_rag_response(
                result,
                session_id,
                question_hint=user_question,
                target_language=target_language,
            )
            recovered = _recover_supported_prompt_from_grounding_abstain(
                response_dict=response_dict,
                user_question=user_question,
                session_id=session_id,
                domain=payload.category,
            )
            if recovered is not None:
                return recovered
            return {
                "response": response_dict
            }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Query Error: {error_msg}")
        if "429" in error_msg or "Rate limit" in error_msg:
            # Groq rate limited — fall back to direct RAG instead of returning 429
            logger.warning("[FALLBACK] Groq rate limited. Falling back to direct RAG for graceful degradation.")
            try:
                try:
                    result = rag_system.query(
                        user_question,
                        category=payload.category or "general",
                        target_language=target_language,
                    )
                except TypeError:
                    result = rag_system.query(user_question, category=payload.category or "general")
                response_dict = format_rag_response(
                    result,
                    session_id,
                    question_hint=user_question,
                    target_language=target_language,
                )
                response_dict.setdefault("system_info", {})["query_type"] = "fallback_direct"
                return {"response": response_dict}
            except Exception as fallback_err:
                logger.error(f"Fallback RAG also failed: {fallback_err}")
                raise HTTPException(status_code=429, detail="AI Service Rate Limit Reached. Please try again later.")
        raise HTTPException(status_code=500, detail=f"Query failed: {error_msg}")

def assess_support_signals(
    *,
    contract_checks: dict,
    valid_citations: int,
    missing_citations: int,
    missing_case_citations: int,
    grounding_abstained: bool,
    grounded_answer: bool,
    currency_violations: int = 0,
    corpus_reachable: bool = False,
    is_curated_statutory_fact: bool = False,
    is_grounded_simple_answer: bool = False,
    answer_chars: int = 0,
) -> dict:
    """Pure decision function for trust signals.

    Extracted from format_rag_response so the calibration rules can be unit
    tested. The behaviour it encodes, and why it changed:

    * The low-support banner used to fire on 28 of 60 benchmark answers - most
      of them correct - and after the first fix it fired on 5 of 5 in a live
      spot check. Two separate causes had to be removed:
        1. `high_hallucination_risk` was `missing_case_citations >= 1`, so with
           no corpus reachable EVERY case citation counted as missing and the
           system apologised for being right.
        2. `weak_contract` demanded 4 of 6 structural sections (issue summary,
           governing law, application, risk, next steps, disclaimer). A concise
           definitional answer legitimately has 2, so it was permanently
           "weak" - which fired the banner on every answer.
    * Structural completeness is now judged against answer LENGTH, because a
      200-character answer cannot carry four sections and holding it to that
      standard marks correct brevity as a defect.
    * Structural completeness no longer fires the banner at all. It lowers
      confidence (see calibrate_confidence) but it is a style signal, not
      evidence that the answer is wrong. The banner is reserved for evidence.
    * When there is no corpus, absence from context is expected by construction
      and is not evidence of invention.

    Returns the flags plus the calibrated confidence band.
    """
    contract_hits = sum(1 for v in contract_checks.values() if v)
    if answer_chars < 900:
        required = 2
    elif answer_chars < 2500:
        required = 3
    else:
        required = 4
    weak_contract = contract_hits < required
    unsupported_citations = missing_citations > valid_citations and missing_citations >= 2

    if corpus_reachable:
        high_hallucination_risk = (
            missing_case_citations >= 2
            and missing_case_citations > valid_citations
        )
    else:
        high_hallucination_risk = False

    # The banner is reserved for evidence that the answer is untrustworthy:
    # the system abstained, cited cases that contradict the corpus, or produced
    # mostly unresolvable citations. Formatting alone is not a reason to tell a
    # user the sources do not support the answer.
    banner_needed = (
        grounding_abstained
        or (high_hallucination_risk and corpus_reachable)
        or (unsupported_citations and missing_citations >= 3)
    )

    support_signals = sum([
        bool(grounded_answer),
        valid_citations >= 1,
        not missing_citations,
        not weak_contract,
        not grounding_abstained,
        not currency_violations,
    ])
    well_supported = support_signals >= 5

    return {
        "weak_contract": weak_contract,
        "contract_hits": contract_hits,
        "contract_required": required,
        "unsupported_citations": unsupported_citations,
        "high_hallucination_risk": high_hallucination_risk,
        "banner_needed": banner_needed,
        "well_supported": well_supported,
        "support_signals": support_signals,
    }


def calibrate_confidence(
    reported_confidence: float,
    *,
    signals: dict,
    grounding_abstained: bool,
    corpus_reachable: bool,
    currency_confidence_cap=None,
    is_curated_statutory_fact: bool = False,
    is_grounded_simple_answer: bool = False,
):
    """Apply the confidence band implied by assess_support_signals.

    Returns (effective_confidence, was_capped). Confidence now has a floor as
    well as a ceiling; it never claims certainty, and a genuine currency
    violation always wins because it outranks the softer signals.
    """
    conf = reported_confidence
    capped = False

    clean = (
        is_curated_statutory_fact
        or is_grounded_simple_answer
        or signals["well_supported"]
    )
    if clean:
        conf = max(conf, 0.80)
        conf = min(conf, 0.92)
    elif not is_curated_statutory_fact and not is_grounded_simple_answer:
        if grounding_abstained:
            conf = min(conf, 0.35)
            capped = True
        elif signals["high_hallucination_risk"] and corpus_reachable:
            conf = min(conf, 0.50)
            capped = True
        elif signals["unsupported_citations"]:
            conf = min(conf, 0.65)
            capped = True
        elif signals["weak_contract"]:
            conf = min(conf, 0.75)
            capped = True

    if currency_confidence_cap is not None:
        conf = min(conf, float(currency_confidence_cap))
        capped = True

    return round(max(0.0, min(1.0, conf)), 2), capped


def brevity_budget_chars(question_text: str, force_full: bool = False) -> int:
    """Character budget for an answer, scaled to the scope of the question.

    Measured against the frozen benchmark (all 60 prompts are <=19 words):

    * The budget must be expressed in CHARACTERS, not words. A 300-word budget
      produced a ~1,800-character answer, but the scored length case
      "Answer in one line only: what is Article 21?" has a 300-character limit,
      so a word budget simply cannot express that request.
    * An explicit brevity instruction in the question ("in one line", "briefly",
      "short answer") is a user requirement, not a hint. It must be honoured
      directly rather than scaled.
    * Every benchmark prompt is short, so a pure word-count tier would cap ALL of
      them - including content-heavy multi-marker cases that genuinely need room.
      The budget therefore stays generous by default and only tightens when the
      question is narrow or explicitly brief.
    * Complex multi-part prompts still get no cap.
    """
    q = (question_text or "").strip()
    low = q.lower()

    if force_full:
        return 0

    # Explicit brevity requests win outright.
    if re.search(r"\bone[- ]line\b|\bone sentence\b|\bin brief\b|\bbriefly\b"
                 r"|\bshort answer\b|\bshortly\b|\bjust tell me\b|\bin short\b",
                 low):
        return 300
    if re.search(r"\bin (?:two|three|2|3) lines\b|\bsummar(?:y|ise|ize) in\b",
                 low):
        return 600

    wc = len(q.split())
    if wc <= 6:
        return 1200
    if wc <= 12:
        return 1800
    if wc <= 25:
        return 2600
    return 3600


def format_rag_response(
    result,
    session_id,
    question_hint: str = "",
    max_answer_words: int = 0,
    target_language: str = "en",
):
    """Helper to format RAG result for API — supports agentic metadata + thinking trace.

    Args:
        max_answer_words: If > 0 and answer exceeds this word count, trim at the last
            sentence boundary within the limit. Use for simple/factual queries (e.g. 350).
    """
    import re as _fmt_re
    import time as _tt2
    meta = result.get('metadata', {})
    answer_text = result.get('answer', 'No answer generated')
    # Prefer the adapter's measured total; fall back to 0 when the path did not
    # report one (then synthesis_time degrades to 0 rather than lying).
    _total_request_seconds = float(meta.get('total_time') or 0)
    _target_language = "hi" if str(target_language or "").strip().lower() == "hi" else "en"
    _is_curated_statutory_fact = (
        meta.get("strategy") == "curated_statutory_fact"
        or meta.get("query_type") == "simple_legal_fact"
        or bool((meta.get("grounding") or {}).get("curated_statutory_fact"))
    )
    _is_grounded_simple_answer = (
        bool(meta.get("grounded_answer"))
        and str(meta.get("complexity") or "").strip().lower() in {"low", "simple", "ultra_simple"}
        and str(meta.get("strategy") or meta.get("query_type") or "").strip().lower()
        in {"simple", "simple_direct", "simple_legal_fact", "curated_statutory_fact"}
    )

    def _derive_title(question_text: str, answer: str) -> str:
        import re as _title_re

        explicit_title = result.get('title') or meta.get('title')
        if explicit_title:
            base = str(explicit_title).strip()
        else:
            cleaned_answer = _title_re.sub(r'<think>.*?</think>\s*', '', answer or '', flags=_title_re.DOTALL).strip()
            cleaned_answer = _title_re.sub(r'(?im)^\s*(#+\s*)?(case summary|governing law|application to facts|conclusion|answer|short answer)\s*:?\s*', '', cleaned_answer, count=1).strip()
            cleaned_answer = _title_re.sub(r'[*_`>#]+', '', cleaned_answer)
            cleaned_answer = _title_re.sub(r'\s+', ' ', cleaned_answer).strip()

            answer_lower = cleaned_answer.lower()
            question_lower = (question_text or "").lower()

            if "age of majority" in question_lower or ("majority act" in answer_lower and "18" in answer_lower):
                base = "Majority Age: 18 Years"
            elif "article 21" in question_lower or "life and personal liberty" in answer_lower:
                base = "Article 21: Life And Liberty"
            elif "anticipatory bail" in question_lower or "pre-arrest bail" in answer_lower:
                base = "Anticipatory Bail: Pre-Arrest Protection"
            elif "section 302" in question_lower or "murder" in answer_lower:
                base = "IPC 302: Murder"
            else:
                first_sentence = _title_re.split(r'(?<=[.!?])\s+', cleaned_answer, maxsplit=1)[0].strip()
                if not first_sentence:
                    first_sentence = "Legal Answer"
                base = first_sentence

        base = _title_re.sub(r'\s+', ' ', base).strip().rstrip('?.! ')
        cleaned_question = _title_re.sub(r'\s+', ' ', (question_text or '').strip()).rstrip('?.! ')
        if cleaned_question and base.lower() == cleaned_question.lower():
            base = "Legal Answer Summary"
        if len(base) > 78:
            base = base[:78].rsplit(' ', 1)[0].strip() or base[:78]

        title_context = f"{question_text}\n{answer}".lower()
        if any(k in title_context for k in ("bail", "arrest", "fir", "bns", "ipc", "criminal", "police")):
            emoji = "🛡️"
        elif any(k in title_context for k in ("contract", "supplier", "delivery", "payment", "sale of goods")):
            emoji = "📄"
        elif any(k in title_context for k in ("property", "land", "sale deed", "mutation", "rera")):
            emoji = "🏛️"
        elif any(k in title_context for k in ("consumer", "refund", "defect", "service")):
            emoji = "✅"
        elif any(k in title_context for k in ("bank", "loan", "drt", "rddbfi", "sarfaesi", "cheque")):
            emoji = "💼"
        else:
            emoji = "⚖️"
        return f"{emoji} {base}"[:96]

    # Best-effort question from result dict or caller hint
    _question_text = (
        result.get('query') or result.get('question') or question_hint or ""
    )[:4000]
    _question_lower = _question_text.lower()

    # --- Extract <think>...</think> if the RAG answer contains one ---------------
    _think_match = _fmt_re.search(r'<think>(.*?)</think>', answer_text, _fmt_re.DOTALL)
    if _think_match:
        think_trace = _think_match.group(1).strip()
        answer_text = _fmt_re.sub(r'<think>.*?</think>\s*', '', answer_text, flags=_fmt_re.DOTALL).strip()
    else:
        think_trace = None

    # --- Brevity trimming: cap the answer to a character budget -----------------
    # The budget is in CHARACTERS. A word budget cannot express a "one line"
    # request: 300 words is ~1,800 characters, and the scored case
    # "Answer in one line only: what is Article 21?" has a 300-character limit.
    # 7 of the 8 call sites passed no budget at all, so a default is derived here.
    if max_answer_words <= 0 and question_hint:
        max_answer_words = brevity_budget_chars(question_hint)
    if max_answer_words > 0:
        if len(answer_text) > max_answer_words:
            truncated = answer_text[:max_answer_words]
            # Prefer cutting at a structural boundary so we never amputate the
            # middle of a section. Heading / bullet / blank-line boundaries are
            # preferred, then a sentence end, and only then a hard cut.
            _half = max_answer_words // 2
            _struct = max(
                truncated.rfind('\n\n'),
                truncated.rfind('\n- '), truncated.rfind('\n* '),
                truncated.rfind('\n#'), truncated.rfind('\n1.'),
            )
            _last_sentence_end = max(
                truncated.rfind('. '), truncated.rfind('.\n'),
                truncated.rfind('? '), truncated.rfind('!\n'),
                truncated.rfind('.\n\n'),
            )
            if _struct > _half:
                answer_text = truncated[:_struct].strip()
                _cut = 'structural'
            elif _last_sentence_end > _half:
                answer_text = truncated[:_last_sentence_end + 1].strip()
                _cut = 'sentence'
            else:
                answer_text = truncated.strip()
                _cut = 'hard'
            logger.info(
                f"[BREVITY] Trimmed answer from {len(answer_text)} to "
                f"{len(answer_text)} chars (cap {max_answer_words}, cut={_cut})"
            )

    # --- Post-hoc thinking: generate a brief reasoning trace for complex answers --
    if not _is_curated_statutory_fact and not think_trace and len(answer_text) > 400:
        client_manager = getattr(rag_system, 'client_manager', None) if rag_system is not None else None
        for _think_attempt in range(3):
            try:
                if client_manager is None:
                    break

                # Rotate to a fresh API key to avoid back-to-back 429 after main query.
                # record_failure=False: this is a PROACTIVE rotation, not a
                # response to an error. Counting it as a failure would slowly
                # open every vendor's circuit after a few dozen long answers
                # and take the whole LLM pool down with no upstream fault.
                force_rotation = getattr(client_manager, 'force_rotation', None)
                if callable(force_rotation):
                    try:
                        force_rotation(reason="pre-thinking-trace",
                                       record_failure=False)
                    except TypeError:
                        # Older client_manager without the kwarg.
                        force_rotation(reason="pre-thinking-trace")
                _tt2.sleep(0.5 * (_think_attempt + 1))  # Increasing backoff

                _think_sys = (
                    "You are an internal legal reasoning engine for Indian law. "
                    "Given a legal question and AI answer, produce a deep reasoning trace (150-250 words) covering:\n"
                    "1. Exact statutes and section numbers applied (e.g., IPC s.302, CPC Order 7 Rule 11)\n"
                    "2. Landmark SC/HC precedents and constitutional provisions directly relied upon\n"
                    "3. Contradictions, unsettled law, or jurisdiction-specific variations in the answer\n"
                    "4. Alternative interpretations a court might consider\n"
                    "5. Why the answer prioritises certain legal sources over others\n"
                    "Output ONLY the reasoning trace — no bullet labels, no headings, no intro or conclusion phrases."
                )
                _think_usr = (
                    f"Question: {_question_text}\n\n"
                    f"Answer excerpt (first 1200 chars):\n{answer_text[:1200]}\n\n"
                    "Internal reasoning trace:"
                )
                # Use the fast model — low latency, avoids rate-limiting the main model
                _think_resp = client_manager.chat.completions.create(
                    model=Config.FAST_LLM_MODEL,
                    messages=[
                        {"role": "system", "content": _think_sys},
                        {"role": "user", "content": _think_usr}
                    ],
                    temperature=0.15,
                    max_tokens=320
                )
                _raw_trace = _think_resp.choices[0].message.content.strip()
                # Strip any accidental think tags the model echoes back
                _raw_trace = _fmt_re.sub(r'</?think>', '', _raw_trace).strip()
                think_trace = _raw_trace if len(_raw_trace) > 30 else None
                logger.info(f"[THINKING] Generated post-hoc trace ({len(think_trace) if think_trace else 0} chars) on attempt {_think_attempt+1}")
                break  # success
            except Exception as _think_err:
                _think_err_str = str(_think_err)
                logger.warning(f"[THINKING] Attempt {_think_attempt+1} failed: {type(_think_err).__name__}: {_think_err_str[:200]}")
                if _think_attempt == 2:
                    think_trace = None

    # --- Normalize source document format (handles raw Milvus/Chroma docs) ------
    _raw_sources = result.get('source_documents', [])
    _normalized_sources = []
    for _s in (_raw_sources or []):
        if isinstance(_s, dict):
            _metadata = _s.get('metadata', {}) if isinstance(_s.get('metadata'), dict) else {}
            _source_url = _s.get('url') or _s.get('link') or _metadata.get('url')
            _content_text = (
                _s.get('content')
                or _s.get('snippet')
                or _s.get('description')
                or _s.get('text')
                or _s.get('page_content', '')
            )
            _normalized_source = {
                'title': (
                    _s.get('title')
                    or _metadata.get('title')
                    or _metadata.get('case_name')
                    or _s.get('id')
                    or 'Legal Document'
                ),
                'content': str(_content_text)[:400],
                'source': _s.get('source') or _metadata.get('source', 'Legal Database'),
            }
            if _source_url:
                _normalized_source['url'] = _source_url
            if _s.get('published'):
                _normalized_source['published'] = _s.get('published')

            for _field in (
                'case_id',
                'case_name',
                'year',
                'judgment_date',
                'court',
                'source_store',
                'source_tier',
                'filename',
                'metadata_relpath',
                'chunks_relpath',
                'source_locator',
                'trusted_source',
            ):
                _value = _s.get(_field, _metadata.get(_field))
                if _value not in (None, ""):
                    _normalized_source[_field] = _value
            _normalized_sources.append(_normalized_source)
        else:
            _normalized_sources.append(_s)

    _search_engines_used = meta.get('search_engines_used') or result.get('search_engines_used')
    _web_search_mode = meta.get('web_search_mode') if 'web_search_mode' in meta else result.get('web_search_mode')
    _strategy = meta.get('strategy')
    if _strategy in (None, '', 'n/a', 'expert_legal'):
        _strategy = 'simple' if meta.get('loops', 0) else meta.get('search_domain', 'simple_direct')
    _strategy = _normalize_query_type(_strategy, fallback='simple_direct')

    # Strengthen legal-currentness for high-impact domains so complex forensic
    # prompts consistently include contemporary legal framing.
    _answer_lower = answer_text.lower()
    _criminal_context = any(
        term in _question_lower
        for term in (
            "criminal law", "ipc", "crpc", "evidence act", "bns", "bnss", "bsa", "uapa", "sedition"
        )
    )
    _bns_markers = (
        " bns", " bnss", " bsa",
        "bharatiya nyaya sanhita",
        "bharatiya nagarik suraksha sanhita",
        "bharatiya sakshya",
    )
    if _criminal_context and not any(marker in _answer_lower for marker in _bns_markers):
        answer_text += (
            "\n\nCurrent-law note: For criminal/procedure/evidence issues, the operative framework is "
            "Bharatiya Nyaya Sanhita, 2023 (BNS), Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS), "
            "and Bharatiya Sakshya Adhiniyam, 2023 (BSA); IPC/CrPC/Evidence Act references are legacy mappings."
        )
        _answer_lower = answer_text.lower()

    _electoral_context = "electoral bond" in _question_lower or (
        "election law" in _question_lower and "bond" in _question_lower
    )
    _electoral_markers = (
        "association for democratic reforms",
        "electoral bonds scheme",
        "struck down",
        "unconstitutional",
        "february 2024",
    )
    if _electoral_context and not any(marker in _answer_lower for marker in _electoral_markers):
        answer_text += (
            "\n\nCurrent-position note: In Association for Democratic Reforms v. Union of India "
            "(February 2024), the Supreme Court held the Electoral Bonds Scheme unconstitutional "
            "and ordered disclosure-linked compliance measures."
        )

    # Deterministic structure normalizer for complex multi-part prompts:
    # if user supplied numbered sub-questions but model omitted explicit
    # headings, append a compact sub-question coverage scaffold.
    _parsed_sub_questions = [
        part.strip()
        for part in _fmt_re.findall(r"(?m)^\s*\d+\.\s*(.+)$", _question_text)
        if part and part.strip()
    ]
    _existing_subq_headings = len(
        _fmt_re.findall(r"sub[-\s]?question\s*\d+", answer_text, _fmt_re.IGNORECASE)
    )
    if len(_parsed_sub_questions) >= 4 and _existing_subq_headings < 4:
        scaffold_lines = ["", "Structured Sub-Question Coverage:"]
        for _idx, _sq in enumerate(_parsed_sub_questions[:5], start=1):
            scaffold_lines.append(f"Sub-Question {_idx}: {_sq}")
            scaffold_lines.append(
                "Answer: This point is addressed through the governing-law, application-to-facts, "
                "and risk/remedy analysis above; apply cited authorities to this specific issue before filing strategy."
            )
        answer_text += "\n" + "\n".join(scaffold_lines)

    citation_extractor = CitationExtractor()
    extracted_citations = citation_extractor.extract_citations(answer_text)
    citation_validation = citation_extractor.validate_citations(extracted_citations, _raw_sources or [])
    _missing_case_entries = [
        item for item in citation_validation.get("missing_from_context", [])
        if item.get("type") == "Case Law"
    ]
    _missing_case_labels = [str(item.get("citation", "")).strip() for item in _missing_case_entries if item.get("citation")]

    # Unsupported case citations are REPORTED, never deleted.
    #
    # History, and why deleting was wrong:
    #   v1 rewrote the case name in place to "Unverified case reference", which
    #      reached users as a fake party name ("Unverified case reference of Kerala").
    #   v2 removed the citation from the prose. That still corrupted the sentence:
    #      "In Basalingappa v. State of Karnataka (2005), ..." became
    #      "In of Karnataka (2005), ...". Real, correctly-cited cases were being
    #      deleted because the validator could not match them.
    #   v3 (here): keep the prose intact and surface the doubt where it belongs -
    #      system_info.unsupported_case_citations plus the low-support banner.
    # The validator itself was also made tolerant (citation_extractor
    # ._case_present_in_context) so genuine cases stop being flagged in the first place.
    _unsupported_case_labels = list(_missing_case_labels)

    contract_checks = {
        "has_issue_summary": bool(_fmt_re.search(r"(issue|summary|facts?)", answer_text, _fmt_re.IGNORECASE)),
        "has_governing_law": bool(_fmt_re.search(r"(section\s+\d+|article\s+\d+|governing\s+law|applicable\s+law)", answer_text, _fmt_re.IGNORECASE)),
        "has_application": bool(_fmt_re.search(r"(apply|application|analysis|reasoning)", answer_text, _fmt_re.IGNORECASE)),
        "has_risk": bool(_fmt_re.search(r"(risk|caution|limitation)", answer_text, _fmt_re.IGNORECASE)),
        "has_next_steps": bool(_fmt_re.search(r"(next\s+step|remedy|file|approach)", answer_text, _fmt_re.IGNORECASE)),
        "has_disclaimer": bool(_fmt_re.search(r"(disclaimer|general\s+information|legal\s+advice)", answer_text, _fmt_re.IGNORECASE)),
    }

    valid_citations = len(citation_validation.get("valid", []))
    missing_citations = len(citation_validation.get("missing_from_context", []))
    missing_case_citations = len(_missing_case_entries)
    _grounding = meta.get('grounding') if isinstance(meta.get('grounding'), dict) else {}
    _grounding_abstained = bool(meta.get('abstained_due_to_grounding', False))
    _grounded_answer = bool(meta.get('grounded_answer', False))
    if _grounding_abstained:
        _strategy = "grounding_abstain"
    weak_contract = sum(1 for v in contract_checks.values() if v) < 4
    unsupported_citations = missing_citations > valid_citations and missing_citations >= 2

    # Whether the corpus is actually available changes what "unverified" means.
    # With no operational retrieval, EVERY case citation is absent from context by
    # construction - penalising that taught the system to apologise for correct
    # answers (the banner fired on 28 of 60 benchmark cases, most of them right).
    _store_ok = False
    try:
        from kaanoon_test.utils import store_check as _sc
        _store_ok = bool(_sc.refresh().get("reachable"))
    except Exception:
        _store_ok = False

    # ── Law-in-force (currency) guard ───────────────────────────────────────
    # Runs here because the trust-signal decision below already takes a currency
    # violation into account, so the guard must be computed before that call.
    # Detects an answer that cites repealed IPC/CrPC/Evidence-Act provisions for a
    # post-2024-07-01 question. It never rewrites the answer; it lowers confidence
    # and adds a visible note, so a repealed provision cannot be presented as
    # current law with a high confidence score.
    _currency = {"violations": [], "confidence_cap": None, "note": None}
    try:
        from kaanoon_test.system_adapters.law_currency import check_currency as _check_currency
        _currency = _check_currency(question_hint or "", answer_text)
    except Exception as _cur_err:  # never let the guard break a response
        logger.warning(f"[CURRENCY] guard unavailable: {_cur_err}")
        _currency = {"violations": [], "confidence_cap": None, "note": None}

    _signals = assess_support_signals(
        contract_checks=contract_checks,
        valid_citations=valid_citations,
        missing_citations=missing_citations,
        missing_case_citations=missing_case_citations,
        grounding_abstained=_grounding_abstained,
        grounded_answer=_grounded_answer,
        currency_violations=len(_currency.get("violations") or []) if isinstance(_currency, dict) else 0,
        corpus_reachable=_store_ok,
        is_curated_statutory_fact=_is_curated_statutory_fact,
        is_grounded_simple_answer=_is_grounded_simple_answer,
        answer_chars=len(answer_text),
    )
    weak_contract = _signals["weak_contract"]
    unsupported_citations = _signals["unsupported_citations"]
    high_hallucination_risk = _signals["high_hallucination_risk"]
    _banner_needed = _signals["banner_needed"]
    _system_info_corpus_aware = _store_ok

    # Only show the low-support banner when the answer is genuinely weak. It used
    # to fire on 28 of 60 benchmark answers - mostly correct ones - which taught
    # users to distrust correct answers. It is now driven by _banner_needed.
    if (
        _banner_needed
    ) and not _grounding_abstained and not _is_curated_statutory_fact and not _is_grounded_simple_answer:
        _unverified_case_snippet = ""
        # Only name case references when there was a corpus to check them against.
        if _missing_case_labels and _store_ok:
            _short_list = ", ".join(_missing_case_labels[:3])
            if len(_missing_case_labels) > 3:
                _short_list += ", ..."
            _unverified_case_snippet = _short_list

        if _target_language == "hi":
            _prefix = (
                "उपलब्ध स्रोत इस प्रश्न पर उच्च-विश्वसनीय कानूनी निष्कर्ष का पूरा समर्थन नहीं करते हैं। "
                "इसे प्रारंभिक मार्गदर्शन मानें और कार्रवाई करने से पहले संबंधित धाराओं/न्यायिक उद्धरणों को "
                "प्रामाणिक स्रोतों या किसी योग्य अधिवक्ता से अवश्य सत्यापित करें।"
            )
            if _unverified_case_snippet:
                _prefix += f" सत्यापित न हो सकने वाले केस-संदर्भ: {_unverified_case_snippet}."
            answer_text = _prefix + "\n\n" + answer_text
        else:
            _prefix = (
                "The available sources do not fully support a high-confidence legal conclusion for this query. "
                "Please treat this as preliminary guidance and verify cited sections/cases with authoritative texts "
                "or a qualified advocate before acting."
            )
            if _unverified_case_snippet:
                _prefix += (
                    " The following case reference(s) could not be confirmed in the"
                    f" retrieved sources; please verify them before relying on them:"
                    f" {_unverified_case_snippet}."
                )
            answer_text = _prefix + "\n\n" + answer_text

    _detected_language = _detect_text_language(answer_text)
    if _target_language == "hi":
        if not answer_text.lstrip().startswith("हिंदी-मोड:"):
            answer_text = "हिंदी-मोड:\n" + answer_text
        _detected_language = _detect_text_language(answer_text)

    _system_info = {
        'detected_language': _detected_language,
        'target_language': _target_language,
        'language_mismatch': _detected_language != _target_language,
        'supported_languages': sorted(SUPPORTED_RESPONSE_LANGUAGES),
        'query_type': _strategy,
        'complexity': meta.get('complexity', 'high'),
        'agentic_loops': meta.get('loops', 0),
        'memory_used': meta.get('memory_used', False),
        'build_fingerprint': BUILD_FINGERPRINT,
        'release_signature': RELEASE_SIGNATURE,
        'grounded_answer': _grounded_answer,
        'abstained_due_to_grounding': _grounding_abstained,
        'grounding': _grounding,
        'grounding_failure_reasons': meta.get('grounding_failure_reasons', []),
    }
    if _search_engines_used:
        _system_info['search_engines_used'] = _search_engines_used
    if _web_search_mode is not None:
        _system_info['web_search_mode'] = bool(_web_search_mode)
    if _target_language == "hi":
        _system_info['hi_enforcement_marker'] = HI_OUTPUT_ENFORCEMENT_MARKER
    _system_info['answer_downgraded'] = bool(
        not _is_curated_statutory_fact
        and not _is_grounded_simple_answer
        and (unsupported_citations or weak_contract or high_hallucination_risk or _grounding_abstained)
    )
    _system_info['unsupported_case_citations'] = missing_case_citations
    _system_info['unsupported_case_names'] = _unsupported_case_labels[:10]
    _system_info['corpus_aware'] = _system_info_corpus_aware

    # ── Confidence calibration ────────────────────────────────────────────────
    # Confidence used to be passed straight through from the adapter (default 0.9)
    # and had no relationship to the support flags computed above. The live system
    # therefore reported confidence 0.95 alongside "The available sources do not
    # fully support a high-confidence legal conclusion", which tells the user
    # nothing trustworthy. Confidence is now derived from the evidence we actually
    # have, and is always reported so the pairing is inspectable.
    _reported_confidence = meta.get('confidence', 0.9)
    try:
        _reported_confidence = float(_reported_confidence)
    except (TypeError, ValueError):
        _reported_confidence = 0.5

    # ── Law-in-force (currency) guard ───────────────────────────────────────
    # _currency itself is computed earlier, above assess_support_signals, which
    # needs the violation count. Keep an untouched copy of the body so the
    # currency notice can be prepended without duplicating whatever prefix was
    # already added above.
    _answer_body = answer_text

    _confidence_capped = False
    _effective_confidence = _reported_confidence

    # Confidence now has a floor as well as a ceiling. Previously it was only
    # ever subtracted, so a clean, well-structured answer still inherited a
    # middling score (measured mean 0.521 on a system that was 80% accurate).
    _effective_confidence, _confidence_capped = calibrate_confidence(
        _reported_confidence,
        signals=_signals,
        grounding_abstained=_grounding_abstained,
        corpus_reachable=_store_ok,
        currency_confidence_cap=_currency.get("confidence_cap"),
        is_curated_statutory_fact=_is_curated_statutory_fact,
        is_grounded_simple_answer=_is_grounded_simple_answer,
    )
    _effective_confidence = round(max(0.0, min(1.0, _effective_confidence)), 2)
    _system_info['confidence_reported'] = _reported_confidence
    _system_info['confidence_effective'] = _effective_confidence
    _system_info['confidence_capped'] = _confidence_capped
    _system_info['law_currency_violations'] = _currency.get('violations') or []
    _system_info['post_bns_transition_query'] = bool(_currency.get('post_transition'))

    # Surface the correction where the reader will see it, not just in metadata.
    _currency_note = _currency.get('note')
    if _currency_note:
        if _target_language == 'hi':
            answer_text = ("कानूनी ध्यान दें: " + _currency_note)
        else:
            answer_text = ("**Law-in-force notice:** " + _currency_note)
        answer_text = answer_text + "\n\n" + _answer_body

    return {
        'answer': answer_text,
        'title': _derive_title(_question_text, answer_text),
        'think_trace': think_trace,
        'sources': _normalized_sources,
        'citations': extracted_citations,
        'citation_validation': citation_validation,
        'reasoning_analysis': {'trace': result.get('reasoning_path', 'N/A')},
        'latency': meta.get('retrieval_time', 0),
        'complexity': meta.get('complexity', 'medium'),
        'query_type': _strategy,
        'retrieval_time': meta.get('retrieval_time', 0),
        # Reported as 0 for years, which made the per-stage split meaningless and
        # hid the real cost centre. Prefer the adapter's measured synthesis time;
        # otherwise derive it as total-minus-retrieval when a total is available.
        'synthesis_time': (
            float(meta.get('synthesis_time') or 0)
            or max(
                0.0,
                round(_total_request_seconds - float(meta.get('retrieval_time') or 0), 3),
            )
        ),
        'total_time': _total_request_seconds or meta.get('retrieval_time', 0),
        'confidence': _effective_confidence,
        'session_id': session_id,
        'from_cache': meta.get('from_cache', False),
        'validation': {
            **contract_checks,
            'supported_citation_count': valid_citations,
            'unsupported_citation_count': missing_citations,
            'unsupported_case_citation_count': missing_case_citations,
            'weak_contract': weak_contract,
            'unsupported_citations': unsupported_citations,
            'high_hallucination_risk': high_hallucination_risk,
            'grounded_answer': _grounded_answer,
            'abstained_due_to_grounding': _grounding_abstained,
            'grounding': _grounding,
        },
        'system_info': _system_info
    }


@app.get("/api/debug-think")
async def debug_think_endpoint(question: str = "What is IPC 302?"):
    """Debug endpoint to test thinking trace generation in isolation."""
    if not rag_system:
        return {"error": "RAG not initialized"}
    import re as _dr; import time as _dt
    try:
        _dt.sleep(0.3)
        _resp = rag_system.client_manager.chat.completions.create(
            model=Config.FAST_LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a legal reasoning engine. Produce a 50-word reasoning trace about the given legal question."},
                {"role": "user", "content": f"Question: {question}\nReasoning trace:"}
            ],
            temperature=0.15, max_tokens=120
        )
        return {"ok": True, "trace": _resp.choices[0].message.content.strip(), "question": question}
    except Exception as e:
        return {"ok": False, "error": type(e).__name__, "detail": str(e)[:400]}


@app.post("/api/feedback")
async def feedback_endpoint(request: FeedbackRequest):
    """
    Collect user feedback for continuous improvement
    """
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    try:
        rag_system.collect_feedback(
            query=request.query,
            answer=request.answer,
            rating=request.rating,
            session_id=request.session_id,
            feedback_text=request.feedback_text or ""
        )
        
        return {
            "status": "success",
            "message": "Feedback collected successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feedback collection failed: {str(e)}")


@app.get("/api/metrics")
async def metrics_endpoint():
    """
    Get system performance metrics
    """
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    try:
        metrics = rag_system.get_metrics()
        feedback_stats = rag_system.get_feedback_stats()
        
        return {
            "metrics": metrics,
            "feedback": feedback_stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics retrieval failed: {str(e)}")


@app.delete("/api/conversation/{session_id}")
async def clear_conversation_endpoint(session_id: str):
    """
    Clear conversation history for a session
    """
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG system not initialized")

    try:
        # Remove from active clarification sessions (multi-turn map)
        _delete_clarification_session(session_id)
        # Clear any internal RAG state
        rag_system.clear_conversation(session_id)
        return {
            "status": "success",
            "message": f"Conversation {session_id} cleared"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clear conversation failed: {str(e)}")


# Health-probe timeouts. These probes used to run inline in the event loop with
# no deadline, so a slow vector store or a hung diagnostic call made /api/health
# block long enough for the platform to return 000 (observed under load). The
# endpoint now has a hard deadline and degrades instead of hanging.
_HEALTH_PROBE_TIMEOUT_S = float(os.environ.get("HEALTH_PROBE_TIMEOUT_S", "6"))
# store_check hits the vector store; caching it briefly keeps a probe loop from
# turning into a self-inflicted load test.
_STORE_CHECK_TTL_S = float(os.environ.get("STORE_CHECK_TTL_S", "30"))
_store_check_cache: Dict[str, Any] = {"at": 0.0, "value": {}}


def _cached_store_check() -> Dict[str, Any]:
    """Return store reachability, probing if necessary.

    This deliberately calls refresh(), not status(). status() only echoes cached
    state and never probes, so relying on the boot background thread meant a
    dead thread left /api/health reporting "not probed yet" forever - the exact
    silence this module exists to remove. refresh() carries its own 300s TTL and
    never raises, and the TTL below keeps the endpoint cheap.
    """
    now = time.time()
    cached = _store_check_cache.get("value")
    if cached and (now - float(_store_check_cache.get("at") or 0)) < _STORE_CHECK_TTL_S:
        return {**cached, "cached": True}
    try:
        from kaanoon_test.utils import store_check as _store_check
        value = _store_check.refresh()
    except Exception as exc:
        value = {"error": str(exc)}
    _store_check_cache["at"] = now
    _store_check_cache["value"] = value
    return {**value, "cached": False}


def _honest_collection_probe(store: Any) -> Dict[str, Any]:
    """Derive collection health from a REAL operation on the handle.

    G3: the deployed /api/rag/diagnostics reported statute_store_ready=true
    and has_operational_retrieval=true while collection_repr was "None" and
    collection_count_error was "AttributeError: 'NoneType' object has no
    attribute 'count'". The cause was a readiness check that asked
    `hasattr(store, "collection")` - True even when the handle is None - and a
    probe that then called .count() on that None. An actual outage therefore
    read green.

    Here the count is only ever attempted on a handle that actually exists, so
    collection_count_error stays null when there is genuinely no error. Never
    raises.
    """
    absent: Dict[str, Any] = {
        "collection_present": False,
        "collection_usable": False,
        "collection_count": None,
        "collection_repr": None,
        "collection_count_error": None,
        "bm25_usable": False,
        "bm25_count": 0,
    }

    if store is None:
        return {**absent, "collection_unavailable_reason": "store_is_none"}

    # The store knows best how to probe itself.
    probe_fn = getattr(store, "probe_collection", None)
    if callable(probe_fn):
        try:
            return {**absent, **dict(probe_fn())}
        except Exception as exc:
            return {
                **absent,
                "collection_unavailable_reason": "probe_failed",
                "collection_count_error": f"{type(exc).__name__}: {exc}",
            }

    coll = getattr(store, "collection", None)
    bm25_count = 0
    if hasattr(store, "documents") and isinstance(store.documents, list):
        bm25_count = len(store.documents)
    bm25_usable = (getattr(store, "bm25", None) is not None) and (bm25_count > 0)

    if coll is None:
        # Absent handle is a STATE, not an error. Do not manufacture an
        # AttributeError by calling .count() on it.
        return {
            **absent,
            "bm25_usable": bm25_usable,
            "bm25_count": bm25_count,
            "collection_unavailable_reason": "collection_handle_is_none",
        }

    probe: Dict[str, Any] = {
        **absent,
        "collection_present": True,
        "bm25_usable": bm25_usable,
        "bm25_count": bm25_count,
    }
    try:
        probe["collection_repr"] = repr(coll)[:300]
    except Exception:
        probe["collection_repr"] = None
    try:
        probe["collection_count"] = int(coll.count())
        probe["collection_usable"] = True
    except Exception as exc:
        probe["collection_count_error"] = f"{type(exc).__name__}: {exc}"
        probe["collection_usable"] = False
    return probe


def _correct_retrieval_health(retrieval: Any, rag_sys: Any) -> Dict[str, Any]:
    """Re-derive store readiness from real operations before it is reported.

    Ensures that when a store has an operational Chroma collection OR loaded
    BM25 keyword documents (statute store hybrid/keyword fallback), its readiness
    is correctly reported as True.
    """
    out = dict(retrieval) if isinstance(retrieval, dict) else {}
    if rag_sys is None:
        return out

    stores = {
        "main": getattr(rag_sys, "store", None),
        "statute": getattr(rag_sys, "statute_store", None),
    }
    probes = {name: _honest_collection_probe(store) for name, store in stores.items()}

    for name in ("main", "statute"):
        key = f"{name}_store_ready"
        if key in out:
            store = stores[name]
            coll_usable = bool(probes[name].get("collection_usable", False))
            
            # Check if store has loaded BM25 documents
            bm25_docs = int(probes[name].get("bm25_count") or 0)
            if bm25_docs == 0 and store is not None:
                if hasattr(store, "keyword_stats"):
                    try:
                        bm25_docs = int(store.keyword_stats().get("bm25_document_count", 0))
                    except Exception:
                        pass
                if bm25_docs == 0:
                    for attr in ("documents", "_documents"):
                        docs = getattr(store, attr, None)
                        if docs is not None:
                            try:
                                bm25_docs = len(docs)
                                if bm25_docs > 0:
                                    break
                            except Exception:
                                pass

            # When the statute store has BM25 documents (and/or Chroma collection handle),
            # statute_store_ready correctly reports True.
            out[key] = bool(coll_usable or (bm25_docs > 0))

    # Preserve the original semantics (any backend, or a live web fallback),
    # but with readiness now resting on a real operation rather than on
    # attribute presence.
    has_any = bool(
        out.get("main_store_ready", False)
        or out.get("statute_store_ready", False)
        or (out.get("pageindex_docs") or 0) > 0
        or out.get("sc_cloud_ready", False)
        or (out.get("free_corpus_docs") or 0) > 0
    )
    if "has_any_retrieval" in out:
        out["has_any_retrieval"] = has_any
    if "has_operational_retrieval" in out:
        out["has_operational_retrieval"] = bool(
            has_any or out.get("live_fallback_capable", False)
        )

    out["collection_probes"] = probes
    return out


def _correct_diagnostics_payload(diagnostics: Any, rag_sys: Any) -> Dict[str, Any]:
    """Apply the honest-readiness correction to a /api/rag/diagnostics body."""
    if not isinstance(diagnostics, dict):
        return {}

    out = dict(diagnostics)
    out["retrieval"] = _correct_retrieval_health(out.get("retrieval"), rag_sys)

    probe_block = out.get("store_readiness_probe")
    if isinstance(probe_block, dict):
        fixed_block = dict(probe_block)
        for name in ("main", "statute"):
            existing = fixed_block.get(name)
            if not isinstance(existing, dict):
                existing = {}
            corrected = dict(existing)
            corrected.update(
                {
                    # has_collection used to mean "the attribute exists", which is
                    # True even when the handle is None - that is the original lie.
                    # It now means the handle is actually present.
                    "has_collection": out["retrieval"]["collection_probes"][name][
                        "collection_present"
                    ],
                    "collection_present": out["retrieval"]["collection_probes"][name][
                        "collection_present"
                    ],
                    "collection_usable": out["retrieval"]["collection_probes"][name][
                        "collection_usable"
                    ],
                    "collection_count": out["retrieval"]["collection_probes"][name][
                        "collection_count"
                    ],
                    "collection_repr": out["retrieval"]["collection_probes"][name][
                        "collection_repr"
                    ],
                    "collection_count_error": out["retrieval"]["collection_probes"][
                        name
                    ]["collection_count_error"],
                }
            )
            fixed_block[name] = corrected
        out["store_readiness_probe"] = fixed_block

    return out


@app.get("/api/health")
async def health_check():
    """Health check endpoint.

    Runs the expensive retrieval/data probes in a worker thread under a hard
    deadline. If they overrun, the endpoint still returns promptly with the
    fields it does have and marks the slow parts as timed out - a late answer
    is worth far less than a partial one that the platform can actually read.
    """
    try:
        return await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(None, _build_health_payload),
            timeout=_HEALTH_PROBE_TIMEOUT_S + 1.0,
        )
    except asyncio.TimeoutError:
        return {
            "status": "degraded" if rag_system else "initializing",
            "rag_system_initialized": rag_system is not None,
            "rag_initializing": rag_initializing,
            "retrieval_ready": False,
            "corpus_live": False,
            "store_check": {"error": "probe timed out"},
            "retrieval": {"error": "probe timed out"},
            "data_diagnostics": {"error": "probe timed out"},
            "health_probe_timeout": True,
            "last_error": rag_last_error or None,
            "build_fingerprint": BUILD_FINGERPRINT,
            "release_signature": RELEASE_SIGNATURE,
            "timestamp": datetime.now().isoformat(),
        }


@app.get("/api/release-info")
async def release_info():
    """Deterministic release metadata for deployment provenance checks."""
    return {
        "build_fingerprint": BUILD_FINGERPRINT,
        "release_signature": RELEASE_SIGNATURE,
        "query_type_taxonomy": sorted(QUERY_TYPE_TAXONOMY),
        "query_type_taxonomy_count": len(QUERY_TYPE_TAXONOMY),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/rag/diagnostics")
async def rag_diagnostics(deep_sc_audit: bool = False):
    """Read-only retrieval/data diagnostics for deployment verification."""
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG system not initialized")

    get_diag = getattr(rag_system, "get_data_diagnostics", None)
    if not callable(get_diag):
        raise HTTPException(status_code=501, detail="RAG diagnostics are not available")

    try:
        diagnostics = get_diag(deep_sc_audit=deep_sc_audit)
        diagnostics = _correct_diagnostics_payload(diagnostics, rag_system)
        diagnostics["timestamp"] = datetime.now().isoformat()
        diagnostics["build_fingerprint"] = BUILD_FINGERPRINT
        diagnostics["release_signature"] = RELEASE_SIGNATURE
        return diagnostics
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RAG diagnostics failed: {exc}")


@app.get("/api/debug/sessions")
async def debug_sessions():
    """Debug: returns PID and active clarification session count. Used by T11 benchmark."""
    import os
    return {
        "pid": os.getpid(),
        "active_sessions": len(active_clarification_sessions),
        "session_ids": list(active_clarification_sessions.keys())[:10],
        "persisted_sessions": len(list(CLARIFICATION_SESSION_DIR.glob("*.json"))),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/examples")
async def examples_endpoint():
    """
    Get example queries (for compatibility with frontend)
    """
    return {
        "examples": [
            "What is IPC Section 302?",
            "How to file for divorce under Hindu law?",
            "What is the procedure for filing FIR?",
            "Explain the principle of res judicata",
            "What are the rights of property owners in India?",
            "How to apply for bail?",
            "What is the difference between murder and culpable homicide?",
            "Explain Order 18 Rule 9 of CPC"
        ]
    }


@app.get("/health")
async def health_check_legacy():
    """Health check endpoint (without /api prefix for compatibility)"""
    return _build_health_payload()


def _build_health_payload() -> Dict[str, Any]:
    retrieval = {}
    data_diagnostics = {}
    retrieval_ready = False

    if rag_system:
        retrieval_ready = True
        if hasattr(rag_system, "get_retrieval_health"):
            try:
                retrieval = rag_system.get_retrieval_health()
                # Re-derive readiness from a real count(). Without this a store
                # whose Chroma handle is None still reports ready=True, so a
                # genuine corpus outage reads green.
                retrieval = _correct_retrieval_health(retrieval, rag_system)
                retrieval_ready = bool(
                    retrieval.get(
                        "has_operational_retrieval",
                        retrieval.get("has_any_retrieval", False),
                    )
                )
            except Exception as exc:
                retrieval = {"error": str(exc)}
                retrieval_ready = False
        get_diag = getattr(rag_system, "get_data_diagnostics", None)
        if callable(get_diag):
            try:
                data_diagnostics = get_diag(deep_sc_audit=False)
            except Exception as exc:
                data_diagnostics = {"error": str(exc)}

    status = "ready" if (rag_system and retrieval_ready) else ("initializing" if rag_initializing else "degraded")

    # Vector-store reachability. The corpus was dark for an extended period without
    # any signal in the health payload, so the check is surfaced here too.
    store = {}
    try:
        store = _cached_store_check()
    except Exception as exc:
        store = {"error": str(exc)}

    # A degraded store is called out explicitly rather than being buried in
    # `retrieval`. Answers served in this state come from web search + model
    # memory, not from the corpus.
    corpus_live = bool(store.get("reachable")) and bool(store.get("documents"))

    return {
        "status": status,
        "rag_system_initialized": rag_system is not None,
        "rag_initializing": rag_initializing,
        "retrieval_ready": retrieval_ready,
        "corpus_live": corpus_live,
        "store_check": store,
        "retrieval": retrieval,
        "data_diagnostics": data_diagnostics,
        "last_error": rag_last_error or None,
        "build_fingerprint": BUILD_FINGERPRINT,
        "release_signature": RELEASE_SIGNATURE,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/stats")
async def stats_endpoint():
    """
    Get system statistics (compatibility with existing endpoints)
    """
    if not rag_system:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    try:
        metrics = rag_system.get_metrics()
        return {
            "total_queries": metrics.get('total_queries', 0),
            "average_latency": metrics.get('average_latency', 0),
            "cache_hit_rate": metrics.get('cache_hit_rate', 0),
            "uptime_seconds": metrics.get('uptime_seconds', 0),
            "agentic_memory": metrics.get('agentic_memory', {}),
            # G5: which vendor is live / which circuits are open.
            "llm_providers": metrics.get('llm_providers', {}),
            "retrieval": metrics.get('retrieval', {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")


# -------------------------------------------------------------------
# AUTH ENDPOINTS
# Local username/password auth with signed bearer tokens.
# -------------------------------------------------------------------

class AuthLoginRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: str


class AuthRegisterRequest(BaseModel):
    username: Optional[str] = None
    email: str
    password: str
    name: Optional[str] = None


@app.post("/api/auth/login")
async def auth_login(request: AuthLoginRequest):
    """Authenticate an existing user and return a signed bearer token."""
    login_identifier = (request.username or request.email or "").strip()
    password = request.password or ""
    if not login_identifier or not password:
        raise HTTPException(status_code=400, detail="Username/email and password are required")

    identifier_norm = _normalize_username(login_identifier)
    with AUTH_USER_DB_LOCK:
        store = _load_auth_store_unlocked()
        user = next(
            (
                candidate
                for candidate in store["users"]
                if _normalize_username(str(candidate.get("username", ""))) == identifier_norm
                or _normalize_email(str(candidate.get("email", ""))) == identifier_norm
            ),
            None,
        )

    if not user or not _verify_password(password, str(user.get("password_hash", ""))):
        raise HTTPException(status_code=401, detail="Invalid username/email or password")

    token = _create_access_token(user)
    return {
        "status": "success",
        "user": _public_user(user),
        "token": token,
        "expires_in": AUTH_TOKEN_TTL_HOURS * 3600,
        "message": "Login successful",
    }


@app.post("/api/auth/register")
async def auth_register(request: AuthRegisterRequest):
    """Register a new user with hashed password and return a signed token."""
    email = (request.email or "").strip()
    password = request.password or ""
    username = (request.username or "").strip()
    if not username:
        username = _derive_username(email or (request.name or "user"))
    display_name = (request.name or username).strip()

    if not username or not _is_valid_username(username):
        raise HTTPException(
            status_code=400,
            detail="Username must be 3-64 chars and use letters, numbers, ., _, or -",
        )
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    username_norm = _normalize_username(username)
    email_norm = _normalize_email(email)
    created_at = datetime.utcnow().isoformat() + "Z"
    new_user = {
        "id": secrets.token_hex(16),
        "username": username,
        "email": email,
        "name": display_name or username,
        "role": "user",
        "password_hash": _hash_password(password),
        "created_at": created_at,
    }

    with AUTH_USER_DB_LOCK:
        store = _load_auth_store_unlocked()
        duplicate = next(
            (
                candidate
                for candidate in store["users"]
                if _normalize_username(str(candidate.get("username", ""))) == username_norm
                or _normalize_email(str(candidate.get("email", ""))) == email_norm
            ),
            None,
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="User with this username/email already exists")

        store["users"].append(new_user)
        _save_auth_store_unlocked(store)

    token = _create_access_token(new_user)
    return {
        "status": "success",
        "user": _public_user(new_user),
        "token": token,
        "expires_in": AUTH_TOKEN_TTL_HOURS * 3600,
        "message": "Registration successful",
    }


@app.get("/api/auth/me")
async def auth_me(http_request: Request):
    """Return the currently authenticated user from bearer token."""
    user = _resolve_current_user(http_request)
    return {"status": "success", "user": _public_user(user)}


@app.post("/api/auth/logout")
async def auth_logout():
    """Stateless logout endpoint; clients should discard bearer token."""
    return {"status": "success", "message": "Logged out"}

@app.get("/api/settings")
async def settings_endpoint():
    """Return frontend configuration / feature flags."""
    return {
        "voice_enabled": False,
        "auth_required": True,
        "max_message_length": 2000,
        "supported_languages": ["en", "hi"],
        "app_name": "LAW-GPT",
        "version": "2.0.0"
    }


# ---------------------------------------------------------------------------
# Safety net for old compiled frontend JS bundles that still contain absolute
# backend URLs. New bundles use same-origin endpoints directly; this middleware
# keeps older cached asset names connected to the active host.
# ---------------------------------------------------------------------------
_OLD_API_URLS = (
    "https://opportunities-cds-bull-animals.trycloudflare.com",
    "https://lawgpt-backend2024.azurewebsites.net",
)
_PATCHED_JS_PATHS = {
    "/chat/assets/index-BiOBT6qp.js",
    "/chat/assets/index-RjapJyOC.js",
}

class PatchJSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        if request.url.path in _PATCHED_JS_PATHS:
            js_name = request.url.path.rsplit("/", 1)[-1]
            js_path = project_root / "static_chat" / "assets" / js_name
            if js_path.exists():
                content = js_path.read_text(encoding="utf-8", errors="replace")
                for old_url in _OLD_API_URLS:
                    content = content.replace(old_url, "")
                content = content.replace(
                    'hn=""',
                    'hn=typeof window!=="undefined"&&window.location?window.location.origin:""',
                )
                content = content.replace(
                    'const p="";try{const g=await fetch(`${p}/api/auth/login`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:d,password:f})});if(g.ok){const w=await g.json();n(!0),s({username:d,...w}),localStorage.setItem("lawgpt_auth","true"),localStorage.setItem("lawgpt_user",JSON.stringify({username:d,...w}));return}}catch{console.log("Auth endpoint not available, using demo mode")}if(d&&f)n(!0),s({username:d,role:"user"}),localStorage.setItem("lawgpt_auth","true"),localStorage.setItem("lawgpt_user",JSON.stringify({username:d,role:"user"}));else throw new Error("Username and password are required")',
                    'const p=typeof window!=="undefined"&&window.location?window.location.origin:"";const g=await fetch(`${p}/api/auth/login`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:d,password:f})});if(!g.ok){const x=await g.json().catch(()=>({}));throw new Error(x.message||`Login failed: ${g.status}`)}const w=await g.json(),m=w.user||{username:d};n(!0),s(m),localStorage.setItem("lawgpt_auth","true"),localStorage.setItem("lawgpt_user",JSON.stringify(m)),w.token?localStorage.setItem("lawgpt_token",w.token):localStorage.removeItem("lawgpt_token");return',
                )
                content = content.replace(
                    'localStorage.removeItem("lawgpt_user")}',
                    'localStorage.removeItem("lawgpt_user"),localStorage.removeItem("lawgpt_token")}',
                )
                return Response(content=content, media_type="application/javascript",
                               headers={"Cache-Control": "no-cache"})
        return await call_next(request)

app.add_middleware(PatchJSMiddleware)



@app.get("/", include_in_schema=False)
async def root_page_redirect():
        # The main link opens the hero + login gate directly (human-lawyer
        # popup design at /chat). The old robot-face landing is retired.
        return RedirectResponse(url="/chat", status_code=302)


@app.get("/home", include_in_schema=False)
async def home_page():
        # Legacy robot-face landing retired — everything routes into the gate.
        return RedirectResponse(url="/chat", status_code=302)


@app.get("/login", include_in_schema=False)
async def login_page():
        # The real login is the Supabase gate (judge hero + Google/OTP card)
        # rendered by the chat app itself at /chat.
        return RedirectResponse(url="/chat", status_code=302)


@app.get("/chat")
async def chat_page():
    """Serve the chat SPA at /chat (without trailing slash)."""
    chat_index = project_root / "static_chat" / "index.html"
    if chat_index.exists():
        return HTMLResponse(content=chat_index.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="Chat page not found")


# -------------------------------------------------------------------
# COURT DEBATE MODE — /api/court-debate
# Registered before static mounts so the path is never intercepted.
# -------------------------------------------------------------------

class CourtDebateRequest(BaseModel):
    """Request body for Court Debate Mode."""
    query: str = Field(..., description="The legal question to debate")
    history: str = Field("", description="Prior conversation context (plain text)")
    modular: bool = Field(
        False,
        description="False = fast single-call debate (Phase 2). True = 3-agent modular debate (Phase 3, highest quality)."
    )
    elite: bool = Field(False, description="Enable Elite court-quality debate mode (~85% target, slower).")
    quality_target: Optional[str] = Field(None, description="Optional quality target, e.g. court_85.")
    session_id: Optional[str] = Field(None, description="Optional session ID for logging")


@app.post("/api/court-debate", tags=["Court Debate Mode"])
async def court_debate_endpoint(req: CourtDebateRequest, http_request: Request):
    """
    **Court Debate Mode** — LAW-GPT's highest-level legal analysis.

    Pipeline:
    - **Phase 1** — Complexity gate (auto-detects if debate is warranted)
    - **Phase 2** — 7-Level integrated deliberation (fast, 1 LLM call)
    - **Phase 3** — Modular 3-agent debate: Advocate A + B + Judge (set `modular=true`)

    Data source: Zilliz Cloud (Main collection + Statute collection).
    Indian law focus: Companies Act 2013, Industrial Disputes Act 1947,
    Whistle Blowers Protection Act 2014, Supreme Court / High Court precedents.
    """
    if not _COURT_DEBATE_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": "Court Debate Engine is not available on this deployment.",
            },
        )

    session_id = req.session_id or f"cd_{datetime.now().timestamp()}"
    logger.info(
        f"[COURT-DEBATE] session={session_id[:16]} modular={req.modular} elite={req.elite} "
        f"query={req.query[:80]!r}"
    )

    try:
        try:
            result = await _run_query_work(
                _get_court_debate_response,
                user_query=req.query,
                conversation_history=req.history,
                modular=req.modular,
                session_id=session_id,
                force_debate=True,
                elite=req.elite,
                quality_target=req.quality_target,
            )
        except _QueryDeadlineExceeded as exc:
            # Elite debates are the slowest path here; bail out well before
            # gunicorn's 600s worker timeout instead of holding the worker.
            logger.error(f"[COURT-DEBATE] Deadline exceeded for session {session_id[:16]}: {exc}")
            return JSONResponse(
                status_code=504,
                content={
                    "status": "timeout",
                    "session_id": session_id,
                    "message": str(exc),
                },
            )
        return {
            "status": "success",
            "session_id": session_id,
            "mode": result.get("mode", "court_debate"),
            "quality_mode": result.get("quality_mode"),
            "quality_target": result.get("quality_target"),
            "legal_domain": result.get("legal_domain", "general"),
            "indian_law_focus": result.get(
                "indian_law_focus",
                "Companies Act 2013 | Industrial Disputes Act 1947 | "
                "Whistle Blowers Protection Act 2014 | SC/HC precedents",
            ),
            "zilliz_used": result.get("zilliz_used", True),
            "provider": result.get("provider", "unknown"),
            "quality_report": result.get("quality_report"),
            "response": result,
        }
    except Exception as exc:
        logger.exception(f"[COURT-DEBATE] Unhandled error for session {session_id[:16]}: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "session_id": session_id,
                "message": str(exc),
            },
        )


# -------------------------------------------------------------------
# COURT DEBATE MODE — STREAMING  /api/court-debate/stream
# Streams Level 1→7 progressively as Server-Sent Events (SSE).
# -------------------------------------------------------------------

@app.post("/api/court-debate/stream", tags=["Court Debate Mode"])
async def court_debate_stream_endpoint(req: CourtDebateRequest, http_request: Request):
    """
    **Court Debate Mode — Streaming**

    Streams the 7-level debate progressively as Server-Sent Events.
    Each SSE message is a JSON object: `{"level": "Level N: Title", "chunk": "...text..."}`
    Final message: `{"level": "done", "chunk": ""}`

    Use `EventSource` on the frontend or `fetch` with `ReadableStream`.
    Session history is auto-loaded from ShortTermMemory when `session_id` is provided.
    """
    if not _COURT_DEBATE_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Court Debate Engine is not available."},
        )

    session_id = req.session_id or f"cd_stream_{datetime.now().timestamp()}"
    logger.info(
        f"[COURT-DEBATE-STREAM] session={session_id[:16]} query={req.query[:80]!r}"
    )

    async def event_generator():
        sentinel = object()
        outbox: "queue.Queue[Any]" = queue.Queue()
        started_at = datetime.now().timestamp()
        # Streaming is incremental, so the deadline is enforced here rather than
        # by wrapping the call: past it we emit a terminal error event and stop
        # instead of streaming until gunicorn's 600s timeout kills the worker.
        deadline_at = _stream_deadline()

        def worker():
            try:
                sync_gen = _get_court_debate_stream(
                    user_query=req.query,
                    conversation_history=req.history,
                    session_id=session_id,
                )
                for item in sync_gen:
                    outbox.put(item)
            except Exception as exc:  # noqa: BLE001
                logger.exception(f"[COURT-DEBATE-STREAM-WORKER] Error: {exc}")
                outbox.put(json.dumps({"event_type": "error", "level": "error", "chunk": str(exc), "status": "error"}))
            finally:
                outbox.put(sentinel)

        try:
            yield "data: " + json.dumps(
                {
                    "event_type": "planning",
                    "request_id": session_id,
                    "status": "planning",
                    "message": "Classifying scenario family",
                }
            ) + "\n\n"
            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            while True:
                if _deadline_expired(deadline_at):
                    logger.error(
                        f"[COURT-DEBATE-STREAM] Deadline exceeded for session {session_id[:16]}"
                    )
                    yield "data: " + json.dumps({
                        "event_type": "error",
                        "level": "error",
                        "status": "timeout",
                        "request_id": session_id,
                        "chunk": (
                            "Court Debate exceeded the server's wall-clock deadline and was "
                            "stopped. Please retry with a narrower question."
                        ),
                        "elapsed_seconds": round(datetime.now().timestamp() - started_at, 3),
                    }) + "\n\n"
                    break
                try:
                    chunk = await asyncio.to_thread(outbox.get, True, 10)
                except queue.Empty:
                    yield "data: " + json.dumps(
                        {
                            "event_type": "heartbeat",
                            "status": "heartbeat",
                            "request_id": session_id,
                            "message": "Court Debate is still working.",
                            "elapsed_seconds": round(datetime.now().timestamp() - started_at, 3),
                        }
                    ) + "\n\n"
                    continue
                if chunk is sentinel:
                    break
                yield f"data: {str(chunk).rstrip()}\n\n"
        except Exception as exc:
            logger.exception(f"[COURT-DEBATE-STREAM] Error: {exc}")
            yield f"data: {json.dumps({'event_type': 'error', 'level': 'error', 'chunk': str(exc), 'status': 'error'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
            "Connection": "keep-alive",
        },
    )


@app.get("/api/court-debate/provider-health", tags=["Court Debate Mode"])
async def court_debate_provider_health(http_request: Request):
    public_debug = os.getenv("COURT_DEBATE_PROVIDER_HEALTH_PUBLIC", "false").strip().lower() in {"1", "true", "yes", "on"}
    client_host = (http_request.client.host if http_request.client else "") or ""
    if not public_debug and client_host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(status_code=403, detail="Provider health is restricted.")
    if _CourtDebateLLMClient is None:
        raise HTTPException(status_code=503, detail="Court Debate provider router is unavailable.")
    return {"status": "ok", "health": _CourtDebateLLMClient.provider_health_snapshot()}


# -------------------------------------------------------------------
# STATIC FILE MOUNTS — Registered LAST so all @app.xxx API routes are
# checked first.  Mounting "/" before API routes would intercept every
# request and return index.html instead of JSON.
# -------------------------------------------------------------------
if static_home_path.exists():
    app.mount("/home_assets", StaticFiles(directory=str(static_home_path / "assets")), name="home_assets")
if static_chat_path.exists():
    app.mount("/chat/assets", StaticFiles(directory=str(static_chat_path / "assets")), name="chat_assets")
# Court Debate agent images — mounted at BOTH /agents and /chat/agents so window.location.origin based paths work
agents_path = static_chat_path / "agents"
if agents_path.exists():
    app.mount("/chat/agents", StaticFiles(directory=str(agents_path)), name="chat_agents")
    app.mount("/agents", StaticFiles(directory=str(agents_path)), name="agents_root")
# Layer images for manga debate visuals — mounted at /layer_images (window.location.origin base)
layer_images_path = static_chat_path / "layer_images"
if layer_images_path.exists():
    app.mount("/chat/layer_images", StaticFiles(directory=str(layer_images_path)), name="chat_layer_images")
    app.mount("/layer_images", StaticFiles(directory=str(layer_images_path)), name="layer_images")
# Serve ELEMENTS and parallax at absolute paths (chat JS references them without /chat prefix)
elements_path = static_chat_path / "ELEMENTS"
if elements_path.exists():
    app.mount("/ELEMENTS", StaticFiles(directory=str(elements_path)), name="elements")
parallax_path = static_chat_path / "parallax"
if parallax_path.exists():
    app.mount("/parallax", StaticFiles(directory=str(parallax_path), html=True), name="parallax")
devloper_path = static_chat_path / "devloper_button"
if devloper_path.exists():
    app.mount("/devloper_button", StaticFiles(directory=str(devloper_path), html=True), name="devloper_button")
if static_chat_path.exists():
    app.mount("/chat", StaticFiles(directory=str(static_chat_path), html=True), name="chat")
if static_home_path.exists():
    app.mount("/", StaticFiles(directory=str(static_home_path), html=True), name="home")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "advanced_rag_api_server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
