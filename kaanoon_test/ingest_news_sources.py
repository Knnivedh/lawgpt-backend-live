"""
PHASE 5: NEWS SOURCES Q&A INGESTION (~3,800 documents)
Index IndianExpress, NDTV, Legallyin news Q&A data
"""

import json
import sys
import logging
from pathlib import Path
from typing import List, Dict
from tqdm import tqdm

# Add parent to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag_system.core.hybrid_chroma_store import HybridChromaStore

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Data paths
DATA_DIR = PROJECT_ROOT / "DATA"

NEWS_SOURCES = [
    {
        'file': DATA_DIR / "indianexpress_property_law_qa" / "indianexpress_property_law_qa.json",
        'source_name': 'IndianExpress Property Law',
        'expected_docs': 2000
    },
    {
        'file': DATA_DIR / "ndtv_legal_qa_data" / "ndtv_legal_qa_data.json",
        'source_name': 'NDTV Legal Q&A',
        'expected_docs': 500
    },
    {
        'file': DATA_DIR / "legallyin.com" / "legallyin.com.json",
        'source_name': 'Legallyin Q&A',
        'expected_docs': 300
    }
]

def safe_str(value, default='N/A'):
    """Convert None to default string"""
    return str(value) if value is not None else default

class NewsQAIndexer:
    """Index news sources Q&A data"""
    
    def __init__(self):
        logger.info("="*80)
        logger.info("NEWS SOURCES Q&A INGESTION")
        logger.info("="*80)
        
        self.store = HybridChromaStore()
        self.total_indexed = 0
    
    def index_source(self, source_info):
        """Index a single news source"""
        file_path = source_info['file']
        source_name = source_info['source_name']
        
        if not file_path.exists():
            logger.warning(f"⚠️ File not found: {file_path}")
            return 0
        
        logger.info(f"\nIndexing: {source_name}")
        logger.info(f"File: {file_path.name}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different data structures
            if isinstance(data, list):
                qa_pairs = data
            elif isinstance(data, dict):
                # Try common keys
                qa_pairs = data.get('data', data.get('questions', data.get('articles', [data])))
            else:
                qa_pairs = [data]
            
            logger.info(f"Found {len(qa_pairs):,} entries")
            
            # Prepare documents
            documents = []
            for i, item in enumerate(qa_pairs):
                # Flexible field extraction
                question = safe_str(
                    item.get('question') or item.get('title') or item.get('query'),
                    'No question'
                )
                answer = safe_str(
                    item.get('answer') or item.get('content') or item.get('text'),
                    'No answer'
                )
                category = safe_str(item.get('category') or item.get('topic'), 'General')
                
                doc_text = f"""
QUESTION: {question}

CATEGORY: {category}

ANSWER:
{answer}
"""
                
                metadata = {
                    'source': source_name,
                    'question': question[:500],
                    'category': category,
                    'type': 'news_qa'
                }
                
                documents.append({
                    'text': doc_text,
                    'metadata': metadata,
                    'id': f"{source_name.replace(' ', '_').lower()}_{i}"
                })
            
            # Index in batches
            batch_size = 100
            indexed = 0
            
            for i in tqdm(range(0, len(documents), batch_size), desc=f"{source_name}"):
                batch = documents[i:i+batch_size]
                
                texts = [doc['text'] for doc in batch]
                metadatas = [doc['metadata'] for doc in batch]
                ids = [doc['id'] for doc in batch]
                
                try:
                    self.store.collection.add(
                        documents=texts,
                        metadatas=metadatas,
                        ids=ids
                    )
                    indexed += len(batch)
                except Exception as e:
                    logger.error(f"Error in batch {i}: {e}")
            
            logger.info(f"✅ Indexed {indexed:,} documents from {source_name}")
            return indexed
            
        except Exception as e:
            logger.error(f"❌ Error processing {source_name}: {e}")
            return 0
    
    def run_full_ingestion(self):
        """Index all news sources"""
        logger.info(f"\nCurrent documents in database: {self.store.collection.count():,}")
        
        for source_info in NEWS_SOURCES:
            indexed = self.index_source(source_info)
            self.total_indexed += indexed
        
        logger.info("\n" + "="*80)
        logger.info("📊 NEWS SOURCES INGESTION COMPLETE")
        logger.info("="*80)
        logger.info(f"Total indexed: {self.total_indexed:,}")
        logger.info(f"Total in database: {self.store.collection.count():,}")
        
        logger.info("\n✅ ALL NEWS SOURCES ADDED!")


def main():
    indexer = NewsQAIndexer()
    
    print("\n" + "="*80)
    print("⚠️  NEWS SOURCES Q&A INGESTION")
    print("   Sources: IndianExpress, NDTV, Legallyin")
    print("   Estimated documents: ~3,800")
    print("   Estimated time: 15 minutes")
    print("="*80)
    
    # indexer.run_full_ingestion()
    print("\n🚀 Starting news sources ingestion...")
    indexer.run_full_ingestion()
    
    print("\n✅ DONE! Verify with: python verify_rag_complete.py")


if __name__ == "__main__":
    main()
