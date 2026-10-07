import json
import os
import concurrent.futures
import sys
from pathlib import Path


project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from kaanoon_test.advanced_rag_api_server import CourtDebateRequest
from kaanoon_test.court_debate_engine import CourtDebateEngineV2, LawGPTLLMClient


def _engine() -> CourtDebateEngineV2:
    return CourtDebateEngineV2.__new__(CourtDebateEngineV2)


def test_elite_routing_flags_and_complexity_signal():
    engine = _engine()
    assert engine._should_run_elite("simple contract definition", elite=True)
    assert engine._should_run_elite("simple contract definition", quality_target="court_85")
    assert engine._should_run_elite(
        "A constitutional PIL about Article 14, Article 21, privacy, habeas corpus, FIR, "
        "criminal conspiracy, interfaith marriage, public order, Special Marriage Act, "
        "and High Court remedies."
    )


def test_llm_router_includes_openrouter_free_models_first(monkeypatch):
    monkeypatch.setattr("kaanoon_test.court_debate_engine.Config", None)
    for k in list(os.environ):
        if any(p in k.lower() for p in ("tokenrouter", "groq", "nvidia", "cerebras")):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-testprimary000000000000000000000000000000")
    monkeypatch.setenv("OPENROUTER_API_KEY_2", "sk-or-v1-testbackup0000000000000000000000000000000")

    client = LawGPTLLMClient()
    openrouter_candidates = [item for item in client._candidates if item["provider"] == "openrouter"]

    assert len(openrouter_candidates) >= 2
    assert openrouter_candidates[0]["models"]["fast"][0] == "openai/gpt-oss-20b:free"
    assert openrouter_candidates[0]["models"]["debate"][0] == "openai/gpt-oss-120b:free"
    assert "tencent/hy3-preview:free" in openrouter_candidates[0]["models"]["fast"]
    assert "nousresearch/hermes-3-llama-3.1-405b:free" in openrouter_candidates[0]["models"]["debate"]
    assert client._ordered_candidates("debate")[0]["provider"] == "openrouter"


def test_llm_router_retries_after_empty_provider_response(monkeypatch):
    monkeypatch.setattr("kaanoon_test.court_debate_engine.Config", None)
    for k in list(os.environ):
        if any(p in k.lower() for p in ("tokenrouter", "groq", "nvidia", "cerebras")):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-testprimary000000000000000000000000000000")

    class EmptyThenOkCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1

            class Message:
                content = "" if kwargs["model"] == "openai/gpt-oss-20b:free" else "OK"

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    completions = EmptyThenOkCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = type("Chat", (), {"completions": completions})()

    monkeypatch.setattr(LawGPTLLMClient, "_client_for", classmethod(lambda cls, candidate: FakeClient()))
    LawGPTLLMClient._cooldowns.clear()
    client = LawGPTLLMClient()

    result = client.generate("Reply OK", max_tokens=5, temperature=0, purpose="fast")

    assert result == "OK"
    assert completions.calls >= 2
    assert client._model == "openai/gpt-oss-120b:free"


def test_engine_initialization_defers_zilliz_retriever_connection(monkeypatch):
    created = {"count": 0}

    class FakeLLM:
        pass

    class FakeRetriever:
        def __init__(self):
            created["count"] += 1

    monkeypatch.setattr("kaanoon_test.court_debate_engine.LawGPTLLMClient", FakeLLM)
    monkeypatch.setattr("kaanoon_test.court_debate_engine.ZillizEvidenceRetriever", FakeRetriever)

    engine = CourtDebateEngineV2()

    assert created["count"] == 0
    assert engine.retriever is engine.retriever
    assert created["count"] == 1


def test_authority_rows_preserve_source_metadata_from_issue_packets():
    engine = _engine()
    rows = engine._authority_rows_from_issue_packets(
        [
            {
                "issue_id": "privacy",
                "label": "Privacy and surveillance",
                "docs": [
                    {
                        "title": "Justice K S Puttaswamy v Union of India",
                        "case_id": "puttaswamy_2017",
                        "court": "Supreme Court of India",
                        "year": "2017",
                        "authority_level": "SC_Judgments_FULL",
                        "source_store": "azure_sc_local",
                        "source_tier": "authoritative",
                        "text": "Privacy is protected under Article 21.",
                    }
                ],
            }
        ]
    )

    assert rows[0]["display_name"] == "Justice K S Puttaswamy v Union of India"
    assert rows[0]["status"] == "retrieved"
    assert rows[0]["court"] == "Supreme Court of India"
    assert rows[0]["year"] == "2017"
    assert rows[0]["case_id"] == "puttaswamy_2017"
    assert rows[0]["source_store"] == "azure_sc_local"
    assert rows[0]["source_tier"] == "authoritative"


