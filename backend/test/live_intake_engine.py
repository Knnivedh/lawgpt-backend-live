"""
Live check of the family-law intake (clarification) engine.

Plays several different family cases end to end against the real models. A
simulated client (an LLM role-playing a hidden fact sheet) answers each
follow-up question, sometimes with "I don't know". Then it checks:

  * every personal case got at least FAMILY_MIN_QUESTIONS questions,
  * no question was repeated inside a case,
  * no question is the canned fallback text,
  * questions differ between cases (they are written per case, not a fixed list),
  * the case with an attached document gets document-aware questions.

Calls the real providers, so it is not a pytest test. Run from backend/:
    .venv/Scripts/python.exe test/live_intake_engine.py
"""

import asyncio
import difflib
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver

from config import get_settings
from graph import create_graph
from lang_utils import detect_language
from llm_utils import invoke_llm, strip_think

NOTICE = """LEGAL NOTICE
From: Adv. R. K. Mehta, counsel for Mr. Suresh Patil
To: Mrs. Kavita Patil
Date: 2 September 2026

Under instructions from my client Mr. Suresh Patil, you are hereby called upon to return to the
matrimonial home at Nashik within 15 days of receipt of this notice. You left the matrimonial home on
10 June 2026 without reasonable cause, taking our client's minor daughter with you. If you fail to
return, my client will file a petition for restitution of conjugal rights under Section 9 of the Hindu
Marriage Act, 1955, and will also seek custody of the minor child.
"""

CASES = [
    {
        "name": "divorce",
        "message": "I want to divorce my wife. We fight every day and she went to her parents' house with our daughter.",
        "persona": "Male, Hindu, married 2017 in Jaipur, daughter aged 5, wife left 8 months ago, he earns 60k/month, "
                   "wife is a teacher, no case filed yet, he does not know if she will agree to mutual divorce.",
    },
    {
        "name": "domestic_violence",
        "message": "My husband beats me when he is drunk and his mother supports him. What can I do?",
        "persona": "Female, Hindu, married 2019, lives with husband and mother-in-law in Lucknow, beaten 3 times this "
                   "month, has photos of injuries, no police complaint yet, no children, works part-time, scared to go home.",
    },
    {
        "name": "custody",
        "message": "My ex-husband is not letting me meet my 4-year-old son after our divorce.",
        "persona": "Female, Christian, divorced in 2025 by Pune family court, custody given to father, court allowed her "
                   "weekend visits, he has blocked visits for 3 months, she has messages proving it.",
    },
    {
        "name": "dowry",
        "message": "My in-laws are demanding 5 lakh rupees and a car, otherwise they say they will throw me out.",
        "persona": "Female, Hindu, married 14 months ago, the demands started 2 months after marriage, she has WhatsApp "
                   "voice notes, parents gave jewellery at wedding (her stridhan), now kept by mother-in-law.",
    },
    {
        "name": "citizen_card_two_courts",
        "message": "I filed a domestic violence case in one court and a maintenance case in another court. Will I get "
                   "money from both courts, or will the judge cut the amount from one of them?",
        "persona": "Female, Hindu, DV case in Magistrate court Delhi asking monthly money, Section 125 maintenance case in "
                   "family court, interim order of 8000/month already in the DV case, husband earns about 50k.",
    },
    {
        "name": "notice_with_document",
        "message": "My husband's lawyer sent me this notice. What should I do?",
        "document": NOTICE,
        "persona": "Female (Kavita), Hindu, left home because husband was abusive and stopped giving household money, "
                   "daughter aged 3 lives with her at her parents' house in Pune, she does not want to go back.",
    },
]

FALLBACK_TEXT = "Could you please provide information about your"


def turn_input(query, document=None):
    state = {
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
    if document:
        state["document_context"] = f"[legal_notice.txt]\n{document}"
    return state


def simulated_client_reply(persona, question):
    """An LLM plays the client: answers only from the fact sheet, briefly."""
    reply = invoke_llm([
        SystemMessage(content=(
            "You are role-playing a client talking to a family lawyer in India. Answer the lawyer's question in "
            "1-2 short, natural sentences using ONLY these facts. If the facts do not cover it, say you don't know "
            f"or are not sure.\nFACTS: {persona}"
        )),
        HumanMessage(content=question),
    ], purpose="fast", max_tokens=200, temperature=0.5, deadline=30)
    return strip_think(reply.content)[:400]


async def run_case(case):
    app = await create_graph(MemorySaver())
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    questions, started = [], time.time()
    out = await app.ainvoke(turn_input(case["message"], case.get("document")), config=config)
    for _ in range(14):
        kind = out.get("message_type") or "final_response"
        if kind == "final_response":
            break
        question = (out.get("response") or "").strip()
        questions.append(question)
        answer = simulated_client_reply(case["persona"], question)
        out = await app.ainvoke(turn_input(answer), config=config)
    return {
        "name": case["name"],
        "questions": questions,
        "final": (out.get("message_type") or "final_response") == "final_response",
        "answer": (out.get("response") or "")[:220].replace("\n", " "),
        "seconds": time.time() - started,
        "fields": list((out.get("info_collected") or {}).keys()),
    }


async def main():
    min_q = get_settings().family_min_questions
    results = []
    for case in CASES:
        r = await run_case(case)
        results.append(r)
        print(f"\n{'=' * 100}\nCASE {r['name']}: {len(r['questions'])} questions, final={r['final']}, {r['seconds']:.0f}s")
        for i, q in enumerate(r["questions"], 1):
            print(f"  Q{i}: {q[:230]}")
        print(f"  ANSWER: {r['answer']}...")

    print(f"\n{'=' * 100}\nCHECKS (min questions = {min_q})")
    problems = 0
    for r in results:
        repeats = [
            (a, b) for i, a in enumerate(r["questions"]) for b in r["questions"][i + 1:]
            if difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() > 0.85
        ]
        canned = [q for q in r["questions"] if FALLBACK_TEXT in q]
        ok = len(r["questions"]) >= min_q and not repeats and not canned and r["final"]
        problems += not ok
        print(f"  {'PASS' if ok else 'FAIL'} {r['name']:26s} questions={len(r['questions'])} repeats={len(repeats)} "
              f"canned={len(canned)} final={r['final']}")

    all_q = [(r["name"], q) for r in results for q in r["questions"]]
    cross = [
        (a, b) for i, (na, a) in enumerate(all_q) for nb, b in all_q[i + 1:]
        if na != nb and difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() > 0.85
    ]
    problems += bool(cross)
    print(f"  {'PASS' if not cross else 'FAIL'} questions differ across cases (near-identical pairs: {len(cross)})")
    print(f"\n{'ALL CHECKS PASSED' if not problems else f'{problems} CHECK(S) FAILED'}")


if __name__ == "__main__":
    asyncio.run(main())
