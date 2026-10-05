"""
Generates reasoning_eval/golden_dataset.csv for evaluating
nodes/reasoning_explainer.py::DynamicReasoningExplainer.analyze_precedent_usage().

Each row pairs one case scenario + a fixed reference response with one real
precedent from the corpus, labelled as clearly relevant ("high") or clearly
irrelevant ("low"). The irrelevant ones include precedents the deployed app
actually showed for the wrong query during manual testing (e.g. the school
admission and caste-breakup posts for the eviction question).

The harness should pass the precedent's full parent content (looked up by
parent_id) and the reference_response to analyze_precedent_usage(), then
check: usage_score band, whether matching_factors invent similarities for
"low" rows, and whether key_excerpt appears verbatim in the precedent.
"""

import csv
import json
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]

SCENARIOS = [
    dict(id="S1", case_summary="Hindu woman, married 2019, evicted from the joint-family home by her in-laws in 2023 without notice; now living at her parents' home; not divorced; no income. Asks whether she has a right to reside in the matrimonial home.",
         reference_response="Under s.17 of the Protection of Women from Domestic Violence Act, 2005 you have a right to reside in the shared household, even if it is owned by your in-laws. You can apply to a Magistrate for a residence order under s.19 and also seek maintenance. Being thrown out without notice supports your claim.",
         precedents=[(2845, "high", "Directly discusses a daughter-in-law's right to live in the in-laws' house. Caution: its expert answer says she needs the father-in-law's permission, which conflicts with Satish Chander Ahuja v. Sneha Ahuja (2020). Topically relevant, but an explainer should not present it as supporting the reference response."),
                     (754, "high", "Right of residence under the DV Act - the exact legal basis of the answer."),
                     (250, "low", "Pre-marital breakup over caste; no marriage, no residence issue. Shown wrongly in manual testing."),
                     (2156, "low", "School admission cancellation; unrelated to family law remedies. Shown wrongly in manual testing.")]),
    dict(id="S2", case_summary="Hindu woman married in 2015 with a 6-year-old daughter; husband left in 2021 and pays nothing; she has no income and lives with her parents.",
         reference_response="You can claim maintenance for yourself and your daughter under s.125 CrPC (now s.144 BNSS) and ask for interim maintenance while the case is pending. The court will consider your husband's income and your needs.",
         precedents=[(86, "high", "Wife seeking maintenance from husband."),
                     (113, "high", "Timeline for interim maintenance - matches the interim relief advice."),
                     (150, "low", "Adoption procedure; unrelated.")]),
    dict(id="S3", case_summary="Hindu couple married in 2018, no children, separated since 2022, both agree to divorce.",
         reference_response="You can file a joint petition for divorce by mutual consent under s.13B of the Hindu Marriage Act after living separately for at least a year. The second motion follows a six-month cooling-off period, which the court can waive.",
         precedents=[(69, "high", "Divorce by mutual consent - core topic."),
                     (16, "high", "Conversion of contested divorce to mutual consent - closely related procedure."),
                     (2083, "low", "Jewellery not returned by in-laws; different issue entirely.")]),
    dict(id="S4", case_summary="Hindu father, separated, 5-year-old daughter living with the mother, who refuses to let him meet the child.",
         reference_response="The child's welfare is paramount. You can apply to the family court for visitation under the Guardians and Wards Act or s.26 HMA; courts usually let the non-custodial parent meet the child, while a child under five ordinarily stays with the mother.",
         precedents=[(154, "high", "Visitation rights without a full custody case - directly on point."),
                     (161, "high", "Visitation and joint custody."),
                     (330, "low", "Extra-marital affair; no custody or visitation question. Shown wrongly in manual testing.")]),
    dict(id="S5", case_summary="Hindu woman married two years, living with in-laws who verbally abuse and threaten her for dowry.",
         reference_response="Demanding dowry is an offence under s.4 of the Dowry Prohibition Act, and cruelty for dowry is punishable under s.498A IPC (now BNS s.85). You can complain to the police or a Protection Officer under the DV Act; keep messages and witness details as evidence.",
         precedents=[(9, "high", "Dowry and domestic violence."),
                     (175, "high", "Domestic violence and dowry."),
                     (2156, "low", "School admission; unrelated.")]),
    dict(id="S6", case_summary="Hindu wife, marriage registered in 2017, not divorced; husband is about to marry another woman.",
         reference_response="A second marriage while your marriage subsists is void under s.11 HMA and bigamy is an offence under s.494 IPC (now BNS s.82). You can file a complaint and seek an injunction to stop the marriage; your right to maintenance continues.",
         precedents=[(225, "high", "Second marriage without divorcing first wife."),
                     (80, "high", "Second marriage without the woman's divorce."),
                     (893, "low", "Underage marriage; different legal issue.")]),
    dict(id="S7", case_summary="Hindu husband married in 2020; wife filed a 498A FIR against him and his parents last month; no chargesheet yet.",
         reference_response="You and your parents can apply for anticipatory bail, and police must follow the Arnesh Kumar guidelines, so arrest is not automatic. Quashing or a mediated settlement may be possible later; preserve evidence and avoid contact that could look like pressure.",
         precedents=[(177, "high", "498A/406 case handling."),
                     (226, "high", "498A compromise and non-cooperation."),
                     (381, "low", "Interfaith marriage question; unrelated to a 498A defence.")]),
    dict(id="S8", case_summary="Muslim woman whose husband pronounced triple talaq over the phone last month.",
         reference_response="Instant triple talaq is void and illegal under the Muslim Women (Protection of Rights on Marriage) Act, 2019 and punishable with up to three years. You are entitled to a subsistence allowance and custody of minor children, and you can complain to the police or a Magistrate.",
         precedents=[(413, "high", "Talaqnama - talaq procedure."),
                     (146, "high", "Single vs triple talaq."),
                     (2052, "low", "Sole guardianship by a single mother; unrelated to talaq validity.")]),
    dict(id="S9", case_summary="Hindu woman whose husband left three years ago and has had no contact since.",
         reference_response="Desertion for a continuous two years without reasonable cause is a ground for divorce under s.13(1)(ib) HMA. You will need to show he intended to end the marriage; you can also claim maintenance.",
         precedents=[(30, "high", "Whether desertion leads to divorce."),
                     (1133, "high", "Desertion by NRI husband."),
                     (250, "low", "Pre-marital breakup over caste; unrelated.")]),
    dict(id="S10", case_summary="Hindu woman living apart from her husband; in-laws refuse to return her wedding jewellery and stridhan.",
         reference_response="Stridhan is your absolute property. Withholding it can be criminal breach of trust (s.406 IPC / BNS s.316), and a Magistrate can order its return under s.19(8) of the DV Act; a civil recovery suit is also possible.",
         precedents=[(2083, "high", "In-laws not returning jewellery - directly on point."),
                     (1552, "high", "Claiming stridhan articles from the groom's parents."),
                     (589, "low", "General marital problems of the client's sister; no stridhan issue. Shown in manual testing for an unrelated query.")]),
]

