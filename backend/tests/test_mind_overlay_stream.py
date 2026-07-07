"""Per-Mind soul-metadata overlay through the streaming orchestrator.

Verifies the wiring added for VP-plan Phase 1 item 4:

* VP fallback: an unpinned chat with no auto-Mind match inherits the VP
  overlay (get_vp_mind) -- routing SSE event carries mind/voice/accent_color
  and the LLM request temperature comes from the VP metadata.
* Department precedence: when a department Mind matches, ITS metadata ships
  (never the VP overlay) and its temperature reaches the LLM request.
* Garbage temperature falls back to the 0.7 pipeline default.

The soul vault (backend/app/soul/) is gitignored, so these tests NEVER read
real persona files -- SoulEngine accessors are monkeypatched with known dicts
(CI portability: the vault does not exist in CI checkouts).

Mocks: SoulEngine metadata accessors, mind_router.pick_mind, LLMService.stream.
Real: auth, session creation, the full stream_reply pipeline, SSE emission.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.constants import HealthStatus, ModelProvider
from app.services.cognition.mind_router import MindMatch
from app.services.providers.base import LLMChunk, ModelInfo
from app.services.soul_engine import SoulEngine

# ── Fixture metadata (NOT vault content -- see module docstring) ──

_VP_META = {
    "slug": "daena",
    "name": "Daena",
    "voice": "en-US-TestNeural",
    "accent_color": "#ABCDEF",
    # bare frontmatter scalar parses as a STRING; exercise the coercion
    "temperature": "0.4",
    "runtime_preference": "claude_code",
    "tier": "vp",
}

_DEPT_META = {
    "slug": "engineering",
    "name": "Aria",
    "voice": "en-GB-DeptNeural",
    "accent_color": "#123456",
    "temperature": "0.3",
    "runtime_preference": "claude_code",
}


# ── Helpers (same harness as test_orchestrator_pipeline.py) ──


async def _register_and_login(client: AsyncClient) -> dict:
    unique = uuid.uuid4().hex[:8]
    email = f"mind-{unique}@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Mind Overlay Tester",
            "tenant_name": f"MindOrg-{unique}",
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
        json={"title": "Mind Overlay Test Session"},
        headers=headers,
    )
    assert resp.status_code == 201, f"Session creation failed: {resp.text}"
    return resp.json()["data"]["id"]


async def _send_user_message(client: AsyncClient, session_id: str, headers: dict, content: str) -> dict:
    resp = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": content, "role": "USER"},
        headers=headers,
    )
    assert resp.status_code == 201, f"Send message failed: {resp.text}"
    return resp.json()["data"]


def _make_mock_registry():
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
        provider,
        HealthStatus.UNAVAILABLE,
    )
    registry.get_model_info.side_effect = lambda model_id: registry._model_cache.get(model_id)
    return registry


def _mock_llm_stream_factory(captured_requests: list):
    """Async-gen mock that captures the GenerateRequest before yielding chunks."""
    async def mock_stream(request, decision):
        captured_requests.append(request)
        chunks = ["Hello", " from", " the", " Mind."]
        for i, text in enumerate(chunks):
            yield LLMChunk(
                content=text,
                model_id="llama3.1:latest",
                provider=ModelProvider.OLLAMA,
                finish_reason="stop" if i == len(chunks) - 1 else None,
                token_index=i,
            )
    return mock_stream


def _parse_sse(body: str) -> list[dict]:
    events = []
    for line in body.split("\n"):
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[len("data: "):]))
            except json.JSONDecodeError:
                continue
    return events


def _routing_event(events: list[dict]) -> dict:
    routing = [
        e for e in events
        if e.get("type") == "thinking" and e.get("stage") == "routing"
    ]
    assert routing, f"No routing event in stream. Event types: {[e.get('type') for e in events]}"
    return routing[0]


async def _stream(
    client: AsyncClient,
    app,
    *,
    mind_match: MindMatch,
    dept_meta_map: dict[str, dict],
    vp_meta: dict,
) -> tuple[dict, list]:
    """Drive one governed stream with patched Soul/Mind layers.

    Returns (routing_event, captured_llm_requests).
    """
    auth = await _register_and_login(client)
    session_id = await _create_session(client, auth["headers"])
    content = "Please give me a short status summary."
    await _send_user_message(client, session_id, auth["headers"], content)

    app.state.model_registry = _make_mock_registry()
    captured: list = []

    def _fake_dept_meta(department):
        if not department:
            return {}
        return dept_meta_map.get(str(department), {})

    with (
        patch("app.services.llm_service.LLMService") as MockLLMCls,
        patch("app.services.cognition.mind_router.pick_mind", return_value=mind_match),
        patch.object(SoulEngine, "get_department_metadata", staticmethod(_fake_dept_meta)),
        patch.object(SoulEngine, "get_vp_mind", staticmethod(lambda: vp_meta)),
    ):
        mock_llm = MagicMock()
        mock_llm.stream = _mock_llm_stream_factory(captured)
        MockLLMCls.return_value = mock_llm

        resp = await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages/stream",
            json={
                "content": content,
                "role": "USER",
                "governance_mode": "GOVERNED",
            },
            headers=auth["headers"],
        )
        assert resp.status_code == 200, f"Stream endpoint failed: {resp.text}"
        events = _parse_sse(resp.text)

    return _routing_event(events), captured


# ── Tests ──


@pytest.mark.asyncio
async def test_vp_fallback_ships_vp_overlay_on_unpinned_chat(client: AsyncClient, app) -> None:
    """No pinned dept + no auto-Mind match -> VP overlay (voice/accent/temp)."""
    routing, captured = await _stream(
        client,
        app,
        mind_match=MindMatch(slug=None, score=0, matched_keywords=()),
        dept_meta_map={},
        vp_meta=_VP_META,
    )

    assert routing["mind"] == "daena"
    assert routing["voice"] == "en-US-TestNeural"
    assert routing["accent_color"] == "#ABCDEF"
    # VP fallback must never masquerade as a pinned-department runtime bias
    assert routing.get("source") != "department_mind"

    assert captured, "LLMService.stream was never called"
    assert captured[0].temperature == pytest.approx(0.4)


@pytest.mark.asyncio
async def test_department_mind_metadata_beats_vp_overlay(client: AsyncClient, app) -> None:
    """Auto-Mind match -> department metadata ships, VP overlay never consulted."""
    routing, captured = await _stream(
        client,
        app,
        mind_match=MindMatch(slug="engineering", score=8, matched_keywords=("code",)),
        dept_meta_map={"engineering": _DEPT_META},
        vp_meta=_VP_META,
    )

    assert routing["mind"] == "engineering"
    assert routing["voice"] == "en-GB-DeptNeural"
    assert routing["accent_color"] == "#123456"
    # precedence: none of the VP values may leak through
    assert routing["voice"] != _VP_META["voice"]
    assert routing["accent_color"] != _VP_META["accent_color"]

    assert captured, "LLMService.stream was never called"
    assert captured[0].temperature == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_garbage_temperature_falls_back_to_pipeline_default(client: AsyncClient, app) -> None:
    """Unparseable frontmatter temperature -> 0.7 default, presentation intact."""
    bad_meta = dict(_DEPT_META, temperature="warm-and-fuzzy")
    routing, captured = await _stream(
        client,
        app,
        mind_match=MindMatch(slug="engineering", score=8, matched_keywords=("code",)),
        dept_meta_map={"engineering": bad_meta},
        vp_meta=_VP_META,
    )

    assert routing["mind"] == "engineering"
    assert routing["voice"] == "en-GB-DeptNeural"

    assert captured, "LLMService.stream was never called"
    assert captured[0].temperature == pytest.approx(0.7)
