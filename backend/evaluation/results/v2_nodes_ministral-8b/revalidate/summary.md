# revalidate: evaluation on the version-2 dataset

- Dataset: `evaluation/revalidate_eval/golden_dataset_v2.csv`; rows scored: 31 of 120
- System model: `mistralai/Ministral-8B-Instruct-2410` served at http://localhost:8000/v1 | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 200; tokens in 166341, out 48363
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

Two decisions are scored. "Model" is what the analyzer model says on its own. "Node" adds the rule in graph.py that stops asking after two re-validations or seven collected facts.

| Metric | Model alone | Node (with the stop rule) |
|---|---|---|
| Decision correct, all rows | 0.74 (23/31) | 0.74 (23/31) |
| Should stop: stops | 1 (23/23) | 1 (23/23) |
| Should ask more: asks more | 0 (0/8) | 0 (0/8) |

| When the model asks for more | Value |
|---|---|
| Rows where it asks | 0 of 31 |
| Mean questions per such row | None |
| Rows re-asking a known fact | - |
| Rows with an out-of-scope question | - |
| Rows asking for private details | - |
| Rows answered by the keyword fallback | 0.13 (4/31) |
| Parallel rounds with the same model decision in all five languages | - stop, - ask |

### By language

| language | rows | model correct | node correct |
|---|---|---|---|
| English | 8 | 0.75 (6/8) | 0.75 (6/8) |
| Hindi | 7 | 0.71 (5/7) | 0.71 (5/7) |
| Hinglish | 16 | 0.75 (12/16) | 0.75 (12/16) |

### By round

| round | rows | model correct | node correct |
|---|---|---|---|
| 1 | 4 | 0.25 (1/4) | 0.25 (1/4) |
| 2 | 14 | 0.64 (9/14) | 0.64 (9/14) |
| 3 | 13 | 1 (13/13) | 1 (13/13) |
