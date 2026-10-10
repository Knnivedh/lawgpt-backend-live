# Saved results (as of 2026-10-04)

Results recorded so far, for later use in the paper and for comparison after
further changes. Code state: commit `0281fd4` plus uncommitted changes.

## 1. Retriever

- Test set: `evaluation/retrieval_eval/golden_dataset.csv` (36 questions: 27 English, 5 Hindi, 2 Hinglish, 2 Tamil).
- Harness: `evaluation/retrieval_eval/run_eval.py` (plain-code checks only, no judge model).
- Per-run reports: `evaluation/results/2026-10-04_0281fd4-dirty/retrieve/<label>/` (`summary.md`, `raw.jsonl`).
- Embedding model `bhavyagiri/InLegal-Sbert`; translation model `google/gemma-3-4b-it`, translation on in every run.

| Run label | Index | Keyword search | Query rewrite | Statute hit | Statute recall | Precedent hit | Precedent recall | Twin overlap |
|---|---|---|---|---|---|---|---|---|
| 0-before | old | off | off | 0.60 | 0.40 | 0.21 | 0.05 | 0.13 |
| 1-curation | old | off | off | 0.63 | 0.45 | 0.15 | 0.04 | 0.13 |
| 2-curation+hybrid | old | on | off | 0.80 | 0.57 | 0.33 | 0.09 | 0.18 |
| 3-rewrite-embed-both | old | off | on (embed both) | 0.60 | 0.37 | 0.12 | 0.03 | 0.25 |
| 4-rewrite-embed-search | old | off | on (embed search query) | 0.77 | 0.50 | 0.15 | 0.04 | 0.20 |
| 5-rewrite-embed-english | old | off | on (embed English) | 0.54 | 0.34 | 0.09 | 0.02 | 0.15 |
| 6-rewrite-both+hybrid | old | on | on (embed both) | 0.74 | 0.52 | 0.21 | 0.07 | 0.15 |
| 7-rewrite-search+hybrid | old | on | on (embed search query) | 0.77 | 0.57 | 0.21 | 0.08 | 0.25 |
| 8-rewrite-english+hybrid | old | on | on (embed English) | 0.71 | 0.51 | 0.15 | 0.04 | 0.14 |
| 9-app-defaults | old | on | off | 0.80 | 0.57 | 0.33 | 0.09 | 0.18 |
| 10-v2-index-vector-only | new (v2) | off | off | 0.60 | 0.35 | 0.36 | 0.10 | 0.04 |
| 11-v2-index-hybrid | new (v2) | on | off | 0.83 | 0.57 | 0.36 | 0.12 | 0.19 |

Column meanings: statute hit = questions with at least one gold statute returned;
statute recall = share of gold statutes returned, documents on the same subject
counted once; precedent hit / recall = the same for gold forum posts; twin overlap =
shared documents between the same question asked in two languages.

All runs from `1-curation` on have corpus curation on (8 off-topic documents skipped,
one document per subject) and the kinship rule in the translation prompt. `0-before`
has neither, but does include the earlier fixes (correct category names, search on the
original question, 5 distinct documents per search).

By language, keyword search on:

| | Old index (run 2) | New index (run 11) |
|---|---|---|
| English: statute hit | 0.88 | 0.85 |
| English: precedent hit | 0.29 | 0.33 |
| Hindi, Tamil, Hinglish: statute hit | 0.56 | 0.78 |
| Hindi, Tamil, Hinglish: precedent hit | 0.44 | 0.44 |

Index facts:

| | Old index (`indian_family_law_cases_hrag_test`) | New index (`indian_family_law_cases_hrag_v2`) |
|---|---|---|
| Records | 11,900 (incl. 64 chunks of 7 extra documents) | 16,714 |
| Child chunks | 8,829 from source files | 13,707 (3,578 question, 10,129 answer) |
| Text embedded per chunk | "Query: question / Answer: chunk" | title + chunk |
| Chunks over the model's 512-token input | 11% embedded as the question only | 0 |
| Chunks sharing an identical vector | 1,222 | not measured |
| Chunks not contained in their parent's text | 1,114 (13%) | 167 (1.2%) |

Caveats to carry into any write-up:
- 36 questions; a difference of one question is about 3 points. Treat gaps under ~10 points as noise.
- Gold precedent lists are short (3-5 posts, chosen by title search), so precedent figures are lower bounds, and keyword search is favoured by how the lists were built.
- Non-English rows: 9 questions only.
- The 7 reference documents are not in the new index.
- Not measured: relevance judged by a model or a person.

