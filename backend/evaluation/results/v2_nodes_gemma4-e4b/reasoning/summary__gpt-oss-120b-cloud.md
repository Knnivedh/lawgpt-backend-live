# reasoning: evaluation on the version-2 dataset

- Dataset: `evaluation/reasoning_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `google/gemma-4-E4B-it` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 163105, out 60034
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Related past cases scored 0.5 or more | 0.55 (72/130) |
| Unrelated past cases scored 0.3 or less | 1 (70/70) |
| Unrelated past cases scored 0.5 or more (over-claiming) | 0 (0/70) |
| Mean score given: related / unrelated | 0.51 / 0.02 |
| Unrelated: explanation invents a specific similarity | 0.01 (1/70) |
| Unrelated: explanation says the case shaped the answer | 0.09 (6/70) |
| Quoted excerpt not found in the past case (replaced by its opening lines) | 0.35 (71/200) |
| Rows where the model output could not be read (default 0.5 used) | 0 (0/200) |
| Parallel pairs scored in the right band in all five languages | 19/30 |

### By language

| language | rows | related scored high | unrelated scored low |
|---|---|---|---|
| English | 40 | 0.54 (14/26) | 1 (14/14) |
| Hindi | 40 | 0.5 (13/26) | 1 (14/14) |
| Hinglish | 40 | 0.65 (17/26) | 1 (14/14) |
| Kannada | 40 | 0.42 (11/26) | 1 (14/14) |
| Tamil | 40 | 0.65 (17/26) | 1 (14/14) |
