"""Regression tests for act-level statute source selection (G2 dedupe).

Context
-------
`act_key_for_file()` deliberately did not strip leading articles, so
"Negotiable_Instruments_Act_1881.json" and "The_Negotiable_Instruments_Act_1881.json"
produced two different act keys, `select_statute_source_files()` never grouped
them, and BOTH copies of the same statute were ingested (measured 251 + 154 =
405 records, 4.2% of the deployed index, 148/255 sections duplicated) so each
competed against its own twin in RRF fusion.

The fix normalises leading articles and punctuation away. The equally important
half is what must STILL NOT merge: the year is the token that distinguishes
repeal/replace enactments of the same short title, so these tests pin that
Companies 1956 vs 2013 and CPA 2019 vs CPA 1986 stay distinct, and that the
Task 6 repair-variant collapse is not regressed.

Run: python -m pytest test_act_key_dedupe.py -v
"""
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rag_system.core.statute_chunker import (  # noqa: E402
    act_key_for_file,
    is_junk_statute_file,
    select_statute_source_files,
)


# --------------------------------------------------------------------------
# The reported defect: one statute, two scraped filenames, must collide.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("formal_title", [
    "The_Negotiable_Instruments_Act_1881.json",
    "the_negotiable_instruments_act_1881.json",
    "The-Negotiable-Instruments-Act-1881.json",
])
def test_negotiable_instruments_act_variants_share_one_key(formal_title):
    """G2: the 1881 NI Act scraped under both titles is ONE act."""
    short = act_key_for_file(Path("Negotiable_Instruments_Act_1881.json"))
    assert short == "negotiable_instruments_act_1881"
    assert act_key_for_file(Path(formal_title)) == short


def test_negotiable_instruments_variants_collide_in_selection(tmp_path):
    """End-to-end: selection must drop the duplicate NI Act variant."""
    (tmp_path / "Negotiable_Instruments_Act_1881.json").write_text("[]")
    (tmp_path / "The_Negotiable_Instruments_Act_1881.json").write_text("[]")

    selected = select_statute_source_files(tmp_path)
    assert len(selected) == 1
    # Same statute: prefer the canonical short-title filename.
    assert selected[0].name == "Negotiable_Instruments_Act_1881.json"


# --------------------------------------------------------------------------
# Different enactments of a similar title must NOT merge.
# --------------------------------------------------------------------------
def test_companies_act_1956_and_2013_stay_distinct():
    """The year distinguishes a repealed Act from its replacement."""
    assert (act_key_for_file(Path("The_Companies_Act_1956.json"))
            != act_key_for_file(Path("The_Companies_Act_2013.json")))
    # And the article is still stripped from both.
    assert act_key_for_file(Path("The_Companies_Act_1956.json")) == "companies_act_1956"


def test_consumer_protection_act_2019_and_1986_stay_distinct():
    """Different years AND different articles => different keys."""
    assert (act_key_for_file(Path("Consumer_Protection_Act_2019.json"))
            != act_key_for_file(Path("The_Consumer_Protection_Act_1986.json")))
    assert act_key_for_file(Path("Consumer_Protection_Act_2019.json")) == "consumer_protection_act_2019"


def test_indian_vs_bare_partnership_act_stay_distinct():
    """Stripping 'The' must not collapse a qualifier that carries identity."""
    assert (act_key_for_file(Path("Indian_Partnership_Act_1932.json"))
            != act_key_for_file(Path("Partnership_Act_1932.json")))


# --------------------------------------------------------------------------
# Task 6 fix must not regress.
# --------------------------------------------------------------------------
def test_bharatiya_nyaya_sanhita_repair_variants_still_collapse():
    """The BNS + _repaired + .REPAIRED trio is still ONE act."""
    keys = {
        act_key_for_file(Path(n)) for n in (
            "Bharatiya_Nyaya_Sanhita_2023.json",
            "Bharatiya_Nyaya_Sanhita_2023_repaired.json",
            "Bharatiya_Nyaya_Sanhita_2023.REPAIRED.json",
        )
    }
    assert keys == {"bharatiya_nyaya_sanhita_2023"}


def test_bns_repair_variants_collapse_with_article_and_punctuation():
    """Article stripping composes with, and does not break, repair stripping."""
    for n in (
        "The_Bharatiya_Nyaya_Sanhita_2023.json",
        "The_Bharatiya_Nyaya_Sanhita_2023_repaired.json",
        "The-Bharatiya-Nyaya-Sanhita-2023.REPAIRED.json",
    ):
        assert act_key_for_file(Path(n)) == "bharatiya_nyaya_sanhita_2023"


def test_junk_files_are_still_never_selected(tmp_path):
    """Junk filtering (Task 6) is unaffected by the article-stripping change."""
    (tmp_path / "Negotiable_Instruments_Act_1881.json").write_text("[]")
    (tmp_path / "Bharatiya_Nyaya_Sanhita_2023.backup_20261003_195801.json").write_text("[]")
    (tmp_path / "summary.json").write_text("[]")

    assert is_junk_statute_file(tmp_path / "summary.json")
    assert [p.name for p in select_statute_source_files(tmp_path)] == [
        "Negotiable_Instruments_Act_1881.json"
    ]


# --------------------------------------------------------------------------
# Degenerate inputs must not produce an empty key.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name,expected", [
    ("The.json", "the"),
    ("A.json", "a"),
    ("An.json", "an"),
])
def test_bare_article_filename_keeps_nonempty_key(name, expected):
    """The last remaining token is never stripped away to ''."""
    assert act_key_for_file(Path(name)) == expected
