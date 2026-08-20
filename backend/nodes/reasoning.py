"""
Reasoning Analysis Node - Separate from Generator

This node runs AFTER the generator creates the response.
It analyzes the generated response to create reasoning steps and precedent explanations.

Benefits:
- Complete separation: reasoning can't contaminate response
- Clean architecture: each node has one job
- Easy debugging: can see exactly what each node produces
- Optional: can skip reasoning if needed
"""

from typing import Dict
import logging
from nodes.reasoning_explainer import (
    DynamicReasoningExplainer,
    create_case_summary
)
from state import FamilyLawState

logger = logging.getLogger(__name__)


def analyze_reasoning(state: FamilyLawState) -> Dict:
    """
    Analyze the generated response to create reasoning steps and precedent explanations.
    
    This runs AFTER generate_response, so the response is already complete and clean.
    
    Input (from state):
    - response: The generated legal advice (clean)
    - user_intent: What the user wants
    - info_collected: Case information
    - retrieved_chunks: Precedents used
    
    Output (added to state):
    - reasoning_steps: List of reasoning step dicts
    - precedent_explanations: List of precedent usage dicts
    """
    
    logger.info("🧠 === ANALYZING REASONING (SEPARATE NODE) ===")
    
    # Get inputs from state
    response = state.get("response", "")
    user_intent = state.get("user_intent", "")
    info_collected = state.get("info_collected", {})
    retrieved_chunks = state.get("retrieved_chunks", [])
    include_reasoning = state.get("include_reasoning", True)
    
    # Initialize outputs
    reasoning_steps = []
    precedent_explanations = []
    
    # Check if we should generate reasoning
    if not include_reasoning:
        logger.info("⏭️  Reasoning disabled, skipping...")
        return {
            "reasoning_steps": [],
            "precedent_explanations": []
        }
    
    # Validate inputs
    if not response:
        logger.warning("⚠️  No response to analyze, skipping reasoning...")
        return {
            "reasoning_steps": [],
            "precedent_explanations": []
        }
    
    if not retrieved_chunks:
        logger.warning("⚠️  No precedents to analyze, skipping reasoning...")
        return {
            "reasoning_steps": [],
            "precedent_explanations": []
        }
    
    try:
        # Initialize explainer
        explainer = DynamicReasoningExplainer()
        
        # Step 1: Generate reasoning chain
        logger.info("📊 Generating reasoning chain...")
        reasoning_steps_objects = explainer.generate_reasoning_chain(
            user_intent=user_intent,
            info_collected=info_collected,
            response=response,
            retrieved_chunks=retrieved_chunks
        )
        
        # Convert to dict format
        reasoning_steps = [
            {
                "step_number": step.step_number,
                "step_type": step.step_type,
                "title": step.title,
                "explanation": step.explanation,
                "confidence": step.confidence,
                "supporting_sources": step.supporting_sources,
                "legal_provisions": step.legal_provisions,
                "response_excerpt": step.response_excerpt
            }
            for step in reasoning_steps_objects
        ]
        
        logger.info(f"   ✓ Generated {len(reasoning_steps)} reasoning steps")
        
        # Step 2: Analyze precedent usage
        logger.info("📚 Analyzing precedent usage...")
        case_summary = create_case_summary(info_collected, user_intent)
        
        precedent_usages = explainer.generate_all_precedent_explanations(
            case_summary=case_summary,
            retrieved_chunks=retrieved_chunks,
            response=response
        )
        
        # Convert to dict format
        precedent_explanations = [
            {
                "precedent_title": usage.precedent_title,
                "precedent_index": usage.precedent_index,
                "retrieval_score": usage.retrieval_score,
                "usage_score": usage.usage_score,
                "similarity_score": usage.retrieval_score,  # For backward compatibility
                "matching_factors": usage.matching_factors,
                "different_factors": usage.different_factors,
                "key_excerpt": usage.key_excerpt,
                "relevance_explanation": usage.how_it_influenced_response,
                "citation": usage.citation,
                "response_sections_influenced": usage.response_sections_influenced
            }
            for usage in precedent_usages
        ]
        
        logger.info(f"   ✓ Analyzed {len(precedent_explanations)} precedents")
        
        # Log usage scores for verification
        for pe in precedent_explanations:
            logger.info(f"     Precedent: retrieval={pe['retrieval_score']:.0%}, "
                       f"usage={pe['usage_score']:.0%}")
        
        logger.info("✅ Reasoning analysis complete")
        
        return {
            "reasoning_steps": reasoning_steps,
            "precedent_explanations": precedent_explanations
        }
    
    except Exception as e:
        logger.error(f"❌ Reasoning analysis failed: {e}", exc_info=True)
        
        # Return empty lists on failure (don't break the flow)
        return {
            "reasoning_steps": [],
            "precedent_explanations": []
        }


def should_analyze_reasoning(state: FamilyLawState) -> bool:
    """
    Helper function to determine if reasoning should be analyzed.
    
    Can be used for conditional routing in the graph.
    """
    return (
        state.get("include_reasoning", True) and
        bool(state.get("response", "")) and
        bool(state.get("retrieved_chunks", []))
    )