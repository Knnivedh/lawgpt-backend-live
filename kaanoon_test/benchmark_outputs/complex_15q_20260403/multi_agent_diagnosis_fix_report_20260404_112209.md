# Multi-Agent Diagnosis and Fix Report

Generated: 2026-04-04 11:22:09

## What Broke

1. Complex prompts entered simple mode in some routes.
2. Simple-mode path returned answer with empty sources.
3. Grounding fail-closed then abstained due to 0 sources.
4. Abstentions were mislabeled in some responses as non-abstain query types.
5. Trust allowlist excluded internal cloud corpus source label cloud_milvus.

## What Was Fixed

1. Simple mode now returns real source documents for grounding.
2. Retrieval fallback added when primary retrieval is empty.
3. Complex simple_direct prompts are forced to full pipeline via stronger heuristics.
4. Grounding abstentions are explicitly labeled as grounding_abstain.
5. Trusted-source classification now recognizes cloud_milvus/milvus/zilliz/internal corpus labels.

## Health Delta

- Before: status=degraded retrieval_ready=False
- After initial deploy: status=ready retrieval_ready=True

## Live Benchmark (15 Scenarios)

| Metric | Before | Bad Deploy | Fixed Deploy |
|---|---:|---:|---:|
| Avg latency (s) | 11.91 | 25.21 | 13.30 |
| Avg subquestion coverage | 1.00 | 0.00 | 1.00 |
| Avg contract score | 0.87 | 0.17 | 0.89 |
| Success count | 15 | 15 | 15 |

## Forensic Pass/Fail

| Metric | Before | Bad Deploy | Fixed Deploy |
|---|---:|---:|---:|
| Pass count | 12 | 0 | 12 |
| Fail count | 3 | 15 | 3 |
| Pass rate | 80.00% | 0.00% | 80.00% |
| High hallucination-risk count | 1 | 0 | 1 |
| Weak subquestion structure count | 0 | 15 | 0 |

## Recovery Summary

- Forensic pass rate recovered from 0.00% (bad deploy) to 80.00% after fixes.
- Net change bad->fixed: 80.00 percentage points.
- Compared to original baseline (80.00%), fixed deploy is now 0.00 percentage points.