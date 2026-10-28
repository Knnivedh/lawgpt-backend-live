"""
Live multi-turn check of the clarification / information-gathering loop.

Calls the real Dahl models (costs a few cents), so it is not a pytest test.
Run from backend/:
    .venv/Scripts/python.exe test/live_clarification_flow.py [scenario ...]

Each scenario feeds user turns into the compiled graph exactly the way
/chat/stream does (same per-turn input keys, one thread per scenario) and
prints what the assistant did on every turn.
"""

import asyncio
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from graph import create_graph
from lang_utils import detect_language

SCENARIOS = {
    # Greeting first: expect a clarification question, then intake questions.
    "vague": [
        "hi",
        "my husband stopped giving money for our son",
        "We are Hindu",
        "My son is 6 years old",
        "I don't know his exact salary, he works in a private company",
        "I am not sure",
    ],
    # General legal question: expect a direct answer, no questions.
    "general": [
        "What income affidavit does the Supreme Court require from husband and wife in maintenance cases?",
    ],
    # Personal case with some facts: expect only the missing facts to be asked.
    "personal": [
        "My husband left me two years ago and stopped sending money. I want maintenance for me and my son.",
        "We are Hindus, married in 2015 in Pune",
        "I prefer not to say",
        "No case filed yet",
        "ok",
    ],
}


def turn_input(query: str) -> dict:
    """Mirror of main.py chat_stream initial_state for a guest user."""
    return {
        "query": query,
        "messages": [HumanMessage(content=query)],
        "include_reasoning": False,
        "include_prediction": False,
        "detected_language": detect_language(query),
        "needs_more_info": False,
        "reasoning_steps": [],
        "precedent_explanations": [],
        "retrieved_chunks": [],
        "sources": [],
        "message_type": None,
        "name": "the client",
    }


async def run(name: str, turns: list) -> None:
    app = await create_graph(MemorySaver())
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    print(f"\n{'=' * 90}\nSCENARIO: {name}\n{'=' * 90}")
    for i, query in enumerate(turns, 1):
        t = time.time()
        out = await app.ainvoke(turn_input(query), config=config)
        kind = out.get("message_type") or ("final_response" if out.get("response") else "?")
        print(f"\n[{i}] USER: {query}")
        print(f"    -> {kind}  ({time.time() - t:.1f}s)")
        text = (out.get("response") or "").strip()
        print("    ASSISTANT:", text[:400].replace("\n", " ") + ("..." if len(text) > 400 else ""))
        print("    intent:", out.get("user_intent"))
        print("    info_collected:", {k: v[:60] for k, v in (out.get("info_collected") or {}).items()})
        print("    still needed:", [x["field"] for x in out.get("info_needed_list") or []],
              "| asked:", out.get("questions_asked"), "| awaiting:", out.get("awaiting_answer"))
        if kind == "final_response":
            print("    root_query used for retrieval:", (out.get("root_query") or "")[:160].replace("\n", " | "))
            print("    sources:", [s.get("title") for s in (out.get("sources") or [])][:5])
            break
    else:
        print("\n    !! conversation ended without a final response")


async def main() -> None:
    names = sys.argv[1:] or list(SCENARIOS)
    for name in names:
        await run(name, SCENARIOS[name])


if __name__ == "__main__":
    asyncio.run(main())
