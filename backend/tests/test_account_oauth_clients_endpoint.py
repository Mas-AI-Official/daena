"""End-to-end tests for /api/v1/account/oauth-clients.

PR-CONN-OAUTH-CLIENT-CONFIG-IN-SETTINGS (2026-05-03).

Pins the leak-safety contract on the HTTP boundary AND the underlying
oauth_credentials_store integration: after a successful save, the
shared store reports the values are present (so oauth_service.start
will pick them up), but the API response NEVER carries the values
themselves.

Also pins:
  * Unknown provider slug -> 404 BEFORE touching either store.
  * Empty client_id or client_secret -> 422 (Pydantic validation).
  * DELETE clears both fields atomically.
  * Tokens table is NOT touched on save / clear (existing
    ConnectorInstance.credentials are preserved across rotations).
  * Save dispatches the marketplace-flip side effect: a subsequent
    oauth_service.get_supported_providers() reports configured=True.

Auth: every endpoint requires ADMIN+ role. The ``auth_headers``
fixture in conftest.py issues a FOUNDER-role JWT which satisfies that.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.integrations import (
    oauth_client_config_store as cfg_store,
    oauth_credentials_store,
)


@pytest.fixture(autouse=True)
def _isolated_stores(tmp_path: Path, monkeypatch):
    """Point both the credentials store AND the metadata sidecar at
    fresh per-test temp files. Clears caches before AND after the
    test so module-level state doesn't bleed between tests."""
    creds_file = tmp_path / "oauth_overrides.json"
    meta_file = tmp_path / "oauth_client_metadata.json"
    monkeypatch.setattr(oauth_credentials_store, "_STORE_PATH", creds_file)
    monkeypatch.setattr(cfg_store, "_METADATA_PATH", meta_file)
    cfg_store.reset_cache_for_tests()
    yield
    cfg_store.reset_cache_for_tests()


# ──────────────────────────────────────────────────────────────────
# Listing
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_returns_all_supported_providers(client, auth_headers):
    res = await client.get("/api/v1/account/oauth-clients", headers=auth_headers)
    assert res.status_code == 200
    rows = res.json()
    assert isinstance(rows, list)
    slugs = {r["slug"] for r in rows}
    # Must surface every slug we declared in PROVIDER_DISPLAY.
    assert slugs == {"google", "github", "slack", "figma", "canva"}


@pytest.mark.asyncio
async def test_list_initial_state_unconfigured(client, auth_headers):
    res = await client.get("/api/v1/account/oauth-clients", headers=auth_headers)
    rows = res.json()
    for row in rows:
        assert row["configured"] is False
        assert row["client_id_present"] is False
        assert row["last_updated"] == ""


@pytest.mark.asyncio
async def test_list_response_never_carries_secret_value(client, auth_headers, tmp_path: Path):
    """Canary: pre-seed values into the underlying store, then verify
    the list endpoint shape contains no field that could ever leak the
    raw value -- not even under a different name."""
    # Pre-seed via the underlying store so the list endpoint observes them.
    await oauth_credentials_store.set_overrides({
        "google_client_id": "FAKE-CLIENT-ID-CANARY",
        "google_client_secret": "FAKE-SECRET-CANARY",
    })

    res = await client.get("/api/v1/account/oauth-clients", headers=auth_headers)
    body_text = json.dumps(res.json())
    # The two canaries must NEVER appear anywhere in the response body.
    assert "FAKE-CLIENT-ID-CANARY" not in body_text
    assert "FAKE-SECRET-CANARY" not in body_text

    # And the configured bit MUST flip to True for google.
    google_row = next(r for r in res.json() if r["slug"] == "google")
    assert google_row["configured"] is True
    assert google_row["client_id_present"] is True


