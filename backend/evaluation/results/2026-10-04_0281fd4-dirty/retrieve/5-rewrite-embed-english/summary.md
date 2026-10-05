# Retrieval evaluation (deterministic checks only)

- Commit: `0281fd4` + uncommitted changes
- Collection: `indian_family_law_cases_hrag_test` | embedding: `bhavyagiri/InLegal-Sbert`
- Query translation: on (`google/gemma-3-4b-it`) | rewrite: on, embedding english | hybrid (BM25): off | corpus curation: on
- Queries: 36 | Hugging Face calls this run: 32 embedding, 0 translation, 0 rewrite

Gold lists are 'known relevant', not exhaustive, so recall and hit rates are lower bounds. 'Grouped' treats near-duplicate statute documents as one.

## Overall

| Metric | Value |
|---|---|
| Statute hit rate (at least one gold statute returned) | 0.54 |
| Statute recall, grouped | 0.34 |
| Statute recall, exact ids | 0.25 |
| Precedent hit rate (at least one gold precedent returned) | 0.09 |
| Precedent recall | 0.02 |
| Distinct statutes per query after merging duplicates (of 3) | 3 |
| Queries with an off-topic statute document | 0 of 36 |

## By language

| Language | Queries | Statute hit | Statute recall (grouped) | Precedent hit |
|---|---|---|---|---|
| en | 27 | 0.5 | 0.35 | 0.12 |
| hi | 5 | 0.8 | 0.4 | 0 |
| hi-en | 2 | 0.5 | 0.17 | 0 |
| ta | 2 | 0.5 | 0.17 | 0 |

## Language twins (same question, different language)

| Topic | Languages | Shared statutes | Shared precedents |
|---|---|---|---|
| right to reside | hi, en, ta | 0 of 6 | 0 of 13 |
| child custody | en, hi | 1 of 5 | 1 of 9 |
| dowry harassment | en, hi | 2 of 4 | 1 of 9 |
| mutual consent divorce | en, hi | 2 of 4 | 1 of 9 |
| bigamy | en, hi | 2 of 4 | 0 of 10 |

## Statute documents returned most often

| Document | Queries (of 36) |
|---|---|
| Bigamy under Indian Family Law | 16 |
| Supreme Court permits divorced Muslim women to claim maintenance under Section 125 CrPC | 13 |
| Hindu Marriage Act, 1955 – Key Provisions on Marriage, Divorce and Maintenance | 9 |
| Hindu Adoptions and Maintenance Act, 1956 – Adoption and Maintenance Provisions | 7 |
| Supreme Court rules child of Muslim‑Hindu fasid marriage entitled to father's property | 5 |
| Void Marriage – Legal Definition, Effects and Grounds | 5 |
| Supreme Court allows divorced Muslim women to claim maintenance under Section 125 CrPC | 4 |
| Supreme Court Rules Child of Muslim Man and Hindu Wife Entitled to Father's Property | 4 |

## Per query

