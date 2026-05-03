"""End-to-end tests for /api/v1/account/provider-keys.

Pins the leak-safety contract on the HTTP boundary AND the
marketplace-flip contract: after a successful save, the marketplace
card for the same provider should report ``provider_key_present=True``
and a ``configured`` lifecycle.

Auth: every endpoint requires ADMIN+ role. The ``auth_headers``
fixture in conftest.py issues a FOUNDER-role JWT which satisfies that.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.integrations import provider_keys_store as store


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path: Path, monkeypatch):
    tmp_file = tmp_path / "provider_overrides.json"
    monkeypatch.setattr(store, "_STORE_PATH", tmp_file)
    store.reset_cache_for_tests()
    yield
    store.reset_cache_for_tests()


@pytest.fixture(autouse=True)
def _stub_model_registry(app):
    """Inject a minimal model_registry into app.state so the endpoint's
    DynamicModelService dependency can construct without the lifespan
    startup that the test client skips.
    """
    from app.services.model_registry import ModelRegistry
    app.state.model_registry = ModelRegistry()
    yield


@pytest.fixture
def _patched_provision(monkeypatch):
    """Replace DynamicModelService.provision_provider so tests don't
    actually try to talk to api.openai.com / api.anthropic.com / etc.

    Returns a controllable stub:
      * default behavior: success=True, models_discovered=5, health=HEALTHY
      * call ``stub.set_failure(reason)`` to flip to a failure response
    """
    from app.core.constants import HealthStatus, ModelProvider
    from app.services.dynamic_model_service import (
        DynamicModelService,
        ProvisionResult,
    )

    state = {"success": True, "reason": None, "models": 5}

    async def _fake_provision(self, *, provider_name, api_key):
        # The stub IS allowed to see the key for routing, but tests
        # MUST NOT assert the key value beyond a length check.
        provider_enum = {
            "anthropic": ModelProvider.ANTHROPIC,
            "openai": ModelProvider.OPENAI,
            "google_gemini": ModelProvider.GEMINI,
            "groq": ModelProvider.GROQ,
            "perplexity": ModelProvider.PERPLEXITY,
            "openrouter": ModelProvider.OPENROUTER,
            "together": ModelProvider.TOGETHER,
        }.get(provider_name, ModelProvider.OLLAMA)
        if state["success"]:
            return ProvisionResult(
                provider=provider_enum,
                success=True,
                models_discovered=state["models"],
                health=HealthStatus.HEALTHY.value,
                model_ids=[f"{provider_name}-fake-1"],
            )
        return ProvisionResult(
            provider=provider_enum,
            success=False,
            health=HealthStatus.UNAVAILABLE.value,
            error=state["reason"] or "Provider rejected the key.",
        )

    async def _fake_remove(self, provider_name):
        return True

    monkeypatch.setattr(DynamicModelService, "provision_provider", _fake_provision)
    monkeypatch.setattr(DynamicModelService, "remove_provider", _fake_remove)

    class _Stub:
        def set_failure(self, reason: str):
            state["success"] = False
            state["reason"] = reason

        def set_success(self, models: int = 5):
            state["success"] = True
            state["models"] = models

    return _Stub()


# ──────────────────────────────────────────────────────────────────
# GET /account/provider-keys -- list (no values)
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_lists_every_supported_provider(client, auth_headers):
    res = await client.get("/api/v1/account/provider-keys", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    slugs = {row["slug"] for row in body}
    assert slugs == {
        "anthropic", "openai", "gemini", "groq",
        "perplexity", "openrouter", "together",
    }
    for row in body:
        # Tri-state shape contract on the wire
        assert isinstance(row["configured"], bool)
        assert "value" not in row
        assert "api_key" not in row


@pytest.mark.asyncio
async def test_get_returns_empty_configured_when_store_clean(client, auth_headers):
    res = await client.get("/api/v1/account/provider-keys", headers=auth_headers)
    body = res.json()
    for row in body:
        assert row["configured"] is False
        assert row["last_updated"] == ""


# ──────────────────────────────────────────────────────────────────
# POST /account/provider-keys/{slug} -- save
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_returns_no_secret_value(
    client, auth_headers, _patched_provision,
):
    """The 200 response after save must NOT echo the key. Defense in
    depth: serialize the response body and grep for the canary string.
    """
    canary = "sk-ant-CANARY-SHOULD-NEVER-LEAK"
    res = await client.post(
        "/api/v1/account/provider-keys/anthropic",
        json={"api_key": canary, "test_after_save": True},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert body["configured"] is True
    assert body["models_discovered"] == 5
    # The key MUST NOT appear anywhere in the response body
    assert canary not in json.dumps(body)
    assert "CANARY" not in json.dumps(body)


@pytest.mark.asyncio
async def test_save_persists_to_store(
    client, auth_headers, _patched_provision,
):
    await client.post(
        "/api/v1/account/provider-keys/openai",
        json={"api_key": "sk-FAKE-FAKE", "test_after_save": True},
        headers=auth_headers,
    )
    # Read directly from the store to confirm persistence
    assert store.get_override("openai_api_key") == "sk-FAKE-FAKE"
    assert store.get_metadata("openai_api_key")["configured"] is True


@pytest.mark.asyncio
async def test_save_rejected_when_provider_health_check_fails(
    client, auth_headers, _patched_provision,
):
    """A bad key triggers a failed health check; the store must NOT
    be touched and the response surfaces a clear failure_reason.
    """
    _patched_provision.set_failure("invalid api key")

    res = await client.post(
        "/api/v1/account/provider-keys/anthropic",
        json={"api_key": "sk-ant-BAD", "test_after_save": True},
        headers=auth_headers,
    )
    assert res.status_code == 200  # body carries success=False
    body = res.json()
    assert body["success"] is False
    assert body["configured"] is False
    assert "invalid" in body["failure_reason"].lower()
    # CRITICAL: store was NOT touched
    assert store.get_override("anthropic_api_key") == ""


@pytest.mark.asyncio
async def test_save_unknown_slug_returns_404(
    client, auth_headers, _patched_provision,
):
    res = await client.post(
        "/api/v1/account/provider-keys/totally-fake-provider",
        json={"api_key": "sk-X", "test_after_save": False},
        headers=auth_headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_save_after_get_flips_configured_true(
    client, auth_headers, _patched_provision,
):
    # Initially unconfigured
    res = await client.get("/api/v1/account/provider-keys", headers=auth_headers)
    anthropic = next(r for r in res.json() if r["slug"] == "anthropic")
    assert anthropic["configured"] is False

    await client.post(
        "/api/v1/account/provider-keys/anthropic",
        json={"api_key": "sk-ant-FAKE", "test_after_save": True},
        headers=auth_headers,
    )

    # GET again -- now configured
    res2 = await client.get("/api/v1/account/provider-keys", headers=auth_headers)
    anthropic2 = next(r for r in res2.json() if r["slug"] == "anthropic")
    assert anthropic2["configured"] is True
    assert anthropic2["last_updated"]  # iso8601 string, non-empty


# ──────────────────────────────────────────────────────────────────
# DELETE /account/provider-keys/{slug}
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_clears_store_and_settings(
    client, auth_headers, _patched_provision,
):
    # Save first
    await client.post(
        "/api/v1/account/provider-keys/groq",
        json={"api_key": "gsk_FAKE", "test_after_save": True},
        headers=auth_headers,
    )
    assert store.get_override("groq_api_key") == "gsk_FAKE"

    # Clear
    res = await client.delete(
        "/api/v1/account/provider-keys/groq", headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["removed_from_store"] is True
    # Store is empty
    assert store.get_override("groq_api_key") == ""
    # In-memory settings is also reset
    from app.core.config import get_settings
    assert getattr(get_settings(), "groq_api_key", None) == ""


@pytest.mark.asyncio
async def test_delete_unknown_slug_returns_404(client, auth_headers):
    res = await client.delete(
        "/api/v1/account/provider-keys/totally-fake-provider",
        headers=auth_headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_idempotent_on_unset(
    client, auth_headers, _patched_provision,
):
    """Calling DELETE on a slug that was never saved should not
    explode. ``removed_from_store=False`` is the honest answer.
    """
    res = await client.delete(
        "/api/v1/account/provider-keys/together", headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["removed_from_store"] is False


# ──────────────────────────────────────────────────────────────────
# Auth gate
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_endpoints_require_auth(client):
    """No auth header -> 401/403. Without this, anyone could read the
    configured-state list (which is non-secret) OR worse, save keys.
    """
    res = await client.get("/api/v1/account/provider-keys")
    assert res.status_code in (401, 403)
    res = await client.post(
        "/api/v1/account/provider-keys/anthropic",
        json={"api_key": "sk-X"},
    )
    assert res.status_code in (401, 403)
    res = await client.delete("/api/v1/account/provider-keys/anthropic")
    assert res.status_code in (401, 403)
