"""Test POST with Authorization header"""
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

config_path = Path(__file__).parent.parent / "config" / ".env"
load_dotenv(dotenv_path=config_path)
token = os.getenv('INDIAN_KANOON_API_TOKEN')

print("Testing POST with Authorization header...")

url = "https://api.indiankanoon.org/search/"
headers = {
    'Authorization': f'Token {token}',
    'User-Agent': 'LAW-GPT/1.0',
    'Accept': 'application/json'
}
data = {
    'formInput': 'habeas corpus',
    'pagenum': 0
}

response = requests.post(url, data=data, headers=headers, timeout=10)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500]}")

if response.status_code == 200:
    print("\n✓ SUCCESS! API is working")
    import json
    results = response.json()
    print(f"Found {len(results.get('docs', []))} documents")
else:
    print(f"\n✗ FAILED with status {response.status_code}")
