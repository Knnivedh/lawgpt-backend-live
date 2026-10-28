"""Offline tests for the answer pipeline helpers: notes selection, polishing, citation-guard fixes."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from citation_guard import _generic_act_mentions, sanitize_citations
from legal_notes import STATUTE_NOTES, select_notes
from nodes.generator import polish_answer


def test_notes_are_selected_by_topic():
    adoption = select_notes("I want to adopt my wife's son from her first marriage")
    assert "Adoption by Hindus" in adoption and "Muslim law" not in adoption
    muslim = select_notes("my husband sent talaq on WhatsApp")
    assert "Muslim Women (Protection of Rights on Marriage) Act 2019" in muslim
    # the core block is always there
    for text in (adoption, muslim, select_notes("hello")):
        assert "Renamed laws" in text and "Rajnesh v. Neha" in text


def test_selected_notes_are_much_smaller_than_all_notes():
    assert len(select_notes("my father died without a will, ancestral house")) < len(STATUTE_NOTES) / 2


def test_polish_fixes_known_slips_and_cut_off_markup():
    out = polish_answer("Hire a solicitor. See Rajneesh v. Neha.\n\n- **")
    assert "solicitor" not in out and "Rajnesh v. Neha" in out
    assert not out.rstrip().endswith("**")
    assert polish_answer("**Heading**\nText with **bold").endswith("Text with")


def test_guard_does_not_treat_while_the_act_as_a_statute():
    assert _generic_act_mentions("While the Act does not prescribe a formula.", []) == []


def test_guard_drops_the_whole_item_when_its_opening_sentence_is_unsupported():
    context = "Section 125 CrPC maintenance. Hindu Marriage Act 1955 s.24."
    answer = "1. Keep the messages.\n2. Seek relief under Section 999 of the Imaginary Code. Courts grant it often.\n3. File under HMA s.24."
    result = sanitize_citations(answer, context)
    assert "Courts grant it often" not in result.text
    assert "Keep the messages" in result.text and "HMA s.24" in result.text


def test_reasoning_leak_is_recognised_and_normal_answers_are_not():
    from llm_utils import looks_like_reasoning
    leaked = ("The user wants me to rewrite the DRAFT into a final answer for the client, following strict editing "
              "rules. I need to check the draft against the verified statute notes.")
    assert looks_like_reasoning(leaked)
    assert looks_like_reasoning("Let me analyze the draft against the sources.")
    assert not looks_like_reasoning("**Immediate steps**\n1. File an application before the Magistrate in Pune.")
    assert not looks_like_reasoning("You may ask the court to order maintenance from the date you file.")


def test_review_that_balloons_or_leaks_is_rejected():
    import pytest
    from nodes.generator import _require_sane_review, _require_substantial
    good = "**Steps**\n" + "Ask the Family Court for interim maintenance and file the disclosure affidavit. " * 12
    _require_sane_review(good, draft_words=len(good.split()))
    with pytest.raises(ValueError):
        _require_sane_review(good * 6, draft_words=80)          # far longer than the draft
    with pytest.raises(ValueError):
        _require_substantial("The user wants me to rewrite the DRAFT. " + good)
    with pytest.raises(ValueError):
        _require_substantial("too short")


def test_review_that_collapses_the_answer_is_rejected():
    import pytest
    from nodes.generator import _require_sane_review
    stub = "**File for child maintenance.** Under Section 144 BNSS a child is entitled to maintenance. " * 3
    with pytest.raises(ValueError, match="shrank"):
        _require_sane_review(stub, draft_words=520)
    # a modest tightening is fine
    tightened = "Ask the Family Court for maintenance and file the disclosure affidavit with proof of paternity. " * 25
    _require_sane_review(tightened, draft_words=len(tightened.split()) + 60)


def test_numbered_list_is_renumbered_after_an_item_is_removed():
    from citation_guard import renumber_lists
    text = "**Steps**\n1. Engage a lawyer.\n2. Prepare the statement.\n4. File the petition.\n5. Discuss options.\n\n**Next**\n1. Call.\n2. Wait."
    assert renumber_lists(text) == (
        "**Steps**\n1. Engage a lawyer.\n2. Prepare the statement.\n3. File the petition.\n4. Discuss options.\n\n**Next**\n1. Call.\n2. Wait."
    )
    already_fine = "1. a\n2. b\n3. c"
    assert renumber_lists(already_fine) == already_fine


def test_guard_output_keeps_list_numbers_consecutive():
    context = "Section 125 CrPC maintenance. Hindu Marriage Act 1955 s.24."
    answer = "1. Keep the messages.\n2. File under Section 999 of the Imaginary Code. It is quick.\n3. Apply under HMA s.24."
    result = sanitize_citations(answer, context)
    assert "2. Apply under HMA s.24." in result.text and "3." not in result.text


def test_numbered_list_restarts_at_one_when_its_first_item_was_removed():
    from citation_guard import renumber_lists
    nl = chr(10)
    text = nl.join(["**Procedure**", "", "2. The court hears evidence.", "3. A decree may follow."])
    assert renumber_lists(text) == nl.join(["**Procedure**", "", "1. The court hears evidence.", "2. A decree may follow."])
