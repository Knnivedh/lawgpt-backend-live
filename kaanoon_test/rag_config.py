"""
Fallback rag_config module for deployment layouts where top-level rag_config.py
is not importable. Uses environment variables and safe defaults.
"""

from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PERMANENT_ROOT = Path(
    os.getenv("RAG_PERMANENT_ROOT", str(PROJECT_ROOT / "PERMANENT_RAG_FILES"))
)

MAIN_DB_PATH = PERMANENT_ROOT / "MAIN_DATABASE"
STATUTES_DB_PATH = PERMANENT_ROOT / "STATUTE_DATABASE"
BACKUP_PATH = PERMANENT_ROOT / "BACKUPS"

MAIN_COLLECTION = os.getenv("MAIN_COLLECTION", "legal_db_hybrid_prod")

# GAP-10 FIX (mirrors the identical fix in the root rag_config.py:26-33):
# this still pointed at "legal_db_statutes_prod", which does not exist in
# STATUTE_DATABASE/chroma.sqlite3. That database contains exactly one
# collection, "legal_db_statutes" (dim 384, 3,972 vectors). With the wrong
# name the statute vector lookup failed outright and the store reported
# not-ready, which live /health showed as statute_store_ready: false.
# The BM25 side masked it because legal_db_statutes_prod_bm25.pkl is a
# byte-identical copy of legal_db_statutes_bm25.pkl.
STATUTES_COLLECTION = os.getenv("STATUTES_COLLECTION", "legal_db_statutes")

ZILLIZ_CLUSTER_ENDPOINT = os.getenv("ZILLIZ_CLUSTER_ENDPOINT", "").strip()
ZILLIZ_TOKEN = os.getenv("ZILLIZ_TOKEN", "").strip()
ZILLIZ_COLLECTION_NAME = os.getenv("ZILLIZ_COLLECTION_NAME", "legal_rag_cloud")

_cloud_mode_flag = os.getenv("CLOUD_MODE_ENABLED", "true").strip().lower()
CLOUD_MODE_ENABLED = (
    _cloud_mode_flag in ("1", "true", "yes", "on")
    and bool(ZILLIZ_CLUSTER_ENDPOINT)
    and bool(ZILLIZ_TOKEN)
)

for p in [MAIN_DB_PATH, STATUTES_DB_PATH, BACKUP_PATH]:
    p.mkdir(parents=True, exist_ok=True)
