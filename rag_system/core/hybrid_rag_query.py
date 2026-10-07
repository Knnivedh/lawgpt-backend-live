"""
Hybrid RAG Query System - Memory-Efficient Version
===================================================
Uses direct SQLite access for large ChromaDB databases.
Combines vector similarity search with keyword (BM25) search.
"""

import sqlite3
import json
import numpy as np
import pickle
from pathlib import Path
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HybridRAGQuery:
    """
    Memory-efficient hybrid RAG query system for large legal databases.
    Combines:
    - Vector similarity search (semantic)
    - BM25 keyword search (lexical)
    - Reciprocal Rank Fusion (RRF) for combining results
    """
    
    def __init__(self, 
                 db_path: str = "chroma_db_hybrid/chroma.sqlite3",
                 bm25_path: str = "chroma_db_hybrid/legal_db_hybrid_bm25.pkl"):
        self.db_path = Path(db_path)
        self.bm25_path = Path(bm25_path)
        self.conn = None
        self.model = None
        self.bm25 = None
        self.bm25_doc_ids = None
        
        # Initialize
        self._connect_db()
        
    def _connect_db(self):
        """Connect to SQLite database"""
        logger.info(f"Connecting to: {self.db_path}")
        self.conn = sqlite3.connect(str(self.db_path))
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        count = cursor.fetchone()[0]
        logger.info(f"Connected! Total documents: {count:,}")
        
    def _load_model(self):
        """Load embedding model lazily"""
        if self.model is None:
            logger.info("Loading embedding model...")
            self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            logger.info(f"Model loaded on: {self.model.device}")
            
    def _load_bm25(self):
        """Load BM25 index lazily (memory intensive)"""
        if self.bm25 is None and self.bm25_path.exists():
            logger.info("Loading BM25 index...")
            try:
                with open(self.bm25_path, 'rb') as f:
                    bm25_data = pickle.load(f)
                self.bm25 = bm25_data.get('bm25')
                self.bm25_doc_ids = bm25_data.get('doc_ids', [])
                logger.info(f"BM25 loaded: {len(self.bm25_doc_ids):,} documents")
            except Exception as e:
                logger.warning(f"Could not load BM25: {e}")
                
    def vector_search(self, query: str, top_k: int = 10, 
                      batch_size: int = 5000) -> List[Dict]:
        """
        Vector similarity search using embeddings.
        Processes in batches to manage memory.
        """
        self._load_model()
        
        # Generate query embedding
        query_embedding = self.model.encode(query, convert_to_numpy=True)
        
        cursor = self.conn.cursor()
        
        # Get total count for batching
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        total = cursor.fetchone()[0]
        
        all_results = []
        
        # Process in batches
        for offset in range(0, min(total, 50000), batch_size):  # Limit to 50k for speed
            cursor.execute("""
                SELECT e.id, e.embedding, em.string_value as document
                FROM embeddings e
                LEFT JOIN embedding_metadata em ON e.id = em.id 
                    AND em.key = 'chroma:document'
                LIMIT ? OFFSET ?
            """, (batch_size, offset))
            
            for row in cursor.fetchall():
                doc_id, embedding_blob, document = row
                if embedding_blob and document:
                    embedding = np.frombuffer(embedding_blob, dtype=np.float32)
                    if len(embedding) == 384:  # Correct dimension
                        similarity = float(np.dot(query_embedding, embedding) / (
                            np.linalg.norm(query_embedding) * np.linalg.norm(embedding) + 1e-8
                        ))
                        all_results.append({
                            'id': doc_id,
                            'text': document[:1000],  # Limit text length
                            'score': similarity,
                            'method': 'vector'
                        })
        
        # Sort by similarity and return top_k
        all_results.sort(key=lambda x: x['score'], reverse=True)
        return all_results[:top_k]
    
    def keyword_search(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        Fast keyword search using SQL LIKE.
        For exact term matching.
        """
        cursor = self.conn.cursor()
        
        # Split query into keywords
        keywords = query.lower().split()
        results = []
        
        # Search for documents containing keywords
        for keyword in keywords[:3]:  # Limit to 3 keywords for speed
            if len(keyword) < 3:
                continue
            like_pattern = f"%{keyword}%"
            cursor.execute("""
                SELECT DISTINCT em.id, em.string_value
                FROM embedding_metadata em
                WHERE em.key = 'chroma:document' 
                AND LOWER(em.string_value) LIKE ?
                LIMIT ?
            """, (like_pattern, top_k * 2))
            
            for row in cursor.fetchall():
                doc_id, text = row
                if text:
                    results.append({
                        'id': doc_id,
                        'text': text[:1000],
                        'score': 1.0,
                        'method': 'keyword'
                    })
        
        # Deduplicate by ID
        seen = set()
        unique_results = []
        for r in results:
            if r['id'] not in seen:
                seen.add(r['id'])
                unique_results.append(r)
        
        return unique_results[:top_k]
    
    def hybrid_search(self, query: str, top_k: int = 10,
                      vector_weight: float = 0.7) -> List[Dict]:
        """
        Hybrid search combining vector and keyword results.
        Uses Reciprocal Rank Fusion (RRF) for combining.
        """
        # Get results from both methods
        vector_results = self.vector_search(query, top_k=top_k * 2)
        keyword_results = self.keyword_search(query, top_k=top_k * 2)
        
        # RRF fusion
        rrf_scores = {}
        k = 60  # RRF constant
        
        # Add vector results
        for rank, result in enumerate(vector_results):
            doc_id = result['id']
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + vector_weight / (k + rank + 1)
            if doc_id not in [r['id'] for r in keyword_results]:
                rrf_scores[doc_id] = {'score': rrf_scores[doc_id], **result}
        
        # Add keyword results
        for rank, result in enumerate(keyword_results):
            doc_id = result['id']
            kw_weight = 1 - vector_weight
            if doc_id in rrf_scores and isinstance(rrf_scores[doc_id], dict):
                rrf_scores[doc_id]['score'] += kw_weight / (k + rank + 1)
            else:
                rrf_scores[doc_id] = {'score': kw_weight / (k + rank + 1), **result}
        
        # Convert to list and sort
        final_results = []
        for doc_id, data in rrf_scores.items():
            if isinstance(data, dict):
                data['method'] = 'hybrid'
                final_results.append(data)
        
        final_results.sort(key=lambda x: x['score'], reverse=True)
        return final_results[:top_k]
    
    def search(self, query: str, top_k: int = 10, 
               method: str = 'hybrid') -> List[Dict]:
        """
        Main search interface.
        
        Args:
            query: Search query string
            top_k: Number of results to return
            method: 'vector', 'keyword', or 'hybrid'
        """
        if method == 'vector':
            return self.vector_search(query, top_k)
        elif method == 'keyword':
            return self.keyword_search(query, top_k)
        else:
            return self.hybrid_search(query, top_k)
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        total = cursor.fetchone()[0]
        
        return {
            'total_documents': total,
            'db_size_mb': self.db_path.stat().st_size / (1024*1024),
            'bm25_available': self.bm25_path.exists()
        }
    
    def close(self):
        if self.conn:
            self.conn.close()


def test_rag():
    """Test the hybrid RAG system"""
    print("="*70)
    print("  HYBRID RAG QUERY SYSTEM TEST")
    print("="*70)
    
    # Initialize
    rag = HybridRAGQuery()
    stats = rag.get_stats()
    print(f"\nDatabase: {stats['total_documents']:,} documents ({stats['db_size_mb']:.0f} MB)")
    
    # Test queries
    test_queries = [
        "Consumer Protection Act 2019 deficiency of service",
        "Supreme Court judgment real estate delay possession refund",
        "What is the limitation period for filing consumer complaint"
    ]
    
    for query in test_queries:
        print(f"\n{'='*70}")
        print(f"Query: {query[:60]}...")
        print("="*70)
        
        # Keyword search
        print("\n[Keyword Search]")
        results = rag.search(query, top_k=3, method='keyword')
        for i, r in enumerate(results[:2], 1):
            print(f"  {i}. {r['text'][:100]}...")
        
        # Vector search
        print("\n[Vector Search]")
        results = rag.search(query, top_k=3, method='vector')
        for i, r in enumerate(results[:2], 1):
            print(f"  {i}. (score: {r['score']:.3f}) {r['text'][:80]}...")
        
        # Hybrid search
        print("\n[Hybrid Search]")
        results = rag.search(query, top_k=3, method='hybrid')
        for i, r in enumerate(results[:2], 1):
            print(f"  {i}. (score: {r['score']:.3f}) {r['text'][:80]}...")
    
    rag.close()
    print("\n" + "="*70)
    print("  TEST COMPLETE!")
    print("="*70)


if __name__ == "__main__":
    test_rag()
