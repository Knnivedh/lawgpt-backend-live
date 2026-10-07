import requests
import json

url = "http://localhost:5000/api/query"
payload = {
    "question": "tell about dharmastal soujanya case update",
    "session_id": "test_dharmastal"
}
headers = {"Content-Type": "application/json"}

try:
    print(f"Sending request to {url}...")
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("\n--- FULL RESPONSE ---")
        print(json.dumps(data, indent=2))
        print("--- END ---")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    import traceback
    print(f"Request failed: {e}")
    traceback.print_exc()
