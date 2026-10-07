"""
PERSISTENT MEMORY SYSTEM — Agentic RAG Memory Layer
=====================================================

Implements 3-tier memory for the Agentic RAG system:

1. SHORT-TERM: Current conversation (in-memory, per session)
2. LONG-TERM: User preferences & past interactions (Supabase)
3. SEMANTIC CACHE: Reuse expensive retrieval + LLM results (hash-based, TTL)

Designed for the LAW-GPT legal assistant — Indian law domain.
"""

import hashlib
import json
import logging
import os
import tempfile
import time
from collections import OrderedDict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class MemoryEntry:
    """Single memory entry (short-term or long-term)."""
    role: str               # 'user' | 'assistant' | 'system'
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserProfile:
    """Long-term user profile built from interactions."""
    user_id: str
    preferred_language: str = "en"
    legal_domains_of_interest: List[str] = field(default_factory=list)
    past_queries_summary: List[str] = field(default_factory=list)  # top-10 compressed
    interaction_count: int = 0
    last_seen: float = field(default_factory=time.time)
    preferences: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheEntry:
    """Semantic cache entry."""
    query_hash: str
    answer: str
    sources: List[Dict]
    created_at: float
    ttl: float              # seconds
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl


# ─── Short-Term Memory ───────────────────────────────────────────────────────

class ShortTermMemory:
    """
    Per-session conversation buffer (in-memory).
    Keeps the most recent `max_turns` exchanges for context injection.
    """

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self._sessions: Dict[str, List[MemoryEntry]] = {}
        self._session_dir = Path(tempfile.gettempdir()) / "lawgpt_short_term_memory"
        self._session_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        safe_id = "".join(ch for ch in session_id if ch.isalnum() or ch in ("-", "_"))
        return self._session_dir / f"{safe_id}.json"

    def _persist_session(self, session_id: str):
        path = self._session_path(session_id)
        payload = [asdict(entry) for entry in self._sessions.get(session_id, [])]
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _load_session(self, session_id: str) -> List[MemoryEntry]:
        if session_id in self._sessions:
            return self._sessions[session_id]

        path = self._session_path(session_id)
        if not path.exists():
            return []

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            messages = [MemoryEntry(**item) for item in data]
            self._sessions[session_id] = messages
            return messages
        except Exception as exc:
            logger.warning(f"[STM] Failed to load session {session_id[:12]}: {exc}")
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            self._sessions.pop(session_id, None)
            return []

    def add(self, session_id: str, role: str, content: str,
            metadata: Optional[Dict] = None):
        messages = self._load_session(session_id)
        messages.append(
            MemoryEntry(role=role, content=content, metadata=metadata or {})
        )
        # Trim to max_turns * 2 messages (user + assistant pairs)
        limit = self.max_turns * 2
        if len(messages) > limit:
            messages = messages[-limit:]
        self._sessions[session_id] = messages
        self._persist_session(session_id)

    def get_context(self, session_id: str, last_n: int = 5) -> str:
        """Return formatted conversation context for prompt injection."""
        msgs = self._load_session(session_id)[-last_n * 2:]
        if not msgs:
            return ""
        parts = []
        for m in msgs:
            label = "User" if m.role == "user" else "Assistant"
            parts.append(f"{label}: {m.content[:500]}")
        return "\n".join(parts)

    def get_messages(self, session_id: str) -> List[MemoryEntry]:
        return self._load_session(session_id)

    def get_last_user_query(self, session_id: str) -> Optional[str]:
        msgs = self._load_session(session_id)
        for m in reversed(msgs):
            if m.role == "user":
                return m.content
        return None

    def clear(self, session_id: str):
        self._sessions.pop(session_id, None)
        try:
            self._session_path(session_id).unlink(missing_ok=True)
        except Exception as exc:
            logger.warning(f"[STM] Failed to clear session {session_id[:12]}: {exc}")

    def session_count(self) -> int:
        return len(self._sessions)


# ─── Long-Term Memory (Supabase backed, graceful fallback) ───────────────────

