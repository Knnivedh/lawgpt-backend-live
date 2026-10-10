# analyzer: evaluation on the version-2 dataset

- Dataset: `evaluation/query_analyzer_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `Qwen/Qwen3-8B` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 161846, out 46504
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Routes correctly (clarify when it should, proceed when it should) | 0.92 (184/200) |
| Confidence matches exactly | 0.69 (138/200) |
| Intent correct | 0.96 (193/200) |
| All given facts captured | 0.34 (67/200) |
| Must-ask field asked (rows that have one) | 1 (70/70) |
| Rows with no re-asked fact | 0.84 (169/200) |
| Rows with no out-of-scope question | 0.12 (24/200) |
| Rows asking for private details | 0.17 (35/200) |
| Mean questions it wants to ask | 3.16 |
| Rows answered by the keyword fallback, not the model | 0 (0/200) |
| Parallel cases routed correctly in all five languages | 28/30 |

### By language

| language | rows | routes correctly | intent | no re-ask | no scope creep |
|---|---|---|---|---|---|
| English | 40 | 0.9 (36/40) | 1 (40/40) | 0.82 (33/40) | 0.15 (6/40) |
| Hindi | 40 | 0.95 (38/40) | 0.97 (39/40) | 0.88 (35/40) | 0.17 (7/40) |
| Hinglish | 40 | 0.9 (36/40) | 0.97 (39/40) | 0.88 (35/40) | 0.1 (4/40) |
| Kannada | 40 | 0.93 (37/40) | 0.93 (37/40) | 0.82 (33/40) | 0.12 (5/40) |
| Tamil | 40 | 0.93 (37/40) | 0.95 (38/40) | 0.82 (33/40) | 0.05 (2/40) |

### By category

| category | rows | routes correctly | intent | no re-ask | no scope creep |
|---|---|---|---|---|---|
| already-detailed | 2 | 1 (2/2) | 1 (2/2) | 0.5 (1/2) | 0 (0/2) |
| asr-garbled | 1 | 1 (1/1) | 0 (0/1) | 1 (1/1) | 0 (0/1) |
| clear-complete | 26 | 1 (26/26) | 0.96 (25/26) | 0.65 (17/26) | 0 (0/26) |
| clear-partial | 68 | 1 (68/68) | 0.97 (66/68) | 0.84 (57/68) | 0.1 (7/68) |
| informational | 5 | 1 (5/5) | 1 (5/5) | 1 (5/5) | 1 (5/5) |
| multi-issue | 10 | 1 (10/10) | 0.9 (9/10) | 0.8 (8/10) | 0 (0/10) |
| noisy | 1 | 0 (0/1) | 1 (1/1) | 1 (1/1) | 0 (0/1) |
| off-topic | 14 | 0 (0/14) | 0.93 (13/14) | 1 (14/14) | 0.21 (3/14) |
| privacy-trap | 5 | 1 (5/5) | 1 (5/5) | 1 (5/5) | 0.2 (1/5) |
| religion-critical | 24 | 1 (24/24) | 0.96 (23/24) | 0.96 (23/24) | 0.12 (3/24) |
| role | 27 | 1 (27/27) | 1 (27/27) | 0.81 (22/27) | 0 (0/27) |
| speech | 4 | 1 (4/4) | 1 (4/4) | 0.5 (2/4) | 0 (0/4) |
| vague | 13 | 0.92 (12/13) | 1 (13/13) | 1 (13/13) | 0.38 (5/13) |
