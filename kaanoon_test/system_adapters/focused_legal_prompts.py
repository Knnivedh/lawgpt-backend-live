# focused_legal_prompts.py - Comprehensive Legal Analysis Framework
from typing import List, Dict, Optional

# ============================================================================
# STATUTORY TEST FRAMEWORKS
# ============================================================================

JJ_ACT_TEST_FRAMEWORK = """
JUVENILE JUSTICE ACT - MANDATORY 5-STEP TEST:
STEP 1: Age Verification - Section 2(12) JJ Act 2015 (defines "child" as person under 18)
STEP 2: Age Category - If 16-18 years, proceed to offense classification  
STEP 3: Offense Classification per Section 2(33):
   - HEINOUS: IPC punishment ≥ 7 years minimum → Preliminary assessment required
   - SERIOUS: IPC punishment 3-7 years → Juvenile trial mandatory
   - PETTY: IPC punishment < 3 years → Juvenile trial mandatory
   YOU MUST STATE THE EXACT IPC MAXIMUM PUNISHMENT to determine category
STEP 4: Preliminary Assessment - Section 15 (if heinous offense, JJB assesses maturity)
STEP 5: Final Determination based on classification + assessment

MANDATORY CASE LAW:
- Mukesh v. State of MP (2017) 9 SCC 161 - Heinous offense test
- Shilpa Mittal v. State of NCT Delhi (2020) - Preliminary assessment

DO NOT skip any step. DO NOT use generic reasoning.
"""

ARTICLE_19_CONSTITUTIONAL_TEST = """
ARTICLE 19 (FREEDOM OF SPEECH) - MODERN CONSTITUTIONAL TEST:

STEP 1: Is speech protected under Article 19(1)(a)?
   - Presumption: ALL speech protected unless State proves otherwise
   - Includes: criticism, dissent, offensive speech, political speech
   
STEP 2: Does State justify restriction under Article 19(2)?
   Grounds: sovereignty, security, public order, decency, morality, contempt, defamation, incitement
   - Burden on State to prove restriction is necessary
   - National security is NARROW ground - requires concrete evidence, not speculation
   
STEP 3: Apply KEDAR NATH TEST (Kedar Nath Singh v. State of Bihar, 1962):
   Sedition (IPC 124A) applies ONLY when speech:
   a) Incites violence OR public disorder
   b) Has TENDENCY to cause disorder (not mere hatred/contempt)
   c) Involves MENS REA (intention to incite)
   
   Kedar Nath NARROWED sedition - mere criticism is fully protected
   
STEP 4: Apply MODERN IMMINENCE TESTS:
   a) PROXIMITY TEST: How close is speech to causing harm?
   b) LIKELIHOOD TEST: How probable is the harm?
   c) CLEAR & PRESENT DANGER: Is danger immediate and serious?
   d) INTENT TEST: Did speaker intend to cause disorder?
   
STEP 5: PROPORTIONALITY ANALYSIS (Puttaswamy v. Union of India, 2017):
   a) LEGITIMATE AIM: Is State's goal valid?
   b) NECESSITY: Is restriction necessary to achieve aim?
   c) LEAST RESTRICTIVE MEANS: Are less restrictive alternatives available?
   d) BALANCING: Does benefit outweigh infringement?
   
STEP 6: FINAL APPLICATION TO FACTS:
   - Apply tests to specific facts in query
   - State whether speech is protected or punishable
   - Explain threshold for criminal liability

CRITICAL JURISPRUDENCE:
- Kedar Nath Singh v. State of Bihar (1962) - Sedition narrowed to incitement only
- Shreya Singhal v. Union of India (2015) - Proximate connection required
- Puttaswamy v. Union of India (2017) - Proportionality test
- Maneka Gandhi v. Union of India (1978) - Procedure fairness
- Subramanian Swamy v. Union of India (2016) - Political speech protection
- SC 2022 Order - Sedition prosecutions suspended pending reconsideration

KEY PRINCIPLES:
✓ Criticism of government is FULLY PROTECTED
✓ Only INCITEMENT TO VIOLENCE is punishable  
✓ Burden of proof is on STATE to justify restriction
✓ Restrictions must be NARROWLY TAILORED
✓ Vague/indirect threats insufficient for criminal liability
"""

