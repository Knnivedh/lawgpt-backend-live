"""
Indian Kanoon Bulk Data Collector
Fetches thousands of Supreme Court and High Court judgments to expand LAW-GPT database
Uses authenticated API for unlimited access
"""

import sys
import json
import time
from pathlib import Path
from typing import List, Dict
from datetime import datetime
import logging

# Add parent to pa-th
sys.path.insert(0, str(Path(__file__).parent.parent))

from external_apis.indian_kanoon_client import IndianKanoonClient
from rag_system.core.hybrid_chroma_store import HybridChromaStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IndianKanoonBulkCollector:
    """Collects bulk legal data from Indian Kanoon API"""
    
    # High-value search queries for comprehensive coverage
    SEARCH_QUERIES = [
        # Constitutional Law
        ("Article 14 equality", "Supreme Court", 50),
        ("Article 19 freedom", "Supreme Court", 50),
        ("Article 21 life liberty", "Supreme Court", 100),
        ("Article 32 writ", "Supreme Court", 50),
        ("Basic structure doctrine", "Supreme Court", 30),
        
        # Criminal Law - Major IPC Sections
        ("IPC 302 murder", "Supreme Court", 100),
        ("IPC 304 culpable homicide", "Supreme Court", 50),
        ("IPC 307 attempt to murder", "Supreme Court", 50),
        ("IPC 376 rape sexual assault", "Supreme Court", 100),
        ("IPC 420 cheating fraud", "Supreme Court", 100),
        ("IPC 498A dowry cruelty", "Supreme Court", 75),
        ("IPC 506 criminal intimidation", "Supreme Court", 30),
        
        # BNS Sections (2024 onwards)
        ("BNS 103 murder", "Supreme Court", 20),
        ("BNS 64 rape", "Supreme Court", 20),
        ("BNS 318 cheating", "Supreme Court", 20),
        
        # Property Law
        ("Transfer of Property Act", "Supreme Court", 50),
        ("adverse possession", "Supreme Court", 75),
        ("property dispute partition", "Supreme Court", 50),
        ("easement rights", "Supreme Court", 30),
        
        # Family Law
        ("Hindu Marriage Act divorce", "Supreme Court", 75),
        ("Section 125 CrPC maintenance", "Supreme Court", 100),
        ("BNSS 144 maintenance", "Supreme Court", 20),
        ("PWDVA domestic violence", "Supreme Court", 50),
        ("child custody guardianship", "Supreme Court", 50),
        ("Section 498A cruelty", "Supreme Court", 50),
        
        # Consumer Law
        ("Consumer Protection Act", "Supreme Court", 50),
        ("deficiency in service", "Supreme Court", 30),
        ("e-commerce consumer", "Supreme Court", 20),
        
        # Labour Law
        ("Industrial Disputes Act", "Supreme Court", 50),
        ("wrongful termination", "Supreme Court", 40),
        ("labour rights workers", "Supreme Court", 30),
        
        # Tax Law
        ("GST Goods Services Tax", "Supreme Court", 40),
        ("Income Tax Act", "Supreme Court", 50),
        ("tax evasion assessment", "Supreme Court", 30),
        
        # Constitutional Writs
        ("habeas corpus", "Supreme Court", 30),
        ("mandamus writ", "Supreme Court", 30),
        ("certiorari judicial review", "Supreme Court", 30),
        
        # Evidence & Procedure  
        ("Section 161 CrPC statement", "Supreme Court", 30),
        ("Section 164 CrPC confession", "Supreme Court", 30),
        ("anticipatory bail Section 438", "Supreme Court", 50),
        ("regular bail", "Supreme Court", 40),
        
        # Landmark Topics
        ("privacy right", "Supreme Court", 50),
        ("right to information RTI", "Supreme Court", 40),
        ("POCSO sexual offences", "Supreme Court", 50),
        ("corruption Prevention Act", "Supreme Court", 40),
        
        # High Courts (Major)
        ("property dispute", "Delhi High Court", 50),
        ("contract breach", "Delhi High Court", 30),
        ("trademark infringement", "Delhi High Court", 30),
        ("service matter employment", "Delhi High Court", 30),
    ]
    
    def __init__(self, api_token: str = None):
        """Initialize collector with Indian Kanoon API"""
        self.client = IndianKanoonClient(api_token=api_token)
        self.collected_docs = []
        self.failed_queries = []
        
        # Load existing database
        project_root = Path(__file__).parent.parent
        db_path = project_root / "chroma_db_hybrid"
        self.store = HybridChromaStore(
            persist_directory=str(db_path),
            collection_name="legal_db_hybrid"
        )
    
    def _fetch_page(self, query: str, court: str, page_num: int) -> List[Dict]:
        """
        Fetch a specific page of results
        
        Args:
            query: Search query
            court: Court filter
            page_num: Page number (0-indexed)
            
        Returns:
            List of judgment dictionaries
        """
        try:
            search_query = query
            if court:
                search_query = f"{query} court:{court}"
            
            data = {
                'formInput': search_query,
                'pagenum': page_num
            }
            
            response = self.client.session.post(
                self.client.SEARCH_URL,
                data=data,
                timeout=self.client.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get('docs', []):
                results.append({
                    'title': item.get('title', ''),
                    'doc_id': item.get('tid', ''),
                    'court': self.client._extract_court(item.get('title', '')),
                    'year': self.client._extract_year(item.get('title', '')),
                    'snippet': item.get('headline', '')[:200]
                })
            
            return results
            
        except Exception as e:
            return []
        
    def collect_all(self, max_total: int = 5000) -> Dict:
        """
        Collect judgments across all search queries
        
        Args:
            max_total: Maximum total documents to collect
            
        Returns:
            Summary of collection
        """
        logger.info("="*80)
        logger.info("INDIAN KANOON BULK DATA COLLECTION")
        logger.info("="*80)
        logger.info(f"Target: {max_total} judgments")
        logger.info(f"Search queries: {len(self.SEARCH_QUERIES)}")
        logger.info("")
        
        total_collected = 0
        doc_ids_seen = set()
        
        for i, (query, court, max_results) in enumerate(self.SEARCH_QUERIES, 1):
            if total_collected >= max_total:
                logger.info(f"✓ Reached target of {max_total} documents. Stopping.")
                break
            
            logger.info(f"[{i}/{len(self.SEARCH_QUERIES)}] Searching: \"{query}\" in {court} (max {max_results})")
            
            try:
                # Search for judgments with pagination
                results = self.client.search_judgments(query, court=court, max_results=max_results)
                
                if not results:
                    logger.warning(f"  ⚠ No results for: {query}")
                    self.failed_queries.append((query, court))
                    continue
                
                logger.info(f"  Found {len(results)} judgments on page 0")
                
                # Fetch multiple pages for each query to get more documents
                # Indian Kanoon returns 10 docs per page, so fetch 20 pages = 200 docs per query
                all_results = results.copy()
                
                # Calculate how many pages to fetch (max 20 pages per query)
                pages_to_fetch = min(20, (max_results // 10))
                
                # Fetch additional pages
                for page_num in range(1, pages_to_fetch):
                    try:
                        page_results = self._fetch_page(query, court, page_num)
                        if page_results:
                            all_results.extend(page_results)
                            logger.info(f"    Page {page_num}: +{len(page_results)} judgments")
                        else:
                            break  # No more results on this page
                        time.sleep(1)  # Rate limit between pages
                    except Exception as e:
                        logger.warning(f"    Page {page_num} failed: {e}")
                        break
                
                logger.info(f"  Total found: {len(all_results)} judgments across {page_num + 1} pages")
                
                # Fetch full text for each judgment
                query_new_docs = 0
                for result in all_results:
                    doc_id = result['doc_id']
                    
                    # Skip duplicates
                    if doc_id in doc_ids_seen:
                        continue
                    
                    # Fetch full judgment
                    judgment = self.client.get_judgment(doc_id)
                    
                    if judgment and judgment['text']:
                        self.collected_docs.append({
                            'id': f"indiankanoon_{doc_id}",
                            'title': judgment['title'],
                            'text': judgment['text'],
                            'court': judgment['court'],
                            'year': judgment['year'],
                            'citation': judgment['citation'],
                            'source': 'Indian Kanoon API',
                            'search_query': query,
                            'collected_at': datetime.now().isoformat()
                        })
                        
                        doc_ids_seen.add(doc_id)
                        query_new_docs += 1
                        total_collected += 1
                        
                        if total_collected >= max_total:
                            break
                    
                    # Rate limiting - 1 second between requests
                    time.sleep(1)
                
                logger.info(f"  ✓ Collected {query_new_docs} new judgments (Total: {total_collected})")
                
                # === INCREMENTAL SAVE & INDEX ===
                # Save JSON after every query
                self.save_to_json()
                
                # Index new documents immediately
                if query_new_docs > 0:
                    try:
                        # Get just the new documents from this query
                        new_docs_list = self.collected_docs[-query_new_docs:]
                        self._index_batch(new_docs_list)
                        logger.info(f"  ✓ Indexed {len(new_docs_list)} docs to ChromaDB")
                    except Exception as e:
                        logger.error(f"  ⚠ Indexing error: {e}")
                # ================================
                
                # Small delay between queries
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"  ❌ Error with query '{query}': {e}")
                self.failed_queries.append((query, court))
                continue
        
        logger.info("="*80)
        logger.info(f"COLLECTION COMPLETE")
        logger.info(f"Total judgments collected: {total_collected}")
        logger.info(f"Failed queries: {len(self.failed_queries)}")
        logger.info("="*80)
        
        return {
            'total_collected': total_collected,
            'unique_documents': len(self.collected_docs),
            'failed_queries': len(self.failed_queries)
        }
    
    def save_to_json(self, filename: str = "indian_kanoon_collection.json"):
        """Save collected documents to JSON file"""
        filepath = Path(__file__).parent / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': {
                    'collection_date': datetime.now().isoformat(),
                    'total_documents': len(self.collected_docs),
                    'source': 'Indian Kanoon API',
                    'queries_used': len(self.SEARCH_QUERIES)
                },
                'documents': self.collected_docs
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ Saved {len(self.collected_docs)} documents to {filepath}")
        return filepath
    
    def _index_batch(self, docs_list: List[Dict]):
        """Index a specific batch of documents"""
        if not docs_list:
            return
            
        texts = []
        metadatas = []
        ids = []
        
        for doc in docs_list:
            # Format text with title
            full_text = f"{doc['title']}\n\n{doc['text']}"
            
            metadata = {
                'id': doc['id'],
                'title': doc['title'],
                'court': doc['court'] or 'Unknown',
                'year': str(doc['year']) if doc['year'] else 'Unknown',
                'citation': doc['citation'] or '',
                'source': 'Indian Kanoon API',
                'category': 'Case Law',
                'priority': 'HIGH',
                'type': 'supreme_court_judgment' if 'Supreme Court' in doc.get('court', '') else 'high_court_judgment'
            }
            
            texts.append(full_text)
            metadatas.append(metadata)
            ids.append(doc['id'])
            
        # Add to ChromaDB
        self.store.collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )

    def index_to_chromadb(self):
        """Index ALL collected documents into ChromaDB (for bulk run finalization)"""
        logger.info("="*80)
        logger.info("INDEXING COMPLETE (Already done incrementally)")
        logger.info("="*80)
        return len(self.collected_docs)


