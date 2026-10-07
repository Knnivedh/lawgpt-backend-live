"""Proves the concurrency guard and the wall-clock deadline actually engage.

Runs entirely offline against the REAL FastAPI app: real middleware, real
endpoint, real query thread pool, real deadline. The only thing stubbed is the
LLM seam itself -- ``_new_clarification_session`` / ``start_session`` are real
Groq calls in production -- so a "heavy request" here is a deterministic,
configurable sleep instead of a network call.

What each scenario proves
-------------------------
1. cap: N concurrent requests run, request N+1 gets 429 + Retry-After, never queued
2. the site stays answerable under saturation (/api/health is not starved)
3. every heavy path is guarded, not just /api/query
4. slots are returned when work completes (no slow leak)
5. the wall-clock deadline fires well under gunicorn's 600s, AND a timed-out
   request keeps its slot until its thread really finishes
6. the cap can be disabled (LAWGPT_MAX_CONCURRENT_QUERIES<=0) for a rollback

Run:
    cd E:\\LAW-GPT_new\\azure_backend_stage
    E:\\LAW-GPT_new\\.venv\\Scripts\\python.exe kaanoon_test\\test_query_guard.py
"""
import asyncio
import os
import sys
import threading
import time
import uuid
from pathlib import Path

# Must be set before the server is imported: the guard builds its cap at import.
os.environ["LAWGPT_MAX_CONCURRENT_QUERIES"] = "2"
os.environ["LAWGPT_QUERY_TIMEOUT_S"] = "30"
os.environ["LAWGPT_QUERY_RETRY_AFTER_S"] = "7"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx  # noqa: E402
from kaanoon_test import advanced_rag_api_server as srv  # noqa: E402
from kaanoon_test.resilience import guards  # noqa: E402

QUESTION = "Explain the doctrine of res judicata under Indian law."
PASSED = []
FAILED = []


