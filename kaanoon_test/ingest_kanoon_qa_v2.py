"""
KANOON Q&A V2 - IMPROVED INGESTION
Index each Q&A answer individually (NO GROUPING!)

This fixes the 98% data loss issue from v1
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

# Data path
KANOON_QA = PROJECT_ROOT / "DATA" / "kanoon.com" / "kanoon.com" / "kanoon_data.json"

def safe_str(value, default='N/A'):
    """Convert None to default string - CRITICAL FIX"""
    return str(value) if value is not None else default

class KanoonQAIndexerV2:
    """Index Kanoon Q&A dataset - EACH ANSWER SEPARATELY"""
    
    def __init__(self):
        logger.info("="*80)
        logger.info("KANOON Q&A INGESTION V2 (Individual Answers)")
        logger.info("="*80)
        
        self.store = HybridChromaStore()
        self.total_indexed = 0
        self.errors = []
    
    def load_qa_data(self):
        """Load Kanoon data WITHOUT grouping"""
        logger.info(f"\nLoading from: {KANOON_QA}")
        logger.info("File size: 191 MB - This may take a moment...")
        
        with open(KANOON_QA, 'r', encoding='utf-8') as f:
            qa_data = json.load(f)
        
        logger.info(f"Loaded {len(qa_data):,} Q&A entries")
        logger.info("\n✅ KEY DIFFERENCE: Indexing EACH entry separately (no grouping!)")
        
        # Show category breakdown
        from collections import Counter
        categories = Counter(safe_str(entry.get('query_category'), 'General') for entry in qa_data)
        
        logger.info("\nTop categories:")
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]:
            logger.info(f"  {cat}: {count:,}")
        
        return qa_data
    
    def index_all_individually(self, qa_data, batch_size=100):
        """Index each Q&A entry as separate document"""
        logger.info("\n" + "="*80)
        logger.info("STARTING INDEXING (INDIVIDUAL ENTRIES)")
        logger.info("="*80)
        
        initial_count = self.store.collection.count()
        logger.info(f"Current documents in database: {initial_count:,}")
        
        total_batches = (len(qa_data) + batch_size - 1) // batch_size
        logger.info(f"\nIndexing {len(qa_data):,} entries in {total_batches:,} batches...")
        
        indexed = 0
        for i in tqdm(range(0, len(qa_data), batch_size), desc="Kanoon Q&A Individual"):
            batch = qa_data[i:i+batch_size]
            
            texts = []
            metadatas = []
            ids = []
            
            for j, entry in enumerate(batch):
                # Extract fields with None safety
                question_title = safe_str(entry.get('query_title'), 'Untitled')
                question_text = safe_str(entry.get('query_text'), 'No question text')
                answer_text = safe_str(entry.get('response_text'), 'No response')
                category = safe_str(entry.get('query_category'), 'General')
                url = safe_str(entry.get('query_url'), f'kanoon_{i}_{j}')
                
                # Create document - EACH answer is separate!
                doc_text = f"""
QUESTION: {question_text}

TITLE: {question_title}
CATEGORY: {category}

EXPERT ANSWER:
{answer_text}
"""
                
                # FIXED METADATA - No None values!
                metadata = {
                    'source': 'Kanoon Q&A Individual',
                    'title': question_title[:500],
                    'question': question_text[:500],
                    'category': category,
                    'url': url[:500],
                    'type': 'qa_individual'
                }
                
                texts.append(doc_text)
                metadatas.append(metadata)
                # Unique ID for each individual entry
                ids.append(f"kanoon_individual_{i+j}_{hash(url) % 100000}")
            
            try:
                self.store.collection.add(
                    documents=texts,
                    metadatas=metadatas,
                    ids=ids
                )
                indexed += len(batch)
            except Exception as e:
                logger.error(f"Error in batch {i}: {e}")
                self.errors.append(f"Batch {i}: {e}")
        
        self.total_indexed = indexed
        
        final_count = self.store.collection.count()
        logger.info("\n" + "="*80)
        logger.info("📊 INDEXING COMPLETE")
        logger.info("="*80)
        logger.info(f"Successfully indexed: {indexed:,} individual Q&A entries")
        logger.info(f"Total in database: {final_count:,}")
        
        if self.errors:
            logger.warning(f"\n⚠️ {len(self.errors)} errors occurred")
        
        return indexed
    
    def run_full_ingestion(self):
        """Run complete Kanoon Q&A ingestion - individual entries"""
        # Load all Q&A data
        qa_data = self.load_qa_data()
        
        # Index individually
        indexed = self.index_all_individually(qa_data)
        
        logger.info("\n✅ KANOON Q&A V2 INGESTION COMPLETE!")
        logger.info(f"🎯 Added {indexed:,} individual Q&A entries to RAG system")
        logger.info(f"\n📊 Previous version indexed: 2,132 grouped questions")
        logger.info(f"📊 This version indexed: {indexed:,} individual answers")
        logger.info(f"✅ Data recovery: {indexed - 2132:,} additional entries!")
        logger.info("\n🔄 Run verify_rag_complete.py to confirm")


def main():
    indexer = KanoonQAIndexerV2()
    
    print("\n" + "="*80)
    print("⚠️  KANOON Q&A INGESTION V2 (IMPROVED)")
    print("   This will index 102,176 individual Q&A pairs")
    print("   (Previous version only indexed 2,132 grouped questions)")
    print("   Estimated time: 2 hours")
    print("   Database growth: +100K documents")
    print("="*80)
    
    response = input("\nProceed with improved Kanoon Q&A ingestion? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Cancelled.")
        return
    
    indexer.run_full_ingestion()
    
    print("\n✅ DONE! Verify with: python verify_rag_complete.py")


if __name__ == "__main__":
    main()
