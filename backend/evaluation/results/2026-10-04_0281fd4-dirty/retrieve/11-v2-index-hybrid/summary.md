# Retrieval evaluation (deterministic checks only)

- Commit: `0281fd4` + uncommitted changes
- Collection: `indian_family_law_cases_hrag_v2` | embedding: `bhavyagiri/InLegal-Sbert`
- Query translation: on (`google/gemma-3-4b-it`) | rewrite: off | hybrid (BM25): on | corpus curation: on
- Queries: 36 | Hugging Face calls this run: 0 embedding, 0 translation, 0 rewrite

Gold lists are 'known relevant', not exhaustive, so recall and hit rates are lower bounds. 'Grouped' treats near-duplicate statute documents as one.

## Overall

| Metric | Value |
|---|---|
| Statute hit rate (at least one gold statute returned) | 0.83 |
| Statute recall, grouped | 0.57 |
| Statute recall, exact ids | 0.45 |
| Precedent hit rate (at least one gold precedent returned) | 0.36 |
| Precedent recall | 0.12 |
| Distinct statutes per query after merging duplicates (of 3) | 3 |
| Queries with an off-topic statute document | 0 of 36 |

## By language

| Language | Queries | Statute hit | Statute recall (grouped) | Precedent hit |
|---|---|---|---|---|
| en | 27 | 0.85 | 0.59 | 0.33 |
| hi | 5 | 0.8 | 0.5 | 0.2 |
| hi-en | 2 | 1 | 0.5 | 1 |
| ta | 2 | 0.5 | 0.5 | 0.5 |

## Language twins (same question, different language)

| Topic | Languages | Shared statutes | Shared precedents |
|---|---|---|---|
| right to reside | hi, en, ta | 0 of 9 | 0 of 12 |
| child custody | en, hi | 1 of 5 | 2 of 8 |
| dowry harassment | en, hi | 2 of 4 | 3 of 7 |
| mutual consent divorce | en, hi | 2 of 4 | 0 of 10 |
| bigamy | en, hi | 1 of 5 | 1 of 9 |

## Statute documents returned most often

| Document | Queries (of 36) |
|---|---|
| Hindu Marriage Act, 1955 – Key Provisions on Marriage, Divorce and Maintenance | 12 |
| Supreme Court Rules Divorced Muslim Women Entitled to Maintenance Under Section 125 CrPC | 8 |
| Hindu Adoptions and Maintenance Act, 1956 – Adoption and Maintenance Provisions | 6 |
| Protection of Women from Domestic Violence Act, 2005 | 5 |
| Supreme Court Rules Child of Muslim Man and Hindu Wife Entitled to Father's Property | 5 |
| Special Marriage Act, 1954 – Key Provisions | 4 |
| Key Provisions of the Indian Divorce Act, 1869 | 4 |
| Kerala HC Declares Marriage Does Not Bar POCSO Rape Prosecution of Minor | 4 |

## Per query

