# analyzer: evaluation on the version-2 dataset

- Dataset: `evaluation/query_analyzer_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `meta-llama/Llama-3.1-8B-Instruct` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 166924, out 67418
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Routes correctly (clarify when it should, proceed when it should) | 0.92 (184/200) |
| Confidence matches exactly | 0.71 (142/200) |
| Intent correct | 0.9 (180/200) |
| All given facts captured | 0.4 (80/200) |
| Must-ask field asked (rows that have one) | 0.86 (55/64) |
| Rows with no re-asked fact | 0.89 (178/200) |
| Rows with no out-of-scope question | 0.02 (4/200) |
| Rows asking for private details | 0.2 (41/200) |
| Mean questions it wants to ask | 3.6 |
| Rows answered by the keyword fallback, not the model | 0.03 (5/200) |
| Parallel cases routed correctly in all five languages | 28/30 |

### By language

| language | rows | routes correctly | intent | no re-ask | no scope creep |
|---|---|---|---|---|---|
| English | 40 | 0.9 (36/40) | 0.97 (39/40) | 0.88 (35/40) | 0 (0/40) |
| Hindi | 40 | 0.93 (37/40) | 0.95 (38/40) | 0.82 (33/40) | 0.03 (1/40) |
| Hinglish | 40 | 0.93 (37/40) | 0.93 (37/40) | 0.95 (38/40) | 0 (0/40) |
| Kannada | 40 | 0.93 (37/40) | 0.82 (33/40) | 0.88 (35/40) | 0.05 (2/40) |
| Tamil | 40 | 0.93 (37/40) | 0.82 (33/40) | 0.93 (37/40) | 0.03 (1/40) |

### By category

| category | rows | routes correctly | intent | no re-ask | no scope creep |
|---|---|---|---|---|---|
| already-detailed | 2 | 1 (2/2) | 1 (2/2) | 1 (2/2) | 0 (0/2) |
| asr-garbled | 1 | 0 (0/1) | 0 (0/1) | 1 (1/1) | 0 (0/1) |
| clear-complete | 26 | 1 (26/26) | 0.88 (23/26) | 0.88 (23/26) | 0.04 (1/26) |
| clear-partial | 68 | 1 (68/68) | 0.93 (63/68) | 0.87 (59/68) | 0.01 (1/68) |
| informational | 5 | 1 (5/5) | 1 (5/5) | 1 (5/5) | 0 (0/5) |
| multi-issue | 10 | 1 (10/10) | 1 (10/10) | 0.9 (9/10) | 0 (0/10) |
| noisy | 1 | 0 (0/1) | 1 (1/1) | 1 (1/1) | 0 (0/1) |
| off-topic | 14 | 0 (0/14) | 0.93 (13/14) | 0.93 (13/14) | 0.14 (2/14) |
| privacy-trap | 5 | 1 (5/5) | 1 (5/5) | 1 (5/5) | 0 (0/5) |
| religion-critical | 24 | 1 (24/24) | 0.96 (23/24) | 0.88 (21/24) | 0 (0/24) |
| role | 27 | 1 (27/27) | 0.89 (24/27) | 0.85 (23/27) | 0 (0/27) |
| speech | 4 | 1 (4/4) | 1 (4/4) | 1 (4/4) | 0 (0/4) |
| vague | 13 | 1 (13/13) | 0.54 (7/13) | 0.92 (12/13) | 0 (0/13) |
