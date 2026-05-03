"""CMP (Connector Management Protocol) request/response schemas.

Manages external integrations as governed connectors with
per-tool permission controls.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas._base import DaenaSchema

# ── Requests ──


class CreateConnectorRequest(BaseModel):
    """Register a new connector type in the catalog."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    auth_type: str = Field("API_KEY", pattern="^(OAUTH2|API_KEY|NONE)$")
    config_schema: dict = Field(default_factory=dict)
    tools: list[dict] = Field(
        default_factory=list,
        description="List of tool definitions this connector exposes",
    )
    icon_url: str | None = Field(None, max_length=500)
    category: str | None = Field(None, max_length=100)


class ConnectRequest(BaseModel):
    """Instantiate a connection to a connector for the current user."""

    connector_id: UUID
    credentials: dict | None = Field(
        None,
        description="Auth credentials (encrypted at rest)",
    )


class InstallConnectorRequest(BaseModel):
    """Install a connector locally without authenticating an external account."""

    connector_id: UUID


class ConnectAccountRequest(BaseModel):
    """Attach account credentials to an already-installed connector instance."""

    credentials: dict = Field(
        ...,
        min_length=1,
        description="Auth credentials to encrypt at rest",
    )


class SetPermissionRequest(BaseModel):
    """Set permission level for a specific tool in a connector instance."""

    tool_name: str = Field(..., min_length=1, max_length=200)
    permission_level: str = Field(
        "ASK_EACH_TIME",
        pattern="^(ALWAYS_ALLOW|ASK_EACH_TIME|BLOCK)$",
    )


# ── Responses ──


class ConnectorResponse(DaenaSchema):
    """Connector catalog entry (template)."""

    id: UUID
    name: str
    description: str | None = None
    auth_type: str
    config_schema: dict
    tools: list[dict]
    icon_url: str | None = None
    category: str | None = None
    created_at: datetime | None = None


class ConnectorInstanceResponse(DaenaSchema):
    """A user's active connection to a connector."""

    id: UUID
    connector_id: UUID
    user_id: UUID
    tenant_id: UUID
    status: str
    last_used: datetime | None = None
    connector_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Session 11: the email / handle of the external account the user
    # authenticated. Populated after Google consent picks e.g.
    # masoud.masoori@mas-ai.co. Never includes tokens. Empty string
    # when we could not fetch userinfo (OAuth succeeded but /userinfo
    # returned non-200).
    account_identity: str | None = None


class ConnectorPermissionResponse(DaenaSchema):
    """Per-tool permission within a connector instance."""

    id: UUID
    instance_id: UUID
    tool_name: str
    permission_level: str