def test_persuasion_guardrail_detects_bad_and_good_signals():
    engine = _engine()
    bad = engine._persuasion_guardrail_report(
        {
            "a": "All interfaith couples should be monitored. Family consent is required.",
            "b": "No dignity autonomy public order discussion.",
        }
    )
    assert "blanket_surveillance" in bad["flags"]
    assert "family_consent_required" in bad["flags"]
    assert bad["passed"] is False

    good = engine._persuasion_guardrail_report(
        {
            "a": "The court must weigh dignity, autonomy, public order, institutional discipline, "
            "and chilling effect while separating empathy from proof."
        }
    )
    assert good["flags"] == []
    assert good["passed"] is True


def test_court_debate_request_accepts_elite_flags():
    req = CourtDebateRequest(
        query="constitutional PIL",
        elite=True,
        quality_target="court_85",
    )

    assert req.elite is True
    assert req.quality_target == "court_85"


def test_elite_compact_strategy_uses_single_llm_call(monkeypatch):
    engine = _engine()

    class FakeLLM:
        provider = "fake"

        def __init__(self):
            self.calls = 0

        def generate(self, *args, **kwargs):
            self.calls += 1
            return """
## Level 1: Issue Framing and Clarification Gate
1. What exact order, circular, policy, FIR, or petition text is before the court?
2. What evidence supports coercion, public order risk, discrimination, or selective enforcement?
3. What interim and final relief has each party sought?
4. What forum posture is active: writ, PIL, habeas corpus, criminal investigation, or appeal?
5. What facts show the lived impact on dignity, education, liberty, safety, or institutional discipline?
Decision Issues: Article 14, Article 21, Article 25, public order, remedy.
## Level 2: Authority Table and Source Discipline
Authority table with Puttaswamy and Shafin Jahan; authority gap - verify before relying.
## Level 3: Petitioner / Claimant Submissions
Petitioner argues dignity, autonomy, chilling effect, and proportionality.
## Level 4: Respondent / Defence Submissions
State argues institutional discipline and public order.
## Level 5: Rebuttal and Sur-Rebuttal
Rebuttal and sur-rebuttal identify evidence and legal vulnerability.
## Level 6: Bench Questions and Cross-Examination
Bench question: what statutory basis and remedy follows?
## Level 7: Ethical Persuasion and Human-Impact Analysis
Human impact, dignity, autonomy, public order, institutional discipline, and chilling effect are separated from proof.
## Level 8: Final Bench Ruling, Remedies, and Alternative Outcomes
Likely outcome with remedy, declaration, mandamus, stay, and confidence.
## Independent Evaluation (Scored by Judge Agent)
Overall Court-Level Quality: 85/100
"""

    fake_llm = FakeLLM()
    engine.llm = fake_llm
    engine._load_history = lambda *args, **kwargs: ""
    engine._infer_sides = lambda query: ("Petitioner", "State")
    engine._decompose_issues = lambda *args, **kwargs: [
        {
            "id": "constitutional_privacy",
            "bucket": "constitutional",
            "label": "Constitutional privacy and proportionality",
            "question": "Whether privacy and proportionality are infringed.",
        }
    ]
    engine._build_evidence_packet = lambda *args, **kwargs: (
        [{"issue_id": "constitutional_privacy", "label": "Constitutional privacy and proportionality", "question": "q", "docs": []}],
        "No retrieved docs.",
    )
    engine._elite_clarification_questions = lambda *args, **kwargs: (
        "1. What exact order, circular, policy, FIR, or petition text is before the court?\n"
        "2. What evidence supports coercion, public order risk, discrimination, or selective enforcement?\n"
        "3. What interim and final relief has each party sought?\n"
        "4. What forum posture is active: writ, PIL, habeas corpus, criminal investigation, or appeal?\n"
        "5. What facts show the lived impact on dignity, education, liberty, safety, or institutional discipline?"
    )
    engine._save_to_memory = lambda *args, **kwargs: None
    monkeypatch.setenv("COURT_DEBATE_ELITE_STRATEGY", "compact")
    monkeypatch.setenv("COURT_DEBATE_ELITE_STATIC_CLARIFICATIONS", "true")

    result = engine.run_debate_elite("Article 21 privacy and interfaith marriage dispute")

    assert fake_llm.calls == 1
    assert result["generation_strategy"] == "compact_single_call"
    assert result["quality_mode"] == "elite"
    assert "Level 8" in result["debate_output"]


