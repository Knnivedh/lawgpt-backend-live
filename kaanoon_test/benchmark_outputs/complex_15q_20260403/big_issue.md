Now I have a complete picture of all 15 responses. Let me write a deep, question-by-question forensic audit.

---

# ⚖️ DEEP LEGAL QA AUDIT REPORT
## AI Legal Chatbot — Benchmark Analysis (15 Scenarios)
---

## 🔴 OVERALL VERDICT FIRST

This AI system demonstrates **surface-level legal literacy** — it knows statute names, landmark case names, and general principles — but consistently **fails at depth, precision, and adversarial reasoning**. It reads like a law student's notes, not a legal advisor's analysis. The core failure pattern repeats across all 15 questions: **it describes the law instead of applying it.**

---

## Q1 — CRIMINAL LAW + EVIDENCE + CONSTITUTIONAL LAW
### *(Narco-Analysis, Section 164, Warrantless Phone Mirror, Delayed TIP)*

**❌ Critical Errors:**

**1. Mischaracterises the Section 164 scenario.** The scenario says the accused was "brought directly from police custody with no gap period" — this is the core procedural defect (Magistrate must give independent time away from police before recording confession). The AI instead says "the accused claims it was made under duress." It replaces the actual legal issue (gap-period violation under Section 164(2) CrPC) with a vague claim, missing the precise safeguard entirely.

**2. Digital evidence analysis is dangerously incomplete.** The AI cites Section 65B of the Evidence Act and says the evidence "might still be considered." It does not engage with: (a) whether a phone can be seized without a warrant at all — Section 102 CrPC permits seizure but **mirroring/cloning** is a distinct act not covered; (b) the Supreme Court's Puttaswamy privacy framework which requires legality, necessity, and proportionality for state access to digital data; (c) the distinction between admissibility and legality of collection.

**3. TIP analysis lacks legal standard.** The AI just says "the delay may affect its credibility." It does not state: what the prescribed gap actually is (generally should happen within a few weeks of arrest), the test of whether the witness had prior exposure to the accused, or the rule that a TIP conducted after the witness has seen the accused in court proceedings becomes worthless.

**4. Does not answer Sub-Question 5 at all** — whether conviction can be sustained if multiple evidence pieces are inadmissible. This is a critical appellate law question it completely ignores.

**5. Still cites old CrPC.** The BNS/BNSS framework replaced the IPC/CrPC in 2023. A system benchmarked in April 2026 should acknowledge this transition, or at minimum flag it.

---

## Q2 — FAMILY LAW + CONSTITUTIONAL LAW + SUCCESSION
### *(Triple Talaq, Maintenance, Inheritance)*

**❌ Critical Errors:**

**1. Factual error on Shah Bano.** The AI does not engage with the critical legal sequence: Shah Bano (1985) → Muslim Women Act 1986 (legislative reversal) → Danial Latifi (2001) (reading down the 1986 Act to align with Section 125) → the 2019 Act. This sequence is essential to answering sub-question 2. The AI treats the 2019 Act as if it exists in a vacuum.

**2. Inheritance analysis is legally wrong.** The AI says "the pronouncement of triple talaq does not affect the wife's rights to inheritance" and cites the Muslim Personal Law Shariat Act. This is a non-answer. The actual question is: **if talaq is void ab initio under the 2019 Act, the marriage continues legally — so the wife is a wife at death and inherits as a widow.** The AI never makes this logical connection.

**3. Constitutional challenge dismissed too quickly.** The husband's Article 25 argument is brushed aside with a one-line reference to Shayara Bano. The AI should engage with the *essential religious practice* test more rigorously, and separately address whether **criminalisation** (as opposed to merely making it void) is a proportionate restriction — this is the core debate around the 2019 Act that the AI ignores.

**4. Cites a fabricated case.** "Bilquis Bano v. State of U.P. (2020)" as an Allahabad High Court case for maintenance — this appears to be either invented or misattributed. High-risk hallucination.

**5. Sub-question 5 (simultaneous proceedings) not addressed** — can she pursue criminal proceedings under the 2019 Act and civil maintenance under BNSS simultaneously? Complete silence.

