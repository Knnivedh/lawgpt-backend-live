
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

# Check token
token = os.getenv("INDIAN_KANOON_API_TOKEN")
print(f"API Token present: {'Yes' if token else 'No'}")

try:
    from rag_system.core.hybrid_chroma_store import HybridChromaStore
    from rag_system.core.enhanced_retriever import EnhancedRetriever
    
    # Initialize Store and Retriever
    print("Initializing components...")
    db_path = current_dir / "chroma_db_hybrid"
    store = HybridChromaStore(persist_directory=str(db_path))
    retriever = EnhancedRetriever(store)
    
    # Test Question (Something unlikely to be in local DB unless collected)
    # "Recent Supreme Court judgment on arbitration 2024"
    query = "Supreme Court judgment on crypto currency 2024" 
    
    print(f"\nTesting Retrieval for: '{query}'")
    results = retriever.retrieve(query, use_reranking=True)
    
    print(f"\nResults Found: {len(results)}")
    
    live_results = [r for r in results if r.get('metadata', {}).get('source') == 'Indian Kanoon (Live)']
    print(f"Live Results: {len(live_results)}")
    
    for i, r in enumerate(results[:5]):
        meta = r.get('metadata', {})
        print(f"{i+1}. {meta.get('title', 'No Title')} | Source: {meta.get('source')}")
        
except Exception as e:
    logger.exception("Test failed")
