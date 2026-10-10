# reasoning: evaluation on the version-2 dataset

- Dataset: `evaluation/reasoning_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `Qwen/Qwen3-8B` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 186348, out 46370
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Related past cases scored 0.5 or more | 0.92 (120/130) |
| Unrelated past cases scored 0.3 or less | 0.99 (69/70) |
| Unrelated past cases scored 0.5 or more (over-claiming) | 0.01 (1/70) |
| Mean score given: related / unrelated | 0.74 / 0.04 |
| Unrelated: explanation invents a specific similarity | 0.06 (4/70) |
| Unrelated: explanation says the case shaped the answer | 0.16 (11/70) |
| Quoted excerpt not found in the past case (replaced by its opening lines) | 0.32 (63/200) |
| Rows where the model output could not be read (default 0.5 used) | 0 (0/200) |
| Parallel pairs scored in the right band in all five languages | 27/30 |

### By language

| language | rows | related scored high | unrelated scored low |
|---|---|---|---|
| English | 40 | 0.92 (24/26) | 1 (14/14) |
| Hindi | 40 | 0.92 (24/26) | 1 (14/14) |
| Hinglish | 40 | 0.92 (24/26) | 1 (14/14) |
| Kannada | 40 | 0.88 (23/26) | 1 (14/14) |
| Tamil | 40 | 0.96 (25/26) | 0.93 (13/14) |
