# Retrieval evaluation (deterministic checks only)

- Commit: `0281fd4` + uncommitted changes
- Collection: `indian_family_law_cases_hrag_v2` | embedding: `bhavyagiri/InLegal-Sbert`
- Query translation: on (`google/gemma-3-4b-it`) | rewrite: off | hybrid (BM25): off | corpus curation: on
- Queries: 36 | Hugging Face calls this run: 0 embedding, 0 translation, 0 rewrite

Gold lists are 'known relevant', not exhaustive, so recall and hit rates are lower bounds. 'Grouped' treats near-duplicate statute documents as one.

## Overall

| Metric | Value |
|---|---|
| Statute hit rate (at least one gold statute returned) | 0.6 |
| Statute recall, grouped | 0.35 |
| Statute recall, exact ids | 0.27 |
| Precedent hit rate (at least one gold precedent returned) | 0.36 |
| Precedent recall | 0.1 |
| Distinct statutes per query after merging duplicates (of 3) | 3 |
| Queries with an off-topic statute document | 0 of 36 |

## By language

| Language | Queries | Statute hit | Statute recall (grouped) | Precedent hit |
|---|---|---|---|---|
| en | 27 | 0.62 | 0.38 | 0.38 |
| hi | 5 | 0.8 | 0.43 | 0.2 |
| hi-en | 2 | 0.5 | 0.17 | 0.5 |
| ta | 2 | 0 | 0.0 | 0.5 |

## Language twins (same question, different language)

| Topic | Languages | Shared statutes | Shared precedents |
|---|---|---|---|
| right to reside | hi, en, ta | 0 of 6 | 0 of 12 |
| child custody | en, hi | 0 of 6 | 1 of 9 |
| dowry harassment | en, hi | 0 of 6 | 0 of 10 |
| mutual consent divorce | en, hi | 0 of 6 | 0 of 10 |
| bigamy | en, hi | 1 of 5 | 1 of 9 |

## Statute documents returned most often

| Document | Queries (of 36) |
|---|---|
| Kerala HC Declares Marriage Does Not Bar POCSO Rape Prosecution of Minor | 10 |
| Hindu Marriage Act, 1955 – Key Provisions on Marriage, Divorce and Maintenance | 9 |
| Hindu Adoptions and Maintenance Act, 1956 – Adoption and Maintenance Provisions | 8 |
| Supreme Court Rules Divorced Muslim Women Entitled to Maintenance Under Section 125 CrPC | 7 |
| Supreme Court Directions on Queer Rights and Marriage Equality | 7 |
| Voidable Marriage under Indian Family Law | 6 |
| Parsi Marriage and Divorce Act, 1936 | 6 |
| Bigamy under Indian Family Law | 5 |

## Per query

