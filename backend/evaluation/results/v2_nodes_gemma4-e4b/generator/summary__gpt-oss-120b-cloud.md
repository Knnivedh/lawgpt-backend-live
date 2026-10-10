# generator: evaluation on the version-2 dataset

- Dataset: `evaluation/generator_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `google/gemma-4-E4B-it` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 180; tokens in 1644424, out 88036
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Mean share of the expected legal points covered | 0.37 |
| Answers making a listed wrong claim | 0.06 (12/200) |
| Answer in the expected language (judge) | 0.98 (196/200) |
| Hindi / Tamil / Kannada rows answered mostly in that script (code check) | 1 (120/120) |
| Answer addressed to the right person | 0.98 (197/200) |
| Answers naming at least one Act or section | 0.88 (176/200) |
| Answers where the citation guard removed a sentence | 0.01 (1/200) |
| Answers where the citation guard flagged a citation | 0.01 (3/200) |
| Answers cut off at the length limit | 0 (0/200) |
| Parallel cases with no wrong claim in all five languages | 23/30 |

Coverage is measured against the rubric, not against what was retrieved. The generator is told to use only retrieved material, so low coverage can come from retrieval; grounding against the retrieved text was not judged in this run.

### By language

| language | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| English | 40 | 0.39 | 0.03 (1/40) | 1 (40/40) | 0.97 (39/40) |
| Hindi | 40 | 0.33 | 0.05 (2/40) | 1 (40/40) | 1 (40/40) |
| Hinglish | 40 | 0.35 | 0.05 (2/40) | 0.9 (36/40) | 0.97 (39/40) |
| Kannada | 40 | 0.36 | 0.1 (4/40) | 1 (40/40) | 1 (40/40) |
| Tamil | 40 | 0.39 | 0.07 (3/40) | 1 (40/40) | 0.97 (39/40) |

### By whether the needed statute is in the knowledge base

| statute_in_corpus | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| no | 19 | 0.33 | 0.05 (1/19) | 1 (19/19) | 1 (19/19) |
| partly | 79 | 0.35 | 0.08 (6/79) | 0.95 (75/79) | 1 (79/79) |
| yes | 102 | 0.39 | 0.05 (5/102) | 1 (102/102) | 0.97 (99/102) |

### By user gender

| user_gender | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| female | 91 | 0.4 | 0.01 (1/91) | 0.98 (89/91) | 1 (91/91) |
| male | 84 | 0.34 | 0.11 (9/84) | 0.98 (82/84) | 1 (84/84) |
| unknown | 25 | 0.33 | 0.08 (2/25) | 1 (25/25) | 0.88 (22/25) |