---

## Q3 — ENVIRONMENTAL LAW + CONSTITUTIONAL LAW + TORT
### *(Absolute Liability, Valid EC, NGT vs High Court)*

**❌ Critical Errors:**

**1. Misapplies Absolute Liability.** The AI says "Absolute Liability applies in this case" without engaging with the core question: does holding a **valid Environmental Clearance** insulate the company? This is the entire crux of the scenario. The correct analysis requires explaining that Absolute Liability is a tort doctrine that operates independently of regulatory compliance — a valid EC does not extinguish civil/constitutional liability. The AI skips this completely.

**2. NGT vs High Court jurisdictional analysis is superficial.** The AI says parties "may approach either." This is incorrect. The NGT Act, 2010 Section 14 gives NGT **original jurisdiction** over substantial environmental questions — the High Court's Article 226 jurisdiction does not automatically override this. The Supreme Court in *Bhopal Gas Peedith Mahila Udyog Sangathan* and related cases has addressed this tension. The AI gives no guidance.

**3. "Polluter Pays" principle cited but not applied.** The AI mentions Vellore Citizens Welfare Forum but doesn't apply the principle to the actual facts — specifically, whether the factory must pay for medical costs, loss of livelihood, groundwater restoration, and monitoring, not just "compensation."

**4. Causation with multiple polluters not addressed.** Sub-question 5 asks specifically how causation is proven when multiple industrial units contribute. The AI is completely silent on this — the "market share liability" analogy, the burden-shifting approach under environmental law, and NGT's practice on joint and several liability are all ignored.

**5. Public Liability Insurance Act analysis absent.** The AI mentions the Act but never explains its trigger (immediate relief for accidents involving hazardous substances, no-fault basis), its relationship to separate tort claims, or its procedural mechanism.

---

## Q4 — COMPANY LAW + INSOLVENCY + FRAUD
### *(IBC, Section 29A, Section 53 Waterfall, SFIO)*

**❌ Critical Errors:**

**1. Section 29A analysis is incomplete and legally imprecise.** The AI says a promoter "found guilty of fraud" is ineligible. But Section 29A disqualifies based on specified conditions — not just a "finding of guilt." Many Section 29A conditions apply before any conviction (e.g., being a connected person of an NPA account, being a wilful defaulter). The correct analysis requires mapping the facts to the specific clauses of Section 29A.

**2. The waterfall under Section 53 is stated incorrectly.** The AI says the order is: insolvency costs → financial creditors → operational creditors → shareholders. This is a gross oversimplification. The actual waterfall under Section 53 IBC is: CIRP costs → secured creditors (up to liquidation value) → workmen dues (24 months) → other employee dues → unsecured financial creditors → government dues → remaining secured creditors → operational creditors → equity. The AI's version would mislead a practitioner.

**3. Workers' rights conflict not resolved.** Sub-question 2 specifically asks how the Supreme Court has resolved the tension between Section 53 and the Industrial Disputes Act. The AI doesn't cite *Maharashtra Seamless Ltd. v. Padmanabhan Venkatesh* or the broader jurisprudence on this. It just says "the RP must prioritise."

**4. The 3% operational creditor plan challenge is not addressed.** Sub-question 3 asks the "fair and equitable" test. The AI ignores the *Swiss Ribbons* ratio and the question of whether the CoC's commercial wisdom can be judicially reviewed when operational creditors are treated so disparately. This is a live and contested area of IBC jurisprudence.

**5. SFIO powers completely under-analysed.** Section 212 Companies Act investigation, the ability to arrest, the SFIO's interaction with ED/CBI, and simultaneous operation with CIRP — none of this is addressed.

---

## Q5 — INTELLECTUAL PROPERTY + COMPETITION LAW + CONTRACTS
### *(AI Training Data, Patent, Competition, GAAR)*

**❌ Critical Errors:**

