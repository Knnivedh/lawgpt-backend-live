"""
HYBRID VECTOR STORE (ChromaDB + BM25) - Python 3.13 Compatible
Combines Vector Search + BM25 Keyword Search
"""

try:
    import chromadb
    from chromadb.config import Settings
except (ImportError, RuntimeError) as _chroma_err:
    chromadb = None  # type: ignore
    Settings = None  # type: ignore
try:
    from sentence_transformers import SentenceTransformer
except (ImportError, RuntimeError) as _st_err:
    SentenceTransformer = None  # type: ignore
from rank_bm25 import BM25Okapi
from typing import Any, List, Dict, Optional
import logging
import os
from tqdm import tqdm
import numpy as np
import pickle
from pathlib import Path

# Try to load permanent config
try:
    import rag_config
    DEFAULT_PERSIST = str(rag_config.MAIN_DB_PATH)
    DEFAULT_COLLECTION = rag_config.MAIN_COLLECTION
except ImportError:
    DEFAULT_PERSIST = "chroma_db_hybrid"
    DEFAULT_COLLECTION = "legal_db_hybrid"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RemoteNvidiaEmbedder:
    """Lightweight remote embedder using NVIDIA NIM API.
    Does not depend on PyTorch or sentence-transformers.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        dimension: int = 384,
    ):
        self.api_key = (
            api_key
            or os.getenv("NVIDIA_API_KEY")
            or os.getenv("nvidia_api")
            or os.getenv("NVIDIA_API_KEY_2")
            or os.getenv("nvidia_api_2")
            or ""
        )
        self.base_url = (base_url or os.getenv("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1").rstrip("/")
        self.model = model or os.getenv("NVIDIA_EMBEDDING_MODEL") or "nvidia/embed-qa-4"
        self.dimension = dimension

    def get_sentence_embedding_dimension(self) -> int:
        return self.dimension

    def encode(
        self,
        texts: Any,
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
        **kwargs,
    ) -> Any:
        import requests

        if isinstance(texts, str):
            input_list = [texts]
            is_single = True
        elif isinstance(texts, (list, tuple)):
            input_list = list(texts)
            is_single = False
        else:
            input_list = [str(texts)]
            is_single = True

        if not self.api_key:
            raise RuntimeError("NVIDIA_API_KEY is not configured for RemoteNvidiaEmbedder")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": input_list,
            "model": self.model,
            "input_type": "query",
            "encoding_format": "float",
        }
        timeout = float(os.getenv("NVIDIA_EMBEDDING_TIMEOUT", "10"))
        resp = requests.post(f"{self.base_url}/embeddings", headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        embeddings = [item["embedding"] for item in data["data"]]
        if convert_to_numpy:
            arr = np.array(embeddings, dtype=np.float32)
            return arr[0] if is_single else arr
        return embeddings[0] if is_single else embeddings


class FastEmbeddingWrapper:
    """Lightweight fallback wrapper supporting fastembed or ONNX or basic CPU embeddings.
    Does not crash if dependencies are missing.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", dimension: int = 384):
        self.model_name = model_name
        self.dimension = dimension
        self._backend = None
        try:
            from fastembed import TextEmbedding

            self._backend = TextEmbedding(model_name=model_name)
        except Exception:
            self._backend = None

    def get_sentence_embedding_dimension(self) -> int:
        return self.dimension

    def encode(
        self,
        texts: Any,
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
        **kwargs,
    ) -> Any:
        if self._backend is None:
            raise RuntimeError("FastEmbedding backend is not available")
        if isinstance(texts, str):
            input_list = [texts]
            is_single = True
        else:
            input_list = list(texts)
            is_single = False
        embeddings = list(self._backend.embed(input_list))
        if convert_to_numpy:
            arr = np.array(embeddings, dtype=np.float32)
            return arr[0] if is_single else arr
        return embeddings[0] if is_single else embeddings


