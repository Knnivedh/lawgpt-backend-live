# Retrieval evaluation (deterministic checks only)

- Commit: `0281fd4` + uncommitted changes
- Collection: `indian_family_law_cases_hrag_test` | embedding: `bhavyagiri/InLegal-Sbert`
- Query translation: on (`gemma4:31b-cloud`) | rewrite: off | hybrid (BM25): on | corpus curation: on
- Dataset: `golden_dataset_v2.csv`
- Queries: 200 | model calls this run: 0 embedding, 0 translation, 0 rewrite

Gold lists are 'known relevant', not exhaustive, so recall and hit rates are lower bounds. 'Grouped' treats near-duplicate statute documents as one.

## Overall

| Metric | Value |
|---|---|
| Statute hit rate (at least one gold statute returned) | 0.65 |
| Statute recall, grouped | 0.36 |
| Statute recall, exact ids | 0.33 |
| Precedent hit rate (at least one gold precedent returned) | 0.47 |
| Precedent recall | 0.14 |
| Source post found (rows that have one; not counted as a precedent hit) | 0.22 |
| Distinct statutes per query after merging duplicates (of 3) | 3 |
| Queries with an off-topic statute document | 0 of 200 |

## By language

| Language | Queries | Statute hit | Statute recall (grouped) | Precedent hit |
|---|---|---|---|---|
| English | 40 | 0.64 | 0.34 | 0.6 |
| Hindi | 40 | 0.68 | 0.38 | 0.47 |
| Hinglish | 40 | 0.69 | 0.38 | 0.42 |
| Kannada | 40 | 0.68 | 0.38 | 0.4 |
| Tamil | 40 | 0.55 | 0.3 | 0.45 |

## Language twins (same question, different language)

| Topic | Languages | Shared statutes | Shared precedents |
|---|---|---|---|
| right to reside | English, Hindi, Hinglish, Tamil, Kannada | 0 of 6 | 0 of 10 |
| mutual consent divorce | English, Hindi, Hinglish, Tamil, Kannada | 1 of 6 | 1 of 14 |
| children taken by spouse | English, Hindi, Hinglish, Tamil, Kannada | 1 of 4 | 0 of 15 |
| domestic violence and maintenance | English, Hindi, Hinglish, Tamil, Kannada | 2 of 4 | 1 of 17 |
| jurisdiction for divorce | English, Hindi, Hinglish, Tamil, Kannada | 1 of 6 | 0 of 12 |
| 498A case, settlement and custody | English, Hindi, Hinglish, Tamil, Kannada | 0 of 7 | 0 of 20 |
| threat of false dowry case | English, Hindi, Hinglish, Tamil, Kannada | 1 of 6 | 2 of 10 |
| maintenance for wife and child | English, Hindi, Hinglish, Tamil, Kannada | 2 of 5 | 1 of 13 |
| maintenance claimed by earning wife | English, Hindi, Hinglish, Tamil, Kannada | 1 of 5 | 0 of 14 |
| recovery of unpaid maintenance | English, Hindi, Hinglish, Tamil, Kannada | 2 of 5 | 1 of 9 |
| evidence for mental cruelty | English, Hindi, Hinglish, Tamil, Kannada | 1 of 6 | 2 of 12 |
| divorce without spouse's consent | English, Hindi, Hinglish, Tamil, Kannada | 3 of 3 | 1 of 13 |
| validity of foreign divorce | English, Hindi, Hinglish, Tamil, Kannada | 1 of 5 | 3 of 11 |
| NRI husband abandons wife | English, Hindi, Hinglish, Tamil, Kannada | 2 of 5 | 0 of 15 |
| custody of young child | English, Hindi, Hinglish, Tamil, Kannada | 3 of 3 | 0 of 18 |
| father's visitation | English, Hindi, Hinglish, Tamil, Kannada | 0 of 8 | 0 of 17 |
| dowry harassment complaint | English, Hindi, Hinglish, Tamil, Kannada | 0 of 8 | 3 of 9 |
| return of dowry (Christian family) | English, Hindi, Hinglish, Tamil, Kannada | 0 of 6 | 0 of 18 |
| husband's second marriage | English, Hindi, Hinglish, Tamil, Kannada | 0 of 6 | 2 of 11 |
| restitution decree not obeyed | English, Hindi, Hinglish, Tamil, Kannada | 2 of 5 | 1 of 15 |
| desertion in unconsummated marriage | English, Hindi, Hinglish, Tamil, Kannada | 0 of 7 | 2 of 13 |
| annulment for impotency | English, Hindi, Hinglish, Tamil, Kannada | 1 of 6 | 1 of 13 |
| divorce and return of stridhan | English, Hindi, Hinglish, Tamil, Kannada | 0 of 7 | 1 of 14 |
| instant triple talaq | English, Hindi, Hinglish, Tamil, Kannada | 2 of 5 | 0 of 11 |
| khula (divorce sought by Muslim wife) | English, Hindi, Hinglish, Tamil, Kannada | 0 of 6 | 1 of 12 |
| interfaith marriage under Special Marriage Act | English, Hindi, Hinglish, Tamil, Kannada | 2 of 5 | 2 of 12 |
| daughter's share in ancestral property | English, Hindi, Hinglish, Tamil, Kannada | 0 of 5 | 4 of 7 |
| senior citizen evicting son and daughter-in-law | English, Hindi, Hinglish, Tamil, Kannada | 2 of 4 | 0 of 12 |
| husband's adultery | English, Hindi, Hinglish, Tamil, Kannada | 2 of 4 | 0 of 12 |
| adoption of a stepchild | English, Hindi, Hinglish, Tamil, Kannada | 3 of 3 | 3 of 8 |