## 2. Citation guard

- Code: `citation_guard.py` (modes `strict`, `mixed`, `flag`).
- Benchmark: `evaluation/citation_guard_eval/run_benchmark.py`; reports `report.md` (seed 7) and `report_seed11.md`.
- Method: citing sentences from 600 corpus documents, kept unchanged or corrupted in a known way. No model calls.

Seed 11 (sample not used while fixing the pair logic):

| Test | Sentences | Detected |
|---|---|---|
| Section changed to one not in the document | 1,058 | 100% |
| Act changed to one not in the document | 1,043 | 100% |
| Section kept, act swapped for another act in the document | 453 | 96.9% |
| Invented case name added | 1,258 | 100% |
| Templated Hindi, section changed | 521 | 100% |
| Templated Hindi, act changed | 521 | 100% |
| Unchanged sentences wrongly flagged (English + Hindi) | 1,833 | 0 |

Seed 7: wrong-act detection was 77.2% before the pair-logic fixes and 97.5% after;
one false alarm before, none after.

Caveats:
- The 100% rows are easy by construction (the changed item appears nowhere in the document).
- Sentences come from the corpus, mostly English, worded like the sources. Hindi rows are templates.
- The pair logic was improved after the first run on seed 7; seed 11 is the clean number.
- Not measured: precision and recall on real generated answers with human labels.

## 3. Unit tests

33 passing: `test/test_citation_guard.py` (18), `test/test_keyword_search.py` (11),
`test/test_context_window.py` (4).

## 4. Retriever on the version-2 test set (2026-10-05)

- Test set: `evaluation/retrieval_eval/golden_dataset_v2.csv` (200 questions, 40 each in English, Hindi, Hinglish, Tamil, Kannada). Labels not yet reviewed by a person, so these numbers are provisional.
- Translation model: `gemma4:31b-cloud` through Ollama (not the `google/gemma-3-4b-it` used in section 1). Keyword search on, corpus curation on, query rewrite off.
- Query embeddings computed locally with `bhavyagiri/InLegal-Sbert`; no Hugging Face credit used.
- Reports: `evaluation/results/2026-10-04_0281fd4-dirty/retrieve/v2set-31b-newindex/` and `evaluation/results/2026-10-05_0281fd4-dirty/retrieve/v2set-31b-oldindex/`.
- Not comparable with section 1: different questions and different gold labels.

| | Old index | New index (v2) |
|---|---|---|
| Statute hit | 0.65 | 0.59 |
| Statute recall | 0.36 | 0.32 |
| Precedent hit | 0.47 | 0.52 |
| Precedent recall | 0.14 | 0.16 |
| Source post found | 0.22 | 0.25 |

By language (statute hit / precedent hit):

| Language | Old index | New index (v2) |
|---|---|---|
| English | 0.64 / 0.60 | 0.64 / 0.62 |
| Hindi | 0.68 / 0.47 | 0.53 / 0.53 |
| Hinglish | 0.69 / 0.42 | 0.64 / 0.45 |
| Tamil | 0.55 / 0.45 | 0.58 / 0.50 |
| Kannada | 0.68 / 0.40 | 0.55 / 0.50 |

Same question in five languages (30 parallel cases, new index): a gold precedent was returned in all five languages for 11 cases and in at least one language for 23. Retrieved precedents overlap with the English row's by 0.26 to 0.32 (Jaccard), so translation changes which posts come back even when a relevant one is still found.

Not yet run: the same test with the Gemma 3 4B translation model (needs Hugging Face credit), which is needed before saying the 31B model is better.

## 5. Retriever after weighting keyword search and returning 5 statutes (2026-10-05)

Same 200-question set and translation model as section 4. Changes: language detection made repeatable and Hinglish always translated; number of statutes returned raised from 3 to 5; keyword ranking weighted against the vector ranking. Reports: `evaluation/results/2026-10-05_0281fd4-dirty/retrieve/f-*`.

