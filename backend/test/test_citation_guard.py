from citation_guard import (
    excerpt_in_source,
    extract_sections,
    sanitize_citations,
    split_sentences,
    trim_to_last_sentence,
)

CONTEXT = (
    "Expert: file under Section 498A IPC and Sections 125 and 13 of HMA for maintenance. "
    "The Hindu Marriage Act allows divorce under section 13. See Amardeep Singh v. Harveen Kaur (2017)."
)


# ── section numbers (original behaviour) ─────────────────────────────────────

def test_extract_sections_handles_lists_and_hindi():
    assert extract_sections("Sections 498A and 323, s.13") == {"498A", "323", "13"}
    assert extract_sections("धारा २२ और धारा 498A") == {"22", "498A"}


def test_extract_sections_reads_numbers_written_before_an_act():
    assert extract_sections("booked u/s 406 and also 498a/323 IPC, plus 125 of the CrPC") == {"406", "498A", "323", "125"}
    assert extract_sections("the 2005 Domestic Violence Act") == set()


def test_unverified_section_sentence_is_removed():
    answer = "पत्नी को धारा 22 के तहत अधिकार है। आप वकील से मिलें।"
    result = sanitize_citations(answer, CONTEXT, "hi")
    assert result.removed == ["section 22"]
    assert "धारा 22" not in result.text
    assert "वकील से मिलें" in result.text
    assert "नोट" in result.text


def test_verified_citations_untouched():
    answer = "You can file under Section 498A IPC. See Amardeep Singh v. Harveen Kaur. Consult a lawyer."
    result = sanitize_citations(answer, CONTEXT, "en", mode="strict")
    assert result.text == answer and result.removed == [] and result.flagged == []


def test_never_returns_empty():
    result = sanitize_citations("Section 999 applies.", CONTEXT, "en")
    assert result.text == "Section 999 applies." and result.removed == []


# ── act names ────────────────────────────────────────────────────────────────

def test_unverified_act_is_flagged_in_mixed_mode_and_removed_in_strict():
    answer = "You have rights under the Domestic Violence Act. Consult a lawyer."
    mixed = sanitize_citations(answer, CONTEXT, "en", mode="mixed")
    assert mixed.removed == [] and mixed.flagged == ["act Protection of Women from Domestic Violence Act"]
    assert "Domestic Violence Act." in mixed.text and "could not be verified" in mixed.text

    strict = sanitize_citations(answer, CONTEXT, "en", mode="strict")
    assert strict.removed == ["act Protection of Women from Domestic Violence Act"]
    assert "Domestic Violence" not in strict.text.split("(Note")[0]


def test_act_aliases_and_hindi_names_match_the_context():
    answer = "हिंदू विवाह अधिनियम के तहत तलाक संभव है। भारतीय दंड संहिता भी लागू होती है।"
    result = sanitize_citations(answer, CONTEXT, "hi", mode="strict")
    assert result.removed == [] and result.text == answer


def test_unknown_act_in_latin_script_is_checked_by_name():
    result = sanitize_citations("The Transfer of Property Act governs this.", CONTEXT, "en", mode="mixed")
    assert result.flagged == ["act Transfer of Property Act"]
    ok = sanitize_citations("The Transfer of Property Act governs this.", CONTEXT + " transfer of property act", "en")
    assert ok.flagged == []


# ── act + section pairs ──────────────────────────────────────────────────────

def test_section_under_the_wrong_act_is_removed():
    context = "Expert: daughters are coparceners under section 6 of the Hindu Succession Act."
    answer = "Section 6 of the Hindu Marriage Act gives daughters a share. Consult a lawyer."
    far_away = " Unrelated discussion." * 10 + " The Hindu Marriage Act covers divorce."
    result = sanitize_citations(answer, context + far_away, "en")
    assert result.removed == ["section 6 of Hindu Marriage Act"]
    assert result.text.startswith("Consult a lawyer.")

    # Another act named close by does not rescue it: the section is tied to its nearest act.
    nearby = sanitize_citations(answer, context + " The Hindu Marriage Act also exists.", "en")
    assert nearby.removed == ["section 6 of Hindu Marriage Act"]


def test_section_far_from_any_act_in_the_answer_is_not_paired():
    context = "Expert: daughters are coparceners under section 6 of the Hindu Succession Act." + " Filler." * 30 + " The Indian Penal Code punishes bigamy."
    answer = "Section 6 gives daughters a share, and this has been settled for years across many courts, quite apart from offences under the IPC."
    assert sanitize_citations(answer, context, "en", mode="strict").removed == []


def test_section_without_an_act_in_the_context_is_given_the_benefit_of_the_doubt():
    context = "Expert: you can claim maintenance under section 125. CrPC applies."
    padded = context.replace(". CrPC", "." + " x" * 80 + " CrPC")
    result = sanitize_citations("Claim maintenance under Section 125 CrPC.", padded, "en", mode="strict")
    assert result.removed == []


# ── case names ───────────────────────────────────────────────────────────────

def test_invented_case_is_removed_but_a_real_one_is_kept():
    answer = "As held in Ramesh Kumar v. Sunita Devi, she wins. See Amardeep Singh vs Harveen Kaur."
    result = sanitize_citations(answer, CONTEXT, "en")
    assert result.removed == ["case Ramesh Kumar v. Sunita Devi"]
    assert "Amardeep Singh vs Harveen Kaur" in result.text


def test_flag_mode_only_removes_sections():
    answer = "As held in Ramesh Kumar v. Sunita Devi, she wins. Section 999 applies. Fine."
    result = sanitize_citations(answer, CONTEXT, "en", mode="flag")
    assert result.removed == ["section 999"]
    assert result.flagged == ["case Ramesh Kumar v. Sunita Devi"]


# ── sentence handling ────────────────────────────────────────────────────────

def test_split_sentences_keeps_abbreviations_and_list_numbers_together():
    assert split_sentences("See Singh v. Kaur for this. Next point.") == ["See Singh v. Kaur for this.", "Next point."]
    assert split_sentences("1. File under s. 13 today. Done.") == ["1. File under s. 13 today.", "Done."]


def test_trim_to_last_sentence():
    assert trim_to_last_sentence("पहला वाक्य। दूसरा वाक्य। तीसरा अधू") == "पहला वाक्य। दूसरा वाक्य।"


def test_excerpt_must_come_from_source():
    source = "Since it is your father's house even you require the permission of your father."
    assert excerpt_in_source("even you require the permission of your father", source)
    assert not excerpt_in_source("पत्नी के पास अपने पति के खिलाफ कार्रवाई करने का अधिकार है", source)


# ── structured citations from the retrieved documents ───────────────────────

def test_structured_citations_count_as_evidence():
    context = "Expert: you should file a case for cruelty and ask for maintenance."
    answer = "File under Section 498A IPC. Claim maintenance under Section 125 CrPC. Consult a lawyer."
    without = sanitize_citations(answer, context, "en")
    assert without.removed == ["section 125", "section 498A"]
    with_meta = sanitize_citations(
        answer, context, "en", mode="strict",
        source_citations=["498a indian penal code, 125 code of criminal procedure"],
    )
    assert with_meta.removed == [] and with_meta.text == answer


def test_structured_citations_expose_a_wrong_act():
    answer = "Maintenance is available under Section 125 of the Hindu Marriage Act. Consult a lawyer."
    result = sanitize_citations(
        answer, "Expert: the Hindu Marriage Act governs divorce." + " Other text." * 20, "en",
        source_citations=[["125 code of criminal procedure", "13 hindu marriage act"]],
    )
    assert result.removed == ["section 125 of Hindu Marriage Act"]