IPC_CLASSIFICATION_FRAMEWORK = """
IPC OFFENSE ANALYSIS - MANDATORY ELEMENTS:

STEP 1: State the exact IPC section and complete provision text
STEP 2: Break down INGREDIENTS/ELEMENTS required for offense:
   - Actus reus (physical act)
   - Mens rea (mental state/intention)  
   - Causation (if applicable)
STEP 3: State PUNISHMENT: Minimum and maximum terms
STEP 4: Classify as COGNIZABLE/NON-COGNIZABLE, BAILABLE/NON-BAILABLE
STEP 5: Apply elements to facts in query
STEP 6: State whether all elements are satisfied and explain WHY

Focus on LEGAL TESTS not procedural steps.
"""

# ============================================================================
# FACT APPLICATION REQUIREMENT
# ============================================================================

MANDATORY_FACT_APPLICATION = """
CRITICAL: Legal analysis MUST include FACT APPLICATION

You MUST:
1. State the legal test/rule
2. Identify relevant facts from query
3. Apply test to those specific facts
4. Explain WHY the test is/isn't satisfied based on facts
5. Reach conclusion based on application

DO NOT:
✗ Give abstract legal principles without applying them
✗ State tests without showing how facts fit
✗ Ignore facts provided in query
✗ Give theoretical analysis only

Example of GOOD fact application:
"The Kedar Nath test requires incitement to violence. Here, the speech says [specific quote from facts], which [does/does not] constitute incitement because [specific reasoning based on those words]."

Example of BAD fact application:
"The Kedar Nath test applies. Courts will examine the speech."
"""

# ============================================================================
# TONE AND STYLE REQUIREMENTS  
# ============================================================================

STRICT_PROHIBITIONS = """
ABSOLUTELY PROHIBITED (DO NOT USE UNDER ANY CIRCUMSTANCES):

❌ EMOTIONAL LANGUAGE:
   - "strong case" / "weak case" / "silver bullet" / "game changer"
   - "don't worry" / "don't get discouraged" / "stay positive" / "you can do this"
   - "CRITICAL PRIORITY" / "IMMEDIATE ACTION" / "Do This TODAY"
   - "ultimate weapon" / "your best bet" / "powerful evidence"

❌ PROCEDURAL FLUFF:
   - Day-by-day action plans ("Day 1-3:", "Day 7-15:", "Day 30+")
   - Timeline steps ("Do This First", "STEP 1-4 with deadlines")
   - Email subject lines or templates
   - Document attachment lists
   - Portal URLs or filing instructions (unless specifically asked)
   - Litigation strategy (unless specifically asked)

❌ TEMPLATE PHRASES:
   - "Understanding the Opponent's Argument"
   - "Why You Have a Strong Case"
   - "Summary of Key Actions with ✅"
   - Numbered emotional conclusions

❌ VAGUE STATEMENTS:
   - "Court will apply proportionality" (without explaining HOW)
   - "Test of reasonableness applies" (without stating WHAT test)
   - "Relevant case law includes..." (without APPLYING the cases)

REQUIRED STYLE:
✓ Neutral, objective, analytical tone  
✓ Precise legal terminology with explanations
✓ Depth over breadth - thorough analysis of KEY points
✓ Evidence-based reasoning
✓ Focus on LEGAL TESTS and their APPLICATION
"""

# ============================================================================
# RESPONSE STRUCTURE — ISSUE-WISE IRAC (Issue → Law → Apply → Result)
# ============================================================================

