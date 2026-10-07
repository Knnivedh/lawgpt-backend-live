"""
Repeal policy registry for Indian statutory law (G1 - purge repealed law).
=================================================================

WHY THIS EXISTS
---------------
The deployed statute index carries enactments that are no longer law. The
Code of Criminal Procedure, 1973 and the Indian Evidence Act, 1872 were both
repealed with effect from 1 July 2024 by the Bharatiya Nagarik Suraksha
Sanhita, 2023 (BNSS) and the Bharatiya Sakshya Adhiniyam, 2023 (BSA). Measured
on the deployed corpus `records_v4.jsonl` (9,541 records):

    1,017  'The Code of Criminal Procedure, 1973'
      190  'The Indian Evidence Act, 1872'
    -----
    1,207  = 12.65% of the index answers from repealed law

The three "new criminal laws" received Presidential assent on 24 April 2023
(Act 45, 46 and 47 of 2023) and all three were brought into force together on
1 July 2024 by a single notification, S.O. 850(E) dated 24 March 2024.

An audit of E:\\LAW-GPT_new\\BACKUP_DATA (107,780 files walked) found that
NEITHER BNSS NOR BSA EXISTS as a source document anywhere - not under any
filename, not as a `.bak` / `.backup_*` / `summary.json` variant, and not as
embedded text. The corpus already contains the third of the trio, BNS 2023
(395 records). So procedure law and evidence law have NO in-force source at
all. See A1_corpus_repeal_REPORT.md.

DESIGN
------
This module is deliberately a REGISTRY, not a branch in the ingestion code. It
carries no filesystem access and no I/O, so it can be imported by the chunker,
by the retrieval layer, by the answer formatter, and by tests without side
effects or import cycles. Callers ask questions; this module answers them.

Two matching surfaces, because repeal has to be caught at two different layers:

  1. FILE level  - `select_statute_source_files()` chooses source JSONs. There
     the identity is `act_key_for_file()`, e.g. `indian_evidence_act_1872`.
  2. RECORD level - a chunk carries `metadata.act`, a human label such as
     'The Code of Criminal Procedure, 1973'.

Both collapse to the same normalised token sequence via
:func:`normalize_act_key`, which mirrors the normalisation already used by
``rag_system.core.statute_chunker.act_key_for_file`` (lowercase, punctuation to
underscores, leading articles dropped, YEAR PRESERVED). Preserving the year is
the safety property: `companies_act_1956` can never collapse into
`companies_act_2013`, so a repeal entry can never accidentally swallow the
replacement that supersedes it.

THE CRITICAL CONSTRAINT ON USING THIS MODULE
-------------------------------------------
Removing a repealed act is only safe when its replacement is already in the
index. :func:`assess_repeal_plan` exists for exactly this: it is handed the set
of act keys that are actually available and it REFUSES to classify an act as
safe-to-drop while its superseding Act is missing. With the present corpus it
reports CrPC 1973 and the Evidence Act 1872 as BLOCKED, not droppable. Nothing
here deletes anything; removing a corpus is a legal decision, not a code path.

Extending the registry: append one :class:`RepealedAct` to :data:`REPEALED_ACTS`
and to the matching new-code entry. No conditional logic needs editing anywhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "RepealedAct",
    "RepealPlan",
    "REPEALED_ACTS",
    "SUPERSEDING_ACT_KEYS",
    "COMMENCEMENT_DATE_NEW_CRIMINAL_LAWS",
    "COMMENCEMENT_NOTIFICATION",
    "ASSENT_DATE_2023",
    "normalize_act_key",
    "lookup",
    "is_repealed",
    "is_superseding_act",
    "is_repealed_record",
    "superseded_by",
    "repealed_act_keys",
    "superseding_act_keys",
    "assess_repeal_plan",
    "filter_repealed_records",
    "repeal_notice",
    "describe_registry",
]

# ---------------------------------------------------------------------------
# Documented legal constants
# ---------------------------------------------------------------------------
#: All three new criminal laws commenced on this single date.
COMMENCEMENT_DATE_NEW_CRIMINAL_LAWS = date(2024, 7, 1)

#: S.O. 850(E) dated 24 March 2024 - the notification that brought Act 45, 46
#: and 47 of 2023 into force on 1 July 2024.
COMMENCEMENT_NOTIFICATION = "S.O. 850(E) dated 24 March 2024"

#: Date of Presidential assent to Act 45, 46 and 47 of 2023.
ASSENT_DATE_2023 = date(2023, 4, 24)

# Leading articles carry no statutory identity and are stripped, matching
# statute_chunker._LEADING_ACT_ARTICLES.
_LEADING_ACT_ARTICLES = frozenset({"the", "a", "an"})

# Trailing repair decoration stripped when deriving a key from a filename,
# matching statute_chunker._ACT_KEY_DECORATION.
_ACT_KEY_DECORATION = re.compile(r"[._-]?repaired$", re.IGNORECASE)


def normalize_act_key(value: Any) -> str:
    """Reduce an act name, act label or filename to its identity token sequence.

    Mirrors ``statute_chunker.act_key_for_file`` so that a key derived from a
    filename and a key derived from a human label meet on one string:

        'The_Indian_Evidence_Act_1872.json'  -> indian_evidence_act_1872
        'The Indian Evidence Act, 1872'      -> indian_evidence_act_1872
        'Code of Criminal Procedure 1973'    -> code_of_criminal_procedure_1973
        'The Code of Criminal Procedure, 1973'-> code_of_criminal_procedure_1973

    The YEAR is never altered, which is what keeps a repealed enactment and its
    replacement distinct.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    # Accept a Path/filename: reduce to its stem first.
    stem = re.sub(r"\.json$", "", text, flags=re.IGNORECASE)
    stem = _ACT_KEY_DECORATION.sub("", stem)
    key = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
    tokens = key.split("_")
    # Never strip the final token, so a bare 'The' keeps the key 'the'.
    while len(tokens) > 1 and tokens[0] in _LEADING_ACT_ARTICLES:
        tokens.pop(0)
    return "_".join(tokens)


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RepealedAct:
    """One repealed enactment and the Act that superseded it.

    Attributes:
        act_key: Canonical normalised key (see :func:`normalize_act_key`).
        display_name: Human title as it appears in citations.
        year: Year of enactment. Discriminating token, never altered.
        aliases: Extra normalised spellings seen in the wild.
        repealed_by_act_key: Normalised key of the superseding Act.
        repealed_by_display: Title of the superseding Act.
        repeal_provision: The repealing provision inside the new Act.
        repeal_provision_number: Section number of that provision.
        commencement_date: Date the repeal took effect.
        commencement_basis: Gazette notification for that date.
        consequence: What the corpus loses if this act is removed.
        partial_repeal_note: Earlier piecemeal repeal history, if any.
    """

    act_key: str
    display_name: str
    year: int
    aliases: frozenset[str]
    repealed_by_act_key: str
    repealed_by_display: str
    repeal_provision: str
    repeal_provision_number: str
    commencement_date: date
    commencement_basis: str
    consequence: str
    partial_repeal_note: str = ""

    @property
    def is_repealed_from(self) -> date:
        """Date the repeal took effect (alias for readability)."""
        return self.commencement_date

    def in_force_as_of(self, as_of: date | None = None) -> bool:
        """False once the repeal has commenced.

        Before 1 July 2024 these enactments were perfectly good law, so the
        policy is time-aware rather than a flat 'repealed' flag.
        """
        return (as_of or date.today()) < self.commencement_date

    def supersedes_key(self) -> str:
        """Normalised key of the Act that replaced this one."""
        return self.repealed_by_act_key

    def aliases_with_key(self) -> frozenset[str]:
        """Canonical key plus every alias."""
        return frozenset({self.act_key}) | self.aliases


