
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
    from kaanoon_test.external_apis.web_search_client import get_web_search_client
    
    client = get_web_search_client()
    
    # query = "What is the Supreme Court judgment on Electoral Bonds?"
    # Fallback query logic from EnhancedRetriever:
    query = "Supreme Court judgment on Electoral Bonds site:indiankanoon.org OR site:livelaw.in OR site:barandbench.com"
    
    # Test WITHOUT explicit year check (simulating user forgetting 'latest')
    print(f"\nSearching (Standard): '{query}'")
    results = client.search(query, max_results=5)
    for r in results:
        print(f" - {r['title']} ({r['link']})")

    # Test WITH explicit year (simulating 'latest' logic)
    query_recent = query + " 2024 2025"
    print(f"\nSearching (Recent): '{query_recent}'")
    results_recent = client.search(query_recent, max_results=5)
    for r in results_recent:
        print(f" - {r['title']} ({r['link']})")

except Exception as e:
    logger.exception("Test failed")
