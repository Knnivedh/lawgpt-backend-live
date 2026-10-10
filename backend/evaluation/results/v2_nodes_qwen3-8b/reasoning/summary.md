# reasoning: evaluation on the version-2 dataset

- Dataset: `evaluation/reasoning_eval/golden_dataset_v2.csv`; rows scored: 78 of 120
- System model: `Qwen/Qwen3-8B` served at http://localhost:8000/v1 | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 200; tokens in 186348, out 46370
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Related past cases scored 0.5 or more | 0.92 (72/78) |
| Unrelated past cases scored 0.3 or less | - |
| Unrelated past cases scored 0.5 or more (over-claiming) | - |
| Mean score given: related / unrelated | 0.74 / None |
| Unrelated: explanation invents a specific similarity | - |
| Unrelated: explanation says the case shaped the answer | - |
| Quoted excerpt not found in the past case (replaced by its opening lines) | 0.24 (19/78) |
| Rows where the model output could not be read (default 0.5 used) | 0 (0/78) |
| Parallel pairs scored in the right band in all five languages | - |

### By language

| language | rows | related scored high | unrelated scored low |
|---|---|---|---|
| English | 26 | 0.92 (24/26) | - |
| Hindi | 26 | 0.92 (24/26) | - |
| Hinglish | 26 | 0.92 (24/26) | - |
