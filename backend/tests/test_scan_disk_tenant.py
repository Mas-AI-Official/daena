"""PR-SCAN-DISK-TENANT contract tests.

Pinned behavior:

* ``ScanWorkflow._persist_report`` writes ``tenant_id`` into the JSON
  payload alongside the existing fields.
* ``ScanWorkflow.get_scan_owner_tenant_id`` returns the tenant id for
  in-memory scans, falls back to the disk payload for restart-recovered
  scans, and returns ``None`` for unknown scans OR legacy reports
  without ``tenant_id``.
* ``_load_report_from_disk`` continues to load legacy reports (no
  ``tenant_id`` key) so View / Download paths stay backwards
  compatible.
* The ``POST /security/scans/{scan_id}/findings/{finding_id}/create-remediation``
  endpoint:
    - Accepts a disk-recovered scan when the persisted ``tenant_id``
      matches the calling user.
    - Returns 404 when the persisted ``tenant_id`` belongs to a
      different tenant (no leak of scan-id existence across tenants).
    - Returns 404 when the disk report has no ``tenant_id`` key
      (fail-closed for pre-PR-SCAN-DISK-TENANT scans).
    - In-memory remediation path is unchanged (regression).

Tests use a fresh ``ScanWorkflow`` per case + ``tmp_path`` for
``SECURITY_REPORTS_DIR`` so the on-disk side effects are scoped to the
test. The endpoint tests pin the singleton ``_scan_workflow`` to a
freshly-built instance so cross-test pollution is impossible.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import Tenant, User
from app.models.organization import Department
from app.services.security.report_tiers import ReportTier
from app.services.security.scan_workflow import (
    ScanJob,
    ScanJobStatus,
    ScanReport,
    ScanWorkflow,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _make_workflow(reports_dir: Path, monkeypatch) -> ScanWorkflow:
    """Build a fresh ScanWorkflow whose disk path is rooted at tmp_path."""
    monkeypatch.setenv("SECURITY_REPORTS_DIR", str(reports_dir))
    return ScanWorkflow()


def _completed_job(
    *, tenant_id: str, target: str = "https://example.com/repo",
) -> ScanJob:
    """Build a minimal COMPLETE ScanJob for persistence tests."""
    return ScanJob(
        id=str(uuid.uuid4())[:12],
        target=target,
        tier=ReportTier.SCOUT,
        user_id="user-test",
        tenant_id=tenant_id,
        status=ScanJobStatus.COMPLETE,
        files_scanned=1,
        findings_count=1,
    )


def _basic_report(job: ScanJob) -> ScanReport:
    """Minimal ScanReport with one finding so persistence shape is realistic."""
    return ScanReport(
        job_id=job.id,
        tier=job.tier,
        findings=[
            {
                "id": "FIND-1",
                "title": "Demo finding",
                "severity": "LOW",
                "location": "demo.py:1",
                "remediation": "Apply the fix",
            },
        ],
        summary="demo",
        report_pdf_path="",
        cost_usd=0.0,
        duration_secs=0.0,
        pipeline_stages_used=["scan"],
        recommendations=[],
        severity_counts={"LOW": 1},
    )


def _write_legacy_report(reports_dir: Path, *, job_id: str) -> None:
    """Hand-write a JSON file shaped like a pre-PR-SCAN-DISK-TENANT report.

    No ``tenant_id`` key. Mirrors the exact field set the prior
    ``_persist_report`` would have produced.
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "job_id": job_id,
        "tier": "SCOUT",
        "target": "https://example.com/legacy",
        "findings": [
            {
                "id": "LEGACY-1",
                "title": "Legacy demo",
                "severity": "LOW",
                "location": "legacy.py:1",
                "remediation": "Apply the legacy fix",
            },
        ],
        "summary": "legacy",
        "report_pdf_path": "",
        "cost_usd": 0.0,
        "duration_secs": 0.0,
        "pipeline_stages_used": ["scan"],
        "recommendations": [],
        "severity_counts": {"LOW": 1},
        "files_scanned": 1,
        "tools_used": [],
        "tools_missing": [],
        "target_kind": "repo",
        "scanner_notes": "",
        "created_at": time.time() - 60,
        "completed_at": time.time(),
    }
    (reports_dir / f"{job_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Persistence shape tests ───────────────────────────────────────────


def test_persist_report_writes_tenant_id(
    tmp_path: Path, monkeypatch,
) -> None:
    """``_persist_report`` must include ``tenant_id`` in the payload."""
    workflow = _make_workflow(tmp_path, monkeypatch)
    tenant_id = str(uuid.uuid4())
    job = _completed_job(tenant_id=tenant_id)
    report = _basic_report(job)

    workflow._persist_report(job, report)  # noqa: SLF001

    raw = json.loads(
        (tmp_path / f"{job.id}.json").read_text(encoding="utf-8"),
    )
    assert raw["tenant_id"] == tenant_id
    # All prior fields still present (regression).
    assert raw["job_id"] == job.id
    assert raw["tier"] == "SCOUT"
    assert raw["findings"][0]["title"] == "Demo finding"


def test_persist_report_writes_none_when_job_lacks_tenant_id(
    tmp_path: Path, monkeypatch,
) -> None:
    """Defensive: an unscoped job (empty tenant_id) yields tenant_id=None."""
    workflow = _make_workflow(tmp_path, monkeypatch)
    job = _completed_job(tenant_id="")
    report = _basic_report(job)

    workflow._persist_report(job, report)  # noqa: SLF001

    raw = json.loads(
        (tmp_path / f"{job.id}.json").read_text(encoding="utf-8"),
    )
    assert raw["tenant_id"] is None


# ── Read-path / loader tests ──────────────────────────────────────────


def test_load_report_payload_returns_full_dict(
    tmp_path: Path, monkeypatch,
) -> None:
    """The new ``_load_report_payload_from_disk`` returns the raw JSON."""
    workflow = _make_workflow(tmp_path, monkeypatch)
    tenant_id = str(uuid.uuid4())
    job = _completed_job(tenant_id=tenant_id)
    workflow._persist_report(job, _basic_report(job))  # noqa: SLF001

    payload = workflow._load_report_payload_from_disk(job.id)  # noqa: SLF001

    assert payload is not None
    assert payload["tenant_id"] == tenant_id
    assert payload["job_id"] == job.id


def test_load_report_payload_returns_none_for_missing(
    tmp_path: Path, monkeypatch,
) -> None:
    """Missing file -> None (the existing contract is preserved)."""
    workflow = _make_workflow(tmp_path, monkeypatch)
    payload = workflow._load_report_payload_from_disk("does-not-exist")  # noqa: SLF001
    assert payload is None


def test_load_report_from_disk_handles_legacy_report_without_tenant_id(
    tmp_path: Path, monkeypatch,
) -> None:
    """A pre-PR-SCAN-DISK-TENANT report still loads as a ScanReport.

    Backwards compatibility: View / Download paths must keep working
    on legacy reports. Only the remediation endpoint fails closed.
    """
    workflow = _make_workflow(tmp_path, monkeypatch)
    job_id = "legacy-1234"
    _write_legacy_report(tmp_path, job_id=job_id)

    report = workflow._load_report_from_disk(job_id)  # noqa: SLF001

    assert report is not None
    assert report.job_id == job_id
    assert report.tier == ReportTier.SCOUT
    assert report.findings[0]["title"] == "Legacy demo"


# ── get_scan_owner_tenant_id contract ─────────────────────────────────


@pytest.mark.asyncio
async def test_owner_lookup_uses_in_memory_jobs_first(
    tmp_path: Path, monkeypatch,
) -> None:
    """In-memory job wins over disk -- recent state is the source of truth."""
    workflow = _make_workflow(tmp_path, monkeypatch)
    tenant_id = str(uuid.uuid4())
    job = _completed_job(tenant_id=tenant_id)
    workflow._jobs[job.id] = job  # noqa: SLF001

    owner = workflow.get_scan_owner_tenant_id(job.id)
    assert owner == tenant_id


def test_owner_lookup_falls_back_to_disk_payload(
    tmp_path: Path, monkeypatch,
) -> None:
    """A scan that exists only on disk still resolves its owner tenant.

    This is the exact scenario PR-SCAN-DISK-TENANT exists to fix:
    a process restart wiped ``_jobs`` but the report survives on disk;
    the operator should still be able to remediate against it.
    """
    workflow = _make_workflow(tmp_path, monkeypatch)
    tenant_id = str(uuid.uuid4())
    job = _completed_job(tenant_id=tenant_id)
    workflow._persist_report(job, _basic_report(job))  # noqa: SLF001
    # Simulate the restart: the new ScanWorkflow has no _jobs entry.
    fresh = _make_workflow(tmp_path, monkeypatch)
    assert job.id not in fresh._jobs  # noqa: SLF001

    owner = fresh.get_scan_owner_tenant_id(job.id)
    assert owner == tenant_id


def test_owner_lookup_returns_none_for_legacy_report(
    tmp_path: Path, monkeypatch,
) -> None:
    """A pre-PR-SCAN-DISK-TENANT report has no tenant_id -> None.

    The endpoint converts None into a 404 so the operator cannot
    create remediation work from a scan whose ownership cannot be
    proved. Documented as fail-closed posture.
    """
    workflow = _make_workflow(tmp_path, monkeypatch)
    job_id = "legacy-no-tenant"
    _write_legacy_report(tmp_path, job_id=job_id)

    owner = workflow.get_scan_owner_tenant_id(job_id)
    assert owner is None


def test_owner_lookup_returns_none_for_unknown_scan(
    tmp_path: Path, monkeypatch,
) -> None:
    """Unknown scan id -> None (no in-memory entry, no disk file)."""
    workflow = _make_workflow(tmp_path, monkeypatch)
    owner = workflow.get_scan_owner_tenant_id("totally-unknown")
    assert owner is None


def test_owner_lookup_treats_blank_disk_tenant_as_missing(
    tmp_path: Path, monkeypatch,
) -> None:
    """Defensive: a report whose ``tenant_id`` is the empty string
    is treated the same as missing -- fail closed."""
    workflow = _make_workflow(tmp_path, monkeypatch)
    job_id = "blank-tenant"
    payload = {
        "job_id": job_id,
        "tenant_id": "",
        "tier": "SCOUT",
        "findings": [],
    }
    (tmp_path / f"{job_id}.json").write_text(
        json.dumps(payload), encoding="utf-8",
    )

    owner = workflow.get_scan_owner_tenant_id(job_id)
    assert owner is None


# ── Endpoint integration: disk-fallback tenant gate ───────────────────


async def _seed_tenant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    slug: str,
) -> None:
    """Seed tenant + founder user + active department.

    The endpoint resolves the user's department implicitly through the
    create_remediation service path; without an active dept, that path
    raises NoActiveDepartmentError. Tests need a real seeded dept.
    """
    db.add(Tenant(id=tenant_id, name=f"disk-{slug}", slug=f"disk-{slug}"))
    await db.flush()
    db.add(
        User(
            id=user_id, tenant_id=tenant_id,
            email=f"disk-{slug}@example.com",
            password_hash="x", role="FOUNDER",
        ),
    )
    await db.flush()
    db.add(
        Department(
            id=uuid.uuid4(), tenant_id=tenant_id,
            name=f"Engineering ({slug})",
            description="disk-test", sunflower_index=0,
            cell_id=f"hex_0_{slug}", config={}, is_active=True,
        ),
    )
    await db.flush()
    await db.commit()


