"""
Index New Knowledge Files - Add specialized knowledge to ChromaDB
Indexes: law_transitions_2024.json, pwdva_comprehensive.json, consumer_law_specifics.json
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_system.core.hybrid_chroma_store import HybridChromaStore
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def index_knowledge_file(file_path: str, store: HybridChromaStore):
    """
    Index a single knowledge JSON file into ChromaDB
    
    Args:
        file_path: Path to JSON file
        store: HybridChromaStore instance
    """
    logger.info(f"Indexing {file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    documents = data.get('documents', [])
    logger.info(f"Found {len(documents)} documents in {file_path}")
    
    texts = []
    metadatas = []
    ids = []
    
    for doc in documents:
        # Prepare document for indexing
        text = f"{doc['title']}\n\n{doc['content']}"
        
        metadata = {
            'id': doc['id'],
            'title': doc['title'],
            'category': doc['category'],
            'tags': ','.join(doc['tags']),
            'source': Path(file_path).stem,
            'priority': 'HIGH',  # Mark as high priority for retrieval
            'type': 'specialized_knowledge'
        }
        
        texts.append(text)
        metadatas.append(metadata)
        ids.append(doc['id'])
    
    # Add to collection
    try:
        store.collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"✓ Successfully indexed {len(documents)} documents from {file_path}")
        return len(documents)
    except Exception as e:
        logger.error(f"❌ Error indexing {file_path}: {e}")
        return 0


def main():
    """Main indexing function"""
    logger.info("="*60)
    logger.info("INDEXING NEW KNOWLEDGE FILES")
    logger.info("="*60)
    
    # Initialize ChromaDB store
    PROJECT_ROOT = Path(__file__).parent.parent
    DB_PATH = PROJECT_ROOT / "chroma_db_hybrid"
    
    logger.info(f"Database path: {DB_PATH}")
    
    store = HybridChromaStore(
        persist_directory=str(DB_PATH),
        collection_name="legal_db_hybrid"
    )
    
    # Knowledge files to index
    knowledge_files = [
        PROJECT_ROOT / "DATA" / "law_transitions_2024.json",
        PROJECT_ROOT / "DATA" / "pwdva_comprehensive.json",
        PROJECT_ROOT / "DATA" / "consumer_law_specifics.json"
    ]
    
    total_indexed = 0
    
    for file_path in knowledge_files:
        if file_path.exists():
            count = index_knowledge_file(str(file_path), store)
            total_indexed += count
        else:
            logger.warning(f"File not found: {file_path}")
    
    logger.info("="*60)
    logger.info(f"✓ INDEXING COMPLETE - {total_indexed} documents added")
    logger.info(f"Total documents in database: {store.collection.count()}")
    logger.info("="*60)
    
    # Test retrieval
    logger.info("\nTesting retrieval of new knowledge...")
    test_queries = [
        "IPC 420 replaced by BNS",
        "PWDVA domestic violence remedies",
        "consumer complaint jurisdiction"
    ]
    
    for query in test_queries:
        results = store.hybrid_search(query, n_results=2)
        logger.info(f"\nQuery: {query}")
        logger.info(f"Top result: {results[0]['metadata'].get('title', 'N/A') if results else 'No results'}")


if __name__ == "__main__":
    main()
