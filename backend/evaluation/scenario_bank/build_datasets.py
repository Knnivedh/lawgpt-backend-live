"""
Build the version-2 golden datasets from the scenario bank and check them.

    cd backend && python evaluation/scenario_bank/build_datasets.py

The bank (the *.json files next to this script) is the single source: every
node's dataset is derived from the same scenarios, so results can be compared
across nodes and across languages.

Split per dataset (200 rows): 150 "parallel" rows (30 scenarios written in all
five languages) + 50 "language-specific" rows (10 per language, written
natively and not translated).

Bank files:
  parallel_*.json, specific_*.json   the scenarios and their question texts
  labels_retrieval.py                relevant corpus documents per scenario
  followups.py                       one follow-up exchange per scenario
  revalidation_rounds.py             multi-round conversations
  rubrics_parallel.py, rubrics_specific.py   what a good answer must say
  reasoning_pairs.py                 reference answers and precedents

Writes golden_dataset_v2.csv (200 rows each) into query_analyzer_eval/,
retrieval_eval/, gather_info_eval/, revalidate_eval/, generator_eval/ and
reasoning_eval/.
"""

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL = HERE.parent
BACKEND = EVAL.parent
sys.path.insert(0, str(HERE))

import followups  # noqa: E402
import reasoning_pairs  # noqa: E402
import revalidation_rounds  # noqa: E402
from labels_retrieval import LABELS, THIN_POOLS  # noqa: E402
from rubrics_parallel import RUBRICS as RUBRICS_PARALLEL  # noqa: E402
from rubrics_specific import RUBRICS as RUBRICS_SPECIFIC  # noqa: E402

RUBRICS = {**RUBRICS_PARALLEL, **RUBRICS_SPECIFIC}

LANGUAGES = ["en", "hi", "hi-en", "ta", "kn"]
LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "hi-en": "Hinglish", "ta": "Tamil", "kn": "Kannada"}
SCRIPT_RANGES = {"hi": (0x0900, 0x097F), "ta": (0x0B80, 0x0BFF), "kn": (0x0C80, 0x0CFF)}
PRIVACY = "residential_address | phone_number | email | aadhaar_or_pan | bank_details | workplace_details"

# The analyzer set uses 24 of the 30 parallel legal scenarios plus the 6
# analyzer-only ones, and 8 of the 10 language-specific legal scenarios per
# language plus 2 analyzer-only ones. The other sets use all legal scenarios.
ANALYZER_PARALLEL_LEGAL = 24
ANALYZER_SPECIFIC_LEGAL = 8


def load_bank():
    scenarios = []
    for path in sorted(list(HERE.glob("parallel*.json")) + list(HERE.glob("specific*.json"))):
        scenarios.extend(json.loads(path.read_text(encoding="utf-8")))
    return scenarios


def script_share(text, language):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 1.0
    if language in SCRIPT_RANGES:
        low, high = SCRIPT_RANGES[language]
        return sum(low <= ord(c) <= high for c in letters) / len(letters)
    return sum(c.isascii() for c in letters) / len(letters)


def corpus_shingles(n=6):
    shingles = set()
    for name in ("family_law.json", "family_law_2.json"):
        path = BACKEND / "data" / "family_law_domain" / name
        if not path.exists():
            return None
        for item in json.loads(path.read_text(encoding="utf-8")):
            words = re.findall(r"[a-z0-9]+", (item.get("query-text") or "").lower())
            shingles.update(" ".join(words[i:i + n]) for i in range(len(words) - n + 1))
    return shingles


