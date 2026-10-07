"""
System Adapters for Testing Different AI Systems
"""

# UltimateRAGAdapter transitively imports chromadb; guard it so the server
# starts even when chromadb is not installed (cloud deployment).
try:
    from .rag_system_adapter_ULTIMATE import UltimateRAGAdapter
    __all__ = ['UltimateRAGAdapter']
except ImportError:
    __all__ = []

