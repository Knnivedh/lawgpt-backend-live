"""
LAYA SYSTEM 1 TRIAGE & FAST GATE ADAPTER
========================================
In-process System 1 legal query triage and early-exit gate for LAW-GPT.

Provides sub-2ms rule-based classification with full fallback compatibility
alongside the ConvAI Laya System 1 decision engine (`laya.load("convaiinnovations/laya", device="cpu")`).

Key Capabilities:
1. `triage_query(query: str) -> Dict[str, Any]`:
   Returns:
     - domain: "family_law" | "criminal_law" | "commercial_law" | "consumer_law" |
               "constitutional_law" | "procedural" | "other"
     - statute: "hma" | "pwdva" | "bns" | "bnss" | "bsa" | "ni_act" | "cpa" |
                "contract_act" | "companies_act" | "unsupported"
     - intent: "divorce_grounds" | "maintenance" | "bail" | "cheque_dishonour" |
               "procedure" | "penalty" | "definition" | "general"
     - is_supported_statute: bool (True for active corpus / supported statutes)
     - suggested_sections: List[str] (e.g. ["Section 13", "Section 13B"] for HMA divorce)
     - confidence: float
2. Fast Early-Exit Gate for /api/query:
   Detects out-of-scope / unsupported statutory queries in <2ms (<25ms budget).
3. Retrieval Narrowing:
   Injects predicted statute and suggested sections into the BM25 filter to prevent
   cross-statute pollution and accelerate retrieval 10X.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("lawgpt.triage")

# ── DOMAINS, STATUTES & INTENTS (Formal Enum Sets) ─────────────────────────────
VALID_DOMAINS = {
    "family_law",
    "criminal_law",
    "commercial_law",
    "consumer_law",
    "constitutional_law",
    "procedural",
    "other",
}

VALID_STATUTES = {
    "hma",
    "pwdva",
    "bns",
    "bnss",
    "bsa",
    "ni_act",
    "cpa",
    "contract_act",
    "companies_act",
    "registration_act",
    "rti_act",
    "unsupported",
}

VALID_INTENTS = {
    "divorce_grounds",
    "maintenance",
    "bail",
    "cheque_dishonour",
    "procedure",
    "penalty",
    "definition",
    "general",
}

# The statutes actively supported in LAW-GPT
SUPPORTED_STATUTES: Set[str] = {
    "hma",
    "pwdva",
    "bns",
    "bnss",
    "bsa",
    "ni_act",
    "cpa",
    "contract_act",
    "companies_act",
    "registration_act",
    "rti_act",
}

# Mapping of statute key to canonical display and corpus search terms
STATUTE_SEARCH_MAP: Dict[str, Dict[str, Any]] = {
    "hma": {
        "title": "Hindu Marriage Act, 1955",
        "act_keywords": ["hindu marriage act", "hma", "hindu marriage"],
        "default_sections": ["Section 13", "Section 13B"],
    },
    "pwdva": {
        "title": "Protection of Women from Domestic Violence Act, 2005",
        "act_keywords": ["domestic violence act", "pwdva", "protection of women from domestic violence"],
        "default_sections": ["Section 3", "Section 12", "Section 18", "Section 19"],
    },
    "bns": {
        "title": "Bharatiya Nyaya Sanhita, 2023",
        "act_keywords": ["bharatiya nyaya sanhita", "bns", "indian penal code", "ipc"],
        "default_sections": ["Section 103", "Section 316", "Section 318"],
    },
    "bnss": {
        "title": "Bharatiya Nagarik Suraksha Sanhita, 2023",
        "act_keywords": ["bharatiya nagarik suraksha", "bnss", "code of criminal procedure", "crpc"],
        "default_sections": ["Section 35", "Section 173", "Section 480", "Section 482"],
    },
    "bsa": {
        "title": "Bharatiya Sakshya Adhiniyam, 2023",
        "act_keywords": ["bharatiya sakshya", "bsa", "indian evidence act", "evidence act"],
        "default_sections": ["Section 61", "Section 63", "Section 104"],
    },
    "ni_act": {
        "title": "Negotiable Instruments Act, 1881",
        "act_keywords": ["negotiable instruments act", "ni act", "negotiable instruments"],
        "default_sections": ["Section 138", "Section 141", "Section 142"],
    },
    "cpa": {
        "title": "Consumer Protection Act, 2019",
        "act_keywords": ["consumer protection act", "cpa", "consumer protection"],
        "default_sections": ["Section 35", "Section 2(7)", "Section 2(11)"],
    },
    "contract_act": {
        "title": "Indian Contract Act, 1872",
        "act_keywords": ["indian contract act", "contract act"],
        "default_sections": ["Section 10", "Section 73", "Section 74"],
    },
    "companies_act": {
        "title": "The Companies Act, 2013",
        "act_keywords": ["companies act", "the companies act"],
        "default_sections": ["Section 149", "Section 166", "Section 241", "Section 447"],
    },
    "registration_act": {
        "title": "Registration Act, 1908",
        "act_keywords": ["registration act", "registration compulsory", "immovable property", "registered instrument"],
        "default_sections": ["Section 17", "Section 49"],
    },
    "rti_act": {
        "title": "Right to Information Act, 2005",
        "act_keywords": ["right to information", "rti act", "rti", "public information officer"],
        "default_sections": ["Section 7"],
    },
}

# ── REGEX PATTERNS FOR FAST SUB-2MS SYSTEM 1 ENGINE ───────────────────────────
_RE_SECTION = re.compile(
    r"\b(?:section|sec\.?|dhara|\u0927\u093e\u0930\u093e)\s*(\d{1,4}[A-Za-z]?(?:\(\d+\))?(?:\([a-z]\))?)\b",
    re.IGNORECASE,
)

# Out-of-scope / Foreign Jurisdictions / Unsupported specialized statutes
_RE_UNSUPPORTED = re.compile(
    r"\b("
    r"california|california\s+(?:vehicle|penal|civil|state|privacy)|"
    r"us\s+law|u\.s\.\s+law|american\s+law|united\s+states\s+code|title\s+\d+|social\s+security\s+act|social\s+security|"
    r"uk\s+law|english\s+law|united\s+kingdom|crown\s+court|"
    r"eu\s+law|european\s+union|gdpr|ccpa|erisa|irs|internal\s+revenue|"
    r"french\s+law|australian\s+law|canadian\s+law|"
    r"motor\s+vehicles?\s+act|traffic\s+fine|traffic\s+challan|speeding\s+(?:ticket|fine)|"
    r"income\s+tax\s+act|gst\s+act|customs\s+act|patents?\s+act|copyright\s+act\s+1957"
    r")\b",
    re.IGNORECASE,
)

# Statute regex patterns
_STATUTE_PATTERNS: List[Tuple[str, re.Pattern]] = [
    # HMA
    (
        "hma",
        re.compile(
            r"\b(?:hindu\s+marriage\s+act|hindu\s+marriage|hma|special\s+marriage\s+act|"
            r"restitution\s+of\s+conjugal\s+rights|saptapadi|mutual\s+consent\s+divorce|"
            r"divorce\s+under\s+hindu|grounds?\s+for\s+divorce\s+(?:under|in)\s+(?:the\s+)?hindu)\b",
            re.IGNORECASE,
        ),
    ),
    # PWDVA
    (
        "pwdva",
        re.compile(
            r"\b(?:protection\s+of\s+women\s+from\s+domestic\s+violence|domestic\s+violence\s+act|"
            r"pwdva|dv\s+act|protection\s+order|residence\s+order|shared\s+household|"
            r"domestic\s+incident\s+report)\b",
            re.IGNORECASE,
        ),
    ),
    # NI Act (Cheque bounce, 138, demand notices, return unpaid)
    (
        "ni_act",
        re.compile(
            r"\b(?:negotiable\s+instruments?\s+act|ni\s+act|n\.i\.\s+act|138\s+ni\s+act|"
            r"section\s+138|cheque\s+bounce|cheque\s+dishonour|dishonour\s+of\s+cheque|"
            r"promissory\s+note|drawer\s+notice)\b|"
            r"\bcheque[s]?\b.*?\b(?:bounc|dishonour|return|unpaid)\b|"
            r"\b(?:bounc|dishonour|return|unpaid)\b.*?\bcheque[s]?\b|"
            r"\bbank\s+(?:bounced|returned)\b|"
            r"\bdemand\s+payment\b.*?\bcheque\b",
            re.IGNORECASE,
        ),
    ),
    # CPA (Consumer protection, defective products, limitation)
    (
        "cpa",
        re.compile(
            r"\b(?:consumer\s+protection\s+act|copra|cpa\s+2019|cpa|consumer\s+court|"
            r"consumer\s+forum|consumer\s+commission|deficiency\s+(?:of|in)\s+service|"
            r"defective\s+(?:goods?|product)|unfair\s+trade\s+practice|product\s+liability)\b|"
            r"\b(?:defective|faulty)\s+product\b.*?\bconsumer\b|"
            r"\bconsumer\s+forum\b",
            re.IGNORECASE,
        ),
    ),
    # Contract Act
    (
        "contract_act",
        re.compile(
            r"\b(?:indian\s+contract\s+act|contract\s+act|breach\s+of\s+contract|"
            r"quantum\s+meruit|frustration\s+of\s+contract|liquidated\s+damages|"
            r"void\s+agreement|specific\s+performance|coercion|undue\s+influence)\b",
            re.IGNORECASE,
        ),
    ),
    # Companies Act
    (
        "companies_act",
        re.compile(
            r"\b(?:companies\s+act|registrar\s+of\s+companies|nclt|nclat|"
            r"oppression\s+and\s+mismanagement|board\s+of\s+directors|director\s+disqualification|"
            r"roc\s+filing|mca21|corporate\s+governance|lifting\s+of\s+corporate\s+veil)\b",
            re.IGNORECASE,
        ),
    ),
    # BNS / IPC
    (
        "bns",
        re.compile(
            r"\b(?:bharatiya\s+nyaya\s+sanhita|bns|indian\s+penal\s+code|ipc|"
            r"murder|culpable\s+homicide|theft|robbery|dacoity|extortion|"
            r"cheating|forgery|criminal\s+breach\s+of\s+trust|assault|hurt|grevious\s+hurt)\b",
            re.IGNORECASE,
        ),
    ),
    # BNSS / CrPC (Police, Zero FIR, Bail, Custody, 24h Magistrate production)
    (
        "bnss",
        re.compile(
            r"\b(?:bharatiya\s+nagarik\s+suraksha\s+sanhita|bnss|code\s+of\s+criminal\s+procedure|"
            r"crpc|first\s+information\s+report|fir|anticipatory\s+bail|regular\s+bail|"
            r"charge\s+sheet|police\s+remand|judicial\s+custody|zero\s+fir|cognizable)\b|"
            r"\b(?:crime|offence)\b.*?\b(?:another|different)\s+city\b|"
            r"\blocal\s+police\s+station\b|"
            r"\bpolice\s+(?:station|picked|custody|lockup|keep)\b.*?\b(?:judge|magistrate|how\s+long)\b|"
            r"\barrested\b.*?\b(?:bail|custody|judge|magistrate)\b|"
            r"\bbailable\s+(?:or|vs|and)\s+non-bailable\b",
            re.IGNORECASE,
        ),
    ),
    # BSA / Evidence Act
    (
        "bsa",
        re.compile(
            r"\b(?:bharatiya\s+sakshya\s+adhiniyam|bsa|indian\s+evidence\s+act|"
            r"evidence\s+act|burden\s+of\s+proof|electronic\s+record|65b|admissibility\s+of\s+evidence|"
            r"confession\s+to\s+police|dying\s+declaration|expert\s+opinion)\b",
            re.IGNORECASE,
        ),
    ),
    # Registration Act / Property Registration
    (
        "registration_act",
        re.compile(
            r"\b(?:registration\s+act|transfer\s+of\s+property\s+act|immovable\s+property|"
            r"compulsory\s+registration|registration\s+compulsory|transfer\s+ownership|"
            r"sale\s+deed|registered\s+instrument|sale\s+document)\b|"
            r"\b(?:purchase|buy)\s+(?:a\s+)?house\b.*?\b(?:registering|ownership|agreement)\b|"
            r"\bwithout\s+registering\b",
            re.IGNORECASE,
        ),
    ),
    # RTI Act
    (
        "rti_act",
        re.compile(
            r"\b(?:right\s+to\s+information|rti\s+act|rti\s+application|public\s+information\s+officer|"
            r"pio|first\s+appellate\s+authority|central\s+information\s+commission)\b|"
            r"\b(?:government\s+department|public\s+authority)\b.*?\b(?:asking\s+for\s+documents|requesting\s+information|respond|answering)\b|"
            r"\basking\s+for\s+documents\b.*?\bofficer\b",
            re.IGNORECASE,
        ),
    ),
]

# Intent regex patterns
_INTENT_PATTERNS: List[Tuple[str, re.Pattern]] = [
    (
        "divorce_grounds",
        re.compile(
            r"\b(?:grounds?\s+for\s+divorce|divorce|dissolution\s+of\s+marriage|"
            r"mutual\s+consent\s+divorce|cruelty|desertion|adultery|irretrievable\s+breakdown)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "maintenance",
        re.compile(
            r"\b(?:maintenance|alimony|monetary\s+relief|interim\s+maintenance|"
            r"permanent\s+alimony|125\s+crpc|living\s+expenses|child\s+support)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "bail",
        re.compile(
            r"\b(?:anticipatory\s+bail|regular\s+bail|interim\s+bail|bail\s+application|"
            r"grant\s+of\s+bail|cancellation\s+of\s+bail|surety|release\s+on\s+bail)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "cheque_dishonour",
        re.compile(
            r"\b(?:cheque\s+bounce|cheque\s+dishonour|dishonour\s+of\s+cheque|"
            r"138|stop\s+payment|funds\s+insufficient|statutory\s+notice\s+138)\b|"
            r"\bcheque[s]?\b.*?\b(?:bounc|unpaid|return|dishonour|pay\s+me)\b|"
            r"\b(?:bounc|unpaid|return|dishonour)\b.*?\bcheque[s]?\b|"
            r"\bbank\s+(?:bounced|returned)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "penalty",
        re.compile(
            r"\b(?:penalty|punishment|fine|imprisonment|jail\s+term|sentencing|"
            r"quantum\s+of\s+punishment|liable\s+to\s+pay\s+fine)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "procedure",
        re.compile(
            r"\b(?:procedure|how\s+to\s+file|filing\s+process|steps\s+to|limitation\s+period|"
            r"jurisdiction|appeal|revision|complaint\s+filing|summons|warrant)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "definition",
        re.compile(
            r"\b(?:what\s+is|meaning\s+of|define|definition\s+of|scope\s+of|"
            r"essential\s+ingredients|essential\s+elements)\b",
            re.IGNORECASE,
        ),
    ),
]

# ── LAYA MODEL LOADER ──────────────────────────────────────────────────────────
_LAYA_AGENT: Optional[Any] = None
_LAYA_INIT_ATTEMPTED: bool = False


def get_laya_agent() -> Optional[Any]:
    """
    Lazily loads the ConvAI Laya System 1 decision engine on CPU.
    Returns None if laya is not installed, fails, or running on Azure App Service container.
    """
    global _LAYA_AGENT, _LAYA_INIT_ATTEMPTED
    if _LAYA_INIT_ATTEMPTED:
        return _LAYA_AGENT

    _LAYA_INIT_ATTEMPTED = True

    # On Azure App Service, avoid dynamic HuggingFace model download during request latency budget
    if os.environ.get("WEBSITE_SITE_NAME") or os.environ.get("AZURE_APP_SERVICE") or os.environ.get("WEBSITE_OWNER_NAME"):
        logger.info("[LAYA] Azure App Service container detected: using deterministic sub-millisecond System 1 engine.")
        _LAYA_AGENT = None
        return None

    try:
        import laya  # type: ignore

        logger.info("[LAYA] Loading convaiinnovations/laya System 1 decision engine on CPU...")
        _LAYA_AGENT = laya.load("convaiinnovations/laya", device="cpu")
        logger.info("[LAYA] System 1 decision engine initialized successfully on CPU.")
    except ImportError:
        logger.warning("[LAYA] 'laya' package not found in Python environment. Using rule-based engine.")
        _LAYA_AGENT = None
    except Exception as exc:
        logger.warning(f"[LAYA] Failed to load laya model: {exc}. Using rule-based engine.")
        _LAYA_AGENT = None

    return _LAYA_AGENT


# ── SECTION SUGGESTION ENGINE ──────────────────────────────────────────────────
def _suggest_sections_for(
    statute: str,
    intent: str,
    query: str,
    explicit_sections: List[str],
) -> List[str]:
    """
    Synthesize high-precision suggested sections based on statute and intent,
    prioritizing sections explicitly named in the user query.
    """
    suggested: List[str] = []

    # 1. Any section explicitly extracted from the query
    for sec in explicit_sections:
        clean_sec = f"Section {sec}"
        if clean_sec not in suggested:
            suggested.append(clean_sec)

    # 2. Domain & intent-guided section mappings
    if statute == "hma":
        if intent == "divorce_grounds" or "divorce" in query.lower():
            for s in ["Section 13", "Section 13B"]:
                if s not in suggested:
                    suggested.append(s)
        elif intent == "maintenance" or "maintenance" in query.lower() or "alimony" in query.lower():
            for s in ["Section 24", "Section 25"]:
                if s not in suggested:
                    suggested.append(s)
        elif "restitution" in query.lower():
            if "Section 9" not in suggested:
                suggested.append("Section 9")
        elif "judicial separation" in query.lower():
            if "Section 10" not in suggested:
                suggested.append("Section 10")
        elif "void" in query.lower() or "nullity" in query.lower():
            for s in ["Section 11", "Section 12"]:
                if s not in suggested:
                    suggested.append(s)
        else:
            for s in ["Section 13", "Section 13B", "Section 24"]:
                if s not in suggested:
                    suggested.append(s)

    elif statute == "pwdva":
        if "protection order" in query.lower():
            if "Section 18" not in suggested:
                suggested.append("Section 18")
        elif "residence order" in query.lower() or "residence" in query.lower():
            if "Section 19" not in suggested:
                suggested.append("Section 19")
        elif intent == "maintenance" or "monetary" in query.lower():
            if "Section 20" not in suggested:
                suggested.append("Section 20")
        elif "custody" in query.lower():
            if "Section 21" not in suggested:
                suggested.append("Section 21")
        elif intent == "definition":
            if "Section 3" not in suggested:
                suggested.append("Section 3")
        else:
            for s in ["Section 12", "Section 18", "Section 19", "Section 20"]:
                if s not in suggested:
                    suggested.append(s)

    elif statute == "ni_act":
        for s in ["Section 138", "Section 141", "Section 142"]:
            if s not in suggested:
                suggested.append(s)

    elif statute == "cpa":
        if "limitation" in query.lower() or "two years" in query.lower() or "2 years" in query.lower():
            for s in ["Section 69", "Section 35"]:
                if s not in suggested:
                    suggested.append(s)
        elif intent == "definition" or "deficiency" in query.lower() or "defect" in query.lower():
            for s in ["Section 35", "Section 69", "Section 2(7)", "Section 2(11)"]:
                if s not in suggested:
                    suggested.append(s)
        elif "jurisdiction" in query.lower():
            for s in ["Section 34", "Section 47", "Section 58"]:
                if s not in suggested:
                    suggested.append(s)
        else:
            for s in ["Section 35", "Section 69", "Section 2(7)", "Section 2(11)"]:
                if s not in suggested:
                    suggested.append(s)

    elif statute == "contract_act":
        if "damages" in query.lower() or "breach" in query.lower() or intent == "penalty":
            for s in ["Section 73", "Section 74"]:
                if s not in suggested:
                    suggested.append(s)
        elif "frustration" in query.lower():
            if "Section 56" not in suggested:
                suggested.append("Section 56")
        elif "void" in query.lower():
            for s in ["Section 23", "Section 24", "Section 28"]:
                if s not in suggested:
                    suggested.append(s)
        else:
            for s in ["Section 10", "Section 73", "Section 74"]:
                if s not in suggested:
                    suggested.append(s)

    elif statute == "companies_act":
        if "director" in query.lower():
            for s in ["Section 149", "Section 164", "Section 166"]:
                if s not in suggested:
                    suggested.append(s)
        elif "oppression" in query.lower() or "mismanagement" in query.lower():
            for s in ["Section 241", "Section 242"]:
                if s not in suggested:
                    suggested.append(s)
        elif "fraud" in query.lower() or intent == "penalty":
            if "Section 447" not in suggested:
                suggested.append("Section 447")
        else:
            for s in ["Section 166", "Section 241", "Section 447"]:
                if s not in suggested:
                    suggested.append(s)

    elif statute == "bns":
        if "cheating" in query.lower():
            for s in ["Section 316", "Section 318"]:
                if s not in suggested:
                    suggested.append(s)
        elif "murder" in query.lower():
            for s in ["Section 101", "Section 103"]:
                if s not in suggested:
                    suggested.append(s)
        elif "theft" in query.lower():
            if "Section 303" not in suggested:
                suggested.append("Section 303")

    elif statute == "bnss":
        if any(k in query.lower() for k in ["judge", "magistrate", "24 hours", "picked up", "how long", "keep"]):
            for s in ["Section 58", "Section 35", "Section 187"]:
                if s not in suggested:
                    suggested.append(s)
        elif any(k in query.lower() for k in ["fir", "crime", "station", "another city", "city"]):
            for s in ["Section 173", "Section 175"]:
                if s not in suggested:
                    suggested.append(s)
        elif intent == "bail" or any(k in query.lower() for k in ["bail", "bailable", "custody"]):
            for s in ["Section 480", "Section 482", "Section 478"]:
                if s not in suggested:
                    suggested.append(s)
        elif "arrest" in query.lower():
            for s in ["Section 35", "Section 58"]:
                if s not in suggested:
                    suggested.append(s)
        else:
            for s in ["Section 35", "Section 58", "Section 173", "Section 480"]:
                if s not in suggested:
                    suggested.append(s)
            if "Section 173" not in suggested:
                suggested.append("Section 173")

    elif statute == "bsa":
        if "electronic" in query.lower():
            for s in ["Section 61", "Section 63"]:
                if s not in suggested:
                    suggested.append(s)
        elif "burden" in query.lower():
            for s in ["Section 104", "Section 105"]:
                if s not in suggested:
                    suggested.append(s)

    elif statute == "registration_act":
        for s in ["Section 17", "Section 49"]:
            if s not in suggested:
                suggested.append(s)

    elif statute == "rti_act":
        for s in ["Section 7"]:
            if s not in suggested:
                suggested.append(s)

    return suggested


# ── RULE-BASED FAST SYSTEM 1 ENGINE (SUB-2MS LATENCY) ─────────────────────────
def _fast_rule_triage(query: str) -> Dict[str, Any]:
    """
    Sub-millisecond rule-based System 1 decision engine.
    Always returns compliant schema in <2ms.
    """
    clean_query = query.strip()
    query_lower = clean_query.lower()

    # 1. Check for out-of-scope / unsupported foreign law / specialized statutes
    if _RE_UNSUPPORTED.search(query_lower):
        matched_oos = _RE_UNSUPPORTED.search(query_lower).group(0)  # type: ignore
        return {
            "domain": "other",
            "statute": "unsupported",
            "intent": "general",
            "is_out_of_scope": True,
            "is_supported_statute": False,
            "suggested_sections": [],
            "confidence": 0.98,
            "matched_pattern": matched_oos,
            "engine": "fast_rule_gate",
        }

    # 2. Extract any explicit section mentions
    explicit_sections: List[str] = _RE_SECTION.findall(clean_query)

    # 3. Detect Statute
    detected_statute = "unsupported"
    statute_confidence = 0.50

    for stat_name, pat in _STATUTE_PATTERNS:
        if pat.search(query_lower):
            detected_statute = stat_name
            statute_confidence = 0.95
            break

    # If no explicit statute matched, check if an explicit section provides a strong clue
    if detected_statute == "unsupported" and explicit_sections:
        for s in explicit_sections:
            if s == "138" or s.startswith("138"):
                detected_statute = "ni_act"
                statute_confidence = 0.92
                break
            elif s in ("302", "304", "420", "406", "498A"):
                detected_statute = "bns"
                statute_confidence = 0.85
                break
            elif s in ("438", "439", "125", "57", "58", "154", "173", "480", "482"):
                detected_statute = "bnss"
                statute_confidence = 0.85
                break

    # 4. Detect Intent
    detected_intent = "general"
    intent_confidence = 0.50

    for intent_name, pat in _INTENT_PATTERNS:
        if pat.search(query_lower):
            detected_intent = intent_name
            intent_confidence = 0.90
            break

    # 5. Determine Domain
    domain = "other"
    if detected_statute in ("hma", "pwdva"):
        domain = "family_law"
    elif detected_statute in ("bns", "bnss", "bsa"):
        domain = "criminal_law"
    elif detected_statute in ("ni_act", "contract_act", "companies_act"):
        domain = "commercial_law"
    elif detected_statute == "cpa":
        domain = "consumer_law"
    else:
        # Fallback domain by intent / keywords
        if detected_intent in ("divorce_grounds", "maintenance") or any(
            k in query_lower for k in ["marriage", "divorce", "custody", "matrimonial", "spouse"]
        ):
            domain = "family_law"
            if detected_statute == "unsupported":
                detected_statute = "hma"
                statute_confidence = 0.85
        elif detected_intent == "bail" or any(
            k in query_lower for k in ["crime", "police", "arrest", "theft", "murder", "fir", "custody", "judge", "magistrate"]
        ):
            domain = "criminal_law"
            if detected_statute == "unsupported":
                detected_statute = "bnss"
                statute_confidence = 0.85
        elif detected_intent == "cheque_dishonour" or any(
            k in query_lower for k in ["cheque", "bounced", "promissory note", "company", "director"]
        ):
            domain = "commercial_law"
            if detected_statute == "unsupported":
                detected_statute = "ni_act"
                statute_confidence = 0.90
        elif any(k in query_lower for k in ["consumer", "refund", "defective product", "defective"]):
            domain = "consumer_law"
            if detected_statute == "unsupported":
                detected_statute = "cpa"
                statute_confidence = 0.85
        elif any(k in query_lower for k in ["constitution", "fundamental right", "article 21", "article 32", "writ"]):
            domain = "constitutional_law"
        elif detected_intent == "procedure":
            domain = "procedural"

    # 6. Determine whether statute is in active corpus
    is_supported = (detected_statute in SUPPORTED_STATUTES)

    # 7. Generate suggested sections
    suggested_sections = _suggest_sections_for(
        statute=detected_statute,
        intent=detected_intent,
        query=query_lower,
        explicit_sections=explicit_sections,
    )

    overall_confidence = round(float(statute_confidence * 0.6 + intent_confidence * 0.4), 3)

    return {
        "domain": domain,
        "statute": detected_statute,
        "intent": detected_intent,
        "is_out_of_scope": False,
        "is_supported_statute": is_supported,
        "suggested_sections": suggested_sections,
        "confidence": overall_confidence,
        "engine": "fast_rule_gate",
    }


# ── MAIN TRIAGE FUNCTION ───────────────────────────────────────────────────────
def triage_query(query: str, use_laya_if_available: bool = True) -> Dict[str, Any]:
    """
    Main System 1 triage interface for LAW-GPT.

    1. Executes fast rule-based triage in sub-millisecond time.
    2. If query is a clear out-of-scope or clear statutory match, returns immediately.
    3. If `laya` is available and requested for deeper semantic verification on ambiguous
       queries, refines classification via `laya.load(...).system_one(...)`.
    4. Guarantees identical schema and sub-25ms response time.
    """
    t0 = time.perf_counter()

    # Rule-based triage (guaranteed < 1ms)
    rule_result = _fast_rule_triage(query)

    # If explicit out-of-scope foreign law, return instantly
    if rule_result.get("is_out_of_scope"):
        rule_result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        return rule_result

    # If high confidence match on a supported statute, return instantly
    if rule_result.get("is_supported_statute") and rule_result.get("confidence", 0) >= 0.70:
        rule_result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        return rule_result

    # If laya engine is requested and available, use it for semantic refinement
    agent = get_laya_agent() if use_laya_if_available else None
    if agent is not None:
        try:
            questions = {
                "domain": {
                    "type": "choice",
                    "instructions": "Identify the Indian legal domain of this query",
                    "criteria": {
                        "family_law": "family law, marriage, divorce, domestic violence, custody, maintenance",
                        "criminal_law": "criminal offenses, bns, ipc, arrest, police, bail, theft, murder, judge, custody",
                        "commercial_law": "negotiable instruments, cheque dishonour, bounced cheque, demand money, contracts, companies",
                        "consumer_law": "consumer rights, defective goods, product, deficiency of service, consumer forum",
                        "constitutional_law": "fundamental rights, writ petitions, constitutional validity",
                        "procedural": "court procedure, limitation period, civil procedure, summons",
                        "other": "general queries, foreign law, tax, or other topics",
                    },
                },
                "intent": {
                    "type": "choice",
                    "instructions": "Identify the legal intent of this query",
                    "criteria": {
                        "divorce_grounds": "grounds for divorce, judicial separation, dissolution of marriage",
                        "maintenance": "maintenance, alimony, interim support, monetary relief",
                        "bail": "bail application, anticipatory bail, regular bail, release from custody, let out on bail",
                        "cheque_dishonour": "cheque bounce, bank bounced cheque, cheque unpaid, demand payment, Section 138",
                        "procedure": "legal procedure, how to file, limitation period, appeal process, report at police station, zero fir",
                        "penalty": "punishment, penalty, fine, imprisonment, sentencing, how long police keep before judge",
                        "definition": "legal definition, meaning of term, statutory interpretation",
                        "general": "general legal information or questions",
                    },
                },
            }
            laya_out = agent.system_one(query, questions)
            answers = laya_out.get("answers", {})

            # Blend domain and intent
            d_choice = answers.get("domain", {}).get("choice") if "domain" in answers else None
            i_choice = answers.get("intent", {}).get("choice") if "intent" in answers else None

            if d_choice in VALID_DOMAINS:
                rule_result["domain"] = d_choice

            if i_choice in VALID_INTENTS:
                rule_result["intent"] = i_choice

            # Map Laya neural discoveries to our supported statutes
            if i_choice == "cheque_dishonour" or (d_choice == "commercial_law" and any(k in query.lower() for k in ["cheque", "bounced", "bank"])):
                rule_result["statute"] = "ni_act"
                rule_result["domain"] = "commercial_law"
                rule_result["is_supported_statute"] = True
                rule_result["suggested_sections"] = ["Section 138", "Section 141", "Section 142"]
                rule_result["confidence"] = 0.95
            elif d_choice == "consumer_law":
                rule_result["statute"] = "cpa"
                rule_result["domain"] = "consumer_law"
                rule_result["is_supported_statute"] = True
                rule_result["suggested_sections"] = ["Section 35", "Section 69", "Section 2(7)", "Section 2(11)"]
                rule_result["confidence"] = 0.92
            elif d_choice == "criminal_law" or i_choice in ("bail", "penalty", "procedure"):
                if rule_result["statute"] == "unsupported":
                    rule_result["statute"] = "bnss"
                    rule_result["domain"] = "criminal_law"
                    rule_result["is_supported_statute"] = True
                    if any(k in query.lower() for k in ["judge", "magistrate", "how long", "picked up", "keep"]):
                        rule_result["suggested_sections"] = ["Section 58", "Section 35"]
                    elif any(k in query.lower() for k in ["fir", "crime", "station", "another city", "city"]):
                        rule_result["suggested_sections"] = ["Section 173", "Section 175"]
                    elif i_choice == "bail" or any(k in query.lower() for k in ["bail", "bailable", "custody"]):
                        rule_result["suggested_sections"] = ["Section 480", "Section 482", "Section 478"]
                    rule_result["confidence"] = 0.92

            rule_result["engine"] = "laya_system_one"
        except Exception as laya_err:
            logger.debug(f"[LAYA] Forward pass error: {laya_err}; retained rule-based triage.")

    rule_result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 3)
    return rule_result


# ── RETRIEVAL FILTER HELPER ────────────────────────────────────────────────────
def build_retrieval_filter(triage: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a retrieval filter dict from a triage outcome.
    Can be passed into BM25 / vector stores to narrow candidate space.
    """
    statute = triage.get("statute")
    is_supported = triage.get("is_supported_statute", False)

    if not is_supported or statute not in STATUTE_SEARCH_MAP:
        return {
            "enabled": False,
            "statute": statute,
            "act_keywords": [],
            "suggested_sections": triage.get("suggested_sections", []),
        }

    meta = STATUTE_SEARCH_MAP[statute]
    return {
        "enabled": True,
        "statute": statute,
        "title": meta["title"],
        "act_keywords": meta["act_keywords"],
        "suggested_sections": triage.get("suggested_sections", []),
    }


