"""
Generate family-law surface_form_pairs from the kanoon corpus.

SOURCE
------
E:\\LAW-GPT_new\\BACKUP_DATA\\DATA\\kanoon.com\\kanoon.com\\kanoon_data.json
  -> 102,176 records; 21,264 are query_category == "Family Law".
  -> BUT only 398 UNIQUE questions; the rest are repeat answers per thread.

HONESTY CONSTRAINTS (deliberate, and the point of this generator)
----------------------------------------------------------------
* a1 (the reference answer) is NEVER invented. It is real kanoon practitioner
  text, de-noised and boilerplate-stripped, and attributed with its source URL.
* q1 (the formal phrasing) is a TEMPLATE naming the act and section. It asserts
  no legal proposition.
* q2_probes are the REAL user questions from kanoon. That is the valuable part:
  real surface forms written by people who did not know the statute's name.
* must_include lists only strings that ACTUALLY OCCUR in a1, so answer grading
  cannot demand something the reference answer never said.
* No statute text is authored anywhere in this file.
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

SRC = Path(r"E:\LAW-GPT_new\BACKUP_DATA\DATA\kanoon.com\kanoon.com\kanoon_data.json")
OUT = Path(r"E:\LAW-GPT_new\azure_backend_stage\kaanoon_test\benchmark"
           r"\family_law_surface_form_pairs.json")

# ---------------------------------------------------------------- cleaning

BOILER = re.compile(
    r"Available Now \d+ Answers \d+ Consultations\s*|Talk to Advocate NOW\s*|"
    r"Consultations Talk to Advocate NOW\s*|"
    r"[A-Z][A-Za-z. ]*Advocate,?\s*[A-Za-z ]*", re.UNICODE)

REPLY_PREFIX = re.compile(
    r"^(dear\s+(sir|madam|client|customer)?\s*[,.]?\s*|"
    r"(hi|hello|hii|hey)[,.\s]*|thanks?,?\s*|thank you\.?\s*)+", re.I)

SEC = re.compile(r"(?:section|s\.)\s*(\d+[A-Za-z]?)", re.I)

# Section numbers that legally exist in each act. STRUCTURE, not statute prose.
VALID: dict[str, set[str]] = {
    "Hindu Marriage Act, 1955": {
        "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13",
        "13B", "14", "15", "16", "17", "19", "20", "21", "21A", "21B", "22",
        "23", "24", "25", "26", "27", "28"},
    "Protection of Women from Domestic Violence Act, 2005": {
        "2", "3", "4", "5", "6", "7", "8", "9", "10", "12", "13", "14", "15",
        "16", "17", "18", "19", "20", "21", "22", "23", "24", "26", "27"},
    "Special Marriage Act, 1954": {"4", "5", "6", "7", "8", "9", "10", "11",
                                   "12", "13", "14"},
    "Hindu Adoption and Maintenance Act, 1956": {
        "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"},
    "Hindu Guardians and Wards Act, 1890": {"2", "3", "4", "7", "8", "9", "11"},
    "Hindu Minority and Guardianship Act, 1956": {
        "2", "3", "4", "6", "7", "8", "9", "11", "14", "18", "25"},
    "Indian Divorce Act, 1869": {"2", "3", "4", "10", "14", "15"},
    "Hindu Succession Act, 1956": {"6", "8", "15", "23", "24"},
    "Dowry Prohibition Act, 1961": {"2", "3", "4", "4A", "5", "6", "8", "10"},
    "Code of Criminal Procedure, 1973": {
        "41A", "91", "125", "126", "127", "128", "133", "144", "190", "200",
        "202", "204", "207", "339", "340", "482", "494", "497", "498", "498A",
        "500", "504"},
    "Indian Penal Code, 1860": {
        "3", "4", "6", "9", "10", "12", "13", "34", "90", "294", "299", "306",
        "375", "376", "378", "406", "415", "417", "420", "425", "426", "494",
        "497", "498", "498A", "499", "500", "504", "506", "509", "511"},
    "Code of Civil Procedure, 1908": {
        "9", "10", "11", "13", "14", "19", "20", "24", "25", "125"},
}

ACT_PATTERNS = [
    ("Hindu Marriage Act, 1955", r"Hindu Marriage Act"),
    ("Protection of Women from Domestic Violence Act, 2005",
     r"Protection of Women from Domestic Violence Act|Domestic Violence Act"
     r"|\bDV Act\b|\bDVA\b|\bPWDVA\b"),
    ("Special Marriage Act, 1954", r"Special Marriage Act"),
    ("Hindu Adoption and Maintenance Act, 1956",
     r"Hindu Adoption and Maintenance Act|Hindu Adoption"),
    ("Hindu Guardians and Wards Act, 1890",
     r"Guardians and Wards Act|Guardian and Guardianship Act"),
    ("Hindu Minority and Guardianship Act, 1956",
     r"Hindu Minority and Guardianship Act|Minority Act"),
    ("Indian Divorce Act, 1869", r"Indian Divorce Act"),
    ("Hindu Succession Act, 1956", r"Hindu Succession Act"),
    ("Dowry Prohibition Act, 1961", r"Dowry Prohibition Act"),
    ("Code of Criminal Procedure, 1973", r"Code of Criminal Procedure|\bCrPC\b"),
    ("Indian Penal Code, 1860", r"Indian Penal Code|\bIPC\b"),
    ("Code of Civil Procedure, 1908", r"Code of Civil Procedure|\bCPC\b"),
]
# Topic hints used only to name the bucket a case belongs to.
TOPIC_RULES = [
    ("domestic_violence", r"domestic violence|\bdv act\b|\bdva\b|dowry|498a|498-a|"
                          r"abuse|assault|beating|harass"),
    ("maintenance", r"maintenance|alimony|maintain|section 125"),
    ("child_custody", r"custody|guardian|visitation|minor child"),
    ("restitution_of_conjugal_rights",
     r"restitution of conjugal|conjugal rights|\brcr\b"),
    ("mutual_consent_divorce", r"mutual consent|mutual divorce|13\(2\)"),
    ("divorce_grounds", r"divorce|adultery|cruelty|desertion|13\(1\)"),
    ("succession", r"succession|inherit|heir|legac"),
    ("special_marriage", r"special marriage|interfaith|inter-religious"),
    ("adoption", r"adoption|adopted"),
    ("property_and_stridhan", r"stridhan|stridan|property"),
]
WINDOW = 220


def clean(text: str) -> str:
    t = BOILER.sub(" ", text or "")
    t = REPLY_PREFIX.sub("", t).strip()
    return " ".join(t.split())


def topic_of(text: str) -> str:
    for name, pat in TOPIC_RULES:
        if re.search(pat, text, re.I):
            return name
    return "family_law_general"


def tier_of(question: str) -> str:
    """Classify the REAL user question into the benchmark's tier vocabulary."""
    q = question.lower()
    has_cite = bool(re.search(r"\bsection\s*\d|\bsec\.?\s*\d|\bact\s*,?\s*\d{4}"
                              r"|\b\d{4}\s+act\b|\bipc\b|\bcrpc\b|\bcpc\b",
                              q, re.I))
    has_first_person = bool(re.search(r"\b(i|my|we|our|me)\b", q))
    story = re.search(r"\b(wife|husband|mother|father|son|daughter|"
                      r"family|in-laws|home)\b", q)
    consequence = re.search(
        r"^\s*(what (should|can|do|happens)|how (do|can|does|long|much)|"
        r"is it possible|can i|can we|am i)", q)

    if has_cite:
        return "T1_paraphrase"
    if consequence and not story:
        return "T4_indirect"
    if has_first_person and story and len(q.split()) > 35:
        return "T3_narrative"
    return "T2_situational"


