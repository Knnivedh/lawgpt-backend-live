"""
PageIndex Retriever - Vectorless, Tree-Based Statute Retrieval
==============================================================
Integrates VectifyAI/PageIndex into LAW-GPT as a high-precision
retrieval layer for statute section lookups.

Architecture:
  1. Documents (statutes) are uploaded once to PageIndex cloud which builds a
     hierarchical tree index (like a Table of Contents).
  2. At query time the LLM searches the tree by reasoning about which
     nodes are relevant (no vector similarity - pure reasoning).
  3. Exact text of the relevant nodes is fetched and returned as context.

Activation: called by AgenticRAGEngine._retrieve() when
  plan.strategy == "statute_lookup"  OR  statutory keywords are detected.

Graceful degradation: if PAGEINDEX_API_KEY is not set, or any call
fails, the retriever returns "" so the caller falls back to Zilliz.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.config import Config

logger = logging.getLogger(__name__)

_pageindex_available: Optional[bool] = None

def _check_pageindex() -> bool:
    global _pageindex_available
    if _pageindex_available is None:
        try:
            import pageindex
            _pageindex_available = True
        except ImportError:
            logger.warning("[PageIndex] 'pageindex' package not installed. Run: pip install pageindex")
            _pageindex_available = False
    return _pageindex_available

STATUTE_KEYWORDS = {
    "bns", "bnss", "bsa", "bharatiya nyaya sanhita",
    "bharatiya nagarik suraksha sanhita", "bharatiya sakshya adhiniyam",
    "ipc", "crpc", "indian penal code", "criminal procedure",
    "cpc", "civil procedure code",
    "consumer protection act", "consumer protection",
    "indian contract act", "contract act",
    "transfer of property", "tpa",
    "companies act", "ibc", "insolvency",
    "competition act",
    "section ", "sec.", "article ", "schedule ",
}


class PageIndexRetriever:
    """
    Wrapper around the PageIndex cloud API for LAW-GPT statute retrieval.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        registry_path: str = "pageindex_doc_registry.json",
        llm_client: Optional[Any] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("PAGEINDEX_API_KEY", "")
        self.registry_path = Path(registry_path)
        self.llm_client = llm_client
        self.model = model or Config.MAIN_LLM_MODEL  # Central model registry
        self._client: Optional[Any] = None
        self._registry: Dict[str, str] = {}
        self._registry_loaded = False
        self._tree_cache: Dict[str, Any] = {}

        if not self.api_key:
            logger.warning(
                "[PageIndex] PAGEINDEX_API_KEY not set - retriever disabled. "
                "Get your key at https://dash.pageindex.ai/api-keys"
            )
        else:
            logger.info("[PageIndex] PageIndexRetriever initialized (key present)")

    @property
    def is_available(self) -> bool:
        return bool(self.api_key) and _check_pageindex()

    def retrieve(self, query: str, top_docs: int = 3, max_nodes_per_doc: int = 5) -> str:
        if not self.is_available:
            return ""
        registry = self._load_registry()
        if not registry:
            logger.warning("[PageIndex] No documents indexed yet. Run pageindex_ingest.py first.")
            return ""
        ranked_docs = self._rank_docs(query, registry, top_docs)
        if not ranked_docs:
            return ""
        context_parts: List[str] = []
        for doc_name, doc_id in ranked_docs:
            try:
                part = self._retrieve_from_doc(query, doc_name, doc_id, max_nodes_per_doc)
                if part:
                    context_parts.append(part)
            except Exception as exc:
                logger.warning(f"[PageIndex] Failed to retrieve from '{doc_name}': {exc}")
        if not context_parts:
            return ""
        header = "[PAGEINDEX STATUTE RETRIEVAL - Tree-Based Reasoning]\n"
        return header + "\n\n".join(context_parts)

    def index_document(self, file_path, doc_name: Optional[str] = None) -> Optional[str]:
        if not self.is_available:
            return None
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"[PageIndex] File not found: {file_path}")
            return None
        doc_name = doc_name or file_path.stem
        client = self._get_client()
        registry = self._load_registry()
        if doc_name in registry:
            logger.info(f"[PageIndex] '{doc_name}' already indexed (id={registry[doc_name]})")
            return registry[doc_name]
        try:
            logger.info(f"[PageIndex] Submitting '{doc_name}' ({file_path.name}) ...")
            result = client.submit_document(file_path=str(file_path))
            doc_id = result.get("doc_id") or result.get("id") or result.get("document_id")
            if not doc_id:
                logger.error(f"[PageIndex] No doc_id in response for '{doc_name}': {result}")
                return None
            logger.info(f"[PageIndex] Waiting for '{doc_name}' (id={doc_id}) to be ready ...")
            ready = self._wait_until_ready(client, doc_id, timeout=300, poll_interval=10)
            if not ready:
                logger.error(f"[PageIndex] '{doc_name}' did not become ready within 5 min.")
                return None
            registry[doc_name] = doc_id
            self._save_registry(registry)
            logger.info(f"[PageIndex] '{doc_name}' indexed successfully (id={doc_id})")
            return doc_id
        except Exception as exc:
            logger.error(f"[PageIndex] Failed to index '{doc_name}': {exc}")
            return None

    def get_indexed_docs(self) -> Dict[str, str]:
        return dict(self._load_registry())

    def _get_client(self) -> Any:
        if self._client is None:
            from pageindex import PageIndexClient
            self._client = PageIndexClient(api_key=self.api_key)
        return self._client
 
    def _load_registry(self) -> Dict[str, str]:
        if not hasattr(self, "_registry_loaded"):
            return self._registry

        if getattr(self, "_registry_loaded", False):
            return self._registry
        if self.registry_path.exists():
            try:
                with open(self.registry_path, "r", encoding="utf-8") as fh:
                    self._registry = json.load(fh)
                logger.info(f"[PageIndex] Registry loaded: {len(self._registry)} docs")
            except Exception as exc:
                logger.warning(f"[PageIndex] Could not read registry: {exc}")
                self._registry = {}
        else:
            self._registry = {}
        self._registry_loaded = True
        return self._registry

    def _save_registry(self, registry: Dict[str, str]) -> None:
        self._registry = registry
        self._registry_loaded = True
        try:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.registry_path, "w", encoding="utf-8") as fh:
                json.dump(registry, fh, indent=2)
        except Exception as exc:
            logger.error(f"[PageIndex] Could not save registry: {exc}")

    def _wait_until_ready(self, client: Any, doc_id: str, timeout: int = 300, poll_interval: int = 10) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if client.is_retrieval_ready(doc_id):
                    return True
            except Exception:
                pass
            time.sleep(poll_interval)
        return False

    def _get_tree(self, doc_id: str) -> Optional[Any]:
        if doc_id in self._tree_cache:
            return self._tree_cache[doc_id]
        client = self._get_client()
        try:
            tree = client.get_tree(doc_id, node_summary=True)
            self._tree_cache[doc_id] = tree
            return tree
        except Exception as exc:
            logger.warning(f"[PageIndex] Could not fetch tree for {doc_id}: {exc}")
            return None

    def _rank_docs(self, query: str, registry: Dict[str, str], top_n: int) -> List[tuple]:
        query_lower = query.lower()
        scores: List[tuple] = []
        for doc_name, doc_id in registry.items():
            name_lower = doc_name.lower().replace("_", " ")
            name_tokens = set(name_lower.split())
            query_tokens = set(query_lower.split())
            score = len(name_tokens & query_tokens)
            if name_lower in query_lower or any(t in query_lower for t in name_tokens if len(t) > 4):
                score += 3
            scores.append((score, doc_name, doc_id))
        scores.sort(key=lambda x: x[0], reverse=True)
        ranked = [(name, doc_id) for s, name, doc_id in scores if s > 0][:top_n]
        if not ranked:
            ranked = [(name, doc_id) for _, name, doc_id in scores[:min(2, len(scores))]]
        return ranked

    def _retrieve_from_doc(self, query: str, doc_name: str, doc_id: str, max_nodes: int) -> str:
        tree = self._get_tree(doc_id)
        if not tree:
            return ""
        try:
            from pageindex import utils as pi_utils
            compact_tree = pi_utils.remove_fields(tree, fields=["text"])
        except Exception:
            compact_tree = tree
        node_ids = self._llm_tree_search(query, compact_tree, doc_name)
        if not node_ids:
            return ""
        try:
            from pageindex import utils as pi_utils
            node_map = pi_utils.create_node_mapping(tree)
        except Exception:
            node_map = self._build_node_map(tree)
        texts: List[str] = []
        for nid in node_ids[:max_nodes]:
            node = node_map.get(nid)
            if node:
                node_text = node.get("text", node.get("content", ""))
                node_title = node.get("title", node.get("heading", nid))
                if node_text:
                    texts.append(f"[{doc_name} / {node_title}]\n{node_text}")
        if not texts:
            return ""
        return "\n\n".join(texts)

    def _llm_tree_search(self, query: str, tree: Any, doc_name: str) -> List[str]:
        if self.llm_client is None:
            logger.warning("[PageIndex] No LLM client - skipping tree search")
            return []
        tree_str = json.dumps(tree, ensure_ascii=False)[:6000]
        system_msg = (
            "You are a precise legal document navigator. "
            "You will be given a hierarchical table of contents (tree) of an Indian legal statute "
            "and a user query. Identify which tree nodes contain the relevant text.\n"
            'Respond ONLY with valid JSON: {"thinking": "brief reasoning", "node_list": ["0001", "0002"]}\n'
            "node_list must contain the node_id strings from the tree."
        )
        user_msg = (
            f"Query: {query}\n\nDocument: {doc_name}\n\nTree structure:\n{tree_str}\n\n"
            "Which node IDs contain the most relevant text? Return at most 5 node IDs."
        )
        try:
            response = self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                model=self.model,
                temperature=0.0,
                max_tokens=300,
            )
            resp_text = response if isinstance(response, str) else (
                response.choices[0].message.content
                if hasattr(response, "choices") else str(response)
            )
            start = resp_text.find("{")
            end = resp_text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(resp_text[start:end])
                node_list = data.get("node_list", [])
                logger.info(
                    f"[PageIndex] Tree search for '{doc_name}': nodes={node_list} "
                    f"(thinking: {data.get('thinking', '')[:80]})"
                )
                return [str(n) for n in node_list]
        except Exception as exc:
            logger.warning(f"[PageIndex] LLM tree search failed for '{doc_name}': {exc}")
        return []

    def _build_node_map(self, tree: Any, _map: Optional[Dict] = None) -> Dict[str, Any]:
        if _map is None:
            _map = {}
        if isinstance(tree, dict):
            nid = tree.get("id") or tree.get("node_id")
            if nid:
                _map[str(nid)] = tree
            for child in tree.get("children", []):
                self._build_node_map(child, _map)
        elif isinstance(tree, list):
            for item in tree:
                self._build_node_map(item, _map)
        return _map

    @staticmethod
    def should_activate(query: str) -> bool:
        q = query.lower()
        return any(kw in q for kw in STATUTE_KEYWORDS)