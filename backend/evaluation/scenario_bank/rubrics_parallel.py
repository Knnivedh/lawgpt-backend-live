"""
Answer rubrics for the 30 parallel legal scenarios (generator dataset).

For each scenario:
  extra     facts gathered in follow-ups, added to what the question itself says
  cover     legal points a good answer should make
  statutes  provisions it should rest on. Criminal provisions are given under
            the new codes (BNS / BNSS, in force from 1 July 2024) with the old
            IPC / CrPC number in brackets; either numbering is acceptable
  avoid     wrong claims an answer must not make

Written by an AI assistant from general knowledge of Indian family law. They
have NOT been checked by a lawyer; treat them as a draft until one reviews them.
"""

RUBRICS = {
    "P01": dict(
        extra="religion: Hindu | house_owner: father-in-law | current_residence: parents' home",
        cover=[
            "A wife has a right to reside in the shared household under s.17 of the Protection of Women from Domestic Violence Act, 2005, whoever owns it",
            "A house owned by the in-laws can be a shared household if she lived there in a domestic relationship (Satish Chander Ahuja v. Sneha Ahuja, 2020)",
            "She can apply to the Magistrate under s.12 for a residence order under s.19, with the help of a Protection Officer",
            "Interim orders are possible (s.23); she may also seek protection and monetary relief",
        ],
        statutes="PWDVA 2005 s.12, s.17, s.19, s.23",
        avoid=["She has no right because the house belongs to her in-laws",
               "The right of residence gives her ownership or a share in the house"],
    ),
    "P02": dict(
        extra="religion: Hindu | separation_duration: 14 months | children: none | spouse_agrees: yes",
        cover=[
            "Mutual consent divorce is under s.13B of the Hindu Marriage Act: a joint petition stating they have lived separately for a year or more and cannot live together",
            "Two motions: the second is made six to eighteen months after the first",
            "The six-month wait can be waived by the court in fit cases (Amardeep Singh v. Harveen Kaur, 2017)",
            "Terms such as alimony and return of belongings should be settled; either spouse can withdraw consent before the decree",
        ],
        statutes="HMA 1955 s.13B, s.19",
        avoid=["A mutual consent divorce needs no period of separation",
               "The Special Marriage Act applies to them by default"],
    ),
    "P03": dict(
        extra="children_ages: 7 and 10 | existing_court_orders: none | divorce_status: not divorced | religion: Hindu",
        cover=[
            "Both parents are natural guardians; with no court order, a parent taking the children is not ordinarily kidnapping",
            "He can file for custody or visitation under the Guardians and Wards Act, 1890 with an application for interim access; the children's welfare is the paramount consideration",
            "If their whereabouts stay unknown he can make a police report and, if needed, file a habeas corpus petition in the High Court to have them traced and produced",
            "Mediation should be tried; he should not use force",
        ],
        statutes="GWA 1890 s.7, s.12, s.25; HMGA 1956 s.6, s.13",
        avoid=["The mother has committed kidnapping and will be arrested",
               "The father automatically gets custody as natural guardian"],
    ),
    "P04": dict(
        extra="current_residence: parents' house in Pune since last month | children: none | own_income: none",
        cover=[
            "Application under s.12 PWDVA for a protection order (s.18), residence order (s.19), monetary relief (s.20) and compensation (s.22); it can be filed where she now lives (s.27)",
            "Maintenance under s.144 BNSS (s.125 CrPC); interim maintenance under s.24 HMA if a matrimonial case is filed",
            "A criminal complaint for cruelty under s.85 BNS (s.498A IPC)",
            "Divorce for cruelty under s.13(1)(ia) HMA or judicial separation are options, not preconditions; she should keep medical records and other evidence",
        ],
        statutes="PWDVA s.12, s.18, s.19, s.20, s.22; BNSS s.144 (CrPC s.125); BNS s.85 (IPC s.498A); HMA s.13(1)(ia), s.24",
        avoid=["She must file for divorce before she can claim maintenance",
               "She can file only where the husband lives"],
    ),
    "P05": dict(
        extra="religion: Hindu | client_current_city: Bengaluru",
        cover=[
            "Jurisdiction is governed by s.19 HMA: where the marriage was solemnised (Mumbai), where the respondent resides (Delhi), or where the couple last resided together (Bengaluru)",
            "As the petitioner husband he can file in the Family Court at Bengaluru, where they last lived together",
            "The option of filing where the wife resides (s.19(iii-a)) is for a wife who is the petitioner",
            "The wife may ask for the case to be transferred to her city (s.25 CPC, Supreme Court for inter-State transfer); courts often favour the wife's convenience",
        ],
        statutes="HMA s.19; Family Courts Act 1984; CPC s.25",
        avoid=["The petition can be filed only in the city where the marriage took place",
               "A husband can file wherever he happens to live, on that ground alone"],
    ),
    "P06": dict(
        extra="religion: Hindu | marriage_duration: 6 years | child_lives_with: wife | terms_of_compromise: not known yet",
        cover=[
            "Cruelty under s.85 BNS (s.498A IPC) is non-compoundable: the wife cannot simply withdraw it",
            "On a genuine settlement the parties ask the High Court to quash the case under s.528 BNSS (s.482 CrPC) (B.S. Joshi v. State of Haryana; Gian Singh v. State of Punjab)",
            "The settlement, usually with a mutual consent divorce, should record alimony, custody and visitation in a court order so it can be enforced",
            "Custody of a child under five is ordinarily with the mother, but the father remains a guardian and can secure visitation or shared parenting; welfare of the child decides",
        ],
        statutes="BNS s.85 (IPC s.498A); BNSS s.528 (CrPC s.482); HMGA s.6(a), s.13; HMA s.13B, s.26",
        avoid=["The wife can withdraw the 498A case on her own at the police station or trial court",
               "The father loses all rights over the child"],
    ),
    "P07": dict(
        extra="marriage_duration: 3 years | living_together: no, wife at her parents' home for 3 months | evidence_of_threats: some WhatsApp messages",
        cover=[
            "Preserve evidence of the threats and the demand (messages, call recordings) and give a written complaint to the police or Superintendent of Police",
            "Demanding property under threat of a false case can amount to extortion or criminal intimidation (BNS s.308, s.351; IPC s.383, s.503)",
            "If an FIR is feared he and his parents can seek anticipatory bail under s.482 BNSS (s.438 CrPC); arrest is not automatic (Arnesh Kumar v. State of Bihar, 2014)",
            "He should not transfer the flat under pressure",
        ],
        statutes="BNSS s.482 (CrPC s.438), s.35(3) (CrPC s.41A); BNS s.85 (IPC s.498A), s.308, s.351; Dowry Prohibition Act 1961",
        avoid=["A complaint filed first guarantees that no FIR can be registered against him",
               "The police can never arrest in a 498A case"],
    ),
    "P08": dict(
        extra="religion: Hindu | husband_income: bank employee, about Rs 80,000/month",
        cover=[
            "A wife unable to maintain herself and a minor child can claim maintenance under s.144 BNSS (s.125 CrPC), whatever their religion",
            "She can file where she now resides; living with her parents is no bar",
            "Interim maintenance can be granted; both sides file affidavits of assets and income, and maintenance runs from the date of application (Rajnesh v. Neha, 2020)",
            "Other routes: s.20 PWDVA, ss.18 and 20 of the Hindu Adoptions and Maintenance Act, s.24 HMA; the amount depends on his income and their needs",
        ],
        statutes="BNSS s.144 (CrPC s.125); PWDVA s.20; HAMA s.18, s.20; HMA s.24",
        avoid=["The law guarantees a fixed percentage of his salary",
               "She cannot claim because she lives with her parents",
               "She must get a divorce first"],
    ),
    "P09": dict(
        extra="client_income: about Rs 45,000/month | children: none | religion: Hindu | law_under_which_she_filed: s.125 CrPC",
        cover=[
            "Under s.144 BNSS (s.125 CrPC) maintenance is for a wife unable to maintain herself; a wife with sufficient income is generally not entitled",
            "Earning is not an absolute bar: the court compares both incomes and the standard of living",
            "Both must file affidavits disclosing assets and liabilities (Rajnesh v. Neha, 2020); he should produce or ask the court to call for proof of her income",
            "Under s.24 HMA either spouse without sufficient independent income may claim",
        ],
        statutes="BNSS s.144 (CrPC s.125); HMA s.24, s.25",
        avoid=["A working wife can never get maintenance",
               "The court will certainly dismiss her claim"],
    ),
    "P10": dict(
        extra="law_under_which_order_was_passed: s.125 CrPC | arrears: Rs 1,20,000 | husband_employment: salaried, private company",
        cover=[
            "She can file a recovery (execution) application before the same court under s.144(3) BNSS (s.125(3) CrPC)",
            "The court can issue a warrant to recover the amount, including by attaching his salary or property, and can sentence him to imprisonment of up to one month for each month's default",
            "The application must be made within one year of the amount falling due, so she should act now",
            "Imprisonment does not wipe out the arrears; they remain payable",
        ],
        statutes="BNSS s.144(3), s.147 (CrPC s.125(3), s.128)",
        avoid=["Going to jail cancels the arrears",
               "She must file a fresh maintenance case"],
    ),
    "P11": dict(
        extra="religion: Hindu | marriage_duration: 5 years | nature_of_cruelty: insults before relatives, two suicide threats, no communication for months | case_filed: none",
        cover=[
            "Mental cruelty is a ground for divorce under s.13(1)(ia) HMA and is proved on a preponderance of probabilities, not beyond reasonable doubt",
            "Audio or video is not required; his own testimony and that of family members is admissible, though the court weighs interested witnesses with care",
            "Supporting material helps: messages, medical records, earlier complaints, neighbours",
            "Specific incidents with dates should be pleaded; repeated suicide threats have been treated as cruelty (Samar Ghosh v. Jaya Ghosh, 2007; Narendra v. K. Meena, 2016)",
        ],
        statutes="HMA s.13(1)(ia); Family Courts Act 1984 s.14",
        avoid=["Without audio or video proof the case cannot succeed",
               "Statements of family members are not admissible"],
    ),
    "P12": dict(
        extra="religion: Hindu | who_left: wife left on her own in 2022 after a fight with the client's mother | marriage_year: 2019 | children: none",
        cover=[
            "Mutual consent divorce is not possible without her, but he can file a contested petition under s.13(1) HMA",
            "Desertion (s.13(1)(ib)): a continuous period of at least two years, without reasonable cause or consent and with intent to end cohabitation, which he must prove",
            "Cruelty (s.13(1)(ia)) may also be pleaded if the facts support it",
            "Irretrievable breakdown is not a ground under the HMA; only the Supreme Court can grant divorce on that basis under Article 142 (Shilpa Sailesh v. Varun Sreenivasan, 2023)",
        ],
        statutes="HMA s.13(1)(ia), s.13(1)(ib); Constitution Art.142",
        avoid=["Four years of separation automatically entitles him to a divorce",
               "A family court can grant divorce for irretrievable breakdown"],
    ),
    "P13": dict(
        extra="religion: Hindu rites | both_took_part_in_foreign_case: yes | year_of_foreign_decree: 2021",
        cover=[
            "A foreign judgment is conclusive under s.13 CPC unless it falls within the listed exceptions",
            "Y. Narasimha Rao v. Y. Venkata Lakshmi (1991): a foreign divorce is recognised where the ground is available under the law the parties married under, or where both voluntarily submitted to the foreign court and consented",
            "Mutual consent is a ground under s.13B HMA and both took part, so the decree is generally recognised and she can remarry",
            "She should keep a certified (apostilled) copy; if anyone disputes it she can seek a declaration from an Indian family court",
        ],
        statutes="CPC s.13, s.14; HMA s.13B, s.15",
        avoid=["A foreign divorce decree is never valid in India",
               "She must always get divorced again in India"],
    ),
    "P14": dict(
        extra="religion: Hindu | daughter's_current_residence: parents' home | relief_sought: undecided",
        cover=[
            "She can act in India although he is abroad: an application under the PWDVA and maintenance under s.144 BNSS (s.125 CrPC) can be filed where she lives, and can proceed ex parte once he is served",
            "If there was cruelty or a dowry demand, a complaint under s.85 BNS (s.498A IPC) and the Dowry Prohibition Act; her stridhan can be recovered",
            "Matrimonial remedies under the HMA: restitution (s.9) or divorce for cruelty or desertion (desertion needs two years; a divorce petition is normally barred in the first year, s.14)",
            "NRI-specific steps: complaints to the Ministry of External Affairs / Indian mission and the NCW NRI cell; his passport can be impounded under s.10(3) Passports Act if he evades court process",
        ],
        statutes="PWDVA s.12, s.27; BNSS s.144 (CrPC s.125); BNS s.85 (IPC s.498A); HMA s.9, s.13, s.14; Passports Act 1967 s.10(3)",
        avoid=["Nothing can be done while he is abroad",
               "The marriage is automatically void because he abandoned her"],
    ),
    "P15": dict(
        extra="religion: Hindu | existing_court_orders: none | divorce_status: not divorced",
        cover=[
            "Under s.6(a) of the Hindu Minority and Guardianship Act the custody of a child under five is ordinarily with the mother",
            "The child's welfare is the paramount consideration (s.13); both parents remain guardians",
            "She can file for custody under the Guardians and Wards Act (or s.26 HMA) and ask for an interim order restraining him from removing the child; s.21 PWDVA is another route",
            "If he takes the child by force she can go to the police and file a habeas corpus petition",
        ],
        statutes="HMGA s.6(a), s.13; GWA s.7, s.12, s.25; PWDVA s.21",
        avoid=["The father, as natural guardian, may lawfully take the child whenever he likes",
               "The father has no right even to visitation"],
    ),
    "P16": dict(
        extra="religion: Hindu | divorce_status: not divorced | interim_application: filed in March, not yet heard",
        cover=[
            "Yes: the court can grant interim visitation while the guardianship petition is pending (s.12 GWA)",
            "A pending domestic violence case does not by itself bar access; s.21 PWDVA itself provides for visitation to the father unless it would harm the child",
            "He should press for an early hearing of the interim application and, if it is still delayed, ask the High Court (Art.227) to direct time-bound disposal",
            "He can propose supervised visits or video calls; a child is entitled to the company of both parents (Yashita Sahu v. State of Rajasthan, 2020)",
        ],
        statutes="GWA s.12, s.25; PWDVA s.21; HMGA s.13",
        avoid=["A father has no right to meet the child until the domestic violence case ends",
               "He may take the child without a court order"],
    ),
    "P17": dict(
        extra="religion: Hindu | current_residence: in-laws' house with husband | children: none | evidence: some messages",
        cover=[
            "She can lodge an FIR at the police station or women's cell for cruelty under s.85 BNS (s.498A IPC) and for dowry demand under ss.3-4 Dowry Prohibition Act",
            "Not having complained earlier is no bar; the delay can be explained",
            "A civil application under s.12 PWDVA can give protection, residence and monetary orders, alongside or instead of the criminal case",
            "She should keep medical records, messages and witnesses, and put her safety first: helplines 181 / 112; she may file where she takes shelter",
        ],
        statutes="BNS s.85, s.86 (IPC s.498A); Dowry Prohibition Act 1961 s.3, s.4; PWDVA s.12, s.18, s.19, s.20",
        avoid=["She cannot complain now because she never complained before",
               "She must file for divorce first"],
    ),
    "P18": dict(
        extra="what_was_given: Rs 5 lakh cash and about 200 g gold, bank receipt for the cash | case_status: none filed | marriage_year: 2022",
        cover=[
            "Under s.6 Dowry Prohibition Act, dowry received by anyone else is held in trust for the woman and must be transferred to her; this applies to all religions",
            "Her jewellery and gifts are her own property; refusal to return them is criminal breach of trust (s.316 BNS / s.406 IPC)",
            "The claim is the sister's: she should be the complainant or applicant; a Magistrate can order return of her valuables under the PWDVA (s.19(8))",
            "As a Christian her matrimonial remedies are under the Divorce Act, 1869; a legal notice listing the articles, with proof, is a sensible first step",
        ],
        statutes="Dowry Prohibition Act s.6; BNS s.316 (IPC s.406); PWDVA s.12, s.19(8); Divorce Act 1869",
        avoid=["The law on return of dowry applies only to Hindus",
               "Her case is governed by the Hindu Marriage Act"],
    ),
    "P19": dict(
        extra="evidence: wedding photographs, priest willing to give a statement | children: one daughter aged 4",
        cover=[
            "A second marriage while the first subsists is void (ss.5(i), 11 HMA) and is bigamy, punishable under s.17 HMA read with s.82 BNS (s.494 IPC), up to seven years",
            "The complaint must be made by the aggrieved wife, normally as a complaint to the Magistrate (s.219 BNSS / s.198 CrPC)",
            "She must prove that the second marriage was performed with the essential ceremonies",
            "She remains his legal wife: she may claim maintenance, seek divorce for adultery or cruelty, or ask a court to declare the second marriage void",
        ],
        statutes="HMA s.5(i), s.11, s.17; BNS s.82 (IPC s.494); BNSS s.219 (CrPC s.198), s.144",
        avoid=["The second marriage is valid because it took place in a temple",
               "Her own marriage has ended automatically"],
    ),
    "P20": dict(
        extra="religion: Hindu | date_of_decree: about 14 months ago | wants_divorce: no, wants her back | children: none",
        cover=[
            "A decree for restitution of conjugal rights (s.9 HMA) cannot be enforced by physically bringing the wife back",
            "It is executed only by attachment of property (Order 21 Rule 32 CPC)",
            "If there is no restitution for a year or more after the decree, either spouse may seek divorce under s.13(1A)(ii)",
            "As the decree was ex parte she may apply to set it aside; mediation or counselling is the practical way to get her back",
        ],
        statutes="HMA s.9, s.13(1A)(ii); CPC Order 21 Rule 32",
        avoid=["The police can bring the wife back by force",
               "The decree itself dissolves the marriage"],
    ),
    "P21": dict(
        extra="religion: Sikh | any_cases_filed: none | reason_the_wife_gives: none",
        cover=[
            "Sikhs are governed by the Hindu Marriage Act (s.2)",
            "Divorce for desertion (s.13(1)(ib)): more than two continuous years have passed; refusal to consummate can also be pleaded as cruelty (s.13(1)(ia))",
            "Nullity under s.12(1)(a) is available only if non-consummation is due to the wife's impotence; wilful refusal alone is not a ground for annulment under the HMA",
            "If she agrees, mutual consent divorce (s.13B) is the quickest; restitution (s.9) is the option if he wants her back",
        ],
        statutes="HMA s.2, s.9, s.12(1)(a), s.13(1)(ia), s.13(1)(ib), s.13B",
        avoid=["The marriage is automatically void because it was not consummated",
               "Sikhs have a separate divorce law"],
    ),
    "P22": dict(
        extra="religion: Hindu | daughter's_own_wishes: wants to end the marriage | medical_evidence: none yet",
        cover=[
            "The marriage is voidable under s.12(1)(a) HMA where it has not been consummated owing to the husband's impotence; the court can grant a decree of nullity",
            "Concealment may also be fraud under s.12(1)(c): that petition must be filed within one year of discovery and she must not live with him as wife after discovering it",
            "The daughter herself must file; the one-year bar in s.14 applies to divorce, not to nullity",
            "The court can direct a medical examination; her gifts and jewellery can be recovered (s.27 HMA; s.6 Dowry Prohibition Act)",
        ],
        statutes="HMA s.12(1)(a), s.12(1)(c), s.12(2), s.27",
        avoid=["She must wait one year before filing",
               "The parents can file the petition in their own names",
               "The marriage is void automatically without a court decree"],
    ),
    "P23": dict(
        extra="religion: Hindu | marriage_year: 2023 | children: none | items: about 150 g gold jewellery and clothes, purchase bills available | current_residence: parents' home for two months",
        cover=[
            "Divorce under the HMA for cruelty (s.13(1)(ia)); adultery (s.13(1)(i)) needs proof of sexual intercourse, otherwise the affair supports cruelty",
            "She can file in the Family Court where she now resides (s.19(iii-a))",
            "Her jewellery and belongings are stridhan, her absolute property (Pratibha Rani v. Suraj Kumar, 1985): demand them in writing with a list",
            "If refused: a complaint of criminal breach of trust (s.316 BNS / s.406 IPC), an order under s.19(8) PWDVA, or s.27 HMA in the divorce case; interim maintenance under s.24",
        ],
        statutes="HMA s.13(1)(i), s.13(1)(ia), s.19, s.24, s.27; BNS s.316 (IPC s.406); PWDVA s.19(8)",
        avoid=["She can prosecute him for adultery",
               "The jewellery belongs jointly to the husband's family"],
    ),
    "P24": dict(
        extra="children_ages: daughter 3, son 6 | own_income: none | mehr_status: unpaid",
        cover=[
            "Instant triple talaq is void and illegal, including by electronic message (Shayara Bano v. Union of India, 2017; s.3 Muslim Women (Protection of Rights on Marriage) Act, 2019); the marriage continues",
            "Pronouncing it is an offence punishable with up to three years (s.4), on a complaint by her or her relatives",
            "She can claim a subsistence allowance for herself and the children (s.5) and custody of the minor children (s.6)",
            "She can also claim maintenance under s.144 BNSS (s.125 CrPC) (Mohd. Abdul Samad v. State of Telangana, 2024) and cannot be thrown out: right of residence under the PWDVA",
        ],
        statutes="Muslim Women (Protection of Rights on Marriage) Act 2019 s.3, s.4, s.5, s.6, s.7; BNSS s.144 (CrPC s.125); PWDVA s.17, s.19",
        avoid=["The divorce is valid and she must leave the house",
               "A Muslim woman cannot claim maintenance under s.125 CrPC"],
    ),
    "P25": dict(
        extra="mehr_status: Rs 50,000, unpaid | children: none | living_together: yes",
        cover=[
            "Khula is divorce at the wife's instance, traditionally with the husband's agreement and often on returning the mehr",
            "If he refuses she can get a judicial divorce without his consent under s.2 Dissolution of Muslim Marriages Act, 1939 (cruelty, failure to maintain for two years, and other grounds) through the Family Court",
            "The Kerala High Court (2021) recognised a wife's right to khula without the husband's consent, but High Courts are not uniform and the question is before the Supreme Court, so the court route is the safe one",
            "Her claims to mehr and maintenance remain",
        ],
        statutes="Dissolution of Muslim Marriages Act 1939 s.2; Muslim Personal Law (Shariat) Application Act 1937 s.2; Family Courts Act 1984 s.7",
        avoid=["A Muslim woman cannot get a divorce without her husband's consent",
               "The grounds in the Hindu Marriage Act apply to her"],
    ),
    "P26": dict(
        extra="partner_age: 31 | either_married_before: no",
        cover=[
            "Yes: the Special Marriage Act, 1954 lets two people of different religions marry without conversion, if the s.4 conditions are met (ages 21 / 18, no living spouse)",
            "Procedure: notice to the Marriage Officer of a district where one of them has lived for 30 days (s.5), objections within 30 days (s.7), then solemnisation before three witnesses and a certificate (ss.11-13)",
            "The 30-day period is statutory and the officer cannot waive it; the Allahabad High Court (Safiya Sultana, 2021) made publication of the notice optional, which applies in Uttar Pradesh",
            "She is an adult: her parents cannot force a marriage, and the couple can ask the police or High Court for protection",
        ],
        statutes="Special Marriage Act 1954 s.4, s.5, s.6, s.7, s.11, s.13; Constitution Art.21",
        avoid=["The 30-day notice can be waived on payment of a fee",
               "One of them must convert",
               "Her parents' consent is required"],
    ),
    "P27": dict(
        extra="mother: deceased | siblings: two brothers | partition: not known whether registered",
        cover=[
            "A daughter is a coparcener by birth with the same rights as a son under s.6 Hindu Succession Act as amended in 2005, whether married or not",
            "Vineeta Sharma v. Rakesh Sharma (2020): this holds whether or not the father was alive on 9 September 2005; only a registered partition or court decree before 20 December 2004 is saved",
            "Her father's own share also passes equally to his Class I heirs, as he died without a will (s.8)",
            "Remedy: legal notice, then a suit for partition and separate possession; entries in the revenue records do not decide title",
        ],
        statutes="Hindu Succession Act 1956 s.6, s.8, Schedule (Class I)",
        avoid=["Married daughters have no share in ancestral property",
               "Her right depends on her father having been alive on 9 September 2005"],
    ),
    "P28": dict(
        extra="house: self-acquired, built in 2018 | state: not given | pending_cases_by_daughter_in_law: none",
        cover=[
            "He can apply to the Maintenance Tribunal under the Maintenance and Welfare of Parents and Senior Citizens Act, 2007; under many State rules and High Court rulings the Tribunal or District Magistrate can order eviction of abusive children from a senior citizen's own property",
            "A son has no legal right to stay in his parents' self-acquired house; a civil suit for eviction is the alternative",
            "The daughter-in-law may claim a right of residence in a shared household under the PWDVA; the 2007 Act does not automatically override it and the two are balanced (S. Vanitha v. Deputy Commissioner, 2020)",
            "Abuse and threats can be reported to the police",
        ],
        statutes="Maintenance and Welfare of Parents and Senior Citizens Act 2007 s.4, s.5, s.22, s.23; PWDVA s.17, s.19",
        avoid=["The son has a birthright in his father's self-acquired house",
               "A daughter-in-law can never be evicted"],
    ),
    "P29": dict(
        extra="religion: Hindu | living_together: same house, separate rooms for about four months | child_age: not given",
        cover=[
            "Adultery is a ground for divorce under s.13(1)(i) HMA (voluntary sexual intercourse with another person); it may be proved by circumstances, and the conduct also supports mental cruelty (s.13(1)(ia))",
            "There is no criminal case for adultery: s.497 IPC was struck down in Joseph Shine v. Union of India (2018) and the BNS has no such offence, so neither he nor the other woman can be prosecuted",
            "The messages need a certificate as electronic evidence (s.63 Bharatiya Sakshya Adhiniyam / s.65B Evidence Act)",
            "She can also seek judicial separation, maintenance and custody of the son",
        ],
        statutes="HMA s.10, s.13(1)(i), s.13(1)(ia), s.24, s.25, s.26; BSA s.63 (Evidence Act s.65B)",
        avoid=["She can file a criminal case for adultery against her husband or the other woman",
               "Adultery makes the marriage void automatically"],
    ),
    "P30": dict(
        extra="client_has_other_children: no | wife's_consent: yes",
        cover=[
            "Under the Hindu Adoptions and Maintenance Act, 1956 he can adopt with his wife's consent (s.7); the mother can give the child in adoption as the father is dead (s.9); the child must be Hindu, unmarried, under 15 and not already adopted (s.10)",
            "Conditions in s.11: to adopt a son he must have no living Hindu son; there must be an actual giving and taking. A registered adoption deed raises a presumption of validity (s.16)",
            "Effect (s.12): the boy becomes his child for all purposes, including inheritance",
            "Alternatively, step-parent adoption under the Juvenile Justice Act, 2015 and the Adoption Regulations, 2022, with an order from the District Magistrate; the name can then be changed in the records",
        ],
        statutes="HAMA 1956 s.7, s.9, s.10, s.11, s.12, s.16; Juvenile Justice Act 2015 s.56; Adoption Regulations 2022",
        avoid=["Marrying the mother automatically makes him the child's legal father",
               "The consent of the late husband's family is legally required"],
    ),
}
