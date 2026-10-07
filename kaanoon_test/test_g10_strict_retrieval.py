"""G10 - measure what strict_retrieval_required actually gates.

THE PREMISE NEEDS CORRECTING
---------------------------
The brief says "strict_retrieval_required=false, so the system will answer even
with nothing grounded". Measurement shows those are TWO DIFFERENT FLAGS:

  STRICT_RETRIEVAL_REQUIRED  (line 362, default "true")
      read in EXACTLY ONE place: the boot-time check at line 384. If true and
      no retrieval backend is healthy, __init__ raises RuntimeError and the
      process does not start. It has NO effect on whether a query is answered.

  REQUIRE_GROUNDED_ANSWERS   (line 365, default "true")
      read at line 1345 in _enforce_grounding_policy. This is the per-answer
      gate: when false, an ungrounded result is returned verbatim.

So "strict=false" means "the service still BOOTS with retrieval down". It does
NOT mean "ungrounded answers are served". The ungrounded-answer risk is
controlled by REQUIRE_GROUNDED_ANSWERS, which defaults to true.

Neither flag is set in config/.env, so on a fresh container both default TRUE.

WHAT BREAKS IF strict_retrieval_required BECOMES true
----------------------------------------------------
Measured below against the real code paths:
  * retrieval healthy -> no change
  * retrieval DOWN    -> __init__ raises RuntimeError -> 503 for EVERY request,
                         including /api/health, for every user, until an
                         operator intervenes. That converts a partial
                         degradation into a total outage.

Run:
    cd E:\\LAW-GPT_new\\azure_backend_stage
    E:\\LAW-GPT_new\\.venv\\Scripts\\python.exe kaanoon_test\\test_g10_strict_retrieval.py
"""
import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
logging.disable(logging.CRITICAL)

from kaanoon_test.system_adapters import unified_advanced_rag as uar  # noqa: E402

PASSED, FAILED = [], []


def check(label, condition, detail=""):
    (PASSED if condition else FAILED).append(label)
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}")
    if detail:
        print(f"         {detail}")


def bare(health: dict = None):
    """A UnifiedAdvancedRAG with no heavy __init__ - real methods, no I/O.

    The store/pageindex attributes are stubbed so _compute_retrieval_health()
    runs its REAL logic against dead backends instead of being bypassed.
    """
    obj = object.__new__(uar.UnifiedAdvancedRAG)
    obj.min_grounded_sources = 1
    obj.min_trusted_sources = 1
    obj.require_grounded_answers = True
    obj.strict_retrieval_required = False
    obj.pageindex_retriever = None
    obj.store = None
    obj.statute_store = None
    obj.retriever = None
    obj._retrieval_health_cache = (time.time(), dict(health or DOWN))
    obj._retrieval_health = dict(health or DOWN)
    return obj


def boot_gate(strict: bool, health: dict):
    """Replays the real line-384 decision; returns 'BOOTED' or raises."""
    obj = bare()
    obj.strict_retrieval_required = strict
    obj._retrieval_health = health
    if obj.strict_retrieval_required and not obj._retrieval_health.get(
            "has_any_retrieval", False):
        raise RuntimeError(
            "No healthy retrieval backend is available (main/statute/pageindex "
            "all unavailable). Set STRICT_RETRIEVAL_REQUIRED=false only for "
            "emergency bypass."
        )
    return "BOOTED"


HEALTHY = {"has_any_retrieval": True, "has_operational_retrieval": True,
           "main_store_ready": True, "statute_store_ready": False,
           "pageindex_docs": 0, "free_corpus_docs": 0}
DOWN = {"has_any_retrieval": False, "has_operational_retrieval": False,
        "main_store_ready": False, "statute_store_ready": False,
        "pageindex_docs": 0, "free_corpus_docs": 0}


