"""
AGENTIC RAG ENGINE — Next-Generation Legal AI (2025-2026 Era)
==============================================================

Transforms LAW-GPT from a linear retrieve→generate pipeline into a
dynamic, goal-oriented **agentic loop** controlled by an LLM agent.

Architecture Overview:
┌─────────────────────────────────────────────────────────┐
│                   AGENTIC RAG ENGINE                     │
│                                                          │
│  User Query                                              │
│     │                                                    │
│     ▼                                                    │
│  ┌────────────┐    ┌───────────┐    ┌──────────────┐    │
│  │ 1. PLANNER │───►│ 2. ROUTER │───►│ 3. RETRIEVER │    │
│  │ (Decompose)│    │ (Strategy)│    │ (Multi-hop)  │    │
│  └────────────┘    └───────────┘    └──────┬───────┘    │
│                                            │             │
│     ┌─────────────┐    ┌──────────┐        ▼             │
│     │ 5. VERIFIER │◄───│ 4. SYNTH │◄── Contexts         │
│     │ (Reflect)   │    │ (Answer) │                      │
│     └──────┬──────┘    └──────────┘                      │
│            │                                             │
│       PASS?─── NO ──► Loop back to PLANNER (max 2)      │
│            │                                             │
│           YES                                            │
│            ▼                                             │
│      Final Answer + Sources + Reasoning Trace            │
│                                                          │
│  Memory: ShortTerm ←→ LongTerm ←→ SemanticCache         │
└─────────────────────────────────────────────────────────┘

Core Capabilities (maps to Agentic RAG concepts):
1. Planning & Decomposition — break complex queries into sub-tasks
2. Query Rewriting & Routing — rewrite poor queries, pick optimal strategy
3. Iterative Multi-hop Retrieval — retrieve → evaluate → re-retrieve
4. Tool Use — RAG + web search + statute lookup + calculator
5. Reflection & Self-Critique — verify answer quality before returning
6. Persistent Memory — short-term + long-term + semantic cache
7. Dynamic Workflow Orchestration — agent decides flow per query
"""

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from config.config import Config

logger = logging.getLogger(__name__)

# Maximum number of reflection loops before returning best answer
MAX_AGENT_LOOPS = 2
# Confidence threshold: if verifier scores >= this, stop looping
CONFIDENCE_THRESHOLD = 0.75
SUBQUERY_COVERAGE_THRESHOLD = 0.80
# Escape hatch for local debugging of the critic loop. When enabled, the verifier's
# internal suggestions are copied into plan.sub_queries (they then show up in rendered
# output). Production MUST leave this False: the suggestions are critic instructions,
# not user-facing prose, and shipping them produced answers that opened with
# "Sub-Question 1: Regenerate with a complete grounded answer...".
_DEBUG_EXPOSE_CRITIC_SUGGESTIONS = str(
    os.getenv("AGENTIC_EXPOSE_CRITIC_SUGGESTIONS", "") or ""
).strip().lower() in ("1", "true", "yes", "on")
SUBQUERY_STOPWORDS = {
    "about", "above", "after", "against", "under", "which", "would", "there",
    "their", "shall", "should", "could", "these", "those", "where", "when",
    "while", "does", "what", "with", "from", "into", "your", "have", "has",
    "this", "that", "they", "them", "than", "then", "also", "been", "being",
    "were", "will", "only", "such", "same", "even", "more", "most", "very",
    "whether", "within", "across", "between", "question", "sub", "part",
}


def _is_stub_answer(answer: str, error_phrases: Tuple[str, ...]) -> bool:
    text = (answer or "").strip().lower()
    if not text:
        return True
    if any(phrase in text for phrase in error_phrases):
        return True
    return len(text.split()) < 40


# ─── Data Types ──────────────────────────────────────────────────────────────

@dataclass
class AgentPlan:
    """Output of the Planner stage."""
    original_query: str
    rewritten_query: str
    sub_queries: List[str]
    strategy: str            # 'simple' | 'multi_hop' | 'research' | 'statute_lookup'
    detected_domains: List[str]
    complexity: str          # 'low' | 'medium' | 'high'
    needs_web_search: bool
    reasoning: str


@dataclass
class RetrievalPacket:
    """Output of one retrieval pass."""
    documents: List[Dict]
    context_text: str
    source_labels: List[str]
    retrieval_method: str
    retrieval_time: float


@dataclass
class VerificationResult:
    """Output of the Verifier / Reflection stage."""
    is_acceptable: bool
    confidence: float        # 0.0 – 1.0
    issues: List[str]
    suggestions: str         # what to improve if looping
    reasoning: str


@dataclass
class AgenticResult:
    """Final output of the Agentic RAG Engine."""
    answer: str
    sources: List[Dict]
    reasoning_trace: List[str]
    confidence: float
    loops_taken: int
    plan: Optional[AgentPlan]
    total_time: float
    from_cache: bool
    memory_context_used: bool


# ─── Agentic RAG Engine ─────────────────────────────────────────────────────

