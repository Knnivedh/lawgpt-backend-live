import pytest

from corpus_curation import EXCLUDED_PARENT_IDS, SAME_SUBJECT_GROUPS, subject_key
from keyword_search import KeywordIndex, reciprocal_rank_fusion, tokenize
from translation_client import QueryTranslator, TranslationError


def build_index():
    index = KeywordIndex()
    index.add(1, "Child custody", "Who gets custody of the child after divorce", "family_law")
    index.add(2, "Divorce in USA", "Married in India, divorce filed in the USA, is it valid", "family_law")
    index.add(3, "Prohibition of Child Marriage Act, 2006", "Minimum age of marriage is 18 for women", "family_law_2")
    index.add(4, "Maintenance", "Wife claims maintenance under section 125", "family_law")
    index.finalize()
    return index


def test_tokenize_drops_stopwords_and_plurals():
    assert tokenize("What are the rights of daughters in properties?") == ["right", "daughter", "property"]


def test_distinctive_term_beats_common_words():
    results = build_index().search("How is child custody decided after divorce in India?", limit=2)
    assert results[0][0] == 1


def test_category_filter_and_exclusion():
    index = build_index()
    assert [d for d, _ in index.search("child marriage age", 5, categories=["family_law_2"])] == [3]
    assert 1 not in [d for d, _ in index.search("child custody", 5, exclude_ids={1})]


def test_empty_index_and_unknown_terms():
    assert KeywordIndex().search("custody", 5) == []
    assert build_index().search("zzzz qqqq", 5) == []


def test_reciprocal_rank_fusion_prefers_documents_in_both_lists():
    assert reciprocal_rank_fusion([[10, 20, 30], [30, 40, 10]])[:2] == [10, 30]


def test_subject_groups_are_disjoint_and_not_excluded():
    seen = set()
    for group in SAME_SUBJECT_GROUPS:
        assert not (group & seen) and not (group & EXCLUDED_PARENT_IDS)
        seen |= group
    assert subject_key(2930) == subject_key(2952)
    assert subject_key(7) == 7 and subject_key(None) is None


class FakeTranslator(QueryTranslator):
    def __init__(self, output):
        super().__init__("model", "key")
        self._output = output

    def _ask(self, system_prompt, text):
        return self._output


def test_falls_back_to_next_provider():
    class Flaky(QueryTranslator):
        def _invoke(self, provider, messages):
            if provider == "first":
                raise RuntimeError("402 Payment Required")
            return "translated text"

    assert Flaky("model", "key", ["first", "second"]).translate("पाठ") == "translated text"
    with pytest.raises(TranslationError):
        Flaky("model", "key", ["first"]).translate("पाठ")


def test_prepare_search_parses_two_lines():
    out = FakeTranslator("ENGLISH: My mother-in-law evicted me.\nSEARCH: wife's right of residence in matrimonial home.")
    result = out.prepare_search("x")
    assert result.english == "My mother-in-law evicted me."
    assert result.search_query == "wife's right of residence in matrimonial home"


def test_prepare_search_rejects_malformed_output():
    with pytest.raises(TranslationError):
        FakeTranslator("Here is some advice about your case.").prepare_search("x")


def test_prepare_search_keeps_english_input_when_model_skips_the_copy():
    result = FakeTranslator("SEARCH: child custody determination after divorce.").prepare_search("How is custody decided?")
    assert result.english == "How is custody decided?"
    assert result.search_query == "child custody determination after divorce"


def test_prepare_search_needs_translation_line_for_non_english_input():
    with pytest.raises(TranslationError):
        FakeTranslator("SEARCH: child custody after divorce.").prepare_search("तलाक के बाद कस्टडी किसे मिलती है?")
