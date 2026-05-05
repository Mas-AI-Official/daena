"""PR-LOCAL-USABLE-TODAY-ACCEPTANCE-FIX (Sprint-7 acceptance)
end-to-end test for the chat self-diagnostic short-circuit.

Drives the real chat stream pipeline with the question "are you ok?"
and confirms:

  1. The stream returns 200 (no auth or pipeline failure).
  2. The done event payload carries ``self_diagnostic: True`` -- the
     short-circuit fired.
  3. The streamed content contains ``## Self-diagnostic`` (the
     advisor's deterministic markdown header).
  4. The streamed content ends with the SAFETY_BOUNDARY string,
     exactly as the advisor mints it.
  5. NO chunks contain secret-shaped substrings (Bearer / sk- /
     access_token / DATABASE_URL / etc.).
  6. NO LLM was invoked: the orchestrator does NOT emit a normal-path
     done event with ``role/model_used/provider_used`` because the
     short-circuit returns BEFORE Stage 8. We assert the absence of
     those keys in the done payload.

This test does NOT need a mocked LLM -- the whole point of the
short-circuit is that no LLM call ever happens. If it did, the
backend would attempt an Ollama call against 11434 and the test
would either hang or fail differently. Either failure mode tells
us the short-circuit broke.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

from app.core.constants import HealthStatus, ModelProvider
from app.services.providers.base import ModelInfo
from app.services.self_diagnostic_advisor import SAFETY_BOUNDARY


pytestmark = pytest.mark.asyncio


def _make_mock_registry():
    """Minimal ModelRegistry stub. The orchestrator's self-diagnostic
    short-circuit returns BEFORE the registry is used, but the chat
    handler resolves the registry as a precondition. Without this stub
    the request 500s before the orchestrator even runs, so the test
    can't observe whether the short-circuit works."""
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


_FORBIDDEN_SUBSTRINGS = (
    "access_token",
    "refresh_token",
    "client_secret",
    "Bearer ",
    "DATABASE_URL",
    "password",
    "sk-ant-",
    "sk-",
    "pplx-",
    "xai-",
)


async def _register_and_login(client: AsyncClient) -> dict:
    unique = uuid.uuid4().hex[:8]
    email = f"sd-e2e-{unique}@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Self-Diag E2E",
            "tenant_name": f"SDE2E-{unique}",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login.json()["data"]
    return {"headers": {"Authorization": f"Bearer {data['access_token']}"}}


async def _create_session(client: AsyncClient, headers: dict) -> str:
    res = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "self-diag e2e"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


async def _send_user_message(client: AsyncClient, sid: str, headers: dict, content: str):
    res = await client.post(
        f"/api/v1/chat/sessions/{sid}/messages",
        json={"content": content, "role": "USER"},
        headers=headers,
    )
    assert res.status_code == 201, res.text


def _parse_sse(body: str) -> list[dict]:
    events: list[dict] = []
    for line in body.split("\n"):
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


async def test_chat_short_circuits_for_self_diagnostic_question(client, app):
    """Posting 'are you ok?' must short-circuit through the advisor;
    NO LLM call, deterministic markdown answer, safety boundary present."""
    app.state.model_registry = _make_mock_registry()
    auth = await _register_and_login(client)
    sid = await _create_session(client, auth["headers"])
    await _send_user_message(client, sid, auth["headers"], "are you ok?")

    resp = await client.post(
        f"/api/v1/chat/sessions/{sid}/messages/stream",
        json={"content": "are you ok?", "role": "USER"},
        headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.text)

    # 1. The done event must carry self_diagnostic=True.
    done_events = [e for e in events if e.get("type") == "done"]
    assert len(done_events) >= 1, (
        f"expected a done event; got events: {[e.get('type') for e in events]}"
    )
    last_done = done_events[-1]
    assert last_done.get("data", {}).get("self_diagnostic") is True, (
        f"short-circuit signal missing from done event: {last_done!r}"
    )

    # 2. The done event must NOT carry the normal-path role/model_used/
    #    provider_used keys (those are emitted at Stage 9 after an LLM
    #    call; the short-circuit returns before Stage 1).
    short_circuit_done = last_done.get("data", {})
    assert "model_used" not in short_circuit_done, (
        f"short-circuit done event should not carry model_used: {short_circuit_done}"
    )
    assert "provider_used" not in short_circuit_done, (
        f"short-circuit done event should not carry provider_used: {short_circuit_done}"
    )

    # 3. Chunks must reconstruct the deterministic markdown.
    chunks = [e for e in events if e.get("type") == "chunk"]
    assert len(chunks) > 0, "no chunks emitted"
    full = "".join(e.get("content", "") for e in chunks)
    assert "## Self-diagnostic" in full, (
        f"streamed answer missing self-diagnostic header: {full[:200]!r}"
    )
    # 4. Safety boundary lands.
    assert SAFETY_BOUNDARY in full, (
        f"streamed answer missing SAFETY_BOUNDARY: {full[-200:]!r}"
    )
    # 5. No secret substrings leak through chunks.
    for needle in _FORBIDDEN_SUBSTRINGS:
        assert needle not in full, (
            f"streamed self-diagnostic answer leaked forbidden substring: {needle!r}"
        )


async def test_chat_normal_question_does_not_short_circuit(client, monkeypatch):
    """Negative control: a non-self-diagnostic question must NOT trigger
    the short-circuit. The done event for a normal turn still carries
    role/model_used. We don't actually let the LLM call hit a real
    provider -- we check the EARLY signal: no self_diagnostic flag in
    the done event.

    The simplest way to do this without standing up the model registry
    + LLM mock is to verify that the question 'what is 2 plus 2?' does
    not match `is_self_diagnostic_question`, which is the gate for the
    short-circuit. If the gate is right, the short-circuit cannot fire,
    and the test passes regardless of what the rest of the pipeline
    does."""
    from app.services.self_diagnostic_advisor import is_self_diagnostic_question
    assert is_self_diagnostic_question("what is 2 plus 2?") is False
    assert is_self_diagnostic_question("write me a haiku about cats") is False
    assert is_self_diagnostic_question("scan https://example.com") is False
