# Evaluation Process — Family Law Assistant (LangGraph nodes)

This folder holds the golden datasets for every node in the LangGraph graph
that needs evaluating, and this document describes how each one will be
evaluated: what is run, what is captured, how it is scored, and how results
are reported and used.

---

## 1. What is being evaluated

The graph (`graph.py`) has 8 nodes. Six of them are evaluated; two are pure
formatters with nothing to measure.

| Node | Code under test | Dataset | Rows |
|---|---|---|---|
| `analyze_query` | `QueryAnalyzer.analyze_query()` on a fresh message | `query_analyzer_eval/` | 42 |
| `gather_info` | `InformationGatherer._extract_information()` | `gather_info_eval/` | 70 |
| `revalidate` | `QueryAnalyzer.analyze_query()` on the synthetic "root query + My Information" message built in `revalidate_information_node` | `revalidate_eval/` | 29 |
| `retrieve` | `retrieve_documents()` | `retrieval_eval/` | 36 |
| `generate` | `generate_response()` | `generator_eval/` | 30 |
| `analyze_reasoning` | `DynamicReasoningExplainer.analyze_precedent_usage()` | `reasoning_eval/` | 31 |
| `clarify`, `ask_question` | dict formatters | — (not evaluated) | — |

Each node is evaluated **in isolation**: it gets fixed inputs from its
dataset, never the live output of the node before it. A failure therefore
points at that node, not at something upstream. (An optional end-to-end run
is described in section 8.)

---

## 2. Folder layout

```
evaluation/
  EVALUATION_PROCESS.md          <- this file
  query_analyzer_eval/           golden_dataset.csv, generate_dataset.py, dataset_info.txt
  gather_info_eval/              (same three files)
  revalidate_eval/
  retrieval_eval/
  generator_eval/
  reasoning_eval/
  results/                       (created by the harness, one folder per run)
    <YYYY-MM-DD>_<git-short-sha>/
      run_config.json            models, temperatures, judge, flags, dataset hashes
      <node>/raw.jsonl           exact inputs + outputs of the node, one line per row/repeat
      <node>/judged.jsonl        judge verdicts per row
      <node>/summary.md          metrics tables for this node
      SUMMARY.md                 one-page roll-up across nodes
```

`dataset_info.txt` in each folder explains that dataset's columns and
categories in detail. This document covers the process.

### Version 2 datasets (200 rows per node, five languages)

Each node folder also holds `golden_dataset_v2.csv` and `dataset_info_v2.txt`.
All six are built from one shared set of cases in `scenario_bank/` by
`scenario_bank/build_datasets.py` (see `scenario_bank/README.md`): 150 rows
are the same cases written in English, Hindi, Hinglish, Tamil and Kannada, and
50 are written natively, 10 per language. Because the cases are shared, a
result can be followed for one case through every node, and compared across
languages with the facts held constant.

The procedure in section 6 applies to both versions. Use version 1 for quick
regression checks (it is small and partly built from manual-test failures)
and version 2 for the reported numbers. For version 2, also report every
metric by language and, on the parallel rows, per-case agreement across the
five languages. The version-2 sets still need the review in Stage 0; until
then their numbers are provisional.

---

## 3. Order of work

Evaluate in this order. It follows the pipeline and puts first the nodes
behind the bugs already seen in manual testing:

1. **`gather_info`**: repeated / reworded questions
2. **`analyze_query`**: re-asking facts the user already gave
3. **`revalidate`**: unbounded follow-up questions (scope creep)
4. **`retrieve`**: irrelevant precedents (re-measure after the category and
   query-construction fixes)
5. **`generate`**: hallucinated sections, missing key law, wrong language/role
6. **`analyze_reasoning`**: over-claiming that unrelated precedents mattered

---

## 4. Lifecycle of an evaluation run

### Stage 0 — Human review of the datasets
Before any scoring, a reviewer checks every golden dataset:
- Are the rows realistic? Would a real user write this?
- Are the expected values correct? Edit them in the CSV directly.
- The `generator_eval` and `reasoning_eval` legal content must be reviewed
  by someone with Indian family-law knowledge. It was written by an AI
  assistant and has not been verified.
