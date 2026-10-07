import requests
import json

url = "http://localhost:5000/api/query"
headers = {"Content-Type": "application/json"}

# Test queries that should be detected as EDUCATIONAL
test_queries = [
    "tell about dharmastal soujanya case update",
    "tell about dharmastal case",
    "details about atul subhash case",
    "information on xyz vs abc case",
    "what happened in landmark case",
]

print("Testing Case Query Detection")
print("=" * 80)

for i, query in enumerate(test_queries, 1):
    print(f"\n[Test {i}] Query: '{query}'")
    payload = {
        "question": query,
        "session_id": f"test_case_detection_{i}"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json().get('response', {})
            answer = data.get('answer', '')
            
            # Check if it's asking for clarification (wrong behavior)
            if "provide more details" in answer.lower() or "clarify" in answer.lower():
                print("❌ FAILED: System is asking for clarification (should not)")
                print(f"Answer snippet: {answer[:200]}...")
            else:
                print("✅ PASSED: System returned educational response")
                print(f"Answer snippet: {answer[:200]}...")
        else:
            print(f"❌ HTTP Error: {response.text}")
    except Exception as e:
        print(f"❌ Request failed: {e}")

print("\n" + "=" * 80)
print("Test complete")
