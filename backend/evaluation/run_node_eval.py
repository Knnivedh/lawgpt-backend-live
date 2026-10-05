"""
Evaluation harness for the five LLM nodes, on the version-2 golden datasets.

    cd backend
    python evaluation/run_node_eval.py --node gather            # one node
    python evaluation/run_node_eval.py --node all --limit 5     # small pilot
    python evaluation/run_node_eval.py --node generator --no-judge

Nodes: gather, analyzer, revalidate, generator, reasoning.

The node under test runs exactly as in the app (Llama through Hugging Face).
The judge is a different model, gemma4:31b-cloud through Ollama, so judging
uses no Hugging Face credit. Checks that plain code can make are made in code.

Every node output and every judge verdict is saved as it is produced, in
evaluation/results/v2_nodes/<node>/, so an interrupted run continues where it
stopped and a re-run makes no model calls. Delete raw.jsonl (or judged.jsonl)
to force fresh calls. A run stops after 3 failed model calls in a row; the
nodes themselves hide such failures behind fallback answers, so failed rows
are not saved.
"""

import argparse
import csv
import json
import logging
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

EVAL = Path(__file__).resolve().parent
BACKEND = EVAL.parent
sys.path.insert(0, str(BACKEND))

import dotenv  # noqa: E402

dotenv.load_dotenv(BACKEND / ".env")

from langchain_ollama import ChatOllama  # noqa: E402

from config import settings  # noqa: E402

OUT = EVAL / "results" / "v2_nodes"
JUDGE_MODEL = settings.ollama_translation_model
PAUSE = 1.0  # seconds between system calls, to stay under provider burst limits
PRIVACY_WORDS = ("address", "phone", "mobile", "email", "aadhaar", "aadhar", "pan_", "pan ", "bank", "workplace", "employer")
SCRIPTS = {"Hindi": (0x0900, 0x097F), "Tamil": (0x0B80, 0x0BFF), "Kannada": (0x0C80, 0x0CFF)}


# ── plumbing ────────────────────────────────────────────────────────────────

class CountingLLM:
    """Stands in for a node's chat model: counts calls, tokens and failures."""

    def __init__(self, inner):
        self.inner = inner
        self.calls = self.errors = self.input_tokens = self.output_tokens = 0
        self.last_error = ""

    def invoke(self, messages, *args, **kwargs):
        try:
            response = self.inner.invoke(messages, *args, **kwargs)
        except Exception as e:
            self.errors += 1
            self.last_error = str(e)[:300]
            raise
        self.calls += 1
        usage = getattr(response, "usage_metadata", None) or {}
        tokens = (getattr(response, "response_metadata", None) or {}).get("token_usage") or {}
        self.input_tokens += usage.get("input_tokens") or tokens.get("prompt_tokens") or 0
        self.output_tokens += usage.get("output_tokens") or tokens.get("completion_tokens") or 0
        return response


def read_jsonl(path):
    if not path.exists():
        return {}
    return {r["id"]: r for r in (json.loads(line) for line in open(path, encoding="utf-8") if line.strip())}


def append_jsonl(path, record):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_rows(folder):
    return list(csv.DictReader(open(EVAL / folder / "golden_dataset_v2.csv", encoding="utf-8")))


def parse_facts(cell):
    facts = {}
    for part in cell.split(" | "):
        if ": " in part:
            key, value = part.split(": ", 1)
            facts[key.strip()] = value.strip()
    return facts


def cells(cell):
    return [x.strip() for x in cell.split(" | ") if x.strip()]


def script_share(text, language):
    letters = [c for c in text if c.isalpha()]
    if not letters or language not in SCRIPTS:
        return None
    low, high = SCRIPTS[language]
    return sum(low <= ord(c) <= high for c in letters) / len(letters)


_judge = None


def judge(prompt):
    """One judge call; returns the parsed JSON object."""
    global _judge
    if _judge is None:
        headers = {"Authorization": f"Bearer {settings.ollama_api_key}"} if settings.ollama_api_key else None
        _judge = ChatOllama(model=JUDGE_MODEL, base_url=settings.ollama_base_url, temperature=0, num_predict=900,
                            reasoning=False, format="json", client_kwargs={"headers": headers} if headers else {})
    text = str(_judge.invoke(
        "You are grading the output of a legal-assistant component against a reference. Be strict and literal. "
        "Reply with one JSON object only, using exactly the keys asked for.\n\n" + prompt).content)
    match = re.search(r"\{.*\}", text, re.S)
    return json.loads(match.group(0) if match else text)