def test_interfaith_autonomy_fallback_issue_map_is_decision_complete():
    engine = _engine()
    issues = engine._fallback_issue_map(
        "A Hindu woman and a Muslim man marry under the Special Marriage Act. The family alleges love jihad and coercion."
    )

    labels = " ".join(issue["label"] for issue in issues).lower()
    questions = " ".join(issue["question"] for issue in issues).lower()

    assert any("article 21" in issue["label"].lower() for issue in issues)
    assert "special marriage act" in labels
    assert "love jihad" in labels or "love jihad" in questions
    assert "burden" in labels or "burden" in questions
    assert "police complaint" in labels or "habeas" in questions or "matrimonial" in questions
    assert "conversion" in labels
    assert "habeas" in labels
    assert "digital" in labels or "whatsapp" in labels


def test_complex_interfaith_issue_blueprint_fallback_is_decision_complete():
    engine = _engine()
    query = (
        "A Hindu woman marries a Muslim man under the Special Marriage Act, later converts, "
        "has a second personal law marriage, faces kidnapping, forced conversion, love jihad, "
        "WhatsApp evidence, and habeas corpus claims."
    )
    preplan = engine._build_preplan(query, "req-blueprint", "")
    authority_matrix = engine._required_authority_matrix(query)
    blueprint = engine._fallback_issue_blueprint(
        user_query=query,
        preplan=preplan,
        guardrails=engine._current_law_guardrails(query),
        authority_hints=engine._authority_hints(query),
        authority_matrix_text=engine._format_required_authority_matrix(authority_matrix),
        evidence_packet="Evidence retrieval timed out; authority gap - verify before relying.",
    )
    flags = engine._issue_blueprint_quality_flags(
        user_query=query,
        text=blueprint,
        issues=preplan["issue_map"],
        authority_matrix=authority_matrix,
    )
    body = blueprint.lower()

    assert "article 21" in body
    assert "special marriage act" in body
    assert "conversion" in body
    assert "second marriage" in body
    assert "habeas" in body
    assert "whatsapp" in body
    assert "love jihad" in body
    assert "authority gap" in body
    assert not [flag for flag in flags if flag.startswith("missing_")]


def test_deep_issue_preplan_stores_locked_blueprint_contract_fields():
    engine = _engine()
    query = (
        "Adult interfaith couple married under the Special Marriage Act, later conversion, "
        "second marriage ceremony, kidnapping FIR, WhatsApp chats, habeas corpus, and love jihad allegation."
    )
    preplan = engine._build_preplan(query, "req-preplan", "")
    authority_matrix = engine._required_authority_matrix(query)
    blueprint = engine._fallback_issue_blueprint(
        user_query=query,
        preplan=preplan,
        guardrails=engine._current_law_guardrails(query),
        authority_hints=engine._authority_hints(query),
        authority_matrix_text=engine._format_required_authority_matrix(authority_matrix),
        evidence_packet="Evidence retrieval timed out; authority_gap.",
    )
    preplan["issue_blueprint"] = blueprint
    preplan["issue_coverage"] = engine._issue_coverage_map(blueprint, preplan["issue_map"])
    preplan["authority_requirements"] = authority_matrix
    preplan["evidence_questions"] = [issue["question"] for issue in preplan["issue_map"]]
    preplan["quality_flags"] = engine._issue_blueprint_quality_flags(
        user_query=query,
        text=blueprint,
        issues=preplan["issue_map"],
        authority_matrix=authority_matrix,
    )

    assert preplan["issue_blueprint"]
    assert all(item["covered"] for item in preplan["issue_coverage"].values())
    assert preplan["forum_posture"]["primary_tracks"]
    assert preplan["authority_requirements"]
    assert len(preplan["evidence_questions"]) == len(preplan["issue_map"])
    assert preplan["side_theories"]["a"]
    assert preplan["side_theories"]["b"]
    assert preplan["quality_flags"] == []