#: Registry of enactments that are no longer law. DATA, NOT CODE: adding an
#: entry here is the only edit required to extend the policy.
REPEALED_ACTS: tuple[RepealedAct, ...] = (
    RepealedAct(
        act_key="code_of_criminal_procedure_1973",
        display_name="The Code of Criminal Procedure, 1973",
        year=1973,
        aliases=frozenset(
            {
                "code_of_criminal_procedure_1973",
                "criminal_procedure_code_1973",
                "crpc_1973",
                "crpc",
            }
        ),
        repealed_by_act_key="bharatiya_nagarik_suraksha_sanhita_2023",
        repealed_by_display="Bharatiya Nagarik Suraksha Sanhita, 2023",
        repeal_provision=(
            "Section 531(2)(a) of the Bharatiya Nagarik Suraksha Sanhita, 2023"
        ),
        repeal_provision_number="531(2)(a)",
        commencement_date=COMMENCEMENT_DATE_NEW_CRIMINAL_LAWS,
        commencement_basis=COMMENCEMENT_NOTIFICATION,
        consequence=(
            "Removes the corpus's ONLY procedural law - arrest, investigation, "
            "bail, framing of charges, trial and appeal procedure. No successor "
            "source exists in this corpus."
        ),
        partial_repeal_note=(
            "The 1973 Act had already been amended and partly repealed "
            "piecemeal before 2024 (e.g. by Act 49 of 1974, Act 5 of 2009 and "
            "the Repealing and Amending Act, 2015), so the text held here is "
            "stale independently of the 2024 repeal."
        ),
    ),
    RepealedAct(
        act_key="indian_evidence_act_1872",
        display_name="The Indian Evidence Act, 1872",
        year=1872,
        aliases=frozenset(
            {
                "indian_evidence_act_1872",
                "evidence_act_1872",
                "iea_1872",
                "indian_evidence_act",
            }
        ),
        repealed_by_act_key="bharatiya_sakshya_adhiniyam_2023",
        repealed_by_display="Bharatiya Sakshya Adhiniyam, 2023",
        repeal_provision=(
            "Section 170 of the Bharatiya Sakshya Adhiniyam, 2023"
        ),
        repeal_provision_number="170",
        commencement_date=COMMENCEMENT_DATE_NEW_CRIMINAL_LAWS,
        commencement_basis=COMMENCEMENT_NOTIFICATION,
        consequence=(
            "Removes the corpus's ONLY evidence law - examination, admission, "
            "confession, expert opinion, hearsay and the burden of proof. No "
            "successor source exists in this corpus."
        ),
        partial_repeal_note=(
            "Several provisions had been repealed earlier, including by Act 11 "
            "of 1889, the Indian Evidence (Amendment) Act, 1972 and the Repealing "
            "and Amending Act, 2015."
        ),
    ),
    RepealedAct(
        act_key="indian_penal_code_1860",
        display_name="The Indian Penal Code, 1860",
        year=1860,
        aliases=frozenset(
            {
                "indian_penal_code_1860",
                "penal_code_1860",
                "ipc_1860",
                "ipc",
            }
        ),
        repealed_by_act_key="bharatiya_nyaya_sanhita_2023",
        repealed_by_display="Bharatiya Nyaya Sanhita, 2023",
        repeal_provision=(
            "Section 358 of the Bharatiya Nyaya Sanhita, 2023"
        ),
        repeal_provision_number="358",
        commencement_date=COMMENCEMENT_DATE_NEW_CRIMINAL_LAWS,
        commencement_basis=COMMENCEMENT_NOTIFICATION,
        consequence=(
            "Listed for completeness: the IPC is NOT present in this corpus, so "
            "removing it costs nothing. It is recorded because BNS 2023 IS "
            "present (395 records), which proves the registry correctly "
            "distinguishes an act whose successor landed from two whose "
            "successors did not."
        ),
        partial_repeal_note=(
            "Extensively amended before repeal; the 2023 repeal was total."
        ),
    ),
)