def validate(scenarios):
    problems = []
    ids = [s["id"] for s in scenarios]
    problems += [f"duplicate id {i}" for i, c in Counter(ids).items() if c > 1]

    texts = Counter()
    shingles = corpus_shingles()
    worst_overlap = (0.0, None)
    for s in scenarios:
        parallel = s["id"][0] in "PA"
        expected = LANGUAGES if parallel else [s.get("language")]
        if sorted(s["query"]) != sorted(expected):
            problems.append(f"{s['id']}: languages {sorted(s['query'])}, expected {sorted(expected)}")
        for language, text in s["query"].items():
            texts[text] += 1
            # Indic-script questions may quote a short English legal term in brackets,
            # which is a large share of a one-line question.
            threshold = 0.9 if language in ("en", "hi-en") else 0.6
            if s.get("style") == "asr-garbled":
                threshold = 0.5
            if script_share(text, language) < threshold:
                problems.append(f"{s['id']} [{language}]: only {script_share(text, language):.0%} in the expected script")
        for field in ("category", "intent", "confidence", "needs_clarification", "info_provided",
                      "must_ask", "acceptable_info_needed", "must_not_ask"):
            if field not in s["analyzer"]:
                problems.append(f"{s['id']}: analyzer.{field} missing")
        if s["analyzer"]["confidence"] not in ("high", "medium", "low"):
            problems.append(f"{s['id']}: bad confidence")
        # Copy check only for legal scenarios: those are used for retrieval, where a
        # question lifted from a corpus post would retrieve that post trivially.
        if shingles is not None and "en" in s["query"] and not s.get("analyzer_only"):
            words = re.findall(r"[a-z0-9]+", s["query"]["en"].lower())
            own = [" ".join(words[i:i + 6]) for i in range(len(words) - 5)]
            if own:
                share = sum(x in shingles for x in own) / len(own)
                if share > worst_overlap[0]:
                    worst_overlap = (share, s["id"])
                if share > 0.25:
                    problems.append(f"{s['id']}: {share:.0%} of its 6-word sequences appear in the corpus (copied?)")
    problems += [f"duplicate question text: {t[:60]}" for t, c in texts.items() if c > 1]
    return problems, worst_overlap, shingles is not None


def analyzer_rows(scenarios):
    by_id = {s["id"]: s for s in scenarios}
    selected = []
    parallel_legal = sorted(i for i in by_id if i.startswith("P"))[:ANALYZER_PARALLEL_LEGAL]
    parallel_extra = sorted(i for i in by_id if i.startswith("A"))
    for sid in parallel_legal + parallel_extra:
        selected += [(by_id[sid], language, "parallel") for language in LANGUAGES]
    for language in LANGUAGES:
        tag = language.replace("-", "")
        legal = sorted(i for i in by_id if i.startswith(f"L-{tag}-"))[:ANALYZER_SPECIFIC_LEGAL]
        extra = sorted(i for i in by_id if i.startswith(f"X-{tag}-"))
        selected += [(by_id[sid], language, "language-specific") for sid in legal + extra]

    rows = []
    for scenario, language, split in selected:
        a = scenario["analyzer"]
        must_not = " | ".join(x for x in (a["must_not_ask"], PRIVACY) if x)
        rows.append({
            "id": f"{scenario['id']}__{language}",
            "scenario_id": scenario["id"], "split": split,
            "language": LANGUAGE_NAMES[language], "category": a["category"], "style": scenario["style"],
            "role": scenario["role"], "user_gender": scenario["gender"], "source": scenario["source"],
            "user_query": scenario["query"][language],
            "expected_intent": a["intent"], "expected_confidence": a["confidence"],
            "expected_needs_clarification": a["needs_clarification"],
            "expected_info_provided": a["info_provided"], "must_ask": a["must_ask"],
            "acceptable_info_needed": a["acceptable_info_needed"], "must_not_ask": must_not,
        })
    return rows


def legal_selection(scenarios):
    """Every legal scenario with each language it exists in: 30 x 5 + 10 x 5 = 200."""
    selected = []
    for s in scenarios:
        if s["id"].startswith("P"):
            selected += [(s, language, "parallel") for language in LANGUAGES]
        elif s["id"].startswith("L-"):
            selected.append((s, s["language"], "language-specific"))
    return selected