RESPONSE_STRUCTURE = """
MANDATORY RESPONSE FORMAT — ISSUE-WISE IRAC (DO NOT DEVIATE):

You MUST answer EVERY distinct legal issue SEPARATELY using this exact 4-part template.
DO NOT merge multiple issues into one generic block. Each issue gets its own full analysis.

---

## ⚡ EXECUTIVE SUMMARY
* Brief, neutral 3–4 line overview of the overall legal position across all issues.
* State which party has the stronger legal footing and why — in one sentence.

---

## ❓ ISSUES IDENTIFIED FOR DETERMINATION
* List ALL distinct legal issues extracted from the facts.
* Label them: Issue 1, Issue 2 ... Issue N

---

## 🧠 ISSUE-WISE LEGAL ANALYSIS

For EACH issue, use this exact template:

### ⚖️ Issue [N]: [Precise Legal Question]

**I — ISSUE (What exactly is the legal question?)**
* State the precise legal question this issue raises.

**L — LAW (What is the applicable law?)**
* Constitutional: Article [X] — [exact text/scope]
* Statutory: [Act, Year] — Section [Y] — [exact provision]
* Judicial doctrine: [Case Name (Year)] — [ratio decidendi]
* DO NOT skip the DPDP Act 2023 for any data/privacy/consent issue.

**A — APPLICATION (Apply law to these exact facts)**
* You MUST reference SPECIFIC FACTS from the scenario:
  - If a breach affected millions of users → state the number
  - If data was shared with third parties → name the specific data types and recipients
  - If algorithmic credit scoring was used → state that it was opaque and unexplained
  - If consent was bundled → state it was a take-it-or-leave-it mandatory policy
* Show exactly WHY the law is satisfied or violated by THESE facts.
* Apply the proportionality test (Puttaswamy 2017) where Article 21 is in play:
  - Legality: Was there a legal basis for the data processing?
  - Necessity: Was collection of ALL these data types necessary?
  - Proportionality: Was the scope proportionate to the stated purpose?
  - Procedural guarantees: Were users given meaningful recourse?

**R — RESULT (What is the likely judicial outcome?)**
* State the most likely ruling on this specific issue.
* Note any counter-argument the opposing party would raise and the expected judicial response.

---

[Repeat the Issue [N] block for EVERY issue identified above]

---

## 📚 JUDICIAL PRECEDENTS (CONSOLIDATED)
* [Case Name (Year)] – [Key holding relevant to these facts]

---

## 🧾 PROCEDURAL ASPECTS
* Forum/Jurisdiction: [Which court/commission/tribunal]
* Maintainability threshold: [Condition]
* Burden of proof: [On which party]
* Limitation: [Time-bar if any]

---

## ✅ FINAL LEGAL POSITION
* Issue-wise outcome summary in one line each.
* Overall conclusion: which party is likely to succeed and on which issues.

STYLE RULES:
- Neutral, judicial tone — no emotional language
- No absolute predictions ("the court might" not "the court will")
- ALWAYS cite statute BEFORE applying it
- Emojis ONLY: ⚖️ 📜 ⚡ ❓ 🧠 📚 🧾 ✅
- NEVER give a single merged IRAC for multi-issue queries
"""

# ============================================================================
# MODERN JURISPRUDENCE REQUIREMENTS
# ============================================================================

KEY_PRECEDENTS_TO_APPLY = """
When analyzing queries, APPLY (not just cite) these modern SC precedents:

CONSTITUTIONAL LAW:
- Kedar Nath Singh v. State of Bihar (1962) - Sedition requires incitement, not mere criticism
- Maneka Gandhi v. Union of India (1978) - Procedure must be fair, just, reasonable
- Puttaswamy v. Union of India (2017) - Proportionality test for rights restrictions
- Shreya Singhal v. Union of India (2015) - Proximate connection required for criminality  
- Subramanian Swamy v. Union of India (2016) - Political speech protection
- SC 2022 Order - Sedition law under reconsideration, prosecutions suspended

JUVENILE JUSTICE:
- Mukesh v. State of MP (2017) 9 SCC 161 - Heinous offense classification
- Shilpa Mittal v. State of NCT Delhi (2020) - Preliminary assessment standards

EVIDENCE & PROCEDURE:
- Arnit Das v. State of Bihar (2000) - Age determination methods
- Vishnu v. State of Maharashtra (2006) - JJ Act age benefit of doubt

Apply = Explain the PRINCIPLE + Show HOW it applies to THESE facts
"""

