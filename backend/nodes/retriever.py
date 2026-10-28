import logging
import threading
import time

from pymilvus import Collection, connections
from typing import Dict, Iterable, List, Optional, Tuple

from config import get_settings
from context_window import trim_around_match
from corpus_curation import EXCLUDED_PARENT_IDS, subject_key
from keyword_search import KeywordIndex, reciprocal_rank_fusion
from embedding_client import HuggingFaceEmbeddingClient
from lang_utils import looks_like_hinglish
from translation_client import QueryTranslator, TranslationError
from state import FamilyLawState

logger = logging.getLogger(__name__)

settings = get_settings()

COLLECTION_NAME = settings.milvus_collection_name
MODEL_NAME = settings.embedding_model
MILVUS_URI = settings.milvus_uri
MILVUS_TOKEN = settings.milvus_token
OUTPUT_FIELDS = [
    "content",
    "parent_id",
    "title",
    "query_text",
    "url",
    "category",
    "citations",
]

# How many distinct parent items we're willing to fetch full context for.
# Keeps generator.py's context window bounded even if many children match
# the same handful of parents (the common case).
MAX_EXPANDED_PARENTS = 8

# Parents are stored whole. One longer than this (about 1,800 tokens) is cut
# to its opening plus a window around the passage that matched the search.
PARENT_CONTEXT_MAX_CHARS = 7200
PARENT_HEAD_CHARS = 1800

# Child chunks fetched per wanted parent before de-duplicating by parent.
CHILD_OVERFETCH_FACTOR = 6

# Hybrid search: how many parents each ranking (vector, keyword) contributes
# to the merge.
HYBRID_CANDIDATES = 20

# With query rewriting on, what the vector search embeds: "english" (the
# faithful translation), "search" (the short rewritten query) or "both".
REWRITE_EMBED_TEXT = "search"

LAW_HINTS = (
    " act",
    "section",
    "statute",
    "bare act",
    "code",
    " ipc",
    " crpc",
    " cpc",
    "hma",
    "hindu marriage act",
    "domestic violence act",
    "guardians and wards act",
    "special marriage act",
)

print("Retriever Configuration:")
print(f"   Model: {MODEL_NAME}")
print(f"   Collection: {COLLECTION_NAME}")
print(f"   Embedding Dimension: {settings.embedding_dimension}")
print(f"   Case chunks: {settings.retrieval_cases_top_k}")
print(
    "   Law/act chunks: "
    f"{settings.retrieval_laws_top_k} or {settings.retrieval_laws_large_context_top_k} "
    f"(context window >= {settings.large_context_window_threshold})"
)

embedding_client = HuggingFaceEmbeddingClient(MODEL_NAME, settings.embedding_dimension)
translator = QueryTranslator(
    settings.translation_model, settings.huggingface_api_key, settings.translation_providers,
    ollama_model=settings.ollama_translation_model,
    ollama_base_url=settings.ollama_base_url,
    ollama_api_key=settings.ollama_api_key,
)


def _retrieval_query(combined_query: str, detected_language: str) -> str:
    """
    Return the text to embed/search with. Translates non-English queries to
    English when translation is enabled (and the language is in the optional
    allowlist); falls back to the original query on any failure. The original
    query in graph state is never modified -- this only affects retrieval.
    """
    allowlist = settings.translation_enabled_languages
    if (
        (detected_language == "en" and not looks_like_hinglish(combined_query))
        or not settings.enable_query_translation
        or (allowlist and detected_language not in allowlist)
    ):
        return combined_query

    try:
        translated = translator.translate(combined_query)
        logger.info(
            "Query translation for retrieval: language=%s success=True", detected_language
        )
        return translated
    except TranslationError as e:
        logger.warning(
            "Query translation for retrieval: language=%s success=False error=%s",
            detected_language, e,
        )
        return combined_query


