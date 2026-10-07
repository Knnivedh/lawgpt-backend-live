"""
score_retrieval.py ------ LAW-GPT retrieval benchmark, Task 2 (Phase 1).

Cold-opens a statute index directory with the PRODUCTION store class
(rag_system.core.hybrid_chroma_store.HybridChromaStore) and scores the
benchmark ground truth produced by gen_ground_truth.py.

Reports recall@5/10/20, MRR and nDCG@10, plus a per-stratum breakdown.

Identity is the COMPOSITE key (act, section_number) ------ never section_number
alone (plan decision AD3). Section 124 exists simultaneously in the Transfer
of Property Act 1882, Consumer Protection Act 2019 and BNS 2023; scoring on
the bare number would award credit to the wrong statute.

Usage
-----
    python score_retrieval.py --index <dir> --ground-truth ground_truth.json
    python score_retrieval.py --index <dir> -g ground_truth.json --k 5,10,20

Runs fully offline. No network calls.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# Windows consoles default to cp1252 and cannot encode the em-dash used in
# section banners. Force UTF-8 on both streams so the report never dies
# mid-print.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

# Import the key normalisers from the generator so both sides of the
# benchmark agree on identity by construction.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_ground_truth import (  # noqa: E402
    composite_key,
    normalise_act,
    normalise_section,
)

DEFAULT_REPO = Path(r"E:\LAW-GPT_new\azure_backend_stage")
DEFAULT_COLLECTION = "legal_db_statutes"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_GT = Path(__file__).resolve().parent / "ground_truth.json"
# Reliability bar from plan Task 4: the depth at which recall crosses the
# threshold where answers become reliable.
DEFAULT_BAR = 0.90


def load_store(index_dir, collection, embedding_model):
    """Cold-open the index exactly as production loads it."""
    repo = str(DEFAULT_REPO)
    if repo not in sys.path:
        sys.path.insert(0, repo)
    from rag_system.core.hybrid_chroma_store import HybridChromaStore

    return HybridChromaStore(
        persist_directory=str(index_dir),
        collection_name=collection,
        embedding_model=embedding_model,
    )


def result_key(doc):
    """Composite key of a retrieval hit, from its metadata."""
    meta = doc.get("metadata") or {}
    key = composite_key(meta.get("act", ""), meta.get("section_number", ""))
    return key


def evaluate(items, store, depths):
    """Run every question once at max depth; score the ranking at each depth."""
    max_k = max(depths)
    per_item = []
    for n, item in enumerate(items, 1):
        want = item["section_key"]
        hits = store.hybrid_search(item["question"], n_results=max_k)
        keys = [result_key(h) for h in hits]
        rank = None
        for i, key in enumerate(keys, 1):
            if key is not None and key == want:
                rank = i
                break
        per_item.append({
            "qid": item["qid"],
            "question": item["question"],
            "act": item["act"],
            "section_number": item["section_number"],
            "section_key": want,
            "section_type": item["section_type"],
            "length_bucket": item["length_bucket"],
            "rank": rank,
            "n_returned": len(hits),
            "top_keys": keys[:5],
        })
        if n % 25 == 0 or n == len(items):
            print("    ... %d/%d questions scored" % (n, len(items)), flush=True)
    return per_item


def metrics(per_item, depths):
    """recall@k, MRR and nDCG@10 from the recorded ranks."""
    n = len(per_item)
    out = {"n_queries": n}
    for k in depths:
        hit = sum(1 for r in per_item if r["rank"] and r["rank"] <= k)
        out["recall@%d" % k] = round(hit / n, 4) if n else 0.0
    rr = [1.0 / r["rank"] for r in per_item if r["rank"]]
    out["mrr"] = round(sum(rr) / n, 4) if n else 0.0
    gains = []
    for r in per_item:
        rank = r["rank"]
        if rank and rank <= 10:
            gains.append(1.0 / math.log2(rank + 1))
    out["ndcg@10"] = round(sum(gains) / n, 4) if n else 0.0
    out["hit_any"] = sum(1 for r in per_item if r["rank"])
    out["no_hit"] = sum(1 for r in per_item if not r["rank"])
    return out


def stratified(per_item, depths, field):
    """Per-stratum recall so a single mean cannot hide a collapsed act."""
    groups = defaultdict(list)
    for row in per_item:
        groups[row[field]].append(row)
    result = {}
    for name, rows in sorted(groups.items()):
        result[name] = metrics(rows, depths)
    return result


def failure_threshold(per_item, depths, bar=DEFAULT_BAR):
    """The retrieval depth at which recall first crosses the bar."""
    for k in depths:
        hit = sum(1 for r in per_item if r["rank"] and r["rank"] <= k)
        recall = hit / len(per_item) if per_item else 0.0
        if recall >= bar:
            return {"threshold_k": k, "recall": round(recall, 4), "bar": bar}
    return {"threshold_k": None, "recall": None, "bar": bar}
# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------
def print_scorecard(title, overall, depths, threshold):
    print("\n" + "=" * 68)
    print(title)
    print("=" * 68)
    print("  queries scored      : %d" % overall["n_queries"])
    row = "  "
    for k in depths:
        row += " recall@%-3d" % k
    print(row)
    row = "  "
    for k in depths:
        row += " %-11.4f" % overall["recall@%d" % k]
    print(row)
    print("  MRR                 : %.4f" % overall["mrr"])
    print("  nDCG@10             : %.4f" % overall["ndcg@10"])
    print("  hit / no-hit        : %d / %d" % (overall["hit_any"], overall["no_hit"]))
    if threshold["threshold_k"]:
        print("  FAILURE THRESHOLD   : k=%d reaches recall %.4f (bar %.0f%%)"
              % (threshold["threshold_k"], threshold["recall"],
                 threshold["bar"] * 100))
    else:
        print("  FAILURE THRESHOLD   : not reached at any measured k (bar %.0f%%)"
              % (threshold["bar"] * 100))


def print_strata(name, table, depths):
    print("\n  BY %s" % name)
    header = "    %-44s %4s" % ("stratum", "n")
    for k in depths:
        header += " %6s" % ("R@%d" % k)
    header += " %6s %6s" % ("MRR", "nDCG")
    print(header)
    for key in sorted(table, key=lambda k: (-table[k]["n_queries"], str(k))):
        m = table[key]
        line = "    %-44s %4d" % (str(key)[:44], m["n_queries"])
        for k in depths:
            line += " %6.3f" % m["recall@%d" % k]
        line += " %6.3f %6.3f" % (m["mrr"], m["ndcg@10"])
        print(line)


def parse_depths(text):
    depths = []
    for chunk in re.split(r"[,\s]+", str(text).strip()):
        if chunk:
            depths.append(int(chunk))
    if not depths:
        raise ValueError("no k values parsed")
    return sorted(set(depths))
def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Score statute retrieval against the benchmark ground truth.")
    ap.add_argument("--index", required=True,
                    help="Index directory to cold-open.")
    ap.add_argument("--ground-truth", "-g", default=str(DEFAULT_GT),
                    help="Ground-truth JSON from gen_ground_truth.py.")
    ap.add_argument("--k", default="5,10,20",
                    help="Comma-separated retrieval depths (default 5,10,20).")
    ap.add_argument("--collection", default=DEFAULT_COLLECTION,
                    help="Chroma collection name (default %s)." % DEFAULT_COLLECTION)
    ap.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL,
                    help="SentenceTransformer model name.")
    ap.add_argument("--label", default=None,
                    help="Name for this index in the output (default: folder name).")
    ap.add_argument("--bar", type=float, default=DEFAULT_BAR,
                    help="Recall bar for the failure threshold (default %.2f)."
                    % DEFAULT_BAR)
    ap.add_argument("--limit", type=int, default=None,
                    help="Score only the first N items (smoke testing).")
    ap.add_argument("--out", default=None,
                    help="Write the full JSON report to this path.")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    index_dir = Path(args.index)
    if not index_dir.is_dir():
        print("index dir not found: %s" % index_dir, file=sys.stderr)
        return 2
    gt_path = Path(args.ground_truth)
    if not gt_path.is_file():
        print("ground truth not found: %s" % gt_path, file=sys.stderr)
        return 2

    with open(gt_path, "r", encoding="utf-8") as fh:
        document = json.load(fh)
    items = document["items"]
    if args.limit:
        items = items[: args.limit]
    depths = parse_depths(args.k)
    label = args.label or index_dir.name

    print("=" * 68)
    print("LAW-GPT retrieval scoring (Task 2)")
    print("=" * 68)
    print("index       : %s" % index_dir)
    print("collection  : %s" % args.collection)
    print("ground truth: %s (%d items)" % (gt_path, len(items)))
    print("depths      : %s" % ", ".join(str(d) for d in depths))

    print("\nCold-opening index (model load ~25-40s)...", flush=True)
    started = time.time()
    store = load_store(index_dir, args.collection, args.embedding_model)
    info = store.get_collection_info()
    print("  collection docs : %d" % info["count"])
    print("  embedding dim  : %d" % info["embedding_dim"])
    print("  bm25 index     : %s" % ("present" if info["has_bm25"] else "ABSENT"))
    print("  load seconds   : %.1f" % (time.time() - started))

    if info["count"] == 0:
        print("ABORT: collection '%s' is empty in %s"
              % (args.collection, index_dir), file=sys.stderr)
        return 3

    print("\nScoring...", flush=True)
    started = time.time()
    per_item = evaluate(items, store, depths)
    elapsed = time.time() - started

    overall = metrics(per_item, depths)
    threshold = failure_threshold(per_item, depths, args.bar)
    by_type = stratified(per_item, depths, "section_type")
    by_act = stratified(per_item, depths, "act")
    by_length = stratified(per_item, depths, "length_bucket")

    print_scorecard("SCORECARD ------ %s" % label, overall, depths, threshold)
    print_strata("SECTION TYPE", by_type, depths)
    print_strata("ACT", by_act, depths)
    print_strata("LENGTH BUCKET", by_length, depths)
    print("\n  scoring seconds: %.1f" % elapsed)

    if args.out:
        report = {
            "label": label,
            "index": str(index_dir),
            "collection": args.collection,
            "collection_docs": info["count"],
            "embedding_dim": info["embedding_dim"],
            "has_bm25": info["has_bm25"],
            "depths": depths,
            "overall": overall,
            "failure_threshold": threshold,
            "by_section_type": by_type,
            "by_act": by_act,
            "by_length_bucket": by_length,
            "per_item": per_item,
        }
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        print("WROTE %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
