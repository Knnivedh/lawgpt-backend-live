# Retrieval evaluation (deterministic checks only)

- Commit: `0281fd4` + uncommitted changes
- Collection: `indian_family_law_cases_hrag_test` | embedding: `bhavyagiri/InLegal-Sbert`
- Query translation: on (`google/gemma-3-4b-it`) | rewrite: on, embedding search | hybrid (BM25): on | corpus curation: on
- Queries: 36 | Hugging Face calls this run: 0 embedding, 0 translation, 0 rewrite

Gold lists are 'known relevant', not exhaustive, so recall and hit rates are lower bounds. 'Grouped' treats near-duplicate statute documents as one.

## Overall

| Metric | Value |
|---|---|
| Statute hit rate (at least one gold statute returned) | 0.77 |
| Statute recall, grouped | 0.57 |
| Statute recall, exact ids | 0.46 |
| Precedent hit rate (at least one gold precedent returned) | 0.21 |
| Precedent recall | 0.08 |
| Distinct statutes per query after merging duplicates (of 3) | 3 |
| Queries with an off-topic statute document | 0 of 36 |

## By language

| Language | Queries | Statute hit | Statute recall (grouped) | Precedent hit |
|---|---|---|---|---|
| en | 27 | 0.81 | 0.64 | 0.29 |
| hi | 5 | 0.8 | 0.43 | 0 |
| hi-en | 2 | 0.5 | 0.33 | 0 |
| ta | 2 | 0.5 | 0.17 | 0 |

## Language twins (same question, different language)

| Topic | Languages | Shared statutes | Shared precedents |
|---|---|---|---|
| right to reside | hi, en, ta | 0 of 7 | 2 of 8 |
| child custody | en, hi | 3 of 3 | 3 of 7 |
| dowry harassment | en, hi | 2 of 4 | 1 of 9 |
| mutual consent divorce | en, hi | 1 of 5 | 2 of 8 |
| bigamy | en, hi | 1 of 5 | 0 of 10 |

## Statute documents returned most often

| Document | Queries (of 36) |
|---|---|
| Hindu Marriage Act, 1955 – Key Provisions on Marriage, Divorce and Maintenance | 17 |
| Special Marriage Act, 1954 – Key Provisions | 11 |
| Hindu Adoptions and Maintenance Act, 1956 – Adoption and Maintenance Provisions | 9 |
| Supreme Court permits divorced Muslim women to claim maintenance under Section 125 CrPC | 7 |
| Supreme Court Rules Child of Muslim Man and Hindu Wife Entitled to Father's Property | 7 |
| Protection of Women from Domestic Violence Act, 2005 | 6 |
| Hindu Minority and Guardianship Act, 1956 | 5 |
| Child Custody: Legal and Physical Custody Framework | 4 |

## Per query