def base(scenario, language, split):
    return {"id": f"{scenario['id']}__{language}", "scenario_id": scenario["id"], "split": split,
            "language": LANGUAGE_NAMES[language], "topic": scenario["topic"], "style": scenario["style"]}


def corpus_parents():
    parents = {}
    for name in ("family_law_chunks.json", "family_law_2_chunks.json"):
        path = BACKEND / "data" / "v2" / "chunked" / name
        if not path.exists():
            return None
        for item in json.loads(path.read_text(encoding="utf-8")):
            if item["metadata"]["is_parent"]:
                parents[item["metadata"]["parent_id"]] = (item["metadata"]["title"], item["content"])
    return parents


def retrieval_rows(scenarios, parents):
    def titles(ids):
        return " | ".join(parents[i][0] for i in ids) if parents else ""

    rows = []
    for scenario, language, split in legal_selection(scenarios):
        label = LABELS[scenario["id"]]
        seed = label["seed"]
        rows.append({
            **base(scenario, language, split), "query": scenario["query"][language],
            "gold_law_parent_ids": " | ".join(map(str, label["law"])), "gold_law_titles": titles(label["law"]),
            "gold_case_parent_ids": " | ".join(map(str, label["case"])), "gold_case_titles": titles(label["case"]),
            "seed_parent_id": "" if seed is None else seed, "seed_title": titles([seed]) if seed is not None else "",
            "statute_in_corpus": label["in_corpus"],
            "thin_pool": "yes" if scenario["id"] in THIN_POOLS else "no",
        })
    return rows


def gather_rows(scenarios):
    rows = []
    for scenario, language, split in legal_selection(scenarios):
        sid = scenario["id"]
        if sid in followups.PARALLEL:
            kind, field, replies, expected = followups.PARALLEL[sid]
            question, reply = followups.QUESTIONS[field][language], replies[language]
        else:
            kind, field, question, reply, expected = followups.SPECIFIC[sid]
            question = followups.QUESTIONS[question][language] if question in followups.QUESTIONS else question
        rows.append({
            **base(scenario, language, split), "category": kind, "field": field,
            "root_query": scenario["query"][language], "already_known": scenario["analyzer"]["info_provided"],
            "last_question": question, "user_response": reply, "expected_extraction": expected,
        })
    return rows


def revalidate_rows(scenarios):
    by_id = {s["id"]: s for s in scenarios}
    rows = []
    for sid, conversation in revalidation_rounds.ROUNDS.items():
        scenario = by_id[sid]
        languages = LANGUAGES if sid.startswith("P") else [scenario["language"]]
        split = "parallel" if sid.startswith("P") else "language-specific"
        for language in languages:
            facts = scenario["analyzer"]["info_provided"]
            for number, (added, converged, missing, note) in enumerate(conversation["rounds"], 1):
                facts = " | ".join(x for x in (facts, added) if x)
                rows.append({
                    "id": f"{sid}__{language}__r{number}", "scenario_id": sid, "split": split,
                    "language": LANGUAGE_NAMES[language], "round": number, "topic": scenario["topic"],
                    "root_query": scenario["query"][language], "info_collected": facts,
                    "expected_converged": converged, "acceptable_still_missing": missing,
                    "scope_creep_fields": conversation["creep"],
                    "must_not_ask": f"any key already in info_collected | {PRIVACY}", "notes": note,
                })
    return rows


def facts_of(scenario):
    return " | ".join(x for x in (scenario["analyzer"]["info_provided"], RUBRICS[scenario["id"]]["extra"]) if x)


def generator_rows(scenarios):
    rows = []
    for scenario, language, split in legal_selection(scenarios):
        rubric = RUBRICS[scenario["id"]]
        rows.append({
            **base(scenario, language, split), "role": scenario["role"], "user_gender": scenario["gender"],
            "expected_response_language": LANGUAGE_NAMES[language], "user_query": scenario["query"][language],
            "info_collected": facts_of(scenario), "must_cover": " | ".join(rubric["cover"]),
            "expected_statutes": rubric["statutes"], "must_not_claim": " | ".join(rubric["avoid"]),
            "statute_in_corpus": LABELS[scenario["id"]]["in_corpus"],
        })
    return rows