**1. AI and patent law analysis is wrong.** The AI says AI model architecture may not be patentable if "contrary to public order or morality" — this is Section 3(b) of the Patents Act, completely inapplicable here. The correct bar is **Section 3(k)** — which excludes "a mathematical method or a business method or a computer programme per se or algorithms." The AI cited the wrong exclusion. This is a significant statutory error.

**2. Fair dealing analysis under Section 52 is shallow.** The AI correctly identifies Section 52 but simply says commercial use means the exception "may not apply." It does not engage with: (a) whether AI training is analogous to "research" under Section 52(1)(a); (b) whether there is a transformative use doctrine in Indian copyright law; (c) the absence of direct Indian precedent and how courts should fill this gap by reference to comparative law (EU's Text and Data Mining exception, US fair use doctrine).

**3. Section 27 Contract Act applied incorrectly.** The AI says exclusive data-sharing agreements may be "void as restraint of trade." Section 27 is about restraining a person from practicing a profession or trade — it applies to the **parties to the agreement**, not third parties (competitors) who are foreclosed. The competition law question (Section 3/4 Competition Act) is the right frame, not Section 27.

**4. Bodhisattwa Gautam v. Subhra Chakraborty (1996) is a fabricated citation.** That case is about criminal defamation/rape — it has nothing to do with copyright infringement. This is a hallucination.

**5. CCI vs civil court concurrent jurisdiction** not addressed. Sub-question 5 explicitly asks this — the AI is silent.

---

## Q6 — LABOUR LAW + CONSTITUTIONAL + GIG ECONOMY
### *(Gig Workers, Control Test, State Legislation Validity)*

**❌ Critical Errors:**

**1. Fabricated case.** "Hamdard Dawakhana v. Union of India (2019) — gig workers entitled to social security" — this is a hallucination. Hamdard Dawakhana is a 1960 constitutional case about advertisement of drugs under the Drugs & Magic Remedies Act. It has zero connection to gig workers. This is a serious fabrication that could mislead practitioners.

**2. Control test applied without nuance.** The AI identifies algorithmic control but doesn't engage with the multi-factor test Indian courts use: control test, integration test, economic reality test. The point that **algorithmic control** as a novel form of the "control test" is itself legally contested — courts have not uniformly accepted that an algorithm = employer control — is not discussed.

**3. Seventh Schedule legislative competence analysis absent.** Sub-question 3 is specifically about whether a **state** can enact gig worker legislation. This requires analysis of: Entry 22 (Labour and employment) of the Concurrent List; whether the state law repugnates central labour codes; Article 254(2) (state law prevails with Presidential assent). The AI does not engage with any of this.

**4. Code on Social Security 2020 analysis missing.** Sub-question 5 specifically asks about this Code and whether it creates enforceable rights for gig workers (Chapter IX — Sections 109-113). The AI doesn't mention the Code at all.

**5. Worker's accident liability analysis uses outdated law.** The AI cites "Workmen's Compensation Act, 1923" — this was replaced by the **Employee's Compensation Act, 1923** (renamed) and is now being consolidated under the Code on Social Security 2020. More critically, the AI doesn't address what happens when the employment relationship is **disputed** — which is the exact scenario in the question.

---

## Q7 — BANKING LAW + FRAUD + CONSTITUTIONAL LAW
### *(Wilful Defaulter, RTI vs Banking Secrecy, Article 19(1)(g))*

**❌ Critical Errors:**

**1. Wilful defaulter definition cited wrongly.** The AI uses the SARFAESI Act definition. But wilful defaulter classification is governed by **RBI's Master Direction on Wilful Defaulters (2024 updated)**, not SARFAESI. The procedural safeguards (two-stage identification committee process, show-cause notice, personal hearing) are from the RBI Master Direction, not from any statute the AI cited.

**2. "P. Narayana v. Union of India (2011)" — appears fabricated.** No such Supreme Court case on wilful defaulters is traceable. This is likely a hallucination.

**3. Article 19(1)(g) challenge not addressed.** Sub-question 5 explicitly asks whether a wilful defaulter can invoke Article 19(1)(g) to challenge exclusions from credit, directorships, and government contracts. The AI is completely silent on this. The correct analysis involves examining whether exclusions are a "reasonable restriction" under Article 19(6) — the State Bank of India v. Jah Developers analysis applies here.

**4. RTI vs banking secrecy analysis is correct in conclusion but shallow.** The AI correctly cites RBI v. Jayantilal Mistry (2016) — but doesn't note that the Supreme Court **ordered disclosure** of defaulter names in that case, which is directly relevant to the scenario. The AI treats the case as merely establishing a "balance" when the outcome was actually pro-disclosure.

**5. PIL against RBI's regulatory inaction not analysed.** Sub-question 4 asks specifically about this — does a PIL lie against the RBI for failing to disclose names and for permitting write-offs? The AI ignores it entirely.

---

## Q8 — CRIMINAL LAW + MEDIA LAW + CONSTITUTIONAL LAW
### *(Sedition, UAPA, OSA, Habeas Corpus, Midnight Raid)*

**❌ Critical Errors:**

**1. Section 124A IPC status completely misstated.** The question explicitly refers to the **post-S.G. Vombatkere** position where the Supreme Court in May 2022 **stayed all pending prosecutions under Section 124A** and directed no fresh FIRs to be registered pending re-examination of the provision. The AI cites Kedar Nath Singh (1962) as if Section 124A is currently operative law — it does not acknowledge the Vombatkere interim stay at all. This is an egregious and current-events failure.

**2. UAPA Section 13 mischaracterised.** The AI says Section 13 "prohibits the promotion of enmity between different groups on grounds of religion, race..." — this is actually **Section 153A IPC/BNS**, not UAPA Section 13. UAPA Section 13 deals with "unlawful activity" as defined in Section 2(o) — supporting or assisting an "unlawful organisation." The AI got the provision description completely wrong.

**3. Bail under UAPA Section 43D(5) not analysed.** Sub-question 4 specifically asks about the constitutional question of bail even when statutory conditions aren't met. The AI says nothing about this. The Supreme Court in *Union of India v. K.A. Najeeb* (2021) held that constitutional courts can grant bail even under UAPA's stringent conditions if continued incarceration violates fundamental rights — a critical ruling ignored entirely.

**4. Midnight raid legality not addressed.** Sub-question 5 on the illegality of the midnight raid and warrantless seizure (Section 100 CrPC requires two independent witnesses, daytime requirement, proper panchnama) is completely missed. The AI says nothing about the raid or seized evidence admissibility.

**5. OSA public interest defence not developed.** The AI says public interest "may outweigh" classified information protection — but doesn't explain the legal test, the absence of a formal public interest defence in the OSA (unlike the UK Official Secrets Act 1989), and how courts have navigated this through Article 19 balancing.

---

## Q9 — PROPERTY LAW + LAND ACQUISITION + CONSTITUTIONAL LAW
### *(RFCTLARR, PESA, Smart City, Gram Sabha Consent)*

**❌ Critical Errors:**

**1. Section citations for RFCTLARR are wrong.** The AI says Section 30 provides for compensation (solatium of 100% market value). The correct provision is **Section 26 and Section 30** of RFCTLARR — Section 26 governs market value determination; Section 30 covers the First Schedule multiplier. The solatium of 100% is under the **First Schedule** — the AI's citation is imprecise.

**2. "Public purpose" analysis is superficial.** The scenario involves land being acquired by the state and transferred to a **private developer**. Sub-question 2 specifically asks whether this is valid "public purpose." The AI says a Smart City "may be considered public purpose" without addressing the critical issue: Section 2(1) of RFCTLARR restricts use of the acquired land, and acquisition for private entities requires **80% consent of affected families**. Transfer to a private developer potentially converts a "public purpose" acquisition into one requiring consent — this entire legal complexity is ignored.

**3. Indira Sawhney cited wrongly.** The AI cites Indira Sawhney (1992) for the proposition that property is not a fundamental right. Indira Sawhney is the reservations judgment (Mandal Commission). The correct citation is **State of West Bengal v. Bela Banerjee (1954)** or simply the 44th Constitutional Amendment removing Article 19(1)(f). The AI hallucinated a citation.

**4. Collector's failure to hear — jurisdictional vs curable defect.** Sub-question 5 asks whether non-hearing is jurisdictional or curable. The AI ignores this entirely. The correct analysis is that under Section 15 RFCTLARR, the Collector has a mandatory duty to hear objectors — courts have generally treated this as a jurisdictional requirement that vitiates the award.

**5. Post-award challenge timing not addressed.** Sub-question 1 asks whether acquisition can be challenged "even after award is passed." The AI doesn't address the question of limitation, the curative nature of statutory processes, or whether award-stage defects in PESA consent can be cured post-award.

---

## Q10 — TAX LAW + CONSTITUTIONAL + INTERNATIONAL LAW
### *(Mauritius DTAA, Transfer Pricing, GAAR, AAR)*

**❌ Critical Errors:**

**1. Azadi Bachao Andolan cited incorrectly.** The AI says the Supreme Court held in Azadi Bachao that the Mauritius DTAA's purpose is "to prevent double taxation, not facilitate tax avoidance." In fact, Azadi Bachao (2003) **upheld the validity of Mauritius tax residency certificates and rejected India's ability to deny DTAA benefits based on motive.** It was a pro-taxpayer ruling. The AI got the ratio backwards — a serious error in a tax law case.

**2. Grandfathering provision of the DTAA amendment ignored.** The 2017 DTAA amendment had an explicit **grandfathering clause** — investments made before April 1, 2017 continue to be governed by the old DTAA. The entire sub-question 1 hinges on this grandfathering provision and whether the MNC's pre-2017 structures qualify. The AI never mentions grandfathering once.

**3. GAAR applicability analysis is incomplete.** Section 96 GAAR applies to "impermissible avoidance arrangements." The AI doesn't engage with the threshold question: GAAR can be overridden by a **specific DTAA provision** (treaty override question under Section 90(2A)) — this is exactly what the scenario is about.

**4. AAR being replaced — not mentioned.** As of 2021, the AAR was replaced by the **Board for Advance Rulings (BAR)** under the Finance Act 2021. The AI repeatedly refers to the "AAR" without noting this transition, which is a factual error for a 2026 benchmark.

**5. Article 265 constitutional challenge not addressed.** Sub-question 5 explicitly asks about Article 265 and whether a transfer pricing adjustment based on subjective arm's length pricing violates it. Complete silence.

---

## Q11 — ELECTION LAW + CONSTITUTIONAL LAW + CONTEMPT
### *(Electoral Bond Scheme, Supreme Court Judgment, Enforcement)*

**❌ Critical Errors:**

**1. The system appears unaware that the Electoral Bond Scheme was struck down.** The AI discusses the PIL as pending and argues both sides — but the Supreme Court **struck down the scheme in February 2024** in *Association for Democratic Reforms v. Union of India*. This is a landmark judgment delivered before the benchmark date. The AI treats it as an open question, revealing a significant knowledge gap on a high-profile, fully decided case.

**2. Post-judgment enforcement crisis not addressed at all.** The scenario specifically asks about **enforcement** after the scheme was struck down — what happens when parties and SBI resist disclosure. The AI does not address Article 142 contempt jurisdiction, SBI's initial resistance to disclosure, the Election Commission's enforcement role, or the Supreme Court's subsequent orders. The AI gives a pre-judgment analysis for a post-judgment question.

**3. Corrupt practice under RPA 1951 not analysed.** Sub-question 5 asks whether receipt of bonds from companies with pending contracts constitutes a "corrupt practice" under the Representation of People Act. The AI mentions it briefly in the conclusion without engaging with which section of the RPA applies (Section 123) and whether electoral bonds even fall within the defined categories of corrupt practices.

**4. Contempt petition against journalist — incorrectly framed.** The AI says journalists have a right to report under Article 19 and contempt shouldn't be used against them — but it doesn't analyse the **specific OSA classification** issue in the scenario. The journalist published a leaked EC note classified under OSA — the contempt petition is secondary to the OSA prosecution question.

**5. Donor confidentiality vs Supreme Court orders — supremacy question avoided.** Sub-question 2 asks directly whether contractual confidentiality agreements can resist Supreme Court disclosure orders. The AI doesn't apply Article 142 or the principle that constitutional court orders override private contractual obligations.

---

## Q12 — MEDICAL LAW + CONSUMER LAW + CRIMINAL LAW
### *(Clinical Trial, Informed Consent, BNS, Jurisdiction)*

**❌ Critical Errors:**

**1. Consumer jurisdiction analysis ignores the paid/unpaid distinction properly.** The AI says clinical trial participation is likely a "consumer" relationship. But it doesn't engage with the actual statutory analysis: under Consumer Protection Act 2019, "consumer" requires availing a service "for consideration." If trial participation is free, the paid-consideration requirement is not met — unless one characterises the trial participant's contribution of their body as non-monetary consideration. The AI doesn't work through this analysis.

**2. "A.S. Mittal v. State of U.P. (1989)" — likely fabricated or misattributed.** This is cited for the proposition that destruction of medical records is an offence under Section 201 IPC. No such Supreme Court ruling on medical record destruction is traceable. High probability of hallucination.

**3. BNS sections cited incorrectly.** The question is set in 2026 — the BNS has replaced the IPC since July 2024. Yet the AI uses "Section 304-A IPC" and "Section 201 IPC" without reference to their BNS equivalents (Section 106 BNS for death by negligence; Section 238 BNS for causing disappearance of evidence). A 2026 benchmark must use current law.

**4. Exclusive jurisdiction question not answered.** Sub-question 5 explicitly asks whether the Drugs & Cosmetics Act creates exclusive jurisdiction. The AI says all forums can operate simultaneously — but doesn't engage with whether the D&C Act's own enforcement mechanism (through licensing authorities) is an exhaustive remedy that bars consumer jurisdiction. The analysis lacks depth.

**5. Mens rea for culpable homicide in clinical trial context not analysed.** Sub-question 4 asks specifically about the mens rea required. The AI just says it's a "serious offense" under Section 304-A (negligence) without distinguishing between: gross negligence (304-A/106 BNS) vs. knowledge that the act is likely to cause death (304 Part II / 105 BNS). The distinction is crucial and entirely absent.

---

## Q13 — ADMINISTRATIVE LAW + SERVICE LAW + CONSTITUTIONAL LAW
### *(IAS Transfer, WBP Act, ACR, Departmental Enquiry)*

**❌ Critical Errors:**

**1. Article 311 applied incorrectly.** The AI says Article 311 "protects government servants from arbitrary dismissal, removal, or reduction in rank." This is correct — but **transfers are not covered under Article 311.** Transfer challenge is an entirely different legal pathway (writ under Article 226, mala fides test). By citing Article 311 for a transfer challenge, the AI demonstrates confusion between the two remedies.

**2. Whistle Blowers Protection Act scope misunderstood.** Sub-question 3 asks whether the WBP Act protects an officer who made an **internal report** to the Chief Secretary (not to the Competent Authority under the Act). The WBP Act, 2014 defines "disclosure" as a complaint to a Competent Authority — an internal report does NOT trigger WBP Act protections. The AI says "yes, WBP Act protects her" without analysing this threshold issue. This is a substantive legal error.

**3. "D.K. Jain v. Union of India (1993)" — appears to be a fabricated citation.** The AI cites this for ACR downgrading natural justice requirements. No such case is prominently traceable. The correct authority is likely **Dev Dutt v. Union of India (2008)** (Supreme Court on adverse ACR entries and natural justice). Hallucination risk.

**4. Concurrent writ + WBP complaint question not answered.** Sub-question 5 asks whether filing a writ before the High Court bars a complaint to the WBP Competent Authority. This involves an election of remedies analysis, and whether the two are mutually exclusive or concurrent. The AI does not address this.

**5. Mala fide transfer standard not stated.** For judicial review of transfers, courts require proof of mala fide — which must be specific, not inferred. The AI says the transfer "may be challenged on grounds of mala fide" but doesn't state the evidentiary standard required, making the advice practically useless.

---

## Q14 — INTERNET LAW + DEFAMATION + FREE SPEECH
### *(Ex Parte Injunction, Section 69A, Section 79 Safe Harbour)*

**❌ Critical Errors:**

**1. Fabricated and irrelevant case citation.** The AI cites "*Babajide Otitoju v. Dapo Abiodun*" — and then itself says "this is not a known Indian case." Including a Nigerian political case in an Indian legal analysis, with no correction or explanation, is a significant quality failure.

**2. "Swamy v. RBI (2018) Delhi High Court" — appears misattributed.** "Swamy v. RBI" is a known case but about RBI's regulatory functions, not online defamation takedowns. The proposition for which it is cited is not traceable to that case. Probable hallucination.

**3. Section 69A procedure not correctly stated.** The AI says the blocking order must be "necessary and proportionate." While correct as a constitutional standard, it doesn't describe the **actual procedure** under the IT (Procedure and Safeguards for Blocking for Access of Information by Public) Rules, 2009 — which requires a designated officer, a Committee review, and a reasoned order. The Shreya Singhal judgment (2015) requires written reasons for blocking. The AI's procedural analysis is too vague to be useful.

**4. Algorithmic amplification and safe harbour — analysis is incomplete.** Sub-question 2 asks whether Section 79 safe harbour covers continued algorithmic recommendation of **mirror content** after a takedown. This is a cutting-edge issue — the AI says it "may be seen as a violation" but doesn't engage with the "actual knowledge" + "expeditious action" requirements in Section 79(3)(b), or the distinction between content the Platform hosted vs. content on third-party mirrors it merely recommended.

**5. Public figure doctrine not properly applied.** Indian defamation law for public figures is not as developed as the US "actual malice" standard (New York Times v. Sullivan). The AI imports the US standard without explaining that Indian defamation law under Section 499 IPC/BNS Exception 1 uses a "good faith and public good" test, which is substantially different.

---

## Q15 — INTERNATIONAL LAW + EXTRADITION + FUNDAMENTAL RIGHTS
### *(FEO Act, Dual Criminality, Family Asset Attachment, Article 20)*

**❌ Critical Errors:**

**1. FEO Act administrator misidentified.** The AI says the FEO Act is administered by the "Director of the Enforcement Wing of the CBI." This is incorrect. The FEO Act is administered by the **Enforcement Directorate (ED)** under the Department of Revenue. The CBI is a separate agency. This is a basic factual error.

**2. "Kartikeya Sarabhai v. State of Gujarat (2012)" — appears fabricated.** This case is cited for the proposition that attachment before conviction violates Article 21. No such Supreme Court ruling is traceable. Hallucination risk. The correct jurisprudence on this issue involves *Nikesh Tarachand Shah v. Union of India* (2018) on PMLA bail and asset attachment, and the subsequent legislative response.

**3. "Gian Chand v. State of Haryana (2016)" — appears fabricated or misattributed.** Cited for upholding pre-conviction attachment under a state act. Not traceable as a Supreme Court precedent on this issue. Another probable hallucination.

**4. Dual criminality principle not properly explained.** Sub-question 3 asks whether extradition can proceed for remaining charges if two charges don't satisfy dual criminality. The AI never addresses this. The correct answer is that most extradition treaties (and the Indian Extradition Act, 1962, Section 2(c)) permit **partial extradition** for charges that do satisfy dual criminality, subject to the requested country's agreement.

**5. Article 20(1) analysis for civil forfeiture missing.** Sub-question 5 asks whether civil forfeiture under the FEO Act attracts Article 20(1) protection (no ex post facto punishment). The AI doesn't answer this. The critical issue is: does civil forfeiture = "punishment" under Article 20(1)? Courts have generally held that civil forfeiture is not "punishment" in the constitutional sense — but the argument deserves engagement. The AI is silent.

---

## 📊 SUMMARY SCORECARD

| Q# | Domain | Fabricated Cases | Statute Errors | Missing Sub-Questions | Depth Rating |
|---|---|---|---|---|---|
| Q1 | Criminal/Evidence | 0 | 2 (CrPC not BNSS; mirroring) | 1 (Q5) | 4/10 |
| Q2 | Family/Muslim Law | 1 (Bilquis Bano) | 1 (Shah Bano sequence) | 1 (Q5) | 3/10 |
| Q3 | Environmental | 0 | 1 (EC shield issue) | 2 (Q4, Q5) | 4/10 |
| Q4 | IBC/Insolvency | 0 | 2 (Section 53 waterfall wrong) | 2 (Q3, Q5) | 3/10 |
| Q5 | IP/Competition | 2 (Bodhisattwa; Perkins) | 2 (Section 3(k) wrong; Sec 27 wrong) | 1 (Q5) | 2/10 |
| Q6 | Labour/Gig | 1 (Hamdard Dawakhana) | 2 (Workmen's Comp; Code 2020) | 2 (Q3, Q5) | 2/10 |
| Q7 | Banking/Fraud | 1 (P. Narayana) | 1 (SARFAESI vs RBI MD) | 2 (Q4, Q5) | 3/10 |
| Q8 | Criminal/Media | 0 | 3 (UAPA S.13; Vombatkere; UAPA bail) | 2 (Q4, Q5) | 2/10 |
| Q9 | Land Acquisition | 1 (Indira Sawhney) | 2 (Sec 30 wrong; public purpose) | 2 (Q1, Q5) | 3/10 |
| Q10 | Tax/International | 1 (Azadi Bachao ratio reversed) | 2 (Grandfathering; BAR vs AAR) | 1 (Q5) | 3/10 |
| Q11 | Election Law | 0 | 1 (Scheme struck down — unaware) | 3 (Q1, Q2, Q5) | **1/10** |
| Q12 | Medical/Consumer | 1 (A.S. Mittal) | 2 (IPC not BNS; consumer test) | 1 (Q5) | 3/10 |
| Q13 | Admin/Service | 1 (D.K. Jain) | 2 (Art 311 misapplied; WBP Act scope) | 1 (Q5) | 3/10 |
| Q14 | Internet/Defamation | 2 (Babajide; Swamy) | 1 (Section 69A procedure) | 1 (Q5) | 2/10 |
| Q15 | Extradition/FEO | 2 (Kartikeya; Gian Chand) | 2 (ED vs CBI; dual criminality) | 2 (Q3, Q5) | 2/10 |

---

## 🔑 SYSTEMIC FAILURE PATTERNS

**Pattern 1 — Case Hallucination (Highest Risk Defect).** The system fabricates or misattributes case citations in at least 10 of 15 questions. For a legal AI, this is the single most dangerous failure — a lawyer who acts on a fabricated precedent faces professional misconduct consequences.

**Pattern 2 — Law Version Freezing.** The system applies IPC/CrPC throughout despite the BNS/BNSS replacing them in July 2024. For a system benchmarked in April 2026, this represents nearly two years of legal obsolescence on one of the most fundamental updates in Indian criminal law history.

**Pattern 3 — Sub-Question 5 Blindness.** In virtually every scenario, the last sub-question (usually the most procedurally or jurisdictionally complex one) is not answered. The system appears to front-load its response and run out of analytical steam.

**Pattern 4 — Describing Law Instead of Applying It.** The system recites what statutes say, then says "therefore the court will consider X." It almost never takes a position, balances competing arguments, or reaches a defensible conclusion. A legal practitioner needs conclusions, not descriptions.

**Pattern 5 — Current Events Blackout.** Q11 (Electoral Bonds) is the most glaring example — a landmark Supreme Court ruling from February 2024 is completely unknown to the system. Any legal AI must be updated or RAG-augmented with recent judgments. Without this, it gives structurally wrong answers to post-judgment enforcement questions.

**Pattern 6 — No Adversarial Depth.** The system identifies one side's argument, mentions the other side exists, and moves on. It never steelmans the losing party's position or identifies the specific point of legal contest that will determine the outcome.