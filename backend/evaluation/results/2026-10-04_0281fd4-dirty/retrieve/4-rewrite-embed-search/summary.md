# Retrieval evaluation (deterministic checks only)

- Commit: `0281fd4` + uncommitted changes
- Collection: `indian_family_law_cases_hrag_test` | embedding: `bhavyagiri/InLegal-Sbert`
- Query translation: on (`google/gemma-3-4b-it`) | rewrite: on, embedding search | hybrid (BM25): off | corpus curation: on
- Queries: 36 | Hugging Face calls this run: 36 embedding, 0 translation, 0 rewrite

Gold lists are 'known relevant', not exhaustive, so recall and hit rates are lower bounds. 'Grouped' treats near-duplicate statute documents as one.

## Overall

| Metric | Value |
|---|---|
| Statute hit rate (at least one gold statute returned) | 0.77 |
| Statute recall, grouped | 0.5 |
| Statute recall, exact ids | 0.41 |
| Precedent hit rate (at least one gold precedent returned) | 0.15 |
| Precedent recall | 0.04 |
| Distinct statutes per query after merging duplicates (of 3) | 3 |
| Queries with an off-topic statute document | 0 of 36 |

## By language

| Language | Queries | Statute hit | Statute recall (grouped) | Precedent hit |
|---|---|---|---|---|
| en | 27 | 0.81 | 0.57 | 0.21 |
| hi | 5 | 0.6 | 0.23 | 0 |
| hi-en | 2 | 1 | 0.5 | 0 |
| ta | 2 | 0.5 | 0.17 | 0 |

## Language twins (same question, different language)

| Topic | Languages | Shared statutes | Shared precedents |
|---|---|---|---|
| right to reside | hi, en, ta | 1 of 6 | 0 of 13 |
| child custody | en, hi | 2 of 4 | 4 of 6 |
| dowry harassment | en, hi | 1 of 5 | 1 of 9 |
| mutual consent divorce | en, hi | 0 of 6 | 2 of 8 |
| bigamy | en, hi | 1 of 5 | 0 of 10 |

## Statute documents returned most often

| Document | Queries (of 36) |
|---|---|
| Hindu Marriage Act, 1955 – Key Provisions on Marriage, Divorce and Maintenance | 16 |
| Special Marriage Act, 1954 – Key Provisions | 10 |
| Hindu Adoptions and Maintenance Act, 1956 – Adoption and Maintenance Provisions | 9 |
| Bigamy under Indian Family Law | 8 |
| Madras High Court: Marriage is Primarily for Procreation, Not Mere Carnal Pleasure | 6 |
| Hindu Minority and Guardianship Act, 1956 | 5 |
| Prohibition of Child Marriage Act, 2006 | 5 |
| Supreme Court Rules Child of Muslim Man and Hindu Wife Entitled to Father's Property | 4 |

## Per query

