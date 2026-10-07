import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from kaanoon_test.system_adapters.clarification_engine import ClarificationSession


def _deterministic_session(**kwargs) -> ClarificationSession:
    """A session pinned to the deterministic keyword planner.

    These tests pin that planner's contract (canned wording, five questions), so
    they must stay offline and reproducible. The LLM-first planner is covered by
    the gap-analysis tests at the end of this file and by the opt-in live test.
    """
    return ClarificationSession(provider="groq", enable_llm_gap_analysis=False, **kwargs)


# The user-reported scenario that exposed the bug: a matrimonial matter (DV Act,
# divorce on cruelty, maintenance, child custody, a privilege objection) that the
# keyword planner used to classify as a criminal arrest matter because of the word
# "custody", and then asked where the "arrested person" was.
_MATRIMONIAL_SCENARIO = (
    "A 29-year-old woman, Ayesha Khan, married Rohan Sharma, a Hindu man, under the Special Marriage "
    "Act, 1954 in Bengaluru in 2023. They have a 3-year-old daughter. In 2025, Ayesha obtained "
    "employment with a private technology company. Rohan alleges that after she started working, she "
    "began transferring a substantial portion of her salary to her parents and refused to contribute to "
    "household expenses. Ayesha alleges that Rohan repeatedly restricted her access to money, monitored "
    "her phone, prevented her from visiting her parents, and demanded that she leave her job. In January "
    "2026, Ayesha left the matrimonial home with their daughter and moved into a rented apartment. She "
    "filed proceedings under the Protection of Women from Domestic Violence Act, 2005, alleging "
    "emotional abuse, economic abuse, and unlawful restriction of her movements. She sought: 1. A "
    "protection order; 2. A residence order; 3. Monthly monetary relief; 4. Custody of the child; and "
    "5. Compensation for mental harassment. Rohan subsequently filed for divorce alleging mental "
    "cruelty under Section 13(1)(ia) of the Hindu Marriage Act, 1955. He claims that Ayesha deliberately "
    "abandoned the matrimonial home, refused marital obligations, and made false allegations of abuse. "
    "During the proceedings, Rohan produces screenshots of private WhatsApp conversations between "
    "Ayesha and her lawyer that were allegedly obtained from her laptop without her knowledge. Ayesha "
    "objects to their production, claiming violation of privacy and advocate-client confidentiality. "
    "Rohan also claims that, before leaving the matrimonial home, Ayesha transferred Rs 18 lakh from a "
    "joint bank account to her father's account. Ayesha says the money represented her own salary "
    "savings and was transferred temporarily because she feared Rohan would withdraw it. Meanwhile, the "
    "couple's minor daughter has been living with Ayesha. Rohan seeks interim custody, alleging that "
    "Ayesha is preventing him from meeting the child. Ayesha argues that Rohan's frequent travel and "
    "working hours make him unsuitable for day-to-day custody, but she is willing to permit structured "
    "visitation. The Family Court is now required to consider the divorce petition, maintenance-related "
    "claims, custody, and evidentiary objections, while the Magistrate is separately considering the DV "
    "Act proceedings. Analyse the legal issues arising from these facts under Indian law. Discuss the "
    "relevant constitutional provisions, statutory provisions, jurisdiction, evidentiary and privacy "
    "issues, maintenance and residence rights, child custody principles, burden of proof, and the "
    "possible interaction between the proceedings before the Family Court and the Magistrate. Support "
    "your answer with relevant Supreme Court/High Court precedents and explain the ratio of the cases "
    "relied upon."
)

