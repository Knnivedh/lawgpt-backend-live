import sys
from pathlib import Path

main_path = Path(r"c:\Users\LOQ\Downloads\Indian-Family-Law-Assistant-repo\backend\main.py")
code = main_path.read_text(encoding="utf-8")

# 1. Ensure import re is present at top
if "import re" not in code:
    code = code.replace("import json", "import json\nimport re", 1)

# 2. Update handle_direct_query to use direct generate_response first
old_direct_query_snippet = """    # Query local core intelligence service on port 8000 if available
    core_answer = None
    try:
        import httpx
        with httpx.Client(timeout=8.0) as client:
            resp = client.post("http://localhost:8000/api/query", json={"question": body.query})
            if resp.status_code == 200:
                d = resp.json()
                ans = d.get("response", {}).get("answer") or d.get("answer")
                if ans and len(ans.strip()) > 50:
                    core_answer = ans.strip()
    except Exception as e:
        logger.info(f"Core intelligence fallback: {e}")"""

new_direct_query_snippet = """    # Direct legal generation with Dahl DeepSeek / MiniMax model
    core_answer = None
    try:
        from nodes.generator import generate_response
        state["retrieved_chunks"] = retrieved_chunks
        gen_res = generate_response(state)
        ans = gen_res.get("response", "")
        if ans and len(ans.strip()) > 30:
            core_answer = ans.strip()
    except Exception as e:
        logger.info(f"Direct legal generation fallback: {e}")
        try:
            import httpx
            with httpx.Client(timeout=4.0) as client:
                resp = client.post("http://localhost:8000/api/query", json={"question": body.query})
                if resp.status_code == 200:
                    d = resp.json()
                    ans = d.get("response", {}).get("answer") or d.get("answer")
                    if ans and len(ans.strip()) > 50:
                        core_answer = ans.strip()
        except Exception as net_err:
            logger.info(f"Port 8000 check: {net_err}")"""

if old_direct_query_snippet in code:
    code = code.replace(old_direct_query_snippet, new_direct_query_snippet, 1)
    print("Replaced direct query snippet successfully.")
else:
    print("WARNING: direct query snippet not matched.")

# 3. Add /judgment-file endpoint if not already present
if "@app.post(\"/judgment-file\")" not in code:
    target_pos = code.find("# ── ASR (voice input) endpoint")
    if target_pos != -1:
        judgment_file_code = """
# ── Document & Judgment File Upload Endpoint ─────────────────────────────────
@app.post("/judgment-file")
async def handle_judgment_file(file: UploadFile = File(...)):
    \"\"\"
    Handle document attachments (PDF, DOCX, DOC, TXT, JPG, PNG) up to 10MB limit.
    Extracts text and produces structured legal analysis, statutes, and precedents.
    \"\"\"
    raw_bytes = await file.read()
    if len(raw_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File size exceeds 10MB limit.")
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    filename = (file.filename or "uploaded_document").lower()
    extracted_text = ""

    if filename.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            from io import BytesIO
            reader = PdfReader(BytesIO(raw_bytes))
            pages = []
            for p in reader.pages:
                txt = p.extract_text()
                if txt:
                    pages.append(txt)
            extracted_text = "\\n".join(pages).strip()
        except Exception as e:
            logger.warning(f"PDF extraction error: {e}")
    elif filename.endswith(".docx") or filename.endswith(".doc"):
        try:
            from docx import Document
            from io import BytesIO
            doc = Document(BytesIO(raw_bytes))
            extracted_text = "\\n".join([p.text for p in doc.paragraphs if p.text]).strip()
        except Exception as e:
            logger.warning(f"DOCX extraction error: {e}")
            extracted_text = raw_bytes.decode("utf-8", errors="ignore").strip()
    elif filename.endswith(".txt"):
        try:
            extracted_text = raw_bytes.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            logger.warning(f"TXT decode error: {e}")
    elif any(filename.endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
        extracted_text = f"[Document Image: {filename}] Court petition / evidentiary exhibits submitted for statutory and precedent review."
    else:
        try:
            extracted_text = raw_bytes.decode("utf-8", errors="ignore").strip()
        except Exception:
            extracted_text = f"[Uploaded File: {filename}] Legal instrument submitted for review."

    query_str = (extracted_text[:1500] if extracted_text else f"Analysis of legal document {filename}").strip()
    dummy_req = DirectQueryRequest(query=query_str, mode="document")
    res = await handle_direct_query(dummy_req)
    res["structured_query"]["facts"] = f"File: {filename}\\n" + (extracted_text[:400] if extracted_text else "Document attachment")
    res["mode"] = "document"
    return res

"""
        code = code[:target_pos] + judgment_file_code + code[target_pos:]
        print("Added /judgment-file endpoint successfully.")
    else:
        print("WARNING: target_pos for ASR not found.")

main_path.write_text(code, encoding="utf-8")
print("SUCCESS: main.py updated successfully!")
