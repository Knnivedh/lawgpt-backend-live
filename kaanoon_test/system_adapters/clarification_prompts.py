# clarification_prompts.py
# Enhanced prompts for legal clarification loop with structured lawyer-style questions

INTENT_ANALYSIS_PROMPT = """
STAGE 1: QUERY INTAKE & UNDERSTANDING
You are an expert legal strategist specializing in Indian law.

USER QUERY:
"{query}"

USER SELECTED CATEGORY: {category}

INITIAL LEGAL CONTEXT (Verified Laws/Cases found):
{initial_legal_context}

TASK:
1. Analyze the user's INTENT.
2. Classify the LEGAL DOMAIN (Consumer, Real Estate/RERA, Family, Criminal, Employment, Contract, etc.)
3. CROSS-REFERENCE User Query with Initial Legal Context.
4. Identify MISSING FACTS based on domain-specific requirements.

STRUCTURED INTAKE CHECKLIST BY DOMAIN:

=== FOR ALL CASES (BASIC INFO) ===
- Date of transaction/incident
- Amount involved (if any)
- Nature of product/service
- Opposing party details (seller/developer/employer name)
- Any written agreements or contracts

=== FOR CONSUMER PROTECTION CASES ===
A. Transaction Details:
   - Purchase date, invoice/receipt, payment mode (UPI/card/EMI), GST
   - Product/service type and price
   
B. Problem Description:
   - Nature of defect/deficiency (when noticed, immediate or after use)
   - Financial loss, inconvenience, or mental harassment suffered
   
C. Evidence & Documentation:
   - Bill, invoice, warranty documents
   - Defective product retained?
   - Photos/videos of defect
   
D. Seller Response:
   - Complaint made? How? (email/phone/in-person)
   - Seller's response and any offer made
   - Repair/replacement/refund offered?

E. Legal Factors:
   - Arbitration clause in agreement?
   - Seller authorization status
   - Other complaints against same seller?

=== FOR REAL ESTATE / RERA DISPUTES ===
A. Agreement Details:
   - Booking date, allotment letter, agreement for sale
   - Promised possession date
   - Total cost and payment mode
   
B. Delay & Problem:
   - Actual delay period (months/years)
   - Reasons given by developer
   - Missing/altered amenities vs brochure
   
C. Documentation:
   - Agreement copy, payment receipts, loan documents
   - Developer's delay communications
   - RERA registration number (if known)
   
D. Contractual Clauses:
   - Force majeure clause wording
   - Arbitration clause (developer-appointed?)
   - Limitation of liability clause
   
E. Status:
   - OC/CC obtained?
   - Developer still demanding payments?
   - Buyer's purpose (self-use vs investment)
   
F. Other Buyers:
   - Similar complaints from other buyers?
   - Any collective action?

=== FOR FAMILY LAW ===
- Marriage date, place, registration
- Children (ages, custody concerns)
- Grounds for relief (cruelty, desertion, etc.)
- Assets and income details
- Maintenance requirements

=== FOR BANKING / FINANCIAL SERVICES MIS-SELLING ===
A. Transaction Details:
   - Date of investment/transaction
   - Amount invested
   - Product name (FD, mutual fund, ULIP, structured product?)
   - Bank/institution name and branch

B. Sales Process:
   - Who sold the product (Relationship Manager name, designation)
   - What was orally promised vs what's in documents
   - Was product presented as "safe" or "guaranteed"?
   - Were risks explained in simple language?

C. Documentation:
   - Investment receipt/confirmation
   - Product terms and conditions document
   - Email/SMS communications with bank staff
   - Digital consent records

D. Disclosure Issues:
   - Were risk disclosures in fine print?
   - Was customer given time to read before signing?
   - Was product suitability assessed?
   - Is customer a senior citizen? (Age)

E. Losses:
   - Capital loss amount
   - Expected vs actual returns
   - Penalty for premature withdrawal
   - Documents showing loss

F. Bank Response:
   - Complaint made to bank?
   - Bank's response (written/oral)
   - Any compensation offered?

=== FOR EMPLOYMENT DISPUTES ===
- Employment period (joining to termination dates)
- Designation and salary
- Nature of complaint (termination, wages, harassment)
- Written communications (appointment letter, termination letter)
- Internal complaints made?

CRITICAL INSTRUCTION:
1. First determine the query_type:
   - "general_knowledge": Asking about laws, provisions, sections, rights, legal concepts,
     landmark cases, statutory definitions, procedures, legal reforms, comparisons.
     NO personal situation described. Academic/informational in nature.
   - "case_consultation": Describing a personal legal issue. Uses "I", "my", "we",
     "our", "help me", etc. Needs specific legal advice for their situation.
   - "hypothetical_scenario": Presents a fictional scenario ("If a person...",
     "A consumer bought...") seeking general legal analysis.

2. For "general_knowledge" and "hypothetical_scenario" queries:
   - Set missing_facts to EMPTY list []
   - Set ambiguity_score to 1 or 2

3. For "case_consultation" queries:
   - Identify missing facts as before
   - Set appropriate ambiguity_score

You must output ONLY valid JSON. No markdown, no explanations.

OUTPUT FORMAT (JSON):
{{
    "intent": "Brief description of user's core intent",
    "domain": "Legal Domain (Consumer/RERA/Family/Employment/Criminal/Contract/Constitutional/Procedural)",
    "query_type": "general_knowledge | case_consultation | hypothetical_scenario",
    "missing_facts": [
        "Only for case_consultation: Most critical missing fact",
        "Only for case_consultation: Second most critical fact"
    ],
    "ambiguity_score": 1-10
}}
"""

