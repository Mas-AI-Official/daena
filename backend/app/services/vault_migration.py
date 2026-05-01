"""Vault V1 -> V2 migration library (Phase 4a-3).

Pure-functional migration logic for re-encrypting legacy
``ConnectorInstance.credentials`` (single-key vault.py format) under the
new envelope vault (vault_v2.py).

Library lives separate from the CLI script (``backend/scripts/
migrate_vault_to_v2.py``) so the logic is unit-testable against an
in-memory SQLite session without spinning up a subprocess.

Per ADR-002 D-003 + Phase 4a-3 founder rules:
  - Dry-run by default; ``--apply`` required to write
  - NEVER prints decrypted secrets (counts + structured fields only)
  - Dual-read validates byte-stable roundtrip BEFORE persisting
  - Drift in ``--apply`` mode aborts the batch unless ``--force``
  - Legacy ``ConnectorInstance.credentials`` is NEVER nulled by this
    script (Phase 4b decides when to delete legacy)
  - Existing legacy ``vault.py`` and ``oauth_credentials_store.py``
    are NEVER deleted by this script
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
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
from app.models.connections import ConnectorInstance
from app.models.identity import Tenant
from app.models.secret import Secret

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────
# Counters and options
# ──────────────────────────────────────────────────────────────────


@dataclass
class MigrationCounters:
    """All counts maintained during a migration run.

    Mirrors founder requirement: candidate / already_migrated / skipped /
    failed / drift. Plus written (apply mode), dek_provisioned, and
    a parallel running total of bytes processed (counts only -- never
    plaintext).
    """

    candidate: int = 0           # legacy ConnectorInstance rows with credentials != NULL
    already_migrated: int = 0    # corresponding Secret row already exists
    skipped: int = 0             # plaintext unparseable / not a dict / empty
    failed: int = 0              # decrypt error (legacy or v2)
    drift: int = 0               # dual-read mismatch
    written: int = 0             # Secret rows inserted (apply mode only)
    dek_provisioned: int = 0     # tenants whose dek_wrapped was created in this run

    def as_dict(self) -> dict[str, int]:
        return dataclasses.asdict(self)


@dataclass
class MigrationOptions:
    """Operator-supplied flags. Defaults are conservative."""

    dry_run: bool = True          # WRITE NOTHING by default
    force: bool = False           # only allowed effect: continue --apply through drift
    tenant_id: UUID | None = None # restrict scope to one tenant
    limit: int | None = None      # cap candidates inspected


@dataclass
class DriftRecord:
    """One row's worth of drift diagnostics. NEVER includes plaintext.

    Captured for the report so the operator can investigate without
    needing to re-run with --force.
    """

    instance_id: UUID
    tenant_id: UUID
    bound_to: str
    reason: str  # short string: "json_decode_error", "dict_inequality", "decrypt_failed"


@dataclass
class MigrationReport:
    """Aggregate result of one migration run. Operator-facing.

    Counts + drift list + per-tenant DEK provision list. NEVER includes
    plaintext or ciphertext bytes.
    """

    options: dict[str, Any]
    counters: dict[str, int]
    drift_records: list[dict[str, Any]] = field(default_factory=list)
    aborted: bool = False
    aborted_reason: str | None = None


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def _canonical_json_bytes(payload: dict) -> bytes:
    """Deterministic JSON encoding so a roundtrip compares byte-stable.

    Sorted keys + tight separators + UTF-8 bytes. Without this, dict
    ordering could trigger false drift.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _bound_to_for_instance(instance_id: UUID) -> str:
    """Stable bound_to AAD field per connection instance.

    Phase 4b will use the same scheme so dual-read against future writes
    stays comparable.
    """
    return f"connection_instance:{instance_id}"


async def _ensure_tenant_dek(
    db: AsyncSession,
    *,
    tenant: Tenant,
    kek_seed: bytes,
    counters: MigrationCounters,
    dry_run: bool,
) -> bytes:
    """Return the tenant's DEK; provision one if missing.

    Provisioning writes ``tenants.dek_wrapped``. In dry-run, returns a
    transient DEK that is NOT persisted (so the dual-read still works
    for validation, but the tenant row is left unchanged).
    """
    tenant_kek = derive_tenant_kek(kek_seed, str(tenant.id))

    existing_wrap = getattr(tenant, "dek_wrapped", None)
    if existing_wrap:
        try:
            return unwrap_dek(existing_wrap, tenant_kek)
        except Exception:
            logger.warning(
                "vault_migration.dek_unwrap_failed",
                tenant_id=str(tenant.id),
                action="provision_replacement_skipped_dry_run" if dry_run else "provision_replacement",
            )
            # Don't auto-replace a potentially-valid DEK. Operator
            # must investigate. Return a fresh DEK so the dual-read
            # still validates the cipher path; this DEK will not be
            # persisted unless the operator re-runs after fixing the
            # underlying tenant row.
            return generate_dek()

    # No DEK yet: provision one.
    new_dek = generate_dek()
    if not dry_run:
        wrapped = wrap_dek(new_dek, tenant_kek)
        tenant.dek_wrapped = wrapped
        await db.flush()
        counters.dek_provisioned += 1
        logger.info(
            "vault_migration.dek_provisioned",
            tenant_id=str(tenant.id),
            kek_version=wrapped.get("kek_version"),
            dek_version=wrapped.get("dek_version"),
        )
    return new_dek