# A model reply shaped exactly like SCENARIO_GAP_ANALYSIS_PROMPT requires.
_FAKE_GAP_ANALYSIS = {
    "domain": "family_matrimonial",
    "domains": ["family_matrimonial", "constitutional", "evidence_bsa"],
    "query_type": "hypothetical_scenario",
    "is_personal_case": False,
    "parties": ["Ayesha Khan", "Rohan Sharma", "their daughter"],
    "issues": [
        {
            "issue": "Economic abuse and residence rights under the DV Act",
            "statutes": ["PWDVA 2005 ss. 12, 17, 18, 20, 22"],
            "why_it_matters": "drives the protection and residence relief",
        }
    ],
    "data_gaps": [
        {
            "key": "chats_acquisition",
            "question": "How did Rohan obtain the WhatsApp chats between Ayesha and her advocate, and was her laptop password or her consent involved?",
            "why": "Decides the privacy and advocate-client privilege objection.",
            "priority": 1,
        },
        {
            "key": "spouse_incomes",
            "question": "What are Ayesha's and Rohan's monthly incomes and existing liabilities, and who currently pays the child's school and household costs?",
            "why": "Decides interim maintenance and the residence order.",
            "priority": 2,
        },
        {
            "key": "shared_household",
            "question": "Is the rented apartment Ayesha now occupies part of the shared household the couple lived in?",
            "why": "Decides residence-order maintainability.",
            "priority": 3,
        },
    ],
}


def test_complex_consultation_triggers_needs_clarification():
    session = _deterministic_session()
    query = (
        "My business partner took money in a property deal, then sent legal notice and threats. "
        "What should I do for FIR, injunction, recovery, and arbitration clause enforcement?"
    )

    result = session.start_session(query, category="general")

    assert result["status"] == "needs_clarification"
    assert "first_question" in result
    assert result["clarification_mode"] == "sequential"
    assert result["question_index"] == 1
    assert result["first_question"].count("?") == 1
    # Only one question is exposed at a time, and it must target a missing intake fact.
    first_question = result["first_question"].lower()
    assert "role" in first_question or "timeline" in first_question
    assert result["intent"]["question_source"] == "intake_gaps"


def test_simple_definition_stays_direct():
    session = _deterministic_session()

    result = session.start_session("What is Section 302 IPC?", category="general")

    assert result["status"] == "simple_direct"


def test_academic_multi_issue_stays_direct_analysis():
    session = _deterministic_session()
    query = (
        "A fintech app shares user financial data without clear consent. Analyze separately:\n"
        "1. Privacy rights under Article 21.\n"
        "2. Deficiency in service and unfair trade practice.\n"
        "3. Effect of the arbitration clause.\n"
        "4. PIL maintainability before the High Court.\n"
        "5. Remedies before commission and writ court."
    )

    result = session.start_session(query, category="general")

    assert result["status"] == "academic_direct"


def test_cross_domain_consultation_runs_full_five_question_clarification(monkeypatch):
    session = _deterministic_session()
    query = (
        "I run a mobile payment and micro-loan app, and I need legal advice because users were forced to accept broad data sharing for location, contacts, browsing behavior, and transaction history. "
        "Our terms permit opaque algorithmic credit scoring and mandatory arbitration in another state. Two years later a breach exposed user data, users received phishing and predatory loan calls, and researchers showed data sharing with marketing firms. "
        "Consumer complaints were filed for deficiency and unfair trade practice, and a PIL was filed over privacy violations under Article 21 and weak cybersecurity safeguards. "
        "What should I do about privacy, consent validity, company liability, PIL maintainability against private entities, and arbitration affecting consumer remedies?"
    )

    result = session.start_session(query, category="general")

    assert result["status"] == "needs_clarification"
    assert session.max_questions == 5
    assert len(session.qa_history) == 1
    assert result["first_question"].count("?") == 1
    assert result["intent"]["question_source"] == "intake_gaps"

    # The stub must vary its question: the loop (correctly) refuses to re-ask an
    # identical question and would fall back to the plan instead.
    asked = {"count": 0}

    def _next_question_stub():
        asked["count"] += 1
        return f"Please clarify detail number {asked['count']}?"

    monkeypatch.setattr(session, "_generate_next_question", _next_question_stub)

    for index in range(4):
        loop_result = session.submit_answer(f"answer {index + 1}")
        assert loop_result["status"] == "clarification_loop"
        assert loop_result["progress"] == f"{index + 2}/5"
        assert loop_result["question_index"] == index + 2
        assert loop_result["total_questions"] == 5
        assert loop_result["clarification_mode"] == "sequential"
        assert loop_result["next_question"] == f"Please clarify detail number {index + 1}?"

    final_result = session.submit_answer("answer 5")
    assert final_result["status"] == "ready_for_synthesis"


