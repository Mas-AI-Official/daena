"""ContentOps batch ingest tests.

Pins the wire contract documented in
``docs/pitch/CONTENTOPS-INGEST-CONTRACT.md``. External scrapers
(YouTube + Grabit + NotebookLM) POST to ``/api/v1/skills/refinery/
ingest-batch`` and expect:

* Invalid source_type -> 422 with the valid enum listed.
* Empty items list -> 422 (Pydantic min_length=1).
* Successful batch with mocked LLM -> per-item ``ok`` status.
* Batch-label defaulting when omitted.
* Tenant isolation across batches.

The LLM call inside the endpoint goes to Ollama via ``httpx``. We
monkey-patch ``httpx.AsyncClient`` to skip the network entirely so
the test runs without a live model.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from httpx import AsyncClient


# ── Ollama stub ───────────────────────────────────────────────────


class _StubOllamaResponse:
    """Minimal httpx.Response stand-in. Returns a canned LLM payload
    shaped like the extraction_service parser expects."""

    def __init__(self, extracted: dict[str, Any]) -> None:
        self._extracted = extracted

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, Any]:
        # Real extraction_service uses parse_extraction_response on the
        # raw string; returning JSON-in-a-string mirrors Ollama's chat
        # completion shape.
        return {
            "message": {
                "content": json.dumps(self._extracted),
            }
        }


class _StubAsyncClient:
    """Replaces httpx.AsyncClient for the duration of a test.

    Returns a DIFFERENT extracted title per call so each item produces
    a unique skill_id (otherwise the batch's second item collides on
    the unique-per-tenant skill_id constraint).
    """

    _call_counter = 0

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> "_StubAsyncClient":
        return self

    async def __aexit__(self, *a: Any) -> None:
        return None

    async def post(self, *args: Any, **kwargs: Any) -> _StubOllamaResponse:
        _StubAsyncClient._call_counter += 1
        return _StubOllamaResponse({
            "title": f"Cold email skill variant {_StubAsyncClient._call_counter}",
            "domain": "sales",
            "subdomains": ["cold_email"],
            "steps": [{"action": "State pain", "example": "..."}],
            "patterns": [],
            "anti_patterns": ["no generic opener"],
            "failure_modes": [],
            "confidence": 0.82,
        })


# ── Auth helper ───────────────────────────────────────────────────


async def _register_and_login(client: AsyncClient) -> dict:
    unique = uuid.uuid4().hex[:8]
    email = f"contentops-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "ContentOps Tester",
            "tenant_name": f"COps-{unique}",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login.json()["data"]
    return {
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "tenant_id": data["user"]["tenant_id"],
    }


# ── Tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ingest_rejects_unknown_source_type(client: AsyncClient) -> None:
    auth = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/skills/refinery/ingest-batch",
        json={
            "items": [{
                "source_type": "tiktok",  # not allowed
                "content": "This transcript is long enough to pass validation.",
            }],
        },
        headers=auth["headers"],
    )
    assert resp.status_code == 422
    # Message should list the valid set so the scraper knows what to send.
    body = resp.json()
    detail = str(body)
    assert "youtube" in detail
    assert "podcast" in detail


@pytest.mark.asyncio
async def test_ingest_rejects_empty_items(client: AsyncClient) -> None:
    auth = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/skills/refinery/ingest-batch",
        json={"items": []},
        headers=auth["headers"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_batch_succeeds_with_mocked_llm(
    client: AsyncClient, monkeypatch,
) -> None:
    """Two items, both extract cleanly, both persist as T1 drafts."""
    auth = await _register_and_login(client)

    # Stub httpx.AsyncClient so no network call leaves the test.
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _StubAsyncClient)

    resp = await client.post(
        "/api/v1/skills/refinery/ingest-batch",
        json={
            "batch_label": "test-batch-1",
            "items": [
                {
                    "source_type": "youtube",
                    "source_url": "https://youtube.com/watch?v=A",
                    "creator": "Alex Hormozi",
                    "title": "The offer",
                    "content": "Long enough transcript text " * 10,
                },
                {
                    "source_type": "podcast",
                    "source_url": "https://example.com/ep1",
                    "creator": "Chris Voss",
                    "content": "Negotiation excerpt " * 10,
                },
            ],
        },
        headers=auth["headers"],
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["batch_label"] == "test-batch-1"
    assert body["data"]["ok"] == 2
    assert body["data"]["errors"] == 0
    results = body["data"]["results"]
    assert len(results) == 2
    assert all(r["status"] == "ok" for r in results)
    assert all(r["skill_id"] for r in results)
    # Per-item source_url / creator preserved for scraper book-keeping.
    assert results[0]["creator"] == "Alex Hormozi"


@pytest.mark.asyncio
async def test_ingest_default_batch_label(
    client: AsyncClient, monkeypatch,
) -> None:
    """Omitted batch_label defaults to a timestamp."""
    auth = await _register_and_login(client)
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _StubAsyncClient)

    resp = await client.post(
        "/api/v1/skills/refinery/ingest-batch",
        json={
            "items": [{
                "source_type": "manual",
                "content": "Some minimal content " * 5,
            }],
        },
        headers=auth["headers"],
    )
    assert resp.status_code == 201
    label = resp.json()["data"]["batch_label"]
    assert label and label != ""
    assert label.startswith("batch-")


@pytest.mark.asyncio
async def test_ingest_preserves_extras_in_source_metadata(
    client: AsyncClient, monkeypatch,
) -> None:
    """extras payload survives round-trip so later stages can inspect it."""
    auth = await _register_and_login(client)
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _StubAsyncClient)

    resp = await client.post(
        "/api/v1/skills/refinery/ingest-batch",
        json={
            "items": [{
                "source_type": "youtube",
                "source_url": "https://youtube.com/watch?v=B",
                "creator": "Alex Hormozi",
                "content": "Transcript content " * 10,
                "extras": {
                    "video_duration_sec": 2400,
                    "chapter_marks": [{"t": 120, "label": "Intro"}],
                    "notebooklm_summary_url": "https://notebooklm.example/abc",
                },
            }],
        },
        headers=auth["headers"],
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["ok"] == 1
    skill_id = data["results"][0]["skill_id"]
    assert skill_id

    # Fetch the persisted skill and verify extras landed.
    fetched = await client.get(
        f"/api/v1/skills/refinery/{skill_id}",
        headers=auth["headers"],
    )
    assert fetched.status_code == 200
    meta = fetched.json().get("data", {}).get("source_metadata", {}) or {}
    assert meta.get("video_duration_sec") == 2400
    assert meta.get("notebooklm_summary_url") == "https://notebooklm.example/abc"


@pytest.mark.asyncio
async def test_ingest_is_tenant_isolated(
    client: AsyncClient, monkeypatch,
) -> None:
    """Tenant B cannot see skills ingested by Tenant A."""
    auth_a = await _register_and_login(client)
    auth_b = await _register_and_login(client)

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _StubAsyncClient)

    await client.post(
        "/api/v1/skills/refinery/ingest-batch",
        json={
            "items": [{
                "source_type": "youtube",
                "creator": "Tenant A creator",
                "content": "Content for tenant A " * 10,
            }],
        },
        headers=auth_a["headers"],
    )

    # Tenant B's catalog must not include A's skill.
    b_catalog = await client.get(
        "/api/v1/skills/refinery/catalog",
        headers=auth_b["headers"],
    )
    assert b_catalog.status_code == 200
    data = b_catalog.json().get("data")
    # Catalog response has shape-flexibility between deployments; unwrap
    # whichever envelope we actually got.
    if isinstance(data, dict):
        skills = data.get("skills") or data.get("items") or []
    elif isinstance(data, list):
        skills = data
    else:
        skills = []
    assert not any(
        (s.get("source_metadata") or {}).get("creator") == "Tenant A creator"
        for s in skills
    )