| # | Lang | Topic | Statute hit | Precedent hit | Statutes returned |
|---|---|---|---|---|---|
| 1 | hi | right to reside | no | no | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A |
| 2 | en | right to reside | no | no | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court permits divorced Muslim women t; Hindu Adoptions and Maintenance Act, 1956 – A |
| 3 | ta | right to reside | no | no | Hindu Succession Act, 1956; Hindu Minority and Guardianship Act, 1956; Supreme Court Rules Child of Muslim Man and H |
| 4 | en | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on  |
| 5 | hi | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| 6 | en | maintenance (wife) | yes | no | Supreme Court permits divorced Muslim women t; Hindu Adoptions and Maintenance Act, 1956 – A; Madras High Court Clarifies Date of Filing fo |
| 7 | hi-en | maintenance + DV | yes | no | Protection of Women from Domestic Violence Ac; Special Marriage Act, 1954 – Key Provisions; Hindu Adoptions and Maintenance Act, 1956 – A |
| 8 | ta | maintenance amount | yes | no | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Child Custody: Legal and Physical Custody Fra |
| 9 | en | dowry harassment | yes | no | Dowry Prohibition Act, 1961; Hindu Adoptions and Maintenance Act, 1956 – A; Protection of Women from Domestic Violence Ac |
| 10 | hi | dowry harassment | yes | no | Dowry Prohibition Act, 1961; Protection of Women from Domestic Violence Ac; Madras High Court Clarifies Date of Filing fo |
| 11 | en | domestic violence | yes | no | Protection of Women from Domestic Violence Ac; Supreme Court permits divorced Muslim women t; Kerala HC Declares Marriage Does Not Bar POCS |
| 12 | en | mutual consent divorce | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Supreme Court clarifies power to grant mutual |
| 13 | hi | mutual consent divorce | yes | no | Parsi Marriage and Divorce Act, 1936; Prenuptial Agreements and Their Limited Recog; Hindu Marriage Act, 1955 – Key Provisions on  |
| 14 | en | cruelty | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Parsi Marriage and Divorce Act, 1936; Special Marriage Act, 1954 – Key Provisions |
| 15 | en | divorce within one year | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Voidable Marriage under Indian Family Law |
| 16 | en | bigamy | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Bigamy under Indian Family Law; Supreme Court clarifies power to grant mutual |
| 17 | hi | bigamy | yes | no | Void Marriage – Legal Definition, Effects and; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| 18 | en | restitution of conjugal rights | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court permits divorced Muslim women t; Madras High Court: Marriage is Primarily for  |
| 19 | hi-en | interfaith court marriage | no | no | Bigamy under Indian Family Law; Supreme Court Rules Child of Muslim Man and H; Legal Status of Polygamy in India |
| 20 | en | triple talaq | yes | no | Abolition of Triple Talaq in India: Judicial ; Parsi Marriage and Divorce Act, 1936; Voidable Marriage under Indian Family Law |
| 21 | en | Muslim woman maintenance | yes | no | Supreme Court allows divorced Muslim women to; Supreme Court Rules Child of Muslim Man and H; Abolition of Triple Talaq in India: Judicial  |
| 22 | en | daughter's property rights | yes | yes | Ancestral Property and Coparcenary under the ; Hindu Succession Act, 1956; Supreme Court Rules Child of Muslim Man and H |
| 23 | en | interfaith child's property | yes | - | Supreme Court Rules Child of Muslim Man and H; Hindu Minority and Guardianship Act, 1956; Hindu Succession Act, 1956 – Intestate Inheri |
| 24 | en | annulment (impotency) | yes | no | Voidable Marriage under Indian Family Law; Void Marriage – Legal Definition, Effects and; Hindu Marriage Act, 1955 – Key Provisions on  |
| 25 | en | alimony | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Alimony – Legal Obligation of Spousal Support; Key Provisions of the Indian Divorce Act, 186 |
| 26 | en | stridhan | no | yes | Bigamy under Indian Family Law; Supreme Court permits divorced Muslim women t; Supreme Court Rules Child of Muslim Man and H |
| 27 | en | 498A defence | - | no | Special Marriage Act, 1954 – Key Provisions; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court permits divorced Muslim women t |
| 28 | en | desertion | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Hindu Adoptions and Maintenance Act, 1956 – A |
| 29 | en | live-in relationship | yes | yes | Protection of Women from Domestic Violence Ac; Supreme Court Rules Child of Muslim Man and H; Supreme Court permits divorced Muslim women t |
| 30 | en | visitation rights | yes | yes | Child Custody: Legal and Physical Custody Fra; Hindu Minority and Guardianship Act, 1956; Hindu Marriage Act, 1955 – Key Provisions on  |
| 31 | en | foreign divorce validity | no | yes | Foreign Marriage Act, 1969 (India); Prenuptial Agreements and Their Limited Recog; Parsi Marriage and Divorce Act, 1936 |
| 32 | en | adoption | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Ashwini Kumar Upadhyay v. Union of India – Un; Hindu Minority and Guardianship Act, 1956 |
| 33 | en | guardianship | yes | yes | Hindu Minority and Guardianship Act, 1956; Guardians and Wards Act, 1890 – Key Provision; Maternal Bond and Its Relevance to Indian Fam |
| 34 | en | child marriage | no | no | Kerala HC Declares Marriage Does Not Bar POCS; Hindu Adoptions and Maintenance Act, 1956 – A; Voidable Marriage under Indian Family Law |
| 35 | en | same-sex marriage | no | - | Void Marriage – Legal Definition, Effects and; Special Marriage Act, 1954 (India); Madras High Court: Marriage is Primarily for  |
| 36 | en | free legal aid | yes | - | Legal Services Authorities Act, 1987 – Free L; Protection of Women from Domestic Violence Ac; Hindu Marriage Act, 1955 – Key Provisions on  |
