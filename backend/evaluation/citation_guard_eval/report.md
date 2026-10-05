# Citation guard: perturbation benchmark

600 corpus documents sampled (seed 7), 6645 test sentences. No model calls.

A perturbed sentence counts as detected when the guard raises an issue of the expected kind. A clean sentence counts as a false alarm when the guard raises any issue.

## Detection (recall) by perturbation

| Perturbation | Sentences | Detected | Recall |
|---|---|---|---|
| section-swap | 1063 | 1063 | 100.0% |
| act-swap | 1006 | 1006 | 100.0% |
| pair-swap | 438 | 427 | 97.5% |
| case-insert | 1239 | 1239 | 100.0% |
| hindi-section-swap | 534 | 534 | 100.0% |
| hindi-act-swap | 534 | 534 | 100.0% |

## False alarms on unmodified sentences

| Set | Sentences | False alarms | Rate |
|---|---|---|---|
| clean | 1297 | 0 | 0.0% |
| hindi-clean | 534 | 0 | 0.0% |

False alarms by kind: none

## Overall

- Recall over all perturbed sentences: 4803/4814 = 99.8%
- Precision (detections on perturbed sentences vs false alarms on clean ones): 100.0%

## What this benchmark does and does not show

- Sentences are taken from the corpus documents themselves, so they are mostly English and closer to the sources than a model's paraphrased answer would be. Real model output is harder.
- Sentences were selected with the guard's own extractors (a sentence must contain something it recognises as a citation), so citations the extractors miss entirely are not counted.
- The Hindi rows are short templated sentences, not natural Hindi answers.
- It measures detection of unsupported citations, not whether the law is stated correctly.

## Examples of misses and false alarms

- MISS (pair-swap, changed to Code of Civil Procedure): Although, my intention is to get the decree invalidated for getting out of Code of Civil Procedure u/s 376 case, I can give the reason to the family court that I want the court's opinion for deciding my future course of 
- MISS (pair-swap, changed to Code of Civil Procedure): 5. If a settlement is arrived accepting the divorce as per exparte divorce passed by US court, you will be in deep trouble in the charges under the provisions of section 376 Code of Civil Procedure.