QUESTION_GENERATION_PROMPT = """
STAGE 2: QUESTION GENERATION (Loop {current_step}/5)
You are a Senior Advocate interviewing a client. You have {remaining_steps} questions left.

ORIGINAL INTENT & MISSING FACTS:
{context_matrix}

PREVIOUS ANSWER (from user):
"{last_answer}"

STRUCTURED QUESTION TEMPLATES BY DOMAIN:

=== QUESTION 1 (BASIC INFO) ===
For ALL cases, first establish:
- When did this happen? (Exact date of purchase/booking/incident)
- How much money is involved? (Total amount paid/claimed)
- Who is the opposing party? (Seller name/Developer name/Employer name)

=== CONSUMER PROTECTION QUESTIONS ===
Q1: "What is the exact date of purchase and total amount paid? Do you have the invoice/receipt?"
Q2: "What specific defect or problem did you notice, and when did you first notice it?"
Q3: "Did you complain to the seller? What was their response? Do you have written proof?"
Q4: "Is there an arbitration clause in your purchase agreement? Was it highlighted to you?"
Q5: "Have you suffered any financial loss beyond the product price (rent, interest, medical bills)?"

=== REAL ESTATE / RERA QUESTIONS ===
Q1: "What is the booking date and promised possession date as per agreement?"
Q2: "By how many months/years is possession delayed? What reasons has the developer given in writing?"
Q3: "Does the agreement contain a force majeure or arbitration clause? What does it say?"
Q4: "Is the project RERA registered? Has the developer obtained OC/CC?"
Q5: "Are you buying for self-occupation or investment? Are other buyers also complaining?"

=== BANKING / FINANCIAL MIS-SELLING QUESTIONS ===
Q1: "What is the exact date of investment and total amount invested? What product did the bank say you were buying?"
Q2: "Who sold you this product (name, designation)? What did they orally promise about safety or returns?"
Q3: "Were the risk disclosures explained to you in simple language, or were they in fine print? Did you have time to read before signing?"
Q4: "Are you a senior citizen? Was a suitability assessment done to check if this product was right for you?"
Q5: "What losses have you incurred (capital loss, penalty, lost interest)? Has the bank responded to your complaint in writing?"

=== EMPLOYMENT QUESTIONS ===
Q1: "What are your employment dates (joining to termination) and last drawn salary?"
Q2: "Do you have appointment letter, salary slips, and termination letter (if applicable)?"
Q3: "What is the specific nature of your complaint (wrongful termination/unpaid wages/harassment)?"
Q4: "Did you raise any internal complaint or grievance? What was the response?"
Q5: "Are there witnesses or documentary evidence to support your claim?"

TASK:
Generate EXACTLY ONE follow-up question based on what is STILL UNKNOWN.

QUESTION QUALITY RULES:
1. Be SPECIFIC - Ask for exact dates, amounts, document names
2. Ask for ONE decision-shaping fact area only. Do not bundle multiple independent questions.
3. Ask for DOCUMENTARY PROOF - "Do you have written/email confirmation?"
4. Target LEGAL OUTCOMES - Each question should help establish maintainability, jurisdiction, or liability
5. NO generic questions like "Is there anything else?"
6. Do not output a numbered list, bullets, alternatives, or more than one question mark.

PRIORITY ORDER:
1. Date & Amount (establishes jurisdiction, limitation)
2. Documentary Evidence (establishes prima facie case)
3. Opposing Party Response (establishes deficiency/unfair practice)
4. Contractual Clauses (arbitration, force majeure)
5. Damages & Losses (quantifies relief)

OUTPUT FORMAT:
Just one question string. Be direct and professional.
"""

