# gather: evaluation on the version-2 dataset

- Dataset: `evaluation/gather_info_eval/golden_dataset_v2.csv`; rows scored: 5 of 5
- System model: `meta-llama/Llama-3.1-8B-Instruct` (Hugging Face) | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 5; tokens in 2067, out 119
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Extraction correct, all rows | 1 (5/5) |
| Rows with a real answer: extracted correctly | 1 (5/5) |
| Rows with a real answer: wrongly returned NOT_PROVIDED | 0 (0/5) |
| Rows with no answer: returned NOT_PROVIDED | - |
| Rows with no answer: a fact was invented | - |
| Correct extractions that keep only the answer | 1 (5/5) |
| Parallel cases correct in all five languages | - |

### By reply type

| category | rows | correct |
|---|---|---|
| negation | 2 | 1 (2/2) |
| numeric | 1 | 1 (1/1) |
| rambling | 1 | 1 (1/1) |
| short | 1 | 1 (1/1) |

### By language

| language | rows | correct |
|---|---|---|
| English | 4 | 1 (4/4) |
| Hindi | 1 | 1 (1/1) |
