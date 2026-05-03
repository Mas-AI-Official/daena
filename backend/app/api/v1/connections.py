"""CMP (Connector Management Protocol) endpoints.

Manages external integrations as governed connectors with
per-tool permission controls. Three resource levels:
- Connectors: global catalog of available integrations
- Instances: per-user connections with credentials
- Permissions: per-tool access control on each instance
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.database import get_db
from app.models.connections import Connector
from app.schemas.connections import (
    ConnectRequest,
    ConnectAccountRequest,
    CreateConnectorRequest,
    InstallConnectorRequest,
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


# ── Connector Catalog (public, cached) ──
#
# The Plugins tab in the frontend used to hardcode a ~110 entry
# CONNECTORS array. The catalog now lives in the ``connectors`` table
# (seeded from ``backend/app/config/connector_catalog.json`` at
# startup) and the frontend fetches it via this endpoint. A simple
# 5-minute in-process cache keeps the endpoint cheap on the polling
# path without sacrificing freshness when an operator hot-reloads the
# JSON file.

_CATALOG_CACHE_TTL_S = 300.0
_CATALOG_VERSION_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "connector_catalog.json"
)
_catalog_cache: dict[str, object] = {"value": None, "expires_at": 0.0}


def _read_catalog_version() -> str:
    """Read the bundled catalog file's version string.

    The DB rows themselves don't store version (it's a property of the
    catalog as a whole), so we re-read the JSON every cache miss to
    decide what to ship to the client. Failure to read just falls back
    to ``"unknown"`` -- the endpoint stays useful even if the JSON is
    deleted post-seed.
    """
    try:
        if _CATALOG_VERSION_PATH.is_file():
            payload = json.loads(_CATALOG_VERSION_PATH.read_text(encoding="utf-8"))
            return str(payload.get("version") or "unknown")
    except Exception:
        pass
    return "unknown"


def _read_rich_catalog_entries() -> list[dict]:
    """Read rich connector metadata from the JSON catalog."""
    try:
        if not _CATALOG_VERSION_PATH.is_file():
            return []
        payload = json.loads(_CATALOG_VERSION_PATH.read_text(encoding="utf-8"))
        entries = payload.get("connectors") or []
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
    except Exception:
        pass
    return []


def _rich_catalog_payload(entry: dict, connector_id: str | None = None) -> dict:
    """Convert one JSON catalog entry to the Plugins tab payload."""
    return {
        "id": connector_id or entry.get("slug") or entry.get("name"),
        "name": entry.get("name"),
        "description": entry.get("description"),
        "category": entry.get("category"),
        "auth_type": entry.get("auth_type") or "none",
        "icon_url": entry.get("icon_url"),
        "tools": entry.get("tools") or [],
        "config_schema": entry.get("config_schema") or {},
        "slug": entry.get("slug"),
        "interface": entry.get("interface") or {},
        "auth": entry.get("auth") or {},
        "skills": entry.get("skills") or [],
        "skill_count": entry.get("skill_count") or len(entry.get("skills") or []),
        "mcp_servers": entry.get("mcp_servers") or {},
        "catalog_seeded": connector_id is not None,
    }


@router.get("/catalog")
async def get_connector_catalog(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public connector catalog used by the Plugins tab.

    Returns ``{ "version": "...", "connectors": [...] }`` with each
    connector sorted by ``(category, name)`` so the UI can render
    grouped sections without sorting client-side.
    """
    now = time.monotonic()
    cached = _catalog_cache.get("value")
    expires_at = float(_catalog_cache.get("expires_at") or 0.0)
    if cached is not None and now < expires_at:
        return cached  # type: ignore[return-value]

    rich_entries = _read_rich_catalog_entries()
    rich_by_name = {
        str(entry.get("name") or ""): entry
        for entry in rich_entries
        if entry.get("name")
    }
    rows = (await db.execute(select(Connector))).scalars().all()
    connectors: list[dict] = []
    seen_names: set[str] = set()
    for row in rows:
        seen_names.add(row.name)
        rich = dict(rich_by_name.get(row.name) or {})
        if rich:
            payload = _rich_catalog_payload(rich, connector_id=str(row.id))
            payload.update(
                {
                    "description": row.description,
                    "category": row.category,
                    "auth_type": row.auth_type,
                    "icon_url": row.icon_url,
                    "tools": row.tools or rich.get("tools") or [],
                    "config_schema": row.config_schema or rich.get("config_schema") or {},
                }
            )
            connectors.append(payload)
        else:
            connectors.append(
                {
                    "id": str(row.id),
                    "name": row.name,
                    "description": row.description,
                    "category": row.category,
                    "auth_type": row.auth_type,
                    "icon_url": row.icon_url,
                    "tools": row.tools or [],
                    "config_schema": row.config_schema or {},
                    "slug": None,
                    "interface": {},
                    "auth": {},
                    "skills": [],
                    "skill_count": 0,
                    "mcp_servers": {},
                    "catalog_seeded": True,
                }
            )

    # If the JSON catalog has been updated but startup seeding has not
    # run yet, still show the connector in the Plugins tab. The new
    # install API can create the missing Connector row from this same
    # catalog entry on first install.
    for entry in rich_entries:
        name = str(entry.get("name") or "")
        if not name or name in seen_names:
            continue
        connectors.append(_rich_catalog_payload(entry, connector_id=None))

    # Sort by (category lowercased, name lowercased) so empty / null
    # categories cluster together at the bottom under "" -- matches
    # the Codex-style grouping the UI does.
    connectors.sort(
        key=lambda c: ((c.get("category") or "").lower(), (c.get("name") or "").lower())
    )

    payload = {
        "version": _read_catalog_version(),
        "connectors": connectors,
    }
    _catalog_cache["value"] = payload
    _catalog_cache["expires_at"] = now + _CATALOG_CACHE_TTL_S
    return payload


