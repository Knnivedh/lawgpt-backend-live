"""
Test Indian Kanoon API Integration
Quick test to verify API connectivity and functionality
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from kaanoon_test.external_apis.indian_kanoon_client import get_indian_kanoon_client


def test_indian_kanoon_api():
    """Test Indian Kanoon API integration."""
    
    print("=" * 60)
    print("TESTING INDIAN KANOON API INTEGRATION")
    print("=" * 60)
    
    client = get_indian_kanoon_client()
    
    # Test 1: Search for famous case
    print("\n[TEST 1] Searching for 'Mukesh v State of MP'...")
    results = client.search_judgments("Mukesh v State of MP", max_results=3)
    
    if results:
        print(f"✅ Found {len(results)} results")
        for i, result in enumerate(results, 1):
            print(f"\n  Result {i}:")
            print(f"  Title: {result['title']}")
            print(f"  Court: {result['court']}")
            print(f"  Year: {result['year']}")
            print(f"  Doc ID: {result['doc_id']}")
    else:
        print("❌ No results found")
    
    # Test 2: Verify citation
    print("\n[TEST 2] Verifying citation '(2017) 9 SCC 161'...")
    verification = client.verify_citation("(2017) 9 SCC 161")
    
    if verification['exists']:
        print(f"✅ Citation verified")
        print(f"  Verified as: {verification['verified_citation']}")
        print(f"  Court: {verification['court']}")
    else:
        print(f"❌ Citation not found")
    
    # Test 3: Search IPC Section
    print("\n[TEST 3] Searching for 'IPC Section 304A'...")
    section_info = client.search_ipc_section("304A")
    
    if section_info:
        print(f"✅ Section found")
        print(f"  Title: {section_info['title']}")
        print(f"  Text preview: {section_info['text'][:200]}...")
    else:
        print("❌ Section not found")
    
    # Test 4: Get recent Supreme Court judgments
    print("\n[TEST 4] Fetching recent Supreme Court judgments...")
    recent = client.get_recent_judgments("Supreme Court", days=30)
    
    if recent:
        print(f"✅ Found {len(recent)} recent judgments")
        for i, judgment in enumerate(recent[:3], 1):
            print(f"\n  Judgment {i}:")
            print(f"  {judgment['title'][:80]}...")
    else:
        print("❌ No recent judgments found")
    
    print("\n" + "=" * 60)
    print("TESTING COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_indian_kanoon_api()
