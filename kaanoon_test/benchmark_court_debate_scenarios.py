import json
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from kaanoon_test.court_debate_engine import CourtDebateEngineV2


SCENARIOS = [
    {
        "name": "interfaith_marriage_autonomy",
        "query": (
            "A Hindu woman and a Muslim man marry under the Special Marriage Act, 1954 without converting. "
            "Her family alleges coercion and love jihad, and she says she married willingly and fears her family."
        ),
    },
    {
        "name": "live_in_relationship_maintenance",
        "query": (
            "An interfaith couple lives together for 5 years without marriage. After separation, "
            "the woman claims maintenance rights and domestic violence protection, and the man argues there was no marriage."
        ),
    },
]


def main() -> None:
    engine = CourtDebateEngineV2.__new__(CourtDebateEngineV2)
    rows = []
    for item in SCENARIOS:
        preplan = engine._build_preplan(item["query"], session_id=f"bench_{item['name']}", conversation_history="")
        issues = preplan["issue_map"]
        issue_text = " ".join(issue["label"] + " " + issue["question"] for issue in issues).lower()
        hints = engine._authority_hints(item["query"]).lower()
        rows.append(
            {
                "scenario": item["name"],
                "detected_family": preplan["scenario_family"],
                "detected_domain": preplan["legal_domain"],
                "issue_count": len(issues),
                "issue_text": issue_text,
                "authority_hints": hints,
                "required_authorities": [row["name"] for row in preplan["authority_matrix"]],
                "forbidden_carryover_terms": preplan["forbidden_carryover_terms"],
            }
        )

    out_path = Path(__file__).with_name("benchmark_court_debate_scenarios.json")
    out_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
