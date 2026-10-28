"""
legal_notes.py - Statute notes handed to the answer generator.

The retrieved material is real forum Q&A and often uses old names or loose
section numbers (for example it puts the right to reside under PWDVA s.12, and
CrPC became BNSS on 1 July 2024). These notes give the generator correct
section numbers for the provisions family-law answers lean on most, so it does
not have to guess.

The notes are split into topics and `select_notes(text)` returns only the ones
a case touches. Sending all of them cost ~2,200 tokens per call, which on a
free Groq key (8,000 tokens/minute) leaves room for one answer a minute.

Keep this short and factual. It orients the model; it is not legal advice, and
it should be reviewed by an advocate when a statute changes.
"""

import re
from typing import List, Tuple

HEADER = "VERIFIED STATUTE NOTES (use with the Legal Context; do not cite anything that is in neither):"

CORE = """Renamed laws (in force from 1 July 2024):
- CrPC 1973 -> Bharatiya Nagarik Suraksha Sanhita (BNSS) 2023: maintenance s.125 CrPC = s.144 BNSS; venue s.126 = s.145; enforcement s.128 = s.147.
- IPC -> Bharatiya Nyaya Sanhita (BNS) 2023: cruelty by husband or his relatives s.498A IPC = s.85 BNS (defined in s.86); dowry death s.304B IPC = s.80 BNS.

Where to apply: a PWDVA application goes to the Magistrate (Judicial Magistrate First Class or Metropolitan Magistrate). Maintenance under s.125 / s.144 and HMA petitions are filed in the Family Court where one exists.

Leading case: Rajnesh v. Neha (2020) 2 SCC 324. In every maintenance case both parties file an Affidavit of Disclosure of Assets and Liabilities; maintenance is payable from the date of the application; earlier awards in other proceedings must be disclosed and set off; the court weighs the standard of living, the earning capacity of the paying spouse, the children's education and medical costs, and whether the claimant gave up work. It does not apply to adoption, custody or inheritance disputes."""