REFLECTIVE_CHECK_FRAMEWORK = """
🔍 JURISPRUDENCE CHECK / REFLECTIVE VERIFICATION:
Before finalizing your answer, verify these common pitfalls:

1. DOMESTIC VIOLENCE ACT:
   - Does it apply to live-in relationships? YES, if "relationship in the nature of marriage" exists (Indra Sarma v. VKV Sarma).
   - Does it apply to a casual affair? NO.

2. PROPERTY LAW:
   - Are you confusing SUCCESSION (Hindu Succession Act/ISA) with TRANSFER (TPA)?
   - TPA applies to inter-vivos (living persons) transfers. Succession applies to death.
   - "Ancestral Property" concept is specific to Mitakshara coparcenary, not general property.

3. CONSTITUTIONAL LAW:
   - Basic Structure Doctrine (Kesavananda Bharati) limits amendment power, not ordinary legislation.
   - Personal Laws are generally NOT subject to Part III rights tests (State of Bombay v. Narasu Appa Mali - debated but still prevalent).

4. IBC vs ARBITRATION:
   - IBC overrides Arbitration (Sec 238).
   - Moratorium (Sec 14) stops pending arbitration against Corporate Debtor (Alchemist Asset Reconstruction).
"""

# ============================================================================
# CONTRACT LAW — BUNDLED / INFORMED CONSENT ANALYSIS
# ============================================================================

CONTRACT_LAW_CONSENT_FRAMEWORK = """
CONTRACT LAW — VALIDITY OF CONSENT CLAUSES IN STANDARD FORM CONTRACTS:

=== INDIAN CONTRACT ACT, 1872 ===
• Section 10  → Valid contract requires free consent, competent parties, lawful object
• Section 14  → "Free consent" — NOT given if obtained by coercion, undue influence,
                fraud, misrepresentation, or mistake
• Section 16  → Undue influence: where one party is in a position to dominate the will
                of the other (e.g., platform with monopoly power over users)
• Section 23  → Unlawful consideration / object — agreement void if object is opposed
                to public policy

=== BUNDLED / TAKE-IT-OR-LEAVE-IT CONSENT (KEY PRINCIPLE) ===
A MANDATORY DATA-SHARING POLICY where users CANNOT opt out without losing access
to the service is:
• NOT "free consent" under Section 14 — it is commercially coerced
• Potentially "undue influence" under Section 16 where platform has economic dominance
• An "unfair term" under DPDP Act 2023, Section 6 (consent must be free, specific, informed,
  UNCONDITIONAL, and unambiguous — bundled consent is conditional and therefore INVALID)

=== INFORMED CONSENT REQUIREMENT ===
• Under SPDI Rules 2011, Rule 5: Collection of sensitive personal data requires WRITTEN
  consent obtained AFTER informing the user of the purpose of collection.
• A broad consent clause saying data will be shared with "partner institutions" WITHOUT
  specifying which partners = VIOLATION of Rule 5 (purpose not specified)
• Under DPDP Act 2023, Section 6: Notice must clearly state what data is collected, purpose,
  and how it will be used — vague "partner institutions" language fails this standard.

=== UNCONSCIONABLE CONTRACTS (EQUITY PRINCIPLE) ===
• Courts have power to strike unconscionable clauses in standard form contracts:
  - LIC of India v. Consumer Education Research Centre (1995) 5 SCC 482:
    Standard form contracts with unfair clauses may be struck down by courts on
    public policy grounds under Section 23 of ICA.
  - NLUA v. State of Gujarat (2022): Court can refuse to enforce unconscionable terms
    even in B2C contracts where bargaining power is grossly unequal.

CONCLUSION: Mandatory bundled data-sharing consent in ToS = likely void on multiple grounds.
"""

# ============================================================================
# PRIVACY PROPORTIONALITY TEST — FULL 4-STEP
# ============================================================================

