import sys
import re
import sqlite3
import bcrypt

sys.stdout.reconfigure(encoding='utf-8')

with open('c:/Users/LOQ/Downloads/ai-legal-assistance-system/vercel_frontend/app/page.js', encoding='utf-8') as f:
    text = f.read()

match = re.search(r'const DEMO_ACCOUNTS = (\[.*?\]);', text, re.DOTALL)
if match:
    raw = match.group(1)
    emails = re.findall(r'email:\s*"([^"]+)"', raw)
    passwords = re.findall(r'password:\s*"([^"]+)"', raw)
    names = re.findall(r'name:\s*"([^"]+)"', raw)

    conn = sqlite3.connect('c:/Users/LOQ/Downloads/Indian-Family-Law-Assistant-repo/backend/family_law.db')
    cur = conn.cursor()
    for e, p, n in zip(emails, passwords, names):
        hashed = bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        print(f"Registering: {n} ({e})")
        cur.execute('''
            INSERT OR REPLACE INTO users (email, full_name, hashed_password)
            VALUES (?, ?, ?)
        ''', (e, n, hashed))
    conn.commit()
    conn.close()
    print("Done! All demo accounts registered successfully.")
