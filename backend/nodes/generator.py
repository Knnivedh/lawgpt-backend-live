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

from langchain_core.messages import HumanMessage, SystemMessage
from typing import Dict
from state import FamilyLawState
from config import get_settings
import os
import logging
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get configuration from centralized config
settings = get_settings()

logger.info(f"🤖 Generator Configuration:")
logger.info(f"   LLM Model: {settings.llm_model}")
logger.info(f"   Note: Using Indian law-specific model for better legal context")

# Initialize LLM with InLegalLlama or IndianLegalGPT
llm = ChatHuggingFace(
    llm=HuggingFaceEndpoint(
        repo_id=settings.llm_model,
        huggingfacehub_api_token=settings.huggingface_api_key,
        task="conversational",
        max_new_tokens=1024,
        temperature=0.7,
    )
)

example_query = (
    "I got engaged in June 2018 and married in February 2019. Soon after, my husband stopped caring for me and the household, then left. "
    "He abused me for talking to friends and about my past, which he already knew. Yesterday, he called me to meet, and I hoped we could reconcile. "
    "Instead, he beat me and stopped me from leaving. I escaped this morning. I want a divorce as soon as possible."
)

example_responses = [
    "First, lodge an FIR under Section 498A for cruelty. Then consult a lawyer to file two cases: one under the Domestic Violence Act, and another for Judicial Separation under Section 10 of the Hindu Marriage Act, since you can't seek divorce before one year of marriage.",
    "You can file for divorce in family court under the Hindu Marriage Act on grounds of mental and physical cruelty. Also, register an FIR under Sections 498A and 323 IPC.",
    "Since you married in February 2019, you must wait one year before filing for divorce. Meanwhile, file a police complaint for assault — it will support your case for cruelty. You can also claim maintenance under Section 125 CrPC if he isn't supporting you."
]

SYSTEM_PROMPT = (
    "You are a senior Indian law analyst. Follow the guidelines strictly. "
    "Explain legal issues in simple, plain English that anyone can understand. Use a warm, professional tone, and avoid robotic phrasing.\n\n"
    "GROUNDING RULES (most important — follow before anything else):\n"
    "- Base every factual claim, statute name, section number, and case outcome ONLY on what appears in the RELEVANT LEGAL CONTEXT provided to you.\n"
    "- Do NOT invent, guess, or assume a section number, act, or legal fact that is not explicitly present in the given context.\n"
    "- If the context does not clearly cover something the client is asking about, say so plainly (e.g. \"The provided material doesn't specify this — please confirm with a lawyer\") instead of filling the gap yourself.\n"
    "- Never state a specific citation you are not certain is present in the context above.\n\n"
    "Guidelines:\n"
    "- Internally reason as Issue → Rule (statute/precedent) → Application → Conclusion, but only output the detailed final answer.\n"
    "- Prefer authoritative Indian sources and cite succinctly, e.g., (IPC s.498A), (HMA 1955 s.13), (CrPC s.125) — only when that citation is present in the context.\n"
    "- If a precise section is uncertain or absent from context, say so briefly instead of guessing.\n"
    "- Give concise response to ensure a Flesch Reading Ease score of at least 55+.\n"
    "- Explain legal terms briefly in everyday language when necessary.\n"
    "- Give practical guidance wherever possible, focusing on what a person can realistically do.\n\n"
    f"Style Example (tone only, not ground truth):\n"
    f"Query:\n{example_query}\n\n"
    "Example Responses:\n"
    f"1. {example_responses[0]}\n"
    f"2. {example_responses[1]}\n"
    f"3. {example_responses[2]}\n"
)


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

    for i, chunk in enumerate(retrieved_chunks, 1):
        group = chunk.get("retrieval_group", "legal_context").replace("_", " ").title()
        context_parts.append(f"\n[{group} {i}] ({chunk['score']:.0%} relevance)")
        context_parts.append(f"Title: {chunk['metadata']['title']}")
        context_parts.append(f"Category: {chunk['metadata']['category']}")
        content = chunk['content']
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
    
    # Build conversation
    conversation = [SystemMessage(content=SYSTEM_PROMPT)]
    
    if messages:
        conversation.extend(messages[-4:])
    
    # Construct prompt
    prompt = f"""Provide complete legal advice (experienced lawyer) based on the case information and precedents below.

{case_information}

Legal Context:
{legal_context}

CLIENT NAME: {name}
CLIENT GENDER: {gender}
CLIENT QUERY: {query}

Provide a COMPLETE, well-structured response with:
- Internally reason as Issue → Rule (statute/precedent) → Application → Conclusion, but only output the detailed final answer.
- Prefer authoritative Indian sources and cite succinctly, e.g., (IPC s.498A), (HMA 1955 s.13), (CrPC s.125) — but ONLY if that exact citation appears in the Legal Context above.
- If a precise section is uncertain or not present in the Legal Context, say so briefly instead of guessing.
- Give concise response to ensure a Flesch Reading Ease score of at least 55+.
- Explain legal terms briefly in everyday language when necessary.
- Give practical guidance wherever possible, focusing on what a person can realistically do.
- Cite relevant legal provisions and precedents appropriately from the necessary legal context, and only from it.

Use empathetic, professional, simple language. Be thorough - this is important for the client's case. Do not introduce facts, laws, or assumptions that are not grounded in the Legal Context above.

YOUR COMPLETE RESPONSE:"""
    
    conversation.append(HumanMessage(content=prompt))
    
    try:
        # Generate main response
        response = llm.invoke(conversation)
        response_content = response.content.strip()
        
        logger.info(f"✅ Generated response: {len(response_content)} characters")
        
        # Add disclaimer if not present
        if "not a substitute for legal advice" not in response_content.lower():
            response_content += "\n\n---\n**Disclaimer**: This information is for educational purposes only and does not constitute legal advice. Please consult with a qualified family law attorney for personalized legal guidance."
        
        # Return ONLY the response (reasoning happens in separate node)
        return {
            "response": response_content,
            "messages": conversation + [response]
        }
    
    except Exception as e:
        logger.error(f"❌ Error generating response: {str(e)}", exc_info=True)
        return {
            "response": f"I apologize, but I encountered an error while generating advice. Please try rephrasing your question or contact support.",
            "messages": messages
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
# from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

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
