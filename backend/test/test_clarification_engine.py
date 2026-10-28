"""
Offline tests for the clarification / information-gathering loop.

The LLM calls are replaced with stubs, so these run without network access.
test/live_clarification_flow.py exercises the same loop against the real models.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import graph
from llm_utils import extract_json, strip_think
from nodes.information_gatherer import InformationGatherer


# ── llm_utils ─────────────────────────────────────────────────────────────────

def test_strip_think_removes_closed_and_unclosed_blocks():
    assert strip_think("<think>plan</think>Answer") == "Answer"
    # MiniMax hitting max_tokens mid-thought: nothing of the thought may leak
    assert strip_think("<think>still reasoning about the client") == ""


def test_extract_json_handles_fences_and_prose():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure, here it is: {"a": 2} hope that helps') == {"a": 2}
    assert extract_json('<think>x</think>{"a": 3}') == {"a": 3}


# ── InformationGatherer ───────────────────────────────────────────────────────

@pytest.fixture
def gatherer(monkeypatch):
    g = InformationGatherer()
    monkeypatch.setattr(g, "_generate_question", lambda **kw: f"Q about {kw['current_target']}?")
    # no model call: ask the first open item
    monkeypatch.setattr(
        g, "_choose_and_ask",
        lambda **kw: (kw["remaining"][0], f"Q about {kw['remaining'][0]['field']}?"),
    )
    return g


def base_state(**overrides):
    state = {
        "query": "My husband left and stopped paying. I want maintenance.",
        "root_query": "My husband left and stopped paying. I want maintenance.",
        "info_collected": {},
        "info_needed_list": [
            {"field": "religion", "reason": "decides the Act"},
            {"field": "son_age", "reason": "duration of support"},
        ],
        "gathering_step": 0,
        "questions_asked": 0,
        "awaiting_answer": False,
        "current_question_target": None,
        "user_gender": "unknown",
    }
    state.update(overrides)
    return state


def test_first_step_asks_without_extracting(gatherer, monkeypatch):
    monkeypatch.setattr(gatherer, "_extract_information", lambda **kw: pytest.fail("nothing to extract yet"))
    out = gatherer.gather_next_information(base_state())
    assert out["needs_more_info"] is True
    assert out["current_question_target"] == "religion"
    assert out["awaiting_answer"] is True
    assert out["questions_asked"] == 1


def test_reply_is_read_from_this_turns_query(gatherer, monkeypatch):
    seen = {}

    def fake_extract(last_question, user_response, info_target):
        seen.update(question=last_question, response=user_response, target=info_target)
        return "The client is Hindu."

    monkeypatch.setattr(gatherer, "_extract_information", fake_extract)
    out = gatherer.gather_next_information(base_state(
        query="We are Hindu",
        awaiting_answer=True,
        current_question_target="religion",
        follow_up_question="What is your religion?",
        gathering_step=1,
        questions_asked=1,
    ))
    assert seen == {"question": "What is your religion?", "response": "We are Hindu", "target": "religion"}
    assert out["info_collected"]["religion"] == "The client is Hindu."
    assert out["current_question_target"] == "son_age"
    assert [i["field"] for i in out["info_needed_list"]] == ["son_age"]


def test_unanswered_question_is_recorded_and_not_asked_again(gatherer, monkeypatch):
    monkeypatch.setattr(gatherer, "_extract_information", lambda **kw: "NOT_PROVIDED")
    out = gatherer.gather_next_information(base_state(
        query="I prefer not to say",
        awaiting_answer=True,
        current_question_target="religion",
        gathering_step=1,
        questions_asked=1,
    ))
    assert out["info_collected"]["religion"] == InformationGatherer.NOT_PROVIDED_TEXT
    assert out["current_question_target"] == "son_age"


def test_new_field_after_revalidation_does_not_reuse_old_reply(gatherer, monkeypatch):
    # Re-validation added a field; the last reply was already consumed, so
    # awaiting_answer is False and the old reply must not be extracted again.
    monkeypatch.setattr(gatherer, "_extract_information", lambda **kw: pytest.fail("reply already consumed"))
    out = gatherer.gather_next_information(base_state(
        query="He is 6",
        info_collected={"religion": "Hindu", "son_age": "6"},
        info_needed_list=[{"field": "existing_cases", "reason": ""}],
        awaiting_answer=False,
        gathering_step=2,
        questions_asked=2,
    ))
    assert out["current_question_target"] == "existing_cases"


def test_question_budget_stops_gathering(gatherer):
    out = gatherer.gather_next_information(base_state(
        questions_asked=InformationGatherer.MAX_FOLLOW_UP_QUESTIONS,
    ))
    assert out["needs_more_info"] is False
    assert out["awaiting_answer"] is False


def test_whole_word_gender_matching(gatherer):
    assert gatherer._normalize_gender("I am the wife") == "female"
    assert gatherer._normalize_gender("the husband") == "male"
    # "the" contains "he" but is not a gender word
    assert gatherer._normalize_gender("the other one") == "the other one"


# ── analyze_query_node clarification rounds ───────────────────────────────────

def test_clarification_reply_is_analysed_with_the_earlier_message(monkeypatch):
    calls = []
    responses = iter([
        {"intent_confidence": "low", "user_intent": "", "clarification_question": "What happened?"},
        {"intent_confidence": "high", "user_intent": "Maintenance for son",
         "info_needed_list": [], "has_sufficient_info": True, "info_collected": {}},
    ])

    def fake_analyze(self, state):
        calls.append(state["query"])
        return next(responses)

    monkeypatch.setattr(graph.QueryAnalyzer, "analyze_query", fake_analyze)

    state = graph.analyze_query_node({"query": "hi", "messages": []})
    assert state["needs_clarification"] is True
    assert state["clarification_question"] == "What happened?"

    state["query"] = "my husband stopped paying for our son"
    state = graph.analyze_query_node(state)
    assert calls[1] == "hi\nmy husband stopped paying for our son"
    assert state["needs_clarification"] is False
    assert state["root_query"] == "hi\nmy husband stopped paying for our son"
    assert graph.route_after_analysis(state) == "retrieve"


def test_clarification_stops_after_max_rounds(monkeypatch):
    monkeypatch.setattr(
        graph.QueryAnalyzer, "analyze_query",
        lambda self, state: {"intent_confidence": "low", "user_intent": ""},
    )
    state = {"query": "hmm", "messages": []}
    for _ in range(graph.MAX_CLARIFICATION_ROUNDS):
        state = graph.analyze_query_node(state)
        assert graph.route_after_analysis(state) == "clarify"
        state["query"] = "not sure"
    state = graph.analyze_query_node(state)
    assert graph.route_after_analysis(state) == "retrieve"


def test_described_non_answer_counts_as_not_provided(gatherer, monkeypatch):
    # qwen sometimes describes the gap instead of returning NOT_PROVIDED
    monkeypatch.setattr(gatherer, "_extract_information",
                        lambda **kw: "The client did not confirm their religion, only that the son is 6.")
    out = gatherer.gather_next_information(base_state(
        query="My son is 6 years old",
        awaiting_answer=True,
        current_question_target="religion",
        gathering_step=1,
        questions_asked=1,
    ))
    assert out["info_collected"]["religion"] == InformationGatherer.NOT_PROVIDED_TEXT
    # the volunteered fact survives for the next question to see
    assert "My son is 6 years old" in out["info_collected"]["additional_info"]


def test_every_reply_is_kept_in_the_clients_words(gatherer, monkeypatch):
    monkeypatch.setattr(gatherer, "_extract_information", lambda **kw: "The client is Hindu.")
    out = gatherer.gather_next_information(base_state(
        query="We are Hindu, and my son is 6",
        awaiting_answer=True,
        current_question_target="religion",
        gathering_step=1,
        questions_asked=1,
    ))
    assert out["info_collected"]["religion"] == "The client is Hindu."
    assert "my son is 6" in out["info_collected"]["additional_info"]


# ── reply coverage: one reply can answer several open gaps ────────────────────

def test_reply_answering_other_open_gaps_removes_them(gatherer, monkeypatch):
    monkeypatch.setattr(gatherer, "_extract_information", lambda **kw: "Neither of us was married before.")
    monkeypatch.setattr(
        gatherer, "_extract_other_answers",
        lambda question, reply, open_items: {"any_children": "They have no children."},
    )
    out = gatherer.gather_next_information(base_state(
        query="No, neither of us was married before. No children either.",
        info_needed_list=[
            {"field": "prior_marriage", "reason": ""},
            {"field": "any_children", "reason": ""},
            {"field": "safety_concerns", "reason": ""},
        ],
        awaiting_answer=True,
        current_question_target="prior_marriage",
        follow_up_question="Has either of you been married before?",
        gathering_step=1,
        questions_asked=1,
    ))
    assert out["info_collected"]["any_children"] == "They have no children."
    assert out["current_question_target"] == "safety_concerns"
    assert [i["field"] for i in out["info_needed_list"]] == ["safety_concerns"]


def test_other_answers_ignore_unknown_fields_and_non_answers(gatherer, monkeypatch):
    class Reply:
        content = ('{"answers": {"any_children": "No children.", "not_a_field": "x", '
                   '"income": "The client did not say what he earns."}}')

    import nodes.information_gatherer as module
    monkeypatch.setattr(module, "invoke_llm", lambda *a, **kw: Reply())
    found = gatherer._extract_other_answers(
        "Any prior marriage?", "No. No children either.",
        [{"field": "any_children"}, {"field": "income"}],
    )
    assert found == {"any_children": "No children."}


def test_other_answers_failure_is_harmless(gatherer, monkeypatch):
    import nodes.information_gatherer as module

    def boom(*a, **kw):
        raise RuntimeError("all providers down")

    monkeypatch.setattr(module, "invoke_llm", boom)
    assert gatherer._extract_other_answers("q", "reply", [{"field": "a"}]) == {}


# ── gaps repeated under another name; one question at a time ──────────────────

def test_gap_repeated_under_another_field_name_is_known():
    from nodes.query_analyzer import gap_is_known
    assert gap_is_known({"field": "marriage_date", "label": "Date of marriage"}, ["date_of_marriage"])
    assert gap_is_known({"field": "current_residence_city_state"}, ["residence_city_state"])
    # different people, same topic: not a duplicate
    assert not gap_is_known({"field": "partner_income"}, ["client_income"])
    assert not gap_is_known({"field": "any_children"}, ["prior_marriage"])


def test_revalidation_does_not_reask_a_collected_fact(monkeypatch):
    monkeypatch.setattr(
        graph.QueryAnalyzer, "analyze_query",
        lambda self, state, mode="intake": {
            "info_needed_list": [{"field": "marriage_date", "label": "Date of marriage", "reason": ""}],
        },
    )
    state = graph.revalidate_information_node({
        "query": "x", "root_query": "my husband beats me",
        "info_collected": {"date_of_marriage": "14 Feb 2021"},
        "info_needed_list": [], "needs_more_info": False,
    })
    assert state["has_sufficient_info"] is True


def test_question_validator_rejects_multi_part_and_notes(gatherer):
    gatherer._check_question("How old is your son?")
    with pytest.raises(ValueError):
        gatherer._check_question("How old is your son? And where does he live now?")
    with pytest.raises(ValueError):
        gatherer._check_question("Is the house in your name, or jointly owned, or sold, " + "and so on " * 60 + "?")
    with pytest.raises(ValueError):
        gatherer._check_question("The client has already said she lives in Pune?")


# ── the model picks which gap to ask about ────────────────────────────────────

class _Reply:
    def __init__(self, content):
        self.content = content


def _real_gatherer():
    return InformationGatherer()


OPEN = [
    {"field": "marriage_date", "label": "Date of marriage", "reason": "limitation"},
    {"field": "second_marriage_proof", "label": "Proof of the second marriage", "reason": "bigamy"},
]


def test_choice_parser_accepts_known_field_and_rejects_unknown():
    g = _real_gatherer()
    field, question = g._parse_choice(
        '{"field": "second_marriage_proof", "question": "Do you have any proof of his second marriage?"}',
        {"marriage_date", "second_marriage_proof"},
    )
    assert field == "second_marriage_proof" and question.endswith("?")
    with pytest.raises(ValueError):
        g._parse_choice('{"field": "made_up", "question": "Anything?"}', {"marriage_date"})
    with pytest.raises(ValueError):  # two questions in one
        g._parse_choice('{"field": "marriage_date", "question": "When? And where?"}', {"marriage_date"})


def test_model_can_ask_about_a_later_gap_first(monkeypatch):
    import nodes.information_gatherer as module
    monkeypatch.setattr(
        module, "invoke_llm",
        lambda *a, **kw: _Reply('{"field": "second_marriage_proof", "question": "Do you have any proof of his second marriage?"}'),
    )
    item, question = _real_gatherer()._choose_and_ask(
        name="the client", gender="unknown", root_query="my husband remarried", user_intent="bigamy",
        info_collected={}, remaining=OPEN, detected_lang="en", document="", asked_questions=[],
    )
    assert item["field"] == "second_marriage_proof"
    assert question == "Do you have any proof of his second marriage?"


def test_choice_failure_falls_back_to_the_first_open_item(monkeypatch):
    import nodes.information_gatherer as module

    def boom(*a, **kw):
        raise RuntimeError("all providers down")

    monkeypatch.setattr(module, "invoke_llm", boom)
    g = _real_gatherer()
    monkeypatch.setattr(g, "_generate_question", lambda **kw: "When did you marry?")
    item, question = g._choose_and_ask(
        name="the client", gender="unknown", root_query="x", user_intent="x",
        info_collected={}, remaining=OPEN, detected_lang="en", document="", asked_questions=[],
    )
    assert item["field"] == "marriage_date" and question == "When did you marry?"


def test_chosen_gap_becomes_the_current_target(monkeypatch):
    g = _real_gatherer()
    monkeypatch.setattr(g, "_choose_and_ask", lambda **kw: (kw["remaining"][1], "Proof of the second marriage?"))
    out = g.gather_next_information(base_state(info_needed_list=OPEN))
    assert out["current_question_target"] == "second_marriage_proof"
    assert out["info_needed_list"][0]["field"] == "second_marriage_proof"


def test_first_person_message_is_never_treated_as_a_general_question():
    from nodes.query_analyzer import FIRST_PERSON_RE
    for personal in (
        "I am a 38-year-old unmarried woman and I want to adopt a baby girl. Is that possible?",
        "My husband left me two years ago",
        "Can I stop my wife taking our daughter abroad?",
        "We got married in a temple 5 years ago",
    ):
        assert FIRST_PERSON_RE.search(personal), personal
    for textbook in (
        "What is the difference between judicial separation and divorce under the Hindu Marriage Act?",
        "What income affidavit does the Supreme Court require from husband and wife in maintenance cases?",
        "Can a wife claim maintenance under Section 125 CrPC?",
    ):
        assert not FIRST_PERSON_RE.search(textbook), textbook


# ── a rich answer must not end the interview before the minimum number of questions ──

def test_revalidation_looks_again_while_fewer_than_the_minimum_were_asked(monkeypatch):
    seen = {}

    def fake_analyze(self, state, mode="intake"):
        seen["mode"] = mode
        seen["asked"] = state.get("questions_asked")
        return {"info_needed_list": [{"field": "documents_held", "label": "Documents you hold", "reason": ""}]}

    monkeypatch.setattr(graph.QueryAnalyzer, "analyze_query", fake_analyze)
    rich = {f"fact_{i}": "x" for i in range(9)}           # 9 facts collected, but only 3 questions asked
    state = graph.revalidate_information_node({
        "query": "x", "root_query": "my husband stopped paying",
        "info_collected": rich, "info_needed_list": [], "needs_more_info": False,
        "questions_asked": 3, "query_type": "personal_situation",
    })
    assert seen == {"mode": "revalidate", "asked": 3}
    assert state["needs_more_info"] is True and state["in_gathering_phase"] is True


def test_revalidation_stops_once_the_minimum_was_asked_and_facts_are_plentiful(monkeypatch):
    monkeypatch.setattr(
        graph.QueryAnalyzer, "analyze_query",
        lambda *a, **kw: pytest.fail("no more questions needed"),
    )
    rich = {f"fact_{i}": "x" for i in range(9)}
    state = graph.revalidate_information_node({
        "query": "x", "root_query": "x", "info_collected": rich, "info_needed_list": [],
        "needs_more_info": False, "questions_asked": 6, "query_type": "personal_situation",
    })
    assert state["has_sufficient_info"] is True and state["needs_more_info"] is False


def test_fallback_analysis_still_interviews_a_person_describing_their_own_case():
    from nodes.query_analyzer import QueryAnalyzer
    qa = QueryAnalyzer.__new__(QueryAnalyzer)
    qa.max_questions = 8
    qa.min_questions = 5
    personal = qa.fallback_analysis("My husband hits me and threatens to throw me out of the house.")
    assert personal["info_needed_list"], "no interview when every model failed"
    assert personal["query_type"] == "personal_situation"
    assert personal["has_sufficient_info"] is False
    general = qa.fallback_analysis("What does the law say about domestic violence?")
    assert general["info_needed_list"] == []