def test_clarification_sanitizer_outputs_one_question():
    session = _deterministic_session()
    bundled = (
        "1. What is the exact date of the notice?\n"
        "2. Which court is involved?\n"
        "3. What relief do you want?"
    )

    question = session._sanitize_single_question(bundled)

    assert question == "What is the exact date of the notice?"
    assert question.count("?") == 1


def test_interfaith_debate_asks_scenario_specific_gap_not_generic_role():
    session = _deterministic_session()
    query = (
        "Complex Scenario: Interfaith Marriage, Conversion, Criminal Allegations and State Intervention. "
        "A 23-year-old Hindu woman from Karnataka marries a Muslim man under the Special Marriage Act. "
        "Two weeks later she converts to Islam and registers a second marriage under Muslim personal law. "
        "Her family files complaints alleging kidnapping, wrongful confinement, forced conversion under a state "
        "anti-conversion law, marriage fraud, and love jihad conspiracy. Police detain B. Meanwhile A appears "
        "before a magistrate and says she acted voluntarily, but WhatsApp chats show confusion and emotional pressure. "
        "Parents file habeas corpus alleging psychological captivity. How should a court balance Article 21 autonomy, "
        "SMA validity, conversion and second marriage, anti-conversion scrutiny, digital evidence, love jihad claims, "
        "state investigation, and parental rights? A good chatbot must argue both sides."
    )

    result = session.start_session(query, category="general")

    assert result["status"] == "needs_clarification"
    assert result["clarification_mode"] == "sequential"
    assert result["question_index"] == 1
    assert result["total_questions"] == 5
    first_question = result["first_question"].lower()
    assert "exact role" not in first_question
    assert "other party" not in first_question
    assert "ipc/bns" in first_question
    assert result["intent"]["scenario_specific_gaps"] is True

    # The Karnataka anti-conversion gap is scenario-specific and must be asked in the
    # loop, not skipped in favour of a generic follow-up.
    loop_result = session.submit_answer("Assume August 2024, so BNS/BNSS/BSA apply.")
    assert loop_result["status"] == "clarification_loop"
    assert "karnataka anti-conversion" in loop_result["next_question"].lower()


