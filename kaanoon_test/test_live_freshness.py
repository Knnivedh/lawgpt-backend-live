
import sys
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add paths
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.append(str(current_dir))
sys.path.append(str(project_root))

# Load .env
load_dotenv(project_root / "config" / ".env")

try:
    from kaanoon_test.external_apis.indian_kanoon_client import IndianKanoonClient
    
    client = IndianKanoonClient()
    
    # Test Queries - Specific to Supreme Court
    queries = ["Electoral Bonds Supreme Court 2024", "Association for Democratic Reforms vs Union of India 2024"]
    
    print("\n===== MANUAL FRESHNESS CHECK =====")
    
    for q in queries:
        print(f"\nSearching for: '{q}'")
        results = client.search_judgments(q, max_results=5)
        
        print(f"Found {len(results)} results:")
        for r in results:
            print(f"  - [{r['year']}] {r['title']} (Court: {r['court']})")
            
    print("\n==================================")

except Exception as e:
    logger.exception("Test failed")
