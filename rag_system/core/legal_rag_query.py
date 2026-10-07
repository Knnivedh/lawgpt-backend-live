"""
Legal RAG Query System - Fast Keyword Search
=============================================
Uses ChromaDB's SQLite fulltext search for fast legal document retrieval.
Works with 241,866 document database without memory issues.
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# GAP-11 FIX: the default used to be the literal relative path
# "chroma_db_hybrid/chroma.sqlite3", which is a 188 KB placeholder holding a
# single collection with ZERO embeddings - it logged "Total documents: 0".
# Resolve the real corpus from rag_config (same pattern as
# hybrid_chroma_store.py) and keep an explicit db_path argument working.
# NOTE: this module opens raw SQLite, but rag_config.MAIN_DB_PATH is the Chroma
# persist DIRECTORY - the database file lives inside it as chroma.sqlite3.
def _resolve_main_db() -> str:
    try:
        import rag_config as _rc
        p = Path(_rc.MAIN_DB_PATH)
        return str(p / "chroma.sqlite3") if p.is_dir() else str(p)
    except Exception as _exc:  # pragma: no cover - must not be fatal
        logger.warning("rag_config unavailable (%s); using convention", _exc)
        return str(Path(__file__).resolve().parents[2]
                   / "PERMANENT_RAG_FILES" / "MAIN_DATABASE" / "chroma.sqlite3")


DEFAULT_DB_PATH = _resolve_main_db()


class LegalRAGQuery:
    """
    Fast legal document query system using SQLite fulltext search.
    Optimized for large databases (241k+ documents).
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.conn = None
        self._connect()
        
    def _connect(self):
        """Connect to SQLite database"""
        logger.info(f"Connecting to: {self.db_path}")
        self.conn = sqlite3.connect(str(self.db_path))
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        count = cursor.fetchone()[0]
        logger.info(f"Connected! Total documents: {count:,}")
        self.doc_count = count
        
    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """
        Search documents using fulltext search.
        Fast and memory-efficient.
        """
        cursor = self.conn.cursor()
        
        # Use SQLite FTS for fast search
        try:
            # Try fulltext search first
            cursor.execute("""
                SELECT e.embedding_id, em.string_value
                FROM embedding_fulltext_search fts
                JOIN embeddings e ON fts.rowid = e.id
                JOIN embedding_metadata em ON e.embedding_id = em.embedding_id 
                    AND em.key = 'chroma:document'
                WHERE embedding_fulltext_search MATCH ?
                LIMIT ?
            """, (query, top_k))
            
            results = []
            for row in cursor.fetchall():
                doc_id, text = row
                results.append({
                    'id': doc_id,
                    'text': text[:1000] if text else '',
                    'score': 1.0
                })
            
            if results:
                return results
                
        except sqlite3.OperationalError:
            logger.debug("FTS search failed, falling back to LIKE")
        
        # Fallback to LIKE search
        keywords = query.lower().split()
        all_results = []
        
        for keyword in keywords[:5]:  # Limit keywords for speed
            if len(keyword) < 3:
                continue
                
            like_pattern = f"%{keyword}%"
            cursor.execute("""
                SELECT DISTINCT id, string_value
                FROM embedding_metadata
                WHERE key = 'chroma:document' 
                AND LOWER(string_value) LIKE ?
                LIMIT ?
            """, (like_pattern, top_k * 2))
            
            for row in cursor.fetchall():
                doc_id, text = row
                if text:
                    all_results.append({
                        'id': doc_id,
                        'text': text[:1000],
                        'score': 1.0
                    })
        
        # Deduplicate by ID
        seen = set()
        unique_results = []
        for r in all_results:
            if r['id'] not in seen:
                seen.add(r['id'])
                unique_results.append(r)
        
        return unique_results[:top_k]
    
    def search_by_source(self, source: str, top_k: int = 10) -> List[Dict]:
        """Search documents by source metadata"""
        cursor = self.conn.cursor()
        
        like_pattern = f"%{source}%"
        cursor.execute("""
            SELECT em_doc.embedding_id, em_doc.string_value, em_src.string_value as source
            FROM embedding_metadata em_doc
            LEFT JOIN embedding_metadata em_src ON em_doc.embedding_id = em_src.embedding_id
                AND em_src.key = 'source'
            WHERE em_doc.key = 'chroma:document'
            AND (em_src.string_value LIKE ? OR em_doc.string_value LIKE ?)
            LIMIT ?
        """, (like_pattern, like_pattern, top_k))
        
        results = []
        for row in cursor.fetchall():
            doc_id, text, src = row
            results.append({
                'id': doc_id,
                'text': text[:1000] if text else '',
                'source': src or 'Unknown',
                'score': 1.0
            })
        
        return results
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        cursor = self.conn.cursor()
        
        # Get unique sources
        cursor.execute("""
            SELECT DISTINCT string_value, COUNT(*) 
            FROM embedding_metadata 
            WHERE key = 'source' 
            GROUP BY string_value 
            ORDER BY COUNT(*) DESC
            LIMIT 20
        """)
        sources = {r[0]: r[1] for r in cursor.fetchall()}
        
        return {
            'total_documents': self.doc_count,
            'db_size_mb': self.db_path.stat().st_size / (1024*1024),
            'sources': sources
        }
    
    def close(self):
        if self.conn:
            self.conn.close()


def test_rag():
    """Test the Legal RAG system"""
    print("="*70)
    print("  LEGAL RAG QUERY SYSTEM TEST")
    print("="*70)
    
    rag = LegalRAGQuery()
    stats = rag.get_stats()
    
    print(f"\nDatabase: {stats['total_documents']:,} documents ({stats['db_size_mb']:.0f} MB)")
    print(f"\nTop Sources:")
    for src, count in list(stats['sources'].items())[:10]:
        print(f"  - {src}: {count:,} docs")
    
    # Test queries
    test_queries = [
        "Consumer Protection Act deficiency of service",
        "Supreme Court real estate delay refund",
        "limitation period consumer complaint",
        "NCDRC insurance claim rejection",
        "Contract Act breach damages"
    ]
    
    print("\n" + "="*70)
    print("  SEARCH RESULTS")
    print("="*70)
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-"*50)
        results = rag.search(query, top_k=3)
        
        if results:
            for i, r in enumerate(results, 1):
                text = r['text'].replace('\n', ' ')[:120]
                print(f"  {i}. {text}...")
        else:
            print("  No results found")
    
    rag.close()
    print("\n" + "="*70)
    print("  TEST COMPLETE!")
    print("="*70)


if __name__ == "__main__":
    test_rag()
