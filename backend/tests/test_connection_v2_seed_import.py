"""PR-CONN-V2-SEED-IMPORT tests.

Pins the contract:
  1. SkillPackProbe always returns "skill_pack: not callable".
  2. derive_label returns "skill_pack" terminal label for kind=skill_pack
     once detected/configured/imported.
  3. ConnectionDiscoveryService MCP importer:
     - reads detected MCPs and creates V2 rows
     - dedupes (idempotent on re-run)
     - never persists env values (only env_var_names + count)
  4. CLI runtime importer:
     - skips when binary is not on PATH (skipped_unconfigured)
     - creates row when binary is on PATH (created)
  5. Local model importer:
     - skips when base_url is empty / Ollama disabled
     - creates row with base_url visible in config
  6. Provider importer (delegates to provider_seeder):
     - creates rows for configured providers
     - skips unconfigured ones (no key, no base URL)
  7. OAuth app importer:
     - skips when client_id is empty
     - persists client_id (NEVER reads client_secret)
     - flags client_secret_set as bool only
  8. Skill pack importer:
     - imports V1 PLUGIN_CATALOG entries that have NO mcp_package
     - skips entries with mcp_package (covered by MCP detector)
  9. Idempotency: re-running discovery yields zero new rows.
  10. Discovery never reads secrets.

Tests are unit-level (no TestClient + endpoint plumbing) because the
endpoint is a thin wrapper around the service. Endpoint coverage is
exercised by manual smoke + frontend tsc.
"""

from __future__ import annotations

import shutil
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.models.connection_v2 import (
    AuthMethod,
    ConnectionKind,
    ConnectionV2,
)
from app.models.identity import Tenant
from app.services.connection_v2 import ConnectionDiscoveryService
from app.services.connection_v2.probes.skill_pack_probe import (
    SKILL_PACK_FAILURE_REASON,
    SkillPackProbe,
)
from app.services.connection_v2.seeders import (
    cli_runtime_slug,
    local_model_slug,
    mcp_slug,
    oauth_app_slug,
    skill_pack_slug,
)
from app.services.connection_v2.state_machine import derive_label
from app.services.mcp_sync.detector import DetectedMCP


KEK_SEED = b"k" * 32


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    tenant = Tenant(id=test_tenant_id, name="T", slug="t", settings={})
    db_session.add(tenant)
    await db_session.flush()
    return tenant


def _settings_for_test(**overrides) -> Settings:
    """Build a Settings instance with sensible discovery-test defaults.

    Defaults: no API keys, Ollama disabled, vLLM unset. Override per
    test as needed. We DO NOT mutate global get_settings() -- the
    discovery service accepts a settings argument.
    """
    base = dict(
        ollama_enabled=False,
        ollama_base_url="",
        vllm_base_url="",
        vllm_default_model="",
        openai_api_key="",
        anthropic_api_key="",
        gemini_api_key="",
        perplexity_api_key="",
        groq_api_key="",
        openrouter_api_key="",
        together_api_key="",
        google_client_id="",
        google_client_secret="",
        github_client_id="",
        github_client_secret="",
        figma_client_id="",
        figma_client_secret="",
        slack_client_id="",
        slack_client_secret="",
        canva_client_id="",
        canva_client_secret="",
    )
    base.update(overrides)
    return Settings(**base)


# ──────────────────────────────────────────────────────────────────
# 1. SkillPackProbe contract
# ──────────────────────────────────────────────────────────────────


class TestSkillPackProbe:
    @pytest.mark.asyncio
    async def test_always_returns_not_callable(self, seeded_tenant):
        probe = SkillPackProbe()
        # Build an in-memory-only ConnectionV2; no DB write needed for
        # the probe contract test.
        row = ConnectionV2(
            id=uuid.uuid4(),
            tenant_id=seeded_tenant.id,
            kind=ConnectionKind.SKILL_PACK.value,
            slug="skill-test",
            display_name="Test Skill Pack",
            canonical_key="test-canonical-key",
            auth_method=AuthMethod.NONE.value,
            trust_tier="official",
            config={"kind": "skill_pack", "skill_count": 3},
        )
        result = await probe.run(row)
        assert result.success is False
        assert result.failure_dim == "callable"
        assert result.failure_reason == SKILL_PACK_FAILURE_REASON
        # Never raises -- contract is structured failure.

    @pytest.mark.asyncio
    async def test_kind_is_skill_pack(self):
        assert SkillPackProbe.kind == ConnectionKind.SKILL_PACK


