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
import re
from lang_utils import detect_language, build_language_instruction, get_language_name
from nodes.query_analyzer import gap_is_known
from config import get_settings
from llm_utils import extract_json, invoke_llm, looks_like_reasoning, strip_think

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
- Client's attached document (excerpt): {document}
- Next information needed: {current_target}
- Why this is needed: {current_reason}

QUESTIONS YOU HAVE ALREADY ASKED (in order):
{asked_questions}

YOUR TASK:
Think about this client's situation, then ask ONE clear, empathetic question to gather: {current_target}

CRITICAL RULES:
1. If client's gender is already known, DO NOT ask about it again
2. Ask ONLY about {current_target}, tied to this client's own story - be specific and direct
3. Be empathetic and professional. Use simple, clear language
4. Reference previously collected information naturally
5. If the client already gave this information anywhere above (including the document), do not ask for it again; ask about what is still unknown
6. Do not repeat, or reword, any question you have already asked. Do not start with the same sympathy phrase as your earlier questions
7. Output ONLY the question, spoken directly to the client ("you"). No notes, no reasoning, no preamble
8. Do not state anything the client has not told you (never assume marital status, children, income, who is at fault). Work out who the client is and who the other people are before you ask
9. Do not state legal rules, conclusions or advice in the question; ask only
10. Never ask for names, exact addresses, phone numbers or ID numbers
11. Ask exactly ONE question: a single sentence ending in a question mark, with no second part ("and also ...") and no list
12. Never treat the other side's acts (a talaq, a notice, a threat, an eviction) as legally valid or effective; describe them neutrally, for example "the talaq messages you received"
13. Do not open with a stock line such as "I'm sorry you're going through this". If you show empathy, tie it to a specific detail the client gave, or just ask
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

    
    # The analyzer finds 5-8 gaps for a personal case; after this many
    # follow-up questions we answer with what we have (FAMILY_MAX_QUESTIONS).
    MAX_FOLLOW_UP_QUESTIONS = get_settings().family_max_questions
    NOT_PROVIDED_TEXT = "Not provided by the client"

    def __init__(self, huggingface_api_key: str = None):
        """Model calls go through llm_utils.invoke_llm (LLM_CHAIN_FAST)."""

    def gather_next_information(self, state: Dict) -> Dict:
        """
        Main logic: record the answer to the last question, then ask the next one.

        The user's reply to a follow-up question is always the `query` of the
        next turn, so `awaiting_answer` + `current_question_target` say exactly
        what it answers. (Counting HumanMessages broke after re-validation: the
        same reply was extracted again as the answer to a brand-new field.)
        """
        query = state["query"]
        root_query = state.get("root_query") or query
        info_collected = dict(state.get("info_collected") or {})
        info_needed_list = normalize_info_needed_list(state.get("info_needed_list", []))
        user_intent = state.get("user_intent") or "legal advice"
        gathering_step = state.get("gathering_step", 0) or 0
        questions_asked = state.get("questions_asked", 0) or 0
        gender = state.get("user_gender") or "unknown"
        name = state.get("name") or "the client"
        current_target = state.get("current_question_target")
        asked_questions = list(state.get("asked_questions") or [])

        logger.info(f"=== Gathering Step {gathering_step} (questions asked: {questions_asked}) ===")
        logger.info(f"Info needed: {[i['field'] for i in info_needed_list]}")
        logger.info(f"Info collected: {list(info_collected.keys())}")

        # STEP 1: this turn's message answers the question asked last turn
        if state.get("awaiting_answer") and current_target:
            last_question = state.get("follow_up_question", "")
            logger.info(f"Extracting answer for: {current_target}")
            extracted = self._extract_information(
                last_question=last_question,
                user_response=query,
                info_target=current_target,
            )
            logger.info(f"Extracted: {extracted}")

            # Keep the client's own words whatever the extraction says: a reply
            # often answers a different question ("My son is 6") and the next
            # question must not ask for it again.
            additional = info_collected.get("additional_info", "")
            info_collected["additional_info"] = f"{additional}\n{query}".strip()

            if extracted and extracted != "NOT_PROVIDED" and not self._is_non_answer(extracted):
                if "gender" in current_target.lower():
                    extracted = self._normalize_gender(extracted)
                    gender = extracted
                info_collected[current_target] = extracted
            else:
                # Record it and move on: asking the same thing again only
                # stalls the consultation, and the generator can say what is unknown.
                info_collected[current_target] = self.NOT_PROVIDED_TEXT
                logger.info(f"No usable answer for {current_target}; marked as not provided")

            # The same reply often answers other open questions too ("No children
            # and no other obligations"); record those so they are not asked again.
            others = [i for i in info_needed_list
                      if i["field"] != current_target and i["field"] not in info_collected]
            if others:
                for field, value in self._extract_other_answers(last_question, query, others).items():
                    info_collected[field] = value
                    logger.info(f"Also answered by this reply: {field}")

        # Drop anything already known (answered, declined, or volunteered earlier)
        labels = state.get("field_labels") or {}
        info_needed_list = [item for item in info_needed_list if not gap_is_known(item, info_collected, labels)]
        if gender != "unknown":
            info_needed_list = [item for item in info_needed_list if item["field"] != "user_gender"]

        done = {
            "needs_more_info": False,
            "info_collected": info_collected,
            "info_needed_list": [],
            "gathering_step": gathering_step,
            "current_question_target": None,
            "awaiting_answer": False,
            "questions_asked": questions_asked,
            "user_gender": gender if gender != "unknown" else None,
        }

        # STEP 2: check if done
        if not info_needed_list:
            logger.info("✓ All information collected!")
            return done
        if questions_asked >= self.MAX_FOLLOW_UP_QUESTIONS:
            logger.info(f"✓ Asked {questions_asked} questions; answering with what we have")
            return done

        # STEP 3: choose and ask the most useful missing fact
        detected_lang = state.get("detected_language") or detect_language(root_query)
        next_item, next_question = self._choose_and_ask(
            name=name,
            gender=gender,
            root_query=root_query,
            user_intent=user_intent,
            info_collected=info_collected,
            remaining=info_needed_list,
            detected_lang=detected_lang,
            document=state.get("document_context") or "",
            asked_questions=asked_questions,
        )
        next_target = next_item["field"]
        logger.info(f"Asking about: {next_target}")
        # Asked item goes first so the extraction on the next turn and the "still to ask" list agree.
        info_needed_list = [next_item] + [i for i in info_needed_list if i["field"] != next_target]

        return {
            "needs_more_info": True,
            "follow_up_question": next_question,
            "info_collected": info_collected,
            "info_needed_list": info_needed_list,
            "gathering_step": gathering_step + 1,
            "current_question_target": next_target,
            "awaiting_answer": True,
            "questions_asked": questions_asked + 1,
            "asked_questions": asked_questions + [next_question],
            "user_gender": gender if gender != "unknown" else None,
        }

    NEXT_QUESTION_PROMPT = """You are a compassionate Indian FAMILY LAW advocate interviewing a client.

SITUATION:
- Client's name: {name}
- Client's message: {root_query}
- Client's gender: {gender}
- Information already collected: {info_collected}
- Client's attached document (excerpt): {document}

STILL UNKNOWN (open items; the id is before the colon):
{open_items}

QUESTIONS YOU HAVE ALREADY ASKED (in order):
{asked_questions}

YOUR TASK:
1. Think like an advocate about THIS client. Of the open items, which ONE would most change your advice if you knew it right now? Choose it; it need not be the first one listed, and it should not be "date of marriage" unless that really decides the remedy.
2. Ask about that one thing in ONE clear, empathetic question.

RULES:
- Output ONLY the JSON below; the question is spoken directly to the client ("you"), with no notes or reasoning.
- Do not state anything the client has not told you (never assume marital status, children, income, who is at fault). Work out who the client is and who the other people are first.
- Do not state legal rules, conclusions or advice; ask only. Never treat the other side's acts (a talaq, a notice, a threat, an eviction) as legally valid; describe them neutrally.
- Never ask for names, exact addresses, phone numbers or ID numbers.
- Ask exactly ONE question: a single sentence ending in a question mark, with no second part ("and also ...") and no list.
- Do not repeat or reword a question you already asked, and do not ask for anything already collected.
- Do not open with a stock phrase ("I'm sorry you're going through this", "To determine...", "To help me understand..."). Tie any empathy to a specific detail the client gave, or just ask.
{lang_instruction}

Reply with ONLY this JSON: {{"field": "<exact id of the open item you chose>", "question": "<your question>"}}"""

    def _choose_and_ask(self, *, name, gender, root_query, user_intent, info_collected, remaining,
                        detected_lang, document, asked_questions):
        """
        Pick the open item that matters most for this client right now and ask about it.

        The analyzer lists the gaps in no particular order, and a fixed list order made
        every case start with the same question. One model call both chooses the gap and
        writes the question; if that fails the first open item is asked the old way.
        """
        first = remaining[0]
        if len(remaining) > 1:
            lang_instruction = build_language_instruction(detected_lang)
            valid = {i["field"] for i in remaining}
            prompt = self.NEXT_QUESTION_PROMPT.format(
                name=name,
                gender=gender,
                root_query=root_query,
                info_collected=self._format_info_collected(info_collected) or "None yet",
                document=document.strip()[:1500] if document and document.strip() else "None",
                open_items="\n".join(
                    f"- {i['field']}: {i.get('label') or i['field'].replace('_', ' ')}"
                    + (f" ({i['reason']})" if i.get("reason") else "")
                    for i in remaining
                ),
                asked_questions="\n".join(f"{n}. {q}" for n, q in enumerate(asked_questions, 1)) or "None yet",
                lang_instruction=lang_instruction,
            )
            try:
                response = invoke_llm(
                    [SystemMessage(content="You are an empathetic attorney. Reply with only the JSON."),
                     HumanMessage(content=prompt)],
                    purpose="fast", max_tokens=700, temperature=0.4, deadline=35,
                    validate=lambda text: self._parse_choice(text, valid),
                )
                field, question = self._parse_choice(strip_think(response.content), valid)
                return next(i for i in remaining if i["field"] == field), question
            except Exception as exc:
                logger.warning(f"Could not choose the next question ({type(exc).__name__}: {str(exc)[:100]}); asking the first open item")

        question = self._generate_question(
            name=name, gender=gender, root_query=root_query, user_intent=user_intent,
            info_collected=info_collected, current_target=first.get("label") or first["field"],
            current_reason=first.get("reason", ""), all_remaining=remaining, detected_lang=detected_lang,
            document=document, asked_questions=asked_questions,
        )
        return first, question

    def _parse_choice(self, text: str, valid_fields):
        """(field, question) from the model's JSON, or ValueError so the chain moves on."""
        data = extract_json(text)
        field = str(data.get("field") or "").strip()
        question = self._clean_question(str(data.get("question") or ""))
        if field not in valid_fields:
            raise ValueError(f"unknown field {field!r}")
        self._check_question(question)
        return field, question
    
    # Models sometimes describe a missing answer instead of returning
    # NOT_PROVIDED ("The client did not confirm their religion ...").
    _NON_ANSWER_RE = re.compile(
        r"\b(?:did not|didn't|does not|doesn't|has not|hasn't|not)\s+"
        r"(?:provide|specify|confirm|mention|answer|state|say|share|give|disclose)\w*"
        r"|\bnot provided\b|\bno (?:relevant )?(?:information|answer|details)\b",
        re.IGNORECASE,
    )

    def _is_non_answer(self, extracted: str) -> bool:
        return bool(self._NON_ANSWER_RE.search(extracted or ""))

    OTHER_ANSWERS_PROMPT = """A family-law lawyer asked a client a question and the client replied.
The lawyer still has these open questions:
{open_items}

QUESTION JUST ASKED: {question}
CLIENT'S REPLY: {reply}

Which of the open questions does the reply ALREADY answer clearly (even though it was not asked)?
Return ONLY JSON: {{"answers": {{"<field id>": "one short sentence stating the answer in the client's own terms"}}}}
Include a field only if the reply states the answer; never guess, and never include a field the reply does not
address. If none, return {{"answers": {{}}}}."""

    def _extract_other_answers(self, question: str, reply: str, open_items: List[Dict[str, str]]) -> Dict[str, str]:
        """Answers the reply gives to open gaps other than the one just asked."""
        listing = "\n".join(
            f"- {i['field']}: {i.get('label') or i['field'].replace('_', ' ')}" for i in open_items
        )
        prompt = self.OTHER_ANSWERS_PROMPT.format(open_items=listing, question=question or "(opening message)", reply=reply)
        try:
            response = invoke_llm(
                [SystemMessage(content="Extract answers. Return only JSON."), HumanMessage(content=prompt)],
                purpose="fast", max_tokens=600, temperature=0.0, deadline=30, validate=extract_json,
            )
            answers = extract_json(response.content).get("answers") or {}
        except Exception as exc:
            logger.warning(f"Could not check the reply against other open questions: {type(exc).__name__}")
            return {}
        valid = {i["field"] for i in open_items}
        return {
            str(f): str(v).strip()
            for f, v in answers.items()
            if f in valid and v and not self._is_non_answer(str(v)) and str(v).strip().upper() != "NOT_PROVIDED"
        }

    # Signs the model wrote notes about the client rather than to them.
    _META_RE = re.compile(
        r"^\s*the client\b|other things the client said|information already collected|"
        r"\bthis information is in\b|\bnext information needed\b",
        re.IGNORECASE,
    )

    @staticmethod
    def _clean_question(text: str) -> str:
        question = (text or "").strip()
        if "YOUR QUESTION:" in question:
            question = question.split("YOUR QUESTION:")[-1].strip()
        return question.strip('"\'').strip()

    def _check_question(self, text: str) -> None:
        question = self._clean_question(text)
        if len(question) < 10 or "?" not in question:
            raise ValueError("no question in reply")
        if self._META_RE.search(question) or looks_like_reasoning(question):
            raise ValueError("reply describes the client or narrates the task instead of asking")
        # One question at a time: a second "?" or a very long reply is several questions in one
        if question.count("?") > 1 or len(question) > 450:
            raise ValueError("more than one question in the reply")

    def _normalize_gender(self, text: str) -> str:
        """Normalize gender responses to consistent values."""
        text_lower = text.lower().strip()
        
        words = set(re.findall(r"[a-z]+", text_lower))
        # Whole words only: "the", "she" and "there" all contain "he".
        if words & {"wife", "woman", "female", "girl", "she", "her", "f"}:
            return "female"
        if words & {"husband", "man", "male", "boy", "he", "him", "m"}:
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
        document: str = "",
        asked_questions: List[str] = (),
    ) -> str:
        """Generate a focused question in the user's language."""

        collected_str = self._format_info_collected(info_collected)
        asked_str = "\n".join(f"{i}. {q}" for i, q in enumerate(asked_questions, 1)) or "None yet"
        document_str = document.strip()[:1500] if document and document.strip() else "None"
        lang_instruction = build_language_instruction(detected_lang)
        if lang_instruction:
            logger.info(f"🌐 Asking follow-up question in: {get_language_name(detected_lang)} ({detected_lang})")
        
        prompt = self.QUESTION_GENERATION_PROMPT.format(
            name=name,
            gender=gender,
            root_query=root_query,
            user_intent=user_intent.replace("_", " ").title(),
            info_collected=collected_str or "None yet",
            # model-written labels are already readable; only prettify raw field ids
            current_target=current_target if " " in current_target else current_target.replace("_", " ").title(),
            current_reason=current_reason,
            document=document_str,
            asked_questions=asked_str,
            lang_instruction=lang_instruction,
        )
        
        try:
            conversation = [
                SystemMessage(content="You are an empathetic attorney. Ask ONE clear question."),
                HumanMessage(content=prompt)
            ]
            
            # A reply that is empty, or the model's notes about the client
            # instead of a question to them, fails validation and the chain
            # moves to the next model.
            response = invoke_llm(conversation, purpose="fast", max_tokens=800, temperature=0.1, deadline=30,
                                  validate=self._check_question)
            return self._clean_question(strip_think(response.content))
        
        except Exception as e:
            logger.error(f"⚠️ Question writer FALLBACK (every model failed): {e}")
            # Last resort only. The target may be a model-written label ("Proof you have of his
            # refusal to pay") or a raw field id, so quote it rather than splice it into a sentence.
            topic = current_target.replace("_", " ").strip().rstrip("?.")
            return f"Could you tell me about this: {topic[:1].lower() + topic[1:]}?"
    
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
            normalized = self._normalize_gender(user_response)
            if normalized in ("female", "male"):
                return normalized
        
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
            
            response = invoke_llm(conversation, purpose="fast", max_tokens=800, temperature=0.1, deadline=30,
                                  validate=extract_json)
            content_clean = strip_think(response.content)
            response_text = content_clean
            
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
            if key != "additional_info":
                formatted.append(f"- {key.replace('_', ' ').title()}: {value}")
        # Replies that didn't answer the question asked often answer a later
        # one ("My son is 6"); show them so that fact isn't asked for again.
        if info_collected.get("additional_info"):
            formatted.append(f"- Other things the client said: {info_collected['additional_info']}")
        return "\n".join(formatted)
