"""
Test file for Dynamic Reasoning Explainer

This allows you to test the generator + reasoning chain WITHOUT going through
the full pipeline (query analyzer → information gatherer → etc.)

Usage:
    python test_reasoning.py

This will:
1. Load mock data (simulating what earlier nodes would provide)
2. Run the generator
3. Generate dynamic reasoning
4. Display results in a readable format
"""

import sys
import os
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from nodes.reasoning_explainer import (
    DynamicReasoningExplainer,
    create_case_summary
)
from nodes.generator import generate_response
from typing import Dict, List


# ============================================================================
# MOCK DATA - Simulates what earlier nodes would provide
# ============================================================================

def get_mock_state() -> Dict:
    """
    Get mock state that simulates output from:
    - Query Analyzer (user_intent, info_collected)
    - Information Gatherer (info_collected complete)
    - Retriever (retrieved_chunks with scores)
    """
    
    # Simulate a divorce case
    mock_state = {
        "query": "I want to file for divorce due to cruelty and we have been separated for 2 years",
        "user_intent": "seeking divorce on grounds of cruelty",
        "user_gender": "female",
        
        # Simulated collected information
        "info_collected": {
            "user_gender": "female",
            "marriage_date": "2018",
            "marriage_duration": "5 years",
            "separation_duration": "2 years",
            "abuse_type": "mental and emotional abuse",
            "children": "one daughter aged 3",
            "reason_for_divorce": "husband's cruel behavior and mental torture"
        },
        
        # Simulated retrieved precedents (you can replace with real chunks)
        "retrieved_chunks": [
            {
                "content": "In cases of cruelty under Section 13(1)(ia) of the Hindu Marriage Act, 1955, mental cruelty is sufficient ground for divorce. The Supreme Court has held that cruelty need not be physical; mental torture and harassment also constitute cruelty. The court will consider the overall conduct and its impact on the petitioner's mental health.",
                "score": 0.89,
                "metadata": {
                    "title": "Divorce on grounds of mental cruelty - Supreme Court precedent",
                    "category": "divorce",
                    "url": "https://example.com/precedent1",
                    "parent_id": 123
                }
            },
            {
                "content": "When parties have been living separately for more than one year, it strengthens the case for divorce under Section 13(1)(ia). The court considers separation as evidence of irretrievable breakdown of marriage. In V. Bhagat v. D. Bhagat (1994), the Supreme Court held that prolonged separation coupled with cruelty is a strong ground for divorce.",
                "score": 0.85,
                "metadata": {
                    "title": "Separation as evidence of marriage breakdown",
                    "category": "divorce",
                    "url": "https://example.com/precedent2",
                    "parent_id": 124
                }
            },
            {
                "content": "In divorce cases involving minor children, the court's primary consideration is the child's welfare. Under the Guardians and Wards Act, 1890, custody is decided based on the best interests of the child. The court may grant custody to either parent while ensuring visitation rights to the other parent.",
                "score": 0.78,
                "metadata": {
                    "title": "Child custody in divorce proceedings",
                    "category": "child_custody",
                    "url": "https://example.com/precedent3",
                    "parent_id": 125
                }
            },
            {
                "content": "Section 125 of CrPC provides for maintenance to wife and children. Even during divorce proceedings, the wife can claim interim maintenance. The amount is determined based on the husband's income and the wife's needs.",
                "score": 0.72,
                "metadata": {
                    "title": "Maintenance rights during divorce",
                    "category": "maintenance",
                    "url": "https://example.com/precedent4",
                    "parent_id": 126
                }
            },
            {
                "content": "Evidence of cruelty must be substantiated with specific instances and dates. Documentary evidence such as medical records, witness testimonies, and communication records strengthen the case. The petitioner should maintain a detailed record of instances of cruelty.",
                "score": 0.68,
                "metadata": {
                    "title": "Evidence requirements for cruelty cases",
                    "category": "divorce",
                    "url": "https://example.com/precedent5",
                    "parent_id": 127
                }
            }
        ],
        
        # Other required fields
        "messages": [],
        "conversation_id": "test_conv_001",
        "include_reasoning": True,
        "include_prediction": False,
        "sources": []
    }
    
    return mock_state


