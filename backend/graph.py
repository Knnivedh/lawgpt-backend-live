"""
graph.py - LangGraph graph with AsyncPostgresSaver for state persistence.

Key changes from the local-file version:
  1. create_graph() is now async and accepts a checkpointer.
  2. The compiled app is no longer a module-level singleton — it is created
     once during application startup (lifespan) and stored on app.state.
  3. All node logic is unchanged.
"""

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from config import get_settings
from state import FamilyLawState
from nodes.query_analyzer import QueryAnalyzer, gap_is_known, normalize_info_needed_list
from nodes.information_gatherer import InformationGatherer
from nodes.retriever import retrieve_documents
from nodes.generator import generate_response
from nodes.reasoning import analyze_reasoning
from node_logger import log_node_execution

import logging

logger = logging.getLogger(__name__)

# After this many clarification questions in a row, answer with what we have
# instead of asking "could you clarify?" forever.
MAX_CLARIFICATION_ROUNDS = 2

DEFAULT_CLARIFICATION_QUESTION = (
    "Could you tell me a little more about your situation? For example, is this about "
    "divorce, maintenance, child custody, domestic violence, dowry or property?"
)


def _merge_labels(state, needed):
    """Remember the model-written label of every field asked about."""
    labels = dict(state.get("field_labels") or {})
    for item in needed or []:
        if item.get("label"):
            labels[item["field"]] = item["label"]
    state["field_labels"] = labels


# ── Node functions ────────────────────────────────────────────────────────────

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
        is_update = state.get("is_update", False)
        if is_update:
            logger.info("📝 Processing information update/correction")

        # A reply to our clarification question means little on its own
        # ("my husband"), so analyse it together with what came before it.
        pending = state.get("clarification_context") if state.get("needs_clarification") else None
        analysis_text = f"{pending}\n{state['query']}" if pending else state["query"]
        logger.info(f"🔍 === {'RE-' if is_revalidation else ''}ANALYZING QUERY ===")
        if pending:
            logger.info("   (combined with the earlier message the user was clarifying)")

        agent = QueryAnalyzer()
        response = agent.analyze_query({**state, "query": analysis_text})

        intent_confidence = response.get("intent_confidence", "low")
        rounds = state.get("clarification_count", 0) or 0

        is_general = response.get("query_type") == "general_question"
        if (intent_confidence == "low" or not response.get("user_intent")) and not is_general:
            if rounds < MAX_CLARIFICATION_ROUNDS:
                state["needs_clarification"]    = True
                state["clarification_context"]  = analysis_text
                state["clarification_count"]    = rounds + 1
                state["clarification_question"] = (
                    response.get("clarification_question") or DEFAULT_CLARIFICATION_QUESTION
                )
                logger.info(f"   ❓ Intent unclear — clarification round {rounds + 1}")
                return state
            logger.info("   Intent still unclear after clarification — answering with what we have")

        state["user_intent"]      = response.get("user_intent") or "Seeking Indian family law guidance"
        if response.get("query_type"):
            state["query_type"]   = response["query_type"]
        state["info_needed_list"] = response.get("info_needed_list", [])
        _merge_labels(state, state["info_needed_list"])
        state["has_sufficient_info"] = response.get("has_sufficient_info", False)
        if response.get("detected_language"):
            state["detected_language"] = response["detected_language"]

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
        logger.info(f"   Info needed: {[i['field'] for i in state['info_needed_list']]}")

        state["needs_clarification"]   = False
        state["clarification_context"] = None
        if not is_update:
            # Retrieval searches on root_query, so it must hold the whole
            # problem statement, including anything said during clarification.
            state["root_query"] = analysis_text
        if not state["info_needed_list"]:
            state["has_sufficient_info"] = True
            state["in_gathering_phase"]  = False
        else:
            state["has_sufficient_info"] = False
            state["in_gathering_phase"]  = True
            state["gathering_step"]      = 0
            state["awaiting_answer"]     = False
            state["questions_asked"]     = 0
            state["asked_questions"]     = []

        state["is_update"] = False
        return state

    except Exception as e:
        logger.error(f"❌ Query Analyzer failed — skipping information gathering: {e}", exc_info=True)
        state["has_sufficient_info"] = True
        state["analysis_complete"]   = True
        state["in_gathering_phase"]  = False
        state["needs_clarification"] = False
        state["root_query"] = state.get("root_query") or state["query"]
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
        state["awaiting_answer"]         = response.get("awaiting_answer", False)
        state["questions_asked"]         = response.get("questions_asked", 0)
        state["asked_questions"]         = response.get("asked_questions", state.get("asked_questions") or [])
        if response.get("user_gender"):
            state["user_gender"] = response["user_gender"]

        logger.info(f"   ✓ Collected: {len(state['info_collected'])} items")
        logger.info(f"   ✓ Needed: {len(state['info_needed_list'])} items")

        if not state["needs_more_info"]:
            logger.info("✅ Gathering complete — triggering re-validation")
            state["has_sufficient_info"] = True
            state["in_gathering_phase"]  = False
            state["revalidation_mode"]   = True

        return state

    except Exception as e:
        logger.error(f"❌ Information Gatherer failed — answering without more questions: {e}", exc_info=True)
        state["has_sufficient_info"] = True
        state["in_gathering_phase"]  = False
        state["needs_more_info"]     = False
        state["awaiting_answer"]     = False
        return state