def _search_texts(combined_query: str, detected_language: str) -> Tuple[str, str]:
    """
    Return (text to embed, text for keyword search). With query rewriting on,
    one model call gives a faithful English version and a short neutral search
    query; otherwise both texts are the (translated) question. Falls back to
    translation only, then to the original text, if the model call fails.
    """
    if settings.enable_query_rewrite:
        try:
            prepared = translator.prepare_search(combined_query)
            logger.info("Query rewrite for retrieval: language=%s success=True", detected_language)
            both = f"{prepared.search_query}. {prepared.english}"
            embed_text = {"english": prepared.english, "search": prepared.search_query}.get(
                REWRITE_EMBED_TEXT, both
            )
            return embed_text, both
        except TranslationError as e:
            logger.warning(
                "Query rewrite for retrieval: language=%s success=False error=%s",
                detected_language, e,
            )

    text = _retrieval_query(combined_query, detected_language)
    return text, text


def connect_and_load():
    """Connect to Milvus using URI + token and load collection."""
    try:
        connections.connect(alias="default", uri=MILVUS_URI, token=MILVUS_TOKEN, timeout=1.0)
        loaded_collection = Collection(COLLECTION_NAME)
        loaded_collection.load()
        print(f"Connected to Milvus collection: {COLLECTION_NAME}")
        return loaded_collection
    except Exception as e:
        print(f"Error connecting to Milvus: {e}")
        return None


collection = connect_and_load()

_keyword_index: Optional[KeywordIndex] = None
_keyword_index_lock = threading.Lock()
_parent_store: Dict[int, Dict] = {}


def _get_keyword_index() -> Optional[KeywordIndex]:
    """Build the BM25 index over parent documents on first use (Milvus or local chunked files)."""
    global _keyword_index, _parent_store
    if _keyword_index is not None:
        return _keyword_index
    with _keyword_index_lock:
        if _keyword_index is not None:
            return _keyword_index
        started = time.time()
        index = KeywordIndex()

        if collection is not None:
            try:
                iterator = collection.query_iterator(
                    expr="is_parent == true",
                    output_fields=["parent_id", "title", "content", "category", "citations", "url", "query_text"],
                    batch_size=500,
                )
                while True:
                    batch = iterator.next()
                    if not batch:
                        break
                    for row in batch:
                        pid = row["parent_id"]
                        title = row.get("title") or ""
                        content = row.get("content") or ""
                        cat = row.get("category") or ""
                        _parent_store[pid] = {
                            "parent_id": pid,
                            "title": title,
                            "content": content,
                            "category": cat,
                            "citations": row.get("citations", ""),
                            "url": row.get("url", ""),
                            "query_text": row.get("query_text", ""),
                        }
                        index.add(pid, title, content, cat)
                iterator.close()
                index.finalize()
                _keyword_index = index
                logger.info("Keyword index built from Milvus: %d documents in %.1fs", len(index), time.time() - started)
                return _keyword_index
            except Exception as e:
                logger.warning("Milvus query_iterator failed; falling back to local files: %s", e)

        # Local fallback from data/chunked/*.json
        try:
            import json
            from pathlib import Path
            base_dir = Path(__file__).resolve().parent.parent
            chunk_files = [
                base_dir / "data" / "chunked" / "family_law_chunks.json",
                base_dir / "data" / "chunked" / "family_law_2_chunks.json",
            ]
            loaded_count = 0
            for chunk_file in chunk_files:
                if not chunk_file.exists():
                    continue
                with open(chunk_file, "r", encoding="utf-8") as cf:
                    chunks_data = json.load(cf)
                is_law_cat = "2" in chunk_file.name
                default_cat = "family_law_2" if is_law_cat else "family_law"
                for item in chunks_data:
                    meta = item.get("metadata", {})
                    if meta.get("is_parent"):
                        pid = meta.get("parent_id")
                        if pid is None:
                            continue
                        title = meta.get("title") or ""
                        content = item.get("content") or ""
                        cat = meta.get("category") or default_cat
                        citations = meta.get("citations") or []
                        url = meta.get("url") or ""
                        query_txt = meta.get("query-text") or meta.get("query_text") or ""
                        _parent_store[pid] = {
                            "parent_id": pid,
                            "title": title,
                            "content": content,
                            "category": cat,
                            "citations": citations,
                            "url": url,
                            "query_text": query_txt,
                        }
                        index.add(pid, title, content, cat)
                        loaded_count += 1
            index.finalize()
            _keyword_index = index
            logger.info("✅ Keyword index built from local chunked data: %d parents in %.1fs", loaded_count, time.time() - started)
            return _keyword_index
        except Exception as e:
            logger.error("Failed to build local keyword index: %s", e, exc_info=True)
            return None


