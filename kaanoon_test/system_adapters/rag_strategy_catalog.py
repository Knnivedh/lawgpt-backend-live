"""
RAG STRATEGY CATALOG — 20 Distinct Retrieval-Augmented Generation Strategies
=============================================================================
Each strategy is a dataclass describing how the MegaRAGOrchestrator should
configure retrieval and synthesis for a particular query profile.

Strategies are selected via the StrategyRouter, which maps query features
(complexity, domain, intent) to the most appropriate strategy (or blend).

Strategy Index
--------------
 1. NAIVE_RAG           — Simple top-k vector retrieval + direct generation
 2. KEYWORD_BM25        — Pure BM25 keyword retrieval (vectorless)
 3. HYBRID_FUSION       — Vector (60%) + BM25 (40%) score fusion
 4. MULTI_QUERY         — 3 rewritten sub-queries, results merged
 5. HyDE                — Hypothetical Document Embeddings
 6. STEP_BACK           — Abstract → concrete query chain
 7. CHAIN_OF_THOUGHT    — CoT decomposition before retrieval
 8. SELF_QUERY          — LLM generates structured metadata filter
 9. CONTEXTUAL_COMPRESS — Retrieved docs compressed before synthesis
10. MULTI_HOP           — Sequential retrieval across fact chains
11. AGENTIC_LOOP        — Plan → retrieve → verify → refine loop (existing engine)
12. ONTOLOGY_GROUNDED   — Legal ontology node expansion (existing adapter)
13. HIERARCHICAL_COT    — HiRAG hierarchical CoT (existing adapter)
14. INSTRUCTION_TUNED   — Feedback-optimised prompting (existing adapter)
15. PARAMETRIC_BLEND    — Parametric memory + retrieval blend (existing adapter)
16. OWL_JUDICIAL        — OWL/SPARQL judicial workforce reasoning (existing adapter)
17. STATUTE_PRIORITY    — Statutes DB first, then judgments fallback
18. TIMELINE_AWARE      — Date-filtered retrieval for time-sensitive queries
19. CITATION_CHAIN      — Retrieve cited cases from root case recursively
20. ENSEMBLE_VOTE       — Run top-5 strategies, majority-vote final answer
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StrategyType(str, Enum):
    NAIVE_RAG           = "naive_rag"
    KEYWORD_BM25        = "keyword_bm25"
    HYBRID_FUSION       = "hybrid_fusion"
    MULTI_QUERY         = "multi_query"
    HyDE                = "hyde"
    STEP_BACK           = "step_back"
    CHAIN_OF_THOUGHT    = "chain_of_thought"
    SELF_QUERY          = "self_query"
    CONTEXTUAL_COMPRESS = "contextual_compress"
    MULTI_HOP           = "multi_hop"
    AGENTIC_LOOP        = "agentic_loop"
    ONTOLOGY_GROUNDED   = "ontology_grounded"
    HIERARCHICAL_COT    = "hierarchical_cot"
    INSTRUCTION_TUNED   = "instruction_tuned"
    PARAMETRIC_BLEND    = "parametric_blend"
    OWL_JUDICIAL        = "owl_judicial"
    STATUTE_PRIORITY    = "statute_priority"
    TIMELINE_AWARE      = "timeline_aware"
    CITATION_CHAIN      = "citation_chain"
    ENSEMBLE_VOTE       = "ensemble_vote"


@dataclass
class StrategyConfig:
    """Configuration for a single RAG strategy."""
    strategy_type: StrategyType
    display_name: str
    description: str
    top_k: int = 5
    use_vector_store: bool = True
    use_bm25_store: bool = False
    vector_weight: float = 1.0
    bm25_weight: float = 0.0
    rewrite_query: bool = False
    num_rewrites: int = 1
    use_hypothetical_doc: bool = False
    step_back_abstraction: bool = False
    cot_decompose: bool = False
    compress_context: bool = False
    multihop_depth: int = 1
    use_agentic_engine: bool = False
    use_ontology: bool = False
    use_hierarchical: bool = False
    use_instruction_tuning: bool = False
    use_parametric: bool = False
    use_owl: bool = False
    statute_first: bool = False
    date_filter: bool = False
    citation_expansion: bool = False
    ensemble_strategies: List[str] = field(default_factory=list)
    extra_params: Dict[str, Any] = field(default_factory=dict)


# ── Strategy Registry ──────────────────────────────────────────────────────────
STRATEGY_REGISTRY: Dict[StrategyType, StrategyConfig] = {

    StrategyType.NAIVE_RAG: StrategyConfig(
        strategy_type=StrategyType.NAIVE_RAG,
        display_name="Naive RAG",
        description="Simple top-k vector similarity retrieval + direct synthesis.",
        top_k=5, use_vector_store=True, use_bm25_store=False,
    ),

    StrategyType.KEYWORD_BM25: StrategyConfig(
        strategy_type=StrategyType.KEYWORD_BM25,
        display_name="Keyword BM25 (Vectorless)",
        description="Pure BM25 keyword-based retrieval. No embeddings required.",
        top_k=8, use_vector_store=False, use_bm25_store=True,
        bm25_weight=1.0, vector_weight=0.0,
    ),

    StrategyType.HYBRID_FUSION: StrategyConfig(
        strategy_type=StrategyType.HYBRID_FUSION,
        display_name="Hybrid Vector+BM25 Fusion",
        description="Reciprocal Rank Fusion of vector retrieval and BM25 scores.",
        top_k=8, use_vector_store=True, use_bm25_store=True,
        vector_weight=0.6, bm25_weight=0.4,
    ),

    StrategyType.MULTI_QUERY: StrategyConfig(
        strategy_type=StrategyType.MULTI_QUERY,
        display_name="Multi-Query Expansion",
        description="LLM rewrites query 3 ways; results merged by union.",
        top_k=6, use_vector_store=True, use_bm25_store=True,
        rewrite_query=True, num_rewrites=3,
        vector_weight=0.6, bm25_weight=0.4,
    ),

    StrategyType.HyDE: StrategyConfig(
        strategy_type=StrategyType.HyDE,
        display_name="HyDE (Hypothetical Doc Embeddings)",
        description="Generate a hypothetical answer doc, embed it, then retrieve similar real docs.",
        top_k=5, use_vector_store=True, use_bm25_store=False,
        use_hypothetical_doc=True,
    ),

    StrategyType.STEP_BACK: StrategyConfig(
        strategy_type=StrategyType.STEP_BACK,
        display_name="Step-Back Prompting",
        description="First ask a broader abstract question; use that to retrieve context, then answer specific.",
        top_k=6, use_vector_store=True, use_bm25_store=True,
        step_back_abstraction=True, vector_weight=0.5, bm25_weight=0.5,
    ),

    StrategyType.CHAIN_OF_THOUGHT: StrategyConfig(
        strategy_type=StrategyType.CHAIN_OF_THOUGHT,
        display_name="Chain-of-Thought RAG",
        description="LLM decomposes query via CoT before triggering retrieval steps.",
        top_k=6, use_vector_store=True, use_bm25_store=True,
        cot_decompose=True, vector_weight=0.55, bm25_weight=0.45,
    ),

    StrategyType.SELF_QUERY: StrategyConfig(
        strategy_type=StrategyType.SELF_QUERY,
        display_name="Self-Query (Metadata Filter)",
        description="LLM generates structured filter (year, act, section) then applies it.",
        top_k=5, use_vector_store=True, use_bm25_store=True,
        rewrite_query=True, num_rewrites=1,
        vector_weight=0.6, bm25_weight=0.4,
    ),

    StrategyType.CONTEXTUAL_COMPRESS: StrategyConfig(
        strategy_type=StrategyType.CONTEXTUAL_COMPRESS,
        display_name="Contextual Compression",
        description="Retrieved chunks compressed by an LLM extractor before synthesis.",
        top_k=10, use_vector_store=True, use_bm25_store=True,
        compress_context=True, vector_weight=0.6, bm25_weight=0.4,
    ),

    StrategyType.MULTI_HOP: StrategyConfig(
        strategy_type=StrategyType.MULTI_HOP,
        display_name="Multi-Hop Iterative Retrieval",
        description="Retrieve fact → extract entities → retrieve again (depth 2).",
        top_k=5, use_vector_store=True, use_bm25_store=True,
        multihop_depth=2, vector_weight=0.6, bm25_weight=0.4,
    ),

    StrategyType.AGENTIC_LOOP: StrategyConfig(
        strategy_type=StrategyType.AGENTIC_LOOP,
        display_name="Agentic Loop (Plan→Retrieve→Verify→Refine)",
        description="Full agentic orchestration: planner, router, retriever, verifier loop.",
        top_k=6, use_vector_store=True, use_bm25_store=True,
        use_agentic_engine=True, vector_weight=0.6, bm25_weight=0.4,
    ),

    StrategyType.ONTOLOGY_GROUNDED: StrategyConfig(
        strategy_type=StrategyType.ONTOLOGY_GROUNDED,
        display_name="Ontology-Grounded RAG",
        description="Legal ontology expands query nodes; richer concept matching.",
        top_k=6, use_vector_store=True, use_bm25_store=True,
        use_ontology=True, vector_weight=0.55, bm25_weight=0.45,
    ),

    StrategyType.HIERARCHICAL_COT: StrategyConfig(
        strategy_type=StrategyType.HIERARCHICAL_COT,
        display_name="Hierarchical Chain-of-Thought (HiRAG)",
        description="Hierarchical thought tree with multi-level retrieval at each node.",
        top_k=6, use_vector_store=True, use_bm25_store=True,
        use_hierarchical=True, vector_weight=0.6, bm25_weight=0.4,
    ),

    StrategyType.INSTRUCTION_TUNED: StrategyConfig(
        strategy_type=StrategyType.INSTRUCTION_TUNED,
        display_name="Instruction-Tuned RAG",
        description="Feedback-optimised instruction prompt wrapping retrieval.",
        top_k=5, use_vector_store=True, use_bm25_store=True,
        use_instruction_tuning=True, vector_weight=0.6, bm25_weight=0.4,
    ),

    StrategyType.PARAMETRIC_BLEND: StrategyConfig(
        strategy_type=StrategyType.PARAMETRIC_BLEND,
        display_name="Parametric Memory + Retrieval Blend",
        description="Blend LLM parametric knowledge with retrieved context via confidence gate.",
        top_k=5, use_vector_store=True, use_bm25_store=True,
        use_parametric=True, vector_weight=0.5, bm25_weight=0.5,
    ),

    StrategyType.OWL_JUDICIAL: StrategyConfig(
        strategy_type=StrategyType.OWL_JUDICIAL,
        display_name="OWL Judicial Workforce Multi-Agent",
        description="Multi-agent: Researcher → Analyst → Reviewer → Drafter chain.",
        top_k=6, use_vector_store=True, use_bm25_store=True,
        use_owl=True, vector_weight=0.6, bm25_weight=0.4,
    ),

    StrategyType.STATUTE_PRIORITY: StrategyConfig(
        strategy_type=StrategyType.STATUTE_PRIORITY,
        display_name="Statute-Priority RAG",
        description="Query statute DB first; use judgments only for gaps.",
        top_k=7, use_vector_store=True, use_bm25_store=True,
        statute_first=True, vector_weight=0.65, bm25_weight=0.35,
    ),

    StrategyType.TIMELINE_AWARE: StrategyConfig(
        strategy_type=StrategyType.TIMELINE_AWARE,
        display_name="Timeline-Aware RAG",
        description="Applies date metadata filters for recent-law or historical queries.",
        top_k=6, use_vector_store=True, use_bm25_store=True,
        date_filter=True, vector_weight=0.6, bm25_weight=0.4,
    ),

    StrategyType.CITATION_CHAIN: StrategyConfig(
        strategy_type=StrategyType.CITATION_CHAIN,
        display_name="Citation-Chain Expansion",
        description="Starting from matched case, recursively retrieve cited precedents (depth 2).",
        top_k=5, use_vector_store=True, use_bm25_store=True,
        citation_expansion=True, multihop_depth=2,
        vector_weight=0.6, bm25_weight=0.4,
    ),

    StrategyType.ENSEMBLE_VOTE: StrategyConfig(
        strategy_type=StrategyType.ENSEMBLE_VOTE,
        display_name="Ensemble Voting (Top-5 strategies)",
        description="Run HYBRID_FUSION + MULTI_QUERY + AGENTIC_LOOP + ONTOLOGY_GROUNDED + HIERARCHICAL_COT; LLM picks best.",
        top_k=7, use_vector_store=True, use_bm25_store=True,
        ensemble_strategies=[
            StrategyType.HYBRID_FUSION, StrategyType.MULTI_QUERY,
            StrategyType.AGENTIC_LOOP, StrategyType.ONTOLOGY_GROUNDED,
            StrategyType.HIERARCHICAL_COT,
        ],
        vector_weight=0.6, bm25_weight=0.4,
    ),
}


# ── Router ─────────────────────────────────────────────────────────────────────
class StrategyRouter:
    """
    Maps query features → optimal strategy.

    Uses rule-based heuristics (fast) with optional LLM override for
    ambiguous queries.
    """

    # Keywords that trigger specific overrides
    _STATUTE_KEYWORDS = re.compile(
        r"\b(section|act|ipc|crpc|bns|bnss|iea|posh|pocso|dowry|divorce|rent|gst)\b",
        re.I,
    ) if __import__("re") else None

    _TIMELINE_KEYWORDS = re.compile(
        r"\b(latest|recent|2024|2025|2026|new law|amendment|after|before|since)\b",
        re.I,
    ) if __import__("re") else None

    _CITATION_KEYWORDS = re.compile(
        r"\b(cited|precedent|followed|overruled|referred|distinguished)\b",
        re.I,
    ) if __import__("re") else None

    _COMPLEX_KEYWORDS = re.compile(
        r"\b(explain|compare|difference|analysis|elaborate|step by step|what if)\b",
        re.I,
    ) if __import__("re") else None

    @classmethod
    def route(cls, query: str, override: Optional[str] = None) -> StrategyType:
        """Return the best strategy type for the given query."""
        if override:
            try:
                return StrategyType(override)
            except ValueError:
                pass

        q = query.lower()

        if cls._STATUTE_KEYWORDS and cls._STATUTE_KEYWORDS.search(q):
            return StrategyType.STATUTE_PRIORITY

        if cls._TIMELINE_KEYWORDS and cls._TIMELINE_KEYWORDS.search(q):
            return StrategyType.TIMELINE_AWARE

        if cls._CITATION_KEYWORDS and cls._CITATION_KEYWORDS.search(q):
            return StrategyType.CITATION_CHAIN

        if cls._COMPLEX_KEYWORDS and cls._COMPLEX_KEYWORDS.search(q):
            return StrategyType.AGENTIC_LOOP

        if len(query.split()) <= 6:
            return StrategyType.HYBRID_FUSION

        return StrategyType.MULTI_QUERY

    @classmethod
    def all_strategies(cls) -> List[StrategyType]:
        return list(STRATEGY_REGISTRY.keys())


# re import needed for _STATUTE_KEYWORDS etc. above
import re
