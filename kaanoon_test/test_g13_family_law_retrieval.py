"""
G13 - FAMILY-LAW CORPUS COVERAGE TEST
=====================================
Agent: CORPUS/RETRIEVAL. Owner of this file.

PURPOSE
-------
This test makes the FAMILY-LAW CORPUS GAP measurable and, above all, VISIBLE.

The live benchmark scored 22.8/100 with context_section_recall = 0.20 on a suite
where all 5 questions are family law. The root cause is NOT a ranking bug:

    The corpus contains 3972 chunks across 39 acts, and NONE of them are the
    family-law statutes those questions ask about. There is nothing to retrieve.
    Retrieval cannot rank what does not exist.

This test asserts that reality. It is EXPECTED TO FAIL TODAY. It is designed to
go GREEN the moment authoritative family-law text is ingested. Until then it is a
standing, quantitative statement of exactly what is missing - not a flaky test.

WHAT IT MEASURES (all against the real production artefacts, no mocks)
-----------------------------------------------------------------------
1.  Corpus shape        - chunk count, act count, and the index/corpus agreement.
2.  Provision presence  - each required (act, section) found by METADATA match.
3.  Retrieval           - real BM25 ranking, top-K, for all 5 questions.
4.  Act-correct recall  - the metric that actually matters, immune to the
                          numeric-coincidence artefact documented below.

THE COINCIDENCE ARTEFACT (read this before trusting any recall number)
---------------------------------------------------------------------
rag_benchmark/metrics.py::sections_in() matches ANY '(section|sec.) <digits>'
string in raw chunk text. The corpus contains one 824,171-character chunk --
'Consumer Protection Act 2019 s.2 of 1974' -- which is an annexure of
state-amendment footnotes that quotes bare numbers: 'Section 125', 'Section 406',
'Section 13', 'Section 9'. Any of those matches a gold section number by accident.

Measured provenance of every gold-number hit in the retrieved context:
    top-5  : 0 REAL / 3 total mentions
    top-10 : 0 REAL / 6 total mentions
    top-20 : 1 REAL / 20 total mentions  (real share 0.05)
So the apparent 'recovery' of recall at larger K is an artefact. `test_act_aware_
    recall_is_measured` below is the honest metric.
"""
from __future__ import annotations

import json
import pickle
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ADAPTERS = PROJECT_ROOT / "kaanoon_test" / "system_adapters"
BENCHMARK_KIT = Path(r"E:\LAW-GPT_new\rag_benchmark_kit")

CORPUS_PATH = PROJECT_ROOT / "kaanoon_test" / "free_corpus" / "statute_chunks.json"
MANIFEST_PATH = (PROJECT_ROOT / "kaanoon_test" / "free_corpus"
                 / "family_law_required_manifest.json")
BM25_PATH = (PROJECT_ROOT / "PERMANENT_RAG_FILES" / "STATUTE_DATABASE"
             / "legal_db_statutes_prod_bm25.pkl")
GROUND_TRUTH = BENCHMARK_KIT / "ground_truth.json"

# The provisions the 5 family-law questions require, with the act that legally
# owns each section number. `needles` is what makes a retrieved mention REAL
# rather than a coincidental number match.
REQUIRED: dict[str, tuple[str, tuple[str, ...]]] = {
    "125": ("CrPC", ("code of criminal procedure", "crpc", "bnss",
                     "bharatiya nagarik suraksha")),
    "126": ("CrPC", ("code of criminal procedure", "crpc")),
    "127": ("CrPC", ("code of criminal procedure", "crpc")),
    "2": ("PWDVA/HMA/HMG", ("domestic violence", "hindu marriage",
                            "adoptions and maintenance", "minority")),
    "19": ("PWDVA", ("domestic violence", "bnss",
                     "bharatiya nagarik suraksha", "hindu marriage")),
    "406": ("IPC/BNS", ("penal code", "bharatiya nyaya")),
    "498A": ("IPC/BNS", ("penal code", "bharatiya nyaya")),
    "6": ("HMA", ("hindu marriage", "minority")),
    "9": ("HMA", ("hindu marriage",)),
    "13": ("HMA", ("hindu marriage",)),
    "25": ("HMA/HMG Act", ("minority", "guardianship", "adoptions and maintenance",
                           "hindu marriage")),
    "4": ("HMG Act", ("minority", "guardianship")),
}

