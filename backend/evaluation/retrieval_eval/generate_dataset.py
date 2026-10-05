"""
Generates retrieval_eval/golden_dataset.csv for evaluating
nodes/retriever.py::retrieve_documents().

Gold documents are real parent_ids from the corpus. Law/act gold ids come
from the family_law_2 category (statutes and case-law digests); case gold
ids are Kaanoon-style Q&A posts from family_law, picked by title search and
hand-filtered. Titles are looked up from data/chunked/*.json at generation
time, and the script fails if any id does not exist, so the dataset can't
silently point at missing documents.

List cells use " | ". Gold lists are "known relevant", not "the only
relevant" documents: other on-topic results are fine and should be judged
by the LLM judge, not counted as misses.
"""

import csv
import json
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]

# (topic, language, query, gold_law_ids, gold_case_ids, notes)
ROWS = [
    ("right to reside", "hi", "मेरी शादी 2019 में हुई थी और मेरे ससुराल वालों ने मुझे 2023 में घर से निकाल दिया, क्या मुझे घर में रहने का अधिकार है?",
     [2930, 2952], [754, 1016, 1333, 1374, 2845], "Exact query from manual testing."),
    ("right to reside", "en", "Do I have the right to stay in my husband's house after my in-laws threw me out?",
     [2930, 2952], [754, 1016, 1333, 1374, 2845], "English twin of row 1 (translation consistency)."),
    ("right to reside", "ta", "என் மாமியார் வீட்டிலிருந்து என்னை வெளியேற்றினார்கள், நான் அங்கு வசிக்க உரிமை உண்டா?",
     [2930, 2952], [754, 1016, 1333, 1374, 2845], "Tamil twin of row 1."),
    ("child custody", "en", "How is child custody decided after divorce in India?",
     [2934, 2955, 2931, 2954], [7, 70, 131, 165], ""),
    ("child custody", "hi", "तलाक के बाद बच्चे की कस्टडी किसे मिलती है?",
     [2934, 2955, 2931, 2954], [7, 70, 131, 165], "Hindi twin of the custody row."),
    ("maintenance (wife)", "en", "Can a wife claim maintenance under Section 125 CrPC if her husband left her?",
     [2950, 2953, 2968, 2933], [17, 53, 68, 86, 113], ""),
    ("maintenance + DV", "hi-en", "Mera husband domestic violence karta hai, maintenance kaise le sakti hoon?",
     [2930, 2952, 2950, 2953], [217, 86, 9, 175], "Code-mixed."),
    ("maintenance amount", "ta", "விவாகரத்திற்குப் பிறகு பராமரிப்புத் தொகை எப்படி நிர்ணயிக்கப்படுகிறது?",
     [2950, 2953, 2933], [107, 17, 113], ""),
    ("dowry harassment", "en", "How do I file a complaint for dowry harassment by my in-laws?",
     [2957, 2930, 2952], [9, 175, 37, 82], ""),
    ("dowry harassment", "hi", "दहेज उत्पीड़न की शिकायत कैसे दर्ज करें?",
     [2957, 2930, 2952], [9, 175, 37, 82], "Hindi twin."),
    ("domestic violence", "en", "My husband beats me. What protection can I get under the domestic violence act?",
     [2930, 2952], [9, 175, 70, 40], ""),
    ("mutual consent divorce", "en", "What is the procedure for mutual consent divorce?",
     [2950, 2983, 2984, 2985], [69, 123, 16], ""),
    ("mutual consent divorce", "hi", "आपसी सहमति से तलाक कैसे लें?",
     [2950, 2983, 2984, 2985], [69, 123, 16], "Hindi twin."),
    ("cruelty", "en", "Can I get a divorce on grounds of mental cruelty by my wife?",
     [2950], [312, 337, 603, 769], ""),
    ("divorce within one year", "en", "Can I file for divorce before one year of marriage?",
     [2950], [575, 1735, 2146, 2850], ""),
    ("bigamy", "en", "My husband is marrying again without divorcing me. Is it legal?",
     [2940, 2939, 2950], [80, 225, 261, 164], ""),
    ("bigamy", "hi", "मेरे पति दूसरी शादी कर रहे हैं जबकि हमारा तलाक नहीं हुआ है, मैं क्या करूँ?",
     [2940, 2939, 2950], [80, 225, 261, 164], "Hindi twin."),
    ("restitution of conjugal rights", "en", "My husband filed for restitution of conjugal rights. How should I respond?",
     [2941, 2950], [106, 509, 1170, 1840], ""),
    ("interfaith court marriage", "hi-en", "Court marriage karni hai, ladka Muslim hai aur main Hindu hoon, kya process hai?",
     [2927, 2951, 2966, 3008], [381, 151, 453], "Code-mixed."),
    ("triple talaq", "en", "My husband gave me triple talaq over the phone. Is it valid?",
     [2937], [146, 413, 41, 445], ""),
    ("Muslim woman maintenance", "en", "Can a divorced Muslim woman claim maintenance from her ex-husband?",
     [2962, 2986, 2987, 2988, 2959], [41, 186, 445], "2986/2987/2988 are near-duplicate articles; see dataset_info."),
    ("daughter's property rights", "en", "Does a daughter have equal rights in her father's ancestral property?",
     [2932, 2960, 2969], [1059, 1553, 1111], ""),
    ("interfaith child's property", "en", "Is a child of a Muslim father and Hindu mother entitled to the father's property?",
     [2989, 2990, 2991, 2992], [], "No clearly matching case posts found; judge case results on relevance only."),
    ("annulment (impotency)", "en", "Can I annul my marriage because my husband is impotent and it was never consummated?",
     [2942, 2943], [117, 124, 276, 458], ""),
    ("alimony", "en", "How much permanent alimony can a wife get after divorce?",
     [2933, 2950], [223, 235, 318, 324], ""),
    ("stridhan", "en", "My in-laws are not returning my jewellery and stridhan. What can I do?",
     [2930, 2957], [219, 1552, 2083, 904], ""),
    ("498A defence", "en", "My wife filed a false 498A case against me and my parents. What are my options?",
     [], [177, 226, 79, 8, 18], "No IPC/BNS statute document exists in family_law_2; law results judged on relevance only."),
    ("desertion", "en", "My husband deserted me 3 years ago. Can I get a divorce on grounds of desertion?",
     [2950], [30, 534, 1133, 1088], ""),
    ("live-in relationship", "en", "What are the legal rights of a woman in a live-in relationship?",
     [3008, 2930], [171, 930, 27], ""),
    ("visitation rights", "en", "My wife is not letting me meet my child. How can I get visitation rights?",
     [2934, 2955], [154, 161, 180, 663], ""),
    ("foreign divorce validity", "en", "My husband lives in the USA and filed for divorce there. Is it valid in India?",
     [2950], [87, 23, 178, 148], ""),
    ("adoption", "en", "What is the procedure to adopt a child as a Hindu couple?",
     [2953, 2975], [150, 234, 354], ""),
    ("guardianship", "en", "As a single mother, how can I become the sole legal guardian of my son?",
     [2931, 2954, 2955], [2052, 26, 1847], ""),
    ("child marriage", "en", "My parents are forcing my 16 year old sister to marry. What can we do?",
     [2961], [893, 1392], ""),
    ("same-sex marriage", "en", "Can same-sex couples legally marry in India?",
     [2995, 3004, 2997, 2964], [], "Law/case-law digest topic only."),
    ("free legal aid", "en", "How can I get free legal aid for my divorce case?",
     [2948, 2947], [], "Law/act topic only."),
]

