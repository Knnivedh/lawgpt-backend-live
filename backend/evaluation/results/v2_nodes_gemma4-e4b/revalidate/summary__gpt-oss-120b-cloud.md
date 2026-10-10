# revalidate: evaluation on the version-2 dataset

- Dataset: `evaluation/revalidate_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `google/gemma-4-E4B-it` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 165639, out 55506
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

Two decisions are scored. "Model" is what the analyzer model says on its own. "Node" adds the rule in graph.py that stops asking after two re-validations or seven collected facts.

| Metric | Model alone | Node (with the stop rule) |
|---|---|---|
| Decision correct, all rows | 0.3 (60/200) | 0.7 (141/200) |
| Should stop: stops | 0 (0/140) | 0.59 (82/140) |
| Should ask more: asks more | 1 (60/60) | 0.98 (59/60) |

| When the model asks for more | Value |
|---|---|
| Rows where it asks | 200 of 200 |
| Mean questions per such row | 2.25 |
| Rows re-asking a known fact | 0.07 (14/200) |
| Rows with an out-of-scope question | 0.12 (25/200) |
| Rows asking for private details | 0.01 (1/200) |
| Rows answered by the keyword fallback | 0 (0/200) |
| Parallel rounds with the same model decision in all five languages | 0/30 stop, 30/30 ask |

### By language

| language | rows | model correct | node correct |
|---|---|---|---|
| English | 40 | 0.3 (12/40) | 0.68 (27/40) |
| Hindi | 40 | 0.3 (12/40) | 0.7 (28/40) |
| Hinglish | 40 | 0.3 (12/40) | 0.7 (28/40) |
| Kannada | 40 | 0.3 (12/40) | 0.72 (29/40) |
| Tamil | 40 | 0.3 (12/40) | 0.72 (29/40) |

### By round

| round | rows | model correct | node correct |
|---|---|---|---|
| 1 | 65 | 0.62 (40/65) | 0.62 (40/65) |
| 2 | 65 | 0.31 (20/65) | 0.48 (31/65) |
| 3 | 65 | 0 (0/65) | 1 (65/65) |
| 4 | 5 | 0 (0/5) | 1 (5/5) |
