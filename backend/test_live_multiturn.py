import sys
import json
import urllib.request
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = 'http://localhost:8001'

def send_chat(query, thread_id=None):
    payload = {'query': query, 'thread_id': thread_id}
    req = urllib.request.Request(
        f'{BASE_URL}/chat/stream',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    done_data = None
    all_events = []
    with urllib.request.urlopen(req, timeout=90) as resp:
        for line in resp:
            s = line.decode('utf-8', errors='ignore').strip()
            if s.startswith('data: '):
                try:
                    d = json.loads(s[6:])
                    all_events.append(d.get('type'))
                    if d.get('type') == 'done':
                        done_data = d
                except:
                    pass
    return done_data, all_events

print("=" * 70)
print("RUNNING MULTI-TURN INTAKE & ADVICE VALIDATION")
print("=" * 70)

# Turn 1
print("\n[TURN 1] Initial Vague Inquiry...")
d1, ev1 = send_chat("I want a divorce from my husband.")
t_id = d1.get("thread_id")
print(f"Thread: {t_id}")
print(f"Events: {' -> '.join(ev1)}")
print(f"Message Type: {d1.get('message_type')}")
print(f"Bot Question: {d1.get('response')}")
print(f"Gaps: {[i.get('field') for i in d1.get('info_needed', [])]}")

# Turn 2
print("\n[TURN 2] Answering grounds & marriage...")
d2, ev2 = send_chat("We were married under Hindu rites in 2020 in Delhi. He beats me and had an extramarital affair.", thread_id=t_id)
print(f"Events: {' -> '.join(ev2)}")
print(f"Message Type: {d2.get('message_type')}")
print(f"Bot Question: {d2.get('response')}")
print(f"Collected Facts: {d2.get('info_collected')}")

# Turn 3
print("\n[TURN 3] Answering child & income...")
d3, ev3 = send_chat("We have a 3 year old son who is with me. My husband earns 1.5 lakhs as an engineer but claims he has zero income.", thread_id=t_id)
print(f"Events: {' -> '.join(ev3)}")
print(f"Message Type: {d3.get('message_type')}")
print(f"Response Length: {len(d3.get('response', ''))}")
print(f"Response Preview:\n{d3.get('response', '')[:400]}...")
print("=" * 70)
