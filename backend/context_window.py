"""
context_window.py - trim a long parent document for the generator.

Parents are stored whole. A long one is cut to a budget, but instead of
keeping only its beginning (which can drop the very passage that matched the
search), keep the opening of the document (the question) plus a window around
the matched passage.
"""

ELLIPSIS = "\n[...]\n"


def trim_around_match(parent_text: str, matched_text: str, max_chars: int, head_chars: int) -> str:
    parent_text = parent_text or ""
    if len(parent_text) <= max_chars:
        return parent_text

    probe = (matched_text or "").strip()[:200]
    position = parent_text.find(probe) if probe else -1
    if position < 0 or position + len(matched_text or "") <= max_chars:
        return parent_text[:max_chars] + ELLIPSIS.rstrip("\n")

    window = max_chars - head_chars
    start = max(head_chars, position - window // 4)
    end = min(len(parent_text), start + window)
    start = max(head_chars, end - window)
    tail = "" if end == len(parent_text) else ELLIPSIS.rstrip("\n")
    return parent_text[:head_chars] + ELLIPSIS + parent_text[start:end] + tail
