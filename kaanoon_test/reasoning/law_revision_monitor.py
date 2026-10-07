"""
Law Revision Monitor
Tracks post-2022 legal changes and ensures the system is aware of:
1. Sedition Law Stay (2022)
2. New Criminal Laws (BNS, BNSS, BSA 2023)
3. Recent Privacy/IT Rules
"""

from typing import Dict, List, Optional

class LawRevisionMonitor:
    """Monitors and injects context for recently revised or stayed laws."""
    
    def __init__(self):
        self.revisions = {
            "sedition": {
                "keywords": ["sedition", "124a", "124-a"],
                "status": "STAYED",
                "context": (
                    "CRITICAL LEGAL UPDATE: The Supreme Court of India in 'S.G. Vombatkere v. Union of India' (2022) "
                    "has kept Section 124A IPC (Sedition) in ABEYANCE. No new FIRs can be registered under this section "
                    "until further orders. The Govt of India is re-examining the provision. "
                    "Any analysis MUST mention this stay order first."
                )
            },
            "ipc_replacement": {
                "keywords": ["ipc", "indian penal code"],
                "status": "REPLACED",
                "context": (
                    "LEGAL UPDATE: The Indian Penal Code (IPC) has been replaced by the 'Bharatiya Nyaya Sanhita' (BNS), 2023. "
                    "However, for offenses committed before the notification date, IPC still applies. "
                    "You must mention the corresponding BNS section if applicable."
                )
            },
            "crpc_replacement": {
                "keywords": ["crpc", "criminal procedure"],
                "status": "REPLACED",
                "context": (
                    "LEGAL UPDATE: The CrPC has been replaced by the 'Bharatiya Nagarik Suraksha Sanhita' (BNSS), 2023. "
                    "Mention the corresponding BNSS provision."
                )
            },
            "evidence_replacement": {
                "keywords": ["evidence act"],
                "status": "REPLACED",
                "context": (
                    "LEGAL UPDATE: The Indian Evidence Act has been replaced by the 'Bharatiya Sakshya Adhiniyam' (BSA), 2023."
                )
            },
            "privacy": {
                "keywords": ["privacy", "data protection"],
                "status": "UPDATED",
                "context": (
                    "LEGAL UPDATE: Refer to the 'Digital Personal Data Protection Act, 2023' and the "
                    "K.S. Puttaswamy judgment (Right to Privacy is a fundamental right)."
                )
            }
        }

    def get_revision_context(self, query: str) -> List[str]:
        """Check query for revised laws and return mandatory context."""
        query_lower = query.lower()
        contexts = []
        
        for key, data in self.revisions.items():
            if any(kw in query_lower for kw in data["keywords"]):
                contexts.append(f"⚠️ {data['context']}")
                
        return contexts

# Singleton
_monitor = None

def get_law_revision_monitor() -> LawRevisionMonitor:
    global _monitor
    if _monitor is None:
        _monitor = LawRevisionMonitor()
    return _monitor