FIELDNAMES = ["id", "topic", "language", "query", "gold_law_parent_ids", "gold_law_titles",
              "gold_case_parent_ids", "gold_case_titles", "notes"]


def load_titles():
    titles = {}
    for name in ("family_law_chunks.json", "family_law_2_chunks.json"):
        for item in json.load(open(BACKEND / "data" / "chunked" / name, encoding="utf-8")):
            md = item["metadata"]
            if md.get("is_parent"):
                titles[md["parent_id"]] = md["title"]
    return titles


def main():
    titles = load_titles()
    missing = sorted({pid for r in ROWS for pid in r[3] + r[4] if pid not in titles})
    if missing:
        raise SystemExit(f"Unknown parent_ids (not in corpus): {missing}")

    law_bucket = {pid for pid in titles if pid >= 2926}  # family_law_2 parent_ids start at 2926
    bad_law = sorted({pid for r in ROWS for pid in r[3] if pid not in law_bucket})
    bad_case = sorted({pid for r in ROWS for pid in r[4] if pid in law_bucket})
    if bad_law or bad_case:
        raise SystemExit(f"Bucket mismatch — law ids not in family_law_2: {bad_law}; case ids in family_law_2: {bad_case}")

    out = Path(__file__).resolve().parent / "golden_dataset.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for i, (topic, lang, query, law, case, notes) in enumerate(ROWS, 1):
            w.writerow(dict(
                id=i, topic=topic, language=lang, query=query,
                gold_law_parent_ids=" | ".join(map(str, law)),
                gold_law_titles=" | ".join(titles[p] for p in law),
                gold_case_parent_ids=" | ".join(map(str, case)),
                gold_case_titles=" | ".join(titles[p] for p in case),
                notes=notes,
            ))
    print(f"Wrote {len(ROWS)} rows to {out}")
    print("Language counts:", Counter(r[1] for r in ROWS))


if __name__ == "__main__":
    main()
