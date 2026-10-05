# Retrieval evaluation (deterministic checks only)

- Commit: `0281fd4` + uncommitted changes
- Collection: `indian_family_law_cases_hrag_test` | embedding: `bhavyagiri/InLegal-Sbert`
- Query translation: on (`google/gemma-3-4b-it`) | rewrite: off | hybrid (BM25): off | corpus curation: on
- Queries: 36 | Hugging Face calls this run: 8 embedding, 9 translation, 0 rewrite

Gold lists are 'known relevant', not exhaustive, so recall and hit rates are lower bounds. 'Grouped' treats near-duplicate statute documents as one.

## Overall

| Metric | Value |
|---|---|
| Statute hit rate (at least one gold statute returned) | 0.63 |
| Statute recall, grouped | 0.45 |
| Statute recall, exact ids | 0.34 |
| Precedent hit rate (at least one gold precedent returned) | 0.15 |
| Precedent recall | 0.04 |
| Distinct statutes per query after merging duplicates (of 3) | 3 |
| Queries with an off-topic statute document | 0 of 36 |

## By language

| Language | Queries | Statute hit | Statute recall (grouped) | Precedent hit |
|---|---|---|---|---|
| en | 27 | 0.65 | 0.5 | 0.12 |
| hi | 5 | 0.8 | 0.4 | 0.2 |
| hi-en | 2 | 0.5 | 0.33 | 0.5 |
| ta | 2 | 0 | 0.0 | 0 |

## Language twins (same question, different language)

| Topic | Languages | Shared statutes | Shared precedents |
|---|---|---|---|
| right to reside | hi, en, ta | 1 of 5 | 0 of 9 |
| child custody | en, hi | 1 of 5 | 0 of 10 |
| dowry harassment | en, hi | 2 of 4 | 0 of 10 |
| mutual consent divorce | en, hi | 2 of 4 | 1 of 9 |
| bigamy | en, hi | 1 of 5 | 1 of 9 |

## Statute documents returned most often

| Document | Queries (of 36) |
|---|---|
| Hindu Marriage Act, 1955 – Key Provisions on Marriage, Divorce and Maintenance | 16 |
| Supreme Court permits divorced Muslim women to claim maintenance under Section 125 CrPC | 16 |
| Bigamy under Indian Family Law | 13 |
| Hindu Adoptions and Maintenance Act, 1956 – Adoption and Maintenance Provisions | 5 |
| Abolition of Triple Talaq in India: Judicial and Legislative Milestones | 5 |
| Child born of marriage between Muslim man and Hindu woman entitled to claim father's property: Supreme Court | 4 |
| Hindu Minority and Guardianship Act, 1956 | 4 |
| Voidable Marriage under Indian Family Law | 4 |

## Per query