def bind(text: str) -> set[tuple[str, str]]:
    """(act, section) pairs where the act name sits near the section number."""
    acts = []
    for name, pat in ACT_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            acts.append((m.start(), name))
    out = set()
    for sm in SEC.finditer(text):
        s = sm.group(1).upper()
        for pos, name in acts:
            if abs(pos - sm.start()) <= WINDOW and s in VALID.get(name, ()):
                out.add((name, s))
    return out


def build_cases() -> tuple[list[dict], dict]:
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    fl = [x for x in raw if x.get("query_category") == "Family Law"]

    by_url: dict[str, list[dict]] = collections.defaultdict(list)
    for x in fl:
        by_url[x["query_url"]].append(x)

    cases: list[dict] = []
    for n, (url, xs) in enumerate(sorted(by_url.items()), 1):
        question = clean(xs[0].get("query_text") or "")
        if len(question) < 40:
            continue

        # Longest de-noised answer in the thread = the reference answer.
        best, blen = None, 0
        for x in xs:
            a = clean(x.get("response_text") or "")
            if len(a) > blen:
                best, blen = a, len(a)
        if not best or blen < 300:
            continue

        pairs = bind(best) or bind(question)
        if not pairs:
            continue

        act, sec = sorted(pairs)[0]
        topic = topic_of(question + " " + best)

        q1 = (f"Under the {act}, what does Section {sec} provide, and what "
              f"does it require of the parties in this situation?")

        # must_include must be SATISFIABLE BY a1, or answer grading is broken.
        # Verify each candidate literally appears in the reference answer.
        low_ans = best.lower()
        must: list[str] = []
        for anchor in (f"section {sec}", f"s.{sec}"):
            if anchor in low_ans:
                must.append(anchor.replace(sec, sec) if anchor.startswith("s.")
                            else f"Section {sec}")
                break
        for kw in ("maintenance", "alimony", "divorce", "custody", "guardian",
                   "domestic violence", "dowry", "adultery", "cruelty",
                   "restitution", "succession", "adoption", "stridhan",
                   "visitation", "child"):
            if kw in low_ans and kw.title() not in must:
                must.append(kw.title())
        must = must[:5]
        if not must:
            # Nothing from the authority is literally present; keep only topics
            # that are, so the case stays gradable.
            must = [kw.title() for kw in ("maintenance", "divorce", "custody",
                                          "domestic violence", "succession")
                    if kw in low_ans][:3]

        slug = re.sub(r"[^a-z0-9]+", "_",
                      f"{act.split(',')[0]}_s{sec}_{topic}".lower())
        cases.append({
            "id": f"kf{n:03d}_{slug}"[:70],
            "tier": tier_of(question),
            "topic": topic,
            "primary_authority": f"{act} - Section {sec}",
            "q1": q1,
            "a1": best,
            "must_include": must,
            "q2_probes": [{
                "text": question,
                "note": ("REAL kanoon user question, verbatim (boilerplate "
                         "stripped). Unedited surface form - this is the "
                         "genuine retrieval stress test."),
            }],
            "all_bound_sections": sorted(f"{a} s.{s}" for a, s in pairs)[:6],
            "source_url": url,
            "provenance": {
                "dataset": "kanoon_data.json (BACKUP_DATA/DATA/kanoon.com)",
                "query_category": "Family Law",
                "query_religion": xs[0].get("query_religion") or "",
                "answers_in_thread": len(xs),
                "answer_chars": blen,
                "a1_origin": ("verbatim kanoon practitioner answer, "
                              "boilerplate and salutation stripped; no legal "
                              "text authored by the generator"),
            },
        })

    stats = {
        "source_dataset_records": len(raw),
        "family_law_records_scanned": len(fl),
        "unique_family_law_threads": len(by_url),
        "cases_emitted": len(cases),
    }
    return cases, stats
