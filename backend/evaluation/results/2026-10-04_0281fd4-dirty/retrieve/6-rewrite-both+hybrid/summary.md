# Retrieval evaluation (deterministic checks only)

- Commit: `0281fd4` + uncommitted changes
- Collection: `indian_family_law_cases_hrag_test` | embedding: `bhavyagiri/InLegal-Sbert`
- Query translation: on (`google/gemma-3-4b-it`) | rewrite: on, embedding both | hybrid (BM25): on | corpus curation: on
- Queries: 36 | Hugging Face calls this run: 0 embedding, 0 translation, 0 rewrite

Gold lists are 'known relevant', not exhaustive, so recall and hit rates are lower bounds. 'Grouped' treats near-duplicate statute documents as one.

## Overall

| Metric | Value |
|---|---|
| Statute hit rate (at least one gold statute returned) | 0.74 |
| Statute recall, grouped | 0.52 |
| Statute recall, exact ids | 0.41 |
| Precedent hit rate (at least one gold precedent returned) | 0.21 |
| Precedent recall | 0.07 |
| Distinct statutes per query after merging duplicates (of 3) | 3 |
| Queries with an off-topic statute document | 0 of 36 |

## By language

| Language | Queries | Statute hit | Statute recall (grouped) | Precedent hit |
|---|---|---|---|---|
| en | 27 | 0.81 | 0.6 | 0.29 |
| hi | 5 | 0.8 | 0.43 | 0 |
| hi-en | 2 | 0.5 | 0.33 | 0 |
| ta | 2 | 0 | 0.0 | 0 |

## Language twins (same question, different language)

| Topic | Languages | Shared statutes | Shared precedents |
|---|---|---|---|
| right to reside | hi, en, ta | 1 of 7 | 0 of 13 |
| child custody | en, hi | 2 of 4 | 2 of 8 |
| dowry harassment | en, hi | 1 of 5 | 0 of 10 |
| mutual consent divorce | en, hi | 2 of 4 | 1 of 9 |
| bigamy | en, hi | 1 of 5 | 0 of 10 |

## Statute documents returned most often

| Document | Queries (of 36) |
|---|---|
| Special Marriage Act, 1954 – Key Provisions | 12 |
| Hindu Marriage Act, 1955 – Key Provisions on Marriage, Divorce and Maintenance | 11 |
| Supreme Court permits divorced Muslim women to claim maintenance under Section 125 CrPC | 10 |
| Voidable Marriage under Indian Family Law | 6 |
| Child Custody: Legal and Physical Custody Framework | 5 |
| Protection of Women from Domestic Violence Act, 2005 | 5 |
| Void Marriage – Legal Definition, Effects and Grounds | 5 |
| Child born of marriage between Muslim man and Hindu woman entitled to claim father's property: Supreme Court | 4 |

## Per query

