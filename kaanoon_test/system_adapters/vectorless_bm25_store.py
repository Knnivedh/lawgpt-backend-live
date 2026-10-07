"""
VECTORLESS BM25 / KEYWORD STORE
================================
A pure keyword-based retrieval store that works entirely WITHOUT embeddings or
vector databases. Uses BM25 (rank_bm25) + TF-IDF fallback + phrase matching.

This is combined with the vector-based Zilliz/Chroma stores in the
MegaRAGOrchestrator to create a HYBRID (vectorless + vector) system.

Data sources indexed here:
  - PERMANENT_RAG_FILES/MAIN_DATABASE  (pre-serialised JSON chunks)
  - PERMANENT_RAG_FILES/STATUTE_DATABASE
  - kaanoon_test/kaanoon_qa_dataset.json
  - kaanoon_test/landmark_cases_database.json
  - All other JSON / TXT files in DATA/
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Optional deps ──────────────────────────────────────────────────────────────
try:
    from rank_bm25 import BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:
    _BM25_AVAILABLE = False
    logger.warning("[BM25] rank_bm25 not installed — falling back to TF-IDF.")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    _TFIDF_AVAILABLE = True
except ImportError:
    _TFIDF_AVAILABLE = False
    logger.warning("[TFIDF] scikit-learn not installed — using term-overlap only.")


# ══════════════════════════════════════════════════════════════════════════════
# TOKENISER
# ══════════════════════════════════════════════════════════════════════════════
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "shall", "should", "may", "might", "can", "could", "that", "this",
    "these", "those", "which", "who", "whom", "whose", "what", "when",
    "where", "why", "how", "it", "its", "as", "if", "then", "than",
}

_LEGAL_STOPWORDS = {
    "court", "case", "judgment", "india",
    "hon", "ble", "herein", "whereas", "aforesaid", "therein",
}

_HINGLISH_MAP = {
    "kya": "what",
    "kaise": "how",
    "kya": "what",
    "kanoon": "law",
    "kanun": "law",
    "adhikar": "right",
    "zamanat": "bail",
    "samjhao": "explain",
    "samjhaiye": "explain",
    "btao": "tell",
    "bataye": "tell",
    "patni": "wife",
    "pati": "husband",
    "makan": "house",
    "kiraya": "rent",
    "dhara": "section",
    "adalat": "court",
    "vakil": "advocate",
    "fir": "fir",
    "bail": "bail",
}


def _tokenise(text: str, remove_stopwords: bool = True) -> List[str]:
    """Normalize Unicode text, split on word boundaries, and optionally strip stop-words."""
    normalized = unicodedata.normalize("NFKC", text or "").lower()
    tokens = re.findall(r"[\w\u0900-\u097F]+", normalized, flags=re.UNICODE)
    normalized_tokens: List[str] = []
    for token in tokens:
        normalized_tokens.append(_HINGLISH_MAP.get(token, token))
    tokens = normalized_tokens
    if remove_stopwords:
        tokens = [t for t in tokens if t not in _STOPWORDS and t not in _LEGAL_STOPWORDS and len(t) > 1]
    else:
        tokens = [t for t in tokens if len(t) > 1]
    return tokens


# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENT MODEL
# ══════════════════════════════════════════════════════════════════════════════
class VLDocument:
    """A single chunk stored in the vectorless index."""

    __slots__ = ("doc_id", "text", "tokens", "metadata", "source")

    def __init__(self, doc_id: str, text: str, metadata: Dict, source: str = ""):
        self.doc_id = doc_id
        self.text = text
        self.tokens = _tokenise(text)
        self.metadata = metadata
        self.source = source

    def to_dict(self) -> Dict:
        return {
            "doc_id": self.doc_id,
            "text": self.text,
            "metadata": self.metadata,
            "source": self.source,
        }


# ══════════════════════════════════════════════════════════════════════════════
# BM25 / TF-IDF INDEX
# ══════════════════════════════════════════════════════════════════════════════
class VectorlessBM25Store:
    """
    Pure keyword retrieval store — no embeddings, no GPU, no cloud needed.

    Supports:
       - BM25Okapi (rank_bm25) if installed
       - TF-IDF cosine (sklearn) as secondary scorer
       - Simple term-overlap score as final fallback
       - Phrase-boost: exact multi-word phrases score higher
    """

    def __init__(self, name: str = "main"):
        self.name = name
        self.documents: List[VLDocument] = []
        self._bm25: Optional[Any] = None
        self._tfidf: Optional[Any] = None
        self._tfidf_matrix: Optional[Any] = None
        self._built = False
        self._doc_count = 0
        logger.info(f"[VL-BM25] Store '{name}' created (mode: "
                    f"{'BM25' if _BM25_AVAILABLE else 'TF-IDF' if _TFIDF_AVAILABLE else 'TermOverlap'})")

    # ── Ingestion ──────────────────────────────────────────────────────────────
    def add_document(self, text: str, metadata: Dict = None, source: str = "") -> None:
        if not text or not text.strip():
            return
        doc_id = f"{self.name}_{self._doc_count:06d}"
        self._doc_count += 1
        self.documents.append(VLDocument(doc_id, text, metadata or {}, source))
        self._built = False          # mark index dirty

    def add_documents_bulk(self, items: List[Dict]) -> int:
        """Add a list of dicts with keys: text, metadata (opt), source (opt)."""
        added = 0
        for item in items:
            text = item.get("text") or item.get("content") or item.get("page_content", "")
            if not text:
                continue
            self.add_document(
                text=str(text),
                metadata=item.get("metadata", {}),
                source=item.get("source", ""),
            )
            added += 1
        return added

    # ── Index Building ─────────────────────────────────────────────────────────
    def build_index(self) -> None:
        if not self.documents:
            logger.warning(f"[VL-BM25] '{self.name}': no documents — index empty.")
            return
        corpus = [doc.tokens for doc in self.documents]
        if _BM25_AVAILABLE:
            self._bm25 = BM25Okapi(corpus)
            logger.info(f"[VL-BM25] '{self.name}': BM25 index built over {len(self.documents)} docs.")
        if _TFIDF_AVAILABLE:
            texts = [doc.text for doc in self.documents]
            self._tfidf = TfidfVectorizer(ngram_range=(1, 2), max_features=50_000, sublinear_tf=True)
            self._tfidf_matrix = self._tfidf.fit_transform(texts)
            logger.info(f"[VL-BM25] '{self.name}': TF-IDF matrix built.")
        self._built = True

    def _ensure_built(self) -> None:
        if not self._built:
            self.build_index()

    # ── Retrieval ──────────────────────────────────────────────────────────────
    # ── Retrieval ──────────────────────────────────────────────────────────────
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.0,
        act_filter: Optional[str] = None,
        section_filter: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Return top-k docs ranked by BM25 (+ optional TF-IDF re-rank).
        Each result dict: {text, metadata, source, score, retrieval_method}

        If `act_filter` is provided, narrows candidate scoring to that Act's chunks,
        accelerating retrieval ~10X and preventing cross-statute pollution.
        If `section_filter` is provided, applies high-precision boost to matching sections.
        """
        self._ensure_built()
        if not self.documents:
            return []

        query_tokens = _tokenise(query)
        if not query_tokens:
            query_tokens = _tokenise(unicodedata.normalize("NFKC", query or ""), remove_stopwords=False)

        # ── Act-filter candidate pre-filtering ─────────────────────────────────
        candidate_indices: Optional[set] = None
        if act_filter:
            _act_map = {
                "ni_act": ["negotiable instruments", "ni act", "1881"],
                "bns": ["bharatiya nyaya sanhita", "bns", "penal code", "ipc"],
                "cpa": ["consumer protection", "cpa", "copra"],
                "contract_act": ["contract act", "1872"],
                "companies_act": ["companies act"],
                "hma": ["hindu marriage", "hma"],
                "pwdva": ["domestic violence", "pwdva"],
                "bnss": ["bharatiya nagarik suraksha", "bnss", "crpc", "criminal procedure"],
                "bsa": ["bharatiya sakshya", "bsa", "evidence act"],
            }
            kws = _act_map.get(act_filter.lower(), [act_filter.lower()])
            matching = set()
            for idx, doc in enumerate(self.documents):
                doc_act = (doc.metadata.get("act") or doc.metadata.get("title") or doc.source or "").lower()
                if any(kw in doc_act for kw in kws):
                    matching.add(idx)
            if matching:
                candidate_indices = matching
                logger.debug(f"[VL-BM25] act_filter='{act_filter}' narrowed search space to {len(matching)} docs.")

        # ── BM25 scores ────────────────────────────────────────────────────────
        if self._bm25 is not None:
            raw_scores = self._bm25.get_scores(query_tokens)
            if hasattr(raw_scores, "tolist"):
                raw_scores = raw_scores.tolist()
            if candidate_indices is not None:
                scored = [(idx, raw_scores[idx]) for idx in candidate_indices]
            else:
                scored = list(enumerate(raw_scores))
        else:
            scored = self._term_overlap_scores(query_tokens)
            if candidate_indices is not None:
                scored = [(idx, s) for idx, s in scored if idx in candidate_indices]

        # ── TF-IDF re-rank (blend 60/40) ──────────────────────────────────────
        if self._tfidf is not None and self._tfidf_matrix is not None and scored:
            import numpy as np
            qvec = self._tfidf.transform([query])
            candidate_list = [idx for idx, _ in scored]
            # Fast slice of TF-IDF matrix for candidates only
            sub_matrix = self._tfidf_matrix[candidate_list]
            tfidf_sub_scores = cosine_similarity(qvec, sub_matrix).flatten()

            bm25_vals = np.array([s for _, s in scored])
            bm25_max = bm25_vals.max() or 1.0
            tfidf_max = tfidf_sub_scores.max() or 1.0

            blended = []
            for sub_i, (doc_idx, bm25_s) in enumerate(scored):
                blend = 0.6 * (bm25_s / bm25_max) + 0.4 * (tfidf_sub_scores[sub_i] / tfidf_max)
                blended.append((doc_idx, blend))
            scored = blended

        # ── Phrase & Suggested Section boost ───────────────────────────────────
        query_lower = query.lower()
        phrase_words = query_lower.split()

        clean_target_secs = set()
        if section_filter:
            for sf in section_filter:
                digits_match = re.findall(r"\d+[A-Za-z]?", sf)
                for d in digits_match:
                    clean_target_secs.add(d.lower())

        boosted = []
        for doc_idx, score in scored:
            doc = self.documents[doc_idx]
            boost = 1.0
            # Boost if any 2-gram from query appears verbatim
            for i in range(len(phrase_words) - 1):
                phrase = f"{phrase_words[i]} {phrase_words[i+1]}"
                if phrase in doc.text.lower():
                    boost += 0.3

            # Suggested section boost (prevents cross-section noise)
            if clean_target_secs:
                doc_sec = str(doc.metadata.get("section_number", "")).lower().strip()
                if doc_sec and any(ts == doc_sec or doc_sec.startswith(ts) for ts in clean_target_secs):
                    boost += 1.5

            boosted.append((doc_idx, score * boost))

        # ── Sort and threshold ─────────────────────────────────────────────────
        boosted.sort(key=lambda x: x[1], reverse=True)
        results = []
        for doc_idx, score in boosted[:top_k]:
            if score < score_threshold:
                break
            doc = self.documents[doc_idx]
            results.append({
                "text": doc.text,
                "metadata": doc.metadata,
                "source": doc.source,
                "score": round(float(score), 4),
                "retrieval_method": "bm25_keyword",
                "doc_id": doc.doc_id,
            })
        return results

    def _term_overlap_scores(self, query_tokens: List[str]) -> List[Tuple[int, float]]:
        """Simple term overlap fallback (no external deps)."""
        query_set = set(query_tokens)
        scored = []
        for i, doc in enumerate(self.documents):
            doc_set = set(doc.tokens)
            overlap = len(query_set & doc_set)
            total = len(query_set | doc_set) or 1
            scored.append((i, overlap / total))
        return scored

    # ── Utilities ──────────────────────────────────────────────────────────────
    def __len__(self) -> int:
        return len(self.documents)

    def stats(self) -> Dict:
        return {
            "name": self.name,
            "doc_count": len(self.documents),
            "index_built": self._built,
            "mode": "BM25" if _BM25_AVAILABLE else ("TF-IDF" if _TFIDF_AVAILABLE else "TermOverlap"),
        }


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADER  —  populates VectorlessBM25Store from project data files
# ══════════════════════════════════════════════════════════════════════════════
PROJECT_ROOT = Path(__file__).parent.parent.parent

