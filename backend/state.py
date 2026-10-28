"""
state.py - FamilyLawState for the LangGraph graph.

thread_id is NOT stored here — it lives in the LangGraph
RunnableConfig as config["configurable"]["thread_id"], which is
the key the AsyncPostgresSaver uses for checkpointing.
"""

from typing import TypedDict, List, Dict, Optional, Literal, Any
from langgraph.graph import MessagesState


class FamilyLawState(MessagesState):
    """
    State for the family law assistant graph.

    MessagesState already provides:
        messages: Annotated[list[BaseMessage], add_messages]
    """

    # ── Current query ─────────────────────────────────────────────────────────
    name: Optional[str]
    query: str
    user_gender: Optional[str]

    # ISO 639-1 language code detected from the user's query (e.g. "hi", "en", "ta").
    # Set by query_analyzer and read by generator / information_gatherer.
    detected_language: Optional[str]

    # ── Analysis phase ────────────────────────────────────────────────────────
    root_query:            Optional[str]
    query_type:            Optional[str]   # general_question | personal_situation | unclear
    user_intent:           Optional[str]
    analysis_complete:     bool
    needs_clarification:   bool
    clarification_question: Optional[str]
    # Text the user has sent while intent was still unclear; combined with the
    # next reply so the analyzer sees the whole story, not just the last line.
    clarification_context: Optional[str]
    clarification_count:   int

    # ── Information collection phase ──────────────────────────────────────────
    in_gathering_phase:     bool
    has_sufficient_info:    bool
    info_collected:         Dict[str, str]
    info_needed_list:       List[Dict[str, str]]
    # Model-written plain-English label per field, shown to the client in the UI.
    field_labels:           Dict[str, str]
    needs_more_info:        bool
    follow_up_question:     Optional[str]
    gathering_step:         int
    current_question_target: Optional[str]
    # True between asking a follow-up question and reading the user's reply.
    # The reply is always the next turn's `query`, so no message counting.
    awaiting_answer:        bool
    questions_asked:        int
    asked_questions:        List[str]

    # Text extracted from a document the client attached (judgment, petition,
    # notice ...). Read by the analyzer, gatherer and generator for the whole thread.
    document_context:       Optional[str]

    # ── Re-validation ─────────────────────────────────────────────────────────
    revalidation_mode:  bool
    revalidation_count: int

    # ── Update / correction handling ──────────────────────────────────────────
    is_update:             bool
    update_type:           Optional[Literal["correction", "addition", "clarification"]]
    previous_response_id:  Optional[str]

    # ── Retrieval results ─────────────────────────────────────────────────────
    retrieved_chunks: List[Dict]

    # ── Generated response ────────────────────────────────────────────────────
    response: str

    # ── Explainability ────────────────────────────────────────────────────────
    reasoning_steps:        List[Dict[str, Any]]
    precedent_explanations: List[Dict[str, Any]]
    include_reasoning:      bool
    include_prediction:     bool
    prediction:             Optional[Dict]

    # ── Metadata ──────────────────────────────────────────────────────────────
    sources:      List[Dict]
    message_type: Optional[Literal[
        "clarification", "information_gathering",
        "final_response", "update_response"
    ]]

    # ── Session tracking ──────────────────────────────────────────────────────
    session_phase:      Optional[Literal["initial", "gathering", "validating", "responding", "updating"]]
    total_interactions: int

    # ── Error handling ────────────────────────────────────────────────────────
    last_error:  Optional[str]
    retry_count: int
