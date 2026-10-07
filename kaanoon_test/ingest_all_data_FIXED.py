"""
FIXED COMPREHENSIVE DATA INGESTION - None-Safe Metadata
Fixes: ChromaDB metadata None value rejection issue
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
PROCESSED_KAGGLE = DATA_DIR / "processed_kaggle"
CASE_STUDIES = DATA_DIR / "Indian_Case_Studies_50K ORG" / "Indian_Case_Studies_50K ORG.json"

def safe_str(value, default='N/A'):
    """Convert None to default string - CRITICAL FIX"""
    return str(value) if value is not None else default

class FixedDataIndexer:
    """Index ALL data with None-safe metadata"""
    
    def __init__(self):
        logger.info("="*80)
        logger.info("FIXED DATA INGESTION (None-Safe Metadata)")
        logger.info("="*80)
        
        self.store = HybridChromaStore()
        self.total_indexed = 0
        self.errors = []
    
    def index_kaggle_batches(self) -> int:
        """Index Kaggle Supreme Court cases with None-safe metadata"""
        logger.info("\n"+ "="*80)
        logger.info("INDEXING SUPREME COURT JUDGMENTS (FIXED)")
        logger.info("="*80)
        
        batch_files = list(PROCESSED_KAGGLE.glob("batch_*.json"))
        logger.info(f"Found {len(batch_files)} batch files")
        
        indexed = 0
        for batch_file in tqdm(batch_files, desc="Kaggle Batches"):
            try:
                with open(batch_file, 'r', encoding='utf-8') as f:
                    batch_data = json.load(f)
                
                for case in batch_data:
                    # CRITICAL FIX: Convert None values to 'N/A'
                    title = safe_str(case.get('title'), 'Untitled Case')
                    date = safe_str(case.get('date'))
                    citation = safe_str(case.get('citation'))
                    headnote = safe_str(case.get('headnote'), '')
                    text = safe_str(case.get('text'), '')
                    
                    doc_text = f"""
CASE NAME: {title}
COURT: Supreme Court of India
DATE: {date}
CITATION: {citation}

HEADNOTE:
{headnote}

FULL JUDGMENT:
{text}
"""
                    
                    # FIXED METADATA - No None values!
                    metadata = {
                        'source': 'Supreme Court Kaggle',
                        'case_name': title,
                        'date': date,
                        'citation': citation,
                        'court': 'Supreme Court of India',
                        'type': 'judgment'
                    }
                    
                    case_id = f"sc_kaggle_{indexed}_{citation[:20]}".replace(" ", "_").replace("/", "_")
                    
                    self.store.collection.add(
                        documents=[doc_text],
                        metadatas=[metadata],
                        ids=[case_id]
                    )
                    indexed += 1
                
            except Exception as e:
                logger.error(f"Error in {batch_file.name}: {e}")
                self.errors.append(f"{batch_file.name}: {e}")
        
        logger.info(f"✅ Indexed {indexed} Supreme Court cases")
        return indexed
    
    def index_case_studies(self) -> int:
        """Index Case Studies with None-safe metadata"""
        logger.info("\n" + "="*80)
        logger.info("INDEXING 50K CASE STUDIES (FIXED)")
        logger.info("="*80)
        
        if not CASE_STUDIES.exists():
            logger.error(f"Case studies file not found: {CASE_STUDIES}")
            return 0
        
        logger.info(f"Loading from: {CASE_STUDIES}")
        
        with open(CASE_STUDIES, 'r', encoding='utf-8') as f:
            case_studies = json.load(f)
        
        logger.info(f"Loaded {len(case_studies)} case studies")
        
        indexed = 0
        batch_size = 100
        
        for i in tqdm(range(0, len(case_studies), batch_size), desc="Case Studies"):
            batch = case_studies[i:i+batch_size]
            
            texts = []
            metadatas = []
            ids = []
            
            for j, case in enumerate(batch):
                # CRITICAL FIX: Convert None to strings
                case_name = safe_str(case.get('case_name') or case.get('title') or case.get('name'), 'Unnamed Case')
                court = safe_str(case.get('court'), 'Unknown Court')
                date = safe_str(case.get('date') or case.get('judgment_date'))
                facts = safe_str(case.get('facts') or case.get('description'), '')
                judgment = safe_str(case.get('judgment') or case.get('text') or case.get('content'), '')
                ratio = safe_str(case.get('ratio'), '')
                
                text = f"""
CASE: {case_name}
COURT: {court}
DATE: {date}

FACTS:
{facts}

JUDGMENT:
{judgment}

