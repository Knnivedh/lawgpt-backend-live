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

from state import FamilyLawState
import os
import json
import logging
import re
from lang_utils import detect_language, build_language_instruction
from llm_utils import extract_json, invoke_llm, strip_think

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
            entry = {
                "field": str(field),
                "reason": str(item.get("reason", "")),
            }
            if item.get("label"):
                entry["label"] = str(item["label"]).strip()
            normalized.append(entry)
        elif isinstance(item, str):
            if item in {"field", "reason"}:
                continue
            normalized.append({"field": item, "reason": ""})

    return normalized


FIRST_PERSON_RE = re.compile(r"\b(?:i|i'm|i’m|i've|i’ve|my|me|mine|we|we're|our)\b", re.IGNORECASE)

_GAP_STOPWORDS = {
    "of", "the", "a", "an", "and", "or", "any", "to", "for", "in", "on", "your", "you", "client", "details",
    "detail", "status", "information", "info", "whether", "has", "have", "is", "are", "if", "about", "current",
}


def _gap_tokens(text: str) -> set:
    words = re.findall(r"[a-z]+", (text or "").lower().replace("_", " "))
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words if w not in _GAP_STOPWORDS}


def gap_is_known(item: Dict[str, str], known_keys, labels: Dict[str, str] = None) -> bool:
    """
    True when a gap repeats something already collected, even under another field name
    ("marriage_date" after "date_of_marriage"). Two gaps are the same when their
    content words overlap by at least two thirds and both have at least two words.
    """
    labels = labels or {}
    candidates = [_gap_tokens(item.get("field")), _gap_tokens(item.get("label"))]
    for key in known_keys:
        if key == item.get("field"):
            return True
        for known in (_gap_tokens(key), _gap_tokens(labels.get(key))):
            if not known:
                continue
            for cand in candidates:
                if len(cand) >= 2 and len(known) >= 2 and len(cand & known) / min(len(cand), len(known)) >= 0.66:
                    return True
    return False


