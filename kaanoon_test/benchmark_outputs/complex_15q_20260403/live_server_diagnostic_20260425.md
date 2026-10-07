# Live Server Diagnostic Report (2026-04-25)

## Scope Executed
- Azure CLI connectivity check and App Service metadata check.
- Live Azure log streaming during test execution.
- Full local backend pytest discovery run in stage folder.
- Live ground-truth benchmark run against production endpoint.
- Live 15-scenario complex benchmark run against production endpoint.
- Live API smoke matrix covering health, auth, routing, clarification/session, web mode, and conversation cleanup.
- Azure log archive download plus direct ZIP parsing for recurring error signatures.

## Production Target
- App: lawgpt-backend2024
- Resource group: lawgpt-rg
- Host: lawgpt-backend2024.azurewebsites.net
- Azure subscription: Azure for Students

## High Severity Findings
1. Production health is degraded due to retrieval backend unavailability.
- Evidence: GET /api/health returns status=degraded and retrieval_ready=false.
- Retrieval payload:
  - main_store_ready=false
  - statute_store_ready=false
  - pageindex_docs=0
  - has_any_retrieval=false

2. Grounded-answer path is effectively collapsing into abstentions for benchmark workload.
- Evidence from live benchmark report:
  - Average composite score: 0.143
  - Exact match rate: 0.000
  - Invalid query_type count: 5/14
- Typical answer pattern: "I cannot provide a reliable legal answer... retrieval backends unavailable..."

3. Web search mode is broken in deployed build.
- Evidence from live log stream:
  - Failed to initialize web search client: 'WebSearchClient' object has no attribute 'DEFAULT_TRUSTED_DOMAINS'
- Smoke behavior impact:
  - web_search_mode request returns abstained_due_to_grounding=true with grounded_answer=false.

4. Retrieval substrate instability appears persistent in logs.
- Evidence from zipped log parsing:
  - "Main hybrid store not available": 223 occurrences.
  - Milvus-related errors sampled:
    - StatusCode.UNAUTHENTICATED
    - Cluster status STOPPED

## Medium Severity Findings
1. Rate-limit pressure remains significant.
- Evidence:
  - 429 Too Many Requests found repeatedly in live stream and log ZIP parsing (55 occurrences in parsed ZIP scan).
  - Retries visible in stream with backoff.

2. Query type contract quality regression.
- Evidence from ground-truth report:
  - Query type valid rate: 0.643
  - Distribution: academic_direct=9, invalid_query_type=5

3. Complex benchmark reliability issue (timeout outlier).
- Evidence from compleQA live run:
  - Q1 timed out at 180s.
  - 14/15 scenarios returned 200, but all classified as academic_direct.

## Local Test Suite Findings (Stage Folder)
- Command: python -m pytest -q in azure_backend_stage/kaanoon_test
- Result: 13 failed, 15 passed.

Primary local failure causes:
1. Invalid LLM API key in test environment for live-initialization path.
- test_10_10_accuracy failed with OpenAI AuthenticationError 401 invalid_api_key.

2. Async test plugin missing.
- Multiple async tests failed with:
  - "async def functions are not natively supported"
  - pytest-asyncio (or equivalent) not installed/configured.

## Functional Areas Verified Working
- API authentication endpoint behavior for invalid credentials (401 expected).
- Greeting route responds correctly (query_type=greeting).
- Clarification flow engages on substantive legal query (query_type=clarification).
- Session continuity works for follow-up in same session.
- Conversation clear endpoint works (DELETE /api/conversation/{session_id} returns success).
- Release metadata endpoint responds (200).

## Artifacts Generated
- Ground-truth report:
  - azure_backend_stage/kaanoon_test/benchmark_outputs_check/20260425_154603/ground_truth_benchmark_report.md
- Ground-truth raw results JSON:
  - azure_backend_stage/kaanoon_test/benchmark_outputs_check/20260425_154603/ground_truth_benchmark_results.json
- Complex benchmark report:
  - azure_backend_stage/kaanoon_test/benchmark_outputs/complex_15q_20260403/compleqa_live_report.md
- Complex benchmark raw results JSON:
  - azure_backend_stage/kaanoon_test/benchmark_outputs/complex_15q_20260403/compleqa_live_results.json
- Azure log archive:
  - latest_logs/azure_live_20260425.zip

## Recommended Fix Order
1. Restore retrieval readiness in production (main/statute/pageindex availability).
2. Deploy web search client fix for DEFAULT_TRUSTED_DOMAINS regression.
3. Re-run strict provenance benchmark gate after health returns ready.
4. Tighten query_type contract emission (eliminate invalid_query_type outputs).
5. Address 429 pressure with key usage policy, per-provider fallback, and retry tuning.
6. Fix test environment quality:
  - Add/configure async pytest plugin.
  - Provide non-production test keys or mock LLM probe path for offline tests.
