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
    """Skill pack: no install path, no callable target."""
    kind: Literal["plugin"] = "plugin"
    skill_pack_path: str | None = None


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