| Setting | Index | Statute hit | Statute recall | Precedent hit | Precedent recall |
|---|---|---|---|---|---|
| 3 statutes, equal weights (before) | old | 0.66 | 0.36 | 0.48 | 0.14 |
| 5 statutes, equal weights | old | 0.78 | 0.49 | 0.48 | 0.14 |
| 5 statutes, keyword x2 (new default) | old | 0.78 | 0.49 | 0.58 | 0.20 |
| 5 statutes, keyword x3 | old | 0.78 | 0.49 | 0.58 | 0.20 |
| 5 statutes, keyword only | old | 0.70 | 0.45 | 0.56 | 0.18 |
| 3 statutes, equal weights (before) | new (v2) | 0.59 | 0.32 | 0.53 | 0.17 |
| 5 statutes, keyword x2 | new (v2) | 0.69 | 0.44 | 0.59 | 0.21 |
| 5 statutes, keyword x3 | new (v2) | 0.68 | 0.44 | 0.59 | 0.21 |
| 5 statutes, keyword only | new (v2) | 0.70 | 0.45 | 0.56 | 0.19 |

The weight was chosen on this same test set, so the gain is somewhat optimistic until checked on other questions.

Offline experiments (no API calls; `evaluation/results/v2_retrieval_models/`): adding collected facts to the search text lowers vector-search hits (cases 0.32 to 0.18) and raises keyword statute hits (top 3: 0.68 to about 0.8); searching at every follow-up turn and merging gives no gain for hybrid search.

## 6. Embedding model and reranker comparison (2026-10-05)

Same 200-question set. Translation `gemma4:31b-cloud`, 5 statutes returned, corpus curation on.

Measured in the app (reports: `evaluation/results/2026-10-05_0281fd4-dirty/retrieve/bge-small-*`), collection `indian_family_law_cases_bge_small` (v2 chunks embedded with `BAAI/bge-small-en-v1.5`, 384 dimensions, query prefix "Represent this sentence for searching relevant passages: "):

| Setting | Statute hit | Statute recall | Precedent hit | Precedent recall |
|---|---|---|---|---|
| InLegal-SBERT, old index, keyword x2 (section 5) | 0.78 | 0.49 | 0.58 | 0.20 |
| bge-small, keyword x2 | 0.86 | 0.58 | 0.59 | 0.20 |
| bge-small, equal weights | 0.88 | 0.58 | 0.57 | 0.19 |
| bge-small, vector search only | 0.85 | 0.57 | 0.47 | 0.17 |

bge-small, keyword x2, by language (statute / precedent hit): English 0.89 / 0.70, Hindi 0.84 / 0.57, Hinglish 0.89 / 0.57, Tamil 0.84 / 0.45, Kannada 0.84 / 0.65. Statute hit is 0.95 on questions whose statute is fully in the knowledge base and 0.73 where it is only partly there.

Measured offline (`evaluation/retrieval_eval/compare_models_offline.py`, results in `evaluation/results/v2_retrieval_models/`), vector + keyword x2, top-3 / top-5 statutes and top-5 precedents: InLegal-SBERT 0.63 / 0.70 / 0.58; bge-small-en-v1.5 0.81 / 0.87 / 0.60; multilingual-e5-base 0.81 / 0.85 / 0.63 (untranslated questions: 0.78 / 0.83 / 0.61). Rerankers over InLegal-SBERT + keyword candidates gave no gain: ms-marco-MiniLM-L-6-v2 0.58 / 0.66 / 0.60; mmarco-mMiniLMv2-L12 0.41 / 0.52 / 0.49; bge-reranker-base 0.63 / 0.70 / 0.58. bge-m3 and bge-reranker-v2-m3 could not be run on the 8 GB machine.

Gold labels were pooled from keyword search and InLegal-SBERT, so precedent scores for other models are lower bounds.

Rerankers over bge-small-en-v1.5 + keyword candidates (offline; top-3 / top-5 statutes, top-5 precedents): no reranker 0.81 / 0.87 / 0.60; ms-marco-MiniLM-L-6-v2 0.55 / 0.66 / 0.59; bge-reranker-base 0.67 / 0.77 / 0.59. Both rerankers lower statute hits and leave precedents unchanged.

## 7. All five LLM nodes on the version-2 sets (2026-10-09/10)