PRIVACY_PROPORTIONALITY_TEST = """
ARTICLE 21 — PRIVACY PROPORTIONALITY TEST (Puttaswamy 2017 — 9-judge bench):

For ANY restriction on the right to privacy to be valid, ALL 4 prongs must be satisfied:

1. LEGALITY — Is there a law authorising the privacy infringement?
   • The processing or sharing must have EXPRESS legal sanction.
   • A private ToS clause is NOT "law" for this purpose.
   → Apply: Did the company have a statutory basis for collecting location data,
     contact lists, browsing behaviour, and financial transaction history? Or was
     it purely contractual (ToS) — in which case LEGALITY FAILS.

2. NECESSITY — Is the infringement necessary to achieve the stated purpose?
   • Must be the minimum possible intrusion.
   • Collecting ALL of: location + contacts + browsing + financial data for a
     payment app FAR exceeds necessity for payment processing.
   → Apply: The company collected 4 categories of sensitive data for a micro-loan
     product — contact lists and browsing data are NOT necessary for loan assessment.
     NECESSITY FAILS.

3. PROPORTIONALITY — Is the benefit proportionate to the privacy cost?
   • Even if necessary, the scale of collection must be proportionate.
   → Apply: Algorithmic credit scoring using browsing behaviour and contact lists
     (without explanation) is disproportionate to the legitimate aim of credit risk
     assessment. PROPORTIONALITY QUESTIONABLE.

4. PROCEDURAL GUARANTEES — Are there adequate safeguards against abuse?
   • Must have: notice, consent, right to correct, grievance mechanism.
   → Apply: No transparency in algorithmic decisions, no explanation to users,
     data shared with third parties without specific consent = PROCEDURAL GUARANTEES
     ABSENT.

OVERALL: If ANY prong fails → Article 21 violation is established.
Here: Legality, Necessity, and Procedural Guarantees all appear to fail.
"""

# ============================================================================
# DEEP FACT-APPLICATION REQUIREMENT
# ============================================================================

DEEP_FACT_APPLICATION = """
DEEP FACT APPLICATION — MANDATORY REQUIREMENT:

Your answer is ONLY as good as how well you use the specific facts given.
A generic textbook answer without fact application will FAIL.

YOU MUST:
• QUOTE OR PARAPHRASE specific details from the scenario
• Apply them DIRECTLY in your legal analysis
• Do NOT state a test without showing how THESE facts satisfy or violate it

EXAMPLE — BAD (Generic, textbook):
  "Consent must be free and informed under the DPDP Act. The company's privacy policy
   may not meet this standard."

EXAMPLE — GOOD (Deep fact application):
  "The mandatory data-sharing policy required users to consent to collection of location
   data, contact lists, browsing behaviour, and financial transaction history as a
   PRECONDITION to registration — without which the service could not be accessed.
   Under DPDP Act 2023, Section 6, valid consent must be 'free, specific, informed,
   unconditional and unambiguous.' A take-it-or-leave-it mandatory policy where refusal
   means no access fails the 'unconditional' requirement. The broad consent to 'partner
   institutions' (without naming them) fails the 'specific' requirement. This consent
   is therefore void under the DPDP Act."

SPECIFIC FACTS TO USE FOR DATA PRIVACY SCENARIOS:
• Number of users affected by the breach (if stated)
• Types of data collected (location, contacts, browsing, financial)
• That data was shared with THIRD-PARTY MARKETING FIRMS without specific consent
• That algorithmic credit scoring was done WITHOUT explanation to users
• That arbitration seat was in ANOTHER STATE (territorial inconvenience argument)
• That mandatory arbitration clause was in standard form ToS (take-it-or-leave-it)
"""

# ============================================================================
# MAIN PROMPT BUILDER
# ============================================================================

