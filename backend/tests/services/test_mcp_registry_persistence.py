"""Persistence tests for MCPRegistry.

Covers the 2026-04-29 fix: MCP servers added through the UI must
survive a process restart. Verifies the registry's tenant scoping,
DB hydration, and backward-compat fallback to the synthetic system
tenant.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.identity import Tenant
from app.models.mcp_server import (
    STATUS_ACTIVE,
    STATUS_DISABLED,
    STATUS_DISCOVERED,
    STATUS_FAILED,
    McpServer,
)
from app.services.mcp_registry import (
    SYSTEM_TENANT_KEY,
    MCPRegistry,
    MCPTool,
)


# ── Helpers ──


async def _seed_tenant(db_session, tenant_id: uuid.UUID, slug: str) -> None:
    """Insert a minimal Tenant row required for FK satisfaction."""
    db_session.add(Tenant(
        id=tenant_id,
        name=f"MCP Tenant {slug}",
        slug=f"mcp-tenant-{slug}",
        plan="FREE",
        settings={},
    ))
    await db_session.flush()


def _make_entry(
    server_key: str = "filesystem",
    *,
    command: str = "npx",
    args: list[str] | None = None,
    description: str | None = None,
) -> dict:
    """Build an entry dict matching what the API layer passes through."""
    return {
        "server_key": server_key,
        "display_name": server_key.title(),
        "description": description or f"{server_key} MCP server",
        "command": command,
        "args": args or ["-y", f"@modelcontextprotocol/server-{server_key}"],
        "package": f"@modelcontextprotocol/server-{server_key}",
        "extra_metadata": {"source": "test"},
    }


# ── Hydration ──


@pytest.mark.asyncio
async def test_hydrate_from_empty_db_returns_zero(db_session, test_tenant_id) -> None:
    """A fresh registry against an empty mcp_servers table yields nothing."""
    await _seed_tenant(db_session, test_tenant_id, "empty")

    registry = MCPRegistry()
    count = await registry.hydrate_from_db(test_tenant_id, db_session)

    assert count == 0
    cached = await registry.list_servers(tenant_id=test_tenant_id)
    assert cached == []


@pytest.mark.asyncio
async def test_persist_addition_writes_row_and_updates_cache(
    db_session, test_tenant_id,
) -> None:
    """persist_addition inserts a new mcp_servers row and caches it."""
    await _seed_tenant(db_session, test_tenant_id, "addition")

    registry = MCPRegistry()
    persisted = await registry.persist_addition(
        tenant_id=test_tenant_id,
        entry=_make_entry("filesystem"),
        db=db_session,
    )

    assert isinstance(persisted, McpServer)
    assert persisted.server_key == "filesystem"
    assert persisted.tenant_id == test_tenant_id
    assert persisted.status == STATUS_DISCOVERED
    assert persisted.command == "npx"
    assert persisted.args == ["-y", "@modelcontextprotocol/server-filesystem"]
    assert persisted.auto_loaded is False
    assert persisted.extra_metadata == {"source": "test"}

    cached = await registry.list_servers(tenant_id=test_tenant_id)
    assert len(cached) == 1
    assert cached[0].server_key == "filesystem"


@pytest.mark.asyncio
async def test_persist_addition_upserts_on_duplicate_key(
    db_session, test_tenant_id,
) -> None:
    """A second persist_addition for the same key updates instead of erroring."""
    await _seed_tenant(db_session, test_tenant_id, "upsert")
    registry = MCPRegistry()

    first = await registry.persist_addition(
        tenant_id=test_tenant_id,
        entry=_make_entry("filesystem", description="First version"),
        db=db_session,
    )
    second = await registry.persist_addition(
        tenant_id=test_tenant_id,
        entry=_make_entry("filesystem", description="Updated description"),
        db=db_session,
    )

    assert first.id == second.id
    assert second.description == "Updated description"
    cached = await registry.list_servers(tenant_id=test_tenant_id)
    assert len(cached) == 1


@pytest.mark.asyncio
async def test_hydrate_after_restart_restores_cached_entries(
    db_session, test_tenant_id,
) -> None:
    """Simulating a restart -- new MCPRegistry hydrates from prior rows."""
    await _seed_tenant(db_session, test_tenant_id, "restart")

    # Session 1: persist two servers in one registry instance.
    registry_a = MCPRegistry()
    await registry_a.persist_addition(
        tenant_id=test_tenant_id,
        entry=_make_entry("filesystem"),
        db=db_session,
    )
    await registry_a.persist_addition(
        tenant_id=test_tenant_id,
        entry=_make_entry("github", args=["-y", "@modelcontextprotocol/server-github"]),
        db=db_session,
    )

    # Session 2: brand-new registry, no in-memory state.
    registry_b = MCPRegistry()
    assert await registry_b.list_servers(tenant_id=test_tenant_id) == []

    count = await registry_b.hydrate_from_db(test_tenant_id, db_session)
    assert count == 2

    keys = sorted(
        s.server_key
        for s in await registry_b.list_servers(tenant_id=test_tenant_id)
    )
    assert keys == ["filesystem", "github"]


@pytest.mark.asyncio
async def test_remove_server_soft_deletes_and_excludes_from_hydrate(
    db_session, test_tenant_id,
) -> None:
    """remove_server -> DISABLED, then re-hydrate skips it."""
    await _seed_tenant(db_session, test_tenant_id, "remove")
    registry = MCPRegistry()

    await registry.persist_addition(
        tenant_id=test_tenant_id,
        entry=_make_entry("filesystem"),
        db=db_session,
    )
    # Also register a tool tied to this server so cascade-unregister fires.
    await registry.register_tools(
        [MCPTool(
            name="fs.read",
            description="Read a file",
            connection_id="mcp_server:filesystem",
        )],
        tenant_id=test_tenant_id,
    )
    assert registry.tool_count_for(test_tenant_id) == 1

    removed = await registry.remove_server(
        tenant_id=test_tenant_id,
        server_key="filesystem",
        db=db_session,
    )
    assert removed is True
    assert await registry.list_servers(tenant_id=test_tenant_id) == []
    assert registry.tool_count_for(test_tenant_id) == 0

    fresh = MCPRegistry()
    rehydrated = await fresh.hydrate_from_db(test_tenant_id, db_session)
    assert rehydrated == 0


@pytest.mark.asyncio
async def test_remove_server_returns_false_when_unknown(
    db_session, test_tenant_id,
) -> None:
    """Removing a server_key that was never persisted is a no-op."""
    await _seed_tenant(db_session, test_tenant_id, "noop")
    registry = MCPRegistry()
    removed = await registry.remove_server(
        tenant_id=test_tenant_id,
        server_key="never-existed",
        db=db_session,
    )
    assert removed is False


@pytest.mark.asyncio
async def test_update_health_flips_status(db_session, test_tenant_id) -> None:
    """update_health writes ACTIVE on success and FAILED on failure."""
    await _seed_tenant(db_session, test_tenant_id, "health")
    registry = MCPRegistry()
    await registry.persist_addition(
        tenant_id=test_tenant_id,
        entry=_make_entry("filesystem"),
        db=db_session,
    )

    await registry.update_health(
        tenant_id=test_tenant_id,
        server_key="filesystem",
        ok=True,
        db=db_session,
    )
    cached = await registry.list_servers(tenant_id=test_tenant_id)
    assert cached[0].status == STATUS_ACTIVE
    assert cached[0].last_health_ok is True
    assert cached[0].last_health_at is not None

    await registry.update_health(
        tenant_id=test_tenant_id,
        server_key="filesystem",
        ok=False,
        db=db_session,
    )
    cached = await registry.list_servers(tenant_id=test_tenant_id)
    assert cached[0].status == STATUS_FAILED
    assert cached[0].last_health_ok is False


# ── Tenant isolation ──


@pytest.mark.asyncio
async def test_tenant_isolation(db_session) -> None:
    """Tenant A's MCPs are invisible to tenant B."""
    tenant_a = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    tenant_b = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    await _seed_tenant(db_session, tenant_a, "a")
    await _seed_tenant(db_session, tenant_b, "b")

    registry = MCPRegistry()
    await registry.persist_addition(
        tenant_id=tenant_a,
        entry=_make_entry("filesystem"),
        db=db_session,
    )
    await registry.persist_addition(
        tenant_id=tenant_b,
        entry=_make_entry("github", args=["-y", "@modelcontextprotocol/server-github"]),
        db=db_session,
    )

    # Each tenant only sees its own servers.
    a_servers = await registry.list_servers(tenant_id=tenant_a)
    b_servers = await registry.list_servers(tenant_id=tenant_b)
    assert [s.server_key for s in a_servers] == ["filesystem"]
    assert [s.server_key for s in b_servers] == ["github"]

    # A fresh registry hydrating tenant A only loads tenant A's row.
    fresh = MCPRegistry()
    count_a = await fresh.hydrate_from_db(tenant_a, db_session)
    assert count_a == 1
    assert await fresh.list_servers(tenant_id=tenant_b) == []


