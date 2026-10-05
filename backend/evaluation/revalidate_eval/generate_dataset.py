"""
Generates revalidate_eval/golden_dataset.csv for evaluating QueryAnalyzer
when it is re-invoked by revalidate_information_node (graph.py) on
"root_query + My Information: <collected facts>".

Each scenario is a sequence of rounds with a growing info_collected. The
key question per row: given these facts, should the analyzer say nothing
more is needed (converged=yes), or is something critical still missing?
The final round of each scenario repeats the previous round's input
exactly, to test stability (same input -> same decision).

info_collected cells use " | " between facts and ": " between key/value.
"""

import csv
from collections import Counter
from pathlib import Path

PRIVACY = "residential_address | phone_number | aadhaar_or_pan | bank_details | workplace_details"

SCENARIOS = [
    dict(id="S1", topic="eviction / right to reside", source="manual test transcript",
         root_query="मेरी शादी 2019 में हुई थी और मेरे ससुराल वालों ने मुझे 2023 में घर से निकाल दिया, क्या मुझे घर में रहने का अधिकार है?",
         rounds=[
             dict(facts="marriage_year: 2019 | eviction_year: 2023 | evicted_by: in-laws",
                  converged="no", still_missing="religion | living_arrangement_or_ownership | current_residence",
                  notes="Round 1 after initial analysis."),
             dict(facts="marriage_year: 2019 | eviction_year: 2023 | evicted_by: in-laws | religion: Hindu | living_arrangement: joint family with in-laws",
                  converged="no", still_missing="current_residence | divorce_status",
                  notes="Acceptable to converge here too; reviewer may mark either."),
             dict(facts="marriage_year: 2019 | eviction_year: 2023 | evicted_by: in-laws | religion: Hindu | living_arrangement: joint family with in-laws | current_residence: parents' home | divorce_status: not divorced | notice_given: none, no reason given",
                  converged="yes", still_missing="",
                  notes="In manual testing the bot kept going here (income, relationship with parents, marriage registration, legal-opinion question). Those are scope creep."),
             dict(facts="marriage_year: 2019 | eviction_year: 2023 | evicted_by: in-laws | religion: Hindu | living_arrangement: joint family with in-laws | current_residence: parents' home | divorce_status: not divorced | notice_given: none, no reason given",
                  converged="yes", still_missing="", notes="Stability repeat of previous round."),
         ],
         scope_creep="income | relationship_with_parents | marriage_registration_proof | client's_legal_opinion_on_HMA | in_laws_attitude"),
    dict(id="S2", topic="maintenance after desertion", source="synthetic",
         root_query="My husband left me and my daughter and does not pay anything. Can I claim maintenance?",
         rounds=[
             dict(facts="client_role: wife | husband_left: 2021 | support_paid: none",
                  converged="no", still_missing="religion | children_details | own_income", notes=""),
             dict(facts="client_role: wife | husband_left: 2021 | support_paid: none | religion: Hindu | marriage_year: 2015 | child: daughter aged 6",
                  converged="no", still_missing="own_income_or_employment", notes=""),
             dict(facts="client_role: wife | husband_left: 2021 | support_paid: none | religion: Hindu | marriage_year: 2015 | child: daughter aged 6 | own_income: none | residence: with parents",
                  converged="yes", still_missing="", notes="Husband's income is useful but not required for preliminary advice."),
             dict(facts="client_role: wife | husband_left: 2021 | support_paid: none | religion: Hindu | marriage_year: 2015 | child: daughter aged 6 | own_income: none | residence: with parents",
                  converged="yes", still_missing="", notes="Stability repeat."),
         ],
         scope_creep="husband's_address | daughter's_school | husband's_employer | bank_details"),
    dict(id="S3", topic="mutual consent divorce", source="synthetic",
         root_query="My wife and I both want a divorce. How do we proceed?",
         rounds=[
             dict(facts="consent: both agree to divorce",
                  converged="no", still_missing="religion | marriage_date | separation_duration", notes=""),
             dict(facts="consent: both agree to divorce | religion: Hindu (both) | marriage_year: 2018 | separated_since: 2022 | children: none",
                  converged="yes", still_missing="", notes=""),
             dict(facts="consent: both agree to divorce | religion: Hindu (both) | marriage_year: 2018 | separated_since: 2022 | children: none",
                  converged="yes", still_missing="", notes="Stability repeat."),
         ],
         scope_creep="reason_for_divorce | property_list | income_of_both"),
    dict(id="S4", topic="father seeking visitation", source="Visitation rights to child - is custody case required?",
         root_query="My wife is not letting me meet my daughter after our separation. How can I get visitation rights?",
         rounds=[
             dict(facts="client_role: father | status: separated | child: daughter | access: denied",
                  converged="no", still_missing="child_age | current_custody | religion", notes=""),
             dict(facts="client_role: father | status: separated | child: daughter aged 5 | access: denied | current_custody: with mother | religion: Hindu",
                  converged="yes", still_missing="", notes=""),
             dict(facts="client_role: father | status: separated | child: daughter aged 5 | access: denied | current_custody: with mother | religion: Hindu",
                  converged="yes", still_missing="", notes="Stability repeat."),
         ],
         scope_creep="father's_income | child's_school_name | mother's_workplace"),
    dict(id="S5", topic="dowry harassment", source="Harassed by my in-laws for money",
         root_query="Shaadi ko 2 saal hue hain, sasural wale dahej ke liye pareshan karte hain, kya karun?",
         rounds=[
             dict(facts="marriage_duration: 2 years | dowry_harassment: by in-laws",
                  converged="no", still_missing="religion | nature_of_harassment | current_residence", notes=""),
             dict(facts="marriage_duration: 2 years | dowry_harassment: by in-laws | religion: Hindu | nature: verbal abuse and threats | residence: lives with in-laws",
                  converged="yes", still_missing="", notes=""),
             dict(facts="marriage_duration: 2 years | dowry_harassment: by in-laws | religion: Hindu | nature: verbal abuse and threats | residence: lives with in-laws",
                  converged="yes", still_missing="", notes="Stability repeat."),
         ],
         scope_creep="dowry_amount_given_at_marriage | in_laws_income | names_of_in_laws"),
    dict(id="S6", topic="bigamy", source="Remarriage without divorce",
         root_query="मेरे पति दूसरी शादी कर रहे हैं जबकि हमारा तलाक नहीं हुआ है, मैं क्या करूँ?",
         rounds=[
             dict(facts="divorce_status: not divorced | husband: remarrying",
                  converged="no", still_missing="religion", notes="Religion is decisive here (personal law differs)."),
             dict(facts="divorce_status: not divorced | husband: remarrying | religion: Hindu (both) | marriage_registered: yes, 2017",
                  converged="yes", still_missing="", notes=""),
             dict(facts="divorce_status: not divorced | husband: remarrying | religion: Hindu (both) | marriage_registered: yes, 2017",
                  converged="yes", still_missing="", notes="Stability repeat."),
         ],
         scope_creep="second_wife's_name | wedding_venue | husband's_income"),
    dict(id="S7", topic="498A defence", source="498a/406",
         root_query="My wife filed a false 498A case against me and my parents.",
         rounds=[
             dict(facts="case: 498A against husband and parents | filed_by: wife",
                  converged="no", still_missing="stage_of_case | marriage_duration", notes=""),
             dict(facts="case: 498A against husband and parents | filed_by: wife | stage: FIR last month, no chargesheet | marriage_year: 2020 | religion: Hindu",
                  converged="yes", still_missing="", notes=""),
             dict(facts="case: 498A against husband and parents | filed_by: wife | stage: FIR last month, no chargesheet | marriage_year: 2020 | religion: Hindu",
                  converged="yes", still_missing="", notes="Stability repeat."),
         ],
         scope_creep="police_station_name | FIR_number | wife's_family_details"),
    dict(id="S8", topic="informational (void vs voidable)", source="synthetic",
         root_query="What is the difference between a void and a voidable marriage?",
         rounds=[
             dict(facts="(none)", converged="yes", still_missing="",
                  notes="General legal question; no personal facts are needed. Asking any is scope creep."),
             dict(facts="(none)", converged="yes", still_missing="", notes="Stability repeat."),
         ],
         scope_creep="religion | marriage_date | children"),
    dict(id="S9", topic="triple talaq", source="Talaqnama",
         root_query="My sister, a Muslim woman, was given triple talaq over the phone last month by her husband. What legal action can she take?",
         rounds=[
             dict(facts="aggrieved_person: client's sister | religion: Muslim | event: triple talaq over phone | when: last month",
                  converged="yes", still_missing="",
                  notes="Key facts already present in the first message; children/mehr are optional."),
         ],
         scope_creep="husband's_income | sister's_address | wedding_details"),
    dict(id="S10", topic="NRI desertion", source="Desertion by NRI husband",
         root_query="My husband went to the USA two years ago and has not contacted me since. What can I do?",
         rounds=[
             dict(facts="husband_location: USA | left: 2 years ago | contact: none",
                  converged="no", still_missing="religion | place_of_marriage | relief_sought", notes=""),
             dict(facts="husband_location: USA | left: 2 years ago | contact: none | religion: Hindu | married_in: India, 2019 | relief_sought: maintenance and divorce",
                  converged="yes", still_missing="", notes=""),
             dict(facts="husband_location: USA | left: 2 years ago | contact: none | religion: Hindu | married_in: India, 2019 | relief_sought: maintenance and divorce",
                  converged="yes", still_missing="", notes="Stability repeat."),
         ],
         scope_creep="husband's_US_address | visa_type | employer_name"),
]

FIELDNAMES = ["id", "scenario_id", "round", "topic", "source", "root_query", "info_collected",
              "expected_converged", "acceptable_still_missing", "scope_creep_fields", "must_not_ask", "notes"]


def main():
    rows = []
    for s in SCENARIOS:
        for r_idx, r in enumerate(s["rounds"], 1):
            rows.append(dict(
                scenario_id=s["id"], round=r_idx, topic=s["topic"], source=s["source"],
                root_query=s["root_query"], info_collected=r["facts"],
                expected_converged=r["converged"], acceptable_still_missing=r["still_missing"],
                scope_creep_fields=s["scope_creep"],
                must_not_ask="any key already in info_collected | " + PRIVACY,
                notes=r["notes"],
            ))
    out = Path(__file__).resolve().parent / "golden_dataset.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for i, row in enumerate(rows, 1):
            w.writerow({"id": i, **row})
    print(f"Wrote {len(rows)} rows ({len(SCENARIOS)} scenarios) to {out}")
    print("Converged counts:", Counter(r["expected_converged"] for r in rows))


if __name__ == "__main__":
    main()