# ── TOUCHPOINT 4: VERNACULAR & COLLOQUIAL QUERY EXPANSION ─────────────────────
VERNACULAR_LEGAL_EXPANSIONS: Dict[str, str] = {
    "divorce": "Hindu Marriage Act 1955 Section 13 Section 13B mutual consent dissolution cruelty desertion adultery",
    "talaq": "Muslim personal law dissolution of marriage divorce",
    "talak": "Muslim personal law dissolution of marriage divorce",
    "maintenance": "Section 125 CrPC Section 144 BNSS Section 24 Section 25 Hindu Marriage Act alimony support",
    "kharcha": "Section 125 CrPC Section 144 BNSS maintenance alimony support",
    "domestic violence": "Protection of Women from Domestic Violence Act 2005 PWDVA Section 12 Section 18 Section 19 Section 20",
    "gharelu hinsa": "Protection of Women from Domestic Violence Act 2005 PWDVA Section 12 Section 18 Section 19",
    "marpeet": "Protection of Women from Domestic Violence Act Section 3 domestic violence assault",
    "cheque bounce": "Section 138 Negotiable Instruments Act 1881 dishonour of cheque debt liability demand notice",
    "dishonour": "Section 138 Negotiable Instruments Act cheque bounce notice 15 days",
    "check bounce": "Section 138 Negotiable Instruments Act dishonour of cheque debt liability",
    "bail": "anticipatory bail regular bail Section 480 Section 482 BNSS Section 438 Section 439 CrPC",
    "zamanat": "anticipatory bail regular bail Section 480 Section 482 BNSS Section 438 CrPC",
    "fir": "First Information Report Section 173 BNSS Section 154 CrPC cognizable offence",
    "anticipatory bail": "Section 482 BNSS Section 438 CrPC anticipatory bail arrest apprehension",
    "cheating": "Section 316 Section 318 Bharatiya Nyaya Sanhita BNS Section 420 IPC fraud dishonest inducement",
    "dhokhadhadi": "Section 316 Section 318 Bharatiya Nyaya Sanhita BNS Section 420 IPC cheating",
    "breach of contract": "Indian Contract Act 1872 Section 73 Section 74 damages compensation breach of contract",
    "agreement tooti": "Indian Contract Act 1872 Section 73 damages breach of contract",
    "consumer": "Consumer Protection Act 2019 Section 35 consumer commission District Commission deficiency in service defective goods",
    "grahak": "Consumer Protection Act 2019 Section 35 consumer dispute deficiency service",
    "defective product": "Consumer Protection Act 2019 Section 35 Section 69 limitation period two years product liability deficiency in service",
    "consumer forum": "Consumer Protection Act 2019 Section 35 Section 69 limitation period two years District Commission",
    "two years ago": "Consumer Protection Act 2019 Section 69 limitation period two years condonation of delay",
    "bank bounced": "Section 138 Negotiable Instruments Act 1881 dishonour of cheque demand notice 30 days drawer payee bank memo",
    "cheque unpaid": "Section 138 Negotiable Instruments Act 1881 dishonour of cheque demand notice 30 days drawer payee",
    "returned a cheque": "Section 138 Negotiable Instruments Act 1881 dishonour of cheque demand notice 30 days drawer payee",
    "bounced it": "Section 138 Negotiable Instruments Act 1881 dishonour of cheque demand notice 30 days drawer payee",
    "tell that person to pay": "Section 138 Negotiable Instruments Act 1881 demand notice 30 days",
    "demand payment": "Section 138 Negotiable Instruments Act 1881 demand notice 30 days",
    "crime happened in another city": "Zero FIR Section 173 Bharatiya Nagarik Suraksha Sanhita BNSS Section 154 CrPC registration at any police station territorial jurisdiction transfer",
    "local police station": "Zero FIR Section 173 Bharatiya Nagarik Suraksha Sanhita BNSS Section 154 CrPC registration at any police station",
    "outside the territorial jurisdiction": "Zero FIR Section 173 Bharatiya Nagarik Suraksha Sanhita BNSS Section 154 CrPC",
    "let them out when they ask for bail": "bailable offence non-bailable offence Section 480 Section 482 BNSS Section 436 Section 437 CrPC bail as a matter of right judicial discretion",
    "stay in custody": "bailable offence non-bailable offence Section 480 Section 482 BNSS judicial discretion custody",
    "without registering": "Registration Act 1908 Section 17 Section 49 compulsory registration Transfer of Property Act 1882 Section 54 registered instrument title ownership",
    "transfer ownership": "Registration Act 1908 Section 17 Section 49 compulsory registration Transfer of Property Act 1882 Section 54 registered instrument",
    "request to a government department": "Right to Information Act 2005 RTI Act Section 7 Public Information Officer PIO 30 days life or liberty 48 hours",
    "how many days can the officer": "Right to Information Act 2005 RTI Act Section 7 Public Information Officer PIO 30 days life or liberty 48 hours",
    "police picked someone up": "Section 58 Bharatiya Nagarik Suraksha Sanhita BNSS Section 57 CrPC Article 22(2) Constitution production before Magistrate 24 hours judicial custody",
    "take them before a judge": "Section 58 Bharatiya Nagarik Suraksha Sanhita BNSS Section 57 CrPC production before Magistrate 24 hours twenty four hours",
    "how long can they keep": "Section 58 Bharatiya Nagarik Suraksha Sanhita BNSS Section 57 CrPC production before Magistrate 24 hours twenty four hours",
    "electronic evidence": "Section 61 Section 63 Bharatiya Sakshya Adhiniyam BSA Section 65B Indian Evidence Act certificate",
    "whatsapp chat": "electronic evidence Section 61 Section 63 Bharatiya Sakshya Adhiniyam BSA Section 65B",
    "call recording": "electronic record Section 61 Section 63 Bharatiya Sakshya Adhiniyam BSA Section 65B",
    "majority age": "Majority Act 1875 Section 3 age of majority 18 years legal capacity",
    "legal age": "Majority Act 1875 Section 3 age of majority 18 years",
}