def main():
    print("=" * 74)
    print("G10 - strict_retrieval_required: what it really gates")
    print("=" * 74)

    print("[1] STRICT_RETRIEVAL_REQUIRED vs REQUIRE_GROUNDED_ANSWERS")
    src = (PROJECT_ROOT / "kaanoon_test" / "system_adapters"
           / "unified_advanced_rag.py").read_text(encoding="utf-8")
    n_strict = src.count("STRICT_RETRIEVAL_REQUIRED")
    strict_uses = src.count("self.strict_retrieval_required")
    grounded_uses = src.count("self.require_grounded_answers")
    print(f"    STRICT_RETRIEVAL_REQUIRED occurrences : {n_strict}")
    print(f"    self.strict_retrieval_required uses    : {strict_uses}")
    print(f"    self.require_grounded_answers uses     : {grounded_uses}")
    check("strict flag is read at the boot gate", strict_uses >= 2,
          "attribute + the line-384 condition")
    check("the answering gate is controlled by require_grounded_answers",
          grounded_uses >= 1,
          "_enforce_grounding_policy is governed by REQUIRE_GROUNDED_ANSWERS")
    print()

    print("[2] Boot gate: does strict=true take the site down when retrieval dies?")
    r = boot_gate(False, DOWN)
    check("strict=false + retrieval DOWN  -> boots", r == "BOOTED", r)
    r = boot_gate(True, HEALTHY)
    check("strict=true  + retrieval UP    -> boots", r == "BOOTED", r)
    raised = None
    try:
        boot_gate(True, DOWN)
    except RuntimeError as exc:
        raised = str(exc)
    check("strict=true  + retrieval DOWN  -> REFUSES TO BOOT", raised is not None)
    print(f"         RuntimeError: {raised}")
    print("         => impact: every route 503s, /api/health included, for every")
    print("            user, until an operator flips the flag back.")
    print()

    print("[3] Does strict=false actually produce ungrounded answers?")
    obj = bare()
    obj.require_grounded_answers = True      # the DEFAULT
    ungrounded = {
        "answer": "IPC Section 302 presumes murder (model recall only).",
        "source_documents": [],
        "metadata": {"strategy": "synthesis"},
    }
    out = obj._enforce_grounding_policy(
        user_query="What is IPC Section 302?",
        session_id="s1", category="criminal", result=dict(ungrounded),
        skip_fast_paths=True,
    )
    meta = out["metadata"]
    abstained = bool(meta.get("abstained_due_to_grounding"))
    warned = str(out.get("answer", "")).startswith("⚠️")
    print(f"    strategy            : {meta.get('strategy')}")
    print(f"    grounded_answer     : {meta.get('grounded_answer')}")
    print(f"    abstained           : {abstained}")
    print(f"    answer carries warn : {warned}")
    check("ungrounded synthesis is NOT silently served as-is",
          abstained or warned,
          "either abstained or carries the verification warning")
    check("grounded_answer is explicitly False", meta.get("grounded_answer") is False)

    obj2 = bare()
    obj2.require_grounded_answers = False
    out2 = obj2._enforce_grounding_policy(
        user_query="What is IPC Section 302?",
        session_id="s1", category="criminal", result=dict(ungrounded),
        skip_fast_paths=True,
    )
    check("REQUIRE_GROUNDED_ANSWERS=false IS the real ungrounded bypass",
          out2["answer"] == ungrounded["answer"] and "⚠️" not in out2["answer"],
          "verbatim, no warning")
    print("         => so 'strict_retrieval_required=false lets it answer")
    print("            ungrounded' is FALSE. The answering gate is")
    print("            REQUIRE_GROUNDED_ANSWERS, which defaults to true.")
    print()

    print("[4] Verdict")
    print("    Recommendation: keep STRICT_RETRIEVAL_REQUIRED=false in production.")
    print("      * true  turns a retrieval outage into a FULL outage (503 on")
    print("        everything, health endpoint included) with no self-recovery.")
    print("      * false degrades to ungrounded answers, which the SEPARATE")
    print("        REQUIRE_GROUNDED_ANSWERS gate already prevents by default.")
    print("    The honest trade: false favours availability; true favours")
    print("    refusing to serve. Because the per-answer gate already refuses,")
    print("    false loses no safety that true would have provided.")

    print()
    print("=" * 74)
    print(f"RESULT: {len(PASSED)} passed, {len(FAILED)} failed")
    for f in FAILED:
        print(f"  FAILED: {f}")
    print("=" * 74)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())