"""
citation_guard.py - deterministic post-checks on LLM-generated legal answers.

The prompt tells the model to cite only what is in the retrieved context, but
smaller models ignore that (especially when answering in Hindi). This module
checks the answer in code, with no model call.

What is checked, sentence by sentence, against the retrieved context:
  section  a section number that appears nowhere in the context
  pair     a section cited under an act when the context only ever mentions
           that section number with a different act
  act      an act that the context never mentions
  case     a case name ("X v. Y") that the context never mentions

What happens to a sentence with an unverified citation depends on the mode:
  strict   remove it, whatever the kind
  mixed    remove for section / pair / case; keep but list in a note for act
  flag     remove for section only (the original behaviour); list the rest

Only citations that can be positively checked are acted on. Act and case names
written in Devanagari that are not in the known-acts list below cannot be
matched against English sources, so they are left alone.
"""

import re
from typing import Dict, Iterable, List, NamedTuple, Optional, Set, Tuple, Union

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

_NUM = r"\d+[A-Za-z]?"
_NUM_LIST = rf"{_NUM}(?:\s*(?:\([0-9a-zA-Z]+\))*\s*(?:,|and|&|/|और|तथा)\s*{_NUM})*"
# "Section 498A", "Sections 498A and 323", "s.13", "sec. 125", "u/s 498A", "धारा 498A"
_SECTION_RE = re.compile(
    rf"(?:\bsections?|\bsec\.?|\bs\.|\bu/s\.?|धाराएं|धाराओं|धारा)\s*({_NUM_LIST})",
    re.IGNORECASE,
)
# A number list directly before an act name: "498A IPC", "125 of the CrPC", "498a/406 IPC"
_NUM_BEFORE_ACT_RE = re.compile(rf"({_NUM_LIST})\s*(?:of\s+(?:the\s+)?)?$", re.IGNORECASE)
_SENTENCE_END = "।.?!"

MODES = {
    "strict": {"section", "pair", "act", "case"},
    "mixed": {"section", "pair", "case"},
    "flag": {"section"},
}

REMOVED_NOTE = {
    "hi": "(नोट: कुछ कानूनी संदर्भों की पुष्टि उपलब्ध स्रोतों में नहीं हो सकी, इसलिए उन्हें हटा दिया गया है।)",
    "en": "(Note: some legal references could not be verified in the retrieved sources and were omitted.)",
}
FLAGGED_NOTE = {
    "hi": "(नोट: इन संदर्भों की पुष्टि उपलब्ध स्रोतों में नहीं हो सकी: {items}।)",
    "en": "(Note: these references could not be verified in the retrieved sources: {items}.)",
}

