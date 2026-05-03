"""OAuthAppProbe -- token-presence + expiration probe for OAuth app rows.

PR-CONN-OAUTH-CONNECT (2026-05-02). Replaces the structured
``probe_unavailable`` outcome for ``kind=oauth_app`` rows with a real
probe that:

  1. Follows ``row.vault_ref`` back to the V1 ``ConnectorInstance``
     where the AES-encrypted token blob lives.
  2. Decrypts via ``app.core.vault.decrypt_dict`` (same vault V1 used
     to encrypt -- founder rule 12: do not duplicate secret storage).
  3. Checks token presence + expiration. Optionally verifies via the
     provider's userinfo endpoint when one is documented + safe.
  4. Returns one of the founder-listed states:
       - token_missing
       - token_expired
       - refresh_failed (reserved for future PR; today maps to expired)
       - userinfo_failed
       - unsupported_provider

Per founder rule 13: failure_reason and capability spec NEVER carry
the access_token / refresh_token / client_secret value.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.core.logging import get_logger
from app.models.connection_v2 import ConnectionKind, ConnectionV2
from app.services.connection_v2.probe import Probe, ProbeResult

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────
# Failure prefixes
# ──────────────────────────────────────────────────────────────────


FAIL_TOKEN_MISSING = "token_missing"
FAIL_TOKEN_EXPIRED = "token_expired"
FAIL_REFRESH_FAILED = "refresh_failed"
FAIL_USERINFO_FAILED = "userinfo_failed"
FAIL_UNSUPPORTED_PROVIDER = "unsupported_provider"
FAIL_VAULT_REF_MISSING = "vault_ref_missing"
FAIL_VAULT_DECRYPT_FAILED = "vault_decrypt_failed"


_REASON_PREVIEW = 200


def _reason(prefix: str, detail: str = "") -> str:
    if not detail:
        return prefix
    cleaned = detail.replace("\n", " ").replace("\r", " ").strip()
    if len(cleaned) > _REASON_PREVIEW:
        cleaned = cleaned[:_REASON_PREVIEW] + "..."
    return f"{prefix}: {cleaned}"


# ──────────────────────────────────────────────────────────────────
# Probe
# ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OAuthProbeOptions:
    """Per-step caps + feature toggles."""

    userinfo: float = 6.0           # max seconds for the userinfo round-trip
    verify_userinfo: bool = False   # off by default; opt-in via this PR's tests


DEFAULT_OPTIONS = OAuthProbeOptions()


class OAuthAppProbe(Probe):
    """Read tokens through vault_ref + verify they're usable."""

    kind = ConnectionKind.OAUTH_APP

    def __init__(self, options: OAuthProbeOptions | None = None) -> None:
        self.options = options or DEFAULT_OPTIONS

    async def run(self, row: ConnectionV2) -> ProbeResult:
        config: dict[str, Any] = row.config or {}
        provider = str(config.get("_provider") or "").strip()
        if not provider:
            return ProbeResult(
                success=False,
                failure_dim="configured",
                failure_reason=_reason(
                    FAIL_UNSUPPORTED_PROVIDER,
                    "row.config missing '_provider' key",
                ),
            )

        vault_ref = (row.vault_ref or "").strip()
        if not vault_ref:
            return ProbeResult(
                success=False,
                failure_dim="authenticated",
                failure_reason=_reason(
                    FAIL_VAULT_REF_MISSING,
                    "vault_ref empty -- callback never wrote a token",
                ),
            )

        # Resolve V1 ConnectorInstance -> credentials blob.
        creds = await self._load_credentials(vault_ref)
        if creds is None:
            return ProbeResult(
                success=False,
                failure_dim="authenticated",
                failure_reason=_reason(
                    FAIL_TOKEN_MISSING,
                    f"no V1 ConnectorInstance for vault_ref={vault_ref}",
                ),
            )
        if creds == "decrypt_failed":
            return ProbeResult(
                success=False,
                failure_dim="authenticated",
                failure_reason=_reason(
                    FAIL_VAULT_DECRYPT_FAILED,
                    "vault decrypt returned None -- KEK mismatch?",
                ),
            )

        access_token = str(creds.get("access_token") or "")
        if not access_token:
            return ProbeResult(
                success=False,
                failure_dim="authenticated",
                failure_reason=_reason(
                    FAIL_TOKEN_MISSING,
                    "access_token field empty in stored credentials",
                ),
            )

        # Expiration check (some providers, e.g. GitHub, omit expires_at;
        # treat empty as "doesn't expire").
        expires_at_str = str(creds.get("expires_at") or "")
        if expires_at_str:
            expired = self._is_expired(expires_at_str)
            if expired is True:
                return ProbeResult(
                    success=False,
                    failure_dim="authenticated",
                    failure_reason=_reason(
                        FAIL_TOKEN_EXPIRED,
                        f"token expired at {expires_at_str}",
                    ),
                )
            # expired is None when we couldn't parse expires_at; treat
            # as "still valid" rather than fail-closed -- the userinfo
            # call (if enabled) will catch a truly bad token.

        # Optional userinfo round-trip. Off by default to keep probes
        # cheap + offline-safe; tests opt in via OAuthProbeOptions.
        if self.options.verify_userinfo:
            ok, identity_or_reason = await self._verify_userinfo(
                provider=provider, access_token=access_token,
            )
            if not ok:
                return ProbeResult(
                    success=False,
                    failure_dim="callable",
                    failure_reason=identity_or_reason,
                )

        identity = str(creds.get("account_identity") or "")
        return ProbeResult(
            success=True,
            capabilities=[{
                "name": provider,
                "kind": "oauth_app",
                "spec": _safe_spec(provider, creds, identity),
            }],
        )

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    async def _load_credentials(self, vault_ref: str) -> dict | str | None:
        """Resolve vault_ref (-> V1 ConnectorInstance.id) and decrypt creds.

        Returns:
          dict -- decrypted credentials
          "decrypt_failed" -- ConnectorInstance found but decrypt returned None
          None -- ConnectorInstance not found

        Reads through the V1 storage path on purpose -- founder rule
        12: do not duplicate secret storage. ``app.core.vault.decrypt_dict``
        is the exact function V1's callback used to encrypt.
        """
        try:
            instance_id = UUID(vault_ref)
        except ValueError:
            return None

        try:
            from sqlalchemy import select
            from app.core.database import get_db_session_maker
            from app.core.vault import decrypt_dict
            from app.models.connections import ConnectorInstance
        except ImportError:
            logger.warning("oauth_app_probe.v1_imports_unavailable")
            return None

        try:
            session_maker = get_db_session_maker()
            async with session_maker() as session:
                instance = (
                    await session.execute(
                        select(ConnectorInstance).where(
                            ConnectorInstance.id == instance_id,
                        )
                    )
                ).scalar_one_or_none()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "oauth_app_probe.v1_lookup_failed",
                vault_ref=vault_ref, error_type=type(exc).__name__,
            )
            return None

        if instance is None:
            return None
        encrypted = instance.credentials
        if not encrypted:
            return {}  # row exists but no creds yet
        if isinstance(encrypted, dict):
            # Some legacy rows store unencrypted dicts; treat as creds.
            return encrypted
        try:
            decrypted = decrypt_dict(encrypted)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "oauth_app_probe.decrypt_raised",
                vault_ref=vault_ref, error_type=type(exc).__name__,
            )
            return "decrypt_failed"
        if decrypted is None:
            return "decrypt_failed"
        return decrypted

    @staticmethod
    def _is_expired(expires_at_iso: str) -> bool | None:
        """Compare ISO8601 expires_at to now-UTC. None = unparseable."""
        try:
            ts = datetime.fromisoformat(expires_at_iso)
        except ValueError:
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= ts

    async def _verify_userinfo(
        self, *, provider: str, access_token: str,
    ) -> tuple[bool, str]:
        """Call provider's userinfo endpoint to prove token still works.

        Returns (True, identity) on success, (False, failure_reason) on
        failure. NEVER includes the token in the failure reason.
        """
        try:
            from app.services.integrations.oauth_service import (
                ConnectorOAuthService,
            )
        except ImportError:
            return False, _reason(FAIL_USERINFO_FAILED, "oauth_service unavailable")

        try:
            # ConnectorOAuthService doesn't need a real DB session for
            # fetch_account_identity (it's a pure HTTP call).
            service = ConnectorOAuthService(db=None)
            identity = await asyncio.wait_for(
                service.fetch_account_identity(access_token, provider=provider),
                timeout=self.options.userinfo,
            )
        except asyncio.TimeoutError:
            return False, _reason(
                FAIL_USERINFO_FAILED,
                f"userinfo call exceeded {self.options.userinfo}s",
            )
        except Exception as exc:  # noqa: BLE001
            return False, _reason(
                FAIL_USERINFO_FAILED, f"{type(exc).__name__}",
            )

        if not identity:
            return False, _reason(
                FAIL_USERINFO_FAILED, "provider returned empty identity",
            )
        return True, identity


