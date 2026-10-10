# reasoning: evaluation on the version-2 dataset

- Dataset: `evaluation/reasoning_eval/golden_dataset_v2.csv`; rows scored: 60 of 60
- System model: `meta-llama/Llama-3.1-8B-Instruct` served at http://localhost:8000/v1 | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 200; tokens in 189620, out 50568
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Related past cases scored 0.5 or more | 1 (56/56) |
| Unrelated past cases scored 0.3 or less | 0.75 (3/4) |
| Unrelated past cases scored 0.5 or more (over-claiming) | 0.25 (1/4) |
| Mean score given: related / unrelated | 0.76 / 0.33 |
| Unrelated: explanation invents a specific similarity | 1 (4/4) |
| Unrelated: explanation says the case shaped the answer | 1 (4/4) |
| Quoted excerpt not found in the past case (replaced by its opening lines) | 0.42 (25/60) |
| Rows where the model output could not be read (default 0.5 used) | 0 (0/60) |
| Parallel pairs scored in the right band in all five languages | 10/10 |

### By language

| language | rows | related scored high | unrelated scored low |
|---|---|---|---|
| English | 14 | 1 (11/11) | 0.67 (2/3) |
| Hindi | 13 | 1 (12/12) | 1 (1/1) |
| Hinglish | 13 | 1 (13/13) | - |
| Kannada | 10 | 1 (10/10) | - |
| Tamil | 10 | 1 (10/10) | - |
