"""
PHASE 4: KANOON Q&A INGESTION (102,176 documents)
Index the massive Kanoon Q&A dataset with None-safe metadata
"""

import json
import sys
import logging
from pathlib import Path
from typing import List, Dict
from tqdm import tqdm
from collections import defaultdict

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

class KanoonQAIndexer:
    """Index Kanoon Q&A dataset with proper metadata"""
    
    def __init__(self):
        logger.info("="*80)
        logger.info("KANOON Q&A INGESTION (102K Documents)")
        logger.info("="*80)
        
        self.store = HybridChromaStore()
        self.total_indexed = 0
        self.errors = []
    
    def load_and_group_qa(self):
        """Load Kanoon data and group by question"""
        logger.info(f"\nLoading from: {KANOON_QA}")
        logger.info("File size: 191 MB - This may take a moment...")
        
        with open(KANOON_QA, 'r', encoding='utf-8') as f:
            qa_data = json.load(f)
        
        logger.info(f"Loaded {len(qa_data):,} Q&A entries")
        
        # Group by query_url to combine multiple answers to same question
        logger.info("\nGrouping responses by question...")
        grouped = defaultdict(lambda: {
            'title': '',
            'question': '',
            'category': 'General',
            'url': '',
            'responses': []
        })
        
        for entry in qa_data:
            url = safe_str(entry.get('query_url'), f'kanoon_q_{len(grouped)}')
            
            if not grouped[url]['question']:
                grouped[url]['title'] = safe_str(entry.get('query_title'), 'Untitled Question')
                grouped[url]['question'] = safe_str(entry.get('query_text'), 'No question text')
                grouped[url]['category'] = safe_str(entry.get('query_category'), 'General')
                grouped[url]['url'] = url
            
            # Add response if not empty
            response = safe_str(entry.get('response_text'), '').strip()
            if response and response != 'N/A':
                grouped[url]['responses'].append(response)
        
        logger.info(f"Grouped into {len(grouped):,} unique questions")
        
        # Show category breakdown
        categories = defaultdict(int)
        for data in grouped.values():
            categories[data['category']] += 1
        
        logger.info("\nTop categories:")
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]:
            logger.info(f"  {cat}: {count:,}")
        
        return list(grouped.values())
    
    def prepare_documents(self, grouped_qa):
        """Prepare documents for indexing"""
        logger.info("\nPreparing documents...")
        
        documents = []
        for qa in grouped_qa:
            # Combine all responses
            combined_responses = "\n\n---\n\n".join(qa['responses']) if qa['responses'] else "No responses available"
            
            # Create document text
            doc_text = f"""
QUESTION: {qa['question']}

CATEGORY: {qa['category']}

TITLE: {qa['title']}

EXPERT RESPONSES:
{combined_responses}
"""
            
            # FIXED METADATA - No None values!
            metadata = {
                'source': 'Kanoon Q&A',
                'title': qa['title'],
                'question': qa['question'][:500],  # Truncate long questions
                'category': qa['category'],
                'url': qa['url'],
                'num_responses': len(qa['responses']),
                'type': 'qa_pair'
            }
            
            documents.append({
                'text': doc_text,
                'metadata': metadata,
                'url': qa['url']
            })
        
        logger.info(f"Prepared {len(documents):,} documents")
        return documents
    
    def index_documents(self, documents, batch_size=100):
        """Index documents with progress tracking"""
        logger.info("\n" + "="*80)
        logger.info("STARTING INDEXING")
        logger.info("="*80)
        
        initial_count = self.store.collection.count()
        logger.info(f"Current documents in database: {initial_count:,}")
        
        total_batches = (len(documents) + batch_size - 1) // batch_size
        logger.info(f"\nIndexing {len(documents):,} documents in {total_batches:,} batches...")
        
        indexed = 0
        for i in tqdm(range(0, len(documents), batch_size), desc="Kanoon Q&A Batches"):
            batch = documents[i:i+batch_size]
            
            texts = []
            metadatas = []
            ids = []
            
            for j, doc in enumerate(batch):
                texts.append(doc['text'])
                metadatas.append(doc['metadata'])
                # Use URL hash for ID to avoid duplicates
                doc_id = f"kanoon_qa_{i+j}_{hash(doc['url']) % 100000}"
                ids.append(doc_id)
            
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
        logger.info(f"Successfully indexed: {indexed:,} documents")
        logger.info(f"Total in database: {final_count:,}")
        
        if self.errors:
            logger.warning(f"\n⚠️ {len(self.errors)} errors occurred")
        
        return indexed
    
    def run_full_ingestion(self):
        """Run complete Kanoon Q&A ingestion"""
        # Load and group
        grouped_qa = self.load_and_group_qa()
        
        # Prepare documents
        documents = self.prepare_documents(grouped_qa)
        
        # Index
        indexed = self.index_documents(documents)
        
        logger.info("\n✅ KANOON Q&A INGESTION COMPLETE!")
        logger.info(f"🎯 Added {indexed:,} Q&A pairs to RAG system")
        logger.info("\n🔄 Run verify_rag_complete.py to confirm")


def main():
    indexer = KanoonQAIndexer()
    
    print("\n" + "="*80)
    print("⚠️  KANOON Q&A INGESTION")
    print("   This will index 102,176 Q&A pairs")
    print("   Estimated time: 1 hour")
    print("="*80)
    
    response = input("\nProceed with Kanoon Q&A ingestion? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Cancelled.")
        return
    
    indexer.run_full_ingestion()
    
    print("\n✅ DONE! Verify with: python verify_rag_complete.py")


if __name__ == "__main__":
    main()
