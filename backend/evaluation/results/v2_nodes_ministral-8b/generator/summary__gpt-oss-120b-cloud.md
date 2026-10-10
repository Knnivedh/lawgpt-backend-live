# generator: evaluation on the version-2 dataset

- Dataset: `evaluation/generator_eval/golden_dataset_v2.csv`; rows scored: 200 of 200
- System model: `mistralai/Ministral-8B-Instruct-2410` served at http://localhost:8000/v1 | judge: `gpt-oss:120b-cloud` (Ollama)
- System calls so far: 200; tokens in 1886389, out 217550
- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional.

| Metric | Value |
|---|---|
| Mean share of the expected legal points covered | 0.2 |
| Answers making a listed wrong claim | 0.1 (21/200) |
| Answer in the expected language (judge) | 0.96 (192/200) |
| Hindi / Tamil / Kannada rows answered mostly in that script (code check) | 0.76 (91/120) |
| Answer addressed to the right person | 0.93 (185/200) |
| Answers naming at least one Act or section | 0.66 (132/200) |
| Answers where the citation guard removed a sentence | 0.08 (16/200) |
| Answers where the citation guard flagged a citation | 0.05 (10/200) |
| Answers cut off at the length limit | 0.4 (80/200) |
| Parallel cases with no wrong claim in all five languages | 20/30 |

Coverage is measured against the rubric, not against what was retrieved. The generator is told to use only retrieved material, so low coverage can come from retrieval; grounding against the retrieved text was not judged in this run.

### By language

| language | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| English | 40 | 0.32 | 0.1 (4/40) | 1 (40/40) | 1 (40/40) |
| Hindi | 40 | 0.19 | 0.1 (4/40) | 0.97 (39/40) | 1 (40/40) |
| Hinglish | 40 | 0.27 | 0.15 (6/40) | 1 (40/40) | 0.93 (37/40) |
| Kannada | 40 | 0.03 | 0.07 (3/40) | 1 (40/40) | 0.78 (31/40) |
| Tamil | 40 | 0.19 | 0.1 (4/40) | 0.82 (33/40) | 0.93 (37/40) |

### By whether the needed statute is in the knowledge base

| statute_in_corpus | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| no | 19 | 0.2 | 0.11 (2/19) | 1 (19/19) | 1 (19/19) |
| partly | 79 | 0.2 | 0.08 (6/79) | 0.96 (76/79) | 0.91 (72/79) |
| yes | 102 | 0.2 | 0.13 (13/102) | 0.95 (97/102) | 0.92 (94/102) |

### By user gender

| user_gender | rows | coverage | wrong claim | language ok | addressee ok |
|---|---|---|---|---|---|
| female | 91 | 0.2 | 0.09 (8/91) | 0.95 (86/91) | 0.91 (83/91) |
| male | 84 | 0.19 | 0.12 (10/84) | 0.98 (82/84) | 0.93 (78/84) |
| unknown | 25 | 0.22 | 0.12 (3/25) | 0.96 (24/25) | 0.96 (24/25) |
