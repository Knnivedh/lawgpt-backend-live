"""
Offline comparison of embedding models and rerankers on the version-2
retrieval set. Everything runs on this machine: no Hugging Face Inference or
Milvus calls (models are downloaded once).

    cd backend
    uv run --no-project --python 3.12 --with sentence-transformers \\
        evaluation/retrieval_eval/compare_models_offline.py [embed] [rerank]

It re-embeds the corpus chunks with each embedding model, ranks documents the
way the app does (best chunk per document; statutes on the same subject count
once) and scores against the gold labels. Rerankers re-order the top
candidates of keyword + InLegal-SBERT search.

Needs the translations cached by run_eval.py --translate-only. Results are
written to evaluation/results/v2_retrieval_models/.
"""

import csv
import gc
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
sys.path.insert(0, str(BACKEND))

from corpus_curation import EXCLUDED_PARENT_IDS, subject_key  # noqa: E402
from keyword_search import KeywordIndex  # noqa: E402

OUT = BACKEND / "evaluation" / "results" / "v2_retrieval_models"
VECTORS = BACKEND / "data" / "v2" / "experiments"
TRANSLATION_KEY = "tr:ollama:gemma4:31b-cloud"
CASES, LAWS = "family_law", "family_law_2"

EMBEDDERS = {
    "InLegal-SBERT (current)": dict(name="bhavyagiri/InLegal-Sbert", query="", passage="", multilingual=False),
    "bge-small-en-v1.5": dict(name="BAAI/bge-small-en-v1.5", passage="", multilingual=False,
                              query="Represent this sentence for searching relevant passages: "),
    "multilingual-e5-base": dict(name="intfloat/multilingual-e5-base", query="query: ", passage="passage: ", multilingual=True),
    "bge-m3": dict(name="BAAI/bge-m3", query="", passage="", multilingual=True, batch=4),
}
RERANKERS = {
    "ms-marco-MiniLM-L-6-v2 (English)": dict(name="cross-encoder/ms-marco-MiniLM-L-6-v2", multilingual=False),
    "mmarco-mMiniLMv2-L12 (multilingual)": dict(name="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", multilingual=True),
    "bge-reranker-base": dict(name="BAAI/bge-reranker-base", multilingual=False),
    # BAAI/bge-reranker-v2-m3 and the bge-m3 embedder (both 568M parameters) need more than
    # the 8 GB this was run on: the machine swapped and made no progress.
}


def load_corpus():
    children, parents = [], {}
    for category, name in ((CASES, "family_law_chunks.json"), (LAWS, "family_law_2_chunks.json")):
        for item in json.loads((BACKEND / "data" / "v2" / "chunked" / name).read_text(encoding="utf-8")):
            meta = item["metadata"]
            if meta["parent_id"] in EXCLUDED_PARENT_IDS:
                continue
            if meta["is_parent"]:
                parents[meta["parent_id"]] = (category, meta["title"], item["content"])
            else:
                children.append((category, meta["parent_id"], f"{meta['title']}\n{item['content']}"[:2400], meta["chunk_id"]))
    return children, parents


def load_queries():
    cache = json.loads((HERE / ".api_cache.json").read_text())
    translations = cache[TRANSLATION_KEY]
    queries = []
    for row in csv.DictReader(open(HERE / "golden_dataset_v2.csv", encoding="utf-8")):
        english = row["query"] if row["language"] == "English" else translations.get(row["query"], row["query"])
        ids = lambda cell: [int(x) for x in cell.split(" | ") if x.strip()]
        queries.append(dict(id=row["id"], language=row["language"], original=row["query"], english=english,
                            gold_case=set(ids(row["gold_case_parent_ids"])),
                            gold_law={subject_key(p) for p in ids(row["gold_law_parent_ids"])}))
    return queries


def free_memory():
    """Release what the last model held; the GPU allocator keeps it otherwise and an 8 GB machine starts swapping."""
    import torch
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()


def unique(sequence, limit=60):
    out = []
    for x in sequence:
        if x not in out:
            out.append(x)
            if len(out) >= limit:
                break
    return out


def fuse(rankings, weights, k=60, depth=20):
    scores = Counter()
    for ranking, weight in zip(rankings, weights):
        for rank, doc in enumerate(ranking[:depth], start=1):
            scores[doc] += weight / (k + rank)
    return [doc for doc, _ in scores.most_common()]


