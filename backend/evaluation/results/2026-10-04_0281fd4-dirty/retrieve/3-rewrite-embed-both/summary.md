# Retrieval evaluation (deterministic checks only)

- Commit: `0281fd4` + uncommitted changes
- Collection: `indian_family_law_cases_hrag_test` | embedding: `bhavyagiri/InLegal-Sbert`
- Query translation: on (`google/gemma-3-4b-it`) | rewrite: on, embedding both | hybrid (BM25): off | corpus curation: on
- Queries: 36 | Hugging Face calls this run: 2 embedding, 0 translation, 2 rewrite

Gold lists are 'known relevant', not exhaustive, so recall and hit rates are lower bounds. 'Grouped' treats near-duplicate statute documents as one.

## Overall

| Metric | Value |
|---|---|
| Statute hit rate (at least one gold statute returned) | 0.6 |
| Statute recall, grouped | 0.37 |
| Statute recall, exact ids | 0.27 |
| Precedent hit rate (at least one gold precedent returned) | 0.12 |
| Precedent recall | 0.03 |
| Distinct statutes per query after merging duplicates (of 3) | 2.94 |
| Queries with an off-topic statute document | 0 of 36 |

## By language

| Language | Queries | Statute hit | Statute recall (grouped) | Precedent hit |
|---|---|---|---|---|
| en | 27 | 0.62 | 0.41 | 0.17 |
| hi | 5 | 0.8 | 0.33 | 0 |
| hi-en | 2 | 0.5 | 0.33 | 0 |
| ta | 2 | 0 | 0.0 | 0 |

## Language twins (same question, different language)

| Topic | Languages | Shared statutes | Shared precedents |
|---|---|---|---|
| right to reside | hi, en, ta | 2 of 4 | 0 of 12 |
| child custody | en, hi | 2 of 4 | 4 of 6 |
| dowry harassment | en, hi | 1 of 5 | 1 of 9 |
| mutual consent divorce | en, hi | 1 of 5 | 2 of 8 |
| bigamy | en, hi | 1 of 5 | 1 of 9 |

## Statute documents returned most often

| Document | Queries (of 36) |
|---|---|
| Supreme Court permits divorced Muslim women to claim maintenance under Section 125 CrPC | 11 |
| Hindu Adoptions and Maintenance Act, 1956 – Adoption and Maintenance Provisions | 10 |
| Bigamy under Indian Family Law | 8 |
| Key Provisions of the Indian Divorce Act, 1869 | 6 |
| Hindu Marriage Act, 1955 – Key Provisions on Marriage, Divorce and Maintenance | 6 |
| Voidable Marriage under Indian Family Law | 6 |
| Abolition of Triple Talaq in India: Judicial and Legislative Milestones | 6 |
| Void Marriage – Legal Definition, Effects and Grounds | 6 |

## Per query