def mean(values):
    values = [v for v in values if v is not None]
    return round(statistics.mean(values), 2) if values else None


def rate(rows, test):
    return f"{mean([1 if test(r) else 0 for r in rows])} ({sum(1 for r in rows if test(r))}/{len(rows)})" if rows else "-"


def by(rows, key):
    groups = defaultdict(list)
    for r in rows:
        groups[r["row"][key]].append(r)
    return groups


def breakdown(title, rows, key, columns):
    """columns: list of (heading, function(group) -> text)."""
    lines = ["", f"### {title}", "", "| " + " | ".join([key, "rows"] + [c[0] for c in columns]) + " |",
             "|" + "---|" * (len(columns) + 2)]
    for name, group in sorted(by(rows, key).items()):
        lines.append("| " + " | ".join([str(name), str(len(group))] + [str(c[1](group)) for c in columns]) + " |")
    return lines


def parallel_agreement(rows, ok):
    """Share of parallel scenarios where the check holds in all five languages."""
    groups = defaultdict(list)
    for r in rows:
        if r["row"]["split"] == "parallel":
            groups[(r["row"]["scenario_id"], r["row"].get("round", ""), r["row"].get("precedent_parent_id", ""))].append(ok(r))
    full = [g for g in groups.values() if len(g) == 5]
    return f"{sum(all(g) for g in full)}/{len(full)}" if full else "-"


# ── gather_info ─────────────────────────────────────────────────────────────

class Gather:
    folder, name = "gather_info_eval", "gather"

    def setup(self):
        from nodes.information_gatherer import InformationGatherer
        self.node = InformationGatherer()
        self.node.llm = self.llm = CountingLLM(self.node.llm)

    def run(self, row):
        return {"extraction": str(self.node._extract_information(
            last_question=row["last_question"], user_response=row["user_response"], info_target=row["field"]))}

    def score(self, row, out, verdict):
        expected_none = row["expected_extraction"] == "NOT_PROVIDED"
        got_none = out["extraction"].strip() == "NOT_PROVIDED"
        if expected_none:
            return {"pass": got_none, "invented": bool(verdict and verdict.get("kind") == "invented_fact")}
        return {"pass": (not got_none) and bool(verdict and verdict.get("verdict") == "pass"),
                "false_not_provided": got_none, "concise": bool(verdict and verdict.get("concise"))}

    def judge_prompt(self, row, out):
        expected_none = row["expected_extraction"] == "NOT_PROVIDED"
        got_none = out["extraction"].strip() == "NOT_PROVIDED"
        if expected_none and not got_none:
            return (f"Question asked: {row['last_question']}\nUser reply: {row['user_response']}\n"
                    f"System extraction: {out['extraction']}\n\n"
                    "The reply does not answer the question. Did the system extraction merely restate that there is no "
                    "answer (for example it repeats the reply or says the user does not know), or does it assert a fact as "
                    "the answer?\nKeys: \"kind\" = \"restates_no_answer\" or \"invented_fact\"; \"reason\".")
        if expected_none or got_none:
            return None
        return (f"Question asked: {row['last_question']}\nUser reply: {row['user_response']}\n"
                f"Expected extraction (in English): {row['expected_extraction']}\nSystem extraction: {out['extraction']}\n\n"
                "Pass if the system extraction states the same facts as the expected one (same numbers, dates, negation, "
                "people). It may be in any language and worded differently. Fail if it drops a negation, changes a number, "
                "adds a fact not in the reply, or misses the answer.\n"
                "Keys: \"verdict\" = \"pass\" or \"fail\"; \"concise\" = true if the extraction keeps only the answer and "
                "leaves out unrelated parts of the reply, else false; \"reason\".")

    def report(self, rows):
        facts = [r for r in rows if r["row"]["expected_extraction"] != "NOT_PROVIDED"]
        none = [r for r in rows if r["row"]["expected_extraction"] == "NOT_PROVIDED"]
        ok = lambda r: r["score"]["pass"]
        lines = ["| Metric | Value |", "|---|---|",
                 f"| Extraction correct, all rows | {rate(rows, ok)} |",
                 f"| Rows with a real answer: extracted correctly | {rate(facts, ok)} |",
                 f"| Rows with a real answer: wrongly returned NOT_PROVIDED | {rate(facts, lambda r: r['score']['false_not_provided'])} |",
                 f"| Rows with no answer: returned NOT_PROVIDED | {rate(none, ok)} |",
                 f"| Rows with no answer: a fact was invented | {rate(none, lambda r: r['score']['invented'])} |",
                 f"| Correct extractions that keep only the answer | {rate([r for r in facts if ok(r)], lambda r: r['score']['concise'])} |",
                 f"| Parallel cases correct in all five languages | {parallel_agreement(rows, ok)} |"]
        lines += breakdown("By reply type", rows, "category", [("correct", lambda g: rate(g, ok))])
        lines += breakdown("By language", rows, "language", [("correct", lambda g: rate(g, ok))])
        return lines


