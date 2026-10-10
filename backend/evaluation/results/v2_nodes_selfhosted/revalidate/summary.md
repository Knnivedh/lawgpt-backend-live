# revalidate: evaluation on the version-2 dataset

- Dataset: `evaluation/revalidate_eval/golden_dataset_v2.csv`; rows scored: 60 of 60
- System model: `meta-llama/Llama-3.1-8B-Instruct` served at http://localhost:8000/v1 | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 200; tokens in 181388, out 53424
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

Two decisions are scored. "Model" is what the analyzer model says on its own. "Node" adds the rule in graph.py that stops asking after two re-validations or seven collected facts.

| Metric | Model alone | Node (with the stop rule) |
|---|---|---|
| Decision correct, all rows | 0.53 (32/60) | 0.6 (36/60) |
| Should stop: stops | 0 (0/27) | 0.15 (4/27) |
| Should ask more: asks more | 0.97 (32/33) | 0.97 (32/33) |

| When the model asks for more | Value |
|---|---|
| Rows where it asks | 59 of 60 |
| Mean questions per such row | 3.32 |
| Rows re-asking a known fact | 0.29 (17/59) |
| Rows with an out-of-scope question | 0.78 (46/59) |
| Rows asking for private details | 0.51 (30/59) |
| Rows answered by the keyword fallback | 0.02 (1/60) |
| Parallel rounds with the same model decision in all five languages | 0/10 stop, 9/10 ask |

### By language

| language | rows | model correct | node correct |
|---|---|---|---|
| English | 14 | 0.5 (7/14) | 0.71 (10/14) |
| Hindi | 13 | 0.46 (6/13) | 0.54 (7/13) |
| Hinglish | 13 | 0.62 (8/13) | 0.62 (8/13) |
| Kannada | 10 | 0.5 (5/10) | 0.5 (5/10) |
| Tamil | 10 | 0.6 (6/10) | 0.6 (6/10) |

### By round

| round | rows | model correct | node correct |
|---|---|---|---|
| 1 | 53 | 0.58 (31/53) | 0.58 (31/53) |
| 2 | 3 | 0.33 (1/3) | 0.33 (1/3) |
| 3 | 3 | 0 (0/3) | 1 (3/3) |
| 4 | 1 | 0 (0/1) | 1 (1/1) |
