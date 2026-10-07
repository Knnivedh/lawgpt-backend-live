"""
ADVANCED AGENTIC RAG SYSTEM - Production-Ready Upgrade
Enhanced with Async, Memory, Redis, Feedback, and Metrics

Key Upgrades:
1. Full Async/Await Support
2. Conversational Memory Agent
3. Redis Cache Integration
4. Feedback Collection System
5. Evaluation Metrics Dashboard
6. Conversation History Management
7. Production-Ready Architecture
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Generator, Tuple, Union, AsyncGenerator
import time
import re
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from dotenv import load_dotenv
import hashlib
from functools import lru_cache
from datetime import datetime
import uuid

# Add parent directories to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

load_dotenv(project_root / "config" / ".env")

from rag_system.core.hybrid_chroma_store import HybridChromaStore
from rag_system.core.enhanced_retriever import EnhancedRetriever
from config.config import Config
from openai import AsyncOpenAI, OpenAI

# Import new expert components
from .legal_embedding_enhancer import LegalEmbeddingEnhancer
from .expert_legal_prompts import build_expert_legal_prompt, build_expert_prompt_for_kaanoon_qa
from .legal_reasoning_agent import LegalReasoningAgent
from .citation_extractor import CitationExtractor

# Try to import Redis (optional)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("[WARNING] Redis not available, using in-memory cache")


@dataclass
class QueryAnalysis:
    """Query analysis result"""
    complexity: str
    query_type: str
    sub_queries: List[str]
    legal_domains: List[str]
    requires_decomposition: bool
    estimated_time: float
    priority: int


@dataclass
class RetrievalResult:
    """Retrieval result with metadata"""
    documents: List[Dict]
    retrieval_time: float
    method: str
    confidence: float


@dataclass
class ConversationMessage:
    """Conversation message structure"""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: float
    message_id: str
    metadata: Dict[str, Any]


@dataclass
class FeedbackData:
    """User feedback data"""
    query: str
    answer: str
    rating: int  # 1-5
    feedback_text: Optional[str]
    timestamp: float
    session_id: str


class RedisCache:
    """Redis-based distributed cache"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", ttl: int = 3600):
        """Initialize Redis cache"""
        if not REDIS_AVAILABLE:
            raise ImportError("Redis not installed. Install with: pip install redis")
        
        self.client = redis.from_url(redis_url, decode_responses=True)
        self.ttl = ttl  # Time to live in seconds
        
        # Test connection
        try:
            self.client.ping()
            print("[OK] Redis cache connected")
        except Exception as e:
            print(f"[WARNING] Redis connection failed: {e}")
            raise
    
    def get_cache_key(self, query: str) -> str:
        """Generate cache key"""
        normalized = re.sub(r'[^\w\s]', '', query.lower())
        normalized = ' '.join(normalized.split())
        return f"rag_cache:{hashlib.md5(normalized.encode()).hexdigest()}"
    
    async def get(self, query: str) -> Optional[Dict]:
        """Get cached result (async)"""
        key = self.get_cache_key(query)
        try:
            cached = self.client.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            print(f"[ERROR] Redis get failed: {e}")
        return None
    
    async def set(self, query: str, result: Dict):
        """Cache result (async)"""
        key = self.get_cache_key(query)
        try:
            self.client.setex(key, self.ttl, json.dumps(result))
        except Exception as e:
            print(f"[ERROR] Redis set failed: {e}")
    
    def clear(self):
        """Clear all cache entries"""
        try:
            keys = self.client.keys("rag_cache:*")
            if keys:
                self.client.delete(*keys)
        except Exception as e:
            print(f"[ERROR] Redis clear failed: {e}")