# Known acts: canonical name -> patterns (full names, abbreviations, Hindi names).
_KNOWN_ACTS: Dict[str, List[str]] = {
    "Hindu Marriage Act": [r"hindu\s+marriage\s+act", r"\bH\.?M\.?A\.?\b", r"हि[ंन्]दू\s+विवाह\s+अधिनियम", r"हि[ंन्]दू\s+मैरिज\s+एक्ट"],
    "Special Marriage Act": [r"special\s+marriage\s+act", r"\bS\.?M\.?A\.?\b", r"विशेष\s+विवाह\s+अधिनियम", r"स्पेशल\s+मैरिज\s+एक्ट"],
    "Protection of Women from Domestic Violence Act": [
        r"protection\s+of\s+women\s+from\s+domestic\s+violence\s+act", r"domestic\s+violence\s+act",
        r"\bPWDVA\b", r"\bD\.?V\.?\s+act\b", r"घरेलू\s+हिंसा\s+(?:से\s+महिलाओं\s+का\s+संरक्षण\s+)?(?:अधिनियम|कानून)",
        r"डोमेस्टिक\s+वायलेंस\s+एक्ट", r"डीवी\s+एक्ट",
    ],
    "Hindu Succession Act": [r"hindu\s+succession\s+act", r"\bHSA\b", r"हि[ंन्]दू\s+उत्तराधिकार\s+अधिनियम"],
    "Hindu Adoptions and Maintenance Act": [
        r"hindu\s+adoptions?\s+(?:and|&)\s+maintenance\s+act", r"\bHAMA\b", r"हि[ंन्]दू\s+दत्तक\S*\s+(?:और|तथा)\s+भरण[- ]पोषण\s+अधिनियम",
    ],
    "Hindu Minority and Guardianship Act": [
        r"hindu\s+minority\s+(?:and|&)\s+guardianship\s+act", r"\bHMGA\b", r"हि[ंन्]दू\s+अप्राप्तवयता\s+(?:और|तथा)\s+संरक्षकता\s+अधिनियम",
    ],
    "Guardians and Wards Act": [r"guardians?\s+(?:and|&)\s+wards\s+act", r"\bGWA\b", r"संरक्षक\s+(?:और|तथा)\s+प्रतिपाल्य\s+अधिनियम"],
    "Dowry Prohibition Act": [r"dowry\s+prohibition\s+act", r"दहेज\s+(?:निषेध|प्रतिषेध)\s+अधिनियम"],
    "Prohibition of Child Marriage Act": [r"prohibition\s+of\s+child\s+marriage\s+act", r"बाल\s+विवाह\s+(?:निषेध|प्रतिषेध)\s+अधिनियम"],
    "Muslim Women (Protection of Rights on Divorce) Act": [r"muslim\s+women\s*\(?\s*protection\s+of\s+rights\s+on\s+divorce\s*\)?\s*act"],
    "Muslim Women (Protection of Rights on Marriage) Act": [r"muslim\s+women\s*\(?\s*protection\s+of\s+rights\s+on\s+marriage\s*\)?\s*act"],
    "Muslim Personal Law (Shariat) Application Act": [r"muslim\s+personal\s+law\s*\(?\s*shariat\s*\)?\s*application\s+act", r"shariat\s+act"],
    "Dissolution of Muslim Marriages Act": [r"dissolution\s+of\s+muslim\s+marriages?\s+act"],
    "Indian Divorce Act": [r"(?<!and )(?<!& )(?:indian\s+)?divorce\s+act"],
    "Indian Succession Act": [r"indian\s+succession\s+act"],
    "Parsi Marriage and Divorce Act": [r"parsi\s+marriage\s+(?:and|&)\s+divorce\s+act"],
    "Foreign Marriage Act": [r"foreign\s+marriage\s+act"],
    "Family Courts Act": [r"family\s+courts?\s+act", r"कुटुंब\s+न्यायालय\s+अधिनियम"],
    "Legal Services Authorities Act": [r"legal\s+services\s+authorit(?:y|ies)\s+act"],
    "Juvenile Justice Act": [r"juvenile\s+justice\s*(?:\(care\s+and\s+protection\s+of\s+children\)\s*)?act", r"\bJJ\s+act\b"],
    "Maintenance and Welfare of Parents and Senior Citizens Act": [
        r"maintenance\s+and\s+welfare\s+of\s+parents\s+and\s+senior\s+citizens\s+act", r"senior\s+citizens?\s+act",
    ],
    "Indian Evidence Act": [r"(?:indian\s+)?evidence\s+act"],
    "Indian Penal Code": [r"indian\s+penal\s+code", r"\bI\.?P\.?C\.?\b", r"भारतीय\s+दंड\s+संहिता", r"आईपीसी"],
    "Code of Criminal Procedure": [
        r"code\s+of\s+criminal\s+procedure", r"criminal\s+procedure\s+code", r"\bCr\.?\s?P\.?C\.?\b",
        r"दंड\s+प्रक्रिया\s+संहिता", r"सीआरपीसी",
    ],
    "Code of Civil Procedure": [r"code\s+of\s+civil\s+procedure", r"civil\s+procedure\s+code", r"\bC\.?P\.?C\.?\b", r"सिविल\s+प्रक्रिया\s+संहिता"],
    "Bharatiya Nyaya Sanhita": [r"bharatiya\s+nyaya\s+sanhita", r"\bBNS\b", r"भारतीय\s+न्याय\s+संहिता"],
    "Bharatiya Nagarik Suraksha Sanhita": [r"bharatiya\s+nagarik\s+suraksha\s+sanhita", r"\bBNSS\b", r"भारतीय\s+नागरिक\s+सुरक्षा\s+संहिता"],
    "Bharatiya Sakshya Adhiniyam": [r"bharatiya\s+sakshya\s+adhiniyam", r"\bBSA\b", r"भारतीय\s+साक्ष्य\s+अधिनियम"],
}
_KNOWN_ACT_RES: List[Tuple[str, "re.Pattern"]] = [
    (name, re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE))
    for name, patterns in _KNOWN_ACTS.items()
]

