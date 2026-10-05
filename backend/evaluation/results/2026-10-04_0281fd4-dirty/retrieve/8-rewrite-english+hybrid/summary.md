# Retrieval evaluation (deterministic checks only)

- Commit: `0281fd4` + uncommitted changes
- Collection: `indian_family_law_cases_hrag_test` | embedding: `bhavyagiri/InLegal-Sbert`
- Query translation: on (`google/gemma-3-4b-it`) | rewrite: on, embedding english | hybrid (BM25): on | corpus curation: on
- Queries: 36 | Hugging Face calls this run: 0 embedding, 0 translation, 0 rewrite

Gold lists are 'known relevant', not exhaustive, so recall and hit rates are lower bounds. 'Grouped' treats near-duplicate statute documents as one.

## Overall

| Metric | Value |
|---|---|
| Statute hit rate (at least one gold statute returned) | 0.71 |
| Statute recall, grouped | 0.51 |
| Statute recall, exact ids | 0.4 |
| Precedent hit rate (at least one gold precedent returned) | 0.15 |
| Precedent recall | 0.04 |
| Distinct statutes per query after merging duplicates (of 3) | 3 |
| Queries with an off-topic statute document | 0 of 36 |

## By language

| Language | Queries | Statute hit | Statute recall (grouped) | Precedent hit |
|---|---|---|---|---|
| en | 27 | 0.73 | 0.57 | 0.21 |
| hi | 5 | 0.8 | 0.43 | 0 |
| hi-en | 2 | 0.5 | 0.33 | 0 |
| ta | 2 | 0.5 | 0.17 | 0 |

## Language twins (same question, different language)

| Topic | Languages | Shared statutes | Shared precedents |
|---|---|---|---|
| right to reside | hi, en, ta | 0 of 9 | 0 of 13 |
| child custody | en, hi | 3 of 3 | 1 of 9 |
| dowry harassment | en, hi | 2 of 4 | 0 of 10 |
| mutual consent divorce | en, hi | 1 of 5 | 1 of 9 |
| bigamy | en, hi | 1 of 5 | 0 of 10 |

## Statute documents returned most often

| Document | Queries (of 36) |
|---|---|
| Hindu Marriage Act, 1955 – Key Provisions on Marriage, Divorce and Maintenance | 12 |
| Supreme Court permits divorced Muslim women to claim maintenance under Section 125 CrPC | 10 |
| Special Marriage Act, 1954 – Key Provisions | 7 |
| Key Provisions of the Indian Divorce Act, 1869 | 7 |
| Hindu Adoptions and Maintenance Act, 1956 – Adoption and Maintenance Provisions | 6 |
| Bigamy under Indian Family Law | 6 |
| Voidable Marriage under Indian Family Law | 5 |
| Supreme Court rules child of Muslim‑Hindu fasid marriage entitled to father's property | 4 |

## Per query