def _law_limit_for_context() -> int:
    """Use more law/act chunks only when the configured LLM context allows it."""
    if settings.llm_context_window >= settings.large_context_window_threshold:
        return settings.retrieval_laws_large_context_top_k
    return settings.retrieval_laws_top_k


def _category_expr(categories: Iterable[str]) -> Optional[str]:
    cleaned = [category.strip() for category in categories if category and category.strip()]
    if not cleaned:
        return None

    quoted = ", ".join(f'"{category.replace(chr(34), "")}"' for category in cleaned)
    return f"category in [{quoted}]"


def _combine_exprs(*exprs: Optional[str]) -> Optional[str]:
    parts = [expr for expr in exprs if expr]
    if not parts:
        return None
    return " and ".join(f"({expr})" for expr in parts)


# Child-only search: precise matching happens against the fine-grained chunks,
# never against the parent record itself (parent embeddings are coarse and
# would otherwise dilute top-k precision).
CHILD_ONLY_EXPR = "is_parent == false"


def _search(query_embedding: List[float], limit: int, expr: Optional[str] = None):
    if limit <= 0:
        return []

    search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
    kwargs = {
        "data": [query_embedding],
        "anns_field": "embedding",
        "param": search_params,
        "limit": limit,
        "output_fields": OUTPUT_FIELDS,
    }
    if expr:
        kwargs["expr"] = expr

    try:
        results = collection.search(**kwargs)
    except Exception as e:
        print(f"Search error with expr={expr!r}: {e}")
        return []

    return [hit for hits in results for hit in hits]


def _chunk_from_hit(hit) -> Dict:
    return {
        "content": hit.entity.get("content"),
        "score": hit.score,
        "metadata": {
            "parent_id": hit.entity.get("parent_id"),
            "title": hit.entity.get("title"),
            "query_text": hit.entity.get("query_text"),
            "url": hit.entity.get("url"),
            "category": hit.entity.get("category"),
            "citations": hit.entity.get("citations", ""),
        },
    }


def _chunk_key(chunk: Dict) -> tuple:
    metadata = chunk.get("metadata", {})
    return (
        metadata.get("parent_id"),
        metadata.get("title"),
        metadata.get("url"),
        (chunk.get("content") or "")[:200],
    )


def _is_law_or_act_chunk(chunk: Dict) -> bool:
    metadata = chunk.get("metadata", {})
    searchable = " ".join(
        str(value or "")
        for value in (
            metadata.get("category"),
            metadata.get("title"),
            metadata.get("citations"),
            chunk.get("content"),
        )
    ).lower()
    return any(hint in searchable for hint in LAW_HINTS)


