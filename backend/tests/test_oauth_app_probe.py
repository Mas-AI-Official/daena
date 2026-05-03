"""PR-CONN-OAUTH-CONNECT -- OAuthAppProbe tests.

Pins the OAuth probe contract:

  1. token_missing when vault_ref is empty
  2. token_missing when row.config has no _provider
  3. token_missing when V1 ConnectorInstance not found
  4. token_expired when expires_at is in the past
  5. happy path: token + future expiration -> success + capability spec
  6. capability spec NEVER carries access_token / refresh_token
  7. Sentinel-secret no-leak: token value never appears in failure_reason
  8. Userinfo verification (opt-in) success / failure paths
  9. Registry wiring: install_oauth_app_probe registers + idempotent
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models.connection_v2 import (
    AuthMethod,
    ConnectionKind,
    ConnectionV2,
)
from app.services.connection_v2.probe import PROBE_REGISTRY
from app.services.connection_v2.probes.oauth_app_probe import (
    FAIL_TOKEN_EXPIRED,
    FAIL_TOKEN_MISSING,
    FAIL_UNSUPPORTED_PROVIDER,
    FAIL_USERINFO_FAILED,
    FAIL_VAULT_REF_MISSING,
    OAuthAppProbe,
    OAuthProbeOptions,
    install_oauth_app_probe,
)


# ──────────────────────────────────────────────────────────────────
# Row builder + creds-loading mock
# ──────────────────────────────────────────────────────────────────


def _row(*, provider: str | None, vault_ref: str | None) -> ConnectionV2:
    """Build a non-persisted ConnectionV2 row for probe tests."""
    config: dict = {"kind": "oauth_app"}
    if provider is not None:
        config["_provider"] = provider
    return ConnectionV2(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        kind=ConnectionKind.OAUTH_APP.value,
        slug=f"oauth-{provider}" if provider else "oauth-bad",
        display_name=f"Test {provider or 'unknown'}",
        canonical_key="x" * 64,
        auth_method=AuthMethod.OAUTH_MANAGED.value,
        config=config,
        vault_ref=vault_ref,
    )


class _StubProbe(OAuthAppProbe):
    """Subclass that injects a fake credentials loader so tests don't
    need a real V1 ConnectorInstance to exercise every path."""

    def __init__(self, creds, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stub_creds = creds

    async def _load_credentials(self, vault_ref: str):  # type: ignore[override]
        return self._stub_creds


# ──────────────────────────────────────────────────────────────────
# 1. token_missing -- vault_ref empty
# ──────────────────────────────────────────────────────────────────


class TestVaultRefMissing:
    @pytest.mark.asyncio
    async def test_no_vault_ref_returns_vault_ref_missing(self):
        row = _row(provider="gmail", vault_ref=None)
        probe = OAuthAppProbe()
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "authenticated"
        assert result.failure_reason is not None
        assert result.failure_reason.startswith(FAIL_VAULT_REF_MISSING)


# ──────────────────────────────────────────────────────────────────
# 2. unsupported_provider -- no _provider in config
# ──────────────────────────────────────────────────────────────────


class TestUnsupportedProvider:
    @pytest.mark.asyncio
    async def test_no_provider_in_config_returns_unsupported(self):
        row = _row(provider=None, vault_ref=str(uuid.uuid4()))
        probe = OAuthAppProbe()
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "configured"
        assert result.failure_reason.startswith(FAIL_UNSUPPORTED_PROVIDER)


# ──────────────────────────────────────────────────────────────────
# 3. token_missing -- V1 ConnectorInstance not found
# ──────────────────────────────────────────────────────────────────


class TestV1InstanceMissing:
    @pytest.mark.asyncio
    async def test_missing_v1_instance_returns_token_missing(self):
        row = _row(provider="gmail", vault_ref=str(uuid.uuid4()))
        # Stub returns None -> probe interprets as token_missing.
        probe = _StubProbe(creds=None)
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "authenticated"
        assert result.failure_reason.startswith(FAIL_TOKEN_MISSING)


# ──────────────────────────────────────────────────────────────────
# 4. token_expired
# ──────────────────────────────────────────────────────────────────


class TestTokenExpired:
    @pytest.mark.asyncio
    async def test_past_expires_at_returns_token_expired(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        row = _row(provider="gmail", vault_ref=str(uuid.uuid4()))
        probe = _StubProbe(creds={
            "access_token": "fake-token",
            "expires_at": past,
        })
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "authenticated"
        assert result.failure_reason.startswith(FAIL_TOKEN_EXPIRED)
        # Expiration timestamp may appear (it's not secret) but token
        # value MUST NOT.
        assert "fake-token" not in result.failure_reason


# ──────────────────────────────────────────────────────────────────
# 5. Happy path -- valid future expiration
# ──────────────────────────────────────────────────────────────────


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_valid_future_token_returns_success(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        row = _row(provider="gmail", vault_ref=str(uuid.uuid4()))
        probe = _StubProbe(creds={
            "access_token": "fake-token-value",
            "expires_at": future,
            "scope": "gmail.readonly",
            "token_type": "Bearer",
            "account_identity": "operator@example.com",
        })
        result = await probe.run(row)

        assert result.success is True, result.failure_reason
        assert len(result.capabilities) == 1
        cap = result.capabilities[0]
        assert cap["name"] == "gmail"
        assert cap["kind"] == "oauth_app"
        assert cap["spec"]["provider"] == "gmail"
        assert cap["spec"]["scope"] == "gmail.readonly"
        assert cap["spec"]["token_type"] == "Bearer"
        assert cap["spec"]["account_identity"] == "operator@example.com"
        assert cap["spec"]["expires_at"] == future

    @pytest.mark.asyncio
    async def test_no_expires_at_treated_as_non_expiring(self):
        # GitHub OAuth tokens don't have expires_at by default.
        row = _row(provider="github", vault_ref=str(uuid.uuid4()))
        probe = _StubProbe(creds={
            "access_token": "ghp_fake_token_value",
            # no expires_at
            "scope": "repo,read:user",
            "token_type": "bearer",
        })
        result = await probe.run(row)
        assert result.success is True


# ──────────────────────────────────────────────────────────────────
# 6-7. No-leak: capability spec + failure_reason never carry token
# ──────────────────────────────────────────────────────────────────


class TestNoLeak:
    @pytest.mark.asyncio
    async def test_capability_spec_omits_token_values(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        sentinel_access = "sk-access-token-do-not-leak-1111"  # noqa: S105
        sentinel_refresh = "sk-refresh-token-do-not-leak-2222"  # noqa: S105
        row = _row(provider="figma", vault_ref=str(uuid.uuid4()))
        probe = _StubProbe(creds={
            "access_token": sentinel_access,
            "refresh_token": sentinel_refresh,
            "expires_at": future,
            "scope": "files:read",
        })
        result = await probe.run(row)
        assert result.success is True

        spec_text = json.dumps(result.capabilities[0]["spec"])
        assert sentinel_access not in spec_text, (
            "PROBE LEAKED access_token into capability spec"
        )
        assert sentinel_refresh not in spec_text, (
            "PROBE LEAKED refresh_token into capability spec"
        )

    @pytest.mark.asyncio
    async def test_failure_reason_never_carries_token(self):
        sentinel = "sk-leaky-token-3333"  # noqa: S105
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        row = _row(provider="slack", vault_ref=str(uuid.uuid4()))
        probe = _StubProbe(creds={
            "access_token": sentinel,
            "expires_at": past,  # forces token_expired branch
        })
        result = await probe.run(row)
        assert result.success is False
        assert sentinel not in (result.failure_reason or "")


# ──────────────────────────────────────────────────────────────────
# 8. Optional userinfo verification
# ──────────────────────────────────────────────────────────────────


class TestUserinfoVerification:
    @pytest.mark.asyncio
    async def test_userinfo_success_keeps_probe_successful(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        row = _row(provider="gmail", vault_ref=str(uuid.uuid4()))
        probe = _StubProbe(
            creds={
                "access_token": "fake",
                "expires_at": future,
            },
            options=OAuthProbeOptions(verify_userinfo=True),
        )
        # Patch the userinfo call so we don't make a real HTTP request.
        with patch.object(
            probe, "_verify_userinfo",
            return_value=(True, "operator@example.com"),
        ):
            result = await probe.run(row)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_userinfo_failure_blocks_callable(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        row = _row(provider="github", vault_ref=str(uuid.uuid4()))
        probe = _StubProbe(
            creds={
                "access_token": "fake",
                "expires_at": future,
            },
            options=OAuthProbeOptions(verify_userinfo=True),
        )
        with patch.object(
            probe, "_verify_userinfo",
            return_value=(False, FAIL_USERINFO_FAILED + ": HTTP 401"),
        ):
            result = await probe.run(row)
        assert result.success is False
        assert result.failure_dim == "callable"
        assert result.failure_reason.startswith(FAIL_USERINFO_FAILED)


# ──────────────────────────────────────────────────────────────────
# 9. Registry wiring
# ──────────────────────────────────────────────────────────────────


class TestRegistryWiring:
    def test_install_oauth_app_probe_registers(self):
        PROBE_REGISTRY.pop("oauth_app", None)
        install_oauth_app_probe()
        assert "oauth_app" in PROBE_REGISTRY
        assert isinstance(PROBE_REGISTRY["oauth_app"], OAuthAppProbe)

    def test_install_all_probes_includes_oauth(self):
        from app.services.connection_v2.probes import install_all_probes
        PROBE_REGISTRY.pop("oauth_app", None)
        install_all_probes()
        assert isinstance(PROBE_REGISTRY.get("oauth_app"), OAuthAppProbe)

    def test_install_is_idempotent(self):
        install_oauth_app_probe()
        install_oauth_app_probe()
        install_oauth_app_probe()
        assert isinstance(PROBE_REGISTRY.get("oauth_app"), OAuthAppProbe)
