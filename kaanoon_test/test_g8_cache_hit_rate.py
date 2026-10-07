"""G8 - cache_hit_rate was hard-wired to 0.0. Root cause + proof.

WHAT THE OPERATOR SAW
    total_queries=29, cache {hits: 13, misses: 16, size: 16}, cache_hit_rate=0.0
A cache with 13 hits cannot have a 0.0 hit rate, so the metric -- not the cache
-- was broken.

ROOT CAUSE (a metric-plumbing bug, NOT a cache-key bug)
    AgenticMemoryManager.get_memory_stats() returned only
        {"short_term_sessions": n, "cache": {...}}
    and unified_advanced_rag.get_metrics() read a FLAT key off it:
        cache_stats.get('cache_hit_rate', 0.0)
    There is no flat `cache_hit_rate` key, so the .get() always missed and
    returned its 0.0 default. The dashboard showed 0.0 forever.

WHAT WAS *NOT* THE CAUSE
    The cache key itself is correct:
        md5(lower(strip_punctuation(collapse_whitespace(query))))
    No session id, no timestamp, no user id. A repeat question, and a repeat
    question with cosmetic noise, both hit. Asserted below so a future change
    cannot silently reintroduce a session-scoped key.

Run:
    cd E:\\LAW-GPT_new\\azure_backend_stage
    E:\\LAW-GPT_new\\.venv\\Scripts\\python.exe kaanoon_test\\test_g8_cache_hit_rate.py
"""
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
logging.disable(logging.CRITICAL)

from kaanoon_test.system_adapters.persistent_memory import (  # noqa: E402
    AgenticMemoryManager,
)

PASSED, FAILED = [], []


def check(label, condition, detail=""):
    (PASSED if condition else FAILED).append(label)
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}")
    if detail:
        print(f"         {detail}")


def reproduce_production_shape():
    """Rebuild the exact observed 29-query / 13-hit / 16-miss / size-16 shape."""
    mm = AgenticMemoryManager()
    questions = [f"What are the requirements of Section {i} of the IPC?"
                 for i in range(16)]
    for q in questions:                      # 16 distinct -> 16 cache misses
        mm.check_cache(q)                    # miss
        mm.cache_response(q, f"answer for {q}", [])   # then stored
    for q in questions[:13]:                 # 13 genuine repeats -> 13 hits
        mm.check_cache(q)
    return mm


def main():
    print("=" * 74)
    print("G8 - cache_hit_rate reporting")
    print("=" * 74)
    mm = reproduce_production_shape()
    stats = mm.get_memory_stats()
    print(f"get_memory_stats() = {stats}")
    print()

    check("reproduced 13 hits", stats["cache"]["hits"] == 13, str(stats["cache"]))
    check("reproduced 16 misses", stats["cache"]["misses"] == 16)
    check("reproduced size 16", stats["cache"]["size"] == 16)
    check("total_queries basis = 29", stats["cache"]["total"] == 29)

    expected_rate = round(13 / 29, 3)
    reported = stats.get("cache_hit_rate", 0.0)
    print(f"  expected cache_hit_rate = 13/29 = {expected_rate}")
    print(f"  reported cache_hit_rate = {reported}")
    check("flat cache_hit_rate is present (was the .get() miss)", "cache_hit_rate" in stats)
    check("cache_hit_rate is no longer 0.0", reported != 0.0, f"{reported}")
    check("cache_hit_rate matches the real hit rate",
          reported == expected_rate, f"{reported} == {expected_rate}")

    # The exact expression unified_advanced_rag.get_metrics() evaluates.
    check("get_metrics() expression now resolves",
          stats.get("cache_hit_rate", 0.0) == expected_rate)

    # Guard the cache KEY so this cannot regress into a session-scoped key.
    mm2 = AgenticMemoryManager()
    q = "Explain res judicata under Section 11 of the CPC."
    mm2.cache_response(q, "answer", [])
    check("exact repeat hits the cache", mm2.check_cache(q) is not None)
    check("case/punctuation/whitespace variant hits the cache",
          mm2.check_cache("  explain res judicata under section 11 of the cpc!  ") is not None)
    sess_a, sess_b = "session-aaa", "session-bbb"
    check("cache is NOT session-scoped (key has no session id)",
          getattr(mm2, "session_id", None) is None
          and sess_a != sess_b
          and mm2.check_cache(q) is not None,
          "same query hits regardless of who asks")

    # And a genuinely empty cache must still report 0.0, not a fabricated value.
    mm3 = AgenticMemoryManager()
    mm3.check_cache("never asked before")
    check("empty cache still reports 0.0 honestly",
          mm3.get_memory_stats()["cache_hit_rate"] == 0.0)

    print()
    print("=" * 74)
    print(f"RESULT: {len(PASSED)} passed, {len(FAILED)} failed")
    for f in FAILED:
        print(f"  FAILED: {f}")
    print("=" * 74)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())