def test_downstream_validator_flags_cards_that_ignore_locked_issues():
    engine = _engine()
    query = (
        "A Hindu woman marries a Muslim man under the Special Marriage Act, later converts, "
        "faces a love jihad complaint, WhatsApp evidence, kidnapping FIR, and habeas corpus."
    )
    issues = engine._fallback_issue_map(query)
    authority_matrix = engine._required_authority_matrix(query)
    weak_likely_outcome = "The core legal issues and remedies depend on facts. The likely outcome is uncertain."

    flags = engine._section_quality_flags(
        section_id="l7",
        text=weak_likely_outcome,
        user_query=query,
        issues=issues,
        prior_sections={"level_1_issue_framing": engine._format_issue_map(issues)},
        authority_matrix=authority_matrix,
        evidence_packet="authority_gap | retrieval timed out",
    )

    assert "missing_major_framed_issues" in flags
    assert any(flag.startswith("missing_framed_issue_") for flag in flags)


def test_evidence_status_rows_use_exact_retrieval_status_contract():
    engine = _engine()
    issues = [
        {"id": "article21", "bucket": "constitutional", "label": "Article 21 autonomy", "question": "Whether adult autonomy applies."},
        {"id": "sma", "bucket": "statutory", "label": "Special Marriage Act validity", "question": "Whether SMA marriage remains valid."},
        {"id": "habeas", "bucket": "procedural", "label": "Habeas corpus maintainability", "question": "Whether habeas remains maintainable."},
    ]
    rows = engine._issue_authority_status_rows(
        issues=issues,
        issue_packets=[
            {"issue_id": "article21", "docs": [{"title": "Shafin Jahan", "retrieval_status": "retrieved", "text": "adult choice"}]},
            {"issue_id": "sma", "docs": [{"title": "Unknown SMA note", "retrieval_status": "suggested_but_unverified", "text": ""}]},
        ],
        authority_matrix=[],
    )

    assert [row["status"] for row in rows] == ["retrieved", "suggested_but_unverified", "authority_gap"]


def test_stream_emits_working_events_before_first_issue_card(monkeypatch):
    engine = _engine()
    query = (
        "Adult interfaith couple under Special Marriage Act with conversion, love jihad, "
        "kidnapping FIR, WhatsApp chats, and habeas corpus."
    )
    issues = engine._fallback_issue_map(query)
    blueprint = engine._fallback_issue_blueprint(
        user_query=query,
        preplan=engine._build_preplan(query, "req-stream", ""),
        guardrails=engine._current_law_guardrails(query),
        authority_hints=engine._authority_hints(query),
        authority_matrix_text=engine._format_required_authority_matrix(engine._required_authority_matrix(query)),
        evidence_packet="authority_gap | timed out",
    )

    engine._load_history = lambda *args, **kwargs: ""
    engine._save_to_memory = lambda *args, **kwargs: None
    engine._build_stream_evidence_packet = lambda *args, **kwargs: (
        [{"issue_id": issue["id"], "label": issue["label"], "question": issue["question"], "docs": []} for issue in issues],
        "authority_gap | timed out",
        True,
    )
    engine._build_issue_blueprint = lambda *args, **kwargs: (blueprint, [], 1)
    engine._generate_section_with_guardrails = lambda **kwargs: (
        blueprint + "\n\nAuthority anchor: authority_gap. Next step: verify.",
        [],
        1,
    )

    events = []
    for raw in engine._stream_modular_sections(query, session_id="req-stream", history=""):
        event = json.loads(raw)
        events.append(event)
        if event.get("section_id") == "l1" and event.get("status") == "complete":
            break

    first_complete_index = next(i for i, event in enumerate(events) if event.get("status") == "complete")
    working_messages = [event.get("message") for event in events[:first_complete_index] if event.get("status") == "working"]

    assert working_messages[:4] == [
        "Classifying scenario family",
        "Building issue blueprint",
        "Checking statutes and forums",
        "Validating Issue Framing",
    ]


def test_interfaith_authority_hints_include_core_cases_and_statute():
    engine = _engine()
    hints = engine._authority_hints(
        "Adult interfaith marriage under the Special Marriage Act with family coercion allegations and love jihad label"
    ).lower()

    assert "shafin jahan" in hints
    assert "lata singh" in hints
    assert "laxmibai chandaragi" in hints
    assert "special marriage act" in hints


