"""
Advanced Reasoning Engine for LAW-GPT
Implements Chain-of-Law reasoning, confidence scoring, and counter-analysis
"""

class AdvancedReasoningEngine:
    """
    Multi-Agent Reasoning System for Legal Analysis
    Provides: IRAC structure, Chain-of-Law, Confidence scoring, Counter-arguments
    """
    
    def __init__(self):
        self.reasoning_steps = []
        self.confidence_factors = {}
    
    def analyze_with_irac(self, issue: str, rule: str, application: str) -> dict:
        """
        IRAC (Issue-Rule-Application-Conclusion) Framework
        Standard legal reasoning structure
        """
        analysis = {
            "issue": issue,
            "rule": rule,
            "application": application,
            "conclusion": self._derive_conclusion(issue, rule, application),
            "confidence": self._calculate_confidence(rule, application)
        }
        
        return analysis
    
    def chain_of_law_reasoning(self, sections: list) -> str:
        """
        Link retrieved sections sequentially to show legal logic flow
        Example: Sec 420 → Sec 467 → Evidence Act 68
        """
        if not sections:
            return ""
        
        chain = []
        for i, section in enumerate(sections):
            if i == 0:
                chain.append(f"**Starting Point:** {section['number']} - {section['title']}")
            else:
                chain.append(f"**Then:** {section['number']} - {section['title']} (builds upon previous)")
        
        chain.append(f"**Conclusion:** These {len(sections)} sections work together to establish liability")
        
        return "\n".join(chain)
    
    def _calculate_confidence(self, rule: str, application: str) -> float:
        """
        Calculate confidence score based on:
        - Specificity of rule
        - Clarity of application
        - Citation strength
        """
        confidence = 0.5  # Base confidence
        
        # Increase if specific sections cited
        if "Section" in rule or "Article" in rule:
            confidence += 0.2
        
        # Increase if case law cited
        if "SCC" in rule or "AIR" in rule:
            confidence += 0.15
        
        # Increase if application is detailed
        if len(application) > 200:
            confidence += 0.1
        
        # Cap at 0.95 (never 100% certain in law)
        return min(confidence, 0.95)
    
    def _derive_conclusion(self, issue: str, rule: str, application: str) -> str:
        """Synthesize conclusion from IRAC components"""
        if "forgery" in issue.lower() and "IPC" in rule:
            return "Hence, criminal liability established under IPC with potential imprisonment"
        elif "partition" in issue.lower() and "Hindu Succession Act" in rule:
            return "Therefore, equal partition rights exist for all Class I heirs"
        else:
            return "Thus, legal remedy available under applicable law"
    
    def generate_counter_argument(self, main_argument: str) -> str:
        """
        Generate opposing viewpoint for balanced analysis
        This helps users understand both sides
        """
        counter = f"**Counter-Perspective:** "
        
        if "criminal liability" in main_argument.lower():
            counter += "Defense may argue lack of mens rea (criminal intent) or prove document genuineness"
        elif "partition" in main_argument.lower():
            counter += "Opponent may claim adverse possession or present alternate evidence of ownership"
        elif "breach" in main_argument.lower():
            counter += "Party may claim force majeure or impossibility of performance as defense"
        else:
            counter += "Alternative interpretation of facts or law may lead to different outcome"
        
        return counter
    
    def extract_procedural_checklist(self, case_type: str) -> list:
        """
        Convert legal analysis into actionable to-do list
        Makes response immediately usable
        """
        checklists = {
            "property_forgery": [
                "☐ File FIR at police station within 48 hours",
                "☐ Send legal notice to accused party",
                "☐ Collect property documents (sale deed, mutation records)",
                "☐ Obtain forensic handwriting analysis report",
                "☐ File partition suit in District Court",
                "☐ Apply for temporary injunction (Order 39 CPC)",
                "☐ Send notice to Registrar to freeze mutation",
                "☐ Gather witness statements from family members",
                "☐ Prepare affidavit proving Class I heirship",
                "☐ Attend court hearings (civil + criminal)"
            ],
            "consumer_complaint": [
                "☐ Gather evidence (bills, warranty, correspondence)",
                "☐ Send legal notice to seller/manufacturer",
                "☐ File complaint on National Consumer Helpline portal",
                "☐ Attach product photos showing defect",
                "☐ Calculate claim amount (product cost + compensation)",
                "☐ Attend Consumer Forum hearing",
                "☐ Present evidence and cross-examine seller",
                "☐ Obtain Consumer Forum order",
                "☐ Execute order if compensation awarded"
            ],
            "divorce": [
                "☐ Attempt reconciliation (mandatory in some cases)",
                "☐ Collect evidence (cruelty/adultery/desertion)",
                "☐ File divorce petition in Family Court",
                "☐ Serve notice on respondent",
                "☐ File maintenance application (if needed)",
                "☐ Attend counseling sessions (court-ordered)",
                "☐ Present evidence in court",
                "☐ Obtain divorce decree",
                "☐ Register divorce with authorities"
            ]
        }
        
        return checklists.get(case_type, ["☐ Consult with legal advisor for specific action plan"])
    
    def format_with_confidence_indicators(self, text: str, confidence: float) -> str:
        """
        Add confidence indicators to output
        Makes AI transparency visible to users
        """
        if confidence >= 0.85:
            indicator = "🟢 **High Confidence** (85%+)"
        elif confidence >= 0.70:
            indicator = "🟡 **Moderate Confidence** (70-85%)"
        else:
            indicator = "🟠 **Lower Confidence** (<70%) - Consult legal expert for verification"
        
        return f"{indicator}\n\n{text}"
    
    def temporal_awareness_note(self) -> str:
        """
        Add temporal context to responses
        Humans rarely remember to mention amendment dates
        """
        from datetime import datetime
        current_date = datetime.now().strftime("%B %Y")
        
        return f"**As of {current_date}:** This analysis is based on current Indian law. Please verify if any recent amendments apply."