# Any other "... Act" written in Latin script with capitalised words.
_CONNECTORS = r"of|and|on|for|the|from|in|to"
_GENERIC_ACT_RE = re.compile(
    rf"\b((?:[A-Z][A-Za-z'’()&-]*\s+)(?:(?:[A-Z][A-Za-z'’()&-]*|{_CONNECTORS})\s+){{0,9}}Act)\b"
)
_ACT_LEADING_JUNK = {
    "under", "the", "as", "per", "in", "of", "and", "see", "by", "both", "also", "section", "sections",
    "this", "that", "said", "to", "from", "on", "for", "with", "further", "however", "act",
}

_PARTY = r"[A-Z][A-Za-z.'’-]*(?:\s+(?:[A-Z][A-Za-z.'’-]*|of|and|the|&)){0,5}"
_CASE_RE = re.compile(rf"({_PARTY})\s+(?:v\.|vs\.?|versus|v)\s+({_PARTY})")
_CASE_V_RE = re.compile(r"\b(?:v\.|vs\.?|versus|v)\s")
_CASE_STOPWORDS = {
    "in", "the", "of", "and", "state", "union", "india", "others", "ors", "anr", "another", "smt",
    "shri", "sri", "mrs", "mr", "dr", "govt", "government", "see", "case", "held", "court", "supreme",
    "high", "per", "also", "as", "under", "judgment", "judgement", "ruling",
}

_PAIR_WINDOW = 120  # in the sources: how far from a section number its act may be named
_ANSWER_PAIR_WINDOW = 60  # in the answer: a section is tied to an act only if they are this close


def _gap(a: "_Mention", b: "_Mention") -> int:
    """Characters between two mentions (0 if they touch or overlap)."""
    return max(0, a.start - b.end, b.start - a.end)


def _nearest_act(section: "_Mention", acts: List["_Mention"], window: int) -> Optional[str]:
    close = [a for a in acts if _gap(section, a) <= window]
    return min(close, key=lambda a: _gap(section, a)).value if close else None

# One entry of a source document's structured citation list: "498a indian penal code"
_STRUCTURED_CITATION_RE = re.compile(rf"^\s*(?:sections?\s*)?({_NUM})(?:\([0-9a-zA-Z]+\))*\s+(\D.*)$", re.IGNORECASE)

_ABBREVIATION_END = re.compile(
    r"(?:\b(?:v|vs|s|ss|sec|secs|no|nos|dr|mr|mrs|ms|smt|shri|art|cl|hon|ors|anr)\.|\bu/s\.|\br/w\.|^\s*\(?\d+[.)])$",
    re.IGNORECASE,
)


class GuardResult(NamedTuple):
    text: str            # the answer after the guard
    removed: List[str]   # citations whose sentences were removed, e.g. "section 22"
    flagged: List[str]   # citations kept but listed as unverified, e.g. "act Domestic Violence Act"


class _Mention(NamedTuple):
    start: int
    end: int
    value: str


def _normalize(text: str) -> str:
    return (text or "").translate(_DEVANAGARI_DIGITS)


def _numbers(listing: str) -> List[str]:
    return [n.upper() for n in re.findall(_NUM, re.sub(r"\([0-9a-zA-Z]+\)", "", listing))]


def _known_act_mentions(text: str) -> List[_Mention]:
    return [
        _Mention(m.start(), m.end(), name)
        for name, pattern in _KNOWN_ACT_RES
        for m in pattern.finditer(text)
    ]