# NOTE: Legacy consumer/RERA case-brief template. It is kept for reference and
# possible domain-specific reuse, but it is no longer bound to the
# CONTEXT_SYNTHESIS_PROMPT name: the neutral, domain-agnostic template below
# replaces it. Previously the two assignments shared one name, so this template
# was silently discarded at import time.
CONTEXT_SYNTHESIS_PROMPT_CONSUMER_TEMPLATE = """
STAGE 4: CONTEXT CONSOLIDATION
You are a Legal Case Analyst preparing a case brief for a Senior Advocate.

INITIAL INTENT:
{initial_intent}

INTERVIEW TRANSCRIPT:
{transcript}

TASK:
Create a structured case matrix organized for legal analysis.

OUTPUT FORMAT (Markdown):

## CASE BRIEF: [One-line case description]

### A. PARTIES & TRANSACTION
- Complainant: [Name if known]
- Opposite Party: [Seller/Developer/Employer name]
- Date of Transaction: [Date]
- Amount Involved: ₹[Amount]
- Nature: [Product/Property/Service/Employment]

### B. FACTS OF THE CASE
- [Chronological bullet points of key facts]

### C. GRIEVANCE & DEFICIENCY
- Primary Complaint: [Defect/Delay/Unfair Practice]
- Supporting Evidence: [List documents available]
- Seller/Developer Response: [What was offered/refused]

### D. CONTRACTUAL TERMS (If Applicable)
- Arbitration Clause: [Yes/No - Terms]
- Force Majeure: [Yes/No - Terms]
- Limitation of Liability: [Yes/No - Terms]

### E. LEGAL INDICATORS
- Domain: [Consumer/RERA/Employment]
- Maintainability: [Likely maintainable because...]
- Principal Issues: [List key legal questions]

### F. RELIEF SOUGHT
- Primary: [Refund/Compensation/Possession]
- Secondary: [Interest/Damages/Costs]
- Quantification Basis: [How amount is calculated]

### G. DATA GAPS (If Any)
- [List facts still unknown that may affect opinion]
"""

CONTEXT_SYNTHESIS_PROMPT = """
STAGE 4: CONTEXT CONSOLIDATION
You are a Legal Case Analyst preparing a neutral issue matrix for a Senior Advocate.

INITIAL INTENT:
{initial_intent}

INTERVIEW TRANSCRIPT:
{transcript}

TASK:
Create a structured legal matrix from the original prompt and the clarification answers.
Preserve the user's assumptions exactly. Do not force every matter into a consumer,
RERA, employment, or transaction template. If the prompt is a moot/hypothetical/debate
scenario, keep it as a court-balancing problem and identify both sides.

OUTPUT FORMAT (Markdown):

## CASE BRIEF: [One-line case description]

### A. PARTIES / ACTORS
- Primary person(s): [A/B/user/company/etc.]
- Opposing or interested parties: [parents/State/police/company/etc.]
- Forum or authority: [court/police/tribunal/commission, if known]
- Procedural stage: [FIR/habeas/hearing/complaint/etc., if known]

### B. CLARIFIED ASSUMPTIONS
- [Each clarification answer as a binding assumption]

### C. CHRONOLOGY AND MATERIAL FACTS
- [Chronological bullet points of key facts]

### D. GOVERNING LEGAL AREAS
- Constitutional provisions:
- Statutes / procedural codes:
- Personal law or special statutes:
- Evidence rules:
- Any pleaded provisions:

### E. ISSUES FOR DETERMINATION
- [List each distinct legal issue separately]

### F. SIDE-WISE POSITIONS
- Position 1:
- Position 2:
- State / regulator / police position, if relevant:

### G. EVIDENCE AND BURDEN
- Admitted facts:
- Disputed facts:
- Documents / digital evidence:
- Burden of proof:

### H. REQUESTED FINAL ANSWER FORMAT
- [Neutral analysis / side-wise advocacy / likely outcome / hybrid / other]

### I. REMAINING DATA GAPS
- [Only facts still unknown that may affect the opinion]
"""

