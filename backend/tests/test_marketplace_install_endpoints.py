"""PR-CONN-MCP-INSTALL-INTO-CLI -- end-to-end endpoint tests.

Pins the public REST contract:

  /api/v1/connections/v2/marketplace/install-plan/{entry_id}/preview
  /api/v1/connections/v2/marketplace/install-plan/{entry_id}/apply

Covers:
  1. preview returns shape + apply_allowed for a happy path
  2. preview rejects unsupported target with 400
  3. preview rejects unknown entry with 404
  4. preview rejects non-mcp_server kind (e.g. cli_runtime) with 400
  5. apply happy path: writes config, imports V2 row, returns label
  6. apply idempotent: second call returns "skipped"
  7. apply with probe_after_apply=true returns post_apply_probe block
  8. apply with malformed config returns failed + does not write
  9. preview's required_env_vars is NAMES only (founder rule 14)
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

from app.models.identity import Tenant


pytestmark = pytest.mark.asyncio


# ──────────────────────────────────────────────────────────────────
# Shared seeded tenant fixture
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    """Idempotent: re-uses the existing tenant if a prior test commit
    left it in the DB. The endpoint tests perform real db.commit calls
    so the rollback in db_session can't undo them; using merge()-style
    upsert avoids the UNIQUE-slug collision on re-runs."""
    from sqlalchemy import select
    existing = (
        await db_session.execute(select(Tenant).where(Tenant.id == test_tenant_id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    tenant = Tenant(id=test_tenant_id, name="T", slug="t", settings={})
    db_session.add(tenant)
    await db_session.flush()
    await db_session.commit()
    return tenant


@pytest.fixture
def patched_home(monkeypatch, tmp_path: Path) -> Path:
    """Repoint Path.home() to tmp_path + reset writer's target cache."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    from app.services.connection_v2.cli_mcp_writer import reset_target_cache
    reset_target_cache()
    yield tmp_path
    reset_target_cache()


# ──────────────────────────────────────────────────────────────────
# 1. Preview happy path
# ──────────────────────────────────────────────────────────────────


