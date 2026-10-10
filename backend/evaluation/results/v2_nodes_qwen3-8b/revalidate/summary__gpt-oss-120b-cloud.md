# revalidate: evaluation on the version-2 dataset

- Dataset: `evaluation/revalidate_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `Qwen/Qwen3-8B` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 176592, out 50322
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

Two decisions are scored. "Model" is what the analyzer model says on its own. "Node" adds the rule in graph.py that stops asking after two re-validations or seven collected facts.

| Metric | Model alone | Node (with the stop rule) |
|---|---|---|
| Decision correct, all rows | 0.52 (104/200) | 0.77 (153/200) |
| Should stop: stops | 0.33 (46/140) | 0.69 (96/140) |
| Should ask more: asks more | 0.97 (58/60) | 0.95 (57/60) |

| When the model asks for more | Value |
|---|---|
| Rows where it asks | 152 of 200 |
| Mean questions per such row | 3.32 |
| Rows re-asking a known fact | 0.22 (33/152) |
| Rows with an out-of-scope question | 0.2 (31/152) |
| Rows asking for private details | 0.07 (11/152) |
| Rows answered by the keyword fallback | 0 (0/200) |
| Parallel rounds with the same model decision in all five languages | 5/30 stop, 18/30 ask |

### By language

| language | rows | model correct | node correct |
|---|---|---|---|
| English | 40 | 0.53 (21/40) | 0.75 (30/40) |
| Hindi | 40 | 0.53 (21/40) | 0.75 (30/40) |
| Hinglish | 40 | 0.47 (19/40) | 0.72 (29/40) |
| Kannada | 40 | 0.53 (21/40) | 0.8 (32/40) |
| Tamil | 40 | 0.55 (22/40) | 0.8 (32/40) |

### By round

| round | rows | model correct | node correct |
|---|---|---|---|
| 1 | 65 | 0.6 (39/65) | 0.6 (39/65) |
| 2 | 65 | 0.54 (35/65) | 0.68 (44/65) |
| 3 | 65 | 0.43 (28/65) | 1 (65/65) |
| 4 | 5 | 0.4 (2/5) | 1 (5/5) |