def test_interfaith_final_request_preserves_clarifications(monkeypatch):
    session = _deterministic_session()
    query = (
        "Complex Scenario: Interfaith Marriage, Conversion, Criminal Allegations and State Intervention. "
        "A 23-year-old Hindu woman from Karnataka marries a Muslim man under the Special Marriage Act. "
        "Two weeks later she converts to Islam and registers a second marriage under Muslim personal law. "
        "Her family files complaints alleging kidnapping, wrongful confinement, forced conversion under a state "
        "anti-conversion law, marriage fraud, and love jihad conspiracy. Police detain B. Meanwhile A appears "
        "before a magistrate and says she acted voluntarily, but WhatsApp chats show confusion and emotional pressure. "
        "Parents file habeas corpus alleging psychological captivity. How should a court balance Article 21 autonomy, "
        "SMA validity, conversion and second marriage, anti-conversion scrutiny, digital evidence, love jihad claims, "
        "state investigation, and parental rights? A good chatbot must argue both sides."
    )

    result = session.start_session(query, category="general")
    assert result["status"] == "needs_clarification"

    answers = [
        "Assume August 2024 so BNS, BNSS and BSA apply.",
        "BNS kidnapping, forced marriage, cheating, conspiracy, and Karnataka Act Sections 3, 5, 6 and 10.",
        "A is present before court, says she is voluntary, and is in temporary protective custody.",
        "Section 63 BSA certificate is filed but disputed; chats show hesitation and emotional pressure, not threats.",
        "Answer as a hybrid: neutral court-balancing, side-wise arguments, and likely outcome.",
    ]

    for answer in answers[:-1]:
        loop_result = session.submit_answer(answer)
        assert loop_result["status"] == "clarification_loop"

    final_result = session.submit_answer(answers[-1])
    assert final_result["status"] == "ready_for_synthesis"

    monkeypatch.setattr(
        session,
        "_call_llm",
        lambda *args, **kwargs: type(
            "Resp",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type(
                                "Message",
                                (),
                                {"content": "## CASE BRIEF\n- Interfaith marriage clarification matrix"},
                            )()
                        },
                    )()
                ]
            },
        )(),
    )

    synthesis = session.synthesize_and_execute()
    final_request = synthesis["final_request"]

    assert "ORIGINAL USER SCENARIO" in final_request
    assert "CLARIFICATION ANSWERS / ASSUMPTIONS" in final_request
    assert "August 2024" in final_request
    assert "Section 63 BSA" in final_request
    assert "hybrid" in final_request.lower()
    assert "Neutral court-balancing analysis" in final_request
    assert "Side-wise arguments" in final_request
    assert "Reasoned likely outcome" in final_request
    assert "Do not call A a victim or B a perpetrator" in final_request


def test_integrated_contract_criminal_banking_query_gets_specific_5q_plan():
    mini_rag_calls = []

    def mini_rag(query):
        mini_rag_calls.append(query)
        return "Mini RAG: Contract Act, IT Act, IPC/BNS transition, RDDBFI/DRT context."

    session = _deterministic_session(retriever_callback=mini_rag)
    query = (
        "Rajesh, a 35-year-old businessman in Mumbai, signed a contract with a supplier in Gujarat "
        "for 500 lithium batteries worth Rs 50 lakh, but only 200 were delivered. Part A -- Contract Law: "
        "discuss Indian Contract Act sections, partial delivery, specific performance, quantum meruit, civil remedies. "
        "Part B -- Criminal Law / IT Law: Sneha found competitor battery design documents on an external hard drive, "
        "photographed and shared them with Rajesh, who used the designs; competitor filed IPC and IT Act complaint. "
        "Part C -- Banking: Rajesh defaulted on a Rs 10 lakh bank loan and the bank issued notice under the RDDBFI Act. "
        "Part D -- Integrated Analysis: discuss overlapping issues and step-by-step strategy."
    )

    result = session.start_session(query, category="general")

    assert result["status"] == "needs_clarification"
    assert result["total_questions"] == 5
    assert result["intent"]["scenario_specific_gaps"] is True
    assert mini_rag_calls == [query]

    q1 = result["first_question"].lower()
    assert "exact outcome" not in q1
    assert "relief do you want" not in q1
    assert "supplier delivery" in q1
    assert "bank notice" in q1

    expected_markers = [
        "contract terms govern quantity",
        "competitor hard drive",
        "bank notice against rajesh personally or the company",
        "part a-d",
    ]
    for answer, marker in zip(["dates", "terms", "access", "bank"], expected_markers):
        loop_result = session.submit_answer(answer)
        assert loop_result["status"] == "clarification_loop"
        assert marker in loop_result["next_question"].lower()