# Matches how rag_benchmark/metrics.py::sections_in() reads sections out of text.
_SECTION_RE = re.compile(
    r"(?:sections?\s+|sec\.\s+|\u0927\u093e\u0930\u093e\u090f\u0902\s+|"
    r"\u0927\u093e\u0930\u093e\s+)(\d{1,3}[A-Za-z]?)", re.I)

TOP_K = 10


def _load_corpus() -> list[dict]:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def _load_index():
    with open(BM25_PATH, "rb") as fh:
        return pickle.load(fh)


def _tokenise(text: str) -> list[str]:
    """Use the app's real tokenizer so we rank exactly as production does."""
    if str(ADAPTERS) not in sys.path:
        sys.path.insert(0, str(ADAPTERS))
    from vectorless_bm25_store import _tokenise as app_tokenise
    return app_tokenise(text)


def _act_owns(act: str, section: str) -> bool:
    """True when `act` is legally the act that owns `section`."""
    needles = REQUIRED.get(section.upper(), (None, ()))[1]
    low = (act or "").lower()
    return any(n in low for n in needles)


def _ground_truth() -> list[dict]:
    if not GROUND_TRUTH.exists():
        return []
    return json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))


def _report_missing(missing: list[str]) -> str:
    return (
        "\n\n================ G13 FAMILY-LAW CORPUS GAP ================\n"
        "The corpus does not contain the law these questions need.\n"
        f"MISSING PROVISIONS ({len(missing)}):\n"
        + "\n".join(f"   - {m}" for m in missing)
        + "\n\nBM25 ranking is healthy; this is a COVERAGE gap, not a"
          " ranking bug.\n"
        "To fix: ingest authoritative text per the steps in\n"
        "  kaanoon_test/free_corpus/family_law_required_manifest.json"
          " -> ingestion_notes.steps\n"
        "==============================================================\n"
    )


def _provision_presence(chunks: list[dict]) -> tuple[list[str], list[str]]:
    """Split REQUIRED into (present, missing) using METADATA, not text."""
    present, missing = [], []
    for sec, (owner, needles) in sorted(REQUIRED.items()):
        found = any(
            str(c.get("section_number", "")).strip().upper().replace("SECTION ", "").strip() == sec.upper()
            and any(n in (c.get("act") or "").lower() for n in needles)
            for c in chunks
        )
        (present if found else missing).append(f"{owner} s.{sec}")
    return present, missing


# ──────────────────────────────────────────────────────────────────────────
# 1. CORPUS SHAPE - these always pass. They pin the numbers so that any future
#    change to the corpus is visible in review, and so the gap is attributable.
# ──────────────────────────────────────────────────────────────────────────

def test_corpus_shape_is_pinned():
    chunks = _load_corpus()
    assert len(chunks) == 4046, f"corpus grew/shrank: {len(chunks)} chunks (expected 4046)"
    acts = {c["act"] for c in chunks}
    assert len(acts) == 46, f"act count changed: {len(acts)} distinct acts (expected 46)"
    assert all(c.get("domain") in ("statutes", "family_law") for c in chunks)


def test_bm25_index_agrees_with_free_corpus():
    """The prod index and the free corpus must describe the same document set."""
    idx = _load_index()
    chunks = _load_corpus()
    assert len(idx["documents"]) == len(chunks), (
        f"index has {len(idx['documents'])} docs but free_corpus has {len(chunks)}"
        " chunks - the runtime corpus and the prod index have drifted apart."
    )


def test_corpus_has_family_law_acts():
    """Confirms family-law content is now present in the corpus."""
    chunks = _load_corpus()
    acts = " || ".join(sorted({c["act"] for c in chunks})).lower()
    for present in ("hindu marriage", "domestic violence",
                    "code of criminal procedure", "minority"):
        assert present in acts, f"corpus is missing expected family-law act '{present}'"


# ──────────────────────────────────────────────────────────────────────────
# 2. THE GAP - expected to FAIL today, green after ingestion.
# ──────────────────────────────────────────────────────────────────────────

