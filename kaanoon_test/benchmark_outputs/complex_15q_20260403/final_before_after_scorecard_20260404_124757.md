# LAW-GPT Final Stability Scorecard

Generated: 2026-04-04 12:47:57

## Run Summary

| Run | Avg Latency (s) | Avg Coverage | Avg Contract | Success/Fail | Forensic Pass/Fail | Forensic Pass Rate | High Hallucination Risk | Weak SubQ Structure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Before | 11.91 | 1.00 | 0.87 | 15/0 | 12/3 | 80.00% | 1 | 0 |
| Regressed | 25.21 | 0.00 | 0.17 | 15/0 | 0/15 | 0.00% | 0 | 15 |
| Latest | 6.29 | 1.00 | 0.97 | 15/0 | 15/0 | 100.00% | 0 | 0 |

## Delta (Before -> Latest)

- Avg latency (s): 11.91 -> 6.29 (-5.62)
- Avg subquestion coverage: 1.00 -> 1.00 (+0.00)
- Avg contract score: 0.87 -> 0.97 (+0.10)
- Forensic pass count: 12 -> 15 (+3)
- Forensic pass rate: 80.00% -> 100.00% (+20.00%)
- Weak subquestion structure count: 0 -> 0 (+0)

## Delta (Regressed -> Latest)

- Avg subquestion coverage: 0.00 -> 1.00 (+1.00)
- Avg contract score: 0.17 -> 0.97 (+0.80)
- Forensic pass count: 0 -> 15 (+15)
- Forensic pass rate: 0.00% -> 100.00% (+100.00%)
- Weak subquestion structure count: 15 -> 0 (-15)