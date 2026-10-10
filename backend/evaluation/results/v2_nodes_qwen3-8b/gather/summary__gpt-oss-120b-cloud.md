# gather: evaluation on the version-2 dataset

- Dataset: `evaluation/gather_info_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `Qwen/Qwen3-8B` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 93159, out 5589
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Extraction correct, all rows | 0.73 (146/200) |
| Rows with a real answer: extracted correctly | 0.73 (146/200) |
| Rows with a real answer: wrongly returned NOT_PROVIDED | 0 (0/200) |
| Rows with no answer: returned NOT_PROVIDED | - |
| Rows with no answer: a fact was invented | - |
| Correct extractions that keep only the answer | 0.92 (135/146) |
| Parallel cases correct in all five languages | 14/30 |

### By reply type

| category | rows | correct |
|---|---|---|
| already-known | 20 | 0.55 (11/20) |
| direct | 46 | 0.57 (26/46) |
| negation | 46 | 0.83 (38/46) |
| numeric | 31 | 0.94 (29/31) |
| rambling | 20 | 0.55 (11/20) |
| short | 37 | 0.84 (31/37) |

### By language

| language | rows | correct |
|---|---|---|
| English | 40 | 0.75 (30/40) |
| Hindi | 40 | 0.65 (26/40) |
| Hinglish | 40 | 0.72 (29/40) |
| Kannada | 40 | 0.8 (32/40) |
| Tamil | 40 | 0.72 (29/40) |
