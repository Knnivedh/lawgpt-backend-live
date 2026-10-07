#!/usr/bin/env python3
"""Build a final before-vs-latest benchmark scorecard."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path("azure_backend_stage/kaanoon_test/benchmark_outputs/complex_15q_20260403")

RUNS = {
    "before": "before_20260403_2237",
    "regressed": "after_20260403_2258",
    "latest": "after_fix_20260404_1233",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def fmt_delta(before: float, after: float, as_pct: bool = False) -> str:
    delta = after - before
    if as_pct:
        return f"{delta * 100:+.2f}%"
    return f"{delta:+.2f}"


def summary_row(label: str, live: dict[str, Any], forensic: dict[str, Any]) -> dict[str, Any]:
    live_summary = live.get("summary", {})
    forensic_summary = forensic.get("summary", {})
    return {
        "label": label,
        "avg_latency_s": float(live_summary.get("avg_latency_s", 0.0)),
        "avg_subquestion_coverage": float(live_summary.get("avg_subquestion_coverage", 0.0)),
        "avg_contract_score": float(live_summary.get("avg_contract_score", 0.0)),
        "successful": int(live_summary.get("successful", 0)),
        "failed": int(live_summary.get("failed", 0)),
        "forensic_pass_count": int(forensic_summary.get("pass_count", 0)),
        "forensic_fail_count": int(forensic_summary.get("fail_count", 0)),
        "forensic_pass_rate": float(forensic_summary.get("pass_rate", 0.0)),
        "high_hallucination_risk_count": int(forensic_summary.get("high_hallucination_risk_count", 0)),
        "weak_subquestion_structure_count": int(forensic_summary.get("weak_subquestion_structure_count", 0)),
    }


def main() -> None:
    rows: dict[str, dict[str, Any]] = {}

    for label, folder in RUNS.items():
        live = load_json(ROOT / folder / "compleqa_live_results.json")
        forensic = load_json(ROOT / folder / "forensic_results.json")
        rows[label] = summary_row(label, live, forensic)

    before = rows["before"]
    regressed = rows["regressed"]
    latest = rows["latest"]

    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "runs": rows,
        "delta_before_to_latest": {
            "avg_latency_s": latest["avg_latency_s"] - before["avg_latency_s"],
            "avg_subquestion_coverage": latest["avg_subquestion_coverage"] - before["avg_subquestion_coverage"],
            "avg_contract_score": latest["avg_contract_score"] - before["avg_contract_score"],
            "forensic_pass_count": latest["forensic_pass_count"] - before["forensic_pass_count"],
            "forensic_fail_count": latest["forensic_fail_count"] - before["forensic_fail_count"],
            "forensic_pass_rate": latest["forensic_pass_rate"] - before["forensic_pass_rate"],
            "weak_subquestion_structure_count": latest["weak_subquestion_structure_count"] - before["weak_subquestion_structure_count"],
        },
        "delta_regressed_to_latest": {
            "avg_latency_s": latest["avg_latency_s"] - regressed["avg_latency_s"],
            "avg_subquestion_coverage": latest["avg_subquestion_coverage"] - regressed["avg_subquestion_coverage"],
            "avg_contract_score": latest["avg_contract_score"] - regressed["avg_contract_score"],
            "forensic_pass_count": latest["forensic_pass_count"] - regressed["forensic_pass_count"],
            "forensic_fail_count": latest["forensic_fail_count"] - regressed["forensic_fail_count"],
            "forensic_pass_rate": latest["forensic_pass_rate"] - regressed["forensic_pass_rate"],
            "weak_subquestion_structure_count": latest["weak_subquestion_structure_count"] - regressed["weak_subquestion_structure_count"],
        },
    }

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_json = ROOT / f"final_before_after_scorecard_{stamp}.json"
    out_md = ROOT / f"final_before_after_scorecard_{stamp}.md"

    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# LAW-GPT Final Stability Scorecard",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Run Summary",
        "",
        "| Run | Avg Latency (s) | Avg Coverage | Avg Contract | Success/Fail | Forensic Pass/Fail | Forensic Pass Rate | High Hallucination Risk | Weak SubQ Structure |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| Before | {before['avg_latency_s']:.2f} | {before['avg_subquestion_coverage']:.2f} | {before['avg_contract_score']:.2f} | "
            f"{before['successful']}/{before['failed']} | {before['forensic_pass_count']}/{before['forensic_fail_count']} | "
            f"{safe_pct(before['forensic_pass_rate'])} | {before['high_hallucination_risk_count']} | {before['weak_subquestion_structure_count']} |"
        ),
        (
            f"| Regressed | {regressed['avg_latency_s']:.2f} | {regressed['avg_subquestion_coverage']:.2f} | {regressed['avg_contract_score']:.2f} | "
            f"{regressed['successful']}/{regressed['failed']} | {regressed['forensic_pass_count']}/{regressed['forensic_fail_count']} | "
            f"{safe_pct(regressed['forensic_pass_rate'])} | {regressed['high_hallucination_risk_count']} | {regressed['weak_subquestion_structure_count']} |"
        ),
        (
            f"| Latest | {latest['avg_latency_s']:.2f} | {latest['avg_subquestion_coverage']:.2f} | {latest['avg_contract_score']:.2f} | "
            f"{latest['successful']}/{latest['failed']} | {latest['forensic_pass_count']}/{latest['forensic_fail_count']} | "
            f"{safe_pct(latest['forensic_pass_rate'])} | {latest['high_hallucination_risk_count']} | {latest['weak_subquestion_structure_count']} |"
        ),
        "",
        "## Delta (Before -> Latest)",
        "",
        f"- Avg latency (s): {before['avg_latency_s']:.2f} -> {latest['avg_latency_s']:.2f} ({fmt_delta(before['avg_latency_s'], latest['avg_latency_s'])})",
        f"- Avg subquestion coverage: {before['avg_subquestion_coverage']:.2f} -> {latest['avg_subquestion_coverage']:.2f} ({fmt_delta(before['avg_subquestion_coverage'], latest['avg_subquestion_coverage'])})",
        f"- Avg contract score: {before['avg_contract_score']:.2f} -> {latest['avg_contract_score']:.2f} ({fmt_delta(before['avg_contract_score'], latest['avg_contract_score'])})",
        f"- Forensic pass count: {before['forensic_pass_count']} -> {latest['forensic_pass_count']} ({latest['forensic_pass_count'] - before['forensic_pass_count']:+d})",
        f"- Forensic pass rate: {safe_pct(before['forensic_pass_rate'])} -> {safe_pct(latest['forensic_pass_rate'])} ({fmt_delta(before['forensic_pass_rate'], latest['forensic_pass_rate'], as_pct=True)})",
        f"- Weak subquestion structure count: {before['weak_subquestion_structure_count']} -> {latest['weak_subquestion_structure_count']} ({latest['weak_subquestion_structure_count'] - before['weak_subquestion_structure_count']:+d})",
        "",
        "## Delta (Regressed -> Latest)",
        "",
        f"- Avg subquestion coverage: {regressed['avg_subquestion_coverage']:.2f} -> {latest['avg_subquestion_coverage']:.2f} ({fmt_delta(regressed['avg_subquestion_coverage'], latest['avg_subquestion_coverage'])})",
        f"- Avg contract score: {regressed['avg_contract_score']:.2f} -> {latest['avg_contract_score']:.2f} ({fmt_delta(regressed['avg_contract_score'], latest['avg_contract_score'])})",
        f"- Forensic pass count: {regressed['forensic_pass_count']} -> {latest['forensic_pass_count']} ({latest['forensic_pass_count'] - regressed['forensic_pass_count']:+d})",
        f"- Forensic pass rate: {safe_pct(regressed['forensic_pass_rate'])} -> {safe_pct(latest['forensic_pass_rate'])} ({fmt_delta(regressed['forensic_pass_rate'], latest['forensic_pass_rate'], as_pct=True)})",
        f"- Weak subquestion structure count: {regressed['weak_subquestion_structure_count']} -> {latest['weak_subquestion_structure_count']} ({latest['weak_subquestion_structure_count'] - regressed['weak_subquestion_structure_count']:+d})",
    ]

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"Saved: {out_json}")
    print(f"Saved: {out_md}")


if __name__ == "__main__":
    main()
