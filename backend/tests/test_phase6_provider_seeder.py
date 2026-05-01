"""Phase 6 tests: provider V2 row seeder.

Founder-mandated coverage:
  1. Provider rows are created for configured providers
  2. Provider rows are NOT created for unconfigured providers
  3. Re-running is idempotent (no duplicates, no row mutation)
  4. Local providers (Ollama / vLLM) seed when base_url is set
  5. Tenant-scoped + multi-tenant variants
  6. Seeder report has the expected shape
  7. Plain API keys are never written into V2 row config
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.connection_v2 import (
    AuthMethod as V2AuthMethod,
    ConnectionKind,
    ConnectionV2,
)
from app.models.identity import Tenant
from app.services.connection_v2.provider_seeder import (
    PROVIDER_CATALOG,
    seed_providers_all_tenants,
    seed_providers_for_tenant,
)


@pytest.fixture
async def seeded_tenant(db_session):
    tid = uuid.uuid4()
    tenant = Tenant(
        id=tid, name="P6Prov", slug=f"p6prov-{uuid.uuid4().hex[:8]}", settings={},
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


def _zero_all_keys(monkeypatch):
    """Force every provider key in settings to empty for a clean baseline."""
    from app.core.config import get_settings
    s = get_settings()
    for spec in PROVIDER_CATALOG:
        monkeypatch.setattr(s, spec.settings_attr, "", raising=False)


# ──────────────────────────────────────────────────────────────────


class TestSeederBaseline:
    @pytest.mark.asyncio
    async def test_no_keys_configured_creates_nothing(
        self, db_session, seeded_tenant, monkeypatch,
    ):
        _zero_all_keys(monkeypatch)
        report = await seed_providers_for_tenant(
            db_session, tenant_id=seeded_tenant.id,
        )
        assert report.created == []
        assert report.skipped_existing == []
        assert len(report.skipped_unconfigured) == len(PROVIDER_CATALOG)
        rows = (await db_session.execute(
            select(ConnectionV2).where(
                ConnectionV2.tenant_id == seeded_tenant.id,
                ConnectionV2.kind == ConnectionKind.PROVIDER.value,
            )
        )).scalars().all()
        assert len(rows) == 0


class TestSeederWithConfiguredProviders:
    @pytest.mark.asyncio
    async def test_configured_providers_get_v2_rows(
        self, db_session, seeded_tenant, monkeypatch,
    ):
        _zero_all_keys(monkeypatch)
        # Configure two paid + one local.
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "openai_api_key", "sk-canary-OPENAI", raising=False)
        monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-canary", raising=False)
        monkeypatch.setattr(s, "ollama_base_url", "http://localhost:11434", raising=False)

        report = await seed_providers_for_tenant(
            db_session, tenant_id=seeded_tenant.id,
        )
        assert sorted(report.created) == sorted(["openai", "anthropic", "ollama"])
        assert report.skipped_existing == []

        rows = (await db_session.execute(
            select(ConnectionV2).where(
                ConnectionV2.tenant_id == seeded_tenant.id,
                ConnectionV2.kind == ConnectionKind.PROVIDER.value,
            )
        )).scalars().all()
        assert len(rows) == 3
        slugs = {r.slug for r in rows}
        assert slugs == {"openai", "anthropic", "ollama"}

        # Local provider has auth_method=NONE; paid have API_TOKEN.
        ollama = next(r for r in rows if r.slug == "ollama")
        assert ollama.auth_method == V2AuthMethod.NONE.value
        assert ollama.config.get("_local") is True

        openai = next(r for r in rows if r.slug == "openai")
        assert openai.auth_method == V2AuthMethod.API_TOKEN.value

    @pytest.mark.asyncio
    async def test_seeder_never_writes_plain_api_key_into_config(
        self, db_session, seeded_tenant, monkeypatch,
    ):
        """Canary: the seeder must not put the API key into ConnectionV2.config."""
        _zero_all_keys(monkeypatch)
        from app.core.config import get_settings
        s = get_settings()
        canary = "sk-DAENA-LEAK-CANARY-DO-NOT-PERSIST"
        monkeypatch.setattr(s, "openai_api_key", canary, raising=False)

        await seed_providers_for_tenant(db_session, tenant_id=seeded_tenant.id)

        rows = (await db_session.execute(
            select(ConnectionV2).where(
                ConnectionV2.tenant_id == seeded_tenant.id,
                ConnectionV2.kind == ConnectionKind.PROVIDER.value,
                ConnectionV2.slug == "openai",
            )
        )).scalars().all()
        assert len(rows) == 1
        dumped = json.dumps(rows[0].config)
        assert canary not in dumped, (
            "Provider seeder leaked API key into ConnectionV2.config"
        )


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_rerun_yields_zero_new_rows(
        self, db_session, seeded_tenant, monkeypatch,
    ):
        _zero_all_keys(monkeypatch)
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "openai_api_key", "sk-test", raising=False)

        first = await seed_providers_for_tenant(
            db_session, tenant_id=seeded_tenant.id,
        )
        assert "openai" in first.created

        second = await seed_providers_for_tenant(
            db_session, tenant_id=seeded_tenant.id,
        )
        assert second.created == []
        assert "openai" in second.skipped_existing

        # Confirm exactly one row.
        rows = (await db_session.execute(
            select(ConnectionV2).where(
                ConnectionV2.tenant_id == seeded_tenant.id,
                ConnectionV2.slug == "openai",
            )
        )).scalars().all()
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_rerun_does_not_reset_callable_at(
        self, db_session, seeded_tenant, monkeypatch,
    ):
        """If a probe flipped callable=True, re-seeding must not undo it."""
        _zero_all_keys(monkeypatch)
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "openai_api_key", "sk-test", raising=False)

        await seed_providers_for_tenant(db_session, tenant_id=seeded_tenant.id)

        # Mock a successful probe by setting callable=True directly.
        row = (await db_session.execute(
            select(ConnectionV2).where(
                ConnectionV2.tenant_id == seeded_tenant.id,
                ConnectionV2.slug == "openai",
            )
        )).scalar_one()
        marker = datetime(2026, 1, 1, tzinfo=timezone.utc)
        row.callable = True
        row.callable_at = marker
        await db_session.flush()

        # Re-seed.
        await seed_providers_for_tenant(db_session, tenant_id=seeded_tenant.id)

        # callable_at unchanged.
        row2 = (await db_session.execute(
            select(ConnectionV2).where(ConnectionV2.id == row.id)
        )).scalar_one()
        assert row2.callable is True
        # SQLite drops tz, but the timestamp should be preserved.
        assert row2.callable_at.replace(tzinfo=None) == marker.replace(tzinfo=None)


class TestMultiTenant:
    @pytest.mark.asyncio
    async def test_seed_all_tenants(self, db_session, monkeypatch):
        _zero_all_keys(monkeypatch)
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "anthropic_api_key", "sk-ant-test", raising=False)

        # Two tenants.
        tenants = [
            Tenant(id=uuid.uuid4(), name=f"T{i}", slug=f"t{i}-{uuid.uuid4().hex[:6]}", settings={})
            for i in range(2)
        ]
        for t in tenants:
            db_session.add(t)
        await db_session.flush()

        reports = await seed_providers_all_tenants(db_session)
        # At least 2 (we just added) -- could be more if other tests ran
        # earlier in the session-scoped engine.
        our_reports = [r for r in reports if r.tenant_id in {str(t.id) for t in tenants}]
        assert len(our_reports) == 2
        for r in our_reports:
            assert "anthropic" in r.created


class TestSeedReportShape:
    @pytest.mark.asyncio
    async def test_report_to_dict_is_json_serializable(
        self, db_session, seeded_tenant, monkeypatch,
    ):
        _zero_all_keys(monkeypatch)
        report = await seed_providers_for_tenant(
            db_session, tenant_id=seeded_tenant.id,
        )
        d = report.to_dict()
        json.dumps(d)
        assert "tenant_id" in d
        assert "created" in d
        assert "skipped_existing" in d
        assert "skipped_unconfigured" in d
