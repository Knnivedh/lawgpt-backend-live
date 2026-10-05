"""
Perturbation benchmark for citation_guard.py. No model calls.

For a sample of corpus documents, take sentences that cite something, and:
  clean         keep the sentence as written            -> must NOT be flagged
  section-swap  change a section number to one the document never mentions
  act-swap      change the act to one the document never mentions
  pair-swap     keep the section, change the act to another act the document
                DOES mention, where the document's structured citation list
                says that section belongs to the original act
  case-insert   add an invented case name
  hindi-*       the same checks on templated Hindi sentences

Labels come from how each item is constructed and from the document's
structured citation metadata, not from the guard's own decisions.

    cd backend && python evaluation/citation_guard_eval/run_benchmark.py

Writes benchmark.jsonl and report.md next to this file.
"""

import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
sys.path.insert(0, str(BACKEND))

from citation_guard import (  # noqa: E402
    _CASE_RE, _KNOWN_ACTS, _SECTION_RE, _STRUCTURED_CITATION_RE, _Context,
    _known_act_mentions, _normalize, find_issues, split_sentences,
)

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 7
DOCS_SAMPLED = 600
MAX_SENTENCES_PER_DOC = 3

FAKE_SECTIONS = ["7", "21", "34", "77", "112", "151", "204", "317", "420A", "88", "63", "145", "239", "301"]
FAKE_PARTIES = [("Ramesh Kumar Bansal", "Sunita Devi Bansal"), ("Harpreet Gill", "Manjot Gill"),
                ("Venkatesh Iyer", "Lakshmi Iyer"), ("Arjun Mehta", "Kavita Mehta"),
                ("Imran Qureshi", "Shabnam Qureshi"), ("Deepak Nair", "Anjali Nair")]
HINDI_ACTS = {
    "Hindu Marriage Act": "हिंदू विवाह अधिनियम",
    "Indian Penal Code": "भारतीय दंड संहिता",
    "Code of Criminal Procedure": "दंड प्रक्रिया संहिता",
    "Protection of Women from Domestic Violence Act": "घरेलू हिंसा अधिनियम",
    "Hindu Succession Act": "हिंदू उत्तराधिकार अधिनियम",
    "Special Marriage Act": "विशेष विवाह अधिनियम",
    "Dowry Prohibition Act": "दहेज निषेध अधिनियम",
}
HINDI_TEMPLATES = ["{act} की धारा {n} के तहत कार्रवाई की जा सकती है।",
                   "आप {act} की धारा {n} के अंतर्गत आवेदन कर सकते हैं।"]
EXPECTED_KINDS = {"section-swap": {"section"}, "act-swap": {"act", "pair"}, "pair-swap": {"pair"},
                  "case-insert": {"case"}, "hindi-section-swap": {"section"}, "hindi-act-swap": {"act", "pair"}}


def load_documents():
    docs = []
    for name in ("family_law_chunks.json", "family_law_2_chunks.json"):
        for row in json.load(open(BACKEND / "data" / "v2" / "chunked" / name, encoding="utf-8")):
            if row["metadata"]["is_parent"]:
                docs.append({"id": row["metadata"]["parent_id"], "text": row["content"],
                             "citations": row["metadata"]["citations"] or []})
    return docs


def structured_pairs(citations):
    """{section number: set of acts} from the document's structured citation list."""
    pairs = defaultdict(set)
    for item in citations:
        m = _STRUCTURED_CITATION_RE.match(_normalize(str(item)))
        if m:
            for act in _known_act_mentions(m.group(2)):
                pairs[m.group(1).upper()].add(act.value)
    return pairs


def build_items(doc, rng):
    context = _Context(doc["text"], doc["citations"])
    pairs = structured_pairs(doc["citations"])
    text_numbers = set(context.section_acts) | set(context.listed_acts)
    absent_acts = sorted(set(_KNOWN_ACTS) - context.known_acts)
    items = []

    def add(kind, sentence, **extra):
        items.append({"doc_id": doc["id"], "type": kind, "sentence": sentence, **extra})

    sentences = [s.strip() for line in doc["text"].split("\n") for s in split_sentences(line)]
    citing = [s for s in sentences if 30 <= len(s) <= 400
              and (_SECTION_RE.search(s) or _known_act_mentions(s) or _CASE_RE.search(s))]
    for sentence in rng.sample(citing, min(MAX_SENTENCES_PER_DOC, len(citing))):
        add("clean", sentence)

        section = _SECTION_RE.search(sentence)
        acts = _known_act_mentions(sentence)
        fake = next((n for n in rng.sample(FAKE_SECTIONS, len(FAKE_SECTIONS)) if n not in text_numbers), None)
        if section and fake:
            number = re.search(r"\d+[A-Za-z]?", section.group(1))
            start = section.start(1) + number.start()
            add("section-swap", sentence[:start] + fake + sentence[start + len(number.group()):], changed_to=fake)

        if acts and absent_acts:
            act, new_act = acts[0], rng.choice(absent_acts)
            add("act-swap", sentence[:act.start] + new_act + sentence[act.end:], changed_to=new_act)

        if section and acts:
            number = re.search(r"\d+[A-Za-z]?", section.group(1)).group().upper()
            act = min(acts, key=lambda a: abs(a.start - section.end()))
            # Ground truth from metadata: this section is listed under the original act only.
            if pairs.get(number) == {act.value}:
                others = sorted(a for a in context.known_acts if a != act.value)
                if others:
                    new_act = rng.choice(others)
                    add("pair-swap", sentence[:act.start] + new_act + sentence[act.end:], changed_to=new_act)

        left, right = rng.choice(FAKE_PARTIES)
        if not _CASE_RE.search(sentence):
            add("case-insert", f"As held in {left} v. {right}, {sentence[0].lower()}{sentence[1:]}",
                changed_to=f"{left} v. {right}")

    # Templated Hindi sentences from the structured citation list.
    hindi_pairs = [(n, a) for n, acts_ in pairs.items() for a in acts_ if a in HINDI_ACTS]
    for number, act in rng.sample(hindi_pairs, min(1, len(hindi_pairs))):
        template = rng.choice(HINDI_TEMPLATES)
        add("hindi-clean", template.format(act=HINDI_ACTS[act], n=number))
        fake = next((n for n in rng.sample(FAKE_SECTIONS, len(FAKE_SECTIONS)) if n not in text_numbers), None)
        if fake:
            add("hindi-section-swap", template.format(act=HINDI_ACTS[act], n=fake), changed_to=fake)
        absent_hindi = [a for a in HINDI_ACTS if a not in context.known_acts]
        if absent_hindi:
            new_act = rng.choice(absent_hindi)
            add("hindi-act-swap", template.format(act=HINDI_ACTS[new_act], n=number), changed_to=new_act)

    for item in items:
        item["issues"] = find_issues(item["sentence"], context)
    return items


