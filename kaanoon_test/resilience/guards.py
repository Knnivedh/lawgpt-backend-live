"""Concurrency guard + wall-clock deadline for the heavy LLM/retrieval endpoints.

Background — the single-worker outage
-------------------------------------
Five concurrent backtest processes against a single gunicorn worker turned every
request from ~3-5s into 120-150s and then stopped the site answering entirely
(TCP connected, zero bytes for 600s).  Two things combined:

1. ``query_endpoint`` is declared ``async`` but performs no ``await`` — the whole
   retrieval + LLM pipeline runs *synchronously on the event loop*.  A single
   in-flight query therefore freezes the entire worker: ``/api/health``, static
   assets and every other request queue behind it with nothing to show for it.
2. Nothing limited how many of those blocking calls could be in flight at once,
   so five backtests saturated the 2 vCPU box and latency compounded.

This module addresses both:

* :class:`QueryGuardMiddleware` — caps simultaneously-executing heavy requests
  and rejects the overflow **fast** with ``429`` + ``Retry-After``.
* :func:`run_query_work` — moves the blocking work onto a dedicated thread pool
  and enforces a wall-clock deadline well under gunicorn's 600s worker timeout.

Reject-fast vs. bounded-queue
-----------------------------
We reject fast on purpose.  A bounded queue would still have reproduced the
outage, only with a shorter line: during the incident the *queue* was the
outage.  Requests waited behind a saturated thread pool until 120-150s each, and
because each caller was still holding a socket open the box never got a chance to
recover.  A queue also cannot express what to do when its own wait expires,
which is a second, rarer failure mode.  Rejecting costs the client one fast 429,
frees the socket immediately, and keeps ``/api/health`` and the static assets
answering — under saturation the site stays *up and honest* instead of going
silent.  Callers get a machine-readable ``Retry-After`` so they back off instead
of stacking more load.

The cap is deliberately set *below* the size of the thread pool that runs the
work.  If admission exceeded the pool, the surplus would queue inside the
executor — invisible, unbounded in latency, and precisely the failure we guard
against.

Configuration (all optional, all backwards compatible)
------------------------------------------------------
``LAWGPT_MAX_CONCURRENT_QUERIES``  max simultaneous heavy requests (default 4,
                                <= 0 disables the guard)
``LAWGPT_QUERY_TIMEOUT_S``        wall-clock deadline per request (default 120s,
                                <= 0 disables the deadline)
``LAWGPT_QUERY_RETRY_AFTER_S``    Retry-After hint on a 429 (default 15s)
"""
import asyncio
import contextvars
import functools
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, FrozenSet, Optional, Set

from fastapi.responses import JSONResponse

logger = logging.getLogger("API_SERVER.RESILIENCE")

# The heavy LLM/retrieval paths. Everything else (/api/health, static assets,
# auth, diagnostics) must stay reachable while these are saturated.
GUARDED_PATHS: FrozenSet[str] = frozenset({
    "/api/query",
    "/api/query/stream",
    "/api/court-debate",
    "/api/court-debate/stream",
})

DEFAULT_MAX_CONCURRENT_QUERIES = 4
DEFAULT_QUERY_TIMEOUT_S = 120.0
DEFAULT_RETRY_AFTER_S = 15.0


