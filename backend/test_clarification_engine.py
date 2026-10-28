import urllib.request
import json
import time
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8001"

print("=" * 80)
print("TESTING CLARIFICATION & INFORMATION GATHERING ENGINE")
print("=" * 80)

# Underspecified legal inquiry that should trigger clarification or information gathering
vague_query = "I want a divorce from my husband."
print(f"Test Query: '{vague_query}'\n")

stream_req = urllib.request.Request(
    f"{BASE_URL}/chat/stream",
    data=json.dumps({"query": vague_query}).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

events = []
thread_id = None
received_question = None

try:
    with urllib.request.urlopen(stream_req, timeout=40) as resp:
        for line in resp:
            line_str = line.decode("utf-8", errors="ignore").strip()
            if line_str.startswith("data:"):
                payload_str = line_str[5:].strip()
                if payload_str in ("[DONE]", ""):
                    continue
                try:
                    payload = json.loads(payload_str)
                    etype = payload.get("type")
                    events.append(etype)
                    if etype == "setup":
                        thread_id = payload.get("thread_id")
                        print(f"• Thread initialized: {thread_id}")
                    elif etype == "clarification":
                        received_question = payload.get("content")
                        print(f"\n[CLARIFICATION TRIGGERED]")
                        print(f"Clarification Question: {received_question}")
                    elif etype == "information_gathering":
                        received_question = payload.get("content")
                        info_needed = payload.get("info_needed")
                        print(f"\n[INFORMATION GATHERING TRIGGERED]")
                        print(f"Follow-up Question: {received_question}")
                        print(f"Items Needed: {info_needed}")
                    elif etype == "token":
                        content = payload.get("content")
                        if not received_question:
                            received_question = content
                except Exception:
                    pass

    print(f"\nSSE Pipeline Events: {' -> '.join(events)}")
    print(f"Clarification / Follow-up received: {bool(received_question)}")

    # If an information-gathering question was asked, let's answer it to test the 2nd turn!
    if thread_id and received_question:
        print("\n" + "-" * 60)
        print("TESTING 2ND CONVERSATION TURN (Answering Clarification Question)")
        print("-" * 60)
        user_answer = "We were married under Hindu rites in 2019 and have been living separately for 2 years."
        print(f"User Reply: '{user_answer}'\n")

        second_req = urllib.request.Request(
            f"{BASE_URL}/chat/stream",
            data=json.dumps({"query": user_answer, "thread_id": thread_id}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        second_tokens = []
        with urllib.request.urlopen(second_req, timeout=40) as resp2:
            for line2 in resp2:
                l2 = line2.decode("utf-8", errors="ignore").strip()
                if l2.startswith("data:"):
                    p2_str = l2[5:].strip()
                    if p2_str in ("[DONE]", ""):
                        continue
                    try:
                        p2 = json.loads(p2_str)
                        if p2.get("type") == "token":
                            second_tokens.append(p2.get("content", ""))
                        elif p2.get("type") == "information_gathering":
                            print(f"Further information question: {p2.get('content')}")
                    except Exception:
                        pass

        ans2 = "".join(second_tokens)
        print(f"Turn 2 Output Length: {len(ans2)} chars")
        print(f"Turn 2 Sample Advice:\n{ans2[:350]}...\n")

except Exception as e:
    print("Test Error:", e)