def _safe_spec(provider: str, creds: dict, identity: str) -> dict:
    """Capability spec for the V2 capability row.

    Carries provider id + scope list + masked identity. NEVER includes
    access_token / refresh_token / client_id / client_secret.
    """
    out: dict[str, Any] = {
        "provider": provider,
        "token_type": str(creds.get("token_type") or "Bearer"),
        "scope": str(creds.get("scope") or ""),
    }
    if identity:
        out["account_identity"] = identity
    expires_at = creds.get("expires_at")
    if expires_at:
        out["expires_at"] = str(expires_at)
    return out


def install_oauth_app_probe(options: OAuthProbeOptions | None = None) -> None:
    """Register the OAuthAppProbe. Idempotent (last write wins)."""
    from app.services.connection_v2.probe import register_probe
    register_probe(OAuthAppProbe(options=options))


__all__ = [
    "DEFAULT_OPTIONS",
    "FAIL_REFRESH_FAILED",
    "FAIL_TOKEN_EXPIRED",
    "FAIL_TOKEN_MISSING",
    "FAIL_UNSUPPORTED_PROVIDER",
    "FAIL_USERINFO_FAILED",
    "FAIL_VAULT_DECRYPT_FAILED",
    "FAIL_VAULT_REF_MISSING",
    "OAuthAppProbe",
    "OAuthProbeOptions",
    "install_oauth_app_probe",
]
