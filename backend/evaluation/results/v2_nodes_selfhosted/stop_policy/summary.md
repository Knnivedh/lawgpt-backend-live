# stop_policy: evaluation on the version-2 dataset

- Dataset: `evaluation/revalidate_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `meta-llama/Llama-3.1-8B-Instruct` served at http://localhost:8000/v1 | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 200; tokens in 90598, out 3428
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | This check alone | With the code's stop rule |
|---|---|---|
| Decision correct, all rows | 0.59 (118/200) | 0.69 (138/200) |
| Should stop: stops | 0.77 (108/140) | 0.91 (128/140) |
| Should ask more: asks more | 0.17 (10/60) | 0.17 (10/60) |

| Other | Value |
|---|---|
| When it rightly asks, the missing fact it names is religion / applicable law | 1 (10/10) |
| Replies that could not be read as yes or no | 0 (0/200) |
| Parallel rounds with the same decision in all five languages | 11/30 stop, 0/30 ask |

Baseline on the same rows (the analyzer re-run on the collected facts): decision correct 0.30 alone, 0.70 with the stop rule; stops when it should 1 of 140.

### By language

| language | rows | correct |
|---|---|---|
| English | 40 | 0.62 (25/40) |
| Hindi | 40 | 0.68 (27/40) |
| Hinglish | 40 | 0.65 (26/40) |
| Kannada | 40 | 0.42 (17/40) |
| Tamil | 40 | 0.57 (23/40) |

### By round

| round | rows | correct |
|---|---|---|
| 1 | 65 | 0.4 (26/65) |
| 2 | 65 | 0.55 (36/65) |
| 3 | 65 | 0.78 (51/65) |
| 4 | 5 | 1 (5/5) |
