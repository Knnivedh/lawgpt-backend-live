# gather: evaluation on the version-2 dataset

- Dataset: `evaluation/gather_info_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `meta-llama/Llama-3.1-8B-Instruct` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 96118, out 5301
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Extraction correct, all rows | 0.71 (142/200) |
| Rows with a real answer: extracted correctly | 0.71 (142/200) |
| Rows with a real answer: wrongly returned NOT_PROVIDED | 0 (0/200) |
| Rows with no answer: returned NOT_PROVIDED | - |
| Rows with no answer: a fact was invented | - |
| Correct extractions that keep only the answer | 0.97 (138/142) |
| Parallel cases correct in all five languages | 12/30 |

### By reply type

| category | rows | correct |
|---|---|---|
| already-known | 20 | 0.7 (14/20) |
| direct | 46 | 0.65 (30/46) |
| negation | 46 | 0.74 (34/46) |
| numeric | 31 | 0.81 (25/31) |
| rambling | 20 | 0.35 (7/20) |
| short | 37 | 0.86 (32/37) |

### By language

| language | rows | correct |
|---|---|---|
| English | 40 | 0.7 (28/40) |
| Hindi | 40 | 0.72 (29/40) |
| Hinglish | 40 | 0.72 (29/40) |
| Kannada | 40 | 0.68 (27/40) |
| Tamil | 40 | 0.72 (29/40) |