## Statute documents returned most often

| Document | Queries (of 200) |
|---|---|
| Hindu Marriage Act, 1955 – Key Provisions on Marriage, Divorce and Maintenance | 109 |
| Hindu Adoptions and Maintenance Act, 1956 – Adoption and Maintenance Provisions | 83 |
| Special Marriage Act, 1954 – Key Provisions | 76 |
| Hindu Succession Act, 1956 – Intestate Inheritance Rules and Gender Equality Amendment | 45 |
| Child born of marriage between Muslim man and Hindu woman entitled to claim father's property: Supreme Court | 41 |
| Abolition of Triple Talaq in India: Judicial and Legislative Milestones | 30 |
| Supreme Court permits divorced Muslim women to claim maintenance under Section 125 CrPC | 25 |
| Bigamy under Indian Family Law | 25 |

## Per query

| # | Lang | Topic | Statute hit | Precedent hit | Statutes returned |
|---|---|---|---|---|---|
| P01__en | English | right to reside | no | yes | Child born of marriage between Muslim man and; Hindu Succession Act, 1956 – Intestate Inheri; Allahabad HC Declares UP Conversion Act Does  |
| P01__hi | Hindi | right to reside | no | yes | Hindu Succession Act, 1956; Child born of marriage between Muslim man and; Supreme Court permits divorced Muslim women t |
| P01__hi-en | Hinglish | right to reside | no | no | Child born of marriage between Muslim man and; Allahabad HC Declares UP Conversion Act Does ; Supreme Court permits divorced Muslim women t |
| P01__ta | Tamil | right to reside | no | yes | Hindu Succession Act, 1956; Allahabad HC Declares UP Conversion Act Does ; Supreme Court permits divorced Muslim women t |
| P01__kn | Kannada | right to reside | no | no | Hindu Succession Act, 1956; Child born of marriage between Muslim man and; Hindu Adoptions and Maintenance Act, 1956 – A |
| P02__en | English | mutual consent divorce | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Supreme Court Expands Scope of Article 142 in |
| P02__hi | Hindi | mutual consent divorce | yes | yes | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Expands Scope of Article 142 in |
| P02__hi-en | Hinglish | mutual consent divorce | yes | yes | Supreme Court Expands Scope of Article 142 in; Special Marriage Act, 1954 – Key Provisions; Bigamy under Indian Family Law |
| P02__ta | Tamil | mutual consent divorce | yes | yes | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Key Provisions of the Indian Divorce Act, 186 |
| P02__kn | Kannada | mutual consent divorce | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Abolition of Triple Talaq in India: Judicial  |
| P03__en | English | children taken by spouse | no | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Child born of marriage between Muslim man and |
| P03__hi | Hindi | children taken by spouse | no | no | Special Marriage Act, 1954 – Key Provisions; Child born of marriage between Muslim man and; Hindu Marriage Act, 1955 – Key Provisions on  |
| P03__hi-en | Hinglish | children taken by spouse | no | no | Special Marriage Act, 1954 – Key Provisions; Child born of marriage between Muslim man and; Hindu Marriage Act, 1955 – Key Provisions on  |
| P03__ta | Tamil | children taken by spouse | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on  |
| P03__kn | Kannada | children taken by spouse | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on  |
| P04__en | English | domestic violence and maintenance | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Hindu Succession Act, 1956 – Intestate Inheri |
| P04__hi | Hindi | domestic violence and maintenance | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Succession Act, 1956 – Intestate Inheri; Special Marriage Act, 1954 – Key Provisions |
| P04__hi-en | Hinglish | domestic violence and maintenance | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Hindu Succession Act, 1956 – Intestate Inheri |
| P04__ta | Tamil | domestic violence and maintenance | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Succession Act, 1956 – Intestate Inheri; Special Marriage Act, 1954 – Key Provisions |
| P04__kn | Kannada | domestic violence and maintenance | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Voidable Marriage under Indian Family Law |
| P05__en | English | jurisdiction for divorce | yes | yes | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A |
| P05__hi | Hindi | jurisdiction for divorce | yes | yes | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Child born of marriage between Muslim man and |
| P05__hi-en | Hinglish | jurisdiction for divorce | yes | no | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Holds Marriage During Pendency  |
| P05__ta | Tamil | jurisdiction for divorce | no | no | Special Marriage Act, 1954 – Key Provisions; Abolition of Triple Talaq in India: Judicial ; Child born of marriage between Muslim man and |
| P05__kn | Kannada | jurisdiction for divorce | yes | no | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Abolition of Triple Talaq in India: Judicial  |
| P06__en | English | 498A case, settlement and custody | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Hindu Marriage Act, 1955 – Key Provisions on  |
| P06__hi | Hindi | 498A case, settlement and custody | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court: Exercise of Article 142 for Di |
| P06__hi-en | Hinglish | 498A case, settlement and custody | no | no | Bigamy under Indian Family Law; Supreme Court: Exercise of Article 142 for Di; Madras High Court: Marriage is Primarily for  |
| P06__ta | Tamil | 498A case, settlement and custody | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Supreme Court: Exercise of Article 142 for Di |
| P06__kn | Kannada | 498A case, settlement and custody | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Special Marriage Act, 1954 – Key Provisions |
| P07__en | English | threat of false dowry case | yes | yes | Dowry Prohibition Act, 1961; Supreme Court Directions on Queer Rights and ; Hindu Adoptions and Maintenance Act, 1956 – A |
| P07__hi | Hindi | threat of false dowry case | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Dowry Prohibition Act, 1961 |
| P07__hi-en | Hinglish | threat of false dowry case | yes | yes | Dowry Prohibition Act, 1961; Supreme Court Directions on Queer Rights and ; Protection of Women from Domestic Violence Ac |
| P07__ta | Tamil | threat of false dowry case | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Dowry Prohibition Act, 1961 |
| P07__kn | Kannada | threat of false dowry case | yes | yes | Supreme Court Directions on Queer Rights and ; Hindu Adoptions and Maintenance Act, 1956 – A; Dowry Prohibition Act, 1961 |
| P08__en | English | maintenance for wife and child | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| P08__hi | Hindi | maintenance for wife and child | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| P08__hi-en | Hinglish | maintenance for wife and child | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court permits divorced Muslim women t |
| P08__ta | Tamil | maintenance for wife and child | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Succession Act, 1956 – Intestate Inheri |
| P08__kn | Kannada | maintenance for wife and child | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| P09__en | English | maintenance claimed by earning wife | yes | no | Key Provisions of the Indian Divorce Act, 186; Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on  |
| P09__hi | Hindi | maintenance claimed by earning wife | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Key Provisions of the Indian Divorce Act, 186; Special Marriage Act, 1954 – Key Provisions |
| P09__hi-en | Hinglish | maintenance claimed by earning wife | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Key Provisions of the Indian Divorce Act, 186 |
| P09__ta | Tamil | maintenance claimed by earning wife | no | no | Key Provisions of the Indian Divorce Act, 186; Special Marriage Act, 1954 – Key Provisions; Supreme Court permits divorced Muslim women t |
| P09__kn | Kannada | maintenance claimed by earning wife | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Key Provisions of the Indian Divorce Act, 186; Hindu Adoptions and Maintenance Act, 1956 – A |
| P10__en | English | recovery of unpaid maintenance | no | yes | Supreme Court Holds Marriage During Pendency ; Supreme Court permits divorced Muslim women t; Supreme Court Rejects Marriage Equality and A |
| P10__hi | Hindi | recovery of unpaid maintenance | no | yes | Mahr as a Mandatory Bride‑Wealth Obligation u; Supreme Court Holds Marriage During Pendency ; Supreme Court permits divorced Muslim women t |
| P10__hi-en | Hinglish | recovery of unpaid maintenance | no | yes | Mahr as a Mandatory Bride‑Wealth Obligation u; Supreme Court Holds Marriage During Pendency ; Supreme Court permits divorced Muslim women t |
| P10__ta | Tamil | recovery of unpaid maintenance | no | yes | Supreme Court Holds Marriage During Pendency ; Supreme Court permits divorced Muslim women t; Special Marriage Act, 1954 – Key Provisions |
| P10__kn | Kannada | recovery of unpaid maintenance | no | no | Supreme Court permits divorced Muslim women t; Supreme Court Holds Marriage During Pendency ; Supreme Court Rejects Marriage Equality and A |
| P11__en | English | evidence for mental cruelty | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Key Provisions of the Indian Divorce Act, 186 |
| P11__hi | Hindi | evidence for mental cruelty | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Supreme Court: Exercise of Article 142 for Di |
| P11__hi-en | Hinglish | evidence for mental cruelty | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Supreme Court: Exercise of Article 142 for Di |
| P11__ta | Tamil | evidence for mental cruelty | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Supreme Court: Exercise of Article 142 for Di |
| P11__kn | Kannada | evidence for mental cruelty | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Child born of marriage between Muslim man and; Voidable Marriage under Indian Family Law |
| P12__en | English | divorce without spouse's consent | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Bigamy under Indian Family Law |
| P12__hi | Hindi | divorce without spouse's consent | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Bigamy under Indian Family Law |
| P12__hi-en | Hinglish | divorce without spouse's consent | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Bigamy under Indian Family Law |
| P12__ta | Tamil | divorce without spouse's consent | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Bigamy under Indian Family Law |
| P12__kn | Kannada | divorce without spouse's consent | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Bigamy under Indian Family Law |
| P13__en | English | validity of foreign divorce | - | yes | Void Marriage – Legal Definition, Effects and; Voidable Marriage under Indian Family Law; Prenuptial Agreements and Their Limited Recog |
| P13__hi | Hindi | validity of foreign divorce | - | yes | Void Marriage – Legal Definition, Effects and; Voidable Marriage under Indian Family Law; Special Marriage Act, 1954 (India) |
| P13__hi-en | Hinglish | validity of foreign divorce | - | yes | Void Marriage – Legal Definition, Effects and; Voidable Marriage under Indian Family Law; Special Marriage Act, 1954 (India) |
| P13__ta | Tamil | validity of foreign divorce | - | yes | Void Marriage – Legal Definition, Effects and; Hindu Marriage Act, 1955 – Key Provisions on ; Voidable Marriage under Indian Family Law |
| P13__kn | Kannada | validity of foreign divorce | - | yes | Void Marriage – Legal Definition, Effects and; Prenuptial Agreements and Their Limited Recog; Hindu Marriage Act, 1955 – Key Provisions on  |
| P14__en | English | NRI husband abandons wife | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Restitution of Conjugal Rights – Historical D; Hindu Marriage Act, 1955 – Key Provisions on  |
| P14__hi | Hindi | NRI husband abandons wife | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Hindu Marriage Act, 1955 – Key Provisions on  |
| P14__hi-en | Hinglish | NRI husband abandons wife | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Hindu Marriage Act, 1955 – Key Provisions on  |
| P14__ta | Tamil | NRI husband abandons wife | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Abolition of Triple Talaq in India: Judicial ; Hindu Marriage Act, 1955 – Key Provisions on  |
| P14__kn | Kannada | NRI husband abandons wife | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Hindu Marriage Act, 1955 – Key Provisions on  |
| P15__en | English | custody of young child | no | no | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A |
| P15__hi | Hindi | custody of young child | no | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Hindu Adoptions and Maintenance Act, 1956 – A |
| P15__hi-en | Hinglish | custody of young child | no | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Hindu Adoptions and Maintenance Act, 1956 – A |
| P15__ta | Tamil | custody of young child | no | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 – Key Provisions |
| P15__kn | Kannada | custody of young child | no | no | Special Marriage Act, 1954 – Key Provisions; Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on  |
| P16__en | English | father's visitation | no | no | Supreme Court: Exercise of Article 142 for Di; Hindu Adoptions and Maintenance Act, 1956 – A; Ashwini Kumar Upadhyay v. Union of India – Un |
| P16__hi | Hindi | father's visitation | no | no | Supreme Court: Exercise of Article 142 for Di; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court Holds Marriage During Pendency  |
| P16__hi-en | Hinglish | father's visitation | no | no | Supreme Court: Exercise of Article 142 for Di; Muslim Personal Law (Shariat) Application Act; Supreme Court rules child of Muslim‑Hindu fas |
| P16__ta | Tamil | father's visitation | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Minority and Guardianship Act, 1956; Supreme Court permits divorced Muslim women t |
| P16__kn | Kannada | father's visitation | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Minority and Guardianship Act, 1956; Ashwini Kumar Upadhyay v. Union of India – Un |
| P17__en | English | dowry harassment complaint | no | yes | Abolition of Triple Talaq in India: Judicial ; Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on  |
| P17__hi | Hindi | dowry harassment complaint | yes | yes | Abolition of Triple Talaq in India: Judicial ; Hindu Marriage Act, 1955 – Key Provisions on ; Dowry Prohibition Act, 1961 |
| P17__hi-en | Hinglish | dowry harassment complaint | yes | yes | Abolition of Triple Talaq in India: Judicial ; Hindu Marriage Act, 1955 – Key Provisions on ; Dowry Prohibition Act, 1961 |
| P17__ta | Tamil | dowry harassment complaint | yes | yes | Dowry Prohibition Act, 1961; Supreme Court permits divorced Muslim women t; Hindu Adoptions and Maintenance Act, 1956 – A |
| P17__kn | Kannada | dowry harassment complaint | yes | yes | Protection of Women from Domestic Violence Ac; Special Marriage Act, 1954 – Key Provisions; Child born of marriage between Muslim man and |
| P18__en | English | return of dowry (Christian family) | no | yes | Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and; Hindu Minority and Guardianship Act, 1956 |
| P18__hi | Hindi | return of dowry (Christian family) | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Dowry Prohibition Act, 1961 |
| P18__hi-en | Hinglish | return of dowry (Christian family) | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Child born of marriage between Muslim man and; Hindu Minority and Guardianship Act, 1956 |
| P18__ta | Tamil | return of dowry (Christian family) | no | no | Hindu Succession Act, 1956 – Intestate Inheri; Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Minority and Guardianship Act, 1956 |
| P18__kn | Kannada | return of dowry (Christian family) | no | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Minority and Guardianship Act, 1956; Child born of marriage between Muslim man and |
| P19__en | English | husband's second marriage | yes | no | Bigamy under Indian Family Law; Supreme Court Rules Child of Muslim Man and H; Hindu Succession Act, 1956 – Intestate Inheri |
| P19__hi | Hindi | husband's second marriage | no | no | Child born of marriage between Muslim man and; Supreme Court permits divorced Muslim women t; Hindu Succession Act, 1956 – Intestate Inheri |
| P19__hi-en | Hinglish | husband's second marriage | no | no | Child born of marriage between Muslim man and; Supreme Court permits divorced Muslim women t; Hindu Adoptions and Maintenance Act, 1956 – A |
| P19__ta | Tamil | husband's second marriage | yes | no | Child born of marriage between Muslim man and; Bigamy under Indian Family Law; Hindu Adoptions and Maintenance Act, 1956 – A |
| P19__kn | Kannada | husband's second marriage | yes | no | Child born of marriage between Muslim man and; Bigamy under Indian Family Law; Hindu Adoptions and Maintenance Act, 1956 – A |
| P20__en | English | restitution decree not obeyed | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Restitution of Conjugal Rights – Historical D; Abolition of Triple Talaq in India: Judicial  |
| P20__hi | Hindi | restitution decree not obeyed | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Restitution of Conjugal Rights – Historical D; Abolition of Triple Talaq in India: Judicial  |
| P20__hi-en | Hinglish | restitution decree not obeyed | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Restitution of Conjugal Rights – Historical D; Supreme Court permits divorced Muslim women t |
| P20__ta | Tamil | restitution decree not obeyed | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court permits divorced Muslim women t; Restitution of Conjugal Rights – Historical D |
| P20__kn | Kannada | restitution decree not obeyed | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Restitution of Conjugal Rights – Historical D; Supreme Court Holds Marriage During Pendency  |
| P21__en | English | desertion in unconsummated marriage | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 – Key Provisions |
| P21__hi | Hindi | desertion in unconsummated marriage | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Uniform Civil Code – proposal for a common pe; Void Marriage – Legal Definition, Effects and |
| P21__hi-en | Hinglish | desertion in unconsummated marriage | yes | no | Voidable Marriage under Indian Family Law; Void Marriage – Legal Definition, Effects and; Abolition of Triple Talaq in India: Judicial  |
| P21__ta | Tamil | desertion in unconsummated marriage | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Uniform Civil Code – proposal for a common pe; Special Marriage Act, 1954 – Key Provisions |
| P21__kn | Kannada | desertion in unconsummated marriage | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Uniform Civil Code – proposal for a common pe; Special Marriage Act, 1954 – Key Provisions |
| P22__en | English | annulment for impotency | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Voidable Marriage under Indian Family Law; Hindu Marriage Act, 1955 – Key Provisions on  |
| P22__hi | Hindi | annulment for impotency | yes | yes | Voidable Marriage under Indian Family Law; Hindu Adoptions and Maintenance Act, 1956 – A; Void Marriage – Legal Definition, Effects and |
| P22__hi-en | Hinglish | annulment for impotency | yes | yes | Voidable Marriage under Indian Family Law; Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri |
| P22__ta | Tamil | annulment for impotency | yes | yes | Voidable Marriage under Indian Family Law; Special Marriage Act, 1954 – Key Provisions; Hindu Succession Act, 1956 – Intestate Inheri |
| P22__kn | Kannada | annulment for impotency | yes | yes | Voidable Marriage under Indian Family Law; Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Succession Act, 1956 – Intestate Inheri |
| P23__en | English | divorce and return of stridhan | yes | no | Supreme Court Rules Child of Muslim Man and H; Supreme Court allows divorced Muslim women to; Hindu Marriage Act, 1955 – Key Provisions on  |
| P23__hi | Hindi | divorce and return of stridhan | yes | no | Supreme Court permits divorced Muslim women t; Allahabad HC Declares UP Conversion Act Does ; Hindu Marriage Act, 1955 – Key Provisions on  |
| P23__hi-en | Hinglish | divorce and return of stridhan | yes | no | Allahabad HC Declares UP Conversion Act Does ; Hindu Marriage Act, 1955 – Key Provisions on ; Abolition of Triple Talaq in India: Judicial  |
| P23__ta | Tamil | divorce and return of stridhan | no | no | Supreme Court Rules Child of Muslim Man and H; Supreme Court permits divorced Muslim women t; Hindu Succession Act, 1956 – Intestate Inheri |
| P23__kn | Kannada | divorce and return of stridhan | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Allahabad HC Declares UP Conversion Act Does ; Supreme Court permits divorced Muslim women t |
| P24__en | English | instant triple talaq | yes | yes | Abolition of Triple Talaq in India: Judicial ; Supreme Court Rules Child of Muslim Man and H; Special Marriage Act, 1954 – Key Provisions |
| P24__hi | Hindi | instant triple talaq | yes | yes | Abolition of Triple Talaq in India: Judicial ; Supreme Court Rules Child of Muslim Man and H; Special Marriage Act, 1954 – Key Provisions |
| P24__hi-en | Hinglish | instant triple talaq | yes | yes | Abolition of Triple Talaq in India: Judicial ; Supreme Court Rules Child of Muslim Man and H; Muslim Personal Law (Shariat) Application Act |
| P24__ta | Tamil | instant triple talaq | yes | yes | Abolition of Triple Talaq in India: Judicial ; Supreme Court Rules Child of Muslim Man and H; Supreme Court allows divorced Muslim women to |
| P24__kn | Kannada | instant triple talaq | yes | yes | Abolition of Triple Talaq in India: Judicial ; Supreme Court Rules Child of Muslim Man and H; Supreme Court allows divorced Muslim women to |
| P25__en | English | khula (divorce sought by Muslim wife) | no | no | Bigamy under Indian Family Law; Abolition of Triple Talaq in India: Judicial ; Hindu Marriage Act, 1955 – Key Provisions on  |
| P25__hi | Hindi | khula (divorce sought by Muslim wife) | no | no | Bigamy under Indian Family Law; Child born of marriage between Muslim man and; Supreme Court permits divorced Muslim women t |
| P25__hi-en | Hinglish | khula (divorce sought by Muslim wife) | no | no | Bigamy under Indian Family Law; Abolition of Triple Talaq in India: Judicial ; Child born of marriage between Muslim man and |
| P25__ta | Tamil | khula (divorce sought by Muslim wife) | no | no | Bigamy under Indian Family Law; Hindu Marriage Act, 1955 – Key Provisions on ; Abolition of Triple Talaq in India: Judicial  |
| P25__kn | Kannada | khula (divorce sought by Muslim wife) | yes | no | Abolition of Triple Talaq in India: Judicial ; Hindu Marriage Act, 1955 – Key Provisions on ; Muslim Personal Law (Shariat) Application Act |
| P26__en | English | interfaith marriage under Special Marriage Act | yes | yes | Bigamy under Indian Family Law; Special Marriage Act, 1954 – Key Provisions; Child born of marriage between Muslim man and |
| P26__hi | Hindi | interfaith marriage under Special Marriage Act | yes | yes | Bigamy under Indian Family Law; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| P26__hi-en | Hinglish | interfaith marriage under Special Marriage Act | yes | yes | Bigamy under Indian Family Law; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| P26__ta | Tamil | interfaith marriage under Special Marriage Act | yes | yes | Bigamy under Indian Family Law; Abolition of Triple Talaq in India: Judicial ; Special Marriage Act, 1954 – Key Provisions |
| P26__kn | Kannada | interfaith marriage under Special Marriage Act | yes | no | Bigamy under Indian Family Law; Child born of marriage between Muslim man and; Special Marriage Act, 1954 – Key Provisions |
| P27__en | English | daughter's share in ancestral property | yes | yes | Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and; Ancestral Property and Coparcenary under the  |
| P27__hi | Hindi | daughter's share in ancestral property | yes | yes | Hindu Succession Act, 1956; Ancestral Property and Coparcenary under the ; Child born of marriage between Muslim man and |
| P27__hi-en | Hinglish | daughter's share in ancestral property | yes | yes | Hindu Succession Act, 1956 – Intestate Inheri; Hindu Marriage Act, 1955 – Key Provisions on ; Child born of marriage between Muslim man and |
| P27__ta | Tamil | daughter's share in ancestral property | yes | yes | Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and; Ancestral Property and Coparcenary under the  |
| P27__kn | Kannada | daughter's share in ancestral property | yes | yes | Hindu Succession Act, 1956 – Intestate Inheri; Ancestral Property and Coparcenary under the ; Hindu Marriage Act, 1955 – Key Provisions on  |
| P28__en | English | senior citizen evicting son and daughter-in-law | - | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Hindu Marriage Act, 1955 – Key Provisions on  |
| P28__hi | Hindi | senior citizen evicting son and daughter-in-law | - | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956; Hindu Marriage Act, 1955 – Key Provisions on  |
| P28__hi-en | Hinglish | senior citizen evicting son and daughter-in-law | - | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Succession Act, 1956 |
| P28__ta | Tamil | senior citizen evicting son and daughter-in-law | - | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956; Hindu Marriage Act, 1955 – Key Provisions on  |
| P28__kn | Kannada | senior citizen evicting son and daughter-in-law | - | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956; Hindu Marriage Act, 1955 – Key Provisions on  |
| P29__en | English | husband's adultery | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court allows divorced Muslim women to; Hindu Succession Act, 1956 – Intestate Inheri |
| P29__hi | Hindi | husband's adultery | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Supreme Court allows divorced Muslim women to |
| P29__hi-en | Hinglish | husband's adultery | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Supreme Court allows divorced Muslim women to |
| P29__ta | Tamil | husband's adultery | no | no | Allahabad HC Declares UP Conversion Act Does ; Hindu Succession Act, 1956 – Intestate Inheri; Supreme Court allows divorced Muslim women to |
| P29__kn | Kannada | husband's adultery | no | yes | Supreme Court allows divorced Muslim women to; Allahabad HC Declares UP Conversion Act Does ; Hindu Succession Act, 1956 – Intestate Inheri |
| P30__en | English | adoption of a stepchild | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and |
| P30__hi | Hindi | adoption of a stepchild | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and |
| P30__hi-en | Hinglish | adoption of a stepchild | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and |
| P30__ta | Tamil | adoption of a stepchild | yes | yes | Child born of marriage between Muslim man and; Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri |
| P30__kn | Kannada | adoption of a stepchild | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Child born of marriage between Muslim man and |
| L-en-01__en | English | one-time alimony in mutual consent divorce | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Key Provisions of the Indian Divorce Act, 186 |
| L-en-02__en | English | 498A FIR against husband living abroad | - | yes | Abolition of Triple Talaq in India: Judicial ; Hindu Succession Act, 1956 – Intestate Inheri; Supreme Court Directions on Queer Rights and  |
| L-en-03__en | English | consent withdrawn before second motion | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Key Provisions of the Indian Divorce Act, 186; Bigamy under Indian Family Law |
| L-en-04__en | English | reducing maintenance after remarriage | yes | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Abolition of Triple Talaq in India: Judicial ; Special Marriage Act, 1954 – Key Provisions |
| L-en-05__en | English | stepfather's name in child's records | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court permits divorced Muslim women t; Hindu Marriage Act, 1955 – Key Provisions on  |
| L-en-06__en | English | will and later unregistered revocation | - | no | Hindu Succession Act, 1956 – Intestate Inheri; Abolition of Triple Talaq in India: Judicial ; Hindu Adoptions and Maintenance Act, 1956 – A |
| L-en-07__en | English | opposing wife's guardianship petition | no | no | Supreme Court: Exercise of Article 142 for Di; Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A |
| L-en-08__en | English | in-laws allege concealment of past illness | no | no | Prohibition of Child Marriage Act, 2006; Bigamy under Indian Family Law; Special Marriage Act, 1954 – Key Provisions |
| L-en-09__en | English | precautions before wife files cases | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Supreme Court Rules Child of Muslim Man and H |
| L-en-10__en | English | husband concealed sexual orientation | yes | no | Voidable Marriage under Indian Family Law; Special Marriage Act, 1954 – Key Provisions; Allahabad HC Declares UP Conversion Act Does  |
| L-hi-01__hi | Hindi | domestic violence by alcoholic husband | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 – Key Provisions |
| L-hi-02__hi | Hindi | dowry demand (father asking for daughter) | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Child born of marriage between Muslim man and; Hindu Succession Act, 1956 – Intestate Inheri |
| L-hi-03__hi | Hindi | bringing wife back (restitution) | no | no | Supreme Court Expands Scope of Article 142 in; Supreme Court permits divorced Muslim women t; Special Marriage Act, 1954 – Key Provisions |
| L-hi-04__hi | Hindi | sisters' share in ancestral farmland | yes | yes | Hindu Succession Act, 1956; Child born of marriage between Muslim man and; Ancestral Property and Coparcenary under the  |
| L-hi-05__hi | Hindi | Muslim husband's second nikah and maintenance | yes | yes | Bigamy under Indian Family Law; Supreme Court permits divorced Muslim women t; Child born of marriage between Muslim man and |
| L-hi-06__hi | Hindi | widow's rights in husband's property | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Child born of marriage between Muslim man and; Hindu Succession Act, 1956 |
| L-hi-07__hi | Hindi | protection after inter-caste court marriage | yes | yes | Special Marriage Act, 1954 – Key Provisions; Allahabad HC Declares UP Conversion Act Does ; Prohibition of Child Marriage Act, 2006 |
| L-hi-08__hi | Hindi | child's expenses after divorce | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court Holds Marriage During Pendency  |
| L-hi-09__hi | Hindi | wife's adultery, divorce and custody | no | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 – Key Provisions; Child born of marriage between Muslim man and |
| L-hi-10__hi | Hindi | husband abroad, no contact or money | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions; Abolition of Triple Talaq in India: Judicial  |
| L-hien-01__hi-en | Hinglish | anticipatory bail in 498A case | - | no | Abolition of Triple Talaq in India: Judicial ; Special Marriage Act, 1954 – Key Provisions; Allahabad HC Declares UP Conversion Act Does  |
| L-hien-02__hi-en | Hinglish | annulment for husband's impotency | yes | yes | Supreme Court Holds Marriage During Pendency ; Voidable Marriage under Indian Family Law; Supreme Court allows divorced Muslim women to |
| L-hien-03__hi-en | Hinglish | maintenance from husband working abroad | yes | no | Child born of marriage between Muslim man and; Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on  |
| L-hien-04__hi-en | Hinglish | visitation order not obeyed | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court rules child of Muslim‑Hindu fas |
| L-hien-05__hi-en | Hinglish | married daughter's right in parents' self-acquired property | yes | no | Hindu Succession Act, 1956 – Intestate Inheri; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court rules child of Muslim‑Hindu fas |
| L-hien-06__hi-en | Hinglish | threat of rape case after live-in relationship | - | no | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Prohibition of Child Marriage Act, 2006 |
| L-hien-07__hi-en | Hinglish | waiver of cooling-off period | yes | yes | Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on ; Abolition of Triple Talaq in India: Judicial  |
| L-hien-08__hi-en | Hinglish | property rights of second wife and her children | yes | yes | Hindu Succession Act, 1956; Child born of marriage between Muslim man and; Hindu Adoptions and Maintenance Act, 1956 – A |
| L-hien-09__hi-en | Hinglish | wife demands separate residence | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Succession Act, 1956 – Intestate Inheri; Hindu Marriage Act, 1955 – Key Provisions on  |
| L-hien-10__hi-en | Hinglish | wife's earlier undissolved marriage | yes | no | Bigamy under Indian Family Law; Special Marriage Act, 1954 – Key Provisions; Voidable Marriage under Indian Family Law |
| L-ta-01__ta | Tamil | protection from violent alcoholic husband | no | no | Supreme Court allows divorced Muslim women to; Hindu Adoptions and Maintenance Act, 1956 – A; Child born of marriage between Muslim man and |
| L-ta-02__ta | Tamil | father denied access to child | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 – Key Provisions; Hindu Succession Act, 1956 – Intestate Inheri |
| L-ta-03__ta | Tamil | dowry demand and jewellery held by in-laws | no | yes | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Key Provisions of the Indian Divorce Act, 186 |
| L-ta-04__ta | Tamil | divorce law for Christians | no | no | Hindu Marriage Act, 1955 – Key Provisions on ; Uniform Civil Code – proposal for a common pe; Hindu Succession Act, 1956 – Intestate Inheri |
| L-ta-05__ta | Tamil | customary marriage with sister's daughter | yes | yes | Prenuptial Agreements and Their Limited Recog; Hindu Marriage Act, 1955 – Key Provisions on ; Bigamy under Indian Family Law |
| L-ta-06__ta | Tamil | husband abroad living with another woman | yes | no | Supreme Court allows divorced Muslim women to; Child born of marriage between Muslim man and; Hindu Adoptions and Maintenance Act, 1956 – A |
| L-ta-07__ta | Tamil | harassment by mother-in-law, separate residence | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Supreme Court permits divorced Muslim women t |
| L-ta-08__ta | Tamil | bringing wife back (voice input) | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Bigamy under Indian Family Law; Hindu Marriage Act, 1955 – Key Provisions on  |
| L-ta-09__ta | Tamil | remarrying while divorce is pending | no | no | Abolition of Triple Talaq in India: Judicial ; Mukul Rohatgi urges Supreme Court to declare ; Justice Sanjiv Khanna Recuses from Supreme Co |
| L-ta-10__ta | Tamil | proving an unregistered temple marriage | no | yes | Abolition of Triple Talaq in India: Judicial ; Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 – Key Provisions |
| L-kn-01__kn | Kannada | how much maintenance a court fixes | no | yes | Key Provisions of the Indian Divorce Act, 186; Special Marriage Act, 1954 – Key Provisions; Hindu Adoptions and Maintenance Act, 1956 – A |
| L-kn-02__kn | Kannada | replying to a divorce legal notice | yes | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Succession Act, 1956 – Intestate Inheri; Special Marriage Act, 1954 – Key Provisions |
| L-kn-03__kn | Kannada | dowry harassment by mother-in-law and sister-in-law | no | no | Supreme Court rules child of Muslim‑Hindu fas; Special Marriage Act, 1954 – Key Provisions; Hindu Marriage Act, 1955 – Key Provisions on  |
| L-kn-04__kn | Kannada | custody when the father earns more | no | no | Hindu Marriage Act, 1955 – Key Provisions on ; Hindu Adoptions and Maintenance Act, 1956 – A; Special Marriage Act, 1954 – Key Provisions |
| L-kn-05__kn | Kannada | rights of a second wife | no | no | Hindu Adoptions and Maintenance Act, 1956 – A; Child born of marriage between Muslim man and; Hindu Marriage Act, 1955 – Key Provisions on  |
| L-kn-06__kn | Kannada | late registration of marriage | yes | yes | Hindu Marriage Act, 1955 – Provisions, Applic; Void Marriage – Legal Definition, Effects and; Madras High Court Clarifies Date of Filing fo |
| L-kn-07__kn | Kannada | husband's affair (voice input) | yes | no | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
| L-kn-08__kn | Kannada | mehr and maintenance after talaq | yes | no | Abolition of Triple Talaq in India: Judicial ; Supreme Court allows divorced Muslim women to; Muslim Personal Law (Shariat) Application Act |
| L-kn-09__kn | Kannada | husband hiding income in maintenance case | no | no | Supreme Court permits divorced Muslim women t; Hindu Adoptions and Maintenance Act, 1956 – A; Supreme Court: Exercise of Article 142 for Di |
| L-kn-10__kn | Kannada | adopting a relative's child | yes | yes | Hindu Adoptions and Maintenance Act, 1956 – A; Hindu Marriage Act, 1955 – Key Provisions on ; Special Marriage Act, 1954 – Key Provisions |