def _invalidate_catalog_cache() -> None:
    """Test hook + safety valve: drop the in-process catalog cache."""
    _catalog_cache["value"] = None
    _catalog_cache["expires_at"] = 0.0


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


@router.post("/instances/install", status_code=201)
async def install_instance(
    body: InstallConnectorRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ConnectionService = Depends(get_connection_service),
) -> dict:
    """Install a connector in Daena without account authentication.

    This is the first step for OAuth/API-key/token apps. The connector
    becomes CONNECTED only after the separate connect-account step
    succeeds. This matches Claude/Codex-style plugin setup: install the
    capability, then sign in/configure credentials.
    """
    instance = await service.install(
        connector_id=body.connector_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": instance}


@router.post("/instances/install-defaults", status_code=201)
async def install_default_instances(
    user: CurrentUser = Depends(get_current_user),
    service: ConnectionService = Depends(get_connection_service),
) -> dict:
    """Install Daena's recommended connector starter set idempotently."""
    instances = await service.install_recommended(
        user_id=user.id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": {"installed": instances, "count": len(instances)}}


@router.post("/instances/{instance_id}/connect")
async def connect_account(
    instance_id: UUID,
    body: ConnectAccountRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ConnectionService = Depends(get_connection_service),
) -> dict:
    """Attach credentials to an installed connector instance."""
    instance = await service.connect_account(
        instance_id=instance_id,
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


def _mcp_package_hint(command: str, args: list[str]) -> str | None:
    """Best-effort package hint for stdio MCP installs."""
    if command.lower() != "npx":
        return None
    for arg in args:
        if arg.startswith("-"):
            continue
        return arg
    return None


@router.post("/extensions/install", status_code=201)
async def install_extension(
    body: ExtensionInstallRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Install an MCP server extension from the catalog.

    Writes the server config to Claude Desktop config file so it
    appears in the extensions list on next scan, then persists the
    tenant-scoped MCP row so UI installs survive backend restart.
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

    persisted_id = None
    mcp_persisted = False
    persistence_error = None
    try:
        from app.core.events import get_mcp_registry
        from app.services.mcp_registry import STATUS_ACTIVE, STATUS_DISCOVERED

        persisted = await get_mcp_registry().persist_addition(
            tenant_id=user.tenant_id,
            entry={
                "server_key": server_key,
                "display_name": body.name,
                "description": body.description,
                "command": install_cmd,
                "args": list(install_args),
                "package": _mcp_package_hint(install_cmd, list(install_args)),
                "status": STATUS_ACTIVE if newly_live else STATUS_DISCOVERED,
                "auto_loaded": False,
                "extra_metadata": {
                    "source": "connections.extensions.install",
                    "catalog_id": body.id,
                    "registry_refreshed": newly_live,
                },
            },
            db=db,
            created_by_user_id=user.id,
        )
        await db.commit()
        persisted_id = str(persisted.id)
        mcp_persisted = True
    except Exception as exc:  # noqa: BLE001 - install response must be honest.
        await db.rollback()
        persistence_error = exc.__class__.__name__

    return {
        "success": True,
        "data": {
            "id": body.id,
            "name": body.name,
            "status": "installed" if mcp_persisted else "installed_not_persisted",
            "server_key": server_key,
            "registry_refreshed": newly_live,
            "mcp_persisted": mcp_persisted,
            "mcp_server_id": persisted_id,
            "persistence_error": persistence_error,
        },
    }


class ExtensionUninstallRequest(BaseModel):
    """Body for the uninstall endpoint. Accepts either the user-facing
    plugin id (``google-drive``) or the canonical ``mcp-<id>`` server
    key the installer wrote to ``claude_desktop_config.json``."""

    id: str


class ExtensionConfigRequest(BaseModel):
    """Body for editing a server's command/args/env in claude_desktop_config.json.

    Mirrors the Codex Settings → MCP servers gear-icon flow: pick a
    server, edit its command line + env vars, save. We re-bootstrap the
    registry so the edit takes effect without a restart.
    """

    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None


@router.get("/extensions/{server_key}/config", status_code=200)
async def get_extension_config(
    server_key: str,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Read a single MCP server's config block from claude_desktop_config.json.

    Used by the Settings modal in the MCP Servers tab to pre-fill the
    editor with the current command + args + env so the operator can
    edit them in place instead of remembering the full launch line.
    """
    import json
    from pathlib import Path

    config_path = Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    if not config_path.exists():
        return {"success": False, "error": {"message": "Claude config not found"}}

    config = json.loads(config_path.read_text(encoding="utf-8"))
    mcp_servers = config.get("mcpServers") or {}
    entry = mcp_servers.get(server_key)
    if entry is None:
        return {"success": False, "error": {"message": f"Server '{server_key}' not found"}}

    return {
        "success": True,
        "data": {
            "server_key": server_key,
            "command": entry.get("command", ""),
            "args": list(entry.get("args") or []),
            "env": dict(entry.get("env") or {}),
            "metadata": entry.get("metadata") or {},
        },
    }


@router.post("/extensions/{server_key}/config", status_code=200)
async def update_extension_config(
    server_key: str,
    body: ExtensionConfigRequest,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Patch an MCP server's command/args/env in claude_desktop_config.json.

    Codex parity: gear icon next to a server in the Settings → MCP
    servers list opens an editor for the launch command + env vars.
    On save we patch the config file in place and re-bootstrap the
    registry so the edit is live without a restart.
    """
    import json
    from pathlib import Path

    config_path = Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    if not config_path.exists():
        return {"success": False, "error": {"message": "Claude config not found"}}

    config = json.loads(config_path.read_text(encoding="utf-8"))
    mcp_servers = config.setdefault("mcpServers", {})
    entry = mcp_servers.get(server_key)
    if entry is None:
        return {"success": False, "error": {"message": f"Server '{server_key}' not found"}}

    # Patch only fields explicitly set in the body.
    if body.command is not None:
        entry["command"] = body.command
    if body.args is not None:
        entry["args"] = list(body.args)
    if body.env is not None:
        entry["env"] = dict(body.env)

    mcp_servers[server_key] = entry
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    # Re-bootstrap so the edited config is live immediately.
    try:
        from app.services.mcp_bootstrap import bootstrap_installed_mcps

        registry = await bootstrap_installed_mcps()
        is_live = server_key in registry
    except Exception:
        is_live = False

    return {
        "success": True,
        "data": {
            "server_key": server_key,
            "command": entry.get("command"),
            "args": entry.get("args"),
            "env": entry.get("env"),
            "registry_refreshed": is_live,
        },
    }


@router.post("/extensions/{server_key}/probe-auth", status_code=200)
async def probe_extension_auth(
    server_key: str,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Check whether an MCP server is alive and what its tool surface looks like.

    Calls the MCP's standard ``tools/list`` over stdio. If the server
    responds, we get the live tool catalog; we also surface a guess
    about whether the server appears to need OAuth (presence of tools
    with names like ``list_calendars``, ``search_drive`` is a strong
    signal that first-call OAuth is required). The frontend uses this
    to decide whether to show a "Sign in" button on the expanded row.
    """
    from app.services.mcp_invoker import list_server_tools
    import re

    result = await list_server_tools(server_key, timeout=10.0)
    if (
        not result.get("success")
        and "not in bootstrap registry" in str(result.get("error", ""))
    ):
        from app.services.mcp_bootstrap import bootstrap_installed_mcps

        await bootstrap_installed_mcps()
        result = await list_server_tools(server_key, timeout=10.0)
    if not result.get("success"):
        # Many MCPs fail at startup when required env vars (API keys,
        # Google client id/secret, service account key, etc.) are
        # missing. Their error message usually names the env vars
        # explicitly: "Please set GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET".
        # Extract that list so the UI can show a guided "Missing
        # credentials" state with a jump straight into the env editor,
        # instead of just "Server not reachable" with no recourse.
        err_text = result.get("error", "Unknown failure")
        # Common phrasings: "Please set X/Y", "missing env var X", "X is required"
        env_var_candidates = re.findall(
            r"\b([A-Z][A-Z0-9_]{2,})(?:[/,\s]+([A-Z][A-Z0-9_]{2,}))*\b",
            err_text,
        )
        # Flatten + dedupe; reject obvious noise (NODE, ENV alone, etc.)
        flat: list[str] = []
        for tup in env_var_candidates:
            for v in tup if isinstance(tup, tuple) else (tup,):
                if v and v not in flat and len(v) >= 4 and v not in {"NODE", "PATH", "HOME", "ENV", "ERROR", "DEBUG"}:
                    flat.append(v)
        # Heuristic check: does the message mention credentials / auth?
        is_creds_error = bool(
            re.search(
                r"(no authentication|missing credential|missing.*env|not.*authenticated|no api key|please set|requires.*key)",
                err_text,
                re.IGNORECASE,
            )
        )
        return {
            "success": False,
            "data": {
                "server_key": server_key,
                "alive": False,
                "error": err_text,
                "missing_credentials": is_creds_error,
                "required_env_vars": flat[:6],  # Cap to avoid noisy regex hits
            },
        }

    tools = result.get("tools", [])
    # OAuth heuristic: if any tool name suggests Google/Microsoft/etc.
    # account-bound resources, the MCP almost certainly needs the user
    # to sign in on first call. We surface this as `auth_required: True`
    # so the UI shows the "Sign in" affordance — even though the actual
    # OAuth runs inside the MCP subprocess (not in Daena).
    oauth_signals = (
        "list_calendars", "list_events", "create_event",       # google calendar
        "search_drive", "list_drive_files", "read_drive_file", # google drive
        "list_emails", "read_email", "send_email",             # gmail
        "list_repos", "read_repo_file",                        # github
        "list_channels_slack",                                  # slack
    )
    auth_required = any(
        t.get("name", "").lower() in oauth_signals for t in tools
    )

    # Best-effort: probe the connected account identity. Many account-bound
    # MCPs expose a "whoami" / "userinfo" / "list_calendars" tool whose
    # response embeds the user's email. We try a small set of likely
    # candidates with empty args; if any returns text containing an
    # email, we surface it as "connected_as". On failure (auth not yet
    # done, MCP errored, etc.) we just leave connected_as=None — the UI
    # then offers a Sign In button.
    connected_as: str | None = None
    if auth_required:
        from app.services.mcp_invoker import call_server_tool
        import re

        WHOAMI_CANDIDATES = (
            "whoami", "get_user", "user_info", "userinfo",
            "list_calendars", "list_drives",  # responses often include email
        )
        available_set = {t.get("name", "") for t in tools}
        for whoami in WHOAMI_CANDIDATES:
            if whoami not in available_set:
                continue
            try:
                wresp = await call_server_tool(server_key, whoami, arguments={}, timeout=15.0)
                if not wresp.get("success") or wresp.get("is_error"):
                    continue
                blob = ""
                for part in wresp.get("content", []) or []:
                    if isinstance(part, dict) and "text" in part:
                        blob += " " + str(part["text"])
                m = re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", blob)
                if m:
                    connected_as = m.group(0)
                    break
            except Exception:
                continue

    return {
        "success": True,
        "data": {
            "server_key": server_key,
            "alive": True,
            "tools_count": len(tools),
            "tools": [{"name": t["name"], "description": t.get("description", "")} for t in tools[:20]],
            "auth_required": auth_required,
            "connected_as": connected_as,
        },
    }


@router.post("/extensions/{server_key}/sign-in", status_code=200)
async def sign_in_extension(
    server_key: str,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Trigger an MCP's lazy OAuth by calling a known auth-required tool.

    Most account-bound MCPs (Google Drive, Gmail, Calendar) lazy-OAuth
    on the first tool call — they spawn a local browser tab. This
    endpoint picks a low-impact tool from the server's catalog and
    invokes it with empty args, which is enough to make the MCP open
    its OAuth window. The actual sign-in happens in the user's browser;
    we just kick the door open.

    The auth flow is owned by the MCP subprocess, NOT by Daena. We
    cannot intercept the OAuth callback or display the consent screen
    inline — the MCP is the OAuth client. Daena only triggers the
    initial call.
    """
    from app.services.mcp_invoker import call_server_tool, list_server_tools

    # Discover a safe tool to call. Prefer well-known read-only listers.
    READ_ONLY_PRIORITY = (
        "list_calendars", "list_drives", "list_drive_files",
        "list_emails", "list_channels", "list_repos",
        "list_zones", "list_tunnels",
    )

    tools_resp = await list_server_tools(server_key, timeout=10.0)
    if not tools_resp.get("success"):
        return {
            "success": False,
            "data": {
                "server_key": server_key,
                "error": tools_resp.get("error", "Server not reachable"),
            },
        }

    available_names = [t["name"] for t in tools_resp.get("tools", [])]
    chosen: str | None = None
    for candidate in READ_ONLY_PRIORITY:
        if candidate in available_names:
            chosen = candidate
            break
    if chosen is None and available_names:
        # Fall back to the first tool, hoping it's read-only.
        chosen = available_names[0]

    if chosen is None:
        return {
            "success": False,
            "data": {
                "server_key": server_key,
                "error": "Server exposes no tools to invoke for auth probe",
            },
        }

    call_result = await call_server_tool(server_key, chosen, arguments={}, timeout=60.0)
    # Many MCPs return is_error=True with a content message that contains
    # an OAuth URL when first-call sign-in is required. Surface that to
    # the UI so the operator can click through.
    excerpt = ""
    for part in call_result.get("content", []) or []:
        if isinstance(part, dict) and "text" in part:
            excerpt = (excerpt + " " + str(part["text"])).strip()
    excerpt = excerpt[:400]

    return {
        "success": True,
        "data": {
            "server_key": server_key,
            "called_tool": chosen,
            "tool_succeeded": bool(call_result.get("success")),
            "is_error": bool(call_result.get("is_error")),
            "excerpt": excerpt,
            "hint": (
                "If a browser window opened, complete the sign-in there. "
                "Once done, click 'Re-check' to confirm Daena can see the auth."
            ),
        },
    }


@router.post("/extensions/uninstall", status_code=200)
async def uninstall_extension(
    body: ExtensionUninstallRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove an MCP entry from ``claude_desktop_config.json``.

    Mirrors ``install`` end-to-end: writes the config, re-bootstraps
    the registry so the removal is live immediately, and soft-deletes
    the tenant-scoped DB row. Idempotent -- removing an entry that's
    not there returns ``removed=False`` but still 200.
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

    db_removed = False
    persistence_error = None
    try:
        from app.core.events import get_mcp_registry

        db_removed = await get_mcp_registry().remove_server(
            user.tenant_id,
            server_key,
            db,
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001 - uninstall response must be honest.
        await db.rollback()
        persistence_error = exc.__class__.__name__

    return {
        "success": True,
        "data": {
            "server_key": server_key,
            "removed": removed,
            "mcp_persisted_removed": db_removed,
            "persistence_error": persistence_error,
        },
    }