- Node model: `meta-llama/Llama-3.1-8B-Instruct`, self-hosted with vLLM 0.31.0 (not through Hugging Face). Judge: `gpt-oss:120b-cloud` via Ollama. One run, no repeats. Settings and dataset hashes: `evaluation/results/v2_nodes_selfhosted/run_config.json`; per-node reports: `summary__gpt-oss-120b-cloud.md` in each node folder.
- Datasets and judge unreviewed; numbers provisional. The gatherer and revalidation sets no longer contain unanswered questions (replaced 2026-10-09).

| Node | Main measure | Result |
|---|---|---|
| Information gatherer | extraction correct | 0.71 (rambling replies 0.35; short 0.86) |
| Query analyzer | routes correctly / intent correct | 0.92 / 0.90 |
| Query analyzer | all stated facts captured | 0.40 |
| Query analyzer | rows with no out-of-scope question / rows asking private details | 0.02 / 0.20 |
| Query analyzer | off-topic messages recognised | 0 of 14 |
| Revalidation | decision correct, model alone / with the code's stop rule | 0.30 / 0.70 |
| Revalidation | stops when it should, model alone | 1 of 140 |
| Generator | expected legal points covered (mean) | 0.13 (English 0.32, Hindi 0.14, Hinglish 0.08, Kannada 0.06, Tamil 0.05) |
| Generator | answers making a listed wrong claim | 0.14 (English 0.05, Tamil 0.23) |
| Generator | right language / right addressee | 0.99 / 0.95 |
| Generator | answers cut off at the length limit | 0.41 (Tamil 30 of 40, Kannada 27 of 40, English 0) |
| Reasoning panel | related cases scored high / unrelated scored low | 1.00 / 0.60 |
| Reasoning panel | unrelated case said to have shaped the answer | 0.91 |
| Reasoning panel | quoted excerpt not found in the source | 0.47 |

Generator retrieval used `gemma4:31b-cloud` translations, not production's `google/gemma-3-4b-it`.

## 8. Two follow-up experiments with Llama 3.1 8B (2026-10-10)

Same self-hosted model and run folder as section 7 (`evaluation/results/v2_nodes_selfhosted/`).

**Stop decision** (`stop_generic`, `stop_policy`, `stop_twostep`; 200 revalidation rows, scored in code):

| Method | Decision correct | Stops when it should | Asks when it should |
|---|---|---|---|
| Current: analyzer re-run, model alone | 0.30 | 1/140 | 59/60 |
| Current, with the hard stop rule in graph.py | 0.70 | 82/140 | 58/60 |
| Plain yes/no question to the model | 0.43 | 39/140 | 47/60 |
| Yes/no with the policy written in the prompt | 0.59 | 108/140 | 10/60 |
| Two steps: model classifies whether the law depends on religion; code decides | 0.92 | 129/140 | 55/60 |

The two-step rule and the dataset labels follow the same policy (religion is the only essential fact, and only for divorce, restitution, validity of marriage, inheritance and adoption), so 0.92 measures how reliably the method applies that policy. Not built into the app.

**Generator with and without retrieval** (`generator_closedbook`: same question, facts, gender and language instruction; no documents, no citation guard; same rubric and judge, `gpt-oss:120b-cloud`):

| | Full pipeline | Llama alone |
|---|---|---|
| Expected legal points covered (mean) | 0.13 | 0.11 |
| English only | 0.32 | 0.23 |
| Hindi / Hinglish / Tamil / Kannada | 0.14 / 0.08 / 0.05 / 0.06 | 0.11 / 0.11 / 0.06 / 0.04 |
| Answers with a listed wrong claim | 0.14 | 0.14 |
| English only | 0.05 | 0.10 |
| Names an Act or section | 0.63 | 0.80 |
| Cut off at the length limit | 0.41 | 0.50 |
| Right addressee | 0.95 | 0.99 |

Row by row, the pipeline covered more in 50 cases, less in 40, the same in 110.

## 9. Model comparison on the five nodes (2026-10-10)

Each model served with vLLM 0.31.0 on one L40 and dropped into the unchanged pipeline (same prompts, token limits, temperatures). Judge `gpt-oss:120b-cloud`. The generator rows use the same retrieved documents for every model (copied from the Llama run). One run per model. Folders: `v2_nodes_selfhosted` (Llama), `v2_nodes_gemma4-e4b` (Gemma).

