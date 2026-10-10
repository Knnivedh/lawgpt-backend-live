"""
scripts/baseline_retrieval_eval.py - Phase 1: confirm the retrieval baseline.

Runs a fixed set of representative family-law queries (English, several
Indic languages, and code-mixed) directly through nodes.retriever and
records which chunks come back. This is the "before" snapshot to diff
against once query translation is enabled (see nodes/retriever.py's
_retrieval_query and the ENABLE_QUERY_TRANSLATION / TRANSLATION_ENABLED_LANGUAGES
settings in config.py).

Usage:
    uv run python scripts/baseline_retrieval_eval.py
    uv run python scripts/baseline_retrieval_eval.py --out eval_results/after.json

To capture the "after" snapshot for the same queries: set
ENABLE_QUERY_TRANSLATION=true (and add the language to
TRANSLATION_ENABLED_LANGUAGES) in the environment, then run again with a
different --out path.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_settings  # noqa: E402
from lang_utils import detect_language  # noqa: E402
from nodes.retriever import retrieve_documents  # noqa: E402

# Representative family-law queries, one entry per (language, scenario).
# "lang" is the expected ISO 639-1 code, recorded for comparison against
# what lang_utils.detect_language actually returns -- code-mixed and
# low-resource languages are exactly where detection can disagree.
QUERIES = [
    {"id": "en_custody", "lang": "en",
     "query": "How is child custody decided after divorce in India?"},
    {"id": "en_maintenance", "lang": "en",
     "query": "Can a wife claim maintenance if she is working?"},
    {"id": "hi_divorce", "lang": "hi",
     "query": "तलाक के बाद बच्चे की कस्टडी किसे मिलती है?"},
    {"id": "hi_dowry", "lang": "hi",
     "query": "दहेज उत्पीड़न की शिकायत कैसे दर्ज करें?"},
    {"id": "ta_maintenance", "lang": "ta",
     "query": "விவாகரத்திற்குப் பிறகு பராமரிப்புத் தொகை எப்படி நிர்ணயிக்கப்படுகிறது?"},
    {"id": "te_domestic_violence", "lang": "te",
     "query": "గృహ హింస చట్టం కింద ఫిర్యాదు ఎలా చేయాలి?"},
    {"id": "bn_custody", "lang": "bn",
     "query": "বিবাহবিচ্ছেদের পর সন্তানের অভিভাবকত্ব কীভাবে নির্ধারিত হয়?"},
    {"id": "hi_en_codemixed", "lang": "hi",
     "query": "Mera husband domestic violence karta hai, maintenance kaise le sakti hoon?"},
    {"id": "ta_en_codemixed", "lang": "ta",
     "query": "Divorce case ல custody எப்படி decide பண்றாங்க?"},
]


def _summarize(chunks):
    return [
        {
            "title": c["metadata"].get("title"),
            "parent_id": c["metadata"].get("parent_id"),
            "category": c["metadata"].get("category"),
            "retrieval_group": c.get("retrieval_group"),
            "score": round(c.get("score", 0.0), 4),
        }
        for c in chunks
    ]


def run(out_path: Path) -> None:
    settings = get_settings()
    results = []

    for item in QUERIES:
        detected = detect_language(item["query"])
        state = {
            "query": item["query"],
            "root_query": item["query"],
            "detected_language": detected,
        }
        result = retrieve_documents(state)
        results.append({
            "id": item["id"],
            "expected_lang": item["lang"],
            "detected_lang": detected,
            "query": item["query"],
            "retrieved": _summarize(result.get("retrieved_chunks", [])),
            "sources": result.get("sources", []),
        })
        print(
            f"[{item['id']}] expected={item['lang']} detected={detected} "
            f"chunks={len(result.get('retrieved_chunks', []))}"
        )

    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "translation_enabled": settings.enable_query_translation,
        "translation_enabled_languages": settings.translation_enabled_languages,
        "results": results,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nWrote {len(results)} query results to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "eval_results" / "baseline_retrieval.json",
    )
    args = parser.parse_args()
    run(args.out)