- Decide the IPC→BNS / CrPC→BNSS policy (new codes in force since 1 July
  2024): accept either numbering, or require the new one.

Edits are made to the CSVs. After review, do **not** re-run
`generate_dataset.py`: it would overwrite the reviewed CSV. Either copy the
edits back into the script, or treat the reviewed CSV as the source of truth
from then on.

### Stage 1 — Freeze the dataset version
Record a hash of each `golden_dataset.csv` in `run_config.json` for every
run. Two runs are only comparable when their dataset hashes match.

### Stage 2 — Run the node (collect raw outputs)
A harness script per node reads the CSV, calls the node exactly as described
in section 6, and writes every input and output to `raw.jsonl`. No scoring
happens here, so outputs can be re-judged later with a better judge without
paying to re-run the system.

Repeats: the LLM nodes run at non-zero temperature (analyzer 0.15, gatherer
0.1, generator 0.3, explainer 0.3), so **run each row 3 times** for
`analyze_query`, `gather_info` and `revalidate`, and report the majority
result plus a consistency rate (share of rows where all 3 runs agree).
Generator and explainer rows run once by default, because they are more
expensive and judged on graded scores rather than pass/fail.

### Stage 3 — Score
Two kinds of checks, always kept separate in the results:
- **Deterministic checks**: plain code, no model, e.g. "is `NOT_PROVIDED`
  returned exactly", "is gold parent_id 2930 in the results", "does
  `key_excerpt` appear verbatim in the precedent".
- **LLM-as-judge checks**: a large model compares the output with the
  expected value or rubric for anything semantic (paraphrased extractions,
  answer coverage, relevance).

### Stage 4 — Aggregate and report
Per node: overall pass rate, pass rate **per category/topic/language**, and a
list of the failing rows with the judge's reason. The per-category breakdown
matters more than the overall number, because it shows which failure mode
is actually happening.

### Stage 5 — Baseline and regression
The first full run on the current code is the **baseline**. Every later
change (prompt edit, model swap, retrieval fix) gets a new run with the same
dataset hashes, compared row by row against the baseline. Report
improvements, regressions, and rows that flipped either way.

---

## 5. Common setup

### 5.1 System under test
- Same models and settings as production: `LLM_MODEL` (Llama 3.1 8B),
  `TRANSLATION_MODEL` (Gemma 3 4B), `ENABLE_QUERY_TRANSLATION` as deployed,
  and the same Milvus collection.
- Record all of these in `run_config.json`, plus the git commit.

### 5.2 The judge
- Use a **large model from a different family** than the system under test.
  A model judging its own family's output tends to be lenient. Do not use
  Llama 3.1 8B as the judge.
- Temperature 0, and require JSON output:
  `{"verdict": "pass"|"fail"|"partial", "score": 0-1, "reason": "..."}`.
- The judge gets only what it needs: the input, the system's output, the
  expected value or rubric, and (for the generator) the frozen retrieved
  context. Keep the judge prompt fixed across runs and store it with the
  results.
- **Validate the judge**: on the first run, a human independently grades a
  random ~15% of judged rows. If human–judge agreement is below about 85%,
  fix the judge prompt before trusting its numbers.

### 5.3 Cost and credits
All system calls share the same Hugging Face credit pool as production
(the pool ran out once during testing). Approximate calls per full run:

| Node | System calls | Judge calls |
|---|---|---|
| analyze_query | 42 × 3 = 126 | ~126 (can batch the 3 repeats into one judge call: 42) |
| gather_info | 70 × 3 = 210 | 70–210 |
| revalidate | 29 × 3 = 87 | ~87 |
| retrieve | 36 embeddings (+ ~9 Gemma translations for non-English rows) | 36 (one judge call scores all chunks of a row) |
| generate | 30 retrievals (once, then frozen) + 30 generations | 30 |
| analyze_reasoning | 31 | 31 |

Roughly **550 system calls and 250–500 judge calls** per full run. Check the
credit balance first, and run one node at a time when credits are low.

### 5.4 Privacy
Datasets contain no real user data. The 7 unexplained documents in Milvus
(real names and addresses, no parent record) can still appear in retrieval
output, so **do not publish raw `retrieve`/`generate` outputs outside the
team** without checking for them.

---

