"""
Offline check: search after every follow-up turn and merge the result lists,
instead of searching once. Uses stored InLegal-SBERT vectors and BM25; no API
calls. Run like facts_in_query_offline.py.

A conversation is simulated as: the first message, then one collected fact per
follow-up turn (the facts in rubrics_*.py "extra").
"""

import json
import statistics
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compare_models_offline as base  # noqa: E402

sys.path.insert(0, str(base.BACKEND / "evaluation" / "scenario_bank"))
from rubrics_parallel import RUBRICS as A  # noqa: E402
from rubrics_specific import RUBRICS as B  # noqa: E402

children, parents = base.load_corpus()
queries = base.load_queries()
extra = {sid: [p.split(": ", 1) for p in r["extra"].split(" | ") if ": " in p] for sid, r in {**A, **B}.items()}
say = lambda pair: f"{pair[0].replace('_', ' ').capitalize()}: {pair[1]}."

vectors = np.load(base.VECTORS / "bhavyagiri__InLegal-Sbert.npy").astype(np.float32)
category = np.array([c[0] for c in children])
parent = np.array([c[1] for c in children])
model = SentenceTransformer("bhavyagiri/InLegal-Sbert")
index = {base.CASES: base.KeywordIndex(), base.LAWS: base.KeywordIndex()}
for pid, (cat, title, content) in parents.items():
    index[cat].add(pid, title, content, cat)
for i in index.values():
    i.finalize()


def search(text):
    vector = model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
    scores = vectors @ vector
    out = {}
    for pool, key in ((base.CASES, lambda p: p), (base.LAWS, base.subject_key)):
        members = np.where(category == pool)[0]
        out[("vector", pool)] = base.unique(key(int(parent[i])) for i in members[np.argsort(-scores[members])[:400]])
        out[("keyword", pool)] = base.unique(key(p) for p, _ in index[pool].search(text, 50))
        out[("vector + keyword x2", pool)] = base.fuse([out[("vector", pool)], out[("keyword", pool)]], [1, 2])
    return out


plans = {
    "search once, first message (now)": lambda q, f: [q],
    "search once at the end, message + all follow-up facts": lambda q, f: [q + "\n" + " ".join(map(say, f))],
    "search at every turn with the text so far, merge": lambda q, f: [q + ("\n" + " ".join(map(say, f[:n])) if n else "") for n in range(len(f) + 1)],
    "search at every turn with message + that turn's fact, merge": lambda q, f: [q] + [q + "\n" + say(x) for x in f],
    "search at every turn with only that turn's reply, merge": lambda q, f: [q] + [say(x) for x in f],
}
rows, steps = [], []
for name, plan in plans.items():
    results = {}
    for q in queries:
        texts = plan(q["english"], extra[q["id"].split("__")[0]])
        steps.append(len(texts))
        per_step = [search(t) for t in texts]
        results[q["id"]] = {k: base.fuse([s[k] for s in per_step], [1] * len(per_step)) if len(per_step) > 1 else per_step[0][k]
                            for k in per_step[0]}
    for method in ("vector", "keyword", "vector + keyword x2"):
        hit = lambda gold, ranking, k: int(bool(gold & set(ranking[:k])))
        cases = [q for q in queries if q["gold_case"]]
        laws = [q for q in queries if q["gold_law"]]
        row = {"plan": name, "method": method,
               "cases@5": round(statistics.mean(hit(q["gold_case"], results[q["id"]][(method, base.CASES)], 5) for q in cases), 2),
               "statutes@3": round(statistics.mean(hit(q["gold_law"], results[q["id"]][(method, base.LAWS)], 3) for q in laws), 2),
               "statutes@5": round(statistics.mean(hit(q["gold_law"], results[q["id"]][(method, base.LAWS)], 5) for q in laws), 2)}
        rows.append(row)
        print(f"{name:60s} {method:20s} cases@5 {row['cases@5']:.2f}  statutes@3 {row['statutes@3']:.2f} @5 {row['statutes@5']:.2f}", flush=True)
print("mean searches per conversation when searching every turn:", round(statistics.mean(len(extra[q['id'].split('__')[0]]) + 1 for q in queries), 1))
(base.OUT / "results_search_each_step.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
