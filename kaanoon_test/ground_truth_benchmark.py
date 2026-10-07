#!/usr/bin/env python3
"""
LAW-GPT ground-truth benchmark runner and chart generator.

This script runs the live hosted backend against the Kaanoon ground-truth
dataset, scores each answer with a few transparent text metrics, and writes
PNG charts plus JSON/Markdown summaries.

It also generates a small system-comparison visual from the existing
ultimate_test_results.json artifact when present.

Usage:
    python ground_truth_benchmark.py
    python ground_truth_benchmark.py --base-url https://lawgpt-backend2024.azurewebsites.net
    python ground_truth_benchmark.py --output-dir benchmark_outputs
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from statistics import mean
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = SCRIPT_DIR / "kaanoon_qa_expanded.json"
DEFAULT_CLEANED_DATASET = SCRIPT_DIR / "kaanoon_qa_dataset_cleaned.json"
DEFAULT_COMPARE_JSON = SCRIPT_DIR / "ultimate_test_results.json"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "benchmark_outputs"
DEFAULT_BASE_URL = "https://lawgpt-backend2024.azurewebsites.net"
ACTIVE_LANGUAGES = ("en", "hi")
SIMPLE_PATH_TYPES = {"simple_direct", "fallback_direct"}
QUERY_TYPE_TAXONOMY = {
    "academic_direct",
    "case_consultation",
    "clarification",
    "fallback_direct",
    "greeting",
    "invalid_reference",
    "multi_hop",
    "out_of_scope",
    "research",
    "safety_refusal",
    "simple",
    "simple_direct",
    "statute_lookup",
    "system_warmup",
    "web_search",
}

EN_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "will",
    "with",
}


@dataclass
class TestCase:
    case_id: str
    category: str
    topic: str
    language: str
    question: str
    expected: str
    query_language: str


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [flatten_text(item) for item in value]
        return " ".join(part for part in parts if part)
    if isinstance(value, dict):
        preferred_keys = [
            "recommendation",
            "answer_summary",
            "short_answer",
            "outcome",
            "defensive_strategy",
            "expert_consensus",
            "key_legal_issues",
            "key_points",
            "legal_references",
        ]
        parts: list[str] = []
        for key in preferred_keys:
            if key in value:
                parts.append(flatten_text(value[key]))
        for key, nested_value in value.items():
            if key not in preferred_keys:
                parts.append(flatten_text(nested_value))
        return " ".join(part for part in parts if part)
    return str(value).strip()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def tokenize(text: str, language: str) -> list[str]:
    tokens = re.findall(r"\w+", normalize_text(text), flags=re.UNICODE)
    if language == "en":
        tokens = [token for token in tokens if token not in EN_STOPWORDS]
    return [token for token in tokens if len(token) > 1]


def keyword_f1(expected: str, actual: str, language: str) -> float:
    expected_tokens = set(tokenize(expected, language))
    actual_tokens = set(tokenize(actual, language))
    if not expected_tokens:
        return 0.0
    if not actual_tokens:
        return 0.0

    true_positive = len(expected_tokens & actual_tokens)
    precision = true_positive / len(actual_tokens)
    recall = true_positive / len(expected_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def sequence_similarity(expected: str, actual: str) -> float:
    return SequenceMatcher(None, normalize_text(expected), normalize_text(actual)).ratio()


def extract_legal_markers(text: str) -> set[str]:
    text_norm = normalize_text(text)
    markers: set[str] = set()
    patterns = [
        r"section\s+\d+[a-z]?",
        r"article\s+\d+[a-z]?",
        r"order\s+\d+[a-z]?",
        r"rule\s+\d+[a-z]?",
        r"धारा\s+\d+[a-z]?",
        r"अनुच्छेद\s+\d+[a-z]?",
        r"\b(?:ipc|crpc|cpc|bns|bnss|bsa)\b",
        r"\b\d{4}\s+\d+\s+scc\s+\d+\b",
    ]
    for pattern in patterns:
        markers.update(re.findall(pattern, text_norm, flags=re.IGNORECASE))
    return markers


def legal_marker_recall(expected: str, actual: str) -> float:
    expected_markers = extract_legal_markers(expected)
    if not expected_markers:
        return 1.0
    actual_markers = extract_legal_markers(actual)
    if not actual_markers:
        return 0.0
    return len(expected_markers & actual_markers) / len(expected_markers)


def response_contract_score(actual: str) -> float:
    text = normalize_text(actual)
    checks = [
        bool(re.search(r"(issue|summary|facts?)", text)),
        bool(re.search(r"(law|section|article|governing)", text)),
        bool(re.search(r"(apply|application|analysis|reasoning)", text)),
        bool(re.search(r"(risk|caution|limitation)", text)),
        bool(re.search(r"(next\s+step|remedy|file|approach)", text)),
        bool(re.search(r"(disclaimer|general\s+information|legal\s+advice)", text)),
    ]
    return sum(1.0 for check in checks if check) / len(checks)


def detect_script_language(text: str) -> str:
    if re.search(r"[\u0900-\u097F]", text or ""):
        return "hi"
    return "en"


def language_matches(expected_language: str, actual_text: str) -> bool:
    return detect_script_language(actual_text) == expected_language


def build_test_cases(dataset_path: Path, cleaned_dataset_path: Path) -> list[TestCase]:
    raw = load_json(dataset_path)
    cleaned = load_json(cleaned_dataset_path) if cleaned_dataset_path.exists() else []
    cleaned_by_id = {str(item.get("id")): item for item in cleaned if isinstance(item, dict)}
    cases: list[TestCase] = []

    for item in raw:
        case_id = str(item.get("id", "")).strip()
        if not case_id or case_id.upper() == "Q5":
            continue

        base_category = str(item.get("category", "unknown")).strip()
        topic = str(item.get("topic", "")).strip()

        variants = [
            ("en", item.get("question"), item.get("short_answer")),
            ("hi", item.get("question_hindi"), item.get("answer_hindi")),
        ]

        for language, question, expected in variants:
            if not question or not expected:
                continue

            if language == "en":
                cleaned_item = cleaned_by_id.get(case_id, {})
                detailed_expected = flatten_text(cleaned_item.get("answer_detail"))
                if not detailed_expected:
                    detailed_expected = flatten_text(cleaned_item.get("answer_summary"))
                if detailed_expected:
                    expected = detailed_expected

            cases.append(
                TestCase(
                    case_id=case_id,
                    category=base_category,
                    topic=topic,
                    language=language,
                    question=str(question).strip(),
                    expected=str(expected).strip(),
                    query_language=language,
                )
            )

    return cases


def call_live_backend(
    session: requests.Session,
    base_url: str,
    test_case: TestCase,
    timeout_s: int,
    retries: int,
) -> dict[str, Any]:
    payload = {
        "question": test_case.question,
        "session_id": f"gt_{test_case.case_id}_{test_case.language}_{int(time.time() * 1000)}",
        "target_language": test_case.query_language,
        "category": test_case.category,
        "enable_thinking": True,
        "web_search_mode": False,
    }

    url = f"{base_url.rstrip('/')}/api/query"

    last_error: str | None = None
    for attempt in range(retries + 1):
        start = time.perf_counter()
        try:
            response = session.post(url, json=payload, timeout=timeout_s)
            latency_s = time.perf_counter() - start

            if response.status_code >= 400:
                last_error = f"HTTP {response.status_code}: {response.text[:250]}"
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return {
                    "error": last_error,
                    "latency_s": latency_s,
                    "status_code": response.status_code,
                }

            data = response.json()
            response_obj = data.get("response", data)
            return {
                "response": response_obj,
                "latency_s": latency_s,
                "status_code": response.status_code,
            }
        except Exception as exc:  # pragma: no cover - network dependent
            last_error = str(exc)
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            return {
                "error": last_error,
                "latency_s": time.perf_counter() - start,
                "status_code": None,
            }

    return {"error": last_error or "unknown error", "latency_s": 0.0, "status_code": None}


def run_preflight_checks(
    session: requests.Session,
    base_url: str,
    timeout_s: int,
    expected_build_fingerprint: str | None,
    strict_provenance: bool,
) -> dict[str, Any]:
    health_url = f"{base_url.rstrip('/')}/api/health"
    out: dict[str, Any] = {
        "health_url": health_url,
        "status": "unknown",
        "build_fingerprint": None,
        "release_signature": None,
        "ok": False,
        "failures": [],
    }

    try:
        resp = session.get(health_url, timeout=timeout_s)
        if resp.status_code >= 400:
            out["failures"].append(f"health endpoint returned HTTP {resp.status_code}")
            return out

        payload = resp.json()
        out["status"] = str(payload.get("status", "unknown"))
        out["build_fingerprint"] = payload.get("build_fingerprint")
        out["release_signature"] = payload.get("release_signature")

        if out["status"] not in {"ready", "initializing"}:
            out["failures"].append(f"unexpected health status: {out['status']}")

        if strict_provenance and not out["build_fingerprint"]:
            out["failures"].append("build_fingerprint missing from /api/health")

        if expected_build_fingerprint and out["build_fingerprint"] != expected_build_fingerprint:
            out["failures"].append(
                f"build_fingerprint mismatch: expected {expected_build_fingerprint}, got {out['build_fingerprint']}"
            )

        out["ok"] = len(out["failures"]) == 0
        return out
    except Exception as exc:  # pragma: no cover - network dependent
        out["failures"].append(f"preflight failed: {exc}")
        return out


def score_answer(expected: str, actual: str, language: str) -> dict[str, float]:
    expected_norm = normalize_text(expected)
    actual_norm = normalize_text(actual)

    exact_match = 1.0 if expected_norm and (expected_norm in actual_norm or actual_norm in expected_norm) else 0.0
    similarity = sequence_similarity(expected, actual)
    keyword = keyword_f1(expected, actual, language)
    length_ratio = min(len(actual_norm) / max(len(expected_norm), 1), 3.0) / 3.0
    citation_recall = legal_marker_recall(expected, actual)
    contract_score = response_contract_score(actual)

    composite = (
        0.30 * similarity
        + 0.20 * keyword
        + 0.10 * exact_match
        + 0.10 * length_ratio
        + 0.15 * citation_recall
        + 0.15 * contract_score
    )

    return {
        "exact_match": exact_match,
        "sequence_similarity": similarity,
        "keyword_f1": keyword,
        "length_ratio": length_ratio,
        "citation_recall": citation_recall,
        "contract_score": contract_score,
        "composite_score": composite,
    }


def aggregate_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key, "unknown"))].append(row)

    summary: dict[str, dict[str, float]] = {}
    for group_key, items in grouped.items():
        summary[group_key] = {
            "count": len(items),
            "composite_score": mean(item["composite_score"] for item in items) if items else 0.0,
            "sequence_similarity": mean(item["sequence_similarity"] for item in items) if items else 0.0,
            "keyword_f1": mean(item["keyword_f1"] for item in items) if items else 0.0,
            "citation_recall": mean(item["citation_recall"] for item in items) if items else 0.0,
            "contract_score": mean(item["contract_score"] for item in items) if items else 0.0,
            "exact_match_rate": mean(item["exact_match"] for item in items) if items else 0.0,
            "language_match_rate": mean(1.0 if item["language_match"] else 0.0 for item in items) if items else 0.0,
            "avg_latency_s": mean(item["latency_s"] for item in items) if items else 0.0,
        }
    return summary


def create_grouped_bar_chart(
    labels: list[str],
    series: dict[str, list[float]],
    title: str,
    ylabel: str,
    output_path: Path,
    ylim: tuple[float, float] | None = (0.0, 1.0),
) -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    x = np.arange(len(labels))
    width = 0.8 / max(len(series), 1)

    for idx, (series_name, values) in enumerate(series.items()):
        ax.bar(x + idx * width - (0.4 - width / 2), values, width, label=series_name)

    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def create_single_bar_chart(
    labels: list[str],
    values: list[float],
    title: str,
    ylabel: str,
    output_path: Path,
    ylim: tuple[float, float] | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(labels, values, color="#5B8FF9")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    if ylim is not None:
      ax.set_ylim(*ylim)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def create_radar_chart(metrics: dict[str, float], title: str, output_path: Path) -> None:
    labels = list(metrics.keys())
    values = list(metrics.values())
    if not labels:
        return

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]

    fig = plt.figure(figsize=(7, 7))
    ax = fig.add_subplot(111, polar=True)
    ax.plot(angles, values, linewidth=2)
    ax.fill(angles, values, alpha=0.18)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_ylim(0.0, 1.0)
    ax.set_title(title, pad=20)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def create_language_plot(rows: list[dict[str, Any]], output_dir: Path) -> None:
    by_language = aggregate_by(rows, "language")
    ordered_languages = [lang for lang in ACTIVE_LANGUAGES if lang in by_language]
    if not ordered_languages:
        ordered_languages = sorted(by_language.keys())

    labels = ordered_languages
    create_grouped_bar_chart(
        labels,
        {
            "composite": [by_language[l]["composite_score"] for l in labels],
            "similarity": [by_language[l]["sequence_similarity"] for l in labels],
            "keyword_f1": [by_language[l]["keyword_f1"] for l in labels],
            "citation_recall": [by_language[l]["citation_recall"] for l in labels],
        },
        "Ground Truth Accuracy by Language",
        "Score",
        output_dir / "ground_truth_accuracy_by_language.png",
    )

    create_single_bar_chart(
        labels,
        [by_language[l]["avg_latency_s"] for l in labels],
        "Average Latency by Language",
        "Latency (seconds)",
        output_dir / "ground_truth_latency_by_language.png",
        ylim=(0.0, max(1.0, max(by_language[l]["avg_latency_s"] for l in labels) * 1.25)),
    )

    create_grouped_bar_chart(
        labels,
        {
            "exact_match": [by_language[l]["exact_match_rate"] for l in labels],
            "language_match": [by_language[l]["language_match_rate"] for l in labels],
        },
        "Exact Match and Language Match by Language",
        "Rate",
        output_dir / "ground_truth_language_match.png",
    )


def create_question_plot(rows: list[dict[str, Any]], output_dir: Path) -> None:
    questions = sorted({f"{row['case_id']}-{row['language']}" for row in rows})
    by_question_language: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        key = f"{row['case_id']}-{row['language']}"
        by_question_language[row["case_id"]][row["language"]] = row

    # Build a grouped chart by case id using language series.
    case_ids = sorted(by_question_language.keys())
    series: dict[str, list[float]] = {lang: [] for lang in ACTIVE_LANGUAGES}
    for case_id in case_ids:
        for language in series:
            row = by_question_language[case_id].get(language)
            series[language].append(row["composite_score"] if row else 0.0)

    create_grouped_bar_chart(
        case_ids,
        series,
        "Composite Accuracy by Question and Language",
        "Composite Score",
        output_dir / "ground_truth_accuracy_by_question.png",
    )

    # Average score by category.
    by_category = aggregate_by(rows, "category")
    category_labels = sorted(by_category.keys())
    create_grouped_bar_chart(
        category_labels,
        {
            "composite": [by_category[c]["composite_score"] for c in category_labels],
            "similarity": [by_category[c]["sequence_similarity"] for c in category_labels],
            "keyword_f1": [by_category[c]["keyword_f1"] for c in category_labels],
            "contract_score": [by_category[c]["contract_score"] for c in category_labels],
        },
        "Ground Truth Accuracy by Category",
        "Score",
        output_dir / "ground_truth_accuracy_by_category.png",
    )


def create_system_comparison(compare_json: Path, output_dir: Path) -> dict[str, Any] | None:
    if not compare_json.exists():
        return None

    data = load_json(compare_json)
    systems = data.get("systems")
    if not isinstance(systems, dict):
        return None

    labels = list(systems.keys())
    accuracy = [systems[label].get("accuracy", 0.0) for label in labels]
    semantic = [systems[label].get("semantic", 0.0) for label in labels]
    keyword = [systems[label].get("keyword_f1", 0.0) for label in labels]

    create_grouped_bar_chart(
        labels,
        {
            "accuracy": accuracy,
            "semantic": semantic,
            "keyword_f1": keyword,
        },
        "System Benchmark Comparison",
        "Score",
        output_dir / "system_comparison.png",
    )

    for label in labels:
        create_radar_chart(
            {
                "accuracy": systems[label].get("accuracy", 0.0),
                "semantic": systems[label].get("semantic", 0.0),
                "keyword_f1": systems[label].get("keyword_f1", 0.0),
            },
            f"{label} benchmark radar",
            output_dir / f"{label}_radar.png",
        )

    return data


def summarize_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "total_tests": 0,
            "overall": {},
            "by_language": {},
            "by_category": {},
        }

    by_language = aggregate_by(rows, "language")
    by_category = aggregate_by(rows, "category")
    invalid_query_type_count = sum(1 for row in rows if not row.get("query_type_valid", False))

    overall = {
        "average_composite_score": mean(row["composite_score"] for row in rows),
        "average_sequence_similarity": mean(row["sequence_similarity"] for row in rows),
        "average_keyword_f1": mean(row["keyword_f1"] for row in rows),
        "average_exact_match": mean(row["exact_match"] for row in rows),
        "average_length_ratio": mean(row["length_ratio"] for row in rows),
        "average_citation_recall": mean(row["citation_recall"] for row in rows),
        "average_contract_score": mean(row["contract_score"] for row in rows),
        "language_match_rate": mean(1.0 if row["language_match"] else 0.0 for row in rows),
        "average_latency_s": mean(row["latency_s"] for row in rows),
        "legal_grounded_path_rate": mean(
            1.0 if (row.get("is_legal_case") and row.get("used_grounded_path")) else 0.0
            for row in rows
            if row.get("is_legal_case")
        ) if any(row.get("is_legal_case") for row in rows) else 1.0,
        "query_type_valid_rate": 1.0 - (invalid_query_type_count / len(rows)),
        "invalid_query_type_count": invalid_query_type_count,
        "query_type_counts": dict(sorted(Counter(row.get("query_type", "unknown") for row in rows).items())),
    }

    return {
        "total_tests": len(rows),
        "overall": overall,
        "by_language": by_language,
        "by_category": by_category,
    }


def write_markdown_report(summary: dict[str, Any], rows: list[dict[str, Any]], output_path: Path) -> None:
    overall = summary.get("overall", {})
    by_language = summary.get("by_language", {})
    by_category = summary.get("by_category", {})

    lines = [
        "# LAW-GPT Ground Truth Benchmark Report",
        "",
        f"- Total tests: {summary.get('total_tests', 0)}",
        f"- Average composite score: {overall.get('average_composite_score', 0.0):.3f}",
        f"- Average similarity: {overall.get('average_sequence_similarity', 0.0):.3f}",
        f"- Average keyword F1: {overall.get('average_keyword_f1', 0.0):.3f}",
        f"- Exact match rate: {overall.get('average_exact_match', 0.0):.3f}",
        f"- Citation recall: {overall.get('average_citation_recall', 0.0):.3f}",
        f"- Answer contract score: {overall.get('average_contract_score', 0.0):.3f}",
        f"- Legal grounded-path rate: {overall.get('legal_grounded_path_rate', 0.0):.3f}",
        f"- Query type valid rate: {overall.get('query_type_valid_rate', 0.0):.3f}",
        f"- Invalid query_type count: {int(overall.get('invalid_query_type_count', 0))}",
        f"- Language match rate: {overall.get('language_match_rate', 0.0):.3f}",
        f"- Average latency: {overall.get('average_latency_s', 0.0):.2f}s",
        "",
        "## Query Type Distribution",
        "",
    ]

    for query_type, count in overall.get("query_type_counts", {}).items():
        lines.append(f"- {query_type}: {count}")

    lines.extend(["", "## By Language", ""])
    for language in ACTIVE_LANGUAGES:
        metrics = by_language.get(language)
        if not metrics:
            continue
        lines.append(
            f"- {language}: composite={metrics['composite_score']:.3f}, "
            f"similarity={metrics['sequence_similarity']:.3f}, "
            f"keyword_f1={metrics['keyword_f1']:.3f}, "
            f"citation_recall={metrics['citation_recall']:.3f}, "
            f"latency={metrics['avg_latency_s']:.2f}s",
        )

    lines.extend(["", "## By Category", ""])
    for category, metrics in sorted(by_category.items()):
        lines.append(
            f"- {category}: composite={metrics['composite_score']:.3f}, "
            f"similarity={metrics['sequence_similarity']:.3f}, keyword_f1={metrics['keyword_f1']:.3f}"
        )

    lines.extend(["", "## Top Results", ""])
    for row in sorted(rows, key=lambda item: item["composite_score"], reverse=True)[:6]:
        lines.append(
            f"- {row['case_id']} ({row['language']}): score={row['composite_score']:.3f}, "
            f"type={row.get('query_type', 'unknown')}, latency={row['latency_s']:.2f}s"
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_benchmark(
    base_url: str,
    dataset_path: Path,
    cleaned_dataset_path: Path,
    timeout_s: int,
    retries: int,
) -> list[dict[str, Any]]:
    cases = build_test_cases(dataset_path, cleaned_dataset_path)
    if not cases:
        raise RuntimeError(f"No benchmark cases found in {dataset_path}")

    session = requests.Session()
    rows: list[dict[str, Any]] = []

    for idx, case in enumerate(cases, 1):
        print(f"[{idx}/{len(cases)}] {case.case_id} ({case.language}) - {case.topic}")
        result = call_live_backend(session, base_url, case, timeout_s=timeout_s, retries=retries)

        if "error" in result:
            row = {
                "case_id": case.case_id,
                "category": case.category,
                "topic": case.topic,
                "language": case.language,
                "question": case.question,
                "expected": case.expected,
                "actual": "",
                "query_type": "error",
                "raw_query_type": "error",
                "query_type_valid": False,
                "latency_s": result.get("latency_s", 0.0),
                "status_code": result.get("status_code"),
                "error": result["error"],
                "exact_match": 0.0,
                "sequence_similarity": 0.0,
                "keyword_f1": 0.0,
                "length_ratio": 0.0,
                "citation_recall": 0.0,
                "contract_score": 0.0,
                "composite_score": 0.0,
                "language_match": False,
                "is_legal_case": False,
                "used_grounded_path": False,
                "confidence": 0.0,
                "from_cache": False,
            }
            rows.append(row)
            print(f"  [ERROR] {result['error']}")
            continue

        response = result["response"]
        actual = str(response.get("answer", ""))
        raw_query_type = str(
            response.get("system_info", {}).get("query_type", response.get("query_type", "unknown"))
        ).strip().lower()
        query_type_valid = raw_query_type in QUERY_TYPE_TAXONOMY
        query_type = raw_query_type if query_type_valid else "invalid_query_type"
        scores = score_answer(case.expected, actual, case.language)
        language_match = language_matches(case.language, actual)
        is_legal_case = bool(legal_marker_recall(case.expected, case.question) < 1.0 or case.category or case.topic)
        used_grounded_path = query_type_valid and query_type not in SIMPLE_PATH_TYPES

        row = {
            "case_id": case.case_id,
            "category": case.category,
            "topic": case.topic,
            "language": case.language,
            "question": case.question,
            "expected": case.expected,
            "actual": actual,
            "query_type": query_type,
            "raw_query_type": raw_query_type,
            "query_type_valid": query_type_valid,
            "latency_s": float(result.get("latency_s", 0.0)),
            "status_code": result.get("status_code"),
            "error": None,
            "exact_match": scores["exact_match"],
            "sequence_similarity": scores["sequence_similarity"],
            "keyword_f1": scores["keyword_f1"],
            "length_ratio": scores["length_ratio"],
            "citation_recall": scores["citation_recall"],
            "contract_score": scores["contract_score"],
            "composite_score": scores["composite_score"],
            "language_match": language_match,
            "is_legal_case": is_legal_case,
            "used_grounded_path": used_grounded_path,
            "confidence": float(response.get("confidence", 0.0) or 0.0),
            "from_cache": bool(response.get("from_cache", False)),
        }
        rows.append(row)

        preview = actual[:120].replace("\n", " ")
        print(
            f"  score={row['composite_score']:.3f} sim={row['sequence_similarity']:.3f} "
            f"kw={row['keyword_f1']:.3f} lang={case.language}->{detect_script_language(actual)} "
            f"type={query_type} latency={row['latency_s']:.2f}s"
        )
        print(f"  answer: {preview}..." if len(actual) > 120 else f"  answer: {preview}")

    return rows


def plot_benchmark_rows(rows: list[dict[str, Any]], output_dir: Path) -> None:
    create_language_plot(rows, output_dir)
    create_question_plot(rows, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LAW-GPT ground-truth benchmark and generate graphs")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Expanded ground-truth dataset JSON")
    parser.add_argument("--cleaned-dataset", type=Path, default=DEFAULT_CLEANED_DATASET, help="Detailed English ground-truth dataset JSON")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Backend base URL")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory for report and charts")
    parser.add_argument("--timeout", type=int, default=90, help="HTTP timeout per request in seconds")
    parser.add_argument("--retries", type=int, default=1, help="Retry count for transient failures")
    parser.add_argument("--compare-json", type=Path, default=DEFAULT_COMPARE_JSON, help="Optional system comparison JSON")
    parser.add_argument(
        "--expected-build-fingerprint",
        default="",
        help="If set, fail preflight unless /api/health build_fingerprint matches exactly",
    )
    parser.add_argument(
        "--strict-provenance",
        action="store_true",
        help="Fail preflight when build_fingerprint is missing or health status is invalid",
    )
    parser.add_argument(
        "--fail-on-invalid-query-type",
        action="store_true",
        help="Exit non-zero if any response has query_type outside the approved taxonomy",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    benchmark_dir = args.output_dir / timestamp
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("LAW-GPT GROUND TRUTH BENCHMARK")
    print("=" * 78)
    print(f"Dataset:   {args.dataset}")
    print(f"Backend:   {args.base_url}")
    print(f"Output:    {benchmark_dir}")
    print("=" * 78)

    preflight_session = requests.Session()
    expected_fingerprint = args.expected_build_fingerprint.strip() or None
    preflight = run_preflight_checks(
        preflight_session,
        args.base_url,
        timeout_s=args.timeout,
        expected_build_fingerprint=expected_fingerprint,
        strict_provenance=args.strict_provenance,
    )
    preflight_session.close()

    print(
        "Preflight: "
        f"status={preflight.get('status')} "
        f"fingerprint={preflight.get('build_fingerprint')} "
        f"signature={preflight.get('release_signature')}"
    )
    if preflight.get("failures"):
        for failure in preflight.get("failures", []):
            print(f"  [PREFLIGHT] {failure}")

    if preflight.get("failures") and (args.strict_provenance or expected_fingerprint):
        raise RuntimeError("Preflight failed under strict provenance rules; benchmark aborted.")

    rows = run_benchmark(args.base_url, args.dataset, args.cleaned_dataset, timeout_s=args.timeout, retries=args.retries)
    summary = summarize_results(rows)

    results_json = benchmark_dir / "ground_truth_benchmark_results.json"
    results_json.write_text(
        json.dumps(
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "preflight": preflight,
                "summary": summary,
                "results": rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report_md = benchmark_dir / "ground_truth_benchmark_report.md"
    write_markdown_report(summary, rows, report_md)

    plot_benchmark_rows(rows, benchmark_dir)
    system_comparison = create_system_comparison(args.compare_json, benchmark_dir)
    if system_comparison:
        (benchmark_dir / "system_comparison_summary.json").write_text(
            json.dumps(system_comparison, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    print("\n" + "=" * 78)
    print("BENCHMARK COMPLETE")
    print("=" * 78)
    print(f"Total tests: {summary['total_tests']}")
    print(f"Average composite score: {summary['overall']['average_composite_score']:.3f}")
    print(f"Average similarity: {summary['overall']['average_sequence_similarity']:.3f}")
    print(f"Average keyword F1: {summary['overall']['average_keyword_f1']:.3f}")
    print(f"Average citation recall: {summary['overall']['average_citation_recall']:.3f}")
    print(f"Average contract score: {summary['overall']['average_contract_score']:.3f}")
    print(f"Legal grounded-path rate: {summary['overall']['legal_grounded_path_rate']:.3f}")
    print(f"Query type valid rate: {summary['overall']['query_type_valid_rate']:.3f}")
    print(f"Invalid query_type count: {summary['overall']['invalid_query_type_count']}")
    print(f"Language match rate: {summary['overall']['language_match_rate']:.3f}")
    print(f"Average latency: {summary['overall']['average_latency_s']:.2f}s")
    print(f"Charts and reports written to: {benchmark_dir}")

    if args.fail_on_invalid_query_type and summary['overall']['invalid_query_type_count'] > 0:
        raise SystemExit("Benchmark failed: invalid query_type values detected.")


if __name__ == "__main__":
    main()