| # | Lang | Topic | Statute hit | Precedent hit | Statutes returned |
|---|---|---|---|---|---|
| 1 | hi | right to reside | no | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Supreme Court permits divorced Muslim women t |
| 2 | en | right to reside | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Child born of marriage between Muslim man and; Supreme Court Rules Divorced Muslim Women Ent |
| 3 | ta | right to reside | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court permits divorced Muslim women t; Hindu Marriage Act, 1955 – Key Provisions on  |
| 4 | en | child custody | no | no | Legal Status of Polygamy in India; Bigamy under Indian Family Law; Voidable Marriage under Indian Family Law |
| 5 | hi | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Hindu Adoptions and Maintenance Act, 1956 – A; Child born of marriage between Muslim man and |
| 6 | en | maintenance (wife) | yes | no | Supreme Court Rules Divorced Muslim Women Ent; Hindu Adoptions and Maintenance Act, 1956 – A; Kerala HC Declares Marriage Does Not Bar POCS |
| 7 | hi-en | maintenance + DV | yes | no | Supreme Court Directions on Queer Rights and ; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rules Child of Muslim Man and H |
| 8 | ta | maintenance amount | no | no | Supreme Court Holds Marriage During Pendency ; Bigamy under Indian Family Law; Lok Adalat – Statutory Alternative Dispute Re |
| 9 | en | dowry harassment | no | no | Supreme Court Directions on Queer Rights and ; Kerala HC Declares Marriage Does Not Bar POCS; Supreme Court Rules Divorced Muslim Women Ent |
| 10 | hi | dowry harassment | yes | no | Mahr as a Mandatory Bride‑Wealth Obligation u; Dowry Prohibition Act, 1961; Voidable Marriage under Indian Family Law |
| 11 | en | domestic violence | yes | no | Protection of Women from Domestic Violence Ac; Kerala HC Declares Marriage Does Not Bar POCS; Supreme Court Allows Divorced Muslim Women to |
| 12 | en | mutual consent divorce | no | no | Bigamy under Indian Family Law; Legal Status of Polygamy in India; Voidable Marriage under Indian Family Law |
| 13 | hi | mutual consent divorce | yes | no | Key Provisions of the Indian Divorce Act, 186; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Expands Scope of Article 142 in |
| 14 | en | cruelty | no | no | Voidable Marriage under Indian Family Law; Parsi Marriage and Divorce Act, 1936; Madras High Court: Marriage is Primarily for  |
| 15 | en | divorce within one year | yes | yes | Parsi Marriage and Divorce Act, 1936; Supreme Court Holds Marriage During Pendency ; Hindu Marriage Act, 1955 – Key Provisions on  |
| 16 | en | bigamy | yes | no | Special Marriage Act, 1954 – Key Provisions; Parsi Marriage and Divorce Act, 1936; Hindu Marriage Act, 1955 – Key Provisions on  |
| 17 | hi | bigamy | yes | no | Supreme Court Rejects Marriage Equality and A; Supreme Court Directions on Queer Rights and ; Hindu Marriage Act, 1955 – Key Provisions on  |
| 18 | en | restitution of conjugal rights | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Directions on Queer Rights and ; Restitution of Conjugal Rights – Historical D |
| 19 | hi-en | interfaith court marriage | no | yes | Supreme Court Rules Child of Muslim Man and H; Mahr as a Mandatory Bride‑Wealth Obligation u; Kerala HC Declares Marriage Does Not Bar POCS |
| 20 | en | triple talaq | no | no | Kerala HC Declares Marriage Does Not Bar POCS; Supreme Court Marriage Equality Case: Mukul R; Supreme Court Rejects Marriage Equality and A |
| 21 | en | Muslim woman maintenance | yes | yes | Supreme Court Rules Divorced Muslim Women Ent; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Allows Single‑Bench Divorce Dec |
| 22 | en | daughter's property rights | yes | yes | Supreme Court Rules Child of Muslim Man and H; Hindu Minority and Guardianship Act, 1956; Ancestral Property and Coparcenary under the  |
| 23 | en | interfaith child's property | yes | - | Supreme Court Rules Child of Muslim Man and H; Hindu Minority and Guardianship Act, 1956; Kerala HC Declares Marriage Does Not Bar POCS |
| 24 | en | annulment (impotency) | yes | no | Voidable Marriage under Indian Family Law; Kerala HC Declares Marriage Does Not Bar POCS; Supreme Court Rules Child of Muslim Man and H |
| 25 | en | alimony | yes | no | Alimony – Legal Obligation of Spousal Support; Parsi Marriage and Divorce Act, 1936; Special Marriage Act, 1954 – Key Provisions |
| 26 | en | stridhan | no | yes | Supreme Court Rules Divorced Muslim Women Ent; Supreme Court Directions on Queer Rights and ; Ancestral Property and Coparcenary under the  |
| 27 | en | 498A defence | - | no | Kerala HC Declares Marriage Does Not Bar POCS; Supreme Court Directions on Queer Rights and ; Supreme Court Rules Divorced Muslim Women Ent |
| 28 | en | desertion | yes | no | Parsi Marriage and Divorce Act, 1936; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Rules Divorced Muslim Women Ent |
| 29 | en | live-in relationship | yes | yes | Prenuptial Agreements and Their Limited Recog; Kerala HC Declares Marriage Does Not Bar POCS; Protection of Women from Domestic Violence Ac |
| 30 | en | visitation rights | no | no | Supreme Court Directions on Queer Rights and ; Hindu Adoptions and Maintenance Act, 1956 – A; Kerala HC Declares Marriage Does Not Bar POCS |
| 31 | en | foreign divorce validity | no | yes | Bigamy under Indian Family Law; Voidable Marriage under Indian Family Law; Parsi Marriage and Divorce Act, 1936 |
| 32 | en | adoption | yes | no | Bigamy under Indian Family Law; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rejects Marriage Equality and A |
| 33 | en | guardianship | yes | yes | Hindu Minority and Guardianship Act, 1956; Mahr as a Mandatory Bride‑Wealth Obligation u; Hindu Succession Act, 1956 – Intestate Inheri |
| 34 | en | child marriage | no | no | Special Marriage Act, 1954 (India); Supreme Court Rejects Marriage Equality and A; Hindu Marriage Act, 1955 – Key Provisions on  |
| 35 | en | same-sex marriage | yes | - | Supreme Court Rejects Marriage Equality and A; Void Marriage – Legal Definition, Effects and; Legal Status of Polygamy in India |
| 36 | en | free legal aid | yes | - | Justice Sanjiv Khanna Recuses from Supreme Co; Legal Services Authorities Act, 1987 – Free L; Supreme Court Marriage Equality Case: Mukul R |
