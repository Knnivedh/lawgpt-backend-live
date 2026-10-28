import io
import json
import urllib.request
import time
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8001"

complex_query = (
    "My sister was married under the Hindu Marriage Act, 1955 in November 2021. "
    "For the past two years, she was subjected to continuous physical and mental cruelty for dowry by her husband and in-laws. "
    "Three months ago, she was thrown out of her matrimonial home without any financial support, while her 2-year-old toddler "
    "was forcibly retained by the father who denies visitation. Her Stridhan gold jewellery and wedding gifts remain locked with her mother-in-law.\n"
    "1. Can she simultaneously claim interim maintenance under Section 125 CrPC (now Section 144 BNSS) and Section 24 Hindu Marriage Act? "
    "How does the Supreme Court ruling in Rajnesh v. Neha prevent conflicting or overlapping maintenance orders?\n"
    "2. What is her immediate legal recourse to recover custody of her 2-year-old child under Section 6(a) of the Hindu Minority and Guardianship Act, 1956?\n"
    "3. How can she secure immediate return of her Stridhan and residence protection orders under the Protection of Women from Domestic Violence Act, 2005 (PWDVA)?"
)

print("=" * 80)
print("TEST 1: DIRECT SYNCHRONOUS LEGAL REASONING (/query)")
print("=" * 80)

t0 = time.time()
req = urllib.request.Request(
    f"{BASE_URL}/query",
    data=json.dumps({"query": complex_query, "mode": "family"}).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        elapsed = time.time() - t0
        data = json.loads(resp.read().decode("utf-8"))
        print(f"Status: {resp.status} OK (Response Time: {elapsed:.2f}s)\n")

        print("=== GROUNDED STATUTES DETECTED ===")
        for s in data.get("statutes", []):
            print(f"  • {s.get('section')}: {s.get('act')}")

        print("\n=== RELEVANT PRECEDENTS ===")
        for c in data.get("top_cases", []):
            print(f"  • {c.get('title')} (Relevance: {c.get('score')})")

        print("\n=== GENERATED LEGAL ASSESSMENT (LAY SUMMARY) ===")
        print(data.get("lay_summary", ""))

except Exception as e:
    print(f"Error executing /query: {e}")

print("\n" + "=" * 80)
print("TEST 2: REAL-TIME STREAMING CONVERSATION (/chat/stream)")
print("=" * 80)

stream_req = urllib.request.Request(
    f"{BASE_URL}/chat/stream",
    data=json.dumps({"query": complex_query}).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

stream_start = time.time()
first_token_time = None
tokens_received = []
event_types = []

try:
    with urllib.request.urlopen(stream_req, timeout=60) as resp:
        print(f"Connection Status: {resp.status} OK")
        for line in resp:
            decoded = line.decode("utf-8", errors="ignore").strip()
            if decoded.startswith("data:"):
                payload_str = decoded[5:].strip()
                if payload_str in ("[DONE]", ""):
                    continue
                try:
                    payload = json.loads(payload_str)
                    etype = payload.get("type")
                    if etype and etype not in event_types:
                        event_types.append(etype)
                    if etype == "token":
                        if first_token_time is None:
                            first_token_time = time.time() - stream_start
                        content = payload.get("content") or payload.get("data") or ""
                        tokens_received.append(content)
                    elif etype == "error":
                        print("Stream event error:", payload)
                except Exception:
                    pass

    total_time = time.time() - stream_start
    stream_output = "".join(tokens_received)
    print(f"Streaming completed in {total_time:.2f}s")
    print(f"First token latency: {first_token_time:.2f}s" if first_token_time else "First token: immediate")
    print(f"SSE Event Pipeline: {' -> '.join(event_types)}")
    print(f"Total Response Length: {len(stream_output)} characters")
    print("\n=== STREAMED ANSWER PREVIEW ===")
    print(stream_output[:500], "\n...\n", stream_output[-300:] if len(stream_output) > 300 else "")

except Exception as e:
    print(f"Streaming request error: {e}")