def _env_number(name: str, default: Any, cast: Callable[[str], Any]) -> Any:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return cast(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning("[RESILIENCE] Ignoring invalid %s=%r; using %s", name, raw, default)
        return default


def max_concurrent_queries() -> int:
    return int(_env_number("LAWGPT_MAX_CONCURRENT_QUERIES", DEFAULT_MAX_CONCURRENT_QUERIES, int))


def query_timeout_s() -> Optional[float]:
    """Wall-clock deadline for a heavy request, or None when disabled."""
    value = float(_env_number("LAWGPT_QUERY_TIMEOUT_S", DEFAULT_QUERY_TIMEOUT_S, float))
    return value if value > 0 else None


def query_retry_after_s() -> float:
    return float(_env_number("LAWGPT_QUERY_RETRY_AFTER_S", DEFAULT_RETRY_AFTER_S, float))


class QueryDeadlineExceeded(Exception):
    """Raised when a heavy request exceeds LAWGPT_QUERY_TIMEOUT_S."""

    def __init__(self, timeout_s: float):
        super().__init__(f"Query exceeded the {timeout_s:.0f}s wall-clock deadline")
        self.timeout_s = timeout_s


class _Slot:
    """One admitted heavy request. ``release`` is idempotent by design."""

    __slots__ = ("path", "started_at", "counted", "released", "deferred")

    def __init__(self, path: str, counted: bool):
        self.path = path
        self.started_at = time.monotonic()
        self.counted = counted
        self.released = False
        self.deferred = False
class ConcurrencyGuard:
    """Non-blocking admission control for the heavy request paths."""

    def __init__(self, name: str = "query", max_concurrent: Optional[int] = None):
        self._name = name
        self._lock = threading.Lock()
        self._in_flight = 0
        self._rejected = 0
        self._max = DEFAULT_MAX_CONCURRENT_QUERIES if max_concurrent is None else int(max_concurrent)

    @property
    def max_concurrent(self) -> int:
        return self._max

    @property
    def in_flight(self) -> int:
        return self._in_flight

    def configure(self, max_concurrent: int) -> None:
        with self._lock:
            self._max = int(max_concurrent)

    def try_acquire(self, path: str) -> Optional[_Slot]:
        """Admit the request, or return None when the cap is already reached.

        Never blocks. A queued request would hold its socket open and add to the
        pile-up, which is the failure mode this guard exists to stop.
        """
        with self._lock:
            if self._max <= 0:
                # Guard disabled - hand back an uncounted slot so callers need no
                # separate code path.
                return _Slot(path, counted=False)
            if self._in_flight >= self._max:
                self._rejected += 1
                return None
            self._in_flight += 1
            return _Slot(path, counted=True)

    def defer_release(self, slot: _Slot) -> None:
        """Hand this slot to the caller: the worker outlives the HTTP response.

        Used on timeout - the blocking call cannot be interrupted, so the slot
        must stay counted until the thread genuinely finishes. Releasing it at
        the deadline would let a new request in behind a thread that is still
        saturating the box.
        """
        with self._lock:
            slot.deferred = True

    def release(self, slot: Optional[_Slot]) -> None:
        """Release a slot unless it was deferred or already released."""
        if slot is None:
            return
        with self._lock:
            if slot.released or slot.deferred or not slot.counted:
                return
            slot.released = True
            self._in_flight = max(0, self._in_flight - 1)

    def force_release(self, slot: Optional[_Slot]) -> None:
        """Release a deferred slot. Called when the orphaned worker finishes."""
        if slot is None:
            return
        with self._lock:
            if slot.released or not slot.counted:
                return
            slot.released = True
            self._in_flight = max(0, self._in_flight - 1)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "max_concurrent": self._max,
                "in_flight": self._in_flight,
                "rejected_total": self._rejected,
            }


# Process-wide singletons. One guard per worker process: the incident was caused
# by a single worker absorbing all load, so a per-process cap is the correct
# unit of admission control.
query_guard = ConcurrencyGuard("query", max_concurrent_queries())

# The slot the current request holds, if any. Set by the middleware and read by
# run_query_work so a timeout can defer the release to the real worker thread.
_CURRENT_SLOT: "contextvars.ContextVar[Optional[_Slot]]" = contextvars.ContextVar(
    "lawgpt_current_query_slot", default=None
)
# --------------------------------------------------------------------------
# Dedicated thread pool for heavy work
# --------------------------------------------------------------------------
# Deliberately NOT the default executor: /api/health and the store probes use
# run_in_executor on the default pool and must keep working while every query
# slot is busy.
_EXECUTOR_LOCK = threading.Lock()
_QUERY_EXECUTOR: Optional[ThreadPoolExecutor] = None
_QUERY_EXECUTOR_SIZE = 0


def query_executor(max_workers: int) -> ThreadPoolExecutor:
    """Thread pool sized to the admission cap, grown (never shrunk) on config."""
    global _QUERY_EXECUTOR, _QUERY_EXECUTOR_SIZE
    size = max(1, int(max_workers))
    with _EXECUTOR_LOCK:
        if _QUERY_EXECUTOR is None or size > _QUERY_EXECUTOR_SIZE:
            if _QUERY_EXECUTOR is not None:
                # Idle threads exit once they see the shutdown flag; in-flight
                # ones finish first. Config changes are rare (boot / tests).
                _QUERY_EXECUTOR.shutdown(wait=False)
            _QUERY_EXECUTOR = ThreadPoolExecutor(
                max_workers=size, thread_name_prefix="lawgpt-query"
            )
            _QUERY_EXECUTOR_SIZE = size
        return _QUERY_EXECUTOR