# ── analyze_query ───────────────────────────────────────────────────────────

def needed_fields(out):
    from nodes.query_analyzer import normalize_info_needed_list
    return [f"{item.get('field', '')}: {item.get('question', item.get('description', ''))}".strip(": ")
            for item in normalize_info_needed_list(out.get("info_needed_list", []))]


class Analyzer:
    folder, name = "query_analyzer_eval", "analyzer"

    def setup(self):
        from nodes.query_analyzer import QueryAnalyzer
        self.node = QueryAnalyzer()
        self.node.llm = self.llm = CountingLLM(self.node.llm)

    def run(self, row):
        out = self.node.analyze_query({"query": row["user_query"]})
        return {"intent": out.get("user_intent", ""), "confidence": out.get("intent_confidence", ""),
                "info_collected": out.get("info_collected", {}), "needed": needed_fields(out),
                "used_fallback": "case_type" in out}

    def judge_prompt(self, row, out):
        return (f"User's first message: {row['user_query']}\n\n"
                f"REFERENCE\nIntent: {row['expected_intent']}\nFacts the message gives: {row['expected_info_provided']}\n"
                f"Fields that must be asked: {row['must_ask'] or '(none)'}\n"
                f"Fields that are acceptable to ask: {row['acceptable_info_needed'] or '(none)'}\n"
                f"Fields that must not be asked: {row['must_not_ask']}\n\n"
                f"SYSTEM OUTPUT\nIntent: {out['intent']}\nFacts captured: {json.dumps(out['info_collected'], ensure_ascii=False)}\n"
                f"Fields it wants to ask: {json.dumps(out['needed'], ensure_ascii=False)}\n\n"
                "Keys:\n\"intent\": \"pass\" if the system intent matches the reference intent in substance, else \"fail\".\n"
                "\"facts\": \"pass\" if every reference fact is captured, \"partial\" if most are, \"fail\" otherwise.\n"
                "\"must_ask\": \"pass\" if every must-ask field is among the fields it wants to ask, \"fail\" if not, \"na\" if there are none.\n"
                "\"reasks\": list of the fields it wants to ask whose answer is already in the user's message.\n"
                "\"private\": list of the fields it wants to ask that request private details (address, phone, email, Aadhaar/PAN, bank, workplace).\n"
                "\"scope_creep\": list of the fields it wants to ask that are neither must-ask nor acceptable and are not clearly needed to answer the legal question.")

    def score(self, row, out, verdict):
        v = verdict or {}
        expected, got = row["expected_confidence"], out["confidence"]
        confidence = "pass" if got == expected else ("partial" if {got, expected} == {"medium", "high"} else "fail")
        private_code = [f for f in out["needed"] if any(w in f.lower() for w in PRIVACY_WORDS)]
        return {"clarify_ok": (got == "low") == (row["expected_needs_clarification"] == "yes"), "confidence": confidence,
                "intent": v.get("intent"), "facts": v.get("facts"), "must_ask": v.get("must_ask"),
                "reasks": len(v.get("reasks") or []), "private": len(set(private_code) | set(v.get("private") or [])),
                "scope_creep": len(v.get("scope_creep") or []), "asked": len(out["needed"]),
                "used_fallback": out["used_fallback"]}

    def report(self, rows):
        s = lambda r: r["score"]
        must = [r for r in rows if s(r)["must_ask"] in ("pass", "fail")]
        lines = ["| Metric | Value |", "|---|---|",
                 f"| Routes correctly (clarify when it should, proceed when it should) | {rate(rows, lambda r: s(r)['clarify_ok'])} |",
                 f"| Confidence matches exactly | {rate(rows, lambda r: s(r)['confidence'] == 'pass')} |",
                 f"| Intent correct | {rate(rows, lambda r: s(r)['intent'] == 'pass')} |",
                 f"| All given facts captured | {rate(rows, lambda r: s(r)['facts'] == 'pass')} |",
                 f"| Must-ask field asked (rows that have one) | {rate(must, lambda r: s(r)['must_ask'] == 'pass')} |",
                 f"| Rows with no re-asked fact | {rate(rows, lambda r: s(r)['reasks'] == 0)} |",
                 f"| Rows with no out-of-scope question | {rate(rows, lambda r: s(r)['scope_creep'] == 0)} |",
                 f"| Rows asking for private details | {rate(rows, lambda r: s(r)['private'] > 0)} |",
                 f"| Mean questions it wants to ask | {mean([s(r)['asked'] for r in rows])} |",
                 f"| Rows answered by the keyword fallback, not the model | {rate(rows, lambda r: s(r)['used_fallback'])} |",
                 f"| Parallel cases routed correctly in all five languages | {parallel_agreement(rows, lambda r: s(r)['clarify_ok'])} |"]
        cols = [("routes correctly", lambda g: rate(g, lambda r: s(r)["clarify_ok"])),
                ("intent", lambda g: rate(g, lambda r: s(r)["intent"] == "pass")),
                ("no re-ask", lambda g: rate(g, lambda r: s(r)["reasks"] == 0)),
                ("no scope creep", lambda g: rate(g, lambda r: s(r)["scope_creep"] == 0))]
        return lines + breakdown("By language", rows, "language", cols) + breakdown("By category", rows, "category", cols)


