"""
Unit & Integration tests for Laya System 1 Triage & Fast Gate Adapter.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add project root and kaanoon_test to path
CUR_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CUR_DIR.parent
if str(CUR_DIR) not in sys.path:
    sys.path.insert(0, str(CUR_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from system_adapters.laya_triage_adapter import (
    triage_query,
    build_retrieval_filter,
    VALID_DOMAINS,
    VALID_STATUTES,
    VALID_INTENTS,
)


def test_triage_hma_divorce():
    """Verify grounds for divorce under Hindu Marriage Act triages to hma and suggests Section 13."""
    q = "grounds for divorce under the Hindu Marriage Act"
    t0 = time.perf_counter()
    res = triage_query(q)
    latency_ms = (time.perf_counter() - t0) * 1000

    print(f"\n[TEST 1] Query: '{q}'")
    print(f"  Latency: {latency_ms:.3f}ms")
    print(f"  Domain: {res['domain']}")
    print(f"  Statute: {res['statute']}")
    print(f"  Intent: {res['intent']}")
    print(f"  Supported: {res['is_supported_statute']}")
    print(f"  Sections: {res['suggested_sections']}")
    print(f"  Confidence: {res['confidence']}")

    assert res["domain"] in VALID_DOMAINS, f"Invalid domain: {res['domain']}"
    assert res["statute"] in VALID_STATUTES, f"Invalid statute: {res['statute']}"
    assert res["intent"] in VALID_INTENTS, f"Invalid intent: {res['intent']}"

    assert res["domain"] == "family_law", f"Expected family_law, got {res['domain']}"
    assert res["statute"] == "hma", f"Expected hma, got {res['statute']}"
    assert res["intent"] == "divorce_grounds", f"Expected divorce_grounds, got {res['intent']}"
    assert any("13" in s for s in res["suggested_sections"]), (
        f"Expected Section 13 in suggested_sections: {res['suggested_sections']}"
    )
    assert res["is_supported_statute"] is True
    assert latency_ms < 25.0, f"Triage exceeded 25ms: {latency_ms:.2f}ms"
    print("  => PASSED!")


def test_triage_out_of_scope_early_exit():
    """Verify an out-of-scope query triages to unsupported with is_supported_statute False in <25ms."""
    queries = [
        "What is the penalty for speeding under California Vehicle Code 22350?",
        "How do I file for retirement benefits under US Social Security Act?",
        "What are GDPR requirements for data subject access requests in the EU?",
        "What is the penalty for speeding under the Motor Vehicles Act?",
    ]

    for q in queries:
        t0 = time.perf_counter()
        res = triage_query(q)
        latency_ms = (time.perf_counter() - t0) * 1000

        print(f"\n[TEST 2] OOS Query: '{q}'")
        print(f"  Latency: {latency_ms:.3f}ms")
        print(f"  Statute: {res['statute']}")
        print(f"  Supported: {res['is_supported_statute']}")
        print(f"  Confidence: {res['confidence']}")

        assert res["statute"] == "unsupported", f"Expected unsupported, got {res['statute']}"
        assert res["is_supported_statute"] is False, f"Expected False for OOS query"
        assert latency_ms < 25.0, f"Early-exit exceeded 25ms: {latency_ms:.2f}ms"
        print("  => PASSED!")


def test_triage_ni_act_section_138():
    """Verify Section 138 NI Act triages to ni_act and cheque_dishonour."""
    q = "Section 138 NI Act"
    t0 = time.perf_counter()
    res = triage_query(q)
    latency_ms = (time.perf_counter() - t0) * 1000

    print(f"\n[TEST 3] Query: '{q}'")
    print(f"  Latency: {latency_ms:.3f}ms")
    print(f"  Domain: {res['domain']}")
    print(f"  Statute: {res['statute']}")
    print(f"  Intent: {res['intent']}")
    print(f"  Supported: {res['is_supported_statute']}")
    print(f"  Sections: {res['suggested_sections']}")

    assert res["domain"] == "commercial_law", f"Expected commercial_law, got {res['domain']}"
    assert res["statute"] == "ni_act", f"Expected ni_act, got {res['statute']}"
    assert res["is_supported_statute"] is True
    assert any("138" in s for s in res["suggested_sections"]), (
        f"Expected Section 138 in suggested_sections: {res['suggested_sections']}"
    )
    assert latency_ms < 25.0, f"Triage exceeded 25ms: {latency_ms:.2f}ms"
    print("  => PASSED!")


def test_retrieval_filter_builder():
    """Verify retrieval filter generation for BM25 narrowing."""
    triage = triage_query("Section 138 NI Act cheque dishonour")
    rf = build_retrieval_filter(triage)

    print(f"\n[TEST 4] Retrieval Filter for NI Act: {rf}")
    assert rf["enabled"] is True
    assert rf["statute"] == "ni_act"
    assert "negotiable instruments act" in rf["act_keywords"]
    assert any("138" in s for s in rf["suggested_sections"])
    print("  => PASSED!")


if __name__ == "__main__":
    test_triage_hma_divorce()
    test_triage_out_of_scope_early_exit()
    test_triage_ni_act_section_138()
    test_retrieval_filter_builder()
    print("\n==========================================")
    print("ALL LAYA TRIAGE ADAPTER TESTS PASSED (100%)")
    print("==========================================")
