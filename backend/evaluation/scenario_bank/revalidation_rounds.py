"""
Conversation rounds for the revalidation dataset (used by build_datasets.py).

Each scenario is a short conversation. Round 1 holds only what the user's first
message said (the scenario's analyzer.info_provided); every later round adds the
facts listed here. For each round the dataset says whether the revalidation
node should now stop asking (converged) and, if not, what it may still ask.

Three patterns:
  no -> no -> yes       an essential fact (usually religion, which decides the
                        applicable law) is still missing after the first reply
  no -> yes -> yes      the last round adds only a non-answer to an optional
                        question; the node must not reopen the questioning
  yes -> yes -> yes     the first message was already complete

Each round: (facts added, converged, what may still be asked, note)
"""

NA = "NOT_PROVIDED"

ROUNDS = {
    # ── parallel ────────────────────────────────────────────────────────────
    "P02": dict(
        creep="income | detailed_reasons_for_breakdown | property_details | spouse's_employer",
        rounds=[
            ("", "no", "religion | separation_duration | whether_spouse_agrees | children", "Only the first message."),
            ("children: none | whether_spouse_agrees: yes", "no", "religion | separation_duration",
             "Religion decides which Act applies and is still unknown."),
            ("religion: Hindu | separation_duration: 14 months", "yes", "", "All essentials known."),
        ]),
    "P12": dict(
        creep="wife's_income | property_details | wife's_family_details",
        rounds=[
            ("", "no", "religion | who_left_and_why | marriage_date | children", "Only the first message."),
            ("who_left: wife left on her own in 2022 after a fight with the client's mother | children: none", "no", "religion",
             "Religion is still unknown."),
            ("religion: Hindu | marriage_year: 2019", "yes", "", "All essentials known."),
        ]),
    "P23": dict(
        creep="husband's_salary | name_of_the_colleague | wedding_expenses",
        rounds=[
            ("", "no", "religion | marriage_date | list_or_proof_of_items | children", "Only the first message."),
            ("current_residence: parents' home for two months | children: none", "no", "religion | list_or_proof_of_items",
             "Religion is still unknown."),
            ("religion: Hindu | marriage_year: 2023 | items: about 150 g gold jewellery and clothes, purchase bills available", "yes", "",
             "All essentials known."),
        ]),
    "P05": dict(
        creep="income | children's_school | detailed_grounds_for_divorce",
        rounds=[
            ("", "no", "religion | client_current_city | marriage_date", "Only the first message."),
            ("religion: Hindu | client_current_city: Bengaluru", "yes", "", "Enough to answer the jurisdiction question."),
            (f"grounds_for_divorce: {NA}", "yes", "", "The user did not answer an optional question; do not reopen."),
        ]),
    "P22": dict(
        creep="wedding_expenses | husband's_income | details_of_intimacy",
        rounds=[
            ("", "no", "religion | medical_evidence | daughter's_own_wishes", "Only the first message."),
            ("religion: Hindu | daughter's_own_wishes: wants to end the marriage", "yes", "", "Enough to answer."),
            (f"medical_evidence: {NA}", "yes", "", "The user did not answer an optional question; do not reopen."),
        ]),
    "P29": dict(
        creep="identity_of_the_other_woman | husband's_salary | how_she_got_into_the_phone",
        rounds=[
            ("", "no", "religion | whether_living_together | child_age", "Only the first message."),
            ("religion: Hindu | living_together: same house, separate rooms for about four months", "yes", "", "Enough to answer."),
            (f"whether_she_wants_maintenance_or_custody: {NA}", "yes", "", "The user did not answer an optional question; do not reopen."),
        ]),
    "P04": dict(
        creep="husband's_salary_details | caste | wedding_expenses | details_of_each_incident",
        rounds=[
            ("", "yes", "", "The first message already gives religion, dates, the abuse and the loss of support."),
            ("current_residence: parents' house in Pune since last month | children: none", "yes", "", "Extra facts; still complete."),
            ("own_income: none", "yes", "", "Extra fact; still complete."),
        ]),
    "P10": dict(
        creep="reason_for_separation | marriage_date | wedding_details",
        rounds=[
            ("", "yes", "", "The order, the amount and the default are all stated."),
            ("law_under_which_order_was_passed: s.125 CrPC | arrears_total: Rs 1,20,000", "yes", "", "Extra facts; still complete."),
            ("husband_employment: salaried, private company", "yes", "", "Extra fact; still complete."),
        ]),
    "P19": dict(
        creep="husband's_income | second_woman's_family | caste",
        rounds=[
            ("", "yes", "", "Religion, subsisting marriage and the second marriage are all stated."),
            ("evidence: wedding photographs, priest willing to give a statement", "yes", "", "Extra fact; still complete."),
            ("children: one daughter aged 4", "yes", "", "Extra fact; still complete."),
        ]),
    "P24": dict(
        creep="husband's_reason | sect | wedding_expenses",
        rounds=[
            ("", "yes", "", "Religion, the form of talaq, the children and the reliefs sought are all stated."),
            ("children_ages: daughter 3, son 6", "yes", "", "Extra fact; still complete."),
            ("own_income: none | mehr_status: unpaid", "yes", "", "Extra facts; still complete."),
        ]),
    # ── English ─────────────────────────────────────────────────────────────
    "L-en-01": dict(
        creep="reasons_for_non_consummation | wedding_expenses | wife's_family_details",
        rounds=[
            ("", "no", "religion | wife's_income | any_case_already_filed", "Only the first message."),
            ("any_case_filed: none, only discussions between the families", "no", "religion | wife's_income", "Religion is still unknown."),
            ("religion: Hindu | wife_income: about Rs 30,000/month", "yes", "", "All essentials known."),
            (f"assets: {NA}", "yes", "", "The user did not answer an optional question; do not reopen."),
        ]),
    "L-en-05": dict(
        creep="reason_for_first_divorce | present_husband's_income | maintenance_from_ex-husband",
        rounds=[
            ("", "no", "religion | daughter's_age | whether_biological_father_consents_or_can_be_traced", "Only the first message."),
            ("religion: Hindu | daughter's_age: 12", "yes", "", "Enough to answer."),
            (f"biological_father_consent: {NA}", "yes", "", "The user did not answer an optional question; do not reopen."),
        ]),
    "L-en-04": dict(
        creep="new_wife's_income | reason_for_the_2019_divorce | wedding_details",
        rounds=[
            ("", "yes", "", "The decree, the amount and the changed circumstances are all stated."),
            ("terms_in_decree: yes, clause 4 of the recorded settlement", "yes", "", "Extra fact; still complete."),
            ("ex_wife_income: about Rs 40,000/month | ex_wife_remarried: no", "yes", "", "Extra facts; still complete."),
        ]),
    # ── Hindi ───────────────────────────────────────────────────────────────
    "L-hi-03": dict(
        creep="wife's_family_details | dowry_details | client's_income",
        rounds=[
            ("", "no", "religion | reason_wife_left | children | marriage_date", "Only the first message."),
            ("marriage_year: 2021 | children: one son aged 3", "no", "religion | reason_wife_left", "Religion is still unknown."),
            ("religion: Hindu | reason_wife_left: quarrels with his mother", "yes", "", "All essentials known."),
            (f"wife_income: {NA}", "yes", "", "The user did not answer an optional question; do not reopen."),
        ]),
    "L-hi-06": dict(
        creep="cause_of_husband's_death | children's_school | remarriage_plans",
        rounds=[
            ("", "no", "religion | whose_name_the_property_is_in | whether_husband_left_a_will", "Only the first message."),
            ("religion: Hindu | property: house in father-in-law's name; husband had a plot in his own name", "yes", "", "Enough to answer."),
            (f"will: {NA}", "yes", "", "The user does not know; do not reopen."),
        ]),
    "L-hi-05": dict(
        creep="second_wife's_details | sect | husband's_reason",
        rounds=[
            ("", "yes", "", "Religion, the second nikah, the children and the lack of support are all stated."),
            ("children_ages: 4, 7 and 10 | living_together: no, at her parents' home for six months", "yes", "", "Extra facts; still complete."),
            ("own_income: none | mehr_status: unpaid", "yes", "", "Extra facts; still complete."),
        ]),
    # ── Hinglish ────────────────────────────────────────────────────────────
    "L-hien-02": dict(
        creep="details_of_intimacy | husband's_income | wedding_expenses",
        rounds=[
            ("", "no", "religion | medical_report | whether_living_together", "Only the first message."),
            ("living_together: no, at her parents' home for one month", "no", "religion", "Religion is still unknown."),
            ("religion: Hindu, Arya Samaj marriage", "yes", "", "All essentials known."),
            ("medical_report: doctor's prescription only", "yes", "", "Extra fact; still complete."),
        ]),
    "L-hien-07": dict(
        creep="reason_for_divorce | incomes | wife's_job_details",
        rounds=[
            ("", "no", "religion | children | whether_settlement_terms_are_final", "Only the first message."),
            ("religion: Hindu | children: one daughter aged 3, to stay with the wife; Rs 10,000/month agreed", "yes", "", "Enough to answer."),
            (f"date_of_first_motion: {NA}", "yes", "", "The user did not answer an optional question; do not reopen."),
        ]),
    "L-hien-04": dict(
        creep="reason_for_divorce | ex-wife's_new_partner | maintenance_paid",
        rounds=[
            ("", "yes", "", "The order and the continuing default are stated."),
            ("court: Family Court, Pune, 2024, with the divorce decree", "yes", "", "Extra fact; still complete."),
            ("child_age: 6 | missed_visits_documented: WhatsApp messages", "yes", "", "Extra facts; still complete."),
        ]),
    # ── Tamil ───────────────────────────────────────────────────────────────
    "L-ta-08": dict(
        creep="dowry_details | wife's_family_details | client's_income",
        rounds=[
            ("", "no", "religion | reason_wife_left | children", "Only the first message."),
            ("children: none", "no", "religion | reason_wife_left", "Religion is still unknown."),
            ("religion: Hindu | reason_wife_left: quarrel with his mother", "yes", "", "All essentials known."),
            (f"wife_employment: {NA}", "yes", "", "The user did not answer an optional question; do not reopen."),
        ]),
    "L-ta-10": dict(
        creep="other_woman's_details | caste | husband's_income",
        rounds=[
            ("", "no", "religion | witnesses_to_the_wedding | other_documents_showing_them_as_spouses", "Only the first message."),
            ("religion: Hindu | other_documents: joint rental agreement, Aadhaar cards with the same address", "yes", "", "Enough to answer."),
            (f"witnesses_to_the_wedding: {NA}", "yes", "", "The user did not answer an optional question; do not reopen."),
        ]),
    "L-ta-04": dict(
        creep="church_denomination | detailed_reasons | income",
        rounds=[
            ("", "yes", "", "Religion, the church wedding and two years' separation are stated."),
            ("whether_the_wife_agrees: yes, ready to file jointly", "yes", "", "Extra fact; still complete."),
            ("children: none", "yes", "", "Extra fact; still complete."),
        ]),
    # ── Kannada ─────────────────────────────────────────────────────────────
    "L-kn-05": dict(
        creep="first_wife's_address | husband's_caste | wedding_expenses",
        rounds=[
            ("", "no", "religion | whether_the_first_wife_is_alive_and_undivorced | proof_of_marriage", "Only the first message."),
            ("marriage_year: 2020 | proof_of_marriage: wedding photographs and invitation card", "no", "religion", "Religion is still unknown."),
            ("religion: Hindu", "yes", "", "All essentials known."),
            (f"first_wife_status: {NA}", "yes", "", "The user does not know; do not reopen."),
        ]),
    "L-kn-06": dict(
        creep="visa_country | spouse's_income | reason_for_not_registering",
        rounds=[
            ("", "no", "religion | state_or_city | available_proof_of_the_wedding", "Only the first message."),
            ("religion: Hindu | city: Mysuru", "yes", "", "Enough to answer."),
            (f"available_proof_of_the_wedding: {NA}", "yes", "", "The user did not answer an optional question; do not reopen."),
        ]),
    "L-kn-08": dict(
        creep="sect | reason_for_talaq | husband's_new_marriage",
        rounds=[
            ("", "yes", "", "Religion, the talaq, the unpaid mehr and the relief sought are stated."),
            ("children: none | how_talaq_was_given: one pronouncement a month over three months", "yes", "", "Extra facts; still complete."),
            ("own_income: none | mehr_amount: Rs 1 lakh", "yes", "", "Extra facts; still complete."),
        ]),
}
