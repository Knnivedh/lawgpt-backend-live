# generator: evaluation on the version-2 dataset

- Dataset: `evaluation/generator_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `Qwen/Qwen3-8B` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 1856723, out 288052
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Mean share of the expected legal points covered | 0.2 |
| Answers making a listed wrong claim | 0.15 (30/200) |
| Answer in the expected language (judge) | 0.99 (198/200) |
| Hindi / Tamil / Kannada rows answered mostly in that script (code check) | 1 (120/120) |
| Answer addressed to the right person | 0.98 (196/200) |
| Answers naming at least one Act or section | 0.69 (137/200) |
| Answers where the citation guard removed a sentence | 0.06 (12/200) |
| Answers where the citation guard flagged a citation | 0.01 (2/200) |
| Answers cut off at the length limit | 0.31 (62/200) |
| Parallel cases with no wrong claim in all five languages | 16/30 |

Coverage is measured against the rubric, not against what was retrieved. The generator is told to use only retrieved material, so low coverage can come from retrieval; grounding against the retrieved text was not judged in this run.

### By language

| language | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| English | 40 | 0.46 | 0.07 (3/40) | 1 (40/40) | 1 (40/40) |
| Hindi | 40 | 0.21 | 0.1 (4/40) | 1 (40/40) | 1 (40/40) |
| Hinglish | 40 | 0.08 | 0.23 (9/40) | 0.95 (38/40) | 0.95 (38/40) |
| Kannada | 40 | 0.11 | 0.1 (4/40) | 1 (40/40) | 0.95 (38/40) |
| Tamil | 40 | 0.12 | 0.25 (10/40) | 1 (40/40) | 1 (40/40) |

### By whether the needed statute is in the knowledge base

| statute_in_corpus | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| no | 19 | 0.18 | 0.16 (3/19) | 1 (19/19) | 0.95 (18/19) |
| partly | 79 | 0.19 | 0.13 (10/79) | 0.99 (78/79) | 0.99 (78/79) |
| yes | 102 | 0.2 | 0.17 (17/102) | 0.99 (101/102) | 0.98 (100/102) |

### By user gender

| user_gender | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| female | 91 | 0.21 | 0.13 (12/91) | 1 (91/91) | 0.99 (90/91) |
| male | 84 | 0.21 | 0.18 (15/84) | 0.98 (82/84) | 0.99 (83/84) |
| unknown | 25 | 0.1 | 0.12 (3/25) | 1 (25/25) | 0.92 (23/25) |
