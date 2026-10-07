import sys
from pathlib import Path
import logging

# Add parent to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress noisy logs
logging.getLogger("chromadb").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

from rag_system.core.hybrid_chroma_store import HybridChromaStore

MISSING_CASES = [
    {"name": "Hadiya Case / Shafin Jahan", "query": "Shafin Jahan v. Asokan K.M. Hadiya case conversion marriage choice", "keywords": ["Hadiya", "Shafin Jahan"]},
    {"name": "Vidya Devi Case", "query": "Vidya Devi v. State of Himachal Pradesh adverse possession state private land", "keywords": ["Vidya Devi", "300A"]},
    {"name": "Sharad Birdhichand Sarda", "query": "Sharad Birdhichand Sarda v. State of Maharashtra circumstantial evidence murder trial", "keywords": ["Sharad Birdhichand"]},
    {"name": "Dev Dutt v. Union of India", "query": "Dev Dutt v. Union of India natural justice service law ACR communication", "keywords": ["Dev Dutt"]},
    {"name": "Jacob Mathew", "query": "Jacob Mathew v. State of Punjab medical negligence criminal liability sectional 304A IPC", "keywords": ["Jacob Mathew"]}
]

def run_diagnostic():
    print("=" * 80)
    print("🔍 DIAGNOSTIC: MISSING LANDMARK CASE SEARCH")
    print("=" * 80)
    
    try:
        store = HybridChromaStore()
        print(f"Total Documents in DB: {store.collection.count():,}")
        print("-" * 80)
        
        results = []
        for case in MISSING_CASES:
            print(f"Searching for: {case['name']}")
            
            # 1. Vector Search
            query_res = store.collection.query(
                query_texts=[case['query']],
                n_results=3
            )
            
            found = False
            top_score = 0
            if query_res['documents'] and query_res['documents'][0]:
                for i, doc in enumerate(query_res['documents'][0]):
                    text = doc.lower()
                    if any(kw.lower() in text for kw in case['keywords']):
                        found = True
                        top_score = 1.0 - (query_res['distances'][0][i] if query_res['distances'] else 0.5)
                        break
            
            status = "✅ FOUND" if found else "❌ NOT FOUND"
            print(f"   Status: {status} (Score: {top_score:.2f})")
            
            results.append({
                "case": case['name'],
                "status": status,
                "score": top_score
            })
            
        print("\n" + "=" * 80)
        print("📊 DIAGNOSTIC SUMMARY")
        print("=" * 80)
        found_count = len([r for r in results if "FOUND" in r['status']])
        print(f"Results: {found_count}/{len(MISSING_CASES)} cases found.")
        
        if found_count < len(MISSING_CASES):
            print("\n🚨 CONCLUSION: Critical data gap detected.")
            print("Missing cases are likely in 'Supreme Court 100%' PDFs.")
            print("ACTION REQUIRED: Run ingest_supreme_court_100.py")
        else:
            print("\n✅ CONCLUSION: Data is present, but retrieval/LLM citation is weak.")
            print("ACTION REQUIRED: Optimize adapter prompts and hybrid search weights.")

    except Exception as e:
        print(f"❌ Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_diagnostic()
