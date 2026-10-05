"""
Retrieval evaluation harness (deterministic checks only, no LLM judge).

Runs every query in golden_dataset.csv through nodes.retriever.retrieve_documents
and scores the results against the gold parent_ids.

    cd backend
    python evaluation/retrieval_eval/run_eval.py --label all-on --curation on --rewrite on --hybrid on
    python evaluation/retrieval_eval/run_eval.py --compare      # table of every label run so far

Each switch (--curation, --rewrite, --hybrid: on/off; --embed: english/search/both)
overrides the app setting for this run only; left out, the app's own setting is used.

Translations and query embeddings are cached in .api_cache.json next to this
file, so re-runs on the same queries make no model calls (only Milvus
searches). Translations are cached per translation model. Delete the cache to
force fresh calls, e.g. after changing the embedding model.

--translator ollama translates through Ollama (settings.ollama_translation_model)
instead of Hugging Face. To run without any Hugging Face call:

    python evaluation/retrieval_eval/run_eval.py --dataset golden_dataset_v2.csv --translator ollama --translate-only
    uv run --no-project --python 3.12 --with sentence-transformers evaluation/retrieval_eval/embed_queries_local.py
    python evaluation/retrieval_eval/run_eval.py --dataset golden_dataset_v2.csv --translator ollama --label <name>

Outputs go to evaluation/results/<date>_<git-sha>/retrieve/<label>/.
"""

import argparse
import csv
import json
import statistics
import subprocess
import time
import sys
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
sys.path.insert(0, str(BACKEND))

import dotenv  # noqa: E402

dotenv.load_dotenv(BACKEND / ".env")

import nodes.retriever as retriever  # noqa: E402
from lang_utils import detect_language, looks_like_hinglish  # noqa: E402
from translation_client import SearchQuery  # noqa: E402

CACHE_PATH = HERE / ".api_cache.json"

from corpus_curation import EXCLUDED_PARENT_IDS as OFF_TOPIC_LAW, subject_key  # noqa: E402


def install_cache(translation_key="tr2"):
    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    # "tr" = translations from the old prompt; "tr2" = Hugging Face translation model;
    # other translation models get a key of their own
    # query vectors: "emb" = InLegal-SBERT; any other embedding model gets a key of its own
    model = retriever.settings.embedding_model
    emb_key = "emb" if model == "bhavyagiri/InLegal-Sbert" else f"emb:{model}"
    for key in ("tr", "tr2", "prep", "emb", translation_key, emb_key):
        cache.setdefault(key, {})
    calls = Counter()
    translator = retriever.translator
    real_translate, real_prepare = translator.translate, translator.prepare_search
    real_embed = retriever.embedding_client.embed

    def translate(text):
        if text not in cache[translation_key]:
            cache[translation_key][text] = real_translate(text)
            calls["translation"] += 1
            if calls["translation"] % 20 == 0:
                CACHE_PATH.write_text(json.dumps(cache))
        return cache[translation_key][text]

    def prepare_search(text):
        if text not in cache["prep"]:
            try:
                time.sleep(2)  # stay under provider burst limits
                cache["prep"][text] = list(real_prepare(text))
            except Exception as e:
                calls["rewrite_failed"] += 1
                if calls["rewrite_failed"] >= 3:
                    CACHE_PATH.write_text(json.dumps(cache))
                    sys.exit(f"Stopping: 3 rewrite calls failed (last: {str(e)[:200]}). No results written.")
                raise
            calls["rewrite"] += 1
        return SearchQuery(*cache["prep"][text])

    translator.prepare_search = prepare_search

    def embed(texts):
        for t in texts:
            if t not in cache[emb_key]:
                cache[emb_key][t] = real_embed([t])[0]
                calls["embedding"] += 1
        return [cache[emb_key][t] for t in texts]

    retriever.translator.translate, retriever.embedding_client.embed = translate, embed
    return cache, calls


def ids(cell):
    return [int(x) for x in cell.split(" | ") if x.strip()]


def group_of(pid):
    return subject_key(pid)


def grouped_recall(gold, returned):
    gold_groups = {group_of(p) for p in gold}
    returned_groups = {group_of(p) for p in returned}
    return len(gold_groups & returned_groups) / len(gold_groups)


def mean(values):
    values = [v for v in values if v is not None]
    return round(statistics.mean(values), 2) if values else None


def results_root():
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BACKEND,
                         capture_output=True, text=True).stdout.strip() or "nogit"
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "nodes", "config.py"], cwd=BACKEND,
                                capture_output=True, text=True).stdout.strip())
    return sha, dirty, BACKEND / "evaluation" / "results" / f"{date.today()}_{sha}{'-dirty' if dirty else ''}" / "retrieve"


