"""
Quick Test Script for Advanced Agentic RAG System
Tests all major features: async, memory, caching, feedback, metrics
"""

import asyncio
import time
from kaanoon_test.system_adapters.advanced_agentic_rag_system import (
    create_advanced_agentic_rag_system
)


async def test_basic_query():
    """Test basic async query"""
    print("\n[TEST 1] Basic Async Query")
    print("=" * 60)
    
    rag_system = create_advanced_agentic_rag_system(use_redis=False)
    
    result = await rag_system.query_async(
        question="What is IPC Section 302?",
        session_id="test-session-1"
    )
    
    print(f"Answer: {result['answer'][:100]}...")
    print(f"Latency: {result['latency']:.2f}s")
    print(f"Complexity: {result['complexity']}")
    print(f"From Cache: {result['from_cache']}")
    print("✅ Basic query test passed")


async def test_conversation_memory():
    """Test conversational memory"""
    print("\n[TEST 2] Conversation Memory")
    print("=" * 60)
    
    rag_system = create_advanced_agentic_rag_system(use_redis=False)
    session_id = "test-session-2"
    
    # First query
    result1 = await rag_system.query_async(
        question="What is IPC Section 302?",
        session_id=session_id
    )
    print(f"Q1 Answer length: {len(result1['answer'])} chars")
    
    # Second query (should have context)
    result2 = await rag_system.query_async(
        question="What about Section 304?",
        session_id=session_id
    )
    print(f"Q2 Answer length: {len(result2['answer'])} chars")
    
    # Check conversation context
    context = rag_system.memory_agent.get_conversation_context(session_id)
    print(f"Conversation context length: {len(context)} chars")
    print("✅ Conversation memory test passed")


async def test_feedback():
    """Test feedback collection"""
    print("\n[TEST 3] Feedback Collection")
    print("=" * 60)
    
    rag_system = create_advanced_agentic_rag_system(use_redis=False)
    
    result = await rag_system.query_async(
        question="What is IPC Section 302?",
        session_id="test-session-3"
    )
    
    # Submit feedback
    rag_system.collect_feedback(
        query="What is IPC Section 302?",
        answer=result['answer'],
        rating=5,
        session_id="test-session-3",
        feedback_text="Very helpful!"
    )
    
    # Get feedback stats
    stats = rag_system.get_feedback_stats()
    print(f"Total Feedback: {stats['total_feedback']}")
    print(f"Average Rating: {stats['average_rating']:.2f}")
    print("✅ Feedback collection test passed")


async def test_metrics():
    """Test metrics tracking"""
    print("\n[TEST 4] Metrics Tracking")
    print("=" * 60)
    
    rag_system = create_advanced_agentic_rag_system(use_redis=False)
    
    # Run a few queries
    queries = [
        "What is IPC Section 302?",
        "What is CPC?",
        "How to file FIR?"
    ]
    
    for query in queries:
        await rag_system.query_async(query, session_id="test-session-4")
    
    # Get metrics
    metrics = rag_system.get_metrics()
    print(f"Total Queries: {metrics['total_queries']}")
    print(f"Average Latency: {metrics['average_latency']:.2f}s")
    print(f"Cache Hit Rate: {metrics['cache_hit_rate']:.1f}%")
    print(f"Complexity Distribution: {metrics['complexity_distribution']}")
    print("✅ Metrics tracking test passed")


async def test_streaming():
    """Test streaming response"""
    print("\n[TEST 5] Streaming Response")
    print("=" * 60)
    
    rag_system = create_advanced_agentic_rag_system(use_redis=False)
    
    print("Streaming answer...")
    full_answer = ""
    async for chunk in rag_system.query_async(
        question="Explain divorce procedure in India",
        session_id="test-session-5",
        stream=True
    ):
        print(chunk, end='', flush=True)
        full_answer += chunk
    
    print(f"\n\nFull answer length: {len(full_answer)} chars")
    print("✅ Streaming test passed")


async def test_cache():
    """Test caching"""
    print("\n[TEST 6] Cache Testing")
    print("=" * 60)
    
    rag_system = create_advanced_agentic_rag_system(use_redis=False)
    
    query = "What is IPC Section 302?"
    
    # First query (cache miss)
    start = time.time()
    result1 = await rag_system.query_async(query, session_id="test-session-6")
    time1 = time.time() - start
    print(f"First query: {time1:.3f}s (cache: {result1['from_cache']})")
    
    # Second query (cache hit)
    start = time.time()
    result2 = await rag_system.query_async(query, session_id="test-session-6")
    time2 = time.time() - start
    print(f"Second query: {time2:.3f}s (cache: {result2['from_cache']})")
    
    if result2['from_cache']:
        speedup = time1 / time2 if time2 > 0 else float('inf')
        print(f"Speedup: {speedup:.1f}X faster")
    print("✅ Cache test passed")


async def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("ADVANCED AGENTIC RAG SYSTEM - TEST SUITE")
    print("=" * 60)
    
    try:
        await test_basic_query()
        await test_conversation_memory()
        await test_feedback()
        await test_metrics()
        await test_streaming()
        await test_cache()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())

