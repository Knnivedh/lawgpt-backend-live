"""
Clean Generator Node - ONLY generates legal response

This node ONLY generates the legal advice response.
Reasoning analysis happens in a separate node (reasoning_node.py).

This ensures:
- Clean separation of concerns
- Response can't be contaminated by reasoning
- Generator is faster (no reasoning overhead)
- Easier to debug and maintain
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from typing import Dict
from state import FamilyLawState
from config import get_settings
import os
import logging
import re
from lang_utils import detect_language, build_language_instruction, get_language_name
from citation_guard import sanitize_citations, trim_to_last_sentence
from llm_utils import invoke_llm, looks_like_reasoning, strip_think
from legal_notes import select_notes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get configuration from centralized config
settings = get_settings()

logger.info(f"🤖 Generator Configuration:")
logger.info(f"   LLM chain: {settings.llm_chain}")
logger.info(f"   Note: Using Indian law-specific model for better legal context")

# Model calls go through llm_utils.invoke_llm (provider chains in config.py).

# The statute notes are added per case (legal_notes.select_notes), not here: all of them
# cost ~2,200 tokens, and a free Groq key allows 8,000 tokens a minute.
SYSTEM_PROMPT = (
    "You are a senior Indian family law analyst writing for a client who is not a lawyer. "
    "Explain legal issues in simple, plain English with a warm, professional tone.\n\n"
    "GROUNDING RULES (most important):\n"
    "- Facts about the client come ONLY from the case information and the client's own words. Never add facts about their family, money or history, and never assume one that was not given.\n"
    "- Law comes ONLY from the RELEVANT LEGAL CONTEXT and the VERIFIED STATUTE NOTES. Never cite a section, Act or case that is in neither.\n"
    "- If neither covers something the client asks, say so plainly (\"The provided material doesn't cover this; please confirm with a lawyer\") and do not invent a procedure, form, court or deadline.\n"
    "- Take section numbers and names from the statute notes. Where the Legal Context uses an older name, give both (for example Section 125 CrPC, now Section 144 BNSS).\n"
    "- Spell the leading maintenance case as Rajnesh v. Neha (2020), whatever spelling the context uses. Its disclosure affidavit applies to maintenance cases only.\n\n"
    "MONEY, TIME AND CERTAINTY RULES:\n"
    "- Never suggest a rupee amount for the client to claim. Explain what the court weighs and tell the client to list their real monthly needs. Quote a rupee figure only as what a named case awarded.\n"
    "- Maintenance (s.125 CrPC / s.144 BNSS, HMA s.24-25, the DV Act's monetary relief) runs from the date of the application. Never promise money for the period before filing; filing sooner protects more of it. This is about maintenance only, not protection or residence orders.\n"
    "- A court decides outcomes: write \"may\", \"is likely to\" or \"can ask for\", not guarantees. Never write that conduct \"amounts to\" cruelty or any legal ground; write \"may amount to\".\n"
    "- Keep the advice consistent with who the client is (a husband does not claim maintenance from himself; a man cannot use the Domestic Violence Act).\n"
    "- State a share or fraction only if the statute notes show how to work it out, and then show the working briefly.\n\n"
    "STYLE:\n"
    "- Internally reason as Issue, Rule, Application, Conclusion, but output only the final answer.\n"
    "- About 350-450 words, plain English (Flesch reading ease 55+), short bold headings, numbered steps in order of urgency, simple bullets. No tables. Do not repeat points. Say lawyer or advocate, never solicitor.\n"
    "- Use the client's attached document for the facts of their case. If it is a judgment or statute you may explain it and cite what it says.\n"
)

REVIEW_PROMPT = """You are the reviewing editor for a legal-information answer written for a client in India. Rewrite the DRAFT into the final answer the client will read.

CHECK THE DRAFT AGAINST THESE SOURCES (and nothing else):
{notes}

CLIENT FACTS:
{case_information}

