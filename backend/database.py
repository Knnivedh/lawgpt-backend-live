"""
database.py - Database models for the Family Law Legal Assistant.
Supports both SQLite (local development) and PostgreSQL (production).

Two application-level tables:
  • threads   — one row per conversation (metadata / status)
  • messages  — every user + AI message with JSON metadata
"""

import os
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, DateTime, Integer,
    ForeignKey, Enum as SAEnum, Index
)
from sqlalchemy.types import TypeDecorator, CHAR, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB as PG_JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func
from dotenv import load_dotenv

load_dotenv()

# ── Connection ────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./family_law.db")

engine_kwargs = {"echo": False}
if "sqlite" not in DATABASE_URL:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    })

engine = create_async_engine(DATABASE_URL, **engine_kwargs)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


class CompatibleUUID(TypeDecorator):
    """Platform-independent GUID/UUID type."""
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            try:
                return uuid.UUID(str(value))
            except Exception:
                return value
        return value


CompatibleJSON = JSON().with_variant(PG_JSONB, "postgresql")


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
    """One row per conversation."""
    __tablename__ = "threads"

    thread_id  = Column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    user_id    = Column(Integer, nullable=False, index=True)
    title      = Column(String(255), nullable=True)
    status     = Column(
        SAEnum("analyzing", "gathering_info", "completed", name="thread_status_enum", native_enum=False),
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
    """Every user and AI message."""
    __tablename__ = "messages"

    id            = Column(CompatibleUUID, primary_key=True, default=uuid.uuid4)
    thread_id     = Column(
        CompatibleUUID,
        ForeignKey("threads.thread_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id       = Column(Integer, nullable=False, index=True)
    role          = Column(String(20), nullable=False)   # "user" | "assistant"
    content       = Column(Text, nullable=False)
    metadata_json = Column(CompatibleJSON, nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_messages_thread_id_created_at", "thread_id", "created_at"),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

async def create_tables():
    """Create all application-level tables (idempotent)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if engine.dialect.name == "postgresql":
            await conn.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS gender VARCHAR(20)"
                )
            )


GUEST_EMAIL = "guest@local.invalid"


async def seed_demo_users():
    """Ensure demo user profiles and the shared guest account exist in the database."""
    import bcrypt
    import secrets
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        try:
            res = await db.execute(select(User).where(User.email == GUEST_EMAIL))
            if not res.scalar_one_or_none():
                # Random password nobody knows: the guest row exists only so
                # unauthenticated chats have an owner; it cannot be signed into.
                unusable = bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt()).decode("utf-8")
                db.add(User(email=GUEST_EMAIL, full_name="", hashed_password=unusable, gender=None))
                await db.commit()
        except Exception:
            await db.rollback()
    demo_profiles = [
        ("adv.rajesh@lawgpt.in", "Adv. Rajesh Sharma", "male"),
        ("priya.verma@lawgpt.in", "Dr. Priya Verma", "female"),
        ("ananya.d@lawgpt.in", "Ananya Deshmukh", "female"),
        ("demo@lawgpt.in", "Demo User", "other"),
    ]
    async with AsyncSessionLocal() as db:
        try:
            for email, full_name, gender in demo_profiles:
                res = await db.execute(select(User).where(User.email == email))
                if not res.scalar_one_or_none():
                    pw = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode("utf-8")
                    user = User(
                        email=email,
                        full_name=full_name,
                        hashed_password=pw,
                        gender=gender,
                    )
                    db.add(user)
            await db.commit()
        except Exception:
            await db.rollback()


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
