# LAW-GPT Fresh Before/After Scorecard

Generated: 2026-04-03 23:08:48

## Health

- Before: status=degraded, retrieval_ready=False
- After: status=ready, retrieval_ready=True

## Live 15-Scenario Benchmark Summary

- Avg latency (s): 11.91 -> 25.21 (delta +13.30)
- Avg subquestion coverage: 1.00 -> 0.00 (delta -1.00)
- Avg contract score: 0.87 -> 0.17 (delta -0.70)
- Success/Failed: 15/0 -> 15/0

## Forensic Summary

- Pass count: 12 -> 0 (delta -12)
- Fail count: 3 -> 15 (delta +12)
- Pass rate: 80.00% -> 0.00% (delta -80.00%)
- High hallucination-risk count: 1 -> 0
- Weak subquestion structure count: 0 -> 15

## Per-Scenario Delta

| QID | Coverage (before->after) | Contract (before->after) | Latency s (before->after) | Forensic fails (before->after) |
|---|---:|---:|---:|---:|
| Q1 | 1.00 -> 0.00 | 0.83 -> 0.17 | 26.32 -> 31.03 | 2 -> 2 |
| Q2 | 1.00 -> 0.00 | 0.83 -> 0.17 | 15.26 -> 26.77 | 0 -> 1 |
| Q3 | 1.00 -> 0.00 | 0.83 -> 0.17 | 7.73 -> 21.28 | 0 -> 1 |
| Q4 | 1.00 -> 0.00 | 0.83 -> 0.17 | 7.61 -> 11.17 | 0 -> 1 |
| Q5 | 1.00 -> 0.00 | 1.00 -> 0.17 | 7.10 -> 19.66 | 0 -> 1 |
| Q6 | 1.00 -> 0.00 | 0.83 -> 0.17 | 9.35 -> 27.54 | 0 -> 1 |
| Q7 | 1.00 -> 0.00 | 1.00 -> 0.17 | 9.42 -> 32.45 | 0 -> 1 |
| Q8 | 1.00 -> 0.00 | 0.83 -> 0.17 | 21.06 -> 31.04 | 1 -> 3 |
| Q9 | 1.00 -> 0.00 | 0.83 -> 0.17 | 7.31 -> 29.72 | 0 -> 1 |
| Q10 | 1.00 -> 0.00 | 0.83 -> 0.17 | 10.72 -> 13.99 | 0 -> 1 |
| Q11 | 1.00 -> 0.00 | 0.83 -> 0.17 | 9.60 -> 29.58 | 0 -> 2 |
| Q12 | 1.00 -> 0.00 | 0.83 -> 0.17 | 19.08 -> 20.90 | 1 -> 2 |
| Q13 | 1.00 -> 0.00 | 0.83 -> 0.17 | 8.92 -> 30.72 | 0 -> 1 |
| Q14 | 1.00 -> 0.00 | 0.83 -> 0.17 | 10.18 -> 21.23 | 0 -> 1 |
| Q15 | 1.00 -> 0.00 | 1.00 -> 0.17 | 8.97 -> 31.11 | 0 -> 1 |