_DATA_PATHS = [
    PROJECT_ROOT / "kaanoon_test" / "kaanoon_qa_dataset.json",
    PROJECT_ROOT / "kaanoon_test" / "kaanoon_qa_dataset_cleaned.json",
    PROJECT_ROOT / "kaanoon_test" / "kaanoon_qa_expanded.json",
    PROJECT_ROOT / "kaanoon_test" / "landmark_cases_database.json",
    PROJECT_ROOT / "kaanoon_test" / "gst_it_professionals_2024.json",
    # FREE, SHIPPABLE GROUNDING. Every other retrieval path was dead: Zilliz is
    # stopped, and PERMANENT_RAG_FILES holds only Chroma binaries that this
    # loader cannot read (and which are excluded from the deploy zip anyway).
    # This JSON is a flat list of statute chunks extracted from the local Chroma
    # store, so the corpus actually travels with the app at no running cost.
    PROJECT_ROOT / "kaanoon_test" / "free_corpus" / "statute_chunks.json",
    PROJECT_ROOT / "PERMANENT_RAG_FILES" / "MAIN_DATABASE",
    PROJECT_ROOT / "PERMANENT_RAG_FILES" / "STATUTE_DATABASE",
    # BACKUP data folder
    PROJECT_ROOT.parent.parent / "BACKUP_DATA" / "DATA",
]


