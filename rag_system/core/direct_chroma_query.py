"""
Direct SQLite Query Solution for Large ChromaDB
==============================================
Bypasses ChromaDB's collection loading entirely.
Queries the 241,866 document database directly via SQL.
"""

import sqlite3
import json
import numpy as np
from pathlib import Path
from typing import Optional
from sentence_transformers import SentenceTransformer

# GAP-11 FIX: the default used to be the literal relative path
# "chroma_db_hybrid/chroma.sqlite3" - the 188 KB placeholder with ZERO
# embeddings, which made this module print "Total documents: 0".
# Resolve the real corpus from rag_config, as hybrid_chroma_store.py does.
# NOTE: this module opens raw SQLite, but rag_config.MAIN_DB_PATH is the Chroma
# persist DIRECTORY - the database file lives inside it as chroma.sqlite3.
def _resolve_main_db() -> str:
    try:
        import rag_config as _rc
        p = Path(_rc.MAIN_DB_PATH)
        return str(p / "chroma.sqlite3") if p.is_dir() else str(p)
    except Exception as _exc:  # pragma: no cover - must not be fatal
        print(f"rag_config unavailable ({_exc}); using convention")
        return str(Path(__file__).resolve().parents[2]
                   / "PERMANENT_RAG_FILES" / "MAIN_DATABASE" / "chroma.sqlite3")


DEFAULT_DB_PATH = _resolve_main_db()


class DirectChromaQuery:
    """Query ChromaDB directly via SQLite for large collections"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.conn = None
        self.model = None
        self._connect()
        
    def _connect(self):
        """Connect to SQLite database"""
        print(f"Connecting to: {self.db_path}")
        self.conn = sqlite3.connect(str(self.db_path))
        print(f"Connected!")
        
        # Get document count
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        count = cursor.fetchone()[0]
        print(f"Total documents: {count:,}")
        
    def _load_model(self):
        """Load embedding model lazily"""
        if self.model is None:
            print("Loading embedding model...")
            self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            print(f"Model loaded on: {self.model.device}")
            
    def search(self, query: str, top_k: int = 10) -> list:
        """
        Search the database using vector similarity.
        Returns top_k most relevant documents.
        """
        self._load_model()
        
        # Generate query embedding
        query_embedding = self.model.encode(query, convert_to_numpy=True)
        
        # Get embeddings from database
        cursor = self.conn.cursor()
        
        # Get embeddings and document IDs
        cursor.execute("""
            SELECT e.id, e.embedding, ed.string_value, em_doc.string_value as document
            FROM embeddings e
            LEFT JOIN embedding_metadata em_doc ON e.id = em_doc.id AND em_doc.key = 'chroma:document'
            LEFT JOIN embeddings_data ed ON e.id = ed.id
            LIMIT 10000
        """)
        
        results = []
        for row in cursor.fetchall():
            doc_id, embedding_blob, string_val, document = row
            if embedding_blob:
                # Parse embedding
                embedding = np.frombuffer(embedding_blob, dtype=np.float32)
                # Calculate cosine similarity
                similarity = np.dot(query_embedding, embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(embedding)
                )
                results.append({
                    'id': doc_id,
                    'text': document or string_val or '',
                    'score': float(similarity)
                })
        
        # Sort by similarity and return top_k
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]
    
    def keyword_search(self, keywords: str, top_k: int = 10) -> list:
        """
        Simple keyword search using SQL LIKE.
        Faster than vector search for exact matches.
        """
        cursor = self.conn.cursor()
        
        # Search in document text
        like_pattern = f"%{keywords}%"
        cursor.execute("""
            SELECT DISTINCT em.id, em.string_value
            FROM embedding_metadata em
            WHERE em.key = 'chroma:document' 
            AND em.string_value LIKE ?
            LIMIT ?
        """, (like_pattern, top_k))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'text': row[1][:500] if row[1] else '',
                'score': 1.0
            })
        
        return results
    
    def get_stats(self) -> dict:
        """Get database statistics"""
        cursor = self.conn.cursor()
        
        # Total embeddings
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        total = cursor.fetchone()[0]
        
        # Table info
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        
        return {
            'total_embeddings': total,
            'tables': tables,
            'db_size_mb': self.db_path.stat().st_size / (1024*1024)
        }
    
    def close(self):
        if self.conn:
            self.conn.close()


def test_query():
    """Test the direct query solution"""
    print("="*60)
    print("  DIRECT CHROMADB QUERY TEST")
    print("="*60)
    
    # Initialize
    db = DirectChromaQuery()
    
    # Get stats
    stats = db.get_stats()
    print(f"\nDatabase stats:")
    print(f"  Total embeddings: {stats['total_embeddings']:,}")
    print(f"  Database size: {stats['db_size_mb']:.1f} MB")
    print(f"  Tables: {', '.join(stats['tables'][:5])}...")
    
    # Test keyword search
    print("\n--- Keyword Search Test ---")
    results = db.keyword_search("Consumer Protection Act", top_k=3)
    print(f"Found {len(results)} results for 'Consumer Protection Act':")
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r['text'][:100]}...")
    
    db.close()
    print("\n[SUCCESS] Direct query test completed!")


if __name__ == "__main__":
    test_query()
