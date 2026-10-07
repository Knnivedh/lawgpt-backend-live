import requests
import json

url = "http://localhost:5000/api/query"
payload = {
    "question": "tell about dharmastal soujanya case update",
    "session_id": "test_timeline_check"
}
headers = {"Content-Type": "application/json"}

try:
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json().get('response', {})
        
        # Check for new fields
        print("\n=== NEW FIELDS CHECK ===")
        print(f"Timeline present: {'timeline' in data}")
        print(f"Primary documents present: {'primary_documents' in data}")
        
        if 'timeline' in data:
            timeline = data['timeline']
            print(f"\nTimeline: {json.dumps(timeline, indent=2)}")
        else:
            print("\nTimeline: Not found in response")
        
        if 'primary_documents' in data:
            p_docs = data['primary_documents']
            print(f"\nPrimary Documents: {json.dumps(p_docs, indent=2)}")
        else:
            print("\nPrimary Documents: Not found in response")
        
        # Print answer snippet
        answer = data.get('answer', '')
        print(f"\nAnswer snippet: {answer[:200]}...")
        
    else:
        print(f"Error: {response.text}")
        
except Exception as e:
    import traceback
    print(f"Request failed: {e}")
    traceback.print_exc()