FIELDNAMES = ["id", "scenario_id", "case_summary", "reference_response", "precedent_parent_id",
              "precedent_title", "precedent_excerpt", "expected_relevance",
              "expected_usage_score_band", "rationale"]


def load_parents():
    parents = {}
    for name in ("family_law_chunks.json", "family_law_2_chunks.json"):
        for item in json.load(open(BACKEND / "data" / "chunked" / name, encoding="utf-8")):
            if item["metadata"].get("is_parent"):
                parents[item["metadata"]["parent_id"]] = item
    return parents


def main():
    parents = load_parents()
    missing = sorted({pid for s in SCENARIOS for pid, _, _ in s["precedents"] if pid not in parents})
    if missing:
        raise SystemExit(f"Unknown parent_ids (not in corpus): {missing}")

    rows = []
    for s in SCENARIOS:
        for pid, rel, why in s["precedents"]:
            p = parents[pid]
            rows.append(dict(
                scenario_id=s["id"], case_summary=s["case_summary"],
                reference_response=s["reference_response"], precedent_parent_id=pid,
                precedent_title=p["metadata"]["title"],
                precedent_excerpt=" ".join(p["content"].split())[:300],
                expected_relevance=rel,
                expected_usage_score_band=">= 0.5" if rel == "high" else "<= 0.3",
                rationale=why,
            ))

    out = Path(__file__).resolve().parent / "golden_dataset.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for i, row in enumerate(rows, 1):
            w.writerow({"id": i, **row})
    print(f"Wrote {len(rows)} rows ({len(SCENARIOS)} scenarios) to {out}")
    print("Relevance counts:", Counter(r["expected_relevance"] for r in rows))


if __name__ == "__main__":
    main()