EDIT RULES:
1. Delete or soften every statement of law, procedure, form, court, deadline or number that the notes or the client facts do not support. Never write "as quoted in the material" unless it really is.
2. Never assume a fact the client did not give (for example how long they have been separated). Delete it, or turn it into "if ...".
3. Keep the advice consistent with who the client is. Do not tell a husband to claim maintenance from himself, or a man to use the Domestic Violence Act (it protects women only).
4. Use the provisions as the notes give them. Maintenance runs from the date of the application, never for the time before it; protection and residence orders are not "from filing". The Rajnesh disclosure affidavit applies to maintenance cases only, not to adoption, custody or inheritance.
5. A court decides outcomes: write "may", "is likely to" or "can ask for", not guarantees such as "you will", "clear path", "amounts to" or "no legal basis".
6. Never name a rupee amount for the client to claim.
7. At most 450 words, but keep every distinct step and answer that applies to this client; do not cut the answer down to a summary. No tables. Short bold headings, numbered steps in order of urgency, simple bullets, a one-line bottom line. Plain English. Say lawyer or advocate, never solicitor. No disclaimer.
8. Remove advice that does not fit this client: defences to accusations nobody has made, documents for proceedings they are not in, and "you do not need ..." remarks about laws that do not apply. Check any share or fraction against the worked example in the notes.
9. Keep the language of the DRAFT.

DRAFT:
{draft}

