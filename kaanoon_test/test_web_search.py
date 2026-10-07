
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kaanoon_test.external_apis.web_search_client import get_web_search_client

def test_web_search():
    print("Testing Web Search Client...")
    client = get_web_search_client()
    
    query = "Supreme Court electoral bonds judgment 2024"
    print(f"Query: {query}")
    
    results = client.search(query)
    
    if results:
        print(f"\nFound {len(results)} results:")
        for i, res in enumerate(results, 1):
            print(f"{i}. {res['title']}")
            print(f"   URL: {res['link']}")
            print(f"   Source: {res['source']}")
            print("-" * 40)
    else:
        print("\nNo results found.")

if __name__ == "__main__":
    test_web_search()
