# Scenario bank (version 2 datasets)

One bank of realistic cases from which every node's version-2 golden dataset is
derived. Edit the bank, then rebuild:

    cd backend && python evaluation/scenario_bank/build_datasets.py

## Files

| File | Scenarios |
|---|---|
| `parallel_01_12.json`, `parallel_13_24.json` | P01-P24: legal scenarios, each written in all five languages |
| `parallel_25_30_and_analyzer_only.json` | P25-P30 (legal, five languages) and A01-A06 (analyzer-only: greeting, vague, off-topic, informational, privacy trap) |
| `specific_en_hi.json` | L-en-01..10, L-hi-01..10 (legal, one language each) and X-en-1..2, X-hi-1..2 (analyzer-only) |
| `specific_hien_ta_kn.json` | The same for Hinglish, Tamil and Kannada |
| `labels_retrieval.py` | Per legal scenario: relevant statute documents, relevant forum posts, the source post, and whether the needed statute is in the knowledge base |
| `pool_candidates.py`, `candidates.json` | The candidate posts that were read to make the retrieval labels (top 6 by BM25 + top 6 by vector search) |
| `followups.py` | One follow-up question and reply per legal scenario, with the expected extraction |
| `revalidation_rounds.py` | 25 conversations of 3-4 rounds: facts added each round and whether to stop asking |
| `rubrics_parallel.py`, `rubrics_specific.py` | Per legal scenario: points a good answer must cover, statutes, claims it must not make |
| `reasoning_pairs.py` | 25 scenarios: a reference answer plus related and unrelated past cases |
| `build_datasets.py` | Checks the bank and writes the six datasets |

Totals: 30 parallel legal + 6 parallel analyzer-only + 50 language-specific legal
+ 10 language-specific analyzer-only = 96 scenarios, 240 question texts.

## Where the scenarios come from

- **Real test conversations** in `backend/event_traces/` (P02-P05, A01, A03, X-hi-1,
  X-hi-2, and the voice style used in the `speech` rows: no punctuation, numbers
  spoken as words, recognition errors). Names were removed.
- **Forum posts in the corpus** (`data/family_law_domain/family_law.json`), sampled by
  topic. Each scenario was rewritten as a new chat message with changed facts; the
  `source` field names the post. The build script checks that no legal question
  shares more than 25% of its 6-word sequences with the corpus (highest is 21%),
  so a test question cannot retrieve its own source post by copying it.
- **Synthetic**, where neither source had a fitting case.

## Languages

`en` English, `hi` Hindi (Devanagari), `hi-en` Hinglish (Roman script), `ta` Tamil,
`kn` Kannada. Parallel scenarios state the same facts in all five. The
language-specific ones were written directly in that language and are not
translations.

## Scenario fields

| Field | Meaning |
|---|---|
| `id` | P = parallel legal, A = parallel analyzer-only, L-xx = language-specific legal, X-xx = language-specific analyzer-only |
| `topic`, `style`, `role`, `gender` | What it is about; how it is written (short, narrative, multi-issue, speech, noisy, vague, off-topic...); who is asking; the gender to select in the app |
| `source` | Trace, corpus post or synthetic |
| `query` | The user's first message, per language |
| `analyzer` | Labels for the query analyzer dataset (see `query_analyzer_eval/dataset_info_v2.txt`) |

The other layers are the `.py` files listed above, keyed by scenario `id`.

## What gets built

| Dataset (`golden_dataset_v2.csv` in) | Rows | Made of |
|---|---|---|
| `query_analyzer_eval/` | 200 | 24 legal + 6 analyzer-only scenarios x 5 languages; 8 legal + 2 analyzer-only per language |
| `retrieval_eval/` | 200 | 30 legal scenarios x 5 languages; 10 per language |
| `gather_info_eval/` | 200 | one follow-up exchange for each of the same 200 |
| `revalidate_eval/` | 200 | 10 conversations x 3 rounds x 5 languages; 10 rounds per language |
| `generator_eval/` | 200 | one answer rubric for each of the same 200 |
| `reasoning_eval/` | 200 | 10 scenarios x 3 past cases x 5 languages; 10 pairs per language |

Each folder's `dataset_info_v2.txt` explains its columns, how the labels were
made, how to score, and the limits. The version-1 files are untouched.

The build stops with an error if any scenario lacks a layer, a text is in the
wrong script, a document id is not in the corpus, a "related" past case is not
in that scenario's retrieval labels, or a dataset does not have exactly 200
unique rows.

## Review still needed

All text and labels were written by an AI assistant. Before results from these
sets are published:

- a lawyer should check the answer rubrics and reference answers (section
  numbers, case names, the BNS/BNSS equivalents);
- native speakers should read the Tamil and Kannada questions, replies and
  reference answers;
- someone should spot-check the retrieval labels against the full posts.

## Rule used for "must ask religion"

Religion is marked `must_ask` only where the answer depends on personal law:
grounds or procedure for divorce, annulment, validity of a marriage, succession,
adoption. For remedies under secular law (Domestic Violence Act, section 125
maintenance, 498A, evidence questions) it is listed as acceptable to ask, but
not required.

## Review needed before use

- **Tamil and Kannada** text was written by an AI assistant, not a native speaker.
- **Hindi and Hinglish** text should also be read by a native speaker, mainly for
  naturalness.
- **Labels** (what must or must not be asked) are judgement calls.