Return ONLY the final answer."""

# Max tokens count against Groq's per-minute budget when the request is admitted
# (prompt + max_tokens), so these are sized to leave room under 7-8k.
DRAFT_MAX_TOKENS = 2200
REVIEW_MAX_TOKENS = 1500


def _require_substantial(text: str) -> None:
    """A draft that is a stub, or the model narrating its task, makes the chain try the next model."""
    if len(text.strip()) < 200:
        raise ValueError("reply too short")
    if looks_like_reasoning(text):
        raise ValueError("reply is the model's reasoning, not an answer")


def _require_sane_review(text: str, draft_words: int) -> None:
    """The review should tighten the draft; one that is far longer has gone off the rails."""
    _require_substantial(text)
    words = len(text.split())
    if words > 750 or words > draft_words * 1.4 + 60:
        raise ValueError(f"review grew from {draft_words} to {words} words")
    # tightening is fine; collapsing a full draft into a few sentences loses the client's answer
    if draft_words >= 250 and words < max(150, draft_words * 0.4):
        raise ValueError(f"review shrank from {draft_words} to {words} words")


def polish_answer(text: str) -> str:
    """Final cleanup that does not depend on the model behaving."""
    text = re.sub(r"\bRajneesh\b", "Rajnesh", text)
    text = re.sub(r"\bsolicitors\b", "lawyers", text)
    text = re.sub(r"\bSolicitors\b", "Lawyers", text)
    text = re.sub(r"\bsolicitor\b", "lawyer", text)
    text = re.sub(r"\bSolicitor\b", "Lawyer", text)
    # an answer cut off mid-heading or mid-bullet ends in bare markup: drop it
    lines = text.rstrip().split("\n")
    while lines and re.fullmatch(r"[\s*\-•#_>|]*", lines[-1]):
        lines.pop()
    text = "\n".join(lines).strip()
    if text.count("**") % 2 == 1:
        text = text[: text.rfind("**")].rstrip()
    return text


def format_context(retrieved_chunks: list) -> str:
    """Format retrieved chunks efficiently.

    Each entry is the FULL original Q&A item (query + all expert responses),
    not an isolated fragment — retrieval expands matches back to their
    complete parent context so nothing needs to be inferred or assumed.
    """
    if not retrieved_chunks:
        return "No relevant precedents found."

    context_parts = [
        "RELEVANT LEGAL CONTEXT (each item below is the complete original case/answer — "
        "treat anything not stated here as unknown, do not fill it in yourself):\n"
    ]

    for i, chunk in enumerate(retrieved_chunks[:4], 1):
        group = chunk.get("retrieval_group", "legal_context").replace("_", " ").title()
        context_parts.append(f"\n[{group} {i}] ({chunk.get('score', 0):.0%} relevance)")
        context_parts.append(f"Title: {chunk.get('metadata', {}).get('title', 'Precedent')}")
        content = chunk.get('content', '')[:700]
        context_parts.append(f"Content: {content}")
        context_parts.append("")

    return "\n".join(context_parts)


def format_case_info(info_collected: Dict, user_intent: str) -> str:
    """Format collected case information."""
    if not info_collected:
        return "Limited case information available."
    
    case_summary = [f"CASE: {user_intent.upper()}\n"]
    case_summary.append("CLIENT INFORMATION:")
    
    for key, value in info_collected.items():
        case_summary.append(f"• {key.replace('_', ' ').title()}: {value}")
    
    return "\n".join(case_summary)


def generate_response(state: FamilyLawState) -> Dict:
    """
    Generate ONLY the legal advice response.
    
    Reasoning analysis happens in a separate node (analyze_reasoning).
    This ensures complete separation and no contamination.
    """
    query = state["query"]
    retrieved_chunks = state.get("retrieved_chunks", [])
    messages = state.get("messages", [])
    info_collected = state.get("info_collected", {})
    user_intent = state.get("user_intent", "legal advice")
    gender = state.get("user_gender", "unknown")
    name = state.get("name", "Client")

    # ── Language-aware response ─────────────────────────────────────────────
    # Prefer the detected_language already stored in state (set by query_analyzer)
    # so we don't re-run detection on every call.
    detected_lang = state.get("detected_language") or detect_language(query)
    lang_instruction = build_language_instruction(detected_lang)
    if lang_instruction:
        logger.info(f"🌐 Responding in language: {get_language_name(detected_lang)} ({detected_lang})")
    
    logger.info("🤖 === GENERATING LEGAL RESPONSE (CLEAN) ===")
    
    # Validate we have information
    if not retrieved_chunks:
        logger.warning("No retrieved chunks available for generation")
        return {
            "response": "I apologize, but I couldn't find sufficient relevant information in the legal database to provide comprehensive advice for your specific situation. Please consider consulting with a family law attorney directly for personalized guidance.",
            "messages": messages
        }
    
    # Format context and case information
    legal_context = format_context(retrieved_chunks)
    case_information = format_case_info(info_collected, user_intent)
    if state.get("query_type") == "general_question":
        case_information += (
            "\n\nTHIS IS A GENERAL LEGAL QUESTION, NOT THE CLIENT'S OWN CASE. Explain the law and compare the "
            "options asked about. Do not give a to-do list, do not tell the client to file or gather anything, "
            "and do not discuss remedies they did not ask about."
        )
    document = (state.get("document_context") or "").strip()
    if document:
        # A notice or petition gives the facts of the client's case; a judgment
        # or statute is also law the answer may explain and cite.
        case_information += (
            "\n\nCLIENT'S ATTACHED DOCUMENT (excerpt). If it is a notice, petition or letter about the "
            "client's case, use it for the facts. If it is a judgment or statute, you may explain it and "
            f"cite the provisions it contains:\n{document[:8000]}"
        )

    # Only the statute notes this case touches (the full set is ~2,200 tokens)
    notes = select_notes(" ".join([
        query,
        state.get("root_query") or "",
        user_intent or "",
        " ".join(str(v) for v in info_collected.values()),
    ]))

    # Build conversation — inject language instruction into system prompt
    system_content = SYSTEM_PROMPT + "\n" + notes + lang_instruction
    conversation = [SystemMessage(content=system_content)]
    
    if messages:
        conversation.extend(messages[-4:])
    
    # Construct prompt — also append language reminder in the user-facing block
    prompt = f"""Provide complete legal advice (experienced lawyer) based on the case information and precedents below.

{case_information}

Legal Context:
{legal_context}

CLIENT NAME: {name}
CLIENT GENDER: {gender}
CLIENT QUERY: {query}
{lang_instruction}

Write the answer by the rules in your instructions: only facts the client gave, only law from the Legal Context and the statute notes, no rupee amounts to claim, no tables, about 350-450 words.

