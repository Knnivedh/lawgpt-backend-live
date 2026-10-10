"""
Compare chat models (served via HF Inference Providers, like the project's Llama)
as Indic->English query translators for retrieval.

For each (model, query) it records: latency, the translation, a fact-preservation
score (negation / relationships / dates / numbers via regex checks), and retrieval
overlap: Jaccard of retrieved parent_ids vs retrieval from a hand-written
reference English translation. Also records retrieval from the untranslated query.

Run from backend/:  python translation_model_comparison/compare.py
Outputs: results.json and report.md next to this file.
"""

import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

import dotenv
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
dotenv.load_dotenv(HERE.parent / ".env")

MODELS = [
    "google/gemma-3-4b-it",
    "google/gemma-3-12b-it",
    "google/gemma-3-27b-it",
    "meta-llama/Llama-3.1-8B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct",
    "Qwen/Qwen3-32B",
    "Qwen/Qwen2.5-7B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct",
]

SYSTEM = (
    "You are a translation engine, not an assistant. Translate the text inside <text> tags "
    "into English. Never answer, explain or comment on it. Preserve negation, relationships "
    "(husband/wife/in-laws), dates, numbers and legal terms exactly (e.g. keep 'maintenance' "
    "as 'maintenance', not 'alimony'). Output only the English translation."
)

# lang, query, reference English, checks: list of regex alternatives that must ALL match
QUERIES = [
    ("hi", "तलाक के बाद बच्चे की कस्टडी किसे मिलती है?",
     "Who gets custody of the child after divorce?",
     [r"custody", r"divorce"]),
    ("hi", "मेरे पति ने मुझे तलाक का नोटिस नहीं दिया है, क्या मैं भरण-पोषण मांग सकती हूँ?",
     "My husband has not given me a divorce notice; can I claim maintenance?",
     [r"husband", r"\bnot\b|n't|\bno\b|never|hasn", r"maintenance", r"divorce"]),
    ("hi", "दहेज उत्पीड़न की शिकायत कैसे दर्ज करें?",
     "How do I file a complaint of dowry harassment?",
     [r"dowry", r"complaint"]),
    ("hi", "मेरी शादी 2019 में हुई थी और मेरे ससुराल वालों ने मुझे 2023 में घर से निकाल दिया, क्या मुझे घर में रहने का अधिकार है?",
     "I got married in 2019 and my in-laws threw me out of the house in 2023; do I have a right to reside in the house?",
     [r"2019", r"2023", r"in-?laws|husband'?s family|marital family|parents-in-law", r"\bright\b"]),
    ("ta", "விவாகரத்திற்குப் பிறகு பராமரிப்புத் தொகை எப்படி நிர்ணயிக்கப்படுகிறது?",
     "How is the maintenance amount determined after divorce?",
     [r"maintenance", r"divorce"]),
    ("te", "గృహ హింస చట్టం కింద ఫిర్యాదు ఎలా చేయాలి?",
     "How do I file a complaint under the domestic violence act?",
     [r"domestic (violence|abuse)", r"complaint"]),
    ("bn", "বিবাহবিচ্ছেদের পর সন্তানের অভিভাবকত্ব কীভাবে নির্ধারিত হয়?",
     "How is custody of the child determined after divorce?",
     [r"custody|guardianship", r"divorce"]),
    ("mr", "माझ्या पतीने मला घटस्फोट दिलेला नाही पण तो दुसरे लग्न करत आहे, हे कायदेशीर आहे का?",
     "My husband has not given me a divorce but he is marrying again; is this legal?",
     [r"husband", r"\bnot\b|n't|\bno\b|never|hasn", r"marr", r"legal"]),
    ("hi-en", "Mera husband domestic violence karta hai, maintenance kaise le sakti hoon?",
     "My husband commits domestic violence; how can I get maintenance?",
     [r"husband", r"domestic (violence|abuse)", r"maintenance"]),
    ("hi-en", "Meri wife ne mujhe chhod diya hai aur 5 saal se alag rehti hai, kya main divorce le sakta hoon?",
     "My wife has left me and has been living separately for 5 years; can I get a divorce?",
     [r"wife", r"\b5\b|five", r"divorce", r"separate|apart"]),
    ("ta-en", "Divorce case ல custody எப்படி decide பண்றாங்க?",
     "How is custody decided in a divorce case?",
     [r"custody", r"divorce"]),
    ("gu", "શું પત્ની પતિની મિલકતમાં ભાગ માંગી શકે છે, જો લગ્ન 10 વર્ષ પહેલાં થયા હોય?",
     "Can a wife claim a share in her husband's property if the marriage took place 10 years ago?",
     [r"wife", r"husband", r"property", r"\b10\b|ten"]),
]

HEADERS = {"Authorization": f"Bearer {os.getenv('HUGGINGFACE_API_KEY')}"}


