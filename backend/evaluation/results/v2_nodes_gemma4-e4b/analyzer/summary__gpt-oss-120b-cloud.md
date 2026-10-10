# analyzer: evaluation on the version-2 dataset

- Dataset: `evaluation/query_analyzer_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `google/gemma-4-E4B-it` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 152751, out 54077
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Routes correctly (clarify when it should, proceed when it should) | 0.93 (185/200) |
| Confidence matches exactly | 0.86 (173/200) |
| Intent correct | 0.99 (199/200) |
| All given facts captured | 0.4 (80/200) |
| Must-ask field asked (rows that have one) | 1 (69/69) |
| Rows with no re-asked fact | 0.89 (178/200) |
| Rows with no out-of-scope question | 0.12 (23/200) |
| Rows asking for private details | 0 (0/200) |
| Mean questions it wants to ask | 2.71 |
| Rows answered by the keyword fallback, not the model | 0 (0/200) |
| Parallel cases routed correctly in all five languages | 28/30 |

### By language

| language | rows | routes correctly | intent | no re-ask | no scope creep |
|---|---|---|---|---|---|
| English | 40 | 0.9 (36/40) | 1 (40/40) | 0.85 (34/40) | 0.07 (3/40) |
| Hindi | 40 | 0.95 (38/40) | 0.97 (39/40) | 0.85 (34/40) | 0.15 (6/40) |
| Hinglish | 40 | 0.93 (37/40) | 1 (40/40) | 0.93 (37/40) | 0.1 (4/40) |
| Kannada | 40 | 0.93 (37/40) | 1 (40/40) | 0.93 (37/40) | 0.12 (5/40) |
| Tamil | 40 | 0.93 (37/40) | 1 (40/40) | 0.9 (36/40) | 0.12 (5/40) |

### By category

| category | rows | routes correctly | intent | no re-ask | no scope creep |
|---|---|---|---|---|---|
| already-detailed | 2 | 1 (2/2) | 1 (2/2) | 1 (2/2) | 0 (0/2) |
| asr-garbled | 1 | 1 (1/1) | 0 (0/1) | 1 (1/1) | 0 (0/1) |
| clear-complete | 26 | 1 (26/26) | 1 (26/26) | 0.85 (22/26) | 0 (0/26) |
| clear-partial | 68 | 1 (68/68) | 1 (68/68) | 0.88 (60/68) | 0.04 (3/68) |
| informational | 5 | 1 (5/5) | 1 (5/5) | 1 (5/5) | 1 (5/5) |
| multi-issue | 10 | 1 (10/10) | 1 (10/10) | 1 (10/10) | 0.3 (3/10) |
| noisy | 1 | 0 (0/1) | 1 (1/1) | 1 (1/1) | 0 (0/1) |
| off-topic | 14 | 0 (0/14) | 1 (14/14) | 0.71 (10/14) | 0.29 (4/14) |
| privacy-trap | 5 | 1 (5/5) | 1 (5/5) | 0.8 (4/5) | 0.2 (1/5) |
| religion-critical | 24 | 1 (24/24) | 1 (24/24) | 1 (24/24) | 0.12 (3/24) |
| role | 27 | 1 (27/27) | 1 (27/27) | 0.81 (22/27) | 0 (0/27) |
| speech | 4 | 1 (4/4) | 1 (4/4) | 1 (4/4) | 0.25 (1/4) |
| vague | 13 | 1 (13/13) | 1 (13/13) | 1 (13/13) | 0.23 (3/13) |