def test_section_quality_flags_detect_same_side_and_missing_statutory_anchor():
    engine = _engine()
    issues = engine._fallback_issue_map(
        "A Hindu woman and a Muslim man marry under the Special Marriage Act. The family alleges love jihad and coercion."
    )
    authority_matrix = engine._required_authority_matrix("special marriage act love jihad interfaith adult autonomy")
    evidence_packet = "### Issue 1\n- No strong retrieval returned for this issue. Treat conclusions as lower-confidence."

    advocate_a = (
        "The family is worried, but the adult woman's autonomy under Article 21 should prevail and the Special Marriage Act protects her choice."
    )
    advocate_b = (
        "The adult woman's autonomy under Article 21 should prevail and the Special Marriage Act protects her choice."
    )

    flags = engine._section_quality_flags(
        section_id="l3",
        text=advocate_b,
        user_query="special marriage act love jihad interfaith adult autonomy",
        issues=issues,
        prior_sections={"l2": advocate_a},
        authority_matrix=authority_matrix,
        evidence_packet=evidence_packet,
    )

    assert "too_similar_to_advocate_a" in flags


def test_stream_debate_emits_completed_section_packets(monkeypatch):
    engine = _engine()
    packets = [
        '{"section_id":"l1","title":"Issue Framing","role":"Issue Framing Bench","status":"complete","body":"Issue framing body","quality_flags":[],"authority_count":1,"request_id":"req-1","level":"## Issue Framing","chunk":"Issue framing body"}',
        '{"section_id":"l2","title":"Advocate A - Challenge / Coercion Inquiry","role":"Family-Side Challenger","status":"complete","body":"Advocate A body","quality_flags":[],"authority_count":1,"request_id":"req-1","level":"## Advocate A","chunk":"Advocate A body"}',
    ]
    engine._stream_modular_sections = lambda *args, **kwargs: iter(packets)

    out = list(engine.stream_debate("query", session_id="req-1"))

    assert '"section_id":"l1"' in out[0]
    assert '"status":"complete"' in out[0]
    assert '"request_id":"req-1"' in out[0]
    assert '"level": "done"' in out[-1] or '"level":"done"' in out[-1]


def test_live_in_relationship_family_detection_and_issue_map():
    engine = _engine()
    family = engine._scenario_family(
        "An interfaith couple lives together for 5 years without marriage and the woman seeks maintenance and domestic violence protection."
    )
    issues = engine._fallback_issue_map(
        "An interfaith couple lives together for 5 years without marriage and the woman seeks maintenance and domestic violence protection."
    )
    text = " ".join(issue["label"] + " " + issue["question"] for issue in issues).lower()

    assert family is not None
    assert family.key == "live_in_relationship_maintenance"
    assert "relationship in the nature of marriage" in text
    assert "domestic violence" in text
    assert "maintenance" in text
    assert "shared household" in text


def test_live_in_authority_matrix_and_hints_are_specific():
    engine = _engine()
    hints = engine._authority_hints(
        "Can a live-in relationship be treated as marriage-like under Indian law for maintenance and domestic violence protection?"
    ).lower()
    rows = engine._required_authority_matrix(
        "Can a live-in relationship be treated as marriage-like under Indian law for maintenance and domestic violence protection?"
    )
    names = " ".join(row["name"] for row in rows).lower()

    assert "indra sarma" in hints
    assert "velusamy" in hints
    assert "chanmuniya" in hints
    assert "section 2(f)" in hints
    assert "indra sarma" in names
    assert "velusamy" in names
    assert "chanmuniya" in names


def test_live_in_section_quality_flags_detect_scenario_contamination():
    engine = _engine()
    issues = engine._fallback_issue_map(
        "A couple lives together for five years without marriage and the woman seeks maintenance and DV protection."
    )
    authority_matrix = engine._required_authority_matrix(
        "A couple lives together for five years without marriage and the woman seeks maintenance and DV protection."
    )
    contaminated = (
        "The Special Marriage Act and love jihad allegations show why the adult woman's Article 21 spouse-choice autonomy should prevail."
    )

    flags = engine._section_quality_flags(
        section_id="l3",
        text=contaminated,
        user_query="A couple lives together for five years without marriage and the woman seeks maintenance and DV protection.",
        issues=issues,
        prior_sections={},
        authority_matrix=authority_matrix,
        evidence_packet="No strong retrieval returned for this issue.",
    )

    assert "scenario_contamination" in flags