def _expand_to_parents(child_chunks: List[Dict]) -> List[Dict]:
    """
    Small-to-big expansion: for each matched child chunk, replace it with its
    parent's full combined text (query + all expert responses) instead of the
    isolated fragment. This is the core hierarchical-RAG fix for grounding —
    the generator sees complete original context instead of a truncated piece
    it would otherwise have to fill in gaps for on its own.
    """
    if not child_chunks:
        return child_chunks

    # Input order is the ranking (vector score, or the merged order in hybrid
    # search), so keep the first chunk seen per parent and preserve that order.
    best_by_parent: Dict[int, Dict] = {}
    for chunk in child_chunks:
        parent_id = chunk["metadata"].get("parent_id")
        if parent_id is None or parent_id in best_by_parent:
            continue
        best_by_parent[parent_id] = chunk

    ranked_parent_ids = list(best_by_parent)[:MAX_EXPANDED_PARENTS]

    if not ranked_parent_ids:
        return child_chunks

    ids_expr = ", ".join(str(pid) for pid in ranked_parent_ids)
    parent_rows = []
    if collection is not None:
        try:
            parent_rows = collection.query(
                expr=f"is_parent == true and parent_id in [{ids_expr}]",
                output_fields=OUTPUT_FIELDS,
            )
        except Exception as e:
            print(f"Parent expansion query failed, falling back to parent_store: {e}")

    parent_by_id = {row.get("parent_id"): row for row in parent_rows}
    for pid in ranked_parent_ids:
        if pid not in parent_by_id and pid in _parent_store:
            parent_by_id[pid] = _parent_store[pid]

    expanded = []
    for parent_id in ranked_parent_ids:
        child = best_by_parent[parent_id]
        parent_row = parent_by_id.get(parent_id)
        if not parent_row:
            # No parent record found (shouldn't happen once re-indexed) — fall
            # back to the child chunk rather than dropping the result.
            if child.get("content"):
                expanded.append(child)
            continue
        expanded.append({
            "content": trim_around_match(
                parent_row.get("content"), child.get("content"),
                PARENT_CONTEXT_MAX_CHARS, PARENT_HEAD_CHARS,
            ),
            "score": child["score"],
            "metadata": {
                "parent_id": parent_id,
                "title": parent_row.get("title"),
                "query_text": parent_row.get("query_text"),
                "url": parent_row.get("url"),
                "category": parent_row.get("category"),
                "citations": parent_row.get("citations", ""),
            },
            "retrieval_group": child.get("retrieval_group"),
            "matched_by": child.get("matched_by", "vector"),
        })

    return expanded


def _dedupe_chunks(chunks: Iterable[Dict]) -> List[Dict]:
    seen = set()
    deduped = []

    for chunk in chunks:
        key = _chunk_key(chunk)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)

    return deduped


def _sources_from_chunks(chunks: Iterable[Dict]) -> List[Dict]:
    sources = []
    seen = set()

    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        key = (metadata.get("title"), metadata.get("url"), metadata.get("category"))
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "title": metadata.get("title"),
                "url": metadata.get("url"),
                "category": metadata.get("category"),
            }
        )

    return sources


def _top_unique_parents(chunks: List[Dict], limit: int) -> List[Dict]:
    """
    Keep the best-ranked chunk per parent, up to `limit` parents. `chunks`
    must already be in ranked order (Milvus returns them best first). With
    corpus curation on, several documents on one subject count as one parent.
    Chunks without a parent_id are kept individually.
    """
    seen = set()
    unique = []
    for chunk in chunks:
        parent_id = chunk["metadata"].get("parent_id")
        if parent_id is not None:
            key = subject_key(parent_id) if settings.enable_corpus_curation else parent_id
            if key in seen:
                continue
            seen.add(key)
        unique.append(chunk)
        if len(unique) >= limit:
            break
    return unique


def _build_retrieval_text(state: FamilyLawState) -> str:
    """
    Search on the original query, not the latest chat message. By the time
    retrieval runs, `state["query"]` is whatever the user typed in the most
    recent turn -- often a follow-up answer ("yes", "I don't know, please
    answer") rather than anything about the legal issue itself. Appending
    that to the search text adds noise and dilutes the embedding away from
    the actual question (confirmed: reproducing a real conversation where
    the last turn was such a non-answer pulled in unrelated precedents).

    Tried also appending a summary of `info_collected` (every fact gathered
    since) on top of root_query, reasoning it would add useful signal with
    less noise than the raw last message. In a side-by-side test it did not
    clearly help -- tangential fields (e.g. income, dowry) pulled the
    embedding toward alimony/financial matches and crowded out sharper
    "right to reside" results that root_query alone found. Not doing that
    for now; root_query alone tested best.

    Exception: when the client attached a document and only wrote a short
    note ("please review this"), that note says nothing to search on, so the
    start of the document is added.
    """
    text = state.get("root_query") or state.get("query") or ""
    document = (state.get("document_context") or "").strip()
    if document and len(text.split()) < 15:
        text = f"{text}\n{document[:600]}".strip()
    return text


def _excluded_expr() -> Optional[str]:
    if not settings.enable_corpus_curation or not EXCLUDED_PARENT_IDS:
        return None
    return f"parent_id not in [{', '.join(str(pid) for pid in sorted(EXCLUDED_PARENT_IDS))}]"


