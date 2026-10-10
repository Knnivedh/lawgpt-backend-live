# stop_twostep: evaluation on the version-2 dataset

- Dataset: `evaluation/revalidate_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `meta-llama/Llama-3.1-8B-Instruct` served at http://localhost:8000/v1 | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 200; tokens in 67587, out 1600
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | This check alone | With the code's stop rule |
|---|---|---|
| Decision correct, all rows | 0.92 (184/200) | 0.94 (187/200) |
| Should stop: stops | 0.92 (129/140) | 0.94 (132/140) |
| Should ask more: asks more | 0.92 (55/60) | 0.92 (55/60) |

| Other | Value |
|---|---|
| When it rightly asks, the missing fact it names is religion / applicable law | 1 (55/55) |
| Replies that could not be read as yes or no | 0 (0/200) |
| Parallel rounds with the same decision in all five languages | 18/30 stop, 6/30 ask |

Baseline on the same rows (the analyzer re-run on the collected facts): decision correct 0.30 alone, 0.70 with the stop rule; stops when it should 1 of 140.

### By language

| language | rows | correct |
|---|---|---|
| English | 40 | 0.85 (34/40) |
| Hindi | 40 | 0.93 (37/40) |
| Hinglish | 40 | 0.97 (39/40) |
| Kannada | 40 | 0.93 (37/40) |
| Tamil | 40 | 0.93 (37/40) |

### By round

| round | rows | correct |
|---|---|---|
| 1 | 65 | 0.89 (58/65) |
| 2 | 65 | 0.91 (59/65) |
| 3 | 65 | 0.95 (62/65) |
| 4 | 5 | 1 (5/5) |