class Scorer:
    def __init__(self, queries):
        self.queries = queries
        self.rows = []

    def add(self, method, text_kind, case_rankings, law_rankings):
        hit = lambda gold, ranking, k: int(bool(gold & set(ranking[:k])))
        groups = {"all": self.queries, "English": [q for q in self.queries if q["language"] == "English"],
                  "other languages": [q for q in self.queries if q["language"] != "English"]}
        record = {"method": method, "queries": text_kind}
        for label, group in groups.items():
            cases = [q for q in group if q["gold_case"]]
            laws = [q for q in group if q["gold_law"]]
            record[label] = {
                "case_hit@5": round(statistics.mean(hit(q["gold_case"], case_rankings[q["id"]], 5) for q in cases), 2),
                "case_recall@5": round(statistics.mean(len(q["gold_case"] & set(case_rankings[q["id"]][:5])) / len(q["gold_case"]) for q in cases), 2),
                "law_hit@3": round(statistics.mean(hit(q["gold_law"], law_rankings[q["id"]], 3) for q in laws), 2),
                "law_hit@5": round(statistics.mean(hit(q["gold_law"], law_rankings[q["id"]], 5) for q in laws), 2),
            }
        self.rows.append(record)
        a = record["all"]
        print(f"{method:44s} {text_kind:9s} cases@5 {a['case_hit@5']:.2f} (recall {a['case_recall@5']:.2f})  "
              f"statutes@3 {a['law_hit@3']:.2f} @5 {a['law_hit@5']:.2f}  | English {record['English']['case_hit@5']:.2f}/"
              f"{record['English']['law_hit@5']:.2f}  others {record['other languages']['case_hit@5']:.2f}/"
              f"{record['other languages']['law_hit@5']:.2f}", flush=True)


def keyword_rankings(queries, parents):
    index = {CASES: KeywordIndex(), LAWS: KeywordIndex()}
    for pid, (category, title, content) in parents.items():
        index[category].add(pid, title, content, category)
    for i in index.values():
        i.finalize()
    cases = {q["id"]: [p for p, _ in index[CASES].search(q["english"], 50)] for q in queries}
    laws = {q["id"]: unique(subject_key(p) for p, _ in index[LAWS].search(q["english"], 50)) for q in queries}
    return cases, laws


def dense_rankings(model_key, spec, children, queries, text_kind):
    from sentence_transformers import SentenceTransformer
    VECTORS.mkdir(parents=True, exist_ok=True)
    slug = spec["name"].replace("/", "__")
    model = SentenceTransformer(spec["name"])
    model.max_seq_length = min(512, model.max_seq_length or 512)
    path = VECTORS / f"{slug}.npy"
    if path.exists():
        vectors = np.load(path)
    elif spec["name"] == "bhavyagiri/InLegal-Sbert":
        # the index was built with this model: reuse those chunk vectors
        by_chunk = {}
        for name in ("family_law_embeddings.jsonl", "family_law_2_embeddings.jsonl"):
            with open(BACKEND / "data" / "v2" / "embeddings" / name, encoding="utf-8") as f:
                for line in f:
                    record = json.loads(line)
                    if not record["metadata"]["is_parent"]:
                        by_chunk[record["metadata"]["chunk_id"]] = np.asarray(record["embedding"], dtype=np.float32)
        vectors = np.vstack([by_chunk[c[3]] for c in children])
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        np.save(path, vectors.astype(np.float16))
        print(f"  reused {len(children)} stored chunk vectors for {spec['name']}", flush=True)
    else:
        start, parts = time.time(), []
        for offset in range(0, len(children), 1000):
            parts.append(model.encode([spec["passage"] + c[2] for c in children[offset:offset + 1000]], batch_size=spec.get("batch", 8),
                                      normalize_embeddings=True, show_progress_bar=False).astype(np.float16))
            free_memory()
            done = min(offset + 1000, len(children))
            left = (time.time() - start) / done * (len(children) - done)
            print(f"  {spec['name']}: {done}/{len(children)} chunks, about {left / 60:.0f} min left", flush=True)
        vectors = np.vstack(parts)
        np.save(path, vectors)
    vectors = vectors.astype(np.float32)
    q_vectors = model.encode([spec["query"] + q[text_kind] for q in queries], batch_size=8,
                             normalize_embeddings=True, show_progress_bar=False)
    del model
    free_memory()
    category = np.array([c[0] for c in children])
    parent = np.array([c[1] for c in children])
    cases, laws = {}, {}
    for q, vector in zip(queries, q_vectors):
        scores = vectors @ vector
        for pool, target, key in ((CASES, cases, lambda p: p), (LAWS, laws, subject_key)):
            members = np.where(category == pool)[0]
            order = members[np.argsort(-scores[members])[:400]]
            target[q["id"]] = unique(key(int(parent[i])) for i in order)
    return cases, laws