YOUR RESPONSE:"""
    
    conversation.append(HumanMessage(content=prompt))
    
    try:
        # 1. Draft
        response = invoke_llm(conversation, purpose="main", max_tokens=DRAFT_MAX_TOKENS, temperature=0.2, deadline=90, budget=150,
                              validate=_require_substantial)
        response_content = polish_answer(strip_think(response.content))

        finish_reason = (getattr(response, "response_metadata", None) or {}).get("finish_reason")
        if finish_reason == "length":
            logger.warning("⚠️ Draft hit the token limit; trimming to the last complete sentence")
            response_content = polish_answer(trim_to_last_sentence(response_content))

        # 2. Review: a second pass checks the draft against the facts, notes and context.
        #    It runs on a different Groq model (own token budget) and falls back to the draft.
        if settings.answer_review and len(response_content) > 200:
            try:
                review_prompt = REVIEW_PROMPT.format(
                    notes=notes,
                    case_information=case_information,
                    draft=response_content,
                )
                reviewed = invoke_llm(
                    [SystemMessage(content="You are a careful legal editor. Output only the corrected answer." + lang_instruction),
                     HumanMessage(content=review_prompt)],
                    purpose="review", max_tokens=REVIEW_MAX_TOKENS, temperature=0.1, deadline=40, budget=50,
                    validate=lambda t: _require_sane_review(t, len(response_content.split())),
                )
                reviewed_finish = (getattr(reviewed, "response_metadata", None) or {}).get("finish_reason")
                reviewed_text = polish_answer(strip_think(reviewed.content))
                if reviewed_finish == "length":
                    logger.warning("⚠️ Review hit the token limit; keeping the draft")
                else:
                    logger.info(f"✏️ Review pass: {len(response_content.split())} -> {len(reviewed_text.split())} words")
                    response_content = reviewed_text
            except Exception as review_exc:
                logger.warning(f"⚠️ Review pass skipped ({type(review_exc).__name__}: {str(review_exc)[:120]}); using the draft")

        # 3. Citation guard. Citations quoted from the client's attached document are grounded too.
        guard_context = f"{legal_context}\n\n{notes}"
        if document:
            guard_context += f"\n\n{document[:8000]}"
        guard = sanitize_citations(
            response_content, guard_context, detected_lang, settings.citation_guard_mode,
            source_citations=[c.get("metadata", {}).get("citations") for c in retrieved_chunks],
        )
        response_content = polish_answer(guard.text)
        if guard.removed:
            logger.warning(f"⚠️ Citation guard removed sentences citing: {guard.removed}")
        if guard.flagged:
            logger.warning(f"⚠️ Citation guard flagged as unverified: {guard.flagged}")

        if len(response_content.strip()) < 60:
            logger.warning("⚠️ Response too short after think stripping, synthesizing legal advice...")
            raise ValueError("Response too short")
        logger.info(f"✅ Generated response: {len(response_content)} characters")
        
        # Add disclaimer if not present
        if "not a substitute for legal advice" not in response_content.lower():
            response_content += "\n\n---\n**Disclaimer**: This information is for educational purposes only and does not constitute legal advice. Please consult with a qualified family law attorney for personalized legal guidance."
        
        # Return ONLY the response (reasoning happens in separate node)
        return {
            "response": response_content,
            # Only the answer joins the persistent history. Returning the whole
            # `conversation` appended this turn's SystemMessage and the huge
            # context prompt to state, and every later turn re-sent them.
            "messages": [AIMessage(content=response_content)]
        }
    
    except Exception as e:
        logger.warning(f"⚠️ Remote LLM endpoint unavailable ({e}), seeking legal synthesis...")
        core_answer = None
        try:
            import httpx
            with httpx.Client(timeout=8.0) as client:
                resp = client.post("http://localhost:8000/api/query", json={"question": query})
                if resp.status_code == 200:
                    d = resp.json()
                    ans = d.get("response", {}).get("answer") or d.get("answer")
                    if ans and len(ans.strip()) > 50:
                        core_answer = ans.strip()
        except Exception as net_err:
            logger.info(f"Local core fallback check: {net_err}")

        if core_answer:
            return {
                "response": core_answer,
                "messages": [AIMessage(content=core_answer)]
            }
        statute_titles = []
        case_titles = []
        citations_found = set()
        for c in retrieved_chunks:
            meta = c.get("metadata", {})
            title = meta.get("title", "")
            cat = meta.get("category", "")
            cits = meta.get("citations") or []
            if isinstance(cits, str):
                cits = [cits]
            for cit in cits:
                if cit:
                    citations_found.add(str(cit))
            if "2" in str(cat) or "act" in title.lower() or "section" in title.lower():
                if title and title not in statute_titles:
                    statute_titles.append(title)
            else:
                if title and title not in case_titles:
                    case_titles.append(title)

        logger.error("⚠️ Generation FALLBACK: both LLMs failed; returning a template built from retrieved titles")
        synthesis_lines = [
            "> ⚠️ The AI model could not be reached, so this is an automatic summary of the retrieved "
            "sources, not advice tailored to your facts. Please try again in a moment.",
            "",
            f"### Indian Family Law Assessment & Statutory Analysis",
            f"Based on your query regarding **{user_intent or query}**, the relevant statutory framework and judicial authorities indicate:",
            "",
        ]
        if statute_titles:
            synthesis_lines.append("#### Applicable Statutory Framework:")
            for s in statute_titles[:4]:
                synthesis_lines.append(f"- **{s}**")
            synthesis_lines.append("")

        if case_titles:
            synthesis_lines.append("#### Relevant Precedents & Legal Authorities:")
            for p in case_titles[:4]:
                synthesis_lines.append(f"- **{p}**")
            synthesis_lines.append("")

        if citations_found:
            synthesis_lines.append("#### Key Legal Provisions & References:")
            for cit in list(citations_found)[:5]:
                synthesis_lines.append(f"- {cit}")
            synthesis_lines.append("")

        synthesis_lines.extend([
            "#### Practical Legal Guidance:",
            "1. **Documentation & Evidence**: Gather all official documentation including marriage registration, proof of residence, correspondence, and financial statements.",
            "2. **Interim Relief & Maintenance**: If maintenance is sought, applications can be preferred under Section 125 CrPC or Section 24/25 of the Hindu Marriage Act, 1955, irrespective of pending matrimonial disputes.",
            "3. **Jurisdiction & Filing**: Petitions should be instituted before the Family Court having territorial jurisdiction over the matrimonial home or where the applicant currently resides.",
            "",
            "---",
            "**Disclaimer**: This information is for educational purposes only and does not constitute formal legal advice. Please consult with an advocate for personalized legal guidance."
        ])
        fallback_content = "\n".join(synthesis_lines)
        return {
            "response": fallback_content,
            "messages": [AIMessage(content=fallback_content)]
        }

# """
# FIXED Generator Node - Absolutely prevents reasoning JSON from appearing in response text.

