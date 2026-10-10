# gather: evaluation on the version-2 dataset

- Dataset: `evaluation/gather_info_eval/golden_dataset_v2.csv`; rows scored: 60 of 60
- System model: `meta-llama/Llama-3.1-8B-Instruct` served at http://localhost:8000/v1 | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 200; tokens in 96118, out 5301
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Extraction correct, all rows | 0.82 (49/60) |
| Rows with a real answer: extracted correctly | 0.82 (49/60) |
| Rows with a real answer: wrongly returned NOT_PROVIDED | 0 (0/60) |
| Rows with no answer: returned NOT_PROVIDED | - |
| Rows with no answer: a fact was invented | - |
| Correct extractions that keep only the answer | 0.98 (48/49) |
| Parallel cases correct in all five languages | - |

### By reply type

| category | rows | correct |
|---|---|---|
| already-known | 6 | 0.5 (3/6) |
| direct | 14 | 0.71 (10/14) |
| negation | 14 | 0.86 (12/14) |
| numeric | 7 | 0.86 (6/7) |
| rambling | 7 | 0.86 (6/7) |
| short | 12 | 1 (12/12) |

### By language

| language | rows | correct |
|---|---|---|
| English | 14 | 0.71 (10/14) |
| Hindi | 13 | 0.92 (12/13) |
| Hinglish | 13 | 0.77 (10/13) |
| Kannada | 10 | 0.9 (9/10) |
| Tamil | 10 | 0.8 (8/10) |
