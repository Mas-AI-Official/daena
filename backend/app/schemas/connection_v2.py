"""Pydantic schemas for ConnectionV2 (Phase 4b PR 1).

Per ADR-002 D-008: per-kind discriminated-union validation on
``connection_v2.config``. Phase 4b PR 1 ships the discriminator + a
permissive default for unknown kinds (so we can refine per-kind shape
in subsequent PRs without rejecting in-progress data).

Wire shape (``ConnectionV2Out``) keys per-dim failure reasons by dim
so a single failure never hides another (D-001).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.connection_v2 import AuthMethod, ConnectionKind, TrustTier


# ──────────────────────────────────────────────────────────────────
# Per-kind config discriminated unions (ADR-002 D-008)
# ──────────────────────────────────────────────────────────────────


class CliRuntimeConfig(BaseModel):
    """CLI runtime: claude_code, codex, gemini_cli, grok_cli, etc."""
    kind: Literal["cli_runtime"] = "cli_runtime"
    binary: str = Field(..., description="Resolved path to the CLI binary")
    extra_args: list[str] = Field(default_factory=list)


class McpStdioConfig(BaseModel):
    """MCP server over stdio."""
    kind: Literal["mcp_stdio"] = "mcp_stdio"
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class McpHttpConfig(BaseModel):
    """MCP server over HTTP/SSE."""
    kind: Literal["mcp_http"] = "mcp_http"
    url: str
    transport: Literal["http", "sse"] = "http"


class ProviderConfig(BaseModel):
    """LLM provider (Anthropic / OpenAI / Groq / etc.)."""
    kind: Literal["provider"] = "provider"
    base_url: str | None = None
    default_model: str | None = None


class OAuthAppConfig(BaseModel):
    """OAuth app: client_id is plaintext config; client_secret in vault."""
    kind: Literal["oauth_app"] = "oauth_app"
    client_id: str
    redirect_uri: str
    scopes: list[str] = Field(default_factory=list)


class LocalModelConfig(BaseModel):
    """Local LLM endpoint (Ollama / vLLM / llama-server)."""
    kind: Literal["local_model"] = "local_model"
    base_url: str
    default_model: str | None = None


class PluginConfig(BaseModel):
    """Plugin: a callable connector (probe runs handshake or HTTP check)."""
    kind: Literal["plugin"] = "plugin"
    skill_pack_path: str | None = None


class SkillPackConfig(BaseModel):
    """Skill pack: capability/instruction bundle, never callable.

    PR-CONN-V2-SEED-IMPORT (2026-05-02): plugin entries that ship only
    instructions / docs / prompt templates land here so the V2 surface
    can mark them clearly as "not a callable connector". Probe always
    returns failure_dim=callable for this kind.
    """
    kind: Literal["skill_pack"] = "skill_pack"
    pack_path: str | None = None
    source_plugin_id: str | None = None
    skill_count: int = 0


# Discriminated union -- the validator picks shape by ``kind`` field.
# Pydantic v2 syntax. Phase 4b PR 1 includes a permissive default
# (PluginConfig) for unknown kinds; per-kind enforcement tightens in
# Phase 4b PR 2 when service writers know exactly which shape to emit.
ConnectionConfigUnion = Annotated[
    Union[
        CliRuntimeConfig,
        McpStdioConfig,
        McpHttpConfig,
        ProviderConfig,
        OAuthAppConfig,
        LocalModelConfig,
        PluginConfig,
        SkillPackConfig,
    ],
    Field(discriminator="kind"),
]


# ──────────────────────────────────────────────────────────────────
# Truth-dim wire shape (per-dim failure storage, ADR-002 D-001)
# ──────────────────────────────────────────────────────────────────


class TruthDimOut(BaseModel):
    """One truth dimension's wire view."""
    value: bool
    at: datetime | None = None
    failure_at: datetime | None = None
    failure_reason: str | None = None


