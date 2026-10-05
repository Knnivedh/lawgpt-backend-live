# analyzer: evaluation on the version-2 dataset

- Dataset: `evaluation/query_analyzer_eval/golden_dataset_v2.csv`; rows scored: 5 of 5
- System model: `meta-llama/Llama-3.1-8B-Instruct` (Hugging Face) | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 5; tokens in 3630, out 1122
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Routes correctly (clarify when it should, proceed when it should) | 1 (5/5) |
| Confidence matches exactly | 0.8 (4/5) |
| Intent correct | 1 (5/5) |
| All given facts captured | 0.8 (4/5) |
| Must-ask field asked (rows that have one) | - |
| Rows with no re-asked fact | 0.6 (3/5) |
| Rows with no out-of-scope question | 0 (0/5) |
| Rows asking for private details | 0.2 (1/5) |
| Mean questions it wants to ask | 3.6 |
| Rows answered by the keyword fallback, not the model | 0 (0/5) |
| Parallel cases routed correctly in all five languages | - |

### By language

| language | rows | routes correctly | intent | no re-ask | no scope creep |
|---|---|---|---|---|---|
| English | 4 | 1 (4/4) | 1 (4/4) | 0.75 (3/4) | 0 (0/4) |
| Hindi | 1 | 1 (1/1) | 1 (1/1) | 0 (0/1) | 0 (0/1) |

### By category

| category | rows | routes correctly | intent | no re-ask | no scope creep |
|---|---|---|---|---|---|
| clear-partial | 2 | 1 (2/2) | 1 (2/2) | 0.5 (1/2) | 0 (0/2) |
| role | 1 | 1 (1/1) | 1 (1/1) | 1 (1/1) | 0 (0/1) |
| speech | 1 | 1 (1/1) | 1 (1/1) | 0 (0/1) | 0 (0/1) |
| vague | 1 | 1 (1/1) | 1 (1/1) | 1 (1/1) | 0 (0/1) |
