"""V2 seed/import service -- ingest the real connection inventory.

PR-CONN-V2-SEED-IMPORT (2026-05-02): the V2 panels were canonical but
empty in dev because the only seeder (``provider_seeder``) is gated on
``USE_CONNECTION_REGISTRY_V2`` at startup. This module fills the gap
by giving the operator an explicit "Refresh discovery" import that
walks the same real sources V1 already reads from and materializes
``ConnectionV2`` rows for each one. Idempotent: re-running on the same
tenant adds nothing new when nothing has changed on disk.

What it imports:
  1. **MCP servers** -- merged across Claude Code / Codex / Gemini CLI
     configs via ``mcp_sync.detector.CLIMCPDetector``. Each unique
     ``(name, command, args)`` triple becomes one row of
     ``kind=mcp_server`` whose probe will eventually run a real
     ``initialize`` + ``tools/list`` JSON-RPC handshake (still
     PROBE_UNAVAILABLE today, see CONN-MCP-PROBE blocker).
  2. **CLI runtimes** -- one row per ``CliRuntimeSpec`` in
     ``providers/claude_cli.py``. Detection is binary-on-PATH only;
     a real ``CliRuntimeProbe`` is still PROBE_UNAVAILABLE.
  3. **Local model endpoints** -- Ollama and vLLM as ``kind=local_model``
     when the operator configured a base URL. Re-uses provider_seeder
     for actual probing once the V2 flag flips, but persists the row
     immediately so the V2 surface is no longer empty.
  4. **API providers** -- delegates to ``provider_seeder`` so dev
     operators see provider rows without having to flip the flag.
  5. **OAuth apps** -- one row per entry in
     ``integrations/oauth_service.OAUTH_PROVIDERS``, with
     auth_method=OAUTH_MANAGED. Configured-ness reflects whether the
     ``client_id`` setting is non-empty (NEVER reads client_secret).
  6. **Skill packs** -- one row per V1 ``PLUGIN_CATALOG`` plugin that
     has skills, marked ``kind=skill_pack``. These are documentation /
     instruction bundles, NOT callable connectors -- the
     ``SkillPackProbe`` enforces that contract.

Deliberate non-goals:
  * NEVER reads or copies secret values (client_secret, API keys, env
    var values from MCP configs). Only reads existence.
  * NEVER auto-installs anything; only writes V2 rows so the operator
    sees what's discoverable.
  * NEVER mutates the source files (CLI configs, plugin_catalog.py,
    oauth catalog).
  * Does NOT promise callable=true. The truth ladder still requires a
    real probe to flip callable. Importing only sets
    detected/configured/imported.

Usage:
    svc = ConnectionDiscoveryService(db, tenant_id=tenant.id)
    report = await svc.run_discovery()
    await db.commit()
    # report.created / report.skipped_existing / report.failed
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.vault_boot import load_kek_from_env
from app.models.connection_v2 import (
    AuthMethod,
    ConnectionKind,
    TrustTier,
)
from app.services.connection_v2.registry import (
    ConnectionRegistryV2,
    ImportResult,
)

if TYPE_CHECKING:
    from app.services.mcp_sync.detector import DetectedMCP

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────
# Report dataclasses
# ──────────────────────────────────────────────────────────────────


@dataclass
class SourceReport:
    """One source's import outcome."""

    source: str
    created: list[str] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    skipped_unconfigured: list[str] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "created": list(self.created),
            "skipped_existing": list(self.skipped_existing),
            "skipped_unconfigured": list(self.skipped_unconfigured),
            "failed": list(self.failed),
            "total_created": len(self.created),
            "total_skipped_existing": len(self.skipped_existing),
            "total_skipped_unconfigured": len(self.skipped_unconfigured),
            "total_failed": len(self.failed),
        }


@dataclass
class DiscoveryReport:
    """Aggregate of all seeder runs for one tenant."""

    tenant_id: str
    sources: list[SourceReport] = field(default_factory=list)

    @property
    def total_created(self) -> int:
        return sum(len(s.created) for s in self.sources)

    @property
    def total_skipped_existing(self) -> int:
        return sum(len(s.skipped_existing) for s in self.sources)

    @property
    def total_skipped_unconfigured(self) -> int:
        return sum(len(s.skipped_unconfigured) for s in self.sources)

    @property
    def total_failed(self) -> int:
        return sum(len(s.failed) for s in self.sources)

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "sources": [s.to_dict() for s in self.sources],
            "total_created": self.total_created,
            "total_skipped_existing": self.total_skipped_existing,
            "total_skipped_unconfigured": self.total_skipped_unconfigured,
            "total_failed": self.total_failed,
        }


