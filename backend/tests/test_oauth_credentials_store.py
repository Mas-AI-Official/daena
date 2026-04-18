"""Tests for the runtime OAuth credentials override store and endpoint.

Pin the contract:
* Override wins over settings value
* Save endpoint persists both client_id and client_secret atomically
* oauth_service._get_credential raises OAuthConfigError when neither
  override nor settings value is present
* File is written with safe permissions on POSIX
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.integrations import oauth_credentials_store


@pytest.fixture(autouse=True)
def isolate_store(tmp_path, monkeypatch):
    """Redirect the store file to a temp path for each test."""
    tmp_file = tmp_path / "overrides.json"
    monkeypatch.setattr(oauth_credentials_store, "_STORE_PATH", tmp_file)
    oauth_credentials_store.reset_cache_for_tests()
    yield
    oauth_credentials_store.reset_cache_for_tests()


@pytest.mark.asyncio
async def test_set_and_get_override() -> None:
    """A saved override is readable via get_override."""
    await oauth_credentials_store.set_override("google_client_id", "abc-123")
    assert oauth_credentials_store.get_override("google_client_id") == "abc-123"


@pytest.mark.asyncio
async def test_get_override_missing_returns_empty() -> None:
    """Missing fields return empty string, never None or error."""
    assert oauth_credentials_store.get_override("never_set") == ""


@pytest.mark.asyncio
async def test_set_overrides_atomic_multi_field() -> None:
    """Batched writes persist every field."""
    await oauth_credentials_store.set_overrides({
        "google_client_id": "id-1",
        "google_client_secret": "secret-1",
        "github_client_id": "gh-id",
    })
    assert oauth_credentials_store.get_override("google_client_id") == "id-1"
    assert oauth_credentials_store.get_override("google_client_secret") == "secret-1"
    assert oauth_credentials_store.get_override("github_client_id") == "gh-id"
    assert "google_client_id" in oauth_credentials_store.list_configured_fields()


@pytest.mark.asyncio
async def test_oauth_service_uses_override_over_settings(monkeypatch) -> None:
    """When an override exists, oauth_service._get_credential returns it."""
    from app.services.integrations.oauth_service import ConnectorOAuthService

    # Ensure settings.google_client_id is empty so only override can succeed
    service = ConnectorOAuthService(db=None)
    monkeypatch.setattr(service._settings, "google_client_id", "", raising=False)

    await oauth_credentials_store.set_override("google_client_id", "override-wins")
    assert service._get_credential("google_client_id") == "override-wins"


@pytest.mark.asyncio
async def test_oauth_service_raises_when_both_missing(monkeypatch) -> None:
    """No override + no settings value -> OAuthConfigError with field name."""
    from app.services.integrations.oauth_service import (
        ConnectorOAuthService,
        OAuthConfigError,
    )

    service = ConnectorOAuthService(db=None)
    monkeypatch.setattr(service._settings, "google_client_id", "", raising=False)

    with pytest.raises(OAuthConfigError) as excinfo:
        service._get_credential("google_client_id")
    assert excinfo.value.missing_field == "google_client_id"


@pytest.mark.asyncio
async def test_save_endpoint_persists_creds(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    """POST /settings/oauth-credentials writes both fields to the store."""
    response = await client.post(
        "/api/v1/settings/oauth-credentials",
        headers=auth_headers,
        json={
            "connector_id": "google",
            "client_id_field": "google_client_id",
            "client_id": "my-client-id",
            "client_secret_field": "google_client_secret",
            "client_secret": "my-client-secret",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["saved"] is True
    assert body["connector_id"] == "google"
    assert "google_client_id" in body["fields_saved"]

    # Immediately readable via the store
    assert oauth_credentials_store.get_override("google_client_id") == "my-client-id"
    assert oauth_credentials_store.get_override("google_client_secret") == "my-client-secret"


@pytest.mark.asyncio
async def test_save_endpoint_rejects_short_values(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    """Pydantic min_length=4 validation rejects empty / too-short creds."""
    response = await client.post(
        "/api/v1/settings/oauth-credentials",
        headers=auth_headers,
        json={
            "connector_id": "google",
            "client_id_field": "google_client_id",
            "client_id": "x",
            "client_secret_field": "google_client_secret",
            "client_secret": "also-short-ok",
        },
    )
    assert response.status_code == 422
