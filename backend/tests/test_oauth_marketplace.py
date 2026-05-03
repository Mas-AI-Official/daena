"""PR-CONN-OAUTH-CONNECT -- bridge + start endpoint tests.

Pins the marketplace OAuth Connect contract:

  1. provider_id_for maps app-<provider> catalog ids to OAUTH_PROVIDERS keys
  2. provider_id_for returns None for unsupported / coming-soon entries
  3. start_oauth_for_marketplace returns auth URL + scopes + state with
     a v2_marketplace flag in the state store
  4. start fails with configure_required when client config is missing
  5. start fails with unsupported_provider when entry id is wrong
  6. POST /marketplace/oauth/{entry_id}/start happy path
  7. POST /marketplace/oauth/{entry_id}/start unknown entry -> 404
  8. POST /marketplace/oauth/{entry_id}/start non-oauth entry -> 400
  9. POST /marketplace/oauth/{entry_id}/start configure_required when
     client_id missing
 10. Start payload NEVER contains client_secret / state values from env
"""

from __future__ import annotations

import pytest

from app.models.identity import Tenant
from app.services.connection_v2.oauth_marketplace import (
    FAIL_CONFIGURE_REQUIRED,
    FAIL_UNSUPPORTED_PROVIDER,
    StartReport,
    oauth_app_slug_for,
    provider_id_for,
    start_oauth_for_marketplace,
    supported_provider_ids,
)


pytestmark = pytest.mark.asyncio


