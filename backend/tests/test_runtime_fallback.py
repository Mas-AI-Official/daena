"""Regression test for the runtime CLI auth-error failover.

THE BUG (confirmed live, traced 2026-06-02):
    When the user's Primary Mind is ``claude_code`` and the Claude Code CLI is
    NOT logged in, the chat surfaced the raw error
    ``[Claude Code error: Not logged in - Please run /login]`` as the
    assistant's answer instead of failing over to the next available brain.

    Root cause: the Step-0 runtime-adapter path in
    ``chat_orchestrator.stream_reply`` streamed each runtime output line to the
    frontend as a ``runtime_output`` event the moment it was produced -- BEFORE
    the error check. The frontend appends ``runtime_output`` to the visible
    assistant message, so the auth-error line became the answer. Control did
    eventually fall through to the ``LLMService.stream`` provider chain, but the
    user had already been shown the raw error and no notice named the swap.

THE FIX (verified by this test):
    The Step-0 path now BUFFERS the runtime output, detects a CLI auth-error via
    the canonical ``_looks_like_cli_auth_error`` detector, and -- on auth-error
    -- emits a single ``governance_notice`` and leaves ``daenabot_result=None``
    so the standard ``LLMService.stream`` fallback answers (Perplexity/Anthropic
    in the live dev backend). The raw error is never streamed as content.

This test mocks the selected runtime adapter to emit the auth-error line and
mocks ``LLMService.stream`` to emit a real fallback answer, then asserts the
assistant content is the FALLBACK answer (not the auth-error) and that a
fallback notice was emitted.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.constants import HealthStatus, ModelProvider
from app.services.providers.base import LLMChunk, ModelInfo
from app.services.runtimes.base_adapter import RuntimeStatus

# The exact line the claude_code adapter yields when the CLI is reachable but
# not logged in (see runtimes/adapters/claude_code.py::execute -> is_error).
AUTH_ERROR_LINE = "[Claude Code error: Not logged in - Please run /login]"
FALLBACK_ANSWER = "Hello from fallback"


async def _register_and_login(client: AsyncClient) -> dict:
    unique = uuid.uuid4().hex[:8]
    email = f"rtfb-{unique}@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Runtime Fallback Tester",
            "tenant_name": f"RtfbOrg-{unique}",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login_resp.json()["data"]
    return {"headers": {"Authorization": f"Bearer {data['access_token']}"}}


async def _create_session(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "Runtime Fallback Session"},
        headers=headers,
    )
    assert resp.status_code == 201, f"Session creation failed: {resp.text}"
    return resp.json()["data"]["id"]


def _make_mock_registry():
    """Mock ModelRegistry exposing a single healthy provider for routing."""
    registry = MagicMock()
    registry._providers = {ModelProvider.OLLAMA: MagicMock()}
    registry._health_cache = {ModelProvider.OLLAMA: HealthStatus.HEALTHY}
    model = ModelInfo(
        model_id="llama3.1:latest",
        provider=ModelProvider.OLLAMA,
        tags=["chat", "fast"],
    )
    registry._model_cache = {model.model_id: model}
    registry.available_providers = [ModelProvider.OLLAMA]
    registry.get_provider.side_effect = lambda provider: registry._providers.get(provider)
    registry.get_health.side_effect = lambda provider: registry._health_cache.get(
        provider, HealthStatus.UNAVAILABLE,
    )
    registry.get_model_info.side_effect = lambda model_id: registry._model_cache.get(model_id)
    return registry


def _make_auth_error_adapter() -> MagicMock:
    """A fake claude_code adapter that yields a CLI auth-error line."""
    adapter = MagicMock()
    adapter.display_name = "Claude Code"

    async def _execute(task, context):  # noqa: ANN001, ARG001
        yield AUTH_ERROR_LINE

    adapter.execute = _execute
    return adapter


def _make_fake_runtime_registry(claude_adapter: MagicMock) -> MagicMock:
    """Registry where only claude_code resolves and reports ONLINE."""
    registry = MagicMock()

    def _get_adapter(rid):  # noqa: ANN001
        return claude_adapter if rid == "claude_code" else None

    async def _ensure_health_fresh(rid):  # noqa: ANN001
        return RuntimeStatus.ONLINE if rid == "claude_code" else RuntimeStatus.OFFLINE

    registry.get_adapter.side_effect = _get_adapter
    registry.ensure_health_fresh = AsyncMock(side_effect=_ensure_health_fresh)
    registry._installed_cache = {"claude_code": True}
    return registry


def _make_noop_ooda():
    """OODAEngine stand-in that produces no output (forces legacy cascade).

    The real cognitive engine runs FIRST in EXE mode; if it produced output it
    would set ``daenabot_result`` and Step-0 (the runtime path under test) would
    be skipped. A no-op engine that yields nothing leaves ``daenabot_result``
    None so control reaches the runtime adapter dispatch.
    """
    class _NoopOODA:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            pass

        async def run(self, *args, **kwargs) -> AsyncIterator[dict]:  # noqa: ANN002, ANN003
            return
            yield  # pragma: no cover -- makes this an async generator

    return _NoopOODA


def _fallback_stream_factory():
    """LLMService.stream stand-in that yields the real fallback answer."""
    async def mock_stream(request, decision):  # noqa: ANN001, ARG001
        yield LLMChunk(
            content=FALLBACK_ANSWER,
            model_id="sonar-pro",
            provider=ModelProvider.PERPLEXITY,
            finish_reason="stop",
            token_index=0,
        )
    return mock_stream


def _parse_sse(body: str) -> list[dict]:
    events = []
    for line in body.split("\n"):
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


@pytest.mark.asyncio
async def test_runtime_auth_error_fails_over_to_provider_chain(
    client: AsyncClient, app,
) -> None:
    """claude_code 'Not logged in' must fail over, not surface the raw error."""
    auth = await _register_and_login(client)
    session_id = await _create_session(client, auth["headers"])

    # A non-action-verb query so the legacy cascade does NOT spin up the
    # SwarmPlanner / AgentLoop (which would also need mocking). The no-op OODA
    # engine ensures the cognitive path produces nothing, so control reaches the
    # Step-0 runtime adapter dispatch under test.
    user_msg = "What is the capital of France?"
    await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": user_msg, "role": "USER"},
        headers=auth["headers"],
    )

    app.state.model_registry = _make_mock_registry()

    claude_adapter = _make_auth_error_adapter()
    fake_registry = _make_fake_runtime_registry(claude_adapter)

    with (
        patch("app.core.events.get_runtime_registry", return_value=fake_registry),
        patch("app.services.cognition.ooda_engine.OODAEngine", _make_noop_ooda()),
        patch("app.services.llm_service.LLMService") as MockLLMCls,
    ):
        mock_llm = MagicMock()
        mock_llm.stream = _fallback_stream_factory()
        MockLLMCls.return_value = mock_llm

        resp = await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages/stream",
            json={
                "content": user_msg,
                "role": "USER",
                "mode": "EXE",  # runtime adapter dispatch only runs in EXE mode
                "routing_mode": "STANDARD",
                "governance_mode": "BALANCED",
            },
            headers=auth["headers"],
        )
        assert resp.status_code == 200, f"Stream failed: {resp.text}"
        events = _parse_sse(resp.text)

    # (a) The assistant content is the FALLBACK answer, NOT the auth-error.
    chunk_content = "".join(
        e.get("content", "") for e in events if e.get("type") == "chunk"
    )
    runtime_output_content = "".join(
        e.get("content", "") for e in events if e.get("type") == "runtime_output"
    )

    assert FALLBACK_ANSWER in chunk_content, (
        f"Expected fallback answer in chunks. Got: {chunk_content!r}"
    )
    # The raw auth error must NOT appear as content anywhere the user can see it.
    assert "Not logged in" not in chunk_content, (
        f"Auth error leaked into chunk content: {chunk_content!r}"
    )
    assert "Not logged in" not in runtime_output_content, (
        "Auth error was streamed as runtime_output (the original bug): "
        f"{runtime_output_content!r}"
    )
    assert AUTH_ERROR_LINE not in chunk_content

    # (b) A fallback / notice event was emitted naming the substitution.
    notice_events = [e for e in events if e.get("type") == "governance_notice"]
    assert notice_events, (
        f"No governance_notice emitted. Event types: "
        f"{[e.get('type') for e in events]}"
    )
    assert any(
        "not logged in" in (e.get("message", "") + e.get("title", "")).lower()
        or "next available" in e.get("message", "").lower()
        for e in notice_events
    ), f"Notice did not name the fallback. Notices: {notice_events}"


@pytest.mark.asyncio
async def test_runtime_happy_path_still_streams_as_answer(
    client: AsyncClient, app,
) -> None:
    """Logged-in runtime: its real output must still stream as the answer.

    Guards against a regression where the buffering fix would swallow a
    legitimate (non-auth-error) runtime response.
    """
    auth = await _register_and_login(client)
    session_id = await _create_session(client, auth["headers"])

    user_msg = "Tell me a fun fact about space."
    await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": user_msg, "role": "USER"},
        headers=auth["headers"],
    )

    app.state.model_registry = _make_mock_registry()

    real_answer = "Saturn could float in water."
    adapter = MagicMock()
    adapter.display_name = "Claude Code"

    async def _execute(task, context):  # noqa: ANN001, ARG001
        yield real_answer

    adapter.execute = _execute
    fake_registry = _make_fake_runtime_registry(adapter)

    # LLMService.stream would only be reached on fallback. If the happy path
    # works, the runtime output is the answer and this fallback text never
    # appears in the response.
    with (
        patch("app.core.events.get_runtime_registry", return_value=fake_registry),
        patch("app.services.cognition.ooda_engine.OODAEngine", _make_noop_ooda()),
        patch("app.services.llm_service.LLMService") as MockLLMCls,
    ):
        mock_llm = MagicMock()
        mock_llm.stream = _fallback_stream_factory()
        MockLLMCls.return_value = mock_llm

        resp = await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages/stream",
            json={
                "content": user_msg,
                "role": "USER",
                "mode": "EXE",
                "routing_mode": "STANDARD",
                "governance_mode": "BALANCED",
            },
            headers=auth["headers"],
        )
        assert resp.status_code == 200, f"Stream failed: {resp.text}"
        events = _parse_sse(resp.text)

    runtime_output_content = "".join(
        e.get("content", "") for e in events if e.get("type") == "runtime_output"
    )
    # The real runtime output is streamed to the UI as runtime_output (happy
    # path preserved) and no auth-error governance notice fires.
    assert real_answer in runtime_output_content, (
        f"Happy-path runtime output not streamed. runtime_output: "
        f"{runtime_output_content!r}"
    )
    notice_events = [
        e for e in events
        if e.get("type") == "governance_notice"
        and "not logged in" in (e.get("message", "") + e.get("title", "")).lower()
    ]
    assert not notice_events, (
        f"Auth-error notice fired on the happy path: {notice_events}"
    )