def _build_index(acts: Sequence[RepealedAct]) -> dict[str, RepealedAct]:
    """Map every normalised alias to its registry entry.

    First entry wins on collision so registry order stays authoritative.
    """
    index: dict[str, RepealedAct] = {}
    for entry in acts:
        for key in entry.aliases_with_key():
            index.setdefault(key, entry)
    return index


_REPEALED_INDEX: dict[str, RepealedAct] = _build_index(REPEALED_ACTS)

#: Normalised keys of every Act that supersedes a registry entry.
SUPERSEDING_ACT_KEYS: frozenset[str] = frozenset(
    entry.repealed_by_act_key for entry in REPEALED_ACTS
)

# Extra spellings that also denote an in-force superseding Act. Registered as
# DATA so `is_superseding_act` never needs a hardcoded branch.
_SUPERSEDING_ALIASES: dict[str, str] = {
    "bharatiya_nagarik_suraksha_sanhita_2023": "BNSS 2023",
    "nagarik_suraksha_sanhita_2023": "BNSS 2023",
    "bharatiya_nagarik_suraksha_sanhita": "BNSS 2023",
    "nagarik_suraksha_sanhita": "BNSS 2023",
    "bnss_2023": "BNSS 2023",
    "bnss": "BNSS 2023",
    "bharatiya_sakshya_adhiniyam_2023": "BSA 2023",
    "sakshya_adhiniyam_2023": "BSA 2023",
    "bharatiya_sakshya_adhiniyam": "BSA 2023",
    "sakshya_adhiniyam": "BSA 2023",
    "bsa_2023": "BSA 2023",
    "bsa": "BSA 2023",
    "bharatiya_nyaya_sanhita_2023": "BNS 2023",
    "nyaya_sanhita_2023": "BNS 2023",
    "bharatiya_nyaya_sanhita": "BNS 2023",
    "nyaya_sanhita": "BNS 2023",
    "bns_2023": "BNS 2023",
    "bns": "BNS 2023",
}

# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def lookup(value: Any, *, as_of: date | None = None) -> RepealedAct | None:
    """Return the registry entry for an act, filename or label, if repealed.

    Args:
        value: Act key, act label or source filename. Normalised by
            :func:`normalize_act_key`, so all three spellings resolve.
        as_of: Date to evaluate. An entry is returned only if its repeal had
            commenced by this date. Defaults to today.

    Returns:
        The matching :class:`RepealedAct`, or None if the act is not in the
        registry or was still in force on ``as_of``.
    """
    key = normalize_act_key(value)
    if not key:
        return None
    entry = _REPEALED_INDEX.get(key)
    if entry is None:
        return None
    if entry.in_force_as_of(as_of):
        return None
    return entry


def is_repealed(value: Any, *, as_of: date | None = None) -> bool:
    """True if `value` names an enactment repealed as of `as_of`.

    >>> is_repealed("The Code of Criminal Procedure, 1973")
    True
    >>> is_repealed("Bharatiya Nagarik Suraksha Sanhita, 2023")
    False
    """
    return lookup(value, as_of=as_of) is not None


def is_superseding_act(value: Any) -> bool:
    """True if `value` names an in-force Act that supersedes a registry entry.

    Guards against the classic off-by-one-generation bug where a repeal rule
    accidentally catches the replacement instead of the repealed act.
    """
    key = normalize_act_key(value)
    if not key:
        return False
    return key in SUPERSEDING_ACT_KEYS or key in _SUPERSEDING_ALIASES


def superseded_by(value: Any, *, as_of: date | None = None) -> RepealedAct | None:
    """Registry entry that `value` replaces, if any. Inverse of :func:`lookup`."""
    key = normalize_act_key(value)
    if not key:
        return None
    for entry in REPEALED_ACTS:
        if entry.repealed_by_act_key != key:
            continue
        if entry.in_force_as_of(as_of):
            continue
        return entry
    return None


