"""G-benchmark fix: a provider timeout must not become an HTTP 500.

THE MEASURED FAILURE
--------------------
Live benchmark against lawgpt-backend-live scored 22.8/100 (F, UNUSABLE) with
4 of 5 questions erroring:

    hfl_01  HTTP 500  "Query failed: Request timed out."
    hfl_02  HTTP 504  Gateway Timeout
    hfl_04  HTTP 500  "Query failed: Request timed out."
    hfl_05  HTTP 504  Gateway Timeout

Root cause was two separate defects in clarification_engine.py:

  1. `_call_llm` used a hardcoded `timeout=30`, ignoring
     LLM_CLIENT_TIMEOUT_SECONDS entirely. Its `except` only handled 404 and
     429 -- every OTHER failure (timeout, connection reset, upstream 5xx) hit
     `else: raise`, so the FIRST timeout escaped as HTTP 500.

  2. `synthesize_and_execute()` and `_generate_next_question()` called
     `_call_llm` with NO error handling at all. A stall there discarded a
     fully-collected 5-question interview and 500'd the request.

The worst part: the user had already supplied every fact. Losing the whole
consultation to one slow provider call is not acceptable behaviour.

WHAT EACH ASSERTION PROVES
  1. a timeout is classified transient, not fatal
  2. a timeout is retried, and a retry that succeeds returns a real answer
  3. sustained timeouts stay inside a wall-clock budget
  4. a 404 still moves to the next model candidate (existing behaviour kept)
  5. a truly fatal error still raises immediately (no pointless retry storm)
  6. the per-call timeout is env-tunable and hard-capped
  7. the request actually carries the tuned timeout (not the old hardcoded 30)
  8. synthesize_and_execute completes on the transcript when the LLM is dead
  9. _generate_next_question still returns a real question when the LLM is dead

Run:
    cd E:\\LAW-GPT_new\\azure_backend_stage
    E:\\LAW-GPT_new\\.venv\\Scripts\\python.exe kaanoon_test\\test_g11_clarification_timeout.py
"""
import logging
import os
import sys
import time
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
logging.disable(logging.CRITICAL)

from kaanoon_test.system_adapters.clarification_engine import (  # noqa: E402
    ClarificationSession,
)

PASSED, FAILED = [], []


def check(label, condition, detail=""):
    (PASSED if condition else FAILED).append(label)
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}")
    if detail:
        print(f"         {detail}")


def fresh(provider="groq", manager=None):
    """A session with NO network client - we only exercise _call_llm."""
    s = object.__new__(ClarificationSession)
    s.provider = provider
    s.model = "primary-model"
    s._fallback_models = ["fallback-a", "fallback-b"]
    s._client_manager = manager
    return s


class FakeCompletions:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        act = self.behaviour.pop(0) if self.behaviour else "ok"
        if act == "ok":
            msg = types.SimpleNamespace(content="OK from model")
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])
        raise act


def client_with(behaviour):
    c = FakeCompletions(behaviour)
    chat = types.SimpleNamespace(completions=c)
    return types.SimpleNamespace(chat=chat), c


