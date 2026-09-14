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
from pathlib import Path
from datetime import datetime

LOG_DIR = Path("./logs")
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
import tempfile
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Depends, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_core.messages import HumanMessage, AIMessage

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import get_settings
from database import AsyncSessionLocal, Thread, Message, User, create_tables, get_db
from graph import create_graph
from auth import hash_password, verify_password, create_access_token, get_current_user
from lang_utils import detect_language
import spaces_client

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
    logger.info("✅ Application tables ready")

    # 2. LangGraph checkpointer
    # AsyncPostgresSaver needs the plain psycopg3 DSN (not asyncpg).
    # Convert: postgresql+asyncpg://... → postgresql://...
    pg_dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    async with AsyncPostgresSaver.from_conn_string(pg_dsn) as checkpointer:
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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


class ChatRequest(BaseModel):
    query:             str           = Field(..., min_length=1, max_length=2000)
    thread_id:         Optional[str] = Field(None, description="UUID; omit to start a new conversation")
    include_reasoning: bool          = Field(default=True)
    include_prediction: bool         = Field(default=True)

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
                "user_gender":        current_user.gender or "unknown",
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

            yield f"data: {json.dumps({'type': 'metadata', 'thread_id': thread_id})}\n\n"

            # ── 3. Open event trace file ──────────────────────────────────────
            trace_path = os.path.join(TRACE_DIR, f"{thread_id}.log")
            trace_file = open(trace_path, "a", encoding="utf-8")

            def write_trace(event_type: str, payload):
                trace_file.write(
                    json.dumps({"ts": datetime.utcnow().isoformat(), "type": event_type, "payload": payload}, default=str) + "\n"
                )
                trace_file.flush()

            # ── 4. Stream graph events ────────────────────────────────────────
            accumulated_response   = ""
            sources                = []
            message_type           = None
            reasoning_steps        = []
            precedent_explanations = []
            final_state            = {}

            family_law_app = request.app.state.family_law_app

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

                # LLM token streaming (only from generate + gather_info nodes)
                elif kind == "on_chat_model_stream" and event.get("metadata", {}).get("langgraph_node") in ("generate", "gather_info"):
                    content = event["data"]["chunk"].content
                    if content:
                        message_type = "final_response"
                        accumulated_response += content
                        yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

                # Graph completed
                elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                    output                 = event.get("data", {}).get("output", {})
                    final_state            = output
                    reasoning_steps        = output.get("reasoning_steps", [])
                    precedent_explanations = output.get("precedent_explanations", [])

                    if reasoning_steps:
                        yield f"data: {json.dumps({'type': 'reasoning', 'steps': reasoning_steps})}\n\n"
                    if precedent_explanations:
                        yield f"data: {json.dumps({'type': 'precedent_explanations', 'explanations': precedent_explanations})}\n\n"

            trace_file.close()

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
            if message_type == "information_gathering":
                completion["info_collected"] = final_state.get("info_collected", {})
                completion["info_needed"]    = final_state.get("info_needed_list", [])
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

@app.get("/")
async def root():
    return {
        "name":    "Family Law Legal Assistant API",
        "version": "3.0.0",
        "status":  "operational",
        "storage": "PostgreSQL + LangGraph AsyncPostgresSaver",
    }


@app.get("/health")
async def health_check():
    return {
        "status":    "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version":   "3.0.0",
    }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=int(os.getenv("PORT", settings.api_port)),
        log_level=settings.log_level.lower(),
        reload=False,
    )