# ── Backward compatibility ──


@pytest.mark.asyncio
async def test_register_tools_without_tenant_defaults_to_system() -> None:
    """Legacy register_tools(tools) call routes to the system tenant."""
    registry = MCPRegistry()
    count = await registry.register_tools([
        MCPTool(name="legacy_tool", description="legacy", connection_id="x"),
    ])
    assert count == 1

    # Lookup via system tenant key works.
    assert registry.tool_count_for(None) == 1
    assert registry.tool_count_for(SYSTEM_TENANT_KEY) == 1
    listed = registry.list_tools()
    assert listed[0]["name"] == "legacy_tool"

    # Lookup via a non-system tenant falls back to system on miss.
    found = registry.get_tool("legacy_tool", tenant_id=uuid.uuid4())
    assert found is not None and found.name == "legacy_tool"


@pytest.mark.asyncio
async def test_get_tool_prefers_tenant_over_system() -> None:
    """A tenant-scoped tool wins over a same-named system tool."""
    registry = MCPRegistry()
    tenant_id = uuid.uuid4()
    await registry.register_tools(
        [MCPTool(name="dup", description="system", connection_id="sys")],
    )
    await registry.register_tools(
        [MCPTool(name="dup", description="tenant", connection_id="t")],
        tenant_id=tenant_id,
    )

    sys_view = registry.get_tool("dup")
    tenant_view = registry.get_tool("dup", tenant_id=tenant_id)
    assert sys_view is not None and sys_view.description == "system"
    assert tenant_view is not None and tenant_view.description == "tenant"