def test_advisory_quote_warning_does_not_force_regeneration():
    engine = _engine()

    class FakeLLM:
        def __init__(self):
            self.calls = 0

        def generate(self, *args, **kwargs):
            self.calls += 1
            return (
                'The claimant says the five-year cohabitation was "marriage-like" and a '
                '"relationship in the nature of marriage" because the parties shared a household. '
                "She seeks maintenance and domestic violence protection under Section 2(f), "
                "while accepting that proof of holding out and dependence remains central."
            )

    fake_llm = FakeLLM()
    engine.llm = fake_llm
    query = "A couple lives together for five years without marriage and the woman seeks maintenance and DV protection."
    body, flags, attempts = engine._generate_section_with_guardrails(
        section_id="l2",
        title="Advocate A",
        role="Woman Claimant",
        base_prompt="Draft Advocate A.",
        user_query=query,
        issues=engine._fallback_issue_map(query),
        prior_sections={},
        authority_matrix=[],
        evidence_packet="",
        max_tokens=500,
        temperature=0.1,
    )

    assert body
    assert attempts == 1
    assert fake_llm.calls == 1
    assert flags == ["uncertain_quote_style"]


def test_live_in_contract_uses_case_specific_roles_and_questions():
    engine = _engine()
    query = (
        "A couple lives together for five years without marriage. The woman seeks "
        "maintenance rights and domestic violence protection."
    )

    contract = engine._scenario_debate_contract(query)
    catalog = engine._section_catalog(query)

    assert "Woman" in contract["advocate_a_title"]
    assert "No Formal Marriage" in contract["advocate_b_title"]
    assert "live-in relationship" in contract["outcome_questions"].lower()
    assert "domestic violence act" in contract["outcome_questions"].lower()
    assert "cultural norms" in contract["outcome_questions"].lower()
    assert "love jihad" not in contract["outcome_questions"].lower()
    assert "annulled" not in contract["outcome_questions"].lower()
    assert catalog[1]["title"] == contract["advocate_a_title"]
    assert catalog[2]["title"] == contract["advocate_b_title"]


def test_stream_issue_packet_exposes_live_in_scenario_family(monkeypatch):
    engine = _engine()
    query = (
        "A couple lives together for five years without marriage. The woman seeks "
        "maintenance rights and domestic violence protection. Can a live-in relationship "
        "be treated as marriage-like under Indian law?"
    )
    engine._load_history = lambda *args, **kwargs: ""
    engine._build_stream_evidence_packet = lambda *args, **kwargs: ([], "authority gap - verify before relying", True)
    engine._build_issue_blueprint = lambda **kwargs: (
        engine._fallback_issue_blueprint(**kwargs),
        [],
        1,
    )

    gen = engine._stream_modular_sections(query, session_id="req-live-in")
    packet = None
    for raw in gen:
        event = json.loads(raw)
        if event.get("section_id") == "l1" and event.get("status") == "complete":
            packet = event
            break
    assert packet is not None

    assert packet["section_id"] == "l1"
    assert packet["scenario_family"] == "live_in_relationship_maintenance"
    assert packet["legal_domain"] == "family_law"
    assert "Relationship in the nature of marriage" in packet["body"]
    assert "Section 2(f), Protection of Women from Domestic Violence Act, 2005" in packet["body"]
    assert "No scenario-specific required authority matrix" not in packet["body"]


def test_stream_emits_working_status_after_issue_card(monkeypatch):
    engine = _engine()
    query = (
        "A couple lives together for five years without marriage. The woman seeks "
        "maintenance rights and domestic violence protection."
    )
    engine._load_history = lambda *args, **kwargs: ""
    engine._build_stream_evidence_packet = lambda *args, **kwargs: ([], "authority gap - verify before relying", True)
    engine._build_issue_blueprint = lambda **kwargs: (
        engine._fallback_issue_blueprint(**kwargs),
        [],
        1,
    )

    gen = engine._stream_modular_sections(query, session_id="req-live-in")
    first = json.loads(next(gen))
    second = json.loads(next(gen))

    assert first["section_id"] == "l1"
    assert first["status"] == "working"
    assert second["status"] == "working"
    assert second["message"]