RATIO: {ratio}
"""
                
                # FIXED METADATA - No None values!
                metadata = {
                    'source': 'Indian Case Studies 50K',
                    'case_name': case_name,
                    'court': court,
                    'date': date,
                    'type': 'case_study'
                }
                
                texts.append(text)
                metadatas.append(metadata)
                ids.append(f"case_study_{i+j}")
            
            try:
                self.store.collection.add(
                    documents=texts,
                    metadatas=metadatas,
                    ids=ids
                )
                indexed += len(batch)
            except Exception as e:
                logger.error(f"Error in batch {i}: {e}")
                self.errors.append(f"Case studies batch {i}: {e}")
        
        logger.info(f"✅ Indexed {indexed} case studies")
        return indexed
    
    def index_knowledge_files(self) -> int:
        """Index knowledge files with None-safe metadata"""
        logger.info("\n" + "="*80)
        logger.info("INDEXING KNOWLEDGE FILES (FIXED)")
        logger.info("="*80)
        
        knowledge_files = [
            "consumer_law_specifics.json",
            "law_transitions_2024.json",
            "pwdva_comprehensive.json",
            "specific_gap_fix_cases.json",
            "landmark_legal_cases.json",
            "landmark_legal_cases_expansion.json"
        ]
        
        indexed = 0
        for filename in knowledge_files:
            filepath = DATA_DIR / filename
            if not filepath.exists():
                logger.warning(f"File not found: {filename}")
                continue
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if isinstance(data, dict):
                    docs = data.get('documents', data.get('cases', [data]))
                else:
                    docs = data
                
                for i, doc in enumerate(docs):
                    text = json.dumps(doc, indent=2, ensure_ascii=False)
                    
                    # FIXED METADATA - No None values!
                    metadata = {
                        'source': filename,
                        'type': 'knowledge_file',
                        'category': safe_str(doc.get('category'), 'general')
                    }
                    
                    doc_id = f"{filename}_{i}".replace(".json", "")
                    
                    self.store.collection.add(
                        documents=[text],
                        metadatas=[metadata],
                        ids=[doc_id]
                    )
                    indexed += 1
                
                logger.info(f"✅ Indexed {filename}: {len(docs)} documents")
                
            except Exception as e:
                logger.error(f"Error in {filename}: {e}")
                self.errors.append(f"{filename}: {e}")
        
        logger.info(f"✅ Total knowledge files indexed: {indexed}")
        return indexed
    
    def run_full_ingestion(self):
        """Run complete data ingestion with fixed metadata"""
        logger.info("\n" + "="*80)
        logger.info("STARTING FIXED DATA INGESTION")
        logger.info("="*80)
        
        initial_count = self.store.collection.count()
        logger.info(f"Current documents in database: {initial_count:,}")
        
        if initial_count > 150000:
            logger.warning("⚠️ Database has 150K+ documents (likely corrupted)")
            logger.warning("⚠️ Recommend deleting chroma_db_hybrid first!")
            response = input("Continue anyway? (yes/no): ")
            if response.lower() != 'yes':
                logger.info("Cancelled. Delete database and retry.")
                return
        
        # Phase 1: Supreme Court
        logger.info("\n📊 PHASE 1: Supreme Court Judgments")
        kaggle_count = self.index_kaggle_batches()
        self.total_indexed += kaggle_count
        
        # Phase 2: Case Studies
        logger.info("\n📊 PHASE 2: Indian Case Studies")
        case_studies_count = self.index_case_studies()
        self.total_indexed += case_studies_count
        
        # Phase 3: Knowledge Files
        logger.info("\n📊 PHASE 3: Knowledge Files")
        knowledge_count = self.index_knowledge_files()
        self.total_indexed += knowledge_count
        
        # Final Report
        logger.info("\n" + "="*80)
        logger.info("📊 INGESTION COMPLETE!")
        logger.info("="*80)
        logger.info(f"Supreme Court Cases: {kaggle_count:,}")
        logger.info(f"Case Studies: {case_studies_count:,}")
        logger.info(f"Knowledge Files: {knowledge_count:,}")
        logger.info(f"TOTAL INDEXED: {self.total_indexed:,}")
        logger.info(f"Total in database: {self.store.collection.count():,}")
        
        if self.errors:
            logger.warning(f"\n⚠️ {len(self.errors)} errors occurred")
        
        logger.info("\n✅ ALL DATA INDEXED WITH PROPER METADATA!")
        logger.info("🔄 Run verify_database.py to confirm")


def main():
    indexer = FixedDataIndexer()
    
    print("\n" + "="*80)
    print("⚠️  FIXED INGESTION SCRIPT")
    print("   This version converts None → 'N/A' for all metadata")
    print("   Estimated time: 45 minutes")
    print("="*80)
    
    response = input("\nProceed with FIXED ingestion? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Cancelled.")
        return
    
    indexer.run_full_ingestion()
    
    print("\n✅ DONE! Verify with: python verify_database.py")


if __name__ == "__main__":
    main()