class HybridChromaStore:
    """
    HYBRID VECTOR STORE with ChromaDB (Python 3.13 compatible):
    
    1. Hybrid Search: Vector (semantic) + BM25 (keyword)
    2. Good Embeddings: MiniLM (384 dimensions, most reliable)
    3. Reciprocal Rank Fusion (RRF) for combining results
    4. Optimized for legal terminology
    """
    
    def __init__(
        self,
        persist_directory: str = DEFAULT_PERSIST,
        collection_name: str = DEFAULT_COLLECTION,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"  # Most reliable
    ):
        """
        Initialize Hybrid ChromaDB Store
        
        Args:
            persist_directory: Where to store database
            collection_name: Name of collection
            embedding_model: HuggingFace embedding model
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.is_vector_db_healthy = True  # FLag to disable vector search if unstable
        self.collection_name = collection_name

        # The Chroma collection handle is ALWAYS defined, so `hasattr(store,
        # "collection")` can never be mistaken for "the collection works".
        # Readiness is decided by probe_collection(), which runs a real count().
        self.collection = None
        self.client = None
        self.collection_unavailable_reason: Optional[str] = None

        # Chroma runtime check: ONLY dependent on chromadb binary availability,
        # decoupled from mandatory local SentenceTransformer!
        _chroma_ok = chromadb is not None and Settings is not None
        if not _chroma_ok:
            self._init_bm25_only("chromadb_runtime_unavailable")
            return
        
        # Initialize ChromaDB with persistence (pre-check size to avoid OOM)
        logger.info(f"Initializing ChromaDB at: {persist_directory}")
        # Total-directory guard BEFORE opening: oversized legacy HNSW indexes
        # cannot fit in RAM and crash the process (cloud fallback is the path
        # for large corpora). Tune via LOCAL_VECTOR_MAX_GB.
        _max_gb = float(os.getenv("LOCAL_VECTOR_MAX_GB", "8"))
        _total_bytes = sum(
            f.stat().st_size for f in self.persist_directory.rglob("*") if f.is_file()
        )
        if _total_bytes > _max_gb * (1024 ** 3):
            logger.warning(
                f"[SAFETY-LIMIT] {self.persist_directory} holds "
                f"{_total_bytes / (1024 ** 3):.1f}GB (limit {_max_gb}GB). Skipping local "
                f"Chroma open for '{collection_name}' — cloud fallback active. "
                f"Raise LOCAL_VECTOR_MAX_GB to force local vector search."
            )
            self.is_vector_db_healthy = False
            self.embedding_model = None
            self.embedding_dim = 0
            self.bm25 = None
            self.documents = []
            self.doc_ids = []
            self.metadatas = []
            self.legal_tokenizer = None
            self.collection = None
            self.client = None
            self.collection_unavailable_reason = "persist_directory_exceeds_safety_limit"
            return

        sqlite_file = self.persist_directory / "chroma.sqlite3"
        if sqlite_file.exists():
            size_gb = sqlite_file.stat().st_size / (1024**3)
            if size_gb > 10.0:
                 logger.warning(f"  [SAFETY-LIMIT] {persist_directory} is {size_gb:.2f}GB. This exceeds the 10GB memory safety limit.")
                 raise ValueError(f"Database too large ({size_gb:.2f}GB) - risk of process crash.")
        
        try:
            self.client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=Settings(anonymized_telemetry=False)
            )
        except Exception as exc:
            # A corrupt/unreadable chroma.sqlite3 used to raise straight out of
            # the constructor. That destroyed the whole store object, so the
            # health endpoint could not say WHY retrieval was gone - it just
            # reported a missing store. Degrade to keyword-only retrieval and
            # record the real cause so the endpoint can report an honest
            # not-ready verdict with a reason attached.
            logger.error(
                "[CHROMA-OPEN-FAILED] %s: %s - falling back to BM25-only",
                type(exc).__name__, exc,
            )
            self._init_bm25_only(f"chroma_open_failed: {type(exc).__name__}: {exc}")
            return

        # Decouple HybridChromaStore from mandatory local SentenceTransformer!
        # Resolution order:
        # 1. Local SentenceTransformer (if installed and functioning)
        # 2. Remote NVIDIA Embedder (if EMBEDDING_PROVIDER=='nvidia' or NVIDIA_API_KEY present)
        # 3. FastEmbeddingWrapper (if fastembed installed)
        # 4. Graceful Fallback: read-only / metadata mode (collection handle remains valid!)
        self.embedding_model = None
        self.embedding_dim = 384
        self.embedding_mode = "none"

        _provider = os.getenv("EMBEDDING_PROVIDER", "").strip().lower()
        _nvidia_key = (
            os.getenv("NVIDIA_API_KEY")
            or os.getenv("nvidia_api")
            or os.getenv("NVIDIA_API_KEY_2")
            or os.getenv("nvidia_api_2")
            or ""
        )

        if SentenceTransformer is not None:
            try:
                logger.info(f"Loading local embedding model: {embedding_model}")
                self.embedding_model = SentenceTransformer(embedding_model)
                self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
                self.embedding_mode = "local_sentence_transformers"
                logger.info(f"  [OK] Local embedding model loaded: {self.embedding_dim}D")
            except Exception as exc:
                logger.warning(f"Local SentenceTransformer failed ({exc}), checking alternatives...")

        if self.embedding_model is None and (_provider == "nvidia" or _nvidia_key):
            try:
                logger.info("Configuring RemoteNvidiaEmbedder for ChromaDB...")
                remote_emb = RemoteNvidiaEmbedder(api_key=_nvidia_key, dimension=384)
                self.embedding_model = remote_emb
                self.embedding_dim = remote_emb.get_sentence_embedding_dimension()
                self.embedding_mode = "remote_nvidia"
                logger.info(f"  [OK] RemoteNvidiaEmbedder configured: {self.embedding_dim}D")
            except Exception as exc:
                logger.warning(f"RemoteNvidiaEmbedder initialization failed ({exc})")

        if self.embedding_model is None:
            try:
                fast_emb = FastEmbeddingWrapper(model_name=embedding_model, dimension=384)
                if getattr(fast_emb, "_backend", None) is not None:
                    self.embedding_model = fast_emb
                    self.embedding_dim = fast_emb.get_sentence_embedding_dimension()
                    self.embedding_mode = "fastembed"
                    logger.info("  [OK] FastEmbeddingWrapper initialized")
            except Exception:
                pass

        if self.embedding_model is None:
            self.embedding_mode = "read_only_metadata"
            logger.info(
                f"[CHROMA-METADATA-MODE] Operating ChromaDB collection '{collection_name}' "
                f"in read-only / metadata mode (count and metadata queries available)."
            )
        
        # BM25 for keyword search
        self.bm25 = None
        self.documents = []
        self.doc_ids = []
        self.metadatas = []
        self.legal_tokenizer = None
        try:
            from rag_system.core.legal_tokenizer import LegalTokenizer

            self.legal_tokenizer = LegalTokenizer()
            logger.info("LegalTokenizer enabled for BM25 tokenization")
        except Exception as e:
            logger.warning(f"LegalTokenizer unavailable, using basic tokenization: {e}")
        
        # BM25 cache file
        self.bm25_cache_file = self.persist_directory / f"{collection_name}_bm25.pkl"
        
        # Create or load collection
        try:
            self._initialize_collection()
        except Exception as exc:
            # Same rationale as above: a failure while resolving the collection
            # must leave a diagnosable store behind, not propagate.
            logger.error(
                "[COLLECTION-INIT-FAILED] %s: %s - falling back to BM25-only",
                type(exc).__name__, exc,
            )
            self._init_bm25_only(f"collection_init_failed: {type(exc).__name__}: {exc}")
            return

    def _init_bm25_only(self, reason: str):
        """Put the store into a well-defined keyword-only state.

        Used whenever the Chroma runtime cannot provide a usable collection
        handle (import failure, corrupt sqlite, oversized index). The object
        stays constructible so retrieval keeps working through BM25 and - the
        point of this refactor - so the health endpoint can report an honest
        not-ready verdict WITH a cause instead of a bare None.
        """
        logger.warning(
            "[BM25-ONLY] %s - vector search disabled for '%s'; "
            "keyword (BM25) retrieval from the cache remains active.",
            reason, self.collection_name,
        )
        self.client = None
        self.collection = None
        self.collection_unavailable_reason = reason
        self.is_vector_db_healthy = False
        self.embedding_model = None
        self.embedding_dim = 0
        self.bm25 = None
        self.documents = []
        self.doc_ids = []
        self.metadatas = []
        self.legal_tokenizer = None
        try:
            from rag_system.core.legal_tokenizer import LegalTokenizer
            self.legal_tokenizer = LegalTokenizer()
        except Exception:
            pass
        self.bm25_cache_file = self.persist_directory / f"{self.collection_name}_bm25.pkl"
        if self.bm25_cache_file.exists():
            try:
                with open(self.bm25_cache_file, "rb") as f:
                    bm25_data = pickle.load(f)
                    self.bm25 = bm25_data["bm25"]
                    self.documents = bm25_data["documents"]
                    self.doc_ids = bm25_data["doc_ids"]
                    self.metadatas = bm25_data["metadatas"]
                logger.info(
                    "[OK] BM25-only store ready: %s documents for '%s'",
                    len(self.documents), self.collection_name,
                )
            except Exception as e:
                logger.error("BM25 cache load failed: %s", e)

    def _tokenize_for_bm25(self, text: str, is_query: bool = False) -> List[str]:
        raw_text = str(text or "")
        if self.legal_tokenizer is not None:
            try:
                tokens = self.legal_tokenizer.tokenize(raw_text, preserve_entities=True)
                if tokens:
                    return tokens
            except Exception as e:
                logger.debug(f"Legal tokenizer failed, falling back to split: {e}")

        fallback_tokens = raw_text.lower().split()
        if fallback_tokens:
            return fallback_tokens

        return [raw_text.lower()] if is_query and raw_text else []
    
    def _initialize_collection(self):
        """Create or load ChromaDB collection"""
        try:
            self.collection = self.client.get_collection(self.collection_name)
            logger.info(f"[OK] Loaded existing collection: {self.collection_name}")
            
            # Load BM25 index
            if self.bm25_cache_file.exists():
                try:
                    with open(self.bm25_cache_file, 'rb') as f:
                        bm25_data = pickle.load(f)
                        self.bm25 = bm25_data['bm25']
                        self.documents = bm25_data['documents']
                        self.doc_ids = bm25_data['doc_ids']
                        self.metadatas = bm25_data['metadatas']
                    logger.info(f"[OK] Loaded BM25 index with {len(self.documents)} documents")
                except Exception as e:
                    logger.error(f"Failed to load BM25 cache: {e}")
                    logger.info("Attempting to rebuild BM25 index...")
                    self._rebuild_bm25_from_chromadb()
                
                # Check if BM25 cache is out of sync with ChromaDB
                # Check if BM25 cache is out of sync with ChromaDB
                try:
                    # SAFE MODE: Try to count, but if it crashes, trust the cache
                    logger.info("Verifying consistency with vector store...")
                    chroma_count = self.collection.count()
                    
                    if len(self.documents) != chroma_count:
                        logger.warning(f"BM25 cache mismatch: {len(self.documents)} docs vs ChromaDB {chroma_count} docs")
                        logger.info("Rebuilding BM25 index from ChromaDB...")
                        self._rebuild_bm25_from_chromadb()
                except Exception as e:
                    logger.warning(f"Could not verify Vector Store consistency: {e}")
                    logger.warning("Proceeding with Cached BM25 data only.")
                    self.is_vector_db_healthy = False
            else:
                # If ChromaDB has documents but no BM25 cache, rebuild it
                logger.info(f"Probing collection size for {self.collection_name}...")
                # count() is a plain SQL COUNT in modern chromadb — safe to run.
                # Loading oversized HNSW indexes into RAM caused OOM crashes
                # historically, so guard by index size before enabling vectors.
                try:
                    count = self.collection.count()
                    index_bytes = sum(
                        f.stat().st_size for f in self.persist_directory.rglob("*.bin")
                    )
                    max_gb = float(os.getenv("LOCAL_VECTOR_MAX_GB", "8"))
                    if index_bytes > max_gb * (1024 ** 3):
                        logger.warning(
                            f"[SAFETY-LIMIT] HNSW index {index_bytes / (1024 ** 3):.1f}GB "
                            f"exceeds {max_gb}GB limit — vector search disabled for "
                            f"'{self.collection_name}' (cloud fallback active). Resume the "
                            f"Zilliz cluster or raise LOCAL_VECTOR_MAX_GB to override."
                        )
                        self.is_vector_db_healthy = False
                    else:
                        self.is_vector_db_healthy = True
                        logger.info(
                            f"  [OK] Vector DB healthy — {count} documents in "
                            f"'{self.collection_name}' (index {index_bytes / (1024 ** 2):.0f}MB)"
                        )
                        if 0 < count < 200_000:
                            logger.info("Rebuilding BM25 index from ChromaDB (one-time, cached afterwards)...")
                            self._rebuild_bm25_from_chromadb()
                except Exception:
                     count = 0
                     self.is_vector_db_healthy = False
                     logger.warning("Local DB probe failed - Defaulting to empty (0 docs). Cloud fallback active.")


        except Exception as e:
            logger.info(f"Collection not found, creating new: {self.collection_name}")
            logger.debug(f"Error: {e}")
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Indian Legal Database - Hybrid Search"}
            )
    
    def _rebuild_bm25_from_chromadb(self):
        """Rebuild BM25 index from ChromaDB documents"""
        logger.info("Loading all documents from ChromaDB...")
        all_docs = self.collection.get()
        
        if not all_docs['ids']:
            logger.warning("No documents in ChromaDB to rebuild BM25")
            return
        
        self.documents = all_docs['documents']
        self.doc_ids = all_docs['ids']
        self.metadatas = all_docs['metadatas'] or [{}] * len(all_docs['ids'])
        
        logger.info(f"Rebuilding BM25 index with {len(self.documents):,} documents...")
        tokenized_docs = [self._tokenize_for_bm25(doc) for doc in self.documents]
        self.bm25 = BM25Okapi(tokenized_docs)
        
        # Save BM25 cache
        with open(self.bm25_cache_file, 'wb') as f:
            pickle.dump({
                'bm25': self.bm25,
                'documents': self.documents,
                'doc_ids': self.doc_ids,
                'metadatas': self.metadatas
            }, f)
        
        logger.info(f"[OK] BM25 index rebuilt with {len(self.documents):,} documents")
    
    
    # Public alias for manual rebuild
    rebuild_index = _rebuild_bm25_from_chromadb

    def add_documents(
        self,
        documents: List[Dict],
        batch_size: int = 100,
        show_progress: bool = True,
        rebuild_bm25: bool = True
    ):
        """
        Add documents with HYBRID indexing
        
        Args:
            documents: List of dicts with 'id', 'text', 'metadata'
            batch_size: Batch size
            show_progress: Show progress bar
            rebuild_bm25: Whether to rebuild BM25 index (set False for bulk ingestion)
        """
        logger.info(f"Adding {len(documents)} documents to HYBRID store...")
        logger.info("  [1/3] Generating embeddings...")
        
        # Load existing documents from ChromaDB if not already loaded
        if not self.documents and self.collection.count() > 0:
            logger.info("  Loading existing documents from database...")
            existing_docs = self.collection.get()
            if existing_docs['ids']:
                self.documents = existing_docs['documents']
                self.doc_ids = existing_docs['ids']
                self.metadatas = existing_docs['metadatas'] or [{}] * len(existing_docs['ids'])
        
        # Prepare new documents for BM25
        new_texts = [doc['text'] for doc in documents]
        new_ids = [doc['id'] for doc in documents]
        # Fix metadata: convert lists to strings
        new_metadata = []
        for doc in documents:
            metadata = doc['metadata'].copy()
            for key, value in metadata.items():
                if isinstance(value, list):
                    metadata[key] = ', '.join(str(v) for v in value)
            new_metadata.append(metadata)
        
        # Append new documents to existing lists (FIX: extend instead of replace)
        self.documents.extend(new_texts)
        self.doc_ids.extend(new_ids)
        self.metadatas.extend(new_metadata)
        
        # Build BM25 with ALL documents (existing + new)
        if rebuild_bm25:
            logger.info("  [2/3] Building BM25 keyword index with all documents...")
            tokenized_docs = [self._tokenize_for_bm25(doc) for doc in self.documents]
            self.bm25 = BM25Okapi(tokenized_docs)
            
            # Save BM25
            with open(self.bm25_cache_file, 'wb') as f:
                pickle.dump({
                    'bm25': self.bm25,
                    'documents': self.documents,
                    'doc_ids': self.doc_ids,
                    'metadatas': self.metadatas
                }, f)
            logger.info("  ✓ BM25 index saved")
        else:
            logger.info("  [2/3] Skipping BM25 rebuild (bulk mode)")
        
        # Add to ChromaDB
        if self.collection is None:
            logger.info("  [3/3] No active ChromaDB collection - skipping vector collection insert (BM25 only).")
        else:
            logger.info("  [3/3] Adding documents to ChromaDB collection...")
            total_batches = (len(documents) + batch_size - 1) // batch_size
            iterator = tqdm(
                range(0, len(documents), batch_size),
                total=total_batches,
                desc="Adding docs"
            ) if show_progress else range(0, len(documents), batch_size)
            
            dim = getattr(self, "embedding_dim", 384) or 384
            for i in iterator:
                batch = documents[i:i+batch_size]
                batch_texts = [doc['text'] for doc in batch]
                
                embeddings = None
                if self.embedding_model is not None:
                    try:
                        embs = self.embedding_model.encode(
                            batch_texts,
                            show_progress_bar=False,
                            convert_to_numpy=True
                        )
                        if hasattr(embs, "tolist"):
                            embeddings = embs.tolist()
                        elif isinstance(embs, list):
                            embeddings = embs
                        else:
                            embeddings = list(embs)
                    except Exception as emb_exc:
                        logger.warning(f"Vector embedding batch failed ({emb_exc}); falling back to zero-vector metadata insert.")

                if embeddings is None:
                    embeddings = [[0.0] * dim for _ in range(len(batch))]

                # Add to ChromaDB
                ids = [batch[j]['id'] for j in range(len(batch))]
                # Fix metadata: convert lists to strings for ChromaDB compatibility
                metadatas = []
                for j in range(len(batch)):
                    metadata = batch[j]['metadata'].copy()
                    for key, value in metadata.items():
                        if isinstance(value, list):
                            metadata[key] = ', '.join(str(v) for v in value)
                    metadatas.append(metadata)
                
                try:
                    self.collection.add(
                        ids=ids,
                        embeddings=embeddings,
                        documents=batch_texts,
                        metadatas=metadatas
                    )
                except Exception as add_exc:
                    logger.warning(f"ChromaDB collection.add failed ({add_exc}); continuing with remaining.")
        
        logger.info(f"✓ Added {len(documents)} documents successfully")
        logger.info(f"  Vector index: {len(documents)} embeddings ({self.embedding_dim}D)")
        logger.info(f"  BM25 index: {len(self.documents)} documents")
    
    def _vector_search(self, query: str, n_results: int) -> List[Dict]:
        """Pure vector search"""
        if not getattr(self, 'is_vector_db_healthy', True):
            logger.warning("Vector DB is unhealthy. Skipping vector search to avoid crash.")
            return []

        if self.embedding_model is None or self.collection is None:
            logger.debug("Embedding model or collection unavailable for vector search. Skipping.")
            return []

        try:
            query_emb = self.embedding_model.encode([query])
            if hasattr(query_emb, "tolist"):
                query_embedding = query_emb.tolist()
            elif isinstance(query_emb, list):
                query_embedding = query_emb
            else:
                query_embedding = list(query_emb)

            if query_embedding and not isinstance(query_embedding[0], list):
                query_embedding = [query_embedding]

            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=n_results * 2,
                include=['documents', 'metadatas', 'distances']
            )
            
            if not results or not results['documents']:
                return []
            
            return [
                {
                    'id': results['ids'][0][i],
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'score': 1 - results['distances'][0][i],
                    'source': 'vector'
                }
                for i in range(len(results['documents'][0]))
            ]
        except Exception as exc:
            logger.warning(f"Vector search failed ({type(exc).__name__}: {exc}) - falling back to BM25.")
            return []
    
    def _bm25_search(self, query: str, n_results: int) -> List[Dict]:
        """Pure keyword search"""
        if not self.bm25:
            return []
        
        query_tokens = self._tokenize_for_bm25(query, is_query=True)
        if not query_tokens:
            return []
        scores = self.bm25.get_scores(query_tokens)
        
        top_indices = np.argsort(scores)[::-1][:n_results * 2]
        
        return [
            {
                'id': self.doc_ids[i],
                'text': self.documents[i],
                'metadata': self.metadatas[i],
                'score': float(scores[i]),
                'source': 'bm25'
            }
            for i in top_indices
            if scores[i] > 0
        ]
    
    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Dict],
        bm25_results: List[Dict],
        k: int = 60
    ) -> List[Dict]:
        """Combine results using RRF"""
        doc_scores = {}
        
        # Add vector scores
        for rank, doc in enumerate(vector_results):
            doc_id = doc['id']
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    'id': doc_id,
                    'text': doc['text'],
                    'metadata': doc['metadata'],
                    'rrf_score': 0,
                    'vector_score': doc['score'],
                    'bm25_score': 0,
                    'sources': []
                }
            doc_scores[doc_id]['rrf_score'] += 1 / (k + rank + 1)
            doc_scores[doc_id]['sources'].append('vector')
        
        # Add BM25 scores
        for rank, doc in enumerate(bm25_results):
            doc_id = doc['id']
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    'id': doc_id,
                    'text': doc['text'],
                    'metadata': doc['metadata'],
                    'rrf_score': 0,
                    'vector_score': 0,
                    'bm25_score': doc['score'],
                    'sources': []
                }
            doc_scores[doc_id]['rrf_score'] += 1 / (k + rank + 1)
            doc_scores[doc_id]['bm25_score'] = doc['score']
            doc_scores[doc_id]['sources'].append('bm25')
        
        # Sort by RRF score
        ranked = sorted(doc_scores.values(), key=lambda x: x['rrf_score'], reverse=True)
        
        return ranked
    
    def hybrid_search(
        self,
        query: str,
        n_results: int = 5,
        alpha: float = 0.5
    ) -> List[Dict]:
        """
        HYBRID SEARCH: Vector + BM25
        
        Args:
            query: Search query
            n_results: Number of results
            alpha: Weight (not used in RRF, kept for compatibility)
        
        Returns:
            List of ranked documents
        """
        logger.info(f"🔍 Hybrid search: '{query}'")
        
        # Vector search
        vector_results = self._vector_search(query, n_results)
        logger.info(f"  Vector: {len(vector_results)} results")
        
        # BM25 search
        bm25_results = self._bm25_search(query, n_results)
        logger.info(f"  BM25: {len(bm25_results)} results")
        
        # Fusion
        fused = self._reciprocal_rank_fusion(vector_results, bm25_results)
        logger.info(f"  Fused: {len(fused)} unique documents")
        
        return fused[:n_results]
    
    def count(self) -> int:
        """Get total number of documents"""
        return len(self.documents)
    
    def get_collection_info(self) -> Dict:
        """Get collection information"""
        return {
            'name': self.collection_name,
            'count': len(self.documents),
            'embedding_dim': self.embedding_dim,
            'has_bm25': self.bm25 is not None,
            'persist_directory': str(self.persist_directory)
        }

    # ------------------------------------------------------------------
    # G3: honest readiness. The previous health probe used
    # `hasattr(store, "collection")` and then called `.count()` on whatever
    # that produced. With a None handle that manufactured
    # "AttributeError: 'NoneType' object has no attribute 'count'" while
    # readiness was still reported True, because the ATTRIBUTE existed.
    # probe_collection() runs a real operation instead.
    # ------------------------------------------------------------------

    def probe_collection(self) -> Dict:
        """Exercise the Chroma collection handle with a real operation.

        Returns a dict that is always safe to serialise into a health payload:

          collection_present   - a handle object exists
          collection_usable    - a real count() against it succeeded
          collection_count     - the real count, or None
          collection_count_error - None unless a real operation actually failed
        """
        out: Dict = {
            "collection_name": self.collection_name,
            "collection_present": False,
            "collection_usable": False,
            "collection_count": None,
            "collection_repr": None,
            "collection_count_error": None,
            "collection_unavailable_reason": self.collection_unavailable_reason,
            "bm25_usable": bool(self.bm25 is not None and len(self.documents) > 0),
            "bm25_count": len(self.documents),
            "embedding_mode": getattr(self, "embedding_mode", "none"),
        }

        coll = getattr(self, "collection", None)
        if coll is None:
            # No handle. That is a STATE, not an error - so collection_count_error
            # stays None and the reason is carried in its own field.
            return out

        out["collection_present"] = True
        try:
            out["collection_repr"] = repr(coll)[:300]
        except Exception:
            out["collection_repr"] = None

        try:
            out["collection_count"] = int(coll.count())
            out["collection_usable"] = True
        except Exception as exc:
            out["collection_count_error"] = f"{type(exc).__name__}: {exc}"
            out["collection_usable"] = False

        return out

    def is_ready(self) -> bool:
        """Readiness derived from a real count(), never from attribute presence.

        A missing handle, or a handle whose count() raises, is NOT ready.
        The BM25/keyword capability is reported separately via
        keyword_stats() so real capability stays visible without overstating
        vector-store health.
        """
        return bool(self.probe_collection()["collection_usable"])

    def keyword_stats(self) -> Dict:
        try:
            docs = len(self.documents)
        except Exception:
            docs = 0
        return {
            "bm25_loaded": self.bm25 is not None,
            "bm25_document_count": docs,
            "vector_search_healthy": bool(getattr(self, "is_vector_db_healthy", False)),
        }

    def get_diagnostics(self, deep_sc_audit: bool = False) -> Dict:
        """Self-reported health. Called by get_data_diagnostics().

        The `ready` key here deliberately overrides the caller's earlier
        guess, so a store with a dead collection reports ready=False even
        though BM25 documents are still loaded.
        """
        probe = self.probe_collection()
        kw = self.keyword_stats()
        return {
            "ready": probe["collection_usable"],
            "collection": probe,
            "keyword": kw,
            "retrieval_documents": kw["bm25_document_count"],
            "persist_directory": str(self.persist_directory),
        }

