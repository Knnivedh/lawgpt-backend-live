"""
PageIndex Store Wrapper for LAW-GPT
--------------------------------------
Wraps the `pageindex` library as a retriever compatible with EnhancedRetriever.
PageIndex provides page-level document indexing and retrieval distinct from
the sentence-level ChromaDB store.

Usage:
    from rag_system.core.pageindex_store import PageIndexStore
    store = PageIndexStore()
    store.index_documents(records)   # records = List[{"id":..,"text":..,"metadata":..}]
    results = store.search("bail application procedure", n_results=5)
"""

import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Attempt to import pageindex — optional dependency
try:
    import pageindex  # noqa: F401
    PAGEINDEX_AVAILABLE = True
    logger.info("[PageIndex] pageindex library available")
except ImportError:
    PAGEINDEX_AVAILABLE = False
    logger.warning(
        "[PageIndex] pageindex library not installed. "
        "Install with: pip install pageindex\n"
        "PageIndex RAG strategy will fall back to BM25 keyword search."
    )


class PageIndexStore:
    """
    Page-level document index using the `pageindex` library.

    When pageindex is unavailable, falls back to a lightweight BM25 index
    so RAG strategies that depend on this store still function.
    """

    def __init__(self, persist_dir: str = "pageindex_store"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._documents: List[Dict] = []
        self._index = None
        self._fallback_bm25 = None
        self._fallback_docs: List[str] = []
        self._fallback_metas: List[Dict] = []
        self._fallback_ids: List[str] = []

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_documents(self, records: List[Dict]) -> None:
        """
        Index a list of documents.

        Args:
            records: List of dicts with keys 'id', 'text', 'metadata'.
        """
        if not records:
            logger.warning("[PageIndex] No records to index.")
            return

        self._documents = records
        texts = [r["text"] for r in records]
        metas = [r.get("metadata", {}) for r in records]
        ids = [r["id"] for r in records]

        if PAGEINDEX_AVAILABLE:
            self._build_pageindex(texts, ids, metas)
        else:
            self._build_fallback_bm25(texts, ids, metas)

        logger.info(f"[PageIndex] Indexed {len(records):,} documents.")

    def _build_pageindex(self, texts: List[str], ids: List[str], metas: List[Dict]) -> None:
        """Build index using the pageindex library."""
        try:
            # pageindex API varies by version — attempt common patterns
            if hasattr(pageindex, "PageIndex"):
                self._index = pageindex.PageIndex()
                for i, text in enumerate(texts):
                    self._index.add(page_id=ids[i], content=text, metadata=metas[i])
            elif hasattr(pageindex, "create_index"):
                self._index = pageindex.create_index(
                    documents=[{"id": ids[i], "text": texts[i]} for i in range(len(texts))]
                )
            else:
                logger.warning("[PageIndex] Unknown pageindex API. Falling back to BM25.")
                self._build_fallback_bm25(texts, ids, metas)
        except Exception as e:
            logger.error(f"[PageIndex] Failed to build pageindex: {e}. Falling back to BM25.")
            self._build_fallback_bm25(texts, ids, metas)

    def _build_fallback_bm25(self, texts: List[str], ids: List[str], metas: List[Dict]) -> None:
        """Build a BM25 fallback index."""
        try:
            from rank_bm25 import BM25Okapi
            import numpy as np

            self._fallback_docs = texts
            self._fallback_ids = ids
            self._fallback_metas = metas
            tokenized = [t.lower().split() for t in texts]
            self._fallback_bm25 = BM25Okapi(tokenized)
            logger.info("[PageIndex] BM25 fallback index built.")
        except ImportError:
            logger.error("[PageIndex] rank_bm25 not available for fallback.")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, n_results: int = 5) -> List[Dict]:
        """
        Search the index and return top-N results.

        Returns:
            List of dicts with keys: id, text, metadata, score, source
        """
        if PAGEINDEX_AVAILABLE and self._index is not None:
            return self._search_pageindex(query, n_results)
        elif self._fallback_bm25 is not None:
            return self._search_bm25(query, n_results)
        else:
            logger.warning("[PageIndex] No index available. Returning empty results.")
            return []

    def _search_pageindex(self, query: str, n_results: int) -> List[Dict]:
        """Search using pageindex library."""
        try:
            if hasattr(self._index, "search"):
                raw = self._index.search(query, k=n_results)
            elif hasattr(self._index, "query"):
                raw = self._index.query(query, top_k=n_results)
            else:
                return self._search_bm25(query, n_results)

            results = []
            for i, item in enumerate(raw[:n_results]):
                if isinstance(item, dict):
                    results.append({
                        "id": item.get("id", f"pi_{i}"),
                        "text": item.get("content", item.get("text", "")),
                        "metadata": item.get("metadata", {}),
                        "score": item.get("score", 1.0 - i * 0.05),
                        "source": "pageindex",
                    })
                else:
                    results.append({
                        "id": f"pi_{i}",
                        "text": str(item),
                        "metadata": {},
                        "score": 1.0 - i * 0.05,
                        "source": "pageindex",
                    })
            return results
        except Exception as e:
            logger.error(f"[PageIndex] Search failed: {e}. Falling back to BM25.")
            return self._search_bm25(query, n_results)

    def _search_bm25(self, query: str, n_results: int) -> List[Dict]:
        """Search using BM25 fallback."""
        if self._fallback_bm25 is None:
            return []
        try:
            import numpy as np

            tokens = query.lower().split()
            scores = self._fallback_bm25.get_scores(tokens)
            top_idx = list(reversed(sorted(range(len(scores)), key=lambda i: scores[i])))[:n_results]
            return [
                {
                    "id": self._fallback_ids[i],
                    "text": self._fallback_docs[i],
                    "metadata": self._fallback_metas[i] if self._fallback_metas else {},
                    "score": float(scores[i]),
                    "source": "pageindex_bm25_fallback",
                }
                for i in top_idx
                if scores[i] > 0
            ]
        except Exception as e:
            logger.error(f"[PageIndex] BM25 search failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def count(self) -> int:
        return len(self._documents)

    def is_ready(self) -> bool:
        return (self._index is not None) or (self._fallback_bm25 is not None)