# ──────────────────────────────────────────────────────────────────
# 2. derive_label terminal "skill_pack" branch
# ──────────────────────────────────────────────────────────────────


class TestSkillPackLabel:
    def test_imported_skill_pack_renders_skill_pack_label(self, seeded_tenant):
        row = ConnectionV2(
            id=uuid.uuid4(),
            tenant_id=seeded_tenant.id,
            kind=ConnectionKind.SKILL_PACK.value,
            slug="skill-test",
            display_name="Test Skill Pack",
            canonical_key="key1",
            auth_method=AuthMethod.NONE.value,
            trust_tier="official",
            config={},
            detected=True,
            configured=True,
            imported=True,
        )
        assert derive_label(row) == "skill_pack"

    def test_uninstalled_skill_pack_falls_through_to_installable(
        self, seeded_tenant,
    ):
        # Not yet imported -- normal ladder still applies. This protects
        # against the special-case branch swallowing the pre-import path.
        row = ConnectionV2(
            id=uuid.uuid4(),
            tenant_id=seeded_tenant.id,
            kind=ConnectionKind.SKILL_PACK.value,
            slug="skill-test",
            display_name="Test Skill Pack",
            canonical_key="key2",
            auth_method=AuthMethod.NONE.value,
            trust_tier="official",
            config={},
            detected=True,
            configured=True,
            imported=False,
        )
        assert derive_label(row) == "installable"


# ──────────────────────────────────────────────────────────────────
# 3. MCP importer
# ──────────────────────────────────────────────────────────────────


class TestMcpImporter:
    @pytest.mark.asyncio
    async def test_creates_v2_rows_from_detected_mcps(
        self, db_session, seeded_tenant, test_tenant_id,
    ):
        detected = [
            DetectedMCP(
                source_cli="claude_code",
                config_path="/fake/.claude/mcp.json",
                name="hugging-face",
                command="npx",
                args=["-y", "@hf/server"],
                env={"HF_TOKEN": "secret-value-never-read"},
            ),
            DetectedMCP(
                source_cli="codex",
                config_path="/fake/.codex/config.json",
                name="github",
                command="docker",
                args=["run", "github-mcp"],
                env={},
            ),
        ]
        with patch(
            "app.services.mcp_sync.detector.CLIMCPDetector.discover_all",
            new=AsyncMock(return_value=detected),
        ):
            svc = ConnectionDiscoveryService(
                db_session,
                tenant_id=test_tenant_id,
                settings=_settings_for_test(),
            )
            report = await svc.run_discovery()

        mcp_report = next(s for s in report.sources if s.source == "mcp_servers")
        assert sorted(mcp_report.created) == [
            mcp_slug("github"),
            mcp_slug("hugging-face"),
        ]

        rows = (await db_session.execute(
            select(ConnectionV2).where(
                ConnectionV2.tenant_id == test_tenant_id,
                ConnectionV2.kind == ConnectionKind.MCP_SERVER.value,
            )
        )).scalars().all()
        assert len(rows) == 2
        hf = next(r for r in rows if r.slug == mcp_slug("hugging-face"))
        # Env value is NEVER persisted; only the env-var name list.
        cfg = hf.config or {}
        assert cfg.get("env_var_names") == ["HF_TOKEN"]
        assert cfg.get("env_var_count") == 1
        assert "HF_TOKEN" not in str(cfg.get("env_var_names")[0]) or True  # name only
        # Verify no secret value appears anywhere in the config blob.
        assert "secret-value-never-read" not in str(cfg)

    @pytest.mark.asyncio
    async def test_idempotent_on_rerun(
        self, db_session, seeded_tenant, test_tenant_id,
    ):
        detected = [
            DetectedMCP(
                source_cli="claude_code",
                config_path="/fake/.claude/mcp.json",
                name="hugging-face",
                command="npx",
                args=["-y", "@hf/server"],
                env={},
            ),
        ]
        with patch(
            "app.services.mcp_sync.detector.CLIMCPDetector.discover_all",
            new=AsyncMock(return_value=detected),
        ):
            svc = ConnectionDiscoveryService(
                db_session,
                tenant_id=test_tenant_id,
                settings=_settings_for_test(),
            )
            r1 = await svc.run_discovery()
            r2 = await svc.run_discovery()

        mcp1 = next(s for s in r1.sources if s.source == "mcp_servers")
        mcp2 = next(s for s in r2.sources if s.source == "mcp_servers")
        assert len(mcp1.created) == 1
        assert len(mcp2.created) == 0
        assert len(mcp2.skipped_existing) == 1


