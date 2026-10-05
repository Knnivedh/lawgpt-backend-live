# Retrieval evaluation (deterministic checks only)

- Commit: `0281fd4` + uncommitted changes
- Collection: `indian_family_law_cases_hrag_v2` | embedding: `bhavyagiri/InLegal-Sbert`
- Query translation: on (`gemma4:31b-cloud`) | rewrite: off | hybrid (BM25): on | corpus curation: on | weights keyword 1.0, vector 1.0
- Dataset: `golden_dataset_v2.csv`
- Queries: 200 | model calls this run: 0 embedding, 0 translation, 0 rewrite

Gold lists are 'known relevant', not exhaustive, so recall and hit rates are lower bounds. 'Grouped' treats near-duplicate statute documents as one.

## Overall

| Metric | Value |
|---|---|
| Statute hit rate (at least one gold statute returned) | 0.59 |
| Statute recall, grouped | 0.32 |
| Statute recall, exact ids | 0.31 |
| Precedent hit rate (at least one gold precedent returned) | 0.53 |
| Precedent recall | 0.17 |
| Source post found (rows that have one; not counted as a precedent hit) | 0.26 |
| Distinct statutes per query after merging duplicates (of 3) | 3 |
| Queries with an off-topic statute document | 0 of 200 |

## By language

| Language | Queries | Statute hit | Statute recall (grouped) | Precedent hit |
|---|---|---|---|---|
| English | 40 | 0.64 | 0.33 | 0.62 |
| Hindi | 40 | 0.53 | 0.28 | 0.53 |
| Hinglish | 40 | 0.64 | 0.37 | 0.47 |
| Kannada | 40 | 0.55 | 0.31 | 0.5 |
| Tamil | 40 | 0.58 | 0.34 | 0.5 |

## Language twins (same question, different language)

| Topic | Languages | Shared statutes | Shared precedents |
|---|---|---|---|
| right to reside | English, Hindi, Hinglish, Tamil, Kannada | 0 of 6 | 2 of 12 |
| mutual consent divorce | English, Hindi, Hinglish, Tamil, Kannada | 2 of 4 | 0 of 17 |
| children taken by spouse | English, Hindi, Hinglish, Tamil, Kannada | 1 of 7 | 0 of 17 |
| domestic violence and maintenance | English, Hindi, Hinglish, Tamil, Kannada | 2 of 4 | 1 of 18 |
| jurisdiction for divorce | English, Hindi, Hinglish, Tamil, Kannada | 2 of 5 | 0 of 13 |
| 498A case, settlement and custody | English, Hindi, Hinglish, Tamil, Kannada | 2 of 6 | 1 of 17 |
| threat of false dowry case | English, Hindi, Hinglish, Tamil, Kannada | 0 of 7 | 0 of 11 |
| maintenance for wife and child | English, Hindi, Hinglish, Tamil, Kannada | 2 of 4 | 1 of 13 |
| maintenance claimed by earning wife | English, Hindi, Hinglish, Tamil, Kannada | 2 of 4 | 1 of 16 |
| recovery of unpaid maintenance | English, Hindi, Hinglish, Tamil, Kannada | 0 of 6 | 1 of 12 |
| evidence for mental cruelty | English, Hindi, Hinglish, Tamil, Kannada | 0 of 6 | 4 of 8 |
| divorce without spouse's consent | English, Hindi, Hinglish, Tamil, Kannada | 3 of 3 | 0 of 13 |
| validity of foreign divorce | English, Hindi, Hinglish, Tamil, Kannada | 2 of 5 | 4 of 8 |
| NRI husband abandons wife | English, Hindi, Hinglish, Tamil, Kannada | 1 of 5 | 1 of 11 |
| custody of young child | English, Hindi, Hinglish, Tamil, Kannada | 1 of 6 | 1 of 16 |
| father's visitation | English, Hindi, Hinglish, Tamil, Kannada | 2 of 5 | 1 of 16 |
| dowry harassment complaint | English, Hindi, Hinglish, Tamil, Kannada | 1 of 7 | 1 of 11 |
| return of dowry (Christian family) | English, Hindi, Hinglish, Tamil, Kannada | 0 of 5 | 1 of 14 |
| husband's second marriage | English, Hindi, Hinglish, Tamil, Kannada | 0 of 8 | 3 of 10 |
| restitution decree not obeyed | English, Hindi, Hinglish, Tamil, Kannada | 2 of 5 | 0 of 15 |
| desertion in unconsummated marriage | English, Hindi, Hinglish, Tamil, Kannada | 0 of 7 | 1 of 15 |
| annulment for impotency | English, Hindi, Hinglish, Tamil, Kannada | 0 of 8 | 0 of 14 |
| divorce and return of stridhan | English, Hindi, Hinglish, Tamil, Kannada | 0 of 6 | 1 of 16 |
| instant triple talaq | English, Hindi, Hinglish, Tamil, Kannada | 2 of 4 | 0 of 12 |
| khula (divorce sought by Muslim wife) | English, Hindi, Hinglish, Tamil, Kannada | 2 of 4 | 0 of 13 |
| interfaith marriage under Special Marriage Act | English, Hindi, Hinglish, Tamil, Kannada | 1 of 5 | 3 of 7 |
| daughter's share in ancestral property | English, Hindi, Hinglish, Tamil, Kannada | 0 of 6 | 2 of 6 |
| senior citizen evicting son and daughter-in-law | English, Hindi, Hinglish, Tamil, Kannada | 2 of 4 | 0 of 13 |
| husband's adultery | English, Hindi, Hinglish, Tamil, Kannada | 2 of 5 | 0 of 14 |
| adoption of a stepchild | English, Hindi, Hinglish, Tamil, Kannada | 2 of 4 | 3 of 8 |

