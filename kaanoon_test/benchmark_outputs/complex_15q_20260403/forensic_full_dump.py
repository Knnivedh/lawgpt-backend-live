#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import requests

SCENARIO_PATTERN = re.compile(
    r"##\s+Q(?P<num>\d+)\s+[-—]\s+(?P<title>.+?)\n"
    r"###\s*\*(?P<subtitle>.+?)\*\n\n"
    r"(?P<body>.*?)(?=\n---\n\n##\s+Q\d+\s+[-—]|\n---\n\n##\s*🧪|\Z)",
    re.DOTALL,
)


def parse_scenarios(md_text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for m in SCENARIO_PATTERN.finditer(md_text):
        qid = f"Q{m.group('num')}"
        title = m.group("title").strip()
        subtitle = m.group("subtitle").strip()
        body = m.group("body").strip()
        prompt = f"## {qid} - {title}\n### {subtitle}\n\n{body}"
        rows.append({"qid": qid, "title": title, "prompt": prompt})
    return rows


def main() -> None:
    base_url = "https://lawgpt-backend2024.azurewebsites.net"
    md_path = Path("azure_backend_stage/kaanoon_test/benchmark_outputs/complex_15q_20260403/compleQA.md")
    out_json = Path("azure_backend_stage/kaanoon_test/benchmark_outputs/complex_15q_20260403/forensic_full_dump.json")

    scenarios = parse_scenarios(md_path.read_text(encoding="utf-8"))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    results: list[dict[str, Any]] = []

    for idx, sc in enumerate(scenarios, start=1):
        nonce = f"audit-{stamp}-{sc['qid']}"
        payload = {
            "question": f"{sc['prompt']}\n\nAudit nonce: {nonce}",
            "target_language": "en",
            "enable_thinking": True,
            "web_search_mode": False,
        }
        t0 = time.perf_counter()
        try:
            resp = requests.post(f"{base_url}/api/query", json=payload, timeout=300)
            latency = time.perf_counter() - t0
            if resp.status_code >= 400:
                results.append({
                    "qid": sc["qid"],
                    "title": sc["title"],
                    "status_code": resp.status_code,
                    "latency_s": latency,
                    "error": resp.text[:500],
                })
                print(f"[{idx}/{len(scenarios)}] {sc['qid']} status={resp.status_code} ERROR")
                continue

            data = resp.json()
            r = data.get("response", data)
            answer = str(r.get("answer", ""))
            sysinfo = r.get("system_info", {}) if isinstance(r, dict) else {}
            validation = r.get("validation", {}) if isinstance(r, dict) else {}

            results.append({
                "qid": sc["qid"],
                "title": sc["title"],
                "status_code": resp.status_code,
                "latency_s": latency,
                "from_cache": r.get("from_cache"),
                "query_type": sysinfo.get("query_type"),
                "answer_downgraded": sysinfo.get("answer_downgraded"),
                "unsupported_case_citations": sysinfo.get("unsupported_case_citations"),
                "high_hallucination_risk": validation.get("high_hallucination_risk"),
                "unsupported_case_citation_count": validation.get("unsupported_case_citation_count"),
                "answer_preview": answer[:700],
                "answer": answer,
            })
            print(
                f"[{idx}/{len(scenarios)}] {sc['qid']} status=200 cache={r.get('from_cache')} "
                f"unsupported_case={sysinfo.get('unsupported_case_citations')} "
                f"hallu={validation.get('high_hallucination_risk')}"
            )
        except Exception as exc:
            latency = time.perf_counter() - t0
            results.append({
                "qid": sc["qid"],
                "title": sc["title"],
                "status_code": None,
                "latency_s": latency,
                "error": str(exc),
            })
            print(f"[{idx}/{len(scenarios)}] {sc['qid']} EXCEPTION: {exc}")

    payload = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stamp": stamp,
        "total": len(results),
        "results": results,
    }
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {out_json}")


if __name__ == "__main__":
    main()
