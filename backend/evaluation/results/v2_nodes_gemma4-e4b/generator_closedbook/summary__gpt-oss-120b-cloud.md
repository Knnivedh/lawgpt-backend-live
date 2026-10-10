# generator_closedbook: evaluation on the version-2 dataset

- Dataset: `evaluation/generator_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `google/gemma-4-E4B-it` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 49518, out 220834
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Mean share of the expected legal points covered | 0.34 |
| Answers making a listed wrong claim | 0.09 (18/200) |
| Answer in the expected language (judge) | 0.96 (192/200) |
| Hindi / Tamil / Kannada rows answered mostly in that script (code check) | 1 (120/120) |
| Answer addressed to the right person | 1 (200/200) |
| Answers naming at least one Act or section | 0.97 (195/200) |
| Answers where the citation guard removed a sentence | 0 (0/200) |
| Answers where the citation guard flagged a citation | 0 (0/200) |
| Answers cut off at the length limit | 0 (0/200) |
| Parallel cases with no wrong claim in all five languages | 21/30 |

Coverage is measured against the rubric, not against what was retrieved. The generator is told to use only retrieved material, so low coverage can come from retrieval; grounding against the retrieved text was not judged in this run.

### By language

| language | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| English | 40 | 0.39 | 0.07 (3/40) | 1 (40/40) | 1 (40/40) |
| Hindi | 40 | 0.36 | 0.05 (2/40) | 1 (40/40) | 1 (40/40) |
| Hinglish | 40 | 0.34 | 0.1 (4/40) | 0.8 (32/40) | 1 (40/40) |
| Kannada | 40 | 0.28 | 0.1 (4/40) | 1 (40/40) | 1 (40/40) |
| Tamil | 40 | 0.33 | 0.12 (5/40) | 1 (40/40) | 1 (40/40) |

### By whether the needed statute is in the knowledge base

| statute_in_corpus | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| no | 19 | 0.41 | 0.05 (1/19) | 0.84 (16/19) | 1 (19/19) |
| partly | 79 | 0.34 | 0.08 (6/79) | 0.95 (75/79) | 1 (79/79) |
| yes | 102 | 0.33 | 0.11 (11/102) | 0.99 (101/102) | 1 (102/102) |

### By user gender

| user_gender | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| female | 91 | 0.35 | 0.02 (2/91) | 0.98 (89/91) | 1 (91/91) |
| male | 84 | 0.38 | 0.17 (14/84) | 0.94 (79/84) | 1 (84/84) |
| unknown | 25 | 0.18 | 0.08 (2/25) | 0.96 (24/25) | 1 (25/25) |
