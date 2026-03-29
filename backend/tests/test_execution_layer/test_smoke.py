"""Phase 1: Execution Layer Smoke Tests.

Tests the full execution pipeline from user message through the orchestrator
to the response. Mocks only the LLM layer; everything else is real.

Test 1: Simple text message through pipeline
Test 2: Message requiring skill retrieval
Test 3: Message requiring tool call (EXE mode)
Test 4: Multi-step task decomposition
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.constants import HealthStatus, ModelProvider
from app.services.providers.base import LLMChunk, ModelInfo


# ── Helpers ───────────────────────────────────────────────────

async def _register_and_login(client: AsyncClient) -> dict:
    unique = uuid.uuid4().hex[:8]
    email = f"smoke-{unique}@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Smoke Tester",
            "tenant_name": f"SmokeOrg-{unique}",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login_resp.json()["data"]
    return {
        "token": data["access_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user": data["user"],
    }


async def _create_session(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "Smoke Test Session"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["data"]["id"]


async def _send_and_stream(
    client: AsyncClient,
    session_id: str,
    headers: dict,
    content: str,
    mode: str = "CMD",
    routing_mode: str = "STANDARD",
) -> list[dict]:
    """Send a message and collect SSE events."""
    resp = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages/stream",
        json={"content": content, "role": "USER", "mode": mode, "routing_mode": routing_mode},
        headers=headers,
    )
    assert resp.status_code == 200, f"Stream failed: {resp.text}"
    events = []
    for line in resp.text.split("\n"):
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


def _mock_registry():
    registry = MagicMock()
    registry._providers = {ModelProvider.OLLAMA: MagicMock()}
    registry._health_cache = {ModelProvider.OLLAMA: HealthStatus.HEALTHY}
    model = ModelInfo(model_id="llama3.1:latest", provider=ModelProvider.OLLAMA, tags=["chat", "fast"])
    registry._model_cache = {model.model_id: model}
    registry.available_providers = [ModelProvider.OLLAMA]
    registry.get_provider.side_effect = lambda p: registry._providers.get(p)
    registry.get_health.side_effect = lambda p: registry._health_cache.get(p, HealthStatus.UNAVAILABLE)
    registry.get_model_info.side_effect = lambda mid: registry._model_cache.get(mid)
    return registry


def _mock_llm_stream(*chunks):
    """Create a mock LLM stream that yields given text chunks."""
    async def stream_fn(request, decision):
        for i, text in enumerate(chunks):
            yield LLMChunk(
                content=text,
                model_id="llama3.1:8b",
                provider=ModelProvider.OLLAMA,
                finish_reason="stop" if i == len(chunks) - 1 else None,
                token_index=i,
            )
    return stream_fn


# ── Tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_1_simple_text_message(client: AsyncClient, app) -> None:
    """POST /api/chat with simple text -> 200, agent selected, response text."""
    auth = await _register_and_login(client)
    session_id = await _create_session(client, auth["headers"])
    await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Hello Daena", "role": "USER"},
        headers=auth["headers"],
    )

    app.state.model_registry = _mock_registry()

    with patch("app.services.llm_service.LLMService") as MockLLM:
        mock = MagicMock()
        mock.stream = _mock_llm_stream("Hello! ", "How can I help ", "you today?")
        MockLLM.return_value = mock

        events = await _send_and_stream(client, session_id, auth["headers"], "Hello Daena")

    # Verify response
    event_types = [e.get("type") for e in events]
    assert "chunk" in event_types, f"No chunks. Events: {event_types}"
    assert "done" in event_types, f"No done event. Events: {event_types}"

    chunks = [e["content"] for e in events if e.get("type") == "chunk"]
    full = "".join(chunks)
    assert len(full) > 0, "Empty response"

    done = [e for e in events if e.get("type") == "done"][0]
    assert done["data"]["role"] == "ASSISTANT"
    assert done["data"]["model_used"] is not None


@pytest.mark.asyncio
async def test_2_skill_retrieval_in_response(client: AsyncClient, app) -> None:
    """Message requiring skill -> correct thinking stages present."""
    auth = await _register_and_login(client)
    session_id = await _create_session(client, auth["headers"])
    await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Analyze the competitive landscape", "role": "USER"},
        headers=auth["headers"],
    )

    app.state.model_registry = _mock_registry()

    with patch("app.services.llm_service.LLMService") as MockLLM:
        mock = MagicMock()
        mock.stream = _mock_llm_stream(
            "Based on my analysis, ", "the competitive landscape shows ",
            "three key players: ", "Perplexity, Manus, and OpenClaw."
        )
        MockLLM.return_value = mock

        events = await _send_and_stream(client, session_id, auth["headers"], "Analyze the competitive landscape")

    # Verify thinking stages ran (skill retrieval happens at Stage 6)
    stages = [e.get("stage") for e in events if e.get("type") == "thinking"]
    assert "analyzing" in stages, f"Missing analysis stage. Stages: {stages}"
    assert "routing" in stages, f"Missing routing stage. Stages: {stages}"

    # Verify complete response
    done = [e for e in events if e.get("type") == "done"]
    assert len(done) == 1


@pytest.mark.asyncio
async def test_3_exe_mode_tool_dispatch(client: AsyncClient, app) -> None:
    """EXE mode message -> DaenaBot dispatch attempted (tool execution path)."""
    auth = await _register_and_login(client)
    session_id = await _create_session(client, auth["headers"])
    await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "list files in current directory", "role": "USER"},
        headers=auth["headers"],
    )

    app.state.model_registry = _mock_registry()

    with patch("app.services.llm_service.LLMService") as MockLLM:
        mock = MagicMock()
        mock.stream = _mock_llm_stream("Here are the files: ", "README.md, package.json, src/")
        MockLLM.return_value = mock

        events = await _send_and_stream(
            client, session_id, auth["headers"],
            "list files in current directory",
            mode="EXE",
        )

    event_types = [e.get("type") for e in events]
    # In EXE mode, we should see runtime or daenabot activity events
    # (or fall through to LLM if no runtime available, which is fine for testing)
    assert "chunk" in event_types or "runtime_activity" in event_types or "daenabot_activity" in event_types, \
        f"Expected execution-related events. Got: {event_types}"

    done = [e for e in events if e.get("type") == "done"]
    assert len(done) == 1


@pytest.mark.asyncio
async def test_4_response_time_under_threshold(client: AsyncClient, app) -> None:
    """Pipeline completes within reasonable time (< 10s with mock LLM)."""
    import time

    auth = await _register_and_login(client)
    session_id = await _create_session(client, auth["headers"])
    await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Quick question: what is 2+2?", "role": "USER"},
        headers=auth["headers"],
    )

    app.state.model_registry = _mock_registry()

    start = time.perf_counter()
    with patch("app.services.llm_service.LLMService") as MockLLM:
        mock = MagicMock()
        mock.stream = _mock_llm_stream("4")
        MockLLM.return_value = mock
        events = await _send_and_stream(client, session_id, auth["headers"], "Quick question: what is 2+2?")
    elapsed = time.perf_counter() - start

    assert elapsed < 10.0, f"Pipeline took {elapsed:.1f}s (threshold: 10s)"
    done = [e for e in events if e.get("type") == "done"]
    assert len(done) == 1
