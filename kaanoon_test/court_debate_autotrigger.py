"""
B — Auto-suggest Court Debate Mode from /api/query
====================================================
Patch the existing query endpoint so it calls Phase 1 complexity check
and, when score ≥ 8, appends a Court Debate offer to the response.

How to apply
------------
Find `async def query_endpoint` (or similar) in advanced_rag_api_server.py
and call `maybe_inject_debate_offer()` on the completed response dict.

Or simply add this import + one call at the bottom of the handler:
    from kaanoon_test.court_debate_autotrigger import maybe_inject_debate_offer
    result = maybe_inject_debate_offer(result, user_query, session_id)
"""

from __future__ import annotations
import logging
import os
import re
import sys
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ── Complexity heuristics (no extra LLM call by default) ────────────────────

_HIGH_COMPLEXITY_KEYWORDS = [
    r"whistle.?blow", r"retalia", r"arbitration",
    r"discriminat", r"termina.*employ", r"fundamental rights",
    r"constitutional.*valid", r"competing.*jurisdict",
    r"senior.*counsel", r"high.?court.*supreme", r"conflicting.*judgment",
    r"writ petition", r"criminal.*civil", r"contempt of court",
    r"injunction.*stay", r"moratorium", r"insolvency.*ibc",
    r"class.*action", r"public.*interest.*litiga", r"pil",
    r"financial.*irregular", r"forensic.*audit", r"money.*launder",
    r"benami", r"fema.*violation", r"derivative.*suit",
    r"oppression.*mismanage", r"companies act.*winding",
]

_COMPILED = [re.compile(p, re.I) for p in _HIGH_COMPLEXITY_KEYWORDS]


def _estimate_complexity(query: str) -> int:
    """
    Quick heuristic score 1-10. Avoids an extra LLM call on every query.
    Falls back to LLM Phase 1 only when score is borderline (6-7).
    """
    score = 3  # base
    q_lower = query.lower()

    # Keyword matches
    hits = sum(1 for pat in _COMPILED if pat.search(q_lower))
    score += min(hits * 1.5, 4)

    # Length signal
    if len(query.split()) > 60:
        score += 1

    # Multiple distinct questions
    if query.count("?") >= 2:
        score += 1

    return min(round(score), 10)


def _llm_complexity_check(query: str, session_id: Optional[str] = None) -> bool:
    """
    Full LLM Phase 1 check — only called when heuristic is borderline.
    Returns True if score ≥ 8.
    """
    try:
        from kaanoon_test.court_debate_engine import CourtDebateEngine
        engine = CourtDebateEngine()
        result = engine.check_complexity(query, session_id=session_id)
        return result.get("is_complex", False)
    except Exception as e:
        logger.warning(f"[AutoTrigger] LLM complexity check failed: {e}")
        return False


_OFFER_BLOCK = (
    "\n\n---\n"
    "⚖ **This is a highly complex legal question.**\n\n"
    "Would you like me to activate **Court Debate Mode**?\n\n"
    "In this mode, multiple senior lawyer agents will:\n"
    "- Present **strong positive and negative arguments** at 7 levels\n"
    "- Cross-examine evidence from your **Zilliz Cloud legal database**\n"
    "- Deliver a **final judicial synthesis** with confidence score\n\n"
    "Reply **YES** or click the **⚖ Court Debate Mode** button below."
)

_OFFER_META = {
    "court_debate_suggested": True,
    "court_debate_endpoint": "/api/court-debate",
    "court_debate_stream_endpoint": "/api/court-debate/stream",
}


def maybe_inject_debate_offer(
    response: Dict,
    user_query: str,
    session_id: Optional[str] = None,
    force_llm: bool = False,
) -> Dict:
    """
    Call at end of /api/query handler.
    Appends Court Debate offer to response when query is highly complex.

    Parameters
    ----------
    response    : The existing response dict from the RAG pipeline.
    user_query  : Raw user question string.
    session_id  : Session id for memory lookup.
    force_llm   : Always use LLM instead of heuristic (slower but accurate).

    Returns
    -------
    Same dict, potentially with `court_debate_suggested` + offer appended.
    """
    if not user_query or not user_query.strip():
        return response

    # Already in debate mode — don't double-offer
    if response.get("court_debate_suggested"):
        return response

    try:
        if force_llm:
            is_complex = _llm_complexity_check(user_query, session_id)
        else:
            score = _estimate_complexity(user_query)
            if score >= 8:
                is_complex = True
            elif score >= 6:
                # borderline — ask the LLM to confirm
                is_complex = _llm_complexity_check(user_query, session_id)
            else:
                is_complex = False

        if not is_complex:
            return response

        logger.info(f"[AutoTrigger] Complex query detected — injecting debate offer ({session_id})")

        # Append offer text to the main answer field
        for field in ("answer", "response", "text", "content", "result"):
            if isinstance(response.get(field), str):
                response[field] += _OFFER_BLOCK
                break

        response.update(_OFFER_META)

    except Exception as e:
        logger.warning(f"[AutoTrigger] Offer injection failed: {e}")

    return response