| # | Lang | Topic | Statute hit | Precedent hit | Statutes returned |
|---|---|---|---|---|---|
| 1 | hi | right to reside | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Minority and Guardianship Act, 1956; Hindu Marriage Act, 1955 – Key Provisions on  |
| 2 | en | right to reside | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court permits divorced Muslim women t; Supreme Court Rules Child of Muslim Man and H |
| 3 | ta | right to reside | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956; Hindu Minority and Guardianship Act, 1956 |
| 4 | en | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| 5 | hi | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Hindu Marriage Act, 1955 – Key Provisions on ; Madras High Court: Marriage is Primarily for  |
| 6 | en | maintenance (wife) | yes | no | Supreme Court permits divorced Muslim women t; Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on  |
| 7 | hi-en | maintenance + DV | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 – Key Provisions; Protection of Women from Domestic Violence Ac |
| 8 | ta | maintenance amount | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Supreme Court permits divorced Muslim women t |
| 9 | en | dowry harassment | yes | no | Dowry Prohibition Act, 1961; Hindu Adoptions and Maintenance Act, 1956 – A; Prohibition of Child Marriage Act, 2006 |
| 10 | hi | dowry harassment | yes | no | Dowry Prohibition Act, 1961; Kerala HC Declares Marriage Does Not Bar POCS; Madras High Court: Marriage is Primarily for  |
| 11 | en | domestic violence | yes | no | Protection of Women from Domestic Violence Ac; Supreme Court permits divorced Muslim women t; Kerala HC Declares Marriage Does Not Bar POCS |
| 12 | en | mutual consent divorce | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Madras High Court: Marriage is Primarily for  |
| 13 | hi | mutual consent divorce | no | no | Abolition of Triple Talaq in India: Judicial ; Parsi Marriage and Divorce Act, 1936; Prenuptial Agreements and Their Limited Recog |
| 14 | en | cruelty | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Madras High Court: Marriage is Primarily for  |
| 15 | en | divorce within one year | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Prohibition of Child Marriage Act, 2006; Bigamy under Indian Family Law |
| 16 | en | bigamy | yes | no | Madras High Court: Marriage is Primarily for ; Supreme Court clarifies power to grant mutual; Hindu Marriage Act, 1955 – Key Provisions on  |
| 17 | hi | bigamy | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Prohibition of Child Marriage Act, 2006; Special Marriage Act, 1954 – Key Provisions |
| 18 | en | restitution of conjugal rights | no | yes | Hindu Succession Act, 1956 – Intestate Inheri; Ancestral Property and Coparcenary under the ; Child born of marriage between Muslim man and |
| 19 | hi-en | interfaith court marriage | yes | no | Parsi Marriage and Divorce Act, 1936; Bigamy under Indian Family Law; Special Marriage Act, 1954 (India) |
| 20 | en | triple talaq | yes | yes | Abolition of Triple Talaq in India: Judicial ; Parsi Marriage and Divorce Act, 1936; Legal Status of Polygamy in India |
| 21 | en | Muslim woman maintenance | yes | no | Supreme Court allows divorced Muslim women to; Bigamy under Indian Family Law; Hindu Marriage Act, 1955 – Key Provisions on  |
| 22 | en | daughter's property rights | yes | no | Ancestral Property and Coparcenary under the ; Hindu Succession Act, 1956; Supreme Court Rules Child of Muslim Man and H |
| 23 | en | interfaith child's property | yes | - | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rules Child of Muslim Man and H; Hindu Succession Act, 1956 – Intestate Inheri |
| 24 | en | annulment (impotency) | yes | no | Voidable Marriage under Indian Family Law; Bigamy under Indian Family Law; Void Marriage – Legal Definition, Effects and |
| 25 | en | alimony | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Key Provisions of the Indian Divorce Act, 186; Special Marriage Act, 1954 – Key Provisions |
| 26 | en | stridhan | no | no | Hindu Succession Act, 1956 – Intestate Inheri; Bigamy under Indian Family Law; Ancestral Property and Coparcenary under the  |
| 27 | en | 498A defence | - | no | Prohibition of Child Marriage Act, 2006; Special Marriage Act, 1954 – Key Provisions; Supreme Court Rules Child of Muslim Man and H |
| 28 | en | desertion | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 – Key Provisions |
| 29 | en | live-in relationship | yes | yes | Protection of Women from Domestic Violence Ac; Kerala HC Declares Marriage Does Not Bar POCS; Bigamy under Indian Family Law |
| 30 | en | visitation rights | yes | no | Hindu Minority and Guardianship Act, 1956; Child Custody: Legal and Physical Custody Fra; Hindu Marriage Act, 1955 – Key Provisions on  |
| 31 | en | foreign divorce validity | no | yes | Prenuptial Agreements and Their Limited Recog; Family Courts: Historical Development, Statut; Restitution of Conjugal Rights – Historical D |
| 32 | en | adoption | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Provisions, Applic; Hindu Minority and Guardianship Act, 1956 |
| 33 | en | guardianship | yes | no | Hindu Minority and Guardianship Act, 1956; Guardians and Wards Act, 1890 – Key Provision; Hindu Adoptions and Maintenance Act, 1956 – A |
| 34 | en | child marriage | yes | no | Prohibition of Child Marriage Act, 2006; Hindu Marriage Act, 1955 – Key Provisions on ; Bigamy under Indian Family Law |
| 35 | en | same-sex marriage | no | - | Madras High Court: Marriage is Primarily for ; Bigamy under Indian Family Law; Parsi Marriage and Divorce Act, 1936 |
| 36 | en | free legal aid | yes | - | Legal Services Authorities Act, 1987 – Free L; Hindu Marriage Act, 1955 – Key Provisions on ; Protection of Women from Domestic Violence Ac |
