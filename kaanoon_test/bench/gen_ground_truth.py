"""
gen_ground_truth.py ------ LAW-GPT retrieval benchmark, Task 1 (Phase 1).

Derives benchmark items mechanically from the repaired statute JSONs so the
question set is reproducible and cannot be quietly hand-tuned (plan AD1).

Ground truth for every item is the COMPOSITE key (act, section_number).
section_number alone collides across acts: section 319 exists in BOTH
Bharatiya Nyaya Sanhita 2023 and CrPC 1973 (plan evidence E4, decision AD3).

Usage
-----
    python gen_ground_truth.py --dry-run
    python gen_ground_truth.py --out ground_truth.json
    python gen_ground_truth.py --out ground_truth.json --seed 7

Guarantees
----------
* Deterministic ------ same --seed yields a byte-identical output file.
* Skips corrupt sources (declared-vs-body-marker audit), prefers
  *_repaired / .REPAIRED variants, always skips *.backup_*.
* --dry-run prints stratum counts and writes nothing.
* Fully offline ------ reads local JSON only, never opens an index.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_SOURCE_DIR = Path(r"E:\LAW-GPT_new\BACKUP_DATA\DATA\Statutes\json")
DEFAULT_SEED = 20261003
DEFAULT_TARGET = 200          # plan requires >= 150
SCHEMA_VERSION = 1

SKIP_FILENAME_SUBSTRINGS = ("summary",)
BACKUP_SUBSTRINGS = (".backup_", "_backup")
REPAIRED_SUBSTRINGS = ("_repaired", ".repaired")

# Corpus boilerplate that is not part of the enacted text.
BOILERPLATE_RE = re.compile(
    r"""^\s*(?:
          \[ | \] | \[\s*\] |
          Entire\s+Act |
          Union\s+of\s+India.* |
          Section\s+\d+.* |
          Sections?\s* |
          Chapter\s+[IVXLCDM0-9]+\s*.* |
          Act\s+\d+.* |
          Published.* | Assented.* | Commenced.* |
          S\.\s* | Description\s* | Notes?\s* |
          Illustrations?:?\s* | Explanation\s* |
          \d+\s* |
          [A-Z]\.\s* |
          \([0-9a-zA-Z]{1,6}\)\s*
        )\s*$""",
    re.IGNORECASE | re.VERBOSE,
)

STOPWORDS = frozenset("""
a an the and or but if of to in on at by for with from as is are be been being
that this these those it its his her their our your my we you they he she i
shall may will can could would should must do does did not no nor so than
then there here what which who whom whose when where why how all any each every
some such other another person persons thing things act acts section sections
provision provisions chapter sub subsection clause clauses
""".split())


# --------------------------------------------------------------------------
# Key normalisation ------ shared with score_retrieval.py
# --------------------------------------------------------------------------
def normalise_act(act) -> str:
    """Loose act-name normaliser (AD3): casefold, drop punctuation.

    The leading article "the" is dropped because source JSONs and index
    metadata disagree about it. The YEAR IS KEPT ------ dropping it would
    collapse "The Companies Act, 1956" into "The Companies Act, 2013",
    which are entirely different statutes.
    """
    s = str(act or "").casefold()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("the "):
        s = s[4:].strip()
    return s


def normalise_section(section_number):
    """Canonicalise a section number to its bare identifier.

    Handles the conventions actually present in the corpus:
        '318'    (BNS, Contract Act)          -> '318'
        '1.'     (Companies Act 1956)         -> '1'
        '58A.'   (Companies Act 1956)         -> '58A'
        '4(a)'   (staged index subsections)   -> '4(a)'
        'preamble'                           -> None (not a section)
        '(5)', '(a)'   (subsection fragments) -> None (not a section)
        'No. 35 of 2019', '1 of 1872'         -> None (preamble blob)

    Returning None keeps preamble blobs and bare subsection fragments out
    of the ground truth.
    """
    s = str(section_number or "").strip()
    if not s:
        return None
    m = re.fullmatch(r"(\d+[A-Za-z]?)\(([^)]*)\)", s)
    if m:
        return "%s(%s)" % (m.group(1), m.group(2).strip())
    m = re.fullmatch(r"(\d+[A-Za-z]?)", s)
    if m:
        return m.group(1)
    m = re.fullmatch(r"(\d+[A-Za-z]?)\s*\.", s)
    if m:
        return m.group(1)
    return None


def composite_key(act, section_number):
    """The composite identity used for all retrieval scoring (AD3)."""
    sec = normalise_section(section_number)
    if sec is None:
        return None
    return "%s::%s" % (normalise_act(act), sec)


def split_number_and_title(raw):
    """Split a raw section_number field into (section_id, inline_title).

    Source files use three shapes:
        '318'             -> ('318', '')
        '1.'              -> ('1', '')
        '2. Definitions.' -> ('2', 'Definitions.')
        '(5)'             -> (None, '')
        'No. 35 of 2019'  -> (None, '')
    """
    s = str(raw or "").strip()
    m = re.match(r"^(\d+[A-Za-z]?)\s*\.\s*(\S.*)$", s)
    if m:
        return m.group(1), m.group(2).strip()
    m = re.fullmatch(r"(\d+[A-Za-z]?)\s*\.?", s)
    if m:
        return m.group(1), ""
    return None, ""
# --------------------------------------------------------------------------
# Source selection ------ corrupt-file avoidance
# --------------------------------------------------------------------------
BODY_MARKER_RE = re.compile(r"^\s*-{2,}\s*Section\s+(\d+[A-Za-z]?)\s*-{2,}", re.I)
# A source is rejected as corrupt when more than this fraction of its
# declared section numbers disagree with its own body marker.
MISMATCH_TOLERANCE = 0.02


def classify_source_file(filename):
    """Return one of 'skip_backup', 'repaired', 'original'."""
    low = filename.casefold()
    if any(b in low for b in BACKUP_SUBSTRINGS):
        return "skip_backup"
    if any(s in low for s in SKIP_FILENAME_SUBSTRINGS):
        return "skip_backup"
    if any(r in low for r in REPAIRED_SUBSTRINGS):
        return "repaired"
    return "original"


def act_from_filename(filename):
    """Identity of the act a file describes, ignoring variant suffixes.

    'Bharatiya_Nyaya_Sanhita_2023_repaired.json' and
    'Bharatiya_Nyaya_Sanhita_2023.json' both map to
    'bharatiya nyaya sanhita 2023', so only ONE is selected per act.
    """
    stem = Path(filename).stem
    for r in REPAIRED_SUBSTRINGS:
        if stem.casefold().endswith(r):
            stem = stem[: -len(r)]
            break
    for b in BACKUP_SUBSTRINGS:
        idx = stem.casefold().find(b)
        if idx != -1:
            stem = stem[:idx]
            break
    return normalise_act(stem.replace("_", " "))


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        print("  ! unreadable %s: %s" % (path.name, exc), file=sys.stderr)
        return None


def audit_source(payload):
    """Compare declared section_number against the body marker.

    This is the machine check behind evidence E1: the corrupt BNS original
    declares section_number = body_marker + 1 on 357 of 358 sections.
    """
    sections = payload.get("sections")
    if not isinstance(sections, list):
        return {"declared": 0, "checked": 0, "mismatch": 0, "ratio": 0.0}
    declared = checked = mismatch = 0
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        declared += 1
        raw = str(sec.get("section_number") or "").strip()
        content = str(sec.get("content") or "")
        m = BODY_MARKER_RE.match(content.lstrip())
        if not m:
            continue
        truth = normalise_section(m.group(1))
        got = normalise_section(raw)
        if truth is None or got is None:
            continue
        checked += 1
        if truth != got:
            mismatch += 1
    ratio = (mismatch / checked) if checked else 0.0
    return {"declared": declared, "checked": checked,
            "mismatch": mismatch, "ratio": ratio}


def title_quality(payload):
    """Fraction of sections carrying a genuinely usable marginal note.

    Some repaired variants keep the statutory text correct but leave
    section_title as an ingestion artefact ('Chunk 3', '--- Section 100').
    Ranking sources by this score selects the variant that is actually
    usable as ground truth.
    """
    sections = payload.get("sections") or []
    if not sections:
        return 0.0
    good = 0
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        title = clean_title(sec.get("section_title") or "")
        if len(title.split()) >= 3 and not PLACEHOLDER_TITLE_RE.match(title):
            good += 1
    return good / len(sections)


def select_sources(source_dir, verbose=True):
    """Pick exactly one clean source file per act.

    Precedence: repaired variants first; among those, the one with the most
    real marginal notes; then the lowest declared-vs-body mismatch rate.
    Backup files are never selected.
    """
    candidates = []
    rejected = []
    for path in sorted(Path(source_dir).glob("*.json")):
        kind = classify_source_file(path.name)
        if kind == "skip_backup":
            rejected.append((path.name, "backup/summary file"))
            continue
        payload = load_json(path)
        if not isinstance(payload, dict):
            rejected.append((path.name, "not a JSON object"))
            continue
        if not isinstance(payload.get("sections"), list) or not payload["sections"]:
            rejected.append((path.name, "no sections list"))
            continue
        entry = {
            "path": path,
            "name": path.name,
            "kind": kind,
            "act_key": act_from_filename(path.name),
            "act_name": str(payload.get("act_name") or "").strip(),
            "audit": audit_source(payload),
            "tq": title_quality(payload),
            "payload": payload,
        }
        audit = entry["audit"]
        if audit["checked"] and audit["ratio"] > MISMATCH_TOLERANCE:
            rejected.append((path.name, "corrupt: %d/%d declared-vs-body mismatches"
                             % (audit["mismatch"], audit["checked"])))
            continue
        candidates.append(entry)

    chosen = {}
    for entry in sorted(candidates, key=lambda e: (
            0 if e["kind"] == "repaired" else 1,
            -e["tq"],
            e["audit"]["ratio"],
            -e["audit"]["checked"],
            e["name"])):
        key = entry["act_key"]
        if key in chosen:
            rejected.append((entry["name"],
                             "duplicate act; %s preferred" % chosen[key]["name"]))
            continue
        chosen[key] = entry

    if verbose:
        print("Scanned %s" % source_dir)
        print("  selected %d act sources, rejected %d"
              % (len(chosen), len(rejected)))
    return chosen, rejected
# --------------------------------------------------------------------------
# Section extraction + classification
# --------------------------------------------------------------------------
# Ingestion artefacts that occupy section_title in some repaired variants
# but carry no legal meaning ('Chunk 3', '--- Section 100', '1.').
PLACEHOLDER_TITLE_RE = re.compile(
    r"^(?:chunk|section|part|para|clause|subsection|schedule|annex|"
    r"exhibit|fragment|snippet)\s*[\w\-]*\s*\d*\s*$|^-{2,}.*-{2,}$|^\d+$",
    re.I)


def clean_title(raw):
    """Strip numbering, markers and trailing punctuation from a marginal note."""
    t = str(raw or "").strip()
    t = re.sub(r"^\s*-{2,}\s*Section\s+\d+[A-Za-z]?\s*-{2,}\s*$", "", t, flags=re.I)
    # Corpus artefacts: unmatched brackets around marginal notes, e.g.
    # '[Power of company to purchase its own securities'
    t = re.sub(r"^[\[\(\{<]+\s*", "", t)
    t = re.sub(r"\s*[\]\)\}>]+$", "", t)
    t = re.sub(r"^\s*\d+[A-Za-z]?\s*\.\s*", "", t)
    t = t.strip().strip(".").strip()
    t = re.sub(r"[.:;]+$", "", t).strip()
    t = re.sub(r"\s+", " ", t)
    if not t or PLACEHOLDER_TITLE_RE.match(t):
        return ""
    return t


def is_usable_title(title):
    """A question needs a real marginal note, not prose or an artefact.

    Rejects body prose that slipped through title derivation, e.g.
    'In this Sanhita unless the context otherwise requires' ------ a heading is
    title-case noun-phrase style, not a sentence.
    """
    if not title:
        return False
    words = title.split()
    if len(words) < 3 or len(words) > 14:
        return False
    if len(title) > 120:
        return False
    if title[0].islower():
        return False
    if title.endswith((",", ";", ":")):
        return False
    if PLACEHOLDER_TITLE_RE.match(title):
        return False
    # Prose markers that never appear in a marginal note.
    if re.search(r"\b(shall|must|may|means|unless|whereas|herein|"
                 r"notwithstanding|provided that|namely|whoever|"
                 r"subject to|saved as|in this Act|in this Sanhita)\b",
                 title, re.I):
        return False
    if ":" in title:                        # 'Kidnapping is of two kinds: ...'
        return False
    if re.search(r"\b(is|are|was|were)\b", title):   # a clause, not a heading
        return False
    if re.search(r"\b\d{3,}\b", title):        # statutory citations
        return False
    if re.search(r"\bsection\b", title, re.I):
        return False                            # 'For the purposes of section ...'
    if re.search(r"[\[\(\{<>]", title):          # dangling '... to the [Tribunal'
        return False
    if title.rstrip().endswith((",", ";", ":")):
        return False
    if title.count(",") >= 2:                  # list-like prose
        return False
    return True


# Cap on body size for a usable benchmark item. Whole-act preambles
# (e.g. a 38k-char Statement of Objects) are not answerable questions.
MAX_BODY_CHARS = 20000


def derive_title(content):
    """Recover a marginal note from the body when section_title is useless.

    Many sources set section_title to the bare number ('1.') and put the
    real heading on the first non-boilerplate line of the body.
    """
    lines = [ln.strip() for ln in str(content or "").split("\n")]
    body = [ln for ln in lines if ln and not BOILERPLATE_RE.match(ln)]
    for first in body[:6]:
        stripped = first.strip()
        if not stripped or BOILERPLATE_RE.match(stripped):
            continue
        m = re.match(r"^\(?\d+[A-Za-z]?\)?[.)]?\s+(.*)$", stripped)
        if m and m.group(1).strip():
            stripped = m.group(1)
        title = clean_title(stripped)
        if is_usable_title(title):
            return title
    return ""


def clean_body(content):
    """Strip corpus boilerplate, keep the enacted text."""
    lines = [ln.strip() for ln in str(content or "").split("\n")]
    keep = [ln for ln in lines if ln and not BOILERPLATE_RE.match(ln)]
    return re.sub(r"\s+", " ", " ".join(keep)).strip()


def content_keyphrases(body, title, limit=6):
    """Distinctive terms from the heading, then salient body terms."""
    phrases = []
    seen = set()
    for tok in re.findall(r"[A-Za-z][A-Za-z\-']{2,}", title or ""):
        low = tok.casefold()
        if low in STOPWORDS or low in seen:
            continue
        seen.add(low)
        phrases.append(tok)
        if len(phrases) >= limit:
            return phrases
    for tok in re.findall(r"[A-Za-z][A-Za-z\-']{3,}", body or ""):
        low = tok.casefold()
        if low in STOPWORDS or low in seen:
            continue
        seen.add(low)
        phrases.append(tok)
        if len(phrases) >= limit:
            break
    return phrases


def length_bucket(chars):
    """Bucket by body length.

    Thresholds are set from the observed corpus distribution
    (p25 ~ 400 chars, median ~ 690, p75 ~ 1190), so the buckets actually
    split the population instead of collapsing into one cell.
    """
    if chars < 450:
        return "short"
    if chars < 1200:
        return "medium"
    return "long"


DEFINITION_RE = re.compile(
    r"\b(definitions?|interpretation|meaning of|defined|construction of|"
    r"general explanations?)\b", re.I)
PUNISHMENT_RE = re.compile(
    r"\b(punish(?:ment|ed)?|offence|offences|penalt(?:y|ies)|imprisonment|"
    r"punishable|compoundable|cognizable|liable to|forfeiture)\b", re.I)
PROCEDURE_RE = re.compile(
    r"\b(procedure|application|apply|notice|hearing|inquiry|appeal|revision|"
    r"jurisdiction|register|filing|petition|complaint|inspection|licence|"
    r"license|registration)\b", re.I)
EXCEPTION_RE = re.compile(
    r"\b(exception|exceptions|notwithstanding|unless|provided that|"
    r"save as|except|subject to|proviso)\b", re.I)


def classify_type(title, body):
    """Assign one of: definition / punishment / procedure / exception.

    Precedence is deliberate. An explicit heading wins; then the strongest
    body signal. Punishment outranks procedure because a section that both
    prescribes a penalty and lays down steps is more usefully graded on the
    penalty. 'except'/'unless' alone is weak evidence, so it is consulted
    last.
    """
    if DEFINITION_RE.search(title):
        return "definition"
    if PUNISHMENT_RE.search(title):
        return "punishment"
    if EXCEPTION_RE.search(title):
        return "exception"
    if PROCEDURE_RE.search(title):
        return "procedure"

    window = "%s %s" % (title, body[:2500])
    if PUNISHMENT_RE.search(window):
        return "punishment"
    if re.search(r"\bmeans\b", body[:1200], re.I):
        return "definition"
    if PROCEDURE_RE.search(window):
        return "procedure"
    if EXCEPTION_RE.search(window):
        return "exception"
    return "procedure"
# --------------------------------------------------------------------------
# Candidate building
# --------------------------------------------------------------------------
def build_candidates(chosen, verbose=True):
    """Turn selected sources into scored, question-ready candidates."""
    candidates = []
    for act_key in sorted(chosen):
        entry = chosen[act_key]
        payload = entry["payload"]
        act_name = entry["act_name"] or act_key
        seen_keys = set()
        for sec in payload["sections"]:
            if not isinstance(sec, dict):
                continue
            raw_sn = str(sec.get("section_number") or "").strip()
            section_id, inline_title = split_number_and_title(raw_sn)
            if section_id is None:
                continue  # subsection fragments, preamble blobs
            key = composite_key(act_name, section_id)
            if key is None or key in seen_keys:
                continue
            body = clean_body(sec.get("content") or "")
            if len(body) < 120 or len(body) > MAX_BODY_CHARS:
                continue
            title = clean_title(sec.get("section_title") or "")
            if title.casefold() == section_id.casefold():
                title = ""
            if not title and inline_title:
                title = clean_title(inline_title)
            if not is_usable_title(title):
                title = derive_title(sec.get("content") or "")
            if not is_usable_title(title):
                continue  # no usable heading -> unanswerable item
            keyphrases = content_keyphrases(body, title)
            if len(keyphrases) < 2:
                continue
            seen_keys.add(key)
            candidates.append({
                "act": act_name,
                "act_key": normalise_act(act_name),
                "section_number": section_id,
                "section_key": key,
                "expected_title": title,
                "expected_keyphrases": keyphrases,
                "section_type": classify_type(title, body),
                "length_bucket": length_bucket(len(body)),
                "body_chars": len(body),
                "source_file": entry["name"],
                "source_kind": entry["kind"],
            })
    if verbose:
        print("  built %d usable candidates across %d acts"
              % (len(candidates), len({c["act_key"] for c in candidates})))
    return candidates


# --------------------------------------------------------------------------
# Question generation
# --------------------------------------------------------------------------
LEADING_ARTICLE_RE = re.compile(r"^(the|a|an)\s+", re.I)

# Some acts begin their formal name with the article ("The Companies Act,
# 1956"). Templates supply their own article, so strip it to avoid
# "In the The Companies Act, 1956".
def act_for_prose(act):
    name = str(act or "").strip()
    return LEADING_ARTICLE_RE.sub("", name) if name else name


TEMPLATES = {
    "definition": (
        "Under {act}, how is {focus} defined?",
        "What does {act} define by {focus}?",
        "In {act}, what is meant by {focus}?",
    ),
    "punishment": (
        "What punishment is prescribed by {act} for {focus}?",
        "Under {act}, what is the penalty for {focus}?",
        "In {act}, how is {focus} punishable?",
    ),
    "procedure": (
        "What procedure does {act} lay down for {focus}?",
        "Under {act}, what steps must be followed for {focus}?",
        "In {act}, how must {focus} be dealt with procedurally?",
    ),
    "exception": (
        "What exception does {act} provide in relation to {focus}?",
        "Under {act}, when does {focus} not apply?",
        "In {act}, what carve-out or proviso governs {focus}?",
    ),
}


def make_question(cand, variant):
    """Build a natural-language question that never leaks the section number.

    Leaking the number would let BM25 win trivially and would make the
    benchmark measure string matching rather than retrieval.
    """
    title = cand["expected_title"]
    focus = title if len(title.split()) <= 10 else " ".join(title.split()[:10])
    options = TEMPLATES[cand["section_type"]]
    return options[variant % len(options)].format(
        act=act_for_prose(cand["act"]), focus=focus)
# --------------------------------------------------------------------------
# Stratified sampling
# --------------------------------------------------------------------------
def stratified_sample(candidates, target, seed):
    """Pick `target` candidates balanced across act x section type x length.

    Round-robins the four section types, then rotates the source act and the
    document length, so no single large act (Companies Act 1956 alone has
    2,043 sections) can dominate the benchmark.
    """
    rng = random.Random(seed)
    pool = list(candidates)
    rng.shuffle(pool)

    buckets = defaultdict(list)
    for cand in pool:
        buckets[(cand["act_key"], cand["section_type"],
                 cand["length_bucket"])].append(cand)

    types = ["definition", "punishment", "procedure", "exception"]
    lengths = ["short", "medium", "long"]
    acts = sorted({c["act_key"] for c in candidates})
    if not acts:
        return []

    chosen = []
    used = set()
    rounds = 0
    # Each round picks one item per type, rotating the length preference and
    # the act offset so no type collapses onto a single length bucket and no
    # single act dominates.
    while len(chosen) < target and rounds < 500:
        progressed = False
        for ti, stype in enumerate(types):
            if len(chosen) >= target:
                break
            picked = None
            for step in range(len(lengths) * len(acts)):
                # Rotate starting length and starting act on every step.
                length = lengths[(step + rounds) % len(lengths)]
                act_key = acts[(step + rounds + ti) % len(acts)]
                bucket = buckets.get((act_key, stype, length))
                if bucket:
                    cand = bucket.pop(0)
                    if cand["section_key"] not in used:
                        picked = cand
                        break
                    continue
            if picked is None:
                # Fall back to any bucket for this type before giving up.
                for key in sorted(buckets):
                    if key[1] != stype:
                        continue
                    bucket = buckets[key]
                    if bucket:
                        cand = bucket.pop(0)
                        if cand["section_key"] not in used:
                            picked = cand
                            break
            if picked:
                used.add(picked["section_key"])
                chosen.append(picked)
                progressed = True
        if not progressed:
            break
        rounds += 1

    # Top up if the balanced sweep ran dry.
    if len(chosen) < target:
        for cand in pool:
            if len(chosen) >= target:
                break
            if cand["section_key"] not in used:
                used.add(cand["section_key"])
                chosen.append(cand)

    chosen.sort(key=lambda c: (c["act_key"], c["section_number"]))
    return chosen


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------
def print_table(title, counter, limit=60):
    print("\n%s" % title)
    if not counter:
        print("  (none)")
        return
    width = max(len(str(k)) for k in counter)
    for key in sorted(counter, key=lambda k: (-counter[k], str(k)))[:limit]:
        print("  %-*s %5d" % (width, key, counter[key]))


def summarise(items, verbose=True):
    by_type = Counter(i["section_type"] for i in items)
    by_act = Counter(i["act"] for i in items)
    by_len = Counter(i["length_bucket"] for i in items)
    by_cross = Counter((i["section_type"], i["length_bucket"]) for i in items)

    print("\n" + "=" * 68)
    print("GROUND TRUTH STRATA")
    print("=" * 68)
    print("TOTAL ITEMS: %d" % len(items))
    print("DISTINCT ACTS: %d" % len(by_act))

    print_table("BY SECTION TYPE", by_type)
    print_table("BY LENGTH BUCKET", by_len)
    print_table("BY ACT", by_act, limit=100)

    print("\nTYPE x LENGTH (short / medium / long)")
    for stype in ["definition", "punishment", "procedure", "exception"]:
        row = "  %-12s" % stype
        for length in ["short", "medium", "long"]:
            row += " %6d" % by_cross.get((stype, length), 0)
        print(row)

    keys = [i["section_key"] for i in items]
    assert len(keys) == len(set(keys)), "duplicate composite keys emitted"
    assert len(items) == sum(by_type.values()), "strata do not sum to total"
    # Word-boundary check: a bare "2" must not count as a leak, but
    # "Section 319 of the BNS" must.
    leaked = [i["qid"] for i in items
              if re.search(r"\b%s\b" % re.escape(i["section_number"]), i["question"])]
    placeholders = [i["qid"] for i in items
                    if not i["expected_title"]
                    or PLACEHOLDER_TITLE_RE.match(i["expected_title"])]
    print("\nINTEGRITY")
    print("  unique composite keys   : %d / %d" % (len(set(keys)), len(items)))
    print("  strata sum == total     : OK")
    print("  question leaks number   : %d" % len(leaked))
    print("  placeholder titles      : %d" % len(placeholders))
    assert not leaked, "section number leaked into question: %s" % leaked[:3]
    assert not placeholders, "placeholder title emitted: %s" % placeholders[:3]
    return {
        "total": len(items),
        "distinct_acts": len(by_act),
        "by_type": dict(by_type),
        "by_length": dict(by_len),
        "by_act": dict(by_act),
        "by_type_length": {"%s|%s" % k: v for k, v in by_cross.items()},
    }
# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Generate the LAW-GPT retrieval benchmark ground truth.")
    ap.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR),
                    help="Directory holding the statute JSON sources.")
    ap.add_argument("--out", default=None,
                    help="Output path for the ground-truth JSON.")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED,
                    help="Deterministic sampling seed (default %d)." % DEFAULT_SEED)
    ap.add_argument("--target", type=int, default=DEFAULT_TARGET,
                    help="Items to emit (default %d, plan minimum 150)." % DEFAULT_TARGET)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print strata counts and write nothing.")
    ap.add_argument("--show-rejected", action="store_true",
                    help="List every rejected source file and the reason.")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    source_dir = Path(args.source_dir)
    if not source_dir.is_dir():
        print("source dir not found: %s" % source_dir, file=sys.stderr)
        return 2

    print("=" * 68)
    print("LAW-GPT ground-truth generation (Task 1)")
    print("=" * 68)
    print("source dir : %s" % source_dir)
    print("seed       : %d" % args.seed)
    print("target     : %d" % args.target)
    print("mode       : %s"
          % ("DRY RUN (no files written)" if args.dry_run else "WRITE"))

    chosen, rejected = select_sources(source_dir)

    print("\nSELECTED SOURCES (%d)" % len(chosen))
    for key in sorted(chosen):
        entry = chosen[key]
        audit = entry["audit"]
        print("  [%-8s] %-52s sections=%5d mismatch=%d/%d"
              % (entry["kind"], entry["name"][:52], audit["declared"],
                 audit["mismatch"], audit["checked"]))

    if args.show_rejected:
        print("\nREJECTED SOURCES (%d)" % len(rejected))
        for name, reason in sorted(rejected):
            print("  %-52s %s" % (name[:52], reason))

    candidates = build_candidates(chosen)
    if len(candidates) < args.target:
        print("WARNING: only %d candidates available for target %d"
              % (len(candidates), args.target), file=sys.stderr)

    picked = stratified_sample(candidates, args.target, args.seed)

    items = []
    for variant, cand in enumerate(picked):
        items.append({
            "qid": "gt_%s_%s" % (
                cand["act_key"].replace(" ", "_"),
                cand["section_number"].replace("(", "_").replace(")", "")),
            "act": cand["act"],
            "act_key": cand["act_key"],
            "section_number": cand["section_number"],
            "section_key": cand["section_key"],
            "expected_title": cand["expected_title"],
            "expected_keyphrases": cand["expected_keyphrases"],
            "section_type": cand["section_type"],
            "length_bucket": cand["length_bucket"],
            "source_file": cand["source_file"],
            "question": make_question(cand, variant),
        })

    stats = summarise(items)

    if args.dry_run:
        print("\n[--dry-run] wrote nothing.")
        return 0

    out_path = Path(args.out or (Path(__file__).parent / "ground_truth.json"))
    document = {
        "schema_version": SCHEMA_VERSION,
        "generator": "gen_ground_truth.py",
        "seed": args.seed,
        "source_dir": str(source_dir),
        "target": args.target,
        "selected_sources": {k: v["name"] for k, v in sorted(chosen.items())},
        "rejected_sources": sorted(rejected),
        "strata": stats,
        "items": items,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(document, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    print("\nWROTE %s (%d items)" % (out_path, len(items)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
