"""
SUPREME COURT 100% INGESTION
Index all Supreme Court judgments from supreme_court_judgments_100% folder
PDF files organized by year (1952-2024)
"""

import json
import sys
import logging
from pathlib import Path
from typing import List, Dict
from tqdm import tqdm
import PyPDF2

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
SC_100_DIR = PROJECT_ROOT / "DATA" / "supreme_court_judgments_100%" / "supreme_court_judgments"

def safe_str(value, default='N/A'):
    """Convert None to default string"""
    return str(value) if value is not None else default

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
    except Exception as e:
        logger.error(f"Error reading PDF {pdf_path.name}: {e}")
        return None

class SupremeCourtIndexer:
    """Index Supreme Court 100% judgments"""
    
    def __init__(self):
        logger.info("="*80)
        logger.info("SUPREME COURT 100% INGESTION")
        logger.info("="*80)
        
        self.store = HybridChromaStore()
        self.total_indexed = 0
        self.errors = []
        self.skipped = 0
    
    def get_all_pdf_files(self):
        """Get all PDF files organized by year"""
        logger.info(f"\nScanning directory: {SC_100_DIR}")
        
        all_pdfs = list(SC_100_DIR.rglob("*.PDF")) + list(SC_100_DIR.rglob("*.pdf"))
        
        logger.info(f"Found {len(all_pdfs):,} PDF files")
        
        # Group by year
        by_year = {}
        for pdf in all_pdfs:
            year = pdf.parent.name
            if year not in by_year:
                by_year[year] = []
            by_year[year].append(pdf)
        
        logger.info(f"\nYears covered: {len(by_year)}")
        for year in sorted(by_year.keys()):
            logger.info(f"  {year}: {len(by_year[year]):,} files")
        
        return all_pdfs
    
    def parse_case_name_from_filename(self, filename):
        """Extract case name from filename"""
        # Remove .PDF extension
        name = filename.replace('.PDF', '').replace('.pdf', '')
        # Replace underscores with spaces
        name = name.replace('_', ' ')
        # Clean up
        name = name.replace('  ', ' ').strip()
        return name
    
    def index_pdfs(self, pdf_files, batch_size=10):
        """Index all PDF files"""
        logger.info("\n" + "="*80)
        logger.info("STARTING INDEXING")
        logger.info("="*80)
        
        initial_count = self.store.collection.count()
        logger.info(f"Current documents in database: {initial_count:,}")
        
        logger.info(f"\nProcessing {len(pdf_files):,} PDF files...")
        logger.info("⚠️ Note: PDF extraction is slow, ~5-10 seconds per file")
        
        indexed = 0
        for i in tqdm(range(0, len(pdf_files), batch_size), desc="SC 100% PDFs"):
            batch = pdf_files[i:i+batch_size]
            
            texts = []
            metadatas = []
            ids = []
            
            for pdf_path in batch:
                # Extract text
                text_content = extract_text_from_pdf(pdf_path)
                
                if not text_content or len(text_content.strip()) < 100:
                    self.skipped += 1
                    continue
                
                # Parse metadata from filename/path
                case_name = self.parse_case_name_from_filename(pdf_path.stem)
                year = pdf_path.parent.name
                
                doc_text = f"""
CASE NAME: {case_name}
COURT: Supreme Court of India
YEAR: {year}

FULL JUDGMENT:
{text_content}
"""
                
                metadata = {
                    'source': 'Supreme Court 100%',
                    'case_name': case_name[:500],
                    'year': year,
                    'court': 'Supreme Court of India',
                    'type': 'judgment',
                    'file': pdf_path.name
                }
                
                texts.append(doc_text)
                metadatas.append(metadata)
                ids.append(f"sc_100_{year}_{hash(pdf_path.name) % 100000}")
            
            if texts:
                try:
                    self.store.collection.add(
                        documents=texts,
                        metadatas=metadatas,
                        ids=ids
                    )
                    indexed += len(texts)
                except Exception as e:
                    logger.error(f"Error in batch {i}: {e}")
                    self.errors.append(f"Batch {i}: {e}")
        
        self.total_indexed = indexed
        
        final_count = self.store.collection.count()
        logger.info("\n" + "="*80)
        logger.info("📊 INDEXING COMPLETE")
        logger.info("="*80)
        logger.info(f"Successfully indexed: {indexed:,} judgments")
        logger.info(f"Skipped (no content): {self.skipped:,}")
        logger.info(f"Total in database: {final_count:,}")
        
        if self.errors:
            logger.warning(f"\n⚠️ {len(self.errors)} errors occurred")
        
        return indexed
    
    def run_full_ingestion(self):
        """Run complete Supreme Court 100% ingestion"""
        # Get all PDFs
        pdf_files = self.get_all_pdf_files()
        
        if not pdf_files:
            logger.error("No PDF files found!")
            return
        
        # Index all
        indexed = self.index_pdfs(pdf_files)
        
        logger.info("\n✅ SUPREME COURT 100% INGESTION COMPLETE!")
        logger.info(f"🎯 Added {indexed:,} Supreme Court judgments")
        logger.info("\n🔄 Run verify_rag_complete.py to confirm")


def main():
    indexer = SupremeCourtIndexer()
    
    print("\n" + "="*80)
    print("⚠️  SUPREME COURT 100% INGESTION")
    print("   This will index PDF judgments from 1952-2024")
    print("   Estimated: ~72,000 PDFs")
    print("   Estimated time: 3-4 hours (PDF extraction is slow)")
    print("="*80)
    
    response = input("\nProceed with Supreme Court 100% ingestion? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Cancelled.")
        return
    
    indexer.run_full_ingestion()
    
    print("\n✅ DONE! Verify with: python verify_rag_complete.py")


if __name__ == "__main__":
    main()