def test_integrated_contract_criminal_banking_final_meets_quality_contract():
    session = _deterministic_session()
    query = (
        "Rajesh, a 35-year-old businessman in Mumbai, signed a contract with a supplier in Gujarat "
        "for 500 lithium batteries worth Rs 50 lakh, but only 200 were delivered. Part A -- Contract Law: "
        "discuss Indian Contract Act sections, partial delivery, specific performance, quantum meruit, civil remedies. "
        "Part B -- Criminal Law / IT Law: Sneha found competitor battery design documents on an external hard drive, "
        "photographed and shared them with Rajesh, who used the designs; competitor filed IPC and IT Act complaint. "
        "Part C -- Banking: Rajesh defaulted on a Rs 10 lakh bank loan and the bank issued notice under the RDDBFI Act. "
        "Part D -- Integrated Analysis: discuss overlapping issues and step-by-step strategy."
    )

    result = session.start_session(query, category="general")
    assert result["status"] == "needs_clarification"

    answers = [
        "Assume all events happened after 1 July 2024.",
        "500 batteries in one lot; Rs 50 lakh payable within 60 days of complete delivery; 7-day inspection; 15-day cure period.",
        "Hard drive was accidentally mixed in; designs were marked Confidential; Sneha photographed and WhatsApped them; Rajesh knowingly used them.",
        "Company is borrower, Rajesh is guarantor; default Rs 10 lakh; collateral inventory and machinery; bank threatens DRT/RDDBFI.",
        "Answer strictly issue-wise under Part A-D with sections, remedies, defenses, banking recovery procedure and likely outcome.",
    ]
    for answer in answers[:-1]:
        assert session.submit_answer(answer)["status"] == "clarification_loop"
    assert session.submit_answer(answers[-1])["status"] == "ready_for_synthesis"

    synthesis = session.synthesize_and_execute()
    final_answer = synthesis["deterministic_answer"]
    final_lower = final_answer.lower()
    quality = session.score_final_answer_quality(final_answer)

    assert quality["passed"] is True
    assert "sale of goods act" in final_lower
    assert "bns" in final_lower
    assert "section 43" in final_lower
    assert "section 66" in final_lower
    assert "66b" in final_lower
    assert "72a" in final_lower
    assert "rddbfi" in final_lower
    assert "threshold" in final_lower
    assert "side" in final_lower or "arguments" in final_lower
    assert "bsa" in final_lower
    assert "likely outcome" in final_lower
    assert "retrieved documents do not provide" not in final_lower


def test_property_fraud_revenue_query_gets_property_specific_5q_plan():
    session = _deterministic_session()
    query = (
        "A 42-year-old woman, Meera, owns agricultural land in Maharashtra inherited from her father. "
        "Her brother claims the land was orally partitioned years ago and sells part of it to a real estate developer. "
        "The developer begins construction after obtaining local permissions. Meera alleges the sale deed is fraudulent "
        "because her signature was forged on a family consent document, the land is still recorded jointly in revenue records, "
        "and she never consented to conversion of agricultural land for commercial use. The developer files a civil suit "
        "for injunction. Meera files a police complaint for forgery, cheating, criminal conspiracy and trespass, a civil suit "
        "for declaration and cancellation of sale deed, temporary injunction, and a revenue complaint challenging mutation. "
        "Part A Property Law, Part B Criminal Law, Part C Revenue and Land Use, Part D Evidence, Part E Integrated Strategy."
    )

    result = session.start_session(query, category="general")

    assert result["status"] == "needs_clarification"
    assert result["total_questions"] == 5
    assert result["intent"]["scenario_specific_gaps"] is True
    q1 = result["first_question"].lower()
    assert "exact outcome" not in q1
    assert "sale deed registration" in q1
    assert "land-use permission" in q1

    expected_markers = [
        "title chain",
        "forged signatures",
        "who is in possession",
        "civil/property rights",
    ]
    for answer, marker in zip(["dates", "title", "forgery", "possession"], expected_markers):
        loop_result = session.submit_answer(answer)
        assert loop_result["status"] == "clarification_loop"
        assert marker in loop_result["next_question"].lower()


# ---------------------------------------------------------------------------
# Regression coverage for the reported bug and for the LLM-first planner.
# ---------------------------------------------------------------------------


