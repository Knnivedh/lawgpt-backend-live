"""
citation_guard.py - deterministic post-checks on LLM-generated legal answers.

The prompt tells the model to cite only sections present in the retrieved
context, but smaller models ignore that (especially when answering in Hindi).
These helpers enforce it in code instead of relying on the model.
"""

import re
from typing import List, Set, Tuple

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

_NUM = r"\d+[A-Za-z]?"
# "Section 498A", "Sections 498A and 323", "s.13", "sec. 125", "धारा 498A", "धाराएं 13, 24"
_SECTION_RE = re.compile(
    rf"(?:sections?|sec\.?|s\.|धाराएं|धारा)\s*({_NUM}(?:\s*(?:,|and|&|/|और|तथा)\s*{_NUM})*)",
    re.IGNORECASE,
)
_SENTENCE_END = "।.?!"

NOTE = {
    "hi": "(नोट: कुछ कानूनी धाराओं का उल्लेख उपलब्ध स्रोतों में सत्यापित नहीं हो सका, इसलिए हटा दिया गया है।)",
    "en": "(Note: some statutory references could not be verified in the retrieved sources and were omitted.)",
}


def _normalize(text: str) -> str:
    return (text or "").translate(_DEVANAGARI_DIGITS)


def extract_sections(text: str) -> Set[str]:
    """Return the set of section numbers (upper-cased, e.g. '498A') mentioned in *text*."""
    found: Set[str] = set()
    for match in _SECTION_RE.finditer(_normalize(text)):
        found.update(n.upper() for n in re.findall(_NUM, match.group(1)))
    return found


def sanitize_citations(answer: str, context_text: str, language: str = "en") -> Tuple[str, List[str]]:
    """
    Drop sentences that cite a section number absent from *context_text*.

    Returns (cleaned_answer, removed_section_numbers). If nothing is unverified
    the answer is returned untouched. If every sentence would be dropped the
    original answer is kept, so the user never gets an empty reply.
    """
    allowed = extract_sections(context_text)
    removed: List[str] = []
    kept_lines: List[str] = []

    for line in answer.split("\n"):
        sentences = re.split(rf"(?<=[{_SENTENCE_END}])\s+", line)
        kept = []
        for sentence in sentences:
            bad = extract_sections(sentence) - allowed
            if bad:
                removed.extend(sorted(bad))
            else:
                kept.append(sentence)
        kept_lines.append(" ".join(kept))

    if not removed:
        return answer, []

    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines)).strip()
    if not cleaned:
        return answer, []

    cleaned += "\n\n" + NOTE.get(language, NOTE["en"])
    return cleaned, sorted(set(removed))


def trim_to_last_sentence(text: str) -> str:
    """Cut a length-truncated answer back to its last complete sentence."""
    last = max(text.rfind(ch) for ch in _SENTENCE_END)
    if last >= len(text) * 0.5:
        return text[: last + 1].rstrip()
    return text.rstrip()


def excerpt_in_source(excerpt: str, source: str) -> bool:
    """True if *excerpt* (ignoring quotes/ellipses/whitespace) appears verbatim in *source*."""
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip().strip("\"'“”‘’").replace("...", "").replace("…", "")).lower().strip()

    e = norm(excerpt)
    return len(e) >= 15 and e in norm(source)