def run_embedders(scorer, children, parents, queries, store):
    bm25_cases, bm25_laws = keyword_rankings(queries, parents)
    store["bm25"] = (bm25_cases, bm25_laws)
    scorer.add("Keyword search (BM25) alone", "english", bm25_cases, bm25_laws)
    for key, spec in EMBEDDERS.items():
        for text_kind in ["english"] + (["original"] if spec["multilingual"] else []):
            cases, laws = dense_rankings(key, spec, children, queries, text_kind)
            store[(key, text_kind)] = (cases, laws)
            scorer.add(f"{key}: vector alone", text_kind, cases, laws)
            for weight in (1, 2):
                scorer.add(f"{key}: vector + keyword x{weight}", text_kind,
                           {q["id"]: fuse([cases[q["id"]], bm25_cases[q["id"]]], [1, weight]) for q in queries},
                           {q["id"]: fuse([laws[q["id"]], bm25_laws[q["id"]]], [1, weight]) for q in queries})


def run_rerankers(scorer, parents, queries, store, base_key="InLegal-SBERT (current)"):
    from sentence_transformers import CrossEncoder
    bm25_cases, bm25_laws = store["bm25"]
    dense_cases, dense_laws = store[(base_key, "english")]
    scorer.add(f"No reranker: {base_key} + keyword x2", "english",
               {q["id"]: fuse([dense_cases[q["id"]], bm25_cases[q["id"]]], [1, 2]) for q in queries},
               {q["id"]: fuse([dense_laws[q["id"]], bm25_laws[q["id"]]], [1, 2]) for q in queries})
    # statutes are ranked by subject; rerank one representative document per subject
    representative = {}
    for pid, (category, _, _) in parents.items():
        if category == LAWS:
            representative.setdefault(subject_key(pid), pid)
    text_of = lambda pid: f"{parents[pid][1]}\n{parents[pid][2][:1500]}"
    candidates = {q["id"]: (unique(bm25_cases[q["id"]][:20] + dense_cases[q["id"]][:20], 40),
                            unique(bm25_laws[q["id"]][:15] + dense_laws[q["id"]][:15], 30)) for q in queries}
    for key, spec in RERANKERS.items():
        for text_kind in ["english"] + (["original"] if spec["multilingual"] else []):
            start = time.time()
            model = CrossEncoder(spec["name"], max_length=384)
            cases, laws = {}, {}
            for number, q in enumerate(queries):
                if number and number % 25 == 0:
                    free_memory()
                    print(f"  {key}: {number}/{len(queries)} questions, about "
                          f"{(time.time() - start) / number * (len(queries) - number) / 60:.0f} min left", flush=True)
                case_ids, law_keys = candidates[q["id"]]
                pairs = [(q[text_kind], text_of(p)) for p in case_ids] + [(q[text_kind], text_of(representative[k])) for k in law_keys]
                scores = model.predict(pairs, batch_size=8, show_progress_bar=False)
                case_scores, law_scores = scores[:len(case_ids)], scores[len(case_ids):]
                cases[q["id"]] = [case_ids[i] for i in np.argsort(-case_scores)]
                laws[q["id"]] = [law_keys[i] for i in np.argsort(-law_scores)]
            del model
            free_memory()
            scorer.add(f"Reranker {key} over keyword + {base_key.split()[0]}", text_kind, cases, laws)
            print(f"  reranked in {time.time() - start:.0f}s ({sum(len(a) + len(b) for a, b in candidates.values())} pairs)", flush=True)


def main():
    only = [x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith("only=")]
    # candidates=<embedder> picks whose results the rerankers re-order; rerankers=<a,b> limits which run
    base = next((x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith("candidates=")), "InLegal")
    base_key = next(k for k in EMBEDDERS if base in k)
    wanted = next((x.split("=", 1)[1].split(",") for x in sys.argv[1:] if x.startswith("rerankers=")), None)
    if wanted:
        for key in [k for k in RERANKERS if not any(w in k for w in wanted)]:
            del RERANKERS[key]
    steps = {x for x in sys.argv[1:] if "=" not in x} or {"embed", "rerank"}
    if only:  # one model per process keeps memory low: only=bge-m3
        for key in [k for k in EMBEDDERS if not any(o in k for o in only)]:
            del EMBEDDERS[key]
    children, parents = load_corpus()
    queries = load_queries()
    print(f"{len(children)} chunks, {len(parents)} documents, {len(queries)} queries", flush=True)
    scorer, store = Scorer(queries), {}
    if "embed" in steps:
        run_embedders(scorer, children, parents, queries, store)
    else:
        store["bm25"] = keyword_rankings(queries, parents)
        store[(base_key, "english")] = dense_rankings(base_key, EMBEDDERS[base_key], children, queries, "english")
    if "rerank" in steps:
        run_rerankers(scorer, parents, queries, store, base_key)
    OUT.mkdir(parents=True, exist_ok=True)
    name = "results_" + "_".join(sorted(steps) + only + ([base] if base != "InLegal" else [])) + ".json"
    (OUT / name).write_text(json.dumps(scorer.rows, indent=1), encoding="utf-8")
    print(f"saved {OUT / name}")


if __name__ == "__main__":
    main()