# ── revalidate ──────────────────────────────────────────────────────────────

class Revalidate:
    folder, name = "revalidate_eval", "revalidate"

    def setup(self):
        from nodes.query_analyzer import QueryAnalyzer
        self.node = QueryAnalyzer()
        self.node.llm = self.llm = CountingLLM(self.node.llm)

    def run(self, row):
        facts = parse_facts(row["info_collected"])
        context = "\n".join(f"- {k.replace('_', ' ').title()}: {v}" for k, v in facts.items())
        out = self.node.analyze_query({"query": f"{row['root_query']}\n\nMy Information:\n{context}"})
        needed = needed_fields(out)
        # graph.py stops asking regardless of the model after 2 re-validations or 7 facts
        capped = int(row["round"]) - 1 >= 2 or len(facts) >= 7
        return {"needed": needed, "model_converged": not needed, "capped": capped,
                "used_fallback": "case_type" in out}

    def judge_prompt(self, row, out):
        if not out["needed"]:
            return None
        return (f"User's question: {row['root_query']}\nFacts already known: {row['info_collected']}\n"
                f"Reasonable to still ask: {row['acceptable_still_missing'] or '(nothing)'}\n"
                f"Irrelevant to the legal answer: {row['scope_creep_fields']}\n\n"
                f"The system wants to ask: {json.dumps(out['needed'], ensure_ascii=False)}\n\n"
                "Put each thing the system wants to ask into exactly one list.\nKeys:\n"
                "\"reasks\": its answer is already among the known facts or in the question.\n"
                "\"private\": asks for address, phone, email, Aadhaar/PAN, bank or workplace details.\n"
                "\"scope_creep\": irrelevant to the legal answer, or not in the reasonable list and not clearly needed.\n"
                "\"acceptable\": in the reasonable list, or clearly needed to answer the legal question.")

    def score(self, row, out, verdict):
        v = verdict or {}
        expected = row["expected_converged"] == "yes"
        node = out["model_converged"] or out["capped"]
        return {"model_ok": out["model_converged"] == expected, "node_ok": node == expected,
                "expected": expected, "model_converged": out["model_converged"], "node_converged": node,
                "asked": len(out["needed"]), "reasks": len(v.get("reasks") or []),
                "private": len(v.get("private") or []), "scope_creep": len(v.get("scope_creep") or []),
                "used_fallback": out["used_fallback"]}

    def report(self, rows):
        s = lambda r: r["score"]
        yes, no = [r for r in rows if s(r)["expected"]], [r for r in rows if not s(r)["expected"]]
        asking = [r for r in rows if s(r)["asked"]]
        lines = ["Two decisions are scored. \"Model\" is what the analyzer model says on its own. \"Node\" adds the rule in "
                 "graph.py that stops asking after two re-validations or seven collected facts.", "",
                 "| Metric | Model alone | Node (with the stop rule) |", "|---|---|---|",
                 f"| Decision correct, all rows | {rate(rows, lambda r: s(r)['model_ok'])} | {rate(rows, lambda r: s(r)['node_ok'])} |",
                 f"| Should stop: stops | {rate(yes, lambda r: s(r)['model_ok'])} | {rate(yes, lambda r: s(r)['node_ok'])} |",
                 f"| Should ask more: asks more | {rate(no, lambda r: s(r)['model_ok'])} | {rate(no, lambda r: s(r)['node_ok'])} |",
                 "", "| When the model asks for more | Value |", "|---|---|",
                 f"| Rows where it asks | {len(asking)} of {len(rows)} |",
                 f"| Mean questions per such row | {mean([s(r)['asked'] for r in asking])} |",
                 f"| Rows re-asking a known fact | {rate(asking, lambda r: s(r)['reasks'] > 0)} |",
                 f"| Rows with an out-of-scope question | {rate(asking, lambda r: s(r)['scope_creep'] > 0)} |",
                 f"| Rows asking for private details | {rate(asking, lambda r: s(r)['private'] > 0)} |",
                 f"| Rows answered by the keyword fallback | {rate(rows, lambda r: s(r)['used_fallback'])} |",
                 f"| Parallel rounds with the same model decision in all five languages | "
                 f"{parallel_agreement(rows, lambda r: s(r)['model_converged'])} stop, "
                 f"{parallel_agreement(rows, lambda r: not s(r)['model_converged'])} ask |"]
        cols = [("model correct", lambda g: rate(g, lambda r: s(r)["model_ok"])),
                ("node correct", lambda g: rate(g, lambda r: s(r)["node_ok"]))]
        return lines + breakdown("By language", rows, "language", cols) + breakdown("By round", rows, "round", cols)


