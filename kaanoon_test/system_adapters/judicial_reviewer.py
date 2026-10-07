import logging
import json
from typing import Dict, Any

logger = logging.getLogger(__name__)

class JudicialReviewer:
    """
    Expert Multi-Agent Reviewer that critiques a legal draft.
    It identifies statutory errors, tone inconsistencies, and missing nuances.
    """
    
    def __init__(self, client, model="llama-3.3-70b-versatile"):
        self.client = client
        self.model = model

    def review_and_correct(self, query: str, context: str, draft: str, **kwargs) -> Dict[str, Any]:
        """
        Takes a draft opinion and performs a 'Judicial Audit'.
        Returns a vetted, high-accuracy final version.
        """
        # TOKEN OPTIMIZATION: Truncate context for the reviewer
        # The reviewer only needs enough to check for hallucinations.
        truncated_context = context[:3000] + "..." if len(context) > 3000 else context
        
        review_prompt = f"""You are a Senior Judge of the Supreme Court of India performing a mandatory Judicial Audit.

AGENT OBJECTIVE:
Identify and CORRECT any errors in the draft to ensure it meets a "10/10" Expert Grade.

QUERY: {query}
CONTEXT SNIPPET: {truncated_context}
DRAFT OPINION:
{draft}

AUDIT CHECKLIST (CRITICAL):
1. **STATUTORY ACCURACY**: Check if the Acts cited match the query's timeline (e.g., Use CPA 2019, NOT 1986).
2. **TONE CHECK**: Eliminate terms like "silver bullet", "lame excuse", or "win". Use "prima facie", "untenable", "doctrines".
3. **PRECEDENT VERIFICATION**: Ensure cited case names and ratios are relevant.
4. **ISSUE ALIGNMENT**: Do the "Issues" section match the user's core dispute?
5. **PRECISION**: Ensure Section numbers are correct for the domain.

MANDATORY RESPONSE FORMAT:
Provide the FINAL VETTED VERSION below. If no changes are needed, return the original draft. 
Apply the corrections SILENTLY - the output must be the complete, ready-to-use Legal Opinion.

VETTED LEGAL OPINION:
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a Senior Supreme Court Judge performing a Judicial Review. Your word is final. Accuracy is absolute."},
                    {"role": "user", "content": review_prompt}
                ],
                temperature=0.1 # Low temperature for high precision
            )
            
            final_content = response.choices[0].message.content.strip()
            
            # Remove any preamble like "Here is the vetted version..."
            if "VETTED LEGAL OPINION:" in final_content:
                final_content = final_content.split("VETTED LEGAL OPINION:")[1].strip()
                
            return {
                "answer": final_content,
                "audit_complete": True
            }
            
        except Exception as e:
            logger.error(f"Judicial Review failed: {e}")
            return {"answer": draft, "audit_complete": False}
