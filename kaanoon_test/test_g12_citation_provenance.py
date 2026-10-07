"""G12 - citation provenance: never present an unsourced statute as sourced.

THE MEASURED FAILURE THIS FIXES
-------------------------------
Benchmark hfl_03 (Domestic Violence) retrieved context containing only
section 125. The answer then cited sections 12, 18, 19, 20, 22, 503 - none
of which were in the retrieved context. The harness flagged all five as
fabrications; groundedness scored 0.0 and answer_support 0.1348.

The model knew the governing law from training data, filled the gaps, and
presented the result as sourced. For a lawyer that is worse than refusing:
a bare "Section 498A" that the index never contained is a false citation.

WHAT THIS GATE DOES
-------------------
After the answer is produced, every section citation is classified as grounded
(supported by retrieved context) or ungrounded (not in context). Ungrounded
ones are annotated or stripped per CITATION_PROVENANCE_MODE. Legitimate
answers that cite what they were actually given are NOT penalised.

TWO REAL BUGS FOUND WHILE VERIFYING (kept here so they cannot regress)
--------------------------------------------------------------------
1. _extract_cited_sections() built its `found` list but never returned it, so
   every call returned None and the gate saw zero citations.
2. _collect_context_sections() assigned `body` only inside the dict branch, so
   a string doc (or a dict with no text key) raised UnboundLocalError. The
   caller swallows exceptions as "degraded -> do not block", which SILENTLY
   disabled the entire gate while reporting success.
Both made the gate a no-op that looked healthy.

Run:
    cd E:\\LAW-GPT_new\\azure_backend_stage
    E:\\LAW-GPT_new\\.venv\\Scripts\\python.exe kaanoon_test\\test_g12_citation_provenance.py
"""
import json
import logging
import sys
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


def bare():
    """Real class methods, no heavy __init__, no network."""
    o = object.__new__(uar.UnifiedAdvancedRAG)
    o.min_grounded_sources = 1
    o.min_trusted_sources = 1
    o.require_grounded_answers = True
    o.strict_retrieval_required = False
    o.pageindex_retriever = None
    o.store = None
    o.statute_store = None
    o.retriever = None
    o._retrieval_health_cache = None
    o._retrieval_health = {"has_any_retrieval": False,
                           "has_operational_retrieval": False}
    o.citation_provenance_required = True
    o.citation_provenance_mode = "annotate"
    # Set by __init__ in production (MIN_GROUNDED_CITATION_RATIO, default 0.5).
    # The gate reads it, so a stub that omits it makes the whole gate no-op.
    o.min_grounded_citation_ratio = 0.5
    return o


CONTEXT = [{
    "title": "HAMA s.6",
    "content": ("Section 6 of the Hindu Adoptions and Maintenance Act, 1956: "
                "a wife is entitled to maintenance from her husband."),
    "url": "https://indiacode.nic.in/hama",
    "source": "indiacode.nic.in",
    "trusted_source": True,
    "source_tier": "trusted",
    "metadata": {"source": "indiacode.nic.in", "trusted_source": True,
                 "url": "https://indiacode.nic.in/hama",
                 "section_number": "6"},
}]

# The exact fabrication shape measured on hfl_03.
FABRICATED = ("Section 2 PWDVA applies. Section 19 PWDVA allows maintenance. "
              "Section 125 PWDVA is the court. Section 406 IPC and "
              "Section 498A IPC also apply.")


