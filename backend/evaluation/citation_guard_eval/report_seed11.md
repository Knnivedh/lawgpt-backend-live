# Citation guard: perturbation benchmark

600 corpus documents sampled (seed 11), 6687 test sentences. No model calls.

A perturbed sentence counts as detected when the guard raises an issue of the expected kind. A clean sentence counts as a false alarm when the guard raises any issue.

## Detection (recall) by perturbation

| Perturbation | Sentences | Detected | Recall |
|---|---|---|---|
| section-swap | 1058 | 1058 | 100.0% |
| act-swap | 1043 | 1043 | 100.0% |
| pair-swap | 453 | 439 | 96.9% |
| case-insert | 1258 | 1258 | 100.0% |
| hindi-section-swap | 521 | 521 | 100.0% |
| hindi-act-swap | 521 | 521 | 100.0% |

## False alarms on unmodified sentences

| Set | Sentences | False alarms | Rate |
|---|---|---|---|
| clean | 1312 | 0 | 0.0% |
| hindi-clean | 521 | 0 | 0.0% |

False alarms by kind: none

## Overall

- Recall over all perturbed sentences: 4840/4854 = 99.7%
- Precision (detections on perturbed sentences vs false alarms on clean ones): 100.0%

## What this benchmark does and does not show

- Sentences are taken from the corpus documents themselves, so they are mostly English and closer to the sources than a model's paraphrased answer would be. Real model output is harder.
- Sentences were selected with the guard's own extractors (a sentence must contain something it recognises as a citation), so citations the extractors miss entirely are not counted.
- The Hindi rows are short templated sentences, not natural Hindi answers.
- It measures detection of unsupported citations, not whether the law is stated correctly.

## Examples of misses and false alarms

- MISS (pair-swap, changed to Code of Civil Procedure): Expert Pradeep Bharathipura: Hi, Your sister has to lodge the police complaint in the Singapore itself and if the Singapore police has not help her in the matter then she has to lodge the police complaint in India and al
- MISS (pair-swap, changed to Protection of Women from Domestic Violence Act): 4. Ask your lawyer to move an application u/s 125 Protection of Women from Domestic Violence Act and Domestic Violence Act (As his acts amount to economic abuse).
