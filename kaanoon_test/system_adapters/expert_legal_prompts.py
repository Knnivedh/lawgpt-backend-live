"""
EXPERT LEGAL PROMPTS - Simplified to use focused prompts only
"""

from typing import Dict, List, Optional
from kaanoon_test.system_adapters.focused_legal_prompts import build_focused_legal_prompt

# For backward compatibility - just use focused prompts
def build_expert_legal_prompt(
    question: str,
    context: str,
    query_analysis: Optional[Dict] = None,
    conversation_context: str = ""
) -> str:
    """Build expert legal prompt - delegates to focused system"""
    return build_focused_legal_prompt(question, context, query_analysis, conversation_context)


def build_expert_prompt_for_kaanoon_qa(
    question: str,
    kaanoon_context: str,
    additional_context: str = "",
    query_analysis: Optional[Dict] = None
) -> str:
    """Build Kaanoon QA prompt"""
    combined_context = kaanoon_context + "\n\n" + additional_context
    return build_focused_legal_prompt(question, combined_context, query_analysis)