def repealed_act_keys() -> frozenset[str]:
    """Canonical normalised keys of every repealed act (not the aliases)."""
    return frozenset(entry.act_key for entry in REPEALED_ACTS)


def superseding_act_keys() -> frozenset[str]:
    """Canonical normalised keys of every superseding act."""
    return frozenset(SUPERSEDING_ACT_KEYS)


# ---------------------------------------------------------------------------
# The escalation guard
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RepealPlan:
    """What may be removed, and what must be escalated to a human.

    Attributes:
        safe_to_drop: Keys whose repeal has commenced AND whose superseding
            Act is present in `available_act_keys`. Removing these replaces
            dead law with live law, so it is a correctness win.
        blocked_missing_replacement: Keys whose repeal has commenced but whose
            superseding Act is ABSENT. Removing these leaves a coverage hole,
            so they are reported, never silently dropped.
        not_yet_repealed: Registry keys still in force on `as_of`.
        absent_already: Registry keys that were not in the corpus to begin with.
        requires_human_signoff: True when anything is blocked. This is the
            escalation signal the G1 brief demands.
    """

    safe_to_drop: tuple[str, ...]
    blocked_missing_replacement: tuple[str, ...]
    not_yet_repealed: tuple[str, ...]
    absent_already: tuple[str, ...]
    as_of: date

    @property
    def requires_human_signoff(self) -> bool:
        """True if removing repealed law would create a coverage gap."""
        return bool(self.blocked_missing_replacement)

    @property
    def blocked_reasons(self) -> dict[str, str]:
        """Human-readable reason each blocked act cannot be dropped."""
        reasons: dict[str, str] = {}
        for entry in REPEALED_ACTS:
            if entry.act_key not in self.blocked_missing_replacement:
                continue
            reasons[entry.act_key] = (
                f"{entry.display_name} was repealed w.e.f. "
                f"{entry.commencement_date.isoformat()} by "
                f"{entry.repeal_provision}, but its replacement "
                f"{entry.repealed_by_display} is NOT in the corpus. "
                f"{entry.consequence}"
            )
        return reasons


def assess_repeal_plan(
    available_act_keys: Iterable[str],
    *,
    as_of: date | None = None,
) -> RepealPlan:
    """Decide which repealed acts can be dropped without losing coverage.

    This is the function that makes the policy safe. It will only mark an act
    droppable when the Act that supersedes it is actually available, so calling
    it on the current corpus reports CrPC 1973 and the Evidence Act 1872 as
    BLOCKED - which is the honest answer, not a bug.

    Args:
        available_act_keys: Act keys, filenames or act labels that the corpus
            actually holds. Normalised internally, so the caller may pass
            ``act_key_for_file(p)`` results or raw filenames.
        as_of: Date to evaluate. Defaults to today.

    Returns:
        A :class:`RepealPlan`. Empty input means "the corpus holds nothing",
        which blocks every repealed act - the correct conservative answer.
    """
    available: set[str] = set()
    for value in available_act_keys or ():
        key = normalize_act_key(value)
        if key:
            available.add(key)
    # An alias spelling of a superseding Act must also count as "available",
    # otherwise 'BNSS.json' would read as missing.
    expanded = set(available)
    for key in available:
        canonical = _SUPERSEDING_ALIASES.get(key)
        if canonical is None:
            continue
        for sup in SUPERSEDING_ACT_KEYS:
            if _SUPERSEDING_ALIASES.get(sup) == canonical:
                expanded.add(sup)

    effective_as_of = as_of or date.today()
    safe: list[str] = []
    blocked: list[str] = []
    pending: list[str] = []
    absent: list[str] = []

    for entry in REPEALED_ACTS:
        if entry.in_force_as_of(effective_as_of):
            pending.append(entry.act_key)
            continue
        present = entry.act_key in available or bool(
            entry.aliases & available
        )
        if not present:
            # Not in the corpus at all: nothing to remove.
            absent.append(entry.act_key)
            continue
        replacement_available = (
            entry.repealed_by_act_key in expanded
            or entry.repealed_by_act_key in available
        )
        if replacement_available:
            safe.append(entry.act_key)
        else:
            blocked.append(entry.act_key)

    return RepealPlan(
        safe_to_drop=tuple(sorted(safe)),
        blocked_missing_replacement=tuple(sorted(blocked)),
        not_yet_repealed=tuple(sorted(pending)),
        absent_already=tuple(sorted(absent)),
        as_of=effective_as_of,
    )


