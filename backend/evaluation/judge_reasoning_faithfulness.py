"""
Extra check for the reasoning panel: for RELATED past cases, does the panel's
explanation describe the past case accurately?

The main harness only asks the judge about unrelated cases (over-claiming).
This script covers the other 130 rows per model, using the outputs already
saved by run_node_eval.py. No node calls are made.

    cd backend
    python evaluation/judge_reasoning_faithfulness.py v2_nodes_selfhosted v2_nodes_gemma4-e4b v2_nodes_qwen3-8b

Writes reasoning/faithful__<judge>.jsonl in each run folder and prints a table.
"""
import csv
import json
import sys
import time
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
import run_node_eval as h  # noqa: E402

h.JUDGE_MODEL, h.JUDGE_REASONING = "gpt-oss:120b-cloud", "medium"
TAG = "gpt-oss-120b-cloud"

rows = {r["id"]: r for r in csv.DictReader(open(EVAL / "reasoning_eval" / "golden_dataset_v2.csv", encoding="utf-8"))}
parents = {}
for item in json.loads((EVAL.parent / "data" / "v2" / "chunked" / "family_law_chunks.json").read_text(encoding="utf-8")):
    if item["metadata"]["is_parent"]:
        parents[item["metadata"]["parent_id"]] = item["content"]

for run in sys.argv[1:]:
    folder = EVAL / "results" / run / "reasoning"
    raw = h.read_jsonl(folder / "raw.jsonl")
    path = folder / f"faithful__{TAG}.jsonl"
    done = h.read_jsonl(path)
    for rid, row in rows.items():
        if row["expected_relevance"] != "high" or rid in done or rid not in raw or raw[rid]["output"]["used_fallback"]:
            continue
        out = raw[rid]["output"]
        # the panel is shown the first 1,000 characters of the past case
        prompt = (f"User's case: {row['case_summary']}\n\nA past case titled \"{row['precedent_title']}\". The text the system was shown:\n"
                  f"{parents[int(row['precedent_parent_id'])][:1000]}\n\n"
                  f"The system's explanation of how the past case relates to the user's case:\n"
                  f"Similarities: {json.dumps(out['matching_factors'], ensure_ascii=False)}\n"
                  f"Differences: {json.dumps(out['different_factors'], ensure_ascii=False)}\n"
                  f"How it influenced the answer: {out['how_it_influenced_response']}\n\nKeys:\n"
                  "\"accurate\": true if every statement the explanation makes about the PAST CASE is supported by the text shown "
                  "(statements about the user's case are judged against the user's case); false if it states something about the "
                  "past case that the text contradicts or does not contain.\n"
                  "\"unsupported\": list of the unsupported statements (empty if none).\n"
                  "\"specific\": true if at least one similarity is specific to these two cases, false if all are generic "
                  "(for example 'both are family disputes').")
        try:
            done[rid] = {"id": rid, "verdict": h.judge(prompt)}
            h.append_jsonl(path, done[rid])
        except Exception as e:
            print(f"[{run}] judge failed on {rid}: {str(e)[:120]}", flush=True)
        time.sleep(0.2)
    verdicts = [d["verdict"] for d in done.values()]
    by_lang = {}
    for rid, d in done.items():
        by_lang.setdefault(rows[rid]["language"], []).append(bool(d["verdict"].get("accurate")))
    print(f"{run}: related rows judged {len(verdicts)} | explanation accurate {sum(bool(v.get('accurate')) for v in verdicts)} "
          f"| has a specific similarity {sum(bool(v.get('specific')) for v in verdicts)} | accurate by language "
          + ", ".join(f"{k} {sum(v)}/{len(v)}" for k, v in sorted(by_lang.items())), flush=True)
