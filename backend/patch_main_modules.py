import re

path = r'c:\Users\LOQ\Downloads\Indian-Family-Law-Assistant-repo\backend\main.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Imports
imports = '''
from temporal_router import get_temporal_regime, patch_retrieved_chunks
from state_guardrails import evaluate_scenario_guardrails, extract_guardrail_slots
from financial_forensics import compute_assessable_maintenance_income, analyze_financial_document_text, PayslipLineItem
from court_generators import calculate_parallel_maintenance_set_off, generate_bsa_section_63_certificate_metadata
'''
if 'from state_guardrails import' not in text:
    text = text.replace('from auth import hash_password, verify_password, create_access_token, get_current_user', 'from auth import hash_password, verify_password, create_access_token, get_current_user' + imports)

# 2. Patch handle_direct_query
old_hdq_start = 'async def handle_direct_query(body: DirectQueryRequest):'
new_hdq_start = '''async def handle_direct_query(body: DirectQueryRequest):
    # Guardrail check
    guardrail_advice, guardrail_meta = evaluate_scenario_guardrails(body.query, {})
    # Financial forensics check
    fin_forensics = analyze_financial_document_text(body.query)'''

if 'guardrail_advice, guardrail_meta = evaluate_scenario_guardrails' not in text:
    text = text.replace(old_hdq_start, new_hdq_start)

old_hdq_ret = '''    return {
        "structured_query": {'''
new_hdq_ret = '''    if guardrail_advice:
        lay_summary = guardrail_advice + "\\n\\n---\\n\\n" + lay_summary
        expert_summary = guardrail_advice + "\\n\\n---\\n\\n" + expert_summary

    return {
        "guardrail_evaluation": guardrail_meta,
        "financial_forensics": fin_forensics if (fin_forensics.get("income_forensics") or fin_forensics.get("num_discrepancies_flagged", 0) > 0) else None,
        "structured_query": {'''

if '"guardrail_evaluation": guardrail_meta,' not in text:
    text = text.replace(old_hdq_ret, new_hdq_ret)

# 3. Patch /judgment-file
old_jf_ret = '''    res["structured_query"]["facts"] = (user_query or f"File: {filename}") + ("\\n\\n[Attached File Excerpt]:\\n" + extracted_text[:350] if extracted_text else "")
    res["mode"] = mode or "document"
    return res'''

new_jf_ret = '''    res["structured_query"]["facts"] = (user_query or f"File: {filename}") + ("\\n\\n[Attached File Excerpt]:\\n" + extracted_text[:350] if extracted_text else "")
    res["mode"] = mode or "document"
    
    # Generate BSA Section 63 Certificate for uploaded evidence
    bsa_cert = generate_bsa_section_63_certificate_metadata(raw_bytes, file.filename or "document")
    res["bsa_section_63_certificate"] = bsa_cert
    
    # Financial forensics on document text
    doc_fin = analyze_financial_document_text(extracted_text)
    if doc_fin.get("income_forensics") or doc_fin.get("num_discrepancies_flagged", 0) > 0:
        res["financial_forensics"] = doc_fin

    return res'''

if 'bsa_cert = generate_bsa_section_63_certificate_metadata' not in text:
    text = text.replace(old_jf_ret, new_jf_ret)

# 4. Patch /documents/extract
old_de_ret = '''    return {
        "filename": file.filename,
        "chars": len(text),
        "text": text[:MAX_DOCUMENT_CHARS],
        "truncated": len(text) > MAX_DOCUMENT_CHARS,
        "warning": warning,
    }'''

new_de_ret = '''    bsa_cert = generate_bsa_section_63_certificate_metadata(raw_bytes, file.filename or "document")
    doc_fin = analyze_financial_document_text(text)
    return {
        "filename": file.filename,
        "chars": len(text),
        "text": text[:MAX_DOCUMENT_CHARS],
        "truncated": len(text) > MAX_DOCUMENT_CHARS,
        "warning": warning,
        "bsa_section_63_certificate": bsa_cert,
        "financial_forensics": doc_fin if (doc_fin.get("income_forensics") or doc_fin.get("num_discrepancies_flagged", 0) > 0) else None,
    }'''

if 'bsa_cert = generate_bsa_section_63_certificate_metadata(raw_bytes' not in text:
    text = text.replace(old_de_ret, new_de_ret)

# 5. Add new standalone API endpoints for financial forensics, BSA certificate, and set-off calculator
new_endpoints = '''

# ── New Dedicated Legal Forensics Endpoints ───────────────────────────────────

class FinancialForensicsPayload(BaseModel):
    gross_monthly_income: Optional[float] = 0.0
    deductions: Optional[List[Dict[str, Any]]] = []
    has_minor_child: Optional[bool] = False
    document_text: Optional[str] = None


@app.post("/api/financial-forensics")
async def api_financial_forensics(payload: FinancialForensicsPayload):
    """
    Rajnesh v. Neha Financial Forensics & Discrepancy Detection.
    Normalizes true net disposable income and checks 5 perjury/concealment rules.
    """
    if payload.document_text:
        return analyze_financial_document_text(payload.document_text)

    line_items = [
        PayslipLineItem(
            label=d.get("label", "Deduction"),
            amount=float(d.get("amount", 0.0)),
            category=d.get("category", "VOLUNTARY_DEDUCTION")
        )
        for d in (payload.deductions or [])
    ]
    calc = compute_assessable_maintenance_income(
        gross_monthly_income=payload.gross_monthly_income or 0.0,
        deductions=line_items,
        has_minor_child=payload.has_minor_child or False
    )
    return {
        "financial_forensics_enabled": True,
        "income_forensics": calc,
        "rajnesh_compliance_status": "COMPLIANT"
    }


class SetOffPayload(BaseModel):
    awards: List[Dict[str, Any]]
    claimant_name: Optional[str] = "Claimant"
    respondent_name: Optional[str] = "Respondent"


@app.post("/api/set-off-calculator")
async def api_set_off_calculator(payload: SetOffPayload):
    """
    Calculates net payable maintenance across parallel proceedings (DV / BNSS / HMA)
    and drafts mandatory disclosure pleading per Rajnesh v. Neha.
    """
    return calculate_parallel_maintenance_set_off(
        awards=payload.awards,
        claimant_name=payload.claimant_name or "Claimant",
        respondent_name=payload.respondent_name or "Respondent"
    )


@app.post("/api/bsa-certificate")
async def api_bsa_certificate(
    file: UploadFile = File(...),
    device_model: Optional[str] = Form("Client Device"),
    os_version: Optional[str] = Form("Operating System"),
    deponent_name: Optional[str] = Form("Deponent")
):
    """
    Generates Section 63(4) Bharatiya Sakshya Adhiniyam, 2023 Electronic Evidence Certificate
    with SHA-256 cryptographic hash and Part A Schedule affidavit text.
    """
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="File is empty")
    return generate_bsa_section_63_certificate_metadata(
        file_bytes=raw_bytes,
        filename=file.filename or "evidence_file",
        device_model=device_model or "Client Device",
        os_version=os_version or "Operating System",
        owner_name=deponent_name or "Deponent"
    )

'''

if '/api/financial-forensics' not in text:
    text = text.replace('@app.get("/health")', new_endpoints + '\n@app.get("/health")')

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Successfully patched main.py with all Module 1-4 capabilities!')
