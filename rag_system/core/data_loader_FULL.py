"""
FULL Legal Data Loader - Loads ALL 156K+ documents
FIXES: Kanoon.com grouping issue - loads each response separately
UPDATED: Statute loading now uses StatuteSectionChunker for structure-aware chunking
"""

import json
from pathlib import Path
from typing import List, Dict
from tqdm import tqdm
import logging

from rag_system.core.statute_chunker import StatuteSectionChunker, process_all_statutes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FullLegalDataLoader:
    """
    Loads ALL available legal data without grouping:
    - Domain 1: Case Studies (50K)
    - Domain 2: Indian Express (1K)
    - Domain 3: Kanoon.com (102K - EACH response separate)
    - Domain 4-7: LegallyIn, NDTV, Hindu, Wikipedia (2.8K)
    
    Total: ~156K documents
    """
    
    def __init__(self, data_dir: str = "DATA"):
        self.data_dir = Path(data_dir)
        self.validate_paths()
        self.stats = {}
    
    def validate_paths(self):
        """Validate data directory exists"""
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
        logger.info(f"Data directory: {self.data_dir}")
    
    # ==================== DOMAIN 1: CASE STUDIES (50K) ====================
    
    def load_domain_1_case_studies(self) -> List[Dict]:
        """Load 50,000 Indian case studies"""
        file_path = self.data_dir / "Indian_Case_Studies_50K ORG" / "Indian_Case_Studies_50K ORG.json"
        logger.info(f"Loading Domain 1: Case Studies from {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        records = []
        case_count = 0
        
        # Handle both list and dict structures
        if isinstance(data, list):
            for case_data in tqdm(data, desc="Domain 1"):
                if isinstance(case_data, dict):
                    text = f"""Case ID: {case_data.get('case_id', 'N/A')}
Title: {case_data.get('case_title', 'N/A')}
Type: {case_data.get('case_type', 'N/A')}
Description: {case_data.get('case_description', 'N/A')}
Victim: {case_data.get('victim_name', 'N/A')}
Accused: {case_data.get('accused_name', 'N/A')}
Location: {case_data.get('location', 'N/A')}
Status: {case_data.get('case_status', 'N/A')}"""
                    
                    if 'legal_aspects' in case_data:
                        sections = case_data['legal_aspects'].get('sections_applied', [])
                        court = case_data['legal_aspects'].get('court_level', 'N/A')
                        text += f"\nSections Applied: {', '.join(sections)}"
                        text += f"\nCourt Level: {court}"
                    
                    records.append({
                        'id': f"D1_{case_count}",
                        'text': text.strip(),
                        'metadata': {
                            'domain': 'case_studies',
                            'case_type': case_data.get('case_type', 'Unknown')
                        }
                    })
                    case_count += 1
        
        elif isinstance(data, dict):
            for case_type, cases in tqdm(data.items(), desc="Domain 1"):
                if isinstance(cases, dict):
                    for case_key, case_data in cases.items():
                        if isinstance(case_data, dict):
                            text = f"""Case ID: {case_data.get('case_id', 'N/A')}
Title: {case_data.get('case_title', 'N/A')}
Type: {case_data.get('case_type', 'N/A')}
Description: {case_data.get('case_description', 'N/A')}"""
                            
                            records.append({
                                'id': f"D1_{case_count}",
                                'text': text.strip(),
                                'metadata': {
                                    'domain': 'case_studies',
                                    'case_type': case_data.get('case_type', 'Unknown')
                                }
                            })
                            case_count += 1
        
        logger.info(f"Loaded {len(records)} case studies")
        self.stats['case_studies'] = len(records)
        return records
    
    # ==================== DOMAIN 2: INDIAN EXPRESS (1K) ====================
    
    def load_domain_2_indian_express(self) -> List[Dict]:
        """Load Indian Express Property Law Q&A"""
        file_path = self.data_dir / "indianexpress_property_law_qa" / "indianexpress_property_law_qa.json"
        logger.info(f"Loading Domain 2: Indian Express from {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        records = []
        for idx, item in enumerate(tqdm(data, desc="Domain 2")):
            text = f"""Question: {item.get('Question', 'N/A')}
Answer: {item.get('Answer', 'N/A')}
Topic: {item.get('topic', 'N/A')}"""
            
            records.append({
                'id': f"D2_{idx:04d}",
                'text': text.strip(),
                'metadata': {
                    'domain': 'indian_express',
                    'category': 'property_law'
                }
            })
        
        logger.info(f"Loaded {len(records)} Indian Express records")
        self.stats['indian_express'] = len(records)
        return records
    
    # ==================== DOMAIN 3: KANOON.COM (102K) - FIXED! ====================
    
    def load_domain_3_kanoon_FULL(self) -> List[Dict]:
        """
        Load Kanoon.com FULL - Each response as separate document
        
        FIXED: Instead of grouping by question, load ALL 102K responses
        This gives much better coverage for RAG retrieval
        """
        file_path = self.data_dir / "kanoon.com" / "kanoon.com" / "kanoon_data.json"
        logger.info(f"Loading Domain 3: Kanoon.com FULL from {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        records = []
        
        logger.info(f"Total Kanoon records: {len(data):,}")
        
        for idx, item in enumerate(tqdm(data, desc="Domain 3 (FULL)")):
            # Each expert response is a separate document
            text = f"""Question: {item.get('query_title', 'N/A')}
Details: {item.get('query_text', 'N/A')}
Category: {item.get('query_category', 'N/A')}

Expert Response ({item.get('responder', 'Unknown')}):
{item.get('response_text', 'N/A')}"""
            
            records.append({
                'id': f"D3_{idx:06d}",
                'text': text.strip(),
                'metadata': {
                    'domain': 'kanoon',
                    'category': item.get('query_category', 'Unknown'),
                    'response_index': item.get('response_index', 0)
                }
            })
        
        logger.info(f"Loaded {len(records):,} Kanoon.com records (FULL - not grouped)")
        self.stats['kanoon'] = len(records)
        return records
    
    # ==================== DOMAIN 4-7: REMAINING DOMAINS ====================
    
    def load_domain_4_legallyin(self) -> List[Dict]:
        """Load LegallyIn corporate/property law"""
        file_path = self.data_dir / "legallyin.com" / "legallyin.com.json"
        logger.info(f"Loading Domain 4: LegallyIn from {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        records = []
        for idx, item in enumerate(tqdm(data, desc="Domain 4")):
            text = f"""Question: {item.get('question', 'N/A')}
Answer: {item.get('answer', 'N/A')}
Category: {item.get('category', 'N/A')}"""
            
            records.append({
                'id': f"D4_{idx:04d}",
                'text': text.strip(),
                'metadata': {
                    'domain': 'legallyin',
                    'category': item.get('category', 'Unknown')
                }
            })
        
        logger.info(f"Loaded {len(records)} LegallyIn records")
        self.stats['legallyin'] = len(records)
        return records
    
    def load_domain_5_ndtv(self) -> List[Dict]:
        """Load NDTV legal Q&A"""
        file_path = self.data_dir / "ndtv_legal_qa_data" / "ndtv_legal_qa_data.json"
        logger.info(f"Loading Domain 5: NDTV from {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        records = []
        for idx, item in enumerate(tqdm(data, desc="Domain 5")):
            text = f"""Question: {item.get('question', 'N/A')}
Answer: {item.get('answer', 'N/A')}
Category: {item.get('category', 'N/A')}"""
            
            records.append({
                'id': f"D5_{idx:04d}",
                'text': text.strip(),
                'metadata': {
                    'domain': 'ndtv',
                    'category': item.get('category', 'Unknown')
                }
            })
        
        logger.info(f"Loaded {len(records)} NDTV records")
        self.stats['ndtv'] = len(records)
        return records
    
    def load_domain_6_hindu(self) -> List[Dict]:
        """Load The Hindu legal news"""
        file_path = self.data_dir / "thehindu" / "thehindu.json"
        logger.info(f"Loading Domain 6: The Hindu from {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        records = []
        for idx, item in enumerate(tqdm(data, desc="Domain 6")):
            text = f"""Question: {item.get('question', 'N/A')}
Answer: {item.get('answer', 'N/A')}
Category: {item.get('category', 'N/A')}"""
            
            records.append({
                'id': f"D6_{idx:04d}",
                'text': text.strip(),
                'metadata': {
                    'domain': 'hindu',
                    'category': item.get('category', 'Unknown')
                }
            })
        
        logger.info(f"Loaded {len(records)} The Hindu records")
        self.stats['hindu'] = len(records)
        return records
    
    def load_domain_7_wikipedia(self) -> List[Dict]:
        """Load Wikipedia legal concepts"""
        file_path = self.data_dir / "wikipedia.org" / "wikipedia.org.json"
        logger.info(f"Loading Domain 7: Wikipedia from {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        records = []
        for idx, item in enumerate(tqdm(data, desc="Domain 7")):
            text = f"""Question: {item.get('question', 'N/A')}
Answer: {item.get('answer', 'N/A')}
Category: {item.get('category', 'N/A')}"""
            
            records.append({
                'id': f"D7_{idx:04d}",
                'text': text.strip(),
                'metadata': {
                    'domain': 'wikipedia',
                    'category': item.get('category', 'Unknown')
                }
            })
        
        logger.info(f"Loaded {len(records)} Wikipedia records")
        self.stats['wikipedia'] = len(records)
        return records

    # ==================== DOMAIN 8: STATUTES (RULE BOOKS) ====================

    def load_domain_8_statutes(self) -> List[Dict]:
        """
        Load Government Rule Books (Statutes) using structure-aware chunking.
        
        Uses StatuteSectionChunker which:
        - Detects section boundaries in statute text
        - Creates one chunk per legal section with proper metadata
        - Handles multiple data formats (chunk-based, number-based, marker-based, monolithic)
        - Splits oversized sections while preserving context headers
        - Produces ~3900+ properly structured chunks from 41+ statute files
        """
        json_dir = self.data_dir / "Statutes" / "json"
        if not json_dir.exists():
            logger.warning(f"Statutes JSON directory not found: {json_dir}. Skipping.")
            return []

        logger.info(f"Loading Domain 8: Statutes (structure-aware chunking) from {json_dir}")
        
        records = process_all_statutes(json_dir, max_chunk_chars=3000)
        
        logger.info(f"Loaded {len(records)} Statute records (structure-aware chunking)")
        self.stats['statutes'] = len(records)
        return records
    
    # ==================== MAIN LOADER ====================
    
    def load_all(self) -> List[Dict]:
        """
        Load all records from all 7 domains
        Returns: List of dicts with 'id', 'text', 'metadata'
        
        TOTAL: ~156K documents (Kanoon.com loaded fully)
        """
        logger.info("="*60)
        logger.info("LOADING ALL 7 DOMAINS (FULL MODE - 156K+ DOCUMENTS)")
        logger.info("="*60)
        
        all_records = []
        
        # Load each domain
        loaders = [
            ('Domain 1: Case Studies (50K)', self.load_domain_1_case_studies),
            ('Domain 2: Indian Express (1K)', self.load_domain_2_indian_express),
            ('Domain 3: Kanoon.com (102K - FULL)', self.load_domain_3_kanoon_FULL),
            ('Domain 4: LegallyIn (414)', self.load_domain_4_legallyin),
            ('Domain 5: NDTV (401)', self.load_domain_5_ndtv),
            ('Domain 6: The Hindu (1K)', self.load_domain_6_hindu),
            ('Domain 7: Wikipedia (1K)', self.load_domain_7_wikipedia),
            ('Domain 8: Statutes (New)', self.load_domain_8_statutes),
        ]
        
        for name, loader_func in loaders:
            try:
                records = loader_func()
                all_records.extend(records)
            except Exception as e:
                logger.error(f"Failed to load {name}: {e}")
                continue
        
        logger.info("="*60)
        logger.info(f"TOTAL LOADED: {len(all_records):,} records")
        logger.info("="*60)
        logger.info("\nBreakdown by domain:")
        for domain, count in self.stats.items():
            logger.info(f"  {domain}: {count:,} records")
        logger.info("="*60)
        
        return all_records
    
    def get_stats(self) -> Dict:
        """Get loading statistics"""
        return self.stats

