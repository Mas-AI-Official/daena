"""MCP (Model Context Protocol) tool registry with tenant-scoped persistence.

Discovers and registers tools from MCP-compatible connections, making
them available to DaenaBot for execution through governance.

Persistence (added 2026-04-29)
------------------------------
The registry is now a runtime cache backed by the ``McpServer`` model.
UI-added MCP servers are persisted on registration and re-hydrated on
process startup via :func:`init_mcp_registry`, fixing the long-standing
"installed MCPs disappear on restart" bug.

The ``_tools`` dict is now nested by tenant: ``{tenant_id: {tool_name: MCPTool}}``.
Backward-compat methods omit ``tenant_id`` and route to a synthetic
``"system"`` tenant so the existing bootstrap path
(``mcp_bootstrap.bootstrap_installed_mcps``) keeps working unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy import select

from app.core.logging import get_logger
from app.models.mcp_server import (
    STATUS_ACTIVE,
    STATUS_DISABLED,
    STATUS_DISCOVERED,
    STATUS_FAILED,
    McpServer,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# Synthetic tenant used by bootstrapped (system-wide) MCP entries and
# by callers that omit ``tenant_id`` for backward compat. The string
# form keeps the in-memory dict lookups cheap and avoids forcing the
# whole codebase to thread a ``Tenant`` row through.
SYSTEM_TENANT_KEY = "system"


def _tenant_key(tenant_id: Any) -> str:
    """Normalize a tenant identifier to a string cache key.

    Accepts ``None`` (treated as ``SYSTEM_TENANT_KEY``), a UUID, or a
    str. Returning a str keeps the nested dict's hashing predictable
    across SQLite (str-backed UUIDs) and PostgreSQL (native UUID).
    """
    if tenant_id is None:
        return SYSTEM_TENANT_KEY
    return str(tenant_id)


@dataclass(frozen=True, slots=True)
class MCPTool:
    """A tool discovered from an MCP server."""
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    connection_id: str = ""
    governance_tier: int = 2  # Default: NOTIFIED tier for external tools


class MCPRegistry:
    """Discovers, registers, and persists tools from MCP connections.

    Two parallel caches:

    * ``_tools[tenant_key][tool_name] -> MCPTool`` -- the runtime tool
      catalog the LLM can call. Populated by ``register_tools`` and by
      ``discover_tools`` after a remote MCP enumerates its tools.
    * ``_servers[tenant_key][server_key] -> McpServer`` -- the
      persisted server registrations. Populated by ``hydrate_from_db``
      at startup and by ``persist_addition`` when the UI adds a new
      server. Tools attached to a server share the same
      ``connection_id`` (we use ``mcp_server:{server_key}`` by
      convention) so ``remove_server`` can cascade-unregister them.
    """

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, MCPTool]] = {}
        self._servers: dict[str, dict[str, McpServer]] = {}
        self._connection_urls: dict[str, str] = {}

    # ── Read-side helpers ──────────────────────────────────────────────

    @property
    def tool_count(self) -> int:
        """Total registered MCP tools across all tenants."""
        return sum(len(tools) for tools in self._tools.values())

    def tool_count_for(self, tenant_id: Any | None = None) -> int:
        """Tools registered for a specific tenant (defaults to system)."""
        return len(self._tools.get(_tenant_key(tenant_id), {}))

    def list_tools(self, tenant_id: Any | None = None) -> list[dict[str, Any]]:
        """List registered MCP tools.

        When ``tenant_id`` is ``None`` we return the system-tenant
        bucket. Existing call sites in chat_orchestrator currently
        only see system-tenant tools; explicit tenant scoping rolls
        out as the chat pipeline learns to thread tenant_id through.
        """
        bucket = self._tools.get(_tenant_key(tenant_id), {})
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
                "connection_id": t.connection_id,
                "governance_tier": t.governance_tier,
            }
            for t in bucket.values()
        ]

    def get_tool(
        self,
        name: str,
        tenant_id: Any | None = None,
    ) -> MCPTool | None:
        """Get a registered MCP tool by name.

        Falls back across tenant buckets (caller's tenant, then system)
        because some tools are shared infrastructure (filesystem, git)
        bootstrapped under the system tenant.

        When called without an explicit tenant_id (legacy callers and
        tests pre-2026-04-29 tenant-scoping refactor), if the tool is
        not found in the system bucket we scan all tenant buckets and
        return the first match. This preserves the backward-compatible
        "discoverable by name alone" contract that pre-tenant-scoping
        callers depend on, while strict tenant lookups (with an explicit
        tenant_id) remain isolated.
        """
        primary = self._tools.get(_tenant_key(tenant_id), {})
        tool = primary.get(name)
        if tool is not None:
            return tool
        if _tenant_key(tenant_id) != SYSTEM_TENANT_KEY:
            return self._tools.get(SYSTEM_TENANT_KEY, {}).get(name)
        if tenant_id is None:
            for bucket_key, bucket in self._tools.items():
                if bucket_key == SYSTEM_TENANT_KEY:
                    continue
                tool = bucket.get(name)
                if tool is not None:
                    return tool
        return None

    async def list_servers(
        self,
        tenant_id: Any | None = None,
    ) -> list[McpServer]:
        """Read the cached server rows for a tenant.

        Returns empty list when no rows have been hydrated yet -- this
        preserves the legacy "fresh registry returns nothing" contract.
        """
        return list(self._servers.get(_tenant_key(tenant_id), {}).values())

    # ── Discovery + tool registration ──────────────────────────────────

    async def discover_tools(
        self,
        connection_id: str,
        server_url: str,
        tenant_id: Any | None = None,
    ) -> list[MCPTool]:
        """Query an MCP server for available tools.

        Args:
            connection_id: The Daena connection ID for this MCP server.
            server_url: The URL of the MCP server.
            tenant_id: Tenant scoping for the discovered tools. Omit
                to attribute discovery to the system tenant (legacy
                bootstrap behaviour).

        Returns:
            List of discovered MCP tools.
        """
        discovered: list[MCPTool] = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{server_url}/tools/list",
                    json={},
                )
                resp.raise_for_status()
                data = resp.json()

                tools_data = data.get("tools", [])
                for tool_data in tools_data:
                    tool = MCPTool(
                        name=tool_data.get("name", ""),
                        description=tool_data.get("description", ""),
                        input_schema=tool_data.get("inputSchema", {}),
                        connection_id=connection_id,
                        governance_tier=self._classify_governance_tier(tool_data),
                    )
                    discovered.append(tool)

                logger.info(
                    "mcp_registry.tools_discovered",
                    connection_id=connection_id,
                    tenant_id=_tenant_key(tenant_id),
                    count=len(discovered),
                )
        except Exception as exc:
            logger.warning(
                "mcp_registry.discovery_failed",
                connection_id=connection_id,
                tenant_id=_tenant_key(tenant_id),
                error=str(exc),
            )

        return discovered

    async def register_tools(
        self,
        tools: list[MCPTool],
        tenant_id: Any | None = None,
    ) -> int:
        """Make discovered tools available to DaenaBot.

        Args:
            tools: List of MCP tools to register.
            tenant_id: Tenant the tools belong to. Defaults to the
                synthetic system tenant for backward compat with the
                bootstrap path that pre-dates tenant scoping.

        Returns:
            Number of tools registered.
        """
        bucket = self._tools.setdefault(_tenant_key(tenant_id), {})
        registered = 0
        for tool in tools:
            if not tool.name:
                continue
            bucket[tool.name] = tool
            registered += 1
            logger.info(
                "mcp_registry.tool_registered",
                name=tool.name,
                tenant_id=_tenant_key(tenant_id),
                governance_tier=tool.governance_tier,
            )
        return registered

    def unregister_connection(
        self,
        connection_id: str,
        tenant_id: Any | None = None,
    ) -> int:
        """Remove all tools from a specific connection.

        Without ``tenant_id`` the cleanup runs against the system
        tenant only; pass an explicit tenant to scope it. The
        connection-id key matches whatever the caller used at
        registration time, typically ``mcp_server:{server_key}``.
        """
        bucket = self._tools.get(_tenant_key(tenant_id), {})
        to_remove = [
            name for name, tool in bucket.items()
            if tool.connection_id == connection_id
        ]
        for name in to_remove:
            del bucket[name]
        return len(to_remove)

    # ── DB-backed persistence ──────────────────────────────────────────

    async def hydrate_from_db(
        self,
        tenant_id: Any,
        db: AsyncSession,
    ) -> int:
        """Repopulate ``_servers[tenant]`` from the ``mcp_servers`` table.

        Only loads non-disabled rows so soft-deleted entries do not
        come back to life on the next restart. Returns the row count
        that landed in the cache (excludes ``DISABLED``).
        """
        stmt = select(McpServer).where(McpServer.tenant_id == tenant_id)
        result = await db.execute(stmt)
        rows = result.scalars().all()

        bucket: dict[str, McpServer] = {}
        for row in rows:
            if row.status == STATUS_DISABLED:
                continue
            bucket[row.server_key] = row
        self._servers[_tenant_key(tenant_id)] = bucket

        logger.info(
            "mcp_registry.hydrated",
            tenant_id=_tenant_key(tenant_id),
            count=len(bucket),
            total_rows=len(rows),
        )
        return len(bucket)

    async def persist_addition(
        self,
        tenant_id: Any,
        entry: dict[str, Any],
        db: AsyncSession,
        created_by_user_id: Any | None = None,
    ) -> McpServer:
        """Insert or update an ``McpServer`` row, then refresh the cache.

        ``entry`` is a flexible dict mirroring the fields the UI
        exposes. The accepted keys are::

            server_key       (required)
            display_name     (defaults to server_key)
            description
            command          (stdio MCPs)
            args             (list, defaults to [])
            package          (npm package hint, e.g. @scope/server-X)
            server_url       (HTTP MCPs)
            status           (defaults to DISCOVERED on insert)
            auto_loaded      (True for bootstrapped entries)
            extra_metadata   (dict, optional governance/transport hints)

        On conflict (same ``tenant_id`` + ``server_key``) we update in
        place rather than failing -- the UI's "add" action is treated
        as upsert so a re-import after a config edit just patches the
        existing row.
        """
        server_key = entry.get("server_key")
        if not server_key:
            raise ValueError("persist_addition requires 'server_key' in entry")

        stmt = (
            select(McpServer)
            .where(McpServer.tenant_id == tenant_id)
            .where(McpServer.server_key == server_key)
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing is None:
            row = McpServer(
                tenant_id=tenant_id,
                server_key=server_key,
                display_name=entry.get("display_name") or server_key,
                description=entry.get("description"),
                command=entry.get("command"),
                args=list(entry.get("args") or []),
                package=entry.get("package"),
                server_url=entry.get("server_url"),
                status=entry.get("status") or STATUS_DISCOVERED,
                auto_loaded=bool(entry.get("auto_loaded", False)),
                created_by_user_id=created_by_user_id,
                extra_metadata=dict(entry.get("extra_metadata") or {}),
            )
            db.add(row)
            await db.flush()
            await db.refresh(row)
            persisted = row
            logger.info(
                "mcp_registry.persisted_new",
                tenant_id=_tenant_key(tenant_id),
                server_key=server_key,
            )
        else:
            existing.display_name = entry.get("display_name") or existing.display_name
            if "description" in entry:
                existing.description = entry["description"]
            if "command" in entry:
                existing.command = entry["command"]
            if "args" in entry:
                existing.args = list(entry["args"] or [])
            if "package" in entry:
                existing.package = entry["package"]
            if "server_url" in entry:
                existing.server_url = entry["server_url"]
            if "status" in entry:
                existing.status = entry["status"]
            if "auto_loaded" in entry:
                existing.auto_loaded = bool(entry["auto_loaded"])
            if "extra_metadata" in entry:
                existing.extra_metadata = dict(entry["extra_metadata"] or {})
            # Reactivate if it had been soft-deleted.
            if existing.status == STATUS_DISABLED:
                existing.status = entry.get("status") or STATUS_DISCOVERED
            await db.flush()
            await db.refresh(existing)
            persisted = existing
            logger.info(
                "mcp_registry.persisted_update",
                tenant_id=_tenant_key(tenant_id),
                server_key=server_key,
            )

        bucket = self._servers.setdefault(_tenant_key(tenant_id), {})
        bucket[server_key] = persisted
        return persisted

    async def remove_server(
        self,
        tenant_id: Any,
        server_key: str,
        db: AsyncSession,
    ) -> bool:
        """Soft-delete an MCP server (status -> DISABLED) and unregister tools.

        Returns ``True`` when a row was found and disabled, ``False``
        when the server_key was not registered for this tenant. The
        soft-delete preserves audit history per Hard Law 6 ("never
        delete, only archive").
        """
        stmt = (
            select(McpServer)
            .where(McpServer.tenant_id == tenant_id)
            .where(McpServer.server_key == server_key)
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            return False

        row.status = STATUS_DISABLED
        await db.flush()

        # Evict from the server cache.
        bucket = self._servers.get(_tenant_key(tenant_id), {})
        bucket.pop(server_key, None)

        # Cascade: unregister any tools that came from this server.
        # We follow the convention ``connection_id == "mcp_server:{server_key}"``
        # which the UI registration path uses today.
        cascade_id = f"mcp_server:{server_key}"
        removed = self.unregister_connection(cascade_id, tenant_id=tenant_id)

        logger.info(
            "mcp_registry.server_removed",
            tenant_id=_tenant_key(tenant_id),
            server_key=server_key,
            tools_unregistered=removed,
        )
        return True

    async def update_health(
        self,
        tenant_id: Any,
        server_key: str,
        ok: bool,
        db: AsyncSession,
    ) -> None:
        """Record the result of a health check on a persisted MCP.

        Updates ``last_health_at``, ``last_health_ok``, and flips
        ``status`` to ``ACTIVE`` (success) or ``FAILED`` (failure).
        Disabled rows are not touched -- a soft-deleted server should
        not silently revive itself because a stale probe came in.
        """
        stmt = (
            select(McpServer)
            .where(McpServer.tenant_id == tenant_id)
            .where(McpServer.server_key == server_key)
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None or row.status == STATUS_DISABLED:
            return

        row.last_health_at = datetime.now(timezone.utc)
        row.last_health_ok = bool(ok)
        row.status = STATUS_ACTIVE if ok else STATUS_FAILED
        await db.flush()

        # Refresh the cache reference so subsequent reads see the
        # new status without an extra SELECT.
        bucket = self._servers.setdefault(_tenant_key(tenant_id), {})
        bucket[server_key] = row

    # ── Internal classification ────────────────────────────────────────

    @staticmethod
    def _classify_governance_tier(tool_data: dict) -> int:
        """Classify governance tier based on tool capabilities.

        Destructive or high-risk operations get higher tiers.
        """
        name = tool_data.get("name", "").lower()
        desc = tool_data.get("description", "").lower()
        combined = f"{name} {desc}"

        # Tier 3: requires approval (destructive actions)
        if any(w in combined for w in ("delete", "remove", "drop", "destroy",
                                        "write", "modify", "update", "create",
                                        "send", "post", "execute", "run")):
            return 3

        # Tier 2: notified (read + potentially sensitive)
        if any(w in combined for w in ("read", "get", "list", "search",
                                        "query", "fetch", "download")):
            return 2

        # Tier 1: logged (minimal risk)
        return 1


# ── Public init function for app.main lifespan ────────────────────────


async def init_mcp_registry(app: FastAPI | None = None) -> int:
    """Hydrate the singleton registry from DB and run legacy bootstrap.

    Lifespan integration (call from ``app.main`` once Phase B wires it
    in)::

        from app.services.mcp_registry import init_mcp_registry
        total = await init_mcp_registry(app)

    What it does, in order:

    1. Pull every Tenant id and call ``hydrate_from_db`` per tenant
       (system tenant included). Soft-deleted rows are skipped.
    2. Run ``mcp_bootstrap.bootstrap_installed_mcps`` to seed system-
       tenant adapters from ``claude_desktop_config.json``. Existing
       behaviour is preserved -- this still works on a fresh install
       with an empty DB.

    Errors at any stage are logged but never raised; the app must
    still start even if the MCP layer is degraded.

    Returns the total cached server count across all tenants.
    """
    from app.core.database import async_session_factory
    from app.core.events import get_mcp_registry
    from app.models.identity import Tenant

    registry = get_mcp_registry()
    total = 0

    try:
        async with async_session_factory() as session:
            tenants = (await session.execute(select(Tenant.id))).scalars().all()
            for tenant_id in tenants:
                try:
                    total += await registry.hydrate_from_db(tenant_id, session)
                except Exception as exc:
                    logger.warning(
                        "mcp_registry.hydrate_failed",
                        tenant_id=str(tenant_id),
                        error=str(exc),
                    )
            await session.commit()
    except Exception as exc:
        logger.warning(
            "mcp_registry.hydrate_session_failed",
            error=str(exc),
            impact="Tenant MCPs may be invisible until next restart.",
        )

    # Legacy bootstrap path (claude_desktop_config.json -> system tenant
    # adapters). Kept separate from DB hydration so a malformed desktop
    # config never blocks per-tenant rows from loading.
    try:
        from app.services.mcp_bootstrap import bootstrap_installed_mcps

        adapters = await bootstrap_installed_mcps()
        logger.info(
            "mcp_registry.bootstrap_after_hydrate",
            adapter_count=len(adapters),
        )
    except Exception as exc:
        logger.warning(
            "mcp_registry.bootstrap_after_hydrate_failed",
            error=str(exc),
        )

    return total


__all__ = [
    "MCPTool",
    "MCPRegistry",
    "init_mcp_registry",
    "SYSTEM_TENANT_KEY",
    "STATUS_DISCOVERED",
    "STATUS_ACTIVE",
    "STATUS_FAILED",
    "STATUS_DISABLED",
]