class LongTermMemory:
    """
    Persistent user memory stored in Supabase.
    Falls back to local JSON file if Supabase is unavailable.
    Stores: user profiles, topic preferences, domain interests.
    """

    TABLE_NAME = "user_memory"

    def __init__(self):
        self._supabase = None
        self._local_profiles: Dict[str, UserProfile] = {}
        self._local_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "user_memory_local.json"
        )
        self._init_supabase()
        if not self._supabase:
            self._load_local()

    def _init_supabase(self):
        try:
            url = os.getenv("SUPABASE_URL")
            key = (
                os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                or os.getenv("SUPABASE_KEY")
                or os.getenv("SUPABASE_ANON_KEY")
            )
            if url and key:
                from supabase import create_client
                self._supabase = create_client(url, key)
                logger.info("[LongTermMemory] Connected to Supabase")
            else:
                logger.info("[LongTermMemory] No Supabase credentials — using local file")
        except Exception as e:
            logger.warning(f"[LongTermMemory] Supabase init failed: {e}. Using local.")

    # ── Profile CRUD ──────────────────────────────────────────────────────

    def get_profile(self, user_id: str) -> UserProfile:
        """Retrieve or create a user profile."""
        if self._supabase:
            try:
                resp = (self._supabase.table(self.TABLE_NAME)
                        .select("*")
                        .eq("user_id", user_id)
                        .execute())
                if resp.data:
                    row = resp.data[0]
                    return UserProfile(
                        user_id=user_id,
                        preferred_language=row.get("preferred_language", "en"),
                        legal_domains_of_interest=json.loads(row.get("domains", "[]")),
                        past_queries_summary=json.loads(row.get("past_queries", "[]")),
                        interaction_count=row.get("interaction_count", 0),
                        last_seen=row.get("last_seen", time.time()),
                        preferences=json.loads(row.get("preferences", "{}")),
                    )
            except Exception as e:
                logger.warning(f"[LTM] Supabase read failed: {e}")

        # Fallback: local
        if user_id in self._local_profiles:
            return self._local_profiles[user_id]

        # New profile
        profile = UserProfile(user_id=user_id)
        self._local_profiles[user_id] = profile
        return profile

    def update_profile(self, profile: UserProfile):
        """Persist updated profile."""
        profile.last_seen = time.time()

        if self._supabase:
            try:
                row = {
                    "user_id": profile.user_id,
                    "preferred_language": profile.preferred_language,
                    "domains": json.dumps(profile.legal_domains_of_interest),
                    "past_queries": json.dumps(profile.past_queries_summary[-20:]),
                    "interaction_count": profile.interaction_count,
                    "last_seen": profile.last_seen,
                    "preferences": json.dumps(profile.preferences),
                }
                self._supabase.table(self.TABLE_NAME).upsert(row).execute()
                return
            except Exception as e:
                logger.warning(f"[LTM] Supabase write failed: {e}")

        # Fallback
        self._local_profiles[profile.user_id] = profile
        self._save_local()

    def record_interaction(self, user_id: str, query: str,
                           detected_domains: List[str]):
        """Update profile after each interaction."""
        profile = self.get_profile(user_id)
        profile.interaction_count += 1

        # Track domain interests
        for d in detected_domains:
            if d and d not in profile.legal_domains_of_interest:
                profile.legal_domains_of_interest.append(d)
        # Cap at 20
        profile.legal_domains_of_interest = profile.legal_domains_of_interest[-20:]

        # Compressed query summary (keep last 20)
        summary = query[:120] if len(query) > 120 else query
        profile.past_queries_summary.append(summary)
        profile.past_queries_summary = profile.past_queries_summary[-20:]

        self.update_profile(profile)

    # ── Local persistence ─────────────────────────────────────────────────

    def _load_local(self):
        try:
            if os.path.exists(self._local_path):
                with open(self._local_path, "r") as f:
                    data = json.load(f)
                for uid, d in data.items():
                    self._local_profiles[uid] = UserProfile(**d)
        except Exception as e:
            logger.warning(f"[LTM] Local load failed: {e}")

    def _save_local(self):
        try:
            data = {uid: asdict(p) for uid, p in self._local_profiles.items()}
            with open(self._local_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"[LTM] Local save failed: {e}")


# ─── Semantic Cache ──────────────────────────────────────────────────────────

