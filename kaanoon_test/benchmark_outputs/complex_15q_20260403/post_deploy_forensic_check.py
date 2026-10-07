#!/usr/bin/env python3
"""
Post-deploy forensic audit against compleQA scenarios.
Focuses on risk patterns from big_issue.md:
- unsupported case citations / hallucination risk flags
- criminal law version framing (BNS/BNSS/BSA)
- sedition current-position handling (Vombatkere/stay)
- electoral bonds current-position handling (struck down Feb 2024)
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

import requests


SCENARIO_PATTERN = re.compile(
    r"##\s+Q(?P<num>\d+)\s+[-—]\s+(?P<title>.+?)\n"
    r"###\s*\*(?P<subtitle>.+?)\*\n\n"
    r"(?P<body>.*?)(?=\n---\n\n##\s+Q\d+\s+[-—]|\n---\n\n##\s*🧪|\Z)",
    re.DOTALL,
)


@dataclass
class ForensicRow:
    qid: str
    title: str
    status_code: int | None
    latency_s: float
    query_type: str
    answer_len: int
    unsupported_case_citations: int
    high_hallucination_risk: bool
    answer_downgraded: bool
    subq_heading_count: int
    has_bns_or_bnss: bool
    has_vombatkere_or_stay: bool
    has_electoral_bond_struck_down_marker: bool
    has_unverified_marker: bool
    hard_fail_reasons: list[str]


def parse_scenarios(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in SCENARIO_PATTERN.finditer(text):
        qid = f"Q{m.group('num')}"
        title = m.group("title").strip()
        subtitle = m.group("subtitle").strip()
        body = m.group("body").strip()
        prompt = f"## {qid} - {title}\n### {subtitle}\n\n{body}".strip()
        out.append({"qid": qid, "title": title, "prompt": prompt})
    return out


def call_api(base_url: str, question: str, timeout_s: int) -> tuple[dict[str, Any] | None, int | None, float, str | None]:
    payload = {
        "question": question,
        "target_language": "en",
        "enable_thinking": True,
        "web_search_mode": False,
    }

    url = f"{base_url.rstrip('/')}/api/query"
    t0 = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, timeout=timeout_s)
        latency = time.perf_counter() - t0
        if resp.status_code >= 400:
            return None, resp.status_code, latency, resp.text[:400]
        data = resp.json()
        return data.get("response", data), resp.status_code, latency, None
    except Exception as exc:
        latency = time.perf_counter() - t0
        return None, None, latency, str(exc)


def analyze_one(qid: str, title: str, response_obj: dict[str, Any] | None, status_code: int | None, latency_s: float) -> ForensicRow:
    if not response_obj:
        return ForensicRow(
            qid=qid,
            title=title,
            status_code=status_code,
            latency_s=latency_s,
            query_type="error",
            answer_len=0,
            unsupported_case_citations=0,
            high_hallucination_risk=False,
            answer_downgraded=False,
            subq_heading_count=0,
            has_bns_or_bnss=False,
            has_vombatkere_or_stay=False,
            has_electoral_bond_struck_down_marker=False,
            has_unverified_marker=False,
            hard_fail_reasons=["request_failed"],
        )

    answer = str(response_obj.get("answer", ""))
    answer_lower = answer.lower()
    sysinfo = response_obj.get("system_info", {}) if isinstance(response_obj, dict) else {}
    validation = response_obj.get("validation", {}) if isinstance(response_obj, dict) else {}

    unsupported_case = int(sysinfo.get("unsupported_case_citations", 0) or 0)
    high_hallu = bool(validation.get("high_hallucination_risk", False))
    downgraded = bool(sysinfo.get("answer_downgraded", False))

    subq_heading_count = len(re.findall(r"sub[-\s]?question\s*\d+", answer_lower))
    has_bns_or_bnss = any(k in answer_lower for k in (
        " bns", " bnss", " bsa",
        "bharatiya nyaya sanhita",
        "bharatiya nagarik suraksha sanhita",
        "bharatiya sakshya",
    ))

    has_vombatkere_or_stay = any(k in answer_lower for k in (
        "vombatkere",
        "abeyance",
        "no fresh fir",
        "stay",
        "interim order",
    ))

    has_electoral_bond_struck_down_marker = any(k in answer_lower for k in (
        "association for democratic reforms",
        "struck down",
        "unconstitutional",
        "february 2024",
        "electoral bonds scheme",
    ))

    has_unverified_marker = any(k in answer for k in (
        "Unverified in retrieved record",
        "Unverified case reference",
        "not found in retrieved sources",
    ))

    hard_fail_reasons: list[str] = []
    if unsupported_case > 0 or high_hallu:
        hard_fail_reasons.append("unsupported_case_citation_risk")

    if qid in {"Q1", "Q8", "Q12"} and not has_bns_or_bnss:
        hard_fail_reasons.append("missing_bns_bnss_framing")

    if qid == "Q8" and not has_vombatkere_or_stay:
        hard_fail_reasons.append("missing_sedition_current_position")

    if qid == "Q11" and not has_electoral_bond_struck_down_marker:
        hard_fail_reasons.append("missing_electoral_bond_current_position")

    if subq_heading_count < 4:
        hard_fail_reasons.append("weak_explicit_subquestion_structure")

    return ForensicRow(
        qid=qid,
        title=title,
        status_code=status_code,
        latency_s=latency_s,
        query_type=str(sysinfo.get("query_type", response_obj.get("query_type", "unknown"))),
        answer_len=len(answer),
        unsupported_case_citations=unsupported_case,
        high_hallucination_risk=high_hallu,
        answer_downgraded=downgraded,
        subq_heading_count=subq_heading_count,
        has_bns_or_bnss=has_bns_or_bnss,
        has_vombatkere_or_stay=has_vombatkere_or_stay,
        has_electoral_bond_struck_down_marker=has_electoral_bond_struck_down_marker,
        has_unverified_marker=has_unverified_marker,
        hard_fail_reasons=hard_fail_reasons,
    )


def main() -> None:
    base_url = "https://lawgpt-backend2024.azurewebsites.net"
    timeout_s = 240
    md_path = Path("azure_backend_stage/kaanoon_test/benchmark_outputs/complex_15q_20260403/compleQA.md")
    out_json = Path("azure_backend_stage/kaanoon_test/benchmark_outputs/complex_15q_20260403/post_deploy_forensic_results.json")
    out_md = Path("azure_backend_stage/kaanoon_test/benchmark_outputs/complex_15q_20260403/post_deploy_forensic_report.md")

    scenarios = parse_scenarios(md_path.read_text(encoding="utf-8"))
    rows: list[ForensicRow] = []

    for i, sc in enumerate(scenarios, start=1):
        print(f"[{i}/{len(scenarios)}] {sc['qid']} - {sc['title']}")
        response_obj, status, latency, err = call_api(base_url, sc["prompt"], timeout_s)
        row = analyze_one(sc["qid"], sc["title"], response_obj, status, latency)
        if err:
            row.hard_fail_reasons.append(f"request_error:{err[:120]}")
        rows.append(row)
        print(
            "  "
            f"status={row.status_code} "
            f"unsupported_case={row.unsupported_case_citations} "
            f"hallu_risk={row.high_hallucination_risk} "
            f"subq_headings={row.subq_heading_count} "
            f"fails={len(row.hard_fail_reasons)}"
        )

    total = len(rows)
    failed = [r for r in rows if r.hard_fail_reasons]
    success = [r for r in rows if not r.hard_fail_reasons]

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "pass_count": len(success),
        "fail_count": len(failed),
        "pass_rate": (len(success) / total) if total else 0.0,
        "avg_latency_s": mean(r.latency_s for r in rows) if rows else 0.0,
        "avg_unsupported_case_citations": mean(r.unsupported_case_citations for r in rows) if rows else 0.0,
        "high_hallucination_risk_count": sum(1 for r in rows if r.high_hallucination_risk),
        "missing_bns_bnss_count": sum(1 for r in rows if "missing_bns_bnss_framing" in r.hard_fail_reasons),
        "missing_sedition_current_position_count": sum(1 for r in rows if "missing_sedition_current_position" in r.hard_fail_reasons),
        "missing_electoral_bond_current_position_count": sum(1 for r in rows if "missing_electoral_bond_current_position" in r.hard_fail_reasons),
        "weak_subquestion_structure_count": sum(1 for r in rows if "weak_explicit_subquestion_structure" in r.hard_fail_reasons),
    }

    payload = {
        "summary": summary,
        "results": [asdict(r) for r in rows],
    }
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Post-Deploy Forensic Report",
        "",
        f"- Total scenarios: {summary['total']}",
        f"- Pass count: {summary['pass_count']}",
        f"- Fail count: {summary['fail_count']}",
        f"- Pass rate: {summary['pass_rate']:.2%}",
        f"- Avg latency: {summary['avg_latency_s']:.2f}s",
        f"- High hallucination-risk responses: {summary['high_hallucination_risk_count']}",
        f"- Missing BNS/BNSS framing (targeted criminal set): {summary['missing_bns_bnss_count']}",
        f"- Missing sedition current-position marker: {summary['missing_sedition_current_position_count']}",
        f"- Missing electoral-bond current-position marker: {summary['missing_electoral_bond_current_position_count']}",
        f"- Weak explicit sub-question structure (<4 headings): {summary['weak_subquestion_structure_count']}",
        "",
        "## Per Scenario",
        "",
    ]

    for r in rows:
        lines.extend([
            f"### {r.qid} - {r.title}",
            f"- status: {r.status_code}",
            f"- query_type: {r.query_type}",
            f"- latency_s: {r.latency_s:.2f}",
            f"- unsupported_case_citations: {r.unsupported_case_citations}",
            f"- high_hallucination_risk: {r.high_hallucination_risk}",
            f"- answer_downgraded: {r.answer_downgraded}",
            f"- subq_heading_count: {r.subq_heading_count}",
            f"- has_bns_or_bnss: {r.has_bns_or_bnss}",
            f"- has_vombatkere_or_stay: {r.has_vombatkere_or_stay}",
            f"- has_electoral_bond_struck_down_marker: {r.has_electoral_bond_struck_down_marker}",
            f"- hard_fail_reasons: {', '.join(r.hard_fail_reasons) if r.hard_fail_reasons else 'none'}",
            "",
        ])

    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {out_json}")
    print(f"Saved: {out_md}")


if __name__ == "__main__":
    main()