def _load_json_file(path: Path, store: VectorlessBM25Store) -> int:
    """Load a single JSON file into the store. Returns doc count added."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except Exception as e:
        logger.debug(f"[VL-BM25] Skip {path.name}: {e}")
        return 0

    added = 0
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                text = (
                    item.get("answer") or item.get("text") or
                    item.get("content") or item.get("judgment_text") or
                    item.get("summary") or ""
                )
                if item.get("question"):
                    text = f"Q: {item['question']}\nA: {text}"
                if text:
                    store.add_document(text=text, metadata=item, source=str(path.name))
                    added += 1
    elif isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, str) and len(val) > 30:
                store.add_document(text=val, metadata={"key": key}, source=str(path.name))
                added += 1
            elif isinstance(val, dict):
                text = str(val)
                store.add_document(text=text, metadata={"key": key}, source=str(path.name))
                added += 1
    return added


def _load_txt_file(path: Path, store: VectorlessBM25Store, chunk_size: int = 600) -> int:
    """Chunk a TXT file and load into the store."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.debug(f"[VL-BM25] Skip TXT {path.name}: {e}")
        return 0
    sentences = re.split(r"\n{2,}|(?<=[.!?])\s+", text)
    chunk, chunks, added = [], [], 0
    for sent in sentences:
        chunk.append(sent)
        if sum(len(s) for s in chunk) >= chunk_size:
            chunks.append(" ".join(chunk))
            chunk = []
    if chunk:
        chunks.append(" ".join(chunk))
    for c in chunks:
        if c.strip():
            store.add_document(text=c, metadata={"file": path.name}, source=str(path.name))
            added += 1
    return added


