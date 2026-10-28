"""
Dynamic Reasoning Explainer - Analyzes actual response generation to provide transparent reasoning.

This module uses LLM analysis to:
1. Trace which precedents influenced which parts of the response
2. Explain the reasoning chain that led to the conclusion
3. Score precedent relevance based on actual usage in response
4. Provide transparency for user trust
"""

from typing import List, Dict, Optional, Tuple
import json
import logging
import re
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage
from llm_utils import invoke_llm
import re
from citation_guard import excerpt_in_source
import os

logger = logging.getLogger(__name__)


class ReasoningStep(BaseModel):
    """Single step in the reasoning chain."""
    step_number: int
    step_type: str  # "situation_analysis", "legal_framework", "precedent_application", "conclusion"
    title: str
    explanation: str
    confidence: float  # 0.0 to 1.0
    supporting_sources: List[str]  # Which precedent chunks were used
    legal_provisions: List[str]  # Specific laws/sections mentioned
    response_excerpt: str  # Which part of the response this step produced


class PrecedentUsage(BaseModel):
    """Detailed analysis of how a precedent was used."""
    precedent_title: str
    precedent_index: int  # Index in retrieved_chunks
    retrieval_score: float  # Original similarity score
    usage_score: float  # How much it was actually used (0.0 to 1.0)
    matching_factors: List[str]
    different_factors: List[str]
    key_excerpt: str  # From the precedent
    how_it_influenced_response: str  # Specific explanation
    response_sections_influenced: List[str]  # Which parts of response
    citation: str


