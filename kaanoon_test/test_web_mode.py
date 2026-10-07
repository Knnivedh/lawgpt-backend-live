import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import asyncio

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from kaanoon_test import advanced_rag_api_server as api
from kaanoon_test.advanced_rag_api_server import QueryRequest
from kaanoon_test.external_apis.web_search_client import WebSearchClient
from kaanoon_test.system_adapters.unified_advanced_rag import UnifiedAdvancedRAG


class _DummyRequest:
    headers = {}


class _FakeRagSystem:
    def __init__(self):
        self.calls = []

    def query(
        self,
        question,
        category="general",
        session_id="",
        user_id="",
        simple_mode=False,
        web_search_mode=False,
        **kwargs,
    ):
        self.calls.append(
            {
                "question": question,
                "category": category,
                "session_id": session_id,
                "user_id": user_id,
                "simple_mode": simple_mode,
                "web_search_mode": web_search_mode,
            }
        )
        return {
            "answer": "Synthesized web answer",
            "source_documents": [
                {
                    "title": "Relevant case",
                    "url": "https://example.com/judgment",
                    "snippet": "Relevant snippet from the live search results.",
                    "source": "Example Search",
                }
            ],
            "metadata": {
                "strategy": "web_search",
                "query_type": "web_search",
                "web_search_mode": True,
                "search_engines_used": ["Example Search"],
                "retrieval_time": 0.1,
                "confidence": 0.95,
                "complexity": "high",
                "from_cache": False,
            },
        }


class _FakeParallelSearchClient:
    def __init__(self, results):
        self.results = results

    def search_duckduckgo(self, query, max_results=15):
        return self.results[:max_results]


class _FakeChatCompletions:
    def __init__(self, calls):
        self._calls = calls

    def create(self, model, messages, temperature, max_tokens):
        self._calls.append(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Synthesized web answer"))]
        )


class _FakeClientManager:
    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(self.calls))


class _FakeWebSearchClient:
    def search(self, query, max_results=8):
        return [
            {
                "title": "Case A",
                "url": "https://example.com/case-a",
                "snippet": "Relevant snippet one.",
                "source": "Example Search",
            },
            {
                "title": "Case B",
                "url": "https://example.com/case-b",
                "snippet": "Relevant snippet two.",
                "source": "Example Search",
            },
        ]
def test_web_mode_routes_directly_to_rag(monkeypatch):
    fake_rag: Any = _FakeRagSystem()
    monkeypatch.setattr(api, "rag_system", fake_rag)
    monkeypatch.setattr(api, "_load_clarification_session", lambda session_id: None)
    monkeypatch.setattr(api, "_new_clarification_session", lambda: (_ for _ in ()).throw(AssertionError("clarification should not be created for web mode")))

    payload = QueryRequest.model_construct(
        question="Latest Supreme Court judgment on electoral bonds",
        session_id="web-mode-session",
        web_search_mode=True,
        user_id=None,
        target_language=None,
        category=None,
        stream=False,
        enable_thinking=True,
    )

    response: Any = asyncio.run(api.query_endpoint(payload, cast(Any, _DummyRequest())))

    assert fake_rag.calls
    assert fake_rag.calls[0]["web_search_mode"] is True
    assert response["response"]["system_info"]["query_type"] == "web_search"
    assert response["response"]["system_info"]["web_search_mode"] is True
    assert response["response"]["sources"]
    assert response["response"]["sources"][0]["url"] == "https://example.com/judgment"
    assert "Relevant snippet" in response["response"]["sources"][0]["content"]


def test_unified_rag_web_mode_synthesizes_sources():
    rag = UnifiedAdvancedRAG.__new__(UnifiedAdvancedRAG)
    rag_any = cast(Any, rag)
    rag_any.reg = re.compile(r"^$")
    rag_any._query_times = []
    rag_any.agentic_engine = None
    rag_any.memory_manager = None
    rag_any.researcher = None
    rag_any.model = "fake-model"
    rag_any.client_manager = _FakeClientManager()
    rag_any._web_search_client = _FakeWebSearchClient()
    rag_any.require_grounded_answers = False

    result: Any = UnifiedAdvancedRAG.query(
        rag,
        "Can theft be made out if an employee takes an employer laptop without permission?",
        session_id="web-mode-rag",
        user_id="tester",
        web_search_mode=True,
    )

    assert result["answer"] == "Synthesized web answer"
    assert result["metadata"]["strategy"] == "web_search"
    assert result["metadata"]["web_search_mode"] is True
    assert result["metadata"]["search_engines_used"] == ["Example Search"]
    assert result["source_documents"][0]["url"] == "https://example.com/case-a"
    assert cast(Any, rag_any.client_manager).calls
    prompt = cast(Any, rag_any.client_manager).calls[0]["messages"][1]["content"]
    assert "https://example.com/case-a" in prompt


def test_web_search_client_prefers_parallel_results():
    client: Any = WebSearchClient()
    client._parallel_client = _FakeParallelSearchClient([
        {
            "title": "Parallel Result",
            "url": "https://indiankanoon.org/doc/123456/",
            "snippet": "Parallel search snippet.",
            "source": "Parallel Search",
        }
    ])
    client.providers = []

    results = client.search("parallel query", max_results=3)

    assert results
    assert results[0]["link"] == "https://indiankanoon.org/doc/123456/"
    assert results[0]["url"] == "https://indiankanoon.org/doc/123456/"
    assert results[0]["source"] == "Parallel Search"
    assert results[0]["snippet"] == "Parallel search snippet."


def test_web_search_client_falls_back_when_parallel_returns_empty():
    client: Any = WebSearchClient()
    client._parallel_client = _FakeParallelSearchClient([])
    client.ddgs = None
    client.providers = [
        {
            "name": "Fallback Provider",
            "func": lambda query, max_results: [
                {
                    "title": "Fallback Result",
                    "link": "https://indiankanoon.org/doc/654321/",
                    "snippet": "Fallback provider snippet.",
                    "source": "Fallback Provider",
                }
            ],
            "limit": 5,
        }
    ]

    results = client.search("fallback query", max_results=3)

    assert results
    assert results[0]["title"] == "Fallback Result"
    assert results[0]["link"] == "https://indiankanoon.org/doc/654321/"
    assert results[0]["source"] == "Fallback Provider"