def main():
    print("=" * 74)
    print("G-benchmark fix - clarification timeout resilience")
    print("=" * 74)

    print("[1] failure classification")
    cls = ClarificationSession._classify_call_error
    check("timeout -> transient",
          cls("APITimeoutError: Request timed out") == "transient")
    check("read timeout -> transient",
          cls("httpx.ReadTimeout: timed out") == "transient")
    check("connection reset -> transient",
          cls("Connection reset by peer") == "transient")
    check("upstream 503 -> transient",
          cls("Error code: 503 - Service Unavailable") == "transient")
    check("429 -> rate_limit", cls("429 Too Many Requests") == "rate_limit")
    check("OTPM ceiling -> rate_limit",
          cls("OTPM: Limit 1000, Used 992") == "rate_limit")
    check("404 -> model_gone", cls("404 model_not_found") == "model_gone")
    check("no available channel -> model_gone",
          cls("No available channel for model") == "model_gone")
    check("unrelated error -> fatal",
          cls("KeyError: 'answer'") == "fatal")
    print()

    print("[2] a timeout is RETRIED, and a successful retry returns an answer")
    s = fresh()
    fake, comp = client_with([
        RuntimeError("APITimeoutError: Request timed out."),
        "ok",
    ])
    s._get_client = lambda: fake
    os.environ["CLARIFICATION_LLM_BUDGET_SECONDS"] = "30"
    got = s._call_llm(messages=[{"role": "user", "content": "hi"}])
    check("retry after timeout returned a real answer",
          got.choices[0].message.content == "OK from model")
    check("exactly 2 attempts were made", len(comp.calls) == 2, f"{len(comp.calls)} calls")
    print()

    print("[3] sustained timeouts stay inside a wall-clock budget")
    s2 = fresh()
    fake2, comp2 = client_with([RuntimeError("APITimeoutError: Request timed out.")] * 30)
    s2._get_client = lambda: fake2
    os.environ["CLARIFICATION_LLM_BUDGET_SECONDS"] = "12"
    t0 = time.time()
    raised = None
    try:
        s2._call_llm(messages=[{"role": "user", "content": "hi"}])
    except Exception as exc:
        raised = exc
    el = time.time() - t0
    check("raised a RuntimeError naming the exhaustion", raised is not None
          and "exhausted" in str(raised).lower(), str(raised)[:90])
    check("bounded by the budget, not an open-ended retry storm",
          el < 15, f"took {el:.1f}s with a 12s budget")
    print()

    print("[4] 404 still advances to the next model candidate")
    s3 = fresh()
    fake3, comp3 = client_with([
        RuntimeError("Error code: 404 - model_not_found"),
        "ok",
    ])
    s3._get_client = lambda: fake3
    got3 = s3._call_llm(messages=[{"role": "user", "content": "hi"}])
    used = [c.get("model") for c in comp3.calls]
    check("fell through to the next candidate",
          used == ["primary-model", "fallback-a"], str(used))
    check("returned the fallback answer", got3 is not None)
    check("session remembers the working model",
          s3.model == "fallback-a", s3.model)
    print()

    print("[5] a genuinely fatal error raises immediately (no retry storm)")
    s4 = fresh()
    fake4, comp4 = client_with([KeyError("not a network problem")] * 30)
    s4._get_client = lambda: fake4
    t0 = time.time()
    fatal = None
    try:
        s4._call_llm(messages=[{"role": "user", "content": "hi"}])
    except Exception as exc:
        fatal = exc
    el = time.time() - t0
    check("fatal error propagated", isinstance(fatal, KeyError))
    check("fatal error did NOT retry (1 attempt only)",
          len(comp4.calls) == 1, f"{len(comp4.calls)} calls")
    check("fatal error returned fast", el < 2, f"{el:.2f}s")
    print()

    print("[6] the per-call timeout is tunable and hard-capped")
    os.environ.pop("CLARIFICATION_LLM_TIMEOUT_SECONDS", None)
    os.environ.pop("LLM_CLIENT_TIMEOUT_SECONDS", None)
    os.environ["LLM_CLIENT_TIMEOUT_MAX"] = "90"
    check("defaults to 45s", ClarificationSession._call_timeout() == 45.0,
          str(ClarificationSession._call_timeout()))
    os.environ["CLARIFICATION_LLM_TIMEOUT_SECONDS"] = "12"
    check("honours CLARIFICATION_LLM_TIMEOUT_SECONDS",
          ClarificationSession._call_timeout() == 12.0)
    os.environ["CLARIFICATION_LLM_TIMEOUT_SECONDS"] = "9999"
    check("a silly value is capped at LLM_CLIENT_TIMEOUT_MAX",
          ClarificationSession._call_timeout() == 90.0,
          str(ClarificationSession._call_timeout()))
    os.environ["CLARIFICATION_LLM_TIMEOUT_SECONDS"] = "not-a-number"
    check("a malformed value falls back to the default, never crashes",
          ClarificationSession._call_timeout() == 45.0)
    print()

    print("[7] the request actually carries the tuned timeout (not 30)")
    s5 = fresh()
    fake5, comp5 = client_with(["ok"])
    s5._get_client = lambda: fake5
    os.environ["CLARIFICATION_LLM_TIMEOUT_SECONDS"] = "17"
    s5._call_llm(messages=[{"role": "user", "content": "hi"}])
    check("timeout passed to the SDK is 17, not the old hardcoded 30",
          comp5.calls[0].get("timeout") == 17.0,
          f"timeout={comp5.calls[0].get('timeout')}")
    os.environ.pop("CLARIFICATION_LLM_TIMEOUT_SECONDS", None)
    print()

    print("[8] synthesize_and_execute completes even when the LLM is dead")
    s6 = fresh()
    s6.qa_history = [
        {"q": "Q1?", "a": "A1"},
        {"q": "Q2?", "a": "A2"},
        {"q": "Q3?", "a": "A3"},
    ]
    s6.initial_intent = "Hindu divorce"
    s6.initial_legal_context = "some context"
    s6._is_interfaith_conversion_scenario = lambda: False
    s6._is_integrated_contract_criminal_banking_scenario = lambda: False
    s6._build_final_analysis_request = lambda matrix, tr: f"REQ:{len(matrix)}:{len(tr)}"
    fake6, _ = client_with([RuntimeError("APITimeoutError: Request timed out.")] * 30)
    s6._get_client = lambda: fake6
    os.environ["CLARIFICATION_LLM_BUDGET_SECONDS"] = "10"
    out = None
    err = None
    t0 = time.time()
    try:
        out = s6.synthesize_and_execute()
    except Exception as exc:
        err = exc
    el = time.time() - t0
    check("did NOT raise (this was the HTTP 500)", err is None, str(err)[:90])
    check("returned a usable synthesis dict",
          isinstance(out, dict) and out.get("status") == "complete")
    check("transcript was preserved into the final request",
          out and "REQ:" in (out.get("final_request") or ""),
          (out or {}).get("final_request"))
    check("the interview was not discarded",
          "Q1?" in (out or {}).get("transcript", ""))
    check("finished inside the budget", el < 15, f"{el:.1f}s")
    print()

    print("[9] _generate_next_question still returns a question when LLM is dead")
    s7 = fresh()
    s7.qa_history = [{"q": "Q1?", "a": "A1"}]
    s7.max_questions = 5
    s7.initial_intent = "alimony"
    s7._next_unasked_question = lambda step: "Deterministic planned question?"
    s7._next_question_focus = lambda: "what relief do you want"
    s7._question_for_focus = lambda focus, n: f"Fallback question ({focus})"
    s7._sanitize_single_question = lambda t, fallback="": t or fallback
    fake7, _ = client_with([RuntimeError("APITimeoutError: Request timed out.")] * 30)
    s7._get_client = lambda: fake7
    os.environ["CLARIFICATION_LLM_BUDGET_SECONDS"] = "10"
    q = None
    err = None
    try:
        q = s7._generate_next_question()
    except Exception as exc:
        err = exc
    check("did NOT raise", err is None, str(err)[:90])
    check("returned a non-empty question", bool(q and str(q).strip()), repr(q)[:80])
    print()

    print("=" * 74)
    print(f"RESULT: {len(PASSED)} passed, {len(FAILED)} failed")
    for f in FAILED:
        print(f"  FAILED: {f}")
    print("=" * 74)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
    check("returned the fallback answer", got3 is not None)
    check("session remembers the working model",
          s3.model == "fallback-a", s3.model)
    print()

    print("[5] a genuinely fatal error raises immediately (no retry storm)")
    s4 = fresh()
    fake4, comp4 = client_with([KeyError("not a network problem")] * 30)
    s4._get_client = lambda: fake4
    t0 = time.time()
    fatal = None
    try:
        s4._call_llm(messages=[{"role": "user", "content": "hi"}])
    except Exception as exc:
        fatal = exc
    el = time.time() - t0
    check("fatal error propagated", isinstance(fatal, KeyError))
    check("fatal error did NOT retry (1 attempt only)",
          len(comp4.calls) == 1, f"{len(comp4.calls)} calls")
    check("fatal error returned fast", el < 2, f"{el:.2f}s")
    print()
def client_with(behaviour):
    c = FakeCompletions(behaviour)
    chat = types.SimpleNamespace(completions=c)
    return types.SimpleNamespace(chat=chat), c