class ConnectionTruthOut(BaseModel):
    """All 6 dims keyed by name. Per ADR-002 D-001: failure on one
    dim never overwrites another's reason."""
    detected: TruthDimOut
    configured: TruthDimOut
    imported: TruthDimOut
    reachable: TruthDimOut
    authenticated: TruthDimOut
    callable: TruthDimOut


# ──────────────────────────────────────────────────────────────────
# REST request/response models
# ──────────────────────────────────────────────────────────────────


class ConnectionV2Out(BaseModel):
    """Read-only view of a ConnectionV2 row + derived label."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    kind: ConnectionKind
    slug: str
    display_name: str
    auth_method: AuthMethod
    trust_tier: TrustTier
    config: dict
    truth: ConnectionTruthOut
    label: str  # one of state_machine.LABELS
    capabilities_count: int = 0
    healthy_call_ratio: float = 1.0
    archived: bool
    disabled: bool
    governance_tier: int


class ImportConnectionRequest(BaseModel):
    """POST /api/v1/connections/v2 body. Idempotent on canonical_key."""
    kind: ConnectionKind
    slug: str
    display_name: str
    auth_method: AuthMethod
    trust_tier: TrustTier = TrustTier.OFFICIAL
    config: dict = Field(default_factory=dict)
    secret_value: str | None = Field(
        default=None,
        description=(
            "Optional plaintext secret for API_TOKEN auth_method. "
            "Routed to vault_v2 envelope storage. NEVER echoed back. "
            "Phase 4b PR 1 supports api_token writes only; OAuth flows "
            "are wired separately."
        ),
    )


class ProbeRequest(BaseModel):
    """POST /api/v1/connections/v2/{id}/probe body. Empty (route-only)."""


class ProbeOutcome(BaseModel):
    """Sanitized probe result. Never includes secrets."""
    success: bool
    label_after: str
    callable_at: datetime | None = None
    failure_dim: str | None = None
    failure_reason: str | None = None


# ──────────────────────────────────────────────────────────────────
# MCP install (PR-CONN-MCP-INSTALL-INTO-CLI, 2026-05-02)
# ──────────────────────────────────────────────────────────────────


class McpInstallTarget(BaseModel):
    """POST body for /marketplace/install-plan/{entry_id}/preview|apply.

    target = which CLI gets the MCP entry written into its config.
    allow_create = create the config file if no candidate exists yet.
                   Default False (safer: refuse the write and tell the
                   operator their CLI's config file is missing).
    probe_after_apply = run McpServerProbe against the imported V2 row
                        immediately after a successful apply, so the UI
                        can show "Connected" without a second round-trip.
    """
    target: Literal["claude_desktop", "claude_code", "codex", "gemini_cli"]
    allow_create: bool = False
    probe_after_apply: bool = False


# ──────────────────────────────────────────────────────────────────
# OAuth marketplace (PR-CONN-OAUTH-CONNECT, 2026-05-02)
# ──────────────────────────────────────────────────────────────────


class OAuthStartRequest(BaseModel):
    """POST body for /marketplace/oauth/{entry_id}/start.

    Empty for now -- redirect URI is computed server-side from the
    request base URL so a misconfigured client cannot trick Daena into
    sending consent to a third-party callback.
    """


class OAuthStartResponse(BaseModel):
    """Sanitized OAuth start payload. NEVER includes secrets."""
    success: bool
    provider: str | None = None
    authorization_url: str | None = None
    redirect_uri: str | None = None
    scopes: list[str] = Field(default_factory=list)
    state_ref: str | None = None
    failure_reason: str | None = None


# ──────────────────────────────────────────────────────────────────
# MCP backup restore (PR-CONN-MCP-INSTALL-RESTORE, 2026-05-02)
# ──────────────────────────────────────────────────────────────────


class McpBackupRestoreRequest(BaseModel):
    """POST body for /marketplace/install-backups/restore.

    target = which CLI's config to restore (claude_desktop / claude_code /
             codex / gemini_cli)
    backup_filename = basename of the backup file (NEVER a path; the
                      restore endpoint refuses anything containing /
                      or \\)
    """
    target: Literal["claude_desktop", "claude_code", "codex", "gemini_cli"]
    backup_filename: str
