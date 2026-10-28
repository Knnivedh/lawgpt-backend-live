import urllib.request
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = 'http://localhost:8001'

queries = [
    ('Vague Query (Clarification Engine)', 'Help me'),
    ('Underspecified Query (Information Gathering Engine)', 'Can I get maintenance?')
]

for label, q in queries:
    print('=' * 80)
    print(f'TEST: {label}')
    print(f'User Query: "{q}"')
    print('=' * 80)
    
    req = urllib.request.Request(
        f'{BASE_URL}/chat/stream',
        data=json.dumps({'query': q}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    with urllib.request.urlopen(req, timeout=40) as resp:
        for line in resp:
            line_str = line.decode('utf-8', errors='ignore').strip()
            if line_str.startswith('data:'):
                payload_str = line_str[5:].strip()
                if payload_str in ('[DONE]', ''):
                    continue
                try:
                    payload = json.loads(payload_str)
                    ptype = payload.get('type')
                    if ptype in ('clarification', 'information_gathering'):
                        print(f'-> Event Type: {ptype}')
                        print(f'-> Emitted Question: {payload.get("content")}')
                        if 'info_needed' in payload:
                            print(f'-> Info Needed: {payload.get("info_needed")}')
                        if 'info_collected' in payload:
                            print(f'-> Info Collected: {payload.get("info_collected")}')
                    elif ptype == 'token':
                        pass
                except Exception as e:
                    pass
    print()