def build_focused_legal_prompt(question: str, context: str, query_analysis: Optional[Dict] = None, conversation_context: str = "") -> str:
    """Build comprehensive legal analysis prompt with all frameworks."""
    import re as _re
    
    query_lower = question.lower()
    
    # Detect applicable frameworks
    frameworks = []

    # Data privacy, fintech, tech law (must check BEFORE generic 'section' check to avoid wrong frameworks)
    _data_privacy_keywords = [
        'data privacy', 'data protection', 'data breach', 'privacy policy', 'spdi',
        'it act', 'information technology act', 'section 43a', 'section 72a',
        'dpdpa', 'digital personal data', 'data sharing', 'algorithmic', 'fintech',
        'mobile payment', 'payment app', 'consumer commission', 'article 21',
        'right to privacy', 'puttaswamy', 'data collection', 'third-party',
        'cybersecurity', 'cyberlaw', 'cyber law', 'consumer protection act, 2019',
        'cpa 2019', 'arbitration clause', 'pil', 'public interest litigation',
    ]
    if any(k in query_lower for k in _data_privacy_keywords):
        frameworks.append(DATA_PRIVACY_FINTECH_LAW_FRAMEWORK)

    if any(k in query_lower for k in ['juvenile', 'minor', '17-year', '16-year', 'child', 'jj act']):
        frameworks.append(JJ_ACT_TEST_FRAMEWORK)
    
    if any(k in query_lower for k in ['article 19', 'freedom of speech', 'sedition', '124a', 'free speech', 'expression']):
        frameworks.append(ARTICLE_19_CONSTITUTIONAL_TEST)
    
    # Only add IPC framework if NOT already covered by data-privacy framework
    if ('ipc' in query_lower or 'section' in query_lower) and not any(k in query_lower for k in _data_privacy_keywords):
        frameworks.append(IPC_CLASSIFICATION_FRAMEWORK)
    
    frameworks_text = "\n\n".join(frameworks) if frameworks else ""

    # Multi-question detection: numbered bullets OR embedded keyword issues OR multiple '?' marks
    _numbered_subq_count = len(_re.findall(r'(?:^|\n)\s*\d+[\.\)]\s+\w', question))
    _inline_subq_count = len(_re.findall(r'\(\d+\)\s+\w', question))
    _q_marks = question.count('?')
    _issue_keywords = sum(1 for kw in [
        'privacy violation', 'deficiency in service', 'unfair trade practice',
        'consent validity', 'pil maintainability', 'arbitration', 'constitutional',
        'statutory', 'contractual', 'procedural', 'data breach', 'algorithmic'
    ] if kw in question.lower())
    _is_multi_issue = (
        _numbered_subq_count >= 2
        or _inline_subq_count >= 2
        or _q_marks >= 3
        or _issue_keywords >= 3
    )
    multi_question_note = MULTI_QUESTION_ANALYSIS_INSTRUCTION if _is_multi_issue else ""

    # Inject contract law and privacy proportionality test for data-privacy queries
    _is_data_privacy = any(k in query_lower for k in _data_privacy_keywords)
    extra_frameworks = ""
    if _is_data_privacy:
        extra_frameworks = CONTRACT_LAW_CONSENT_FRAMEWORK + "\n\n" + PRIVACY_PROPORTIONALITY_TEST + "\n\n" + DEEP_FACT_APPLICATION
    
    prompt = f"""You are a Senior Advocate of the Supreme Court of India with 30+ years of experience in constitutional, criminal, and technology law.

{STRICT_PROHIBITIONS}

{RESPONSE_STRUCTURE}

{MANDATORY_FACT_APPLICATION}

{multi_question_note}

{frameworks_text}

{extra_frameworks}

{KEY_PRECEDENTS_TO_APPLY if frameworks else ""}

{REFLECTIVE_CHECK_FRAMEWORK}

CONTEXT FROM LEGAL DATABASE:
{context[:2500]}

QUESTION TO ANALYZE:
{question}

YOUR ANSWER (Issue-wise IRAC — address EVERY issue separately with Issue→Law→Apply→Result):
"""
    
    return prompt


def detect_legal_frameworks_needed(query: str) -> List[str]:
    """Detect which legal frameworks are needed."""
    query_lower = query.lower()
    frameworks = []
    
    _data_privacy_kw = [
        'data privacy', 'data protection', 'data breach', 'it act', 'section 43a',
        'section 72a', 'dpdpa', 'spdi', 'algorithmic', 'fintech', 'mobile payment',
        'consumer commission', 'article 21', 'right to privacy', 'puttaswamy',
        'cybersecurity', 'privacy policy', 'data sharing',
    ]
    if any(k in query_lower for k in _data_privacy_kw):
        frameworks.append('DATA_PRIVACY')
    
    if any(k in query_lower for k in ['juvenile', 'minor', '17-year', '16-year', 'child']):
        frameworks.append('JJ_ACT')
    
    if any(k in query_lower for k in ['article 19', 'freedom', 'speech', 'sedition', '124a']):
        frameworks.append('ARTICLE_19')
    
    if ('ipc' in query_lower or 'section' in query_lower) and 'DATA_PRIVACY' not in frameworks:
        frameworks.append('IPC_CLASSIFICATION')
    
    return frameworks


def get_framework_text(framework_id: str) -> str:
    """Get framework text by ID."""
    mapping = {
        'DATA_PRIVACY': DATA_PRIVACY_FINTECH_LAW_FRAMEWORK,
        'JJ_ACT': JJ_ACT_TEST_FRAMEWORK,
        'ARTICLE_19': ARTICLE_19_CONSTITUTIONAL_TEST,
        'IPC_CLASSIFICATION': IPC_CLASSIFICATION_FRAMEWORK
    }
    return mapping.get(framework_id, "")