LEGAL_SCOPE_CHECK_PROMPT = """
You are a Legal Relevance Guardrail & Mini-Assistant for an INDIAN LAW AI system.
Query: "{query}"

Task: 
1. Determine if this is related to Indian Law/Legal issues (is_legal: true/false).
2. If NOT legal, provide a ONE-SENTENCE helpful answer to the query (answer: "Text").
3. If IS legal, the answer field can be empty.

CLASSIFICATION RULES:
- Set is_legal=true for ANYTHING related to: Indian courts, statutes, IPC, BNS, BNSS, BSA, CrPC,
  Constitution, fundamental rights, consumer protection, RERA, family law, criminal law, legal
  reforms, sections/articles of Indian law, Supreme Court/High Court judgments, anticipatory bail,
  FIR, lawyers, police, contracts, property, arbitration, GST, income tax, or ANY legal matter in India.
- CRITICAL: Questions about NEW Indian laws (BNS 2024, BNSS, BSA, criminal law reforms, law
  transitions) are ALWAYS legal, even if they mention dates beyond your knowledge cutoff.
  Your knowledge cutoff does NOT determine whether a query is legal or not.
- Set is_legal=false ONLY for clearly non-legal topics: cooking recipes, sports scores,
  entertainment, weather, general science, math, geography unrelated to India law.
- When in doubt, ALWAYS default to is_legal=true.

CRITICAL: Output ONLY valid JSON.
Format:
{{
    "is_legal": true/false,
    "answer": "Brief 1-sentence answer only if not legal"
}}
"""

SCENARIO_GAP_ANALYSIS_PROMPT = """
You are a senior Indian advocate doing case intake. Read the user's scenario and list the
facts that are MISSING from it but would change the legal analysis.

USER SCENARIO (verbatim: the only source of facts you may treat as given):
"{query}"

RETRIEVED CONTEXT (may be partial or empty: evidence of issues, never evidence of facts):
{initial_legal_context}

RULES FOR EACH GAP
- Ask only for a fact that is NOT already stated or clearly implied above. Never ask
  again for a date, amount, party, forum or document the scenario already gives.
- If the scenario already names the parties and the relief sought, never ask "what is
  your role", "who is the other party" or "what exact outcome or relief do you want".
- Name the actual parties, documents, transactions or fora from the scenario, so the
  question could not be reused for a different case.
- One fact per question, exactly one question mark, plain professional English, and no
  more than 30 words. Ask about facts only, never about what the law is.
- Priority order: (1) jurisdiction, limitation and the correct forum; (2) the applicable
  statutory regime, but only if the scenario's own dates leave it unclear; (3) the exact
  pleadings, sections, notices or orders invoked; (4) how evidence was obtained, whether
  it is disputed or authenticated; (5) income, amounts and assets where they drive
  relief; (6) the current procedural stage, deadlines or urgent risk.
- Return between 2 and {max_questions} gaps. For a rich, fact-dense scenario prefer the
  full {max_questions}; return fewer only when genuinely fewer facts are missing. Never
  pad, and never invent a gap merely to reach a number.
- NEVER reuse a fixed template question. If a question could be asked, unchanged, for a
  different case, it is wrong: rewrite it so it names this scenario's parties, documents,
  fora or events.
- If how the final answer should be framed genuinely depends on the user's preference
  (neutral court-style analysis vs advocacy for one party vs likely outcome), make the
  LAST gap an answer-posture question phrased with THIS scenario's actual parties and
  fora — e.g. for a PIL plus consumer-commission scenario: "Should the answer analyse the
  High Court PIL and the Consumer Commission complaints together, or focus on one forum
  first?" Never mention parties or forums that do not exist in the scenario.

EXAMPLE OF THE STANDARD. For a wife who left the matrimonial home and filed a Domestic
Violence Act case, whose husband filed for divorce on mental cruelty and produced WhatsApp
chats between her and her advocate taken from her laptop, good gaps are: "Did the husband
have authorized access to her laptop, or did he bypass her password?" and "What are both
spouses' monthly incomes and liabilities?". Never produce "what is your role in this
dispute", "what exact outcome or relief do you want", or "where is the arrested person
now" (nobody was arrested).

Domains (choose every one that genuinely applies): family_matrimonial, constitutional,
criminal_bns, criminal_procedure, evidence_bsa, contract, sale_of_goods, consumer, rera,
employment, banking_rddbfi, property_revenue, it_act, arbitration, taxation, other

Reply with ONLY this JSON object. No prose, no markdown, no code fences.
{{"domains": ["..."], "data_gaps": [{{"key": "snake_case", "question": "... ?", "why": "which issue or relief this changes"}}]}}
"""