class DynamicReasoningExplainer:
    """
    Analyzes the generated response to provide transparent reasoning.
    
    Unlike static reasoning, this actually traces:
    - Which precedents influenced which parts of the response
    - Why certain legal provisions were chosen
    - How the conclusion was reached step by step
    """
    
    # Prompt for analyzing reasoning chain
    REASONING_ANALYSIS_PROMPT = """You are a legal reasoning analyst. Your task is to reverse-engineer the legal reasoning that led to a specific response.

CASE INFORMATION:
{case_info}

RETRIEVED PRECEDENTS:
{precedents_summary}

GENERATED LEGAL ADVICE:
{response}

YOUR TASK:
Analyze the reasoning chain that led to this response. Identify 4 key steps:

1. **SITUATION ANALYSIS**: What key facts were identified and why they matter
2. **LEGAL FRAMEWORK**: Which laws/provisions apply and why
3. **PRECEDENT APPLICATION**: How precedents informed the advice
4. **CONCLUSION**: Final recommendations and reasoning

For each step, provide:
- A clear title
- Detailed explanation
- Confidence level (0.0-1.0)
- Which precedents/sources were used (reference by [Precedent N])
- Which legal provisions were cited
- A brief excerpt from the response that this step produced

OUTPUT FORMAT (JSON):
{{
  "reasoning_steps": [
    {{
      "step_number": 1,
      "step_type": "situation_analysis",
      "title": "Brief title",
      "explanation": "Detailed explanation of this reasoning step",
      "confidence": 0.95,
      "supporting_sources": ["Precedent 1", "Precedent 2"],
      "legal_provisions": ["IPC s.498A", "HMA 1955 s.13"],
      "response_excerpt": "The relevant part of the response this produced"
    }},
    ...
  ]
}}

CRITICAL RULES:
- Reference precedents using [Precedent N] format
- Extract actual legal provisions from the response
- Be specific about which part of response each step produced
- Confidence should reflect certainty of reasoning
- Focus on ACTUAL reasoning, not hypothetical

YOUR ANALYSIS (JSON only):"""

    # Prompt for analyzing precedent usage
    PRECEDENT_USAGE_PROMPT = """Analyze how a specific precedent influenced the legal response.

PRECEDENT INFORMATION:
Title: {precedent_title}
Retrieval Score: {retrieval_score:.0%}
Content: {precedent_content}

CASE SUMMARY:
{case_summary}

GENERATED RESPONSE:
{response}

YOUR TASK:
Analyze HOW MUCH and HOW this precedent actually influenced the response.

Provide:
1. **Usage Score** (0.0-1.0): How heavily was this precedent used?
   - 1.0 = Core precedent, directly shaped response
   - 0.5-0.9 = Important supporting precedent
   - 0.1-0.4 = Minor reference or background
   - 0.0 = Retrieved but not used

2. **Matching Factors**: What similarities between precedent and case made it relevant?

3. **Different Factors**: What differences exist (if any)?

4. **Influence Explanation**: HOW did this precedent shape the response?

5. **Response Sections**: Which specific parts of the response were influenced?

OUTPUT FORMAT (JSON):
{{
  "usage_score": calculated score between 0.0 and 1.0,
  "matching_factors": ["Both cases involve...", "Similar factual pattern of..."],
  "different_factors": ["Different on procedural aspect", "Time period differs"],
  "key_excerpt": "Most relevant quote from the precedent",
  "how_it_influenced_response": "This precedent directly informed the advice on X because...",
  "response_sections_influenced": ["The section on grounds for divorce", "Recommendation to file under Section 13"]
}}

CRITICAL RULES:
- Usage score must reflect ACTUAL usage, not just similarity
- Be specific about which response sections were influenced
- If precedent wasn't used, usage_score should be low (< 0.3)
- Matching factors should be case-specific, not generic

YOUR ANALYSIS (JSON only):"""

    def __init__(self, huggingface_api_key: str = None):
        """Model calls go through llm_utils.invoke_llm (LLM_CHAIN)."""

    def generate_reasoning_chain(
        self,
        user_intent: str,
        info_collected: Dict,
        response: str,
        retrieved_chunks: List[Dict]
    ) -> List[ReasoningStep]:
        """
        Generate dynamic reasoning chain by analyzing the actual response.
        
        This traces backwards from the response to understand the reasoning.
        """
        logger.info("🧠 === GENERATING DYNAMIC REASONING CHAIN ===")
        
        try:
            # Format inputs
            case_info = self._format_case_info(info_collected, user_intent)
            precedents_summary = self._format_precedents_for_analysis(retrieved_chunks)
            
            # Build prompt
            prompt = self.REASONING_ANALYSIS_PROMPT.format(
                case_info=case_info,
                precedents_summary=precedents_summary,
                response=response
            )
            
            # Get analysis
            conversation = [
                SystemMessage(content="You are a legal reasoning analyst. Provide detailed JSON analysis."),
                HumanMessage(content=prompt)
            ]
            
            llm_response = invoke_llm(conversation, purpose="main", max_tokens=1500, temperature=0.2, deadline=60)
            raw_c = re.sub(r'<think>.*?</think>', '', llm_response.content, flags=re.DOTALL).strip()
            response_text = raw_c
            
            # Parse JSON
            reasoning_data = self._extract_json(response_text)
            
            # Convert to ReasoningStep objects
            reasoning_steps = []
            for step_data in reasoning_data.get("reasoning_steps", []):
                step = ReasoningStep(
                    step_number=step_data.get("step_number", 0),
                    step_type=step_data.get("step_type", "analysis"),
                    title=step_data.get("title", ""),
                    explanation=step_data.get("explanation", ""),
                    confidence=float(step_data.get("confidence", 0.8)),
                    supporting_sources=step_data.get("supporting_sources", []),
                    legal_provisions=step_data.get("legal_provisions", []),
                    response_excerpt=step_data.get("response_excerpt", "")
                )
                reasoning_steps.append(step)
            
            logger.info(f"   ✓ Generated {len(reasoning_steps)} dynamic reasoning steps")
            
            return reasoning_steps
            
        except Exception as e:
            logger.error(f"❌ Failed to generate reasoning chain: {e}", exc_info=True)
            return self._fallback_reasoning(response, retrieved_chunks)
    
    def analyze_precedent_usage(
        self,
        precedent: Dict,
        precedent_index: int,
        case_summary: str,
        response: str
    ) -> PrecedentUsage:
        """
        Analyze how a specific precedent influenced the response.
        
        This provides transparency on precedent relevance.
        """
        try:
            metadata = precedent.get('metadata', {})
            content = precedent.get('content', '')
            retrieval_score = precedent.get('score', 0.0)
            
            # Build prompt
            prompt = self.PRECEDENT_USAGE_PROMPT.format(
                precedent_title=metadata.get('title', f'Precedent {precedent_index + 1}'),
                retrieval_score=retrieval_score,
                precedent_content=content[:1000],  # Limit length
                case_summary=case_summary,
                response=response
            )
            
            # Get analysis
            conversation = [
                SystemMessage(content="You are analyzing precedent usage. Provide JSON analysis."),
                HumanMessage(content=prompt)
            ]
            
            llm_response = invoke_llm(conversation, purpose="main", max_tokens=1500, temperature=0.2, deadline=60)
            raw_c = re.sub(r'<think>.*?</think>', '', llm_response.content, flags=re.DOTALL).strip()
            response_text = raw_c
            
            # Parse JSON
            usage_data = self._extract_json(response_text)
            
            # The prompt contains both the precedent and the generated response, so the
            # model sometimes quotes the response. Only trust an excerpt found in the precedent.
            key_excerpt = usage_data.get('key_excerpt', '')
            if not excerpt_in_source(key_excerpt, content):
                key_excerpt = content[:200]

            # Create PrecedentUsage object
            usage = PrecedentUsage(
                precedent_title=metadata.get('title', f'Precedent {precedent_index + 1}'),
                precedent_index=precedent_index,
                retrieval_score=retrieval_score,
                usage_score=float(usage_data.get('usage_score', 0.5)),
                matching_factors=usage_data.get('matching_factors', []),
                different_factors=usage_data.get('different_factors', []),
                key_excerpt=key_excerpt,
                how_it_influenced_response=usage_data.get('how_it_influenced_response', ''),
                response_sections_influenced=usage_data.get('response_sections_influenced', []),
                citation=metadata.get('url', metadata.get('source', ''))
            )
            
            return usage
            
        except Exception as e:
            logger.error(f"❌ Failed to analyze precedent {precedent_index}: {e}")
            return self._fallback_precedent_usage(precedent, precedent_index)
    
    def generate_all_precedent_explanations(
        self,
        case_summary: str,
        retrieved_chunks: List[Dict],
        response: str
    ) -> List[PrecedentUsage]:
        """
        Analyze all precedents to show which were actually used.
        
        Provides full transparency on precedent relevance.
        """
        logger.info("📊 === ANALYZING PRECEDENT USAGE ===")
        
        explanations = []
        
        # Analyze top 2 precedents with LLM, use fallback heuristic for others for fast response
        for i, chunk in enumerate(retrieved_chunks[:5]):
            try:
                if i < 2:
                    usage = self.analyze_precedent_usage(
                        precedent=chunk,
                        precedent_index=i,
                        case_summary=case_summary,
                        response=response
                    )
                else:
                    usage = self._fallback_precedent_usage(chunk, i)
                explanations.append(usage)
                
                logger.info(f"   Precedent {i+1}: "
                          f"retrieval={usage.retrieval_score:.0%}, "
                          f"usage={usage.usage_score:.0%}")
                
            except Exception as e:
                logger.error(f"Failed to analyze precedent {i}: {e}")
                continue
        
        # Sort by usage score (most used first)
        explanations.sort(key=lambda x: x.usage_score, reverse=True)
        
        logger.info(f"   ✓ Analyzed {len(explanations)} precedents")
        
        return explanations
    
    def _format_case_info(self, info_collected: Dict, user_intent: str) -> str:
        """Format case information for analysis."""
        lines = [f"User Intent: {user_intent}", ""]
        
        if info_collected:
            lines.append("Collected Information:")
            for key, value in info_collected.items():
                if key != "additional_info":
                    lines.append(f"  - {key.replace('_', ' ').title()}: {value}")
        else:
            lines.append("Limited case information available.")
        
        return "\n".join(lines)
    
    def _format_precedents_for_analysis(self, retrieved_chunks: List[Dict]) -> str:
        """Format precedents for reasoning analysis."""
        if not retrieved_chunks:
            return "No precedents retrieved."
        
        lines = []
        for i, chunk in enumerate(retrieved_chunks[:5], 1):
            metadata = chunk.get('metadata', {})
            lines.append(f"\n[Precedent {i}] ({chunk.get('score', 0):.0%} similarity)")
            lines.append(f"Title: {metadata.get('title', 'Unknown')}")
            lines.append(f"Content: {chunk.get('content', '')[:300]}...")
        
        return "\n".join(lines)
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from LLM response."""
        # Remove markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        # Parse JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            # Try to find JSON object in text
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise
    
    def _fallback_reasoning(self, response: str, retrieved_chunks: List[Dict]) -> List[ReasoningStep]:
        """Fallback reasoning if LLM analysis fails."""
        logger.warning("Using fallback reasoning generation")
        
        return [
            ReasoningStep(
                step_number=1,
                step_type="situation_analysis",
                title="Case Analysis",
                explanation="Analyzed the client's situation based on provided information.",
                confidence=0.7,
                supporting_sources=["User Input"],
                legal_provisions=[],
                response_excerpt=response[:200] if response else ""
            ),
            ReasoningStep(
                step_number=2,
                step_type="legal_framework",
                title="Legal Framework",
                explanation="Identified applicable Indian family law provisions.",
                confidence=0.8,
                supporting_sources=["Indian Legal Code"],
                legal_provisions=self._extract_legal_refs(response),
                response_excerpt=response[200:400] if len(response) > 200 else ""
            ),
            ReasoningStep(
                step_number=3,
                step_type="precedent_application",
                title="Precedent Analysis",
                explanation=f"Reviewed {len(retrieved_chunks)} relevant precedents.",
                confidence=0.75,
                supporting_sources=[f"Precedent {i+1}" for i in range(min(3, len(retrieved_chunks)))],
                legal_provisions=[],
                response_excerpt=""
            ),
            ReasoningStep(
                step_number=4,
                step_type="conclusion",
                title="Recommendations",
                explanation="Provided actionable legal recommendations based on analysis.",
                confidence=0.85,
                supporting_sources=["Legal Analysis"],
                legal_provisions=[],
                response_excerpt=response[-200:] if len(response) > 200 else response
            )
        ]
    
    def _fallback_precedent_usage(self, precedent: Dict, index: int) -> PrecedentUsage:
        """Fallback precedent analysis if LLM fails."""
        metadata = precedent.get('metadata', {})
        
        return PrecedentUsage(
            precedent_title=metadata.get('title', f'Precedent {index + 1}'),
            precedent_index=index,
            retrieval_score=precedent.get('score', 0.0),
            usage_score=0.5,  # Neutral score
            matching_factors=["Similar family law context"],
            different_factors=["Specific circumstances may vary"],
            key_excerpt=precedent.get('content', '')[:200],
            how_it_influenced_response="Analysis unavailable",
            response_sections_influenced=[],
            citation=metadata.get('url', '')
        )
    
    def _extract_legal_refs(self, text: str) -> List[str]:
        """Extract legal provision references from text."""
        provisions = []
        
        # Common patterns
        patterns = [
            r'Section \d+[A-Z]?',
            r's\.\s?\d+[A-Z]?',
            r'IPC.*?Section \d+',
            r'Hindu Marriage Act.*?Section \d+',
            r'CrPC.*?Section \d+'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            provisions.extend(matches)
        
        return list(set(provisions))[:5]  # Deduplicate and limit


def create_case_summary(info_collected: Dict, user_intent: str) -> str:
    """Create brief case summary for precedent analysis."""
    parts = [user_intent]
    
    if "user_gender" in info_collected:
        parts.append(f"({info_collected['user_gender']} seeking advice)")
    
    for key in ["marriage_duration", "separation_duration", "child_age", "abuse_type"]:
        if key in info_collected:
            parts.append(f"{key.replace('_', ' ')}: {info_collected[key]}")
    
    return " | ".join(parts)