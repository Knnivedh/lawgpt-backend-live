"""Tests for the G1 repeal policy registry.

Context
-------
The deployed index carries 1,207 records (12.65% of 9,541) that answer from
enactments repealed on 1 July 2024. These tests pin the three properties the
G1 brief demands:

  1. CrPC 1973 and the Indian Evidence Act 1872 ARE matched as repealed -
     by act key, by source filename, and by the human ``metadata.act`` label
     that corpus records actually carry.
  2. BNSS 2023 and BSA 2023 are NOT matched as repealed. They are the
     replacements; a policy that caught them would be deleting live law.
  3. The policy ESCALATES rather than purges when a replacement is missing.

Run: python -m pytest test_repeal_policy.py -v
"""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rag_system.core.repeal_policy import (  # noqa: E402
    COMMENCEMENT_DATE_NEW_CRIMINAL_LAWS,
    REPEALED_ACTS,
    assess_repeal_plan,
    describe_registry,
    filter_repealed_records,
    is_repealed,
    is_repealed_record,
    is_superseding_act,
    lookup,
    normalize_act_key,
    repeal_notice,
    repealed_act_keys,
    superseded_by,
)
from rag_system.core.statute_chunker import act_key_for_file  # noqa: E402

CRPC = "code_of_criminal_procedure_1973"
EVIDENCE = "indian_evidence_act_1872"

# The labels measured in the deployed corpus, verbatim.
CRPC_LABEL = "The Code of Criminal Procedure, 1973"
EVIDENCE_LABEL = "The Indian Evidence Act, 1872"


# --------------------------------------------------------------------------
# 1. The two repealed Acts must match.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("value", [
    CRPC,
    "Code_of_Criminal_Procedure_1973.json",
    "The_Code_of_Criminal_Procedure_1973.json",
    "code-of-criminal-procedure-1973.json",
    CRPC_LABEL,
    "Code of Criminal Procedure, 1973",
    "crpc_1973",
    "CRPC",
])
def test_crpc_1973_is_matched_as_repealed(value):
    assert is_repealed(value) is True


@pytest.mark.parametrize("value", [
    EVIDENCE,
    "The_Indian_Evidence_Act_1872.json",
    "indian_evidence_act_1872.json",
    EVIDENCE_LABEL,
    "Indian Evidence Act, 1872",
    "iea_1872",
])
def test_evidence_act_1872_is_matched_as_repealed(value):
    assert is_repealed(value) is True


def test_repealed_entries_carry_commencement_and_successor():
    crpc = lookup(CRPC_LABEL)
    evidence = lookup(EVIDENCE_LABEL)
    for entry in (crpc, evidence):
        assert entry is not None
        assert entry.commencement_date == date(2024, 7, 1)
        assert entry.commencement_date == COMMENCEMENT_DATE_NEW_CRIMINAL_LAWS
        assert entry.repealed_by_act_key
        assert entry.repeal_provision
    assert crpc.repealed_by_display == "Bharatiya Nagarik Suraksha Sanhita, 2023"
    assert evidence.repealed_by_display == "Bharatiya Sakshya Adhiniyam, 2023"
    # The IPC entry exists to show a repeal whose successor DID land (BNS).
    assert lookup("The Indian Penal Code, 1860") is not None


# --------------------------------------------------------------------------
# 2. BNSS and BSA must NOT match - they are the live replacements.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("value", [
    "Bharatiya Nagarik Suraksha Sanhita, 2023",
    "Bharatiya_Nagarik_Suraksha_Sanhita_2023.json",
    "bharatiya_nagarik_suraksha_sanhita_2023",
    "Nagarik Suraksha Sanhita 2023",
    "BNSS",
    "bnss_2023",
    "Bharatiya Sakshya Adhiniyam, 2023",
    "Bharatiya_Sakshya_Adhiniyam_2023.json",
    "bharatiya_sakshya_adhiniyam_2023",
    "Sakshya Adhiniyam 2023",
    "BSA",
    "bsa_2023",
])
def test_replacement_acts_are_not_repealed(value):
    assert is_repealed(value) is False


@pytest.mark.parametrize("value", [
    "Bharatiya Nagarik Suraksha Sanhita, 2023",
    "Bharatiya Sakshya Adhiniyam, 2023",
    "Bharatiya Nyaya Sanhita, 2023",
    "BNSS",
    "BSA",
    "BNS",
])
def test_replacement_acts_are_recognised_as_superseding(value):
    assert is_superseding_act(value) is True


def test_inforce_acts_are_not_superseding():
    assert is_superseding_act("The Companies Act, 2013") is False
    assert is_superseding_act("Arbitration and Conciliation Act, 1996") is False


def test_inverse_lookup_bnss_replaces_crpc():
    entry = superseded_by("Bharatiya Nagarik Suraksha Sanhita, 2023")
    assert entry is not None
    assert entry.act_key == CRPC
    bsa_entry = superseded_by("Bharatiya Sakshya Adhiniyam, 2023")
    assert bsa_entry is not None
    assert bsa_entry.act_key == EVIDENCE


# --------------------------------------------------------------------------
# 3. Normalisation must not merge distinct enactments.
# --------------------------------------------------------------------------
def test_normalisation_matches_ingestion_act_key():
    """The policy must agree with act_key_for_file, or it will miss files."""
    for filename, expected in [
        ("The_Indian_Evidence_Act_1872.json", EVIDENCE),
        ("The_Code_of_Criminal_Procedure_1973.json", CRPC),
        ("Indian_Penal_Code_1860.json", "indian_penal_code_1860"),
    ]:
        assert normalize_act_key(filename) == act_key_for_file(Path(filename))
        assert normalize_act_key(filename) == expected