def test_stream_evidence_timeout_returns_authority_gap(monkeypatch):
    engine = _engine()
    query = "Adult interfaith marriage under the Special Marriage Act with forced conversion allegations."

    class NeverDoneFuture:
        def result(self, timeout=None):
            raise concurrent.futures.TimeoutError()

        def cancel(self):
            return True

    class FakeExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def submit(self, *args, **kwargs):
            return NeverDoneFuture()

        def shutdown(self, *args, **kwargs):
            pass

    monkeypatch.setattr(concurrent.futures, "ThreadPoolExecutor", FakeExecutor)

    packets, evidence, timed_out = engine._build_stream_evidence_packet(
        query,
        engine._fallback_issue_map(query),
    )

    assert packets == []
    assert timed_out is True
    assert "Evidence retrieval timed out" in evidence
    assert "authority gap - verify before relying" in evidence


def test_deterministic_l4_evidence_card_covers_all_locked_issues():
    engine = _engine()
    query = (
        "A Hindu woman marries a Muslim man under the Special Marriage Act, later converts, "
        "faces kidnapping, forced conversion, love jihad, WhatsApp evidence, and habeas corpus."
    )
    issues = engine._fallback_issue_map(query)
    rows = engine._issue_authority_status_rows(
        issues=issues,
        issue_packets=[],
        authority_matrix=engine._required_authority_matrix(query),
        user_query=query,
    )

    card = engine._render_evidence_authority_card(
        issues=issues,
        authority_status_rows=rows,
        evidence_timed_out=True,
    )
    flags = engine._section_quality_flags(
        section_id="l4",
        text=card,
        user_query=query,
        issues=issues,
        prior_sections={"l1": engine._format_issue_map(issues)},
        authority_matrix=engine._required_authority_matrix(query),
        evidence_packet="authority_gap | timed out",
    )

    assert len(rows) == len(issues)
    assert all(row["status"] in {"retrieved", "suggested_but_unverified", "authority_gap"} for row in rows)
    assert "Retrieval Status" in card
    assert "authority_gap" in card or "suggested_but_unverified" in card
    assert "too_thin" not in flags
    assert "missing_exact_retrieval_status" not in flags
    assert "missing_major_framed_issues" not in flags


def test_section_timeout_uses_deterministic_fallback(monkeypatch):
    engine = _engine()
    engine.llm = type("SlowLLM", (), {"generate": lambda *args, **kwargs: "never"})()
    query = "Adult interfaith marriage under the Special Marriage Act with forced conversion allegations."
    issues = engine._fallback_issue_map(query)
    fallback = engine._render_bench_fallback(
        issues=issues,
        authority_status_rows=[
            {"issue_id": issue["id"], "issue": issue["label"], "authority": "Authority gap - verify before relying", "status": "authority_gap"}
            for issue in issues
        ],
    )

    class NeverDoneFuture:
        def result(self, timeout=None):
            raise concurrent.futures.TimeoutError()

        def cancel(self):
            return True

    class FakeExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def submit(self, *args, **kwargs):
            return NeverDoneFuture()

        def shutdown(self, *args, **kwargs):
            pass

    monkeypatch.setattr(concurrent.futures, "ThreadPoolExecutor", FakeExecutor)

    text, flags, attempts = engine._generate_section_with_guardrails(
        section_id="l6",
        title="Bench Analysis",
        role="The Bench",
        base_prompt="bench",
        user_query=query,
        issues=issues,
        prior_sections={"l1": engine._format_issue_map(issues)},
        authority_matrix=engine._required_authority_matrix(query),
        evidence_packet="authority_gap | timed out",
        max_tokens=100,
        temperature=0.1,
        fallback=fallback,
        timeout_seconds=0.01,
    )

    assert text == fallback
    assert attempts == 1
    assert "llm_generation_timeout" not in flags
    assert "too_thin" not in flags


def test_provider_health_records_empty_response():
    key = "test-provider:test-key:model"
    LawGPTLLMClient._health.pop(key, None)
    LawGPTLLMClient._record_health(key, "empty", "empty LLM response")
    snapshot = LawGPTLLMClient.provider_health_snapshot()

    assert snapshot[key]["empty_response_count"] == 1
    assert snapshot[key]["last_failure_reason"] == "empty LLM response"
