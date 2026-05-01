"""Phase 4b PR 3 tests: ConnectionReconciliationService.

Founder-mandated test cases:
  1. zero drift case
  2. missing V2 mirror
  3. status mismatch
  4. stale probe
  5. legacy-only row
  6. v2-only row
  7. feature flag off blocks unsafe behavior (apply=True)
  8. report does not print secrets / KEK / DEK material
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.constants import ConnectorStatus
from app.models.connection_v2 import (
    AuthMethod as V2AuthMethod,
    ConnectionKind,
    ConnectionV2,
    ConnectionV2OpLock,
)
from app.models.connections import Connector, ConnectorInstance
from app.models.identity import Tenant, User
from app.models.secret import Secret
from app.services.connection_v2 import legacy_bridge
from app.services.connection_v2.legacy_bridge import (
    _kind_for_connector,
    _slug_for_instance,
)
from app.services.connection_v2.reconciliation import (
    ConnectionReconciliationService,
    DriftEntry,
    ReconciliationReport,
)


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_tenant(db_session):
    """Per-test tenant -- avoid shared id collisions when service.commit()
    bypasses the per-test rollback."""
    tid = uuid.uuid4()
    tenant = Tenant(
        id=tid, name="Recon", slug=f"recon-{uuid.uuid4().hex[:8]}",
        settings={},
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def seeded_user(db_session, seeded_tenant):
    user = User(
        id=uuid.uuid4(),
        tenant_id=seeded_tenant.id,
        email=f"recon-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        role="FOUNDER",
        settings={},
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def seeded_connector(db_session, seeded_tenant):
    c = Connector(
        id=uuid.uuid4(),
        name=f"ReconConn-{uuid.uuid4().hex[:6]}",
        description="reconciliation test connector",
        auth_type="API_KEY",
        config_schema={},
        tools=[],
        category="test",
    )
    db_session.add(c)
    await db_session.flush()
    return c


async def _make_legacy(db_session, connector, user, status: str = "INSTALLED",
                       credentials=None) -> ConnectorInstance:
    inst = ConnectorInstance(
        id=uuid.uuid4(),
        connector_id=connector.id,
        user_id=user.id,
        tenant_id=user.tenant_id,
        credentials=credentials,
        status=status,
    )
    db_session.add(inst)
    await db_session.flush()
    return inst


async def _make_v2_for_legacy(
    db_session, connector, user, *,
    detected: bool = True, configured: bool = True, imported: bool = True,
    reachable: bool = False, authenticated: bool = False, callable_: bool = False,
    callable_at: datetime | None = None,
) -> ConnectionV2:
    kind = _kind_for_connector(connector)
    slug = _slug_for_instance(connector, user.id)
    now = datetime.now(timezone.utc)
    row = ConnectionV2(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        kind=kind.value,
        slug=slug,
        display_name=connector.name,
        canonical_key=f"k-{uuid.uuid4().hex[:16]}",
        auth_method=V2AuthMethod.API_TOKEN.value,
        trust_tier="official",
        config={"_legacy_user_id": str(user.id)},
        detected=detected, detected_at=now if detected else None,
        configured=configured, configured_at=now if configured else None,
        imported=imported, imported_at=now if imported else None,
        reachable=reachable, reachable_at=now if reachable else None,
        authenticated=authenticated, authenticated_at=now if authenticated else None,
        callable=callable_, callable_at=callable_at,
    )
    db_session.add(row)
    await db_session.flush()
    return row


# ──────────────────────────────────────────────────────────────────
# 1. Zero drift case
# ──────────────────────────────────────────────────────────────────


class TestZeroDrift:
    @pytest.mark.asyncio
    async def test_empty_db_yields_zero_drift(self, db_session):
        # Scope to a fresh tenant id so committed rows from other tests
        # in the session-scoped engine can't leak into this assertion.
        svc = ConnectionReconciliationService(db_session)
        report = await svc.run(tenant_id=uuid.uuid4(), apply=False)
        assert report.legacy_row_count == 0
        assert report.v2_row_count == 0
        assert report.has_drift is False
        assert report.counters == {}
        assert report.mutations_applied == 0

    @pytest.mark.asyncio
    async def test_perfect_mirror_no_drift(
        self, db_session, seeded_tenant, seeded_user, seeded_connector,
    ):
        """Legacy + V2 row both exist, status agrees, no stale probe."""
        legacy = await _make_legacy(
            db_session, seeded_connector, seeded_user,
            status=ConnectorStatus.ERROR.value,  # matches V2 'failed'
        )
        await _make_v2_for_legacy(
            db_session, seeded_connector, seeded_user,
        )  # all defaults: imported=T, reachable=F -> label='failed' -> ERROR

        svc = ConnectionReconciliationService(db_session)
        report = await svc.run(tenant_id=seeded_tenant.id, apply=False)
        assert report.legacy_row_count == 1
        assert report.v2_row_count == 1
        # No status mismatch, no missing mirror, no stale_probe.
        assert "missing_v2_mirror" not in report.counters
        assert "status_mismatch" not in report.counters
        assert "stale_probe" not in report.counters


# ──────────────────────────────────────────────────────────────────
# 2. Missing V2 mirror
# ──────────────────────────────────────────────────────────────────


class TestMissingV2Mirror:
    @pytest.mark.asyncio
    async def test_legacy_without_v2_yields_missing_mirror(
        self, db_session, seeded_tenant, seeded_user, seeded_connector,
    ):
        legacy = await _make_legacy(db_session, seeded_connector, seeded_user)

        svc = ConnectionReconciliationService(db_session)
        report = await svc.run(tenant_id=seeded_tenant.id, apply=False)
        assert report.counters.get("missing_v2_mirror", 0) == 1
        # The drift entry references the legacy id.
        entry = next(d for d in report.drift if d.kind == "missing_v2_mirror")
        assert entry.legacy_instance_id == str(legacy.id)
        assert entry.suggested_action is not None


# ──────────────────────────────────────────────────────────────────
# 3. Status mismatch
# ──────────────────────────────────────────────────────────────────


class TestStatusMismatch:
    @pytest.mark.asyncio
    async def test_legacy_says_connected_but_v2_says_failed(
        self, db_session, seeded_tenant, seeded_user, seeded_connector,
    ):
        # Legacy lies as CONNECTED; V2 truth is reachable=False -> failed -> ERROR.
        legacy = await _make_legacy(
            db_session, seeded_connector, seeded_user,
            status=ConnectorStatus.CONNECTED.value,
        )
        v2 = await _make_v2_for_legacy(
            db_session, seeded_connector, seeded_user,
        )
        svc = ConnectionReconciliationService(db_session)
        report = await svc.run(tenant_id=seeded_tenant.id, apply=False)
        assert report.counters.get("status_mismatch", 0) == 1
        entry = next(d for d in report.drift if d.kind == "status_mismatch")
        assert "CONNECTED" in entry.detail
        assert "ERROR" in entry.detail


# ──────────────────────────────────────────────────────────────────
# 4. Stale probe
# ──────────────────────────────────────────────────────────────────


class TestStaleProbe:
    @pytest.mark.asyncio
    async def test_callable_row_with_old_callable_at_is_stale(
        self, db_session, seeded_tenant, seeded_user, seeded_connector,
    ):
        long_ago = datetime.now(timezone.utc) - timedelta(days=2)
        legacy = await _make_legacy(
            db_session, seeded_connector, seeded_user,
            status=ConnectorStatus.CONNECTED.value,
        )
        await _make_v2_for_legacy(
            db_session, seeded_connector, seeded_user,
            reachable=True, authenticated=True, callable_=True,
            callable_at=long_ago,
        )
        svc = ConnectionReconciliationService(db_session)
        report = await svc.run(
            tenant_id=seeded_tenant.id, apply=False,
            stale_probe_threshold=timedelta(hours=24),
        )
        assert report.counters.get("stale_probe", 0) == 1
        entry = next(d for d in report.drift if d.kind == "stale_probe")
        assert "h old" in entry.detail


# ──────────────────────────────────────────────────────────────────
# 5. Legacy-only row (already covered by missing_v2_mirror)
# 6. V2-only row
# ──────────────────────────────────────────────────────────────────


class TestV2Only:
    @pytest.mark.asyncio
    async def test_v2_row_without_legacy_counterpart(
        self, db_session, seeded_tenant, seeded_user, seeded_connector,
    ):
        await _make_v2_for_legacy(
            db_session, seeded_connector, seeded_user,
        )
        svc = ConnectionReconciliationService(db_session)
        report = await svc.run(tenant_id=seeded_tenant.id, apply=False)
        assert report.counters.get("missing_legacy_row", 0) == 1
        entry = next(d for d in report.drift if d.kind == "missing_legacy_row")
        # severity is 'info' for V2-native rows -- expected behavior, not error.
        assert entry.severity == "info"


# ──────────────────────────────────────────────────────────────────
# 7. Feature flag off blocks apply mutations
# ──────────────────────────────────────────────────────────────────


class TestFeatureFlagBlocksApply:
    @pytest.mark.asyncio
    async def test_apply_with_flag_off_refused(
        self, db_session, seeded_tenant, seeded_user, seeded_connector, monkeypatch,
    ):
        monkeypatch.setattr(legacy_bridge, "is_v2_enabled", lambda: False)

        # Seed an expired op-lock that WOULD be cleaned under apply=True.
        v2 = await _make_v2_for_legacy(
            db_session, seeded_connector, seeded_user,
        )
        expired = ConnectionV2OpLock(
            id=uuid.uuid4(),
            connection_id=v2.id,
            op="probe",
            acquired_at=datetime.now(timezone.utc) - timedelta(hours=2),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            owner_token="t",
        )
        db_session.add(expired)
        await db_session.flush()

        svc = ConnectionReconciliationService(db_session)
        report = await svc.run(tenant_id=seeded_tenant.id, apply=True)

        # Apply was refused -> mutations_applied == 0.
        assert report.mutations_applied == 0
        # Refusal is itself a drift entry.
        kinds = {d.kind for d in report.drift}
        assert "apply_refused_flag_off" in kinds
        # Op-lock still present.
        still_there = (await db_session.execute(
            select(ConnectionV2OpLock).where(ConnectionV2OpLock.id == expired.id)
        )).scalar_one_or_none()
        assert still_there is not None

    @pytest.mark.asyncio
    async def test_apply_with_flag_on_cleans_orphan_lock(
        self, db_session, seeded_tenant, seeded_user, seeded_connector, monkeypatch,
    ):
        monkeypatch.setattr(legacy_bridge, "is_v2_enabled", lambda: True)
        v2 = await _make_v2_for_legacy(
            db_session, seeded_connector, seeded_user,
        )
        expired = ConnectionV2OpLock(
            id=uuid.uuid4(),
            connection_id=v2.id,
            op="probe",
            acquired_at=datetime.now(timezone.utc) - timedelta(hours=2),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            owner_token="t",
        )
        db_session.add(expired)
        await db_session.flush()

        svc = ConnectionReconciliationService(db_session)
        report = await svc.run(tenant_id=seeded_tenant.id, apply=True)
        assert report.mutations_applied == 1
        # Op-lock gone.
        still_there = (await db_session.execute(
            select(ConnectionV2OpLock).where(ConnectionV2OpLock.id == expired.id)
        )).scalar_one_or_none()
        assert still_there is None


# ──────────────────────────────────────────────────────────────────
# 8. Report does not print secrets
# ──────────────────────────────────────────────────────────────────


class TestNoSecretLeakage:
    @pytest.mark.asyncio
    async def test_drift_report_never_contains_plaintext_secret(
        self, db_session, seeded_tenant, seeded_user, seeded_connector,
    ):
        # Seed a legacy row with encrypted creds string-shaped to look like a
        # known marker -- if the reconciler ever prints credentials, the
        # marker will appear in the JSON dump.
        marker = "DAENA_LEAK_CANARY_SUPER_SECRET_12345"
        legacy = await _make_legacy(
            db_session, seeded_connector, seeded_user,
            credentials=marker,
        )
        await _make_v2_for_legacy(
            db_session, seeded_connector, seeded_user,
        )

        svc = ConnectionReconciliationService(db_session)
        report = await svc.run(tenant_id=seeded_tenant.id, apply=False)

        dumped = json.dumps(report.to_dict())
        assert marker not in dumped, (
            "Reconciliation report leaked credential plaintext into output"
        )

    @pytest.mark.asyncio
    async def test_secret_drift_is_informational_only(
        self, db_session, seeded_tenant, seeded_user, seeded_connector,
    ):
        # Legacy has creds + V2 row exists, but no Secret row in vault yet.
        await _make_legacy(
            db_session, seeded_connector, seeded_user,
            credentials="encrypted-blob-XXXX",
        )
        await _make_v2_for_legacy(
            db_session, seeded_connector, seeded_user,
        )
        svc = ConnectionReconciliationService(db_session)
        report = await svc.run(tenant_id=seeded_tenant.id, apply=False)
        assert report.counters.get("secret_drift", 0) >= 1
        entry = next(d for d in report.drift if d.kind == "secret_drift")
        assert entry.severity == "info"
        # Suggested action mentions vault migration, NOT credentials value.
        assert "vault" in (entry.suggested_action or "").lower()
        assert "encrypted-blob" not in (entry.detail + (entry.suggested_action or ""))


# ──────────────────────────────────────────────────────────────────
# Extra: multi-tenant scoping
# ──────────────────────────────────────────────────────────────────


class TestTenantScoping:
    @pytest.mark.asyncio
    async def test_run_with_tenant_id_filters_to_that_tenant(
        self, db_session, seeded_tenant, seeded_user, seeded_connector,
    ):
        # Seed a legacy row for our tenant.
        await _make_legacy(db_session, seeded_connector, seeded_user)

        # Seed a SECOND tenant + legacy row to confirm scoping.
        other_tenant = Tenant(
            id=uuid.uuid4(), name="Other", slug=f"other-{uuid.uuid4().hex[:8]}",
            settings={},
        )
        db_session.add(other_tenant)
        await db_session.flush()
        other_user = User(
            id=uuid.uuid4(),
            tenant_id=other_tenant.id,
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password_hash="x",
            role="FOUNDER",
            settings={},
        )
        db_session.add(other_user)
        await db_session.flush()
        other_conn = Connector(
            id=uuid.uuid4(),
            name=f"OtherConn-{uuid.uuid4().hex[:6]}",
            auth_type="API_KEY",
            config_schema={},
            tools=[],
            category="test",
        )
        db_session.add(other_conn)
        await db_session.flush()
        await _make_legacy(db_session, other_conn, other_user)

        svc = ConnectionReconciliationService(db_session)
        report = await svc.run(tenant_id=seeded_tenant.id, apply=False)
        assert report.legacy_row_count == 1  # only ours

        report_all = await svc.run(tenant_id=None, apply=False)
        assert report_all.legacy_row_count >= 2


# ──────────────────────────────────────────────────────────────────
# Report shape contract
# ──────────────────────────────────────────────────────────────────


class TestReportShape:
    @pytest.mark.asyncio
    async def test_report_to_dict_contains_required_fields(self, db_session):
        svc = ConnectionReconciliationService(db_session)
        report = await svc.run(apply=False)
        d = report.to_dict()
        assert "started_at" in d
        assert "finished_at" in d
        assert "duration_ms" in d
        assert "apply_mode" in d
        assert "legacy_row_count" in d
        assert "v2_row_count" in d
        assert "secret_row_count" in d
        assert "mutations_applied" in d
        assert "counters" in d
        assert "drift" in d
        assert "has_drift" in d
        # JSON serializable.
        json.dumps(d)
