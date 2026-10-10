# reasoning: evaluation on the version-2 dataset

- Dataset: `evaluation/reasoning_eval/golden_dataset_v2.csv`; rows scored: 60 of 60
- System model: `google/gemma-4-E4B-it` served at http://localhost:8000/v1 | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 200; tokens in 163105, out 60034
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Related past cases scored 0.5 or more | 0.5 (28/56) |
| Unrelated past cases scored 0.3 or less | 1 (4/4) |
| Unrelated past cases scored 0.5 or more (over-claiming) | 0 (0/4) |
| Mean score given: related / unrelated | 0.48 / 0.03 |
| Unrelated: explanation invents a specific similarity | 0 (0/4) |
| Unrelated: explanation says the case shaped the answer | 0 (0/4) |
| Quoted excerpt not found in the past case (replaced by its opening lines) | 0.3 (18/60) |
| Rows where the model output could not be read (default 0.5 used) | 0 (0/60) |
| Parallel pairs scored in the right band in all five languages | 3/10 |

### By language

| language | rows | related scored high | unrelated scored low |
|---|---|---|---|
| English | 14 | 0.55 (6/11) | 1 (3/3) |
| Hindi | 13 | 0.42 (5/12) | 1 (1/1) |
| Hinglish | 13 | 0.69 (9/13) | - |
| Kannada | 10 | 0.3 (3/10) | - |
| Tamil | 10 | 0.5 (5/10) | - |
