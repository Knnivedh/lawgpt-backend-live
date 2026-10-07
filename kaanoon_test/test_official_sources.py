"""
Test Official Legal Data Sources
Verify India Code and Supreme Court clients
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kaanoon_test.external_apis.india_code_client import get_india_code_client
from kaanoon_test.external_apis.supreme_court_client import get_supreme_court_client

def test_official_sources():
    print("=" * 60)
    print("TESTING OFFICIAL DATA SOURCES")
    print("=" * 60)
    
    # 1. Test India Code Client
    print("\n[TEST 1] India Code (Bare Acts)")
    ic_client = get_india_code_client()
    
    acts_to_test = ["Indian Penal Code", "Juvenile Justice", "Contract Act"]
    
    for act in acts_to_test:
        print(f"\n  Searching for: {act}")
        results = ic_client.search_act(act)
        
        if results:
            print(f"  ✅ Found: {results[0]['title']}")
            print(f"     URL: {results[0]['url']}")
        else:
            print(f"  ❌ Not found")
            
    # 2. Test Supreme Court Client
    print("\n[TEST 2] Supreme Court Official")
    sc_client = get_supreme_court_client()
    
    print(f"\n  Latest Judgments URL: {sc_client.get_latest_judgments_link()}")
    
    citations = ["2017 10 SCC 1", "2017 SCR 1"]
    for cit in citations:
        print(f"\n  Verifying citation: {cit}")
        res = sc_client.verify_official_citation(cit)
        print(f"  Is Official SCR? {res['is_official_scr']}")
        print(f"  Source: {res['source']}")

    print("\n" + "=" * 60)
    print("TESTING COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_official_sources()