# ──────────────────────────────────────────────────────────────────
# Slug helpers (deterministic so re-runs are idempotent)
# ──────────────────────────────────────────────────────────────────


def _safe_slug(raw: str) -> str:
    """Lowercase + collapse whitespace + restrict to a stable charset.

    The ``ConnectionV2.slug`` column is 128 chars; we cap at 96 to
    leave headroom for source-prefix-style discriminators.
    """
    cleaned = raw.strip().lower().replace(" ", "-")
    out_chars: list[str] = []
    for ch in cleaned:
        if ch.isalnum() or ch in {"-", "_", "."}:
            out_chars.append(ch)
        else:
            out_chars.append("-")
    slug = "".join(out_chars).strip("-") or "unnamed"
    return slug[:96]


def mcp_slug(detected_name: str) -> str:
    """Slug for an MCP server row. Stable across detector runs."""
    return _safe_slug(f"mcp-{detected_name}")


def cli_runtime_slug(runtime_id: str) -> str:
    return _safe_slug(f"cli-{runtime_id}")


def local_model_slug(provider_id: str) -> str:
    return _safe_slug(f"local-{provider_id}")


def oauth_app_slug(provider_id: str) -> str:
    return _safe_slug(f"oauth-{provider_id}")


def skill_pack_slug(plugin_id: str) -> str:
    return _safe_slug(f"skill-{plugin_id}")


# ──────────────────────────────────────────────────────────────────
# Discovery service
# ──────────────────────────────────────────────────────────────────