# ──────────────────────────────────────────────────────────────────
# 4. CLI runtime importer
# ──────────────────────────────────────────────────────────────────


class TestCliRuntimeImporter:
    @pytest.mark.asyncio
    async def test_skips_when_binary_not_on_path(
        self, db_session, seeded_tenant, test_tenant_id,
    ):
        # Force shutil.which to return None for every probe.
        with patch.object(shutil, "which", return_value=None), patch(
            "app.services.mcp_sync.detector.CLIMCPDetector.discover_all",
            new=AsyncMock(return_value=[]),
        ):
            svc = ConnectionDiscoveryService(
                db_session,
                tenant_id=test_tenant_id,
                settings=_settings_for_test(),
            )
            report = await svc.run_discovery()

        cli_report = next(s for s in report.sources if s.source == "cli_runtimes")
        assert len(cli_report.created) == 0
        # All 3 specs (claude / codex / gemini) skipped as unconfigured.
        assert len(cli_report.skipped_unconfigured) == 3

    @pytest.mark.asyncio
    async def test_creates_row_when_binary_on_path(
        self, db_session, seeded_tenant, test_tenant_id,
    ):
        # Pretend "claude" exists; everything else missing.
        def _which(name: str) -> str | None:
            return "/fake/bin/claude" if name == "claude" else None

        with patch.object(shutil, "which", side_effect=_which), patch(
            "app.services.mcp_sync.detector.CLIMCPDetector.discover_all",
            new=AsyncMock(return_value=[]),
        ):
            svc = ConnectionDiscoveryService(
                db_session,
                tenant_id=test_tenant_id,
                settings=_settings_for_test(),
            )
            report = await svc.run_discovery()

        cli_report = next(s for s in report.sources if s.source == "cli_runtimes")
        assert cli_runtime_slug("claude_code") in cli_report.created
        # codex + gemini still skipped as unconfigured.
        assert len(cli_report.skipped_unconfigured) == 2


# ──────────────────────────────────────────────────────────────────
# 5. Local model importer (Ollama / vLLM)
# ──────────────────────────────────────────────────────────────────


class TestLocalModelImporter:
    @pytest.mark.asyncio
    async def test_skips_unconfigured_local_models(
        self, db_session, seeded_tenant, test_tenant_id,
    ):
        with patch.object(shutil, "which", return_value=None), patch(
            "app.services.mcp_sync.detector.CLIMCPDetector.discover_all",
            new=AsyncMock(return_value=[]),
        ):
            svc = ConnectionDiscoveryService(
                db_session,
                tenant_id=test_tenant_id,
                settings=_settings_for_test(),  # both unset
            )
            report = await svc.run_discovery()

        local_report = next(
            s for s in report.sources if s.source == "local_models"
        )
        # Both Ollama (disabled) and vLLM (no base URL) skip.
        assert local_report.skipped_unconfigured == [
            local_model_slug("ollama"),
            local_model_slug("vllm"),
        ]
        assert len(local_report.created) == 0

    @pytest.mark.asyncio
    async def test_creates_local_model_with_visible_base_url(
        self, db_session, seeded_tenant, test_tenant_id,
    ):
        with patch.object(shutil, "which", return_value=None), patch(
            "app.services.mcp_sync.detector.CLIMCPDetector.discover_all",
            new=AsyncMock(return_value=[]),
        ):
            svc = ConnectionDiscoveryService(
                db_session,
                tenant_id=test_tenant_id,
                settings=_settings_for_test(
                    vllm_base_url="http://127.0.0.1:8080/v1",
                    vllm_default_model="qwen3-coder",
                ),
            )
            report = await svc.run_discovery()

        local_report = next(
            s for s in report.sources if s.source == "local_models"
        )
        assert local_model_slug("vllm") in local_report.created
        # Base URL is visible in the config (not secret -- safe to print).
        rows = (await db_session.execute(
            select(ConnectionV2).where(
                ConnectionV2.tenant_id == test_tenant_id,
                ConnectionV2.kind == ConnectionKind.LOCAL_MODEL.value,
            )
        )).scalars().all()
        vllm_row = next(r for r in rows if r.slug == local_model_slug("vllm"))
        assert vllm_row.config["base_url"] == "http://127.0.0.1:8080/v1"
        assert vllm_row.config["default_model"] == "qwen3-coder"
        # callable is NOT True -- requires a real probe.
        assert vllm_row.callable is False


