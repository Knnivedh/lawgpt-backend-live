# Query-translation model comparison

> **INCOMPLETE RUN.** The HF account hit its monthly Inference Providers credit limit (HTTP 402) partway through, so most models have 0 results and gemma-3-4b / Llama-3.1-8B were scored on different subsets of the queries (`OK` column). The table below is NOT a like-for-like comparison. Re-run `python translation_model_comparison/compare.py` after credits are restored. Qwen2.5-7B is also not enabled for this account (400).

12 queries (hi, ta, te, bn, mr, gu, plus Hinglish/Tanglish code-mixed). Same system prompt and temperature 0 for every model, via the HF router.

- **fact**: share of must-preserve checks (negation, relationship, year/number, legal term) present in the output.
- **retrieval overlap**: Jaccard of retrieved parent_ids vs retrieval from a hand-written reference English query (1.0 = identical results).
- **Untranslated baseline** retrieval overlap vs reference: mean **0.00**.

| Model | OK | Mean latency (s) | Fact score | Retrieval overlap |
|---|---|---|---|---|
| google/gemma-3-4b-it | 9/12 | 1.8 | 1.00 | 0.34 |
| google/gemma-3-12b-it | 0/12 | - | - | - |  (402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide)
| google/gemma-3-27b-it | 0/12 | - | - | - |  (402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide)
| meta-llama/Llama-3.1-8B-Instruct | 9/12 | 1.4 | 0.89 | 0.25 |
| meta-llama/Llama-3.3-70B-Instruct | 0/12 | - | - | - |  (402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide)
| Qwen/Qwen3-32B | 0/12 | - | - | - |  (402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide)
| Qwen/Qwen2.5-7B-Instruct | 0/12 | - | - | - |  (400: {"error":{"message":"The requested model 'Qwen/Qwen2.5-7B-Instruct' is not supported by any provider you have enabled.",)
| Qwen/Qwen2.5-72B-Instruct | 0/12 | - | - | - |  (402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide)

## Per-query outputs

### Q0 (hi) तलाक के बाद बच्चे की कस्टडी किसे मिलती है?
Reference: Who gets custody of the child after divorce?

| Model | Translation | fact | overlap |
|---|---|---|---|
| google/gemma-3-4b-it | Who gets custody of the child after a divorce? | 1.0 | 0.8 |
| google/gemma-3-12b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| google/gemma-3-27b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| meta-llama/Llama-3.1-8B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| meta-llama/Llama-3.3-70B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen3-32B | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen2.5-7B-Instruct | ERROR 400: {"error":{"message":"The requested model 'Qwen/Qwen2.5-7B-Instruct' is not supported by any provider you have enabled.", | - | - |
| Qwen/Qwen2.5-72B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |

### Q1 (hi) मेरे पति ने मुझे तलाक का नोटिस नहीं दिया है, क्या मैं भरण-पोषण मांग सकती हूँ?
Reference: My husband has not given me a divorce notice; can I claim maintenance?

| Model | Translation | fact | overlap |
|---|---|---|---|
| google/gemma-3-4b-it | My husband has not served me with a divorce notice, can I claim maintenance? | 1.0 | 0.2 |
| google/gemma-3-12b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| google/gemma-3-27b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| meta-llama/Llama-3.1-8B-Instruct | My husband has not given me a notice of divorce, can I ask for maintenance? | 1.0 | 0.2 |
| meta-llama/Llama-3.3-70B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen3-32B | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen2.5-7B-Instruct | ERROR 400: {"error":{"message":"The requested model 'Qwen/Qwen2.5-7B-Instruct' is not supported by any provider you have enabled.", | - | - |
| Qwen/Qwen2.5-72B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |

### Q2 (hi) दहेज उत्पीड़न की शिकायत कैसे दर्ज करें?
Reference: How do I file a complaint of dowry harassment?

| Model | Translation | fact | overlap |
|---|---|---|---|
| google/gemma-3-4b-it | How to file a complaint about dowry harassment? | 1.0 | 0.111 |
| google/gemma-3-12b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| google/gemma-3-27b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| meta-llama/Llama-3.1-8B-Instruct | How to lodge a complaint of dowry harassment? | 1.0 | 0.125 |
| meta-llama/Llama-3.3-70B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen3-32B | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen2.5-7B-Instruct | ERROR 400: {"error":{"message":"The requested model 'Qwen/Qwen2.5-7B-Instruct' is not supported by any provider you have enabled.", | - | - |
| Qwen/Qwen2.5-72B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |

### Q3 (hi) मेरी शादी 2019 में हुई थी और मेरे ससुराल वालों ने मुझे 2023 में घर से निकाल दिया, क्या मुझे घर में रहने का अधिकार है?
Reference: I got married in 2019 and my in-laws threw me out of the house in 2023; do I have a right to reside in the house?

| Model | Translation | fact | overlap |
|---|---|---|---|
| google/gemma-3-4b-it | My marriage took place in 2019, and my in-laws evicted me from the house in 2023, do I have the right to reside in the house? | 1.0 | 0.4 |
| google/gemma-3-12b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| google/gemma-3-27b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| meta-llama/Llama-3.1-8B-Instruct | My marriage took place in 2019 and my in-laws evicted me from the house in 2023, do I have the right to live in the house? | 1.0 | 0.286 |
| meta-llama/Llama-3.3-70B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen3-32B | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen2.5-7B-Instruct | ERROR 400: {"error":{"message":"The requested model 'Qwen/Qwen2.5-7B-Instruct' is not supported by any provider you have enabled.", | - | - |
| Qwen/Qwen2.5-72B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |

### Q4 (ta) விவாகரத்திற்குப் பிறகு பராமரிப்புத் தொகை எப்படி நிர்ணயிக்கப்படுகிறது?
Reference: How is the maintenance amount determined after divorce?

| Model | Translation | fact | overlap |
|---|---|---|---|
| google/gemma-3-4b-it | How is maintenance amount determined after a divorce? | 1.0 | 0.333 |
| google/gemma-3-12b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| google/gemma-3-27b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| meta-llama/Llama-3.1-8B-Instruct | After the marriage certificate, how is the maintenance allowance determined? | 0.5 | 0.0 |
| meta-llama/Llama-3.3-70B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen3-32B | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen2.5-7B-Instruct | ERROR 400: {"error":{"message":"The requested model 'Qwen/Qwen2.5-7B-Instruct' is not supported by any provider you have enabled.", | - | - |
| Qwen/Qwen2.5-72B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |

### Q5 (te) గృహ హింస చట్టం కింద ఫిర్యాదు ఎలా చేయాలి?
Reference: How do I file a complaint under the domestic violence act?

| Model | Translation | fact | overlap |
|---|---|---|---|
| google/gemma-3-4b-it | How to file a complaint under the Protection of Women from Domestic Violence Act? | 1.0 | 0.111 |
| google/gemma-3-12b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| google/gemma-3-27b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| meta-llama/Llama-3.1-8B-Instruct | How to file a complaint under the Domestic Violence Act? | 1.0 | 0.125 |
| meta-llama/Llama-3.3-70B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen3-32B | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen2.5-7B-Instruct | ERROR 400: {"error":{"message":"The requested model 'Qwen/Qwen2.5-7B-Instruct' is not supported by any provider you have enabled.", | - | - |
| Qwen/Qwen2.5-72B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |

### Q6 (bn) বিবাহবিচ্ছেদের পর সন্তানের অভিভাবকত্ব কীভাবে নির্ধারিত হয়?
Reference: How is custody of the child determined after divorce?

| Model | Translation | fact | overlap |
|---|---|---|---|
| google/gemma-3-4b-it | How is custody of a child determined after a divorce? | 1.0 | 0.4 |
| google/gemma-3-12b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| google/gemma-3-27b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| meta-llama/Llama-3.1-8B-Instruct | How is the custodianship of a child determined after a divorce? | 0.5 | 0.286 |
| meta-llama/Llama-3.3-70B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen3-32B | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen2.5-7B-Instruct | ERROR 400: {"error":{"message":"The requested model 'Qwen/Qwen2.5-7B-Instruct' is not supported by any provider you have enabled.", | - | - |
| Qwen/Qwen2.5-72B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |

### Q7 (mr) माझ्या पतीने मला घटस्फोट दिलेला नाही पण तो दुसरे लग्न करत आहे, हे कायदेशीर आहे का?
Reference: My husband has not given me a divorce but he is marrying again; is this legal?

| Model | Translation | fact | overlap |
|---|---|---|---|
| google/gemma-3-4b-it | Is it legal for my husband not to have given me a divorce, but for him to be marrying another woman? | 1.0 | 0.143 |
| google/gemma-3-12b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| google/gemma-3-27b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| meta-llama/Llama-3.1-8B-Instruct | My husband has not given me a talaq, but he is getting married to another woman, is this legal? | 1.0 | 0.143 |
| meta-llama/Llama-3.3-70B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen3-32B | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen2.5-7B-Instruct | ERROR 400: {"error":{"message":"The requested model 'Qwen/Qwen2.5-7B-Instruct' is not supported by any provider you have enabled.", | - | - |
| Qwen/Qwen2.5-72B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |

### Q8 (hi-en) Mera husband domestic violence karta hai, maintenance kaise le sakti hoon?
Reference: My husband commits domestic violence; how can I get maintenance?

| Model | Translation | fact | overlap |
|---|---|---|---|
| google/gemma-3-4b-it | My husband is committing domestic violence, how can I get maintenance? | 1.0 | 0.6 |
| google/gemma-3-12b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| google/gemma-3-27b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| meta-llama/Llama-3.1-8B-Instruct | My husband is doing domestic violence, how can I get maintenance? | 1.0 | 0.5 |
| meta-llama/Llama-3.3-70B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen3-32B | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen2.5-7B-Instruct | ERROR 400: {"error":{"message":"The requested model 'Qwen/Qwen2.5-7B-Instruct' is not supported by any provider you have enabled.", | - | - |
| Qwen/Qwen2.5-72B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |

### Q9 (hi-en) Meri wife ne mujhe chhod diya hai aur 5 saal se alag rehti hai, kya main divorce le sakta hoon?
Reference: My wife has left me and has been living separately for 5 years; can I get a divorce?

| Model | Translation | fact | overlap |
|---|---|---|---|
| google/gemma-3-4b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| google/gemma-3-12b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| google/gemma-3-27b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| meta-llama/Llama-3.1-8B-Instruct | My wife has left me and we have been separated for 5 years, can I get a divorce? | 1.0 | 0.6 |
| meta-llama/Llama-3.3-70B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen3-32B | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen2.5-7B-Instruct | ERROR 400: {"error":{"message":"The requested model 'Qwen/Qwen2.5-7B-Instruct' is not supported by any provider you have enabled.", | - | - |
| Qwen/Qwen2.5-72B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |

### Q10 (ta-en) Divorce case ல custody எப்படி decide பண்றாங்க?
Reference: How is custody decided in a divorce case?

| Model | Translation | fact | overlap |
|---|---|---|---|
| google/gemma-3-4b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| google/gemma-3-12b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| google/gemma-3-27b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| meta-llama/Llama-3.1-8B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| meta-llama/Llama-3.3-70B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen3-32B | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen2.5-7B-Instruct | ERROR 400: {"error":{"message":"The requested model 'Qwen/Qwen2.5-7B-Instruct' is not supported by any provider you have enabled.", | - | - |
| Qwen/Qwen2.5-72B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |

### Q11 (gu) શું પત્ની પતિની મિલકતમાં ભાગ માંગી શકે છે, જો લગ્ન 10 વર્ષ પહેલાં થયા હોય?
Reference: Can a wife claim a share in her husband's property if the marriage took place 10 years ago?

| Model | Translation | fact | overlap |
|---|---|---|---|
| google/gemma-3-4b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| google/gemma-3-12b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| google/gemma-3-27b-it | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| meta-llama/Llama-3.1-8B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| meta-llama/Llama-3.3-70B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen3-32B | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
| Qwen/Qwen2.5-7B-Instruct | ERROR 400: {"error":{"message":"The requested model 'Qwen/Qwen2.5-7B-Instruct' is not supported by any provider you have enabled.", | - | - |
| Qwen/Qwen2.5-72B-Instruct | ERROR 402: {"error":"You have depleted your monthly included credits. Purchase pre-paid credits to continue using Inference Provide | - | - |
