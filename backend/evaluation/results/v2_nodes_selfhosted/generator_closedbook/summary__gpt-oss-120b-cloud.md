# generator_closedbook: evaluation on the version-2 dataset

- Dataset: `evaluation/generator_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `meta-llama/Llama-3.1-8B-Instruct` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 182; tokens in 68805, out 253789
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Mean share of the expected legal points covered | 0.11 |
| Answers making a listed wrong claim | 0.14 (27/200) |
| Answer in the expected language (judge) | 1 (200/200) |
| Hindi / Tamil / Kannada rows answered mostly in that script (code check) | 1 (120/120) |
| Answer addressed to the right person | 0.99 (198/200) |
| Answers naming at least one Act or section | 0.8 (160/200) |
| Answers where the citation guard removed a sentence | 0 (0/200) |
| Answers where the citation guard flagged a citation | 0 (0/200) |
| Answers cut off at the length limit | 0.5 (100/200) |
| Parallel cases with no wrong claim in all five languages | 22/30 |

Coverage is measured against the rubric, not against what was retrieved. The generator is told to use only retrieved material, so low coverage can come from retrieval; grounding against the retrieved text was not judged in this run.

### By language

| language | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| English | 40 | 0.23 | 0.1 (4/40) | 1 (40/40) | 1 (40/40) |
| Hindi | 40 | 0.11 | 0.15 (6/40) | 1 (40/40) | 1 (40/40) |
| Hinglish | 40 | 0.11 | 0.12 (5/40) | 1 (40/40) | 0.97 (39/40) |
| Kannada | 40 | 0.04 | 0.07 (3/40) | 1 (40/40) | 0.97 (39/40) |
| Tamil | 40 | 0.06 | 0.23 (9/40) | 1 (40/40) | 1 (40/40) |

### By whether the needed statute is in the knowledge base

| statute_in_corpus | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| no | 19 | 0.22 | 0.11 (2/19) | 1 (19/19) | 1 (19/19) |
| partly | 79 | 0.11 | 0.13 (10/79) | 1 (79/79) | 0.97 (77/79) |
| yes | 102 | 0.09 | 0.15 (15/102) | 1 (102/102) | 1 (102/102) |

### By user gender

| user_gender | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| female | 91 | 0.1 | 0.15 (14/91) | 1 (91/91) | 0.99 (90/91) |
| male | 84 | 0.14 | 0.14 (12/84) | 1 (84/84) | 0.99 (83/84) |
| unknown | 25 | 0.06 | 0.04 (1/25) | 1 (25/25) | 1 (25/25) |
