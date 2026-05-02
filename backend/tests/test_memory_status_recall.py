"""PR-RAG-HONEST -- pin /memory/status returns an honest recall descriptor.

The Atlas / Backlog previously framed Daena's recall as "RAG NOT
IMPLEMENTED" -- technically correct (no embeddings) but understated:
``MemoryService.recall_for_chat`` actually runs a deterministic
keyword Jaccard blend across NBMF tier, entry confidence, and recency
decay. PR-RAG-HONEST surfaces that algorithm in
``GET /api/v1/memory/status`` so operators see what runs without
reading code.

These tests pin:

* The ``recall`` block exists on the response.
* Required keys are present (mode / embeddings_enabled / scoring /
  scope_priority / filters / tokenizer / function_path / reason).
* The 4 scoring weights sum to 1.0 (matches recall_for_chat's blend).
* ``embeddings_enabled`` is False (this build has no vector retrieval).
* The pre-existing ``rag`` block is unchanged (regression guard --
  removing the honest "not_configured" badge would re-open the
  Hallucination of Control wound).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> dict[str, str]:
    """Register a fresh tenant + user; return Authorization headers."""
    unique = uuid.uuid4().hex[:8]
    email = f"recall-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Recall Tester",
            "tenant_name": f"RecallOrg-{unique}",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    return {
        "Authorization": f"Bearer {login_resp.json()['data']['access_token']}",
    }


@pytest.mark.asyncio
async def test_memory_status_returns_recall_descriptor(
    client: AsyncClient,
) -> None:
    """The new ``recall`` key appears alongside memory/rag/obsidian."""
    headers = await _register_and_login(client)
    resp = await client.get("/api/v1/memory/status", headers=headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    data = payload["data"]
    assert "recall" in data, (
        "PR-RAG-HONEST: /memory/status must include the recall descriptor "
        "so operators know what algorithm runs (not just that RAG isn't "
        "configured)."
    )


@pytest.mark.asyncio
async def test_memory_status_recall_has_required_keys(
    client: AsyncClient,
) -> None:
    """Required keys for any operator / SDK consumer of the descriptor."""
    headers = await _register_and_login(client)
    resp = await client.get("/api/v1/memory/status", headers=headers)
    recall = resp.json()["data"]["recall"]

    required = {
        "mode",
        "embeddings_enabled",
        "function_path",
        "scoring",
        "scope_priority",
        "filters",
        "tokenizer",
        "default_top_k",
        "reason",
    }
    missing = required - set(recall.keys())
    assert not missing, f"recall descriptor missing keys: {missing}"


@pytest.mark.asyncio
async def test_memory_status_recall_describes_keyword_blend(
    client: AsyncClient,
) -> None:
    """The descriptor must accurately describe ``recall_for_chat``'s
    blended formula. If the algorithm is ever swapped to embeddings,
    these assertions force a documentation update at the same time.
    """
    headers = await _register_and_login(client)
    resp = await client.get("/api/v1/memory/status", headers=headers)
    recall = resp.json()["data"]["recall"]

    assert recall["mode"] == "keyword_jaccard_blend"
    assert recall["embeddings_enabled"] is False
    assert recall["function_path"].endswith("recall_for_chat")
    assert recall["default_top_k"] == 5

    # Scoring weights must sum to 1.0 (matches the blend in
    # MemoryService._blended_score: 0.50 + 0.20 + 0.20 + 0.10).
    scoring = recall["scoring"]
    assert set(scoring.keys()) == {
        "keyword_relevance",
        "tier_normalized",
        "confidence",
        "recency_decay",
    }
    total_weight = sum(scoring.values())
    assert abs(total_weight - 1.0) < 1e-6, (
        f"scoring weights must sum to 1.0, got {total_weight}"
    )

    # Scope priority order matches recall_for_chat: SESSION > USER > TENANT
    assert recall["scope_priority"] == ["SESSION", "USER", "TENANT"]

    # Filter set: non-quarantined, non-expired, tier ≥ LONG_TERM
    assert "non_quarantined" in recall["filters"]
    assert "non_expired" in recall["filters"]


@pytest.mark.asyncio
async def test_memory_status_rag_block_remains_honest(
    client: AsyncClient,
) -> None:
    """Regression: PR-RAG-HONEST must NOT remove the existing honest
    ``rag.status = not_configured`` badge. The truth-telling there is
    what closes the Hallucination of Control on this surface; replacing
    it with the new ``recall`` descriptor would be a regression even
    though both are honest.
    """
    headers = await _register_and_login(client)
    resp = await client.get("/api/v1/memory/status", headers=headers)
    rag = resp.json()["data"]["rag"]

    assert rag["status"] == "not_configured"
    assert rag["enabled"] is False
    assert isinstance(rag.get("reason"), str) and rag["reason"]