## 6. Per-node procedure

### 6.1 `gather_info`: answer extraction
**Tests:** does the gatherer correctly pull the answer out of the user's
reply, and return `NOT_PROVIDED` only when there genuinely is no answer?

**Call:**
```python
from nodes.information_gatherer import InformationGatherer
g = InformationGatherer()
out = g._extract_information(last_question=row.last_question,
                             user_response=row.user_response,
                             info_target=row.field)
```

**Deterministic checks**
- `NOT_PROVIDED` rows: output must be exactly `NOT_PROVIDED`.
- All other rows: output must NOT be `NOT_PROVIDED`. A miss here is the
  direct cause of a question being re-asked.

**Judge check** (rows not expected to be `NOT_PROVIDED`):
> Question: … User reply: … Expected extraction: … System extraction: …
> Pass if the system extraction states the same facts as the expected
> one (same numbers, dates, negation, people). Fail if it drops a negation,
> changes a number, adds a fact not in the reply, or misses the answer.

**Metrics**
- Extraction accuracy (overall and per category: direct, short, negation,
  numeric, hindi, code-mixed, rambling, already-known)
- False-`NOT_PROVIDED` rate (real answers treated as no answer)
- False-extraction rate on `non-answer` rows (invented answers; the worst
  error, because a made-up fact enters the case silently)
- Consistency across the 3 repeats

**How to read it:** low scores on `negation` or `numeric` mean facts are
being corrupted. A high false-`NOT_PROVIDED` rate explains the reworded
repeat questions. The `already-known` rows also flag a loop-level problem
(the question should not have been asked at all), which better extraction
cannot fix alone.

---

### 6.2 `analyze_query`: first-message analysis
**Tests:** intent, confidence, extracted facts, and whether `info_needed`
contains only critical, not-yet-given, non-private fields.

**Call:**
```python
from nodes.query_analyzer import QueryAnalyzer, normalize_info_needed_list
out = QueryAnalyzer().analyze_query({"query": row.user_query})
needed = normalize_info_needed_list(out.get("info_needed_list", []))
used_fallback = "case_type" in out   # keyword fallback path when the LLM/JSON fails
```
Record `used_fallback`, and report how often it fires. Those rows test the
fallback, not the model.

**Deterministic checks**
- Clarification: `intent_confidence == "low"` should match
  `expected_needs_clarification == "yes"` (graph.py routes low confidence
  to `clarify`).
- Privacy: no `needed` field matches a privacy keyword (address, phone,
  email, aadhaar, pan, bank, workplace). Do a keyword match first, then
  have the judge confirm borderline cases.

**Judge checks**, one call per row and repeat, returning a verdict per item:
1. Confidence matches (`medium` vs `high` = partial, not fail)
2. Every fact in `expected_info_provided` is in `info_collected`
3. Every `must_ask` field is in `needed`
4. **No re-ask**: nothing in `needed` asks for something already provided
   or in `must_not_ask`
5. **No scope creep**: every `needed` item is within
   `acceptable_info_needed` (clearly critical extras = "acceptable extra")

**Metrics:** pass rate per check, per category. Checks 4 and 5 are the
headline numbers.

---

### 6.3 `revalidate`: does it know when to stop
**Tests:** given the original query plus accumulated facts, does the
analyzer converge (empty `info_needed`), and does it stay converged?

**Call:** build the message exactly as `revalidate_information_node` does:
```python
facts = parse(row.info_collected)            # "k: v | k: v" -> dict; "(none)" -> {}
info_context = "\n".join(f"- {k.replace('_', ' ').title()}: {v}" for k, v in facts.items())
synthetic = f"{row.root_query}\n\nMy Information:\n{info_context}"
out = QueryAnalyzer().analyze_query({"query": synthetic})
needed = normalize_info_needed_list(out.get("info_needed_list", []))
converged = len(needed) == 0
```

**Deterministic checks**
- Decision: `converged` matches `expected_converged`.
- Stability: within a scenario, the repeat round gets the same decision as
  the round before it.

**Judge checks**
- No re-ask: nothing in `needed` is already in `info_collected`.
- Scope creep: count `needed` items outside `acceptable_still_missing`;
  also flag any that match `scope_creep_fields`.