| # | Lang | Topic | Statute hit | Precedent hit | Statutes returned |
|---|---|---|---|---|---|
| 1 | hi | right to reside | no | no | Special Marriage Act, 1954 – Key Provisions; Supreme Court: Exercise of Article 142 for Di; Hindu Adoptions and Maintenance Act, 1956 – A |
| 2 | en | right to reside | no | no | Supreme Court permits divorced Muslim women t; Supreme Court rules child of Muslim‑Hindu fas; Hindu Marriage Act, 1955 – Key Provisions on  |
| 3 | ta | right to reside | no | no | Hindu Succession Act, 1956; Child born of marriage between Muslim man and; Hindu Minority and Guardianship Act, 1956 |
| 4 | en | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Key Provisions of the Indian Divorce Act, 186; Special Marriage Act, 1954 – Key Provisions |
| 5 | hi | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Special Marriage Act, 1954 – Key Provisions; Key Provisions of the Indian Divorce Act, 186 |
| 6 | en | maintenance (wife) | no | no | Supreme Court permits divorced Muslim women t; Madras High Court Clarifies Date of Filing fo; Supreme Court rules child of Muslim‑Hindu fas |
| 7 | hi-en | maintenance + DV | yes | no | Protection of Women from Domestic Violence Ac; Supreme Court permits divorced Muslim women t; Hindu Marriage Act, 1955 – Key Provisions on  |
| 8 | ta | maintenance amount | yes | no | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Key Provisions of the Indian Divorce Act, 186 |
| 9 | en | dowry harassment | yes | no | Supreme Court permits divorced Muslim women t; Dowry Prohibition Act, 1961; Hindu Adoptions and Maintenance Act, 1956 – A |
| 10 | hi | dowry harassment | yes | no | Dowry Prohibition Act, 1961; Protection of Women from Domestic Violence Ac; Supreme Court permits divorced Muslim women t |
| 11 | en | domestic violence | yes | no | Protection of Women from Domestic Violence Ac; Supreme Court permits divorced Muslim women t; Kerala HC Declares Marriage Does Not Bar POCS |
| 12 | en | mutual consent divorce | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court clarifies power to grant mutual; Special Marriage Act, 1954 – Key Provisions |
| 13 | hi | mutual consent divorce | yes | no | Prenuptial Agreements and Their Limited Recog; Hindu Marriage Act, 1955 – Key Provisions on ; Bigamy under Indian Family Law |
| 14 | en | cruelty | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Voidable Marriage under Indian Family Law; Key Provisions of the Indian Divorce Act, 186 |
| 15 | en | divorce within one year | no | no | Supreme Court: Exercise of Article 142 for Di; Supreme Court Holds Marriage During Pendency ; Key Provisions of the Indian Divorce Act, 186 |
| 16 | en | bigamy | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Bigamy under Indian Family Law; Supreme Court Holds Marriage During Pendency  |
| 17 | hi | bigamy | yes | no | Void Marriage – Legal Definition, Effects and; Abolition of Triple Talaq in India: Judicial ; Hindu Marriage Act, 1955 – Key Provisions on  |
| 18 | en | restitution of conjugal rights | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Restitution of Conjugal Rights – Historical D; Supreme Court permits divorced Muslim women t |
| 19 | hi-en | interfaith court marriage | no | no | Supreme Court Rules Child of Muslim Man and H; Bigamy under Indian Family Law; Supreme Court allows divorced Muslim women to |
| 20 | en | triple talaq | yes | yes | Voidable Marriage under Indian Family Law; Abolition of Triple Talaq in India: Judicial ; Bigamy under Indian Family Law |
| 21 | en | Muslim woman maintenance | yes | no | Supreme Court allows divorced Muslim women to; Supreme Court rules child of Muslim‑Hindu fas; Key Provisions of the Indian Divorce Act, 186 |
| 22 | en | daughter's property rights | yes | no | Ancestral Property and Coparcenary under the ; Hindu Succession Act, 1956; Supreme Court Rules Child of Muslim Man and H |
| 23 | en | interfaith child's property | yes | - | Supreme Court Rules Child of Muslim Man and H; Hindu Minority and Guardianship Act, 1956; Hindu Succession Act, 1956 – Intestate Inheri |
| 24 | en | annulment (impotency) | yes | no | Voidable Marriage under Indian Family Law; Void Marriage – Legal Definition, Effects and; Prohibition of Child Marriage Act, 2006 |
| 25 | en | alimony | yes | no | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Key Provisions of the Indian Divorce Act, 186 |
| 26 | en | stridhan | no | no | Review Petition Challenging Supreme Court's R; Bigamy under Indian Family Law; Child born of marriage between Muslim man and |
| 27 | en | 498A defence | - | no | Supreme Court Holds Marriage During Pendency ; Supreme Court permits divorced Muslim women t; Supreme Court: Exercise of Article 142 for Di |
| 28 | en | desertion | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court allows divorced Muslim women to |
| 29 | en | live-in relationship | yes | yes | Supreme Court Rules Child of Muslim Man and H; Supreme Court permits divorced Muslim women t; Allahabad HC Declares UP Conversion Act Does  |
| 30 | en | visitation rights | no | yes | Supreme Court rules child of Muslim‑Hindu fas; Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A |
| 31 | en | foreign divorce validity | no | yes | Voidable Marriage under Indian Family Law; Supreme Court Holds Marriage During Pendency ; Bigamy under Indian Family Law |
| 32 | en | adoption | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rejects Marriage Equality and A; Ashwini Kumar Upadhyay v. Union of India – Un |
| 33 | en | guardianship | yes | no | Hindu Minority and Guardianship Act, 1956; Guardians and Wards Act, 1890 – Key Provision; Child Custody: Legal and Physical Custody Fra |
| 34 | en | child marriage | no | no | Voidable Marriage under Indian Family Law; Supreme Court permits divorced Muslim women t; Hindu Adoptions and Maintenance Act, 1956 – A |
| 35 | en | same-sex marriage | yes | - | Mukul Rohatgi urges Supreme Court to declare ; Void Marriage – Legal Definition, Effects and; Special Marriage Act, 1954 – Key Provisions |
| 36 | en | free legal aid | yes | - | Legal Services Authorities Act, 1987 – Free L; Supreme Court clarifies power to grant mutual; Prenuptial Agreements and Their Limited Recog |
