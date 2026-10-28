import asyncio
import json
import httpx

questions = [
    "Can a father get custody of a 4-year-old child under Hindu Minority and Guardianship Act?",
    "Can a working wife claim maintenance under Section 125 CrPC if she earns an income?",
    "What is the cooling-off period in mutual consent divorce under Section 13B of Hindu Marriage Act, and can it be waived?"
]

async def test_all():
    async with httpx.AsyncClient(base_url="http://localhost:8001", timeout=30.0) as client:
        # Auth
        auth_res = await client.post("/auth/signin", json={"email": "adv.rajesh@lawgpt.in", "password": "password123"})
        token = auth_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        print("=== VERIFYING FAMILY LAW ASSISTANT EXACT QUESTION ANSWERING ===\n")

        for idx, q in enumerate(questions, 1):
            print(f"[{idx}] TESTING USER QUESTION:\n\"{q}\"")
            
            # 1. Test /query endpoint (Used by Frontend tabs)
            res_query = await client.post("/query", json={"query": q, "mode": "family"})
            q_data = res_query.json()
            print(f"  [Direct /query response]")
            print(f"  - Statutes Found ({len(q_data.get('statutes', []))}):")
            for s in q_data.get("statutes", [])[:2]:
                print(f"      • {s.get('act')} ({s.get('section')})")
            print(f"  - Precedents Found ({len(q_data.get('top_cases', []))}):")
            for c in q_data.get("top_cases", [])[:2]:
                print(f"      • {c.get('title')} [Score: {c.get('score')}]")
            print(f"  - Layman Summary Preview:")
            lay = q_data.get("lay_summary", "")
            print(f"    {lay[:250]}...\n")

            # 2. Test /chat/stream endpoint (Used by Chatbot SSE stream)
            print(f"  [Chatbot /chat/stream SSE response]")
            async with client.stream("POST", "/chat/stream", json={"query": q, "include_reasoning": True}, headers=headers) as chat_resp:
                final_answer = ""
                async for line in chat_resp.aiter_lines():
                    if line.startswith("data: "):
                        ev = json.loads(line[6:])
                        if ev.get("type") == "done":
                            final_answer = ev.get("response", "")
                print(f"  - Chatbot Final Answer Preview:")
                print(f"    {final_answer[:250]}...\n")
                print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_all())
