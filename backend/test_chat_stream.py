import asyncio
import json
import httpx

async def test():
    async with httpx.AsyncClient(base_url="http://localhost:8001", timeout=30.0) as client:
        # Auth
        auth = await client.post("/auth/signin", json={"email": "adv.rajesh@lawgpt.in", "password": "password123"})
        token = auth.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        q = "Can a father get custody of a 4-year-old child under Hindu Minority and Guardianship Act?"
        print("Testing query:", q)
        async with client.stream("POST", "/chat/stream", json={"query": q, "include_reasoning": True}, headers=headers) as resp:
            print("Status:", resp.status_code)
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    ev = json.loads(line[6:])
                    print("  Event type:", ev.get("type"))
                    if ev.get("type") == "information_gathering":
                        print("    Info gathering question:", ev.get("content"))
                    elif ev.get("type") == "clarification":
                        print("    Clarification:", ev.get("content"))
                    elif ev.get("type") == "done":
                        print("    Done response:")
                        print("--------------------------------------------------")
                        print(ev.get("response"))
                        print("--------------------------------------------------")

if __name__ == "__main__":
    asyncio.run(test())