def get_alternative_mock_state() -> Dict:
    """
    Alternative test case - domestic violence
    """
    return {
        "query": "My husband beats me and threatens me. I want protection.",
        "user_intent": "seeking protection from domestic violence",
        "user_gender": "female",
        
        "info_collected": {
            "user_gender": "female",
            "marriage_date": "2020",
            "abuse_type": "physical violence and threats",
            "recent_incident": "beaten last week, injuries documented",
            "safety_concern": "high - fears for life",
            "police_complaint": "not yet filed"
        },
        
        "retrieved_chunks": [
            {
                "content": "The Protection of Women from Domestic Violence Act, 2005 (PWDVA) provides comprehensive protection to women facing domestic violence. Under Section 12, a woman can file a complaint and seek protection orders, residence orders, monetary relief, and custody orders. The Act has a broad definition of domestic violence including physical, sexual, verbal, emotional, and economic abuse.",
                "score": 0.92,
                "metadata": {
                    "title": "Protection of Women from Domestic Violence Act - Overview",
                    "category": "domestic_violence",
                    "url": "https://example.com/dv1"
                }
            },
            {
                "content": "Section 498A of IPC criminalizes cruelty by husband or his relatives. This is a cognizable, non-bailable offense. The woman should immediately file an FIR at the nearest police station. Medical evidence of injuries should be preserved.",
                "score": 0.88,
                "metadata": {
                    "title": "IPC Section 498A - Cruelty by husband",
                    "category": "domestic_violence",
                    "url": "https://example.com/dv2"
                }
            },
            {
                "content": "In urgent cases, the court can pass ex-parte protection orders under PWDVA. The woman need not wait for full trial. Protection Officers are available at district level to assist women in filing complaints and accessing shelters.",
                "score": 0.83,
                "metadata": {
                    "title": "Emergency protection measures",
                    "category": "domestic_violence",
                    "url": "https://example.com/dv3"
                }
            }
        ],
        
        "messages": [],
        "conversation_id": "test_conv_002",
        "include_reasoning": True,
        "include_prediction": False,
        "sources": []
    }


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def test_generator_and_reasoning(state: Dict, test_name: str = "Test Case"):
    """
    Test the generator and reasoning explainer with mock state.
    """
    print("\n" + "="*80)
    print(f"🧪 {test_name}")
    print("="*80)
    
    print("\n📋 Case Information:")
    print(f"   Intent: {state['user_intent']}")
    print(f"   Gender: {state['user_gender']}")
    print(f"   Info Collected: {len(state['info_collected'])} items")
    print(f"   Retrieved Chunks: {len(state['retrieved_chunks'])} precedents")
    
    # Step 1: Generate Response
    print("\n🤖 Generating legal response...")
    result = generate_response(state)
    
    response_text = result.get("response", "")
    print(f"\n✅ Response Generated ({len(response_text)} characters)")
    print("\n" + "─"*80)
    print("GENERATED RESPONSE:")
    print("─"*80)
    print(response_text[:500] + "..." if len(response_text) > 500 else response_text)
    print("─"*80)
    
    # Step 2: Generate Dynamic Reasoning
    print("\n🧠 Generating dynamic reasoning chain...")
    
    explainer = DynamicReasoningExplainer()
    
    reasoning_steps = explainer.generate_reasoning_chain(
        user_intent=state["user_intent"],
        info_collected=state["info_collected"],
        response=response_text,
        retrieved_chunks=state["retrieved_chunks"]
    )
    
    print(f"\n✅ Generated {len(reasoning_steps)} reasoning steps")
    
    # Display reasoning
    print("\n" + "="*80)
    print("REASONING CHAIN")
    print("="*80)
    
    for step in reasoning_steps:
        print(f"\n📍 Step {step.step_number}: {step.title}")
        print(f"   Type: {step.step_type}")
        print(f"   Confidence: {step.confidence:.0%}")
        print(f"\n   Explanation:")
        print(f"   {step.explanation}")
        
        if step.legal_provisions:
            print(f"\n   Legal Provisions:")
            for provision in step.legal_provisions:
                print(f"   • {provision}")
        
        if step.supporting_sources:
            print(f"\n   Supporting Sources:")
            for source in step.supporting_sources:
                print(f"   • {source}")
        
        if step.response_excerpt:
            print(f"\n   Response Excerpt:")
            print(f"   \"{step.response_excerpt[:150]}...\"")
        
        print("   " + "─"*76)
    
    # Step 3: Analyze Precedent Usage
    print("\n📊 Analyzing precedent usage...")
    
    case_summary = create_case_summary(state["info_collected"], state["user_intent"])
    
    precedent_usages = explainer.generate_all_precedent_explanations(
        case_summary=case_summary,
        retrieved_chunks=state["retrieved_chunks"],
        response=response_text
    )
    
    print(f"\n✅ Analyzed {len(precedent_usages)} precedents")
    
    # Display precedent analysis
    print("\n" + "="*80)
    print("PRECEDENT USAGE ANALYSIS")
    print("="*80)
    
    for usage in precedent_usages:
        print(f"\n📚 {usage.precedent_title}")
        print(f"   Retrieval Score: {usage.retrieval_score:.0%}")
        print(f"   Usage Score: {usage.usage_score:.0%} ⭐")
        
        print(f"\n   ✅ Matching Factors:")
        for factor in usage.matching_factors:
            print(f"      • {factor}")
        
        if usage.different_factors:
            print(f"\n   ⚠️  Different Factors:")
            for factor in usage.different_factors:
                print(f"      • {factor}")
        
        print(f"\n   💡 How It Influenced Response:")
        print(f"      {usage.how_it_influenced_response}")
        
        if usage.response_sections_influenced:
            print(f"\n   📝 Response Sections Influenced:")
            for section in usage.response_sections_influenced:
                print(f"      • {section}")
        
        print("   " + "─"*76)
    
    # Save results
    save_test_results(state, response_text, reasoning_steps, precedent_usages, test_name)
    
    print("\n" + "="*80)
    print("✅ Test Complete!")
    print("="*80)