# (topic, trigger regex on the lower-cased case text, note)
SECTIONS: List[Tuple[str, str, str]] = [
    ("maintenance", r"maintenance|alimony|support|expenses|money|income|salary|stopped (?:giving|paying|sending)|\b125\b|\b144\b|bnss",
     """Maintenance:
- s.125 CrPC / s.144 BNSS: wife who cannot maintain herself, minor children, disabled adult children, parents. A maintenance case under this section (and only this section) may be filed where the respondent lives, where the claimant wife lives, or where the couple last lived together (s.126 / s.145); a parent or child claiming against a son or father files where that person lives. Unpaid maintenance is recovered like a fine, with up to one month's imprisonment for each month unpaid (s.125(3)); the order can be enforced anywhere in India (s.128 / s.147).
- HAMA 1956: s.18 wife's maintenance; s.20 maintenance of children and aged parents; s.19 widowed daughter-in-law; s.22 dependants of a deceased Hindu."""),

    ("hma", r"hindu|divorce|separat|restitution|cruelty|desertion|conjugal|mutual|marriage act|\bhma\b",
     """Hindu Marriage Act 1955: s.9 restitution of conjugal rights; s.10 judicial separation; s.13 divorce grounds (cruelty, desertion for 2 years, adultery, conversion, mental disorder and others); s.13B mutual consent (the 6-month wait can be waived by the court: Amardeep Singh v. Harveen Kaur, 2017); s.14 no divorce petition in the first year of marriage except for exceptional hardship; s.19 a petition lies in the court where the marriage was held, where the parties last lived together, where the respondent lives, or where the wife (as petitioner) lives. The respondent is the spouse who was sued: a husband who files as petitioner cannot rely on his own city, so a husband's petition in a city where only he lives can be challenged for want of territorial jurisdiction. A pending petition can be transferred: by the High Court within one State (s.24 CPC) or by the Supreme Court between States (s.25 CPC), and the Supreme Court often moves a case to the wife's home city; s.24 interim maintenance and litigation costs, claimed in the court where the HMA petition is pending (the spouse who was sued can apply there); a spouse with no HMA case pending claims under s.125 CrPC / s.144 BNSS instead; s.25 permanent alimony; s.26 custody, maintenance and education of children; s.28A enforcement of decrees and orders like civil decrees."""),

    ("sma", r"inter-?faith|inter-?religio|different religion|special marriage|court marriage|register(?:ed)? marriage|boyfriend|girlfriend|elope",
     """Special Marriage Act 1954: ss.5, 6 and 7 give 30 days' public notice of intended marriage to the Marriage Officer of the district where one party has lived for 30 days, and the objection process; no conversion is needed; s.27 divorce; s.28 mutual consent; s.36 interim alimony; s.37 permanent alimony. Two adults may marry by choice without their parents' consent; police protection can be sought if the family threatens them."""),

    ("christian", r"christian|church|indian divorce act|adulter|affair|co-?respondent",
     """Christian divorce (Indian Divorce Act 1869): s.10 grounds (including adultery and cruelty); s.10A mutual consent after 2 years' separation; the alleged adulterer must normally be made a co-respondent (s.11), and adultery is usually proved by circumstantial evidence. Alimony under s.36 (during the case) and s.37 (permanent) is for the wife. India has no statutory formula for dividing matrimonial property: assets are dealt with by title and general property law."""),

    ("muslim", r"muslim|talaq|talak|nikah|mehr|mahr|khula|islam|sunni|shia|iddat",
     """Muslim law: the Muslim Women (Protection of Rights on Marriage) Act 2019 makes instant triple talaq (talaq-e-biddat) void and illegal, punishable with up to 3 years' imprisonment; the wife stays married, may claim a subsistence allowance for herself and dependent children (s.5) and custody of minor children (s.6). The Muslim Women (Protection of Rights on Divorce) Act 1986 s.3: mehr and a fair and reasonable provision (Danial Latifi, 2001). A Muslim woman can also claim under s.125 CrPC / s.144 BNSS (Mohd. Abdul Samad v. State of Telangana, 2024). A wife can seek dissolution under the Dissolution of Muslim Marriages Act 1939 (s.2) or by khula, which is separate from the 1986 Act. Mehr is a debt owed to the wife, recoverable separately from maintenance. Under Muslim personal law the mother has hizanat (custody) of a son up to about age 7 and of a daughter until puberty, subject to the child's welfare."""),

    ("pwdva", r"violence|beat|beating|abus|harass|domestic|threat|residen|shared household|live-?in|taunt|thrown out|throw|evict|dowry|stridhan|dispossess|protection order",
     """Domestic Violence Act 2005 (PWDVA): s.3 definition of domestic violence, including economic abuse (stopping money, taking stridhan); s.12 application to the Magistrate; s.17 right to reside in the shared household; s.18 protection orders; s.19 residence orders; s.20 monetary relief; s.21 custody orders; s.22 compensation; s.23 interim and ex parte orders. Only a woman can be an aggrieved person under the PWDVA; a man cannot apply under it. A woman in a live-in relationship "in the nature of marriage" is covered (Indra Sarma v. V.K.V. Sarma, 2013)."""),

    ("dowry", r"dowry|498|stridhan|false case|false dowry|harassment case|extort|anticipatory",
     """Dowry and stridhan: Dowry Prohibition Act 1961 s.3 (giving or taking) and s.4 (demanding); s.6 dowry must be handed over to the woman. Stridhan belongs to the woman and can be recovered. Voluntary gifts to the couple are not dowry, but gifts to the bride are her stridhan.
False or threatened cruelty/dowry cases: s.498A IPC / s.85 BNS is cognizable and non-bailable. A person who fears arrest may apply for anticipatory bail (s.438 CrPC = s.482 BNSS). Arnesh Kumar v. State of Bihar (2014): police must not arrest automatically in such cases and must first use the notice-of-appearance procedure (s.41A CrPC = s.35 BNSS). The High Court can quash an abusive case (s.482 CrPC = s.528 BNSS). Threatening a false case to extract money can amount to extortion (s.384 IPC = s.308 BNS) or criminal intimidation (s.506 IPC = s.351 BNS). Wrongful confinement: s.127 BNS."""),

    ("evidence", r"whatsapp|screenshot|message|recording|call record|photo|chat|video|audio|email",
     """Evidence: WhatsApp messages, screenshots and call recordings are electronic evidence and need a certificate under s.63 of the Bharatiya Sakshya Adhiniyam 2023 (formerly s.65B of the Evidence Act)."""),

    ("children", r"child|son\b|daughter|custody|visit|guardian|passport|abroad|school|minor|kid",
     """Children and travel: the welfare of the child is the paramount consideration (Guardians and Wards Act 1890 s.7 and s.17). Both parents are treated as natural guardians (Gita Hariharan, 1999). Under HMGA 1956 s.6(a), custody of a child under 5 should ordinarily be with the mother. A guardianship or custody petition can ask the court to stop a parent taking the child out of the country; a parent can also write to the Regional Passport Office objecting to a minor's passport. India is not a party to the Hague Convention on child abduction."""),

    ("adoption", r"adopt",
     """Adoption by Hindus (HAMA 1956 ss.6-12, 16): the adopter must be an adult of sound mind; a married man needs his wife's consent (s.7); a married woman adopts only with her husband's consent (s.8). The child must be a Hindu, unmarried and under 15 unless custom allows (s.10). A man cannot adopt a son if he already has a Hindu son, grandson or great-grandson living (s.11); a step-son is not the adopter's son for this rule. The child must be actually given and taken (s.11(vi)); a registered adoption deed raises a presumption that the adoption is valid (s.16). The mother can give a child in adoption only if the father is dead, has renounced the world or has ceased to be a Hindu (s.9). HAMA adoption is a private ceremony and deed, not a court decree. Where HAMA does not fit, or the child is orphaned, abandoned or surrendered, the Juvenile Justice Act 2015 route applies, with an order from the District Magistrate and CARA rules; step-parent adoption under that Act needs the consent of the child's other parent or proof of that parent's death."""),

    ("property", r"propert|inherit|\bwill\b|ancestral|succession|partition|\bland\b|\bshare\b|passed away|\bdied\b|death|estate",
     """Property: Hindu Succession Act 1956 s.6 (as amended in 2005): a daughter is a coparcener by birth with the same rights as a son, even if the father died before 2005 (Vineeta Sharma v. Rakesh Sharma, 2020). s.8: heirs of a Hindu male who dies without a will; Class I heirs (widow, sons, daughters, mother) take equally. In ancestral (coparcenary) property, a notional partition is made at the father's death (s.6(3)): each coparcener, including daughters, gets a share by birth, and the father's own share then passes under s.8, so each child receives a coparcenary share plus part of the father's share. Self-acquired property passes by s.8 only. Marriage does not take away a daughter's share. Nobody inherits from a living person: while a husband or father is alive his property is his, and a wife or child has no ownership share in it, only maintenance claims and, for a wife, a right to reside in the shared household. Worked example (ancestral house; father dead; mother alive; two sons and one daughter): the notional partition gives the father and each of the three children 1/4; the father's 1/4 is then shared equally by his four Class I heirs (the mother and the three children), 1/16 each. So each child holds 1/4 + 1/16 = 5/16 and the mother 1/16. If the house were the father's self-acquired property, the four heirs would each take 1/4."""),

    ("senior", r"senior|aged|elderly|old age|retired|pension|parents?\b|\b[6-9]\d[- ]year|i am (?:6|7|8|9)\d\b",
     """Senior citizens: the Maintenance and Welfare of Parents and Senior Citizens Act 2007 s.4 makes children and heirs liable to maintain parents; ss.5, 6 and 7 (application to the Maintenance Tribunal, which should decide within 90 days); s.23 a transfer of property made on condition that the transferee will provide basic needs is void if he then neglects the parent, and the Tribunal can order it set aside; s.24 abandonment of a senior citizen is an offence (up to 3 months' imprisonment). The Tribunal can also order eviction in suitable cases. Parents may alternatively claim under s.125 CrPC / s.144 BNSS or HAMA s.20."""),

    ("bigamy", r"second (?:wife|marriage|husband)|another (?:woman|wife|man)|bigam|remarr|convert|conversion|polygam",
     """Second marriage while the first subsists: for Hindus a second marriage is void (HMA s.5(i) and s.11) and bigamy is punishable (HMA s.17; s.494 IPC = s.82 BNS, up to 7 years' imprisonment); children of the void second marriage are legitimate (HMA s.16). Converting to another religion does not end the first marriage or make a second marriage valid (Sarla Mudgal v. Union of India, 1995). The first wife stays his legal wife with her rights to maintenance and to reside in the shared household."""),

    ("nri", r"\bnri\b|abroad|overseas|\busa\b|america|united states|canada|\buk\b|england|australia|dubai|foreign|emigrat|green card|h-?1b|visa",
     """Spouse abroad (NRI): a summons or notice for a spouse living abroad is served through the court via the Ministry of External Affairs or the Hague Service Convention channel (India and the USA are both parties); a court can also allow service by email or WhatsApp. A foreign divorce decree is recognised in India only if it meets s.13 of the Code of Civil Procedure: the foreign court must have had jurisdiction under the law the parties are governed by and must have decided the case on the merits on a ground available under Indian law (Y. Narasimha Rao v. Y. Venkata Lakshmi, 1991). A parent who fears the child will be taken abroad can seek a court order restraining it and object at the Regional Passport Office. Indian maintenance orders can be enforced against assets in India."""),

    ("livein", r"live-?in|without marriage|not married|unmarried|pregnan|partner|cohabit|relationship",
     """Live-in relationships: s.125 CrPC / s.144 BNSS speaks of a "wife", so a live-in partner succeeds only if the court treats the relationship as a presumed marriage (Chanmuniya v. Virendra Kumar, 2010); the PWDVA is the safer route (Indra Sarma, 2013). A child born of the relationship can claim maintenance from the father under s.125 / s.144 either way."""),
]

# When nothing in a case matches a topic, these are the most useful defaults.
DEFAULT_TOPICS = ("maintenance", "hma", "pwdva")


def select_notes(text: str) -> str:
    """The statute notes a case touches: the core block plus every topic whose trigger matches `text`."""
    low = (text or "").lower()
    picked = [note for name, pattern, note in SECTIONS if re.search(pattern, low)]
    if not picked:
        picked = [note for name, _, note in SECTIONS if name in DEFAULT_TOPICS]
    return HEADER + "\n\n" + CORE + "\n\n" + "\n\n".join(picked)


# Everything, for tests and for callers that want the full reference.
STATUTE_NOTES = HEADER + "\n\n" + CORE + "\n\n" + "\n\n".join(note for _, _, note in SECTIONS)
