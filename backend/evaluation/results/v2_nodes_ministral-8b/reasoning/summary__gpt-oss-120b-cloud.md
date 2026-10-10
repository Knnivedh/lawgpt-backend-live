# reasoning: evaluation on the version-2 dataset

- Dataset: `evaluation/reasoning_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `mistralai/Ministral-8B-Instruct-2410` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 166492, out 50108
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Related past cases scored 0.5 or more | 1 (130/130) |
| Unrelated past cases scored 0.3 or less | 0.21 (15/70) |
| Unrelated past cases scored 0.5 or more (over-claiming) | 0.77 (54/70) |
| Mean score given: related / unrelated | 0.77 / 0.55 |
| Unrelated: explanation invents a specific similarity | 0.61 (43/70) |
| Unrelated: explanation says the case shaped the answer | 0.81 (57/70) |
| Quoted excerpt not found in the past case (replaced by its opening lines) | 0.53 (105/200) |
| Rows where the model output could not be read (default 0.5 used) | 0 (0/200) |
| Parallel pairs scored in the right band in all five languages | 20/30 |

### By language

| language | rows | related scored high | unrelated scored low |
|---|---|---|---|
| English | 40 | 1 (26/26) | 0.21 (3/14) |
| Hindi | 40 | 1 (26/26) | 0.29 (4/14) |
| Hinglish | 40 | 1 (26/26) | 0.29 (4/14) |
| Kannada | 40 | 1 (26/26) | 0.14 (2/14) |
| Tamil | 40 | 1 (26/26) | 0.14 (2/14) |
