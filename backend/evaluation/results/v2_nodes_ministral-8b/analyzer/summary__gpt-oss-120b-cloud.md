# analyzer: evaluation on the version-2 dataset

- Dataset: `evaluation/query_analyzer_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `mistralai/Ministral-8B-Instruct-2410` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 153096, out 50842
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Routes correctly (clarify when it should, proceed when it should) | 0.9 (179/200) |
| Confidence matches exactly | 0.54 (107/200) |
| Intent correct | 0.92 (184/200) |
| All given facts captured | 0.27 (53/200) |
| Must-ask field asked (rows that have one) | 0.7 (43/61) |
| Rows with no re-asked fact | 0.79 (158/200) |
| Rows with no out-of-scope question | 0.07 (13/200) |
| Rows asking for private details | 0.2 (39/200) |
| Mean questions it wants to ask | 4.01 |
| Rows answered by the keyword fallback, not the model | 0.01 (1/200) |
| Parallel cases routed correctly in all five languages | 26/30 |

### By language

| language | rows | routes correctly | intent | no re-ask | no scope creep |
|---|---|---|---|---|---|
| English | 40 | 0.9 (36/40) | 0.97 (39/40) | 0.88 (35/40) | 0.07 (3/40) |
| Hindi | 40 | 0.9 (36/40) | 0.93 (37/40) | 0.78 (31/40) | 0.05 (2/40) |
| Hinglish | 40 | 0.9 (36/40) | 0.88 (35/40) | 0.75 (30/40) | 0.07 (3/40) |
| Kannada | 40 | 0.9 (36/40) | 0.93 (37/40) | 0.8 (32/40) | 0.07 (3/40) |
| Tamil | 40 | 0.88 (35/40) | 0.9 (36/40) | 0.75 (30/40) | 0.05 (2/40) |

### By category

| category | rows | routes correctly | intent | no re-ask | no scope creep |
|---|---|---|---|---|---|
| already-detailed | 2 | 1 (2/2) | 1 (2/2) | 0.5 (1/2) | 0 (0/2) |
| asr-garbled | 1 | 0 (0/1) | 0 (0/1) | 1 (1/1) | 0 (0/1) |
| clear-complete | 26 | 1 (26/26) | 1 (26/26) | 0.73 (19/26) | 0 (0/26) |
| clear-partial | 68 | 1 (68/68) | 0.93 (63/68) | 0.75 (51/68) | 0.03 (2/68) |
| informational | 5 | 1 (5/5) | 1 (5/5) | 1 (5/5) | 1 (5/5) |
| multi-issue | 10 | 1 (10/10) | 1 (10/10) | 0.8 (8/10) | 0 (0/10) |
| noisy | 1 | 1 (1/1) | 1 (1/1) | 1 (1/1) | 0 (0/1) |
| off-topic | 14 | 0 (0/14) | 1 (14/14) | 0.79 (11/14) | 0.29 (4/14) |
| privacy-trap | 5 | 1 (5/5) | 0.8 (4/5) | 1 (5/5) | 0 (0/5) |
| religion-critical | 24 | 1 (24/24) | 0.96 (23/24) | 0.92 (22/24) | 0.08 (2/24) |
| role | 27 | 1 (27/27) | 0.96 (26/27) | 0.7 (19/27) | 0 (0/27) |
| speech | 4 | 1 (4/4) | 1 (4/4) | 0.5 (2/4) | 0 (0/4) |
| vague | 13 | 0.54 (7/13) | 0.46 (6/13) | 1 (13/13) | 0 (0/13) |