class ConnectionDiscoveryService:
    """Walk every real source and materialize V2 rows for one tenant.

    Caller manages the surrounding transaction (commit / rollback).
    Each importer flushes via ``ConnectionRegistryV2.import_connection``
    but does NOT commit on its own.
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.settings = settings or get_settings()
        kek = load_kek_from_env(is_production=self.settings.is_production)
        self.registry = ConnectionRegistryV2(db, kek_seed=kek)

    async def run_discovery(self) -> DiscoveryReport:
        """Run every importer in sequence and return an aggregate report."""
        report = DiscoveryReport(tenant_id=str(self.tenant_id))
        report.sources.append(await self._import_mcp_servers())
        report.sources.append(await self._import_cli_runtimes())
        report.sources.append(await self._import_local_models())
        report.sources.append(await self._import_providers())
        report.sources.append(await self._import_oauth_apps())
        report.sources.append(await self._import_skill_packs())
        logger.info(
            "connection_discovery.complete",
            tenant_id=str(self.tenant_id),
            created=report.total_created,
            skipped_existing=report.total_skipped_existing,
            skipped_unconfigured=report.total_skipped_unconfigured,
            failed=report.total_failed,
        )
        return report

    # ── MCP servers (Claude Code / Codex / Gemini CLI configs) ──────

    async def _import_mcp_servers(self) -> SourceReport:
        from app.services.mcp_sync.detector import CLIMCPDetector

        out = SourceReport(source="mcp_servers")
        try:
            detector = CLIMCPDetector()
            mcps = await detector.discover_all()
            mcps = CLIMCPDetector.deduplicate(mcps)
        except Exception as exc:  # noqa: BLE001 - importer must never crash discovery
            out.failed.append({
                "slug": "discover_all",
                "error_type": type(exc).__name__,
                "error": str(exc)[:200],
            })
            logger.warning(
                "connection_discovery.mcp_detect_failed",
                tenant_id=str(self.tenant_id),
                error_type=type(exc).__name__,
            )
            return out

        for m in mcps:
            slug = mcp_slug(m.name)
            display_name = self._humanize_mcp_name(m.name)
            try:
                # Note: do NOT persist env values -- they may contain
                # secrets. Only persist transport metadata + the count
                # of env keys so the operator sees "this MCP needs
                # 3 env vars" without leaking their values.
                config = {
                    "kind": "mcp_stdio" if m.command else "mcp_http",
                    "command": m.command,
                    "args": list(m.args),
                    "env_var_names": sorted(m.env.keys()),
                    "env_var_count": len(m.env),
                    "url": m.url,
                    "_source_cli": m.source_cli,
                    "_source_path": m.config_path,
                    "_source_notes": m.notes,
                    "_seeded_by": "connection_discovery",
                }
                # Strip empty / falsy fields so the discriminated-union
                # validator picks a clean shape.
                config = {k: v for k, v in config.items() if v not in (None, "")}
                result = await self.registry.import_connection(
                    tenant_id=self.tenant_id,
                    kind=ConnectionKind.MCP_SERVER,
                    slug=slug,
                    display_name=display_name,
                    auth_method=AuthMethod.NONE,
                    config=config,
                )
                self._record(out, slug, result)
            except Exception as exc:  # noqa: BLE001
                out.failed.append({
                    "slug": slug,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:200],
                })
                logger.warning(
                    "connection_discovery.mcp_import_failed",
                    tenant_id=str(self.tenant_id),
                    slug=slug,
                    error_type=type(exc).__name__,
                )
        return out

    @staticmethod
    def _humanize_mcp_name(raw: str) -> str:
        """``chrome-devtools`` -> ``Chrome Devtools`` (display only)."""
        cleaned = raw.replace("-", " ").replace("_", " ").strip()
        if not cleaned:
            return raw or "MCP Server"
        return cleaned.title()

    # ── CLI runtimes (binary-on-PATH check) ─────────────────────────

    async def _import_cli_runtimes(self) -> SourceReport:
        from app.services.providers.claude_cli import ALL_CLI_SPECS

        out = SourceReport(source="cli_runtimes")
        for spec in ALL_CLI_SPECS:
            slug = cli_runtime_slug(spec.runtime_id)
            try:
                binary_path = shutil.which(spec.binary_name) or ""
                config = {
                    "kind": "cli_runtime",
                    "binary": binary_path,
                    "extra_args": [],
                    "_runtime_id": spec.runtime_id,
                    "_provider_enum": spec.provider.value,
                    "_model_id": spec.model_id,
                    "_seeded_by": "connection_discovery",
                }
                if not binary_path:
                    out.skipped_unconfigured.append(slug)
                    continue
                result = await self.registry.import_connection(
                    tenant_id=self.tenant_id,
                    kind=ConnectionKind.CLI_RUNTIME,
                    slug=slug,
                    display_name=spec.display_name,
                    auth_method=AuthMethod.SUBSCRIPTION,
                    config=config,
                )
                self._record(out, slug, result)
            except Exception as exc:  # noqa: BLE001
                out.failed.append({
                    "slug": slug,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:200],
                })
                logger.warning(
                    "connection_discovery.cli_import_failed",
                    tenant_id=str(self.tenant_id),
                    slug=slug,
                    error_type=type(exc).__name__,
                )
        return out

    # ── Local model endpoints (Ollama, vLLM) ────────────────────────

    async def _import_local_models(self) -> SourceReport:
        out = SourceReport(source="local_models")

        candidates = (
            ("ollama", "Ollama", self.settings.ollama_base_url,
             self.settings.ollama_default_model,
             bool(getattr(self.settings, "ollama_enabled", False))),
            ("vllm", "vLLM (local llama-server / vLLM)",
             self.settings.vllm_base_url,
             self.settings.vllm_default_model, True),
        )

        for provider_id, display_name, base_url, default_model, enabled in candidates:
            slug = local_model_slug(provider_id)
            if not enabled or not (base_url and base_url.strip()):
                out.skipped_unconfigured.append(slug)
                continue
            try:
                config = {
                    "kind": "local_model",
                    "base_url": base_url.strip(),
                    "default_model": default_model or None,
                    "_provider_id": provider_id,
                    "_seeded_by": "connection_discovery",
                }
                # Strip None / "" so the discriminated-union validator
                # picks a clean shape.
                config = {k: v for k, v in config.items() if v not in (None, "")}
                result = await self.registry.import_connection(
                    tenant_id=self.tenant_id,
                    kind=ConnectionKind.LOCAL_MODEL,
                    slug=slug,
                    display_name=display_name,
                    auth_method=AuthMethod.NONE,
                    config=config,
                )
                self._record(out, slug, result)
            except Exception as exc:  # noqa: BLE001
                out.failed.append({
                    "slug": slug,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:200],
                })
                logger.warning(
                    "connection_discovery.local_model_import_failed",
                    tenant_id=str(self.tenant_id),
                    slug=slug,
                    error_type=type(exc).__name__,
                )
        return out

    # ── API providers (delegates to provider_seeder) ────────────────

    async def _import_providers(self) -> SourceReport:
        from app.services.connection_v2.provider_seeder import (
            seed_providers_for_tenant,
        )

        out = SourceReport(source="providers")
        try:
            seed_report = await seed_providers_for_tenant(
                self.db,
                tenant_id=self.tenant_id,
                settings=self.settings,
            )
            out.created.extend(seed_report.created)
            out.skipped_existing.extend(seed_report.skipped_existing)
            out.skipped_unconfigured.extend(seed_report.skipped_unconfigured)
        except Exception as exc:  # noqa: BLE001
            out.failed.append({
                "slug": "seed_providers_for_tenant",
                "error_type": type(exc).__name__,
                "error": str(exc)[:200],
            })
            logger.warning(
                "connection_discovery.provider_import_failed",
                tenant_id=str(self.tenant_id),
                error_type=type(exc).__name__,
            )
        return out

    # ── OAuth apps (config existence, NEVER reads client_secret) ────

    async def _import_oauth_apps(self) -> SourceReport:
        from app.services.integrations.oauth_service import OAUTH_PROVIDERS

        out = SourceReport(source="oauth_apps")
        for provider_id, cfg in OAUTH_PROVIDERS.items():
            slug = oauth_app_slug(provider_id)
            try:
                # Read ONLY existence-check fields, never the secret.
                client_id_value = (
                    getattr(self.settings, cfg.client_id_setting, "") or ""
                ).strip()
                client_secret_set = bool(
                    (getattr(self.settings, cfg.client_secret_setting, "") or "").strip()
                )
                if not client_id_value:
                    # Still surface as discoverable but unconfigured so
                    # the operator can see "Daena knows about this OAuth
                    # app, just no creds yet". The row gets imported
                    # only after configured=True (we record both states
                    # via the truth ladder).
                    out.skipped_unconfigured.append(slug)
                    continue
                config = {
                    "kind": "oauth_app",
                    "client_id": client_id_value,
                    "redirect_uri": "",  # Not in catalog; populated by oauth_service at runtime
                    "scopes": list(cfg.scopes),
                    "_provider_id": provider_id,
                    "_auth_url": cfg.auth_url,
                    "_token_url": cfg.token_url,
                    "_client_secret_set": client_secret_set,
                    "_seeded_by": "connection_discovery",
                }
                result = await self.registry.import_connection(
                    tenant_id=self.tenant_id,
                    kind=ConnectionKind.OAUTH_APP,
                    slug=slug,
                    display_name=self._humanize_mcp_name(provider_id),
                    auth_method=AuthMethod.OAUTH_MANAGED,
                    config=config,
                )
                self._record(out, slug, result)
            except Exception as exc:  # noqa: BLE001
                out.failed.append({
                    "slug": slug,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:200],
                })
                logger.warning(
                    "connection_discovery.oauth_import_failed",
                    tenant_id=str(self.tenant_id),
                    slug=slug,
                    error_type=type(exc).__name__,
                )
        return out

    # ── Skill packs (V1 PLUGIN_CATALOG -> kind=skill_pack rows) ─────

    async def _import_skill_packs(self) -> SourceReport:
        from app.services.plugin_catalog import PLUGIN_CATALOG

        out = SourceReport(source="skill_packs")
        for plugin_id, plugin in PLUGIN_CATALOG.items():
            # Only V1 plugins WITHOUT a callable mcp_package count as
            # skill packs. Plugins that ship an mcp_package will be
            # picked up by the MCP detector once installed; importing
            # them here as skill_pack would double-count.
            if plugin.mcp_package:
                continue
            slug = skill_pack_slug(plugin_id)
            try:
                config = {
                    "kind": "skill_pack",
                    "pack_path": None,
                    "source_plugin_id": plugin_id,
                    "skill_count": len(plugin.skills),
                    "_category": plugin.category,
                    "_subtitle": plugin.subtitle,
                    "_skill_ids": [s.id for s in plugin.skills],
                    "_seeded_by": "connection_discovery",
                }
                result = await self.registry.import_connection(
                    tenant_id=self.tenant_id,
                    kind=ConnectionKind.SKILL_PACK,
                    slug=slug,
                    display_name=plugin.name,
                    auth_method=AuthMethod.NONE,
                    config=config,
                )
                self._record(out, slug, result)
            except Exception as exc:  # noqa: BLE001
                out.failed.append({
                    "slug": slug,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:200],
                })
                logger.warning(
                    "connection_discovery.skill_pack_import_failed",
                    tenant_id=str(self.tenant_id),
                    slug=slug,
                    error_type=type(exc).__name__,
                )
        return out

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _record(out: SourceReport, slug: str, result: ImportResult) -> None:
        if result.created:
            out.created.append(slug)
        else:
            out.skipped_existing.append(slug)


__all__ = [
    "ConnectionDiscoveryService",
    "DiscoveryReport",
    "SourceReport",
    "cli_runtime_slug",
    "local_model_slug",
    "mcp_slug",
    "oauth_app_slug",
    "skill_pack_slug",
]
