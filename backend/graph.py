"""
graph.py - LangGraph graph with AsyncPostgresSaver for state persistence.

Key changes from the local-file version:
  1. create_graph() is now async and accepts a checkpointer.
  2. The compiled app is no longer a module-level singleton — it is created
     once during application startup (lifespan) and stored on app.state.
  3. All node logic is unchanged.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from state import FamilyLawState
from nodes.query_analyzer import QueryAnalyzer, normalize_info_needed_list
from nodes.information_gatherer import InformationGatherer
from nodes.retriever import retrieve_documents
from nodes.generator import generate_response
from nodes.reasoning import analyze_reasoning
from node_logger import log_node_execution

import logging

logger = logging.getLogger(__name__)


# ── Node functions (unchanged logic) ─────────────────────────────────────────

@log_node_execution("analyze_query")
def analyze_query_node(state: FamilyLawState) -> FamilyLawState:
    is_revalidation = state.get("revalidation_mode", False)

    if is_revalidation:
        logger.info("🔄 RE-VALIDATING after information gathering")
        state["revalidation_mode"] = False
    elif state.get("in_gathering_phase", False):
        logger.info("⏭️  Skipping analysis — already in gathering phase")
        return state
    elif state.get("analysis_complete", False) and not state.get("is_update", False):
        logger.info("⏭️  Skipping analysis — already complete")
        return state

    try:
        logger.info(f"🔍 === {'RE-' if is_revalidation else ''}ANALYZING QUERY ===")
        is_update = state.get("is_update", False)
        if is_update:
            logger.info("📝 Processing information update/correction")

        agent = QueryAnalyzer()
        response = agent.analyze_query(state)

        intent_confidence = response.get("intent_confidence", "low")

        if intent_confidence == "low" or not response.get("user_intent"):
            state["needs_clarification"]   = True
            state["clarification_question"] = "Could you please provide more details about your legal situation?"
            return state

        state["user_intent"]      = response.get("user_intent")
        state["info_needed_list"] = response.get("info_needed_list", [])
        state["has_sufficient_info"] = response.get("has_sufficient_info", False)

        new_info = response.get("info_collected", {})
        if is_update:
            existing = state.get("info_collected", {})
            existing.update(new_info)
            state["info_collected"] = existing
        else:
            state["info_collected"] = new_info

        state["analysis_complete"] = True

        logger.info(f"   Intent: {state['user_intent']}")
        logger.info(f"   Info collected: {list(state['info_collected'].keys())}")
        logger.info(f"   Info needed: {state['info_needed_list']}")
        logger.info(f"   Sufficient: {state['has_sufficient_info']}")

        state["needs_clarification"] = False
        if not is_update and state["user_intent"]:
            state["root_query"] = state["query"]
        if not state["info_needed_list"]:
            state["has_sufficient_info"] = True
            state["in_gathering_phase"]  = False
        else:
            state["in_gathering_phase"] = True
            state["gathering_step"]     = 0
        

        state["is_update"] = False
        return state

    except Exception as e:
        logger.error(f"❌ Query Analyzer failed: {e}", exc_info=True)
        state["has_sufficient_info"] = True
        state["analysis_complete"]   = True
        state["in_gathering_phase"]  = False
        return state


@log_node_execution("gather_info")
def gather_information_node(state: FamilyLawState) -> FamilyLawState:
    try:
        step = state.get("gathering_step", 0)
        logger.info(f"📊 === GATHERING INFORMATION (Step {step}) ===")

        gatherer = InformationGatherer()
        response = gatherer.gather_next_information(state)

        state["info_collected"]          = response.get("info_collected", {})
        state["info_needed_list"]        = response.get("info_needed_list", [])
        state["follow_up_question"]      = response.get("follow_up_question")
        state["needs_more_info"]         = response.get("needs_more_info", False)
        state["gathering_step"]          = response.get("gathering_step", 0)
        state["current_question_target"] = response.get("current_question_target")

        logger.info(f"   ✓ Collected: {len(state['info_collected'])} items")
        logger.info(f"   ✓ Needed: {len(state['info_needed_list'])} items")

        if not state["needs_more_info"]:
            logger.info("✅ Gathering complete — triggering re-validation")
            state["has_sufficient_info"] = True
            state["in_gathering_phase"]  = False
            state["revalidation_mode"]   = True

        return state

    except Exception as e:
        logger.error(f"❌ Information Gatherer failed: {e}", exc_info=True)
        state["has_sufficient_info"] = True
        state["in_gathering_phase"]  = False
        state["needs_more_info"]     = False
        return state


@log_node_execution("revalidate")
def revalidate_information_node(state: FamilyLawState) -> FamilyLawState:
    logger.info("🔄 === RE-VALIDATING COLLECTED INFORMATION ===")
    try:
        info_collected = state.get("info_collected", {})

        if state.get("revalidation_count", 0) >= 2 or len(info_collected) >= 7:
            logger.warning("⚠️  Maximum re-validation attempts reached")
            state.update({
                "has_sufficient_info": True,
                "in_gathering_phase":  False,
                "needs_more_info":     False,
                "revalidation_mode":   False,
            })
            return state

        original_query = state.get("root_query", "")
        info_context   = "\n".join(
            f"- {k.replace('_', ' ').title()}: {v}"
            for k, v in info_collected.items()
        )
        synthetic_query = f"{original_query}\n\nMy Information:\n{info_context}"

        temp_state = dict(state)
        temp_state["query"]            = synthetic_query
        temp_state["analysis_complete"] = False
        temp_state["in_gathering_phase"] = False

        agent    = QueryAnalyzer()
        response = agent.analyze_query(temp_state)
        additional_needed = normalize_info_needed_list(response.get("info_needed_list", []))

        if additional_needed:
            logger.info(f"⚠️  Re-validation found {len(additional_needed)} missing items")
            current = normalize_info_needed_list(state.get("info_needed_list", []))
            merged = {item["field"]: item for item in current}
            for item in additional_needed:
                merged[item["field"]] = item
            state.update({
                "info_needed_list":    list(merged.values()),
                "in_gathering_phase":  True,
                "needs_more_info":     True,
                "has_sufficient_info": False,
                "revalidation_mode":   False,
                "revalidation_count":  state.get("revalidation_count", 0) + 1,
            })
        else:
            logger.info("✅ Re-validation passed")
            state.update({
                "has_sufficient_info": True,
                "in_gathering_phase":  False,
                "needs_more_info":     False,
                "revalidation_mode":   False,
            })

        return state

    except Exception as e:
        logger.error(f"❌ Re-validation failed: {e}", exc_info=True)
        state["has_sufficient_info"] = True
        return state


@log_node_execution("retrieve")
def retrieve_documents_node(state: FamilyLawState) -> FamilyLawState:
    result = retrieve_documents(state)
    state.update(result)
    return state


@log_node_execution("generate")
def generate_response_node(state: FamilyLawState) -> FamilyLawState:
    result = generate_response(state)
    state.update(result)
    return state


@log_node_execution("analyze_reasoning")
def analyze_reasoning_node(state: FamilyLawState) -> FamilyLawState:
    result = analyze_reasoning(state)
    state.update(result)
    return state


# ── Routing functions (unchanged) ─────────────────────────────────────────────

def route_after_analysis(state: FamilyLawState) -> str:
    if state.get("needs_clarification", False):
        return "clarify"
    if state.get("has_sufficient_info", False) or not state.get("info_needed_list", []):
        return "retrieve"
    return "gather_info"


def route_after_gathering(state: FamilyLawState) -> str:
    if state.get("needs_more_info", False):
        return "ask_question"
    if state.get("revalidation_mode", False):
        return "revalidate"
    return "retrieve"


def route_after_revalidation(state: FamilyLawState) -> str:
    return "retrieve" if state.get("has_sufficient_info", False) else "gather_info"


def format_clarification_response(state: FamilyLawState) -> dict:
    return {
        "response":     state.get("clarification_question", "Could you please clarify your legal situation?"),
        "sources":      [],
        "message_type": "clarification",
    }


def format_follow_up_response(state: FamilyLawState) -> dict:
    return {
        "response":      state.get("follow_up_question", "Could you provide more details?"),
        "sources":       [],
        "message_type":  "information_gathering",
        "info_collected": state.get("info_collected", {}),
        "info_needed":   state.get("info_needed_list", []),
    }


# ── Graph factory ─────────────────────────────────────────────────────────────

async def create_graph(checkpointer: AsyncPostgresSaver):
    """
    Build and compile the LangGraph app with a Postgres checkpointer.

    Called once during application startup (lifespan).
    The checkpointer must already have its schema set up via
    `await checkpointer.setup()` before this is called.
    """
    logger.info("🏗️  Building LangGraph with AsyncPostgresSaver …")

    workflow = StateGraph(FamilyLawState)

    workflow.add_node("analyze_query",    analyze_query_node)
    workflow.add_node("clarify",          format_clarification_response)
    workflow.add_node("gather_info",      gather_information_node)
    workflow.add_node("ask_question",     format_follow_up_response)
    workflow.add_node("revalidate",       revalidate_information_node)
    workflow.add_node("retrieve",         retrieve_documents_node)
    workflow.add_node("generate",         generate_response_node)
    workflow.add_node("analyze_reasoning", analyze_reasoning_node)

    workflow.add_edge(START, "analyze_query")

    workflow.add_conditional_edges(
        "analyze_query", route_after_analysis,
        {"clarify": "clarify", "gather_info": "gather_info", "retrieve": "retrieve"},
    )
    workflow.add_edge("clarify", END)

    workflow.add_conditional_edges(
        "gather_info", route_after_gathering,
        {"ask_question": "ask_question", "revalidate": "revalidate", "retrieve": "retrieve"},
    )
    workflow.add_edge("ask_question", END)

    workflow.add_conditional_edges(
        "revalidate", route_after_revalidation,
        {"retrieve": "retrieve", "gather_info": "gather_info"},
    )

    workflow.add_edge("retrieve",         "generate")
    workflow.add_edge("generate",         "analyze_reasoning")
    workflow.add_edge("analyze_reasoning", END)

    app = workflow.compile(checkpointer=checkpointer)
    logger.info("✅ Graph compiled with AsyncPostgresSaver")
    return app
