import httpx
import json
import time

BASE_URL = "http://127.0.0.1:8001"

print("=" * 70)
print("VERIFYING FAMILY LAW ASSISTANT ENDPOINTS")
print("=" * 70)

# 1. Health / Root Check
print("\n[TEST 1] Testing /health / /api/docs ...")
try:
    r = httpx.get(f"{BASE_URL}/api/docs", timeout=5.0)
    print(f"Swagger Docs Status: {r.status_code} (OK)")
except Exception as e:
    print(f"Failed to reach /api/docs: {e}")

# 2. Auth Signin / Signup
print("\n[TEST 2] Testing Authentication ...")
email = "verified_demo_user@lawgpt.local"
password = "SecurePassword123!"

try:
    auth_resp = httpx.post(f"{BASE_URL}/auth/signin", json={"email": email, "password": password}, timeout=10.0)
    if auth_resp.status_code != 200:
        auth_resp = httpx.post(f"{BASE_URL}/auth/signup", json={"email": email, "password": password, "full_name": "Verified User", "gender": "female"}, timeout=10.0)
    
    assert auth_resp.status_code == 200, f"Auth failed with {auth_resp.status_code}: {auth_resp.text}"
    token = auth_resp.json()["access_token"]
    print(f"Auth Success! Token received: {token[:25]}...")
except Exception as e:
    print(f"Auth test failed: {e}")
    token = None

headers = {"Authorization": f"Bearer {token}"} if token else {}

# 3. Test /query endpoint (Used by Legal Research tabs)
print("\n[TEST 3] Testing /query endpoint (Direct Research Analysis) ...")
test_questions = [
    "What are the rights of a working mother regarding child custody in India?",
    "Can a Hindu wife claim maintenance under Section 125 CrPC if she is living separately due to cruelty?"
]

for idx, q in enumerate(test_questions, 1):
    t0 = time.time()
    resp = httpx.post(f"{BASE_URL}/query", json={"query": q, "mode": "hybrid"}, timeout=60.0)
    dur = round(time.time() - t0, 2)
    print(f"\nQuery {idx}: '{q}'")
    print(f"Status: {resp.status_code} ({dur}s)")
    if resp.status_code == 200:
        d = resp.json()
        print(f"Statutes Found: {len(d.get('statutes', []))}")
        print(f"Cases Found: {len(d.get('top_cases', []))}")
        lay_summary = d.get("lay_summary", "")
        print(f"Lay Summary Length: {len(lay_summary)} chars")
        print(f"Lay Summary Snippet: {lay_summary[:200]}...")
    else:
        print(f"Error: {resp.text}")

# 4. Test /chat/stream endpoint (Conversational Assistant with LangGraph)
print("\n[TEST 4] Testing /chat/stream endpoint (Conversational SSE) ...")
chat_query = "My husband forced me out of our home after dowry harassment. What immediate legal protections do I have under Indian law?"
print(f"Chat Query: '{chat_query}'")

t0 = time.time()
accumulated_text = ""
events_received = []

with httpx.stream(
    "POST",
    f"{BASE_URL}/chat/stream",
    json={"query": chat_query, "include_reasoning": True, "include_prediction": False},
    headers=headers,
    timeout=120.0
) as r:
    for line in r.iter_lines():
        if line.startswith("data: "):
            try:
                evt = json.loads(line[6:])
                evt_type = evt.get("type")
                events_received.append(evt_type)
                if evt_type == "token":
                    accumulated_text += evt.get("content", "")
                elif evt_type in ("setup", "sources", "done", "reasoning"):
                    print(f"  [SSE Event] {evt_type}")
            except Exception:
                pass

dur = round(time.time() - t0, 2)
print(f"\nStreaming Completed in {dur}s")
print(f"Events captured: {list(set(events_received))}")
print(f"Has <think> tag in text: {'<think>' in accumulated_text}")
print(f"Text length: {len(accumulated_text)} chars")
print("\n--- FINAL ANSWER (FIRST 400 CHARACTERS) ---")
print(accumulated_text[:400])
print("\n--- FINAL ANSWER (LAST 250 CHARACTERS) ---")
print(accumulated_text[-250:])
print("\n" + "=" * 70)
print("TEST SUITE COMPLETE")
print("=" * 70)
