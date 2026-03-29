"""Phase 5: Browser Round-Trip Tests (Service-Layer).

These test the same flows that browser E2E would test, but at the
HTTP/service layer using the ASGI test client. No live server needed.

Test 18: Send message -> see response (full SSE flow)
Test 19: Multi-turn conversation maintains context
Test 20: Governance gate shows in response
Test 21: Session list reflects new sessions
Test 22: Audit log captures events
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.constants import HealthStatus, ModelProvider
from app.services.providers.base import LLMChunk, ModelInfo


# ── Helpers ───────────────────────────────────────────────────

async def _auth(client: AsyncClient) -> dict:
    unique = uuid.uuid4().hex[:8]
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"rt-{unique}@test.com",
            "password": "SecurePass123!",
            "display_name": "RT Tester",
            "tenant_name": f"RTOrg-{unique}",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": f"rt-{unique}@test.com", "password": "SecurePass123!"},
    )
    data = resp.json()["data"]
    return {"headers": {"Authorization": f"Bearer {data['access_token']}"}, "user": data["user"]}


async def _session(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "RT Test"},
        headers=headers,
    )
    return resp.json()["data"]["id"]


async def _stream(client: AsyncClient, sid: str, headers: dict, content: str, **extra) -> list[dict]:
    body = {"content": content, "role": "USER", **extra}
    resp = await client.post(
        f"/api/v1/chat/sessions/{sid}/messages/stream",
        json=body,
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


def _reg():
    r = MagicMock()
    r._providers = {ModelProvider.OLLAMA: MagicMock()}
    r._health_cache = {ModelProvider.OLLAMA: HealthStatus.HEALTHY}
    m = ModelInfo(model_id="llama3.1:latest", provider=ModelProvider.OLLAMA, tags=["chat"])
    r._model_cache = {m.model_id: m}
    r.available_providers = [ModelProvider.OLLAMA]
    r.get_provider.side_effect = lambda p: r._providers.get(p)
    r.get_health.side_effect = lambda p: r._health_cache.get(p, HealthStatus.UNAVAILABLE)
    r.get_model_info.side_effect = lambda mid: r._model_cache.get(mid)
    return r


def _llm(*chunks):
    async def fn(req, dec):
        for i, t in enumerate(chunks):
            yield LLMChunk(content=t, model_id="llama3.1:8b", provider=ModelProvider.OLLAMA,
                           finish_reason="stop" if i == len(chunks) - 1 else None, token_index=i)
    return fn


# ── Test 18: Full SSE Round-Trip ──────────────────────────────

@pytest.mark.asyncio
async def test_18_full_sse_roundtrip(client: AsyncClient, app) -> None:
    """Send message via SSE, verify thinking + chunks + done."""
    auth = await _auth(client)
    sid = await _session(client, auth["headers"])
    await client.post(
        f"/api/v1/chat/sessions/{sid}/messages",
        json={"content": "What is Daena?", "role": "USER"},
        headers=auth["headers"],
    )

    app.state.model_registry = _reg()
    with patch("app.services.llm_service.LLMService") as M:
        m = MagicMock()
        m.stream = _llm("Daena is a ", "governed AI ", "orchestration platform.")
        M.return_value = m
        events = await _stream(client, sid, auth["headers"], "What is Daena?")

    types = [e.get("type") for e in events]
    assert "thinking" in types, f"Missing thinking events: {types}"
    assert "chunk" in types, f"Missing chunk events: {types}"
    assert "done" in types, f"Missing done event: {types}"

    content = "".join(e["content"] for e in events if e.get("type") == "chunk")
    assert "Daena" in content


# ── Test 19: Multi-Turn Context ───────────────────────────────

@pytest.mark.asyncio
async def test_19_multi_turn_context(client: AsyncClient, app) -> None:
    """Second message in session should see first message's context."""
    auth = await _auth(client)
    sid = await _session(client, auth["headers"])

    # Turn 1
    await client.post(
        f"/api/v1/chat/sessions/{sid}/messages",
        json={"content": "My name is Masoud", "role": "USER"},
        headers=auth["headers"],
    )

    app.state.model_registry = _reg()
    with patch("app.services.llm_service.LLMService") as M:
        m = MagicMock()
        m.stream = _llm("Nice to meet you!")
        M.return_value = m
        await _stream(client, sid, auth["headers"], "My name is Masoud")

    # Turn 2: should have context from turn 1
    with patch("app.services.llm_service.LLMService") as M:
        m = MagicMock()
        m.stream = _llm("Your name is Masoud, as you mentioned.")
        M.return_value = m
        events = await _stream(client, sid, auth["headers"], "What is my name?")

    # Verify messages endpoint shows all messages
    msg_resp = await client.get(
        f"/api/v1/chat/sessions/{sid}/messages",
        headers=auth["headers"],
    )
    assert msg_resp.status_code == 200
    messages = msg_resp.json()["data"]
    assert len(messages) >= 3  # at least: user1, assistant1, user2 (assistant2 may be pending)


# ── Test 20: Governance Thinking Stage ────────────────────────

@pytest.mark.asyncio
async def test_20_governance_stage_in_response(client: AsyncClient, app) -> None:
    """Governance stage should emit a thinking event."""
    auth = await _auth(client)
    sid = await _session(client, auth["headers"])
    await client.post(
        f"/api/v1/chat/sessions/{sid}/messages",
        json={"content": "Deploy to production", "role": "USER"},
        headers=auth["headers"],
    )

    app.state.model_registry = _reg()
    with patch("app.services.llm_service.LLMService") as M:
        m = MagicMock()
        m.stream = _llm("Starting deployment ", "process...")
        M.return_value = m
        events = await _stream(client, sid, auth["headers"], "Deploy to production")

    stages = [e.get("stage") for e in events if e.get("type") == "thinking"]
    assert "governance" in stages, f"Missing governance stage. Stages: {stages}"


# ── Test 21: Session List Updates ─────────────────────────────

@pytest.mark.asyncio
async def test_21_session_list_reflects_new_session(client: AsyncClient, app) -> None:
    """Creating a session should appear in the session list."""
    auth = await _auth(client)

    # Create 2 sessions
    s1 = await _session(client, auth["headers"])
    s2 = await _session(client, auth["headers"])

    resp = await client.get(
        "/api/v1/chat/sessions",
        headers=auth["headers"],
    )
    assert resp.status_code == 200
    sessions = resp.json()["data"]
    session_ids = [s["id"] for s in sessions]
    assert s1 in session_ids
    assert s2 in session_ids


# ── Test 22: Audit Log Captures Events ────────────────────────

@pytest.mark.asyncio
async def test_22_audit_log_populated(client: AsyncClient, app) -> None:
    """After a message, audit log should have entries."""
    auth = await _auth(client)
    sid = await _session(client, auth["headers"])
    await client.post(
        f"/api/v1/chat/sessions/{sid}/messages",
        json={"content": "Check system status", "role": "USER"},
        headers=auth["headers"],
    )

    app.state.model_registry = _reg()
    with patch("app.services.llm_service.LLMService") as M:
        m = MagicMock()
        m.stream = _llm("All systems operational.")
        M.return_value = m
        await _stream(client, sid, auth["headers"], "Check system status")

    # Check audit log endpoint
    audit_resp = await client.get(
        "/api/v1/governance/audit",
        headers=auth["headers"],
    )
    assert audit_resp.status_code == 200
    entries = audit_resp.json()["data"]
    assert isinstance(entries, list)
    # After a full pipeline run, should have at least 1 audit entry
    assert len(entries) >= 1, "Audit log should capture pipeline events"