# ---------------------------------------------------------------------------
# Record-level helpers (the CrPC case: it has no file of its own)
# ---------------------------------------------------------------------------
def _record_act_label(record: Mapping[str, Any]) -> str:
    """Extract the act label from a corpus record."""
    meta = record.get("metadata") or {}
    return str(meta.get("act") or "")


def is_repealed_record(record: Mapping[str, Any], *, as_of: date | None = None) -> bool:
    """True if a corpus record's ``metadata.act`` names a repealed enactment.

    Necessary because the CrPC records cannot be dropped at file level: they
    arrive inside ``Consumer_Protection_Act_2019.json``, a mis-scraped file that
    carries six different Acts' text. Only the record's own act label reveals
    which Act a chunk really belongs to.
    """
    return is_repealed(_record_act_label(record), as_of=as_of)


def filter_repealed_records(
    records: Iterable[Mapping[str, Any]],
    *,
    as_of: date | None = None,
    dry_run: bool = True,
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    """Split records into (keep, drop) on the repeal policy.

    Args:
        records: Corpus records with a ``metadata.act`` field.
        as_of: Date to evaluate. Defaults to today.
        dry_run: Kept True by default and honoured only as documentation of
            intent - this function NEVER mutates its input and NEVER deletes
            anything. It returns lists and leaves every decision to the caller.

    Returns:
        ``(keep, drop)``. `drop` holds only records whose act is repealed.
    """
    keep: list[Mapping[str, Any]] = []
    drop: list[Mapping[str, Any]] = []
    for record in records:
        if is_repealed_record(record, as_of=as_of):
            drop.append(record)
        else:
            keep.append(record)
    return keep, drop


def repeal_notice(value: Any, *, as_of: date | None = None) -> str | None:
    """Retrieval-time warning string for a repealed act, else None.

    This is the zero-risk mitigation: keep the text retrievable, but refuse to
    let the assistant present repealed law as current. Surface it wherever an
    answer cites the source act.
    """
    entry = lookup(value, as_of=as_of)
    if entry is None:
        return None
    return (
        f"{entry.display_name} was repealed with effect from "
        f"{entry.commencement_date.isoformat()} by {entry.repeal_provision} "
        f"(commenced by {entry.commencement_basis}) and replaced by "
        f"{entry.repealed_by_display}. Do not answer from this text as current "
        f"law; if the replacement is not in the index, say so."
    )


def describe_registry() -> str:
    """Operator-facing dump of the policy, for logs and the report."""
    lines = [
        "Repeal policy registry "
        f"(commencement {COMMENCEMENT_DATE_NEW_CRIMINAL_LAWS.isoformat()}, "
        f"{COMMENCEMENT_NOTIFICATION}):"
    ]
    for entry in REPEALED_ACTS:
        lines.append(
            f"  REPEALED  {entry.display_name} "
            f"(key={entry.act_key}, {entry.year})"
        )
        lines.append(
            f"            -> superseded by {entry.repealed_by_display} "
            f"(key={entry.repealed_by_act_key})"
        )
        lines.append(
            f"            -> by {entry.repeal_provision}, w.e.f. "
            f"{entry.commencement_date.isoformat()}"
        )
    return "\n".join(lines)