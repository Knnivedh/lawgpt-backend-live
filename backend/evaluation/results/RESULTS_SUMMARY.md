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

