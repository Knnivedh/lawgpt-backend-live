# stop_generic: evaluation on the version-2 dataset

- Dataset: `evaluation/revalidate_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `meta-llama/Llama-3.1-8B-Instruct` served at http://localhost:8000/v1 | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 200; tokens in 65998, out 4690
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | This check alone | With the code's stop rule |
|---|---|---|
| Decision correct, all rows | 0.43 (86/200) | 0.72 (145/200) |
| Should stop: stops | 0.28 (39/140) | 0.71 (99/140) |
| Should ask more: asks more | 0.78 (47/60) | 0.77 (46/60) |

| Other | Value |
|---|---|
| When it rightly asks, the missing fact it names is religion / applicable law | 0.13 (6/47) |
| Replies that could not be read as yes or no | 0 (0/200) |
| Parallel rounds with the same decision in all five languages | 2/30 stop, 11/30 ask |

Baseline on the same rows (the analyzer re-run on the collected facts): decision correct 0.30 alone, 0.70 with the stop rule; stops when it should 1 of 140.

### By language

| language | rows | correct |
|---|---|---|
| English | 40 | 0.38 (15/40) |
| Hindi | 40 | 0.53 (21/40) |
| Hinglish | 40 | 0.53 (21/40) |
| Kannada | 40 | 0.4 (16/40) |
| Tamil | 40 | 0.33 (13/40) |

### By round

| round | rows | correct |
|---|---|---|
| 1 | 65 | 0.63 (41/65) |
| 2 | 65 | 0.38 (25/65) |
| 3 | 65 | 0.31 (20/65) |
| 4 | 5 | 0 (0/5) |