async def run_query_work(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run a blocking heavy-work callable off the event loop under a deadline.

    Two guarantees matter here:

    * the event loop stays free, so ``/api/health`` and static assets answer
      while queries are in flight (the direct cause of the zero-byte outage);
    * the request cannot occupy the worker indefinitely - the deadline fires
      well before gunicorn's 600s timeout.

    Raises :class:`QueryDeadlineExceeded` on timeout. The blocking thread is not
    cancellable, so on timeout the current admission slot is deferred and
    released only when that thread actually finishes.
    """
    loop = asyncio.get_running_loop()
    timeout_s = query_timeout_s()
    slot = _CURRENT_SLOT.get()
    call = functools.partial(
        contextvars.copy_context().run, functools.partial(fn, *args, **kwargs)
    )
    workers = query_guard.max_concurrent or DEFAULT_MAX_CONCURRENT_QUERIES
    executor = query_executor(workers)

    if timeout_s is None:
        return await loop.run_in_executor(executor, call)

    future = loop.run_in_executor(executor, call)
    try:
        # shield(): a timeout must cancel only our wait, never the work itself.
        return await asyncio.wait_for(asyncio.shield(future), timeout=timeout_s)
    except asyncio.TimeoutError:
        if future.done():
            # The callable itself raised TimeoutError - not our deadline.
            return future.result()
        logger.error(
            "[RESILIENCE] Query deadline of %.0fs exceeded (path=%s in_flight=%s); "
            "the worker thread is still running and keeps its slot.",
            timeout_s, getattr(slot, "path", "?"), query_guard.in_flight,
        )
        if slot is not None:
            query_guard.defer_release(slot)
            future.add_done_callback(lambda _f: query_guard.force_release(slot))
        raise QueryDeadlineExceeded(timeout_s) from None


def stream_deadline() -> Optional[float]:
    """Absolute monotonic deadline for a streaming heavy request."""
    timeout_s = query_timeout_s()
    return None if timeout_s is None else time.monotonic() + timeout_s


def deadline_expired(deadline_at: Optional[float]) -> bool:
    return deadline_at is not None and time.monotonic() > deadline_at
# --------------------------------------------------------------------------
# ASGI middleware
# --------------------------------------------------------------------------
class QueryGuardMiddleware:
    """Cap simultaneously-executing heavy requests; reject the rest fast.

    Implemented as raw ASGI (not BaseHTTPMiddleware) on purpose: a raw ASGI
    ``await self.app(...)`` spans the *entire* streaming lifetime of an SSE
    response, so a /api/query/stream request holds its slot until the last chunk
    is written. BaseHTTPMiddleware returns as soon as response headers are
    flushed, which would let unlimited streams through and defeat the cap.
    """

    def __init__(
        self,
        app: Callable[..., Any],
        guard: Optional[ConcurrencyGuard] = None,
        guarded_paths: Optional[Set[str]] = None,
    ):
        self.app = app
        self.guard = guard or query_guard
        self.guarded_paths: Set[str] = set(
            guarded_paths if guarded_paths is not None else GUARDED_PATHS
        )

    async def __call__(self, scope: Dict[str, Any], receive: Callable[..., Any],
                       send: Callable[..., Any]) -> None:
        if scope.get("type") != "http" or scope.get("path") not in self.guarded_paths:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        slot = self.guard.try_acquire(path)
        if slot is None:
            await self._reject(scope, receive, send, path)
            return

        token = _CURRENT_SLOT.set(slot)
        try:
            await self.app(scope, receive, send)
        finally:
            _CURRENT_SLOT.reset(token)
            self.guard.release(slot)

    async def _reject(self, scope: Dict[str, Any], receive: Callable[..., Any],
                      send: Callable[..., Any], path: str) -> None:
        snapshot = self.guard.snapshot()
        retry_after = max(1, int(round(query_retry_after_s())))
        # Log the first rejection and then every 25th: a saturated worker must
        # not turn its own log into the next bottleneck.
        if snapshot["rejected_total"] == 1 or snapshot["rejected_total"] % 25 == 0:
            logger.warning(
                "[RESILIENCE] Rejected %s: %s heavy requests already in flight (cap=%s).",
                path, snapshot["in_flight"], snapshot["max_concurrent"],
            )
        message = (
            "LAW-GPT is at capacity. Please retry in "
            f"{retry_after}s - retrying immediately slows everyone down."
        )
        response = JSONResponse(
            status_code=429,
            # "detail" mirrors the existing 429 contract raised by the query
            # endpoint itself, so current frontend handling keeps working.
            content={
                "error": "server_busy",
                "detail": message,
                "message": message,
                "retry_after": retry_after,
                "max_concurrent_queries": snapshot["max_concurrent"],
                "in_flight": snapshot["in_flight"],
                "path": path,
            },
            headers={
                "Retry-After": str(retry_after),
                "X-LawGPT-Concurrency-Limit": str(snapshot["max_concurrent"]),
                "X-LawGPT-In-Flight": str(snapshot["in_flight"]),
            },
        )
        await response(scope, receive, send)


def install_query_guard(app: Any, guard: Optional[ConcurrencyGuard] = None) -> bool:
    """Attach the guard middleware. Returns False (never raises) on failure."""
    try:
        app.add_middleware(QueryGuardMiddleware, guard=guard or query_guard)
        logger.info(
            "[RESILIENCE] Query guard active: max_concurrent=%s timeout=%ss",
            (guard or query_guard).max_concurrent,
            query_timeout_s(),
        )
        return True
    except Exception as exc:  # noqa: BLE001 - a guard must never block startup
        logger.warning("[RESILIENCE] Query guard could not be installed: %s", exc)
        return False