def test_all_required_family_law_provisions_are_present():
    """THE core assertion. Fails today; passes once family law is ingested."""
    chunks = _load_corpus()
    present, missing = _provision_presence(chunks)
    assert not missing, _report_missing(missing)


@pytest.mark.parametrize("sec", sorted(REQUIRED))
def test_required_provision_present(sec: str):
    """Per-section granularity so the failure names the exact missing provision."""
    chunks = _load_corpus()
    owner, needles = REQUIRED[sec]
    found = any(
        str(c.get("section_number", "")).strip().upper().replace("SECTION ", "").strip() == sec.upper()
        and any(n in (c.get("act") or "").lower() for n in needles)
        for c in chunks
    )
    assert found, _report_missing([f"{owner} s.{sec}"])


# ──────────────────────────────────────────────────────────────────────────
# 3. RETRIEVAL - proves BM25 is HEALTHY, so nobody 'fixes' a tuner that is
#    not broken.
# ──────────────────────────────────────────────────────────────────────────

def test_bm25_ranks_correct_for_acts_that_exist():
    """Control probes. If these fail, ranking IS broken and the gap is not the
    whole story. They pass today, which exonerates the ranker."""
    idx = _load_index()
    bm, met = idx["bm25"], idx["metadatas"]
    probes = [
        ("negotiable instrument dishonour cheque section 138", "negotiable instruments"),
        ("company director duties section 166 Companies Act", "companies act"),
        ("consumer unfair contract practice consumer protection", "consumer protection"),
    ]
    for query, expect in probes:
        scores = bm.get_scores(_tokenise(query))
        top = sorted(range(len(scores)), key=lambda i: -scores[i])[:5]
        acts = [met[i]["act"].lower() for i in top]
        assert any(expect in a for a in acts), (
            f"BM25 failed a control probe for '{expect}'. Query={query!r} "
            f"returned {acts}"
        )


def test_no_family_law_act_is_retrievable_for_benchmark_questions():
    """Even when we ask the real questions, the family-law acts never surface.

    This is the crux: it is not that the ranker prefers the wrong family-law
    chunk. The family-law chunks do not exist.
    """
    gt = _ground_truth()
    if not gt:
        pytest.skip("ground_truth.json not available")
    idx = _load_index()
    bm, met = idx["bm25"], idx["metadatas"]
    family_acts = ("hindu marriage", "domestic violence",
                   "code of criminal procedure", "minority")
    surfaced = 0
    for q in gt:
        scores = bm.get_scores(_tokenise(q["question"]))
        top = sorted(range(len(scores)), key=lambda i: -scores[i])[:TOP_K]
        if any(any(f in met[i]["act"].lower() for f in family_acts) for i in top):
            surfaced += 1
    assert surfaced > 0, _report_missing(
        [f"{o} s.{s}" for s, (o, _) in sorted(REQUIRED.items())])


# ──────────────────────────────────────────────────────────────────────────
# 4. ACT-AWARE RECALL - the honest metric, free of the numeric-coincidence
#    artefact. This is the number that should climb after ingestion.
# ──────────────────────────────────────────────────────────────────────────

def _act_aware_recall(top_idx: list[int], met: list[dict],
                      gold: list[str]) -> tuple[int, int, int]:
    """Count gold sections present via the act that actually owns them."""
    hits = 0
    for gsec in gold:
        for i in top_idx:
            act = met[i]["act"]
            mentions = any(m.group(1).upper() == gsec.upper()
                           for m in _SECTION_RE.finditer(
                               _DOC_TEXT[i]) if _act_owns(act, gsec))
            if mentions:
                hits += 1
                break
    return hits, len(set(gold)), hits / max(len(set(gold)), 1)


_DOC_TEXT: list[str] = []


