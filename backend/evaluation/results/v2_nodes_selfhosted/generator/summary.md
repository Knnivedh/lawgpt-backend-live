# generator: evaluation on the version-2 dataset

- Dataset: `evaluation/generator_eval/golden_dataset_v2.csv`; rows scored: 60 of 60
- System model: `meta-llama/Llama-3.1-8B-Instruct` served at http://localhost:8000/v1 | judge: `gemma4:31b-cloud` (Ollama)
- System calls so far: 99; tokens in 900274, out 130849
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Mean share of the expected legal points covered | 0.32 |
| Answers making a listed wrong claim | 0.22 (13/60) |
| Answer in the expected language (judge) | 1 (60/60) |
| Hindi / Tamil / Kannada rows answered mostly in that script (code check) | 1 (33/33) |
| Answer addressed to the right person | 0.97 (58/60) |
| Answers naming at least one Act or section | 0.75 (45/60) |
| Answers where the citation guard removed a sentence | 0.08 (5/60) |
| Answers where the citation guard flagged a citation | 0.03 (2/60) |
| Answers cut off at the length limit | 0.28 (17/60) |
| Parallel cases with no wrong claim in all five languages | - |

Coverage is measured against the rubric, not against what was retrieved. The generator is told to use only retrieved material, so low coverage can come from retrieval; grounding against the retrieved text was not judged in this run.

### By language

| language | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| English | 14 | 0.57 | 0.07 (1/14) | 1 (14/14) | 1 (14/14) |
| Hindi | 13 | 0.31 | 0.23 (3/13) | 1 (13/13) | 0.92 (12/13) |
| Hinglish | 13 | 0.29 | 0.31 (4/13) | 1 (13/13) | 1 (13/13) |
| Kannada | 10 | 0.3 | 0.2 (2/10) | 1 (10/10) | 0.9 (9/10) |
| Tamil | 10 | 0.03 | 0.3 (3/10) | 1 (10/10) | 1 (10/10) |

### By whether the needed statute is in the knowledge base

| statute_in_corpus | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| no | 6 | 0.25 | 0 (0/6) | 1 (6/6) | 1 (6/6) |
| partly | 24 | 0.31 | 0.29 (7/24) | 1 (24/24) | 1 (24/24) |
| yes | 30 | 0.34 | 0.2 (6/30) | 1 (30/30) | 0.93 (28/30) |

### By user gender

| user_gender | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| female | 28 | 0.37 | 0.21 (6/28) | 1 (28/28) | 1 (28/28) |
| male | 24 | 0.28 | 0.25 (6/24) | 1 (24/24) | 0.96 (23/24) |
| unknown | 8 | 0.25 | 0.12 (1/8) | 1 (8/8) | 0.88 (7/8) |