# The issue: LLM sometimes outputs reasoning JSON after the legal advice.
# The fix: Aggressively clean the response before returning it.
# """

# from langchain_core.messages import HumanMessage, SystemMessage
# from typing import Dict
# from state import FamilyLawState
# import os
# import logging
# import re
# from nodes.reasoning_explainer import (
#     DynamicReasoningExplainer,
#     create_case_summary
# )
# from langchain_openai import ChatOpenAI
import re

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Initialize LLM
# llm = ChatHuggingFace(
#     llm=HuggingFaceEndpoint(
#         repo_id=os.getenv("LLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct"),
#         huggingfacehub_api_token=os.getenv("HUGGINGFACE_API_KEY"),
#         task="conversational",
#         max_new_tokens=2048,
#         temperature=0.7,
#     )
# )

# example_query = (
#     "I got engaged in June 2018 and married in February 2019. Soon after, my husband stopped caring for me and the household, then left. "
#     "He abused me for talking to friends and about my past, which he already knew. Yesterday, he called me to meet, and I hoped we could reconcile. "
#     "Instead, he beat me and stopped me from leaving. I escaped this morning. I want a divorce as soon as possible."
# )

# example_responses = [
#     "First, lodge an FIR under Section 498A for cruelty. Then consult a lawyer to file two cases: one under the Domestic Violence Act, and another for Judicial Separation under Section 10 of the Hindu Marriage Act, since you can't seek divorce before one year of marriage.",
#     "You can file for divorce in family court under the Hindu Marriage Act on grounds of mental and physical cruelty. Also, register an FIR under Sections 498A and 323 IPC.",
#     "Since you married in February 2019, you must wait one year before filing for divorce. Meanwhile, file a police complaint for assault — it will support your case for cruelty. You can also claim maintenance under Section 125 CrPC if he isn't supporting you."
# ]

