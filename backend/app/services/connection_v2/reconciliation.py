"""Phase 4b PR 3: ConnectionV2 reconciliation service.

Compares legacy ``ConnectorInstance`` rows, ``ConnectionV2`` rows, and
``Secret`` rows to surface drift between the three sources of truth
during the soak window. Always read-only by default; mutation only
under explicit ``apply=True`` and only when the dev feature flag is
on.

Drift kinds:
  * ``missing_v2_mirror``      -- legacy row exists, no V2 row
  * ``missing_legacy_row``     -- V2 row exists, no legacy row
  * ``status_mismatch``        -- legacy.status disagrees with V2
                                  derived label mapped via
                                  ``label_to_legacy_status``
  * ``stale_probe``            -- V2 row callable=True but
                                  callable_at older than
                                  ``stale_probe_threshold`` (default
                                  24h)
  * ``secret_drift``           -- legacy ConnectorInstance.credentials
                                  is encrypted but no matching Secret
                                  row exists in V2 vault
                                  (informational; vault migration
                                  PR ships the actual fix)
  * ``orphan_op_lock``         -- ConnectionV2OpLock with expires_at
                                  in the past (cron should have
                                  cleaned it up)

Every report entry NEVER includes plaintext secrets, KEK material,
or DEK bytes. Names + ids only.

Per founder rule (overnight authorization):
  * Always dry-run by default
  * Mutation requires apply=True AND dev feature flag (or founder
    override token, but that is a separate API gate -- this service
    just enforces "no mutation without apply")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.connection_v2 import (
    ConnectionV2,
    ConnectionV2OpLock,
)
from app.models.connections import Connector, ConnectorInstance
from app.models.secret import Secret
from app.services.connection_v2.legacy_bridge import (
    _kind_for_connector,
    _slug_for_instance,
    label_to_legacy_status,
)
from app.services.connection_v2.op_lock import active_ops_for
from app.services.connection_v2.state_machine import derive_label

logger = get_logger(__name__)

# Default thresholds. Tunable per call.
DEFAULT_STALE_PROBE_THRESHOLD = timedelta(hours=24)


# ──────────────────────────────────────────────────────────────────
# Report dataclasses
# ──────────────────────────────────────────────────────────────────


@dataclass
class DriftEntry:
    """One drift finding. Names + ids only -- never secret material."""

    kind: str  # missing_v2_mirror | missing_legacy_row | status_mismatch | stale_probe | secret_drift | orphan_op_lock
    severity: str  # info | warn | error
    tenant_id: str | None = None
    legacy_instance_id: str | None = None
    v2_connection_id: str | None = None
    detail: str = ""
    suggested_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "tenant_id": self.tenant_id,
            "legacy_instance_id": self.legacy_instance_id,
            "v2_connection_id": self.v2_connection_id,
            "detail": self.detail,
            "suggested_action": self.suggested_action,
        }


@dataclass
class ReconciliationReport:
    """Structured output of one reconciliation run.

    Counts are summarised; drift list is the full per-row detail.
    Safe to serialise to JSON for the API + CLI.
    """

    started_at: datetime
    finished_at: datetime
    apply_mode: bool
    legacy_row_count: int = 0
    v2_row_count: int = 0
    secret_row_count: int = 0
    drift: list[DriftEntry] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)
    mutations_applied: int = 0

    def add(self, entry: DriftEntry) -> None:
        self.drift.append(entry)
        self.counters[entry.kind] = self.counters.get(entry.kind, 0) + 1

    @property
    def has_drift(self) -> bool:
        return any(e.severity in ("warn", "error") for e in self.drift)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_ms": int(
                (self.finished_at - self.started_at).total_seconds() * 1000
            ),
            "apply_mode": self.apply_mode,
            "legacy_row_count": self.legacy_row_count,
            "v2_row_count": self.v2_row_count,
            "secret_row_count": self.secret_row_count,
            "mutations_applied": self.mutations_applied,
            "counters": dict(self.counters),
            "drift": [d.to_dict() for d in self.drift],
            "has_drift": self.has_drift,
        }


# ──────────────────────────────────────────────────────────────────
# Service
# ──────────────────────────────────────────────────────────────────


class ConnectionReconciliationService:
    """Read-only by default. Mutation requires explicit apply=True.

    Caller is responsible for the dev/founder gate on the API side --
    this service exists to be a pure data check + reporter. The
    ``apply`` knob is a safety gate: even when the dev flag is on,
    nothing is written until ``apply=True`` is passed AND the V2
    feature flag is on.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(
        self,
        *,
        tenant_id: UUID | None = None,
        apply: bool = False,
        stale_probe_threshold: timedelta | None = None,
    ) -> ReconciliationReport:
        """Run reconciliation and return a structured report.

        Args:
            tenant_id: limit scope to a single tenant. None = all.
            apply: when True, perform the safe automatic remediations
                (currently only orphan op-lock cleanup). Even with
                apply=True, never mutates legacy rows or secrets --
                those need explicit founder approval per ADR-002.
            stale_probe_threshold: callable rows older than this are
                tagged stale_probe. Default 24h.
        """
        from app.services.connection_v2.legacy_bridge import is_v2_enabled

        threshold = stale_probe_threshold or DEFAULT_STALE_PROBE_THRESHOLD
        started = _now()
        report = ReconciliationReport(
            started_at=started, finished_at=started, apply_mode=apply,
        )

        # Block mutation when V2 flag is off -- safety belt.
        if apply and not is_v2_enabled():
            logger.warning(
                "reconciliation.apply_blocked_flag_off",
                tenant_id=str(tenant_id) if tenant_id else None,
            )
            apply = False
            report.add(DriftEntry(
                kind="apply_refused_flag_off",
                severity="error",
                tenant_id=str(tenant_id) if tenant_id else None,
                detail=(
                    "apply=True requested but USE_CONNECTION_REGISTRY_V2 is "
                    "False. Refusing all mutation; report continues read-only."
                ),
                suggested_action=(
                    "Set USE_CONNECTION_REGISTRY_V2=True in dev .env to "
                    "enable mutation, or run with apply=False."
                ),
            ))

        # Load all three tables (filtered by tenant if requested).
        legacy_rows = await self._load_legacy(tenant_id)
        v2_rows = await self._load_v2(tenant_id)
        secret_rows = await self._load_secrets(tenant_id)
        report.legacy_row_count = len(legacy_rows)
        report.v2_row_count = len(v2_rows)
        report.secret_row_count = len(secret_rows)

        # Cache connector lookup (for slug derivation).
        connector_ids = {r.connector_id for r in legacy_rows}
        connectors = await self._load_connectors(connector_ids)

        # Index V2 rows by canonical key (tenant_id, kind, slug).
        v2_by_key: dict[tuple[str, str, str], ConnectionV2] = {}
        for v2 in v2_rows:
            v2_by_key[(str(v2.tenant_id), v2.kind, v2.slug)] = v2

        legacy_keys_seen: set[tuple[str, str, str]] = set()

        # ── 1. Legacy -> V2 mirror checks ──
        for legacy in legacy_rows:
            connector = connectors.get(legacy.connector_id)
            if connector is None:
                report.add(DriftEntry(
                    kind="legacy_orphan_connector",
                    severity="warn",
                    tenant_id=str(legacy.tenant_id),
                    legacy_instance_id=str(legacy.id),
                    detail=(
                        f"legacy instance {legacy.id} references non-existent "
                        f"connector {legacy.connector_id}"
                    ),
                    suggested_action=(
                        "investigate why connector was deleted while instance "
                        "still references it"
                    ),
                ))
                continue

            kind = _kind_for_connector(connector)
            slug = _slug_for_instance(connector, legacy.user_id)
            key = (str(legacy.tenant_id), kind.value, slug)
            legacy_keys_seen.add(key)
            v2_match = v2_by_key.get(key)

            if v2_match is None:
                report.add(DriftEntry(
                    kind="missing_v2_mirror",
                    severity="warn",
                    tenant_id=str(legacy.tenant_id),
                    legacy_instance_id=str(legacy.id),
                    detail=(
                        f"legacy '{connector.name}' for user {legacy.user_id} "
                        f"has no V2 row at slug={slug}"
                    ),
                    suggested_action=(
                        "enable USE_CONNECTION_REGISTRY_V2 then re-install or "
                        "re-connect the connector to trigger mirror_legacy_install"
                    ),
                ))
                continue

            # ── 2. Status mismatch ──
            active_ops = await active_ops_for(self.db, v2_match.id)
            v2_label = derive_label(v2_match, active_ops)
            expected_legacy = label_to_legacy_status(v2_label)
            if legacy.status != expected_legacy:
                report.add(DriftEntry(
                    kind="status_mismatch",
                    severity="warn",
                    tenant_id=str(legacy.tenant_id),
                    legacy_instance_id=str(legacy.id),
                    v2_connection_id=str(v2_match.id),
                    detail=(
                        f"legacy.status={legacy.status} but V2 label="
                        f"{v2_label} -> expected legacy.status={expected_legacy}"
                    ),
                    suggested_action=(
                        "next install/connect/probe will overwrite legacy "
                        "status from V2; or invoke ConnectionRegistryV2.probe "
                        "to refresh truth"
                    ),
                ))

            # ── 3. Stale probe ──
            if v2_match.callable and v2_match.callable_at is not None:
                callable_at = v2_match.callable_at
                # SQLite drops tz info; re-attach UTC for comparison.
                if callable_at.tzinfo is None:
                    callable_at = callable_at.replace(tzinfo=timezone.utc)
                age = _now() - callable_at
                if age > threshold:
                    report.add(DriftEntry(
                        kind="stale_probe",
                        severity="info",
                        tenant_id=str(legacy.tenant_id),
                        legacy_instance_id=str(legacy.id),
                        v2_connection_id=str(v2_match.id),
                        detail=(
                            f"V2 row callable_at is {age.total_seconds() / 3600:.1f}h "
                            f"old (> {threshold.total_seconds() / 3600:.1f}h "
                            f"threshold); label collapses to *_stale"
                        ),
                        suggested_action=(
                            "trigger probe via "
                            "POST /api/v1/connections/v2/{id}/probe"
                        ),
                    ))

            # ── 4. Secret drift (informational) ──
            await self._check_secret_drift(legacy, v2_match, report)

        # ── 5. V2-only rows (no legacy mirror) ──
        for key, v2 in v2_by_key.items():
            if key in legacy_keys_seen:
                continue
            report.add(DriftEntry(
                kind="missing_legacy_row",
                severity="info",
                tenant_id=str(v2.tenant_id),
                v2_connection_id=str(v2.id),
                detail=(
                    f"V2 row {v2.kind}/{v2.slug} has no legacy "
                    f"ConnectorInstance counterpart (V2-native row, "
                    f"expected for new-style imports)"
                ),
                suggested_action=None,
            ))

        # ── 6. Orphan op-locks ──
        await self._check_orphan_op_locks(tenant_id, report, apply)

        report.finished_at = _now()
        logger.info(
            "reconciliation.run_complete",
            tenant_id=str(tenant_id) if tenant_id else None,
            apply=apply,
            legacy_count=report.legacy_row_count,
            v2_count=report.v2_row_count,
            drift_total=len(report.drift),
            mutations=report.mutations_applied,
        )
        return report

    # ──────────────────────────────────────────────────────────
    # Internal queries
    # ──────────────────────────────────────────────────────────

    async def _load_legacy(self, tenant_id: UUID | None) -> list[ConnectorInstance]:
        stmt = select(ConnectorInstance)
        if tenant_id is not None:
            stmt = stmt.where(ConnectorInstance.tenant_id == tenant_id)
        return list((await self.db.execute(stmt)).scalars().all())

    async def _load_v2(self, tenant_id: UUID | None) -> list[ConnectionV2]:
        stmt = select(ConnectionV2)
        if tenant_id is not None:
            stmt = stmt.where(ConnectionV2.tenant_id == tenant_id)
        return list((await self.db.execute(stmt)).scalars().all())

    async def _load_secrets(self, tenant_id: UUID | None) -> list[Secret]:
        stmt = select(Secret)
        if tenant_id is not None:
            stmt = stmt.where(Secret.tenant_id == tenant_id)
        return list((await self.db.execute(stmt)).scalars().all())

    async def _load_connectors(self, ids: set[UUID]) -> dict[UUID, Connector]:
        if not ids:
            return {}
        rows = (await self.db.execute(
            select(Connector).where(Connector.id.in_(ids))
        )).scalars().all()
        return {r.id: r for r in rows}

    async def _check_secret_drift(
        self,
        legacy: ConnectorInstance,
        v2_match: ConnectionV2,
        report: ReconciliationReport,
    ) -> None:
        """Inspect whether legacy creds have a V2 vault counterpart.

        Read-only. Never decrypts. Just checks for *presence* of a
        Secret row bound to this V2 connection. Plaintext is never
        loaded. Per founder spec: report does not print secrets.
        """
        if legacy.credentials is None:
            return
        # bound_to convention: see legacy_bridge / registry._bound_to_for_connection
        bound_to = f"connection_v2:{v2_match.id}"
        count = await self.db.execute(
            select(Secret.id).where(
                Secret.tenant_id == legacy.tenant_id,
                Secret.bound_to == bound_to,
            ).limit(1)
        )
        has_secret = count.scalar_one_or_none() is not None
        if not has_secret:
            report.add(DriftEntry(
                kind="secret_drift",
                severity="info",
                tenant_id=str(legacy.tenant_id),
                legacy_instance_id=str(legacy.id),
                v2_connection_id=str(v2_match.id),
                detail=(
                    "legacy ConnectorInstance has credentials but no V2 Secret "
                    "row exists for this connection (vault migration pending)"
                ),
                suggested_action=(
                    "run backend/scripts/migrate_vault_to_v2.py --dry-run "
                    "then --apply (founder approval required)"
                ),
            ))

    async def _check_orphan_op_locks(
        self,
        tenant_id: UUID | None,
        report: ReconciliationReport,
        apply: bool,
    ) -> None:
        """Find expired op-locks. Optionally clean them up under apply=True."""
        now = _now()
        stmt = select(ConnectionV2OpLock).where(
            ConnectionV2OpLock.expires_at < now,
        )
        if tenant_id is not None:
            stmt = stmt.where(
                ConnectionV2OpLock.connection_id.in_(
                    select(ConnectionV2.id).where(
                        ConnectionV2.tenant_id == tenant_id,
                    )
                )
            )
        orphans = list((await self.db.execute(stmt)).scalars().all())
        for lock in orphans:
            report.add(DriftEntry(
                kind="orphan_op_lock",
                severity="warn",
                v2_connection_id=str(lock.connection_id),
                detail=(
                    f"op_lock {lock.op} expired at {lock.expires_at.isoformat()} "
                    f"(now {now.isoformat()})"
                ),
                suggested_action=(
                    "delete the row; safe automatic cleanup with apply=True"
                ),
            ))
            if apply:
                await self.db.delete(lock)
                report.mutations_applied += 1
        if apply and orphans:
            await self.db.flush()


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "ConnectionReconciliationService",
    "DriftEntry",
    "ReconciliationReport",
    "DEFAULT_STALE_PROBE_THRESHOLD",
]
