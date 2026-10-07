"""
Diagnose Indian Kanoon API Issue
"""
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

# Load token
config_path = Path(__file__).parent.parent / "config" / ".env"
load_dotenv(dotenv_path=config_path)

token = os.getenv('INDIAN_KANOON_API_TOKEN')
print(f"Token loaded: {token[:20]}...")

# Test different API call methods
print("\n" + "="*60)
print("TEST 1: GET request with token in URL params")
print("="*60)

url = "https://api.indiankanoon.org/search/"
params = {
    'formInput': 'habeas corpus',
    'pagenum': 0,
    'token': token  # Try token as param
}

try:
    response = requests.get(url, params=params, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*60)
print("TEST 2: GET request with Authorization header")
print("="*60)

headers = {
    'Authorization': f'Token {token}',
    'User-Agent': 'LAW-GPT/1.0'
}
params = {
    'formInput': 'habeas corpus',
    'pagenum': 0
}

try:
    response = requests.get(url, params=params, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*60)
print("TEST 3: POST request with token")
print("="*60)

data = {
    'formInput': 'habeas corpus',
    'pagenum': 0,
    'token': token
}

try:
    response = requests.post(url, data=data, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*60)
print("Checking Indian Kanoon API documentation...")
print("="*60)
print("According to Indian Kanoon docs:")
print("- API URL format: https://api.indiankanoon.org/search/")
print("- Method: Likely POST with token in form data")
print("- Token should be in request body, not header")
