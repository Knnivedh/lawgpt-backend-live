"""
Pool candidate precedents for every legal scenario, for relevance labelling.

For each scenario, take the top results from two different search methods over
the forum posts (category family_law) of the rebuilt index:
  - BM25 keyword search over whole documents
  - vector search over chunk embeddings (local model, no API calls)
and write their union to candidates.json. A person (or the assistant) then reads
each candidate and marks it relevant or not; that judgement, not the search
ranking, becomes the gold label. Pooling from two methods avoids labels that
favour one of them.

Run from backend/ (sentence-transformers is not a project dependency):
    uv run --no-project --python 3.12 --with sentence-transformers --with numpy \
        python evaluation/scenario_bank/pool_candidates.py
"""

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
sys.path.insert(0, str(BACKEND))

from keyword_search import KeywordIndex  # noqa: E402

TOP_EACH = 6
CASE_FILE = "family_law"
MODEL = "bhavyagiri/InLegal-Sbert"


def load_scenarios():
    scenarios = []
    for path in sorted(HERE.glob("*.json")):
        if path.name in ("candidates.json",) or not path.name.startswith(("parallel", "specific")):
            continue
        scenarios.extend(json.loads(path.read_text(encoding="utf-8")))
    return [s for s in scenarios if not s.get("analyzer_only")]


def search_text(scenario):
    # English question where there is one; otherwise the English topic and intent.
    return " ".join(x for x in (scenario["query"].get("en", ""), scenario["topic"], scenario["analyzer"]["intent"]) if x)


def main():
    scenarios = load_scenarios()

    parents, index = {}, KeywordIndex()
    for row in json.load(open(BACKEND / "data" / "v2" / "chunked" / f"{CASE_FILE}_chunks.json", encoding="utf-8")):
        if row["metadata"]["is_parent"]:
            pid = row["metadata"]["parent_id"]
            parents[pid] = row
            index.add(pid, row["metadata"]["title"], row["content"], CASE_FILE)
    index.finalize()

    child_parent, vectors = [], []
    with open(BACKEND / "data" / "v2" / "embeddings" / f"{CASE_FILE}_embeddings.jsonl", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            if not record["metadata"]["is_parent"]:
                child_parent.append(record["metadata"]["parent_id"])
                vectors.append(np.asarray(record["embedding"], dtype=np.float32))
    matrix = np.vstack(vectors)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    del vectors

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL)
    texts = [search_text(s) for s in scenarios]
    queries = model.encode(texts, batch_size=8, show_progress_bar=False)
    queries = queries / np.linalg.norm(queries, axis=1, keepdims=True)

    out = {}
    for scenario, text, q in zip(scenarios, texts, queries):
        bm25 = [pid for pid, _ in index.search(text, TOP_EACH)]
        dense = []
        for i in np.argsort(-(matrix @ q))[:60]:
            if child_parent[i] not in dense:
                dense.append(child_parent[i])
            if len(dense) >= TOP_EACH:
                break
        candidates = []
        for pid in dict.fromkeys(bm25 + dense):
            row = parents[pid]
            candidates.append({
                "parent_id": pid,
                "title": row["metadata"]["title"],
                "snippet": " ".join(row["content"].split())[:230],
                "found_by": "both" if pid in bm25 and pid in dense else ("keyword" if pid in bm25 else "vector"),
            })
        out[scenario["id"]] = {"search_text": text, "candidates": candidates}

    (HERE / "candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    sizes = [len(v["candidates"]) for v in out.values()]
    print(f"{len(out)} scenarios, {sum(sizes)} candidates (average {sum(sizes) / len(sizes):.1f} per scenario)")


if __name__ == "__main__":
    main()
