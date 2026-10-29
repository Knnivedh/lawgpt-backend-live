"""
main.py - Family Law Legal Assistant API (production-ready).

Key changes from the local-file version:
  • Conversations persist in PostgreSQL (threads + messages tables).
  • LangGraph state persists via AsyncPostgresSaver, keyed by thread_id.
  • thread_id is a UUID generated in the backend on new conversations.
  • Messages are saved via a FastAPI BackgroundTask (non-blocking).
  • Auth stub: user_id passed in request body, FK → users table.
  • Graph is initialised once in the lifespan via asynccontextmanager.
  • Local history files and history_dir are gone.
"""

# ── Logging setup — must be first ─────────────────────────────────────────────
from hmac import new
import logging
import sys
import io
if sys.stdout and hasattr(sys.stdout, "buffer") and getattr(sys.stdout, "encoding", "").lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from pathlib import Path
from datetime import datetime

LOG_DIR = Path("./logs")
TRACE_DIR = LOG_DIR / "event_traces"
LOG_DIR.mkdir(exist_ok=True)
log_filename = LOG_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
    force=True,
)
for noisy in ("httpx", "httpcore", "urllib3", "pymilvus", "sentence_transformers"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.info("=" * 80)
logger.info("FAMILY LAW ASSISTANT API STARTING")
logger.info(f"Log file: {log_filename}")
logger.info("=" * 80)

# ── Imports ───────────────────────────────────────────────────────────────────
import json
import os
import re
import tempfile
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Depends, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_core.messages import HumanMessage, AIMessage

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import get_settings
from database import AsyncSessionLocal, Thread, Message, User, create_tables, seed_demo_users, get_db
from graph import create_graph
from auth import hash_password, verify_password, create_access_token, get_current_user
from temporal_router import get_temporal_regime, patch_retrieved_chunks
from state_guardrails import evaluate_scenario_guardrails, extract_guardrail_slots
from financial_forensics import compute_assessable_maintenance_income, analyze_financial_document_text, PayslipLineItem
from court_generators import calculate_parallel_maintenance_set_off, generate_bsa_section_63_certificate_metadata

from lang_utils import detect_language
import spaces_client

settings = get_settings()

# ─── Lifespan ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup (lightweight — no local model loading):
      1. Create application-level tables (threads, messages).
      2. Initialise the AsyncPostgresSaver and create its tables
         (checkpoints, checkpoint_writes).
      3. Compile the LangGraph app with the checkpointer.

    All AI inference is delegated to separate HuggingFace Spaces:
      - ASR (Indic)  → rverma0631/MultilingualASR
      - ASR (English)→ rverma0631/Whisper
      - TTS          → R910/IndicParler_TTS
      - LLM          → HuggingFace Inference API (via HuggingFaceEndpoint)

    Shutdown:
      Close the checkpointer connection pool.
    """
    logger.info("🚀 Starting up …")
    logger.info("🔗 ASR Space  (Indic): %s", settings.indic_asr_space_url)
    logger.info("🔗 ASR Space  (Whisper): %s", settings.whisper_space_url)
    logger.info("🔗 TTS Space: %s", settings.indic_tts_space_url)

    # 1. Application tables
    await create_tables()
    await seed_demo_users()
    logger.info("✅ Application tables ready")

    # 2. LangGraph checkpointer
    # AsyncPostgresSaver needs the plain psycopg3 DSN (not asyncpg).
    # Convert: postgresql+asyncpg://... → postgresql://...
    if not settings.database_url.startswith("postgresql"):
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        logger.info("✅ LangGraph in-memory checkpointer ready (local mode)")
        app.state.family_law_app = await create_graph(checkpointer)
        logger.info("✅ LangGraph app ready")
        yield
        logger.info("👋 Shutdown complete")
        return

    pg_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    # A pool that tests each connection before lending it out. The database
    # host (Neon) closes idle connections when it suspends; a single long-lived
    # connection then failed every chat request until the app was restarted.
    async with AsyncConnectionPool(
        pg_dsn,
        min_size=1,
        max_size=5,
        open=False,
        check=AsyncConnectionPool.check_connection,
        # autocommit and dict rows are what AsyncPostgresSaver expects;
        # no prepared statements, since the DSN may point at a pooler.
        kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
    ) as checkpointer_pool:
        checkpointer = AsyncPostgresSaver(checkpointer_pool)
        await checkpointer.setup()
        logger.info("✅ LangGraph checkpointer tables ready")

        # 3. Compile graph
        app.state.family_law_app = await create_graph(checkpointer)
        logger.info("✅ LangGraph app ready")

        yield  # ← application runs here

    logger.info("👋 Shutdown complete")


# ── FastAPI app ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Family Law Legal Assistant API",
    description="AI-powered family law consultation with explainable reasoning",
    version="3.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

cors_origins = list(settings.cors_origins) if isinstance(settings.cors_origins, (list, tuple)) else ["*"]
if "https://lawgpt-frontend.pages.dev" not in cors_origins:
    cors_origins.extend(["https://lawgpt-frontend.pages.dev", "http://localhost:3000", "http://127.0.0.1:3000"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.pages\.dev|http://localhost:.*|http://127\.0\.0\.1:.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"CORS origins: {settings.cors_origins}")


# ── Request / Response models ─────────────────────────────────────────────────

class SignUpRequest(BaseModel):
    email:     str = Field(..., min_length=3, max_length=255)
    password:  str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    gender:    Optional[str] = Field(None, description="male | female | other")


class SignInRequest(BaseModel):
    email:    str = Field(...)
    password: str = Field(...)


class AuthResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         dict


MAX_DOCUMENT_CHARS = 20000


class ChatRequest(BaseModel):
    query:             str           = Field(..., min_length=1, max_length=2000)
    thread_id:         Optional[str] = Field(None, description="UUID; omit to start a new conversation")
    include_reasoning: bool          = Field(default=True)
    include_prediction: bool         = Field(default=True)
    # Text of a document the client attached (from /documents/extract). Only
    # sent on the turn it is attached; the thread keeps it after that.
    document_text:     Optional[str] = Field(None, max_length=MAX_DOCUMENT_CHARS)
    document_name:     Optional[str] = Field(None, max_length=255)

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query cannot be empty")
        return v


class ThreadSummary(BaseModel):
    thread_id:     str
    title:         Optional[str]
    status:        str
    message_count: int
    updated_at:    str


class MessageOut(BaseModel):
    role:       str
    content:    str
    metadata:   Optional[dict]
    created_at: str


class TranscriptionResponse(BaseModel):
    text:                  str
    language:              str
    language_probability:  float
    duration_seconds:      float


MAX_ASR_UPLOAD_BYTES = 25 * 1024 * 1024  # 25MB


# ── Background task — save messages to DB ─────────────────────────────────────

async def _save_interaction(
    thread_id:   str,
    user_id:     int,
    user_query:  str,
    ai_response: str,
    ai_metadata: dict,
    final_state: dict,
):
    """
    Persist user + AI messages and update thread status.
    Runs as a BackgroundTask so it never blocks the streaming response.
    """
    async with AsyncSessionLocal() as db:
        try:
            thread_uuid = uuid.UUID(thread_id)

            # Determine new status from final graph state
            if final_state.get("has_sufficient_info"):
                new_status = "completed"
            elif final_state.get("in_gathering_phase"):
                new_status = "gathering_info"
            else:
                new_status = "analyzing"

            # Update thread title (use first query truncated) + status
            result = await db.execute(select(Thread).where(Thread.thread_id == thread_uuid))
            thread = result.scalar_one_or_none()
            if thread:
                if new_status == "gathering_info":
                    intent = final_state.get("user_intent")
                    
                    if intent:
                        thread.title = intent[:120]
                    else:
                        thread.title = user_query[:120]
                thread.status     = new_status
                thread.updated_at = datetime.utcnow()

            # Save user message
            db.add(Message(
                thread_id=thread_uuid,
                user_id=user_id,
                role="user",
                content=user_query,
            ))

            # Save AI message with full metadata
            db.add(Message(
                thread_id=thread_uuid,
                user_id=user_id,
                role="assistant",
                content=ai_response,
                metadata_json=ai_metadata,
            ))

            await db.commit()
            logger.info(f"✅ [bg] Saved interaction for thread {thread_id}")

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ [bg] Failed to save interaction: {e}", exc_info=True)


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/auth/signup", response_model=AuthResponse)
async def signup(body: SignUpRequest, db: AsyncSession = Depends(get_db)):
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        gender=body.gender,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"user_id": user.id, "email": user.email})
    logger.info(f"✅ New user registered: {user.email} (id={user.id})")
    return AuthResponse(
        access_token=token,
        user={"id": user.id, "email": user.email, "full_name": user.full_name, "gender": user.gender},
    )


@app.post("/auth/signin", response_model=AuthResponse)
async def signin(body: SignInRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"user_id": user.id, "email": user.email})
    logger.info(f"✅ User signed in: {user.email}")
    return AuthResponse(
        access_token=token,
        user={"id": user.id, "email": user.email, "full_name": user.full_name, "gender": user.gender},
    )


@app.get("/auth/me")
async def auth_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's info."""
    return {"id": current_user.id, "email": current_user.email, "full_name": current_user.full_name, "gender": current_user.gender}


class DirectQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    mode: Optional[str] = "family"
    context: Optional[str] = None
    chat_history: Optional[List[Dict[str, Any]]] = None


@app.post("/query")
@app.post("/api/query")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def handle_direct_query_endpoint(request: Request, body: DirectQueryRequest):
    return await handle_direct_query(body)


async def handle_direct_query(body: DirectQueryRequest):
    # Guardrail check
    guardrail_advice, guardrail_meta = evaluate_scenario_guardrails(body.query, {})
    # Financial forensics check
    fin_forensics = analyze_financial_document_text(body.query)

    active_mode = (body.mode or "family").lower()
    
    # ── Specialized General Citizen Legal Consultation (mode="ask") ──────────
    if active_mode == "ask":
        from advanced_legal_engine import analyze_general_legal_query
        res = analyze_general_legal_query(body.query, body.chat_history)
        if guardrail_advice:
            res["lay_summary"] = guardrail_advice + "\n\n---\n\n" + res.get("lay_summary", "")
            res["expert_summary"] = guardrail_advice + "\n\n---\n\n" + res.get("expert_summary", "")
        res["guardrail_evaluation"] = guardrail_meta
        if fin_forensics.get("income_forensics") or (fin_forensics.get("num_discrepancies_flagged", 0) > 0):
            res["financial_forensics"] = fin_forensics
        return res

    # ── Specialized Court Judgment Analysis & QA (mode="judgment") ─────────
    elif active_mode == "judgment":
        from advanced_legal_engine import analyze_court_judgment
        res = analyze_court_judgment(body.query, "query_judgment", user_query=body.query, chat_history=body.chat_history)
        if guardrail_advice:
            res["lay_summary"] = guardrail_advice + "\n\n---\n\n" + res.get("lay_summary", "")
            res["expert_summary"] = guardrail_advice + "\n\n---\n\n" + res.get("expert_summary", "")
        res["guardrail_evaluation"] = guardrail_meta
        if fin_forensics.get("income_forensics") or (fin_forensics.get("num_discrepancies_flagged", 0) > 0):
            res["financial_forensics"] = fin_forensics
        return res

    # ── Specialized Interactive Contract & Document Risk Auditor (mode="document") ──
    elif active_mode == "document":
        from advanced_legal_engine import audit_contract_document
        res = audit_contract_document(body.query, "query_document", user_query=body.query, chat_history=body.chat_history)
        if guardrail_advice:
            res["lay_summary"] = guardrail_advice + "\n\n---\n\n" + res.get("lay_summary", "")
            res["expert_summary"] = guardrail_advice + "\n\n---\n\n" + res.get("expert_summary", "")
        res["guardrail_evaluation"] = guardrail_meta
        if fin_forensics.get("income_forensics") or (fin_forensics.get("num_discrepancies_flagged", 0) > 0):
            res["financial_forensics"] = fin_forensics
        return res

    """
    Direct synchronous query endpoint providing full RAG retrieval & legal analysis
    from the 3,000+ Indian Family Law case & statutory parents.
    """
    from nodes.retriever import retrieve_documents
    state = {
        "query": body.query,
        "root_query": body.query,
        "detected_language": detect_language(body.query),
        "user_gender": "unknown",
        "name": "Client",
    }
    retrieval_res = retrieve_documents(state)
    retrieved_chunks = retrieval_res.get("retrieved_chunks", [])
    
    statutes = []
    cases = []
    seen_statutes = set()
    seen_cases = set()
    
    for c in retrieved_chunks:
        meta = c.get("metadata", {})
        title = meta.get("title") or "Indian Family Law Provision"
        cat = meta.get("category", "")
        citations = meta.get("citations") or []
        if isinstance(citations, list) and citations:
            cit_str = ", ".join(str(x) for x in citations[:3])
        else:
            cit_str = str(citations) if citations else ""
            
        content_snippet = (c.get("content") or "")[:280] + "..."
        score = float(c.get("score") or 0.88)
        
        if "2" in str(cat) or "act" in title.lower() or "section" in title.lower():
            if title not in seen_statutes:
                seen_statutes.add(title)
                statutes.append({
                    "section": cit_str or "Key Section",
                    "act": title,
                    "desc": content_snippet
                })
        else:
            if title not in seen_cases:
                seen_cases.add(title)
                cases.append({
                    "title": title,
                    "citation": meta.get("url") or "Indian Kanoon / Supreme Court of India",
                    "score": round(score, 2),
                    "headline": content_snippet
                })

    top_statute_names = [s["act"] for s in statutes[:4]]
    top_case_names = [c["title"] for c in cases[:4]]
    
    # Direct legal generation with Dahl DeepSeek / MiniMax model
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
            logger.info(f"Port 8000 check: {net_err}")

    if core_answer:
        lay_summary = core_answer
        expert_summary = (
            f"**Statutory & Judicial Framework Analysis**\n\n"
            f"- **Primary Statutes Applicable**: {', '.join(top_statute_names) if top_statute_names else 'Indian Family Law statutes'}\n"
            f"- **Key Judicial Authorities**: {', '.join(top_case_names) if top_case_names else 'Relevant Precedents'}\n\n"
            f"**Comprehensive Legal Opinion**:\n{core_answer}"
        )
    else:
        # Fallback intelligent extraction from retrieved parent chunks
        excerpts = []
        for c in retrieved_chunks[:3]:
            content = (c.get("content") or "").strip()
            if content:
                excerpts.append(content[:250])
        grounded_context = "\n\n".join([f"• {e}..." for e in excerpts]) if excerpts else "Relevant provisions under Indian Family Law."
        lay_summary = (
            f"Based on Indian Family Law provisions and retrieved judicial authorities:\n\n"
            f"Regarding your query on '{body.query}':\n\n"
            f"**Applicable Law & Principles**:\n"
            f"{grounded_context}\n\n"
            f"**Remedies & Recommendations**:\n"
            f"1. Institute proceedings before the competent Family Court under {', '.join(top_statute_names[:2]) if top_statute_names else 'the applicable statutory enactment'}.\n"
            f"2. Apply for interim relief or urgent orders supported by comprehensive documentary evidence.\n\n"
            f"---\n*Disclaimer: This analysis is for educational purposes only and does not constitute formal legal counsel.*"
        )
        expert_summary = (
            f"**Formal Legal Assessment**:\n\n"
            f"Jurisdiction and statutory interpretation under {', '.join(top_statute_names) if top_statute_names else 'governing family law codes'}.\n\n"
            f"Precedent Authorities Analyzed:\n"
            + "\n".join([f"- **{name}**" for name in top_case_names])
            + f"\n\n{lay_summary}"
        )

    if guardrail_advice:
        lay_summary = guardrail_advice + "\n\n---\n\n" + lay_summary
        expert_summary = guardrail_advice + "\n\n---\n\n" + expert_summary

    return {
        "guardrail_evaluation": guardrail_meta,
        "financial_forensics": fin_forensics if (fin_forensics.get("income_forensics") or fin_forensics.get("num_discrepancies_flagged", 0) > 0) else None,
        "structured_query": {
            "facts": body.query,
            "legal_issue": "Indian Family Law Matters (Matrimonial, Maintenance, Custody, Domestic Rights)",
            "relief_sought": "Statutory remedies, interim relief & precedent grounding",
            "keywords": ["Family Law", "CrPC 125", "Hindu Marriage Act", "Domestic Violence Act", "Maintenance", "Divorce"]
        },
        "statutes": statutes[:5],
        "top_cases": cases[:5],
        "lay_summary": lay_summary,
        "expert_summary": expert_summary,
        "total_parents_searched": 3007,
        "mode": body.mode
    }



# ── Document text extraction (shared by uploads) ─────────────────────────────

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _extract_document_text(filename: str, raw_bytes: bytes) -> Tuple[str, Optional[str]]:
    """
    Return (text, warning) for an uploaded PDF / DOCX / TXT.

    `warning` explains why little or no text came out (scanned PDF, image, old
    .doc), so callers can tell the user instead of analysing an empty file.
    """
    from io import BytesIO
    name = (filename or "").lower()

    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(raw_bytes))
            text = "\n".join(t for t in (p.extract_text() for p in reader.pages) if t).strip()
        except Exception as e:
            logger.warning(f"PDF extraction error: {e}")
            return "", "This PDF could not be read."
        if not text:
            return "", "No text found in this PDF. It may be a scanned image; please type the key details instead."
        return text, None
    if name.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(BytesIO(raw_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text).strip(), None
        except Exception as e:
            logger.warning(f"DOCX extraction error: {e}")
            return "", "This Word file could not be read."
    if name.endswith(".doc"):
        return "", "Old .doc files are not supported. Please save it as .docx or PDF and attach it again."
    if name.endswith(".txt"):
        return raw_bytes.decode("utf-8", errors="ignore").strip(), None
    if name.endswith((".jpg", ".jpeg", ".png")):
        return "", "Images are not read yet (no OCR). Please type the key details from the document."
    return "", "Unsupported file type. Please attach a PDF, DOCX or TXT file."


@app.post("/documents/extract")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def extract_document(request: Request, file: UploadFile = File(...)):
    """Extract text from an attached document so the consultation can use it."""
    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File size exceeds 10MB limit.")
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    text, warning = _extract_document_text(file.filename or "", raw_bytes)
    return {
        "filename": file.filename,
        "chars": len(text),
        "text": text[:MAX_DOCUMENT_CHARS],
        "truncated": len(text) > MAX_DOCUMENT_CHARS,
        "warning": warning,
    }


# ── Document & Judgment File Upload Endpoint ─────────────────────────────────
@app.post("/judgment-file")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def handle_judgment_file(
    request: Request,
    file: UploadFile = File(...),
    query: Optional[str] = Form(None),
    mode: Optional[str] = Form(None),
):
    """
    Handle document attachments (PDF, DOCX, TXT) up to 10MB limit.
    Extracts text and produces structured legal analysis, statutes, and precedents.
    """
    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File size exceeds 10MB limit.")
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    filename = (file.filename or "uploaded_document").lower()
    extracted_text, warning = _extract_document_text(filename, raw_bytes)
    if warning and not extracted_text:
        raise HTTPException(status_code=422, detail=warning)

    user_query = (query or "").strip()
    active_mode = (mode or "judgment").lower()

    # Generate BSA Section 63 Certificate for uploaded evidence
    bsa_cert = generate_bsa_section_63_certificate_metadata(raw_bytes, file.filename or "document")

    # ── Mode 1: Specialized Court Judgment Analysis & Briefing ───────────
    if active_mode == "judgment":
        from advanced_legal_engine import analyze_court_judgment
        res = analyze_court_judgment(extracted_text, filename, user_query)
        res["bsa_section_63_certificate"] = bsa_cert
        return res

    # ── Mode 2: Interactive Contract & Document Risk Auditor ─────────────
    elif active_mode == "document":
        from advanced_legal_engine import audit_contract_document
        res = audit_contract_document(extracted_text, filename, user_query)
        res["bsa_section_63_certificate"] = bsa_cert
        doc_fin = analyze_financial_document_text(extracted_text)
        if doc_fin.get("income_forensics") or doc_fin.get("num_discrepancies_flagged", 0) > 0:
            res["financial_forensics"] = doc_fin
        return res

    # ── Mode 3: Family or Other Context Attachment ────────────────────────
    else:
        query_str = f"{user_query}\n\n[Attached Document Context: {filename}]\n{extracted_text[:2500]}".strip() if user_query else extracted_text[:2500]
        dummy_req = DirectQueryRequest(query=query_str, mode=active_mode)
        res = await handle_direct_query(dummy_req)
        res["structured_query"]["facts"] = (user_query or f"File: {filename}") + ("\n\n[Attached File Excerpt]:\n" + extracted_text[:400] if extracted_text else "")
        res["mode"] = active_mode
        res["bsa_section_63_certificate"] = bsa_cert
        doc_fin = analyze_financial_document_text(extracted_text)
        if doc_fin.get("income_forensics") or doc_fin.get("num_discrepancies_flagged", 0) > 0:
            res["financial_forensics"] = doc_fin
        return res

# ── ASR (voice input) endpoint ────────────────────────────────────────────────


@app.post("/asr/transcribe", response_model=TranscriptionResponse)
@limiter.limit(f"{settings.asr_rate_limit_per_minute}/minute")
async def transcribe_audio(
    request:      Request,
    file:         UploadFile = File(...),
    language:     Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """
    Transcribe a short voice recording into text.

    Routes to the appropriate HuggingFace Space:
      - Explicit Indic language → rverma0631/MultilingualASR (IndicConformer)
      - Explicit non-Indic / English → rverma0631/Whisper
      - Auto-detect: Whisper for language ID, then IndicConformer if Indic

    Does not send a chat message — the client must POST the transcript to /chat/stream.
    """
    if not settings.enable_asr:
        raise HTTPException(status_code=503, detail="Voice input is disabled")

    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_ASR_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Audio file is too large")
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="No audio data received")

    suffix   = Path(file.filename or "").suffix or ".webm"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        lang_code = language  # None → auto-detect

        if lang_code and lang_code in settings.asr_indic_languages:
            # Explicit Indic language → IndicConformer Space
            data = await run_in_threadpool(
                spaces_client.call_indic_asr_space, tmp_path, lang_code
            )
        elif lang_code:
            # Explicit non-Indic (e.g. "en") → Whisper Space
            data = await run_in_threadpool(
                spaces_client.call_whisper_space, tmp_path
            )
            data["language"] = lang_code
        else:
            # Auto-detect: Whisper for language ID, IndicConformer if Indic
            logger.info("🔍 Auto-detecting language from audio …")
            data = await run_in_threadpool(
                spaces_client.call_auto_detect_space,
                tmp_path,
                settings.asr_indic_languages,
            )

        result = TranscriptionResponse(
            text=data["text"],
            language=data["language"],
            language_probability=data.get("language_probability", 1.0),
            duration_seconds=0.0,  # Gradio spaces don’t return duration
        )

    except Exception as e:
        logger.error("❌ ASR transcription failed: %s", e)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail="Could not process audio file")
    finally:
        if tmp_path:
            os.unlink(tmp_path)

    if not result.text:
        raise HTTPException(status_code=422, detail="No speech detected")

    logger.info(
        "🎙️  Transcribed audio for user=%s lang=%s",
        current_user.id, result.language,
    )
    return result