def translate(model: str, text: str):
    t0 = time.time()
    try:
        r = requests.post(
            "https://router.huggingface.co/v1/chat/completions",
            headers=HEADERS, timeout=120,
            json={"model": model, "max_tokens": 400, "temperature": 0,
                  "messages": [{"role": "system", "content": SYSTEM},
                               {"role": "user", "content": f"<text>{text}</text>"}]},
        )
    except requests.RequestException as e:
        return None, time.time() - t0, f"request error: {e}"
    dt = time.time() - t0
    if not r.ok:
        return None, dt, f"{r.status_code}: {r.text[:120]}"
    out = r.json()["choices"][0]["message"]["content"] or ""
    out = re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()
    out = re.sub(r"</?text>", "", out).strip()
    return out, dt, None


def fact_score(text: str, checks):
    hits = [bool(re.search(c, text or "", re.I)) for c in checks]
    return sum(hits) / len(hits)


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a | b) else 1.0


def main():
    from nodes.retriever import retrieve_documents  # connects to Milvus

    cache = {}

    def parents(text):
        if text not in cache:
            res = retrieve_documents({"query": text, "root_query": text, "detected_language": "en"})
            cache[text] = [c["metadata"].get("parent_id") for c in res.get("retrieved_chunks", [])]
        return cache[text]

    rows = []
    ref_parents, raw_parents = {}, {}
    for i, (lang, q, ref, _) in enumerate(QUERIES):
        ref_parents[i] = parents(ref)
        raw_parents[i] = parents(q)
        print(f"[ref] q{i} done", flush=True)

    for model in MODELS:
        for i, (lang, q, ref, checks) in enumerate(QUERIES):
            out, dt, err = translate(model, q)
            row = {"model": model, "q": i, "lang": lang, "latency_s": round(dt, 2), "error": err,
                   "translation": out}
            if out:
                row["fact_score"] = fact_score(out, checks)
                row["retrieval_jaccard_vs_reference"] = round(jaccard(parents(out), ref_parents[i]), 3)
            rows.append(row)
            print(f"{model} q{i} {dt:.1f}s {'ERR '+err if err else out[:70]!r}", flush=True)

    raw_j = [jaccard(raw_parents[i], ref_parents[i]) for i in range(len(QUERIES))]
    (HERE / "results.json").write_text(json.dumps(
        {"queries": [{"lang": l, "query": q, "reference": r} for l, q, r, _ in QUERIES],
         "raw_untranslated_jaccard_vs_reference": raw_j, "rows": rows},
        ensure_ascii=False, indent=2))
    write_report(rows, raw_j)


def write_report(rows, raw_j):
    lines = ["# Query-translation model comparison", "",
             f"{len(QUERIES)} queries (hi, ta, te, bn, mr, gu, plus Hinglish/Tanglish code-mixed). "
             "Same system prompt and temperature 0 for every model, via the HF router.", "",
             "- **fact**: share of must-preserve checks (negation, relationship, year/number, legal term) present in the output.",
             "- **retrieval overlap**: Jaccard of retrieved parent_ids vs retrieval from a hand-written reference English query (1.0 = identical results).",
             f"- **Untranslated baseline** retrieval overlap vs reference: mean **{statistics.mean(raw_j):.2f}**.", "",
             "| Model | OK | Mean latency (s) | Fact score | Retrieval overlap |", "|---|---|---|---|---|"]
    for m in MODELS:
        mr = [r for r in rows if r["model"] == m]
        ok = [r for r in mr if r["translation"]]
        if not ok:
            lines.append(f"| {m} | 0/{len(mr)} | - | - | - |  ({mr[0]['error']})")
            continue
        lines.append(
            f"| {m} | {len(ok)}/{len(mr)} | {statistics.mean(r['latency_s'] for r in ok):.1f} | "
            f"{statistics.mean(r['fact_score'] for r in ok):.2f} | "
            f"{statistics.mean(r['retrieval_jaccard_vs_reference'] for r in ok):.2f} |")
    lines += ["", "## Per-query outputs", ""]
    for i, (lang, q, ref, _) in enumerate(QUERIES):
        lines += [f"### Q{i} ({lang}) {q}", f"Reference: {ref}", "",
                  "| Model | Translation | fact | overlap |", "|---|---|---|---|"]
        for m in MODELS:
            r = next(x for x in rows if x["model"] == m and x["q"] == i)
            t = (r["translation"] or f"ERROR {r['error']}").replace("\n", " ").replace("|", "/")
            lines.append(f"| {m} | {t} | {r.get('fact_score', '-')} | {r.get('retrieval_jaccard_vs_reference', '-')} |")
        lines.append("")
    (HERE / "report.md").write_text("\n".join(lines))
    print("\n".join(lines[:20]))


if __name__ == "__main__":
    main()