# SYSTEM_PROMPT = (
#     "You are a senior Indian law analyst. Follow the guidelines strictly. "
#     "Explain legal issues in simple, plain English that anyone can understand. Use a warm, professional tone, and avoid robotic phrasing. "
#     "CRITICAL: Output ONLY the legal advice. DO NOT include any JSON, reasoning steps, or analysis in your response.\n\n"
#     "Guidelines:\n"
#     "- Internally reason as Issue → Rule (statute/precedent) → Application → Conclusion, but only output the detailed final answer.\n"
#     "- Prefer authoritative Indian sources and cite succinctly, e.g., (IPC s.498A), (HMA 1955 s.13), (CrPC s.125).\n"
#     "- If a precise section is uncertain, mention it briefly without guessing.\n"
#     "- Give concise response to ensure a Flesch Reading Ease score of at least 55+.\n"
#     "- Explain legal terms briefly in everyday language when necessary.\n"
#     "- Give practical guidance wherever possible, focusing on what a person can realistically do.\n"
#     "- END your response after the legal advice. DO NOT add reasoning, JSON, or analysis.\n\n"
#     f"Style Example (tone only, not ground truth):\n"
#     f"Query:\n{example_query}\n\n"
#     "Example Responses:\n"
#     f"1. {example_responses[0]}\n"
#     f"2. {example_responses[1]}\n"
#     f"3. {example_responses[2]}\n"
# )


# def format_context(retrieved_chunks: list) -> str:
#     """Format retrieved chunks efficiently."""
#     if not retrieved_chunks:
#         return "No relevant precedents found."
    
#     context_parts = ["RELEVANT LEGAL PRECEDENTS:\n"]
    
#     for i, chunk in enumerate(retrieved_chunks[:5], 1):
#         context_parts.append(f"\n[Precedent {i}] ({chunk['score']:.0%} relevance)")
#         context_parts.append(f"Title: {chunk['metadata']['title']}")
#         context_parts.append(f"Category: {chunk['metadata']['category']}")
#         content = chunk['content']
#         context_parts.append(f"Content: {content}")
#         context_parts.append("")
    
#     return "\n".join(context_parts)


# def format_case_info(info_collected: Dict, user_intent: str) -> str:
#     """Format collected case information."""
#     if not info_collected:
#         return "Limited case information available."
    
#     case_summary = [f"CASE: {user_intent.upper()}\n"]
#     case_summary.append("CLIENT INFORMATION:")
    
#     for key, value in info_collected.items():
#         case_summary.append(f"• {key.replace('_', ' ').title()}: {value}")
    
#     return "\n".join(case_summary)


# def aggressive_clean_response(response_content: str) -> str:
#     """
#     AGGRESSIVELY clean response to remove ANY JSON, reasoning, or appended content.
    
#     This is the key fix - we remove everything after the legal advice ends.
#     """
    
#     # Step 1: Find where JSON starts (if any)
#     json_markers = [
#         '{',  # Any JSON object start
#         '"reasoning_steps"',
#         '"usage_score"',
#         '"matching_factors"',
#         '"step_number"',
#         '"precedent_title"',
#         'REASONING CHAIN',
#         'PRECEDENT ANALYSIS',
#         'Here is the',
#         '```json'
#     ]
    
#     # Find the earliest marker
#     earliest_json_pos = len(response_content)
#     found_marker = None
    
#     for marker in json_markers:
#         pos = response_content.find(marker)
#         if pos != -1 and pos < earliest_json_pos:
#             # But make sure it's not in the legal advice itself
#             # Legal advice might mention "Section {X}" etc.
#             # So we only cut if it's a standalone JSON pattern
#             if marker == '{':
#                 # Check if it's a JSON object (not just a section reference)
#                 snippet = response_content[pos:pos+200]
#                 if any(x in snippet for x in ['"reasoning', '"usage', '"step', '"precedent']):
#                     earliest_json_pos = pos
#                     found_marker = marker
#             else:
#                 earliest_json_pos = pos
#                 found_marker = marker
    
#     if found_marker:
#         response_content = response_content[:earliest_json_pos].strip()
#         logger.warning(f"⚠️ Cut response at marker '{found_marker}' (position {earliest_json_pos})")
    
