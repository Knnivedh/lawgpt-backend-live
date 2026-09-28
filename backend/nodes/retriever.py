import logging

from pymilvus import Collection, connections
from typing import Dict, Iterable, List, Optional

from config import get_settings
from embedding_client import HuggingFaceEmbeddingClient
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
translator = QueryTranslator(settings.translation_model, settings.huggingface_api_key)


def _retrieval_query(combined_query: str, detected_language: str) -> str:
    """
    Return the text to embed/search with. Translates non-English queries to
    English when translation is enabled (and the language is in the optional
    allowlist); falls back to the original query on any failure. The original
    query in graph state is never modified -- this only affects retrieval.
    """
    allowlist = settings.translation_enabled_languages
    if (
        detected_language == "en"
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


def connect_and_load():
    """Connect to Milvus using URI + token and load collection."""
    try:
        connections.connect(alias="default", uri=MILVUS_URI, token=MILVUS_TOKEN)
        loaded_collection = Collection(COLLECTION_NAME)
        loaded_collection.load()
        print(f"Connected to Milvus collection: {COLLECTION_NAME}")
        return loaded_collection
    except Exception as e:
        print(f"Error connecting to Milvus: {e}")
        return None


collection = connect_and_load()


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
    if not child_chunks or not collection:
        return child_chunks

    best_by_parent: Dict[int, Dict] = {}
    for chunk in child_chunks:
        parent_id = chunk["metadata"].get("parent_id")
        if parent_id is None:
            continue
        current_best = best_by_parent.get(parent_id)
        if current_best is None or chunk["score"] > current_best["score"]:
            best_by_parent[parent_id] = chunk

    # Keep only the highest-scoring parents so context stays bounded.
    ranked_parent_ids = sorted(
        best_by_parent, key=lambda pid: best_by_parent[pid]["score"], reverse=True
    )[:MAX_EXPANDED_PARENTS]

    if not ranked_parent_ids:
        return child_chunks

    ids_expr = ", ".join(str(pid) for pid in ranked_parent_ids)
    try:
        parent_rows = collection.query(
            expr=f"is_parent == true and parent_id in [{ids_expr}]",
            output_fields=OUTPUT_FIELDS,
        )
    except Exception as e:
        print(f"Parent expansion query failed, falling back to child chunks: {e}")
        return [best_by_parent[pid] for pid in ranked_parent_ids]

    parent_by_id = {row.get("parent_id"): row for row in parent_rows}

    expanded = []
    for parent_id in ranked_parent_ids:
        child = best_by_parent[parent_id]
        parent_row = parent_by_id.get(parent_id)
        if not parent_row:
            # No parent record found (shouldn't happen once re-indexed) — fall
            # back to the child chunk rather than dropping the result.
            expanded.append(child)
            continue
        expanded.append({
            "content": parent_row.get("content"),
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


def retrieve_documents(state: FamilyLawState) -> Dict:
    """
    Retrieve separate context pools:
    - 5 chunks from legal case / precedent material.
    - 3 law/act chunks by default, or 5 when the configured context window is large.
    """
    root = state.get("root_query") or ""
    query = state.get("query") or ""
    combined_query = f"{root} {query}" if root else query

    if not collection:
        return {"retrieved_chunks": [], "sources": []}

    detected_language = state.get("detected_language") or "en"
    retrieval_query = _retrieval_query(combined_query, detected_language)

    query_embedding = embedding_client.embed([retrieval_query])[0]

    if len(query_embedding) != settings.embedding_dimension:
        print(
            "Warning: Query embedding has "
            f"{len(query_embedding)} dimensions, expected {settings.embedding_dimension}"
        )

    case_limit = settings.retrieval_cases_top_k
    law_limit = _law_limit_for_context()

    # Stage 1 (small): search fine-grained child chunks for precise matching.
    case_hits = _search(
        query_embedding,
        limit=case_limit,
        expr=_combine_exprs(CHILD_ONLY_EXPR, _category_expr(settings.retrieval_case_categories)),
    )

    if not case_hits:
        case_hits = _search(query_embedding, limit=case_limit, expr=CHILD_ONLY_EXPR)

    law_hits = _search(
        query_embedding,
        limit=law_limit,
        expr=_combine_exprs(CHILD_ONLY_EXPR, _category_expr(settings.retrieval_law_categories)),
    )

    case_chunks = [_chunk_from_hit(hit) for hit in case_hits[:case_limit]]
    law_chunks = [_chunk_from_hit(hit) for hit in law_hits[:law_limit]]

    if not law_chunks:
        fallback_hits = _search(
            query_embedding, limit=case_limit + (law_limit * 4), expr=CHILD_ONLY_EXPR
        )
        fallback_chunks = [_chunk_from_hit(hit) for hit in fallback_hits]
        law_chunks = [chunk for chunk in fallback_chunks if _is_law_or_act_chunk(chunk)][:law_limit]

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
