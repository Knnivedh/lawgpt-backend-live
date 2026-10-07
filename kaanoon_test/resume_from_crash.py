"""
RESUME INGESTION FROM CRASH POINT
Continues from where the system crashed (11,172 docs indexed)

Current state:
- Phase 1: 11,172 / 26,688 Supreme Court docs (42% complete)
- Phase 2: 0 / 50,000 Case Studies (not started)
- Phase 3: 0 / 43 Knowledge files (not started)
- Phase 4-5: Missing sources (Kanoon Q&A, News) not started

This script will:
1. Complete Phase 1 (remaining 15,516 Supreme Court docs)
2. Execute Phase 2 (50,000 Case Studies)
3. Execute Phase 3 (43 Knowledge files)
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
    """Convert None to default string"""
    return str(value) if value is not None else default

class ResumeIngester:
    """Resume ingestion from crash point"""
    
    def __init__(self):
        logger.info("="*80)
        logger.info("RESUME INGESTION FROM CRASH")
        logger.info("="*80)
        
        self.store = HybridChromaStore()
        self.total_indexed = 0
        self.errors = []
        
        # Check current state
        current_count = self.store.collection.count()
        logger.info(f"Current documents in database: {current_count:,}")
        logger.info(f"Expected: 11,172 Supreme Court docs")
        
        if current_count != 11172:
            logger.warning(f"⚠️ Count mismatch! Expected 11,172, got {current_count:,}")
            logger.warning(f"Script may re-index some documents")
    
    def resume_phase1_supreme_court(self):
        """Resume Phase 1 from crash point (~batch 112/266)"""
        logger.info("\n📊 PHASE 1: Complete Supreme Court (Resume)")
        logger.info("="*80)
        
        # Get all batch files
        batch_files = sorted(PROCESSED_KAGGLE.glob("batch_*.json"))
        logger.info(f"Found {len(batch_files)} batch files")
        
        # Calculate approximate crash point
        # 11,172 docs / ~100 docs per batch = ~112 batches completed
        ESTIMATED_CRASH_BATCH = 112
        
        logger.info(f"\n⚡ Resuming from batch {ESTIMATED_CRASH_BATCH} onwards")
        logger.info(f"   (Skipping first {ESTIMATED_CRASH_BATCH} batches)")
        
        resume_files = batch_files[ESTIMATED_CRASH_BATCH:]
        logger.info(f"   Processing remaining {len(resume_files)} batches")
        
        indexed = 0
        for batch_file in tqdm(resume_files, desc="Supreme Court (Resume)"):
            try:
                with open(batch_file, 'r', encoding='utf-8') as f:
                    batch_data = json.load(f)
                
                for case in batch_data:
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
                    
                    metadata = {
                        'source': 'Supreme Court Kaggle',
                        'case_name': title,
                        'date': date,
                        'citation': citation,
                        'court': 'Supreme Court of India',
                        'type': 'judgment'
                    }
                    
                    case_id = f"sc_kaggle_resume_{indexed}_{hash(citation) % 100000}"
                    
                    self.store.collection.add(
                        documents=[doc_text],
                        metadatas=[metadata],
                        ids=[case_id]
                    )
                    indexed += 1
                
            except Exception as e:
                logger.error(f"Error in {batch_file.name}: {e}")
                self.errors.append(f"{batch_file.name}: {e}")
        
        logger.info(f"\n✅ Phase 1 Resume: Indexed {indexed:,} additional Supreme Court cases")
        return indexed
    
    def execute_phase2_case_studies(self):
        """Execute Phase 2: Case Studies (50,000 docs)"""
        logger.info("\n📊 PHASE 2: Case Studies (50K)")
        logger.info("="*80)
        
        if not CASE_STUDIES.exists():
            logger.error(f"Case studies file not found: {CASE_STUDIES}")
            return 0
        
        logger.info(f"Loading from: {CASE_STUDIES}")
        
        with open(CASE_STUDIES, 'r', encoding='utf-8') as f:
            case_studies = json.load(f)
        
        logger.info(f"Loaded {len(case_studies):,} case studies")
        
        indexed = 0
        batch_size = 100
        
        for i in tqdm(range(0, len(case_studies), batch_size), desc="Case Studies"):
            batch = case_studies[i:i+batch_size]
            
            texts = []
            metadatas = []
            ids = []
            
            for j, case in enumerate(batch):
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
        
        logger.info(f"\n✅ Phase 2 Complete: Indexed {indexed:,} case studies")
        return indexed
    
    def execute_phase3_knowledge(self):
        """Execute Phase 3: Knowledge Files"""
        logger.info("\n📊 PHASE 3: Knowledge Files")
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
        
        logger.info(f"\n✅ Phase 3 Complete: Indexed {indexed} knowledge files")
        return indexed
    
    def run_full_resume(self):
        """Run complete resume from crash"""
        logger.info("\nStarting resume ingestion...")
        
        # Phase 1: Complete Supreme Court
        phase1_count = self.resume_phase1_supreme_court()
        self.total_indexed += phase1_count
        
        # Phase 2: Case Studies
        phase2_count = self.execute_phase2_case_studies()
        self.total_indexed += phase2_count
        
        # Phase 3: Knowledge
        phase3_count = self.execute_phase3_knowledge()
        self.total_indexed += phase3_count
        
        # Final Report
        logger.info("\n" + "="*80)
        logger.info("📊 RESUME INGESTION COMPLETE!")
        logger.info("="*80)
        logger.info(f"Phase 1 (Resume): {phase1_count:,}")
        logger.info(f"Phase 2 (Case Studies): {phase2_count:,}")
        logger.info(f"Phase 3 (Knowledge): {phase3_count:,}")
        logger.info(f"TOTAL NEW: {self.total_indexed:,}")
        logger.info(f"Total in database: {self.store.collection.count():,}")
        
        if self.errors:
            logger.warning(f"\n⚠️ {len(self.errors)} errors occurred")
        
        logger.info("\n✅ PHASES 1-3 COMPLETE!")
        logger.info("🎯 Next: Run Phase 4 (Kanoon Q&A) for 90%+ accuracy")


def main():
    resumer = ResumeIngester()
    
    print("\n" + "="*80)
    print("⚡ RESUME INGESTION FROM CRASH")
    print("   Current: 11,172 docs (42% of Phase 1)")
    print("   Will complete: Phase 1-3 (remaining 65,559 docs)")
    print("   Estimated time: 2-3 hours")
    print("="*80)
    
    response = input("\nProceed with resume? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Cancelled.")
        return
    
    resumer.run_full_resume()
    
    print("\n✅ DONE! Next: python kaanoon_test/ingest_kanoon_qa.py")


if __name__ == "__main__":
    main()
