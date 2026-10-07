"""Qdrant-backed vector store — the FREE replacement for the stopped Zilliz cluster.

Why this exists
---------------
Zilliz (Milvus Cloud) has been stopped, so `CLOUD_MODE_ENABLED` resolves false and
the deployed app answered from web search plus model memory with 0 documents.
Zilliz's free cluster auto-suspends, which is exactly how it died unnoticed.

Qdrant Cloud offers a free tier of 1 GB with no card and no time limit, and the
full case-law corpus fits:

    91,899 judgments, 540 MB of text
      + 768-d int8 vectors (70.6 MB)  =  611 MB   -> fits 1 GB comfortably

The 14.7 GB local Chroma store is misleading: `link_lists.bin` alone is 12.2 GB of
HNSW graph, which is discarded here and rebuilt by Qdrant.

Duck-typed to match CloudMilvusStore (`is_connected`, `hybrid_search`,
`advanced_search`, `count`, `get_diagnostics`) so it drops into the existing
cloud -> local fallback chain without touching the orchestrator.

Never raises on connect failure: a dead vector store must degrade, not crash.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class QdrantStore:
    """Drop-in vector store backed by Qdrant (free tier friendly)."""

    def __init__(
        self,
        collection_name: str,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        vector_size: Optional[int] = None,
        embed_fn=None,
    ) -> None:
        self.collection_name = collection_name
        self.collection = None
        self.is_connected = False
        self._client = None
        self._embed_fn = embed_fn
        self._vector_size = vector_size
        self._last_error: Optional[str] = None

        url = (url or os.getenv("QDRANT_URL") or "").strip()
        api_key = (api_key or os.getenv("QDRANT_API_KEY") or "").strip()
        if not url:
            self._last_error = "QDRANT_URL not set"
            return

        try:
            from qdrant_client import QdrantClient
        except Exception as exc:  # pragma: no cover
            self._last_error = f"qdrant-client not installed: {exc}"
            logger.warning("[QDRANT] client library unavailable: %s", exc)
            return

        try:
            self._client = QdrantClient(url=url, api_key=api_key or None, timeout=30)
            names = [c.name for c in self._client.get_collections().collections]
            if collection_name not in names:
                # Do not auto-create: an empty collection would report "connected"
                # with 0 points and recreate exactly the failure this replaces.
                self._last_error = (
                    f"collection '{collection_name}' absent (have: {names})")
                logger.warning("[QDRANT] %s", self._last_error)
                return
            self.collection = self._client.get_collection(collection_name)
            self.is_connected = True
            logger.info("[QDRANT] connected to '%s' (points=%s)",
                        collection_name, self.count())
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("[QDRANT] connect failed: %s", self._last_error)

    # ── helpers ────────────────────────────────────────────────────────────
    def _embed(self, texts: List[str]) -> List[List[float]]:
        if self._embed_fn is None:
            raise RuntimeError("QdrantStore has no embed function configured")
        return self._embed_fn(texts)

    # ── CloudMilvusStore-compatible surface ────────────────────────────────
    def count(self) -> int:
        if not self.is_connected:
            return 0
        try:
            return int(self.collection.points_count or 0)
        except Exception:
            return 0

    def hybrid_search(self, query: str, n_results: int = 5, alpha: float = 0.5,
                      metadata_filter: Optional[Dict] = None) -> List[Dict]:
        return self.advanced_search(query, n_results=n_results)

    def advanced_search(self, query: str, n_results: int = 5, **_: Any) -> List[Dict]:
        """Dense search returning dicts shaped like the other stores."""
        if not self.is_connected:
            return []
        try:
            vec = self._embed([query])[0]
            resp = self._client.search(
                collection_name=self.collection_name,
                query_vector=vec,
                limit=max(1, int(n_results)),
                with_payload=True,
            )
            out: List[Dict] = []
            for point in resp:
                payload = dict(point.payload or {})
                payload.setdefault("text", "")
                out.append({
                    "id": point.id,
                    "text": payload.get("text", ""),
                    "metadata": payload,
                    "score": float(point.score),
                    "distance": float(point.score),
                })
            return out
        except Exception as exc:
            logger.warning("[QDRANT] search failed: %s", exc)
            return []

    def add(self, documents: List[str], metadatas: List[Dict],
            ids: List[str]) -> int:
        if not self.is_connected:
            return 0
        try:
            from qdrant_client.models import PointStruct
            vectors = self._embed(documents)
            pts = [
                PointStruct(id=str(i), vector=v,
                            payload={**(m or {}), "text": d})
                for i, v, d, m in zip(ids, vectors, documents, metadatas)
            ]
            self._client.upsert(collection_name=self.collection_name, points=pts)
            return len(pts)
        except Exception as exc:
            logger.warning("[QDRANT] add failed: %s", exc)
            return 0

    def get_diagnostics(self, **_: Any) -> Dict:
        return {
            "backend": "qdrant",
            "connected": self.is_connected,
            "collection": self.collection_name,
            "points": self.count(),
            "url": (os.getenv("QDRANT_URL") or "").strip(),
            "error": self._last_error,
        }

    def sc_store(self) -> None:
        """The orchestrator probes `store.sc_store.enabled`; we have no sparse
        companion, so return None rather than a truthy object."""
        return None