# gather: evaluation on the version-2 dataset

- Dataset: `evaluation/gather_info_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `mistralai/Ministral-8B-Instruct-2410` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 82745, out 5086
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Extraction correct, all rows | 0.6 (120/200) |
| Rows with a real answer: extracted correctly | 0.6 (120/200) |
| Rows with a real answer: wrongly returned NOT_PROVIDED | 0 (0/200) |
| Rows with no answer: returned NOT_PROVIDED | - |
| Rows with no answer: a fact was invented | - |
| Correct extractions that keep only the answer | 0.99 (119/120) |
| Parallel cases correct in all five languages | 10/30 |

### By reply type

| category | rows | correct |
|---|---|---|
| already-known | 20 | 0.35 (7/20) |
| direct | 46 | 0.5 (23/46) |
| negation | 46 | 0.7 (32/46) |
| numeric | 31 | 0.77 (24/31) |
| rambling | 20 | 0.15 (3/20) |
| short | 37 | 0.84 (31/37) |

### By language

| language | rows | correct |
|---|---|---|
| English | 40 | 0.57 (23/40) |
| Hindi | 40 | 0.65 (26/40) |
| Hinglish | 40 | 0.7 (28/40) |
| Kannada | 40 | 0.53 (21/40) |
| Tamil | 40 | 0.55 (22/40) |
