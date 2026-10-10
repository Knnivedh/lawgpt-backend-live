# revalidate: evaluation on the version-2 dataset

- Dataset: `evaluation/revalidate_eval/golden_dataset_v2.csv`; rows scored: 29 of 120
- System model: `Qwen/Qwen3-8B` served at http://localhost:8000/v1 | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 200; tokens in 176592, out 50322
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

Two decisions are scored. "Model" is what the analyzer model says on its own. "Node" adds the rule in graph.py that stops asking after two re-validations or seven collected facts.

| Metric | Model alone | Node (with the stop rule) |
|---|---|---|
| Decision correct, all rows | 0.93 (27/29) | 0.93 (27/29) |
| Should stop: stops | 1 (27/27) | 1 (27/27) |
| Should ask more: asks more | 0 (0/2) | 0 (0/2) |

| When the model asks for more | Value |
|---|---|
| Rows where it asks | 0 of 29 |
| Mean questions per such row | None |
| Rows re-asking a known fact | - |
| Rows with an out-of-scope question | - |
| Rows asking for private details | - |
| Rows answered by the keyword fallback | 0 (0/29) |
| Parallel rounds with the same model decision in all five languages | - stop, - ask |

### By language

| language | rows | model correct | node correct |
|---|---|---|---|
| English | 9 | 1 (9/9) | 1 (9/9) |
| Hindi | 9 | 1 (9/9) | 1 (9/9) |
| Hinglish | 11 | 0.82 (9/11) | 0.82 (9/11) |

### By round

| round | rows | model correct | node correct |
|---|---|---|---|
| 1 | 1 | 0 (0/1) | 0 (0/1) |
| 2 | 10 | 0.9 (9/10) | 0.9 (9/10) |
| 3 | 16 | 1 (16/16) | 1 (16/16) |
| 4 | 2 | 1 (2/2) | 1 (2/2) |