class QueryAnalyzer:
    """
    Analyzes user queries to understand intent, case type, and information needs.
    """
    
    QUERY_ANALYSIS_PROMPT = """You are an expert Indian FAMILY LAW advocate doing intake for a client consultation.
Read the client's message and any attached document together, think about THIS client's situation, and
decide what you still need to know before you can advise them properly.
Respond STRICTLY with one JSON object: no markdown, no explanation.

RESPONSE FORMAT:
{{
  "user_intent": "what the client wants to achieve, for whom and why (1-2 sentences); empty string if unclear",
  "intent_confidence": "high|medium|low",
  "query_type": "general_question|personal_situation|unclear",
  "info_provided": {{
    "snake_case_fact_name": "fact the client already gave (from the message or the document)"
  }},
  "info_needed": [
    {{
      "field": "snake_case_field_name",
      "label": "3-7 word plain-English title of this gap, specific to this client's story",
      "reason": "how this specific fact changes the advice for this client"
    }}
  ],
  "clarification_question": "only when intent_confidence is low: one short, kind question, written for this message, asking what legal problem they need help with; otherwise empty string"
}}

HOW TO CLASSIFY:
- personal_situation: the message is about the client's own family in any way (I, my, me, we, our, their
  spouse, child, in-laws, a case they are in), even when it is phrased as a general question.
- general_question: a purely textbook question with no personal facts ("What does Section 125 CrPC say?").
- unclear: greetings, single words, or messages where the legal problem cannot be identified. Set
  "intent_confidence": "low", "user_intent": "" and write a clarification_question.

{gap_rules}

GENERAL RULES:
- Never list something already stated in the message, the attached document, or KNOWN FACTS.
- If the document and the message disagree, add an item asking the client to resolve it.
- Which personal law governs the family (Hindu, Muslim, Christian, Parsi, Special Marriage Act ...) matters only
  when it is unknown AND it would change the Act, remedy or court. Skip it when the story already makes it
  clear or when the answer would not change the advice (for example enforcing an order that already exists).
- Do not copy any example wording from these instructions; every field name and label must come from this
  client's own situation.
- PRIVACY: never ask for an exact address, phone, email, Aadhaar/PAN/passport numbers, bank details,
  workplace name or other identifying details. City/state is fine when jurisdiction matters.

KNOWN FACTS FROM EARLIER IN THE CONSULTATION:
{known_facts}

QUESTIONS ALREADY ASKED OF THE CLIENT (never list a gap that one of these already covered):
{asked}

ATTACHED DOCUMENT FROM THE CLIENT (may be an excerpt):
{document}

CLIENT MESSAGE:
{query}

JSON:"""

    INTAKE_GAP_RULES = """FINDING THE GAPS (first analysis of a personal_situation):
- Think like an advocate preparing this exact case: which remedy fits, which Act applies, what the court will
  ask, deadlines and limitation, evidence, jurisdiction, money on both sides, children, residence, safety,
  and any proceedings already filed.
- List EVERY missing or unclear fact that could change the advice. Return between {min_q} and {max_q} items,
  most decisive first.
- Each item must come from this client's story and be clearly different from the others. Do not use a
  generic checklist: two different clients should get different items.
- Order the items by what changes THIS client's advice most, not by a standard form. Do not start with
  "date of marriage" or "city" unless that truly decides the remedy for this client.
- general_question: "info_needed": []."""

    REVALIDATE_GAP_RULES = """FINDING THE GAPS (re-check after the interview):
- The client has already answered several questions (see KNOWN FACTS and their own words).
- List only facts that are STILL missing and decisive: at most 3 items, or [] if you can advise now."""

    REVALIDATE_MORE_RULES = """
- Only {asked} questions have been asked so far, and a proper intake covers at least {min_q}. Look again,
  as an advocate preparing this exact case, for up to {more} more facts that are still unknown and would
  change this client's advice (evidence and documents they hold, income or assets, children, earlier
  proceedings, the outcome they want, deadlines). Each must be new, not covered by KNOWN FACTS or the
  questions already asked. Return [] only if nothing decisive really remains."""

    def __init__(self, huggingface_api_key: str = None):
        """Model calls go through llm_utils.invoke_llm (LLM_CHAIN_FAST)."""
        from config import get_settings
        settings = get_settings()
        self.min_questions = settings.family_min_questions
        self.max_questions = settings.family_max_questions

    def analyze_query(self, state: FamilyLawState, mode: str = "intake") -> Dict:
        """
        Analyze the user's query (and attached document) for intent and information gaps.

        Args:
            state: FamilyLawState containing the query (and any info_collected so far)
            mode: "intake" for the first analysis (5-8 case-specific gaps for a
                  personal situation) or "revalidate" after the interview (<= 3).

        Returns:
            Dict with analysis results
        """
        query = state["query"]
        known = state.get("info_collected") or {}
        known_facts = "\n".join(
            f"- {k.replace('_', ' ')}: {v}" for k, v in known.items() if k != "additional_info"
        ) or "None"
        if known.get("additional_info"):
            known_facts += f"\n- client's own words during the interview: {known['additional_info']}"
        document = (state.get("document_context") or "").strip()

        if mode == "revalidate":
            asked_n = state.get("questions_asked", 0) or 0
            if asked_n < self.min_questions and state.get("query_type") != "general_question":
                # A rich answer can fill several gaps at once and end the interview after 3 questions.
                # A family-law intake covers at least min_questions facts, so look harder, and let the
                # model decide whether anything decisive really remains.
                gap_rules = self.REVALIDATE_GAP_RULES + self.REVALIDATE_MORE_RULES.format(
                    asked=asked_n, min_q=self.min_questions, more=self.min_questions - asked_n)
                limit = max(3, self.min_questions - asked_n)
            else:
                gap_rules, limit = self.REVALIDATE_GAP_RULES, 3
        else:
            gap_rules = self.INTAKE_GAP_RULES.format(min_q=self.min_questions, max_q=self.max_questions)
            limit = self.max_questions

        prompt = self.QUERY_ANALYSIS_PROMPT.format(
            gap_rules=gap_rules,
            known_facts=known_facts,
            asked="\n".join(f"- {a}" for a in (state.get("asked_questions") or [])) or "None",
            document=document[:8000] if document else "None",
            query=query,
        )
        response_text = ""

        try:
            conversation = [
                SystemMessage(content="You are a legal intake analyst. Respond ONLY with valid JSON."),
                HumanMessage(content=prompt)
            ]

            logger.info(f"Invoking LLM for query analysis ({mode})")
            response = invoke_llm(conversation, purpose="analyze", max_tokens=1500, temperature=0.3, deadline=35, budget=110,
                                  validate=extract_json)
            response_text = response.content or ""
            analysis = extract_json(response_text)
            # A message in the first person is about the client's own situation, however the
            # model labelled it ("I am a 38-year-old unmarried woman and I want to adopt...").
            if (mode == "intake" and analysis.get("query_type") == "general_question"
                    and FIRST_PERSON_RE.search(query)):
                logger.info("   First-person message labelled general; treating it as a personal situation")
                analysis["query_type"] = "personal_situation"
            info_needed = self._new_gaps(analysis, known, limit, state.get("field_labels"))

            # Intake must surface at least min_questions gaps for a personal case.
            # If the model stopped short, ask it to think again (no canned list).
            if (mode == "intake" and analysis.get("query_type") == "personal_situation"
                    and len(info_needed) < self.min_questions):
                logger.info(f"   Only {len(info_needed)} gaps found; asking the model to look again")
                retry = conversation + [
                    response,
                    HumanMessage(content=(
                        f"You listed {len(info_needed)} gaps. A proper intake for this client needs at least "
                        f"{self.min_questions} distinct facts they have not given yet that could change the advice. "
                        f"Think again about their specific situation and the document, then return the full JSON "
                        f"with between {self.min_questions} and {self.max_questions} items in info_needed."
                    )),
                ]
                try:
                    second = invoke_llm(retry, purpose="analyze", max_tokens=1500, temperature=0.4, deadline=35, budget=70,
                                        validate=extract_json)
                    second_analysis = extract_json(second.content or "")
                    second_needed = self._new_gaps(second_analysis, known, limit, state.get("field_labels"))
                    if len(second_needed) > len(info_needed):
                        analysis, info_needed = second_analysis, second_needed
                except Exception as retry_exc:
                    logger.warning(f"   Second gap pass failed ({type(retry_exc).__name__}); using the first")

            user_intent = (analysis.get("user_intent") or "").strip()
            intent_confidence = (analysis.get("intent_confidence") or "medium").strip().lower()
            info_provided = analysis.get("info_provided") or {}
            if not isinstance(info_provided, dict):
                info_provided = {}

            logger.info(f"Query analysis ({mode}): intent_confidence={intent_confidence}, "
                        f"type={analysis.get('query_type')}, intent={user_intent!r}, "
                        f"needs={[i['field'] for i in info_needed]}")

            detected_lang = detect_language(query)
            logger.info(f"Detected language: {detected_lang!r}")

            return {
                "user_intent": user_intent,
                "intent_confidence": intent_confidence,
                "query_type": analysis.get("query_type"),
                "info_collected": {str(k): str(v) for k, v in info_provided.items()},
                "info_needed_list": info_needed,
                "has_sufficient_info": not info_needed,
                "detected_language": detected_lang,
                "clarification_question": (analysis.get("clarification_question") or "").strip(),
            }

        except json.JSONDecodeError as e:
            logger.error(f"⚠️ Query analysis FALLBACK (unparseable JSON): {e}\nResponse: {strip_think(response_text)[:200]}")
            return self.fallback_analysis(query)

        except Exception as e:
            logger.error(f"⚠️ Query analysis FALLBACK (LLM error): {type(e).__name__}: {e}")
            return self.fallback_analysis(query)
    
    def _new_gaps(self, analysis: Dict, known: Dict, limit: int, labels: Dict[str, str] = None) -> List[Dict[str, str]]:
        """info_needed without anything already known or repeated, capped at `limit`."""
        seen, gaps = set(), []
        for item in normalize_info_needed_list(analysis.get("info_needed", [])):
            if item["field"] in seen or gap_is_known(item, known, labels):
                continue
            seen.add(item["field"])
            gaps.append(item)
        return gaps[:limit]

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
        is_greeting = query_lower.strip() in ["hi", "hello", "hey", "help", "good morning", "good evening", "namaste", "test"]
        if is_greeting:
            intent_confidence = "low"
            info_needed = []
            has_sufficient_info = False
        else:
            intent_confidence = "high"
            # Every model failed, so nothing here is written for this client. A person describing their
            # own situation still gets an interview (topics by case type, worded by the question writer
            # when a model is back) instead of advice on a guess.
            personal = bool(FIRST_PERSON_RE.search(query))
            info_needed = normalize_info_needed_list(self._get_case_specific_needs(case_type)) if personal else []
            info_needed = info_needed[: self.max_questions]
            has_sufficient_info = not info_needed

        logger.info(f"Fallback analysis: case_type={case_type}, confidence={intent_confidence}, "
                    f"topics={[i['field'] for i in info_needed]}")

        return {
            "user_intent": user_intent,
            "intent_confidence": intent_confidence,
            "query_type": "personal_situation" if info_needed else None,
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
