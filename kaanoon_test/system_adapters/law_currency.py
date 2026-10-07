"""Law-in-force (currency) guard for Indian legal answers.

The BNS / BNSS / BSA replaced the IPC / CrPC / Evidence Act for offences on or
after 2024-07-01. The model answered post-2024 questions with the repealed
provisions (Section 438 CrPC for anticipatory bail, Evidence Act s.65B for
electronic evidence) because nothing in the pipeline told it which regime applied.

This module is a deterministic POST-CHECK. It does not try to rewrite the law; it
detects the mismatch and downgrades confidence so the UI stops presenting a
repealed provision as authoritative, and returns a note the caller can surface.

It is deliberately conservative: it only fires when the answer asserts a repealed
provision AND offers no current-law alternative, and only when the query looks
post-transition.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Dict, List, Optional, Tuple

BNS_EFFECTIVE = date(2024, 7, 1)

# provision -> (repealed act, current act, current provision label)
REPEALED_TO_CURRENT: Dict[str, Tuple[str, str, str]] = {
    "438": ("CrPC", "BNSS", "Section 482 BNSS (anticipatory bail)"),
    "437": ("CrPC", "BNSS", "Section 481 BNSS"),
    "436": ("CrPC", "BNSS", "Section 480 BNSS"),
    "439": ("CrPC", "BNSS", "Section 483 BNSS"),
    "167": ("CrPC", "BNSS", "Section 94 BNSS"),
    "65b": ("Evidence Act", "BSA", "Section 63 BSA (electronic records)"),
    "65a": ("Evidence Act", "BSA", "Section 63 BSA"),
    "45": ("Evidence Act", "BSA", "Section 23 BSA"),
    "302": ("IPC", "BNS", "Section 103 BNS (murder)"),
    "304a": ("IPC", "BNS", "Section 106 BNS (culpable homicide not intended)"),
    "306": ("IPC", "BNS", "Section 105 BNS"),
    "377": ("IPC", "BNS", "Section 303 BNS (theft)"),
    "379": ("IPC", "BNS", "Section 303 BNS (theft)"),
    "378": ("IPC", "BNS", "Section 304 BNS (dishonest misappropriation)"),
    "380": ("IPC", "BNS", "Section 305 BNS (theft by deception)"),
    "390": ("IPC", "BNS", "Section 316 BNS (rioting)"),
    "392": ("IPC", "BNS", "Section 316 BNS"),
    "395": ("IPC", "BNS", "Section 318 BNS"),
    "376": ("IPC", "BNS", "Section 63 BNS (rape)"),
    "420": ("IPC", "BNS", "Section 318 BNS (cheating)"),
    "406": ("IPC", "BNS", "Section 314 BNS (criminal breach of trust)"),
    "405": ("IPC", "BNS", "Section 314 BNS (criminal breach of trust)"),
    "409": ("IPC", "BNS", "Section 316 BNS"),
    "409a": ("IPC", "BNS", "Section 318 BNS"),
    "120b": ("IPC", "BNS", "Section 351 BNS (criminal conspiracy)"),
    "141": ("IPC", "BNS", "Section 190 BNS (unlawful assembly)"),
    "143": ("IPC", "BNS", "Section 189 BNS"),
    "147": ("IPC", "BNS", "Section 190 BNS (rioting armed)"),
    "148": ("IPC", "BNS", "Section 191 BNS"),
    "153a": ("IPC", "BNS", "Section 196 BNS"),
    "124a": ("IPC", "BNS", "Section 152 BNS (sedition)"),
    "499": ("IPC", "BNS", "Section 356 BNS (defamation)"),
    "500": ("IPC", "BNS", "Section 356 BNS"),
    "503": ("IPC", "BNS", "Section 357 BNS (criminal intimidation)"),
    "509": ("IPC", "BNS", "Section 74 BNS (insulting a woman's modesty)"),
}

CURRENT_MARKERS = ("bns", "bnss", "bsa", "bharatiya nyaya",
                   "bharatiya nagarik", "bharatiya sakshya")

# Statutory section numbers run 1-4 digits with an optional letter suffix (65B,
# 304A, 120B, 482). The earlier {3,4} floor missed the two-digit+suffix forms,
# which is exactly where s.65B of the Evidence Act lives.
_REPEALED_ACT_PATTERN = re.compile(
    r"\b(\d{2,4}[a-z]?)\s*(?:of\s+)?(?:the\s+)?(IPC|Indian Penal Code|CrPC|Code of Criminal Procedure|"
    r"Evidence Act|Indian Evidence Act)\b",
    flags=re.IGNORECASE,
)
_REPEALED_ACT_PREFIX = re.compile(
    r"\b(IPC|Indian Penal Code|CrPC|Code of Criminal Procedure|Evidence Act|Indian Evidence Act)\s*"
    r"(?:Section|Sec\.?|s\.?)\s*(\d{2,4}[a-z]?)\b",
    flags=re.IGNORECASE,
)

_ACT_CANONICAL = {
    "ipc": "IPC", "indian penal code": "IPC",
    "crpc": "CrPC", "code of criminal procedure": "CrPC",
    "evidence act": "Evidence Act", "indian evidence act": "Evidence Act",
}
def extract_offence_date(text: str) -> Optional[date]:
    """Best-effort offence/incident date from a user query."""
    t = str(text or "")
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b", t)
    if m and m.group(2).lower()[:9] in _MONTHS:
        try:
            return date(int(m.group(3)), _MONTHS[m.group(2).lower()[:9]], int(m.group(1)))
        except ValueError:
            pass
    m = re.search(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", t)
    if m and m.group(1).lower()[:9] in _MONTHS:
        try:
            return date(int(m.group(3)), _MONTHS[m.group(1).lower()[:9]], int(m.group(2)))
        except ValueError:
            pass
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r"\b(?:in|on)\s+(\d{4})\b", t, re.IGNORECASE)
    if m:
        try:
            return date(int(m.group(1)), 6, 15)
        except ValueError:
            pass
    return None


def current_law_expected(query: str) -> bool:
    """True unless the question is explicitly anchored to a pre-2024 regime.

    The earlier version required an explicit post-2024 date, so a question with no
    date at all ("Can WhatsApp chats be used as evidence in an Indian court?") was
    exempt - yet the answer must cite BSA s.63, because that is the law today. The
    rule is therefore inverted: current law is the default, and only a question
    that explicitly points at an earlier date is treated as historical.
    """
    d = extract_offence_date(query)
    if d:
        return d >= BNS_EFFECTIVE
    low = str(query or "").lower()
    if re.search(r"\b(was|were|formerly|back\s+then|at\s+the\s+time|historical(?:ly)?|"
                 r"under\s+the\s+(?:old|then|previous)\s+law)\b", low):
        return False
    return True


# Backwards-compatible alias used elsewhere.
is_post_transition = current_law_expected


def find_repealed_citations(answer: str) -> List[Dict[str, str]]:
    """Repealed provisions asserted in the answer."""
    text = str(answer or "")
    hits: List[Dict[str, str]] = []
    seen = set()

    def record(num: str, act: str, raw: str) -> None:
        key = (num.lower(), act)
        if key in seen:
            return
        canon = _ACT_CANONICAL.get(re.sub(r"\s+", " ", act.strip().lower()), "")
        if not canon:
            return
        if canon == "IPC" and num.lower() in ("65", "65a", "65b"):
            canon = "Evidence Act"  # s.65* is Evidence Act territory
        mapping = REPEALED_TO_CURRENT.get(num.lower())
        if not mapping or mapping[0] != canon:
            return
        seen.add(key)
        hits.append({
            "citation": raw.strip()[:80],
            "repealed_act": canon,
            "section": num,
            "current_provision": mapping[2],
        })

    for m in _REPEALED_ACT_PREFIX.finditer(text):
        record(m.group(2), m.group(1), m.group(0))
    for m in _REPEALED_ACT_PATTERN.finditer(text):
        record(m.group(1), m.group(2), m.group(0))
    return hits


def check_currency(query: str, answer: str) -> Dict[str, object]:
    """Post-check an answer for the BNS transition.

    Returns violations, a suggested confidence ceiling, and a note. Only fires
    when a post-2024 question is answered purely with repealed provisions.
    """
    result = {"violations": [], "confidence_cap": None, "note": None,
              "post_transition": False, "offence_date": None}

    d = extract_offence_date(query)
    if d:
        result["offence_date"] = d.isoformat()
    post = current_law_expected(query)
    result["post_transition"] = post
    if not post:
        return result

    violations = find_repealed_citations(answer)
    if not violations:
        return result

    # If the answer already names the current law alongside the old law, that is a
    # legitimate transition explanation and must NOT be penalised.
    if any(m in (answer or "").lower() for m in CURRENT_MARKERS):
        return result

    result["violations"] = violations
    result["confidence_cap"] = 0.45
    names = ", ".join(v["current_provision"] for v in violations[:3])
    result["note"] = (
        "For matters arising on or after 1 July 2024 the applicable provisions are "
        f"{names}. The repealed provision cited above should not be relied on as "
        "current law."
    )
    return result

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}
_MONTHS.update({m[:3]: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])})