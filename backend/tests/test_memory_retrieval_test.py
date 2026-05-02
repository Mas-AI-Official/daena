"""Pin GET /api/v1/memory/retrieval-test + the new probe fields on
/memory/status.

The previous /memory/status reported Obsidian as ``available`` based
on a bare ``Path.exists()`` check, which let the UI claim retrieval
was working when no document had ever been listed. PR #2 of
PR-AUDIT-VERIFY+PR-RAG-HONEST closes that gap with real probes:

* RAG probe: hardcoded ``configured=False`` (no vector engine in this
  build).
* Obsidian probe: actually globs the vault for ``*.md`` -- empty path
  reports ``configured=False`` with an honest ``error`` message.
* Recall probe: runs a sentinel ``recall_for_chat`` call against a
  fake session id and reports ``document_count`` = non-archived
  MemoryEntry count for the tenant.

Each probe carries five fields the operator needs:
``configured, reachable, document_count, last_test_at, error``.

These tests pin the contract so a future regression that reverts to
"available if path exists" will fail at CI.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> dict[str, str]:
    unique = uuid.uuid4().hex[:8]
    email = f"retrieval-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Retrieval Tester",
            "tenant_name": f"RetrievalOrg-{unique}",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    return {
        "Authorization": f"Bearer {login_resp.json()['data']['access_token']}",
    }


# ---------------------------------------------------------------------------
# GET /memory/retrieval-test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieval_test_returns_three_probes(
    client: AsyncClient,
) -> None:
    """The endpoint runs three probes (rag, obsidian, recall) and
    returns each in the canonical 5-field shape.
    """
    headers = await _register_and_login(client)
    resp = await client.get("/api/v1/memory/retrieval-test", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    for kind in ("rag", "obsidian", "recall"):
        assert kind in data, f"missing probe: {kind}"
        probe = data[kind]
        for field in (
            "configured", "reachable", "document_count", "last_test_at", "error",
        ):
            assert field in probe, f"{kind} probe missing field: {field}"

    assert "tested_at" in data


@pytest.mark.asyncio
async def test_retrieval_test_rag_is_honestly_not_configured(
    client: AsyncClient,
) -> None:
    """No vector retrieval engine in this build -> RAG must report
    ``configured=False`` with an honest ``error`` message that names
    the gap. Replacing this assertion requires a real vector engine
    to be wired AND ``_probe_rag`` to be replaced by a real probe.
    """
    headers = await _register_and_login(client)
    resp = await client.get("/api/v1/memory/retrieval-test", headers=headers)
    rag = resp.json()["data"]["rag"]

    assert rag["configured"] is False
    assert rag["reachable"] is False
    assert rag["document_count"] is None
    assert rag["last_test_at"] is not None
    assert rag["error"] is not None
    assert "vector" in rag["error"].lower() or "rag" in rag["error"].lower()


@pytest.mark.asyncio
async def test_retrieval_test_obsidian_only_configured_when_vault_listable(
    client: AsyncClient,
) -> None:
    """The probe MUST list the vault to claim configured=True. A bare
    path-exists check is NOT enough.

    On the test environment the vault path may or may not exist
    depending on the developer machine. Either outcome is acceptable
    so long as the probe is honest:

    * Path missing: configured=False AND error mentions the missing path.
    * Path present: configured=True AND document_count is a non-negative int.
    """
    headers = await _register_and_login(client)
    resp = await client.get("/api/v1/memory/retrieval-test", headers=headers)
    obs = resp.json()["data"]["obsidian"]

    if obs["configured"]:
        assert obs["reachable"] is True
        assert isinstance(obs["document_count"], int)
        assert obs["document_count"] >= 0
        assert obs["error"] is None
    else:
        assert obs["reachable"] is False
        assert obs["document_count"] is None
        assert obs["error"] is not None


@pytest.mark.asyncio
async def test_retrieval_test_recall_succeeds_for_fresh_tenant(
    client: AsyncClient,
) -> None:
    """A fresh tenant has zero memories but the recall probe call
    (``recall_for_chat`` with a sentinel session) must still succeed.
    document_count == 0 is honest (no entries yet); configured=True
    means the algorithm RAN, not that it returned data.
    """
    headers = await _register_and_login(client)
    resp = await client.get("/api/v1/memory/retrieval-test", headers=headers)
    recall = resp.json()["data"]["recall"]

    assert recall["configured"] is True
    assert recall["reachable"] is True
    assert recall["document_count"] == 0
    assert recall["error"] is None
    assert recall["last_test_at"] is not None


# ---------------------------------------------------------------------------
# /memory/status absorbs the same probe fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_status_includes_probe_fields_on_each_surface(
    client: AsyncClient,
) -> None:
    """The same five probe fields appear inside ``status.rag``,
    ``status.obsidian``, and ``status.recall_status`` so the existing
    SettingsMemory.tsx grid renders honestly without calling a second
    endpoint.
    """
    headers = await _register_and_login(client)
    resp = await client.get("/api/v1/memory/status", headers=headers)
    data = resp.json()["data"]

    for key in ("rag", "obsidian", "recall_status"):
        block = data[key]
        for field in (
            "configured", "reachable", "document_count", "last_test_at", "error",
        ):
            assert field in block, f"{key} block missing field: {field}"


@pytest.mark.asyncio
async def test_memory_status_obsidian_legacy_status_reflects_probe_truth(
    client: AsyncClient,
) -> None:
    """Backward-compat: legacy ``obsidian.status`` must agree with the
    probe. ``configured=True`` AND ``reachable=True`` -> ``available``;
    anything else -> NOT ``available``. This prevents the prior
    Hallucination of Control where the badge said available solely
    because a path existed.
    """
    headers = await _register_and_login(client)
    resp = await client.get("/api/v1/memory/status", headers=headers)
    obs = resp.json()["data"]["obsidian"]

    if obs["configured"] and obs["reachable"]:
        assert obs["status"] == "available"
    else:
        assert obs["status"] != "available"


@pytest.mark.asyncio
async def test_memory_status_rag_remains_not_configured(
    client: AsyncClient,
) -> None:
    """Regression guard from PR #1: the honest ``rag.status =
    not_configured`` badge stays. PR #2's richer probe fields must NOT
    accidentally upgrade this to ``available`` -- there is still no
    vector retrieval engine.
    """
    headers = await _register_and_login(client)
    resp = await client.get("/api/v1/memory/status", headers=headers)
    rag = resp.json()["data"]["rag"]

    assert rag["status"] == "not_configured"
    assert rag["enabled"] is False
    assert rag["configured"] is False
    assert rag["reachable"] is False