| # | Lang | Topic | Statute hit | Precedent hit | Statutes returned |
|---|---|---|---|---|---|
| 1 | hi | right to reside | no | yes | Special Marriage Act, 1954 – Key Provisions; Supreme Court Constitutes New Bench to Hear R; Muslim Personal Law (Shariat) Application Act |
| 2 | en | right to reside | no | yes | Supreme Court Rules Divorced Muslim Women Ent; Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and |
| 3 | ta | right to reside | yes | yes | Protection of Women from Domestic Violence Ac; Supreme Court permits divorced Muslim women t; Hindu Marriage Act, 1955 – Key Provisions on  |
| 4 | en | child custody | yes | no | Key Provisions of the Indian Divorce Act, 186; Kerala HC Declares Marriage Does Not Bar POCS; Child Custody: Legal and Physical Custody Fra |
| 5 | hi | child custody | yes | no | Child Custody: Legal and Physical Custody Fra; Hindu Marriage Act, 1955 – Key Provisions on ; Guardians and Wards Act, 1890 – Key Provision |
| 6 | en | maintenance (wife) | yes | no | Supreme Court Rules Divorced Muslim Women Ent; Hindu Adoptions and Maintenance Act, 1956 – A; Madras High Court Clarifies Date of Filing fo |
| 7 | hi-en | maintenance + DV | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Protection of Women from Domestic Violence Ac; Supreme Court Rules Divorced Muslim Women Ent |
| 8 | ta | maintenance amount | no | no | Supreme Court Holds Marriage During Pendency ; Muslim Personal Law (Shariat) Application Act; Mahr as a Mandatory Bride‑Wealth Obligation u |
| 9 | en | dowry harassment | no | no | Supreme Court Directions on Queer Rights and ; Kerala HC Declares Marriage Does Not Bar POCS; Mahr as a Mandatory Bride‑Wealth Obligation u |
| 10 | hi | dowry harassment | yes | no | Mahr as a Mandatory Bride‑Wealth Obligation u; Dowry Prohibition Act, 1961; Kerala HC Declares Marriage Does Not Bar POCS |
| 11 | en | domestic violence | yes | no | Protection of Women from Domestic Violence Ac; Kerala HC Declares Marriage Does Not Bar POCS; Supreme Court Directions on Queer Rights and  |
| 12 | en | mutual consent divorce | yes | no | Supreme Court clarifies power to grant mutual; Voidable Marriage under Indian Family Law; Key Provisions of the Indian Divorce Act, 186 |
| 13 | hi | mutual consent divorce | yes | no | Supreme Court clarifies power to grant mutual; Key Provisions of the Indian Divorce Act, 186; Hindu Marriage Act, 1955 – Key Provisions on  |
| 14 | en | cruelty | yes | no | Voidable Marriage under Indian Family Law; Parsi Marriage and Divorce Act, 1936; Hindu Marriage Act, 1955 – Key Provisions on  |
| 15 | en | divorce within one year | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Parsi Marriage and Divorce Act, 1936; Voidable Marriage under Indian Family Law |
| 16 | en | bigamy | yes | no | Special Marriage Act, 1954 – Key Provisions; Bigamy under Indian Family Law; Justice Sanjiv Khanna Recuses from Supreme Co |
| 17 | hi | bigamy | yes | no | Supreme Court Expands Scope of Article 142 in; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| 18 | en | restitution of conjugal rights | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Restitution of Conjugal Rights – Historical D; Supreme Court permits divorced Muslim women t |
| 19 | hi-en | interfaith court marriage | yes | yes | Supreme Court Rules Child of Muslim Man and H; Mahr as a Mandatory Bride‑Wealth Obligation u; Special Marriage Act, 1954 (India) |
| 20 | en | triple talaq | yes | yes | Muslim Personal Law (Shariat) Application Act; Abolition of Triple Talaq in India: Judicial ; Child born of marriage between Muslim man and |
| 21 | en | Muslim woman maintenance | yes | no | Supreme Court Rules Divorced Muslim Women Ent; Supreme Court Rules Child of Muslim Man and H; Bigamy under Indian Family Law |
| 22 | en | daughter's property rights | yes | yes | Ancestral Property and Coparcenary under the ; Supreme Court Rules Child of Muslim Man and H; Hindu Succession Act, 1956 |
| 23 | en | interfaith child's property | yes | - | Supreme Court Rules Child of Muslim Man and H; Hindu Minority and Guardianship Act, 1956; Supreme Court Rules Divorced Muslim Women Ent |
| 24 | en | annulment (impotency) | yes | no | Void Marriage – Legal Definition, Effects and; Supreme Court Holds Marriage During Pendency ; Hindu Marriage Act, 1955 – Key Provisions on  |
| 25 | en | alimony | yes | no | Alimony – Legal Obligation of Spousal Support; Special Marriage Act, 1954 – Key Provisions; Parsi Marriage and Divorce Act, 1936 |
| 26 | en | stridhan | no | yes | Supreme Court Rules Divorced Muslim Women Ent; Supreme Court Rules Child of Muslim Man and H; Hindu Adoptions and Maintenance Act, 1956 – A |
| 27 | en | 498A defence | - | no | Supreme Court Rules Divorced Muslim Women Ent; Voidable Marriage under Indian Family Law; Hindu Adoptions and Maintenance Act, 1956 – A |
| 28 | en | desertion | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Parsi Marriage and Divorce Act, 1936; Key Provisions of the Indian Divorce Act, 186 |
| 29 | en | live-in relationship | yes | yes | Protection of Women from Domestic Violence Ac; Supreme Court Rules Divorced Muslim Women Ent; Supreme Court Rejects Marriage Equality and A |
| 30 | en | visitation rights | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Maternal Bond and Its Relevance to Indian Fam; Child Custody: Legal and Physical Custody Fra |
| 31 | en | foreign divorce validity | yes | no | Bigamy under Indian Family Law; Supreme Court Holds Marriage During Pendency ; Hindu Marriage Act, 1955 – Key Provisions on  |
| 32 | en | adoption | yes | no | Supreme Court Rejects Marriage Equality and A; Hindu Adoptions and Maintenance Act, 1956 – A; Justice Sanjiv Khanna Recuses from Supreme Co |
| 33 | en | guardianship | yes | yes | Hindu Minority and Guardianship Act, 1956; Ashwini Kumar Upadhyay v. Union of India – Un; Guardians and Wards Act, 1890 – Key Provision |
| 34 | en | child marriage | no | no | Special Marriage Act, 1954 (India); Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on  |
| 35 | en | same-sex marriage | yes | - | Mukul Rohatgi urges Supreme Court to declare ; Supreme Court Rejects Marriage Equality and A; Void Marriage – Legal Definition, Effects and |
| 36 | en | free legal aid | yes | - | Legal Services Authorities Act, 1987 – Free L; Supreme Court Allows Single‑Bench Divorce Dec; Protection of Women from Domestic Violence Ac |
