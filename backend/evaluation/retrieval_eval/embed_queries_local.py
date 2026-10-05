"""
Embed, on this machine, every query text the retrieval harness will search
with, and store the vectors in .api_cache.json so the harness makes no
Hugging Face embedding calls. The local model gives the same vectors as the
hosted one.

    cd backend
    uv run --no-project --python 3.12 --with sentence-transformers \\
        evaluation/retrieval_eval/embed_queries_local.py [dataset.csv]

Texts embedded: each query in the dataset and every cached translation (run
run_eval.py --translate-only first). The model and query prefix come from
EMBEDDING_MODEL and EMBEDDING_QUERY_PREFIX, as in the app.
"""

import csv
import json
import os
import sys
from pathlib import Path

from sentence_transformers import SentenceTransformer

HERE = Path(__file__).resolve().parent
CACHE_PATH = HERE / ".api_cache.json"
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "bhavyagiri/InLegal-Sbert")
PREFIX = os.getenv("EMBEDDING_QUERY_PREFIX", "")
KEY = "emb" if MODEL_NAME == "bhavyagiri/InLegal-Sbert" else f"emb:{MODEL_NAME}"

cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
cache.setdefault(KEY, {})
dataset = HERE / (sys.argv[1] if len(sys.argv) > 1 else "golden_dataset_v2.csv")

texts = {row["query"] for row in csv.DictReader(open(dataset, encoding="utf-8"))}
for key, table in cache.items():
    if key == "tr2" or key.startswith("tr:"):
        texts.update(table.values())
texts = {PREFIX + t for t in texts}
missing = sorted(t for t in texts if t not in cache[KEY])
print(f"{len(texts)} texts, {len(missing)} not yet embedded with {MODEL_NAME}")

if missing:
    model = SentenceTransformer(MODEL_NAME)
    vectors = model.encode(missing, batch_size=8, show_progress_bar=False).tolist()
    cache[KEY].update(zip(missing, vectors))
    CACHE_PATH.write_text(json.dumps(cache))
    print(f"embedded {len(missing)} texts locally")