# ──────────────────────────────────────────────────────────────────
# Shared seeded tenant
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    from sqlalchemy import select
    existing = (
        await db_session.execute(select(Tenant).where(Tenant.id == test_tenant_id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    tenant = Tenant(id=test_tenant_id, name="T", slug="t", settings={})
    db_session.add(tenant)
    await db_session.flush()
    await db_session.commit()
    return tenant


# ──────────────────────────────────────────────────────────────────
# 1-2. Provider id mapping
# ──────────────────────────────────────────────────────────────────


class TestProviderIdMapping:
    @pytest.mark.parametrize(
        "catalog_id, expected",
        [
            ("app-gmail", "gmail"),
            ("app-google-calendar", "google-calendar"),
            ("app-google-drive", "google-drive"),
            ("app-github", "github"),
            ("app-figma", "figma"),
            ("app-slack", "slack"),
            ("app-canva", "canva"),
        ],
    )
    def test_supported_providers_map_correctly(self, catalog_id, expected):
        assert provider_id_for(catalog_id) == expected

    def test_unsupported_returns_none(self):
        # Notion / Stripe / Cloudflare / Sentry are in the catalog as
        # coming-soon but NOT in OAUTH_PROVIDERS yet. The bridge must
        # return None so the start endpoint refuses with a clear reason.
        assert provider_id_for("app-notion-oauth") is None
        assert provider_id_for("app-stripe-oauth") is None
        assert provider_id_for("app-cloudflare-oauth") is None
        assert provider_id_for("app-sentry-oauth") is None

    def test_unprefixed_returns_none(self):
        assert provider_id_for("gmail") is None
        assert provider_id_for("") is None
        assert provider_id_for("mcp-time") is None

    def test_supported_set_matches_oauth_providers_table(self):
        from app.services.integrations.oauth_service import OAUTH_PROVIDERS
        assert set(supported_provider_ids()) == set(OAUTH_PROVIDERS.keys())

    def test_oauth_app_slug_for_canonical(self):
        assert oauth_app_slug_for("gmail") == "oauth-gmail"
        assert oauth_app_slug_for("google-drive") == "oauth-google-drive"


# ──────────────────────────────────────────────────────────────────
# 3-5. start_oauth_for_marketplace direct
# ──────────────────────────────────────────────────────────────────


class TestStartOauthBridge:
    async def test_happy_path_returns_auth_url(
        self, db_session, monkeypatch, test_tenant_id, test_user_id,
    ):
        # Plant a fake client_id via the runtime override store so
        # generate_auth_url doesn't raise OAuthConfigError.
        monkeypatch.setenv("DAENA_TEST_OK", "1")
        from app.services.integrations import oauth_credentials_store

        oauth_credentials_store.reset_cache_for_tests()
        # Inject directly into the module-level cache so we don't
        # touch the on-disk override file in tests.
        oauth_credentials_store._cache = {
            "google_client_id": "fake-client-id.apps.googleusercontent.com",
            "google_client_secret": "fake-secret-do-not-leak",
        }

        state_store: dict[str, dict] = {}
        report: StartReport = start_oauth_for_marketplace(
            db=db_session,
            catalog_entry_id="app-gmail",
            base_url="http://test.local/",
            state_store=state_store,
            user_id=test_user_id,
            tenant_id=test_tenant_id,
        )

        assert report.success is True
        assert report.provider == "gmail"
        assert report.authorization_url is not None
        assert report.authorization_url.startswith(
            "https://accounts.google.com/o/oauth2/v2/auth?",
        )
        # Scopes round-trip from the OAuth provider table.
        assert "https://www.googleapis.com/auth/gmail.modify" in report.scopes
        # state_ref present + state_store gained an entry tagged for V2.
        assert report.state_ref in state_store
        entry = state_store[report.state_ref]
        assert entry["_v2_marketplace"] is True
        assert entry["connector_id"] == "gmail"
        assert entry["_catalog_entry_id"] == "app-gmail"
        # No secret in the report (failure_reason is None on success).
        assert report.failure_reason is None
        # Cleanup so the cache doesn't leak into other tests.
        oauth_credentials_store.reset_cache_for_tests()

    async def test_configure_required_when_client_missing(
        self, db_session, monkeypatch, test_tenant_id, test_user_id,
    ):
        from app.services.integrations import oauth_credentials_store

        oauth_credentials_store.reset_cache_for_tests()
        oauth_credentials_store._cache = {}  # NO overrides
        # Also wipe the env-based settings keys for the test.
        monkeypatch.setattr(
            "app.core.config.get_settings",
            lambda: type("S", (), {
                "is_production": False,
                "google_client_id": "",
                "google_client_secret": "",
            })(),
        )

        state_store: dict[str, dict] = {}
        report = start_oauth_for_marketplace(
            db=db_session,
            catalog_entry_id="app-gmail",
            base_url="http://test.local/",
            state_store=state_store,
            user_id=test_user_id,
            tenant_id=test_tenant_id,
        )

        assert report.success is False
        assert report.provider == "gmail"
        assert report.failure_reason is not None
        assert report.failure_reason.startswith(FAIL_CONFIGURE_REQUIRED)
        assert report.authorization_url is None
        # NO state was stashed.
        assert state_store == {}
        oauth_credentials_store.reset_cache_for_tests()

    async def test_unsupported_entry_returns_clear_reason(
        self, db_session, test_tenant_id, test_user_id,
    ):
        state_store: dict[str, dict] = {}
        report = start_oauth_for_marketplace(
            db=db_session,
            catalog_entry_id="mcp-time",  # not OAuth at all
            base_url="http://test.local/",
            state_store=state_store,
            user_id=test_user_id,
            tenant_id=test_tenant_id,
        )

        assert report.success is False
        assert report.provider is None
        assert report.failure_reason is not None
        assert report.failure_reason.startswith(FAIL_UNSUPPORTED_PROVIDER)
        assert state_store == {}


# ──────────────────────────────────────────────────────────────────
# 6-9. /marketplace/oauth/{entry_id}/start endpoint
# ──────────────────────────────────────────────────────────────────


class TestStartEndpoint:
    async def test_happy_path_endpoint(
        self, client, auth_headers, seeded_tenant,
    ):
        from app.services.integrations import oauth_credentials_store

        oauth_credentials_store.reset_cache_for_tests()
        oauth_credentials_store._cache = {
            "github_client_id": "Iv1.fake-github-client-id",
            "github_client_secret": "fake-github-secret",
        }

        res = await client.post(
            "/api/v1/connections/v2/marketplace/oauth/app-github/start",
            headers=auth_headers,
            json={},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["success"] is True
        assert body["provider"] == "github"
        assert body["authorization_url"].startswith(
            "https://github.com/login/oauth/authorize?",
        )
        assert body["state_ref"] is not None
        assert body["redirect_uri"].endswith(
            "/api/v1/connectors/oauth/callback",
        )
        assert "repo" in body["scopes"]
        # No secrets ever surface in the response payload.
        full_text = res.text
        assert "fake-github-secret" not in full_text, (
            "endpoint LEAKED client_secret into response"
        )
        oauth_credentials_store.reset_cache_for_tests()

    async def test_unknown_entry_returns_404(
        self, client, auth_headers, seeded_tenant,
    ):
        res = await client.post(
            "/api/v1/connections/v2/marketplace/oauth/app-does-not-exist/start",
            headers=auth_headers,
            json={},
        )
        assert res.status_code == 404
        assert res.json()["detail"] == "catalog_entry_not_found"

    async def test_non_oauth_entry_returns_400(
        self, client, auth_headers, seeded_tenant,
    ):
        # cli-claude-code is a CLI runtime, not an OAuth app.
        res = await client.post(
            "/api/v1/connections/v2/marketplace/oauth/cli-claude-code/start",
            headers=auth_headers,
            json={},
        )
        assert res.status_code == 400
        assert "entry_not_oauth" in res.json()["detail"]

    async def test_configure_required_endpoint(
        self, client, auth_headers, seeded_tenant, monkeypatch,
    ):
        from app.services.integrations import oauth_credentials_store

        oauth_credentials_store.reset_cache_for_tests()
        oauth_credentials_store._cache = {}
        # And blank the settings so generate_auth_url has nothing to fall
        # back on.
        from app.core import config as core_config

        original = core_config.get_settings
        def blank_settings():
            s = original()
            # Don't actually mutate the real settings object;
            # OAuthConfigError is raised by _get_credential when
            # getattr(settings, "google_client_id", "") is empty.
            return s
        # The test's blank-cache _cache={} already forces _get_credential
        # to fall through to settings.google_client_id which is empty
        # in test env. So we don't need to monkeypatch get_settings.

        res = await client.post(
            "/api/v1/connections/v2/marketplace/oauth/app-figma/start",
            headers=auth_headers,
            json={},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is False
        assert body["failure_reason"].startswith(FAIL_CONFIGURE_REQUIRED)
        oauth_credentials_store.reset_cache_for_tests()


# ──────────────────────────────────────────────────────────────────
# 10. No-leak audit -- start payload never carries secret material
# ──────────────────────────────────────────────────────────────────


class TestNoLeak:
    async def test_response_payload_never_has_client_secret(
        self, client, auth_headers, seeded_tenant,
    ):
        from app.services.integrations import oauth_credentials_store

        sentinel = "sk-do-not-leak-9999"  # noqa: S105
        oauth_credentials_store.reset_cache_for_tests()
        oauth_credentials_store._cache = {
            "slack_client_id": "fake-slack-id",
            "slack_client_secret": sentinel,
        }

        res = await client.post(
            "/api/v1/connections/v2/marketplace/oauth/app-slack/start",
            headers=auth_headers,
            json={},
        )
        assert res.status_code == 200, res.text
        # The auth URL contains client_id (public, by-design). The
        # secret must NEVER appear anywhere in the payload.
        assert sentinel not in res.text, (
            f"start endpoint LEAKED client_secret value: {sentinel!r}"
        )
        oauth_credentials_store.reset_cache_for_tests()
