"""
Offline check: does adding the facts collected in follow-up rounds to the
search text improve retrieval? Uses the stored InLegal-SBERT chunk vectors
and BM25; no API calls.

    cd backend
    uv run --no-project --python 3.12 --with sentence-transformers \
        evaluation/retrieval_eval/facts_in_query_offline.py

Facts come from generator_eval/golden_dataset_v2.csv (info_collected), which
lists what the first message says plus what follow-ups would add.
"""

import csv
import json
import statistics
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compare_models_offline as base  # noqa: E402

children, parents = base.load_corpus()
queries = base.load_queries()
facts = {r["id"]: r["info_collected"] for r in csv.DictReader(open(base.BACKEND / "evaluation" / "generator_eval" / "golden_dataset_v2.csv", encoding="utf-8"))}
rubric_extra = {}
sys.path.insert(0, str(base.BACKEND / "evaluation" / "scenario_bank"))
from rubrics_parallel import RUBRICS as A  # noqa: E402
from rubrics_specific import RUBRICS as B  # noqa: E402
extra = {sid: r["extra"] for sid, r in {**A, **B}.items()}


def sentence(cell):
    """'religion: Hindu | children: none' -> 'Religion: Hindu. Children: none.'"""
    return " ".join(f"{k.replace('_', ' ').capitalize()}: {v}." for k, v in (p.split(": ", 1) for p in cell.split(" | ") if ": " in p))


def religion(cell):
    for part in cell.split(" | "):
        if part.startswith("religion:"):
            return part.split(": ", 1)[1]
    return ""


variants = {
    "first message only (what the app searches now)": lambda q: q["english"],
    "first message + all collected facts": lambda q: q["english"] + "\n" + sentence(facts[q["id"]]),
    "first message + facts from follow-ups only": lambda q: q["english"] + "\n" + sentence(extra[q["id"].split("__")[0]]),
    "first message + religion only": lambda q: q["english"] + (f"\nReligion: {religion(facts[q['id']])}." if religion(facts[q["id"]]) else ""),
}

vectors = np.load(base.VECTORS / "bhavyagiri__InLegal-Sbert.npy").astype(np.float32)
category = np.array([c[0] for c in children])
parent = np.array([c[1] for c in children])
model = SentenceTransformer("bhavyagiri/InLegal-Sbert")
index = {base.CASES: base.KeywordIndex(), base.LAWS: base.KeywordIndex()}
for pid, (cat, title, content) in parents.items():
    index[cat].add(pid, title, content, cat)
for i in index.values():
    i.finalize()

rows = []
for name, build in variants.items():
    texts = [build(q) for q in queries]
    q_vectors = model.encode(texts, batch_size=8, normalize_embeddings=True, show_progress_bar=False)
    dense_c, dense_l, kw_c, kw_l = {}, {}, {}, {}
    for q, text, vector in zip(queries, texts, q_vectors):
        scores = vectors @ vector
        for pool, target, key in ((base.CASES, dense_c, lambda p: p), (base.LAWS, dense_l, base.subject_key)):
            members = np.where(category == pool)[0]
            target[q["id"]] = base.unique(key(int(parent[i])) for i in members[np.argsort(-scores[members])[:400]])
        kw_c[q["id"]] = [p for p, _ in index[base.CASES].search(text, 50)]
        kw_l[q["id"]] = base.unique(base.subject_key(p) for p, _ in index[base.LAWS].search(text, 50))
    methods = {"vector": (dense_c, dense_l), "keyword": (kw_c, kw_l),
               "vector + keyword x2": ({k: base.fuse([dense_c[k], kw_c[k]], [1, 2]) for k in dense_c},
                                       {k: base.fuse([dense_l[k], kw_l[k]], [1, 2]) for k in dense_l})}
    for method, (cases, laws) in methods.items():
        with_case = [q for q in queries if q["gold_case"]]
        with_law = [q for q in queries if q["gold_law"]]
        hit = lambda gold, ranking, k: int(bool(gold & set(ranking[:k])))
        row = {"search text": name, "method": method,
               "cases@5": round(statistics.mean(hit(q["gold_case"], cases[q["id"]], 5) for q in with_case), 2),
               "statutes@3": round(statistics.mean(hit(q["gold_law"], laws[q["id"]], 3) for q in with_law), 2),
               "statutes@5": round(statistics.mean(hit(q["gold_law"], laws[q["id"]], 5) for q in with_law), 2)}
        rows.append(row)
        print(f"{name:48s} {method:20s} cases@5 {row['cases@5']:.2f}  statutes@3 {row['statutes@3']:.2f}  @5 {row['statutes@5']:.2f}", flush=True)

base.OUT.mkdir(parents=True, exist_ok=True)
(base.OUT / "results_facts_in_query.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