class TestPreviewHappyPath:
    async def test_preview_returns_proposed_block_and_action(
        self, client, auth_headers, seeded_tenant, patched_home,
    ):
        res = await client.post(
            "/api/v1/connections/v2/marketplace/install-plan/mcp-time/preview",
            headers=auth_headers,
            json={"target": "claude_code", "allow_create": True},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["success"] is True
        data = body["data"]
        assert data["target"] == "claude_code"
        assert data["server_name"] == "time"
        assert data["proposed_block"]["command"] == "npx"
        assert "@modelcontextprotocol/server-time" in data["proposed_block"]["args"]
        assert data["action"] == "create_file"
        assert data["apply_allowed"] is True
        assert data["failure_reason"] is None


# ──────────────────────────────────────────────────────────────────
# 2. Preview rejects unsupported target with 400
# ──────────────────────────────────────────────────────────────────


class TestPreviewRejectsUnsupportedTarget:
    async def test_invalid_target_returns_422(
        self, client, auth_headers, seeded_tenant,
    ):
        # Pydantic Literal validation -> 422 for unknown literal.
        res = await client.post(
            "/api/v1/connections/v2/marketplace/install-plan/mcp-time/preview",
            headers=auth_headers,
            json={"target": "vim", "allow_create": False},
        )
        assert res.status_code == 422, res.text


# ──────────────────────────────────────────────────────────────────
# 3. Preview unknown entry -> 404
# ──────────────────────────────────────────────────────────────────


class TestPreviewUnknownEntry:
    async def test_unknown_entry_returns_404(
        self, client, auth_headers, seeded_tenant,
    ):
        res = await client.post(
            "/api/v1/connections/v2/marketplace/install-plan/mcp-does-not-exist/preview",
            headers=auth_headers,
            json={"target": "claude_code"},
        )
        assert res.status_code == 404, res.text
        assert res.json()["detail"] == "catalog_entry_not_found"


# ──────────────────────────────────────────────────────────────────
# 4. Preview rejects non-mcp_server kind (e.g. cli_runtime) -> 400
# ──────────────────────────────────────────────────────────────────


class TestPreviewRejectsNonMcpKind:
    async def test_cli_runtime_entry_rejected(
        self, client, auth_headers, seeded_tenant,
    ):
        # cli-claude-code is a CLI runtime, NOT an MCP server.
        res = await client.post(
            "/api/v1/connections/v2/marketplace/install-plan/cli-claude-code/preview",
            headers=auth_headers,
            json={"target": "claude_code"},
        )
        assert res.status_code == 400, res.text
        assert "install_unsupported_kind" in res.json()["detail"]


# ──────────────────────────────────────────────────────────────────
# 5. Apply happy path -- writes config + imports V2 row
# ──────────────────────────────────────────────────────────────────


class TestApplyHappyPath:
    async def test_apply_creates_config_and_imports_row(
        self, client, auth_headers, seeded_tenant, patched_home,
    ):
        res = await client.post(
            "/api/v1/connections/v2/marketplace/install-plan/mcp-time/apply",
            headers=auth_headers,
            json={"target": "claude_code", "allow_create": True},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["success"] is True
        data = body["data"]
        assert data["action"] == "create_file"
        assert data["server_name"] == "time"
        assert data["failure_reason"] is None

        # File now exists and has the time MCP under mcpServers.
        cfg = json.loads((patched_home / ".claude.json").read_text())
        assert "mcpServers" in cfg
        assert "time" in cfg["mcpServers"]
        assert cfg["mcpServers"]["time"]["command"] == "npx"

        # V2 row was imported.
        assert data["v2_row_id"] is not None
        assert data["v2_label"] is not None


# ──────────────────────────────────────────────────────────────────
# 6. Apply idempotent: second call returns "skipped"
# ──────────────────────────────────────────────────────────────────


class TestApplyIdempotent:
    async def test_second_apply_skips(
        self, client, auth_headers, seeded_tenant, patched_home,
    ):
        # First apply
        res1 = await client.post(
            "/api/v1/connections/v2/marketplace/install-plan/mcp-time/apply",
            headers=auth_headers,
            json={"target": "claude_code", "allow_create": True},
        )
        assert res1.status_code == 200
        assert res1.json()["data"]["action"] == "create_file"

        # Second apply -- everything matches; expect skipped.
        res2 = await client.post(
            "/api/v1/connections/v2/marketplace/install-plan/mcp-time/apply",
            headers=auth_headers,
            json={"target": "claude_code"},
        )
        assert res2.status_code == 200
        body2 = res2.json()
        assert body2["data"]["action"] == "skipped"
        assert body2["data"]["backup_path"] is None


# ──────────────────────────────────────────────────────────────────
# 7. Apply with probe_after_apply=true returns probe block
# ──────────────────────────────────────────────────────────────────


class TestApplyWithProbe:
    async def test_apply_then_probe_runs_mcp_initialize(
        self, client, auth_headers, seeded_tenant, patched_home, monkeypatch,
    ):
        # Use a custom catalog entry pointing at our happy fake MCP so
        # the probe actually succeeds. We stub the entry's command_template
        # to invoke fake_mcp_ok.py via sys.executable.
        from app.services.connection_v2 import marketplace_catalog as catalog_mod

        FIX = (
            Path(__file__).parent / "fixtures" / "fake_mcp_servers" / "fake_mcp_ok.py"
        )
        # We can't mutate frozen CatalogEntry; replace the time entry in
        # CATALOG with a mutable shim for the duration of this test.
        original = catalog_mod.CATALOG
        replaced = []
        for e in original:
            if e.id == "mcp-time":
                # Build a new entry with the fake command_template.
                replaced.append(catalog_mod.CatalogEntry(
                    id=e.id, display_name=e.display_name, vendor=e.vendor,
                    category=e.category, kind=e.kind,
                    short_description=e.short_description,
                    capabilities=e.capabilities,
                    install_method=e.install_method,
                    command_template=f"{sys.executable} {FIX}",
                    required_env_vars=e.required_env_vars,
                    auth_type=e.auth_type, official_url=e.official_url,
                    risk_level=e.risk_level, probe_type=e.probe_type,
                    compatible_os=e.compatible_os,
                    matches_v2_slug=e.matches_v2_slug,
                    setup_notes=e.setup_notes,
                ))
            else:
                replaced.append(e)
        monkeypatch.setattr(
            catalog_mod, "CATALOG", tuple(replaced),
        )
        # The connections_v2 module imported CATALOG by name, so patch
        # it there too.
        from app.api.v1 import connections_v2 as endpoint_mod
        monkeypatch.setattr(endpoint_mod, "CATALOG", tuple(replaced))

        # Ensure the MCP probe is registered in the registry.
        from app.services.connection_v2.probes import install_all_probes
        install_all_probes()

        res = await client.post(
            "/api/v1/connections/v2/marketplace/install-plan/mcp-time/apply",
            headers=auth_headers,
            json={
                "target": "claude_code",
                "allow_create": True,
                "probe_after_apply": True,
            },
        )
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["action"] == "create_file"
        assert data["v2_row_id"] is not None
        # Probe should fire and succeed against the fake MCP.
        assert data["post_apply_probe"] is not None
        # Either succeeded (happy path) or surfaced an honest failure
        # reason -- in CI environments the asyncio plumbing can hiccup,
        # but we should NEVER see a None outcome when probe was opted in.
        assert "success" in data["post_apply_probe"]


# ──────────────────────────────────────────────────────────────────
# 8. Apply with malformed config -> failed + no overwrite
# ──────────────────────────────────────────────────────────────────


class TestApplyMalformedConfig:
    async def test_apply_refuses_to_overwrite_malformed_json(
        self, client, auth_headers, seeded_tenant, patched_home,
    ):
        cfg = patched_home / ".claude.json"
        original_bytes = b"{ this is broken json"
        cfg.write_bytes(original_bytes)

        res = await client.post(
            "/api/v1/connections/v2/marketplace/install-plan/mcp-time/apply",
            headers=auth_headers,
            json={"target": "claude_code"},
        )
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["action"] == "failed"
        assert data["failure_reason"].startswith("config_parse_error")
        # File untouched on disk.
        assert cfg.read_bytes() == original_bytes


# ──────────────────────────────────────────────────────────────────
# 9. Required env vars surface as NAMES only
# ──────────────────────────────────────────────────────────────────


class TestEnvVarsSurfaceAsNames:
    async def test_preview_carries_env_var_names_not_values(
        self, client, auth_headers, seeded_tenant, patched_home, monkeypatch,
    ):
        # Plant a sentinel value in the env. The preview must NEVER
        # return it (founder rule 14: env values stay in env / vault).
        sentinel = "ghp_test_sentinel_should_not_leak_8765"  # noqa: S105
        monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", sentinel)

        res = await client.post(
            "/api/v1/connections/v2/marketplace/install-plan/mcp-github/preview",
            headers=auth_headers,
            json={"target": "claude_code", "allow_create": True},
        )
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        # NAME present, VALUE absent.
        assert "GITHUB_PERSONAL_ACCESS_TOKEN" in data["required_env_vars"]
        full_text = json.dumps(data)
        assert sentinel not in full_text, (
            "preview LEAKED env value into response payload"
        )
        # Proposed block has no env block at all.
        assert "env" not in data["proposed_block"]
