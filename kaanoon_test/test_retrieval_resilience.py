import sys
from pathlib import Path
from typing import Any, Dict
import asyncio

import requests

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from kaanoon_test.external_apis.indian_kanoon_client import IndianKanoonClient
from kaanoon_test import advanced_rag_api_server as api
from kaanoon_test.system_adapters.unified_advanced_rag import UnifiedAdvancedRAG
from rag_system.core.enhanced_retriever import EnhancedRetriever


class _FakeResponse:
    def __init__(self, status_code: int, payload: Dict[str, Any] | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self) -> Dict[str, Any]:
        return self._payload


def test_retrieve_uses_live_fallback_when_local_stores_are_unavailable(monkeypatch):
    retriever = EnhancedRetriever(hybrid_store=None, statute_store=None)
    monkeypatch.setattr(retriever, "preprocess_query", lambda query: (query, query))
    monkeypatch.setattr(retriever, "adaptive_retrieval_count", lambda _query: 2)
    monkeypatch.setattr(
        retriever,
        "_fetch_live_results",
        lambda _query, max_results=2: [
            {
                "id": "live_doc_1",
                "text": "IPC 302 sample live result",
                "metadata": {"source": "Web Search (Live)"},
                "distance": 0.1,
            }
        ],
    )

    results = retriever.retrieve(
        "What is IPC 302?",
        use_reranking=False,
        allow_live_search=False,
    )

    assert results
    assert results[0]["id"] == "live_doc_1"


def test_get_judgment_falls_back_to_get_when_post_returns_405(monkeypatch):
    client = IndianKanoonClient(api_token="test-token", timeout=1)

    monkeypatch.setattr(
        client.session,
        "post",
        lambda *_args, **_kwargs: _FakeResponse(status_code=405),
    )
    monkeypatch.setattr(
        client.session,
        "get",
        lambda *_args, **_kwargs: _FakeResponse(
            status_code=200,
            payload={
                "title": "Sample Case",
                "doc": "Full judgment text",
            },
        ),
    )

    result = client.get_judgment("12345")

    assert result is not None
    assert result["title"] == "Sample Case"
    assert result["text"] == "Full judgment text"


def test_health_endpoint_treats_live_fallback_as_operational(monkeypatch):
    class _FakeRagSystem:
        @staticmethod
        def get_retrieval_health() -> Dict[str, Any]:
            return {
                "has_any_retrieval": False,
                "live_fallback_capable": True,
                "has_operational_retrieval": True,
            }

    monkeypatch.setattr(api, "rag_system", _FakeRagSystem())
    monkeypatch.setattr(api, "rag_initializing", False)
    monkeypatch.setattr(api, "rag_last_error", None)

    health_payload = asyncio.run(api.health_check())

    assert health_payload["status"] == "ready"
    assert health_payload["retrieval_ready"] is True


def test_grounding_policy_accepts_sufficient_sources_without_local_backends():
    rag = UnifiedAdvancedRAG.__new__(UnifiedAdvancedRAG)
    rag_any = rag  # keep explicit assignment for clarity in tests
    rag_any.require_grounded_answers = True
    rag_any.min_grounded_sources = 2
    rag_any.min_trusted_sources = 1
    rag_any.has_retrieval_backends = lambda: False
    rag_any.has_operational_retrieval = lambda: False

    source_documents = [
        {
            "title": "Case law extract",
            "url": "https://indiankanoon.org/doc/123456/",
            "trusted_source": True,
        },
        {
            "title": "Statute text",
            "url": "https://www.indiacode.nic.in/handle/123456789/2000",
            "trusted_source": True,
        },
    ]

    result = {
        "answer": "Preliminary answer",
        "source_documents": source_documents,
        "metadata": {
            "strategy": "agentic",
            "query_type": "agentic",
        },
    }

    output = rag._enforce_grounding_policy(
        user_query="Explain legal ingredients for theft under IPC",
        session_id="grounding-test",
        category="criminal",
        result=result,
    )

    assert output["metadata"]["grounded_answer"] is True
    assert output["metadata"]["abstained_due_to_grounding"] is False


def test_grounding_policy_answers_simple_majority_age_when_sources_are_thin():
    rag = UnifiedAdvancedRAG.__new__(UnifiedAdvancedRAG)
    rag.require_grounded_answers = True
    rag.min_grounded_sources = 2
    rag.min_trusted_sources = 1
    rag.has_retrieval_backends = lambda: False
    rag.has_operational_retrieval = lambda: False

    output = rag._enforce_grounding_policy(
        user_query="What is the legal age of majority in India, and which law governs it?",
        session_id="simple-majority-test",
        category="general",
        result={
            "answer": "Draft answer that had no sources",
            "source_documents": [],
            "metadata": {"strategy": "simple", "query_type": "simple"},
        },
    )

    answer = output["answer"].lower()
    assert "18" in answer
    assert "majority act, 1875" in answer
    assert "section 3" in answer
    assert output["metadata"]["query_type"] == "simple_legal_fact"
    assert output["metadata"]["grounded_answer"] is True
    assert output["metadata"]["abstained_due_to_grounding"] is False
    assert output["source_documents"][0]["trusted_source"] is True


def test_format_keeps_curated_statutory_fact_clean():
    result = {
        "answer": (
            "In India, the general legal age of majority is 18 years. "
            "The governing law is the Majority Act, 1875, especially Section 3. "
            "Important caveat: Section 2 of the Act does not decide capacity for marriage or adoption."
        ),
        "source_documents": [
            {
                "title": "The Majority Act, 1875 - Section 3",
                "url": "https://www.indiacode.nic.in/handle/123456789/2284?locale=en",
                "source": "India Code",
                "trusted_source": True,
            }
        ],
        "metadata": {
            "strategy": "curated_statutory_fact",
            "query_type": "simple_legal_fact",
            "grounded_answer": True,
            "abstained_due_to_grounding": False,
            "grounding": {"curated_statutory_fact": True},
            "complexity": "low",
        },
        "reasoning_path": "Curated statutory fact fallback",
    }

    formatted = api.format_rag_response(
        result,
        session_id="simple-majority-format-test",
        question_hint="What is the legal age of majority in India, and which law governs it?",
        max_answer_words=350,
    )

    assert not formatted["answer"].startswith("The available sources do not fully support")
    assert formatted["think_trace"] is None
    assert formatted["system_info"]["answer_downgraded"] is False
    assert formatted["system_info"]["grounded_answer"] is True


def test_format_title_uses_short_answer_not_user_question():
    question = "What is the legal age of majority in India, and which law governs it?"
    result = {
        "answer": (
            "In India, the general legal age of majority is 18 years. "
            "The governing law is the Majority Act, 1875, especially Section 3."
        ),
        "source_documents": [],
        "metadata": {
            "strategy": "simple",
            "query_type": "simple_legal_fact",
            "grounded_answer": True,
            "abstained_due_to_grounding": False,
            "complexity": "low",
        },
    }

    formatted = api.format_rag_response(
        result,
        session_id="title-summary-test",
        question_hint=question,
        max_answer_words=350,
    )

    assert formatted["title"] == "⚖️ Majority Age: 18 Years"
    assert formatted["title"].lower() != question.lower().rstrip("?")
