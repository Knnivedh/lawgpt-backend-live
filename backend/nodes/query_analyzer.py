"""
Enhanced Query Analyzer Node - Analyzes user queries with intent confidence.

This node identifies:
1. User intent and confidence level (high/medium/low)
2. Case type (divorce, domestic violence, custody, etc.)
3. Information already provided by the user
4. Critical information still needed
"""

from langchain_core.messages import HumanMessage, SystemMessage
from typing import Any, Dict, List

from sympy import use
from state import FamilyLawState
import os
import json
import logging
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

logger = logging.getLogger(__name__)


def normalize_info_needed_list(raw_items: Any) -> List[Dict[str, str]]:
    """Normalize LLM/fallback outputs into [{field, reason}, ...]."""
    if not raw_items:
        return []

    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    normalized = []
    for item in raw_items:
        if isinstance(item, dict):
            field = item.get("field")
            if not field:
                continue
            normalized.append({
                "field": str(field),
                "reason": str(item.get("reason", "")),
            })
        elif isinstance(item, str):
            if item in {"field", "reason"}:
                continue
            normalized.append({"field": item, "reason": ""})

    return normalized


class QueryAnalyzer:
    """
    Analyzes user queries to understand intent, case type, and information needs.
    """
    
    QUERY_ANALYSIS_PROMPT = """You are an expert Indian FAMILY LAW analyst. Analyze the user's query to understand their legal situation.

Your task is to:

1. Identify the PRIMARY legal intent (what they want help with)

2. Assess confidence in understanding their intent (high / medium / low)

3. Extract the information the user HAS PROVIDED
   (such as dates, relationships, incidents, religion for matrimonial matters, court actions, children, financial issues, etc.)

4. Identify ONLY the MOST CRITICAL information STILL NEEDED to answer the query accurately without making assumptions.
   - Ask only for legally relevant and necessary facts.
   - Do NOT ask for PERSONALLY SENSITIVE or PRIVACY invasive information unless absolutely essential to the legal issue.
   - IMPORTANT: Avoid requesting below:
     - residential address
     - phone number
     - email address
     - Aadhaar/PAN/passport numbers
     - bank details
     - workplace details
     - any other personally identifying information
   - Prefer broader non-identifying details where sufficient
     (e.g., city/state instead of exact address, age range instead of DOB).

5. The client's RELIGION is a CRITICAL information if the query relates to marriage, divorce, maintenance, custody, inheritance, domestic violence, dowry.

6. Cross-check whether every field listed under `info_needed` is:
   - legally relevant,
   - strictly necessary,
   - and minimally privacy-invasive.

7. Never request information that is not required for preliminary legal analysis.

RESPONSE FORMAT (Strictly JSON only, no other text):
{{
  "user_intent": "comprehensive description of what user wants to achieve, for whom and why",

  "intent_confidence": "high|medium|low",

  "info_provided": {{
    "detailed_collected_info_key1": "value1",
    "detailed_collected_info_key2": "value2"
  }},

  "info_needed": [
    {{
      "field": "needed_information_field",
      "reason": "why this information is legally necessary or critical to understanding the case"
    }}
  ]
}}

CONFIDENCE GUIDELINES:
- HIGH: Query is clear, specific, contains sufficient context
- MEDIUM: General direction is clear but lacks some important context
- LOW: Vague, ambiguous, greetings, general doubts, or unclear legal objective

RULES:
- If user provides comprehensive details, set "info_needed": []
- If critical information is missing, list only legally necessary information
- Extract dates, religion, relationships, incidents, children details, court proceedings and financial concerns when relevant
- Be specific about fields (e.g., "marriage_date" instead of "details")
- Avoid unnecessary assumptions
- Do not request identity documents or contact information unless legally indispensable
- Every item in "info_needed" must include:
  - "field": detailed_needed_info field name
  - "reason": brief explanation of why the information is critically and legally necessary for this case
- If the query is too vague, set confidence to "low"

USER QUERY:
{query}

ANALYSIS (JSON only):"""

    def __init__(self, huggingface_api_key: str = None):
        """Initialize the QueryAnalyzer with LLM."""
        from config import get_settings
        settings = get_settings()
        
        api_key = huggingface_api_key or settings.huggingface_api_key
        
        self.llm = ChatHuggingFace(
            llm=HuggingFaceEndpoint(
                repo_id=settings.llm_model,
                huggingfacehub_api_token=api_key,
                task="text-generation",
                max_new_tokens=1024,
            )
        )
    
    def analyze_query(self, state: FamilyLawState) -> Dict:
        """
        Analyze the user's query to understand intent and information needs.
        
        Args:
            state: FamilyLawState containing the query
            
        Returns:
            Dict with analysis results
        """
        query = state["query"]
        
        # Prepare prompt
        prompt = self.QUERY_ANALYSIS_PROMPT.format(query=query)
        
        try:
            # Get LLM analysis
            conversation = [
                SystemMessage(content="You are a legal query analyzer. Respond ONLY with valid JSON."),
                HumanMessage(content=prompt)
            ]
            
            logger.info("Invoking LLM for query analysis")
            response = self.llm.invoke(conversation)
            response_text = response.content.strip()
            
            # Extract JSON from response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            analysis = json.loads(response_text)
            
            # Validate and set defaults

            user_intent = analysis.get("user_intent", "")
            intent_confidence = analysis.get("intent_confidence", "medium")
            info_provided = analysis.get("info_provided", {})
            info_needed = normalize_info_needed_list(analysis.get("info_needed", []))
            
            # Determine if we have sufficient info
            has_sufficient_info = len(info_needed) == 0 and len(info_provided) > 0
            
            logger.info(f"Query analysis: intent_confidence={intent_confidence}, "
                       f"user_type={user_intent}, needs={len(info_needed)} items")
            
            return {
                "user_intent": user_intent,
                "intent_confidence": intent_confidence,
                "info_collected": info_provided,
                "info_needed_list": info_needed,
                "has_sufficient_info": has_sufficient_info,
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}\nResponse: {response_text[:200]}")
            return self.fallback_analysis(query)
        
        except Exception as e:
            logger.error(f"Query analysis error: {str(e)}")
            return self.fallback_analysis(query)
    
    def fallback_analysis(self, query: str) -> Dict:
        """
        Fallback keyword-based analysis if LLM fails.
        """
        query_lower = query.lower()
        
        # Determine case type
        if any(word in query_lower for word in ["violence", "abuse", "beat", "assault", "hit", "threat"]):
            case_type = "domestic_violence"
            user_intent = "Seeking help with domestic violence"
        elif any(word in query_lower for word in ["dowry", "dahej", "demand", "harassment"]):
            case_type = "dowry"
            user_intent = "Seeking help with dowry-related issues"
        elif any(word in query_lower for word in ["custody", "children", "child", "visitation"]):
            case_type = "child_custody"
            user_intent = "Seeking help with child custody"
        elif any(word in query_lower for word in ["divorce", "separation", "marriage"]):
            case_type = "divorce"
            user_intent = "Seeking help with divorce/separation"
        elif any(word in query_lower for word in ["maintenance", "alimony", "support"]):
            case_type = "maintenance"
            user_intent = "Seeking help with maintenance/alimony"
        else:
            case_type = "general"
            user_intent = "Seeking family law advice"
        
        # Basic information extraction
        info_provided = {}
        if "married" in query_lower or "marriage" in query_lower:
            info_provided["marriage_mentioned"] = "yes"
        if "child" in query_lower:
            info_provided["children_mentioned"] = "yes"
        
        # Determine confidence and info needs
        word_count = len(query.split())
        if word_count > 50:
            intent_confidence = "high"
            info_needed = []
            has_sufficient_info = True
        elif word_count > 20:
            intent_confidence = "medium"
            info_needed = normalize_info_needed_list(self._get_case_specific_needs(case_type))
            has_sufficient_info = False
        else:
            intent_confidence = "low"
            info_needed = []  # Will trigger clarification
            has_sufficient_info = False
        
        logger.info(f"Fallback analysis: case_type={case_type}, confidence={intent_confidence}")
        
        return {
            "user_intent": user_intent,
            "intent_confidence": intent_confidence,
            "case_type": case_type,
            "info_collected": info_provided,
            "info_needed_list": info_needed,
            "has_sufficient_info": has_sufficient_info
        }
    
    def _get_case_specific_needs(self, case_type: str) -> List[Dict[str, str]]:
        """Get case-specific information needs."""
        needs_map = {
            "divorce": [
                {"field": "marriage_date", "reason": "Marriage date affects limitation and applicable divorce remedies."},
                {"field": "grounds_for_divorce", "reason": "The legal ground determines which divorce provision may apply."},
                {"field": "children_details", "reason": "Children affect custody, visitation, and maintenance advice."},
                {"field": "property_details", "reason": "Property details affect residence and financial relief options."},
            ],
            "domestic_violence": [
                {"field": "current_safety_status", "reason": "Safety risk determines whether urgent protection steps are needed."},
                {"field": "incident_details", "reason": "Incident details help identify relevant Domestic Violence Act reliefs."},
                {"field": "relationship_to_perpetrator", "reason": "The domestic relationship determines coverage under the Act."},
                {"field": "previous_complaints", "reason": "Prior complaints affect immediate legal strategy and evidence."},
            ],
            "child_custody": [
                {"field": "children_ages", "reason": "Children's ages are central to welfare and custody analysis."},
                {"field": "current_custody_arrangement", "reason": "Current care arrangement affects interim custody advice."},
                {"field": "reason_for_custody_change", "reason": "The reason shows whether a custody change may be justified."},
            ],
            "dowry": [
                {"field": "marriage_date", "reason": "Marriage timing helps assess dowry harassment context."},
                {"field": "dowry_demands_details", "reason": "Specific demands are needed to assess dowry-related offences."},
                {"field": "evidence_available", "reason": "Evidence affects complaint and court strategy."},
                {"field": "complaints_filed", "reason": "Existing complaints affect next procedural steps."},
            ],
            "maintenance": [
                {"field": "marriage_duration", "reason": "Marriage duration helps assess maintenance context."},
                {"field": "income_details", "reason": "Income is needed to estimate maintenance rights and exposure."},
                {"field": "dependents", "reason": "Dependents affect financial obligations."},
                {"field": "current_financial_status", "reason": "Current need is central to maintenance advice."},
            ],
            "general": [
                {"field": "detailed_situation", "reason": "More facts are needed to identify the legal issue."},
                {"field": "timeline_of_events", "reason": "Timeline affects urgency, limitation, and available remedies."},
                {"field": "desired_outcome", "reason": "The requested outcome determines the proper legal path."},
            ],
        }
        return needs_map.get(case_type, needs_map["general"])
