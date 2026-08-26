"""
Fixed Information Gatherer Node - Improved answer extraction and gender handling.

Key fixes:
1. Better answer extraction with multiple attempts
2. Gender persistence across conversation
3. Clearer extraction prompts
"""

from langchain_core.messages import HumanMessage, SystemMessage
from typing import Any, Dict, List
import os
import json
import logging
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from torch import ge
from lang_utils import detect_language, build_language_instruction, get_language_name

logger = logging.getLogger(__name__)


def normalize_info_needed_list(raw_items: Any) -> List[Dict[str, str]]:
    """Accept legacy string items and current dict items in info_needed_list."""
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


class InformationGatherer:
    """
    Gathers information iteratively through targeted questions.
    """

    QUESTION_GENERATION_PROMPT = """You are a compassionate Indian FAMILY LAW attorney conducting a client consultation.

SITUATION:
- Client's Name: {name}
- Client's Query: {root_query}
- Client's Gender: {gender}
- Information already collected: {info_collected}
- Next information needed: {current_target}
- Why this is needed: {current_reason}

YOUR TASK:
Ask ONE clear, empathetic question to gather: {current_target}

CRITICAL RULES:
1. If client's gender is already known, DO NOT ask about it again
2. Ask ONLY about {current_target} that support the case - be specific and direct
3. Be empathetic and professional. Use simple, clear language
4. Reference previously collected information naturally
{lang_instruction}

YOUR QUESTION:"""

#     ANSWER_EXTRACTION_PROMPT = """Extract ONLY the answer to the question from the user's response.

# QUESTION ASKED: {last_question}
# USER'S RESPONSE: {user_response}

# EXTRACTION RULES:
# 1. If the user directly answers the question, extract that answer
# 2. Be concise - extract only the relevant part
# 3. If user says "yes", "no", "I am", single word, etc., extract the actual answer (e.g., "yes" → "female") and generate comprehensive answer based on the question and context
# 4. If user provides no relevant answer, return "NOT_PROVIDED"
# 5. Generate a compact answer based on the user's response and the question asked

# EXAMPLES:
# Q: "Are you the husband or wife in this marriage?"
# Response: "I am the wife" → Extract: "wife"

# Q: "What is your gender?"
# Response: "female" → Extract: "female"

# Q: "When did you get married?"
# Response: "We got married in 2020" → Extract: "2020"

# Response: "I don't remember" → Extract: "NOT_PROVIDED"