def _generic_act_mentions(text: str, known: List[_Mention]) -> List[_Mention]:
    mentions = []
    for m in _GENERIC_ACT_RE.finditer(text):
        if any(k.start < m.end() and m.start() < k.end for k in known):
            continue  # already identified as a known act
        words = m.group(1).split()
        while len(words) > 1 and words[0].lower() in _ACT_LEADING_JUNK:
            words = words[1:]
        if len(words) >= 3:  # at least two name words before "Act"
            mentions.append(_Mention(m.start(), m.end(), " ".join(words)))
    return mentions


def _section_mentions(text: str, acts: List[_Mention]) -> List[_Mention]:
    """Every section number in *text*, one mention per number."""
    mentions = []
    for m in _SECTION_RE.finditer(text):
        mentions.extend(_Mention(m.start(), m.end(), n) for n in _numbers(m.group(1)))
    for act in acts:  # "498A IPC": numbers written directly before an act
        before = _NUM_BEFORE_ACT_RE.search(text[max(0, act.start - 40):act.start])
        if before:
            start = max(0, act.start - 40) + before.start()
            mentions.extend(
                _Mention(start, act.start, n) for n in _numbers(before.group(1))
                if not re.fullmatch(r"(?:18|19|20)\d\d", n)  # "the 2005 Domestic Violence Act" is a year
            )
    return mentions


def extract_sections(text: str) -> Set[str]:
    """Return the set of section numbers (upper-cased, e.g. '498A') mentioned in *text*."""
    text = _normalize(text)
    return {m.value for m in _section_mentions(text, _known_act_mentions(text))}


