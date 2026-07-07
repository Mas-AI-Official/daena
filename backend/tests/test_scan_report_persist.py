"""PR-9 Klyntar Hardening: durable scan-report persistence (Rule 17).

Mirrors test_error_sink: a test-engine-bound session factory is patched in so
the fail-safe DB writer exercises a real SQLite schema (FK pragma ON, so a real
tenant must be seeded), and the broken-DB path is proven never to raise into the
scan completion flow.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.identity import Tenant
from app.models.scan_report import ScanReportRecord
from app.services.security.report_tiers import ReportTier
from app.services.security.scan_workflow import (
    ScanJob,
    ScanJobStatus,
    ScanReport,
    ScanWorkflow,
)

pytestmark = pytest.mark.asyncio

_FINDINGS = [{"id": "F1", "severity": "high", "title": "Test finding"}]


async def _seed_tenant(factory, tenant_id: uuid.UUID) -> None:
    async with factory() as session:
        session.add(
            Tenant(id=tenant_id, name="Acme", slug=f"acme-{tenant_id.hex[:8]}"),
        )
        await session.commit()


def _job(tenant_id: str, *, job_id: str = "job-abc-123") -> ScanJob:
    return ScanJob(
        id=job_id,
        target="https://example.test",
        tier=ReportTier.SCOUT,
        user_id="user-1",
        tenant_id=tenant_id,
        status=ScanJobStatus.COMPLETE,
    )


def _report(*, job_id: str = "job-abc-123", summary: str = "1 finding") -> ScanReport:
    return ScanReport(
        job_id=job_id,
        tier=ReportTier.SCOUT,
        findings=list(_FINDINGS),
        summary=summary,
        report_pdf_path="var/security_reports/job-abc-123.pdf",
        cost_usd=0.42,
        duration_secs=12.5,
        pipeline_stages_used=["recon"],
        recommendations=["patch it"],
        severity_counts={"high": 1},
    )


async def test_persist_report_db_inserts_row(test_engine) -> None:
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False,
    )
    tenant_id = uuid.uuid4()
    await _seed_tenant(factory, tenant_id)

    wf = ScanWorkflow()
    with patch("app.core.database.async_session_factory", factory):
        await wf._persist_report_db(_job(str(tenant_id)), _report())

    async with factory() as s:
        rows = (
            await s.execute(
                select(ScanReportRecord).where(
                    ScanReportRecord.tenant_id == tenant_id,
                    ScanReportRecord.job_id == "job-abc-123",
                )
            )
        ).scalars().all()

    assert len(rows) == 1
    row = rows[0]
    assert row.status == "complete"
    assert row.summary == "1 finding"
    assert row.target == "https://example.test"
    assert row.findings == _FINDINGS
    assert row.severity_counts == {"high": 1}
    assert row.cost_usd == pytest.approx(0.42)
    assert row.duration_secs == pytest.approx(12.5)


async def test_persist_report_db_is_idempotent(test_engine) -> None:
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False,
    )
    tenant_id = uuid.uuid4()
    await _seed_tenant(factory, tenant_id)

    wf = ScanWorkflow()
    job = _job(str(tenant_id))
    with patch("app.core.database.async_session_factory", factory):
        await wf._persist_report_db(job, _report())
        await wf._persist_report_db(job, _report(summary="updated summary"))

    async with factory() as s:
        rows = (
            await s.execute(
                select(ScanReportRecord).where(
                    ScanReportRecord.tenant_id == tenant_id,
                    ScanReportRecord.job_id == "job-abc-123",
                )
            )
        ).scalars().all()

    assert len(rows) == 1
    assert rows[0].summary == "updated summary"


async def test_get_persisted_report_record_is_tenant_scoped(test_engine) -> None:
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False,
    )
    tenant_id = uuid.uuid4()
    other_tenant = uuid.uuid4()
    await _seed_tenant(factory, tenant_id)

    wf = ScanWorkflow()
    with patch("app.core.database.async_session_factory", factory):
        await wf._persist_report_db(_job(str(tenant_id)), _report())
        found = await wf.get_persisted_report_record("job-abc-123", str(tenant_id))
        miss = await wf.get_persisted_report_record("job-abc-123", str(other_tenant))

    assert found is not None
    assert found.job_id == "job-abc-123"
    assert miss is None


async def test_persist_report_db_skips_when_no_tenant(test_engine) -> None:
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False,
    )
    wf = ScanWorkflow()
    # Empty tenant_id cannot satisfy the NOT NULL FK -> must skip, not error.
    job = _job("", job_id="job-skip-no-tenant")
    with patch("app.core.database.async_session_factory", factory):
        await wf._persist_report_db(job, _report(job_id="job-skip-no-tenant"))

    async with factory() as s:
        rows = (
            await s.execute(
                select(ScanReportRecord).where(
                    ScanReportRecord.job_id == "job-skip-no-tenant",
                )
            )
        ).scalars().all()
    assert rows == []


async def test_persist_report_db_never_raises_when_db_broken() -> None:
    def _boom():
        raise RuntimeError("db down")

    wf = ScanWorkflow()
    job = _job(str(uuid.uuid4()))
    with patch("app.core.database.async_session_factory", _boom):
        result = await wf._persist_report_db(job, _report())
    assert result is None
