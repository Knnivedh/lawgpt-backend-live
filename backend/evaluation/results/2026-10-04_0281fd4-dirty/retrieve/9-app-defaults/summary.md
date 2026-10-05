# Retrieval evaluation (deterministic checks only)

- Commit: `0281fd4` + uncommitted changes
- Collection: `indian_family_law_cases_hrag_test` | embedding: `bhavyagiri/InLegal-Sbert`
- Query translation: on (`google/gemma-3-4b-it`) | rewrite: off | hybrid (BM25): on | corpus curation: on
- Queries: 36 | Hugging Face calls this run: 0 embedding, 0 translation, 0 rewrite

Gold lists are 'known relevant', not exhaustive, so recall and hit rates are lower bounds. 'Grouped' treats near-duplicate statute documents as one.

## Overall

| Metric | Value |
|---|---|
| Statute hit rate (at least one gold statute returned) | 0.8 |
| Statute recall, grouped | 0.57 |
| Statute recall, exact ids | 0.46 |
| Precedent hit rate (at least one gold precedent returned) | 0.33 |
| Precedent recall | 0.09 |
| Distinct statutes per query after merging duplicates (of 3) | 3 |
| Queries with an off-topic statute document | 0 of 36 |

## By language

| Language | Queries | Statute hit | Statute recall (grouped) | Precedent hit |
|---|---|---|---|---|
| en | 27 | 0.88 | 0.67 | 0.29 |
| hi | 5 | 0.8 | 0.33 | 0.2 |
| hi-en | 2 | 0.5 | 0.5 | 1 |
| ta | 2 | 0 | 0.0 | 0.5 |

## Language twins (same question, different language)

| Topic | Languages | Shared statutes | Shared precedents |
|---|---|---|---|
| right to reside | hi, en, ta | 0 of 8 | 1 of 10 |
| child custody | en, hi | 2 of 4 | 2 of 8 |
| dowry harassment | en, hi | 2 of 4 | 1 of 9 |
| mutual consent divorce | en, hi | 2 of 4 | 1 of 9 |
| bigamy | en, hi | 0 of 6 | 1 of 9 |

## Statute documents returned most often

| Document | Queries (of 36) |
|---|---|
| Hindu Marriage Act, 1955 – Key Provisions on Marriage, Divorce and Maintenance | 15 |
| Supreme Court permits divorced Muslim women to claim maintenance under Section 125 CrPC | 12 |
| Special Marriage Act, 1954 – Key Provisions | 7 |
| Key Provisions of the Indian Divorce Act, 1869 | 6 |
| Bigamy under Indian Family Law | 6 |
| Child born of marriage between Muslim man and Hindu woman entitled to claim father's property: Supreme Court | 5 |
| Supreme Court rules child of Muslim‑Hindu fasid marriage entitled to father's property | 4 |
| Hindu Adoptions and Maintenance Act, 1956 – Adoption and Maintenance Provisions | 4 |

## Per query