def _simplify(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def _citation_items(source_citations: Union[None, str, Iterable]) -> List[str]:
    """Flatten the retrieved documents' citation metadata (lists or comma-joined strings)."""
    if not source_citations:
        return []
    if isinstance(source_citations, str):
        source_citations = [source_citations]
    items: List[str] = []
    for entry in source_citations:
        if isinstance(entry, str):
            items.extend(part.strip() for part in entry.split(",") if part.strip())
        elif entry:
            items.extend(str(part).strip() for part in entry if str(part).strip())
    return items


class _Context:
    """What the retrieved context supports, computed once per answer.

    *source_citations* is the structured citation list stored with each
    retrieved document (e.g. "498a indian penal code"). Those are exact
    act-and-section pairs, so they are used as evidence alongside the text.
    """

    def __init__(self, text: str, source_citations: Union[None, str, Iterable] = None) -> None:
        text = _normalize(text)
        items = [_normalize(item) for item in _citation_items(source_citations)]
        self._lower = text.lower()
        self._simple = _simplify(text + " " + " ".join(items))
        acts = _known_act_mentions(text)
        self.known_acts = {a.value for a in acts}
        # section number -> for each place it occurs in the text, the act named
        # nearest to it (None if no act is close by)
        self.section_acts: Dict[str, List[Optional[str]]] = {}
        for section in _section_mentions(text, acts):
            self.section_acts.setdefault(section.value, []).append(_nearest_act(section, acts, _PAIR_WINDOW))
        # section number -> acts it is listed under in the documents' citation metadata
        self.listed_acts: Dict[str, Set[str]] = {}
        for item in items:
            item_acts = {a.value for a in _known_act_mentions(item)}
            self.known_acts |= item_acts
            structured = _STRUCTURED_CITATION_RE.match(item)
            if structured:
                self.listed_acts.setdefault(structured.group(1).upper(), set()).update(item_acts)

    def has_section(self, number: str) -> bool:
        return number in self.section_acts or number in self.listed_acts

    def has_act(self, name: str, known: bool) -> bool:
        return name in self.known_acts if known else _simplify(name) in self._simple

    def pair_contradicted(self, number: str, act: str) -> bool:
        """
        True when the sources tie this section number to other acts and never
        to *act*. The documents' citation lists are exact, so when one lists
        the number, a bare "section N" in the text (no act nearby) no longer
        counts as possible support. Without a listing, a bare mention gives
        the benefit of the doubt.
        """
        in_text = self.section_acts.get(number, [])
        listed = self.listed_acts.get(number, set())
        if act in listed or act in in_text:
            return False
        if listed:
            return True
        return bool(in_text) and all(nearest is not None for nearest in in_text)

    def has_case(self, left: Set[str], right: Set[str]) -> bool:
        for m in _CASE_V_RE.finditer(self._lower):
            before = set(re.findall(r"[a-z]+", self._lower[max(0, m.start() - 80):m.start()]))
            after = set(re.findall(r"[a-z]+", self._lower[m.end():m.end() + 80]))
            if left & before and right & after:
                return True
        return False


def _party_tokens(party: str) -> Set[str]:
    tokens = {t for t in re.findall(r"[a-z]+", party.lower()) if len(t) >= 3}
    return (tokens - _CASE_STOPWORDS) or tokens


def find_issues(sentence: str, context: _Context) -> List[Tuple[str, str]]:
    """Return [(kind, label)] for every citation in *sentence* the context does not support."""
    sentence = _normalize(sentence)
    issues: List[Tuple[str, str]] = []

    known = _known_act_mentions(sentence)
    generic = _generic_act_mentions(sentence, known)
    known_names = {a.value for a in known}

    for name in sorted(known_names):
        if not context.has_act(name, known=True):
            issues.append(("act", f"act {name}"))
    for name in sorted({a.value for a in generic}):
        if not context.has_act(name, known=False):
            issues.append(("act", f"act {name}"))

    seen_sections: Set[str] = set()
    for section in _section_mentions(sentence, known):
        if not context.has_section(section.value):
            if section.value not in seen_sections:
                issues.append(("section", f"section {section.value}"))
                seen_sections.add(section.value)
            continue
        cited_under = _nearest_act(section, known, _ANSWER_PAIR_WINDOW)
        if cited_under is None:
            continue
        label = f"section {section.value} of {cited_under}"
        if context.pair_contradicted(section.value, cited_under) and ("pair", label) not in issues:
            issues.append(("pair", label))

    for m in _CASE_RE.finditer(sentence):
        left, right = _party_tokens(m.group(1)), _party_tokens(m.group(2))
        if left and right and not context.has_case(left, right):
            issues.append(("case", f"case {' '.join(m.group(0).split())}"))

    return issues


def split_sentences(line: str) -> List[str]:
    """Split a line into sentences without breaking at "v.", "s.", "Sec." or list numbers."""
    sentences: List[str] = []
    for part in re.split(rf"(?<=[{_SENTENCE_END}])\s+", line):
        if sentences and _ABBREVIATION_END.search(sentences[-1]):
            sentences[-1] += " " + part
        else:
            sentences.append(part)
    return sentences


def sanitize_citations(
    answer: str,
    context_text: str,
    language: str = "en",
    mode: str = "mixed",
    source_citations: Union[None, str, Iterable] = None,
) -> GuardResult:
    """
    Check every citation in *answer* against *context_text* (and the retrieved
    documents' structured *source_citations*, if given) and apply *mode*.

    If nothing is unverified the answer is returned untouched. If every
    sentence would be removed the original answer is kept, so the user never
    gets an empty reply.
    """
    remove_kinds = MODES.get(mode, MODES["mixed"])
    context = _Context(context_text, source_citations)
    removed: List[str] = []
    flagged: List[str] = []
    kept_lines: List[str] = []

    for line in answer.split("\n"):
        kept = []
        for sentence in split_sentences(line):
            issues = find_issues(sentence, context)
            blocking = [label for kind, label in issues if kind in remove_kinds]
            if blocking:
                removed.extend(blocking)
            else:
                flagged.extend(label for _, label in issues)
                kept.append(sentence)
        kept_lines.append(" ".join(kept))

    removed = sorted(set(removed))
    flagged = sorted(set(flagged))
    if not removed and not flagged:
        return GuardResult(answer, [], [])

    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines)).strip() if removed else answer.strip()
    if not cleaned:
        return GuardResult(answer, [], [])

    lang = language if language in REMOVED_NOTE else "en"
    if removed:
        cleaned += "\n\n" + REMOVED_NOTE[lang]
    if flagged:
        items = "; ".join(label.split(" ", 1)[1] for label in flagged)
        cleaned += "\n\n" + FLAGGED_NOTE[lang].format(items=items)
    return GuardResult(cleaned, removed, flagged)


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
