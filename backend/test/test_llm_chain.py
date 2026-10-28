"""
Offline tests for llm_utils.invoke_llm: provider chain, rate-limit waiting, validation.
The model call is stubbed, so no network or API keys are needed.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import llm_utils


class Reply:
    def __init__(self, content):
        self.content = content


class FakeSettings:
    llm_chain = "groq:model-a,groq:model-b"
    llm_chain_fast = "groq:fast-a,groq:fast-b"
    llm_chain_analyze = "groq:analyze-a,groq:analyze-b"
    groq_api_key = "test-key"
    openrouter_api_keys = ""
    dahl_api_key = ""
    dahl_api_key_2 = ""
    dahl_base_url = ""


@pytest.fixture
def chain(monkeypatch):
    """Patch settings, sleep and the model call; returns (calls, sleeps, script)."""
    calls, sleeps = [], []
    script = []  # list of Reply or Exception, consumed per call

    def fake_invoke(llm, messages, deadline):
        calls.append(llm.model_name)
        step = script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    monkeypatch.setattr("config.get_settings", lambda: FakeSettings)
    monkeypatch.setattr(llm_utils, "invoke_with_deadline", fake_invoke)
    monkeypatch.setattr(llm_utils.time, "sleep", lambda s: sleeps.append(s))
    return calls, sleeps, script


def test_retry_after_is_read_from_the_message():
    assert llm_utils._retry_after_seconds(Exception("Rate limit reached. Please try again in 2.5s.")) == 2.5
    assert llm_utils._retry_after_seconds(Exception("429: try again in 400ms")) == pytest.approx(0.4)
    assert llm_utils._retry_after_seconds(Exception("boom")) is None


def test_short_rate_limit_is_waited_out_on_the_same_model(chain):
    calls, sleeps, script = chain
    script += [Exception("Error code: 429 - Rate limit reached. Please try again in 1.0s"), Reply("ok")]
    reply = llm_utils.invoke_llm([], purpose="main")
    assert reply.content == "ok"
    assert calls == ["model-a", "model-a"]
    assert sleeps and sleeps[0] >= 1.0


def test_long_rate_limit_moves_to_the_next_model_without_waiting(chain):
    calls, sleeps, script = chain
    script += [Exception("Error code: 429 - Rate limit reached. Please try again in 45.0s"), Reply("ok")]
    llm_utils.invoke_llm([], purpose="main")
    assert calls == ["model-a", "model-b"]
    assert not sleeps


def test_other_errors_move_on_and_are_not_retried(chain):
    calls, sleeps, script = chain
    script += [RuntimeError("model not found"), Reply("ok")]
    llm_utils.invoke_llm([], purpose="main")
    assert calls == ["model-a", "model-b"]
    assert not sleeps


def test_invalid_reply_fails_over(chain):
    calls, _, script = chain
    script += [Reply("not json at all"), Reply('{"a": 1}')]
    reply = llm_utils.invoke_llm([], purpose="main", validate=llm_utils.extract_json)
    assert reply.content == '{"a": 1}'
    assert calls == ["model-a", "model-b"]


def test_empty_reply_fails_over(chain):
    calls, _, script = chain
    script += [Reply("<think>only thinking</think>"), Reply("real answer")]
    assert llm_utils.invoke_llm([], purpose="main").content == "real answer"
    assert calls == ["model-a", "model-b"]


def test_purpose_selects_the_chain(chain):
    calls, _, script = chain
    script += [Reply("x"), Reply("x"), Reply("x")]
    llm_utils.invoke_llm([], purpose="main")
    llm_utils.invoke_llm([], purpose="fast")
    llm_utils.invoke_llm([], purpose="analyze")
    assert calls == ["model-a", "fast-a", "analyze-a"]


def test_all_providers_failing_raises(chain):
    _, _, script = chain
    script += [RuntimeError("down"), RuntimeError("down")]
    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        llm_utils.invoke_llm([], purpose="main")


def test_a_fully_rate_limited_chain_waits_and_tries_again(chain):
    calls, sleeps, script = chain
    limited = Exception("Error code: 429 - Rate limit reached. Please try again in 12.0s")
    # both models rate-limited (waits too long for the single retry), then the second pass works
    script += [limited, limited, Reply("ok")]
    assert llm_utils.invoke_llm([], purpose="main").content == "ok"
    assert calls == ["model-a", "model-b", "model-a"]
    assert sleeps and sleeps[-1] >= 12.0


def test_a_chain_rate_limited_for_too_long_gives_up(chain):
    _, sleeps, script = chain
    way_too_long = Exception("Error code: 429 - Rate limit reached. Please try again in 300.0s")
    script += [way_too_long, way_too_long]
    with pytest.raises(RuntimeError, match="All LLM providers failed"):
        llm_utils.invoke_llm([], purpose="main")
    assert not sleeps


def test_a_spent_time_budget_stops_trying_providers(chain):
    calls, _, script = chain
    script += [Reply("never used")]
    with pytest.raises(RuntimeError, match="time budget"):
        llm_utils.invoke_llm([], purpose="main", budget=-1)
    assert calls == []


def test_fallback_models_get_room_to_think_but_groq_keeps_its_small_cap(monkeypatch):
    """Reasoning models return nothing when 1,500 tokens run out mid-thought, so only Groq keeps the cap."""
    class Settings(FakeSettings):
        llm_chain = "groq:g-model,openrouter:o-model:free"
        openrouter_api_keys = "or-key"

    seen = []

    def fake_invoke(llm, messages, deadline):
        seen.append((llm.model_name, llm.max_tokens, deadline))
        if llm.model_name == "g-model":
            raise Exception("Error code: 429 - tokens per day (TPD): Limit 200000. Please try again in 18m57s")
        return Reply("ok")

    monkeypatch.setattr("config.get_settings", lambda: Settings)
    monkeypatch.setattr(llm_utils, "invoke_with_deadline", fake_invoke)
    monkeypatch.setattr(llm_utils.time, "sleep", lambda s: None)
    llm_utils.invoke_llm([], purpose="main", max_tokens=1500, deadline=35)
    assert seen[0] == ("g-model", 1500, 35)
    assert seen[1][0] == "o-model:free"
    assert seen[1][1] >= 4000
    assert seen[1][2] >= 60


def test_extract_json_survives_a_trailing_comma_and_raw_newline():
    nl = chr(10)
    comma = '{"query_type": "personal_situation", "info_needed": [{"field": "a", "reason": "r"},],}'
    assert llm_utils.extract_json(comma)["info_needed"][0]["field"] == "a"
    raw_newline = '{"reason": "line one' + nl + 'line two", "x": 1}'
    assert llm_utils.extract_json(raw_newline)["x"] == 1