def test_year_is_never_collapsed():
    """1956 vs 2013 - a repeal rule must never span two enactments."""
    assert normalize_act_key("The_Companies_Act_1956.json") != (
        normalize_act_key("The_Companies_Act_2013.json")
    )
    assert is_repealed("The Companies Act, 1956") is False


def test_normalisation_is_defensive():
    for bad in (None, "", "   "):
        assert normalize_act_key(bad) == ""
        assert is_repealed(bad) is False
    assert normalize_act_key(123) == "123"
    assert is_repealed(123) is False


# --------------------------------------------------------------------------
# 4. Time-awareness: before 1 Jul 2024 these Acts were good law.
# --------------------------------------------------------------------------
def test_crpc_was_in_force_before_commencement():
    assert is_repealed(CRPC_LABEL, as_of=date(2024, 6, 30)) is False
    assert is_repealed(CRPC_LABEL, as_of=date(2024, 7, 1)) is True
    assert lookup(CRPC_LABEL, as_of=date(2023, 1, 1)) is None


# --------------------------------------------------------------------------
# 5. The escalation guard - the heart of the brief.
# --------------------------------------------------------------------------
def test_missing_replacement_blocks_drop_and_escalates():
    """Present corpus: Evidence present, BSA absent -> BLOCK + escalate."""
    plan = assess_repeal_plan(
        ["The_Indian_Evidence_Act_1872.json", "The_Companies_Act_2013.json"],
        as_of=date(2024, 7, 1),
    )
    assert EVIDENCE in plan.blocked_missing_replacement
    assert plan.safe_to_drop == ()
    assert plan.requires_human_signoff is True
    reason = plan.blocked_reasons[EVIDENCE]
    assert "Bharatiya Sakshya Adhiniyam, 2023" in reason
    assert "NOT in the corpus" in reason


def test_present_replacement_unblocks_drop():
    """When BNSS and BSA arrive, the same call becomes a safe drop."""
    plan = assess_repeal_plan(
        [
            "The_Indian_Evidence_Act_1872.json",
            "Code_of_Criminal_Procedure_1973.json",
            "Bharatiya_Nagarik_Suraksha_Sanhita_2023.json",
            "Bharatiya_Sakshya_Adhiniyam_2023.json",
        ],
        as_of=date(2024, 7, 1),
    )
    assert set(plan.safe_to_drop) == {CRPC, EVIDENCE}
    assert plan.blocked_missing_replacement == ()
    assert plan.requires_human_signoff is False


def test_ipc_is_absent_already_and_needs_no_decision():
    plan = assess_repeal_plan(
        ["Bharatiya_Nyaya_Sanhita_2023.json"], as_of=date(2024, 7, 1)
    )
    assert "indian_penal_code_1860" in plan.absent_already
    assert plan.requires_human_signoff is False


def test_empty_corpus_reports_everything_absent():
    """Fail closed: with nothing available, nothing is droppable."""
    plan = assess_repeal_plan([], as_of=date(2024, 7, 1))
    assert plan.safe_to_drop == ()
    assert plan.absent_already == (CRPC, EVIDENCE, "indian_penal_code_1860")


# --------------------------------------------------------------------------
# 6. Record-level filtering - required because CrPC has no file of its own.
# --------------------------------------------------------------------------
def _rec(act):
    return {"id": "x", "text": "t", "metadata": {"act": act}}


def test_crpc_records_are_caught_by_act_label_not_filename():
    """CrPC chunks live inside Consumer_Protection_Act_2019.json."""
    crpc_rec = {
        "id": "c1",
        "metadata": {
            "act": CRPC_LABEL,
            "source_file": "Consumer_Protection_Act_2019.json",
        },
    }
    assert is_repealed_record(crpc_rec) is True
    keep, drop = filter_repealed_records(
        [_rec(CRPC_LABEL), _rec(EVIDENCE_LABEL), _rec("Consumer Protection Act 2019")]
    )
    assert len(drop) == 2
    assert len(keep) == 1


def test_filter_does_not_mutate_input():
    records = [_rec(CRPC_LABEL), _rec("The Companies Act, 2013")]
    snapshot = [dict(r) for r in records]
    keep, drop = filter_repealed_records(records)
    assert records == snapshot
    assert len(keep) + len(drop) == 2


# --------------------------------------------------------------------------
# 7. Retrieval-time notice (the zero-risk mitigation).
# --------------------------------------------------------------------------
def test_repeal_notice_names_replacement_and_date():
    notice = repeal_notice(CRPC_LABEL)
    assert notice is not None
    assert "2024-07-01" in notice
    assert "Bharatiya Nagarik Suraksha Sanhita, 2023" in notice
    assert repeal_notice("Bharatiya Nagarik Suraksha Sanhita, 2023") is None
    assert repeal_notice("The Companies Act, 2013") is None


def test_registry_is_documented_and_extensible():
    text = describe_registry()
    for entry in REPEALED_ACTS:
        assert entry.display_name in text
        assert entry.repealed_by_display in text
    assert CRPC in repealed_act_keys()
    assert len(REPEALED_ACTS) >= 3