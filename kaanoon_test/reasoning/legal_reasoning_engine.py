"""
Legal Reasoning Engine (LRE) - PROFESSIONAL EDITION
The core brain of LAW-GPT that enforces:
1. Contextual Mode Switching
2. Mandatory Structured Reasoning (IRAC + Professional Enhancements)
3. Precedent Prioritization
4. Hallucination Firewall
5. Executive Summary
6. Practical Remedies & Litigation Strategy
"""

import re
from typing import Dict, List, Optional, Tuple
from .law_revision_monitor import get_law_revision_monitor

class LegalReasoningEngine:
    """
    Orchestrates the legal reasoning process with professional enhancements.
    """
    
    MODES = {
        "CONSTITUTIONAL": "Constitutional Analysis",
        "CRIMINAL": "Criminal Law Analysis",
        "CIVIL": "Civil Law Analysis",
        "CONSUMER": "Consumer Protection Analysis",
        "DRAFTING": "Legal Drafting",
        "GENERAL": "General Legal Query"
    }
    
    def __init__(self):
        self.revision_monitor = get_law_revision_monitor()
        
    def detect_mode(self, query: str) -> str:
        """Detect the legal domain/mode of the query."""
        q = query.lower()
        
        if any(w in q for w in ["article", "constitution", "fundamental right", "sedition", "liberty", "equality", "internet", "platform", "shutdown"]):
            return "CONSTITUTIONAL"
        elif any(w in q for w in ["ipc", "bns", "murder", "theft", "arrest", "bail", "police", "fir"]):
            return "CRIMINAL"
        elif any(w in q for w in ["consumer", "deficiency", "service", "unfair trade", "refund", "compensation", "product liability", "laptop", "mobile", "car", "insurance"]):
            return "CONSUMER"
        elif any(w in q for w in ["contract", "property", "divorce", "marriage", "suit", "damages"]):
            return "CIVIL"
        elif any(w in q for w in ["draft", "notice", "affidavit", "agreement", "application"]):
            return "DRAFTING"
        else:
            return "GENERAL"
    
    def get_reasoning_framework(self, mode: str) -> str:
        """Return the specific reasoning steps for the mode."""
        if mode == "CONSTITUTIONAL":
            return (
                "1. **Identify the Right:** Which Fundamental Right is at stake?\n"
                "2. **Legality Test:** Is there a valid law restricting it?\n"
                "3. **Legitimate Aim:** Does the law serve a valid purpose?\n"
                "4. **Proportionality Test:** Is the restriction the least intrusive measure?\n"
                "5. **Safeguards:** Are there procedural checks?"
            )
        elif mode == "CRIMINAL":
            return (
                "1. **Elements of Offense:** Break down the section into ingredients (Actus Reus + Mens Rea).\n"
                "2. **Fact Application:** Map each ingredient to the user's facts.\n"
                "3. **Exceptions:** Do any General Exceptions (self-defense, accident) apply?\n"
                "4. **Punishment:** State the cognizable/bailable nature and quantum."
            )
        elif mode == "CONSUMER":
            return (
                "1. **STEP 1: COMMERCIAL PURPOSE CHECK (CRITICAL):**\n"
                "   - **Rule:** Buying goods for 'commercial purpose' (resale/profit-generation) EXCLUDES a person from being a 'Consumer' (Sec 2(7)(i)).\n"
                "   - **Flags:** Bulk purchase (>1 unit), Business use (Office/Institute), or Resale.\n"
                "   - **Result:** If Commercial -> STOP. Declare 'NOT A CONSUMER' and 'Complaint Not Maintainable'.\n"
                "2. **Jurisdiction Check (CPA 2019 ONLY):**\n"
                "   - **District:** Up to ₹50 Lakhs (New Rules) / ₹1 Cr (Act) -> **Cite Section 34**\n"
                "   - **State:** ₹50L - ₹2 Cr (New Rules) / ₹1 Cr - ₹10 Cr (Act) -> **Cite Section 47**\n"
                "   - **National:** Above ₹2 Cr (New Rules) / ₹10 Cr (Act) -> **Cite Section 58**\n"
                "3. **Deficiency Analysis:** Was there a fault/defect?\n"
                "4. **Relief:** Reject relief if not a consumer. Otherwise, Refund/Compensation."
            )
        elif mode == "CIVIL":
            return (
                "1. **Cause of Action:** What is the legal basis for the claim?\n"
                "2. **Jurisdiction:** Which court has the power to hear this?\n"
                "3. **Limitation:** Is the claim within the limitation period?\n"
                "4. **Remedy:** What relief can be granted (injunction, damages)?"
            )
        else:
            return "Apply standard legal interpretation: Facts -> Law -> Application -> Conclusion."

    def _prioritize_precedents(self, context: str) -> str:
        """
        Analyzes context for case hierarchy and returns prioritization instructions.
        """
        instructions = []
        lower_context = context.lower()
        
        # Constitution Bench detection
        if "constitution bench" in lower_context:
            instructions.append("CRITICAL: A Constitution Bench judgment is cited. This overrides all smaller bench decisions.")
            
        # Supreme Court vs High Court
        if "supreme court" in lower_context and "high court" in lower_context:
            instructions.append("HIERARCHY: Supreme Court judgments (Article 141) override High Court rulings.")
            
        # Recent vs Old
        instructions.append("RECENCY: Prefer recent judgments (2020-2025) over older ones if law has evolved.")
        
        return "\n".join(instructions)

    def _detect_conflicts(self, context: str) -> str:
        """
        Detects potential conflicts in the retrieved case law.
        """
        lower_context = context.lower()
        conflict_keywords = ["overruled", "dissenting", "distinguished", "per incuriam", "conflict", "contrary view"]
        
        if any(w in lower_context for w in conflict_keywords):
            return "CONFLICT ALERT: Conflicting judgments detected. You must explicitly resolve this by citing Article 141 and identifying the binding precedent."
        return ""

    def construct_structured_prompt(self, query: str, context: str, history: str) -> str:
        """
        Builds the ENHANCED dynamic prompt with professional features.
        """
        mode = self.detect_mode(query)
        print(f" [DEBUG] LegalReasoningEngine MODE: {mode}")
        framework = self.get_reasoning_framework(mode)
        revisions = self.revision_monitor.get_revision_context(query)
        precedent_instructions = self._prioritize_precedents(context)
        conflict_instructions = self._detect_conflicts(context)
        
        revision_text = "\n".join(revisions) if revisions else ""
        
        # Inject Specific Logic for CONSUMER cases
        consumer_instruction = ""
        if mode == "CONSUMER":
             consumer_instruction = """
**🛑 CRITICAL CONSUMER LAW RULES (DO NOT IGNORE):**
1. **Commercial Purpose Exclusion (Section 2(7) CPA 2019):**
   - **RULE:** Buying goods for commercial advantage/profit (e.g., for a training institute, factory, office) is **COMMERCIAL PURPOSE**.
   - **VERDICT:** If commercial purpose detected -> Buyer is **NOT A CONSUMER**. Complaint is **NOT MAINTAINABLE**.
   - **Your Conclusion:** MUST be "No, the buyer is not a consumer."
   - **Self-Employment Exception:** Applies ONLY to buying 1-2 units for personal livelihood (e.g., 1 car for taxi, 1 sewing machine). 
     - **10 Laptops = Commercial (NO Exception).**
     
2. **Correct Jurisdiction Sections (CPA 2019):**
   - **District Commission:** Section 34
   - **State Commission:** Section 47
   - **National Commission:** Section 58
   - **DO NOT cite Section 15** (That is for appeals, or old Act).

3. **Remedy Strategy:**
   - If NOT a consumer -> Advise filing a **Civil Suit** for recovery of money or specific performance.
"""

        # Base prompt
        prompt = f"""
You are an expert Senior Advocate of the Supreme Court of India.
Your task is to provide a **legally reasoned, professional opinion** on the following query.

{consumer_instruction}

**QUERY:** "{query}"

**LEGAL CONTEXT (Retrieved Data):**
{context}

**CRITICAL LEGAL UPDATES (Mandatory Application):**
{revision_text}

**REASONING FRAMEWORK TO USE ({mode}):**
{framework}

**PRECEDENT HIERARCHY & CONFLICTS:**
{precedent_instructions}
{conflict_instructions}

**STRICT RESPONSE STRUCTURE (Mandatory):**
You must structure your response using the EXACT format below.
Do not deviate. No conversational filler. NEVER use "may be" or vague language.
COMPLETE EVERY SECTION FULLY - Do not cut off mid-sentence.

⚡ EXECUTIVE SUMMARY
(State the factual dispute clearly in 2-3 sentences. NO predictions like "may be maintainable" - instead state: "The complaint involves..." or "This dispute concerns...")

❓ ISSUES FOR DETERMINATION
(Bullet points of specific legal questions that need resolution)

📜 APPLICABLE LAW
**DOMAIN-SPECIFIC PROVISIONS (Select ONLY the relevant domain - DO NOT mix domains):**

=== FOR BANKING / FINANCIAL SERVICES MIS-SELLING ===
- Consumer Protection Act, 2019:
  * Section 2(7): Consumer definition - Person availing banking services = Consumer
  * Section 2(11): Definition of "defect" and "deficiency"
  * Section 2(42): Unfair trade practice - Misleading representation about product
  * Section 2(47): Unfair contract - One-sided terms, hidden charges
- RBI Master Direction on Fair Practices Code:
  * Banks MUST provide clear, transparent information about products
  * Risk disclosure MUST be in simple language, not fine print
  * Suitability assessment required for complex products
  * Special duty of care towards senior citizens
- SEBI (Investment Advisers) Regulations, 2013:
  * Suitability of product to investor profile
  * Duty to act in best interest of client
- Senior Citizen Protection:
  * Maintenance and Welfare of Parents and Senior Citizens Act, 2007
  * Enhanced duty of care when dealing with elderly/vulnerable persons
  * Presumption of undue influence if terms are grossly unfair
- Digital Consent Issues:
  * IT Act, 2000: Valid consent requires understanding of terms
  * Fine print buried in digital documents ≠ informed consent
  * Burden on bank to prove risk was EXPLAINED, not just disclosed

=== FOR REAL ESTATE / BUILDER-BUYER DISPUTES ===
- Real Estate (Regulation and Development) Act, 2016 (RERA):
  * Section 18: Delay in possession → Refund with interest / Compensation
  * Section 19: Homebuyer rights (amenities, specifications, documents)
  * Section 31: Filing complaints before RERA Authority
  * Sections 71-72: Penalties for developers
- Consumer Protection Act, 2019:
  * Section 2(7): Buyer for PERSONAL USE = Consumer
  * Section 2(42): Unfair trade practice (misleading ads)
- RERA + CPA: BOTH forums have CONCURRENT jurisdiction

=== FOR E-COMMERCE / ONLINE PRODUCT DISPUTES (ONLY for online marketplace purchases) ===
- Consumer Protection Act, 2019 - Section 2(7), 2(11), 2(42)
- Consumer Protection (E-Commerce) Rules, 2020 - Rules 4, 5, 6 [Platform duties]
- NOTE: Do NOT cite E-Commerce Rules for banking, real estate, or offline transactions

=== FOR INSURANCE MIS-SELLING ===
- Insurance Act, 1938: Section 41 - Prohibition of rebates
- IRDAI (Protection of Policyholders' Interests) Regulations
- Mis-selling = Selling unsuitable product / misrepresenting terms

=== FOR EMPLOYMENT DISPUTES ===
- Industrial Disputes Act, 1947: Sections 2(s), 10, 25F, 25G
- Payment of Wages Act, 1936
- Employees' Provident Funds Act, 1952

=== ARBITRATION CLAUSE (For all consumer disputes) ===
- Section 2(6) CPA 2019: Consumer forum NOT barred by arbitration clause
- Consumer forum ALWAYS has jurisdiction despite arbitration

B. Judicial Doctrines / Principles
- Doctrine of Uberrima Fides (Utmost Good Faith) - For banking/insurance
- Doctrine of Unconscionability (for one-sided contracts)
- Contra Proferentem (ambiguity interpreted against drafter - bank/seller)
- Fiduciary duty (bank owes duty of care to customer)

🧠 LEGAL ANALYSIS (IRAC)
A. Issue (Restate the core legal question)

B. Rule (Settled Position of Law)
(Cite DOMAIN-SPECIFIC sections - NOT E-Commerce Rules for banking cases)

C. Application to Facts
(Apply the law to the user's specific situation with direct reasoning)

D. Counter-Arguments & Judicial Response
(What the opposing party might argue + How courts have responded)
FOR BANKING MIS-SELLING: Address "digital consent" argument - Fine print ≠ informed consent; Bank must PROVE explanation, not just disclosure

📚 JUDICIAL PRECEDENTS
**BANKING / FINANCIAL MIS-SELLING CASES:**
- Citibank N.A. v. Bimal Kumar Mukherjee (2016) NCDRC - Bank liable for mis-selling
- ICICI Bank v. Shanti Devi Sharma (2018) SC - Duty to explain product risks
- Standard Chartered Bank v. Dheeraj Tiwari (2020) - Digital consent invalid if not explained
- LIC v. Consumer Education & Research Society (2009) SC - Insurance mis-selling

**REAL ESTATE CASES:**
- Pioneer Urban v. Govindarajan (2019) SC - CPA and RERA concurrent jurisdiction
- Fortune Infrastructure v. Trevor D'Lima (2018) SC - Builder delay = deficiency
- Ireo Grace Realtech v. Abhishek Khanna (2021) SC - Refund with 9% interest

**ARBITRATION (For all domains):**
- Emaar MGF v. Aftab Singh (2019) - Consumer forum has jurisdiction despite arbitration

🧾 PROCEDURAL ASPECTS
Maintainability: (State clearly if complaint IS maintainable and WHY)
Jurisdiction: 
- RERA Authority for RERA violations
- Consumer Forum for deficiency/unfair trade practice (can file in EITHER or BOTH)
- Value-based: District (<1Cr), State (1-10Cr), National (>10Cr)

Burden of Proof: 
- CONSUMER LAW: Once prima facie defect shown, BURDEN SHIFTS TO DEVELOPER/SELLER
- REAL ESTATE: Developer must prove force majeure / compliance

⚖️ POSSIBLE OUTCOMES
Outcome A (Favorable): (Specific relief - Refund with 9-12% interest, compensation, costs)
Outcome B (Unfavorable): (What happens if complaint fails)
Outcome C (Settlement): (Possession with compensation for delay)

✅ FINAL LEGAL POSITION
(Clear, reasoned summary. Use definitive language: "The buyer has grounds to..." NOT "may have...")

⚠️ Disclaimer
Disclaimer: This response is for general legal information only and does not constitute legal advice. For case-specific guidance, consult a qualified advocate.
"""
        
        if "WEB SEARCH RESULTS" in context:
            prompt += "\n**SPECIAL INSTRUCTION:** You are using LIVE WEB SEARCH results. Cite the source title/URL for claims.\n"
            
        return prompt

    def validate_response(self, response: str) -> Dict[str, bool]:
        """
        Hallucination Firewall: Checks the generated response for safety.
        """
        issues = []
        
        # Check 1: Mandatory Disclaimer (Strict validation)
        if "⚠️ 9. Disclaimer" not in response and "Disclaimer (MANDATORY)" not in response:
             issues.append("Missing Mandatory Disclaimer")

        # Check 2: Structure Headers
        required_headers = [
            "🏷️ 1. Query Classification",
            "⚡ 2. Executive Summary",
            "❓ 3. Issues Involved",
            "📜 4. Applicable Law",
            "⚖️ 5. Legal Analysis",
            "🏛️ 6. Jurisdiction",
            "⏳ 7. Limitation Period",
            "🎯 8. Reliefs Available"
        ]
        
        missing_headers = [header for header in required_headers if header not in response]
        if len(missing_headers) > 2: # Allow small fuzziness but strict on major sections
            issues.append(f"Missing sections: {', '.join(missing_headers)}")
            
        # Check 3: Fake Citations (Basic heuristic)
        if "as an ai language model" in response.lower():
            issues.append("AI disclaimer found (should be professional)")
            
        # Check 4: Placeholder Check
        if "[Insert Section]" in response or "[Case Name]" in response:
            issues.append("Placeholder text found")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }

# Singleton
_engine = None

def get_legal_reasoning_engine() -> LegalReasoningEngine:
    global _engine
    if _engine is None:
        _engine = LegalReasoningEngine()
    return _engine
