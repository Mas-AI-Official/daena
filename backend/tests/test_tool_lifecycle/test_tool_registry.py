"""Tests for ToolRegistry -- catalog management, governance, schema isolation."""

from __future__ import annotations

import pytest
import threading

from app.services.tool_lifecycle.tool_registry import (
    GovernanceRules,
    LightweightCatalogEntry,
    ToolDefinition,
    ToolRegistry,
)


# ── Fixtures ──────────────────────────────────────────────────

def _make_tool(
    tool_id: str = "google_drive",
    name: str = "Google Drive",
    category: str = "storage",
    light_desc: str = "Read/write files in Google Drive",
    schema: dict | None = None,
    auth: str = "oauth",
    cost: str = "low",
    departments: list[str] | None = None,
    requires_approval: bool = False,
    max_concurrent: int = 5,
    tokens: int = 200,
) -> ToolDefinition:
    return ToolDefinition(
        id=tool_id,
        name=name,
        category=category,
        light_description=light_desc,
        full_schema=schema or {"type": "function", "name": tool_id, "params": {}},
        auth_type=auth,
        connection_cost=cost,
        governance_rules=GovernanceRules(
            allowed_departments=departments or [],
            requires_approval=requires_approval,
            max_concurrent_sessions=max_concurrent,
        ),
        estimated_schema_tokens=tokens,
    )


@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry()


@pytest.fixture
def populated_registry() -> ToolRegistry:
    """Registry with 5 tools across categories."""
    reg = ToolRegistry()
    reg.register_tool(_make_tool("google_drive", "Google Drive", "storage"))
    reg.register_tool(_make_tool("canva", "Canva", "design", tokens=350))
    reg.register_tool(_make_tool("web_search", "Web Search", "search", auth="api_key"))
    reg.register_tool(_make_tool("slack", "Slack", "comms", cost="medium"))
    reg.register_tool(_make_tool(
        "terminal", "Terminal", "code",
        departments=["engineering", "security"],
        requires_approval=True,
        tokens=150,
    ))
    return reg


# ── Registration Tests ────────────────────────────────────────

class TestRegistration:
    def test_register_tool(self, registry: ToolRegistry):
        tool = _make_tool()
        registry.register_tool(tool)
        assert registry.count == 1

    def test_register_retrieve_by_id(self, registry: ToolRegistry):
        tool = _make_tool("my_tool", "My Tool")
        registry.register_tool(tool)
        retrieved = registry.get_tool("my_tool")
        assert retrieved is not None
        assert retrieved.id == "my_tool"
        assert retrieved.name == "My Tool"

    def test_duplicate_registration_raises(self, registry: ToolRegistry):
        tool = _make_tool()
        registry.register_tool(tool)
        with pytest.raises(ValueError, match="already registered"):
            registry.register_tool(tool)

    def test_register_or_update_idempotent(self, registry: ToolRegistry):
        tool1 = _make_tool("x", "Version 1")
        tool2 = _make_tool("x", "Version 2")
        registry.register_or_update(tool1)
        registry.register_or_update(tool2)
        assert registry.count == 1
        assert registry.get_tool("x").name == "Version 2"

    def test_unregister_existing(self, populated_registry: ToolRegistry):
        assert populated_registry.unregister_tool("canva") is True
        assert populated_registry.get_tool("canva") is None
        assert populated_registry.count == 4

    def test_unregister_nonexistent(self, registry: ToolRegistry):
        assert registry.unregister_tool("nonexistent") is False

    def test_register_many(self, registry: ToolRegistry):
        tools = [
            _make_tool("a", "Tool A"),
            _make_tool("b", "Tool B"),
            _make_tool("c", "Tool C"),
        ]
        count = registry.register_many(tools)
        assert count == 3
        assert registry.count == 3

    def test_register_many_skips_duplicates(self, registry: ToolRegistry):
        registry.register_tool(_make_tool("a", "Existing"))
        tools = [_make_tool("a", "Dup"), _make_tool("b", "New")]
        count = registry.register_many(tools)
        assert count == 1  # only "b" was new
        assert registry.get_tool("a").name == "Existing"

    def test_clear(self, populated_registry: ToolRegistry):
        populated_registry.clear()
        assert populated_registry.count == 0


# ── Catalog Tests ─────────────────────────────────────────────

class TestCatalog:
    def test_catalog_returns_lightweight_entries(self, populated_registry: ToolRegistry):
        catalog = populated_registry.get_tool_catalog()
        assert len(catalog) == 5
        assert all(isinstance(e, LightweightCatalogEntry) for e in catalog)

    def test_catalog_no_full_schemas_leaked(self, populated_registry: ToolRegistry):
        catalog = populated_registry.get_tool_catalog()
        for entry in catalog:
            assert not hasattr(entry, "full_schema")
            assert not hasattr(entry, "governance_rules")
            assert not hasattr(entry, "auth_type")

    def test_catalog_has_required_fields(self, populated_registry: ToolRegistry):
        catalog = populated_registry.get_tool_catalog()
        for entry in catalog:
            assert entry.id
            assert entry.name
            assert entry.category
            assert entry.light_description

    def test_empty_catalog(self, registry: ToolRegistry):
        assert registry.get_tool_catalog() == []