def _merge_with_keywords(
    dense_chunks: List[Dict], keyword_text: str, categories: Iterable[str], limit: int
) -> List[Dict]:
    """
    Hybrid search for one pool: merge the vector ranking with a BM25 keyword
    ranking by reciprocal rank fusion and return the top `limit` documents.
    Documents found only by keyword get a stub chunk; parent expansion fills
    in their text.
    """
    index = _get_keyword_index() if settings.enable_hybrid_search else None
    if index is None:
        return _top_unique_parents(dense_chunks, limit)

    curated = settings.enable_corpus_curation
    key_of = subject_key if curated else (lambda pid: pid)

    dense = [c for c in _top_unique_parents(dense_chunks, HYBRID_CANDIDATES)
             if c["metadata"].get("parent_id") is not None]
    dense_by_parent = {c["metadata"]["parent_id"]: c for c in dense}
    parent_for_subject = {key_of(pid): pid for pid in dense_by_parent}

    keyword_ids = []
    for pid, _score in index.search(
        keyword_text, HYBRID_CANDIDATES, categories=categories,
        exclude_ids=EXCLUDED_PARENT_IDS if curated else None,
    ):
        # Count a keyword hit on the same subject as a hit on the vector result.
        pid = parent_for_subject.get(key_of(pid), pid)
        if pid not in keyword_ids:
            keyword_ids.append(pid)

    floor_score = min((c["score"] for c in dense), default=0.0)
    merged = []
    for pid in reciprocal_rank_fusion(
        [list(dense_by_parent), keyword_ids],
        weights=[settings.retrieval_vector_weight, settings.retrieval_keyword_weight],
    ):
        chunk = dense_by_parent.get(pid)
        if chunk is not None:
            chunk["matched_by"] = "both" if pid in keyword_ids else "vector"
        else:
            chunk = {"content": "", "score": floor_score,
                     "metadata": {"parent_id": pid}, "matched_by": "keyword"}
        merged.append(chunk)
    return _top_unique_parents(merged, limit)