def test_matrimonial_scenario_never_asks_the_arrest_question():
    """The reported bug: a family scenario was asked where the arrested person was."""
    session = _deterministic_session()

    result = session.start_session(_MATRIMONIAL_SCENARIO, category="general")

    assert result["status"] == "needs_clarification"
    assert "family_matrimonial" in result["intent"]["detected_domains"]

    questions = [result["first_question"]]
    for _ in range(result["total_questions"] - 1):
        loop_result = session.submit_answer("Assume the facts above.")
        if loop_result["status"] != "clarification_loop":
            break
        questions.append(loop_result["next_question"])

    joined = " ".join(questions).lower()
    # The canned criminal-procedure plan must be unreachable for this scenario.
    assert "arrested person" not in joined
    assert "police custody" not in joined
    assert "judicial custody" not in joined
    assert "arrest memo" not in joined
    # ...and the questions must actually address this scenario's issues.
    assert "shared household" in joined
    assert "incomes" in joined or "monthly incomes" in joined
    assert "child" in joined
    assert len(result["first_question"].split()) >= 6


def test_third_person_scenario_gets_scenario_gaps_not_client_intake():
    """'She filed a case' is a third-person hypothetical, not the user's own intake.

    The personal-case detector also fires on third-person narratives, which used to
    make the planner fall back to generic intake questions ("what is the current
    stage", "what documents do you have") for a fully-described scenario.
    """
    session = _deterministic_session()
    query = (
        "A 29-year-old woman married a Hindu man under the Special Marriage Act, 1954 in Bengaluru. "
        "In January 2026 she left the matrimonial home with their daughter and filed a case under the "
        "Protection of Women from Domestic Violence Act, 2005 seeking a protection order, a residence "
        "order, monthly monetary relief and custody of the child. Her husband filed for divorce alleging "
        "mental cruelty under Section 13(1)(ia) of the Hindu Marriage Act, 1955 and produced WhatsApp "
        "chats between her and her lawyer taken from her laptop. The Family Court must consider the "
        "divorce petition and custody while the Magistrate considers the DV Act proceedings. Analyse "
        "the legal issues arising from these facts under Indian law, including jurisdiction, "
        "maintenance and residence rights, custody principles and burden of proof."
    )

    result = session.start_session(query, category="general")

    assert result["status"] == "needs_clarification"
    assert result["intent"]["question_source"] == "deterministic_plan"
    assert "family_matrimonial" in result["intent"]["detected_domains"]

    questions = [result["first_question"]]
    for _ in range(result["total_questions"] - 1):
        loop_result = session.submit_answer("Assume the facts above.")
        if loop_result["status"] != "clarification_loop":
            break
        questions.append(loop_result["next_question"])

    joined = " ".join(questions).lower()
    assert "arrested person" not in joined
    assert "what is the current stage: notice, fir" not in joined
    assert "shared household" in joined


def test_generic_intake_question_is_never_asked_for_a_named_party_scenario():
    session = _deterministic_session()

    result = session.start_session(_MATRIMONIAL_SCENARIO, category="general")
    questions = [result["first_question"]]
    for _ in range(result["total_questions"] - 1):
        loop_result = session.submit_answer("Assume the facts above.")
        if loop_result["status"] != "clarification_loop":
            break
        questions.append(loop_result["next_question"])

    joined = " ".join(questions).lower()
    assert "what is your exact role" not in joined
    assert "who is the other party" not in joined