def main():
    """Main execution"""
    # Configuration
    MAX_DOCUMENTS = 10000  # Maximum quality - will take ~5 hours
    
    print("\n" + "="*80)
    print("INDIAN KANOON BULK DATA COLLECTION")
    print("="*80)
    print(f"Target documents: {MAX_DOCUMENTS}")
    print(f"This will take approximately {MAX_DOCUMENTS * 1.5 / 60:.0f} minutes")
    print("")
    
    # Initialize collector
    collector = IndianKanoonBulkCollector()
    
    # Collect data
    summary = collector.collect_all(max_total=MAX_DOCUMENTS)
    
    # Save to JSON
    json_path = collector.save_to_json()
    
    # Index to ChromaDB
    indexed_count = collector.index_to_chromadb()
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    print(f"Documents collected: {summary['total_collected']}")
    print(f"Documents indexed: {indexed_count}")
    print(f"Failed queries: {summary['failed_queries']}")
    print(f"JSON file saved: {json_path}")
    print(f"Database size: {collector.store.collection.count()} documents")
    print("="*80)
    print("\n✅ COLLECTION COMPLETE!")
    print("Your LAW-GPT database has been significantly expanded with Supreme Court judgments.")
    print("\nNext steps:")
    print("1. Restart backend server to rebuild BM25 index")
    print("2. Test with legal queries to see improved accuracy")
    print("="*80)


if __name__ == "__main__":
    main()
