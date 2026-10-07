"""
AGENTIC LLM ROUTER - Intelligent Query Routing System
Flow: User Query → LLM Analyzes → Decides if RAG needed → Route accordingly
"""

import json
from typing import Dict, Any, Optional
from openai import OpenAI
import os

class AgenticLLMRouter:
    """LLM-based intelligent router that decides if RAG is needed"""
    
    def __init__(self, client: OpenAI):
        self.client = client
        self.model = os.getenv("NVIDIA_MODEL_NAME", "nvidia/llama-3.1-nemotron-70b-instruct")
    
    def analyze_and_route(self, user_query: str) -> Dict[str, Any]:
        """
        Analyze user query and decide routing strategy
        
        Returns:
            {
                'needs_rag': bool,
                'query_type': str,
                'reasoning': str,
                'direct_response': Optional[str],  # If can answer directly
                'rag_params': Optional[Dict]  # Parameters for RAG if needed
            }
        """
        
        routing_prompt = f"""You are an intelligent routing system for a legal AI assistant. Analyze the user's query and determine the best way to respond.

USER QUERY: "{user_query}"

Your task:
1. Determine if this query requires legal document retrieval (RAG) or can be answered directly
2. Classify the query type
3. If RAG is needed, specify what parameters/filters to use

Guidelines:
- NEEDS RAG: Legal questions requiring case law, statutes, precedents, specific legal procedures
- NO RAG: Greetings, general questions, clarifications, simple definitions you know
- PARAMETRIC RAG: Specify what to search for (IPC sections, acts, case names, legal domains)

Respond in JSON format:
{{
    "needs_rag": true/false,
    "query_type": "legal_query|greeting|general|clarification",
    "reasoning": "brief explanation",
    "confidence": 0.0-1.0,
    "direct_response": "response text if no RAG needed, else null",
    "rag_params": {{
        "search_domain": "IPC|GST|DPDP|Contract|Property|Criminal|Civil|Corporate",
        "specific_sections": ["section numbers if mentioned"],
        "case_names": ["case names if mentioned"],
        "keywords": ["important legal terms"],
        "complexity": "simple|medium|complex"
    }}
}}

Examples:

Query: "What is IPC Section 302?"
{{
    "needs_rag": true,
    "query_type": "legal_query",
    "reasoning": "Specific IPC section query requires legal database",
    "confidence": 1.0,
    "direct_response": null,
    "rag_params": {{
        "search_domain": "IPC",
        "specific_sections": ["302"],
        "keywords": ["murder", "punishment"],
        "complexity": "simple"
    }}
}}

Query: "Hi"
{{
    "needs_rag": false,
    "query_type": "greeting",
    "reasoning": "Simple greeting, no legal information needed",
    "confidence": 1.0,
    "direct_response": "Hello! I'm your AI legal assistant. How can I help you with your legal query today?",
    "rag_params": null
}}

Query: "DPDP Act processing of personal data"
{{
    "needs_rag": true,
    "query_type": "legal_query",
    "reasoning": "Complex legal query about data protection act",
    "confidence": 0.95,
    "direct_response": null,
    "rag_params": {{
        "search_domain": "DPDP",
        "specific_sections": [],
        "keywords": ["personal data", "processing", "consent", "DPDP Act 2023"],
        "complexity": "complex"
    }}
}}

Now analyze the user query and provide your routing decision:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": routing_prompt}],
                temperature=0.0,  # Deterministic routing
                max_tokens=400
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            routing_decision = json.loads(response_text)
            return routing_decision
            
        except Exception as e:
            print(f"[ERROR] Routing analysis failed: {e}")
            # Fallback: assume RAG needed for safety
            return {
                'needs_rag': True,
                'query_type': 'legal_query',
                'reasoning': 'Fallback to RAG due to routing error',
                'confidence': 0.5,
                'direct_response': None,
                'rag_params': {
                    'search_domain': 'general',
                    'specific_sections': [],
                    'case_names': [],
                    'keywords': user_query.split()[:5],
                    'complexity': 'medium'
                }
            }
    
    def generate_direct_response(self, user_query: str, context: str = "") -> str:
        """Generate response without RAG for simple queries"""
        
        prompt = f"""You are a helpful legal AI assistant. Answer the user's query directly and concisely.

USER QUERY: {user_query}

{f'CONTEXT: {context}' if context else ''}

Provide a natural, helpful response. Keep it brief and professional."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=200
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[ERROR] Direct response generation failed: {e}")
            return "I'm here to help with legal questions. Please provide more details about your concern."