**Metrics**
- Decision accuracy, split by expected yes / no. Accuracy on the "yes" rows
  is the key number: it shows whether the loop can terminate.
- Total scope-creep items per scenario
- Stability rate
- Rounds-to-converge vs expected. A scenario that never converges is the
  unbounded-loop bug.

**Note:** good results here do not replace a hard cap on follow-up
questions in code. One bad call can still restart the loop.

---

### 6.4 `retrieve`: right documents for the query
**Tests:** case precedents and statutes returned for each query, in several
languages.

**Call:**
```python
from lang_utils import detect_language
from nodes.retriever import retrieve_documents
state = {"query": row.query, "root_query": row.query,
         "detected_language": detect_language(row.query)}
res = retrieve_documents(state)
law  = [c for c in res["retrieved_chunks"] if c.get("retrieval_group") == "law_or_act"]
case = [c for c in res["retrieved_chunks"] if c.get("retrieval_group") == "legal_case"]
```
Also log whether translation ran, and its success flag (from the retriever
log line).

**Deterministic checks**
- `law_recall`: share of `gold_law_parent_ids` found in `law` parent_ids
- `case_hit`: at least one `gold_case_parent_ids` in `case` (also report
  `case_recall`)
- Twin agreement: parent_id overlap (Jaccard) between language twins (same
  topic, different language)
- Junk check: count results whose parent_id is in the known junk/duplicate
  lists in `retrieval_eval/dataset_info.txt`

**Judge check**, one call per row covering every returned chunk:
> Query: … For each document (title + first 500 chars), answer relevant
> 0/1 and give a short reason.

This yields **judged precision** and catches good results that are not in
the gold list. Gold lists are "known relevant", not exhaustive.

**Metrics:** law recall, case hit/recall, judged precision, twin agreement,
junk rate. Report per language, to show whether Hindi/Tamil retrieval
matches English.

**Run it twice:** once on the code before the category/query-construction
fixes and once after, to put numbers on the improvement seen manually.

---

### 6.5 `generate`: the final answer
**Tests:** coverage of key law, no harmful or wrong claims, grounding in
retrieved context, language and role.

**Call (two steps):**
1. Freeze context, once per dataset version:
   ```python
   state = {"query": row.user_query, "root_query": row.user_query,
            "detected_language": detect_language(row.user_query)}
   chunks = retrieve_documents(state)["retrieved_chunks"]   # save to frozen_context/<id>.json
   ```
2. Generate with the frozen chunks:
   ```python
   from nodes.generator import generate_response
   state = {"query": row.user_query, "root_query": row.user_query,
            "retrieved_chunks": frozen_chunks, "info_collected": parse(row.info_collected),
            "user_gender": row.user_gender, "user_intent": row.topic,
            "detected_language": detect_language(row.user_query),
            "name": "Client", "messages": []}
   answer = generate_response(state)["response"]
   ```
   Also capture citation_guard's removals from the log
   (`Removed unverified section citations: [...]`).

**Deterministic checks**
- Response language: run `detect_language` on the answer and compare with
  `expected_response_language` (Hinglish rows: accept Hindi or English;
  let the judge decide).
- Citation-guard removal rate across rows.

**Judge check**, one call per row with the rubric:
1. Coverage: which `must_cover` points are made (score = share covered)
2. Hard fails: any `must_not_claim` present → row fails regardless of
   coverage
3. Grounding: is each legal claim supported by the frozen context? (0–1)
4. Role: does it address the user in their actual role (father, mother-in-
   law respondent, sibling helping a sister)?
5. Language: correct language throughout

**Score coverage and grounding separately.** The generator is told to cite
only what is in the context, so when retrieval missed a statute, a
well-behaved answer will leave it out. That is low coverage with high
grounding, and it points at retrieval, not the generator.

**Metrics:** mean coverage, hard-fail rate, mean grounding, language
accuracy, role accuracy, citation-guard removal rate. Compare English rows
with their Hindi twins to see whether quality drops in Hindi.

---

### 6.6 `analyze_reasoning`: honest precedent explanations
**Tests:** usage scores track real relevance, no invented similarities for
irrelevant precedents, excerpts are real quotes.

