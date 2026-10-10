# stop_policy: evaluation on the version-2 dataset

- Dataset: `evaluation/revalidate_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `google/gemma-4-E4B-it` served at http://localhost:8000/v1 | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 200; tokens in 65978, out 2140
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | This check alone | With the code's stop rule |
|---|---|---|
| Decision correct, all rows | 0.68 (136/200) | 0.7 (140/200) |
| Should stop: stops | 0.97 (136/140) | 1 (140/140) |
| Should ask more: asks more | 0 (0/60) | 0 (0/60) |

| Other | Value |
|---|---|
| When it rightly asks, the missing fact it names is religion / applicable law | - |
| Replies that could not be read as yes or no | 0 (0/200) |
| Parallel rounds with the same decision in all five languages | 29/30 stop, 0/30 ask |

Baseline on the same rows (the analyzer re-run on the collected facts): decision correct 0.30 alone, 0.70 with the stop rule; stops when it should 1 of 140.

### By language

| language | rows | correct |
|---|---|---|
| English | 40 | 0.68 (27/40) |
| Hindi | 40 | 0.7 (28/40) |
| Hinglish | 40 | 0.68 (27/40) |
| Kannada | 40 | 0.68 (27/40) |
| Tamil | 40 | 0.68 (27/40) |

### By round

| round | rows | correct |
|---|---|---|
| 1 | 65 | 0.38 (25/65) |
| 2 | 65 | 0.69 (45/65) |
| 3 | 65 | 0.94 (61/65) |
| 4 | 5 | 1 (5/5) |