class MemoryAgent:
    """Conversational memory agent - stores and retrieves chat history"""
    
    def __init__(self, hybrid_store: HybridChromaStore, max_history: int = 10):
        """
        Initialize memory agent
        
        Args:
            hybrid_store: Vector store for storing conversation history
            max_history: Maximum number of messages to keep in context
        """
        self.hybrid_store = hybrid_store
        self.max_history = max_history
        self.conversations: Dict[str, List[ConversationMessage]] = {}
    
    def add_message(self, session_id: str, role: str, content: str, metadata: Dict = None):
        """Add message to conversation history"""
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        
        message = ConversationMessage(
            role=role,
            content=content,
            timestamp=time.time(),
            message_id=str(uuid.uuid4()),
            metadata=metadata or {}
        )
        
        self.conversations[session_id].append(message)
        
        # Keep only last max_history messages
        if len(self.conversations[session_id]) > self.max_history:
            self.conversations[session_id] = self.conversations[session_id][-self.max_history:]
    
    def get_conversation_context(self, session_id: str, max_messages: int = 5) -> str:
        """Get recent conversation context"""
        if session_id not in self.conversations:
            return ""
        
        messages = self.conversations[session_id][-max_messages:]
        context_parts = []
        
        for msg in messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            context_parts.append(f"{role_label}: {msg.content}")
        
        return "\n".join(context_parts)
    
    def get_relevant_history(self, session_id: str, query: str, top_k: int = 3) -> List[ConversationMessage]:
        """Get relevant conversation history using semantic search"""
        if session_id not in self.conversations:
            return []
        
        # Simple relevance: return recent messages
        # In production, use vector search on conversation embeddings
        return self.conversations[session_id][-top_k:]
    
    def clear_conversation(self, session_id: str):
        """Clear conversation history"""
        if session_id in self.conversations:
            del self.conversations[session_id]