class AgenticRAGEngine:
    """
    The brain of the Agentic RAG system.
    Orchestrates planning, retrieval, synthesis, and reflection.
    """

    def __init__(self, *, client_manager, parametric_rag, retriever,
                 memory_manager, hirag=None, researcher=None,
                 pageindex_retriever=None):
        """
        Args:
            client_manager: GroqClientManager (key-rotating LLM proxy)
            parametric_rag: ParametricRAGSystem (handles advanced retrieval)
            retriever: EnhancedRetriever (direct search)
            memory_manager: AgenticMemoryManager (3-tier memory)
            hirag: HierarchicalThoughtRAG (optional, used for synthesis)
            researcher: DeepResearchAgent (optional, for web search fallback)
            pageindex_retriever: PageIndexRetriever (optional, vectorless
                                 tree-based statute retrieval)
        """
        self.llm = client_manager
        self.parametric_rag = parametric_rag
        self.retriever = retriever
        self.memory = memory_manager
        self.hirag = hirag
        self.researcher = researcher
        self.pageindex_retriever = pageindex_retriever
        self.model = Config.MAIN_LLM_MODEL
        pi_status = "enabled" if (pageindex_retriever and getattr(pageindex_retriever, "is_available", False)) else "disabled"
        logger.info(f"[AgenticRAGEngine] Initialised with all components (PageIndex: {pi_status})")

    # ═══════════════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════

    def run(self, user_query: str, *,
            session_id: str = "",
            user_id: str = "",
            category: str = "general",
            chat_history: Optional[List[Dict]] = None,
            simple_mode: bool = False,
            statute_filter: Optional[str] = None,
            suggested_sections: Optional[List[str]] = None,
            ) -> AgenticResult:
        """
        Main entry point. Runs the full agentic loop.

        Args:
            simple_mode: When True, skip Plan→Verify loop and use a lightweight
                         single-pass retrieval+synthesis. Used for simple factual
                         queries to avoid rate-limiting the 70b model.
        """
        t0 = time.time()
        trace: List[str] = []

        # ── 0. MEMORY: record user turn & check cache ────────────────────
        if session_id:
            self.memory.remember_turn(session_id, "user", user_query)

        # Error phrases that indicate a stale/failed cached response
        _ERROR_PHRASES = (
            "unable to generate", "service issue", "please try again",
            "technical difficulty", "try again later", "error occurred",
            "i encountered an error", "failed to retrieve",
        )

        cached = self.memory.check_cache(user_query)
        if cached:
            _is_stale = (
                len(cached.answer.split()) < 50
                or any(p in cached.answer.lower() for p in _ERROR_PHRASES)
            )
            if _is_stale:
                # Evict the bad cached entry by overwriting with None (or just skip)
                logger.warning("[AGENT] Cached answer is a stub/error — skipping cache")
            else:
                trace.append("cache_hit")
                logger.info("[AGENT] Cache hit — returning cached answer")
                return AgenticResult(
                    answer=cached.answer, sources=cached.sources,
                    reasoning_trace=trace, confidence=0.95,
                    loops_taken=0, plan=None,
                    total_time=time.time() - t0, from_cache=True,
                    memory_context_used=False,
                )

        # ── Conversation context from short-term memory ──────────────────
        conv_context = ""
        if session_id:
            conv_context = self.memory.get_conversation_context(session_id)

        # ── User profile from long-term memory ───────────────────────────
        user_profile = None
        if user_id:
            user_profile = self.memory.get_user_profile(user_id)

        # ── SIMPLE MODE: lightweight single-pass for factual queries ─────
        if simple_mode:
            trace.append("simple_mode")
            try:
                simple_result, simple_source_docs = self._simple_mode_answer(
                    user_query,
                    category,
                    session_id,
                    statute_filter=statute_filter,
                    suggested_sections=suggested_sections,
                )
                if simple_result and len(simple_result.split()) >= 40:
                    formatted_sources = self._format_sources(simple_source_docs)
                    if session_id:
                        self.memory.remember_turn(session_id, "assistant", simple_result[:500])
                    if len(simple_result.split()) >= 50 and formatted_sources:
                        self.memory.cache_response(user_query, simple_result, formatted_sources)
                    return AgenticResult(
                        answer=simple_result, sources=formatted_sources,
                        reasoning_trace=trace + ["simple_direct_answer"],
                        confidence=0.80, loops_taken=1, plan=None,
                        total_time=time.time() - t0, from_cache=False,
                        memory_context_used=bool(conv_context),
                    )
            except Exception as e:
                logger.warning(f"[AGENT] Simple mode failed: {e} — falling back to full agentic loop")
            # Fall through to full agentic loop if simple mode fails

        # ── 1. PLAN ──────────────────────────────────────────────────────
        trace.append("planning")
        if "FINAL LEGAL ANALYSIS REQUEST AFTER CLARIFICATION LOOP" in (user_query or ""):
            plan = AgentPlan(
                original_query=user_query,
                rewritten_query=user_query,
                sub_queries=[],
                strategy="multi_hop",
                detected_domains=[
                    "Constitutional Law",
                    "Criminal Law",
                    "Family Law",
                    "Evidence Law",
                ],
                complexity="high",
                needs_web_search=False,
                reasoning="Post-clarification final answer; preserve exact scenario and assumptions.",
            )
            trace.append("clarified_final_plan")
        else:
            plan = self._plan(user_query, conv_context, user_profile, category)
        trace.append(f"strategy={plan.strategy}")
        trace.append(f"sub_queries={len(plan.sub_queries)}")
        logger.info(f"[AGENT] Plan: strategy={plan.strategy}, "
                     f"complexity={plan.complexity}, subs={len(plan.sub_queries)}")

        # ── AGENTIC LOOP ─────────────────────────────────────────────────
        best_answer = ""
        best_sources: List[Dict] = []
        best_confidence = 0.0
        loops_taken = 0

        for loop_idx in range(MAX_AGENT_LOOPS + 1):
            loops_taken = loop_idx + 1
            trace.append(f"loop_{loop_idx}")

            # ── 2. RETRIEVE ──────────────────────────────────────────────
            retrieval = self._retrieve(plan, conv_context)
            trace.append(f"retrieved_{len(retrieval.documents)}_docs")

            # Merge web research if plan says so
            web_context = ""
            if plan.needs_web_search and self.researcher:
                try:
                    trace.append("web_search")
                    web_context = self.researcher.conduct_research(
                        plan.rewritten_query
                    )
                    logger.info(f"[AGENT] Web research returned {len(web_context)} chars")
                except Exception as e:
                    logger.warning(f"[AGENT] Web research failed: {e}")

            # ── 3. SYNTHESISE ────────────────────────────────────────────
            full_context = retrieval.context_text
            if web_context:
                full_context += "\n\n--- Web Research ---\n" + web_context[:2000]

            answer = self._synthesise(
                plan, full_context, conv_context, user_profile
            )
            trace.append("synthesised")

            # ── 4. VERIFY / REFLECT ──────────────────────────────────────
            if _is_stub_answer(answer, _ERROR_PHRASES):
                trace.append("stub_answer_detected")
                verification = VerificationResult(
                    is_acceptable=False,
                    confidence=0.0,
                    issues=["stub_or_empty_answer"],
                    suggestions="Regenerate with a complete grounded answer and preserve the required legal structure.",
                    reasoning="Synthesiser returned an empty or service-stub answer.",
                )
            else:
                verification = self._verify(
                    user_query, answer, full_context, plan
                )
            trace.append(f"confidence={verification.confidence:.2f}")
            logger.info(f"[AGENT] Loop {loop_idx}: confidence={verification.confidence:.2f}, "
                        f"acceptable={verification.is_acceptable}")

            # Track best
            if verification.confidence > best_confidence:
                best_answer = answer
                best_sources = self._format_sources(retrieval.documents)
                best_confidence = verification.confidence

            if verification.is_acceptable:
                trace.append("accepted")
                break

            # ── NOT ACCEPTABLE → ADAPT PLAN ──────────────────────────────
            if loop_idx < MAX_AGENT_LOOPS:
                trace.append(f"refining: {verification.suggestions[:60]}")
                plan = self._refine_plan(plan, verification)
            else:
                trace.append("max_loops_reached_returning_best")

        # ── 5. POST-PROCESS: Memory updates ──────────────────────────────
        if session_id:
            self.memory.remember_turn(session_id, "assistant", best_answer[:1000])
        if user_id and plan:
            self.memory.update_user_profile(
                user_id, user_query, plan.detected_domains
            )
        # Cache the response — only if answer is substantive (skip error stubs)
        _is_error_answer = any(p in best_answer.lower() for p in _ERROR_PHRASES)
        if not _is_error_answer and len(best_answer.split()) >= 50:
            self.memory.cache_response(user_query, best_answer, best_sources)

        total_time = time.time() - t0
        logger.info(f"[AGENT] Done in {total_time:.1f}s, {loops_taken} loop(s), "
                     f"confidence={best_confidence:.2f}")

        return AgenticResult(
            answer=best_answer,
            sources=best_sources,
            reasoning_trace=trace,
            confidence=best_confidence,
            loops_taken=loops_taken,
            plan=plan,
            total_time=total_time,
            from_cache=False,
            memory_context_used=bool(conv_context),
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  SIMPLE MODE: fast single-pass answer for factual queries
    # ═══════════════════════════════════════════════════════════════════════

    def _simple_mode_answer(
        self,
        query: str,
        category: str,
        session_id: str = "",
        statute_filter: Optional[str] = None,
        suggested_sections: Optional[List[str]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """One-shot lightweight answer: retrieve → synthesise with 8b model.

        Uses free BM25 corpus + parametric RAG + Laya System 1 context pruning
        and fast LLM synthesis.
        """
        recent_context = ""
        retrieval_query = query
        if session_id:
            recent_messages = self.memory.get_messages(session_id)
            previous_user_queries = [
                msg.content for msg in recent_messages[:-1]
                if msg.role == "user" and msg.content.strip()
            ]
            previous_assistant_turns = [
                msg.content for msg in recent_messages[:-1]
                if msg.role == "assistant" and msg.content.strip()
            ]
            if previous_user_queries or previous_assistant_turns:
                recent_parts = []
                if previous_user_queries:
                    recent_parts.append(f"Previous user question: {previous_user_queries[-1]}")
                if previous_assistant_turns:
                    recent_parts.append(f"Previous assistant answer: {previous_assistant_turns[-1][:500]}")
                recent_context = "\n".join(recent_parts)

            is_follow_up = bool(re.search(
                r"\b(it|its|that|this|they|them|those|these|there|here)\b|\bunder\s+it\b|\bfor\s+it\b",
                query.lower(),
            ))
            if is_follow_up and recent_context:
                retrieval_query = f"{recent_context}\nFollow-up question: {query}"

        # Retrieve relevant context
        source_docs: List[Dict[str, Any]] = []
        context = ""

        # ── 1. Free Corpus BM25 & Laya System 1 Acceleration ──────────────────
        try:
            from system_adapters.laya_triage_adapter import (
                triage_query,
                expand_legal_query,
                prune_retrieved_chunks,
            )
            from system_adapters.vectorless_bm25_store import get_global_bm25_store

            triage_info = None
            if not statute_filter or not suggested_sections:
                triage_info = triage_query(query)
                if not statute_filter and triage_info.get("is_supported_statute"):
                    statute_filter = triage_info.get("statute")
                if not suggested_sections:
                    suggested_sections = triage_info.get("suggested_sections") or []
            else:
                triage_info = {
                    "statute": statute_filter,
                    "suggested_sections": suggested_sections,
                    "domain": category,
                    "is_supported_statute": True,
                }

            expanded_search_query = expand_legal_query(retrieval_query, triage_info)
            bm25_store = get_global_bm25_store()
            bm25_chunks = bm25_store.retrieve(
                expanded_search_query,
                top_k=8,
                act_filter=statute_filter,
                section_filter=suggested_sections,
            )
            pruned_bm25 = prune_retrieved_chunks(bm25_chunks, triage_info, max_tokens=2500)
            if pruned_bm25:
                bm25_parts = []
                for pdoc in pruned_bm25:
                    p_text = str(pdoc.get("text") or pdoc.get("content") or "").strip()
                    p_meta = pdoc.get("metadata") if isinstance(pdoc.get("metadata"), dict) else {}
                    p_act = p_meta.get("act") or pdoc.get("act") or "Statute"
                    p_sec = p_meta.get("section_number") or pdoc.get("section_number") or ""
                    p_title = f"{p_act} {p_sec}".strip() if p_sec else p_act

                    doc_entry = {
                        "title": p_title,
                        "content": p_text,
                        "text": p_text,
                        "source": pdoc.get("source") or "statute_chunks.json",
                        "score": pdoc.get("score", 1.0),
                        "metadata": {
                            "act": p_act,
                            "section_number": p_sec,
                            "domain": p_meta.get("domain") or "statutes",
                            "trusted_source": True,
                            "source_tier": "trusted",
                        },
                    }
                    source_docs.append(doc_entry)
                    bm25_parts.append(f"[{p_title}]\n{p_text}")

                if bm25_parts:
                    context = "\n\n---\n\n".join(bm25_parts)
                    logger.info(f"[SIMPLE] Free BM25 corpus supplied {len(pruned_bm25)} high-precision chunks.")
        except Exception as _bm25_err:
            logger.warning(f"[SIMPLE] BM25 free corpus retrieval error: {_bm25_err}")

        # ── 2. Secondary/Fallback Parametric RAG Retrieval ────────────────────
        try:
            if not source_docs:
                rag_params = {
                    "search_domain": category,
                    "complexity": "simple",
                    "keywords": retrieval_query.split()[:12],
                }
                retrieval = self.parametric_rag.retrieve_with_params(retrieval_query, rag_params)
                sec_context = retrieval.get("context", "")[:3000]
                sec_docs = retrieval.get("documents", []) if isinstance(retrieval, dict) else []
                if sec_docs:
                    source_docs.extend(sec_docs)
                    context = (context + "\n\n" + sec_context).strip() if context else sec_context

            # Guardrail: if primary retrieval returns context but no structured docs,
            # attempt fallback retrieval so grounding has concrete evidence records.
            if not source_docs and self.retriever is not None:
                fallback_results = self.retriever.retrieve(
                    retrieval_query,
                    top_k=6,
                    allow_live_search=False,
                )
                source_docs = fallback_results or []
                if not context and source_docs:
                    fallback_parts: List[str] = []
                    for doc in source_docs[:4]:
                        title = doc.get("title") or doc.get("id") or "Legal Document"
                        content = str(doc.get("content") or doc.get("text") or "")[:500]
                        if content:
                            fallback_parts.append(f"[{title}]\n{content}")
                    context = "\n\n".join(fallback_parts)[:3000]
        except Exception as e:
            logger.warning(f"[SIMPLE] Parametric retrieval fallback skipped: {e}")

        system_msg = (
            "You are a concise Indian law assistant. Answer the question accurately in 150-350 words. "
            "Cite the specific section/article number and act. Mention 1-2 key cases if relevant. "
            "End with a one-line ⚠️ Disclaimer that this is general information only."
        )
        user_msg = (
            f"Question: {query}\n\n"
            + (f"Recent conversation context:\n{recent_context}\n\n" if recent_context else "")
            + (f"Retrieved legal context:\n{context}\n\n" if context else "")
            + "If the question refers to an earlier topic using words like 'it' or 'that', stay grounded in that earlier legal topic unless the user changes topic explicitly. Answer concisely."
        )
        # Use fast model directly — quick, generous TPM limit
        resp = self.llm.chat.completions.create(
            model=Config.FAST_LLM_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.15,
            max_tokens=700,
        )
        return (resp.choices[0].message.content or "").strip(), source_docs[:8]

    # ═══════════════════════════════════════════════════════════════════════
    #  STAGE 1: PLANNER — decompose + route + rewrite
    # ═══════════════════════════════════════════════════════════════════════

    def _plan(self, query: str, conv_context: str,
              user_profile: Optional[Any], category: str) -> AgentPlan:
        """
        LLM-powered planner that analyses the query and decides strategy.
        """
        profile_hint = ""
        if user_profile and user_profile.legal_domains_of_interest:
            profile_hint = (
                f"User's areas of interest: {', '.join(user_profile.legal_domains_of_interest[:5])}. "
                f"Interaction count: {user_profile.interaction_count}."
            )

        conv_hint = ""
        if conv_context:
            conv_hint = f"Recent conversation:\n{conv_context[-500:]}\n"

        system_msg = (
            "You are a legal query PLANNER for an Indian law AI system. "
            "Analyse the user query and output a JSON plan.\n\n"
            "Output ONLY valid JSON with these fields:\n"
            "{\n"
            '  "rewritten_query": "<improved, unambiguous version of the query>",\n'
            '  "sub_queries": ["<sub-question 1>", ...],  // empty if simple\n'
            '  "strategy": "<one of: simple | multi_hop | research | statute_lookup>",\n'
            '  "detected_domains": ["<legal domain 1>", ...],\n'
            '  "complexity": "<low | medium | high>",\n'
            '  "needs_web_search": true/false,\n'
            '  "reasoning": "<1-2 sentence explanation>"\n'
            "}\n\n"
            "Strategy guide:\n"
            "- simple: factual / single-section lookup (Section 302 BNS, etc.)\n"
            "- statute_lookup: requires precise statute section text\n"
            "- multi_hop: needs information from multiple sources / acts / cases\n"
            "- research: broad / comparative / opinion / recent developments\n\n"
            "Rewrite ambiguous queries to be specific to Indian law.\n"
            "Detect all relevant legal domains (IPC/BNS, CrPC/BNSS, CPA, GST, IT Act, etc.).\n"
            "Set needs_web_search=true only for very recent events or topics not in law databases."
        )

        user_msg = f"{conv_hint}{profile_hint}\nUser query: {query}\nCategory hint: {category}"

        try:
            resp = self._llm_call(system_msg, user_msg, temperature=0.1, max_tokens=600)
            data = self._parse_json(resp)
            plan = AgentPlan(
                original_query=query,
                rewritten_query=data.get("rewritten_query", query),
                sub_queries=data.get("sub_queries", []),
                strategy=data.get("strategy", "simple"),
                detected_domains=data.get("detected_domains", [category]),
                complexity=data.get("complexity", "medium"),
                needs_web_search=data.get("needs_web_search", False),
                reasoning=data.get("reasoning", ""),
            )
            return self._post_process_plan(plan, query)
        except Exception as e:
            logger.warning(f"[PLANNER] LLM planner failed: {e}. Using rule-based fallback.")
            return self._post_process_plan(self._rule_based_plan(query, category), query)

    def _rule_based_plan(self, query: str, category: str) -> AgentPlan:
        """Fallback planner using regex heuristics."""
        q_lower = query.lower()
        strategy = "simple"
        complexity = "low"
        needs_web = False
        sub_queries = []
        domains = [category] if category != "general" else []

        # Detect domains
        domain_map = {
            "ipc": "IPC", "bns": "BNS", "crpc": "CrPC", "bnss": "BNSS",
            "consumer": "Consumer Protection", "gst": "GST", "income tax": "Income Tax",
            "dpdp": "DPDPA", "property": "Property Law", "family": "Family Law",
            "constitution": "Constitutional Law", "contract": "Contract Act",
            "motor vehicle": "Motor Vehicle Act", "arbitration": "Arbitration Act",
        }
        for keyword, domain in domain_map.items():
            if keyword in q_lower and domain not in domains:
                domains.append(domain)

        # Strategy detection
        word_count = len(query.split())
        if word_count > 25 or " and " in q_lower:
            strategy = "multi_hop"
            complexity = "high"
        elif any(k in q_lower for k in ["section", "article", "rule"]):
            strategy = "statute_lookup"
            complexity = "low"
        elif any(k in q_lower for k in ["compare", "difference", "vs", "versus"]):
            strategy = "multi_hop"
            complexity = "medium"
        elif any(k in q_lower for k in ["latest", "recent", "2025", "2026", "new law"]):
            strategy = "research"
            needs_web = True
            complexity = "medium"

        return AgentPlan(
            original_query=query,
            rewritten_query=query,
            sub_queries=sub_queries,
            strategy=strategy,
            detected_domains=domains or ["general"],
            complexity=complexity,
            needs_web_search=needs_web,
            reasoning="rule-based fallback plan",
        )

    def _extract_explicit_subquestions(self, query: str) -> List[str]:
        """Extract explicit numbered/sub-question prompts from user input."""
        if not query:
            return []

        extracted: List[str] = []
        seen = set()

        numbered_pattern = re.compile(
            r"(?:sub[-\s]?question|question|q)\s*(\d{1,2})\s*[:.)\-]\s*(.+?)(?=(?:\n|(?:sub[-\s]?question|question|q)\s*\d{1,2}\s*[:.)\-])|$)",
            re.IGNORECASE | re.DOTALL,
        )
        for match in numbered_pattern.finditer(query):
            text = " ".join(match.group(2).split())
            if len(text) < 8:
                continue
            key = text.lower()
            if key not in seen:
                seen.add(key)
                extracted.append(text)

        if extracted:
            return extracted

        for raw_line in query.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            m = re.match(r"^(\d{1,2})\s*[:.)\-]\s*(.+)$", line)
            if not m:
                continue
            text = " ".join(m.group(2).split())
            if len(text) < 8:
                continue
            key = text.lower()
            if key not in seen:
                seen.add(key)
                extracted.append(text)

        return extracted

    def _post_process_plan(self, plan: AgentPlan, query: str) -> AgentPlan:
        """Apply deterministic planner corrections for legal QA quality."""
        explicit_sub_queries = self._extract_explicit_subquestions(query)
        if explicit_sub_queries and len(explicit_sub_queries) > len(plan.sub_queries or []):
            plan.sub_queries = explicit_sub_queries
            if plan.strategy == "simple":
                plan.strategy = "multi_hop"
            if plan.complexity == "low":
                plan.complexity = "high"

        q_lower = (query or "").lower()
        freshness_triggers = (
            "latest", "recent", "2024", "2025", "2026",
            "electoral bond", "vombatkere", "section 124a", "sedition",
        )
        if any(trigger in q_lower for trigger in freshness_triggers):
            plan.needs_web_search = True

        criminal_transition_terms = ("ipc", "crpc", "evidence act", "bns", "bnss", "bsa")
        if any(term in q_lower for term in criminal_transition_terms):
            if "Criminal Law" not in plan.detected_domains:
                plan.detected_domains.append("Criminal Law")
            if plan.strategy == "simple":
                plan.strategy = "multi_hop"

        return plan

    # ═══════════════════════════════════════════════════════════════════════
    #  STAGE 2: RETRIEVER — multi-hop, sub-query expansion
    # ═══════════════════════════════════════════════════════════════════════

    def _retrieve(self, plan: AgentPlan, conv_context: str) -> RetrievalPacket:
        """Execute retrieval based on plan strategy."""
        t0 = time.time()
        all_docs: List[Dict] = []
        primary_docs: List[Dict] = []

        # Primary retrieval
        rag_params = {
            "search_domain": plan.detected_domains[0] if plan.detected_domains else "general",
            "complexity": plan.complexity,
            "keywords": plan.rewritten_query.split()[:5],
        }

        try:
            primary = self.parametric_rag.retrieve_with_params(
                plan.rewritten_query, rag_params
            )
            primary_docs = primary.get("documents", []) if isinstance(primary, dict) else []
            all_docs.extend(primary_docs)
        except Exception as e:
            logger.warning(f"[RETRIEVER] Primary retrieval failed: {e}")

        # Fallback retrieval path when parametric retrieval is sparse/empty.
        if not primary_docs and self.retriever is not None:
            try:
                fallback_docs = self.retriever.retrieve(
                    plan.rewritten_query,
                    top_k=8,
                    allow_live_search=plan.needs_web_search,
                )
                for doc in fallback_docs or []:
                    normalized = dict(doc)
                    metadata = normalized.get("metadata") if isinstance(normalized.get("metadata"), dict) else {}
                    if not normalized.get("content"):
                        normalized["content"] = str(normalized.get("text") or "")
                    if not normalized.get("title"):
                        normalized["title"] = (
                            metadata.get("title")
                            or normalized.get("id")
                            or "Legal Document"
                        )
                    if not normalized.get("source"):
                        normalized["source"] = metadata.get("source", "Legal Database")
                    all_docs.append(normalized)
                if fallback_docs:
                    logger.info(f"[RETRIEVER] Fallback retriever supplied {len(fallback_docs)} docs")
            except Exception as fallback_exc:
                logger.warning(f"[RETRIEVER] Fallback retrieval failed: {fallback_exc}")

        # Sub-query retrieval (multi-hop)
        if plan.strategy in ("multi_hop", "research") and plan.sub_queries:
            for sq in plan.sub_queries[:3]:  # cap at 3 sub-queries
                try:
                    sq_params = {**rag_params, "keywords": sq.split()[:5]}
                    sq_result = self.parametric_rag.retrieve_with_params(sq, sq_params)
                    sq_docs = sq_result.get("documents", [])
                    all_docs.extend(sq_docs)
                except Exception as e:
                    logger.warning(f"[RETRIEVER] Sub-query retrieval failed: {e}")

        # Free Corpus BM25 backfill for agentic planning & multi-hop
        if len(all_docs) < 4:
            try:
                from system_adapters.vectorless_bm25_store import get_global_bm25_store
                from system_adapters.laya_triage_adapter import (
                    triage_query,
                    expand_legal_query,
                    prune_retrieved_chunks,
                )
                triage_info = triage_query(plan.rewritten_query or plan.original_query)
                stat_filter = triage_info.get("statute") if triage_info.get("is_supported_statute") else None
                s_sections = triage_info.get("suggested_sections") or []
                exp_query = expand_legal_query(plan.rewritten_query or plan.original_query, triage_info)
                bm25_store = get_global_bm25_store()
                bm25_res = bm25_store.retrieve(
                    exp_query,
                    top_k=8,
                    act_filter=stat_filter,
                    section_filter=s_sections,
                )
                pruned_bm25 = prune_retrieved_chunks(bm25_res, triage_info, max_tokens=2500)
                for pdoc in pruned_bm25:
                    p_text = str(pdoc.get("text") or pdoc.get("content") or "").strip()
                    p_meta = pdoc.get("metadata") if isinstance(pdoc.get("metadata"), dict) else {}
                    p_act = p_meta.get("act") or pdoc.get("act") or "Statute"
                    p_sec = p_meta.get("section_number") or pdoc.get("section_number") or ""
                    p_title = f"{p_act} {p_sec}".strip() if p_sec else p_act
                    doc_entry = {
                        "title": p_title,
                        "content": p_text,
                        "text": p_text,
                        "source": pdoc.get("source") or "statute_chunks.json",
                        "score": pdoc.get("score", 1.0),
                        "metadata": {
                            "act": p_act,
                            "section_number": p_sec,
                            "domain": p_meta.get("domain") or "statutes",
                            "trusted_source": True,
                            "source_tier": "trusted",
                        },
                    }
                    all_docs.append(doc_entry)
            except Exception as _fc_err:
                logger.warning(f"[RETRIEVER] Free BM25 corpus backfill error: {_fc_err}")

        # Deduplicate by content hash
        seen = set()
        unique_docs = []
        for doc in all_docs:
            content = str(doc.get("content", doc.get("text", "")))[:200]
            h = hash(content)
            if h not in seen:
                seen.add(h)
                unique_docs.append(doc)

        # Build context string
        context_parts = []
        source_labels = []
        for i, doc in enumerate(unique_docs[:12]):  # cap at 12 docs
            title = doc.get("title", doc.get("id", f"Document {i+1}"))
            content = str(doc.get("content", doc.get("text", "")))[:600]
            source = doc.get("source", "Legal Database")
            context_parts.append(f"[Document {i+1}: {title}]\n{content}\n")
            source_labels.append(f"{title} ({source})")

        retrieval_time = time.time() - t0
        vector_context = "\n".join(context_parts)

        # ── PageIndex Statute Retrieval (vectorless tree-based reasoning) ──────────
        # Activated when: plan.strategy == 'statute_lookup', OR statutory
        # keywords detected in the query (e.g. "Section 302 BNS").
        pi_context = ""
        try:
            from kaanoon_test.system_adapters.pageindex_retriever import PageIndexRetriever  # noqa
            pi = self.pageindex_retriever
            if pi and getattr(pi, "is_available", False):
                should_activate = (
                    plan.strategy == "statute_lookup"
                    or PageIndexRetriever.should_activate(plan.rewritten_query)
                )
                if should_activate:
                    logger.info("[RETRIEVER] PageIndex activated for statute lookup")
                    pi_context = pi.retrieve(plan.rewritten_query)
                    if pi_context:
                        logger.info(f"[RETRIEVER] PageIndex returned {len(pi_context)} chars")
        except Exception as _pi_exc:
            logger.warning(f"[RETRIEVER] PageIndex retrieval failed (non-fatal): {_pi_exc}")

        # Merge: PageIndex (higher precision) prepended before vector context
        if pi_context:
            merged_context = pi_context + "\n\n[VECTOR DB RETRIEVAL]\n" + vector_context
        else:
            merged_context = vector_context

        return RetrievalPacket(
            documents=unique_docs[:12],
            context_text=merged_context,
            source_labels=source_labels,
            retrieval_method=f"{plan.strategy}{'_+pageindex' if pi_context else ''}",
            retrieval_time=retrieval_time,
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  STAGE 3: SYNTHESISER — generate answer from context
    # ═══════════════════════════════════════════════════════════════════════

    def _synthesise(self, plan: AgentPlan, context: str,
                    conv_context: str, user_profile: Optional[Any]) -> str:
        """Generate the answer using LLM with structured legal prompt."""
        is_clarified_final = (
            "FINAL LEGAL ANALYSIS REQUEST AFTER CLARIFICATION LOOP" in (plan.original_query or "")
            or "FINAL LEGAL ANALYSIS REQUEST AFTER CLARIFICATION LOOP" in (plan.rewritten_query or "")
        )

        # Personalisation hints
        lang_hint = ""
        if user_profile and user_profile.preferred_language != "en":
            lang_hint = f"\nUser prefers responses in: {user_profile.preferred_language}"

        history_hint = ""
        if conv_context:
            history_hint = (
                f"\n\nConversation history (for context continuity):\n"
                f"{conv_context[-400:]}\n"
            )

        system_msg = (
            "You are a senior Indian legal analysis assistant.\n\n"
            "NON-NEGOTIABLE RULES:\n"
            "- Treat retrieved documents as the primary authority.\n"
            "- If the prompt contains 'FINAL LEGAL ANALYSIS REQUEST AFTER CLARIFICATION LOOP', treat the original scenario and clarification answers as binding facts/assumptions.\n"
            "- For clarified-final prompts, copy the user's date/statute/forum/evidence assumptions exactly; do not substitute older assumptions such as 2022, IPC, CrPC, or Evidence Act when the user selected August 2024, BNS, BNSS, and BSA.\n"
            "- For clarified-final prompts, do not output 'Sub-Question N' headings unless the user expressly requested that label. Use the requested final response format instead.\n"
            "- Never ignore a user-selected response posture such as hybrid, balanced analysis, side-wise arguments, or likely-outcome prediction.\n"
            "- Do NOT invent case names, citations, section numbers, years, or holdings.\n"
            "- If a precedent/section is not present in retrieved records, label it as 'Unverified in retrieved record' and do not rely on it for conclusions.\n"
            "- For criminal/procedure/evidence topics, use BNS/BNSS/BSA framing and mention IPC/CrPC/Evidence Act only as legacy-equivalent mapping when necessary.\n"
            "- Apply law to facts explicitly (Issue -> Rule -> Application -> Conclusion).\n"
            "- For comparative questions, steelman both sides before your conclusion.\n"
            "- Do not describe a party as victim/perpetrator unless that status is legally established by the assumed facts.\n"
            "- End with one-line disclaimer that this is general legal information.\n\n"
            "OUTPUT FORMAT:\n"
            "Use the format expressly requested by the user or final clarification request. "
            "If no special format is requested, use: "
            "1) Case Summary; 2) Governing Law (exact sections/articles); "
            "3) Application to Facts; 4) Risks and Procedural Next Steps; 5) Conclusion."
            f"{lang_hint}"
        )

        sub_query_block = ""
        if plan.sub_queries and not is_clarified_final:
            formatted_subs = "\n".join(
                f"Sub-Question {idx + 1}: {sq}" for idx, sq in enumerate(plan.sub_queries[:12])
            )
            sub_query_block = (
                "\n\nMANDATORY SUB-QUESTIONS TO ANSWER:\n"
                f"{formatted_subs}\n"
                "You MUST answer every listed sub-question explicitly using headings 'Sub-Question N'."
            )

        user_msg = (
            f"Question: {plan.rewritten_query}\n\n"
            f"Retrieved legal documents:\n{context[:4000]}\n"
            f"{history_hint}\n"
            f"{sub_query_block}\n\n"
            "Provide a comprehensive legal analysis. "
            + (
                "Because this is a clarified-final prompt, begin from the clarification answers exactly as provided and obey the requested final response structure."
                if is_clarified_final else ""
            )
        )

        try:
            answer = self._llm_call(system_msg, user_msg,
                                    temperature=0.3, max_tokens=2500)
            return answer
        except Exception as e:
            logger.error(f"[SYNTHESISER] Primary LLM synthesis failed: {e}. Trying fast fallback...")
            # ── Fallback: use lighter model + shorter prompt ─────────────
            try:
                fallback_usr = (
                    f"You are an Indian law expert. Answer this question based on the context below.\n\n"
                    f"Question: {plan.original_query}\n\n"
                    f"Context (legal documents):\n{context[:2000]}\n\n"
                    f"Give a clear, concise answer in 150-400 words. "
                    f"Use only citations that are present in the context. "
                    f"If a citation is unavailable, explicitly mark it unverified."
                )
                resp = self.llm.chat.completions.create(
                    model=Config.FAST_LLM_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a concise Indian law assistant."},
                        {"role": "user", "content": fallback_usr},
                    ],
                    temperature=0.3,
                    max_tokens=800,
                )
                fallback_answer = (resp.choices[0].message.content or "").strip()
                if len(fallback_answer.split()) >= 30:
                    logger.info(f"[SYNTHESISER] Fallback model succeeded ({len(fallback_answer.split())} words)")
                    return fallback_answer
            except Exception as e2:
                logger.error(f"[SYNTHESISER] Fallback model also failed: {e2}")
            return (
                f"I was unable to generate a complete answer due to a service issue. "
                f"Based on the retrieved documents, your question about "
                f"'{plan.original_query[:100]}' relates to Indian law. Please try again."
            )

    # ═══════════════════════════════════════════════════════════════════════
    #  STAGE 4: VERIFIER — self-critique / reflection
    # ═══════════════════════════════════════════════════════════════════════

    def _verify(self, original_query: str, answer: str,
                context: str, plan: AgentPlan) -> VerificationResult:
        """
        LLM-powered self-critique.
        Checks: completeness, accuracy, hallucination risk, relevance.
        """
        system_msg = (
            "You are a LEGAL ANSWER VERIFIER. You review AI-generated legal answers "
            "for quality. Output ONLY valid JSON:\n"
            "{\n"
            '  "confidence": <float 0.0-1.0>,\n'
            '  "is_acceptable": <true/false>,\n'
            '  "issues": ["<issue 1>", ...],\n'
            '  "suggestions": "<what to improve if not acceptable>",\n'
            '  "reasoning": "<brief explanation>"\n'
            "}\n\n"
            "Check:\n"
            "1. Does it answer the actual question asked?\n"
            "2. Are cited sections/cases plausible for Indian law?\n"
            "3. Is the answer substantive (not just filler)?\n"
            "4. Is the structure clear (Framework → Precedents → Reasoning)?\n"
            "5. Any obvious hallucinated case names or fabricated sections?\n\n"
            "Set confidence >= 0.75 if answer is good enough to serve.\n"
            "Set is_acceptable = true if confidence >= 0.75."
        )

        user_msg = (
            f"ORIGINAL QUESTION: {original_query}\n\n"
            f"GENERATED ANSWER (first 2000 chars):\n{answer[:2000]}\n\n"
            f"RETRIEVED CONTEXT (first 1800 chars):\n{context[:1800]}\n\n"
            f"STRATEGY USED: {plan.strategy}\n"
            f"DOMAINS: {', '.join(plan.detected_domains)}"
        )

        heuristic_issues, heuristic_cap, heuristic_suggestions = self._run_heuristic_checks(
            original_query=original_query,
            answer=answer,
            context=context,
            plan=plan,
        )

        try:
            resp = self._llm_call(system_msg, user_msg,
                                  temperature=0.1, max_tokens=400)
            data = self._parse_json(resp)
            confidence = float(data.get("confidence", 0.5))
            confidence = min(confidence, heuristic_cap)
            llm_issues = data.get("issues", [])
            merged_issues = list(llm_issues)
            for issue in heuristic_issues:
                if issue not in merged_issues:
                    merged_issues.append(issue)

            suggestions = data.get("suggestions", "")
            if heuristic_suggestions:
                suggestions = (
                    f"{suggestions} {heuristic_suggestions}".strip()
                    if suggestions else heuristic_suggestions
                )

            llm_accept = data.get("is_acceptable", confidence >= CONFIDENCE_THRESHOLD)
            is_acceptable = bool(llm_accept) and not heuristic_issues and confidence >= CONFIDENCE_THRESHOLD
            return VerificationResult(
                is_acceptable=is_acceptable,
                confidence=confidence,
                issues=merged_issues,
                suggestions=suggestions,
                reasoning=data.get("reasoning", ""),
            )
        except Exception as e:
            logger.warning(f"[VERIFIER] Verification failed: {e}. Falling back to deterministic checks.")
            fallback_confidence = min(0.65, heuristic_cap)
            fallback_accept = not heuristic_issues and fallback_confidence >= CONFIDENCE_THRESHOLD
            return VerificationResult(
                is_acceptable=fallback_accept,
                confidence=fallback_confidence,
                issues=["verifier_failed", *heuristic_issues],
                suggestions=heuristic_suggestions,
                reasoning=f"Verifier error: {e}",
            )

    # ═══════════════════════════════════════════════════════════════════════
    #  PLAN REFINEMENT (between loops)
    # ═══════════════════════════════════════════════════════════════════════

    def _refine_plan(self, plan: AgentPlan,
                     verification: VerificationResult) -> AgentPlan:
        """Adapt the plan based on verification feedback."""
        logger.info(f"[AGENT] Refining plan: {verification.suggestions[:80]}")

        # Escalate strategy
        if plan.strategy == "simple":
            plan.strategy = "multi_hop"
        elif plan.strategy == "statute_lookup":
            plan.strategy = "multi_hop"
        elif plan.strategy == "multi_hop":
            plan.needs_web_search = True
            plan.strategy = "research"

        # Add sub-queries from verifier suggestions.
        # NOTE: these are INTERNAL critic instructions, never user-facing copy.
        # Promoting them into plan.sub_queries leaked scaffolding such as
        # "Sub-Question 1: Regenerate with a complete grounded answer..." into
        # rendered answers. Keep them out of anything the user can see; the
        # refinement prompt below already receives the full suggestions text.
        if verification.suggestions and not plan.sub_queries:
            plan.sub_queries = [verification.suggestions[:200]] if _DEBUG_EXPOSE_CRITIC_SUGGESTIONS else []

        # Rewrite query if issues found
        if "doesn't answer" in " ".join(verification.issues).lower():
            plan.rewritten_query = f"{plan.original_query} (elaborate with sections and cases)"

        if "incomplete_subquestion_coverage" in verification.issues:
            if plan.strategy == "simple":
                plan.strategy = "multi_hop"
            if plan.complexity == "low":
                plan.complexity = "high"

        if any(issue in verification.issues for issue in (
            "ungrounded_case_citations",
            "outdated_statute_framing",
            "missing_sedition_current_position",
            "missing_electoral_bond_current_position",
        )):
            plan.needs_web_search = True

        return plan

    def _estimate_subquery_coverage(self, plan: AgentPlan, answer: str) -> Tuple[float, List[int]]:
        """Estimate how many planned sub-questions were addressed in the answer."""
        if not plan.sub_queries:
            return 1.0, []

        answer_lower = (answer or "").lower()
        missing_indices: List[int] = []

        for idx, sub_query in enumerate(plan.sub_queries[:12], start=1):
            heading_hit = bool(
                re.search(rf"(?:sub[-\s]?question|question|q)\s*{idx}\b", answer_lower)
            )
            tokens = [
                tok for tok in re.findall(r"[a-z]{4,}", (sub_query or "").lower())
                if tok not in SUBQUERY_STOPWORDS
            ][:6]
            token_hits = sum(1 for tok in tokens if tok in answer_lower)
            required_hits = max(1, min(2, len(tokens))) if tokens else 1

            if heading_hit or token_hits >= required_hits:
                continue
            missing_indices.append(idx)

        covered = max(0, len(plan.sub_queries[:12]) - len(missing_indices))
        coverage = covered / max(1, len(plan.sub_queries[:12]))
        return coverage, missing_indices

    def _count_ungrounded_case_citations(self, answer: str, context: str) -> int:
        """Count case citations that do not appear in retrieved context."""
        try:
            from kaanoon_test.system_adapters.citation_extractor import CitationExtractor

            extractor = CitationExtractor()
            extracted = extractor.extract_citations(answer or "")
            validation = extractor.validate_citations(extracted, [{"text": context or ""}])
            missing = validation.get("missing_from_context", [])
            return sum(1 for item in missing if item.get("type") == "Case Law")
        except Exception as exc:
            logger.debug(f"[VERIFIER] Citation grounding check skipped: {exc}")
            return 0

    def _has_outdated_statute_framing(self, query: str, answer: str) -> bool:
        """Detect old-code-only criminal/procedure/evidence framing without transitions."""
        q_lower = (query or "").lower()
        a_lower = (answer or "").lower()

        criminal_context = any(term in q_lower for term in (
            "criminal", "bail", "fir", "uapa", "sedition", "ipc", "crpc", "evidence", "bns", "bnss", "bsa",
        ))
        if not criminal_context:
            return False

        old_refs = any(term in a_lower for term in (" ipc", "crpc", "indian evidence act"))
        new_refs = any(term in a_lower for term in (
            " bns", " bnss", " bsa", "bharatiya nyaya sanhita", "bharatiya nagarik suraksha sanhita",
            "bharatiya sakshya",
        ))
        transition_refs = any(term in a_lower for term in (
            "legacy", "equivalent", "mapping", "transition", "saved proceeding", "section 534",
        ))

        return old_refs and not (new_refs or transition_refs)

    @staticmethod
    def _missing_sedition_current_position(query: str, answer: str) -> bool:
        q_lower = (query or "").lower()
        if "sedition" not in q_lower and "124a" not in q_lower:
            return False
        a_lower = (answer or "").lower()
        required_markers = ("vombatkere", "abeyance", "stay", "no fresh fir", "re-examination")
        return not any(marker in a_lower for marker in required_markers)

    @staticmethod
    def _missing_electoral_bond_current_position(query: str, answer: str) -> bool:
        q_lower = (query or "").lower()
        if "electoral bond" not in q_lower and "electoral bonds" not in q_lower:
            return False
        a_lower = (answer or "").lower()
        required_markers = (
            "association for democratic reforms",
            "struck down",
            "unconstitutional",
            "february 2024",
        )
        return not any(marker in a_lower for marker in required_markers)

    def _run_heuristic_checks(self, *, original_query: str, answer: str,
                              context: str, plan: AgentPlan) -> Tuple[List[str], float, str]:
        """Deterministic quality gates for failures seen in production legal QA."""
        issues: List[str] = []
        suggestions: List[str] = []
        confidence_cap = 1.0

        sub_cov, missing_subs = self._estimate_subquery_coverage(plan, answer)
        if sub_cov < SUBQUERY_COVERAGE_THRESHOLD:
            issues.append("incomplete_subquestion_coverage")
            missing_text = ", ".join(str(idx) for idx in missing_subs) if missing_subs else "unknown"
            suggestions.append(
                f"Answer every mandatory sub-question explicitly. Missing sub-question indices: {missing_text}."
            )
            confidence_cap = min(confidence_cap, 0.55)

        missing_cases = self._count_ungrounded_case_citations(answer, context)
        if missing_cases > 0:
            issues.append("ungrounded_case_citations")
            suggestions.append("Remove or clearly mark unverified case citations not present in retrieved context.")
            confidence_cap = min(confidence_cap, 0.50)

        if self._has_outdated_statute_framing(original_query, answer):
            issues.append("outdated_statute_framing")
            suggestions.append("Use BNS/BNSS/BSA framing and map legacy IPC/CrPC/Evidence references explicitly.")
            confidence_cap = min(confidence_cap, 0.55)

        clarified_final = "final legal analysis request after clarification loop" in (original_query or "").lower()
        if clarified_final:
            q_lower = (original_query or "").lower()
            a_lower = (answer or "").lower()
            if ("august 2024" in q_lower or "post-1 july 2024" in q_lower or "post-1 july 2024" in q_lower) and "2022" in a_lower:
                issues.append("contradicted_clarified_timeline")
                suggestions.append("Use the clarified August 2024/post-1 July 2024 timeline; remove any 2022 assumption.")
                confidence_cap = min(confidence_cap, 0.35)
            if "answer as a hybrid" in q_lower and re.search(r"sub[-\s]?question\s+\d+", a_lower):
                issues.append("wrong_clarified_final_format")
                suggestions.append("Do not use Sub-Question headings; use neutral court-balancing, side-wise arguments, and likely outcome.")
                confidence_cap = min(confidence_cap, 0.45)
            if "section 63" in q_lower and "section 63" not in a_lower:
                issues.append("missing_clarified_evidence_assumption")
                suggestions.append("Include the BSA Section 63 electronic-record assumption and its disputed-proof effect.")
                confidence_cap = min(confidence_cap, 0.55)
            if "article 21" in q_lower and "article 21" not in a_lower:
                issues.append("missing_article_21_balance")
                suggestions.append("Analyze Article 21 autonomy and liberty as a central issue.")
                confidence_cap = min(confidence_cap, 0.55)
            if "karnataka" in q_lower and not any(term in a_lower for term in ("karnataka", "anti-conversion", "freedom of religion")):
                issues.append("missing_karnataka_anti_conversion_assumption")
                suggestions.append("Analyze the Karnataka anti-conversion provisions invoked in the clarified assumptions.")
                confidence_cap = min(confidence_cap, 0.55)
            if "answer as a hybrid" in q_lower and not any(term in a_lower for term in ("likely outcome", "probable outcome", "side-wise", "parents", "state")):
                issues.append("missing_hybrid_response_posture")
                suggestions.append("Use the requested hybrid format: neutral balancing, side-wise arguments, and likely outcome.")
                confidence_cap = min(confidence_cap, 0.50)

        if self._missing_sedition_current_position(original_query, answer):
            issues.append("missing_sedition_current_position")
            suggestions.append("For sedition queries, mention the post-Vombatkere interim stay/abeyance position.")
            confidence_cap = min(confidence_cap, 0.45)

        if self._missing_electoral_bond_current_position(original_query, answer):
            issues.append("missing_electoral_bond_current_position")
            suggestions.append("For electoral bond queries, include the February 2024 Supreme Court strike-down position.")
            confidence_cap = min(confidence_cap, 0.45)

        return issues, confidence_cap, " ".join(suggestions).strip()

    # ═══════════════════════════════════════════════════════════════════════
    #  LLM UTILITIES
    # ═══════════════════════════════════════════════════════════════════════

    def _llm_call(self, system_msg: str, user_msg: str, *,
                  temperature: float = 0.3, max_tokens: int = 1500) -> str:
        """Call LLM with retry + cross-vendor failover + fast model fallback.

        G5 LATENCY BOUND
        -----------------
        This cascade is 2 models x 2 attempts, so the naive worst case is
        4 x per-request-timeout plus the sleeps -- at a 30 s timeout that is
        ~127 s for ONE internal LLM call, which is how a single query reached
        the measured 71.6 s p95 and the read-timeout probe failure.

        A wall-clock deadline now caps the WHOLE cascade. Once it is spent the
        loop stops retrying and surfaces the last real error, so the caller can
        fail over or degrade instead of stacking another timeout. Budget is
        LLM_REQUEST_BUDGET_SECONDS (default 75 s).
        """
        # Model cascade: start with 70b, fall back to 8b on rate-limit
        _model_cascade = [
            (self.model,                     max_tokens),          # primary
            (Config.FAST_LLM_MODEL, min(max_tokens, 1200)),  # fallback: fast model
        ]
        try:
            _budget = float(os.getenv("LLM_REQUEST_BUDGET_SECONDS", "75"))
        except (TypeError, ValueError):
            _budget = 75.0
        _deadline = time.time() + max(5.0, _budget)
        last_exc = None
        for model_name, m_tokens in _model_cascade:
            for attempt in range(2):  # 2 attempts per model
                if time.time() >= _deadline:
                    logger.warning(
                        "[LLM] deadline exhausted (%.1fs budget) before trying %s; "
                        "stopping cascade", _budget, model_name)
                    raise RuntimeError(
                        f"LLM deadline exceeded after {_budget:.0f}s. Last error: {last_exc}"
                    )
                try:
                    resp = self.llm.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": user_msg},
                        ],
                        temperature=temperature,
                        max_tokens=m_tokens,
                    )
                    if model_name != self.model:
                        logger.info(f"[LLM] Fallback model '{model_name}' succeeded")
                    # Reasoning models can return content=None (HTTP 200 with the
                    # budget consumed by the reasoning trace). Treat as empty and
                    # retry rather than crashing on .strip().
                    _content = (resp.choices[0].message.content or "").strip()
                    if not _content:
                        raise ValueError("empty LLM response (reasoning consumed budget)")
                    return _content
                except Exception as e:
                    last_exc = e
                    err_str = str(e)
                    logger.warning(f"[LLM] {model_name} attempt {attempt+1} failed: {err_str[:120]}")
                    if "429" in err_str or "rate_limit" in err_str.lower():
                        # Cross-VENDOR failover. force_rotation() records the
                        # failure on the current vendor's breaker and steps to a
                        # different vendor, skipping any open circuit -- so a
                        # Groq org-wide 429 is not retried on the next Groq key.
                        if hasattr(self.llm, "force_rotation"):
                            self.llm.force_rotation(reason=err_str[:60])
                        sleep_t = 1.5 if attempt == 0 else 0
                        if sleep_t and time.time() + sleep_t < _deadline:
                            time.sleep(sleep_t)
                    else:
                        # Do not sleep past the deadline.
                        if time.time() + 1.0 < _deadline:
                            time.sleep(1.0)
        raise RuntimeError(f"LLM call failed for all models. Last error: {last_exc}")

    @staticmethod
    def _parse_json(text: str) -> Dict:
        """Extract JSON from LLM output (handles markdown fences)."""
        # Strip markdown code fences
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try finding JSON object in text
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        logger.warning(f"[JSON] Could not parse: {text[:200]}")
        return {}

    @staticmethod
    def _format_sources(documents: List[Dict]) -> List[Dict]:
        """Format source documents for API response.

        PROVENANCE FIX: this used to emit only title/content/source, which
        DELETED url, link, metadata, trusted_source and source_tier. The
        downstream gate (_is_trusted_source_doc in unified_advanced_rag.py)
        tries to establish trust from exactly those fields, so after this
        function ran, `url` was always gone -> `domain` always "" -> every
        document was untrusted, and the only thing that saved it was the
        literal default string "Legal Database" matching a label in the trust
        list. Net effect: the trust signal was pure noise, and genuine
        indiacode.nic.in sources were demoted while anything was accepted.

        We now carry provenance through, and we do NOT default `source` to a
        trust-bearing label.
        """
        PROVENANCE_KEYS = (
            "url", "link", "metadata", "trusted_source", "source_tier",
            "source_domain", "act", "court", "year", "case_name",
            "section_number", "act_name", "chapter",
        )
        sources = []
        for doc in list(documents)[:8]:
            if isinstance(doc, str):
                # The agentic engine can emit bare strings; never assume a dict.
                sources.append({
                    "title": doc[:90] or "Legal document",
                    "content": doc[:300],
                    "source": "corpus",
                })
                continue
            if not isinstance(doc, dict):
                doc = {"content": str(doc)}
            row = {k: doc.get(k) for k in PROVENANCE_KEYS if doc.get(k) is not None}
            row["title"] = doc.get("title") or doc.get("id") or "Legal document"
            row["content"] = str(doc.get("content", doc.get("text", "")))[:300]
            # Keep the real source label when present. Only fall back to a
            # NON-trust-bearing placeholder so the downstream gate cannot
            # accidentally trust a document via a default string.
            row["source"] = doc.get("source") or doc.get("source_domain") or "corpus"
            sources.append(row)
        return sources