def reasoning_rows(scenarios, parents):
    by_id = {s["id"]: s for s in scenarios}
    rows = []
    pairs = [(sid, p, LANGUAGES, "parallel") for sid, p in reasoning_pairs.PARALLEL.items()]
    pairs += [(sid, p, [by_id[sid]["language"]], "language-specific") for sid, p in reasoning_pairs.SPECIFIC.items()]
    for sid, pair, languages, split in pairs:
        scenario = by_id[sid]
        summary = f"{scenario['role']} ({scenario['gender']}); question about {scenario['topic']}. Facts: {facts_of(scenario)}"
        for language in languages:
            reference = pair["reference"][language] if isinstance(pair["reference"], dict) else pair["reference"]
            for relevance, ids in (("high", pair["relevant"]), ("low", pair["irrelevant"])):
                for pid in ids:
                    title, content = parents[pid] if parents else ("", "")
                    if relevance == "high":
                        band = ">= 0.5"
                        why = f"The post \"{title}\" deals with the same issue ({scenario['topic']}); the panel may present it as a similar situation."
                    else:
                        band = "<= 0.3"
                        why = (f"The post \"{title}\" is about a different matter from {scenario['topic']}; "
                               "the panel should score it low and must not present it as support for the answer.")
                    rows.append({
                        "id": f"{sid}__{language}__{pid}", "scenario_id": sid, "split": split,
                        "language": LANGUAGE_NAMES[language], "topic": scenario["topic"],
                        "user_query": scenario["query"][language], "case_summary": summary,
                        "reference_response": reference, "precedent_parent_id": pid, "precedent_title": title,
                        "precedent_excerpt": " ".join(content[:400].split()),
                        "expected_relevance": relevance, "expected_usage_score_band": band, "rationale": why,
                    })
    return rows


def validate_layers(scenarios, parents):
    problems = []
    by_id = {s["id"]: s for s in scenarios}
    legal = [s["id"] for s in scenarios if s["id"][0] in "PL"]
    for name, table_ in (("retrieval labels", LABELS), ("rubrics", RUBRICS),
                         ("follow-ups", {**followups.PARALLEL, **followups.SPECIFIC})):
        missing, extra = set(legal) - set(table_), set(table_) - set(legal)
        if missing or extra:
            problems.append(f"{name}: missing {sorted(missing)}, unknown {sorted(extra)}")

    def check_text(where, text, language):
        threshold = 0.9 if language in ("en", "hi-en") else 0.6
        if script_share(text, language) < threshold:
            problems.append(f"{where} [{language}]: only {script_share(text, language):.0%} in the expected script")

    for field, texts in followups.QUESTIONS.items():
        for language in LANGUAGES:
            check_text(f"question {field}", texts[language], language)
    for sid, (kind, field, replies, expected) in followups.PARALLEL.items():
        if field not in followups.QUESTIONS:
            problems.append(f"{sid}: no question for field {field}")
        for language in LANGUAGES:
            check_text(f"{sid} reply", replies[language], language)
    for sid, (kind, field, question, reply, expected) in followups.SPECIFIC.items():
        language = by_id[sid]["language"]
        check_text(f"{sid} reply", reply, language)
        if question not in followups.QUESTIONS:
            check_text(f"{sid} question", question, language)
    for sid, pair in {**reasoning_pairs.PARALLEL, **reasoning_pairs.SPECIFIC}.items():
        references = pair["reference"] if isinstance(pair["reference"], dict) else {by_id[sid]["language"]: pair["reference"]}
        for language, text in references.items():
            # legal answers quote English act names and section numbers
            if script_share(text, language) < (0.9 if language in ("en", "hi-en") else 0.75):
                problems.append(f"{sid} reference [{language}]: only {script_share(text, language):.0%} in the expected script")
        if parents:
            problems += [f"{sid}: precedent {pid} not in the corpus" for pid in pair["relevant"] + pair["irrelevant"] if pid not in parents]
            gold = set(LABELS[sid]["case"]) | {LABELS[sid]["seed"]}
            problems += [f"{sid}: relevant precedent {pid} is not in its retrieval labels" for pid in pair["relevant"] if pid not in gold]
            problems += [f"{sid}: irrelevant precedent {pid} is in its retrieval labels" for pid in pair["irrelevant"] if pid in gold]
    if parents:
        for sid, label in LABELS.items():
            ids = label["law"] + label["case"] + ([label["seed"]] if label["seed"] is not None else [])
            problems += [f"{sid}: document {pid} not in the corpus" for pid in ids if pid not in parents]
    for sid, conversation in revalidation_rounds.ROUNDS.items():
        if sid not in by_id:
            problems.append(f"revalidation: unknown scenario {sid}")
        seen_yes = False
        for added, converged, missing, note in conversation["rounds"]:
            if converged == "yes":
                seen_yes = True
                if missing:
                    problems.append(f"{sid}: converged round still lists missing fields")
            elif seen_yes:
                problems.append(f"{sid}: goes back to 'no' after converging")
            elif not missing:
                problems.append(f"{sid}: non-converged round lists nothing to ask")
    return problems


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def table(rows, key):
    counts = Counter(r[key] for r in rows)
    return ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))