class FeedbackCollector:
    """Collect and store user feedback for continuous improvement"""
    
    def __init__(self, storage_path: str = "feedback_data.json"):
        """Initialize feedback collector"""
        self.storage_path = Path(storage_path)
        self.feedback_data: List[FeedbackData] = []
        self._load_feedback()
    
    def _load_feedback(self):
        """Load feedback from storage"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self.feedback_data = [FeedbackData(**item) for item in data]
            except Exception as e:
                print(f"[WARNING] Failed to load feedback: {e}")
    
    def _save_feedback(self):
        """Save feedback to storage"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump([asdict(fb) for fb in self.feedback_data], f, indent=2)
        except Exception as e:
            print(f"[ERROR] Failed to save feedback: {e}")
    
    def collect_feedback(
        self,
        query: str,
        answer: str,
        rating: int,
        session_id: str,
        feedback_text: Optional[str] = None
    ):
        """Collect user feedback"""
        feedback = FeedbackData(
            query=query,
            answer=answer,
            rating=rating,
            feedback_text=feedback_text,
            timestamp=time.time(),
            session_id=session_id
        )
        
        self.feedback_data.append(feedback)
        self._save_feedback()
        
        # Log feedback
        print(f"[FEEDBACK] Rating: {rating}/5, Query: {query[:50]}...")
    
    def get_average_rating(self, last_n: int = 100) -> float:
        """Get average rating from recent feedback"""
        if not self.feedback_data:
            return 0.0
        
        recent = self.feedback_data[-last_n:]
        ratings = [fb.rating for fb in recent]
        return sum(ratings) / len(ratings) if ratings else 0.0
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get feedback statistics"""
        if not self.feedback_data:
            return {
                'total_feedback': 0,
                'average_rating': 0.0,
                'rating_distribution': {}
            }
        
        ratings = [fb.rating for fb in self.feedback_data]
        rating_dist = {i: ratings.count(i) for i in range(1, 6)}
        
        return {
            'total_feedback': len(self.feedback_data),
            'average_rating': sum(ratings) / len(ratings),
            'rating_distribution': rating_dist
        }


class MetricsTracker:
    """Track system performance metrics"""
    
    def __init__(self):
        """Initialize metrics tracker"""
        self.metrics: Dict[str, List[float]] = {
            'latency': [],
            'retrieval_time': [],
            'synthesis_time': [],
            'cache_hits': [],
            'cache_misses': [],
            'complexity_distribution': {},
            'query_types': {}
        }
        self.start_time = time.time()
    
    def record_latency(self, latency: float):
        """Record query latency"""
        self.metrics['latency'].append(latency)
    
    def record_retrieval_time(self, time_taken: float):
        """Record retrieval time"""
        self.metrics['retrieval_time'].append(time_taken)
    
    def record_synthesis_time(self, time_taken: float):
        """Record synthesis time"""
        self.metrics['synthesis_time'].append(time_taken)
    
    def record_cache_hit(self):
        """Record cache hit"""
        self.metrics['cache_hits'].append(time.time())
    
    def record_cache_miss(self):
        """Record cache miss"""
        self.metrics['cache_misses'].append(time.time())
    
    def record_complexity(self, complexity: str):
        """Record query complexity"""
        if complexity not in self.metrics['complexity_distribution']:
            self.metrics['complexity_distribution'][complexity] = 0
        self.metrics['complexity_distribution'][complexity] += 1
    
    def record_query_type(self, query_type: str):
        """Record query type"""
        if query_type not in self.metrics['query_types']:
            self.metrics['query_types'][query_type] = 0
        self.metrics['query_types'][query_type] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        stats = {
            'uptime_seconds': time.time() - self.start_time,
            'total_queries': len(self.metrics['latency']),
            'average_latency': self._average(self.metrics['latency']),
            'p50_latency': self._percentile(self.metrics['latency'], 50),
            'p95_latency': self._percentile(self.metrics['latency'], 95),
            'p99_latency': self._percentile(self.metrics['latency'], 99),
            'average_retrieval_time': self._average(self.metrics['retrieval_time']),
            'average_synthesis_time': self._average(self.metrics['synthesis_time']),
            'cache_hit_rate': self._cache_hit_rate(),
            'complexity_distribution': self.metrics['complexity_distribution'],
            'query_types': self.metrics['query_types']
        }
        return stats
    
    def _average(self, values: List[float]) -> float:
        """Calculate average"""
        return sum(values) / len(values) if values else 0.0
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def _cache_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        hits = len(self.metrics['cache_hits'])
        misses = len(self.metrics['cache_misses'])
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0


# Import existing agents - define inline to avoid circular imports
# RouterAgent, RetrieverAgent, ValidatorAgent, QueryDecomposer, SemanticCache
# We'll define simplified versions here or import from agentic_rag_system

# Import existing agents from agentic_rag_system
from kaanoon_test.system_adapters.agentic_rag_system import (
    RouterAgent, RetrieverAgent, ValidatorAgent,
    QueryDecomposer, SemanticCache
)


class AsyncSynthesizerAgent:
    """Async version of Synthesizer Agent"""
    
    def __init__(self, llm_client: AsyncOpenAI, model: Optional[str] = None):
        self.client = llm_client
        self.model = model or Config.NVIDIA_MODEL
    
    async def synthesize_answer_async(
        self,
        query: str,
        context: str,
        query_analysis: QueryAnalysis,
        conversation_context: str = "",
        reasoning_text: str = "",
        has_kaanoon: bool = False
    ) -> str:
        """Async answer synthesis with expert prompts"""
        prompt = self._build_prompt(query, context, query_analysis, conversation_context, reasoning_text, has_kaanoon)
        
        max_tokens = {
            'ultra_simple': 200,
            'simple': 400,
            'moderate': 600,
            'complex': 900,
            'very_complex': 1200
        }.get(query_analysis.complexity, 600)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[ERROR] Async LLM generation failed: {e}")
            return "I encountered an error generating the response. Please try again."
    
    async def synthesize_answer_stream(
        self,
        query: str,
        context: str,
        query_analysis: QueryAnalysis,
        conversation_context: str = "",
        reasoning_text: str = "",
        has_kaanoon: bool = False
    ) -> AsyncGenerator[str, None]:
        """Stream answer generation"""
        prompt = self._build_prompt(query, context, query_analysis, conversation_context, reasoning_text, has_kaanoon)
        
        max_tokens = {
            'ultra_simple': 200,
            'simple': 400,
            'moderate': 600,
            'complex': 900,
            'very_complex': 1200
        }.get(query_analysis.complexity, 600)
        
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=max_tokens,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"[ERROR] Streaming failed: {e}")
            yield "I encountered an error generating the response. Please try again."
    
    def _build_prompt(self, query: str, context: str, analysis: QueryAnalysis, conversation_context: str = "", reasoning_text: str = "", has_kaanoon: bool = False) -> str:
        """Build expert-level legal prompt"""
        query_analysis_dict = {
            'query_type': analysis.query_type,
            'complexity': analysis.complexity,
            'sub_queries': analysis.sub_queries,
            'legal_domains': analysis.legal_domains
        }
        
        if has_kaanoon:
            # Use specialized Kaanoon Q&A prompt
            kaanoon_context = context[:2000]  # Prioritize Kaanoon context
            return build_expert_prompt_for_kaanoon_qa(
                query, kaanoon_context, context[2000:], query_analysis_dict
            )
        else:
            # Use standard expert prompt
            return build_expert_legal_prompt(
                query, context, query_analysis_dict, conversation_context
            ) + f"\n\n{reasoning_text}"


class AdvancedAgenticRAGSystem:
    """Advanced Agentic RAG System with all upgrades"""
    
    def __init__(
        self,
        nvidia_api_key: str = None,
        use_redis: bool = False,
        redis_url: str = "redis://localhost:6379"
    ):
        """Initialize advanced agentic RAG system"""
        print("\n[INIT] Advanced Agentic RAG System - Production Ready")
        
        # Initialize components with correct database path
        db_path = project_root / "chroma_db_hybrid"
        self.hybrid_store = HybridChromaStore(
            persist_directory=str(db_path),
            collection_name="legal_db_hybrid",
            embedding_model="sentence-transformers/all-MiniLM-L6-v2"
        )
        doc_count = self.hybrid_store.count()
        print(f"[OK] Loaded {doc_count:,} documents from database")
        
        if doc_count == 0:
            print("[WARNING] Database is empty! Please rebuild the database using rebuild_database_156K.py")
        
        self.enhanced_retriever = EnhancedRetriever(self.hybrid_store)
        
        # Initialize agents (sync versions for now)
        self.router = RouterAgent()
        self.retriever_agent = RetrieverAgent(self.hybrid_store, self.enhanced_retriever)
        self.validator = ValidatorAgent()
        self.decomposer = QueryDecomposer()
        
        # Initialize async synthesizer
        self.async_synthesizer = AsyncSynthesizerAgent(
            AsyncOpenAI(
                base_url=Config.NVIDIA_BASE_URL,
                api_key=nvidia_api_key or Config.get_nvidia_api_key()
            ),
            model=Config.NVIDIA_MODEL
        )
        
        # Initialize memory agent
        self.memory_agent = MemoryAgent(self.hybrid_store, max_history=10)
        
        # Initialize cache (Redis or in-memory)
        if use_redis and REDIS_AVAILABLE:
            try:
                self.cache = RedisCache(redis_url=redis_url)
                self.cache_type = "redis"
            except Exception as e:
                print(f"[WARNING] Redis init failed, using in-memory cache: {e}")
                self.cache = SemanticCache(max_size=1000)
                self.cache_type = "memory"
        else:
            self.cache = SemanticCache(max_size=1000)
            self.cache_type = "memory"
        
        # Initialize feedback collector
        self.feedback_collector = FeedbackCollector()
        
        # Initialize metrics tracker
        self.metrics = MetricsTracker()
        
        # Import fast lookups
        from .rag_system_adapter_ULTIMATE import UltimateRAGAdapter
        ultimate_adapter = UltimateRAGAdapter()
        self.ipc_lookup = ultimate_adapter.IPC_SECTIONS_FAST_LOOKUP
        self.legal_definitions = ultimate_adapter.LEGAL_DEFINITIONS_FAST_LOOKUP
        
        # Initialize expert components
        self.legal_embedding_enhancer = LegalEmbeddingEnhancer()
        self.legal_reasoning_agent = LegalReasoningAgent()
        self.citation_extractor = CitationExtractor()
        
        print(f"[OK] Advanced Agentic RAG System initialized (Cache: {self.cache_type})")
        print(f"[OK] Expert components loaded: Legal Reasoning, Citation Extraction, Embedding Enhancement")
    
    async def query_async(
        self,
        question: str,
        session_id: str = None,
        target_language: str = None,
        stream: bool = False
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """
        Async query interface with full agentic orchestration
        
        Args:
            question: User question
            session_id: Conversation session ID
            target_language: Target language for response
            stream: Whether to stream response
        
        Returns:
            Dict with answer and metadata, or AsyncGenerator for streaming
        """
        start_time = time.time()
        
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Add user message to memory
        self.memory_agent.add_message(session_id, "user", question)
        
        # Get conversation context
        conversation_context = self.memory_agent.get_conversation_context(session_id, max_messages=3)
        
        # Step 1: Check cache (async if Redis)
        if self.cache_type == "redis":
            cached = await self.cache.get(question)
        else:
            cached = self.cache.get(question)
        
        if cached:
            print("[CACHE HIT] Returning cached result")
            self.metrics.record_cache_hit()
            cached['from_cache'] = True
            cached['latency'] = 0.01
            
            # Add to memory
            self.memory_agent.add_message(session_id, "assistant", cached['answer'])
            
            return cached
        
        self.metrics.record_cache_miss()
        
        # Step 1.5: Greeting/Casual Detection (Skip RAG for greetings)
        if self._is_greeting_or_casual(question):
            casual_response = self._get_casual_response(question)
            latency = time.time() - start_time
            
            result = {
                'answer': casual_response,
                'sources': [],
                'citations': None,
                'citation_validation': None,
                'reasoning_analysis': None,
                'latency': latency,
                'complexity': 'trivial',
                'query_type': 'greeting',
                'retrieval_time': 0,
                'synthesis_time': 0,
                'confidence': 1.0,
                'session_id': session_id,
                'from_cache': False,
                'validation': {'is_greeting': True},
                'detected_language': target_language or 'en'
            }
            
            # Add to memory
            self.memory_agent.add_message(session_id, "assistant", casual_response)
            
            # Don't cache greetings (user-specific)
            print(f"[GREETING] Responded in {latency*1000:.0f}ms (skipped RAG)")
            return result
        
        # Step 2: Route query
        query_analysis = self.router.route_query(question)
        self.metrics.record_complexity(query_analysis.complexity)
        self.metrics.record_query_type(query_analysis.query_type)
        
        print(f"[ROUTER] Complexity: {query_analysis.complexity}, Type: {query_analysis.query_type}")
        
        # Step 3: Fast lookup check
        fast_result = self._check_fast_lookup(question, query_analysis)
        if fast_result:
            if self.cache_type == "redis":
                await self.cache.set(question, fast_result)
            else:
                self.cache.set(question, fast_result)
            
            self.memory_agent.add_message(session_id, "assistant", fast_result['answer'])
            return fast_result
        
        # Step 4: Parallel retrieval (with legal query enhancement)
        retrieval_start = time.time()
        
        # Enhance query with legal-domain expansion
        normalized_query, enhanced_query = self.legal_embedding_enhancer.get_enhanced_query_pair(question)
        
        # Use enhanced query for retrieval
        retrieval_result = self.retriever_agent.retrieve_parallel(enhanced_query, query_analysis)
        retrieval_time = time.time() - retrieval_start
        
        self.metrics.record_retrieval_time(retrieval_time)
        print(f"[RETRIEVER] Retrieved {len(retrieval_result.documents)} docs in {retrieval_time:.2f}s")
        
        # Step 5: Context selection (with authority prioritization)
        context = self._select_best_context(retrieval_result.documents, query_analysis)
        
        # Step 5.5: Legal Reasoning Analysis (NEW)
        reasoning_analysis = self.legal_reasoning_agent.analyze_legal_issue(
            question, retrieval_result.documents, {
                'complexity': query_analysis.complexity,
                'query_type': query_analysis.query_type,
                'sub_queries': query_analysis.sub_queries,
                'legal_domains': query_analysis.legal_domains
            }
        )
        reasoning_text = self.legal_reasoning_agent.format_reasoning_for_prompt(reasoning_analysis)
        
        # Step 6: Query decomposition check
        if query_analysis.requires_decomposition:
            sub_queries = self.decomposer.decompose(question, query_analysis)
            if len(sub_queries) > 1:
                result = await self._process_sub_queries_async(
                    sub_queries, query_analysis, start_time, session_id, conversation_context
                )
                return result
        
        # Step 7: Synthesize answer (async) with expert prompts
        synthesis_start = time.time()
        
        # Check if Kaanoon Q&A is available
        kaanoon_docs = [d for d in retrieval_result.documents if 'kaanoon' in str(d.get('metadata', {}).get('source', '')).lower()]
        has_kaanoon = len(kaanoon_docs) > 0
        
        if stream:
            return self._stream_query_async(question, context, query_analysis, start_time, session_id, conversation_context, reasoning_text, has_kaanoon)
        else:
            answer = await self.async_synthesizer.synthesize_answer_async(
                question, context, query_analysis, conversation_context, reasoning_text, has_kaanoon
            )
            synthesis_time = time.time() - synthesis_start
            self.metrics.record_synthesis_time(synthesis_time)
            
            # Step 7.5: Extract and validate citations (NEW)
            citations = self.citation_extractor.extract_citations(answer)
            citation_validation = self.citation_extractor.validate_citations(citations, retrieval_result.documents)
            
            # Step 7.6: Fix any truncated citations (NEW)
            answer = self.citation_extractor.fix_truncated_citations(answer, retrieval_result.documents)
            
            # Step 8: Validate
            validation = self.validator.validate_response(question, answer, context)
            
            # Step 9: Build response
            total_latency = time.time() - start_time
            self.metrics.record_latency(total_latency)
            
            result = {
                'answer': answer,
                'context': context[:500],
                'sources': self._extract_sources(retrieval_result.documents),
                'citations': citations,  # NEW: Include extracted citations
                'citation_validation': citation_validation,  # NEW: Include validation results
                'reasoning_analysis': reasoning_analysis,  # NEW: Include legal reasoning
                'latency': total_latency,
                'complexity': query_analysis.complexity,
                'query_type': query_analysis.query_type,
                'retrieval_time': retrieval_time,
                'synthesis_time': synthesis_time,
                'retrieval_method': retrieval_result.method,
                'confidence': retrieval_result.confidence,
                'validation': validation,
                'session_id': session_id,
                'from_cache': False
            }
            
            # Cache result
            if self.cache_type == "redis":
                await self.cache.set(question, result)
            else:
                self.cache.set(question, result)
            
            # Add to memory
            self.memory_agent.add_message(session_id, "assistant", answer, result)
            
            return result
    
    async def _stream_query_async(
        self,
        question: str,
        context: str,
        analysis: QueryAnalysis,
        start_time: float,
        session_id: str,
        conversation_context: str,
        reasoning_text: str = "",
        has_kaanoon: bool = False
    ) -> AsyncGenerator[str, None]:
        """Stream query response async"""
        full_answer = ""
        
        async for chunk in self.async_synthesizer.synthesize_answer_stream(
            question, context, analysis, conversation_context, reasoning_text, has_kaanoon
        ):
            full_answer += chunk
            yield chunk
        
        # Extract and validate citations after streaming
        citations = self.citation_extractor.extract_citations(full_answer)
        full_answer = self.citation_extractor.fix_truncated_citations(full_answer, [])
        
        # Validate after streaming
        validation = self.validator.validate_response(question, full_answer, context)
        
        # Cache and store
        result = {
            'answer': full_answer,
            'context': context[:500],
            'citations': citations,
            'latency': time.time() - start_time,
            'complexity': analysis.complexity,
            'validation': validation
        }
        
        if self.cache_type == "redis":
            await self.cache.set(question, result)
        else:
            self.cache.set(question, result)
        
        self.memory_agent.add_message(session_id, "assistant", full_answer, result)
    
    async def _process_sub_queries_async(
        self,
        sub_queries: List[str],
        analysis: QueryAnalysis,
        start_time: float,
        session_id: str,
        conversation_context: str
    ) -> Dict[str, Any]:
        """Process sub-queries in parallel (async)"""
        print(f"[PARALLEL] Processing {len(sub_queries)} sub-queries")
        
        # Process sub-queries concurrently
        tasks = []
        for sub_q in sub_queries:
            sub_analysis = self.router.route_query(sub_q)
            retrieval_result = self.retriever_agent.retrieve_parallel(sub_q, sub_analysis)
            context = self._select_best_context(retrieval_result.documents, sub_analysis)
            
            task = self.async_synthesizer.synthesize_answer_async(
                sub_q, context, sub_analysis, conversation_context
            )
            tasks.append((sub_q, task, retrieval_result.documents))
        
        # Wait for all tasks
        answers = []
        all_sources = []
        
        for i, (sub_q, task, docs) in enumerate(tasks, 1):
            answer = await task
            formatted_answer = f"Q{i}: {sub_q}\n\n{answer}\n"
            answers.append(formatted_answer)
            all_sources.extend(self._extract_sources(docs))
        
        combined_answer = "\n\n".join(answers)
        
        # Validate
        validation = self.validator.validate_response(" ".join(sub_queries), combined_answer, "")
        
        result = {
            'answer': combined_answer,
            'context': f"Processed {len(sub_queries)} sub-queries",
            'sources': all_sources[:10],
            'latency': time.time() - start_time,
            'complexity': analysis.complexity,
            'query_type': 'multi_part',
            'sub_queries_count': len(sub_queries),
            'validation': validation,
            'session_id': session_id,
            'from_cache': False
        }
        
        # Cache and store
        if self.cache_type == "redis":
            await self.cache.set(" ".join(sub_queries), result)
        else:
            self.cache.set(" ".join(sub_queries), result)
        
        self.memory_agent.add_message(session_id, "assistant", combined_answer, result)
        
        return result
    
    def collect_feedback(
        self,
        query: str,
        answer: str,
        rating: int,
        session_id: str,
        feedback_text: Optional[str] = None
    ):
        """Collect user feedback"""
        self.feedback_collector.collect_feedback(query, answer, rating, session_id, feedback_text)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get system metrics"""
        return self.metrics.get_stats()
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get feedback statistics"""
        return self.feedback_collector.get_feedback_stats()
    
    def clear_conversation(self, session_id: str):
        """Clear conversation history"""
        self.memory_agent.clear_conversation(session_id)
    
    # Import helper methods from base class
    def _check_fast_lookup(self, question: str, analysis: QueryAnalysis) -> Optional[Dict]:
        """Check fast lookup dictionaries"""
        question_upper = question.upper()
        
        # IPC section lookup
        ipc_match = re.search(r'\b(?:IPC|Section)\s*(?:Section\s*)?(\d{3}[A-Z]?)\b', question, re.IGNORECASE)
        if ipc_match:
            section = ipc_match.group(1)
            if section in self.ipc_lookup:
                ipc_data = self.ipc_lookup[section]
                answer = f"{ipc_data['title']}\n\n{ipc_data['answer']}\n\nPenalty: {ipc_data['penalty']}"
                if ipc_data.get('related_sections'):
                    answer += f"\n\nRelated Sections: {', '.join(ipc_data['related_sections'])}"
                
                return {
                    'answer': answer,
                    'context': f"Fast lookup for IPC Section {section}",
                    'sources': [{'rank': 1, 'score': 1.0, 'source': 'IPC Fast Lookup', 'category': 'IPC'}],
                    'latency': 0.01,
                    'complexity': 'ultra_simple',
                    'query_type': 'ipc_section',
                    'retrieval_method': 'fast_lookup',
                    'confidence': 1.0,
                    'from_cache': False
                }
        
        # Definition lookup
        acronyms = re.findall(r'\b([A-Z]{2,6})\b', question_upper)
        non_acronyms = {'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HER', 'WAS', 'ONE', 'OUR', 'OUT'}
        filtered_acronyms = [a for a in acronyms if a not in non_acronyms]
        
        for acronym in filtered_acronyms:
            if acronym in self.legal_definitions:
                def_data = self.legal_definitions[acronym]
                answer = f"{acronym} stands for {def_data['full_form']}.\n\n{def_data['definition']}"
                if def_data.get('year') and def_data['year'] != 'N/A':
                    answer += f"\n\nEnacted/Established: {def_data['year']}"
                if def_data.get('key_sections'):
                    answer += f"\n\nKey Sections/Provisions: {', '.join(def_data['key_sections'])}"
                
                return {
                    'answer': answer,
                    'context': f"Fast lookup for {acronym} definition",
                    'sources': [{'rank': 1, 'score': 1.0, 'source': 'Legal Definitions Fast Lookup', 'category': 'Definition'}],
                    'latency': 0.01,
                    'complexity': 'ultra_simple',
                    'query_type': 'definition',
                    'retrieval_method': 'fast_lookup',
                    'confidence': 1.0,
                    'from_cache': False
                }
        
        return None
    
    def _select_best_context(self, documents: List[Dict], analysis: QueryAnalysis) -> str:
        """
        Select and format best context with authority-based prioritization
        
        Authority Hierarchy:
        1. Supreme Court cases (highest authority)
        2. High Court judgments (high authority)
        3. Kaanoon.com expert Q&As (verified expert answers)
        4. Statutory provisions (Acts, Sections, Rules)
        5. Case studies (illustrative examples)
        6. News articles / Wikipedia (lowest priority)
        """
        if not documents:
            return ""
        
        # Group documents by authority level
        sc_cases = []
        hc_cases = []
        kaanoon_qa = []
        statutes = []
        case_studies = []
        other_docs = []
        
        for doc in documents:
            metadata = doc.get('metadata', {})
            source = str(metadata.get('source', '')).lower()
            court = str(metadata.get('court', '')).lower()
            category = str(metadata.get('category', '')).lower()
            text = str(doc.get('text', doc.get('document', ''))).lower()
            
            # Supreme Court cases (highest priority)
            if 'supreme court' in court or 'sc' in court or 'apex court' in text:
                sc_cases.append(doc)
            # High Court cases
            elif 'high court' in court or 'hc' in court:
                hc_cases.append(doc)
            # Kaanoon expert Q&As
            elif 'kaanoon' in source or 'kaanoon_qa' in source:
                kaanoon_qa.append(doc)
            # Statutory provisions (contains section numbers, acts)
            elif any(keyword in text for keyword in ['section', 'article', 'order', 'rule', 'act']) or \
                 any(keyword in str(metadata).lower() for keyword in ['section', 'article', 'act']):
                statutes.append(doc)
            # Case studies
            elif 'case study' in category or 'case_study' in source or 'case studies' in text[:200]:
                case_studies.append(doc)
            # Everything else
            else:
                other_docs.append(doc)
        
        # Prioritize: SC > HC > Kaanoon > Statutes > Case Studies > Others
        # Determine max docs based on complexity
        max_docs = {
            'ultra_simple': 1,
            'simple': 3,
            'moderate': 5,
            'complex': 8,
            'very_complex': 10
        }.get(analysis.complexity, 5)
        
        # Build prioritized list
        prioritized = []
        prioritized.extend(sc_cases[:2])  # Top 2 Supreme Court cases
        prioritized.extend(hc_cases[:2])  # Top 2 High Court cases
        prioritized.extend(kaanoon_qa[:2])  # Top 2 Kaanoon Q&As
        prioritized.extend(statutes[:2])  # Top 2 statutory provisions
        
        # Fill remaining slots with case studies and others
        remaining = max_docs - len(prioritized)
        if remaining > 0:
            prioritized.extend(case_studies[:min(2, remaining)])
            remaining -= min(2, len(case_studies))
        if remaining > 0:
            prioritized.extend(other_docs[:remaining])
        
        # If still not enough, add more from any category
        if len(prioritized) < max_docs:
            all_docs = sc_cases + hc_cases + kaanoon_qa + statutes + case_studies + other_docs
            seen_ids = {id(d) for d in prioritized}
            for doc in all_docs:
                if id(doc) not in seen_ids and len(prioritized) < max_docs:
                    prioritized.append(doc)
                    seen_ids.add(id(doc))
        
        # Format context with authority labels
        max_chars_per_doc = {
            'ultra_simple': 200,
            'simple': 400,
            'moderate': 600,
            'complex': 800,
            'very_complex': 1000
        }.get(analysis.complexity, 600)
        
        context_parts = []
        for i, doc in enumerate(prioritized[:max_docs], 1):
            text = doc.get('text', doc.get('document', ''))
            if not text:
                continue
            
            # Determine authority label
            metadata = doc.get('metadata', {})
            source = str(metadata.get('source', '')).lower()
            court = str(metadata.get('court', '')).lower()
            
            if 'supreme court' in court or 'sc' in court:
                label = f"[Supreme Court Case {i}]"
            elif 'high court' in court or 'hc' in court:
                label = f"[High Court Judgment {i}]"
            elif 'kaanoon' in source:
                label = f"[Expert Q&A {i}]"
            elif any(keyword in text.lower()[:200] for keyword in ['section', 'article', 'order', 'rule']):
                label = f"[Statutory Provision {i}]"
            else:
                label = f"[Legal Source {i}]"
            
            truncated_text = text[:max_chars_per_doc]
            if len(text) > max_chars_per_doc:
                truncated_text = text[:max_chars_per_doc].rsplit(' ', 1)[0].strip()
                if not truncated_text:
                    truncated_text = text[:max_chars_per_doc]
                truncated_text += '...'
            context_parts.append(f"{label}\n{truncated_text}")

        return "\n\n".join(context_parts)
    
    def _get_casual_response(self, question: str) -> str:
        """Generate natural response for greetings/casual conversation"""
        question_lower = question.lower().strip()
        
        # Map greetings to responses
        if any(g in question_lower for g in ['hi', 'hello', 'hey', 'hii', 'helo', 'heya', 'hell']):
            return "Hello! I'm your legal assistant. How can I help you with your legal query today?"
        elif 'good morning' in question_lower:
            return "Good morning! I'm here to assist you with legal questions. What would you like to know?"
        elif 'good afternoon' in question_lower:
            return "Good afternoon! How can I help you with your legal concerns today?"
        elif 'good evening' in question_lower:
            return "Good evening! I'm ready to assist you with any legal questions you have."
        elif 'good night' in question_lower:
            return "Good night! Feel free to return anytime you need legal assistance."
        elif any(g in question_lower for g in ['thanks', 'thank you']):
            return "You're welcome! If you have any more legal questions, I'm here to help."
        elif any(g in question_lower for g in ['bye', 'goodbye']):
            return "Goodbye! Don't hesitate to return if you need legal assistance in the future."
        elif 'how are you' in question_lower:
            return "I'm functioning well, thank you! I'm here to help you with legal questions. What would you like to know?"
        elif any(g in question_lower for g in ['namaste', 'namaskar', 'pranam']):
            return "Namaste! I'm your legal assistant. How may I assist you with your legal concerns today?"
        else:
            return "Hello! I'm your AI legal assistant. Please ask me any legal question and I'll be happy to help."
    
    def _extract_sources(self, documents: List[Dict]) -> List[Dict]:
        """Extract source metadata"""
        sources = []
        for i, doc in enumerate(documents[:5], 1):
            metadata = doc.get('metadata', {})
            sources.append({
                'rank': i,
                'score': doc.get('score', 0),
                'source': metadata.get('source', 'Unknown'),
                'category': metadata.get('category', 'Unknown')
            })
        return sources


# Factory function
def create_advanced_agentic_rag_system(
    nvidia_api_key: str = None,
    use_redis: bool = False,
    redis_url: str = "redis://localhost:6379"
) -> AdvancedAgenticRAGSystem:
    """Create advanced agentic RAG system"""
    return AdvancedAgenticRAGSystem(
        nvidia_api_key=nvidia_api_key,
        use_redis=use_redis,
        redis_url=redis_url
    )