def test_llm_gap_analysis_plans_the_session_from_the_scenario(monkeypatch):
    """When the model is usable, its scenario-specific gaps drive the loop verbatim."""
    session = ClarificationSession(provider="groq", enable_llm_gap_analysis=True)
    monkeypatch.setattr(
        session, "_analyze_scenario_gaps_llm", lambda query: dict(_FAKE_GAP_ANALYSIS)
    )

    result = session.start_session(_MATRIMONIAL_SCENARIO, category="general")

    assert result["status"] == "needs_clarification"
    assert result["intent"]["question_source"] == "llm_gap_analysis"
    # Adaptive: one question per real gap, not a padded fixed five.
    assert result["total_questions"] == 3
    assert result["first_question"] == _FAKE_GAP_ANALYSIS["data_gaps"][0]["question"]

    next_question = session.submit_answer("Her laptop was unlocked at home.")["next_question"]
    assert next_question == _FAKE_GAP_ANALYSIS["data_gaps"][1]["question"]

    final = session.submit_answer("Both earn about Rs 1 lakh a month.")
    assert final["next_question"] == _FAKE_GAP_ANALYSIS["data_gaps"][2]["question"]

    assert session.submit_answer("Yes, it was the matrimonial home.")["status"] == "ready_for_synthesis"
    # Model-authored questions must never be wrapped in the canned template prefix.
    assert not result["first_question"].startswith("To answer accurately")


def test_llm_gap_analysis_falls_back_to_deterministic_plan(monkeypatch):
    session = ClarificationSession(provider="groq", enable_llm_gap_analysis=True)
    monkeypatch.setattr(session, "_analyze_scenario_gaps_llm", lambda query: None)

    result = session.start_session(_MATRIMONIAL_SCENARIO, category="general")

    assert result["status"] == "needs_clarification"
    assert result["intent"]["question_source"] == "deterministic_plan"
    assert "arrested person" not in result["first_question"].lower()


def test_llm_gap_analysis_is_disabled_by_config_flag(monkeypatch):
    """A session with the flag off must not call the gap-analysis model at all."""
    calls = []

    def _boom(self, messages):
        calls.append(messages)
        raise AssertionError("gap analysis must not reach the model when disabled")

    # Patch the network boundary, not the method that owns the enable/disable check.
    monkeypatch.setattr(ClarificationSession, "_call_gap_llm", _boom)
    session = _deterministic_session()

    result = session.start_session(_MATRIMONIAL_SCENARIO, category="general")

    assert result["status"] == "needs_clarification"
    assert result["intent"]["question_source"] == "deterministic_plan"
    assert calls == []


def test_session_state_round_trip_preserves_gap_plan():
    """Clarification requests bounce across workers, so gaps must survive persistence."""
    session = _deterministic_session()
    session.gap_plan = [
        {"key": "chats_acquisition", "question": "How were the chats obtained?", "why": "privilege"},
    ]
    session.gap_analysis = {"domains": ["family_matrimonial"]}

    state = session.to_state_dict()
    restored = ClarificationSession.from_state_dict(state)

    assert restored.gap_plan == session.gap_plan
    assert restored.gap_analysis == session.gap_analysis
    assert restored.enable_llm_gap_analysis is False


def test_trivial_definition_detector_is_a_real_instance_method():
    """Regression: this was a nested function called as self._is_trivial_direct_query(...)."""
    session = _deterministic_session()

    assert session._is_trivial_direct_query("What is BNS?") is True
    assert session._is_trivial_direct_query("What is the limitation period for a money suit?") is False


@pytest.mark.skipif(os.getenv("LAW_GPT_GAP_LIVE") != "1", reason="live gap-analysis smoke is opt-in")
def test_live_gap_analysis_produces_scenario_specific_matrimonial_questions():
    """Opt-in smoke test against the real gap-analysis model."""
    session = ClarificationSession(provider="groq", enable_llm_gap_analysis=True)

    result = session.start_session(_MATRIMONIAL_SCENARIO, category="general")

    assert result["status"] == "needs_clarification"
    assert result["intent"]["question_source"] == "llm_gap_analysis"
    assert 2 <= result["total_questions"] <= 5

    questions = [result["first_question"]]
    for _ in range(result["total_questions"] - 1):
        loop_result = session.submit_answer("Assume the facts above; use reasonable assumptions.")
        if loop_result["status"] != "clarification_loop":
            break
        questions.append(loop_result["next_question"])

    joined = " ".join(questions).lower()
    assert "arrested person" not in joined
    assert "police custody" not in joined
    assert len(questions) >= 2
