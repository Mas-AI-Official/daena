"""ConnectionRegistryV2 service (Phase 4b PR 1).

CRUD over the ``connection_v2`` table + dual-read fallback to legacy
``ConnectorInstance`` rows. New secret writes go through ``vault_v2``
(envelope encryption) per ADR-002 D-003. Legacy reads via
``app.core.vault.decrypt_dict`` per founder rule 9 (legacy read path
must remain available).

Behavior gates:
- ``settings.use_connection_registry_v2`` False (production default):
  * V2 reads/writes still work for callers that explicitly invoke
    this service (e.g. /api/v1/connections/v2 routes), but the LIVE
    UI does NOT call them. Legacy ``connection_service.py`` is the
    canonical path.
- ``settings.use_connection_registry_v2`` True (dev only):
  * Future Phase 4b PR 2 routes call this service; legacy paths
    become fallback-only.

This service does NOT delete legacy modules. Per founder rules 3 + 4
(don't delete vault.py / oauth_credentials_store.py), the legacy code
stays alongside until the soak window proves zero drift.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.vault import decrypt_dict, is_encrypted
from app.core.vault_v2 import (
    SecretClass,
    decrypt_secret,
    derive_tenant_kek,
    encrypt_secret,
    generate_dek,
    unwrap_dek,
    wrap_dek,
)
from app.models.connection_v2 import (
    AuthMethod,
    ConnectionKind,
    ConnectionV2,
    ConnectionV2Capability,
    ConnectionV2OpLock,
    OpKind,
    TrustTier,
)
from app.models.connections import ConnectorInstance
from app.models.identity import Tenant
from app.models.secret import Secret
from app.services.connection_v2.op_lock import (
    acquire_op_lock,
    active_ops_for,
    release_op_lock,
)
from app.services.connection_v2.probe import run_probe
from app.services.connection_v2.state_machine import derive_label

logger = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_key(tenant_id: UUID, kind: str, slug: str, auth_method: str) -> str:
    """Stable 64-char hex key for idempotent insert + cross-tenant dedup-friendly lookup."""
    raw = f"{tenant_id}|{kind}|{slug}|{auth_method}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _bound_to_for_connection(connection_id: UUID) -> str:
    """Stable AAD bound_to identifier for vault_v2 secret writes."""
    return f"connection_v2:{connection_id}"


def _canonical_json_bytes(payload: dict) -> bytes:
    """Deterministic JSON encoding (matches vault_migration.py)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass
class ImportResult:
    """Outcome of an import operation."""

    connection: ConnectionV2
    created: bool   # True if newly inserted; False if returned existing
    secret_written: bool  # True iff vault_v2 path actually persisted a Secret row


