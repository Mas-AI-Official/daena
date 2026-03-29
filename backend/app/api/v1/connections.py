"""CMP (Connector Management Protocol) endpoints.

Manages external integrations as governed connectors with
per-tool permission controls. Three resource levels:
- Connectors: global catalog of available integrations
- Instances: per-user connections with credentials
- Permissions: per-tool access control on each instance
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.database import get_db
from app.schemas.connections import (
    ConnectRequest,
    CreateConnectorRequest,
    SetPermissionRequest,
)
from app.services.connection_service import ConnectionService

router = APIRouter()


async def get_connection_service(
    db: AsyncSession = Depends(get_db),
) -> ConnectionService:
    """Factory dependency for ConnectionService."""
    return ConnectionService(db)


# ── Connector Catalog (global) ──


@router.post("/connectors", status_code=201)
async def create_connector(
    body: CreateConnectorRequest,
    user: CurrentUser = Depends(require_role("ADMIN")),
    service: ConnectionService = Depends(get_connection_service),
) -> dict:
    """Register a new connector type in the global catalog.

    Requires ADMIN role. Connectors define integration templates;
    users create instances to actually connect.
    """
    connector = await service.create_connector(
        name=body.name,
        description=body.description,
        auth_type=body.auth_type,
        config_schema=body.config_schema,
        tools=body.tools,
        icon_url=body.icon_url,
        category=body.category,
    )
    return {"success": True, "data": connector}


@router.get("/connectors")
async def list_connectors(
    user: CurrentUser = Depends(get_current_user),
    service: ConnectionService = Depends(get_connection_service),
    category: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    """List available connector types from the global catalog."""
    result = await service.list_connectors(
        category=category,
        page=page,
        page_size=page_size,
    )
    return {"success": True, "data": result.data, "pagination": result.pagination}


@router.get("/connectors/{connector_id}")
async def get_connector(
    connector_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ConnectionService = Depends(get_connection_service),
) -> dict:
    """Get a connector template by ID."""
    connector = await service.get_connector(connector_id)
    return {"success": True, "data": service._connector_to_dict(connector)}


# ── Connector Instances (per-user) ──


@router.post("/instances", status_code=201)
async def connect(
    body: ConnectRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ConnectionService = Depends(get_connection_service),
) -> dict:
    """Create a connection to a connector for the current user.

    Each user can have at most one instance per connector
    within a tenant.
    """
    instance = await service.connect(
        connector_id=body.connector_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
        credentials=body.credentials,
    )
    return {"success": True, "data": instance}


@router.get("/instances")
async def list_instances(
    user: CurrentUser = Depends(get_current_user),
    service: ConnectionService = Depends(get_connection_service),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """List the current user's connector instances."""
    result = await service.list_instances(
        user_id=user.id,
        tenant_id=user.tenant_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return {"success": True, "data": result.data, "pagination": result.pagination}


@router.get("/instances/{instance_id}")
async def get_instance(
    instance_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ConnectionService = Depends(get_connection_service),
) -> dict:
    """Get a specific connector instance."""
    instance = await service.get_instance(instance_id, user.tenant_id)
    return {"success": True, "data": instance}


@router.post("/instances/{instance_id}/disconnect")
async def disconnect(
    instance_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ConnectionService = Depends(get_connection_service),
) -> dict:
    """Disconnect a connector instance.

    Soft-disconnect: sets status to DISCONNECTED and clears
    stored credentials for security.
    """
    instance = await service.disconnect(instance_id, user.tenant_id)
    return {"success": True, "data": instance}


# ── Per-tool Permissions ──


@router.post("/instances/{instance_id}/permissions")
async def set_permission(
    instance_id: UUID,
    body: SetPermissionRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ConnectionService = Depends(get_connection_service),
) -> dict:
    """Set permission level for a specific tool in a connector.

    Upsert pattern: creates or updates the permission record.
    Levels: ALWAYS_ALLOW, ASK_EACH_TIME, BLOCK.
    """
    permission = await service.set_tool_permission(
        instance_id=instance_id,
        tenant_id=user.tenant_id,
        tool_name=body.tool_name,
        permission_level=body.permission_level,
    )
    return {"success": True, "data": permission}


@router.get("/instances/{instance_id}/permissions")
async def list_permissions(
    instance_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ConnectionService = Depends(get_connection_service),
) -> dict:
    """List all tool permissions for a connector instance."""
    permissions = await service.list_permissions(instance_id, user.tenant_id)
    return {"success": True, "data": permissions}


# ── Extensions (MCP servers + Claude Code plugins) ──


@router.get("/extensions")
async def list_extensions(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """List installed extensions from Claude Code plugins and MCP servers.

    Reads from:
      - ~/.claude/plugins/installed_plugins.json
      - ~/AppData/Roaming/Claude/claude_desktop_config.json
    """
    from app.services.extension_scanner import scan_extensions

    extensions = scan_extensions()
    # Only show MCP servers (user-facing extensions), not internal Claude Code plugins
    mcp_only = [e for e in extensions if e.source == "mcp-server"]
    return {
        "success": True,
        "data": [e.to_dict() for e in mcp_only],
    }
