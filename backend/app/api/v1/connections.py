"""CMP (Connector Management Protocol) endpoints.

Manages external integrations as governed connectors with
per-tool permission controls. Three resource levels:
- Connectors: global catalog of available integrations
- Instances: per-user connections with credentials
- Permissions: per-tool access control on each instance
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.database import get_db
from app.schemas.connections import (
    ConnectRequest,
    CreateConnectorRequest,
    SetPermissionRequest,
)
from app.services.connection_service import ConnectionService
from app.services.plugin_catalog import (
    PLUGIN_CATALOG,
    get_plugin,
    list_plugins,
    list_plugins_by_category,
    plugins_with_mcp,
)

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


@router.get("/mcp-registry")
async def get_mcp_registry(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return the live stdio-bootstrap registry.

    Unlike ``/extensions`` (which reads the raw
    ``claude_desktop_config.json`` on every call), this returns the
    adapter-ready entries held in process memory -- what Daena can
    actually ``plugin.call_tool`` right now without a restart.

    Use this endpoint from the Plugins tab to show a live-spawnable
    badge next to installed MCPs so the user can tell the difference
    between "config written but not loaded yet" and "loaded and
    callable".
    """
    from app.services.mcp_bootstrap import list_installed_mcps

    entries = [
        {
            "server_key": m.server_key,
            "display_name": m.display_name,
            "description": m.description,
            "command": m.command,
            "args": m.args,
            "package": m.package,
        }
        for m in list_installed_mcps()
    ]
    return {
        "success": True,
        "data": {"count": len(entries), "entries": entries},
    }


@router.post("/mcp-registry/refresh")
async def refresh_mcp_registry(
    _user: CurrentUser = Depends(require_role("MANAGER")),
) -> dict:
    """Force a manual re-scan of ``claude_desktop_config.json``.

    Primarily a debug/ops affordance -- install/uninstall flows
    already trigger refresh automatically. Gated at MANAGER so
    casual users can't thrash the registry. Returns the new entry
    count so the UI can show "Refreshed: 3 plugins live" in a
    toast.
    """
    from app.services.mcp_bootstrap import bootstrap_installed_mcps

    registry = await bootstrap_installed_mcps()
    return {"success": True, "data": {"count": len(registry)}}


@router.get("/plugin-catalog")
async def get_plugin_catalog(
    _user: CurrentUser = Depends(get_current_user),
    grouped: bool = Query(False, description="Group response by category"),
) -> dict:
    """Return the single-source-of-truth plugin catalog.

    The frontend Plugins tab can read from here instead of embedding
    a hardcoded catalog. Ships every plugin's skills + descriptions
    so the two halves cannot drift.
    """
    if grouped:
        return {"success": True, "data": list_plugins_by_category()}
    return {"success": True, "data": list_plugins()}