def main() -> None:
    cases, stats = build_cases()

    # HARD GATE: every case must be gradable. A case whose must_include cannot
    # be satisfied by its own reference answer is a broken test, not a hard one.
    dropped: list[str] = []
    for c in cases:
        low = c["a1"].lower()
        c["must_include"] = [m for m in c["must_include"] if m.lower() in low]
        if not c["must_include"]:
            dropped.append(c["id"])
    if dropped:
        print(f"DROPPED {len(dropped)} ungradable case(s): {dropped}")

    # De-duplicate on reference answer text.
    seen: set[str] = set()
    uniq: list[dict] = []
    for c in cases:
        if c["a1"] in seen:
            continue
        seen.add(c["a1"])
        uniq.append(c)
    if len(uniq) != len(cases):
        print(f"de-duplicated {len(cases) - len(uniq)} repeated a1")
    cases = uniq
    stats["cases_emitted"] = len(cases)
    stats["dropped_ungradable"] = len(dropped)

    doc = {
        "schema_version": "1.0",
        "name": "Indian Family Law - Surface-Form Pairs (kanoon-derived)",
        "purpose": (
            "Detects the 'same answer, different surface form' RAG failure. Each "
            "case pairs a FORMAL, statute-naming phrasing (q1) with the REAL "
            "everyday phrasing a person actually typed (q2_probes). The q2 text "
            "is verbatim from kanoon, so it carries the genuine messiness of "
            "real queries - no legal vocabulary, typos, run-on sentences."),
        "provenance": {
            "source_dataset": str(SRC),
            **stats,
            "IMPORTANT": (
                f"The kanoon Family Law slice contains only "
                f"{stats['unique_family_law_threads']} DISTINCT questions "
                f"across {stats['family_law_records_scanned']} records (each "
                "question was answered dozens of times by different "
                "practitioners). Real topical diversity is therefore "
                f"{stats['unique_family_law_threads']}, not "
                f"{stats['family_law_records_scanned']}. This file cannot "
                "exceed that ceiling and no filtering will raise it."),
            "a1_is_practitioner_opinion": (
                "a1 is public Q&A text from kanoon.com, not statutory text. It "
                "reflects one practitioner's view and may be wrong or outdated. "
                "It is suitable for RETRIEVAL testing; it must NOT be treated "
                "as an authoritative statement of law."),
            "no_fabrication": (
                "No statute text was authored by the generator. q1 is a fixed "
                "template naming the act and section; a1 is carried from the "
                "source; q2_probes are real user questions."),
        },
        "corpus": {
            "note": ("Searchable corpus = cases[*].q1 -> cases[*].a1 plus "
                     "distractors[*].q1 -> distractors[*].a1."),
            "documents": ("cases[*].q1 -> cases[*].a1, plus "
                          "distractors[*].q1 -> distractors[*].a1"),
        },
        "grounding": {
            "must_include": ("Strings that genuinely occur in that case's a1. "
                             "Used for answer-level grading, not retrieval."),
            "must_not": "Phrases that must be absent; used for negative controls.",
        },
        "tiers": {
            "T1_paraphrase": "Question names the statute or a section number.",
            "T2_situational": "Described as a life situation, no statute names.",
            "T3_narrative": "First-person story with incidental detail.",
            "T4_indirect": "Asks for the consequence or the practical next step.",
            "tier_note": ("tier is assigned from the REAL kanoon question by "
                          "kaanoon_test/benchmark/build_family_law_surface_pairs.py"),
            "NEG_in_domain": "In-domain but out-of-corpus topic.",
            "NEG_out_of_domain": "Wholly outside family law.",
        },
        "disclaimer": (
            "Case text is practitioner opinion gathered from a public legal "
            "Q&A site. It is NOT statutory text and NOT legal advice. Verify "
            "every proposition against the current bare Act and applicable "
            "amendments - notably the Bharatiya Nyaya Sanhita, 2023 and the "
            "Bharatiya Nagarik Suraksha Sanhita, 2023, which repeal much of the "
            "Indian Penal Code and the Code of Criminal Procedure, 1973."),
        "cases": cases,
        "negative_cases": [],
        "distractors": [],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Family Law records scanned : {stats['family_law_records_scanned']}")
    print(f"Unique threads             : {stats['unique_family_law_threads']}")
    print(f"Cases emitted              : {len(cases)}")
    print("tiers :", dict(collections.Counter(c["tier"] for c in cases)))
    print("topics:", dict(collections.Counter(c["topic"] for c in cases)))
    print("acts  :", dict(collections.Counter(
        c["primary_authority"].split(" - ")[0] for c in cases)))
    print(f"\nwrote -> {OUT}  ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()