def compare():
    _, _, root = results_root()
    print("| Run | Statute hit | Statute recall | Precedent hit | Precedent recall | Twin overlap |")
    print("|---|---|---|---|---|---|")
    for path in sorted(root.glob("*/raw.jsonl"), key=lambda p: p.stat().st_mtime):
        rows = [json.loads(line) for line in open(path, encoding="utf-8")]
        topics = {}
        for r in rows:
            topics.setdefault(r["topic"], []).append(set(r["law_ids"]) | set(r["case_ids"]))
        twins = [len(set.intersection(*g)) / len(set.union(*g)) for g in topics.values() if len(g) > 1]
        print(f"| {path.parent.name} | {mean([r['law_hit'] for r in rows])} | {mean([r['law_recall_grouped'] for r in rows])} | "
              f"{mean([r['case_hit'] for r in rows])} | {mean([r['case_recall'] for r in rows])} | {mean(twins)} |")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="run")
    parser.add_argument("--compare", action="store_true")
    for flag in ("curation", "rewrite", "hybrid"):
        parser.add_argument(f"--{flag}", choices=["on", "off"])
    parser.add_argument("--embed", choices=["english", "search", "both"])
    parser.add_argument("--dataset", default="golden_dataset.csv",
                        help="file in this folder, e.g. golden_dataset_v2.csv")
    parser.add_argument("--keyword-weight", type=float, help="weight of the keyword ranking in the merge")
    parser.add_argument("--vector-weight", type=float, help="weight of the vector ranking in the merge (0 = keyword only)")
    parser.add_argument("--laws", type=int, help="how many statute documents to return")
    parser.add_argument("--translator", choices=["hf", "ollama"], default="hf",
                        help="hf = the app's Hugging Face translation model; ollama = settings.ollama_translation_model")
    parser.add_argument("--translate-only", action="store_true",
                        help="only fill the translation cache; no embedding, search or report")
    parser.add_argument("--languages", help="comma-separated subset of the language column, e.g. English,Hinglish")
    args = parser.parse_args()
    if args.compare:
        return compare()

    s = retriever.settings
    if args.curation: s.enable_corpus_curation = args.curation == "on"
    if args.rewrite: s.enable_query_rewrite = args.rewrite == "on"
    if args.hybrid: s.enable_hybrid_search = args.hybrid == "on"
    if args.embed: retriever.REWRITE_EMBED_TEXT = args.embed
    if args.keyword_weight is not None: s.retrieval_keyword_weight = args.keyword_weight
    if args.vector_weight is not None: s.retrieval_vector_weight = args.vector_weight
    if args.laws: s.retrieval_laws_top_k = s.retrieval_laws_large_context_top_k = args.laws

    if args.translator == "ollama":
        retriever.translator._providers = ["ollama"]
        translation_model, translation_key = s.ollama_translation_model, f"tr:ollama:{s.ollama_translation_model}"
    else:
        translation_model, translation_key = s.translation_model, "tr2"
    cache, calls = install_cache(translation_key)
    rows = list(csv.DictReader(open(HERE / args.dataset, encoding="utf-8")))
    if args.languages:
        wanted = {x.strip().lower() for x in args.languages.split(",")}
        rows = [r for r in rows if r["language"].lower() in wanted]
    results = []

    if args.translate_only:
        failed = 0
        for row in rows:
            lang = detect_language(row["query"])
            before = calls["translation"]
            text = retriever._retrieval_query(row["query"], lang)
            if calls["translation"] > before:
                time.sleep(0.5)
            elif (lang != "en" or looks_like_hinglish(row["query"])) and row["query"] not in cache[translation_key]:
                failed += 1  # the retriever fell back to the untranslated text
                if failed >= 3:
                    break
        CACHE_PATH.write_text(json.dumps(cache))
        print(f"{calls['translation']} new translations with {translation_model}; "
              f"{len(cache[translation_key])} cached; {failed} failed" + (" (stopped)" if failed >= 3 else ""))
        return

    for row in rows:
        lang = detect_language(row["query"])
        res = retriever.retrieve_documents(
            {"query": row["query"], "root_query": row["query"], "detected_language": lang}
        )
        chunks = res["retrieved_chunks"]
        law = [c for c in chunks if c.get("retrieval_group") == "law_or_act"]
        case = [c for c in chunks if c.get("retrieval_group") == "legal_case"]
        law_ids = [c["metadata"]["parent_id"] for c in law]
        case_ids = [c["metadata"]["parent_id"] for c in case]
        gold_law, gold_case = ids(row["gold_law_parent_ids"]), ids(row["gold_case_parent_ids"])
        seed = int(row["seed_parent_id"]) if row.get("seed_parent_id") else None

        results.append({
            "id": int(row["id"]) if row["id"].isdigit() else row["id"], "topic": row["topic"], "language": row["language"],
            "detected_language": lang, "query": row["query"],
            "searched_as": cache["prep"].get(row["query"]) if s.enable_query_rewrite else cache[translation_key].get(row["query"]),
            "law_ids": law_ids, "law_titles": [c["metadata"]["title"] for c in law],
            "case_ids": case_ids, "case_titles": [c["metadata"]["title"] for c in case],
            "law_recall": len(set(gold_law) & set(law_ids)) / len(gold_law) if gold_law else None,
            "law_recall_grouped": grouped_recall(gold_law, law_ids) if gold_law else None,
            "law_hit": int(bool({group_of(p) for p in gold_law} & {group_of(p) for p in law_ids})) if gold_law else None,
            "case_recall": len(set(gold_case) & set(case_ids)) / len(gold_case) if gold_case else None,
            "case_hit": int(bool(set(gold_case) & set(case_ids))) if gold_case else None,
            # the post the scenario was modelled on; kept out of the gold list
            "seed_hit": int(seed in case_ids) if seed is not None else None,
            "distinct_law_groups": len({group_of(p) for p in law_ids}),
            "off_topic_law": len(set(law_ids) & OFF_TOPIC_LAW),
        })

    CACHE_PATH.write_text(json.dumps(cache))

    sha, dirty, root = results_root()
    out_dir = root / args.label
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "raw.jsonl", "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    lines = [
        "# Retrieval evaluation (deterministic checks only)", "",
        f"- Commit: `{sha}`{' + uncommitted changes' if dirty else ''}",
        f"- Collection: `{s.milvus_collection_name}` | embedding: `{s.embedding_model}`",
        f"- Query translation: {'on' if s.enable_query_translation else 'off'} (`{translation_model}`)"
        f" | rewrite: {'on, embedding ' + retriever.REWRITE_EMBED_TEXT if s.enable_query_rewrite else 'off'}"
        f" | hybrid (BM25): {'on' if s.enable_hybrid_search else 'off'}"
        f" | corpus curation: {'on' if s.enable_corpus_curation else 'off'}"
        f" | weights keyword {s.retrieval_keyword_weight}, vector {s.retrieval_vector_weight}",
        f"- Dataset: `{args.dataset}`" + (f" (languages: {args.languages})" if args.languages else ""),
        f"- Queries: {len(results)} | model calls this run: {calls['embedding']} embedding, "
        f"{calls['translation']} translation, {calls['rewrite']} rewrite", "",
        "Gold lists are 'known relevant', not exhaustive, so recall and hit rates are lower bounds. "
        "'Grouped' treats near-duplicate statute documents as one.", "",
        "## Overall", "",
        "| Metric | Value |", "|---|---|",
        f"| Statute hit rate (at least one gold statute returned) | {mean([r['law_hit'] for r in results])} |",
        f"| Statute recall, grouped | {mean([r['law_recall_grouped'] for r in results])} |",
        f"| Statute recall, exact ids | {mean([r['law_recall'] for r in results])} |",
        f"| Precedent hit rate (at least one gold precedent returned) | {mean([r['case_hit'] for r in results])} |",
        f"| Precedent recall | {mean([r['case_recall'] for r in results])} |",
        f"| Source post found (rows that have one; not counted as a precedent hit) | {mean([r['seed_hit'] for r in results])} |",
        f"| Distinct statutes per query after merging duplicates (of {retriever._law_limit_for_context()}) | {mean([r['distinct_law_groups'] for r in results])} |",
        f"| Queries with an off-topic statute document | {sum(r['off_topic_law'] > 0 for r in results)} of {len(results)} |",
        "", "## By language", "",
        "| Language | Queries | Statute hit | Statute recall (grouped) | Precedent hit |", "|---|---|---|---|---|",
    ]
    for lang in sorted({r["language"] for r in results}):
        sub = [r for r in results if r["language"] == lang]
        lines.append(f"| {lang} | {len(sub)} | {mean([r['law_hit'] for r in sub])} | "
                     f"{mean([r['law_recall_grouped'] for r in sub])} | {mean([r['case_hit'] for r in sub])} |")

    lines += ["", "## Language twins (same question, different language)", "",
              "| Topic | Languages | Shared statutes | Shared precedents |", "|---|---|---|---|"]
    by_topic = {}
    for r in results:
        by_topic.setdefault(r["topic"], []).append(r)
    for topic, group in by_topic.items():
        if len(group) < 2:
            continue
        law_sets = [set(r["law_ids"]) for r in group]
        case_sets = [set(r["case_ids"]) for r in group]
        lines.append(f"| {topic} | {', '.join(r['language'] for r in group)} | "
                     f"{len(set.intersection(*law_sets))} of {len(set.union(*law_sets))} | "
                     f"{len(set.intersection(*case_sets))} of {len(set.union(*case_sets))} |")

    hub = Counter(t for r in results for t in set(r["law_titles"]))
    lines += ["", "## Statute documents returned most often", "", "| Document | Queries (of %d) |" % len(results), "|---|---|"]
    lines += [f"| {t} | {n} |" for t, n in hub.most_common(8)]

    lines += ["", "## Per query", "", "| # | Lang | Topic | Statute hit | Precedent hit | Statutes returned |", "|---|---|---|---|---|---|"]
    show = lambda v: "-" if v is None else ("yes" if v else "no")
    for r in results:
        lines.append(f"| {r['id']} | {r['language']} | {r['topic']} | {show(r['law_hit'])} | {show(r['case_hit'])} | "
                     + "; ".join(t[:45] for t in r["law_titles"]) + " |")

    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[2:20]))
    print(f"\nFull report: {out_dir / 'summary.md'}")


if __name__ == "__main__":
    main()