| # | Lang | Topic | Statute hit | Precedent hit | Statutes returned |
|---|---|---|---|---|---|
| 1 | hi | right to reside | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court rules child of Muslim‑Hindu fas; Supreme Court permits divorced Muslim women t |
| 2 | en | right to reside | no | no | Supreme Court permits divorced Muslim women t; Supreme Court rules child of Muslim‑Hindu fas; Bigamy under Indian Family Law |
| 3 | ta | right to reside | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| 4 | en | child custody | no | no | Supreme Court permits divorced Muslim women t; Key Provisions of the Indian Divorce Act, 186; Bigamy under Indian Family Law |
| 5 | hi | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Key Provisions of the Indian Divorce Act, 186; Special Marriage Act, 1954 – Key Provisions |
| 6 | en | maintenance (wife) | no | no | Supreme Court permits divorced Muslim women t; Madras High Court Clarifies Date of Filing fo; Supreme Court rules child of Muslim‑Hindu fas |
| 7 | hi-en | maintenance + DV | yes | no | Protection of Women from Domestic Violence Ac; Supreme Court permits divorced Muslim women t; Prohibition of Child Marriage Act, 2006 |
| 8 | ta | maintenance amount | yes | no | Supreme Court permits divorced Muslim women t; Key Provisions of the Indian Divorce Act, 186; Hindu Marriage Act, 1955 – Key Provisions on  |
| 9 | en | dowry harassment | yes | no | Supreme Court permits divorced Muslim women t; Hindu Adoptions and Maintenance Act, 1956 – A; Dowry Prohibition Act, 1961 |
| 10 | hi | dowry harassment | yes | no | Dowry Prohibition Act, 1961; Supreme Court permits divorced Muslim women t; Supreme Court clarifies power to grant mutual |
| 11 | en | domestic violence | yes | no | Protection of Women from Domestic Violence Ac; Supreme Court permits divorced Muslim women t; Kerala HC Declares Marriage Does Not Bar POCS |
| 12 | en | mutual consent divorce | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Bigamy under Indian Family Law; Void Marriage – Legal Definition, Effects and |
| 13 | hi | mutual consent divorce | yes | no | Bigamy under Indian Family Law; Prenuptial Agreements and Their Limited Recog; Hindu Marriage Act, 1955 – Key Provisions on  |
| 14 | en | cruelty | no | no | Supreme Court allows divorced Muslim women to; Supreme Court Holds Marriage During Pendency ; Supreme Court Expands Scope of Article 142 in |
| 15 | en | divorce within one year | no | yes | Supreme Court Holds Marriage During Pendency ; Supreme Court clarifies power to grant mutual; Bigamy under Indian Family Law |
| 16 | en | bigamy | yes | no | Prohibition of Child Marriage Act, 2006; Hindu Marriage Act, 1955 – Key Provisions on ; Bigamy under Indian Family Law |
| 17 | hi | bigamy | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Void Marriage – Legal Definition, Effects and; Bigamy under Indian Family Law |
| 18 | en | restitution of conjugal rights | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Mukul Rohatgi urges Supreme Court to declare ; Supreme Court permits divorced Muslim women t |
| 19 | hi-en | interfaith court marriage | no | no | Bigamy under Indian Family Law; Supreme Court allows divorced Muslim women to; Supreme Court Rules Child of Muslim Man and H |
| 20 | en | triple talaq | no | no | Bigamy under Indian Family Law; Supreme Court Rules Child of Muslim Man and H; Void Marriage – Legal Definition, Effects and |
| 21 | en | Muslim woman maintenance | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court allows divorced Muslim women to; Supreme Court rules child of Muslim‑Hindu fas |
| 22 | en | daughter's property rights | yes | no | Ancestral Property and Coparcenary under the ; Hindu Succession Act, 1956; Hindu Minority and Guardianship Act, 1956 |
| 23 | en | interfaith child's property | yes | - | Supreme Court Rules Child of Muslim Man and H; Hindu Minority and Guardianship Act, 1956; Bigamy under Indian Family Law |
| 24 | en | annulment (impotency) | yes | no | Voidable Marriage under Indian Family Law; Supreme Court Expands Scope of Article 142 in; Void Marriage – Legal Definition, Effects and |
| 25 | en | alimony | yes | no | Supreme Court permits divorced Muslim women t; Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on  |
| 26 | en | stridhan | no | no | Child born of marriage between Muslim man and; Abolition of Triple Talaq in India: Judicial ; Bigamy under Indian Family Law |
| 27 | en | 498A defence | - | no | Abolition of Triple Talaq in India: Judicial ; Supreme Court permits divorced Muslim women t; Hindu Succession Act, 1956 – Intestate Inheri |
| 28 | en | desertion | no | no | Voidable Marriage under Indian Family Law; Hindu Adoptions and Maintenance Act, 1956 – A; Bigamy under Indian Family Law |
| 29 | en | live-in relationship | no | no | Supreme Court Rules Child of Muslim Man and H; Bigamy under Indian Family Law; Mukul Rohatgi urges Supreme Court to declare  |
| 30 | en | visitation rights | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court permits divorced Muslim women t; Supreme Court rules child of Muslim‑Hindu fas |
| 31 | en | foreign divorce validity | no | yes | Voidable Marriage under Indian Family Law; Bigamy under Indian Family Law; Supreme Court Holds Marriage During Pendency  |
| 32 | en | adoption | yes | no | Ancestral Property and Coparcenary under the ; Abolition of Triple Talaq in India: Judicial ; Hindu Adoptions and Maintenance Act, 1956 – A |
| 33 | en | guardianship | yes | no | Hindu Minority and Guardianship Act, 1956; Guardians and Wards Act, 1890 – Key Provision; Hindu Succession Act, 1956 |
| 34 | en | child marriage | no | no | Bigamy under Indian Family Law; Hindu Marriage Act, 1955 – Provisions, Applic; Voidable Marriage under Indian Family Law |
| 35 | en | same-sex marriage | no | - | Void Marriage – Legal Definition, Effects and; Bigamy under Indian Family Law; Hindu Marriage Act, 1955 – Key Provisions on  |
| 36 | en | free legal aid | yes | - | Legal Services Authorities Act, 1987 – Free L; Supreme Court allows divorced Muslim women to; Supreme Court clarifies power to grant mutual |
