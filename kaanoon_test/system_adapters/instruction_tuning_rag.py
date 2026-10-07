"""
INSTRUCTION-TUNING RAG - Query-Specific Retrieval Instructions
Generates optimized retrieval instructions based on query type
"""

from typing import Dict, List, Any
from enum import Enum

class QueryIntent(Enum):
    """Legal query intent types"""
    DEFINITION = "definition"
    PROCEDURE = "procedure"
    ELIGIBILITY = "eligibility"
    PENALTY = "penalty"
    CASE_LAW = "case_law"
    COMPARATIVE = "comparative"
    HYPOTHETICAL = "hypothetical"
    CALCULATION = "calculation"


class InstructionTuningRAG:
    """
    Generates tailored retrieval and generation instructions
    based on query intent and type
    """
    
    def __init__(self):
        # Query intent patterns
        self.intent_patterns = {
            QueryIntent.DEFINITION: [
                'what is', 'what are', 'define', 'meaning of', 'explain',
                'definition of', 'stands for'
            ],
            QueryIntent.PROCEDURE: [
                'how to', 'procedure', 'process', 'steps to', 'how can',
                'method', 'way to', 'file', 'register', 'apply'
            ],
            QueryIntent.ELIGIBILITY: [
                'eligible', 'qualify', 'who can', 'requirements', 'criteria',
                'applicable to', 'applies to'
            ],
            QueryIntent.PENALTY: [
                'penalty', 'punishment', 'fine', 'consequences', 'liable',
                'imprisonment', 'sentence'
            ],
            QueryIntent.CASE_LAW: [
                'case law', 'precedent', 'judgment', 'ruling', 'held that',
                'supreme court', 'high court'
            ],
            QueryIntent.COMPARATIVE: [
                'difference between', 'compare', 'versus', 'vs', 'distinction',
                'compared to', 'better', 'worse'
            ],
            QueryIntent.HYPOTHETICAL: [
                'if', 'suppose', 'what if', 'assuming', 'scenario',
                'hypothetical', 'example'
            ],
            QueryIntent.CALCULATION: [
                'calculate', 'tax amount', 'how much', 'computation',
                'percentage', 'rate'
            ]
        }
    
    def identify_intent(self, query: str) -> List[QueryIntent]:
        """Identify query intent(s)"""
        query_lower = query.lower()
        identified_intents = []
        
        for intent, patterns in self.intent_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                identified_intents.append(intent)
        
        # Default to definition if no specific intent
        if not identified_intents:
            identified_intents.append(QueryIntent.DEFINITION)
        
        return identified_intents
    
    def generate_retrieval_instruction(
        self,
        query: str,
        intents: List[QueryIntent],
        domains: List[str]
    ) -> str:
        """Generate optimized retrieval instruction"""
        
        instructions = []
        
        # Intent-specific retrieval focus
        if QueryIntent.DEFINITION in intents:
            instructions.append("Focus on statutory definitions and authoritative explanations")
        
        if QueryIntent.PROCEDURE in intents:
            instructions.append("Retrieve step-by-step procedures and practical guides")
        
        if QueryIntent.ELIGIBILITY in intents:
            instructions.append("Find eligibility criteria and qualifying conditions")
        
        if QueryIntent.PENALTY in intents:
            instructions.append("Retrieve penalty provisions and punishment details")
        
        if QueryIntent.CASE_LAW in intents:
            instructions.append("Prioritize Supreme Court and High Court judgments")
        
        if QueryIntent.COMPARATIVE in intents:
            instructions.append("Retrieve contrasting provisions for comparison")
        
        if QueryIntent.HYPOTHETICAL in intents:
            instructions.append("Find similar case examples and precedents")
        
        if QueryIntent.CALCULATION in intents:
            instructions.append("Retrieve tax rates, formulas, and calculation methods")
        
        # Domain-specific instructions
        if 'Criminal Law' in domains or 'IPC' in domains:
            instructions.append("Include IPC sections and criminal procedure references")
        
        if 'Tax Law' in domains or 'GST' in domains:
            instructions.append("Include GST rules, rates, and compliance requirements")
        
        if 'Data Protection' in domains or 'DPDP' in domains:
            instructions.append("Include DPDP Act provisions and data protection guidelines")
        
        # Combine instructions
        if instructions:
            return "RETRIEVAL FOCUS: " + " | ".join(instructions)
        else:
            return "RETRIEVAL FOCUS: Retrieve relevant legal provisions and authoritative sources"
    
    def generate_generation_instruction(
        self,
        query: str,
        intents: List[QueryIntent],
        complexity: str
    ) -> str:
        """Generate optimized answer generation instruction"""
        
        instruction_parts = []
        
        # Base instruction
        instruction_parts.append("Generate a precise legal answer addressing the query directly.")
        
        # Intent-specific generation style
        if QueryIntent.DEFINITION in intents:
            instruction_parts.append(
                "Provide clear definition with statutory reference. "
                "Include key characteristics and scope."
            )
        
        if QueryIntent.PROCEDURE in intents:
            instruction_parts.append(
                "Present as step-by-step procedure with numbered points. "
                "Include timelines and required documents."
            )
        
        if QueryIntent.ELIGIBILITY in intents:
            instruction_parts.append(
                "List eligibility criteria as bullet points. "
                "Specify who qualifies and who doesn't."
            )
        
        if QueryIntent.PENALTY in intents:
            instruction_parts.append(
                "Clearly state penalties with section references. "
                "Distinguish between different violation levels."
            )
        
        if QueryIntent.CASE_LAW in intents:
            instruction_parts.append(
                "Cite relevant case law with case names and citations. "
                "Explain the legal principle established."
            )
        
        if QueryIntent.COMPARATIVE in intents:
            instruction_parts.append(
                "Present comparison in table or side-by-side format. "
                "Highlight key differences clearly."
            )
        
        if QueryIntent.HYPOTHETICAL in intents:
            instruction_parts.append(
                "Apply law to the hypothetical scenario. "
                "Provide likely outcome with reasoning."
            )
        
        if QueryIntent.CALCULATION in intents:
            instruction_parts.append(
                "Show calculation with formula and worked example. "
                "Explain each component clearly."
            )
        
        # Complexity-based adjustments
        if complexity in ['simple', 'ultra_simple']:
            instruction_parts.append("Keep answer concise and straightforward.")
        elif complexity in ['complex', 'very_complex']:
            instruction_parts.append(
                "Provide comprehensive analysis with detailed explanation. "
                "Cover all aspects and implications."
            )
        
        # Structure requirement
        instruction_parts.append(
            "\n\nSTRUCTURE YOUR ANSWER:\n"
            "1. **Direct Answer** - Clear response to the question\n"
            "2. **Legal Basis** - Relevant sections/provisions\n"
            "3. **Explanation** - Detailed analysis\n"
            "4. **Practical Guidance** - How to proceed (if applicable)"
        )
        
        return "\n".join(instruction_parts)
    
    def generate_prompt_with_instructions(
        self,
        query: str,
        context: str,
        intents: List[QueryIntent],
        domains: List[str],
        complexity: str
    ) -> str:
        """Generate complete prompt with tuned instructions"""
        
        # Get instructions
        retrieval_instruction = self.generate_retrieval_instruction(query, intents, domains)
        generation_instruction = self.generate_generation_instruction(query, intents, complexity)
        
        # Build complete prompt
        prompt = f"""You are an expert Indian legal assistant providing accurate, well-structured answers.

USER QUERY: {query}

{retrieval_instruction}

LEGAL CONTEXT:
{context}

{generation_instruction}

Generate your answer now:"""
        
        return prompt
    
    def get_token_budget(self, intents: List[QueryIntent], complexity: str) -> int:
        """Determine token budget based on intent and complexity"""
        
        base_budget = {
            'ultra_simple': 150,
            'simple': 250,
            'moderate': 400,
            'complex': 600,
            'very_complex': 800
        }.get(complexity, 400)
        
        # Adjust for intent
        if QueryIntent.PROCEDURE in intents:
            base_budget += 150  # Procedures need more tokens
        
        if QueryIntent.COMPARATIVE in intents:
            base_budget += 100  # Comparisons need more space
        
        if QueryIntent.CALCULATION in intents:
            base_budget += 100  # Calculations with examples
        
        return min(base_budget, 1000)  # Cap at 1000 tokens
