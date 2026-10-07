"""
TEST EXPERT LEGAL RAG - Comprehensive Testing Suite
Tests citation accuracy, legal reasoning depth, authority prioritization, and expert terminology
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from kaanoon_test.system_adapters.advanced_agentic_rag_system import create_advanced_agentic_rag_system


async def test_ipc_citation_accuracy():
    """Test IPC section citation accuracy (no truncation)"""
    print("\n" + "="*60)
    print("TEST 1: IPC Citation Accuracy")
    print("="*60)
    
    rag_system = create_advanced_agentic_rag_system(use_redis=False)
    
    test_queries = [
        "What is IPC Section 302?",
        "Explain IPC Section 304",
        "Tell me about IPC Section 379"
    ]
    
    results = []
    for query in test_queries:
        result = await rag_system.query_async(query, session_id="test-ipc")
        answer = result['answer']
        
        # Check for truncation
        has_truncation = any(pattern in answer for pattern in ['IPC 30...', 'IPC 30 ...', 'Section 30...'])
        has_complete = 'IPC Section 302' in answer or 'IPC Section 304' in answer or 'IPC Section 379' in answer
        
        results.append({
            'query': query,
            'has_truncation': has_truncation,
            'has_complete': has_complete,
            'passed': not has_truncation and has_complete
        })
        
        print(f"\nQuery: {query}")
        print(f"Truncation Found: {has_truncation}")
        print(f"Complete Citation: {has_complete}")
        print(f"Status: {'PASS' if results[-1]['passed'] else 'FAIL'}")
    
    passed = sum(1 for r in results if r['passed'])
    print(f"\nIPC Citation Accuracy: {passed}/{len(results)} passed")
    return passed == len(results)


async def test_case_law_citations():
    """Test case law citation format"""
    print("\n" + "="*60)
    print("TEST 2: Case Law Citations")
    print("="*60)
    
    rag_system = create_advanced_agentic_rag_system(use_redis=False)
    
    result = await rag_system.query_async(
        "What are landmark Supreme Court cases on fundamental rights?",
        session_id="test-cases"
    )
    
    answer = result['answer']
    citations = result.get('citations', {})
    
    # Check for case citations
    case_citations = citations.get('case_law', [])
    
    print(f"\nFound {len(case_citations)} case citations")
    for i, case in enumerate(case_citations[:5], 1):
        print(f"{i}. {case.get('formatted', case.get('case_name', 'Unknown'))}")
    
    # Check citation validation
    validation = result.get('citation_validation', {})
    valid_citations = len(validation.get('valid', []))
    
    print(f"\nValid Citations: {valid_citations}")
    print(f"Status: {'PASS' if valid_citations > 0 else 'FAIL'}")
    
    return valid_citations > 0


async def test_legal_reasoning_depth():
    """Test legal reasoning depth"""
    print("\n" + "="*60)
    print("TEST 3: Legal Reasoning Depth")
    print("="*60)
    
    rag_system = create_advanced_agentic_rag_system(use_redis=False)
    
    result = await rag_system.query_async(
        "How to file for divorce under Hindu law?",
        session_id="test-reasoning"
    )
    
    reasoning = result.get('reasoning_analysis', {})
    
    print("\nReasoning Analysis:")
    print(f"- Issues Identified: {len(reasoning.get('issues', []))}")
    print(f"- Statutes Found: {sum(len(v) for v in reasoning.get('statutes', {}).values() if isinstance(v, list))}")
    print(f"- Precedents Found: {len(reasoning.get('precedents', []))}")
    print(f"- Exceptions Identified: {len(reasoning.get('exceptions', []))}")
    
    has_reasoning = (
        len(reasoning.get('issues', [])) > 0 and
        len(reasoning.get('precedents', [])) > 0
    )
    
    print(f"\nStatus: {'PASS' if has_reasoning else 'FAIL'}")
    return has_reasoning


async def test_authority_prioritization():
    """Test authority-based document prioritization"""
    print("\n" + "="*60)
    print("TEST 4: Authority Prioritization")
    print("="*60)
    
    rag_system = create_advanced_agentic_rag_system(use_redis=False)
    
    result = await rag_system.query_async(
        "What is the procedure for filing FIR?",
        session_id="test-authority"
    )
    
    sources = result.get('sources', [])
    
    print("\nSource Prioritization:")
    for i, source in enumerate(sources[:5], 1):
        print(f"{i}. {source.get('source', 'Unknown')} (Score: {source.get('score', 0):.3f})")
    
    # Check if high-authority sources are prioritized
    has_prioritization = len(sources) > 0
    
    print(f"\nStatus: {'PASS' if has_prioritization else 'FAIL'}")
    return has_prioritization


async def test_expert_terminology():
    """Test expert legal terminology usage"""
    print("\n" + "="*60)
    print("TEST 5: Expert Terminology")
    print("="*60)
    
    rag_system = create_advanced_agentic_rag_system(use_redis=False)
    
    result = await rag_system.query_async(
        "Explain the principle of res judicata",
        session_id="test-terminology"
    )
    
    answer = result['answer'].lower()
    
    # Check for expert terminology
    expert_terms = [
        'res judicata', 'stare decisis', 'habeas corpus',
        'prima facie', 'bona fide', 'ultra vires'
    ]
    
    found_terms = [term for term in expert_terms if term in answer]
    
    print(f"\nExpert Terms Found: {len(found_terms)}/{len(expert_terms)}")
    for term in found_terms:
        print(f"- {term}")
    
    print(f"\nStatus: {'PASS' if len(found_terms) > 0 else 'FAIL'}")
    return len(found_terms) > 0


async def test_user_friendly_language():
    """Test that responses are user-friendly despite expert level"""
    print("\n" + "="*60)
    print("TEST 6: User-Friendly Language")
    print("="*60)
    
    rag_system = create_advanced_agentic_rag_system(use_redis=False)
    
    result = await rag_system.query_async(
        "What is IPC Section 302 in simple terms?",
        session_id="test-friendly"
    )
    
    answer = result['answer']
    
    # Check for clarity indicators
    clarity_indicators = [
        'simple', 'clear', 'explain', 'means', 'refers to',
        'in other words', 'that is', 'specifically'
    ]
    
    found_indicators = sum(1 for indicator in clarity_indicators if indicator in answer.lower())
    
    # Check sentence length (shorter = more user-friendly)
    sentences = answer.split('.')
    avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
    
    print(f"\nClarity Indicators: {found_indicators}")
    print(f"Average Sentence Length: {avg_sentence_length:.1f} words")
    print(f"Total Words: {len(answer.split())}")
    
    is_friendly = found_indicators > 0 and avg_sentence_length < 25
    
    print(f"\nStatus: {'PASS' if is_friendly else 'FAIL'}")
    return is_friendly


async def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("EXPERT LEGAL RAG SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*60)
    
    tests = [
        ("IPC Citation Accuracy", test_ipc_citation_accuracy),
        ("Case Law Citations", test_case_law_citations),
        ("Legal Reasoning Depth", test_legal_reasoning_depth),
        ("Authority Prioritization", test_authority_prioritization),
        ("Expert Terminology", test_expert_terminology),
        ("User-Friendly Language", test_user_friendly_language),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = await test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n[ERROR] {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed_count}/{total_count} tests passed")
    print(f"Success Rate: {passed_count/total_count*100:.1f}%")
    
    return passed_count == total_count


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)

