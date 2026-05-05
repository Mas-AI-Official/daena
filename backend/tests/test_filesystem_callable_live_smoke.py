"""PR-CONN-FILESYSTEM-CALLABLE-LIVE-SMOKE (Sprint-8 PR-2).

End-to-end smoke proving the placeholder fix from PR-1 unblocks the
real Filesystem-MCP install path. Drives the same three calls the
operator hits from the UI:

  1. POST /marketplace/install-plan/mcp-filesystem/preview
       (no placeholder_values) -- expect placeholder_unresolved + the
       <ALLOWED_ROOT> token surfaced via unresolved_placeholders.

  2. POST /marketplace/install-plan/mcp-filesystem/preview
       (placeholder_values={"<ALLOWED_ROOT>": <safe sandbox>})
       -- expect apply_allowed=True, proposed_block carrying the
       resolved path, no failure_reason.

  3. POST /marketplace/install-plan/mcp-filesystem/apply
       (placeholder_values={"<ALLOWED_ROOT>": <safe sandbox>},
        probe_after_apply=True)
       -- expect a V2 row imported, the on-disk config carrying the
       resolved command, AND a post_apply_probe block whose verdict
       is either success=True OR carries a clear failure_reason.

Honesty:

  * Real test sandbox: ``patched_home`` repoints Path.home + APPDATA
    to a tmp dir so we never touch the operator's actual Claude
    Desktop config.
  * Real probe: probe_after_apply=True triggers an actual stdio spawn.
    The probe fails honestly when ``npx`` is not on PATH (CI) -- that
    failure mode is itself the brief's pass condition ("if real install
    cannot be completed without manual operator action, do not fake it
    -- report exact blocker"). The smoke test asserts the failure is
    REPORTED (not silenced).
  * No external network commit: the test never enables Phase 3 writes
    and never POSTs to a non-localhost host.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.models.identity import Tenant


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    from sqlalchemy import select
    existing = (
        await db_session.execute(select(Tenant).where(Tenant.id == test_tenant_id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    tenant = Tenant(
        id=test_tenant_id,
        name="Sprint-8 PR-2",
        slug=f"s8-{uuid.uuid4().hex[:6]}",
        settings={},
    )
    db_session.add(tenant)
    await db_session.flush()
    await db_session.commit()
    return tenant


@pytest.fixture
def patched_home(monkeypatch, tmp_path: Path) -> Path:
    """Sandbox every CLI config write into tmp_path."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    from app.services.connection_v2.cli_mcp_writer import reset_target_cache
    reset_target_cache()
    yield tmp_path
    reset_target_cache()


# ──────────────────────────────────────────────────────────────────
# 1. Pre-fix path: preview without placeholder_values is honest
# ──────────────────────────────────────────────────────────────────


async def test_filesystem_preview_without_values_surfaces_unresolved_token(
    client, auth_headers, seeded_tenant, patched_home,
):
    res = await client.post(
        "/api/v1/connections/v2/marketplace/install-plan/mcp-filesystem/preview",
        headers=auth_headers,
        json={"target": "claude_desktop", "allow_create": True},
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["apply_allowed"] is False
    assert data["failure_reason"], data
    assert data["failure_reason"].startswith("placeholder_unresolved")
    # The UI's contract: surface the placeholder list so the input form
    # renders on first call, BEFORE the operator has supplied anything.
    assert "<ALLOWED_ROOT>" in data["unresolved_placeholders"]


# ──────────────────────────────────────────────────────────────────
# 2. Post-fix path: preview with placeholder_values reaches apply_allowed
# ──────────────────────────────────────────────────────────────────


async def test_filesystem_preview_with_values_resolves_to_apply_allowed(
    client, auth_headers, seeded_tenant, patched_home,
):
    sandbox = str(patched_home)
    res = await client.post(
        "/api/v1/connections/v2/marketplace/install-plan/mcp-filesystem/preview",
        headers=auth_headers,
        json={
            "target": "claude_desktop",
            "allow_create": True,
            "placeholder_values": {"<ALLOWED_ROOT>": sandbox},
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["apply_allowed"] is True, data
    assert data["failure_reason"] is None
    assert data["unresolved_placeholders"] == []
    assert data["proposed_block"] is not None
    args = data["proposed_block"]["args"]
    # The resolved path must reach the args list, not the literal token.
    assert "<ALLOWED_ROOT>" not in args
    assert any(
        a == sandbox or a.replace("\\", "/") == sandbox.replace("\\", "/")
        for a in args
    ), args


# ──────────────────────────────────────────────────────────────────
# 3. Apply: V2 row imported + on-disk config carries resolved command
# ──────────────────────────────────────────────────────────────────


async def test_filesystem_apply_writes_resolved_command_and_imports_row(
    client, auth_headers, seeded_tenant, patched_home,
):
    sandbox = str(patched_home)
    res = await client.post(
        "/api/v1/connections/v2/marketplace/install-plan/mcp-filesystem/apply",
        headers=auth_headers,
        json={
            "target": "claude_desktop",
            "allow_create": True,
            "placeholder_values": {"<ALLOWED_ROOT>": sandbox},
            # NOTE: probe_after_apply=False here -- we exercise the probe
            # in a separate test so this one stays fast even on machines
            # without npx on PATH.
            "probe_after_apply": False,
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["action"] in ("created", "create_file"), data
    assert data["failure_reason"] is None
    assert data["v2_row_id"] is not None
    assert data["v2_label"] is not None

    cfg_path = Path(data["config_path"])
    assert cfg_path.exists()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    block = cfg.get("mcpServers", {}).get("filesystem")
    assert block is not None, cfg
    args = block["args"]
    # Literal placeholder must not survive into the on-disk config.
    assert "<ALLOWED_ROOT>" not in args
    assert any(
        a == sandbox or a.replace("\\", "/") == sandbox.replace("\\", "/")
        for a in args
    ), args


# ──────────────────────────────────────────────────────────────────
# 4. Apply with probe_after_apply: probe MUST run and report a verdict
# ──────────────────────────────────────────────────────────────────


async def test_filesystem_apply_probe_after_apply_returns_honest_verdict(
    client, auth_headers, seeded_tenant, patched_home,
):
    """The brief's pass condition: lifecycle flips to callable OR the
    response carries a clear failure_reason explaining what's missing.
    Either outcome is honest; faking success without a probe is not."""
    sandbox = str(patched_home)
    res = await client.post(
        "/api/v1/connections/v2/marketplace/install-plan/mcp-filesystem/apply",
        headers=auth_headers,
        json={
            "target": "claude_desktop",
            "allow_create": True,
            "placeholder_values": {"<ALLOWED_ROOT>": sandbox},
            "probe_after_apply": True,
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["action"] in ("created", "create_file"), data
    probe = data.get("post_apply_probe")
    assert probe is not None, (
        "probe_after_apply=true must always return a post_apply_probe "
        "block; silence here would mean the UI shows a fake 'connected' "
        "without proof"
    )
    if probe.get("success") is True:
        # Lifecycle truly callable -- best-case acceptance.
        assert probe.get("failure_reason") in (None, ""), probe
    else:
        # Honest blocker -- failure_reason MUST be present.
        assert probe.get("failure_reason"), (
            f"probe failed without an explanation: {probe!r}"
        )
        assert probe.get("failure_dim") in (
            "callable", "reachable", "configured", "installed",
        ), probe
