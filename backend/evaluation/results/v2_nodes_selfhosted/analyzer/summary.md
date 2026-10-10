# analyzer: evaluation on the version-2 dataset

- Dataset: `evaluation/query_analyzer_eval/golden_dataset_v2.csv`; rows scored: 60 of 60
- System model: `meta-llama/Llama-3.1-8B-Instruct` served at http://localhost:8000/v1 | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 200; tokens in 166924, out 67418
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Routes correctly (clarify when it should, proceed when it should) | 0.92 (55/60) |
| Confidence matches exactly | 0.68 (41/60) |
| Intent correct | 0.88 (53/60) |
| All given facts captured | 0.58 (35/60) |
| Must-ask field asked (rows that have one) | 0.88 (15/17) |
| Rows with no re-asked fact | 0.77 (46/60) |
| Rows with no out-of-scope question | 0.05 (3/60) |
| Rows asking for private details | 0.3 (18/60) |
| Mean questions it wants to ask | 3.73 |
| Rows answered by the keyword fallback, not the model | 0.02 (1/60) |
| Parallel cases routed correctly in all five languages | - |

### By language

| language | rows | routes correctly | intent | no re-ask | no scope creep |
|---|---|---|---|---|---|
| English | 14 | 0.86 (12/14) | 1 (14/14) | 0.71 (10/14) | 0.07 (1/14) |
| Hindi | 13 | 0.92 (12/13) | 0.92 (12/13) | 0.85 (11/13) | 0.15 (2/13) |
| Hinglish | 13 | 0.92 (12/13) | 0.92 (12/13) | 0.77 (10/13) | 0 (0/13) |
| Kannada | 10 | 1 (10/10) | 0.9 (9/10) | 0.8 (8/10) | 0 (0/10) |
| Tamil | 10 | 0.9 (9/10) | 0.6 (6/10) | 0.7 (7/10) | 0 (0/10) |

### By category

| category | rows | routes correctly | intent | no re-ask | no scope creep |
|---|---|---|---|---|---|
| already-detailed | 1 | 1 (1/1) | 1 (1/1) | 1 (1/1) | 0 (0/1) |
| asr-garbled | 1 | 0 (0/1) | 0 (0/1) | 1 (1/1) | 0 (0/1) |
| clear-complete | 7 | 1 (7/7) | 0.86 (6/7) | 0.86 (6/7) | 0 (0/7) |
| clear-partial | 21 | 1 (21/21) | 0.9 (19/21) | 0.67 (14/21) | 0.05 (1/21) |
| informational | 2 | 1 (2/2) | 1 (2/2) | 1 (2/2) | 0 (0/2) |
| multi-issue | 3 | 1 (3/3) | 1 (3/3) | 1 (3/3) | 0 (0/3) |
| off-topic | 4 | 0 (0/4) | 1 (4/4) | 1 (4/4) | 0.25 (1/4) |
| privacy-trap | 1 | 1 (1/1) | 1 (1/1) | 1 (1/1) | 0 (0/1) |
| religion-critical | 8 | 1 (8/8) | 0.88 (7/8) | 0.62 (5/8) | 0.12 (1/8) |
| role | 8 | 1 (8/8) | 0.88 (7/8) | 0.62 (5/8) | 0 (0/8) |
| vague | 4 | 1 (4/4) | 0.75 (3/4) | 1 (4/4) | 0 (0/4) |