**Call:**
```python
from nodes.reasoning_explainer import DynamicReasoningExplainer
parent = load_parent(row.precedent_parent_id)   # full parent content from data/chunked/*.json
precedent = {"content": parent["content"], "score": 0.9,
             "metadata": {"title": parent["metadata"]["title"], "url": parent["metadata"]["url"]}}
usage = DynamicReasoningExplainer().analyze_precedent_usage(
    precedent=precedent, precedent_index=0,
    case_summary=row.case_summary, response=row.reference_response)
```
Use the same fixed retrieval score (0.9) for every row, so the score the
explainer sees doesn't hint at relevance.

**Deterministic checks**
- Score band: `usage.usage_score` within `expected_usage_score_band`
- Excerpt: `citation_guard.excerpt_in_source(usage.key_excerpt,
  parent["content"])`. Also record how often the model's own excerpt failed
  and the code fell back to the first 200 characters.

**Judge checks**, for `low` rows:
- `matching_factors` invent specific similarities that are not true?
- `how_it_influenced_response` claims the precedent shaped the advice?

**Metrics:** score-band accuracy split by high/low, **false-high rate on
low rows** (the over-claiming bug), invented-similarity rate, excerpt-
verbatim rate. For row 1 (the outdated "Daughter in law's rights" post),
check whether `different_factors` flags the conflict with current law.

---

## 7. Reporting

`SUMMARY.md` for each run contains:
1. Run config (commit, models, temperatures, judge, dataset hashes, flags)
2. One headline table, one row per node:

   | Node | Headline metric | Baseline | This run | Δ |
   |---|---|---|---|---|
   | gather_info | extraction accuracy | | | |
   | analyze_query | no-re-ask + no-scope-creep pass rate | | | |
   | revalidate | decision accuracy on "yes" rows | | | |
   | retrieve | law recall / judged precision | | | |
   | generate | coverage / hard-fail rate / grounding | | | |
   | analyze_reasoning | false-high rate on low rows | | | |

3. Per-category breakdowns (link to each node's `summary.md`)
4. Rows that flipped (pass→fail and fail→pass) since the baseline
5. Judge validation result (human–judge agreement) for that run

**Targets:** don't set pass/fail targets before the baseline exists. After
the first run, set targets per node relative to the baseline, and decide
before running which regressions block a deploy (e.g. any new hard fail in
`generate`).

---

## 8. Optional: end-to-end check

After the per-node evaluations, run a handful of full conversations through
the compiled graph (scripted user replies taken from the `revalidate_eval`
scenarios). Measure the number of follow-up questions before an answer, and
whether the final answer passes its `generator_eval` rubric. This catches
interaction problems that isolated tests can't, such as a correct extraction
followed by an unnecessary revalidation question.

---

## 9. How results feed back into fixes

| Finding | Likely fix (already on the todo list) |
|---|---|
| High false-`NOT_PROVIDED` in gather_info | Improve extraction prompt; skip a field after 2 failed extractions instead of re-asking |
| Low "yes" accuracy / scope creep in revalidate | Hard cap on follow-up questions (`MAX_FOLLOWUP_QUESTIONS`); pass already-asked fields to the analyzer |
| Re-ask / scope creep in analyze_query | Tighten prompt; pass `info_collected` explicitly |
| Low law recall, junk in law results | Remove duplicate/off-topic documents from `family_law_2`; widen law top-k |
| Low case precision | Re-embed corpus with question text, not only answers |
| Low coverage but high grounding in generate | Retrieval gap (see above), not a generator problem |
| Hard fails / low grounding in generate | Generator prompt, temperature, citation guard coverage (act names, case outcomes) |
| High false-high rate in reasoning | Hide or de-emphasise low-usage precedents; stricter explainer prompt |

---

## 10. Caveats

- All six datasets were drafted by an AI assistant. Human review (Stage 0)
  comes before any number is treated as meaningful.
- Dataset sizes (29–70 rows) give directional, per-category signal and are
  good for before/after comparisons. They are not precise absolute
  estimates.
- The corpus has no Hindi documents. All Hindi/Tamil rows test translation
  and model language ability, not matching against native-language sources.
- Judge results depend on the judge prompt. Keep it versioned, and re-check
  human agreement whenever it changes.