| Measure | Llama 3.1 8B | Gemma 4 E4B |
|---|---|---|
| Gatherer: extraction correct | 0.71 | 0.68 |
| Analyzer: routes correctly / intent correct | 0.92 / 0.90 | 0.93 / 0.99 |
| Analyzer: intent correct, Tamil / Kannada | 0.82 / 0.82 | 1.00 / 1.00 |
| Analyzer: all stated facts captured | 0.40 | 0.40 |
| Analyzer: must-ask field asked | 0.86 | 1.00 |
| Analyzer: rows with no out-of-scope question | 0.02 | 0.12 |
| Analyzer: rows asking for private details | 0.20 | 0.00 |
| Analyzer: off-topic messages recognised | 0/14 | 0/14 |
| Revalidation: stops when it should (model alone) | 1/140 | 0/140 |
| Revalidation: decision correct with the code's stop rule | 0.70 | 0.70 |
| Revalidation: rows asking private details, when asking | 0.37 | 0.01 |
| Generator: expected legal points covered | 0.13 | 0.37 |
| Generator: English / Hindi / Hinglish / Tamil / Kannada | 0.32 / 0.14 / 0.08 / 0.05 / 0.06 | 0.39 / 0.33 / 0.35 / 0.39 / 0.36 |
| Generator: answers with a listed wrong claim | 0.14 | 0.06 |
| Generator: answers cut off at the length limit | 0.41 | 0.00 |
| Generator: names an Act or section | 0.63 | 0.88 |
| Generator: right language / right addressee | 0.99 / 0.95 | 0.98 / 0.98 |
| Reasoning: related past cases scored high | 130/130 | 72/130 |
| Reasoning: unrelated past cases scored low | 42/70 | 70/70 |
| Reasoning: unrelated case said to have shaped the answer | 64/70 | 6/70 |
| Reasoning: quoted excerpt not found in the source | 0.47 | 0.35 |

### Qwen 3 8B added (2026-10-10)

Run folder `v2_nodes_qwen3-8b`; thinking switched off (`--no-thinking`); otherwise as section 9.

| Measure | Llama 3.1 8B | Gemma 4 E4B | Qwen 3 8B |
|---|---|---|---|
| Gatherer: extraction correct | 0.71 | 0.68 | 0.73 |
| Gatherer: on rambling replies | 0.35 | 0.25 | 0.55 |
| Analyzer: routes correctly / intent correct | 0.92 / 0.90 | 0.93 / 0.99 | 0.92 / 0.96 |
| Analyzer: all stated facts captured | 0.40 | 0.40 | 0.34 |
| Analyzer: rows asking for private details | 0.20 | 0.00 | 0.17 |
| Analyzer: off-topic messages recognised | 0/14 | 0/14 | 0/14 |
| Revalidation: stops when it should (model alone) | 1/140 | 0/140 | 46/140 |
| Revalidation: decision correct, model alone / with stop rule | 0.30 / 0.70 | 0.30 / 0.70 | 0.52 / 0.77 |
| Generator: expected legal points covered | 0.13 | 0.37 | 0.2 |
| Generator: coverage, English / Hindi / Hinglish / Tamil / Kannada | 0.32 / 0.14 / 0.08 / 0.05 / 0.06 | 0.39 / 0.33 / 0.35 / 0.39 / 0.36 | 0.46 / 0.21 / 0.08 / 0.12 / 0.11 |
| Generator: answers with a listed wrong claim | 0.14 | 0.06 | 0.15 |
| Generator: cut off at the length limit | 0.41 | 0 | 0.31 |
| Generator: names an Act or section | 0.63 | 0.88 | 0.69 |
| Generator: right language / right addressee | 0.99 / 0.95 | 0.98 / 0.98 | 0.99 / 0.98 |
| Reasoning: related past cases scored high | 130/130 | 72/130 | 120/130 |
| Reasoning: unrelated past cases scored low | 42/70 | 70/70 | 69/70 |
| Reasoning: unrelated case said to have shaped the answer | 64/70 | 6/70 | 11/70 |

### Follow-up experiments with Gemma 4 E4B (2026-10-10)

**Stop decision** (200 revalidation rows): analyzer re-run 0.30 correct (stops 0/140); plain yes/no 0.66 (stops 120/140, asks 12/60); yes/no with the policy in the prompt 0.68 (stops 136/140, asks 0/60); two-step (model classifies, code decides) 0.99 (stops 140/140, asks 59/60). With Llama the two-step method scored 0.92.

**Generator with and without retrieval** (same rubric and judge):