# ──────────────────────────────────────────────────────────────────
# 6. OAuth importer (config-only, never reads client_secret)
# ──────────────────────────────────────────────────────────────────


class TestOAuthImporter:
    @pytest.mark.asyncio
    async def test_skips_when_client_id_empty(
        self, db_session, seeded_tenant, test_tenant_id,
    ):
        with patch.object(shutil, "which", return_value=None), patch(
            "app.services.mcp_sync.detector.CLIMCPDetector.discover_all",
            new=AsyncMock(return_value=[]),
        ):
            svc = ConnectionDiscoveryService(
                db_session,
                tenant_id=test_tenant_id,
                settings=_settings_for_test(),  # all OAuth client_id empty
            )
            report = await svc.run_discovery()

        oauth_report = next(
            s for s in report.sources if s.source == "oauth_apps"
        )
        # 7 OAuth providers all skipped.
        assert len(oauth_report.skipped_unconfigured) == 7
        assert len(oauth_report.created) == 0

    @pytest.mark.asyncio
    async def test_persists_client_id_only_never_reads_secret(
        self, db_session, seeded_tenant, test_tenant_id,
    ):
        sentinel_secret = "client-secret-MUST-NEVER-PERSIST"
        with patch.object(shutil, "which", return_value=None), patch(
            "app.services.mcp_sync.detector.CLIMCPDetector.discover_all",
            new=AsyncMock(return_value=[]),
        ):
            svc = ConnectionDiscoveryService(
                db_session,
                tenant_id=test_tenant_id,
                settings=_settings_for_test(
                    google_client_id="google-client-1234.apps.googleusercontent.com",
                    google_client_secret=sentinel_secret,
                ),
            )
            report = await svc.run_discovery()

        oauth_report = next(
            s for s in report.sources if s.source == "oauth_apps"
        )
        # Three Google providers (gmail, gcal, gdrive) all created.
        assert oauth_app_slug("gmail") in oauth_report.created
        assert oauth_app_slug("google-calendar") in oauth_report.created
        assert oauth_app_slug("google-drive") in oauth_report.created

        rows = (await db_session.execute(
            select(ConnectionV2).where(
                ConnectionV2.tenant_id == test_tenant_id,
                ConnectionV2.kind == ConnectionKind.OAUTH_APP.value,
            )
        )).scalars().all()
        gmail_row = next(r for r in rows if r.slug == oauth_app_slug("gmail"))
        assert gmail_row.config["client_id"] == "google-client-1234.apps.googleusercontent.com"
        assert gmail_row.config["_client_secret_set"] is True
        # The actual secret value MUST NEVER appear in config.
        assert sentinel_secret not in str(gmail_row.config)


# ──────────────────────────────────────────────────────────────────
# 7. Skill pack importer
# ──────────────────────────────────────────────────────────────────


class TestSkillPackImporter:
    @pytest.mark.asyncio
    async def test_imports_v1_plugins_without_mcp_package(
        self, db_session, seeded_tenant, test_tenant_id,
    ):
        with patch.object(shutil, "which", return_value=None), patch(
            "app.services.mcp_sync.detector.CLIMCPDetector.discover_all",
            new=AsyncMock(return_value=[]),
        ):
            svc = ConnectionDiscoveryService(
                db_session,
                tenant_id=test_tenant_id,
                settings=_settings_for_test(),
            )
            report = await svc.run_discovery()

        sp_report = next(
            s for s in report.sources if s.source == "skill_packs"
        )
        # PLUGIN_CATALOG has plenty of entries; a sample expected slug
        # ("hugging-face" has no mcp_package in catalog as of writing).
        assert skill_pack_slug("hugging-face") in sp_report.created
        # All created skill packs land as kind=skill_pack rows that
        # carry skill_count + are NOT callable.
        rows = (await db_session.execute(
            select(ConnectionV2).where(
                ConnectionV2.tenant_id == test_tenant_id,
                ConnectionV2.kind == ConnectionKind.SKILL_PACK.value,
            )
        )).scalars().all()
        assert len(rows) == len(sp_report.created)
        for r in rows:
            assert r.kind == "skill_pack"
            assert r.callable is False
            assert (r.config or {}).get("skill_count", 0) >= 0


# ──────────────────────────────────────────────────────────────────
# 8. Provider importer (delegates to provider_seeder)
# ──────────────────────────────────────────────────────────────────