# NOW EXTRACT:
# Response (JSON only, no other text):
# {{
#     "extracted_answer": "the comprehensive generated answer based on user response OR NOT_PROVIDED",
# }}"""

    ANSWER_EXTRACTION_PROMPT = """You are extracting structured information from a client interview.

QUESTION ASKED:
{last_question}

USER RESPONSE:
{user_response}

YOUR TASK:
Extract the answer to the question in a SLIGHTLY DESCRIPTIVE way.

EXTRACTION RULES:
1. If the user answers directly, rewrite it as a clear, complete sentence.
2. Preserve important details such as time, place, duration, reasons, or conditions.
3. Do NOT add new facts or assumptions.
4. If the response is very short ("yes", "no", "I am"), expand it using the question context.
5. If the user does not provide relevant information, return "NOT_PROVIDED".

STYLE GUIDELINES:
- 3 - 5 words minimum
- 15–20 words maximum
- Clear and factual
- No legal conclusions
- No advice

EXAMPLES:

Q: "When did you get married?"
Response: "In 2020"
→ "The marriage took place in the year 2020."

Q: "Are you the husband or wife?"
Response: "wife"
→ "The client stated that she is the wife."

Q: "Have you been living separately?"
Response: "Since last year due to constant fights"
→ "The parties have been living separately since last year due to ongoing conflicts."

Q: "What's your income?"
Response: "10 thousand"
→ "The client's monthly income is 10 thousand rupees."(rupees because it's an Indian family law context)

Response (JSON only, no other text):
{{
  "extracted_answer": "the comprehensive generated answer based on user response OR NOT_PROVIDED"
}}
"""

    
    def __init__(self, huggingface_api_key: str = None):
        """Initialize the InformationGatherer with LLM."""
        from config import get_settings
        settings = get_settings()
        
        api_key = huggingface_api_key or settings.huggingface_api_key
        
        self.llm = ChatHuggingFace(
            llm=HuggingFaceEndpoint(
                repo_id=settings.llm_model,
                huggingfacehub_api_token=api_key,
                task="text-generation",
                max_new_tokens=256,
                temperature=0.1,  # Lower temperature for more consistent extraction
            )
        )
    
    def gather_next_information(self, state: Dict) -> Dict:
        """
        Main logic: Extract answer from previous response OR ask next question.
        """
        query = state["query"]
        root_query = state.get("root_query", query)
        messages = state.get("messages", [])
        info_collected = dict(state.get("info_collected", {}))
        info_needed_list = normalize_info_needed_list(state.get("info_needed_list", []))
        if not info_needed_list and state.get("current_question_target"):
            info_needed_list = [{
                "field": state["current_question_target"],
                "reason": "",
            }]
        user_intent = state.get("user_intent", "legal advice")
        gathering_step = state.get("gathering_step", 0)
        gender = state.get("user_gender", "unknown")
        name = state.get("name", "the client")

        logger.info(f"\nUser name:{name}, Gender:{gender}, Intent: {user_intent}\n")
        
        logger.info(f"=== Gathering Step {gathering_step} ===")
        logger.info(f"Info needed: {info_needed_list}")
        logger.info(f"Info collected: {list(info_collected.keys())}")
        
        # STEP 1: Extract answer from previous response if applicable
        if gathering_step > 0 and info_needed_list:
            # current_target = state.get("current_question_target") or info_needed_list[0]
            current_item = info_needed_list[0]

            current_target = (
                state.get("current_question_target")
                or current_item["field"]
            )

            current_reason = current_item.get("reason", "")
            
            # Get user's response
            user_messages = [m for m in messages if m.__class__.__name__ == "HumanMessage"]
            # print(user_messages)
            if len(user_messages) > gathering_step:
                last_user_msg = user_messages[-1]
                print(last_user_msg)
                last_question = state.get("follow_up_question", "")
                
                logger.info(f"Extracting answer for: {current_target}")
                logger.info(f"Question was: {last_question}")
                logger.info(f"User response: {last_user_msg.content[:100]}...")
                
                # Extract the information  
                extracted = self._extract_information(
                    last_question=last_question,
                    user_response=last_user_msg.content,
                    info_target=current_target
                )
                
                logger.info(f"Extracted: {extracted}")
                
                # Store the answer
                if extracted and extracted != "NOT_PROVIDED":
                    # Special handling for gender
                    if current_target == "user_gender":
                        extracted = self._normalize_gender(extracted)
                        info_collected["user_gender"] = extracted
                        state["user_gender"] = extracted
                        logger.info(f"✓ Gender identified and stored: {extracted}")
                    else:
                        info_collected[current_target] = extracted
                        logger.info(f"✓ Stored: {current_target} = {extracted}")
                    
                    # Remove from needed list
                    info_needed_list = [
                        item for item in info_needed_list
                        if item["field"] != current_target
                    ]
                else:
                    # Store in additional_info if not the target answer
                    additional = info_collected.get("additional_info", "")
                    info_collected["additional_info"] = f"{additional}\n{last_user_msg.content}".strip()
                    logger.warning(f"Could not extract {current_target}, stored in additional_info")
        
        # STEP 2: Check if done
        if not info_needed_list:
            logger.info("✓ All information collected!")
            return {
                "needs_more_info": False,
                "info_collected": info_collected,
                "info_needed_list": [],
                "gathering_step": gathering_step,
                "current_question_target": None
            }
        
        # Generate next question
        next_item = info_needed_list[0]

        next_target = next_item["field"]
        next_reason = next_item.get("reason", "")
        print(f"Next target: {next_target}, reason: {next_reason}")
        
        # Skip if gender already collected
        if next_target == "user_gender" and state.get("user_gender") != "unknown":
            logger.info("Gender already known, skipping...")
            info_needed_list = [
                item for item in info_needed_list
                if item["field"] != "user_gender"
            ]
            if not info_needed_list:
                return {
                    "needs_more_info": False,
                    "info_collected": info_collected,
                    "info_needed_list": [],
                    "gathering_step": gathering_step,
                    "current_question_target": None
                }
            next_item = info_needed_list[0]
            next_target = next_item["field"]
            next_reason = next_item.get("reason", "")
        
        logger.info(f"Generating question for: {next_target}")

        # Read language from state (set by query_analyzer)
        detected_lang = state.get("detected_language") or detect_language(root_query)
        
        next_question = self._generate_question(
            name=name,
            gender=gender,
            root_query=root_query,
            user_intent=user_intent,
            info_collected=info_collected,
            current_target=next_target,
            current_reason=next_reason,
            all_remaining=info_needed_list,
            detected_lang=detected_lang,
        )
        
        return {
            "needs_more_info": True,
            "follow_up_question": next_question,
            "info_collected": info_collected,
            "info_needed_list": info_needed_list,
            "gathering_step": gathering_step + 1,
            "current_question_target": next_target
        }
    
    def _normalize_gender(self, text: str) -> str:
        """Normalize gender responses to consistent values."""
        text_lower = text.lower().strip()
        
        # Female indicators
        if any(word in text_lower for word in ["wife", "woman", "female", "girl", "she", "her"]):
            return "female"
        
        # Male indicators
        if any(word in text_lower for word in ["husband", "man", "male", "boy", "he", "him"]):
            return "male"
        
        # Direct answers
        if "f" == text_lower[0]:
            return "female"
        if "m" == text_lower[0]:
            return "male"
        
        return text
    
    def _generate_question(
        self,
        name: str,
        gender: str,
        root_query: str,
        user_intent: str,
        info_collected: Dict,
        current_target: str,
        current_reason: str,
        all_remaining: List[Dict[str, str]],
        detected_lang: str = "en",
    ) -> str:
        """Generate a focused question in the user's language."""
        
        collected_str = self._format_info_collected(info_collected)
        lang_instruction = build_language_instruction(detected_lang)
        if lang_instruction:
            logger.info(f"🌐 Asking follow-up question in: {get_language_name(detected_lang)} ({detected_lang})")
        
        prompt = self.QUESTION_GENERATION_PROMPT.format(
            name=name,
            gender=gender,
            root_query=root_query,
            user_intent=user_intent.replace("_", " ").title(),
            info_collected=collected_str or "None yet",
            current_target=current_target.replace("_", " ").title(),
            current_reason=current_reason,
            lang_instruction=lang_instruction,
        )
        
        try:
            conversation = [
                SystemMessage(content="You are an empathetic attorney. Ask ONE clear question."),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(conversation)
            question = response.content.strip()
            
            # Clean response
            if "YOUR QUESTION:" in question:
                question = question.split("YOUR QUESTION:")[-1].strip()
            question = question.strip('"\'')
            
            return question
        
        except Exception as e:
            logger.error(f"Error generating question: {e}")
            return f"Could you please provide information about your {current_target.replace('_', ' ')}?"
    
    def _extract_information(
        self, 
        last_question: str, 
        user_response: str, 
        info_target: str
    ) -> str:
        """Extract specific information with improved logic."""
        
        # Quick pattern matching for common answers
        user_lower = user_response.lower().strip()
        
        # Gender-specific quick extraction
        if "gender" in info_target.lower():
            if any(word in user_lower for word in ["wife", "woman", "female", "girl", "she"]):
                return "female"
            if any(word in user_lower for word in ["husband", "man", "male", "boy", "he"]):
                return "male"
        
        # Simple yes/no to actual values
        if "yes" in user_lower and len(user_lower) < 10:
            # Extract from question what they're saying yes to
            if "wife" in last_question.lower():
                return "wife"
            if "female" in last_question.lower():
                return "female"
        
        # Use LLM for complex extraction
        prompt = self.ANSWER_EXTRACTION_PROMPT.format(
            last_question=last_question,
            user_response=user_response
        )
        
        try:
            conversation = [
                SystemMessage(content="Extract only the direct answer. Return JSON."),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(conversation)
            response_text = response.content.strip()
            
            # Parse JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            try:
                data = json.loads(response_text)
                extracted = data.get("extracted_answer", "NOT_PROVIDED")
            except:
                # Fallback: look for the pattern
                if '"extracted_answer"' in response_text:
                    import re
                    match = re.search(r'"extracted_answer":\s*"([^"]+)"', response_text)
                    extracted = match.group(1) if match else user_response.strip()
                else:
                    extracted = user_response.strip()
            
            # Normalize if it's a gender answer
            if "gender" in info_target.lower() and extracted != "NOT_PROVIDED":
                extracted = self._normalize_gender(extracted)
            
            return extracted
        
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return user_response.strip()
    
    def _format_info_collected(self, info_collected: Dict) -> str:
        """Format collected information for display."""
        if not info_collected:
            return "No information collected yet."
        
        formatted = []
        for key, value in info_collected.items():
            if key != "additional_info":  # Skip additional_info in display
                formatted.append(f"- {key.replace('_', ' ').title()}: {value}")
        return "\n".join(formatted)