| # | Lang | Topic | Statute hit | Precedent hit | Statutes returned |
|---|---|---|---|---|---|
| 1 | hi | right to reside | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court permits divorced Muslim women t; Supreme Court rules child of Muslim‑Hindu fas |
| 2 | en | right to reside | no | no | Supreme Court permits divorced Muslim women t; Supreme Court rules child of Muslim‑Hindu fas; Hindu Adoptions and Maintenance Act, 1956 – A |
| 3 | ta | right to reside | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Child born of marriage between Muslim man and; Supreme Court permits divorced Muslim women t |
| 4 | en | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Supreme Court permits divorced Muslim women t; Key Provisions of the Indian Divorce Act, 186 |
| 5 | hi | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Hindu Marriage Act, 1955 – Key Provisions on ; Key Provisions of the Indian Divorce Act, 186 |
| 6 | en | maintenance (wife) | no | no | Supreme Court permits divorced Muslim women t; Madras High Court Clarifies Date of Filing fo; Supreme Court Expands Scope of Article 142 in |
| 7 | hi-en | maintenance + DV | yes | no | Protection of Women from Domestic Violence Ac; Supreme Court permits divorced Muslim women t; Hindu Adoptions and Maintenance Act, 1956 – A |
| 8 | ta | maintenance amount | no | no | Supreme Court permits divorced Muslim women t; Key Provisions of the Indian Divorce Act, 186; Special Marriage Act, 1954 – Key Provisions |
| 9 | en | dowry harassment | yes | no | Dowry Prohibition Act, 1961; Hindu Adoptions and Maintenance Act, 1956 – A; Key Provisions of the Indian Divorce Act, 186 |
| 10 | hi | dowry harassment | yes | no | Dowry Prohibition Act, 1961; Supreme Court Rules Divorced Muslim Women Ent; Madras High Court Clarifies Date of Filing fo |
| 11 | en | domestic violence | yes | no | Protection of Women from Domestic Violence Ac; Supreme Court permits divorced Muslim women t |
| 12 | en | mutual consent divorce | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Voidable Marriage under Indian Family Law |
| 13 | hi | mutual consent divorce | yes | no | Abolition of Triple Talaq in India: Judicial ; Hindu Marriage Act, 1955 – Key Provisions on ; Prenuptial Agreements and Their Limited Recog |
| 14 | en | cruelty | no | no | Supreme Court Expands Scope of Article 142 in; Supreme Court: Exercise of Article 142 for Di; Key Provisions of the Indian Divorce Act, 186 |
| 15 | en | divorce within one year | no | yes | Bigamy under Indian Family Law; Voidable Marriage under Indian Family Law; Void Marriage – Legal Definition, Effects and |
| 16 | en | bigamy | yes | no | Void Marriage – Legal Definition, Effects and; Bigamy under Indian Family Law; Prohibition of Child Marriage Act, 2006 |
| 17 | hi | bigamy | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Void Marriage – Legal Definition, Effects and |
| 18 | en | restitution of conjugal rights | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Mukul Rohatgi urges Supreme Court to declare ; Supreme Court permits divorced Muslim women t |
| 19 | hi-en | interfaith court marriage | no | no | Bigamy under Indian Family Law; Abolition of Triple Talaq in India: Judicial ; Legal Status of Polygamy in India |
| 20 | en | triple talaq | yes | no | Voidable Marriage under Indian Family Law; Void Marriage – Legal Definition, Effects and; Abolition of Triple Talaq in India: Judicial  |
| 21 | en | Muslim woman maintenance | yes | no | Supreme Court allows divorced Muslim women to; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court rules child of Muslim‑Hindu fas |
| 22 | en | daughter's property rights | yes | no | Ancestral Property and Coparcenary under the ; Hindu Succession Act, 1956; Hindu Minority and Guardianship Act, 1956 |
| 23 | en | interfaith child's property | yes | - | Supreme Court Rules Child of Muslim Man and H; Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri |
| 24 | en | annulment (impotency) | yes | no | Voidable Marriage under Indian Family Law; Void Marriage – Legal Definition, Effects and; Bigamy under Indian Family Law |
| 25 | en | alimony | yes | no | Key Provisions of the Indian Divorce Act, 186; Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on  |
| 26 | en | stridhan | no | no | Child born of marriage between Muslim man and; Bigamy under Indian Family Law; Hindu Succession Act, 1956 – Intestate Inheri |
| 27 | en | 498A defence | - | no | Child born of marriage between Muslim man and; Supreme Court permits divorced Muslim women t; Abolition of Triple Talaq in India: Judicial  |
| 28 | en | desertion | no | no | Supreme Court rules child of Muslim‑Hindu fas; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court: Exercise of Article 142 for Di |
| 29 | en | live-in relationship | yes | no | Child born of marriage between Muslim man and; Bigamy under Indian Family Law; Protection of Women from Domestic Violence Ac |
| 30 | en | visitation rights | no | yes | Supreme Court permits divorced Muslim women t; Abolition of Triple Talaq in India: Judicial ; Hindu Adoptions and Maintenance Act, 1956 – A |
| 31 | en | foreign divorce validity | no | yes | Voidable Marriage under Indian Family Law; Supreme Court: Exercise of Article 142 for Di; Restitution of Conjugal Rights – Historical D |
| 32 | en | adoption | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Ancestral Property and Coparcenary under the ; Hindu Marriage Act, 1955 – Provisions, Applic |
| 33 | en | guardianship | yes | no | Hindu Minority and Guardianship Act, 1956; Guardians and Wards Act, 1890 – Key Provision |
| 34 | en | child marriage | no | no | Bigamy under Indian Family Law; Voidable Marriage under Indian Family Law; Abolition of Triple Talaq in India: Judicial  |
| 35 | en | same-sex marriage | no | - | Void Marriage – Legal Definition, Effects and; Bigamy under Indian Family Law; Legal Status of Polygamy in India |
| 36 | en | free legal aid | yes | - | Legal Services Authorities Act, 1987 – Free L; Supreme Court allows divorced Muslim women to; Mukul Rohatgi urges Supreme Court to declare  |