def main():
    scenarios = load_bank()
    ids = Counter(s["id"].split("-")[0] if s["id"][0] in "LX" else s["id"][0] for s in scenarios)
    print(f"Scenario bank: {len(scenarios)} scenarios "
          f"({ids['P']} parallel legal, {ids['A']} parallel analyzer-only, "
          f"{ids['L']} language-specific legal, {ids['X']} language-specific analyzer-only); "
          f"{sum(len(s['query']) for s in scenarios)} question texts")

    problems, worst, checked_corpus = validate(scenarios)
    if checked_corpus:
        print(f"Corpus overlap check: highest share of 6-word sequences found in the corpus = {worst[0]:.0%} ({worst[1]})")
    else:
        print("Corpus overlap check skipped: data/family_law_domain not found")
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("Checks passed: ids unique, all languages present, scripts match, no duplicate or copied questions")

    parents = corpus_parents()
    if parents is None:
        print("Corpus titles not found (data/v2/chunked): titles and excerpts left blank, id checks skipped")
    problems = validate_layers(scenarios, parents)
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("Layer checks passed: every legal scenario has labels, a follow-up and a rubric; scripts and corpus ids are valid")

    datasets = [
        ("query analyzer", "query_analyzer_eval", analyzer_rows(scenarios), ("split", "language", "category", "expected_confidence")),
        ("retriever", "retrieval_eval", retrieval_rows(scenarios, parents), ("split", "language", "statute_in_corpus", "thin_pool")),
        ("information gatherer", "gather_info_eval", gather_rows(scenarios), ("split", "language", "category")),
        ("revalidation", "revalidate_eval", revalidate_rows(scenarios), ("split", "language", "round", "expected_converged")),
        ("generator", "generator_eval", generator_rows(scenarios), ("split", "language", "user_gender", "statute_in_corpus")),
        ("reasoning panel", "reasoning_eval", reasoning_rows(scenarios, parents), ("split", "language", "expected_relevance")),
    ]
    for name, folder, rows, keys in datasets:
        if len(rows) != 200 or len({r["id"] for r in rows}) != 200:
            print(f"\nPROBLEM: {name} has {len(rows)} rows, {len({r['id'] for r in rows})} unique ids (expected 200)")
            sys.exit(1)
        out = EVAL / folder / "golden_dataset_v2.csv"
        write_csv(out, rows)
        print(f"\n{name}: {len(rows)} rows -> {out.relative_to(BACKEND)}")
        for key in keys:
            print(f"  by {key}: {table(rows, key)}")

if __name__ == "__main__":
    main()