# ── TTS (IndicParler-TTS via HuggingFace Space) ──────────────────────────────

# Voice descriptions keyed by BCP-47 language prefix.
_TTS_VOICE_DESCRIPTIONS: dict[str, str] = {
    "hi": (
        "Divya speaks Hindi naturally with a clear female voice, "
        "a neutral and slightly expressive tone, moderate speaking pace "
        "and medium pitch. The recording is very high quality, "
        "close-sounding, and has no background noise."
    ),
    "ta": (
        "A natural Tamil female speaker speaks clearly at a moderate pace "
        "with a neutral, slightly expressive tone and medium pitch. "
        "The recording is very high quality, close-sounding, "
        "and has no background noise."
    ),
    "te": (
        "A natural Telugu female speaker speaks clearly at a moderate pace "
        "with a neutral, slightly expressive tone and medium pitch. "
        "The recording is very high quality, close-sounding, "
        "and has no background noise."
    ),
    "bn": (
        "A natural Bengali female speaker speaks clearly at a moderate pace "
        "with a neutral, slightly expressive tone and medium pitch. "
        "The recording is very high quality, close-sounding, "
        "and has no background noise."
    ),
    "mr": (
        "A natural Marathi female speaker speaks clearly at a moderate pace "
        "with a neutral, slightly expressive tone and medium pitch. "
        "The recording is very high quality, close-sounding, "
        "and has no background noise."
    ),
    "gu": (
        "A natural Gujarati female speaker speaks clearly at a moderate pace "
        "with a neutral, slightly expressive tone and medium pitch. "
        "The recording is very high quality, close-sounding, "
        "and has no background noise."
    ),
    "kn": (
        "A natural Kannada female speaker speaks clearly at a moderate pace "
        "with a neutral, slightly expressive tone and medium pitch. "
        "The recording is very high quality, close-sounding, "
        "and has no background noise."
    ),
    "ml": (
        "A natural Malayalam female speaker speaks clearly at a moderate pace "
        "with a neutral, slightly expressive tone and medium pitch. "
        "The recording is very high quality, close-sounding, "
        "and has no background noise."
    ),
    "pa": (
        "A natural Punjabi female speaker speaks clearly at a moderate pace "
        "with a neutral, slightly expressive tone and medium pitch. "
        "The recording is very high quality, close-sounding, "
        "and has no background noise."
    ),
    "ur": (
        "A natural Urdu female speaker speaks clearly at a moderate pace "
        "with a neutral, slightly expressive tone and medium pitch. "
        "The recording is very high quality, close-sounding, "
        "and has no background noise."
    ),
}