def _install_singleton_workflow(
    reports_dir: Path, monkeypatch,
) -> ScanWorkflow:
    """Replace the lazy singleton in security_dashboard with a fresh
    workflow rooted at the given reports_dir.

    Without this, tests would share state with each other AND with any
    real workflow accumulated by other test modules earlier in the run.
    """
    monkeypatch.setenv("SECURITY_REPORTS_DIR", str(reports_dir))
    from app.api.v1 import security_dashboard
    workflow = ScanWorkflow()
    monkeypatch.setattr(security_dashboard, "_scan_workflow", workflow)
    return workflow


def _build_auth_headers(*, user_id: uuid.UUID, tenant_id: uuid.UUID) -> dict:
    """JWT for arbitrary tenant + user combos.

    The conftest ``auth_headers`` fixture is fixed to one tenant id;
    these tests need to swap tenants per case so they mint their own.
    """
    from app.core.security import create_access_token
    token = create_access_token(
        user_id=str(user_id), tenant_id=str(tenant_id), role="FOUNDER",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_endpoint_disk_recovered_scan_with_matching_tenant_succeeds(
    tmp_path: Path, monkeypatch, db_session: AsyncSession, client: AsyncClient,
) -> None:
    """Restart-recovered scan: matching tenant can create remediation."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await _seed_tenant(
        db_session, tenant_id=tenant_id, user_id=user_id, slug="ok",
    )

    workflow = _install_singleton_workflow(tmp_path, monkeypatch)
    # Persist a scan owned by this tenant, then drop _jobs to simulate restart.
    job = _completed_job(tenant_id=str(tenant_id))
    workflow._persist_report(job, _basic_report(job))  # noqa: SLF001
    workflow._jobs.pop(job.id, None)  # noqa: SLF001 -- ensure disk-only

    headers = _build_auth_headers(user_id=user_id, tenant_id=tenant_id)
    resp = await client.post(
        f"/api/v1/security/scans/{job.id}/findings/FIND-1/create-remediation",
        json={},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["scan_id"] == job.id
    assert body["data"]["finding_id"] == "FIND-1"
    assert body["data"]["task_id"]
    assert body["data"]["workstream_id"]


@pytest.mark.asyncio
async def test_endpoint_disk_recovered_scan_with_wrong_tenant_returns_404(
    tmp_path: Path, monkeypatch, db_session: AsyncSession, client: AsyncClient,
) -> None:
    """Cross-tenant access returns 404 (no leak of scan-id existence)."""
    owning_tenant = uuid.uuid4()
    intruder_tenant = uuid.uuid4()
    intruder_user = uuid.uuid4()
    await _seed_tenant(
        db_session, tenant_id=intruder_tenant, user_id=intruder_user,
        slug="intruder",
    )

    workflow = _install_singleton_workflow(tmp_path, monkeypatch)
    # The scan belongs to owning_tenant but is being addressed by
    # intruder_tenant's user.
    job = _completed_job(tenant_id=str(owning_tenant))
    workflow._persist_report(job, _basic_report(job))  # noqa: SLF001
    workflow._jobs.pop(job.id, None)  # noqa: SLF001

    headers = _build_auth_headers(
        user_id=intruder_user, tenant_id=intruder_tenant,
    )
    resp = await client.post(
        f"/api/v1/security/scans/{job.id}/findings/FIND-1/create-remediation",
        json={},
        headers=headers,
    )

    assert resp.status_code == 404
    # Detail mirrors the in-memory not-found wording so existence is
    # not distinguishable across tenants.
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_endpoint_disk_legacy_report_without_tenant_id_returns_404(
    tmp_path: Path, monkeypatch, db_session: AsyncSession, client: AsyncClient,
) -> None:
    """Pre-PR-SCAN-DISK-TENANT report on disk: fail closed with 404.

    Operator cannot create remediation work from a scan whose ownership
    cannot be proved. They must re-run the scan to upgrade the on-disk
    record to the new shape.
    """
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await _seed_tenant(
        db_session, tenant_id=tenant_id, user_id=user_id, slug="legacy",
    )

    _install_singleton_workflow(tmp_path, monkeypatch)
    job_id = "legacy-recovered"
    _write_legacy_report(tmp_path, job_id=job_id)

    headers = _build_auth_headers(user_id=user_id, tenant_id=tenant_id)
    resp = await client.post(
        f"/api/v1/security/scans/{job_id}/findings/LEGACY-1/create-remediation",
        json={},
        headers=headers,
    )

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_endpoint_in_memory_remediation_path_still_works(
    tmp_path: Path, monkeypatch, db_session: AsyncSession, client: AsyncClient,
) -> None:
    """Regression: an in-memory scan owned by the caller still remediates.

    PR-SCAN-DISK-TENANT changed the tenant check from
    ``_jobs[scan_id].tenant_id`` to ``get_scan_owner_tenant_id``; the
    in-memory branch must continue to work the same.
    """
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await _seed_tenant(
        db_session, tenant_id=tenant_id, user_id=user_id, slug="inmem",
    )

    workflow = _install_singleton_workflow(tmp_path, monkeypatch)
    job = _completed_job(tenant_id=str(tenant_id))
    workflow._jobs[job.id] = job  # noqa: SLF001
    workflow._reports[job.id] = _basic_report(job)  # noqa: SLF001

    headers = _build_auth_headers(user_id=user_id, tenant_id=tenant_id)
    resp = await client.post(
        f"/api/v1/security/scans/{job.id}/findings/FIND-1/create-remediation",
        json={},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["scan_id"] == job.id
    assert body["data"]["task_id"]
    assert body["data"]["workstream_id"]