# ── generate ────────────────────────────────────────────────────────────────

class Generator:
    folder, name = "generator_eval", "generator"

    def setup(self):
        import nodes.generator as generator
        import nodes.retriever as retriever
        sys.path.insert(0, str(EVAL / "retrieval_eval"))
        import run_eval
        self.generator, self.retriever = generator, retriever
        generator.llm = self.llm = CountingLLM(generator.llm)
        # retrieval as in the retriever evaluation: translations and embeddings from its cache
        retriever.translator._providers = ["ollama"]
        self.cache, self.retrieval_calls = run_eval.install_cache(f"tr:ollama:{settings.ollama_translation_model}")
        self.cache_path = run_eval.CACHE_PATH
        self.warnings = []
        handler = logging.Handler()
        handler.emit = lambda record: self.warnings.append(record.getMessage())
        handler.setLevel(logging.WARNING)
        logging.getLogger("nodes.generator").addHandler(handler)
        self.frozen_path = OUT / self.name / "frozen_context.json"
        self.frozen = json.loads(self.frozen_path.read_text()) if self.frozen_path.exists() else {}

    def run(self, row):
        from lang_utils import detect_language
        language = detect_language(row["user_query"])
        if row["id"] not in self.frozen:
            state = {"query": row["user_query"], "root_query": row["user_query"], "detected_language": language}
            self.frozen[row["id"]] = self.retriever.retrieve_documents(state)["retrieved_chunks"]
            self.frozen_path.write_text(json.dumps(self.frozen, ensure_ascii=False))
            self.cache_path.write_text(json.dumps(self.cache))
        chunks = self.frozen[row["id"]]
        self.warnings.clear()
        answer = self.generator.generate_response({
            "query": row["user_query"], "root_query": row["user_query"], "retrieved_chunks": chunks,
            "info_collected": parse_facts(row["info_collected"]), "user_gender": row["user_gender"],
            "user_intent": row["topic"], "detected_language": language, "name": "Client", "messages": []})["response"]
        return {"answer": answer, "detected_language": language,
                "retrieved": [[c["metadata"].get("parent_id"), c["metadata"].get("title")] for c in chunks],
                "guard_removed": [w for w in self.warnings if "removed" in w],
                "guard_flagged": [w for w in self.warnings if "flagged" in w],
                "truncated": any("token limit" in w for w in self.warnings)}

    def judge_prompt(self, row, out):
        cover, avoid = cells(row["must_cover"]), cells(row["must_not_claim"])
        return (f"User ({row['role']}, gender {row['user_gender']}) asked, in {row['language']}: {row['user_query']}\n"
                f"Facts known: {row['info_collected']}\n\n"
                "POINTS A GOOD ANSWER MAKES\n" + "\n".join(f"{i}. {p}" for i, p in enumerate(cover, 1)) + "\n\n"
                "WRONG CLAIMS IT MUST NOT MAKE\n" + "\n".join(f"{i}. {p}" for i, p in enumerate(avoid, 1)) + "\n\n"
                f"SYSTEM ANSWER\n{out['answer']}\n\nKeys:\n"
                f"\"covered\": list of {len(cover)} true/false values, one per point: true if the answer makes that point in "
                "substance (any language; the exact section number or case name is not required).\n"
                f"\"wrong_claims\": list of {len(avoid)} true/false values, one per wrong claim: true if the answer makes it.\n"
                f"\"language_ok\": true if the answer is written in {row['expected_response_language']} "
                "(for Hinglish: Hindi in Roman script, Hindi or English are all acceptable); legal terms in English are fine.\n"
                "\"addressee_ok\": true if the answer speaks to the user in their actual role "
                "(a parent or sibling asking for someone else is not addressed as the spouse; a man is not addressed as the wife).\n"
                "\"cites_statute\": true if the answer names at least one Act or section number.")

    def score(self, row, out, verdict):
        v = verdict or {}
        covered, wrong = v.get("covered") or [], v.get("wrong_claims") or []
        share = script_share(out["answer"].split("---")[0], row["language"])
        return {"coverage": (sum(bool(x) for x in covered) / len(covered)) if covered else None,
                "wrong_claim": any(bool(x) for x in wrong), "language_ok": v.get("language_ok"),
                "script_ok": None if share is None else share >= 0.5, "addressee_ok": v.get("addressee_ok"),
                "cites_statute": v.get("cites_statute"), "guard_removed": bool(out["guard_removed"]),
                "guard_flagged": bool(out["guard_flagged"]), "truncated": out["truncated"],
                "failed": "encountered an error while generating" in out["answer"]}

    def report(self, rows):
        s = lambda r: r["score"]
        indic = [r for r in rows if s(r)["script_ok"] is not None]
        lines = ["| Metric | Value |", "|---|---|",
                 f"| Mean share of the expected legal points covered | {mean([s(r)['coverage'] for r in rows])} |",
                 f"| Answers making a listed wrong claim | {rate(rows, lambda r: s(r)['wrong_claim'])} |",
                 f"| Answer in the expected language (judge) | {rate(rows, lambda r: s(r)['language_ok'])} |",
                 f"| Hindi / Tamil / Kannada rows answered mostly in that script (code check) | {rate(indic, lambda r: s(r)['script_ok'])} |",
                 f"| Answer addressed to the right person | {rate(rows, lambda r: s(r)['addressee_ok'])} |",
                 f"| Answers naming at least one Act or section | {rate(rows, lambda r: s(r)['cites_statute'])} |",
                 f"| Answers where the citation guard removed a sentence | {rate(rows, lambda r: s(r)['guard_removed'])} |",
                 f"| Answers where the citation guard flagged a citation | {rate(rows, lambda r: s(r)['guard_flagged'])} |",
                 f"| Answers cut off at the length limit | {rate(rows, lambda r: s(r)['truncated'])} |",
                 f"| Parallel cases with no wrong claim in all five languages | {parallel_agreement(rows, lambda r: not s(r)['wrong_claim'])} |",
                 "", "Coverage is measured against the rubric, not against what was retrieved. The generator is told to use only "
                 "retrieved material, so low coverage can come from retrieval; grounding against the retrieved text was not judged in this run."]
        cols = [("coverage", lambda g: mean([s(r)["coverage"] for r in g])),
                ("wrong claim", lambda g: rate(g, lambda r: s(r)["wrong_claim"])),
                ("language ok", lambda g: rate(g, lambda r: s(r)["language_ok"])),
                ("addressee ok", lambda g: rate(g, lambda r: s(r)["addressee_ok"]))]
        return (lines + breakdown("By language", rows, "language", cols)
                + breakdown("By whether the needed statute is in the knowledge base", rows, "statute_in_corpus", cols)
                + breakdown("By user gender", rows, "user_gender", cols))