| # | Lang | Topic | Statute hit | Precedent hit | Statutes returned |
|---|---|---|---|---|---|
| 1 | hi | right to reside | no | yes | Special Marriage Act, 1954 – Key Provisions; Supreme Court Rejects Marriage Equality and A; Child born of marriage between Muslim man and |
| 2 | en | right to reside | no | yes | Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and; Supreme Court permits divorced Muslim women t |
| 3 | ta | right to reside | no | yes | Hindu Succession Act, 1956; Supreme Court rules child of Muslim‑Hindu fas; Hindu Minority and Guardianship Act, 1956 |
| 4 | en | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Hindu Marriage Act, 1955 – Key Provisions on ; Key Provisions of the Indian Divorce Act, 186 |
| 5 | hi | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| 6 | en | maintenance (wife) | no | no | Supreme Court permits divorced Muslim women t; Madras High Court Clarifies Date of Filing fo; Supreme Court rules child of Muslim‑Hindu fas |
| 7 | hi-en | maintenance + DV | yes | yes | Protection of Women from Domestic Violence Ac; Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on  |
| 8 | ta | maintenance amount | no | no | Mahr as a Mandatory Bride‑Wealth Obligation u; Supreme Court permits divorced Muslim women t; Key Provisions of the Indian Divorce Act, 186 |
| 9 | en | dowry harassment | yes | no | Dowry Prohibition Act, 1961; Supreme Court permits divorced Muslim women t; Protection of Women from Domestic Violence Ac |
| 10 | hi | dowry harassment | yes | no | Dowry Prohibition Act, 1961; Supreme Court permits divorced Muslim women t; Supreme Court clarifies power to grant mutual |
| 11 | en | domestic violence | yes | no | Protection of Women from Domestic Violence Ac; Supreme Court permits divorced Muslim women t; Kerala HC Declares Marriage Does Not Bar POCS |
| 12 | en | mutual consent divorce | yes | no | Supreme Court clarifies power to grant mutual; Hindu Marriage Act, 1955 – Key Provisions on ; Bigamy under Indian Family Law |
| 13 | hi | mutual consent divorce | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Bigamy under Indian Family Law; Prenuptial Agreements and Their Limited Recog |
| 14 | en | cruelty | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Voidable Marriage under Indian Family Law; Key Provisions of the Indian Divorce Act, 186 |
| 15 | en | divorce within one year | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Voidable Marriage under Indian Family Law; Supreme Court: Exercise of Article 142 for Di |
| 16 | en | bigamy | yes | no | Prohibition of Child Marriage Act, 2006; Bigamy under Indian Family Law; Special Marriage Act, 1954 – Key Provisions |
| 17 | hi | bigamy | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Restitution of Conjugal Rights – Historical D; Abolition of Triple Talaq in India: Judicial  |
| 18 | en | restitution of conjugal rights | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court permits divorced Muslim women t; Restitution of Conjugal Rights – Historical D |
| 19 | hi-en | interfaith court marriage | no | yes | Bigamy under Indian Family Law; Supreme Court Rules Child of Muslim Man and H; Supreme Court Rules Divorced Muslim Women Ent |
| 20 | en | triple talaq | yes | yes | Abolition of Triple Talaq in India: Judicial ; Muslim Personal Law (Shariat) Application Act; Hindu Marriage Act, 1955 – Key Provisions on  |
| 21 | en | Muslim woman maintenance | yes | no | Supreme Court allows divorced Muslim women to; Supreme Court rules child of Muslim‑Hindu fas; Key Provisions of the Indian Divorce Act, 186 |
| 22 | en | daughter's property rights | yes | no | Ancestral Property and Coparcenary under the ; Hindu Succession Act, 1956; Supreme Court Rules Child of Muslim Man and H |
| 23 | en | interfaith child's property | yes | - | Supreme Court Rules Child of Muslim Man and H; Hindu Minority and Guardianship Act, 1956; Hindu Succession Act, 1956 |
| 24 | en | annulment (impotency) | yes | no | Void Marriage – Legal Definition, Effects and; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| 25 | en | alimony | yes | no | Key Provisions of the Indian Divorce Act, 186; Alimony – Legal Obligation of Spousal Support; Supreme Court permits divorced Muslim women t |
| 26 | en | stridhan | no | yes | Bigamy under Indian Family Law; Supreme Court permits divorced Muslim women t; Child born of marriage between Muslim man and |
| 27 | en | 498A defence | - | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court permits divorced Muslim women t |
| 28 | en | desertion | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Key Provisions of the Indian Divorce Act, 186 |
| 29 | en | live-in relationship | yes | yes | Supreme Court permits divorced Muslim women t; Child born of marriage between Muslim man and; Allahabad HC Declares UP Conversion Act Does  |
| 30 | en | visitation rights | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Child Custody: Legal and Physical Custody Fra; Supreme Court rules child of Muslim‑Hindu fas |
| 31 | en | foreign divorce validity | yes | no | Bigamy under Indian Family Law; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Holds Marriage During Pendency  |
| 32 | en | adoption | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 (India); Child born of marriage between Muslim man and |
| 33 | en | guardianship | yes | yes | Hindu Minority and Guardianship Act, 1956; Guardians and Wards Act, 1890 – Key Provision; Uniform Civil Code – proposal for a common pe |
| 34 | en | child marriage | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Prohibition of Child Marriage Act, 2006; Special Marriage Act, 1954 – Key Provisions |
| 35 | en | same-sex marriage | yes | - | Mukul Rohatgi urges Supreme Court to declare ; Void Marriage – Legal Definition, Effects and; Special Marriage Act, 1954 – Key Provisions |
| 36 | en | free legal aid | yes | - | Legal Services Authorities Act, 1987 – Free L; Prenuptial Agreements and Their Limited Recog; Supreme Court permits divorced Muslim women t |