def main():
    rng = random.Random(SEED)
    docs = load_documents()
    sample = rng.sample(docs, min(DOCS_SAMPLED, len(docs)))
    items = [item for doc in sample for item in build_items(doc, rng)]

    with open(HERE / (f"benchmark_seed{SEED}.jsonl" if len(sys.argv) > 1 else "benchmark.jsonl"), "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    by_type = defaultdict(list)
    for item in items:
        by_type[item["type"]].append(item)

    clean = by_type["clean"] + by_type["hindi-clean"]
    false_alarms = [i for i in clean if i["issues"]]
    false_alarm_kinds = Counter(kind for i in false_alarms for kind, _ in i["issues"])

    lines = ["# Citation guard: perturbation benchmark", "",
             f"{len(sample)} corpus documents sampled (seed {SEED}), {len(items)} test sentences. No model calls.", "",
             "A perturbed sentence counts as detected when the guard raises an issue of the expected kind. "
             "A clean sentence counts as a false alarm when the guard raises any issue.", "",
             "## Detection (recall) by perturbation", "",
             "| Perturbation | Sentences | Detected | Recall |", "|---|---|---|---|"]
    true_positives = 0
    perturbed_total = 0
    for kind, expected in EXPECTED_KINDS.items():
        rows = by_type[kind]
        hits = sum(1 for i in rows if {k for k, _ in i["issues"]} & expected)
        true_positives += hits
        perturbed_total += len(rows)
        lines.append(f"| {kind} | {len(rows)} | {hits} | {hits / len(rows):.1%} |" if rows else f"| {kind} | 0 | - | - |")

    precision = true_positives / (true_positives + len(false_alarms)) if true_positives + len(false_alarms) else 0
    lines += ["", "## False alarms on unmodified sentences", "",
              "| Set | Sentences | False alarms | Rate |", "|---|---|---|---|"]
    for name in ("clean", "hindi-clean"):
        rows = by_type[name]
        bad = sum(1 for i in rows if i["issues"])
        lines.append(f"| {name} | {len(rows)} | {bad} | {bad / len(rows):.1%} |" if rows else f"| {name} | 0 | - | - |")
    lines += ["", f"False alarms by kind: {dict(false_alarm_kinds) or 'none'}", "",
              "## Overall", "",
              f"- Recall over all perturbed sentences: {true_positives}/{perturbed_total} = {true_positives / perturbed_total:.1%}",
              f"- Precision (detections on perturbed sentences vs false alarms on clean ones): {precision:.1%}", "",
              "## What this benchmark does and does not show", "",
              "- Sentences are taken from the corpus documents themselves, so they are mostly English and "
              "closer to the sources than a model's paraphrased answer would be. Real model output is harder.",
              "- Sentences were selected with the guard's own extractors (a sentence must contain something "
              "it recognises as a citation), so citations the extractors miss entirely are not counted.",
              "- The Hindi rows are short templated sentences, not natural Hindi answers.",
              "- It measures detection of unsupported citations, not whether the law is stated correctly.", "",
              "## Examples of misses and false alarms", ""]
    for kind in EXPECTED_KINDS:
        misses = [i for i in by_type[kind] if not ({k for k, _ in i["issues"]} & EXPECTED_KINDS[kind])][:2]
        for i in misses:
            lines.append(f"- MISS ({kind}, changed to {i.get('changed_to')}): {i['sentence'][:220]}")
    for i in false_alarms[:6]:
        lines.append(f"- FALSE ALARM {i['issues']}: {i['sentence'][:220]}")

    (HERE / (f"report_seed{SEED}.md" if len(sys.argv) > 1 else "report.md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:30]))


if __name__ == "__main__":
    main()