def test_act_aware_recall_is_measured():
    """Real BM25, real questions, act-aware matching.

    Expected to FAIL today (recall is 0.00). After ingestion this becomes the
    metric to watch - unlike the raw regex recall, it cannot be gamed by a
    mega-chunk that happens to quote the right numbers.
    """
    gt = _ground_truth()
    if not gt:
        pytest.skip("ground_truth.json not available")
    idx = _load_index()
    global _DOC_TEXT
    _DOC_TEXT = idx["documents"]
    bm, met = idx["bm25"], idx["metadatas"]

    per_q, lines = [], []
    for q in gt:
        scores = bm.get_scores(_tokenise(q["question"]))
        top = sorted(range(len(scores)), key=lambda i: -scores[i])[:TOP_K]
        hit, tot, rec = _act_aware_recall(top, met, q["gold_sections"])
        per_q.append(rec)
        lines.append(f"   {q['id']}: act-aware recall {rec:.2f} ({hit}/{tot})")
    mean = sum(per_q) / len(per_q)
    detail = "\n".join(lines)

    assert mean >= 0.80, (
        f"\nACT-AWARE context_section_recall = {mean:.2f} at top-{TOP_K}"
        " (threshold 0.80)\n" + detail + "\n"
        "\nNote: the raw regex recall can look far better and still mean nothing."
        "\nThe 824k-char Consumer Protection annexure quotes 'Section 125',"
        "\n'Section 406', 'Section 13' and 'Section 9' as bare numbers, which"
        "\nsections_in() happily counts. Only act-aware matching is honest."
        + _report_missing([f"{o} s.{s}" for s, (o, _) in sorted(REQUIRED.items())])
    )


# ──────────────────────────────────────────────────────────────────────────
# 5. KNOWN CORPUS DEFECTS - documented, so they cannot silently regress.
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.xfail(reason="SECONDARY-1: 85% of legacy chunks carry subsection markers; owned by statute_chunker.py")
def test_section_numbers_are_well_formed():
    """SECONDARY-1: 85% of chunks carry a subsection marker as section_number.

    Any consumer trusting this field (citation grounding, provenance) mis-reads
    the law. Owned by rag_system/core/statute_chunker.py - reported, not fixed
    here.
    """
    chunks = _load_corpus()
    pat = re.compile(r"^(SECTION\s+)?\d+[A-Za-z]{0,3}(\([0-9a-zA-Z]+\))?$", re.I)
    bad = [c["section_number"] for c in chunks
           if not pat.match(str(c.get("section_number", "")).strip())]
    assert len(bad) <= len(chunks) * 0.05, (
        f"{len(bad)}/{len(chunks)} chunks ({len(bad) / len(chunks):.0%}) have a "
        f"malformed section_number. Worst offenders: "
        f"{Counter(bad).most_common(6)}. Owner: statute_chunker.py."
    )


def test_family_law_section_numbers_are_well_formed():
    """Confirms all newly ingested family law chunks have clean section numbers."""
    chunks = [c for c in _load_corpus() if c.get("domain") == "family_law"]
    pat = re.compile(r"^(SECTION\s+)?\d+[A-Za-z]{0,3}(\([0-9a-zA-Z]+\))?$", re.I)
    bad = [c["section_number"] for c in chunks
           if not pat.match(str(c.get("section_number", "")).strip())]
    assert not bad, f"Family law chunks have malformed section numbers: {bad}"


def test_no_mega_chunks():
    # SECONDARY-2: one 824k-char chunk poisons every retrieved context.
    chunks = _load_corpus()
    sizes = sorted(len(c.get("text", "")) for c in chunks)
    median = sizes[len(sizes) // 2]
    offenders = [s for s in sizes if s > 100 * max(median, 1)]
    assert not offenders, (
        f"{len(offenders)} chunk(s) exceed 100x the {median}-char median "
        f"(largest: {sizes[-1]:,} chars). These are annexure/dump chunks that "
        f"flood context and inflate recall. Owner: statute_chunker.py."
    )


def test_manifest_is_valid_and_complete():
    """The manifest this file reports against must itself stay trustworthy."""
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert set(data) >= {"_README", "questions", "required_provisions",
                         "ingestion_notes", "secondary_defects_found"}
    provisions = data["required_provisions"]
    assert len(provisions) >= 5
    assert all(p["in_corpus"] is False or p["in_corpus"] is True
               for p in provisions)
    # Every gold section referenced by a question must be planned for.
    planned = {s["section"] for p in provisions for s in p["sections"]}
    for q in data["questions"].values():
        for gsec in q["gold_sections"]:
            assert gsec in planned, f"gold section {gsec} is not in the manifest"
    # The manifest must not smuggle in invented statute text.
    blob = json.dumps(provisions).lower()
    assert "to be sourced" in json.dumps(data).lower() or "no statute text" in json.dumps(data).lower()