def main():
    print("=" * 74)
    print("G12 - citation provenance enforcement")
    print("=" * 74)

    print("[1] the two no-op bugs are gone (gate actually runs)")
    o = bare()
    got = o._extract_cited_sections("Section 6 HAMA and Section 498A IPC apply.")
    check("_extract_cited_sections returns a list, not None",
          isinstance(got, list), f"got {type(got).__name__}")
    check("it actually finds both sections",
          isinstance(got, list) and len(got) == 2,
          f"found {[g['key'] for g in (got or [])]}")
    ctx_sections = o._collect_context_sections(CONTEXT)
    check("_collect_context_sections works on a dict doc",
          isinstance(ctx_sections, dict) and "6" in ctx_sections,
          f"keys={sorted(ctx_sections)}")
    o2 = bare()
    check("_collect_context_sections survives a bare string doc",
          isinstance(o2._collect_context_sections(["Section 9 of some Act"]), dict))
    o3 = bare()
    check("_collect_context_sections survives a doc with no text",
          isinstance(o3._collect_context_sections([{"title": "x"}]), dict))
    print()

    print("[2] a citation PRESENT in context stays grounded")
    o = bare()
    r = o._evaluate_citation_provenance(
        "Under Section 6 of the HAMA, maintenance is payable.", CONTEXT)
    check("detected the citation", r["citations_detected"] == 1,
          str(r["citations_detected"]))
    check("classified it GROUNDED", r["citations_grounded"] == 1)
    check("zero ungrounded", r["citations_ungrounded"] == 0)
    check("provenance_ok is True", r["provenance_ok"] is True)
    check("grounded_ratio is 1.0", r["grounded_ratio"] == 1.0)
    print()

    print("[3] the REAL hfl_03 fabrication is caught")
    o = bare()
    r = o._evaluate_citation_provenance(FABRICATED, CONTEXT)
    print(f"         detected={r['citations_detected']} "
          f"grounded={r['citations_grounded']} "
          f"ungrounded={r['citations_ungrounded']}")
    print(f"         ungrounded_citations={r['ungrounded_citations']}")
    check("detected all 5 fabricated sections", r["citations_detected"] == 5,
          str(r["citations_detected"]))
    check("grounded ZERO of them", r["citations_grounded"] == 0)
    check("flagged 498A as ungrounded", "498A" in r["ungrounded_citations"])
    check("flagged 406 as ungrounded", "406" in r["ungrounded_citations"])
    check("provenance_ok is False", r["provenance_ok"] is False)
    check("grounded_ratio is 0.0", r["grounded_ratio"] == 0.0)
    print()

    print("[4] MIXED answer is partial, never counted as fully grounded")
    o = bare()
    r = o._evaluate_citation_provenance(
        "Section 6 HAMA applies, and also Section 498A IPC.", CONTEXT)
    check("grounded==1", r["citations_grounded"] == 1, str(r))
    check("ungrounded==1", r["citations_ungrounded"] == 1, str(r))
    check("provenance_ok is False for a mixed answer",
          r["provenance_ok"] is False,
          "a half-fabricated answer must not pass")
    check("ratio reflects the partial state", r["grounded_ratio"] == 0.5)
    print()

    print("[5] OVER-BLOCKING GUARD: a fully grounded answer is untouched")
    o = bare()
    good = "Under Section 6 of the HAMA, a wife is entitled to maintenance."
    res = {"answer": good, "source_documents": CONTEXT,
           "metadata": {"strategy": "synthesis"}}
    out = o._enforce_grounding_policy(
        user_query="maintenance?", session_id="s", category="family",
        result=res, skip_fast_paths=True)
    check("answer text was NOT altered", out["answer"] == good,
          repr(out["answer"][:70]))
    check("grounded_answer is True", out["metadata"].get("grounded_answer") is True)
    print()

    print("[6] the fabricated answer IS altered / flagged")
    o = bare()
    res = {"answer": FABRICATED, "source_documents": CONTEXT,
           "metadata": {"strategy": "synthesis"}}
    out = o._enforce_grounding_policy(
        user_query="domestic violence?", session_id="s", category="criminal",
        result=res, skip_fast_paths=True)
    md = out["metadata"]
    prov = md.get("citation_provenance") or {}
    check("metadata carries a provenance report",
          bool(prov), str(prov)[:80])
    check("the report shows ungrounded citations",
          prov.get("citations_ungrounded", 0) >= 5,
          f"ungrounded={prov.get('citations_ungrounded')}")
    check("grounded_answer is NOT True for a fabricated answer",
          md.get("grounded_answer") is not True,
          f"grounded_answer={md.get('grounded_answer')}")
    print(f"         answer head: {out['answer'][:150]!r}")
    print()

    print("[7] fail-safe: a broken doc must not 500")
    o = bare()
    class Boom:
        def get(self, *a, **k):
            raise RuntimeError("kaboom")
    r = o._evaluate_citation_provenance("Section 498A IPC applies.", [Boom()])
    check("hostile document degrades instead of raising",
          isinstance(r, dict) and "provenance_ok" in r,
          f"degraded={r.get('degraded')}")
    print()

    print("=" * 74)
    print(f"RESULT: {len(PASSED)} passed, {len(FAILED)} failed")
    for f in FAILED:
        print(f"  FAILED: {f}")
    print("=" * 74)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
# The exact fabrication shape measured on hfl_03.
FABRICATED = ("Section 2 PWDVA applies. Section 19 PWDVA allows maintenance. "
              "Section 125 PWDVA is the court. Section 406 IPC and "
              "Section 498A IPC also apply.")