def load_all_data(store: Optional[VectorlessBM25Store] = None) -> VectorlessBM25Store:
    """
    Populate (or create) a VectorlessBM25Store from all available project data.
    Returns the ready-to-query store.
    """
    if store is None:
        store = VectorlessBM25Store(name="lawgpt_full")

    total = 0
    for path in _DATA_PATHS:
        p = Path(path)
        if p.is_file():
            if p.suffix == ".json":
                n = _load_json_file(p, store)
            elif p.suffix in (".txt", ".md"):
                n = _load_txt_file(p, store)
            else:
                n = 0
            if n:
                logger.info(f"[VL-BM25] Loaded {n} docs from {p.name}")
                total += n
        elif p.is_dir():
            for fp in p.rglob("*.json"):
                n = _load_json_file(fp, store)
                total += n
            for fp in p.rglob("*.txt"):
                n = _load_txt_file(fp, store)
                total += n

    logger.info(f"[VL-BM25] Total docs loaded: {total}")
    store.build_index()
    return store


# ── Singleton helper ───────────────────────────────────────────────────────────
_GLOBAL_STORE: Optional[VectorlessBM25Store] = None

def get_global_bm25_store() -> VectorlessBM25Store:
    """Return (lazily initialised) global BM25 store."""
    global _GLOBAL_STORE
    if _GLOBAL_STORE is None:
        logger.info("[VL-BM25] Initialising global BM25 store from all data...")
        _GLOBAL_STORE = load_all_data()
    return _GLOBAL_STORE