class ConnectionRegistryV2:
    """Service-layer API for ConnectionV2.

    Stateless wrapper around an AsyncSession. Caller manages commit /
    rollback. Does NOT depend on FastAPI; safe to use in scripts +
    background jobs as well as request handlers.
    """

    def __init__(self, db: AsyncSession, *, kek_seed: bytes):
        self.db = db
        self._kek_seed = kek_seed

    # ──────────────────────────────────────────────
    # Read API
    # ──────────────────────────────────────────────

    async def get(self, *, tenant_id: UUID, connection_id: UUID) -> ConnectionV2 | None:
        return (await self.db.execute(
            select(ConnectionV2).where(
                ConnectionV2.id == connection_id,
                ConnectionV2.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()

    async def list_for_tenant(
        self, *, tenant_id: UUID, kind: ConnectionKind | None = None,
    ) -> list[ConnectionV2]:
        stmt = select(ConnectionV2).where(ConnectionV2.tenant_id == tenant_id)
        if kind is not None:
            stmt = stmt.where(ConnectionV2.kind == kind.value)
        stmt = stmt.order_by(ConnectionV2.created_at)
        return list((await self.db.execute(stmt)).scalars().all())

    async def find_by_slug(
        self, *, tenant_id: UUID, kind: ConnectionKind, slug: str,
    ) -> ConnectionV2 | None:
        return (await self.db.execute(
            select(ConnectionV2).where(
                ConnectionV2.tenant_id == tenant_id,
                ConnectionV2.kind == kind.value,
                ConnectionV2.slug == slug,
            )
        )).scalar_one_or_none()

    async def label_for(self, row: ConnectionV2) -> str:
        ops = await active_ops_for(self.db, row.id)
        return derive_label(row, ops)

    async def capabilities_count(self, connection_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).where(
                ConnectionV2Capability.connection_id == connection_id,
            )
        )
        return int(result.scalar() or 0)

    # ──────────────────────────────────────────────
    # Import (idempotent on canonical_key)
    # ──────────────────────────────────────────────

    async def import_connection(
        self,
        *,
        tenant_id: UUID,
        kind: ConnectionKind,
        slug: str,
        display_name: str,
        auth_method: AuthMethod,
        config: dict | None = None,
        trust_tier: TrustTier = TrustTier.OFFICIAL,
        secret_value: str | None = None,
    ) -> ImportResult:
        """Import a connection (durably persisted -- ADR-002 D-007).

        Idempotent on (tenant_id, kind, slug). Re-importing returns the
        existing row with ``created=False``. Secret writes go through
        ``vault_v2`` -- legacy ``vault.encrypt_dict`` is NEVER called
        from this code path.
        """
        config = config or {}

        # Idempotency check first: same (tenant, kind, slug) returns existing.
        existing = await self.find_by_slug(tenant_id=tenant_id, kind=kind, slug=slug)
        if existing is not None:
            return ImportResult(connection=existing, created=False, secret_written=False)

        now = _now()
        row = ConnectionV2(
            id=uuid4(),
            tenant_id=tenant_id,
            kind=kind.value,
            slug=slug,
            display_name=display_name,
            canonical_key=_canonical_key(tenant_id, kind.value, slug, auth_method.value),
            auth_method=auth_method.value,
            trust_tier=trust_tier.value,
            config=config,
            detected=True, detected_at=now,
            configured=True, configured_at=now,
            imported=True, imported_at=now,
        )
        self.db.add(row)
        await self.db.flush()

        secret_written = False
        if secret_value is not None and auth_method == AuthMethod.API_TOKEN:
            await self._persist_secret(
                tenant_id=tenant_id,
                connection_id=row.id,
                secret_class=SecretClass.API_KEY,
                plaintext={"api_key": secret_value},
            )
            row.vault_ref = _bound_to_for_connection(row.id)
            secret_written = True

        logger.info(
            "connection_v2.imported",
            tenant_id=str(tenant_id),
            kind=kind.value,
            slug=slug,
            connection_id=str(row.id),
            secret_written=secret_written,
        )
        return ImportResult(connection=row, created=True, secret_written=secret_written)

    # ──────────────────────────────────────────────
    # Probe orchestration
    # ──────────────────────────────────────────────

    async def probe_and_record(
        self,
        *,
        tenant_id: UUID,
        connection_id: UUID,
    ) -> tuple[ConnectionV2, str, dict]:
        """Acquire probe lock, run probe, record per-dim outcome, release.

        Returns (refreshed_row, derived_label, sanitized_outcome).
        Sanitized outcome NEVER includes secret material.
        """
        row = await self.get(tenant_id=tenant_id, connection_id=connection_id)
        if row is None:
            raise LookupError(f"connection {connection_id} not found in tenant {tenant_id}")

        token = await acquire_op_lock(self.db, connection_id=row.id, op=OpKind.PROBE.value)
        if token is None:
            # Already probing -- return current state.
            label = await self.label_for(row)
            return row, label, {"success": False, "label_after": label, "failure_reason": "probe_already_in_progress"}

        try:
            result = await run_probe(row)
            now = _now()

            if result.success:
                # Mark callable=True; clear stale failure reason.
                row.reachable = True
                row.reachable_at = now
                row.reachable_failure_at = None
                row.reachable_failure_reason = None
                if (row.auth_method or "none") != "none":
                    row.authenticated = True
                    row.authenticated_at = now
                    row.authenticated_failure_at = None
                    row.authenticated_failure_reason = None
                row.callable = True
                row.callable_at = now
                row.callable_failure_at = None
                row.callable_failure_reason = None
                row.healthy_call_ratio = 1.0
                outcome = {"success": True, "callable_at": now}
            else:
                # Record per-dim failure -- DO NOT touch other dims' reasons.
                dim = result.failure_dim or "callable"
                reason = (result.failure_reason or "probe failed")[:500]
                if dim == "reachable":
                    row.reachable = False
                    row.reachable_failure_at = now
                    row.reachable_failure_reason = reason
                elif dim == "authenticated":
                    row.authenticated = False
                    row.authenticated_failure_at = now
                    row.authenticated_failure_reason = reason
                else:
                    # Default to callable failure.
                    row.callable = False
                    row.callable_failure_at = now
                    row.callable_failure_reason = reason
                row.callable = False  # Safety: never mark callable on failure.
                # Update healthy ratio (rough EWMA-style: shift toward 0).
                row.healthy_call_ratio = max(0.0, row.healthy_call_ratio * 0.5)
                outcome = {
                    "success": False,
                    "failure_dim": dim,
                    "failure_reason": reason,
                }

            # Capability discovery -- replace last_seen_at on each cap.
            if result.success and result.capabilities:
                for cap in result.capabilities:
                    name = str(cap.get("name") or "").strip()
                    cap_kind = str(cap.get("kind") or "mcp_tool")
                    if not name:
                        continue
                    existing_cap = (await self.db.execute(
                        select(ConnectionV2Capability).where(
                            ConnectionV2Capability.connection_id == row.id,
                            ConnectionV2Capability.kind == cap_kind,
                            ConnectionV2Capability.name == name,
                        )
                    )).scalar_one_or_none()
                    if existing_cap is None:
                        self.db.add(ConnectionV2Capability(
                            id=uuid4(),
                            connection_id=row.id,
                            kind=cap_kind,
                            name=name,
                            spec=cap.get("spec") or {},
                            discovered_at=now,
                            last_seen_at=now,
                        ))
                    else:
                        existing_cap.last_seen_at = now
                        existing_cap.spec = cap.get("spec") or existing_cap.spec

            await self.db.flush()
        finally:
            await release_op_lock(
                self.db, connection_id=row.id, op=OpKind.PROBE.value, owner_token=token,
            )
        # Compute label AFTER releasing -- otherwise active_ops still
        # contains "probe" and derive_label returns "probing" forever.
        label = await self.label_for(row)
        outcome["label_after"] = label
        return row, label, outcome

    # ──────────────────────────────────────────────
    # Soft-delete
    # ──────────────────────────────────────────────

    async def archive(self, *, tenant_id: UUID, connection_id: UUID) -> ConnectionV2 | None:
        row = await self.get(tenant_id=tenant_id, connection_id=connection_id)
        if row is None:
            return None
        row.archived = True
        row.archived_at = _now()
        await self.db.flush()
        return row

    async def disable(self, *, tenant_id: UUID, connection_id: UUID) -> ConnectionV2 | None:
        row = await self.get(tenant_id=tenant_id, connection_id=connection_id)
        if row is None:
            return None
        row.disabled = True
        await self.db.flush()
        return row

    async def enable(self, *, tenant_id: UUID, connection_id: UUID) -> ConnectionV2 | None:
        row = await self.get(tenant_id=tenant_id, connection_id=connection_id)
        if row is None:
            return None
        row.disabled = False
        await self.db.flush()
        return row

    # ──────────────────────────────────────────────
    # Vault_v2 secret persistence (writes ONLY through here)
    # ──────────────────────────────────────────────

    async def _ensure_tenant_dek(self, tenant: Tenant) -> bytes:
        """Provision tenant.dek_wrapped if missing; return unwrapped DEK."""
        tenant_kek = derive_tenant_kek(self._kek_seed, str(tenant.id))
        existing = getattr(tenant, "dek_wrapped", None)
        if existing:
            try:
                return unwrap_dek(existing, tenant_kek)
            except Exception:
                logger.warning(
                    "connection_v2.dek_unwrap_failed_provisioning_fresh",
                    tenant_id=str(tenant.id),
                )
        dek = generate_dek()
        tenant.dek_wrapped = wrap_dek(dek, tenant_kek)
        await self.db.flush()
        logger.info("connection_v2.dek_provisioned", tenant_id=str(tenant.id))
        return dek

    async def _persist_secret(
        self,
        *,
        tenant_id: UUID,
        connection_id: UUID,
        secret_class: SecretClass,
        plaintext: dict,
    ) -> Secret:
        """Encrypt under vault_v2 envelope and persist into the secrets table."""
        tenant = (await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )).scalar_one()
        dek = await self._ensure_tenant_dek(tenant)

        bound_to = _bound_to_for_connection(connection_id)
        record = encrypt_secret(
            _canonical_json_bytes(plaintext),
            dek=dek,
            secret_class=secret_class,
            tenant_id=str(tenant_id),
            bound_to=bound_to,
        )
        sec = Secret(
            id=uuid4(),
            tenant_id=tenant_id,
            secret_class=record["class"],
            bound_to=record["bound_to"],
            ciphertext=base64.b64decode(record["ciphertext"]),
            nonce=base64.b64decode(record["nonce"]),
            tag=base64.b64decode(record["tag"]),
            dek_version=record["dek_version"],
            kek_version=record["kek_version"],
            format_version=record["format_version"],
        )
        self.db.add(sec)
        await self.db.flush()
        logger.info(
            "connection_v2.secret_persisted",
            tenant_id=str(tenant_id),
            connection_id=str(connection_id),
            secret_id=str(sec.id),
        )
        return sec

    # ──────────────────────────────────────────────
    # Dual-read (legacy fallback per founder rule 9)
    # ──────────────────────────────────────────────

    async def read_secret_dual(
        self,
        *,
        tenant_id: UUID,
        connection_id: UUID,
        secret_class: SecretClass = SecretClass.API_KEY,
    ) -> dict | None:
        """Read a secret. Try V2 (secrets table) first; fall back to legacy
        ``ConnectorInstance.credentials`` decrypted via vault.decrypt_dict.

        Returns the plaintext dict, or None if not found in either store.
        Per founder rule 9 -- legacy read MUST remain available.
        """
        # V2 path.
        bound_to = _bound_to_for_connection(connection_id)
        sec = (await self.db.execute(
            select(Secret).where(
                Secret.tenant_id == tenant_id,
                Secret.secret_class == secret_class.value,
                Secret.bound_to == bound_to,
            )
        )).scalar_one_or_none()
        if sec is not None:
            tenant = (await self.db.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )).scalar_one()
            tenant_kek = derive_tenant_kek(self._kek_seed, str(tenant.id))
            if not getattr(tenant, "dek_wrapped", None):
                logger.warning(
                    "connection_v2.dual_read_dek_missing",
                    tenant_id=str(tenant_id),
                )
                return None
            dek = unwrap_dek(tenant.dek_wrapped, tenant_kek)
            record = {
                "ciphertext": base64.b64encode(sec.ciphertext).decode("ascii"),
                "nonce": base64.b64encode(sec.nonce).decode("ascii"),
                "tag": base64.b64encode(sec.tag).decode("ascii"),
                "dek_version": sec.dek_version,
                "kek_version": sec.kek_version,
                "tenant_id": str(sec.tenant_id),
                "class": sec.secret_class,
                "bound_to": sec.bound_to,
                "format_version": sec.format_version,
            }
            try:
                plaintext_bytes = decrypt_secret(
                    record,
                    dek=dek,
                    secret_class=secret_class,
                    tenant_id=str(tenant_id),
                    bound_to=bound_to,
                )
                return json.loads(plaintext_bytes.decode("utf-8"))
            except Exception as exc:
                logger.warning(
                    "connection_v2.dual_read_v2_failed",
                    tenant_id=str(tenant_id),
                    connection_id=str(connection_id),
                    error_type=type(exc).__name__,
                )
                # Fall through to legacy.

        # Legacy fallback: try ConnectorInstance.credentials.
        # Phase 4b PR 1 uses connection_id as ConnectorInstance.id matching
        # by convention -- a fuller mapping comes in Phase 4b PR 2.
        legacy = (await self.db.execute(
            select(ConnectorInstance).where(
                ConnectorInstance.tenant_id == tenant_id,
                ConnectorInstance.id == connection_id,
            )
        )).scalar_one_or_none()
        if legacy is None or legacy.credentials is None:
            return None
        raw = legacy.credentials
        if isinstance(raw, dict):
            return raw if raw else None
        if isinstance(raw, str) and is_encrypted(raw):
            try:
                return decrypt_dict(raw)
            except Exception:
                return None
        return None
