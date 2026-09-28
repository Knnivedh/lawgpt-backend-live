from citation_guard import (
    excerpt_in_source,
    extract_sections,
    sanitize_citations,
    trim_to_last_sentence,
)

CONTEXT = "Expert: file under Section 498A IPC and Sections 125 and 13 of HMA for maintenance."


def test_extract_sections_handles_lists_and_hindi():
    assert extract_sections("Sections 498A and 323, s.13") == {"498A", "323", "13"}
    assert extract_sections("धारा २२ और धारा 498A") == {"22", "498A"}


def test_unverified_section_sentence_is_removed():
    answer = "पत्नी को धारा 22 के तहत अधिकार है। आप वकील से मिलें।"
    cleaned, removed = sanitize_citations(answer, CONTEXT, "hi")
    assert removed == ["22"]
    assert "धारा 22" not in cleaned
    assert "वकील से मिलें" in cleaned
    assert "नोट" in cleaned


def test_verified_sections_untouched():
    answer = "You can file under Section 498A. Consult a lawyer."
    cleaned, removed = sanitize_citations(answer, CONTEXT, "en")
    assert cleaned == answer and removed == []


def test_never_returns_empty():
    cleaned, removed = sanitize_citations("Section 999 applies.", CONTEXT, "en")
    assert cleaned == "Section 999 applies." and removed == []


def test_trim_to_last_sentence():
    assert trim_to_last_sentence("पहला वाक्य। दूसरा वाक्य। तीसरा अधू") == "पहला वाक्य। दूसरा वाक्य।"


def test_excerpt_must_come_from_source():
    source = "Since it is your father's house even you require the permission of your father."
    assert excerpt_in_source("even you require the permission of your father", source)
    assert not excerpt_in_source("पत्नी के पास अपने पति के खिलाफ कार्रवाई करने का अधिकार है", source)
