# revalidate: evaluation on the version-2 dataset

- Dataset: `evaluation/revalidate_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `mistralai/Ministral-8B-Instruct-2410` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 166341, out 48363
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

Two decisions are scored. "Model" is what the analyzer model says on its own. "Node" adds the rule in graph.py that stops asking after two re-validations or seven collected facts.

| Metric | Model alone | Node (with the stop rule) |
|---|---|---|
| Decision correct, all rows | 0.47 (94/200) | 0.71 (143/200) |
| Should stop: stops | 0.34 (48/140) | 0.7 (98/140) |
| Should ask more: asks more | 0.77 (46/60) | 0.75 (45/60) |

| When the model asks for more | Value |
|---|---|
| Rows where it asks | 138 of 200 |
| Mean questions per such row | 3.7 |
| Rows re-asking a known fact | 0.11 (15/138) |
| Rows with an out-of-scope question | 0.17 (24/138) |
| Rows asking for private details | 0.43 (60/138) |
| Rows answered by the keyword fallback | 0.03 (5/200) |
| Parallel rounds with the same model decision in all five languages | 5/30 stop, 11/30 ask |

### By language

| language | rows | model correct | node correct |
|---|---|---|---|
| English | 40 | 0.4 (16/40) | 0.68 (27/40) |
| Hindi | 40 | 0.38 (15/40) | 0.68 (27/40) |
| Hinglish | 40 | 0.5 (20/40) | 0.75 (30/40) |
| Kannada | 40 | 0.5 (20/40) | 0.75 (30/40) |
| Tamil | 40 | 0.57 (23/40) | 0.72 (29/40) |

### By round

| round | rows | model correct | node correct |
|---|---|---|---|
| 1 | 65 | 0.57 (37/65) | 0.57 (37/65) |
| 2 | 65 | 0.46 (30/65) | 0.55 (36/65) |
| 3 | 65 | 0.4 (26/65) | 1 (65/65) |
| 4 | 5 | 0.2 (1/5) | 1 (5/5) |
