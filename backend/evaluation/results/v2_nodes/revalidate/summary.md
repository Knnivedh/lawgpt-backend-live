# revalidate: evaluation on the version-2 dataset

- Dataset: `evaluation/revalidate_eval/golden_dataset_v2.csv`; rows scored: 4 of 5
- System model: `meta-llama/Llama-3.1-8B-Instruct` (Hugging Face) | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 4; tokens in 3581, out 964
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

Two decisions are scored. "Model" is what the analyzer model says on its own. "Node" adds the rule in graph.py that stops asking after two re-validations or seven collected facts.

| Metric | Model alone | Node (with the stop rule) |
|---|---|---|
| Decision correct, all rows | 0.5 (2/4) | 0.75 (3/4) |
| Should stop: stops | 0 (0/2) | 0.5 (1/2) |
| Should ask more: asks more | 1 (2/2) | 1 (2/2) |

| When the model asks for more | Value |
|---|---|
| Rows where it asks | 4 of 4 |
| Mean questions per such row | 3.5 |
| Rows re-asking a known fact | 0.5 (2/4) |
| Rows with an out-of-scope question | 1 (4/4) |
| Rows asking for private details | 0.5 (2/4) |
| Rows answered by the keyword fallback | 0 (0/4) |
| Parallel rounds with the same model decision in all five languages | - stop, - ask |

### By language

| language | rows | model correct | node correct |
|---|---|---|---|
| English | 2 | 0.5 (1/2) | 0.5 (1/2) |
| Hindi | 1 | 0 (0/1) | 1 (1/1) |
| Tamil | 1 | 1 (1/1) | 1 (1/1) |

### By round

| round | rows | model correct | node correct |
|---|---|---|---|
| 1 | 2 | 0.5 (1/2) | 0.5 (1/2) |
| 2 | 1 | 1 (1/1) | 1 (1/1) |
| 3 | 1 | 0 (0/1) | 1 (1/1) |