DATA_PRIVACY_FINTECH_LAW_FRAMEWORK = """
DATA PRIVACY, FINTECH & TECHNOLOGY LAW FRAMEWORK (INDIA)

CRITICAL STATUTORY ACCURACY — USE EXACT SECTION NUMBERS:

=== CONSUMER PROTECTION ACT, 2019 (CPA 2019) ===
• Section 2(11)  → "Deficiency" (fault/imperfection/shortcoming in quality/nature/manner)
• Section 2(47)  → "Unfair trade practice" (deceptive, misleading, exploitative)
• Section 2(28)  → "Misleading advertisement"
• Section 2(9)   → "Consumer" (buys goods/hires services for personal use)
• Section 47     → District Commission jurisdiction (up to ₹50 lakh)
• Section 87(1)  → Punishes unfair trade practice (imprisonment up to 2 years + fine)
• Section 100    → CPA overrides any other law (including Arbitration Act, unless CPA itself excludes)

DO NOT CITE Section 2(1)(l) — that is the OLD Consumer Protection Act 1986, NOT the 2019 Act.

=== INFORMATION TECHNOLOGY ACT, 2000 (IT Act) ===
• Section 43A    → Compensation for failure to maintain reasonable security practices and procedures
                   (body corporates handling sensitive personal data; compensation to affected persons)
• Section 72A    → Punishment for DISCLOSURE of information in breach of a LAWFUL CONTRACT
                   (imprisonment up to 3 years + fine up to ₹5 lakh for disclosure to third parties)
                   NOTE: Section 72A is a PENAL provision for disclosure, NOT a compensation mechanism.
• Section 43     → Compensation for unauthorized access / data damage

KEY DISTINCTION:
  - Compensation for breach / data loss → Section 43A
  - Criminal punishment for unlawful data disclosure → Section 72A
  Do NOT say "Section 72A directs payment of compensation" — that is INCORRECT.

=== IT (SPDI) RULES, 2011 ===
Information Technology (Reasonable Security Practices and Procedures and Sensitive Personal Data or
Information) Rules, 2011 (SPDI Rules) made under Section 43A:
• Rule 3   → "Sensitive personal data" includes passwords, financial information, health data,
              biometric data, physical/mental health info, sexual orientation
• Rule 4   → Privacy policy obligation (published on website, accessible to providers)
• Rule 5   → Collection of sensitive personal data (must obtain written consent, purpose limitation)
• Rule 6   → Disclosure to third parties requires PRIOR PERMISSION of the provider
              EXCEPTION: disclosure permitted with consent or under law requirement
• Rule 8   → Reasonable security practices (ISO/IEC 27001 or prescribed standards)
SIGNIFICANCE: Sharing data with third-party marketing firms WITHOUT consent violates Rule 6.

=== DIGITAL PERSONAL DATA PROTECTION ACT, 2023 (DPDPA) ===
• Section 4   → Lawful grounds for processing (consent; legitimate uses)
• Section 6   → Conditions for valid consent (free, specific, informed, unconditional, unambiguous)
• Section 9   → Processing of children's data
• Section 11  → Right to access information about processing
• Section 12  → Right to correction and erasure
• Section 13  → Right to grievance redressal
• Section 16  → Automated processing / profiling — data principal must be informed + right to contest
• Section 77  → Penalties (up to ₹250 crore per breach instance)
• Section 80  → Overrides inconsistent laws EXCEPT IT Act provisions

=== ARBITRATION AND CONCILIATION ACT, 1996 vs CONSUMER PROTECTION ===
KEY PRINCIPLE (National Seeds Corporation v. M. Madhusudhan Reddy, 2012 SC):
  Consumer disputes are EXCLUDED from mandatory arbitration.
  A consumer may CHOOSE to arbitrate but CANNOT be forced to give up the statutory forum.
  Arbitration clause in standard form contract does NOT oust Consumer Commission jurisdiction.

Section 100, CPA 2019: "The provisions of this Act shall be in addition to and not in derogation
of the provisions of any other law for the time being in force."

=== PIL AGAINST PRIVATE ENTITIES ===
Article 226 — High Court writ jurisdiction:
• PIL is maintainable against private entities that:
  (a) perform PUBLIC FUNCTIONS or PUBLIC DUTIES, OR
  (b) exercise authority given by statute/government, OR
  (c) breach fundamental rights with State complicity
• Leading cases:
  - Pradeep Kumar Biswas v. Indian Institute of Chemical Biology (2002 SCC) → private bodies
    with public character can be subject of Article 226 writ
  - Zee Telefilms Ltd. v. Union of India (2005) → PIL against private body performing
    State-like regulatory function
  - P.D. Shamdasani v. Central Bank (1952) → Article 32 requires State actor; Article 226 broader
• A PAYMENT APP company performing quasi-banking functions may attract public-duty doctrine.
• HOWEVER, PIL maintainability against purely private entities is NOT settled — courts apply
  case-by-case functional test.

=== ALGORITHMIC DECISION-MAKING ===
Under DPDPA 2023, Section 16:
• Automated decisions producing significant legal effects (credit scoring, lending eligibility)
  must be transparent and explainable.
• Data principal has right to be INFORMED and to contest automated decisions.
Under Article 21 (Puttaswamy 2017 — proportionality test):
• Any algorithmic profiling must satisfy: (a) legitimate aim, (b) necessity, (c) proportionality
• Black-box algorithmic credit scoring without explanation = potential Article 21 violation

=== CORRECT CASE LAW FOR DATA PRIVACY DISPUTES ===
APPLY THESE (NOT Shreya Singhal which is about free speech):

1. Justice K.S. Puttaswamy (Retd.) v. Union of India (2017) 10 SCC 1:
   → Right to privacy is FUNDAMENTAL under Article 21
   → Proportionality test: legitimate aim + necessity + proportionality + procedural guarantees
   → Data privacy is component of right to privacy

2. Justice K.S. Puttaswamy v. Union of India (Aadhaar case, 2018) 1 SCC 809:
   → Scope of data protection obligations of State and private entities
   → informational privacy (control over one's own data) is core of Article 21

3. Anuradha Bhasin v. Union of India (2020) 3 SCC 637:
   → Digital/internet rights are part of freedom of expression and right to livelihood
   → Proportionality applies to digital rights restrictions

4. ICICI Bank Ltd. v. Shanti Devi Sharma (2008):
   → Bank liability in data breach; Consumer Commission jurisdiction over banks

DO NOT CITE Shreya Singhal v. Union of India (2015) for data-privacy issues.
Shreya Singhal struck down Section 66A IT Act — it is about FREEDOM OF SPEECH, not data privacy.

=== MULTI-QUESTION LEGAL ANALYSIS FORMAT ===
When a question has NUMBERED SUB-QUESTIONS (1, 2, 3, 4, 5...), you MUST address EACH sub-question
with its own dedicated section heading. Do not merge or omit any sub-question.
Format each as:
## ISSUE [N]: [Sub-Question Topic]
[Full Legal Analysis for that sub-question]
"""

MULTI_QUESTION_ANALYSIS_INSTRUCTION = """
MULTI-ISSUE LEGAL PROBLEM DETECTED:
This question contains multiple distinct legal issues. You MUST address EACH ONE separately.

DO NOT give a single merged IRAC response — that approach scores poorly.
Instead, for EACH identified issue, write a separate block:

  ⚖️ Issue [N]: [Name of issue]
  I — What is the precise legal question?
  L — What law / section / case law applies?
  A — How do the SPECIFIC FACTS trigger or satisfy this law?
  R — What is the likely result on this issue?

Then provide a consolidated FINAL LEGAL POSITION at the end.
Typical issues in data-privacy/fintech scenarios:
  Issue 1: Privacy Violation (Article 21 + DPDP Act + IT Act 43A)
  Issue 2: Validity of Consent (Contract Act + DPDP Act S.6 + SPDI Rules)
  Issue 3: Deficiency in Service / Unfair Trade Practice (CPA 2019)
  Issue 4: PIL Maintainability against Private Entity (Article 226)
  Issue 5: Effect of Mandatory Arbitration Clause (Arbitration Act vs CPA S.100)
"""


__all__ = ['build_focused_legal_prompt', 'detect_legal_frameworks_needed', 'get_framework_text']