# ── analyze_reasoning ───────────────────────────────────────────────────────

class Reasoning:
    folder, name = "reasoning_eval", "reasoning"

    def setup(self):
        from nodes.reasoning_explainer import DynamicReasoningExplainer
        self.node = DynamicReasoningExplainer()
        self.node.llm = self.llm = CountingLLM(self.node.llm)
        self.fell_back = False
        real_fallback = self.node._fallback_precedent_usage

        def fallback(*args, **kwargs):
            self.fell_back = True
            return real_fallback(*args, **kwargs)
        self.node._fallback_precedent_usage = fallback
        self.parents = {}
        for item in json.loads((BACKEND / "data" / "v2" / "chunked" / "family_law_chunks.json").read_text(encoding="utf-8")):
            if item["metadata"]["is_parent"]:
                self.parents[item["metadata"]["parent_id"]] = item

    def run(self, row):
        parent = self.parents[int(row["precedent_parent_id"])]
        precedent = {"content": parent["content"], "score": 0.9,  # same score for every row, so it gives no hint
                     "metadata": {"title": parent["metadata"]["title"], "url": parent["metadata"].get("url", "")}}
        self.fell_back = False
        usage = self.node.analyze_precedent_usage(precedent=precedent, precedent_index=0,
                                                  case_summary=row["case_summary"], response=row["reference_response"])
        return {"usage_score": usage.usage_score, "matching_factors": usage.matching_factors,
                "different_factors": usage.different_factors, "how_it_influenced_response": usage.how_it_influenced_response,
                "excerpt_is_fallback": usage.key_excerpt == parent["content"][:200], "used_fallback": self.fell_back}

    def judge_prompt(self, row, out):
        if row["expected_relevance"] != "low" or out["used_fallback"]:
            return None
        return (f"User's case: {row['case_summary']}\nAnswer given to the user: {row['reference_response']}\n\n"
                f"A past case titled \"{row['precedent_title']}\", which is about a DIFFERENT legal matter: {row['precedent_excerpt']}\n\n"
                f"The system's explanation of how that past case relates:\nMatching factors: {json.dumps(out['matching_factors'], ensure_ascii=False)}\n"
                f"How it influenced the answer: {out['how_it_influenced_response']}\n\nKeys:\n"
                "\"invented_similarity\": true if the matching factors claim a specific similarity between the two cases that "
                "is not real (a generic one such as 'both are family disputes' does not count).\n"
                "\"claims_influence\": true if the explanation says or implies that this past case shaped or supported the answer.")

    def score(self, row, out, verdict):
        v = verdict or {}
        high = row["expected_relevance"] == "high"
        score = out["usage_score"]
        return {"high": high, "band_ok": (score >= 0.5) if high else (score <= 0.3), "usage_score": score,
                "false_high": (not high) and score >= 0.5, "invented_similarity": bool(v.get("invented_similarity")),
                "claims_influence": bool(v.get("claims_influence")), "excerpt_is_fallback": out["excerpt_is_fallback"],
                "used_fallback": out["used_fallback"]}

    def report(self, rows):
        s = lambda r: r["score"]
        high, low = [r for r in rows if s(r)["high"]], [r for r in rows if not s(r)["high"]]
        lines = ["| Metric | Value |", "|---|---|",
                 f"| Related past cases scored 0.5 or more | {rate(high, lambda r: s(r)['band_ok'])} |",
                 f"| Unrelated past cases scored 0.3 or less | {rate(low, lambda r: s(r)['band_ok'])} |",
                 f"| Unrelated past cases scored 0.5 or more (over-claiming) | {rate(low, lambda r: s(r)['false_high'])} |",
                 f"| Mean score given: related / unrelated | {mean([s(r)['usage_score'] for r in high])} / {mean([s(r)['usage_score'] for r in low])} |",
                 f"| Unrelated: explanation invents a specific similarity | {rate(low, lambda r: s(r)['invented_similarity'])} |",
                 f"| Unrelated: explanation says the case shaped the answer | {rate(low, lambda r: s(r)['claims_influence'])} |",
                 f"| Quoted excerpt not found in the past case (replaced by its opening lines) | {rate(rows, lambda r: s(r)['excerpt_is_fallback'])} |",
                 f"| Rows where the model output could not be read (default 0.5 used) | {rate(rows, lambda r: s(r)['used_fallback'])} |",
                 f"| Parallel pairs scored in the right band in all five languages | {parallel_agreement(rows, lambda r: s(r)['band_ok'])} |"]
        cols = [("related scored high", lambda g: rate([r for r in g if s(r)["high"]], lambda r: s(r)["band_ok"])),
                ("unrelated scored low", lambda g: rate([r for r in g if not s(r)["high"]], lambda r: s(r)["band_ok"]))]
        return lines + breakdown("By language", rows, "language", cols)