def _classify_legacy_credentials(raw: Any) -> tuple[dict | None, str | None]:
    """Decode legacy ``ConnectorInstance.credentials`` to a plaintext dict.

    Returns ``(plaintext_dict, None)`` on success or
    ``(None, reason_string)`` on skip/failure.

    Three legacy shapes per audit of connection_service.py:
      1. NULL (filtered out before we get here)
      2. ``enc:v1:...`` string -> decrypt via legacy vault
      3. plaintext dict (un-encrypted older row) -> use as-is
    """
    if raw is None:
        return None, "null"
    if isinstance(raw, str):
        if not is_encrypted(raw):
            return None, "string_not_encrypted_format"
        try:
            decoded = decrypt_dict(raw)
        except Exception as exc:
            return None, f"legacy_decrypt_error:{type(exc).__name__}"
        if decoded is None:
            return None, "legacy_decrypt_returned_none"
        if not isinstance(decoded, dict):
            return None, "legacy_decrypt_not_dict"
        return decoded, None
    if isinstance(raw, dict):
        if not raw:
            return None, "empty_dict"
        return raw, None
    return None, f"unsupported_type:{type(raw).__name__}"


# ──────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────


async def run_migration(
    db: AsyncSession,
    *,
    kek_seed: bytes,
    options: MigrationOptions | None = None,
) -> MigrationReport:
    """Walk legacy ConnectorInstance rows, dual-read-validate, optionally write.

    The library never reads or writes the filesystem. Caller controls
    the AsyncSession + commit. The KEK seed is passed in explicitly
    so the script can wire up ``app.core.vault_boot.load_kek_from_env``
    without this library reading env directly.
    """
    options = options or MigrationOptions()
    counters = MigrationCounters()
    drift_records: list[DriftRecord] = []

    # Graceful precheck: secrets table must exist before we run.
    # Phase 4a-2 ships migration 006_secrets_envelope_vault.py which
    # creates the table; this script requires that the operator has
    # already run `alembic upgrade head`.
    from sqlalchemy import inspect as sa_inspect

    def _has_secrets_table(sync_conn) -> bool:
        return "secrets" in sa_inspect(sync_conn).get_table_names()

    bind = await db.connection()
    if not await bind.run_sync(_has_secrets_table):
        msg = (
            "vault_migration precheck failed: 'secrets' table is missing. "
            "Run `alembic upgrade head` (apply migration 006) before invoking "
            "this script. Aborting without inspecting candidates."
        )
        logger.warning("vault_migration.precheck_failed", reason="secrets_table_missing")
        return MigrationReport(
            options={
                "dry_run": options.dry_run,
                "force": options.force,
                "tenant_id": str(options.tenant_id) if options.tenant_id else None,
                "limit": options.limit,
            },
            counters=counters.as_dict(),
            drift_records=[],
            aborted=True,
            aborted_reason="secrets_table_missing",
        )

    logger.info(
        "vault_migration.started",
        dry_run=options.dry_run,
        force=options.force,
        tenant_id=str(options.tenant_id) if options.tenant_id else None,
        limit=options.limit,
    )

    # Build query: candidates have non-null credentials; optional tenant filter.
    stmt = select(ConnectorInstance).where(ConnectorInstance.credentials.is_not(None))
    if options.tenant_id is not None:
        stmt = stmt.where(ConnectorInstance.tenant_id == options.tenant_id)
    if options.limit is not None:
        stmt = stmt.limit(options.limit)

    candidates = (await db.execute(stmt)).scalars().all()
    counters.candidate = len(candidates)

    # Cache tenant rows + their decrypted DEKs to avoid re-derivation.
    tenant_cache: dict[UUID, Tenant] = {}
    dek_cache: dict[UUID, bytes] = {}

    aborted = False
    aborted_reason: str | None = None

    for instance in candidates:
        bound_to = _bound_to_for_instance(instance.id)
        tenant_id = instance.tenant_id

        # Already migrated?
        existing = (await db.execute(
            select(Secret).where(
                Secret.tenant_id == tenant_id,
                Secret.secret_class == SecretClass.API_KEY.value,
                Secret.bound_to == bound_to,
            )
        )).scalar_one_or_none()
        if existing is not None:
            counters.already_migrated += 1
            continue

        # Decode legacy.
        plaintext_dict, skip_reason = _classify_legacy_credentials(instance.credentials)
        if plaintext_dict is None:
            counters.skipped += 1
            logger.info(
                "vault_migration.skipped",
                instance_id=str(instance.id),
                reason=skip_reason,
            )
            continue

        # Resolve tenant + DEK.
        if tenant_id not in tenant_cache:
            tenant = (await db.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )).scalar_one_or_none()
            if tenant is None:
                counters.failed += 1
                logger.warning(
                    "vault_migration.tenant_missing",
                    instance_id=str(instance.id),
                    tenant_id=str(tenant_id),
                )
                continue
            tenant_cache[tenant_id] = tenant

        tenant = tenant_cache[tenant_id]
        if tenant_id not in dek_cache:
            dek_cache[tenant_id] = await _ensure_tenant_dek(
                db, tenant=tenant, kek_seed=kek_seed,
                counters=counters, dry_run=options.dry_run,
            )
        dek = dek_cache[tenant_id]

        # Encrypt under v2.
        plaintext_bytes = _canonical_json_bytes(plaintext_dict)
        try:
            record = encrypt_secret(
                plaintext_bytes,
                dek=dek,
                secret_class=SecretClass.API_KEY,
                tenant_id=str(tenant_id),
                bound_to=bound_to,
            )
        except Exception as exc:
            counters.failed += 1
            logger.warning(
                "vault_migration.encrypt_failed",
                instance_id=str(instance.id),
                error_type=type(exc).__name__,
            )
            continue

        # Dual-read validation: decrypt the freshly produced record and
        # compare to the original plaintext_dict. NEVER print plaintext.
        try:
            roundtripped_bytes = decrypt_secret(
                record,
                dek=dek,
                secret_class=SecretClass.API_KEY,
                tenant_id=str(tenant_id),
                bound_to=bound_to,
            )
        except Exception as exc:
            counters.drift += 1
            drift_records.append(DriftRecord(
                instance_id=instance.id,
                tenant_id=tenant_id,
                bound_to=bound_to,
                reason=f"decrypt_failed:{type(exc).__name__}",
            ))
            logger.warning(
                "vault_migration.drift",
                instance_id=str(instance.id),
                reason="decrypt_failed",
                error_type=type(exc).__name__,
            )
            if not options.dry_run and not options.force:
                aborted = True
                aborted_reason = "drift_decrypt_failed"
                break
            continue

        try:
            roundtripped_dict = json.loads(roundtripped_bytes.decode("utf-8"))
        except Exception:
            counters.drift += 1
            drift_records.append(DriftRecord(
                instance_id=instance.id,
                tenant_id=tenant_id,
                bound_to=bound_to,
                reason="json_decode_error",
            ))
            logger.warning(
                "vault_migration.drift",
                instance_id=str(instance.id),
                reason="json_decode_error",
            )
            if not options.dry_run and not options.force:
                aborted = True
                aborted_reason = "drift_json_decode"
                break
            continue

        if roundtripped_dict != plaintext_dict:
            counters.drift += 1
            drift_records.append(DriftRecord(
                instance_id=instance.id,
                tenant_id=tenant_id,
                bound_to=bound_to,
                reason="dict_inequality",
            ))
            logger.warning(
                "vault_migration.drift",
                instance_id=str(instance.id),
                reason="dict_inequality",
            )
            if not options.dry_run and not options.force:
                aborted = True
                aborted_reason = "drift_dict_inequality"
                break
            continue

        # Dual-read passed.
        if options.dry_run:
            # Don't write. The successful encrypt+decrypt validated the
            # cipher path for this row.
            continue

        # Apply mode: persist the Secret row.
        import base64
        sec = Secret(
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
        db.add(sec)
        await db.flush()
        counters.written += 1
        logger.info(
            "vault_migration.row_written",
            instance_id=str(instance.id),
            tenant_id=str(tenant_id),
            secret_id=str(sec.id),
            kek_version=record["kek_version"],
            dek_version=record["dek_version"],
        )

    # Final structured log -- counts only.
    logger.info(
        "vault_migration.complete",
        aborted=aborted,
        aborted_reason=aborted_reason,
        **counters.as_dict(),
    )

    return MigrationReport(
        options={
            "dry_run": options.dry_run,
            "force": options.force,
            "tenant_id": str(options.tenant_id) if options.tenant_id else None,
            "limit": options.limit,
        },
        counters=counters.as_dict(),
        drift_records=[dataclasses.asdict(d) for d in drift_records],
        aborted=aborted,
        aborted_reason=aborted_reason,
    )