@pytest.mark.asyncio
async def test_unregister_connection_scoped_by_tenant() -> None:
    """unregister_connection only clears the named tenant's bucket."""
    registry = MCPRegistry()
    tenant_id = uuid.uuid4()
    await registry.register_tools(
        [MCPTool(name="t1", description="sys", connection_id="conn-1")],
    )
    await registry.register_tools(
        [MCPTool(name="t1", description="tenant", connection_id="conn-1")],
        tenant_id=tenant_id,
    )

    removed = registry.unregister_connection("conn-1", tenant_id=tenant_id)
    assert removed == 1
    assert registry.tool_count_for(tenant_id) == 0
    # System bucket untouched.
    assert registry.tool_count_for(None) == 1


# ── Persisted-row attributes ──


@pytest.mark.asyncio
async def test_persist_addition_records_user_provenance(
    db_session, test_tenant_id, test_user_id,
) -> None:
    """created_by_user_id is captured and survives hydrate."""
    await _seed_tenant(db_session, test_tenant_id, "user")

    # We need a User row for the FK; insert a minimal one.
    from app.models.identity import User
    db_session.add(User(
        id=test_user_id,
        tenant_id=test_tenant_id,
        email="mcp-author@example.com",
        password_hash="x",
        role="FOUNDER",
        is_active=True,
        settings={},
    ))
    await db_session.flush()

    registry = MCPRegistry()
    persisted = await registry.persist_addition(
        tenant_id=test_tenant_id,
        entry=_make_entry("filesystem"),
        db=db_session,
        created_by_user_id=test_user_id,
    )

    assert persisted.created_by_user_id == test_user_id

    # Hydrate from a fresh registry and confirm the value round-trips.
    fresh = MCPRegistry()
    await fresh.hydrate_from_db(test_tenant_id, db_session)
    rows = await fresh.list_servers(tenant_id=test_tenant_id)
    assert len(rows) == 1
    assert rows[0].created_by_user_id == test_user_id
