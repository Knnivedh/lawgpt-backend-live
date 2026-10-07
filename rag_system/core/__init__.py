"""
Core RAG System Components
"""

# HybridChromaStore imports chromadb — may not be available on cloud (no sqlite3 >= 3.35.0)
try:
    from rag_system.core.hybrid_chroma_store import HybridChromaStore
    __all__ = ["HybridChromaStore"]
except (ImportError, RuntimeError):
    # chromadb not available or sqlite3 too old — cloud deployments use Milvus/Zilliz instead
    HybridChromaStore = None  # type: ignore
    __all__ = []