def check(name, condition, detail=""):
    (PASSED if condition else FAILED).append(name)
    print(f"    [{'PASS' if condition else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


class Clock:
    """Tracks how many heavy requests are executing simultaneously."""

    def __init__(self):
        self.lock = threading.Lock()
        self.entered = 0
        self.peak = 0
        self.finished = 0

    def enter(self):
        with self.lock:
            self.entered += 1
            self.peak = max(self.peak, self.entered)

    def leave(self):
        with self.lock:
            self.entered -= 1
            self.finished += 1


class FakeClarificationSession:
    """Stands in for ClarificationSession at the seam /api/query always hits.

    ``_query_endpoint_impl`` calls ``_new_clarification_session()`` and then
    ``session.start_session(...)``; in production both hit Groq. Stubbing them
    lets the test push a genuinely blocking request through the real pipeline
    code path without a network call.
    """

    def __init__(self, work_s, clock):
        self._work_s = work_s
        self._clock = clock

    def start_session(self, user_question, category=None):
        self._clock.enter()
        try:
            time.sleep(self._work_s)
        finally:
            self._clock.leave()
        # "greeting" short-circuits straight to a response: no retrieval, no
        # synthesis, so the cost of the request is exactly the sleep above.
        return {"status": "greeting", "message": "Hello, LAW-GPT here."}


async def post_query(client, work_s, clock, tag="q"):
    started = time.monotonic()
    response = await client.post(
        "/api/query",
        json={"question": QUESTION, "session_id": f"guardtest_{tag}_{uuid.uuid4().hex[:8]}"},
    )
    return response, time.monotonic() - started


def install_fakes(work_s, clock):
    srv.rag_system = object()  # truthy: the endpoint 503s when this is None
    srv._new_clarification_session = lambda: FakeClarificationSession(work_s, clock)
    # Health would otherwise probe the live vector store; keep the test offline.
    srv._cached_store_check = lambda: {"reachable": True, "documents": 1234}
async def scenario_1_guard_engages(client, cap, work_s):
    print(f"\n1) N+1 rejection  (cap={cap}, {cap + 3} concurrent heavy requests, each {work_s}s)")
    clock = Clock()
    install_fakes(work_s, clock)

    responses = await asyncio.gather(
        *[post_query(client, work_s, clock, tag=f"s1-{i}") for i in range(cap + 3)]
    )
    admitted = [(r, e) for r, e in responses if r.status_code == 200]
    rejected = [(r, e) for r, e in responses if r.status_code == 429]

    print(f"    statuses: {[r.status_code for r, _ in responses]}")
    check(f"exactly {cap} requests admitted", len(admitted) == cap, f"got {len(admitted)}")
    check("exactly 3 requests rejected with 429", len(rejected) == 3, f"got {len(rejected)}")
    check("never more than `cap` executing at once", clock.peak == cap,
          f"peak concurrent = {clock.peak}")
    check("every 429 carries Retry-After",
          all(r.headers.get("retry-after") == "7" for r, _ in rejected),
          f"values={[r.headers.get('retry-after') for r, _ in rejected]}")
    check("429 body is machine-readable",
          all(r.json().get("error") == "server_busy" for r, _ in rejected))
    check("429 body keeps the `detail` contract the frontend already handles",
          all(isinstance(r.json().get("detail"), str) for r, _ in rejected))

    slowest_reject = max((e for _, e in rejected), default=0.0)
    fastest_admit = min((e for _, e in admitted), default=0.0)
    check("rejections are immediate, not queued behind the cap",
          slowest_reject < 1.0, f"slowest rejection = {slowest_reject:.3f}s")
    check("admitted requests actually ran to completion",
          fastest_admit >= work_s, f"fastest admitted = {fastest_admit:.3f}s (work={work_s}s)")
    check("rejection beat the admitted work by a wide margin",
          slowest_reject < fastest_admit / 2,
          f"reject={slowest_reject:.3f}s vs admit={fastest_admit:.3f}s")


async def scenario_2_health_stays_responsive(client, cap, work_s):
    print("\n2) /api/health stays answerable while the cap is saturated")
    clock = Clock()
    install_fakes(work_s, clock)

    in_flight = [asyncio.create_task(post_query(client, work_s, clock, tag=f"s2-{i}"))
                 for i in range(cap)]
    # Wait until the guard is genuinely full before probing health.
    while clock.entered < cap:
        await asyncio.sleep(0.02)

    started = time.monotonic()
    health = await client.get("/api/health")
    health_s = time.monotonic() - started
    print(f"    /api/health -> {health.status_code} in {health_s:.3f}s "
          f"(status={health.json().get('status')})")
    check("health answered 200 while every slot was busy", health.status_code == 200)
    check("health was not starved by the heavy work", health_s < 1.0, f"{health_s:.3f}s")
    check("health payload unchanged in shape", "rag_system_initialized" in health.json())

    await asyncio.gather(*in_flight)


async def scenario_3_all_heavy_paths_guarded(client, cap, work_s):
    print("\n3) every heavy path is guarded while the cap is saturated")
    clock = Clock()
    install_fakes(work_s, clock)

    in_flight = [asyncio.create_task(post_query(client, work_s, clock, tag=f"s3-{i}"))
                 for i in range(cap)]
    while clock.entered < cap:
        await asyncio.sleep(0.02)

    probes = [
        ("/api/query/stream", {"question": QUESTION}),
        ("/api/court-debate", {"query": QUESTION}),
        ("/api/court-debate/stream", {"query": QUESTION}),
    ]
    for path, body in probes:
        started = time.monotonic()
        response = await client.post(path, json=body)
        elapsed = time.monotonic() - started
        print(f"    {path:26s} -> {response.status_code} in {elapsed:.3f}s")
        check(f"{path} rejected with 429 at the cap", response.status_code == 429)
        check(f"{path} rejected immediately", elapsed < 1.0, f"{elapsed:.3f}s")

    await asyncio.gather(*in_flight)


async def scenario_4_slots_released(client, cap, work_s):
    print("\n4) slots are returned once work completes")
    await asyncio.gather(*[post_query(client, 0.4, Clock(), tag=f"s4-{i}") for i in range(cap + 2)])
    snapshot = guards.query_guard.snapshot()
    print(f"    guard snapshot: {snapshot}")
    check("no slots leaked after the burst", snapshot["in_flight"] == 0)
    response, _ = await post_query(client, 0.1, Clock(), tag="s4-final")
    check("a new request is admitted once slots free up", response.status_code == 200)
async def scenario_5_deadline(client, cap):
    print("\n5) wall-clock deadline (set to 1s against 6s of work)")
    os.environ["LAWGPT_QUERY_TIMEOUT_S"] = "1"
    work_s = 6.0
    clock = Clock()
    install_fakes(work_s, clock)

    try:
        response, elapsed = await post_query(client, work_s, clock, tag="s5")
        body = response.json()
        print(f"    /api/query -> {response.status_code} in {elapsed:.3f}s")
        print(f"    body system_info: {body.get('response', {}).get('system_info')}")
        check("deadline produced a 504", response.status_code == 504, str(response.status_code))
        check("504 arrived long before the work would have finished",
              elapsed < 3.0, f"{elapsed:.3f}s vs {work_s}s of work")
        check("504 keeps the response envelope the frontend reads",
              "response" in body and "answer" in body.get("response", {}))

        # The blocking thread cannot be interrupted. Its slot must stay counted,
        # otherwise the next request queues behind a thread that is still
        # saturating the box -- exactly the incident we are preventing.
        snapshot = guards.query_guard.snapshot()
        print(f"    guard snapshot right after the 504: {snapshot}")
        check("timed-out request still holds its slot", snapshot["in_flight"] == 1, str(snapshot))
        rejected, reject_s = await post_query(client, 0.1, Clock(), tag="s5b")
        print(f"    follow-up request -> {rejected.status_code} in {reject_s:.3f}s")
        check("next request is refused, not queued behind the orphan thread",
              rejected.status_code == 429)

        deadline = time.monotonic() + 20
        while guards.query_guard.snapshot()["in_flight"] and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
        check("slot is released once the orphaned thread finishes",
              guards.query_guard.snapshot()["in_flight"] == 0)
    finally:
        os.environ["LAWGPT_QUERY_TIMEOUT_S"] = "30"


async def scenario_6_cap_can_be_disabled(client, cap):
    print("\n6) LAWGPT_MAX_CONCURRENT_QUERIES=0 disables the guard (rollback path)")
    guards.query_guard.configure(0)
    clock = Clock()
    install_fakes(1.0, clock)
    try:
        responses = await asyncio.gather(
            *[post_query(client, 1.0, clock, tag=f"s6-{i}") for i in range(cap + 3)]
        )
        codes = [r.status_code for r, _ in responses]
        print(f"    statuses: {codes}, peak concurrent = {clock.peak}")
        check("nothing is rejected when the guard is disabled", 429 not in codes)
        check("all requests executed concurrently", clock.peak == cap + 3, f"peak={clock.peak}")
    finally:
        guards.query_guard.configure(cap)


async def main():
    cap = guards.query_guard.max_concurrent
    print("=" * 78)
    print("LAW-GPT concurrency guard + query deadline")
    print(f"python {sys.version.split()[0]}  |  guard cap = {cap}  |  "
          f"timeout = {guards.query_timeout_s():.0f}s  |  "
          f"retry-after = {guards.query_retry_after_s():.0f}s")
    print(f"guarded paths: {sorted(guards.GUARDED_PATHS)}")
    print(f"app routes: {len(srv.app.routes)}  |  resilience available: {srv._RESILIENCE_AVAILABLE}")
    print("=" * 78)

    saved = (srv.rag_system, srv._new_clarification_session, srv._cached_store_check)
    transport = httpx.ASGITransport(app=srv.app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://guardtest",
                                     timeout=60.0) as client:
            await scenario_1_guard_engages(client, cap, 2.0)
            await scenario_2_health_stays_responsive(client, cap, 3.0)
            await scenario_3_all_heavy_paths_guarded(client, cap, 3.0)
            await scenario_4_slots_released(client, cap, 0.4)
            await scenario_5_deadline(client, cap)
            await scenario_6_cap_can_be_disabled(client, cap)
    finally:
        (srv.rag_system, srv._new_clarification_session, srv._cached_store_check) = saved
        os.environ["LAWGPT_QUERY_TIMEOUT_S"] = "30"
        guards.query_guard.configure(cap)

    print("\n" + "=" * 78)
    print(f"RESULT: {len(PASSED)} passed, {len(FAILED)} failed")
    for name in FAILED:
        print(f"  FAILED: {name}")
    print("=" * 78)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))