#!/bin/bash
# Rebuild the index into a NEW Milvus collection, leaving the live one alone.
# Run from backend/:  bash scripts/reindex_v2.sh
#
#   1. chunking.py   -> data/v2/chunked      (already run if the folder exists)
#   2. embedding.py  -> data/v2/embeddings   (local model, no API calls)
#   3. milvus_store.py -> collection $NEW_COLLECTION
#   4. retrieval evaluation against the new collection
set -euo pipefail

NEW_COLLECTION="${NEW_COLLECTION:-indian_family_law_cases_hrag_v2}"
export CHUNKED_DIR=./data/v2/chunked
export EMBEDDINGS_DIR=./data/v2/embeddings

source .venv/bin/activate

if [ ! -f "$CHUNKED_DIR/family_law_chunks.json" ]; then
  echo "== [1/4] chunking"
  python chunking.py
else
  echo "== [1/4] chunking: $CHUNKED_DIR already present, skipping"
fi

echo "== [2/4] embedding locally  $(date)"
EMBED_BACKEND=local uv run --no-project --python 3.12 \
  --with sentence-transformers --with tqdm --with tokenizers python embedding.py

echo "== [3/4] loading into Milvus collection $NEW_COLLECTION  $(date)"
# "no" answers the drop-and-recreate prompt if the collection already exists.
echo no | MILVUS_COLLECTION_NAME="$NEW_COLLECTION" python milvus_store.py

echo "== [4/4] retrieval evaluation on $NEW_COLLECTION  $(date)"
MILVUS_COLLECTION_NAME="$NEW_COLLECTION" python evaluation/retrieval_eval/run_eval.py --label 10-v2-index-vector-only --hybrid off
MILVUS_COLLECTION_NAME="$NEW_COLLECTION" python evaluation/retrieval_eval/run_eval.py --label 11-v2-index-hybrid --hybrid on
python evaluation/retrieval_eval/run_eval.py --compare

echo "== done  $(date)"