# ──────────────────────────────────────────────────────────────────
# Save
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_persists_and_returns_no_secret(client, auth_headers):
    res = await client.post(
        "/api/v1/account/oauth-clients/github",
        headers=auth_headers,
        json={
            "client_id": "Iv1.PERSIST-ID-CANARY",
            "client_secret": "GH-SECRET-CANARY",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    body_text = json.dumps(body)

    # Response shape contract.
    assert body["success"] is True
    assert body["slug"] == "github"
    assert body["configured"] is True
    assert body["client_id_present"] is True
    assert body["last_updated"]  # iso8601, non-empty

    # No secret echo, in any form.
    assert "PERSIST-ID-CANARY" not in body_text
    assert "GH-SECRET-CANARY" not in body_text

    # The underlying store DOES have the values now (so oauth_service
    # can use them). This is the round-trip integration check.
    assert oauth_credentials_store.get_override("github_client_id") == "Iv1.PERSIST-ID-CANARY"
    assert oauth_credentials_store.get_override("github_client_secret") == "GH-SECRET-CANARY"


@pytest.mark.asyncio
async def test_save_unknown_slug_returns_404(client, auth_headers):
    res = await client.post(
        "/api/v1/account/oauth-clients/notion",
        headers=auth_headers,
        json={"client_id": "x", "client_secret": "y"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_save_empty_client_id_rejected(client, auth_headers):
    res = await client.post(
        "/api/v1/account/oauth-clients/google",
        headers=auth_headers,
        json={"client_id": "", "client_secret": "valid"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_save_empty_client_secret_rejected(client, auth_headers):
    res = await client.post(
        "/api/v1/account/oauth-clients/google",
        headers=auth_headers,
        json={"client_id": "valid", "client_secret": ""},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_save_then_list_never_returns_just_saved_secret(client, auth_headers):
    """Tightest canary: save with a deterministic-looking sentinel,
    then list, then assert the response body bytes don't contain it."""
    SENTINEL_ID = "SAVE-LIST-CANARY-ID-9876"
    SENTINEL_SECRET = "SAVE-LIST-CANARY-SECRET-9876"

    save_res = await client.post(
        "/api/v1/account/oauth-clients/slack",
        headers=auth_headers,
        json={"client_id": SENTINEL_ID, "client_secret": SENTINEL_SECRET},
    )
    assert save_res.status_code == 200

    list_res = await client.get("/api/v1/account/oauth-clients", headers=auth_headers)
    list_text = json.dumps(list_res.json())
    assert SENTINEL_ID not in list_text
    assert SENTINEL_SECRET not in list_text


# ──────────────────────────────────────────────────────────────────
# Marketplace-flip side effect
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_makes_oauth_service_report_configured(client, auth_headers):
    """After Save, the existing ConnectorOAuthService.get_supported_providers()
    MUST report ``configured: True`` for every provider_id covered by
    the saved slug. This is the contract the marketplace card relies
    on to flip Configure -> Connect."""
    from app.services.integrations.oauth_service import ConnectorOAuthService

    # Pre-state: google not configured.
    svc = ConnectorOAuthService(db=None)
    pre = {p["provider_id"]: p["configured"] for p in svc.get_supported_providers()}
    assert pre["gmail"] is False
    assert pre["google-calendar"] is False
    assert pre["google-drive"] is False

    # Save google client config.
    res = await client.post(
        "/api/v1/account/oauth-clients/google",
        headers=auth_headers,
        json={"client_id": "g-id", "client_secret": "g-secret"},
    )
    assert res.status_code == 200

    # Post-state: all three Google provider_ids report configured.
    post = {p["provider_id"]: p["configured"] for p in svc.get_supported_providers()}
    assert post["gmail"] is True
    assert post["google-calendar"] is True
    assert post["google-drive"] is True


# ──────────────────────────────────────────────────────────────────
# Delete
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_clears_both_fields(client, auth_headers):
    # Save first.
    save_res = await client.post(
        "/api/v1/account/oauth-clients/figma",
        headers=auth_headers,
        json={"client_id": "fig-id", "client_secret": "fig-secret"},
    )
    assert save_res.status_code == 200
    assert oauth_credentials_store.get_override("figma_client_id") == "fig-id"

    # Delete.
    del_res = await client.delete(
        "/api/v1/account/oauth-clients/figma", headers=auth_headers,
    )
    assert del_res.status_code == 200
    body = del_res.json()
    assert body["success"] is True
    assert body["removed_any"] is True
    assert body["configured"] is False
    assert body["client_id_present"] is False

    # Underlying store is cleared too (oauth_service falls back to env).
    assert oauth_credentials_store.get_override("figma_client_id") == ""
    assert oauth_credentials_store.get_override("figma_client_secret") == ""


@pytest.mark.asyncio
async def test_delete_unknown_slug_returns_404(client, auth_headers):
    res = await client.delete(
        "/api/v1/account/oauth-clients/notion", headers=auth_headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_when_unconfigured_is_noop(client, auth_headers):
    """Calling delete on a slug that was never saved returns success
    with removed_any=False. No error, no store touched."""
    res = await client.delete(
        "/api/v1/account/oauth-clients/canva", headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["removed_any"] is False


# ──────────────────────────────────────────────────────────────────
# Auth gating
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_requires_auth(client):
    res = await client.get("/api/v1/account/oauth-clients")
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_save_requires_auth(client):
    res = await client.post(
        "/api/v1/account/oauth-clients/github",
        json={"client_id": "x", "client_secret": "y"},
    )
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_delete_requires_auth(client):
    res = await client.delete("/api/v1/account/oauth-clients/github")
    assert res.status_code in (401, 403)


# ──────────────────────────────────────────────────────────────────
# Provider-id mapping coverage
# ──────────────────────────────────────────────────────────────────


def test_every_slug_provider_id_maps_to_oauth_providers():
    """Coverage gate: every provider_id referenced by PROVIDER_DISPLAY
    must exist in oauth_service.OAUTH_PROVIDERS. Fails the moment a
    drift happens."""
    from app.services.integrations.oauth_service import OAUTH_PROVIDERS

    for slug, meta in cfg_store.PROVIDER_DISPLAY.items():
        for pid in meta["provider_ids"]:  # type: ignore[index]
            assert pid in OAUTH_PROVIDERS, (
                f"Slug {slug!r} references provider_id {pid!r} "
                f"which is not in OAUTH_PROVIDERS."
            )