| | Gemma, full pipeline | Gemma alone | Llama, full pipeline | Llama alone |
|---|---|---|---|---|
| Expected legal points covered | 0.37 | 0.34 | 0.13 | 0.11 |
| English / Hindi / Hinglish / Tamil / Kannada | 0.39 / 0.33 / 0.35 / 0.39 / 0.36 | 0.39 / 0.36 / 0.34 / 0.33 / 0.28 | 0.32 / 0.14 / 0.08 / 0.05 / 0.06 | 0.23 / 0.11 / 0.11 / 0.06 / 0.04 |
| Answers with a listed wrong claim | 0.06 | 0.09 | 0.14 | 0.14 |
| Statute in knowledge base: coverage / wrong claim | 0.39 / 0.05 | 0.33 / 0.11 | 0.13 / 0.12 | 0.09 / 0.15 |
| Statute not in knowledge base: coverage | 0.33 | 0.41 | 0.17 | 0.22 |
| Names an Act or section | 0.88 | 0.97 | 0.63 | 0.80 |

Row by row with Gemma, the pipeline covered more in 69 cases, less in 49, the same in 82.

### Reasoning panel: accuracy of explanations for related past cases (2026-10-10)

`evaluation/judge_reasoning_faithfulness.py`; judge `gpt-oss:120b-cloud`; 130 related pairs per model (129 for Llama, one unreadable output). "Accurate" = every statement about the past case is supported by the text the panel was shown (strict: one unsupported statement fails the row).

| | Llama 3.1 8B | Gemma 4 E4B | Qwen 3 8B |
|---|---|---|---|
| Explanation fully accurate | 15/129 | 75/130 | 27/130 |
| Unsupported statements per explanation (mean) | 1.81 | 0.64 | 1.38 |
| Names at least one specific similarity | 103/129 | 71/130 | 112/130 |

### Four-model table (2026-10-10)

Ministral 8B run folder: `v2_nodes_ministral-8b` (served with `--tokenizer-mode mistral --config-format mistral --load-format mistral`). All four models have about 8 billion parameters. All 200 rows per node are scored for every model.

| Measure | Llama 3.1 8B | Gemma 4 E4B | Qwen 3 8B | Ministral 8B |
|---|---|---|---|---|
| Gatherer: extraction correct | 0.71 | 0.68 | 0.73 | 0.60 |
| Gatherer: on rambling replies | 0.35 | 0.25 | 0.55 | 0.15 |
| Analyzer: routes correctly / intent correct | 0.92 / 0.90 | 0.93 / 0.99 | 0.92 / 0.96 | 0.90 / 0.92 |
| Analyzer: all stated facts captured | 0.40 | 0.40 | 0.34 | 0.27 |
| Analyzer: must-ask field asked | 0.86 | 1.00 | 1.00 | 0.70 |
| Analyzer: rows asking for private details | 0.20 | 0.00 | 0.17 | 0.20 |
| Analyzer: off-topic messages recognised | 0/14 | 0/14 | 0/14 | 0/14 |
| Revalidation: stops when it should (model alone) | 1/140 | 0/140 | 46/140 | 48/140 |
| Revalidation: asks more when it should | 59/60 | 60/60 | 58/60 | 46/60 |
| Generator: expected legal points covered | 0.13 | 0.37 | 0.20 | 0.20 |
| Generator: English / Hindi / Hinglish / Tamil / Kannada | 0.32 / 0.14 / 0.08 / 0.05 / 0.06 | 0.39 / 0.33 / 0.35 / 0.39 / 0.36 | 0.46 / 0.21 / 0.08 / 0.12 / 0.11 | 0.32 / 0.19 / 0.27 / 0.19 / 0.03 |
| Generator: answers with a listed wrong claim | 0.14 | 0.06 | 0.15 | 0.10 |
| Generator: cut off at the length limit | 0.41 | 0.00 | 0.31 | 0.40 |
| Generator: right language / right addressee | 0.99 / 0.95 | 0.98 / 0.98 | 0.99 / 0.98 | 0.96 / 0.93 |
| Reasoning: related past cases scored high | 130/130 | 72/130 | 120/130 | 130/130 |
| Reasoning: unrelated past cases scored low | 42/70 | 70/70 | 69/70 | 15/70 |
| Reasoning: unrelated case said to have shaped the answer | 64/70 | 6/70 | 11/70 | 57/70 |

