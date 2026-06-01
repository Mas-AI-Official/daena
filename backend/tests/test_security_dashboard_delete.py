"""Tests for the DELETE /security/scans endpoints + tool install endpoints.

Covers the user-facing additions from the 2026-04-21 report-manager ticket:
    * DELETE /security/scans/{id} archives to .archive/ by default
    * DELETE /security/scans/{id}?hard=true actually unlinks
    * DELETE /security/scans bulk-archives everything
    * POST /security/tools/install-all?dry_run=true returns planned tools
      without executing
"""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import security_dashboard as dash_module


@pytest.fixture
def client_with_tmp_dirs(tmp_path, monkeypatch):
    """Create a FastAPI TestClient with DAENA_VAR + SECURITY_REPORTS_DIR
    pointed at a temp dir so deletes don't clobber real data.

    Overrides ``get_current_user`` to return a fake FOUNDER so the K-2
    auth gate (2026-06-01) doesn't reject these focused delete-behavior
    tests. Auth itself is covered by tests/test_scan_events_auth.py.
    """
    import uuid as _uuid
    from fastapi import FastAPI
    from app.api.deps import CurrentUser, get_current_user

    monkeypatch.setenv("DAENA_VAR", str(tmp_path / "var"))
    monkeypatch.setenv(
        "SECURITY_REPORTS_DIR", str(tmp_path / "var" / "security_reports"),
    )

    def _fake_current_user() -> CurrentUser:
        return CurrentUser(
            id=_uuid.UUID("22222222-2222-2222-2222-222222222222"),
            tenant_id=_uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="test@daena.local",
            role="FOUNDER",
            display_name="Test",
        )

    app = FastAPI()
    app.dependency_overrides[get_current_user] = _fake_current_user
    app.include_router(dash_module.router, prefix="/security")
    yield TestClient(app), tmp_path


_FAKE_TENANT_ID = "11111111-1111-1111-1111-111111111111"


def _write_fake_scan(
    tmp_path,
    scan_id: str,
    with_trace=True,
    with_report=True,
    tenant_id: str = _FAKE_TENANT_ID,
):
    """Write a synthetic scan trace + report to disk.

    K-3 ownership (2026-06-01): the report payload now includes a
    ``tenant_id`` so ``ScanWorkflow.get_scan_owner_tenant_id`` returns
    a real owner and the ownership check passes. Pass a different
    tenant_id to simulate cross-tenant access.
    """
    var = tmp_path / "var"
    if with_trace:
        trace_dir = var / "scan_traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        (trace_dir / f"{scan_id}.json").write_text(json.dumps({
            "scan_id": scan_id, "target": "example.com", "total_findings": 3,
            "tenant_id": tenant_id,
        }), encoding="utf-8")
    if with_report:
        reports_dir = var / "security_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / f"{scan_id}.json").write_text(json.dumps({
            "job_id": scan_id, "tier": "SCOUT", "target": "example.com",
            "findings": [], "summary": "",
            "tenant_id": tenant_id,
        }), encoding="utf-8")


