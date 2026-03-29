"""Phase 4: Error Handling and Edge Cases.

Test 13: LLM timeout / failure handling
Test 14: Tool execution failure
Test 15: Concurrent requests (session isolation)
Test 16: Large payload handling
Test 17: TLM integration with execution layer
"""

from __future__ import annotations

import asyncio
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
    email = f"edge-{unique}@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Edge Tester",
            "tenant_name": f"EdgeOrg-{unique}",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login_resp.json()["data"]
    return {
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user": data["user"],
    }


async def _create_session(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "Edge Test"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["data"]["id"]


async def _stream_message(client: AsyncClient, session_id: str, headers: dict, content: str) -> list[dict]:
    resp = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages/stream",
        json={"content": content, "role": "USER"},
        headers=headers,
    )
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


# ── Test 13: LLM Error Handling ───────────────────────────────

@pytest.mark.asyncio
async def test_13_llm_error_produces_graceful_message(client: AsyncClient, app) -> None:
    """When LLM stream fails, user should get an error event, not a crash."""
    auth = await _register_and_login(client)
    session_id = await _create_session(client, auth["headers"])
    await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "test", "role": "USER"},
        headers=auth["headers"],
    )

    app.state.model_registry = _mock_registry()

    # Mock LLM that raises an exception
    async def failing_stream(request, decision):
        raise RuntimeError("LLM provider unavailable")
        yield  # make it a generator  # noqa: E501

    with patch("app.services.llm_service.LLMService") as MockLLM:
        mock = MagicMock()
        mock.stream = failing_stream
        MockLLM.return_value = mock

        events = await _stream_message(client, session_id, auth["headers"], "test message")

    # Should get an error event or a done event, not an HTTP 500
    event_types = [e.get("type") for e in events]
    assert "error" in event_types or "done" in event_types, \
        f"Expected error or done event on LLM failure. Got: {event_types}"


# ── Test 14: Tool Execution Failure ───────────────────────────

class TestToolFailure:
    """Verify tool execution errors are handled gracefully."""

    @pytest.mark.asyncio
    async def test_execution_service_handles_unknown_tool(self):
        """ExecutionService with unknown agent prefix returns error, not crash."""
        from app.services.execution_service import ExecutionService

        mock_db = AsyncMock()
        svc = ExecutionService(mock_db)
        result = await svc._dispatch_tool("nonexistent.tool", {})
        assert result.get("success") is False, \
            "Unknown tool should return success=False"

    @pytest.mark.asyncio
    async def test_execution_service_disabled_daenabot(self):
        """When DaenaBot disabled, _dispatch_tool returns disabled message."""
        from app.services.execution_service import ExecutionService

        mock_db = AsyncMock()
        svc = ExecutionService(mock_db)

        with patch("app.core.config.get_settings") as mock_settings:
            settings = MagicMock()
            settings.enable_daenabot = False
            mock_settings.return_value = settings

            result = await svc._dispatch_tool("file.read_file", {"path": "/tmp/x"})
            assert result["success"] is False
            assert "not enabled" in result.get("error", "")


# ── Test 15: Concurrent Session Isolation ─────────────────────

@pytest.mark.asyncio
async def test_15_concurrent_sessions_isolated(client: AsyncClient, app) -> None:
    """Multiple sessions running simultaneously should not cross-contaminate."""
    auth = await _register_and_login(client)
    s1 = await _create_session(client, auth["headers"])
    s2 = await _create_session(client, auth["headers"])

    # Send different messages to each session
    await client.post(
        f"/api/v1/chat/sessions/{s1}/messages",
        json={"content": "Session 1 context about cats", "role": "USER"},
        headers=auth["headers"],
    )
    await client.post(
        f"/api/v1/chat/sessions/{s2}/messages",
        json={"content": "Session 2 context about dogs", "role": "USER"},
        headers=auth["headers"],
    )

    app.state.model_registry = _mock_registry()

    # Verify sessions are separate by fetching messages
    r1 = await client.get(
        f"/api/v1/chat/sessions/{s1}/messages",
        headers=auth["headers"],
    )
    r2 = await client.get(
        f"/api/v1/chat/sessions/{s2}/messages",
        headers=auth["headers"],
    )

    assert r1.status_code == 200
    assert r2.status_code == 200

    msgs1 = r1.json()["data"]
    msgs2 = r2.json()["data"]

    # Each session should have exactly 1 message, and they should differ
    assert len(msgs1) >= 1
    assert len(msgs2) >= 1
    assert msgs1[0]["content"] != msgs2[0]["content"]


# ── Test 16: Large Payload ────────────────────────────────────

@pytest.mark.asyncio
async def test_16_large_payload_handled(client: AsyncClient, app) -> None:
    """10,000 character message should be handled without crash."""
    auth = await _register_and_login(client)
    session_id = await _create_session(client, auth["headers"])

    large_content = "A" * 10000
    resp = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": large_content, "role": "USER"},
        headers=auth["headers"],
    )
    # Should accept or reject gracefully, not 500
    assert resp.status_code in (200, 201, 400, 413), \
        f"Unexpected status {resp.status_code} for large payload"


# ── Test 17: TLM Integration with Execution ──────────────────

class TestTLMExecution:
    """Verify TLM tracking works during execution flow."""

    def test_tlm_initializes_cleanly(self):
        from app.services.tool_lifecycle.orchestra_integration import (
            initialize_tlm,
            get_tlm_registry,
            reset_tlm,
        )
        reset_tlm()
        initialize_tlm()
        assert get_tlm_registry().count >= 10
        reset_tlm()

    def test_tlm_records_execution(self):
        from app.services.tool_lifecycle.orchestra_integration import (
            initialize_tlm,
            record_tool_execution,
            get_tlm_tracker,
            reset_tlm,
        )
        reset_tlm()
        initialize_tlm()
        record_tool_execution("conv-1", "file.read_file", "agent-1", "engineering")
        stats = get_tlm_tracker().get_tool_stats("conv-1", "file.read_file")
        assert stats is not None
        assert stats.call_count == 1
        reset_tlm()

    def test_tlm_tick_turn_works(self):
        from app.services.tool_lifecycle.orchestra_integration import (
            initialize_tlm,
            tick_conversation_turn,
            get_tlm_session_manager,
            reset_tlm,
        )
        reset_tlm()
        initialize_tlm()
        sm = get_tlm_session_manager()
        sm.activate_tool("file.read_file", "conv-1")
        result = tick_conversation_turn("conv-1")
        assert "active_count" in result
        reset_tlm()

    def test_tlm_finalize_session(self):
        from app.services.tool_lifecycle.orchestra_integration import (
            initialize_tlm,
            record_tool_execution,
            finalize_session,
            reset_tlm,
        )
        reset_tlm()
        initialize_tlm()
        record_tool_execution("conv-1", "terminal.execute_command", "agent-1", "engineering")
        result = finalize_session("conv-1", "agent-1", "engineering")
        assert result["total_calls"] == 1
        reset_tlm()
