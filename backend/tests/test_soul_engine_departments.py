"""Tests for the Department Mind overlay in SoulEngine.

Validates that:
- All 10 Department Minds have soul files with valid frontmatter.
- The alias resolver accepts DB names, snake_case, and Mind names.
- ``get_soul_prompt`` composes core soul + dept overlay + governance
  addendum in the right order.
- ``get_department_metadata`` surfaces the runtime / voice / tools.
- Missing departments degrade silently to core-soul-only.
- Reload clears both caches.
"""

from __future__ import annotations

import pytest

from app.services.soul_engine import (
    SoulEngine,
    _load_department_soul,
    _normalize_department,
    _parse_frontmatter,
)


# Every row is (alias, expected_slug, expected_mind_name).
_ALIASES = [
    ("engineering", "engineering", "Aria"),
    ("Engineering", "engineering", "Aria"),
    ("aria", "engineering", "Aria"),
    ("ENG", "engineering", "Aria"),
    ("product", "product", "Nova"),
    ("Nova", "product", "Nova"),
    ("marketing", "marketing", "Zephyr"),
    ("Zephyr", "marketing", "Zephyr"),
    ("sales", "sales", "Orion"),
    ("Orion", "sales", "Orion"),
    ("finance", "finance", "Sterling"),
    ("Sterling", "finance", "Sterling"),
    ("operations", "operations", "Atlas"),
    ("Atlas", "operations", "Atlas"),
    ("research", "research", "Iris"),
    ("Iris", "research", "Iris"),
    ("Legal & Compliance", "legal_compliance", "Themis"),
    ("legal_compliance", "legal_compliance", "Themis"),
    ("Themis", "legal_compliance", "Themis"),
    ("Skill Governance", "skill_governance", "Kira"),
    ("Kira", "skill_governance", "Kira"),
    ("Security Operations", "security_operations", "Rourke"),
    ("security", "security_operations", "Rourke"),
    ("Rourke", "security_operations", "Rourke"),
]


@pytest.mark.parametrize("alias,expected_slug,_expected_name", _ALIASES)
def test_normalize_department_aliases(alias: str, expected_slug: str, _expected_name: str) -> None:
    """Any valid alias resolves to the canonical slug."""
    assert _normalize_department(alias) == expected_slug


def test_normalize_department_unknown_returns_none() -> None:
    assert _normalize_department("marketing_ops") is None
    assert _normalize_department("") is None
    assert _normalize_department(None) is None


def test_all_ten_department_souls_present() -> None:
    """Every department in the canonical list has a well-formed soul."""
    expected_slugs = {
        "engineering", "product", "marketing", "sales", "finance",
        "operations", "research", "legal_compliance", "skill_governance",
        "security_operations",
    }
    departments = SoulEngine.list_departments()
    slugs = {d["slug"] for d in departments}
    assert expected_slugs.issubset(slugs), (
        f"Missing souls: {expected_slugs - slugs}"
    )


@pytest.mark.parametrize("alias,expected_slug,expected_name", _ALIASES)
def test_department_metadata_loads_all_required_fields(
    alias: str, expected_slug: str, expected_name: str,
) -> None:
    """Each soul exposes name, runtime_preference, voice, color, and tools."""
    meta = SoulEngine.get_department_metadata(alias)
    assert meta, f"no metadata for {alias!r}"
    assert meta["name"] == expected_name
    assert meta["department"] == expected_slug
    assert meta.get("runtime_preference"), f"{alias}: missing runtime_preference"
    assert meta.get("voice"), f"{alias}: missing voice profile"
    assert meta.get("accent_color"), f"{alias}: missing accent_color"
    tools = meta.get("tools_enabled") or []
    assert isinstance(tools, list) and tools, f"{alias}: tools_enabled must be a non-empty list"


def test_get_soul_prompt_with_department_includes_overlay_marker() -> None:
    """Composite prompt contains the core soul AND the department overlay."""
    prompt = SoulEngine.get_soul_prompt("GOVERNED", department="engineering")
    assert prompt, "soul prompt should not be empty"
    # Core soul (always present)
    assert "Daena" in prompt
    # Overlay header we inject in SoulEngine
    assert "DEPARTMENT MIND OVERLAY" in prompt
    # Specific Mind content
    assert "Aria" in prompt
    # Governance addendum
    assert "GOVERNED MODE ACTIVE" in prompt


def test_get_soul_prompt_without_department_has_no_overlay() -> None:
    """Unscoped chats get core soul + governance only; no overlay header."""
    prompt = SoulEngine.get_soul_prompt("GOVERNED")
    assert prompt, "soul prompt should not be empty"
    assert "DEPARTMENT MIND OVERLAY" not in prompt


def test_get_soul_prompt_with_unknown_department_degrades_silently() -> None:
    """An unknown department must not crash -- degrade to core soul."""
    prompt = SoulEngine.get_soul_prompt("GOVERNED", department="ghost_department")
    assert prompt, "must still return core soul"
    assert "DEPARTMENT MIND OVERLAY" not in prompt


def test_governance_mode_switches_addendum() -> None:
    unleashed = SoulEngine.get_soul_prompt("UNLEASHED")
    balanced = SoulEngine.get_soul_prompt("BALANCED")
    governed = SoulEngine.get_soul_prompt("GOVERNED")
    assert "UNLEASHED MODE ACTIVE" in unleashed
    assert "BALANCED MODE ACTIVE" in balanced
    assert "GOVERNED MODE ACTIVE" in governed
    # Mutual exclusivity
    assert "BALANCED MODE ACTIVE" not in unleashed
    assert "UNLEASHED MODE ACTIVE" not in balanced


def test_parse_frontmatter_handles_inline_list_and_quoted_strings() -> None:
    sample = (
        "---\n"
        "name: Aria\n"
        "runtime_preference: claude_code\n"
        "fallback_runtimes: [codex, gemini_cli]\n"
        "accent_color: \"#3B82F6\"\n"
        "temperature: 0.3\n"
        "---\n\n"
        "# Body\n"
    )
    meta, body = _parse_frontmatter(sample)
    assert meta["name"] == "Aria"
    assert meta["runtime_preference"] == "claude_code"
    assert meta["fallback_runtimes"] == ["codex", "gemini_cli"]
    assert meta["accent_color"] == "#3B82F6"
    assert meta["temperature"] == "0.3"  # bare scalars come back as strings
    assert "# Body" in body


def test_reload_clears_dept_cache() -> None:
    """SoulEngine.reload must flush both the core and dept lru_caches."""
    # Warm cache
    SoulEngine.get_department_metadata("engineering")
    assert _load_department_soul.cache_info().currsize >= 1
    SoulEngine.reload()
    assert _load_department_soul.cache_info().currsize == 0