@router.get("/plugin-catalog/{plugin_id}")
async def get_plugin_definition(
    plugin_id: str,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return a single plugin's full definition."""
    plugin = get_plugin(plugin_id)
    if plugin is None:
        raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")
    return {"success": True, "data": plugin.to_dict()}


@router.get("/extensions")
async def list_extensions(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List installed extensions from Claude Code plugins and MCP servers.

    Reads from:
      - ~/.claude/plugins/installed_plugins.json
      - ~/AppData/Roaming/Claude/claude_desktop_config.json

    Session 11: merges per-user permission overrides from
    ``User.settings['extension_permissions']`` so the UI hydrates with
    whatever the operator set last time instead of the hardcoded
    ASK_EACH_TIME default.
    """
    from sqlalchemy import select

    from app.models.identity import User
    from app.services.extension_scanner import scan_extensions

    extensions = scan_extensions()
    mcp_only = [e for e in extensions if e.source == "mcp-server"]

    # Pull this user's saved per-extension permissions. Structure:
    #   settings.extension_permissions[ext_id] = {
    #       "default": "ALLOW" | "ASK_EACH_TIME" | "BLOCK",
    #       "tools": { "<tool_name>": "ALLOW" | ... }
    #   }
    saved_perms: dict = {}
    try:
        stmt = select(User).where(User.id == user.id)
        result = await db.execute(stmt)
        db_user = result.scalar_one_or_none()
        if db_user and db_user.settings:
            saved_perms = db_user.settings.get("extension_permissions", {}) or {}
    except Exception:
        pass  # Fallback to empty overrides -- UI will show defaults.

    payload = []
    for ext in mcp_only:
        ext_dict = ext.to_dict()
        slug = ext_dict["name"].lower().replace(" ", "-").replace("_", "-")
        by_slug = saved_perms.get(slug) or saved_perms.get(ext_dict["id"]) or {}
        if by_slug.get("default"):
            ext_dict["permission"] = by_slug["default"]
        if by_slug.get("tools"):
            ext_dict["tool_permissions"] = by_slug["tools"]
        payload.append(ext_dict)

    return {"success": True, "data": payload}


class ExtensionPermissionRequest(BaseModel):
    """Body for saving per-extension permission overrides."""

    default: str | None = None      # ALLOW | ASK_EACH_TIME | BLOCK
    tools: dict[str, str] | None = None   # per-tool overrides


@router.post("/extensions/{extension_id}/permissions")
async def save_extension_permissions(
    extension_id: str,
    body: ExtensionPermissionRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Persist per-extension permission state into User.settings JSONB.

    Session 11: fixes the "permission reverts after logout" bug. The
    frontend previously kept permission in local React state only and
    never called the backend. This endpoint is called whenever the
    user changes the Default Permission pill or a per-tool pill.

    ``extension_id`` is the slug the frontend uses (e.g. ``filesystem``,
    ``figma``). Stored as-is so the GET path can look it up either by
    slug or raw id.
    """
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    from app.models.identity import User

    allowed = {"ALLOW", "ASK_EACH_TIME", "BLOCK"}
    if body.default and body.default not in allowed:
        raise HTTPException(status_code=422, detail=f"default must be one of {sorted(allowed)}")
    if body.tools:
        for tool_name, perm in body.tools.items():
            if perm not in allowed:
                raise HTTPException(
                    status_code=422,
                    detail=f"tool permission for {tool_name} must be one of {sorted(allowed)}",
                )

    stmt = select(User).where(User.id == user.id)
    result = await db.execute(stmt)
    db_user = result.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(status_code=404, detail="user not found")

    settings = dict(db_user.settings or {})
    ext_perms = dict(settings.get("extension_permissions", {}) or {})
    entry = dict(ext_perms.get(extension_id, {}) or {})

    if body.default is not None:
        entry["default"] = body.default
    if body.tools is not None:
        # Merge, don't replace -- lets the UI send single-tool updates
        tools = dict(entry.get("tools", {}) or {})
        tools.update(body.tools)
        entry["tools"] = tools

    ext_perms[extension_id] = entry
    settings["extension_permissions"] = ext_perms
    db_user.settings = settings
    flag_modified(db_user, "settings")
    await db.flush()

    return {
        "success": True,
        "data": {"extension_id": extension_id, "saved": entry},
    }


class ExtensionInstallRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    # Optional explicit command + args. When present, written verbatim
    # to claude_desktop_config.json so npm packages like
    # ``@modelcontextprotocol/server-gdrive`` install correctly.
    # If the caller omits these we fall back to ``npx -y <id>`` for
    # backward compatibility with older clients.
    command: str | None = None
    args: list[str] | None = None


@router.post("/extensions/install", status_code=201)
async def install_extension(
    body: ExtensionInstallRequest,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Install an MCP server extension from the catalog.

    Writes the server config to Claude Desktop config file so it
    appears in the extensions list on next scan.
    """
    import json
    from pathlib import Path

    config_path = Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing config or start fresh
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        config = {}

    mcp_servers = config.setdefault("mcpServers", {})

    # Prefer the explicit command + args supplied by the caller so the
    # real npm package name is used. If a client omits them we fall
    # back to ``npx -y <body.id>`` -- that keeps older install dialogs
    # working, but the new dialogs now forward mcp.command / mcp.args
    # from the connector catalog so packages like
    # ``@modelcontextprotocol/server-gdrive`` land in the config
    # correctly.
    server_key = body.id.replace("/", "-").replace("@", "").lower()
    install_cmd = body.command or "npx"
    install_args = body.args if body.args is not None else ["-y", body.id]
    mcp_servers[server_key] = {
        "command": install_cmd,
        "args": list(install_args),
        "metadata": {"name": body.name, "description": body.description},
    }

    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    # Re-scan the bootstrap registry so the new MCP is immediately
    # spawnable from chat (plugin.call_tool) without a server
    # restart. Previously the UI install path wrote the config but
    # left the registry stale -- the MCP only went live on next
    # startup. Now the install + chat awareness are genuinely
    # end-to-end on the same request.
    try:
        from app.services.mcp_bootstrap import bootstrap_installed_mcps

        registry = await bootstrap_installed_mcps()
        newly_live = server_key in registry
    except Exception:
        newly_live = False

    return {
        "success": True,
        "data": {
            "id": body.id,
            "name": body.name,
            "status": "installed",
            "server_key": server_key,
            "registry_refreshed": newly_live,
        },
    }


class ExtensionUninstallRequest(BaseModel):
    """Body for the uninstall endpoint. Accepts either the user-facing
    plugin id (``google-drive``) or the canonical ``mcp-<id>`` server
    key the installer wrote to ``claude_desktop_config.json``."""

    id: str


@router.post("/extensions/uninstall", status_code=200)
async def uninstall_extension(
    body: ExtensionUninstallRequest,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Remove an MCP entry from ``claude_desktop_config.json``.

    Mirrors ``install`` end-to-end: writes the config, re-bootstraps
    the registry so the removal is live immediately. Idempotent --
    removing an entry that's not there returns ``removed=False``
    but still 200.
    """
    import json
    from pathlib import Path

    config_path = Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    server_key = body.id if body.id.startswith("mcp-") else f"mcp-{body.id}"

    removed = False
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        mcp_servers = config.get("mcpServers") or {}
        if server_key in mcp_servers:
            del mcp_servers[server_key]
            config["mcpServers"] = mcp_servers
            config_path.write_text(
                json.dumps(config, indent=2), encoding="utf-8"
            )
            removed = True

    try:
        from app.services.mcp_bootstrap import bootstrap_installed_mcps

        await bootstrap_installed_mcps()
    except Exception:
        pass

    return {
        "success": True,
        "data": {"server_key": server_key, "removed": removed},
    }