#     # Step 2: Remove common mistaken additions
#     unwanted_patterns = [
#         r'\{[\s\S]*"reasoning_steps"[\s\S]*\}',  # Any JSON with reasoning_steps
#         r'\{[\s\S]*"usage_score"[\s\S]*\}',      # Any JSON with usage_score
#         r'```json[\s\S]*```',                     # JSON code blocks
#         r'Here is the generated reasoning[\s\S]*',
#         r'Here is my analysis[\s\S]*',
#     ]
    
#     for pattern in unwanted_patterns:
#         match = re.search(pattern, response_content, re.IGNORECASE)
#         if match:
#             response_content = response_content[:match.start()].strip()
#             logger.warning(f"⚠️ Removed pattern: {pattern[:50]}...")
    
#     # Step 3: Ensure we end on a complete sentence
#     # Find the last period before any suspicious content
#     sentences = response_content.split('.')
#     clean_sentences = []
    
#     for sentence in sentences:
#         # Stop if we see JSON-like content
#         if any(marker in sentence for marker in ['{', '"reasoning', '"usage', '"step']):
#             break
#         clean_sentences.append(sentence)
    
#     if clean_sentences:
#         response_content = '.'.join(clean_sentences)
#         if not response_content.endswith('.'):
#             response_content += '.'
    
#     # Step 4: Remove trailing whitespace and ensure proper ending
#     response_content = response_content.strip()
    
#     # Step 5: Final sanity check - if response is too short, something went wrong
#     if len(response_content) < 200:
#         logger.error("❌ Response seems too short after cleaning. Might have cut too much.")
    
#     logger.info(f"✅ Cleaned response: {len(response_content)} characters")
    
#     return response_content


# def generate_response(state: FamilyLawState) -> Dict:
#     """
#     Generate legal advice with GUARANTEED clean response (no appended JSON).
    
#     Key fix: Aggressive cleaning of response before returning.
#     """
#     query = state["query"]
#     retrieved_chunks = state.get("retrieved_chunks", [])
#     messages = state.get("messages", [])
#     info_collected = state.get("info_collected", {})
#     user_intent = state.get("user_intent", "legal advice")
#     include_reasoning = state.get("include_reasoning", True)
#     gender = state.get("user_gender", "unknown")
    
#     # Validate we have information
#     if not retrieved_chunks:
#         logger.warning("No retrieved chunks available for generation")
#         return {
#             "response": "I apologize, but I couldn't find sufficient relevant information in the legal database to provide comprehensive advice for your specific situation. Please consider consulting with a family law attorney directly for personalized guidance.",
#             "messages": messages,
#             "reasoning_steps": [],
#             "precedent_explanations": []
#         }
    
#     # Format context and case information
#     legal_context = format_context(retrieved_chunks)
#     case_information = format_case_info(info_collected, user_intent)
    
#     # Build conversation
#     conversation = [SystemMessage(content=SYSTEM_PROMPT)]
    
#     if messages:
#         conversation.extend(messages[-4:])
    
#     # Construct prompt - emphasize to STOP after advice
#     prompt = f"""Provide complete legal advice (experienced lawyer) based on the case information and precedents below.

# {case_information}

# Legal Context:
# {legal_context}

# CLIENT GENDER: {gender}
# CLIENT QUERY: {query}

# Provide a COMPLETE, well-structured response with:
# - Internally reason as Issue → Rule (statute/precedent) → Application → Conclusion, but only output the detailed final answer.
# - Prefer authoritative Indian sources and cite succinctly, e.g., (IPC s.498A), (HMA 1955 s.13), (CrPC s.125).
# - If a precise section is uncertain, mention it briefly without guessing.
# - Give concise response to ensure a Flesch Reading Ease score of at least 55+.
# - Explain legal terms briefly in everyday language when necessary.
# - Give practical guidance wherever possible, focusing on what a person can realistically do.
# - Cite relevant legal provisions and precedents appropriately from the necessary legal context.

# Use empathetic, professional, simple language. Be thorough - this is important for the client's case.

# IMPORTANT: Output ONLY the legal advice. Do NOT include reasoning steps, JSON objects, or analysis after your advice. STOP after giving recommendations.

# YOUR COMPLETE RESPONSE:"""
    
#     conversation.append(HumanMessage(content=prompt))
    
#     try:
#         logger.info("🤖 Generating legal response...")
        
#         # Generate main response
#         response = llm.invoke(conversation)
#         response_content = response.content
        