## Statute documents returned most often

| Document | Queries (of 200) |
|---|---|
| Hindu Marriage Act, 1955 – Key Provisions on Marriage, Divorce and Maintenance | 99 |
| Hindu Adoptions and Maintenance Act, 1956 – Adoption and Maintenance Provisions | 95 |
| Supreme Court Rules Divorced Muslim Women Entitled to Maintenance Under Section 125 CrPC | 36 |
| Supreme Court Expands Scope of Article 142 in Mutual‑Consent Divorce Decrees | 34 |
| Special Marriage Act, 1954 – Key Provisions | 34 |
| Supreme Court Rules Child of Muslim Man and Hindu Wife Entitled to Father's Property | 34 |
| Hindu Succession Act, 1956 – Intestate Inheritance Rules and Gender Equality Amendment | 33 |
| Child born of marriage between Muslim man and Hindu woman entitled to claim father's property: Supreme Court | 27 |

## Per query

| # | Lang | Topic | Statute hit | Precedent hit | Statutes returned |
|---|---|---|---|---|---|
| P01__en | English | right to reside | no | yes | Supreme Court Directions on Queer Rights and ; Supreme Court permits divorced Muslim women t; Hindu Adoptions and Maintenance Act, 1956 – A |
| P01__hi | Hindi | right to reside | no | yes | Supreme Court Directions on Queer Rights and ; Supreme Court permits divorced Muslim women t; Hindu Adoptions and Maintenance Act, 1956 – A |
| P01__hi-en | Hinglish | right to reside | yes | no | Supreme Court Directions on Queer Rights and ; Supreme Court permits divorced Muslim women t; Protection of Women from Domestic Violence Ac |
| P01__ta | Tamil | right to reside | yes | yes | Supreme Court Directions on Queer Rights and ; Supreme Court permits divorced Muslim women t; Protection of Women from Domestic Violence Ac |
| P01__kn | Kannada | right to reside | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Child born of marriage between Muslim man and; Hindu Minority and Guardianship Act, 1956 |
| P02__en | English | mutual consent divorce | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Expands Scope of Article 142 in; Special Marriage Act, 1954 – Key Provisions |
| P02__hi | Hindi | mutual consent divorce | yes | yes | Supreme Court Expands Scope of Article 142 in; Hindu Marriage Act, 1955 – Key Provisions on ; Voidable Marriage under Indian Family Law |
| P02__hi-en | Hinglish | mutual consent divorce | yes | no | Supreme Court Expands Scope of Article 142 in; Voidable Marriage under Indian Family Law; Hindu Marriage Act, 1955 – Key Provisions on  |
| P02__ta | Tamil | mutual consent divorce | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Supreme Court Expands Scope of Article 142 in |
| P02__kn | Kannada | mutual consent divorce | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Expands Scope of Article 142 in; Special Marriage Act, 1954 – Key Provisions |
| P03__en | English | children taken by spouse | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rejects Marriage Equality and A; Parsi Marriage and Divorce Act, 1936 |
| P03__hi | Hindi | children taken by spouse | no | no | Special Marriage Act, 1954 – Key Provisions; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Declares Child of Muslim Man an |
| P03__hi-en | Hinglish | children taken by spouse | no | no | Special Marriage Act, 1954 – Key Provisions; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rules Child of Muslim Man and H |
| P03__ta | Tamil | children taken by spouse | no | no | Special Marriage Act, 1954 – Key Provisions; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rejects Marriage Equality and A |
| P03__kn | Kannada | children taken by spouse | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 – Key Provisions; Hindu Succession Act, 1956 – Intestate Inheri |
| P04__en | English | domestic violence and maintenance | yes | yes | Supreme Court Expands Scope of Article 142 in; Hindu Succession Act, 1956 – Intestate Inheri; Hindu Marriage Act, 1955 – Key Provisions on  |
| P04__hi | Hindi | domestic violence and maintenance | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Expands Scope of Article 142 in; Hindu Succession Act, 1956 – Intestate Inheri |
| P04__hi-en | Hinglish | domestic violence and maintenance | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Rejects Marriage Equality and A; Supreme Court Expands Scope of Article 142 in |
| P04__ta | Tamil | domestic violence and maintenance | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Expands Scope of Article 142 in; Hindu Succession Act, 1956 – Intestate Inheri |
| P04__kn | Kannada | domestic violence and maintenance | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Expands Scope of Article 142 in; Supreme Court Rejects Marriage Equality and A |
| P05__en | English | jurisdiction for divorce | yes | yes | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Parsi Marriage and Divorce Act, 1936 |
| P05__hi | Hindi | jurisdiction for divorce | yes | yes | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Rules Child of Muslim Man and H |
| P05__hi-en | Hinglish | jurisdiction for divorce | yes | no | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Parsi Marriage and Divorce Act, 1936 |
| P05__ta | Tamil | jurisdiction for divorce | yes | yes | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Rules Child of Muslim Man and H |
| P05__kn | Kannada | jurisdiction for divorce | yes | no | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Expands Scope of Article 142 in |
| P06__en | English | 498A case, settlement and custody | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Succession Act, 1956 – Intestate Inheri |
| P06__hi | Hindi | 498A case, settlement and custody | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Prenuptial Agreements and Their Limited Recog |
| P06__hi-en | Hinglish | 498A case, settlement and custody | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Special Marriage Act, 1954 – Key Provisions |
| P06__ta | Tamil | 498A case, settlement and custody | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Parsi Marriage and Divorce Act, 1936 |
| P06__kn | Kannada | 498A case, settlement and custody | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Parsi Marriage and Divorce Act, 1936 |
| P07__en | English | threat of false dowry case | no | yes | Supreme Court Directions on Queer Rights and ; Ashwini Kumar Upadhyay v. Union of India – Un; Mahr as a Mandatory Bride‑Wealth Obligation u |
| P07__hi | Hindi | threat of false dowry case | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Mahr as a Mandatory Bride‑Wealth Obligation u; Prenuptial Agreements and Their Limited Recog |
| P07__hi-en | Hinglish | threat of false dowry case | no | yes | Supreme Court Directions on Queer Rights and ; Prenuptial Agreements and Their Limited Recog; Protection of Women from Domestic Violence Ac |
| P07__ta | Tamil | threat of false dowry case | no | yes | Supreme Court Directions on Queer Rights and ; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Expands Scope of Article 142 in |
| P07__kn | Kannada | threat of false dowry case | no | yes | Supreme Court Directions on Queer Rights and ; Supreme Court Expands Scope of Article 142 in; Protection of Women from Domestic Violence Ac |
| P08__en | English | maintenance for wife and child | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rules Divorced Muslim Women Ent; Hindu Marriage Act, 1955 – Key Provisions on  |
| P08__hi | Hindi | maintenance for wife and child | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rules Divorced Muslim Women Ent; Hindu Marriage Act, 1955 – Key Provisions on  |
| P08__hi-en | Hinglish | maintenance for wife and child | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rules Divorced Muslim Women Ent; Child born of marriage between Muslim man and |
| P08__ta | Tamil | maintenance for wife and child | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Rules Divorced Muslim Women Ent |
| P08__kn | Kannada | maintenance for wife and child | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Rules Divorced Muslim Women Ent |
| P09__en | English | maintenance claimed by earning wife | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Mahr as a Mandatory Bride‑Wealth Obligation u |
| P09__hi | Hindi | maintenance claimed by earning wife | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Rules Divorced Muslim Women Ent |
| P09__hi-en | Hinglish | maintenance claimed by earning wife | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rules Divorced Muslim Women Ent |
| P09__ta | Tamil | maintenance claimed by earning wife | yes | yes | Supreme Court Rules Divorced Muslim Women Ent; Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on  |
| P09__kn | Kannada | maintenance claimed by earning wife | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Rules Divorced Muslim Women Ent |
| P10__en | English | recovery of unpaid maintenance | no | no | Kerala HC Declares Marriage Does Not Bar POCS; Mahr as a Mandatory Bride‑Wealth Obligation u; Supreme Court Holds Marriage During Pendency  |
| P10__hi | Hindi | recovery of unpaid maintenance | no | yes | Muslim Personal Law (Shariat) Application Act; Mahr as a Mandatory Bride‑Wealth Obligation u; Supreme Court Holds Marriage During Pendency  |
| P10__hi-en | Hinglish | recovery of unpaid maintenance | no | yes | Supreme Court Holds Marriage During Pendency ; Muslim Personal Law (Shariat) Application Act; Mahr as a Mandatory Bride‑Wealth Obligation u |
| P10__ta | Tamil | recovery of unpaid maintenance | no | yes | Supreme Court permits divorced Muslim women t; Supreme Court Holds Marriage During Pendency ; Kerala HC Declares Marriage Does Not Bar POCS |
| P10__kn | Kannada | recovery of unpaid maintenance | no | no | Supreme Court permits divorced Muslim women t; Hindu Adoptions and Maintenance Act, 1956 – A; Mahr as a Mandatory Bride‑Wealth Obligation u |
| P11__en | English | evidence for mental cruelty | yes | yes | Parsi Marriage and Divorce Act, 1936; Hindu Marriage Act, 1955 – Key Provisions on ; Voidable Marriage under Indian Family Law |
| P11__hi | Hindi | evidence for mental cruelty | yes | yes | Parsi Marriage and Divorce Act, 1936; Hindu Marriage Act, 1955 – Key Provisions on ; Voidable Marriage under Indian Family Law |
| P11__hi-en | Hinglish | evidence for mental cruelty | yes | yes | Parsi Marriage and Divorce Act, 1936; Hindu Marriage Act, 1955 – Key Provisions on ; Voidable Marriage under Indian Family Law |
| P11__ta | Tamil | evidence for mental cruelty | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Parsi Marriage and Divorce Act, 1936; Special Marriage Act, 1954 – Key Provisions |
| P11__kn | Kannada | evidence for mental cruelty | no | yes | Supreme Court Constitutes New Bench to Hear R; Voidable Marriage under Indian Family Law; Prenuptial Agreements and Their Limited Recog |
| P12__en | English | divorce without spouse's consent | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Supreme Court Expands Scope of Article 142 in |
| P12__hi | Hindi | divorce without spouse's consent | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Supreme Court Expands Scope of Article 142 in |
| P12__hi-en | Hinglish | divorce without spouse's consent | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Supreme Court Expands Scope of Article 142 in |
| P12__ta | Tamil | divorce without spouse's consent | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Supreme Court Expands Scope of Article 142 in |
| P12__kn | Kannada | divorce without spouse's consent | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Supreme Court Expands Scope of Article 142 in |
| P13__en | English | validity of foreign divorce | - | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Parsi Marriage and Divorce Act, 1936; Bigamy under Indian Family Law |
| P13__hi | Hindi | validity of foreign divorce | - | yes | Parsi Marriage and Divorce Act, 1936; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| P13__hi-en | Hinglish | validity of foreign divorce | - | yes | Parsi Marriage and Divorce Act, 1936; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Expands Scope of Article 142 in |
| P13__ta | Tamil | validity of foreign divorce | - | yes | Parsi Marriage and Divorce Act, 1936; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Expands Scope of Article 142 in |
| P13__kn | Kannada | validity of foreign divorce | - | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Parsi Marriage and Divorce Act, 1936; Supreme Court Expands Scope of Article 142 in |
| P14__en | English | NRI husband abandons wife | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Parsi Marriage and Divorce Act, 1936; Supreme Court to Hear Review Petitions on Sam |
| P14__hi | Hindi | NRI husband abandons wife | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Parsi Marriage and Divorce Act, 1936 |
| P14__hi-en | Hinglish | NRI husband abandons wife | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Parsi Marriage and Divorce Act, 1936 |
| P14__ta | Tamil | NRI husband abandons wife | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Parsi Marriage and Divorce Act, 1936 |
| P14__kn | Kannada | NRI husband abandons wife | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Succession Act, 1956 – Intestate Inheri |
| P15__en | English | custody of young child | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Protection of Women from Domestic Violence Ac |
| P15__hi | Hindi | custody of young child | no | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Protection of Women from Domestic Violence Ac |
| P15__hi-en | Hinglish | custody of young child | no | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Protection of Women from Domestic Violence Ac |
| P15__ta | Tamil | custody of young child | no | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 – Key Provisions |
| P15__kn | Kannada | custody of young child | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Succession Act, 1956 |
| P16__en | English | father's visitation | yes | yes | Ashwini Kumar Upadhyay v. Union of India – Un; Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Minority and Guardianship Act, 1956 |
| P16__hi | Hindi | father's visitation | no | yes | Ashwini Kumar Upadhyay v. Union of India – Un; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Holds Marriage During Pendency  |
| P16__hi-en | Hinglish | father's visitation | yes | yes | Ashwini Kumar Upadhyay v. Union of India – Un; Hindu Minority and Guardianship Act, 1956; Hindu Adoptions and Maintenance Act, 1956 – A |
| P16__ta | Tamil | father's visitation | no | yes | Ashwini Kumar Upadhyay v. Union of India – Un; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Declares Child of Muslim Man an |
| P16__kn | Kannada | father's visitation | no | yes | Ashwini Kumar Upadhyay v. Union of India – Un; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Declares Child of Muslim Man an |
| P17__en | English | dowry harassment complaint | no | yes | Supreme Court Directions on Queer Rights and ; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| P17__hi | Hindi | dowry harassment complaint | no | yes | Supreme Court Directions on Queer Rights and ; Mahr as a Mandatory Bride‑Wealth Obligation u; Hindu Marriage Act, 1955 – Key Provisions on  |
| P17__hi-en | Hinglish | dowry harassment complaint | no | yes | Supreme Court Directions on Queer Rights and ; Mahr as a Mandatory Bride‑Wealth Obligation u; Hindu Marriage Act, 1955 – Key Provisions on  |
| P17__ta | Tamil | dowry harassment complaint | no | yes | Supreme Court Directions on Queer Rights and ; Child born of marriage between Muslim man and; Supreme Court Rules Divorced Muslim Women Ent |
| P17__kn | Kannada | dowry harassment complaint | no | yes | Supreme Court Directions on Queer Rights and ; Supreme Court Rules Child of Muslim Man and H; Special Marriage Act, 1954 – Key Provisions |
| P18__en | English | return of dowry (Christian family) | no | yes | Hindu Succession Act, 1956 – Intestate Inheri; Hindu Minority and Guardianship Act, 1956; Child born of marriage between Muslim man and |
| P18__hi | Hindi | return of dowry (Christian family) | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and |
| P18__hi-en | Hinglish | return of dowry (Christian family) | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Minority and Guardianship Act, 1956; Child born of marriage between Muslim man and |
| P18__ta | Tamil | return of dowry (Christian family) | no | no | Hindu Succession Act, 1956 – Intestate Inheri; Hindu Minority and Guardianship Act, 1956; Child born of marriage between Muslim man and |
| P18__kn | Kannada | return of dowry (Christian family) | no | no | Hindu Minority and Guardianship Act, 1956; Hindu Succession Act, 1956 – Intestate Inheri; Hindu Marriage Act, 1955 – Key Provisions on  |
| P19__en | English | husband's second marriage | yes | no | Voidable Marriage under Indian Family Law; Supreme Court Rules Child of Muslim Man and H; Bigamy under Indian Family Law |
| P19__hi | Hindi | husband's second marriage | no | no | Supreme Court Rules Child of Muslim Man and H; Hindu Succession Act, 1956; Supreme Court Rules Divorced Muslim Women Ent |
| P19__hi-en | Hinglish | husband's second marriage | no | no | Supreme Court Rules Child of Muslim Man and H; Supreme Court Rules Divorced Muslim Women Ent; Hindu Succession Act, 1956 |
| P19__ta | Tamil | husband's second marriage | yes | no | Child born of marriage between Muslim man and; Bigamy under Indian Family Law; Mahr as a Mandatory Bride‑Wealth Obligation u |
| P19__kn | Kannada | husband's second marriage | no | no | Child born of marriage between Muslim man and; Supreme Court Expands Scope of Article 142 in; Mahr as a Mandatory Bride‑Wealth Obligation u |
| P20__en | English | restitution decree not obeyed | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Parsi Marriage and Divorce Act, 1936; Restitution of Conjugal Rights – Historical D |
| P20__hi | Hindi | restitution decree not obeyed | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Restitution of Conjugal Rights – Historical D; Parsi Marriage and Divorce Act, 1936 |
| P20__hi-en | Hinglish | restitution decree not obeyed | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Restitution of Conjugal Rights – Historical D; Supreme Court Rejects Marriage Equality and A |
| P20__ta | Tamil | restitution decree not obeyed | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Restitution of Conjugal Rights – Historical D; Supreme Court Rejects Marriage Equality and A |
| P20__kn | Kannada | restitution decree not obeyed | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Expands Scope of Article 142 in; Restitution of Conjugal Rights – Historical D |
| P21__en | English | desertion in unconsummated marriage | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court to Hear Review Petitions on Sam; Hindu Adoptions and Maintenance Act, 1956 – A |
| P21__hi | Hindi | desertion in unconsummated marriage | yes | no | Supreme Court to Hear Review Petitions on Sam; Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A |
| P21__hi-en | Hinglish | desertion in unconsummated marriage | no | no | Supreme Court Expands Scope of Article 142 in; Supreme Court to Hear Review Petitions on Sam; Abolition of Triple Talaq in India: Judicial  |
| P21__ta | Tamil | desertion in unconsummated marriage | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court to Hear Review Petitions on Sam; Special Marriage Act, 1954 – Key Provisions |
| P21__kn | Kannada | desertion in unconsummated marriage | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court to Hear Review Petitions on Sam; Supreme Court Expands Scope of Article 142 in |
| P22__en | English | annulment for impotency | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Voidable Marriage under Indian Family Law; Bigamy under Indian Family Law |
| P22__hi | Hindi | annulment for impotency | yes | yes | Muslim Personal Law (Shariat) Application Act; Hindu Adoptions and Maintenance Act, 1956 – A; Voidable Marriage under Indian Family Law |
| P22__hi-en | Hinglish | annulment for impotency | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Expands Scope of Article 142 in; Voidable Marriage under Indian Family Law |
| P22__ta | Tamil | annulment for impotency | yes | yes | Kerala HC Declares Marriage Does Not Bar POCS; Muslim Personal Law (Shariat) Application Act; Void Marriage – Legal Definition, Effects and |
| P22__kn | Kannada | annulment for impotency | yes | yes | Muslim Personal Law (Shariat) Application Act; Voidable Marriage under Indian Family Law; Hindu Marriage Act, 1955 – Key Provisions on  |
| P23__en | English | divorce and return of stridhan | no | no | Supreme Court Rules Divorced Muslim Women Ent; Supreme Court Rules Child of Muslim Man and H; Muslim Personal Law (Shariat) Application Act |
| P23__hi | Hindi | divorce and return of stridhan | yes | no | Supreme Court Rules Divorced Muslim Women Ent; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Rules Child of Muslim Man and H |
| P23__hi-en | Hinglish | divorce and return of stridhan | yes | no | Supreme Court Rules Divorced Muslim Women Ent; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Rules Child of Muslim Man and H |
| P23__ta | Tamil | divorce and return of stridhan | no | no | Supreme Court Rules Child of Muslim Man and H; Supreme Court Rules Divorced Muslim Women Ent; Supreme Court Expands Scope of Article 142 in |
| P23__kn | Kannada | divorce and return of stridhan | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Mahr as a Mandatory Bride‑Wealth Obligation u; Muslim Personal Law (Shariat) Application Act |
| P24__en | English | instant triple talaq | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rules Child of Muslim Man and H; Supreme Court Rules Divorced Muslim Women Ent |
| P24__hi | Hindi | instant triple talaq | yes | yes | Supreme Court Rules Child of Muslim Man and H; Hindu Adoptions and Maintenance Act, 1956 – A; Muslim Personal Law (Shariat) Application Act |
| P24__hi-en | Hinglish | instant triple talaq | yes | yes | Supreme Court Rules Child of Muslim Man and H; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rules Divorced Muslim Women Ent |
| P24__ta | Tamil | instant triple talaq | yes | yes | Supreme Court Rules Child of Muslim Man and H; Supreme Court Rules Divorced Muslim Women Ent; Hindu Adoptions and Maintenance Act, 1956 – A |
| P24__kn | Kannada | instant triple talaq | yes | yes | Supreme Court Rules Child of Muslim Man and H; Supreme Court Rules Divorced Muslim Women Ent; Hindu Adoptions and Maintenance Act, 1956 – A |
| P25__en | English | khula (divorce sought by Muslim wife) | no | no | Bigamy under Indian Family Law; Supreme Court Rules Child of Muslim Man and H; Supreme Court Rules Divorced Muslim Women Ent |
| P25__hi | Hindi | khula (divorce sought by Muslim wife) | no | no | Supreme Court Rules Divorced Muslim Women Ent; Supreme Court Rules Child of Muslim Man and H; Bigamy under Indian Family Law |
| P25__hi-en | Hinglish | khula (divorce sought by Muslim wife) | no | no | Supreme Court Rules Child of Muslim Man and H; Hindu Marriage Act, 1955 – Key Provisions on ; Bigamy under Indian Family Law |
| P25__ta | Tamil | khula (divorce sought by Muslim wife) | no | no | Supreme Court Rules Divorced Muslim Women Ent; Bigamy under Indian Family Law; Supreme Court Rules Child of Muslim Man and H |
| P25__kn | Kannada | khula (divorce sought by Muslim wife) | no | no | Supreme Court Rules Divorced Muslim Women Ent; Supreme Court Rules Child of Muslim Man and H; Bigamy under Indian Family Law |
| P26__en | English | interfaith marriage under Special Marriage Act | yes | yes | Special Marriage Act, 1954 (India); Child born of marriage between Muslim man and; Hindu Marriage Act, 1955 – Key Provisions on  |
| P26__hi | Hindi | interfaith marriage under Special Marriage Act | yes | yes | Special Marriage Act, 1954 (India); Hindu Marriage Act, 1955 – Key Provisions on ; Bigamy under Indian Family Law |
| P26__hi-en | Hinglish | interfaith marriage under Special Marriage Act | yes | yes | Special Marriage Act, 1954 (India); Hindu Marriage Act, 1955 – Key Provisions on ; Bigamy under Indian Family Law |
| P26__ta | Tamil | interfaith marriage under Special Marriage Act | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Rules Child of Muslim Man and H; Special Marriage Act, 1954 (India) |
| P26__kn | Kannada | interfaith marriage under Special Marriage Act | yes | yes | Child born of marriage between Muslim man and; Special Marriage Act, 1954 (India); Bigamy under Indian Family Law |
| P27__en | English | daughter's share in ancestral property | yes | yes | Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and; Hindu Adoptions and Maintenance Act, 1956 – A |
| P27__hi | Hindi | daughter's share in ancestral property | yes | yes | Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and; Ancestral Property and Coparcenary under the  |
| P27__hi-en | Hinglish | daughter's share in ancestral property | yes | yes | Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and; Ancestral Property and Coparcenary under the  |
| P27__ta | Tamil | daughter's share in ancestral property | yes | yes | Hindu Succession Act, 1956 – Intestate Inheri; Ancestral Property and Coparcenary under the ; Supreme Court Rules Divorced Muslim Women Ent |
| P27__kn | Kannada | daughter's share in ancestral property | yes | yes | Hindu Succession Act, 1956; Child born of marriage between Muslim man and; Hindu Adoptions and Maintenance Act, 1956 – A |
| P28__en | English | senior citizen evicting son and daughter-in-law | - | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Minority and Guardianship Act, 1956; Hindu Marriage Act, 1955 – Key Provisions on  |
| P28__hi | Hindi | senior citizen evicting son and daughter-in-law | - | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| P28__hi-en | Hinglish | senior citizen evicting son and daughter-in-law | - | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Minority and Guardianship Act, 1956; Hindu Marriage Act, 1955 – Key Provisions on  |
| P28__ta | Tamil | senior citizen evicting son and daughter-in-law | - | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| P28__kn | Kannada | senior citizen evicting son and daughter-in-law | - | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| P29__en | English | husband's adultery | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rules Divorced Muslim Women Ent; Supreme Court Expands Scope of Article 142 in |
| P29__hi | Hindi | husband's adultery | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Kerala HC Declares Marriage Does Not Bar POCS; Supreme Court Rules Divorced Muslim Women Ent |
| P29__hi-en | Hinglish | husband's adultery | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Kerala HC Declares Marriage Does Not Bar POCS; Supreme Court Rules Divorced Muslim Women Ent |
| P29__ta | Tamil | husband's adultery | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Rules Divorced Muslim Women Ent |
| P29__kn | Kannada | husband's adultery | yes | yes | Supreme Court Rules Divorced Muslim Women Ent; Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on  |
| P30__en | English | adoption of a stepchild | yes | yes | Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and; Hindu Adoptions and Maintenance Act, 1956 – A |
| P30__hi | Hindi | adoption of a stepchild | yes | yes | Child born of marriage between Muslim man and; Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri |
| P30__hi-en | Hinglish | adoption of a stepchild | yes | yes | Child born of marriage between Muslim man and; Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri |
| P30__ta | Tamil | adoption of a stepchild | yes | yes | Supreme Court Rules Child of Muslim Man and H; Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri |
| P30__kn | Kannada | adoption of a stepchild | yes | yes | Supreme Court Rules Child of Muslim Man and H; Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri |
| L-en-01__en | English | one-time alimony in mutual consent divorce | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Parsi Marriage and Divorce Act, 1936; Supreme Court Expands Scope of Article 142 in |
| L-en-02__en | English | 498A FIR against husband living abroad | - | yes | Supreme Court Directions on Queer Rights and ; Supreme Court Rejects Marriage Equality and A; Abolition of Triple Talaq in India: Judicial  |
| L-en-03__en | English | consent withdrawn before second motion | yes | yes | Supreme Court Expands Scope of Article 142 in; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Constitutes New Bench to Hear R |
| L-en-04__en | English | reducing maintenance after remarriage | yes | yes | Mahr as a Mandatory Bride‑Wealth Obligation u; Hindu Marriage Act, 1955 – Key Provisions on ; Muslim Personal Law (Shariat) Application Act |
| L-en-05__en | English | stepfather's name in child's records | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rules Divorced Muslim Women Ent; Hindu Succession Act, 1956 – Intestate Inheri |
| L-en-06__en | English | will and later unregistered revocation | - | no | Hindu Succession Act, 1956 – Intestate Inheri; Abolition of Triple Talaq in India: Judicial ; Hindu Marriage Act, 1955 – Key Provisions on  |
| L-en-07__en | English | opposing wife's guardianship petition | yes | yes | Hindu Minority and Guardianship Act, 1956; Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on  |
| L-en-08__en | English | in-laws allege concealment of past illness | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Bigamy under Indian Family Law; Supreme Court Rejects Marriage Equality and A |
| L-en-09__en | English | precautions before wife files cases | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Supreme Court Rules Child of Muslim Man and H |
| L-en-10__en | English | husband concealed sexual orientation | yes | no | Allahabad HC Declares UP Conversion Act Does ; Supreme Court Rejects Marriage Equality and A; Voidable Marriage under Indian Family Law |
| L-hi-01__hi | Hindi | domestic violence by alcoholic husband | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rejects Marriage Equality and A; Special Marriage Act, 1954 – Key Provisions |
| L-hi-02__hi | Hindi | dowry demand (father asking for daughter) | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and |
| L-hi-03__hi | Hindi | bringing wife back (restitution) | no | no | Supreme Court Directions on Queer Rights and ; Supreme Court Expands Scope of Article 142 in; Supreme Court Constitutes New Bench to Hear R |
| L-hi-04__hi | Hindi | sisters' share in ancestral farmland | yes | yes | Hindu Succession Act, 1956; Child born of marriage between Muslim man and; Ancestral Property and Coparcenary under the  |
| L-hi-05__hi | Hindi | Muslim husband's second nikah and maintenance | yes | yes | Supreme Court Rules Divorced Muslim Women Ent; Bigamy under Indian Family Law; Supreme Court Rules Child of Muslim Man and H |
| L-hi-06__hi | Hindi | widow's rights in husband's property | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Minority and Guardianship Act, 1956; Child born of marriage between Muslim man and |
| L-hi-07__hi | Hindi | protection after inter-caste court marriage | no | yes | Supreme Court Directions on Queer Rights and ; Kerala HC Declares Marriage Does Not Bar POCS; Family Courts: Historical Development, Statut |
| L-hi-08__hi | Hindi | child's expenses after divorce | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Mahr as a Mandatory Bride‑Wealth Obligation u |
| L-hi-09__hi | Hindi | wife's adultery, divorce and custody | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Child born of marriage between Muslim man and; Supreme Court Rules Divorced Muslim Women Ent |
| L-hi-10__hi | Hindi | husband abroad, no contact or money | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Parsi Marriage and Divorce Act, 1936 |
| L-hien-01__hi-en | Hinglish | anticipatory bail in 498A case | - | no | Ashwini Kumar Upadhyay v. Union of India – Un; Abolition of Triple Talaq in India: Judicial ; Supreme Court Directions on Queer Rights and  |
| L-hien-02__hi-en | Hinglish | annulment for husband's impotency | yes | yes | Supreme Court Holds Marriage During Pendency ; Supreme Court Allows Video‑Conferencing Regis; Voidable Marriage under Indian Family Law |
| L-hien-03__hi-en | Hinglish | maintenance from husband working abroad | yes | no | Supreme Court Rules Child of Muslim Man and H; Hindu Marriage Act, 1955 – Provisions, Applic; Supreme Court Rules Divorced Muslim Women Ent |
| L-hien-04__hi-en | Hinglish | visitation order not obeyed | no | no | Kerala HC Declares Marriage Does Not Bar POCS; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rules Child of Muslim Man and H |
| L-hien-05__hi-en | Hinglish | married daughter's right in parents' self-acquired property | yes | no | Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and; Hindu Adoptions and Maintenance Act, 1956 – A |
| L-hien-06__hi-en | Hinglish | threat of rape case after live-in relationship | - | no | Kerala HC Declares Marriage Does Not Bar POCS; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Directions on Queer Rights and  |
| L-hien-07__hi-en | Hinglish | waiver of cooling-off period | yes | yes | Supreme Court Expands Scope of Article 142 in; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| L-hien-08__hi-en | Hinglish | property rights of second wife and her children | yes | yes | Child born of marriage between Muslim man and; Hindu Succession Act, 1956 – Intestate Inheri; Hindu Adoptions and Maintenance Act, 1956 – A |
| L-hien-09__hi-en | Hinglish | wife demands separate residence | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Succession Act, 1956 – Intestate Inheri |
| L-hien-10__hi-en | Hinglish | wife's earlier undissolved marriage | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Expands Scope of Article 142 in; Supreme Court Rules Child of Muslim Man and H |
| L-ta-01__ta | Tamil | protection from violent alcoholic husband | no | no | Supreme Court Directions on Queer Rights and ; Hindu Adoptions and Maintenance Act, 1956 – A; Child born of marriage between Muslim man and |
| L-ta-02__ta | Tamil | father denied access to child | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Child born of marriage between Muslim man and; Hindu Marriage Act, 1955 – Key Provisions on  |
| L-ta-03__ta | Tamil | dowry demand and jewellery held by in-laws | no | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Mahr as a Mandatory Bride‑Wealth Obligation u |
| L-ta-04__ta | Tamil | divorce law for Christians | no | no | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Uniform Civil Code – proposal for a common pe |
| L-ta-05__ta | Tamil | customary marriage with sister's daughter | yes | yes | Prenuptial Agreements and Their Limited Recog; Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on  |
| L-ta-06__ta | Tamil | husband abroad living with another woman | yes | no | Supreme Court Rules Child of Muslim Man and H; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court allows divorced Muslim women to |
| L-ta-07__ta | Tamil | harassment by mother-in-law, separate residence | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Protection of Women from Domestic Violence Ac |
| L-ta-08__ta | Tamil | bringing wife back (voice input) | yes | no | Supreme Court Expands Scope of Article 142 in; Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on  |
| L-ta-09__ta | Tamil | remarrying while divorce is pending | no | no | Supreme Court Marriage Equality Case: Mukul R; Supreme Court Rejects Marriage Equality and A; Kerala HC Declares Marriage Does Not Bar POCS |
| L-ta-10__ta | Tamil | proving an unregistered temple marriage | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 – Key Provisions; Supreme Court Rules Child of Muslim Man and H |
| L-kn-01__kn | Kannada | how much maintenance a court fixes | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rules Child of Muslim Man and H; Supreme Court permits divorced Muslim women t |
| L-kn-02__kn | Kannada | replying to a divorce legal notice | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Parsi Marriage and Divorce Act, 1936 |
| L-kn-03__kn | Kannada | dowry harassment by mother-in-law and sister-in-law | no | no | Supreme Court Rules Child of Muslim Man and H; Supreme Court Directions on Queer Rights and ; Hindu Marriage Act, 1955 – Key Provisions on  |
| L-kn-04__kn | Kannada | custody when the father earns more | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Kerala HC Declares Marriage Does Not Bar POCS |
| L-kn-05__kn | Kannada | rights of a second wife | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Child born of marriage between Muslim man and; Hindu Marriage Act, 1955 – Key Provisions on  |
| L-kn-06__kn | Kannada | late registration of marriage | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Void Marriage – Legal Definition, Effects and; Special Marriage Act, 1954 – Key Provisions |
| L-kn-07__kn | Kannada | husband's affair (voice input) | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 (India) |
| L-kn-08__kn | Kannada | mehr and maintenance after talaq | yes | no | Supreme Court Rules Divorced Muslim Women Ent; Muslim Personal Law (Shariat) Application Act; Supreme Court Rules Child of Muslim Man and H |
| L-kn-09__kn | Kannada | husband hiding income in maintenance case | no | yes | Supreme Court Rules Divorced Muslim Women Ent; Protection of Women from Domestic Violence Ac; Supreme Court Holds Marriage During Pendency  |
| L-kn-10__kn | Kannada | adopting a relative's child | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Rejects Marriage Equality and A; Hindu Marriage Act, 1955 – Key Provisions on  |
