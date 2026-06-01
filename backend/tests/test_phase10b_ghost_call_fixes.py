"""Phase 10b — pin the four real OpenAPI ghost-call fixes.

Phase 9D's live-spec diff surfaced four UI calls that hit the running
backend with a 404/405 response:

* G1 ``DELETE /api/v1/company-mode/seed-brief`` (route did not exist)
* G2 ``GET /api/v1/projects/{id}/files``      (route did not exist)
* G3 ``GET /api/v1/projects/{id}/tasks``      (route did not exist)
* G4 ``GET /api/v1/runtimes/subscriptions``    (route did not exist)

This test pins the new shape:

* G1 the route now archives the seed file (rename to ``*.archived-<ts>.md``)
  and returns ``exists: false``. A second DELETE on the absent file
  succeeds idempotently.
* G2/G3 the routes return an honest empty list with a
  ``meta.tracking_enabled: false`` flag because the schema does not
  link tasks/files to projects yet.
* G4 the route returns the per-runtime subscription cache flat-listed
  for the Settings ▸ LLM panel.

(G5 is a one-line frontend trailing-slash fix; covered by ``tsc``.)
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> dict[str, Any]:
    """Create a real tenant + user row so FK constraints are satisfied.

    The shared ``auth_headers`` fixture mints a JWT for hard-coded UUIDs
    that do not exist in the test DB, which trips the
    ``projects.tenant_id → tenants.id`` FK on insert. Following the
    pattern in ``test_engagement_approval_persistence.py``: register +
    login → real tenant + user → real headers.
    """
    unique = uuid.uuid4().hex[:8]
    email = f"phase10b-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Phase 10b Tester",
            "tenant_name": f"Phase10bOrg-{unique}",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login_resp.json()["data"]
    return {
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "tenant_id": uuid.UUID(data["user"]["tenant_id"]),
    }


# ---------------------------------------------------------------------------
# G1 — DELETE /api/v1/company-mode/seed-brief
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_g1_delete_seed_brief_archives_file_when_present(
    client: AsyncClient,
    auth_headers: dict[str, str],
    tmp_path: Path,
) -> None:
    """A real seed file gets renamed to ``*.archived-<UTC-stamp>.md``.

    The route is best-effort about clearing the runtime CompanyContext
    store; we only assert the on-disk file moved + the response shape.
    """
    seed_file = tmp_path / "company_seed.md"
    seed_file.write_text("---\nfoo: bar\n---\n# Seed brief\n", encoding="utf-8")

    with patch(
        "app.api.v1.company_mode._seed_path",
        return_value=seed_file,
    ):
        resp = await client.delete(
            "/api/v1/company-mode/seed-brief",
            headers=auth_headers,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["exists"] is False
    assert body["archived_to"] is not None
    assert body["archived_to"].startswith("company_seed.archived-")
    assert body["archived_to"].endswith(".md")

    # Original file must be gone; archived sibling must exist.
    assert not seed_file.exists()
    archived = list(tmp_path.glob("company_seed.archived-*.md"))
    assert len(archived) == 1


@pytest.mark.asyncio
async def test_g1_delete_seed_brief_idempotent_when_absent(
    client: AsyncClient,
    auth_headers: dict[str, str],
    tmp_path: Path,
) -> None:
    """DELETE on a missing seed file returns ``exists: false`` cleanly.

    The UI fires DELETE optimistically; the route must not 404 just
    because the file was already archived.
    """
    seed_file = tmp_path / "company_seed.md"
    assert not seed_file.exists()

    with patch(
        "app.api.v1.company_mode._seed_path",
        return_value=seed_file,
    ):
        resp = await client.delete(
            "/api/v1/company-mode/seed-brief",
            headers=auth_headers,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["exists"] is False
    assert body["archived_to"] is None


# ---------------------------------------------------------------------------
# G2 / G3 — Project sub-resources
# ---------------------------------------------------------------------------


async def _create_project(
    client: AsyncClient, headers: dict[str, str], name: str = "Phase 10b project"
) -> dict[str, Any]:
    """Create a project via REST so the test exercises the full flow."""
    resp = await client.post(
        "/api/v1/projects",
        json={"name": name, "description": "phase10b ghost-fix"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["project"]


@pytest.mark.asyncio
async def test_g3_project_tasks_endpoint_returns_honest_empty(
    client: AsyncClient,
) -> None:
    """G3: route exists, returns empty list with explicit gap flag."""
    auth = await _register_and_login(client)
    project = await _create_project(client, auth["headers"])
    resp = await client.get(
        f"/api/v1/projects/{project['id']}/tasks",
        headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["project_id"] == project["id"]
    assert body["task_ids"] == []
    assert body["total"] == 0
    assert body["meta"]["tracking_enabled"] is False
    # Message must mention the schema gap so a future reader knows
    # the empty list is by design, not a transient backend failure.
    assert "schema" in body["meta"]["message"].lower()


@pytest.mark.asyncio
async def test_g2_project_files_endpoint_returns_honest_empty(
    client: AsyncClient,
) -> None:
    """G2: route exists, returns empty list with explicit gap flag."""
    auth = await _register_and_login(client)
    project = await _create_project(client, auth["headers"], name="Phase 10b files")
    resp = await client.get(
        f"/api/v1/projects/{project['id']}/files",
        headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["project_id"] == project["id"]
    assert body["file_paths"] == []
    assert body["total"] == 0
    assert body["meta"]["tracking_enabled"] is False


@pytest.mark.asyncio
async def test_g2_g3_unknown_project_returns_404(
    client: AsyncClient,
) -> None:
    """Unknown project id must still 404 — no leaking other-tenant data."""
    auth = await _register_and_login(client)
    bogus = uuid.uuid4()
    files_resp = await client.get(
        f"/api/v1/projects/{bogus}/files", headers=auth["headers"],
    )
    tasks_resp = await client.get(
        f"/api/v1/projects/{bogus}/tasks", headers=auth["headers"],
    )
    assert files_resp.status_code == 404, files_resp.text
    assert tasks_resp.status_code == 404, tasks_resp.text


# ---------------------------------------------------------------------------
# B3 — archived-scans visibility (GET /security/scans?archived=true)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_b3_scans_list_default_excludes_archive(
    client: AsyncClient,
    auth_headers: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default ``GET /security/scans`` reads from the live reports dir.

    K-3 (2026-06-01): GET /security/scans now filters to scans owned by the
    caller's tenant (and fail-closes legacy reports with no tenant_id, to
    avoid leaking other tenants' scan history). The seeded reports therefore
    carry the auth_headers tenant id (11111111-...) so they represent a
    real, owned scan - which is the only kind a production list ever shows.
    """
    tid = "11111111-1111-1111-1111-111111111111"  # matches auth_headers tenant
    reports = tmp_path / "security_reports"
    archive = reports / ".archive"
    reports.mkdir()
    archive.mkdir()
    (reports / "live-1.json").write_text(
        '{"job_id":"live-1","target":"live.example","tier":"SCOUT",'
        f'"findings":[],"tenant_id":"{tid}"}}',
        encoding="utf-8",
    )
    (archive / "archived-1.report.123.json").write_text(
        '{"job_id":"archived-1","target":"old.example","tier":"SCOUT",'
        f'"findings":[],"tenant_id":"{tid}"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("SECURITY_REPORTS_DIR", str(reports))
    # DAENA_VAR controls the legacy scan_traces dir; point it at tmp so
    # we don't pull real local traces into the assertion.
    monkeypatch.setenv("DAENA_VAR", str(tmp_path))

    resp = await client.get(
        "/api/v1/security/scans", headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    ids = {r["scan_id"] for r in rows}
    assert "live-1" in ids
    assert "archived-1" not in ids


@pytest.mark.asyncio
async def test_b3_scans_list_archived_true_reads_archive(
    client: AsyncClient,
    auth_headers: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``archived=true`` swaps the loader to read the .archive folder.

    K-3 (2026-06-01): both seeded reports carry the auth_headers tenant id
    so they pass the ownership filter. This also pins the K-3 fix that the
    archived view filters on the tenant_id read from the ARCHIVE payload
    (the prior filter consulted only the live dir and hid the whole
    archive even from its owner).
    """
    tid = "11111111-1111-1111-1111-111111111111"  # matches auth_headers tenant
    reports = tmp_path / "security_reports"
    archive = reports / ".archive"
    reports.mkdir()
    archive.mkdir()
    (reports / "live-2.json").write_text(
        '{"job_id":"live-2","target":"live2.example","tier":"SCOUT",'
        f'"findings":[],"tenant_id":"{tid}"}}',
        encoding="utf-8",
    )
    (archive / "archived-2.report.456.json").write_text(
        '{"job_id":"archived-2","target":"old2.example","tier":"SCOUT",'
        f'"findings":[],"tenant_id":"{tid}"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("SECURITY_REPORTS_DIR", str(reports))
    monkeypatch.setenv("DAENA_VAR", str(tmp_path))

    resp = await client.get(
        "/api/v1/security/scans?archived=true", headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    ids = {r["scan_id"] for r in rows}
    assert "archived-2" in ids
    assert "live-2" not in ids


# ---------------------------------------------------------------------------
# G4 — /api/v1/runtimes/subscriptions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_g4_runtimes_subscriptions_returns_envelope_with_warming(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """G4: route exists, shape matches the ``SettingsLLM`` consumer.

    On a fresh test backend the registry has no installed runtimes and
    no subscriptions yet, so the contract is that ``data`` is a list and
    ``warming`` is True. This is the empty-but-honest path the UI relies
    on to render the "no providers connected" badge.
    """
    resp = await client.get(
        "/api/v1/runtimes/subscriptions",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert "warming" in body
    assert body["total"] == len(body["data"])
    for sub in body["data"]:
        # Required keys for the SettingsLLM hash-by-provider lookup.
        for required in ("provider", "runtime_id", "is_authenticated"):
            assert required in sub, f"{required} missing in {sub}"