# ── Schema Tests ──────────────────────────────────────────────

class TestSchema:
    def test_get_full_schema(self, populated_registry: ToolRegistry):
        schema = populated_registry.get_full_schema("google_drive")
        assert schema is not None
        assert "type" in schema

    def test_full_schema_is_copy(self, populated_registry: ToolRegistry):
        """Returned schema is a copy, not a reference to internal state."""
        schema1 = populated_registry.get_full_schema("google_drive")
        schema1["injected"] = True
        schema2 = populated_registry.get_full_schema("google_drive")
        assert "injected" not in schema2

    def test_unknown_tool_schema_returns_none(self, registry: ToolRegistry):
        assert registry.get_full_schema("nonexistent") is None

    def test_total_schema_tokens_all(self, populated_registry: ToolRegistry):
        total = populated_registry.get_total_schema_tokens()
        # google_drive=200, canva=350, web_search=200, slack=200, terminal=150
        assert total == 1100

    def test_total_schema_tokens_subset(self, populated_registry: ToolRegistry):
        total = populated_registry.get_total_schema_tokens(["canva", "terminal"])
        assert total == 500  # 350 + 150

    def test_total_schema_tokens_unknown_ids_ignored(self, populated_registry: ToolRegistry):
        total = populated_registry.get_total_schema_tokens(["canva", "nonexistent"])
        assert total == 350


# ── Category Filtering ────────────────────────────────────────

class TestCategoryFiltering:
    def test_filter_by_category(self, populated_registry: ToolRegistry):
        storage = populated_registry.get_tools_by_category("storage")
        assert len(storage) == 1
        assert storage[0].id == "google_drive"

    def test_filter_case_insensitive(self, populated_registry: ToolRegistry):
        storage = populated_registry.get_tools_by_category("STORAGE")
        assert len(storage) == 1

    def test_filter_empty_category(self, populated_registry: ToolRegistry):
        assert populated_registry.get_tools_by_category("nonexistent") == []


# ── Governance Tests ──────────────────────────────────────────

class TestGovernance:
    def test_tool_allowed_no_restrictions(self, populated_registry: ToolRegistry):
        allowed, reason = populated_registry.is_tool_allowed("google_drive", "marketing")
        assert allowed is True
        assert reason == ""

    def test_tool_blocked_wrong_department(self, populated_registry: ToolRegistry):
        allowed, reason = populated_registry.is_tool_allowed("terminal", "marketing")
        assert allowed is False
        assert "not allowed" in reason
        assert "marketing" in reason

    def test_tool_allowed_correct_department(self, populated_registry: ToolRegistry):
        allowed, _ = populated_registry.is_tool_allowed("terminal", "engineering")
        assert allowed is True

    def test_unknown_tool_not_allowed(self, registry: ToolRegistry):
        allowed, reason = registry.is_tool_allowed("nonexistent", "engineering")
        assert allowed is False
        assert "not registered" in reason

    def test_requires_approval_true(self, populated_registry: ToolRegistry):
        assert populated_registry.requires_approval("terminal") is True

    def test_requires_approval_false(self, populated_registry: ToolRegistry):
        assert populated_registry.requires_approval("google_drive") is False

    def test_unknown_tool_requires_approval(self, registry: ToolRegistry):
        assert registry.requires_approval("unknown") is True


# ── Thread Safety ─────────────────────────────────────────────

class TestThreadSafety:
    def test_concurrent_registration(self, registry: ToolRegistry):
        """Multiple threads registering different tools simultaneously."""
        errors: list[Exception] = []

        def register_batch(start: int, count: int):
            try:
                for i in range(start, start + count):
                    registry.register_or_update(
                        _make_tool(f"tool_{i}", f"Tool {i}")
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_batch, args=(i * 100, 100))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert registry.count == 500

    def test_concurrent_read_write(self, populated_registry: ToolRegistry):
        """Readers and writers running simultaneously."""
        errors: list[Exception] = []
        catalogs: list[int] = []

        def reader():
            try:
                for _ in range(50):
                    cat = populated_registry.get_tool_catalog()
                    catalogs.append(len(cat))
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(50):
                    populated_registry.register_or_update(
                        _make_tool(f"new_{i}", f"New Tool {i}")
                    )
            except Exception as e:
                errors.append(e)

        t_read = threading.Thread(target=reader)
        t_write = threading.Thread(target=writer)
        t_read.start()
        t_write.start()
        t_read.join()
        t_write.join()

        assert not errors
        # All catalog sizes should be valid (between 5 and 55)
        assert all(5 <= c <= 55 for c in catalogs)


# ── Utility Tests ─────────────────────────────────────────────

class TestUtility:
    def test_all_tool_ids(self, populated_registry: ToolRegistry):
        ids = populated_registry.all_tool_ids()
        assert set(ids) == {"google_drive", "canva", "web_search", "slack", "terminal"}

    def test_count_property(self, populated_registry: ToolRegistry):
        assert populated_registry.count == 5
