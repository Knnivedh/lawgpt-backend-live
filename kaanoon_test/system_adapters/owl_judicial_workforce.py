import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv

# camel-ai is optional — import lazily so the server starts even if package is missing
try:
    from camel.agents import ChatAgent
    from camel.configs import ChatGPTConfig
    from camel.models import ModelFactory
    from camel.types import ModelType, RoleType, ModelPlatformType
    from camel.messages import BaseMessage
    _CAMEL_AVAILABLE = True
except ImportError:
    _CAMEL_AVAILABLE = False
    # Create stub types so class definition doesn't crash
    class ModelType:
        GROQ_LLAMA_3_3_70B = "groq-llama-3.3-70b"
    class ModelPlatformType:
        GROQ = "groq"
    logging.getLogger(__name__).warning(
        "camel-ai not installed — OwlJudicialWorkforce will be disabled"
    )

load_dotenv()
logger = logging.getLogger(__name__)

class OwlJudicialWorkforce:
    """
    Enhanced Multi-Agent Workforce using CAMEL-AI OWL.
    Collaborates across specialized agents to perform a deep judicial audit.
    """
    
    def __init__(self, client_manager=None, model_platform=None, model_type=None):
        self.client_manager = client_manager
        self.model_platform = model_platform or (ModelPlatformType.GROQ if _CAMEL_AVAILABLE else "groq")
        self.model_type = model_type or (ModelType.GROQ_LLAMA_3_3_70B if _CAMEL_AVAILABLE else "groq-llama-3.3-70b")
        self.statutory_agent = None
        self.precedent_agent = None
        self.style_agent = None

        if not _CAMEL_AVAILABLE:
            logger.warning("OwlJudicialWorkforce: camel-ai not available, running in stub mode")
            return

        # Initial agent creation (will be refreshed per run)
        self._refresh_agents()

    def _refresh_agents(self):
        """Re-creates agents using the current active API key from the manager"""
        if not _CAMEL_AVAILABLE:
            return
        active_key = self.client_manager.get_active_key() if self.client_manager else os.getenv("GROQ_API_KEY")
        
        # FORCE: Temporarily set env var for ModelFactory (Standard Hack for CAMEL)
        if active_key:
            os.environ["GROQ_API_KEY"] = active_key
            os.environ["groq_api"] = active_key
            
        self.statutory_agent = self._create_agent(
            "Statutory Specialist",
            "You are a Senior Legal Auditor. Your job is to CATCH STATUTORY ERRORS.\n" +
            "CRITICAL CHECKS (CPA 2019):\n" +
            "1. 'Consumer' is Section 2(7), NOT 2(11).\n" +
            "2. 'Defect' is Section 2(10), NOT 2(42).\n" +
            "3. 'Deficiency' is Section 2(11).\n" +
            "4. 'Unfair Trade Practice' is Section 2(47).\n" +
            "5. 'Misleading Ad' is Section 2(28).\n" +
            "6. 'Product Liability' is Chapter VI (Sections 82-87) - MANDATORY for defects.\n" +
            "7. Ensure 2(28) (Ads) and 2(46) (Unfair Contract) are TREATED SEPARATELY.\n" +
            "Output: List specific corrections needed."
        )
        self.precedent_agent = self._create_agent(
            "Precedent Researcher",
            "You are a Senior Legal Researcher. \n" +
            "1. Retain 'Emaar MGF' for arbitration.\n" +
            "2. Identify specific liability for Service Centers (Failure to service) and Platforms (Intermediary liability).\n" +
            "3. Ensure the 'Ratio Decidendi' supports the specific product defect."
        )
        self.style_agent = self._create_agent(
            "Linguistic Auditor",
            "Ensure 'Judicial Restraint' in tone. \n" +
            "1. REPLACE 'Strong grounds' with 'Arguable case' or 'Prima facie merit'.\n" +
            "2. REPLACE 'Will win' with 'Subject to evidence'.\n" +
            "3. Ensure formal, objective language."
        )

    def _create_agent(self, role_name: str, system_message: str):
        if not _CAMEL_AVAILABLE:
            return None
        model = ModelFactory.create(
            model_platform=self.model_platform,
            model_type=self.model_type,
        )
        return ChatAgent(
            system_message=BaseMessage.make_assistant_message(
                role_name=role_name,
                content=system_message
            ),
            model=model,
        )

    def review_and_correct(self, query: str, context: str, draft: str) -> Dict[str, Any]:
        """
        Orchestrates a collaborative review of the legal draft.
        """
        # CRITICAL: Refresh agents with NEW key if rotation happened
        if self.client_manager:
            # Trigger rotation check on manager side
            self.client_manager.get_client() 
            self._refresh_agents()
            
        logger.info("Starting OWL Multi-Agent Multi-Step Judicial Review...")
        
    def review_and_correct(self, query: str, context: str, draft: str, dynamic_law_context: str = "") -> Dict[str, Any]:
        """
        Orchestrates a collaborative review with AUTO-FAILOVER and DYNAMIC LAW INJECTION.
        """
        if self.client_manager:
            self._refresh_agents()
            
        logger.info("Starting OWL Multi-Agent Multi-Step Judicial Review...")
        
        # 1. Inject Dynamic Laws into Statutory Agent
        statutory_system = (
            "You are a Senior Legal Auditor.\n"
            "YOUR SOURCE OF TRUTH IS THE PROVIDED 'DYNAMIC LAW CONTEXT'.\n"
            "1. If the context contains specific Acts (e.g. IT Act, Copyright Act), ENFORCE THEM.\n"
            "2. If the context is empty/irrelevant, fallback to General Indian Law principles.\n"
            "3. FOR CONSUMER CASES: Enforce CPA 2019 (S. 2(7), 2(10), 82-87) strictly.\n"
            "4. FOR OTHER DOMAINS: Use the laws cited in the Dynamic Context.\n"
            "Output: specific corrections."
        )
        self.statutory_agent = self._create_agent("Statutory Specialist", statutory_system)
        
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # 1. Statutory Review with Dynamic Context
                statutory_task = (
                    f"Audit based on DYNAMIC LAW:\n{dynamic_law_context}\n\n"
                    f"Query: {query}\n"
                    f"Draft: {draft}"
                )
                statutory_response = self.statutory_agent.step(statutory_task)
                statutory_critique = statutory_response.msgs[0].content

                # 2. Precedent Review
                precedent_task = f"Audit case law usage. Verify liability attribution.\nDraft: {draft}\nContext: {context}"
                precedent_response = self.precedent_agent.step(precedent_task)
                precedent_critique = precedent_response.msgs[0].content

                # 3. Linguistic Review
                style_task = f"Check tone (Judicial Restraint). Suggest 'Prima facie'.\nDraft: {draft}"
                style_response = self.style_agent.step(style_task)
                style_critique = style_response.msgs[0].content
                
                # 4. Final Synthesis
                # 4. Final Synthesis
                synthesis_prompt = f"""
                You are the Chief Justice. REWRITE the draft into a FINAL OPINION.
                
                SOURCE MATERIAL:
                - Dynamic Law Context: {dynamic_law_context}
                
                CRITICAL INSTRUCTIONS:
                1. FORMAT (STRICTLY FOLLOW THIS ORDER):
                   🔹 **DIRECT SOLUTION & CONCLUSION**
                   (Start with "The Complainant has arguable grounds..." or "A prima facie case exists...". 
                    AVOID "You will win". Use judicial neutrality. State the likely outcome based on evidence.)
                   
                   🔹 **WHAT THIS CASE IS ABOUT (IN SIMPLE WORDS)**
                   (1–2 short lines explaining facts plainly. No legal jargon.)

                   🔹 **⚖️ LEGAL ISSUES FOR DETERMINATION**
                   (Frame 2-3 specific legal questions the court must decide.
                    Example: "1. Whether the heating issue constitutes a 'defect' under S. 2(10)?")

                   🔹 **🛡️ MANUFACTURER'S DEFENSE / COUNTER-ARGUMENTS**
                   (Anticipate the other side's defense. 
                    Example: "The manufacturer may argue that the defect is due to misuse...")
                   
                   🔹 **WHY THE LAW SUPPORTS YOU**
                   (Explain rights using CORRECT keywords: 
                    - 'Defect' (S. 2(10))
                    - 'Deficiency' (S. 2(11))
                    - 'Unfair Trade Practice' (S. 2(47)).
                    - 'Product Liability' (S. 82-87).
                    refute the counter-arguments here.)
                   
                   🔹 **🏛️ RELEVANT CASE LAW PRECEDENTS**
                   (CITE AT LEAST 1-2 RELEVANT CASES. If precise case unknown, cite principle from "Emaar MGF" or similar standard consumer cases.
                    Format: *Case Name* (Year) - Principle.)

                   🔹 **WHAT YOU CAN LEGALLY ASK FOR**
                   (Clear reliefs: Refund, Replacement, Compensation, Litigation Costs.)
                   
                   🔹 **WHAT YOU SHOULD DO NEXT**
                   (Step-by-step: "Send Legal Notice", "File in District Commission (if < ₹50L)", etc.)
                   
                   🔹 **LEGAL VIEW (FOR REFERENCE – MANDATORY ACCURACY)**
                   (Cite PRECISELY:
                    - Consumer Definition: S. 2(7) [NOT 2(11)]
                    - Defect: S. 2(10)
                    - Product Liability: S. 82-87
                    - Jurisdiction: S. 34 (District) / S. 47 (State) / S. 58 (National).
                    Use professional legal language here.)
                   
                   ⚠️ **IMPORTANT NOTE**
                   (Standard disclaimer: "Consult an advocate for representation.")

                2. TONE:
                   - **Judicial & Balanced**: Use "Subject to evidence", "Onus of proof".
                   - **Dual-Layer**: Simple English for user sections, Strict Legal for Issues/Law/View.
                   - **Accuracy**: ZERO HALLUCINATIONS on Section numbers. 
                
                3. IMPLEMENT corrections silently (Statutory/Precedent/Style).
                
                3. IMPLEMENT corrections silently (Statutory/Precedent/Style).
                
                INPUTS:
                - Statutory Critique: {statutory_critique}
                - Precedent Critique: {precedent_critique}
                - Draft: {draft}
                
                OUTPUT: ONLY the rewritten judgment in the requested format.
                """
                
                final_agent = self._create_agent("Chief Justice", "You are the final authority in legal drafting.")
                final_response = final_agent.step(synthesis_prompt)
                final_draft = final_response.msgs[0].content
                
                return {
                    "answer": final_draft,
                    "statutory_critique": statutory_critique,
                    "precedent_critique": precedent_critique,
                    "style_critique": style_critique,
                    "audit_complete": True
                }

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "rate limit" in error_msg.lower():
                    logger.error(f"⚠️ RATE LIMIT HIT (Attempt {attempt+1}/{max_retries}). Triggering Failover...")
                    if self.client_manager and attempt < max_retries:
                        self.client_manager.force_rotation(reason=f"429 Rate Limit: {error_msg[:100]}")
                        self._refresh_agents() # Re-init with new key
                        import time
                        time.sleep(2) # Brief cooldown
                        continue
                    else:
                        logger.error("❌ ALL RETRIES EXHAUSTED. Returning Draft without Audit.")
                        return {
                            "answer": draft + "\n\n[System Note: Judicial Audit Skipped due to High Traffic. Logic Unverified.]", 
                            "audit_complete": False
                        }
                else:
                    logger.error(f"Workforce Error: {e}")
                    raise e