class SemanticCache:
    """
    Query-level answer cache.
    Uses MD5 hash of normalised query as key.
    Avoids re-running expensive retrieval + LLM generation for repeated / similar queries.
    """

    DEFAULT_TTL = 3600  # 1 hour

    def __init__(self, max_entries: int = 500, default_ttl: float = DEFAULT_TTL):
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = {"hits": 0, "misses": 0}

    @staticmethod
    def _normalise_query(query: str) -> str:
        import re
        q = query.lower().strip()
        q = re.sub(r"[^\w\s]", "", q)
        q = " ".join(q.split())
        return q

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    def get(self, query: str) -> Optional[CacheEntry]:
        """Look up cache. Returns None on miss or expiry."""
        norm = self._normalise_query(query)
        h = self._hash(norm)
        entry = self._cache.get(h)
        if entry is None:
            self._stats["misses"] += 1
            return None
        if entry.is_expired:
            del self._cache[h]
            self._stats["misses"] += 1
            return None
        entry.hit_count += 1
        self._stats["hits"] += 1
        self._cache.move_to_end(h)
        return entry

    def put(self, query: str, answer: str, sources: List[Dict],
            ttl: Optional[float] = None):
        """Store answer in cache."""
        norm = self._normalise_query(query)
        h = self._hash(norm)
        self._cache[h] = CacheEntry(
            query_hash=h,
            answer=answer,
            sources=sources,
            created_at=time.time(),
            ttl=ttl or self.default_ttl,
        )
        # Evict oldest if over capacity
        while len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)

    def invalidate(self, query: str):
        norm = self._normalise_query(query)
        h = self._hash(norm)
        self._cache.pop(h, None)

    def clear(self):
        self._cache.clear()

    @property
    def stats(self) -> Dict[str, int]:
        total = self._stats["hits"] + self._stats["misses"]
        return {
            **self._stats,
            "total": total,
            "hit_rate": round(self._stats["hits"] / total, 3) if total else 0.0,
            "size": len(self._cache),
        }


# ─── Unified Memory Manager ─────────────────────────────────────────────────

class AgenticMemoryManager:
    """
    Unified facade over the 3-tier memory system.
    Used by the Agentic RAG Engine.
    """

    def __init__(self):
        self.short_term = ShortTermMemory(max_turns=10)
        self.long_term = LongTermMemory()
        self.cache = SemanticCache(max_entries=500, default_ttl=3600)
        logger.info("[AgenticMemoryManager] 3-tier memory initialised")

    # ── Convenience wrappers ──────────────────────────────────────────────

    def remember_turn(self, session_id: str, role: str, content: str,
                      metadata: Optional[Dict] = None):
        """Record a conversation turn in short-term memory."""
        self.short_term.add(session_id, role, content, metadata)

    def get_conversation_context(self, session_id: str, last_n: int = 5) -> str:
        return self.short_term.get_context(session_id, last_n)

    def get_messages(self, session_id: str) -> List[MemoryEntry]:
        return self.short_term.get_messages(session_id)

    def check_cache(self, query: str) -> Optional[CacheEntry]:
        return self.cache.get(query)

    def cache_response(self, query: str, answer: str, sources: List[Dict]):
        self.cache.put(query, answer, sources)

    def update_user_profile(self, user_id: str, query: str,
                            domains: List[str]):
        self.long_term.record_interaction(user_id, query, domains)

    def get_user_profile(self, user_id: str) -> UserProfile:
        return self.long_term.get_profile(user_id)

    def get_memory_stats(self) -> Dict[str, Any]:
        return {
            "short_term_sessions": self.short_term.session_count(),
            "cache": self.cache.stats,
            # G8: the caller reads a FLAT `cache_hit_rate` off this dict, but only
            # ever got the nested `cache` sub-dict, so `.get('cache_hit_rate')`
            # always missed and /api/metrics reported a hard 0.0 no matter how
            # well the cache performed (measured: 13 hits / 16 misses reported as
            # 0.0). Expose the flat keys the metrics endpoint actually reads.
            "cache_hit_rate": self.cache.stats.get("hit_rate", 0.0),
            "cache_hits": self.cache.stats.get("hits", 0),
            "cache_misses": self.cache.stats.get("misses", 0),
            "cache_size": self.cache.stats.get("size", 0),
        }

    def clear_session(self, session_id: str):
        """Clear short-term memory for a session."""
        self.short_term.clear(session_id)