NODES = {n.name: n for n in (Gather, Analyzer, Revalidate, Generator, Reasoning)}


# ── driver ──────────────────────────────────────────────────────────────────

def evaluate(name, limit, use_judge, languages):
    spec = NODES[name]()
    out_dir = OUT / name
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = load_rows(spec.folder)
    if languages:
        rows = [r for r in rows if r["language"].lower() in languages]
    if limit:
        # spread a pilot over the languages instead of taking the first rows
        step = max(1, len(rows) // limit)
        rows = rows[::step][:limit]

    raw_path, judged_path = out_dir / "raw.jsonl", out_dir / "judged.jsonl"
    raw, judged = read_jsonl(raw_path), read_jsonl(judged_path)
    todo = [r for r in rows if r["id"] not in raw]
    stopped = ""
    if todo:
        spec.setup()
        failures = 0
        for row in todo:
            errors_before = spec.llm.errors
            try:
                output = spec.run(row)
            except Exception as e:  # a node that raises instead of falling back
                spec.llm.errors += 1
                spec.llm.last_error = str(e)[:300]
                output = None
            if output is None or spec.llm.errors > errors_before:
                failures += 1
                if failures >= 3:
                    stopped = f"Stopped after 3 failed model calls in a row. Last error: {spec.llm.last_error}"
                    break
                time.sleep(5)
                continue
            failures = 0
            raw[row["id"]] = {"id": row["id"], "output": output}
            append_jsonl(raw_path, raw[row["id"]])
            time.sleep(PAUSE)
        print(f"[{name}] system calls {spec.llm.calls}, tokens in {spec.llm.input_tokens}, out {spec.llm.output_tokens}"
              + (f" | {stopped}" if stopped else ""))
        usage_path = out_dir / "usage.json"
        usage = json.loads(usage_path.read_text()) if usage_path.exists() else {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        usage = {"calls": usage["calls"] + spec.llm.calls, "input_tokens": usage["input_tokens"] + spec.llm.input_tokens,
                 "output_tokens": usage["output_tokens"] + spec.llm.output_tokens}
        usage_path.write_text(json.dumps(usage))

    done = [r for r in rows if r["id"] in raw]
    judge_failures = 0
    if use_judge:
        for row in done:
            if row["id"] in judged:
                continue
            prompt = spec.judge_prompt(row, raw[row["id"]]["output"])
            if prompt is None:
                continue
            try:
                judged[row["id"]] = {"id": row["id"], "verdict": judge(prompt)}
                append_jsonl(judged_path, judged[row["id"]])
                judge_failures = 0
            except Exception as e:
                judge_failures += 1
                print(f"[{name}] judge failed on {row['id']}: {str(e)[:150]}")
                if judge_failures >= 3:
                    stopped += " Judge stopped after 3 failures in a row."
                    break
            time.sleep(0.3)

    results = []
    for row in done:
        output = raw[row["id"]]["output"]
        needs_judge = spec.judge_prompt(row, output) is not None
        if needs_judge and row["id"] not in judged:
            continue  # not judged yet; left out of the report rather than scored as a failure
        verdict = judged.get(row["id"], {}).get("verdict")
        results.append({"row": row, "output": output, "verdict": verdict, "score": spec.score(row, output, verdict)})

    usage_path = out_dir / "usage.json"
    usage = json.loads(usage_path.read_text()) if usage_path.exists() else {}
    header = [f"# {name}: evaluation on the version-2 dataset", "",
              f"- Dataset: `evaluation/{spec.folder}/golden_dataset_v2.csv`; rows scored: {len(results)} of {len(rows)}",
              f"- System model: `{settings.llm_model}` (Hugging Face) | judge: `{JUDGE_MODEL}` (Ollama)",
              f"- System calls so far: {usage.get('calls', 0)}; tokens in {usage.get('input_tokens', 0)}, out {usage.get('output_tokens', 0)}",
              "- Dataset labels and judge verdicts have not been reviewed by a person; treat the numbers as provisional."]
    if stopped:
        header.append(f"- **Incomplete:** {stopped.strip()}")
    summary = header + [""] + (spec.report(results) if results else ["No rows scored."])
    (out_dir / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    with open(out_dir / "scored.jsonl", "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps({"id": r["row"]["id"], "output": r["output"], "verdict": r["verdict"], "score": r["score"]},
                               ensure_ascii=False) + "\n")
    print("\n".join(summary[:6 + 16]))
    print(f"[{name}] report: {out_dir / 'summary.md'}\n")
    return not stopped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", required=True, choices=list(NODES) + ["all"])
    parser.add_argument("--limit", type=int, help="score only this many rows (a pilot)")
    parser.add_argument("--languages", help="comma-separated subset, e.g. English,Tamil")
    parser.add_argument("--no-judge", action="store_true")
    args = parser.parse_args()
    languages = {x.strip().lower() for x in args.languages.split(",")} if args.languages else None
    for name in (list(NODES) if args.node == "all" else [args.node]):
        if not evaluate(name, args.limit, not args.no_judge, languages):
            sys.exit(1)


if __name__ == "__main__":
    main()