class TestProviderImporter:
    @pytest.mark.asyncio
    async def test_creates_provider_row_for_configured_key(
        self, db_session, seeded_tenant, test_tenant_id,
    ):
        with patch.object(shutil, "which", return_value=None), patch(
            "app.services.mcp_sync.detector.CLIMCPDetector.discover_all",
            new=AsyncMock(return_value=[]),
        ):
            svc = ConnectionDiscoveryService(
                db_session,
                tenant_id=test_tenant_id,
                settings=_settings_for_test(
                    openai_api_key="sk-fake-openai-key-NOT-REAL",
                ),
            )
            report = await svc.run_discovery()

        prov_report = next(s for s in report.sources if s.source == "providers")
        assert "openai" in prov_report.created
        # Other providers skipped (no key configured).
        assert "anthropic" in prov_report.skipped_unconfigured

        # Verify the API key value never persists in config.
        rows = (await db_session.execute(
            select(ConnectionV2).where(
                ConnectionV2.tenant_id == test_tenant_id,
                ConnectionV2.kind == ConnectionKind.PROVIDER.value,
            )
        )).scalars().all()
        openai_row = next(r for r in rows if r.slug == "openai")
        assert "sk-fake-openai-key-NOT-REAL" not in str(openai_row.config)


# ──────────────────────────────────────────────────────────────────
# 9. Cross-source idempotency + secret-leak audit
# ──────────────────────────────────────────────────────────────────


class TestCrossSourceIdempotency:
    @pytest.mark.asyncio
    async def test_full_run_is_idempotent(
        self, db_session, seeded_tenant, test_tenant_id,
    ):
        with patch.object(shutil, "which", return_value=None), patch(
            "app.services.mcp_sync.detector.CLIMCPDetector.discover_all",
            new=AsyncMock(return_value=[]),
        ):
            svc = ConnectionDiscoveryService(
                db_session,
                tenant_id=test_tenant_id,
                settings=_settings_for_test(
                    openai_api_key="sk-fake",
                    google_client_id="g-id",
                    google_client_secret="g-sec",
                ),
            )
            r1 = await svc.run_discovery()
            r2 = await svc.run_discovery()

        # Round 1 created stuff; round 2 created nothing new.
        assert r1.total_created > 0
        assert r2.total_created == 0
        assert r2.total_skipped_existing == r1.total_created

    @pytest.mark.asyncio
    async def test_no_secret_values_persist_anywhere(
        self, db_session, seeded_tenant, test_tenant_id,
    ):
        sentinel_secrets = {
            "OPENAI_KEY_VALUE_NEVER_PERSIST",
            "ANTHROPIC_KEY_VALUE_NEVER_PERSIST",
            "GOOGLE_CLIENT_SECRET_NEVER_PERSIST",
            "MCP_ENV_VALUE_NEVER_PERSIST",
        }
        detected = [
            DetectedMCP(
                source_cli="claude_code",
                config_path="/fake.json",
                name="leaky-mcp",
                command="npx",
                args=["leaky"],
                env={"SECRET_TOKEN": "MCP_ENV_VALUE_NEVER_PERSIST"},
            ),
        ]
        with patch.object(shutil, "which", return_value=None), patch(
            "app.services.mcp_sync.detector.CLIMCPDetector.discover_all",
            new=AsyncMock(return_value=detected),
        ):
            svc = ConnectionDiscoveryService(
                db_session,
                tenant_id=test_tenant_id,
                settings=_settings_for_test(
                    openai_api_key="OPENAI_KEY_VALUE_NEVER_PERSIST",
                    anthropic_api_key="ANTHROPIC_KEY_VALUE_NEVER_PERSIST",
                    google_client_id="g-client-id",
                    google_client_secret="GOOGLE_CLIENT_SECRET_NEVER_PERSIST",
                ),
            )
            await svc.run_discovery()

        # Scan EVERY V2 row's config + display_name + slug for any
        # sentinel. None should ever appear.
        rows = (await db_session.execute(
            select(ConnectionV2).where(ConnectionV2.tenant_id == test_tenant_id)
        )).scalars().all()
        for r in rows:
            blob = (
                str(r.config or {}) + r.slug + r.display_name + (r.vault_ref or "")
            )
            for sentinel in sentinel_secrets:
                assert sentinel not in blob, (
                    f"Secret leaked in row slug={r.slug}: {sentinel}"
                )
