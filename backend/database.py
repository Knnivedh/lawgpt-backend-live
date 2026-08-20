"""
database.py - PostgreSQL models for the Family Law Legal Assistant.

Two application-level tables:
  • threads   — one row per conversation (metadata / status)
  • messages  — every user + AI message with JSONB metadata

LangGraph state (info_collected, gathering_step, etc.) is persisted separately
via AsyncPostgresSaver, which creates and manages its own
`checkpoints` / `checkpoint_writes` tables automatically.
"""

import os
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, DateTime, Integer,
    ForeignKey, Enum as SAEnum, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func
from dotenv import load_dotenv

load_dotenv()

# ── Connection ────────────────────────────────────────────────────────────────
# Expects DATABASE_URL in the form:
#   postgresql+asyncpg://user:password@host:5432/dbname
DATABASE_URL = os.getenv("DATABASE_URL")
print("DB URL:", DATABASE_URL)
if not DATABASE_URL:
    raise EnvironmentError("DATABASE_URL environment variable is not set.")

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,          # set True for SQL debug logs
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


# ── Models ────────────────────────────────────────────────────────────────────

class User(Base):
    """Registered user."""
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    full_name       = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    gender          = Column(String(20), nullable=True)   # male | female | other
    created_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Thread(Base):
    """
    One row per conversation.

    status mirrors the frontend status values so the thread list
    endpoint can return them directly without extra logic.
    """
    __tablename__ = "threads"

    thread_id  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(Integer, nullable=False, index=True)   # FK → users.user_id (added later)
    title      = Column(String(255), nullable=True)            # auto-filled from first query
    status     = Column(
        SAEnum("analyzing", "gathering_info", "completed", name="thread_status_enum"),
        default="analyzing",
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_threads_user_id_updated_at", "user_id", "updated_at"),
    )


class Message(Base):
    """
    Every user and AI message.

    metadata_json stores per-message extras that are not needed for
    querying but are useful for the frontend or analytics:
      - For AI messages: reasoning_steps, precedent_explanations, sources,
                         latency_ms, message_type
      - For user messages: (empty / null is fine)
    """
    __tablename__ = "messages"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id     = Column(
        UUID(as_uuid=True),
        ForeignKey("threads.thread_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id       = Column(Integer, nullable=False, index=True)
    role          = Column(String(20), nullable=False)   # "user" | "assistant"
    content       = Column(Text, nullable=False)
    metadata_json = Column(JSONB, nullable=True)         # reasoning, sources, latency …
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_messages_thread_id_created_at", "thread_id", "created_at"),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

async def create_tables():
    """Create all application-level tables (idempotent)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight migration: add columns that may be missing on older schemas
        await conn.execute(
            __import__("sqlalchemy").text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS gender VARCHAR(20)"
            )
        )


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()