def save_test_results(state, response, reasoning_steps, precedent_usages, test_name):
    """Save test results to JSON file for inspection."""
    
    results = {
        "test_name": test_name,
        "case_info": {
            "intent": state["user_intent"],
            "info_collected": state["info_collected"]
        },
        "response": response,
        "reasoning_steps": [
            {
                "step_number": step.step_number,
                "title": step.title,
                "type": step.step_type,
                "explanation": step.explanation,
                "confidence": step.confidence,
                "supporting_sources": step.supporting_sources,
                "legal_provisions": step.legal_provisions,
                "response_excerpt": step.response_excerpt
            }
            for step in reasoning_steps
        ],
        "precedent_usage": [
            {
                "title": usage.precedent_title,
                "retrieval_score": usage.retrieval_score,
                "usage_score": usage.usage_score,
                "matching_factors": usage.matching_factors,
                "different_factors": usage.different_factors,
                "influence": usage.how_it_influenced_response,
                "sections_influenced": usage.response_sections_influenced
            }
            for usage in precedent_usages
        ]
    }
    
    output_file = f"test_results_{test_name.lower().replace(' ', '_')}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to: {output_file}")


def run_all_tests():
    """Run all test cases."""
    print("\n" + "="*80)
    print("🚀 STARTING DYNAMIC REASONING TESTS")
    print("="*80)
    
    # Test Case 1: Divorce
    test_generator_and_reasoning(
        get_mock_state(),
        "Divorce Case - Mental Cruelty"
    )
    
    # Test Case 2: Domestic Violence
    test_generator_and_reasoning(
        get_alternative_mock_state(),
        "Domestic Violence Case"
    )
    
    print("\n" + "="*80)
    print("🎉 ALL TESTS COMPLETED")
    print("="*80)


def run_single_test(case_type: str = "divorce"):
    """Run a single test case."""
    if case_type == "divorce":
        test_generator_and_reasoning(
            get_mock_state(),
            "Divorce Case - Mental Cruelty"
        )
    elif case_type == "dv":
        test_generator_and_reasoning(
            get_alternative_mock_state(),
            "Domestic Violence Case"
        )
    else:
        print(f"Unknown case type: {case_type}")
        print("Available types: 'divorce', 'dv'")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Dynamic Reasoning Explainer")
    parser.add_argument(
        "--case",
        type=str,
        choices=["divorce", "dv", "all"],
        default="all",
        help="Which test case to run"
    )
    
    args = parser.parse_args()
    
    if args.case == "all":
        run_all_tests()
    else:
        run_single_test(args.case)