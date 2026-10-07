"""Regression tests for the grounding trust gate.

Context
-------
`_is_trusted_source_doc` previously trusted nothing in the curated statute
corpus, so every statute question abstained with "insufficient trusted legal
sources" even when retrieval returned the exact correct provision. The fix
widens trust to documents that carry real statutory provenance
(`domain: "statutes"` + non-empty `act` + non-empty `section_number`).

The equally important half is what must STILL NOT be trusted: the earlier
TRUST FIX removed "statutes"/"legal database" as trust *labels* because
_format_sources() defaulted `source` to the literal "Legal Database", which
made every document pass. These tests pin that behaviour so the new branch
cannot silently reintroduce it.

Run: python -m pytest test_statute_trust_gate.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kaanoon_test.system_adapters.unified_advanced_rag import UnifiedAdvancedRAG


def _rag():
    """Build without touching the network or any real index."""
    return UnifiedAdvancedRAG.__new__(UnifiedAdvancedRAG)


def _statute_hit(act="Bharatiya Nyaya Sanhita 2023", section="319"):
    return {
        "id": "D8_9a0d334c_s319_0",
        "text": "Section 319 - Cheating by personation\n\n--- Section 319 ---",
        "source": "corpus",
        "metadata": {
            "domain": "statutes",
            "act": act,
            "section_number": section,
            "section_title": "Cheating by personation",
            "source_file": "Bharatiya_Nyaya_Sanhita_2023_repaired.json",
        },
    }


# --- the fix -------------------------------------------------------------

def test_statute_corpus_hit_is_trusted():
    assert _rag()._is_trusted_source_doc(_statute_hit()) is True


def test_trust_is_earned_from_provenance_not_the_source_label():
    """Same document, but the pipeline provenance stripped away.

    It must now FAIL: this is exactly the shape that the old TRUST FIX was
    defending against.
    """
    doc = _statute_hit()
    doc["metadata"].pop("domain")
    assert _rag()._is_trusted_source_doc(doc) is False


def test_partial_provenance_is_not_enough():
    for missing in ("act", "section_number"):
        doc = _statute_hit()
        doc["metadata"][missing] = ""
        assert _rag()._is_trusted_source_doc(doc) is False, missing


def test_empty_section_number_is_not_trusted():
    doc = _statute_hit()
    doc["metadata"]["section_number"] = ""
    assert _rag()._is_trusted_source_doc(doc) is False


# --- the original TRUST FIX must survive ----------------------------------

def test_generic_legal_database_label_is_not_trusted():
    """Regression guard for the original bug: a default label trusted everything."""
    doc = {"title": "x", "content": "y", "source": "Legal Database"}
    assert _rag()._is_trusted_source_doc(doc) is False


def test_bare_statutes_label_is_not_trusted():
    assert _rag()._is_trusted_source_doc({"source": "statutes", "text": "..."}) is False
    assert _rag()._is_trusted_source_doc({"source": "statute", "text": "..."}) is False


def test_unlabelled_corpus_doc_is_not_trusted():
    assert _rag()._is_trusted_source_doc({"source": "corpus", "text": "..."}) is False


def test_unknown_domain_with_act_is_not_trusted():
    doc = _statute_hit()
    doc["metadata"]["domain"] = "case_law"
    assert _rag()._is_trusted_source_doc(doc) is False


# --- pre-existing trust paths still work ---------------------------------

def test_explicit_trusted_flag_still_works():
    assert _rag()._is_trusted_source_doc({"trusted_source": True, "text": "..."}) is True


def test_source_tier_trusted_still_works():
    # NB: source_tier is read from `metadata`, not from the top level. That is
    # pre-existing behaviour and is deliberately not changed here.
    assert _rag()._is_trusted_source_doc(
        {"metadata": {"source_tier": "trusted"}, "text": "..."}) is True


def test_top_level_source_tier_is_not_read():
    """Pins the existing asymmetry so it is never 'fixed' by accident."""
    assert _rag()._is_trusted_source_doc(
        {"source_tier": "trusted", "text": "..."}) is False


def test_recognised_publisher_still_works():
    assert _rag()._is_trusted_source_doc({"source": "Indian Kanoon"}) is True


def test_government_domain_still_works():
    doc = {"url": "https://www.indiacode.nic.in/handle/123456789/17272"}
    assert _rag()._is_trusted_source_doc(doc) is True


def test_non_dict_is_not_trusted():
    assert _rag()._is_trusted_source_doc("not a dict") is False
    assert _rag()._is_trusted_source_doc(None) is False