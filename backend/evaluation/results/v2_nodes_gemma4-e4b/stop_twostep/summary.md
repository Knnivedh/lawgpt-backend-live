# stop_twostep: evaluation on the version-2 dataset

- Dataset: `evaluation/revalidate_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `google/gemma-4-E4B-it` served at http://localhost:8000/v1 | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 200; tokens in 42779, out 1600
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | This check alone | With the code's stop rule |
|---|---|---|
| Decision correct, all rows | 0.99 (199/200) | 0.99 (198/200) |
| Should stop: stops | 1 (140/140) | 1 (140/140) |
| Should ask more: asks more | 0.98 (59/60) | 0.97 (58/60) |

| Other | Value |
|---|---|
| When it rightly asks, the missing fact it names is religion / applicable law | 1 (59/59) |
| Replies that could not be read as yes or no | 0 (0/200) |
| Parallel rounds with the same decision in all five languages | 21/30 stop, 9/30 ask |

Baseline on the same rows (the analyzer re-run on the collected facts): decision correct 0.30 alone, 0.70 with the stop rule; stops when it should 1 of 140.

### By language

| language | rows | correct |
|---|---|---|
| English | 40 | 0.97 (39/40) |
| Hindi | 40 | 1 (40/40) |
| Hinglish | 40 | 1 (40/40) |
| Kannada | 40 | 1 (40/40) |
| Tamil | 40 | 1 (40/40) |

### By round

| round | rows | correct |
|---|---|---|
| 1 | 65 | 0.98 (64/65) |
| 2 | 65 | 1 (65/65) |
| 3 | 65 | 1 (65/65) |
| 4 | 5 | 1 (5/5) |