#         logger.info(f"📝 Raw response length: {len(response_content)} characters")
        
#         # CRITICAL: Aggressively clean response
#         response_content = aggressive_clean_response(response_content)
        
#         logger.info(f"✅ Cleaned response: {len(response_content)} characters")
        
#         # Initialize for reasoning
#         reasoning_steps_dict = []
#         precedent_explanations = []
        
#         # Generate dynamic reasoning if requested
#         # This happens AFTER cleaning, so it can't contaminate the response
#         if include_reasoning:
#             try:
#                 logger.info("🧠 Generating dynamic reasoning analysis...")
                
#                 explainer = DynamicReasoningExplainer()
                
#                 # Generate reasoning chain by analyzing the CLEAN response
#                 reasoning_steps = explainer.generate_reasoning_chain(
#                     user_intent=user_intent,
#                     info_collected=info_collected,
#                     response=response_content,  # Use CLEAN response
#                     retrieved_chunks=retrieved_chunks
#                 )
                
#                 # Analyze precedent usage
#                 case_summary = create_case_summary(info_collected, user_intent)
#                 precedent_usages = explainer.generate_all_precedent_explanations(
#                     case_summary=case_summary,
#                     retrieved_chunks=retrieved_chunks,
#                     response=response_content  # Use CLEAN response
#                 )
                
#                 # Convert to dict format for serialization
#                 reasoning_steps_dict = [
#                     {
#                         "step_number": step.step_number,
#                         "step_type": step.step_type,
#                         "title": step.title,
#                         "explanation": step.explanation,
#                         "confidence": step.confidence,
#                         "supporting_sources": step.supporting_sources,
#                         "legal_provisions": step.legal_provisions,
#                         "response_excerpt": step.response_excerpt
#                     }
#                     for step in reasoning_steps
#                 ]
                
#                 precedent_explanations = [
#                     {
#                         "precedent_title": usage.precedent_title,
#                         "precedent_index": usage.precedent_index,
#                         "retrieval_score": usage.retrieval_score,
#                         "usage_score": usage.usage_score,
#                         "similarity_score": usage.retrieval_score,
#                         "matching_factors": usage.matching_factors,
#                         "different_factors": usage.different_factors,
#                         "key_excerpt": usage.key_excerpt,
#                         "relevance_explanation": usage.how_it_influenced_response,
#                         "citation": usage.citation,
#                         "response_sections_influenced": usage.response_sections_influenced
#                     }
#                     for usage in precedent_usages
#                 ]
                
#                 logger.info(f"   ✓ Generated {len(reasoning_steps_dict)} reasoning steps")
#                 logger.info(f"   ✓ Analyzed {len(precedent_explanations)} precedents")
                
#             except Exception as e:
#                 logger.error(f"❌ Failed to generate reasoning: {e}", exc_info=True)
#                 reasoning_steps_dict = []
#                 precedent_explanations = []
        
#         # Add disclaimer if not present
#         if "not a substitute for legal advice" not in response_content.lower():
#             response_content += "\n\n---\n**Disclaimer**: This information is for educational purposes only and does not constitute legal advice. Please consult with a qualified family law attorney for personalized legal guidance."
        
#         # FINAL SANITY CHECK: Ensure no JSON in response
#         if '{' in response_content or '"reasoning' in response_content.lower():
#             logger.error("❌❌❌ CRITICAL: JSON still found in response after cleaning!")
#             logger.error(f"Response tail: ...{response_content[-500:]}")
#             # One more aggressive clean
#             response_content = aggressive_clean_response(response_content)
        
#         # Return clean response with separate reasoning
#         return {
#             "response": response_content,  # GUARANTEED CLEAN
#             "messages": conversation + [response],
#             "reasoning_steps": reasoning_steps_dict,  # SEPARATE
#             "precedent_explanations": precedent_explanations,  # SEPARATE
#         }
    
#     except Exception as e:
#         logger.error(f"❌ Error generating response: {str(e)}", exc_info=True)
#         return {
#             "response": f"I apologize, but I encountered an error while generating advice. Please try rephrasing your question or contact support.",
#             "messages": messages,
#             "reasoning_steps": [],
#             "precedent_explanations": []
#         }
