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
    with urllib.request.urlopen(req, timeout=120) as resp:
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

print("--- Turn 8: Answering property & assets ---")
t_id = "3b8fe080-df36-4af7-bfc5-a3f58bd51d99"
d8, ev8 = send_chat("He owns a 2BHK flat in Noida and a Honda City car registered in his name.", thread_id=t_id)

print(f"Events: {' -> '.join(ev8)}")
print(f"Message Type: {d8.get('message_type')}")
print(f"Response Length: {len(d8.get('response', ''))}")
print(f"Sources retrieved: {len(d8.get('sources', []))}")
print(f"\n=== FINAL LEGAL RESPONSE ===\n{d8.get('response', '')}\n")