_TTS_VOICE_DESCRIPTIONS["en"] = (
    f"{settings.tts_english_speaker} speaks English with a clear Indian accent "
    "at a moderate pace with a neutral, slightly expressive tone and medium pitch. "
    "The recording is very clear audio, very high quality, close-sounding, "
    "and has no background noise."
)

TTS_MAX_CHARS = 500


class TTSRequest(BaseModel):
    text: str     = Field(..., min_length=1, max_length=TTS_MAX_CHARS)
    language: str = Field(default="en", max_length=10)


@app.post("/tts/synthesize")
@limiter.limit("10/minute")
async def tts_synthesize(
    request: Request,
    body: TTSRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Synthesize speech via the AI4Bharat IndicParler-TTS HuggingFace Space.
    Delegates all inference to R910/IndicParler_TTS — no local model loaded.
    Returns a WAV audio file.
    """
    text        = body.text[:TTS_MAX_CHARS].strip()
    lang_prefix = body.language.lower().split("-")[0]
    voice_desc  = _TTS_VOICE_DESCRIPTIONS.get(lang_prefix, _TTS_VOICE_DESCRIPTIONS["en"])

    logger.info(
        "🔊 TTS request: user=%s  lang=%s  chars=%d",
        current_user.id, lang_prefix, len(text),
    )

    try:
        audio_bytes = await run_in_threadpool(
            spaces_client.call_tts_space, text, voice_desc
        )
        logger.info("✅ TTS synthesized %d bytes via HF Space", len(audio_bytes))

        from fastapi.responses import Response as FastAPIResponse
        return FastAPIResponse(
            content=audio_bytes,
            media_type="audio/wav",
            headers={
                "Cache-Control": "no-store",
                "X-TTS-Language": lang_prefix,
            },
        )

    except Exception as e:
        logger.error("❌ TTS synthesis error: %s", e)
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {e}")


# ── Chat streaming endpoint ───────────────────────────────────────────────────

@app.options("/chat/stream")
async def chat_stream_options():
    return {}


@app.post("/chat/stream")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def chat_stream(
    request:          Request,
    chat_request:     ChatRequest,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
    current_user:     User         = Depends(get_current_user),
):
    """
    Streaming chat endpoint.

    Flow:
      1. If thread_id is absent → generate UUID, create Thread row, emit 'setup' SSE.
      2. Load LangGraph state from Postgres checkpointer (automatic via thread_id config).
      3. Stream graph events.
      4. After stream completes, fire a BackgroundTask to save messages.
    """

    async def event_generator():
        start_time = time.time()
        thread_id  = chat_request.thread_id or str(uuid.uuid4())
        is_new     = chat_request.thread_id is None
        user_id    = current_user.id
        trace_file = None

        try:
            logger.info("=" * 80)
            logger.info(f"REQUEST  thread={thread_id}  user={user_id}  new={is_new}")
            logger.info(f"Query: {chat_request.query}")
            logger.info("=" * 80)

            # ── 1. Create Thread row if new ───────────────────────────────────
            if is_new:
                db.add(Thread(
                    thread_id=uuid.UUID(thread_id),
                    user_id=user_id,
                    title=chat_request.query[:120],
                    status="analyzing",
                ))
                await db.commit()
                yield f"data: {json.dumps({'type': 'setup', 'thread_id': thread_id})}\n\n"
                logger.info(f"✅ Created new thread {thread_id}")

            # ── 2. Prepare initial graph state ────────────────────────────────
            # LangGraph's checkpointer restores the full state automatically when
            # we pass config={"configurable": {"thread_id": thread_id}}.
            # We only need to pass the new turn's inputs.
            graph_config = {"configurable": {"thread_id": thread_id}}

            initial_state = {
                "query":              chat_request.query,
                "messages":           [HumanMessage(content=chat_request.query)],
                "include_reasoning":  chat_request.include_reasoning,
                "include_prediction": chat_request.include_prediction,
                # Pre-detect query language so all nodes have it from turn 1
                "detected_language":  detect_language(chat_request.query),
                # Resettable per-turn fields
                "needs_more_info":    False,
                "reasoning_steps":    [],
                "precedent_explanations": [],
                "retrieved_chunks":   [],
                "sources":            [],
                "message_type":       None,
                "name": current_user.full_name or "the client",
            }
            # Only send gender when the account knows it. Sending "unknown" on
            # every turn overwrote the gender the gatherer had learned in this thread.
            if current_user.gender:
                initial_state["user_gender"] = current_user.gender
            if chat_request.document_text and chat_request.document_text.strip():
                doc_name = chat_request.document_name or "attached document"
                initial_state["document_context"] = f"[{doc_name}]\n{chat_request.document_text.strip()}"

            yield f"data: {json.dumps({'type': 'metadata', 'thread_id': thread_id})}\n\n"

            # ── 3. Open event trace file ──────────────────────────────────────
            try:
                TRACE_DIR.mkdir(parents=True, exist_ok=True)
                trace_path = TRACE_DIR / f"{thread_id}.log"
                trace_file = trace_path.open("a", encoding="utf-8")
            except OSError:
                logger.warning("Unable to open event trace; continuing chat", exc_info=True)

            def write_trace(event_type: str, payload):
                if trace_file is None:
                    return
                try:
                    trace_file.write(
                        json.dumps({"ts": datetime.utcnow().isoformat(), "type": event_type, "payload": payload}, default=str) + "\n"
                    )
                    trace_file.flush()
                except OSError:
                    logger.warning("Unable to write event trace; continuing chat", exc_info=True)

            # ── 4. Stream graph events ────────────────────────────────────────
            accumulated_response   = ""
            sources                = []
            message_type           = None
            reasoning_steps        = []
            precedent_explanations = []
            final_state            = {}
            inside_think           = False
            think_buf              = ""

            family_law_app = getattr(request.app.state, "family_law_app", None)
            if family_law_app is None:
                from langgraph.checkpoint.memory import MemorySaver
                checkpointer = MemorySaver()
                family_law_app = await create_graph(checkpointer)
                request.app.state.family_law_app = family_law_app

            async for event in family_law_app.astream_events(
                initial_state, config=graph_config, version="v2"
            ):
                write_trace("langgraph_event", event)
                kind = event["event"]

                # Clarification
                if kind == "on_chain_end" and event.get("name") == "clarify":
                    output       = event.get("data", {}).get("output", {})
                    message_type = "clarification"
                    response_text = output.get("response", "")
                    accumulated_response = response_text
                    yield f"data: {json.dumps({'type': 'clarification', 'content': response_text})}\n\n"

                # Information gathering question
                elif kind == "on_chain_end" and event.get("name") == "ask_question":
                    output        = event.get("data", {}).get("output", {})
                    message_type  = "information_gathering"
                    response_text = output.get("response", "")
                    info_collected = output.get("info_collected", {})
                    info_needed    = output.get("info_needed", [])
                    accumulated_response = response_text
                    yield f"data: {json.dumps({'type': 'information_gathering', 'content': response_text, 'info_collected': info_collected, 'info_needed': info_needed})}\n\n"

                # Retrieval sources
                elif kind == "on_chain_end" and event.get("name") == "retrieve":
                    output  = event.get("data", {}).get("output", {})
                    sources = output.get("sources", [])
                    yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

                # Generate completed - emit legal response immediately without waiting for background reasoning
                elif kind == "on_chain_end" and event.get("name") == "generate":
                    output = event.get("data", {}).get("output", {})
                    resp_val = output.get("response", "")
                    if resp_val:
                        cleaned = re.sub(r"<think>.*?</think>", "", resp_val, flags=re.DOTALL).strip()
                        if not accumulated_response:
                            accumulated_response = cleaned
                            message_type = "final_response"
                            yield f"data: {json.dumps({'type': 'token', 'content': cleaned})}\n\n"
                        else:
                            accumulated_response = cleaned

                # LLM token streaming, from the generate node only. gather_info also
                # calls the model to extract the user's answer as JSON; streaming that
                # put {"extracted_answer": ...} at the top of the final answer. Its
                # follow-up question reaches the client through ask_question above.
                elif kind == "on_chat_model_stream" and event.get("metadata", {}).get("langgraph_node") == "generate":
                    content = event["data"]["chunk"].content
                    if content:
                        think_buf += content
                        if inside_think:
                            if "</think>" in think_buf:
                                _, _, after = think_buf.partition("</think>")
                                inside_think = False
                                think_buf = ""
                                if after:
                                    message_type = "final_response"
                                    accumulated_response += after
                                    yield f"data: {json.dumps({'type': 'token', 'content': after})}\n\n"
                        elif "<think>" in think_buf:
                            before, _, remainder = think_buf.partition("<think>")
                            if before:
                                message_type = "final_response"
                                accumulated_response += before
                                yield f"data: {json.dumps({'type': 'token', 'content': before})}\n\n"
                            inside_think = True
                            think_buf = remainder
                            if "</think>" in think_buf:
                                _, _, after = think_buf.partition("</think>")
                                inside_think = False
                                think_buf = ""
                                if after:
                                    message_type = "final_response"
                                    accumulated_response += after
                                    yield f"data: {json.dumps({'type': 'token', 'content': after})}\n\n"
                        else:
                            message_type = "final_response"
                            accumulated_response += think_buf
                            yield f"data: {json.dumps({'type': 'token', 'content': think_buf})}\n\n"
                            think_buf = ""

                # Graph completed
                elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                    output                 = event.get("data", {}).get("output", {})
                    final_state            = output
                    reasoning_steps        = output.get("reasoning_steps", [])
                    precedent_explanations = output.get("precedent_explanations", [])

                    # Ensure accumulated_response is populated from generated response
                    # and token event is yielded to SSE stream if not already streamed
                    if output.get("response"):
                        cleaned_resp = re.sub(r"<think>.*?</think>", "", output["response"], flags=re.DOTALL).strip()
                        if not accumulated_response:
                            yield f"data: {json.dumps({'type': 'token', 'content': cleaned_resp})}\n\n"
                        accumulated_response = cleaned_resp
                        message_type = message_type or "final_response"

                    if reasoning_steps:
                        yield f"data: {json.dumps({'type': 'reasoning', 'steps': reasoning_steps})}\n\n"
                    if precedent_explanations:
                        yield f"data: {json.dumps({'type': 'precedent_explanations', 'explanations': precedent_explanations})}\n\n"

            # ── 5. Schedule background save ───────────────────────────────────
            latency_ms   = int((time.time() - start_time) * 1000)
            ai_metadata  = {
                "latency_ms":              latency_ms,
                "message_type":            message_type or "final_response",
                "reasoning_steps":         reasoning_steps,
                "precedent_explanations":  precedent_explanations,
                "sources":                 sources,
            }

            background_tasks.add_task(
                _save_interaction,
                thread_id,
                user_id,
                chat_request.query,
                accumulated_response,
                ai_metadata,
                final_state,
            )

            # ── 6. Send done event ────────────────────────────────────────────
            completion: dict = {
                "type":         "done",
                "message_type": message_type or "final_response",
                "response":     accumulated_response,
                "thread_id":    thread_id,
            }
            # The intake summary is useful on every turn: the UI shows what has
            # been gathered so far, and the final answer's "facts" panel too.
            completion["info_collected"] = final_state.get("info_collected", {}) or {}
            completion["info_needed"]    = final_state.get("info_needed_list", []) or []
            completion["user_intent"]    = final_state.get("user_intent")
            completion["field_labels"]   = final_state.get("field_labels", {}) or {}
            completion["sources"]        = sources
            if reasoning_steps:
                completion["reasoning_steps"] = reasoning_steps
            if precedent_explanations:
                completion["precedent_explanations"] = precedent_explanations

            yield f"data: {json.dumps(completion)}\n\n"
            logger.info(f"✅ Request done — thread={thread_id}  latency={latency_ms}ms")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"❌ Streaming error: {e}")
            logger.error(traceback.format_exc())
            yield f"data: {json.dumps({'type': 'error', 'message': 'An error occurred.'})}\n\n"
        finally:
            if trace_file is not None:
                try:
                    trace_file.close()
                except OSError:
                    logger.warning("Unable to close event trace", exc_info=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Thread management endpoints ───────────────────────────────────────────────

@app.get("/threads", response_model=List[ThreadSummary])
async def list_threads(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List all threads for a user, most-recently-updated first."""
    user_id = current_user.id
    # Count messages per thread
    msg_count_sq = (
        select(Message.thread_id, func.count(Message.id).label("cnt"))
        .group_by(Message.thread_id)
        .subquery()
    )
    result = await db.execute(
        select(Thread, msg_count_sq.c.cnt)
        .outerjoin(msg_count_sq, Thread.thread_id == msg_count_sq.c.thread_id)
        .where(Thread.user_id == user_id)
        .order_by(Thread.updated_at.desc())
    )
    rows = result.all()

    return [
        ThreadSummary(
            thread_id=str(row.Thread.thread_id),
            title=row.Thread.title,
            status=row.Thread.status,
            message_count=row.cnt or 0,
            updated_at=row.Thread.updated_at.isoformat(),
        )
        for row in rows
    ]


@app.get("/threads/{thread_id}", response_model=List[MessageOut])
async def get_thread(
    thread_id: str,
    db:        AsyncSession = Depends(get_db),
    current_user: User      = Depends(get_current_user),
):
    """Return all messages for a thread (oldest first)."""
    try:
        thread_uuid = uuid.UUID(thread_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid thread_id format")

    user_id = current_user.id
    # Verify ownership
    result = await db.execute(
        select(Thread).where(Thread.thread_id == thread_uuid, Thread.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Thread not found")

    msgs = await db.execute(
        select(Message)
        .where(Message.thread_id == thread_uuid)
        .order_by(Message.created_at.asc())
    )
    return [
        MessageOut(
            role=m.role,
            content=m.content,
            metadata=m.metadata_json,
            created_at=m.created_at.isoformat(),
        )
        for m in msgs.scalars().all()
    ]


@app.delete("/threads/{thread_id}", status_code=status.HTTP_200_OK)
async def delete_thread(
    thread_id: str,
    db:        AsyncSession = Depends(get_db),
    current_user: User      = Depends(get_current_user),
):
    """Delete a thread and all its messages (CASCADE)."""
    try:
        thread_uuid = uuid.UUID(thread_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid thread_id format")

    user_id = current_user.id
    result = await db.execute(
        select(Thread).where(Thread.thread_id == thread_uuid, Thread.user_id == user_id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    await db.execute(delete(Message).where(Message.thread_id == thread_uuid))
    await db.delete(thread)
    await db.commit()

    logger.info(f"🗑️  Deleted thread {thread_id}")
    return {"status": "success", "thread_id": thread_id}


# ── Health / root ─────────────────────────────────────────────────────────────

@app.get("/api/info")
async def api_info():
    return {
        "name":    "Family Law Legal Assistant API",
        "version": "3.0.0",
        "status":  "operational",
        "storage": "PostgreSQL + LangGraph AsyncPostgresSaver",
    }




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


@app.get("/health")
async def health_check():
    return {
        "status":    "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version":   "3.1.0-advanced-legal-engine",
    }


# ── Entry point ───────────────────────────────────────────────────────────────
# Mount static frontend
from fastapi.staticfiles import StaticFiles

_frontend_dir = Path(__file__).resolve().parent / "static_frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=int(os.getenv("PORT", settings.api_port)),
        log_level=settings.log_level.lower(),
        reload=False,
    )