| # | Lang | Topic | Statute hit | Precedent hit | Statutes returned |
|---|---|---|---|---|---|
| 1 | hi | right to reside | no | yes | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court permits divorced Muslim women t |
| 2 | en | right to reside | no | yes | Child born of marriage between Muslim man and; Hindu Succession Act, 1956 – Intestate Inheri; Hindu Marriage Act, 1955 – Key Provisions on  |
| 3 | ta | right to reside | no | no | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court permits divorced Muslim women t |
| 4 | en | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Mukul Rohatgi urges Supreme Court to declare ; Supreme Court permits divorced Muslim women t |
| 5 | hi | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Hindu Minority and Guardianship Act, 1956; Bigamy under Indian Family Law |
| 6 | en | maintenance (wife) | no | no | Supreme Court permits divorced Muslim women t; Madras High Court Clarifies Date of Filing fo; Supreme Court rules child of Muslim‑Hindu fas |
| 7 | hi-en | maintenance + DV | yes | no | Protection of Women from Domestic Violence Ac; Prohibition of Child Marriage Act, 2006; Hindu Marriage Act, 1955 – Key Provisions on  |
| 8 | ta | maintenance amount | no | no | Bigamy under Indian Family Law; Supreme Court permits divorced Muslim women t; Mahr as a Mandatory Bride‑Wealth Obligation u |
| 9 | en | dowry harassment | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court permits divorced Muslim women t; Dowry Prohibition Act, 1961 |
| 10 | hi | dowry harassment | yes | no | Dowry Prohibition Act, 1961; Supreme Court clarifies power to grant mutual; Supreme Court permits divorced Muslim women t |
| 11 | en | domestic violence | yes | no | Protection of Women from Domestic Violence Ac; Supreme Court permits divorced Muslim women t; Hindu Marriage Act, 1955 – Key Provisions on  |
| 12 | en | mutual consent divorce | yes | no | Bigamy under Indian Family Law; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court clarifies power to grant mutual |
| 13 | hi | mutual consent divorce | yes | no | Bigamy under Indian Family Law; Prenuptial Agreements and Their Limited Recog; Hindu Marriage Act, 1955 – Key Provisions on  |
| 14 | en | cruelty | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Voidable Marriage under Indian Family Law; Key Provisions of the Indian Divorce Act, 186 |
| 15 | en | divorce within one year | no | no | Voidable Marriage under Indian Family Law; Bigamy under Indian Family Law; Supreme Court clarifies power to grant mutual |
| 16 | en | bigamy | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Bigamy under Indian Family Law |
| 17 | hi | bigamy | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Abolition of Triple Talaq in India: Judicial ; Restitution of Conjugal Rights – Historical D |
| 18 | en | restitution of conjugal rights | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court permits divorced Muslim women t; Mukul Rohatgi urges Supreme Court to declare  |
| 19 | hi-en | interfaith court marriage | no | yes | Bigamy under Indian Family Law; Supreme Court Rules Child of Muslim Man and H; Supreme Court Rules Divorced Muslim Women Ent |
| 20 | en | triple talaq | yes | no | Abolition of Triple Talaq in India: Judicial ; Bigamy under Indian Family Law; Legal Status of Polygamy in India |
| 21 | en | Muslim woman maintenance | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court allows divorced Muslim women to; Supreme Court rules child of Muslim‑Hindu fas |
| 22 | en | daughter's property rights | yes | no | Ancestral Property and Coparcenary under the ; Hindu Succession Act, 1956; Hindu Minority and Guardianship Act, 1956 |
| 23 | en | interfaith child's property | yes | - | Supreme Court Rules Child of Muslim Man and H; Hindu Succession Act, 1956; Hindu Minority and Guardianship Act, 1956 |
| 24 | en | annulment (impotency) | yes | no | Voidable Marriage under Indian Family Law; Void Marriage – Legal Definition, Effects and; Bigamy under Indian Family Law |
| 25 | en | alimony | yes | no | Key Provisions of the Indian Divorce Act, 186; Supreme Court permits divorced Muslim women t; Alimony – Legal Obligation of Spousal Support |
| 26 | en | stridhan | no | yes | Ancestral Property and Coparcenary under the ; Child born of marriage between Muslim man and; Supreme Court permits divorced Muslim women t |
| 27 | en | 498A defence | - | no | Supreme Court permits divorced Muslim women t; Child born of marriage between Muslim man and; Hindu Marriage Act, 1955 – Key Provisions on  |
| 28 | en | desertion | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Supreme Court permits divorced Muslim women t |
| 29 | en | live-in relationship | no | no | Bigamy under Indian Family Law; Child born of marriage between Muslim man and; Supreme Court permits divorced Muslim women t |
| 30 | en | visitation rights | no | no | Hindu Marriage Act, 1955 – Key Provisions on ; Abolition of Triple Talaq in India: Judicial ; Supreme Court permits divorced Muslim women t |
| 31 | en | foreign divorce validity | no | yes | Voidable Marriage under Indian Family Law; Bigamy under Indian Family Law; Abolition of Triple Talaq in India: Judicial  |
| 32 | en | adoption | yes | no | Bigamy under Indian Family Law; Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Provisions, Applic |
| 33 | en | guardianship | yes | no | Hindu Minority and Guardianship Act, 1956; Guardians and Wards Act, 1890 – Key Provision; Hindu Succession Act, 1956 |
| 34 | en | child marriage | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Succession Act, 1956 |
| 35 | en | same-sex marriage | no | - | Void Marriage – Legal Definition, Effects and; Bigamy under Indian Family Law; Hindu Marriage Act, 1955 – Key Provisions on  |
| 36 | en | free legal aid | yes | - | Legal Services Authorities Act, 1987 – Free L; Supreme Court permits divorced Muslim women t; Abolition of Triple Talaq in India: Judicial  |
