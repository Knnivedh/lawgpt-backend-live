# reasoning: evaluation on the version-2 dataset

- Dataset: `evaluation/reasoning_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `meta-llama/Llama-3.1-8B-Instruct` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 189620, out 50568
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Related past cases scored 0.5 or more | 1 (130/130) |
| Unrelated past cases scored 0.3 or less | 0.6 (42/70) |
| Unrelated past cases scored 0.5 or more (over-claiming) | 0.37 (26/70) |
| Mean score given: related / unrelated | 0.77 / 0.38 |
| Unrelated: explanation invents a specific similarity | 0.66 (46/70) |
| Unrelated: explanation says the case shaped the answer | 0.91 (64/70) |
| Quoted excerpt not found in the past case (replaced by its opening lines) | 0.47 (94/200) |
| Rows where the model output could not be read (default 0.5 used) | 0.01 (1/200) |
| Parallel pairs scored in the right band in all five languages | 23/30 |

### By language

| language | rows | related scored high | unrelated scored low |
|---|---|---|---|
| English | 40 | 1 (26/26) | 0.79 (11/14) |
| Hindi | 40 | 1 (26/26) | 0.64 (9/14) |
| Hinglish | 40 | 1 (26/26) | 0.57 (8/14) |
| Kannada | 40 | 1 (26/26) | 0.57 (8/14) |
| Tamil | 40 | 1 (26/26) | 0.43 (6/14) |