@log_node_execution("revalidate")
def revalidate_information_node(state: FamilyLawState) -> FamilyLawState:
    logger.info("🔄 === RE-VALIDATING COLLECTED INFORMATION ===")
    try:
        info_collected = state.get("info_collected", {})

        asked = state.get("questions_asked", 0)
        min_asked = get_settings().family_min_questions
        general = state.get("query_type") == "general_question"
        # Collected facts alone (info_collected) do not end the interview before the minimum
        # number of questions: rich answers fill many fields while the client was asked little.
        if (
            state.get("revalidation_count", 0) >= 3
            or (len(info_collected) >= 7 and (asked >= min_asked or general))
            or asked >= InformationGatherer.MAX_FOLLOW_UP_QUESTIONS
        ):
            logger.info("⏭️  Question budget used — moving on to retrieval")
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
        response = agent.analyze_query(temp_state, mode="revalidate")
        # Never re-ask something already answered (or already declined).
        labels = state.get("field_labels") or {}
        additional_needed = [
            item for item in normalize_info_needed_list(response.get("info_needed_list", []))
            if not gap_is_known(item, info_collected, labels)
        ]

        if additional_needed:
            logger.info(f"⚠️  Re-validation found {len(additional_needed)} missing items")
            current = normalize_info_needed_list(state.get("info_needed_list", []))
            merged = {item["field"]: item for item in current}
            for item in additional_needed:
                merged[item["field"]] = item
            _merge_labels(state, additional_needed)
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
        state["revalidation_mode"]   = False
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


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_analysis(state: FamilyLawState) -> str:
    if state.get("needs_clarification", False):
        return "clarify"
    if state.get("in_gathering_phase", False):
        return "gather_info"
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


# The question nodes also record what the assistant asked as an AIMessage, so
# the generator's conversation context shows both sides of the interview.

def format_clarification_response(state: FamilyLawState) -> dict:
    question = state.get("clarification_question") or DEFAULT_CLARIFICATION_QUESTION
    return {
        "response":     question,
        "sources":      [],
        "message_type": "clarification",
        "messages":     [AIMessage(content=question)],
    }


def format_follow_up_response(state: FamilyLawState) -> dict:
    question = state.get("follow_up_question") or "Could you provide more details?"
    return {
        "response":       question,
        "sources":        [],
        "message_type":   "information_gathering",
        "info_collected": state.get("info_collected", {}),
        "info_needed":    state.get("info_needed_list", []),
        "field_labels":   state.get("field_labels", {}),
        "messages":       [AIMessage(content=question)],
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