def test_delete_scan_archives_by_default(client_with_tmp_dirs):
    client, tmp_path = client_with_tmp_dirs
    _write_fake_scan(tmp_path, "scan-1")
    resp = client.delete("/security/scans/scan-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["archived"] is True
    assert data["deleted"] is False
    # Artifacts moved to .archive
    assert (tmp_path / "var" / "security_reports" / ".archive").exists()
    # Originals gone
    assert not (tmp_path / "var" / "scan_traces" / "scan-1.json").exists()
    assert not (tmp_path / "var" / "security_reports" / "scan-1.json").exists()


def test_delete_scan_hard_unlinks(client_with_tmp_dirs):
    client, tmp_path = client_with_tmp_dirs
    _write_fake_scan(tmp_path, "scan-hard")
    resp = client.delete("/security/scans/scan-hard?hard=true")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    assert not (tmp_path / "var" / "scan_traces" / "scan-hard.json").exists()
    # No archive should have been created for the hard-deleted scan
    archive = tmp_path / "var" / "security_reports" / ".archive"
    if archive.exists():
        leftover = list(archive.glob("scan-hard.*"))
        assert leftover == []


def test_delete_scan_missing_returns_404(client_with_tmp_dirs):
    client, _ = client_with_tmp_dirs
    resp = client.delete("/security/scans/does-not-exist")
    assert resp.status_code == 404


def test_delete_all_scans_archives_everything(client_with_tmp_dirs):
    client, tmp_path = client_with_tmp_dirs
    for i in range(3):
        _write_fake_scan(tmp_path, f"bulk-{i}")
    resp = client.delete("/security/scans")
    assert resp.status_code == 200
    body = resp.json()
    assert body["processed"] == 3
    assert body["hard"] is False
    # All report files moved
    remaining = [
        p for p in (tmp_path / "var" / "security_reports").glob("*.json")
        if p.name != ".archive"
    ]
    assert remaining == [], f"still on disk: {remaining}"


def test_install_all_dry_run_lists_plan(client_with_tmp_dirs, monkeypatch):
    client, _ = client_with_tmp_dirs

    # Stub ToolCatalog so the test doesn't depend on which tools are
    # actually installed on the dev box.
    from app.services.security import tool_catalog as tc_module

    class _FakeTool:
        def __init__(self, name, cat, cmd):
            self.name = name
            self.category = cat
            self.install_cmd = cmd
            self.offensive_only = False

    class _FakeCatalog:
        def get_missing(self):
            return [
                _FakeTool("alpha", "recon", "choco install alpha -y"),
                _FakeTool("beta", "scanning", "pip install beta"),
            ]

        def get(self, name):
            return None

        def is_installed(self, name):
            return False

    monkeypatch.setattr(tc_module, "ToolCatalog", _FakeCatalog)
    resp = client.post("/security/tools/install-all?dry_run=true")
    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True
    assert body["planned"] == 2
    names = sorted(t["name"] for t in body["tools"])
    assert names == ["alpha", "beta"]


# ---------------------------------------------------------------------------
# K-3 (2026-06-01): cross-tenant ownership tests for the scan surface
# ---------------------------------------------------------------------------


_OTHER_TENANT_ID = "99999999-9999-9999-9999-999999999999"


def test_delete_scan_cross_tenant_returns_404(client_with_tmp_dirs):
    """A scan owned by a DIFFERENT tenant returns 404 to the caller -
    cannot probe id-existence cross-tenant, cannot delete cross-tenant.
    """
    client, tmp_path = client_with_tmp_dirs
    _write_fake_scan(tmp_path, "other-tenant-scan", tenant_id=_OTHER_TENANT_ID)
    resp = client.delete("/security/scans/other-tenant-scan")
    assert resp.status_code == 404


def test_delete_all_scans_only_archives_callers_tenant(client_with_tmp_dirs):
    """Bulk DELETE /security/scans must NOT wipe other tenants' scans.

    Writes 2 owned scans + 2 cross-tenant scans + 1 legacy (no tenant_id).
    Expects processed=2, skipped_cross_tenant=2, skipped_legacy_no_tenant=1.
    """
    client, tmp_path = client_with_tmp_dirs
    _write_fake_scan(tmp_path, "mine-1")
    _write_fake_scan(tmp_path, "mine-2")
    _write_fake_scan(tmp_path, "other-1", tenant_id=_OTHER_TENANT_ID)
    _write_fake_scan(tmp_path, "other-2", tenant_id=_OTHER_TENANT_ID)
    # Legacy scan (pre-PR-SCAN-DISK-TENANT): write the report payload by hand
    # with NO tenant_id field.
    var = tmp_path / "var"
    reports_dir = var / "security_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "legacy-1.json").write_text(json.dumps({
        "job_id": "legacy-1", "tier": "SCOUT", "target": "example.com",
        "findings": [], "summary": "",
    }), encoding="utf-8")

    resp = client.delete("/security/scans")
    assert resp.status_code == 200
    body = resp.json()
    assert body["processed"] == 2
    assert body["skipped_cross_tenant"] == 2
    assert body["skipped_legacy_no_tenant"] == 1
