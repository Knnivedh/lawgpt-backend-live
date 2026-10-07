"""
CLOUD MILVUS STORE (Zilliz Cloud)
Cloud-hosted version of the RAG vector store for high availability.
Uses OpenAI embeddings API for cloud deployment to avoid heavy PyTorch dependencies.
"""

import os
import logging
from typing import List, Dict, Optional
from collections import Counter
import numpy as np
from pymilvus import connections, utility, Collection, CollectionSchema, FieldSchema, DataType
try:
    import rag_config
except ModuleNotFoundError:
    from kaanoon_test import rag_config

logger = logging.getLogger(__name__)

# Check which embedding provider to use (default to NVIDIA for cloud)
EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "nvidia").lower()

try:
    from rag_system.core.azure_sc_local_store import AzureSupremeCourtStore
except Exception:
    try:
        from .azure_sc_local_store import AzureSupremeCourtStore  # type: ignore
    except Exception:
        AzureSupremeCourtStore = None  # type: ignore

class CloudMilvusStore:
    def __init__(
        self,
        endpoint: str = rag_config.ZILLIZ_CLUSTER_ENDPOINT,
        token: str = rag_config.ZILLIZ_TOKEN,
        collection_name: str = rag_config.ZILLIZ_COLLECTION_NAME
    ):
        self.collection_name = collection_name
        self.is_connected = False
        self.provider = EMBEDDING_PROVIDER
        self.sc_store = None
        if AzureSupremeCourtStore is not None:
            try:
                self.sc_store = AzureSupremeCourtStore()
            except Exception as sc_exc:
                logger.warning(f"Supreme Court Azure store unavailable: {sc_exc}")

        if not endpoint or not token:
            logger.warning("☁️ Zilliz Cloud credentials missing in rag_config! Cloud mode disabled.")
            return

        try:
            # Connect to Zilliz
            connections.connect(
                alias="default",
                uri=endpoint,
                token=token
            )
            self.is_connected = True
            logger.info(f"✅ Connected to Zilliz Cloud: {endpoint}")
            
            # Initialize embedding model based on provider
            if self.provider == "nvidia":
                self.nvidia_api_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("nvidia_api", "")
                self.nvidia_model = "nvidia/llama-3.2-nv-embedqa-1b-v2"
                self.embedding_dim = 2048 # NVIDIA model dimension confirmed via test
                logger.info(f"🚀 Using NVIDIA Embeddings API: {self.nvidia_model}")
            elif self.provider == "openai":
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                self.embedding_model_name = "text-embedding-3-small"
                self.embedding_dim = 1536
                logger.info(f"🚀 Using OpenAI Embeddings API")
            else:
                # Fallback to local (only if dependencies are installed)
                import torch
                from sentence_transformers import SentenceTransformer
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                model_name = "sentence-transformers/all-MiniLM-L6-v2"
                self.embedding_model = SentenceTransformer(model_name, device=device)
                self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
                logger.info(f"🚀 Using Local Embeddings: {model_name} on {device.upper()}")
            
            # Initialize collection
            self._initialize_collection()
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Zilliz Cloud or init embeddings: {e}")
            self.is_connected = False

    def _initialize_collection(self):
        """Create collection if it doesn't exist"""
        if not self.is_connected:
            return

        try:
            if not utility.has_collection(self.collection_name):
                # Define Schema
                fields = [
                    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
                    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
                    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="metadata", dtype=DataType.JSON)
                ]
                schema = CollectionSchema(fields, description="Legal RAG Cloud Store")
                self.collection = Collection(self.collection_name, schema)
                
                # Create Index
                index_params = {
                    "metric_type": "L2",
                    "index_type": "AUTOINDEX",
                    "params": {}
                }
                self.collection.create_index(field_name="vector", index_params=index_params)
                logger.info(f"✨ Created new Cloud collection: {self.collection_name}")
            else:
                self.collection = Collection(self.collection_name)
                self.collection.load()
                logger.info(f"📂 Loaded Cloud collection: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"❌ Cloud collection initialization failed: {e}")

    def get_diagnostics(self, *, sample_limit: int = 200, deep_sc_audit: bool = False) -> Dict:
        diagnostics = {
            "collection_name": self.collection_name,
            "connected": self.is_connected,
            "embedding_provider": self.provider,
            "num_entities": None,
            "sampled_source_distribution": {},
            "sc_store": None,
        }

        if self.sc_store and hasattr(self.sc_store, "get_diagnostics"):
            try:
                diagnostics["sc_store"] = self.sc_store.get_diagnostics(deep=deep_sc_audit)
            except Exception as exc:
                diagnostics["sc_store"] = {"enabled": False, "error": str(exc)}

        if not self.is_connected or not getattr(self, "collection", None):
            return diagnostics

        try:
            diagnostics["num_entities"] = int(self.collection.num_entities)
        except Exception as exc:
            diagnostics["num_entities_error"] = str(exc)

        try:
            rows = self.collection.query(
                expr='id != ""',
                output_fields=["metadata"],
                limit=max(1, min(sample_limit, 1000)),
            )
            counts: Counter = Counter()
            for row in rows:
                metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
                source = (
                    metadata.get("source")
                    or metadata.get("source_file")
                    or metadata.get("source_store")
                    or metadata.get("act")
                    or "Unknown"
                )
                counts[str(source)] += 1
            diagnostics["sampled_source_distribution"] = dict(counts.most_common(20))
        except Exception as exc:
            diagnostics["sample_error"] = str(exc)

        return diagnostics

    def _encode(self, texts: List[str]) -> List[List[float]]:
        """Encode texts to embeddings using NVIDIA API, OpenAI API or local model."""
        if self.provider == "nvidia":
            import requests
            headers = {
                "Authorization": f"Bearer {self.nvidia_api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            payload = {
                "input": texts,
                "model": self.nvidia_model,
                "input_type": "query",
                "encoding_format": "float"
            }
            _nvidia_base = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
            response = requests.post(f"{_nvidia_base}/embeddings", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return [item['embedding'] for item in data['data']]
            
        elif self.provider == "openai":
            # Use OpenAI embeddings API
            response = self.openai_client.embeddings.create(
                model=self.embedding_model_name,
                input=texts
            )
            return [item.embedding for item in response.data]
        else:
            # Use local SentenceTransformers
            return self.embedding_model.encode(texts).tolist()

    def add(self, documents: List[str], metadatas: List[Dict], ids: List[str]):
        """Upload documents to the cloud"""
        if not self.is_connected:
            return

        try:
            vectors = self._encode(documents)
            # Milvus expects data in columns
            data = [
                ids,
                vectors,
                documents,
                metadatas
            ]
            self.collection.upsert(data)
            self.collection.flush()
            logger.info(f"🛰️ Uploaded {len(ids)} documents to Zilliz Cloud")
        except Exception as e:
            logger.error(f"❌ Cloud upload failed: {e}")

    def hybrid_search(self, query: str, n_results: int = 5, alpha: float = 0.5, metadata_filter: Dict = None) -> List[Dict]:
        """
        Advanced search with metadata filtering support.
        
        Args:
            query: Search query text
            n_results: Number of results to return
            alpha: Balance between vector and keyword (for future hybrid)
            metadata_filter: Optional dict like {'act': 'Consumer Protection Act', 'year': '2019'}
        """
        if not self.is_connected:
            if self.sc_store and getattr(self.sc_store, "enabled", False):
                try:
                    return self.sc_store.search(query, n_results=n_results)
                except Exception as sc_exc:
                    logger.warning(f"[CLOUD SEARCH] Supreme Court Azure fallback failed without Zilliz: {sc_exc}")
            return []

        try:
            query_vector = self._encode([query])
            search_params = {"metric_type": "L2", "params": {}}
            
            # Build expression for metadata filtering
            expr = None
            if metadata_filter:
                conditions = []
                for key, value in metadata_filter.items():
                    if value:
                        # JSON field access in Milvus
                        conditions.append(f'metadata["{key}"] == "{value}"')
                if conditions:
                    expr = " and ".join(conditions)
                    logger.info(f"[ADVANCED SEARCH] Applying filter: {expr}")
            
            results = self.collection.search(
                data=query_vector,
                anns_field="vector",
                param=search_params,
                limit=n_results,
                expr=expr,
                output_fields=["text", "metadata"]
            )
            
            hits = []
            if results:
                for hit in results[0]:
                    hits.append({
                        'id': hit.id,
                        'text': hit.entity.get("text"),
                        'metadata': hit.entity.get("metadata"),
                        'score': 1 - hit.distance,  # Convert distance to score
                        'distance': hit.distance,
                        'source': 'cloud_milvus'
                    })
            
            if self.sc_store and getattr(self.sc_store, "enabled", False):
                try:
                    sc_hits = self.sc_store.search(query, n_results=max(2, min(4, n_results)))
                    if sc_hits:
                        existing_ids = {hit["id"] for hit in hits}
                        for hit in sc_hits:
                            if hit["id"] not in existing_ids:
                                hits.append(hit)
                    hits = sorted(hits, key=lambda item: item.get("score", 0), reverse=True)[:n_results]
                except Exception as sc_exc:
                    logger.warning(f"[CLOUD SEARCH] Supreme Court Azure fallback failed: {sc_exc}")

            logger.info(f"[CLOUD SEARCH] Retrieved {len(hits)} documents")
            return hits
            
        except Exception as e:
            logger.error(f"❌ Cloud query failed: {e}")
            return []
    
    def advanced_search(
        self, 
        query: str, 
        n_results: int = 10,
        metadata_filter: Dict = None,
        reranker = None
    ) -> List[Dict]:
        """
        Advanced search with optional re-ranking.
        
        Args:
            query: Search query
            n_results: Final number of results
            metadata_filter: Metadata constraints
            reranker: Optional CrossEncoder for re-ranking
        """
        # Fetch more than needed for re-ranking
        fetch_count = n_results * 3 if reranker else n_results
        
        results = self.hybrid_search(query, n_results=fetch_count, metadata_filter=metadata_filter)
        
        # Apply re-ranking if available
        if reranker and results:
            logger.info(f"[RE-RANKING] Applying cross-encoder to {len(results)} cloud results...")
            pairs = [[query, doc['text'][:512]] for doc in results]
            scores = reranker.predict(pairs)
            
            for i, doc in enumerate(results):
                doc['rerank_score'] = float(scores[i])
            
            results = sorted(results, key=lambda x: x.get('rerank_score', 0), reverse=True)
            logger.info(f"[RE-RANKING] Complete. Top score: {results[0].get('rerank_score', 0):.3f}")
        
        return results[:n_results]

    def count(self) -> int:
        """Get estimate of documents in cloud"""
        if not self.is_connected:
            return 0
        return self.collection.num_entities
