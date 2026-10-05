from context_window import trim_around_match


def test_short_parent_is_untouched():
    assert trim_around_match("short text", "text", 100, 20) == "short text"


def test_match_near_the_start_keeps_the_head():
    parent = "Q" * 50 + "MATCH" + "x" * 500
    out = trim_around_match(parent, "MATCH", 100, 20)
    assert out.startswith(parent[:100]) and "MATCH" in out


def test_match_deep_in_the_document_is_kept_with_the_question():
    parent = "QUESTION " + "a" * 1000 + "THE MATCHED PASSAGE" + "b" * 1000
    out = trim_around_match(parent, "THE MATCHED PASSAGE", 300, 50)
    assert out.startswith("QUESTION ") and "THE MATCHED PASSAGE" in out
    assert len(out) <= 300 + 20


def test_unknown_match_falls_back_to_the_head():
    parent = "a" * 1000
    assert trim_around_match(parent, "zzz", 100, 20).startswith("a" * 100)