def retrieve_documents(state: FamilyLawState) -> Dict:
    """
    Retrieve separate context pools:
    - 5 documents from legal case / precedent material.
    - 3 law/act documents by default, or 5 when the configured context window is large.
    """
    combined_query = _build_retrieval_text(state)
    detected_language = state.get("detected_language") or "en"
    embed_text, keyword_text = _search_texts(combined_query, detected_language)

    if not collection:
        index = _get_keyword_index()
        if index is not None:
            case_limit = settings.retrieval_cases_top_k
            law_limit = _law_limit_for_context()
            case_hits = index.search(keyword_text, limit=case_limit, categories=settings.retrieval_case_categories)
            if not case_hits:
                case_hits = index.search(keyword_text, limit=case_limit)
            law_hits = index.search(keyword_text, limit=law_limit, categories=settings.retrieval_law_categories)
            if not law_hits:
                law_hits = index.search(keyword_text, limit=law_limit)

            case_chunks = [
                {
                    "content": (_parent_store.get(pid, {}).get("content") or "")[:600],
                    "score": min(float(score) / 10.0, 0.99),
                    "metadata": {
                        "parent_id": pid,
                        "title": _parent_store.get(pid, {}).get("title"),
                        "url": _parent_store.get(pid, {}).get("url"),
                        "category": _parent_store.get(pid, {}).get("category"),
                        "citations": _parent_store.get(pid, {}).get("citations"),
                    },
                    "retrieval_group": "legal_case",
                    "matched_by": "keyword",
                }
                for pid, score in case_hits
            ]
            law_chunks = [
                {
                    "content": (_parent_store.get(pid, {}).get("content") or "")[:600],
                    "score": min(float(score) / 10.0, 0.99),
                    "metadata": {
                        "parent_id": pid,
                        "title": _parent_store.get(pid, {}).get("title"),
                        "url": _parent_store.get(pid, {}).get("url"),
                        "category": _parent_store.get(pid, {}).get("category"),
                        "citations": _parent_store.get(pid, {}).get("citations"),
                    },
                    "retrieval_group": "law_or_act",
                    "matched_by": "keyword",
                }
                for pid, score in law_hits
            ]
            for chunk in case_chunks:
                chunk["retrieval_group"] = "legal_case"
            for chunk in law_chunks:
                chunk["retrieval_group"] = "law_or_act"
            expanded_case_chunks = _expand_to_parents(case_chunks)
            expanded_law_chunks = _expand_to_parents(law_chunks)
            retrieved_chunks = _dedupe_chunks(expanded_case_chunks + expanded_law_chunks)
            sources = _sources_from_chunks(retrieved_chunks)
            logger.info("✅ Retrieved offline BM25 chunks: %d case, %d law (total %d)", len(case_chunks), len(law_chunks), len(retrieved_chunks))
            return {"retrieved_chunks": retrieved_chunks, "sources": sources}
        return {"retrieved_chunks": [], "sources": []}

    # One space between prefix and question whether or not the setting kept its
    # trailing space (.env files and hosting dashboards often strip it).
    prefix = settings.embedding_query_prefix.strip()
    query_embedding = embedding_client.embed([f"{prefix} {embed_text}" if prefix else embed_text])[0]

    if len(query_embedding) != settings.embedding_dimension:
        print(
            "Warning: Query embedding has "
            f"{len(query_embedding)} dimensions, expected {settings.embedding_dimension}"
        )

    case_limit = settings.retrieval_cases_top_k
    law_limit = _law_limit_for_context()

    # Stage 1 (small): search fine-grained child chunks for precise matching.
    # Several top chunks often belong to the same parent (siblings can even
    # share an identical vector), so fetch more chunks than needed and keep
    # the best one per parent. Otherwise 5 hits collapse to 2-3 documents.
    wanted = HYBRID_CANDIDATES if settings.enable_hybrid_search else 0
    case_fetch = max(case_limit * CHILD_OVERFETCH_FACTOR, wanted * 3)
    law_fetch = max(law_limit * CHILD_OVERFETCH_FACTOR, wanted * 3)
    base_expr = _combine_exprs(CHILD_ONLY_EXPR, _excluded_expr())

    case_hits = _search(
        query_embedding,
        limit=case_fetch,
        expr=_combine_exprs(base_expr, _category_expr(settings.retrieval_case_categories)),
    )

    if not case_hits:
        case_hits = _search(query_embedding, limit=case_fetch, expr=base_expr)

    law_hits = _search(
        query_embedding,
        limit=law_fetch,
        expr=_combine_exprs(base_expr, _category_expr(settings.retrieval_law_categories)),
    )

    case_chunks = _merge_with_keywords(
        [_chunk_from_hit(hit) for hit in case_hits], keyword_text,
        settings.retrieval_case_categories, case_limit,
    )
    law_chunks = _merge_with_keywords(
        [_chunk_from_hit(hit) for hit in law_hits], keyword_text,
        settings.retrieval_law_categories, law_limit,
    )

    if not law_chunks:
        fallback_hits = _search(query_embedding, limit=case_fetch + law_fetch, expr=base_expr)
        fallback_chunks = [_chunk_from_hit(hit) for hit in fallback_hits]
        law_chunks = _top_unique_parents(
            [chunk for chunk in fallback_chunks if _is_law_or_act_chunk(chunk)], law_limit
        )

    for chunk in case_chunks:
        chunk["retrieval_group"] = "legal_case"
    for chunk in law_chunks:
        chunk["retrieval_group"] = "law_or_act"

    # Stage 2 (big): expand each matched child back to its parent's full,
    # ungrounded-free context before handing it to the generator.
    expanded_case_chunks = _expand_to_parents(case_chunks)
    expanded_law_chunks = _expand_to_parents(law_chunks)

    retrieved_chunks = _dedupe_chunks(expanded_case_chunks + expanded_law_chunks)
    sources = _sources_from_chunks(retrieved_chunks)

    print(
        "Retrieved "
        f"{len(case_chunks)} legal-case chunks and {len(law_chunks)} law/act chunks, "
        f"expanded to {len(retrieved_chunks)} unique parent contexts"
    )

    return {
        "retrieved_chunks": retrieved_chunks,
        "sources": sources,
    }