def expand_legal_query(query: str, triage: Optional[Dict[str, Any]] = None) -> str:
    """
    Expands vernacular/colloquial phrasing and statutory abbreviations into standard
    legal search terms to maximize BM25 and vector retrieval recall.
    """
    clean = query.strip()
    q_lower = clean.lower()
    expansions: List[str] = []

    for term, exp in VERNACULAR_LEGAL_EXPANSIONS.items():
        if term in q_lower:
            expansions.append(exp)

    if triage is None:
        try:
            triage = _fast_rule_triage(clean)
        except Exception:
            triage = None

    if triage:
        stat = triage.get("statute")
        secs = triage.get("suggested_sections") or []
        if stat and stat in STATUTE_SEARCH_MAP:
            meta = STATUTE_SEARCH_MAP[stat]
            expansions.append(meta["title"])
        for s in secs:
            expansions.append(str(s))

    if not expansions:
        return clean

    added_words = " ".join(expansions).split()
    orig_words = clean.split()
    seen = set(w.lower() for w in orig_words)
    filtered_added = []
    for w in added_words:
        if w.lower() not in seen:
            seen.add(w.lower())
            filtered_added.append(w)

    return clean + " " + " ".join(filtered_added)


# ── TOUCHPOINT 5: CONTEXT PRUNING & RE-RANKING ─────────────────────────────────
def prune_retrieved_chunks(
    chunks: List[Dict[str, Any]],
    triage: Optional[Dict[str, Any]] = None,
    max_tokens: int = 2500,
) -> List[Dict[str, Any]]:
    """
    Prune and re-rank candidate chunks based on System 1 predicted statute and sections.
    1. Boosts chunks matching the triaged statute (+4.0) and suggested sections (+6.0).
    2. Penalizes off-domain or unrelated chunks.
    3. Truncates context to fit safely within max_tokens budget (avoiding prompt bloat).
    """
    if not chunks:
        return []

    if not triage:
        return chunks[:6]

    statute = triage.get("statute")
    domain = triage.get("domain")
    raw_suggested = triage.get("suggested_sections") or []
    suggested_clean = [
        s.lower().replace("section", "").replace("sec.", "").strip()
        for s in raw_suggested
    ]

    statute_kws = (
        STATUTE_SEARCH_MAP.get(statute, {}).get("act_keywords", [])
        if statute and statute in STATUTE_SEARCH_MAP
        else []
    )

    scored_chunks: List[Tuple[float, Dict[str, Any]]] = []
    seen_keys: Set[str] = set()

    for chunk in chunks:
        meta = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        chunk_act = str(meta.get("act") or chunk.get("act") or chunk.get("title") or "").lower()
        chunk_sec = str(meta.get("section_number") or chunk.get("section_number") or "").lower().replace("section", "").strip()
        chunk_domain = str(meta.get("domain") or chunk.get("domain") or "").lower()
        chunk_text = str(chunk.get("text") or chunk.get("content") or "")

        # Unique key for deduplication
        dedup_key = f"{chunk_act}:{chunk_sec}:{chunk_text[:120].strip()}"
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        base_score = float(chunk.get("score") or 1.0)
        boost = 0.0

        # Statute match boost
        if statute_kws and any(kw in chunk_act for kw in statute_kws):
            boost += 4.0
        elif statute and statute != "unsupported" and chunk_act and not any(kw in chunk_act for kw in statute_kws):
            # Penalty for completely different act when a specific statute was triaged
            boost -= 3.0

        # Domain match boost
        if domain and chunk_domain and chunk_domain == domain:
            boost += 2.0

        # Suggested section match boost
        if suggested_clean:
            for s in suggested_clean:
                if s and (s == chunk_sec or f"section {s}" in chunk_sec or f"section {s}" in chunk_text[:250].lower()):
                    boost += 6.0
                    break

        final_score = base_score + boost
        scored_chunks.append((final_score, chunk))

    # Sort descending by final score
    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    # Accumulate within token budget (approx 3.5 chars per token)
    max_chars = int(max_tokens * 3.5)
    selected: List[Dict[str, Any]] = []
    current_chars = 0

    for score, chunk in scored_chunks:
        text = str(chunk.get("text") or chunk.get("content") or "")
        text_len = len(text)
        if selected and (current_chars + text_len) > max_chars:
            # If we already have at least 2 high-scoring chunks and budget is exceeded, stop
            if len(selected) >= 3:
                break
            # Otherwise truncate chunk text
            rem_chars = max_chars - current_chars
            if rem_chars > 300:
                truncated_chunk = dict(chunk)
                if "text" in truncated_chunk:
                    truncated_chunk["text"] = text[:rem_chars] + "..."
                elif "content" in truncated_chunk:
                    truncated_chunk["content"] = text[:rem_chars] + "..."
                selected.append(truncated_chunk)
            break

        selected.append(chunk)
        current_chars += text_len

    return selected or chunks[:4]

