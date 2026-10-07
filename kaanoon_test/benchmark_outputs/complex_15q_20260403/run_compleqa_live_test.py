#!/usr/bin/env python3
"""
Run live API tests from compleQA.md scenarios.

Outputs:
- compleqa_live_results.json
- compleqa_live_report.md
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

import requests


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "what",
    "when",
    "while",
    "shall",
    "must",
    "should",
    "could",
    "would",
    "under",
    "against",
    "after",
    "before",
    "analysis",
    "question",
    "legal",
    "court",
    "courts",
    "section",
    "article",
    "whether",
}

CONTRACT_CHECKS = {
    "issue_summary": r"(issue|summary|facts?)",
    "governing_law": r"(law|section|article|governing)",
    "application": r"(apply|application|analysis|reasoning)",
    "risk": r"(risk|caution|limitation)",
    "next_steps": r"(next\s+step|remedy|file|approach)",
    "disclaimer": r"(disclaimer|legal advice|general information)",
}


@dataclass
class Scenario:
    qid: str
    title: str
    subtitle: str
    prompt: str
    subquestions: list[str]


@dataclass
class ScenarioResult:
    qid: str
    title: str
    status_code: int | None
    latency_s: float
    error: str | None
    query_type: str
    detected_language: str
    target_language: str
    language_mismatch: bool
    answer_len: int
    subquestions_total: int
    subquestions_covered: int
    subquestion_coverage: float
    missing_subquestions: list[str]
    contract_score: float



def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())



def tokenize(text: str) -> list[str]:
    toks = re.findall(r"[a-z]{4,}", normalize_text(text))
    return [t for t in toks if t not in STOPWORDS]



def extract_scenarios(markdown_text: str) -> list[Scenario]:
    pattern = re.compile(
        r"##\s+Q(?P<num>\d+)\s+[-—]\s+(?P<title>.+?)\n"
        r"###\s*\*(?P<subtitle>.+?)\*\n\n"
        r"(?P<body>.*?)(?=\n---\n\n##\s+Q\d+\s+[-—]|\n---\n\n##\s*🧪|\Z)",
        re.DOTALL,
    )

    scenarios: list[Scenario] = []
    for match in pattern.finditer(markdown_text):
        qid = f"Q{match.group('num')}"
        title = match.group("title").strip()
        subtitle = match.group("subtitle").strip()
        body = match.group("body").strip()

        subquestions = [
            re.sub(r"^\d+\.\s+", "", line.strip())
            for line in body.splitlines()
            if re.match(r"^\d+\.\s+", line.strip())
        ]

        prompt = f"## {qid} - {title}\n### {subtitle}\n\n{body}".strip()

        scenarios.append(
            Scenario(
                qid=qid,
                title=title,
                subtitle=subtitle,
                prompt=prompt,
                subquestions=subquestions,
            )
        )

    return scenarios



def evaluate_subquestion_coverage(answer: str, subquestions: list[str]) -> tuple[int, list[str]]:
    answer_tokens = set(tokenize(answer))
    covered = 0
    missing: list[str] = []

    for sq in subquestions:
        sq_tokens = list(dict.fromkeys(tokenize(sq)))
        if not sq_tokens:
            covered += 1
            continue

        # Minimum lexical overlap threshold for considering a sub-issue addressed.
        overlap = sum(1 for token in sq_tokens[:10] if token in answer_tokens)
        threshold = 2 if len(sq_tokens) >= 6 else 1

        if overlap >= threshold:
            covered += 1
        else:
            missing.append(sq)

    return covered, missing



def contract_score(answer: str) -> float:
    text = normalize_text(answer)
    checks = [bool(re.search(regex, text)) for regex in CONTRACT_CHECKS.values()]
    return sum(1 for c in checks if c) / len(checks)



def call_api(base_url: str, scenario: Scenario, timeout_s: int) -> dict[str, Any]:
    payload = {
        "question": scenario.prompt,
        "target_language": "en",
        "enable_thinking": True,
        "web_search_mode": False,
    }
    url = f"{base_url.rstrip('/')}/api/query"

    start = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, timeout=timeout_s)
        latency = time.perf_counter() - start

        if resp.status_code >= 400:
            return {
                "status_code": resp.status_code,
                "latency_s": latency,
                "error": resp.text[:300],
            }

        data = resp.json()
        response_obj = data.get("response", data)
        return {
            "status_code": resp.status_code,
            "latency_s": latency,
            "error": None,
            "response": response_obj,
        }
    except Exception as exc:  # pragma: no cover - network dependent
        return {
            "status_code": None,
            "latency_s": time.perf_counter() - start,
            "error": str(exc),
        }



def run(markdown_path: Path, base_url: str, timeout_s: int) -> tuple[list[ScenarioResult], dict[str, Any]]:
    scenarios = extract_scenarios(markdown_path.read_text(encoding="utf-8"))
    if not scenarios:
        raise RuntimeError(f"No scenarios parsed from {markdown_path}")

    out: list[ScenarioResult] = []

    for idx, scenario in enumerate(scenarios, 1):
        print(f"[{idx}/{len(scenarios)}] {scenario.qid} - {scenario.title}")
        result = call_api(base_url=base_url, scenario=scenario, timeout_s=timeout_s)

        if result.get("error"):
            out.append(
                ScenarioResult(
                    qid=scenario.qid,
                    title=scenario.title,
                    status_code=result.get("status_code"),
                    latency_s=float(result.get("latency_s", 0.0)),
                    error=result["error"],
                    query_type="error",
                    detected_language="",
                    target_language="en",
                    language_mismatch=False,
                    answer_len=0,
                    subquestions_total=len(scenario.subquestions),
                    subquestions_covered=0,
                    subquestion_coverage=0.0,
                    missing_subquestions=scenario.subquestions,
                    contract_score=0.0,
                )
            )
            print(f"  ERROR: {result['error']}")
            continue

        response = result["response"]
        answer = str(response.get("answer", ""))
        sysinfo = response.get("system_info", {}) if isinstance(response, dict) else {}

        covered_count, missing = evaluate_subquestion_coverage(answer, scenario.subquestions)
        sq_cov = covered_count / max(1, len(scenario.subquestions))
        c_score = contract_score(answer)

        row = ScenarioResult(
            qid=scenario.qid,
            title=scenario.title,
            status_code=result.get("status_code"),
            latency_s=float(result.get("latency_s", 0.0)),
            error=None,
            query_type=str(sysinfo.get("query_type", response.get("query_type", "unknown"))),
            detected_language=str(sysinfo.get("detected_language", "")),
            target_language=str(sysinfo.get("target_language", "en")),
            language_mismatch=bool(sysinfo.get("language_mismatch", False)),
            answer_len=len(answer),
            subquestions_total=len(scenario.subquestions),
            subquestions_covered=covered_count,
            subquestion_coverage=sq_cov,
            missing_subquestions=missing,
            contract_score=c_score,
        )
        out.append(row)

        print(
            f"  status=200 type={row.query_type} "
            f"coverage={row.subquestions_covered}/{row.subquestions_total} "
            f"contract={row.contract_score:.2f} latency={row.latency_s:.2f}s"
        )

    successes = [r for r in out if r.error is None]
    summary = {
        "total": len(out),
        "successful": len(successes),
        "failed": len(out) - len(successes),
        "avg_latency_s": mean(r.latency_s for r in successes) if successes else 0.0,
        "avg_subquestion_coverage": mean(r.subquestion_coverage for r in successes) if successes else 0.0,
        "avg_contract_score": mean(r.contract_score for r in successes) if successes else 0.0,
        "language_mismatch_rate": mean(1.0 if r.language_mismatch else 0.0 for r in successes) if successes else 0.0,
        "query_type_counts": {},
    }

    if successes:
        counts: dict[str, int] = {}
        for r in successes:
            counts[r.query_type] = counts.get(r.query_type, 0) + 1
        summary["query_type_counts"] = dict(sorted(counts.items(), key=lambda kv: kv[0]))

    return out, summary



def write_outputs(output_dir: Path, rows: list[ScenarioResult], summary: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "compleqa_live_results.json"
    md_path = output_dir / "compleqa_live_report.md"

    payload = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
        "results": [asdict(r) for r in rows],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# COMPLEQA Live Test Report",
        "",
        f"- Total scenarios: {summary['total']}",
        f"- Successful: {summary['successful']}",
        f"- Failed: {summary['failed']}",
        f"- Avg latency: {summary['avg_latency_s']:.2f}s",
        f"- Avg subquestion coverage: {summary['avg_subquestion_coverage']:.3f}",
        f"- Avg answer contract score: {summary['avg_contract_score']:.3f}",
        f"- Language mismatch rate: {summary['language_mismatch_rate']:.3f}",
        "",
        "## Query Types",
        "",
    ]

    if summary["query_type_counts"]:
        for k, v in summary["query_type_counts"].items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- none")

    lines.extend(["", "## Per Scenario", ""])

    for row in rows:
        lines.append(f"### {row.qid} - {row.title}")
        lines.append("")
        lines.append(f"- status: {row.status_code}")
        lines.append(f"- latency_s: {row.latency_s:.2f}")
        lines.append(f"- query_type: {row.query_type}")
        lines.append(f"- subquestion_coverage: {row.subquestions_covered}/{row.subquestions_total} ({row.subquestion_coverage:.2f})")
        lines.append(f"- contract_score: {row.contract_score:.2f}")
        lines.append(f"- language_mismatch: {row.language_mismatch}")
        lines.append(f"- answer_len: {row.answer_len}")
        if row.error:
            lines.append(f"- error: {row.error}")
        if row.missing_subquestions:
            lines.append("- missing_subquestions:")
            for sq in row.missing_subquestions[:5]:
                lines.append(f"  - {sq}")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")



def main() -> None:
    parser = argparse.ArgumentParser(description="Run live tests from compleQA.md")
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("azure_backend_stage/kaanoon_test/benchmark_outputs/complex_15q_20260403/compleQA.md"),
    )
    parser.add_argument(
        "--base-url",
        default="https://lawgpt-backend2024.azurewebsites.net",
    )
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("azure_backend_stage/kaanoon_test/benchmark_outputs/complex_15q_20260403"),
    )
    args = parser.parse_args()

    rows, summary = run(markdown_path=args.markdown, base_url=args.base_url, timeout_s=args.timeout)
    write_outputs(output_dir=args.output_dir, rows=rows, summary=summary)


if __name__ == "__main__":
    main()