| # | Lang | Topic | Statute hit | Precedent hit | Statutes returned |
|---|---|---|---|---|---|
| 1 | hi | right to reside | no | no | Special Marriage Act, 1954 – Key Provisions; Supreme Court: Exercise of Article 142 for Di; Supreme Court permits divorced Muslim women t |
| 2 | en | right to reside | no | no | Supreme Court permits divorced Muslim women t; Supreme Court rules child of Muslim‑Hindu fas; Supreme Court Holds Marriage During Pendency  |
| 3 | ta | right to reside | no | no | Child born of marriage between Muslim man and; Hindu Succession Act, 1956; Supreme Court permits divorced Muslim women t |
| 4 | en | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Special Marriage Act, 1954 – Key Provisions; Key Provisions of the Indian Divorce Act, 186 |
| 5 | hi | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| 6 | en | maintenance (wife) | yes | no | Supreme Court permits divorced Muslim women t; Madras High Court Clarifies Date of Filing fo; Supreme Court Bars Stays on Section 125 Maint |
| 7 | hi-en | maintenance + DV | yes | no | Protection of Women from Domestic Violence Ac; Supreme Court permits divorced Muslim women t; Hindu Marriage Act, 1955 – Key Provisions on  |
| 8 | ta | maintenance amount | no | no | Special Marriage Act, 1954 – Key Provisions; Child Custody: Legal and Physical Custody Fra; Key Provisions of the Indian Divorce Act, 186 |
| 9 | en | dowry harassment | yes | no | Protection of Women from Domestic Violence Ac; Dowry Prohibition Act, 1961; Supreme Court permits divorced Muslim women t |
| 10 | hi | dowry harassment | yes | no | Dowry Prohibition Act, 1961; Madras High Court Clarifies Date of Filing fo; Supreme Court Rules Divorced Muslim Women Ent |
| 11 | en | domestic violence | yes | no | Protection of Women from Domestic Violence Ac; Supreme Court permits divorced Muslim women t; Kerala HC Declares Marriage Does Not Bar POCS |
| 12 | en | mutual consent divorce | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Supreme Court Expands Scope of Article 142 in |
| 13 | hi | mutual consent divorce | yes | no | Supreme Court clarifies power to grant mutual; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| 14 | en | cruelty | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Voidable Marriage under Indian Family Law; Key Provisions of the Indian Divorce Act, 186 |
| 15 | en | divorce within one year | no | no | Supreme Court: Exercise of Article 142 for Di; Special Marriage Act, 1954 – Key Provisions; Voidable Marriage under Indian Family Law |
| 16 | en | bigamy | yes | no | Bigamy under Indian Family Law; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Holds Marriage During Pendency  |
| 17 | hi | bigamy | yes | no | Void Marriage – Legal Definition, Effects and; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| 18 | en | restitution of conjugal rights | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court permits divorced Muslim women t; Supreme Court Rules Child of Muslim Man and H |
| 19 | hi-en | interfaith court marriage | no | no | Supreme Court Rules Child of Muslim Man and H; Bigamy under Indian Family Law; Legal Status of Polygamy in India |
| 20 | en | triple talaq | yes | yes | Abolition of Triple Talaq in India: Judicial ; Voidable Marriage under Indian Family Law; Void Marriage – Legal Definition, Effects and |
| 21 | en | Muslim woman maintenance | yes | no | Supreme Court allows divorced Muslim women to; Supreme Court rules child of Muslim‑Hindu fas; Hindu Succession Act, 1956 – Intestate Inheri |
| 22 | en | daughter's property rights | yes | yes | Ancestral Property and Coparcenary under the ; Hindu Succession Act, 1956; Child born of marriage between Muslim man and |
| 23 | en | interfaith child's property | yes | - | Supreme Court Rules Child of Muslim Man and H; Hindu Succession Act, 1956 – Intestate Inheri; Hindu Minority and Guardianship Act, 1956 |
| 24 | en | annulment (impotency) | yes | no | Voidable Marriage under Indian Family Law; Void Marriage – Legal Definition, Effects and; Prohibition of Child Marriage Act, 2006 |
| 25 | en | alimony | yes | no | Key Provisions of the Indian Divorce Act, 186; Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on  |
| 26 | en | stridhan | no | no | Review Petition Challenging Supreme Court's R; Bigamy under Indian Family Law; Child born of marriage between Muslim man and |
| 27 | en | 498A defence | - | no | Supreme Court permits divorced Muslim women t; Supreme Court Holds Marriage During Pendency ; Supreme Court: Exercise of Article 142 for Di |
| 28 | en | desertion | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 – Key Provisions |
| 29 | en | live-in relationship | yes | yes | Protection of Women from Domestic Violence Ac; Supreme Court permits divorced Muslim women t; Child born of marriage between Muslim man and |
| 30 | en | visitation rights | yes | yes | Child Custody: Legal and Physical Custody Fra; Hindu Marriage Act, 1955 – Key Provisions on ; Maternal Bond and Its Relevance to Indian Fam |
| 31 | en | foreign divorce validity | no | yes | Voidable Marriage under Indian Family Law; Void Marriage – Legal Definition, Effects and; Special Marriage Act, 1954 (India) |
| 32 | en | adoption | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Ashwini Kumar Upadhyay v. Union of India – Un; Supreme Court Rejects Marriage Equality and A |
| 33 | en | guardianship | yes | yes | Hindu Minority and Guardianship Act, 1956; Guardians and Wards Act, 1890 – Key Provision; Child Custody: Legal and Physical Custody Fra |
| 34 | en | child marriage | no | no | Voidable Marriage under Indian Family Law; Kerala HC Declares Marriage Does Not Bar POCS; Special Marriage Act, 1954 – Key Provisions |
| 35 | en | same-sex marriage | yes | - | Mukul Rohatgi urges Supreme Court to declare ; Void Marriage – Legal Definition, Effects and; Special Marriage Act, 1954 – Key Provisions |
| 36 | en | free legal aid | yes | - | Legal Services Authorities Act, 1987 – Free L; Protection of Women from Domestic Violence Ac; Prenuptial Agreements and Their Limited Recog |
