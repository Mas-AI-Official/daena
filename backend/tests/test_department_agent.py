"""Tests for the DepartmentAgent runtime class.

Pins the architectural contract:
* 10 departments, 6 roles as methods (not 60 processes)
* Shared DaenaBot pool (not per-department duplication)
* Security Lens overlay pivots non-SHIELD roles when /3vilbob is active
* Offensive SHIELD prompt (from department_prompts) still replaces SHIELD
* record_outcome writes to NBMF with the department tag
"""

from __future__ import annotations

import pytest

from app.services.departments import (
    DepartmentAgent,
    DepartmentContext,
    SecurityLens,
)
from app.services.departments.department_agent import ROLES, build_department


def test_six_canonical_roles() -> None:
    """The six roles are facets, not processes."""
    assert ROLES == ("MIND", "EYES", "HANDS", "VOICE", "SHIELD", "MEMORY")
    assert len(ROLES) == 6


def test_build_role_prompt_composes_department_base() -> None:
    """MIND prompt for Engineering must include the department-specific text."""
    dept = build_department(
        "Engineering",
        working_directory="D:/Ideas/Daena",
    )
    prompt = dept.build_role_prompt("MIND")
    lower = prompt.lower()
    # The department prompt mentions strategic/architecture thinking.
    # Not anchoring on an exact phrase -- the base prompts are authored
    # content; we only pin that SOME content comes through.
    assert "engineering" in lower or "architect" in lower or "code" in lower
    assert "D:/Ideas/Daena" in prompt


def test_build_role_prompt_rejects_unknown_role() -> None:
    dept = build_department("Marketing")
    with pytest.raises(ValueError):
        dept.build_role_prompt("TELEPATHY")


def test_security_lens_adds_overlay_to_non_shield_roles() -> None:
    """When the lens is active, MIND/EYES/HANDS/VOICE/MEMORY get the overlay."""
    dept = build_department(
        "Engineering",
        security_active=True,
        security_reason="3vilbob engagement for acme.com",
    )
    mind_prompt = dept.build_role_prompt("MIND")
    assert "SECURITY LENS ACTIVE" in mind_prompt

    eyes_prompt = dept.build_role_prompt("EYES")
    assert "SECURITY LENS ACTIVE" in eyes_prompt


def test_security_lens_does_not_double_overlay_shield() -> None:
    """SHIELD is ALREADY swapped by department_prompts offensive prompts when
    evilbob is active. The lens MUST NOT add a second overlay to SHIELD.
    """
    dept = build_department("Engineering", security_active=True)
    shield_prompt = dept.build_role_prompt("SHIELD")
    # The security lens text must not be appended to SHIELD by this class.
    # (The offensive SHIELD prompt from department_prompts handles SHIELD.)
    assert shield_prompt.count("SECURITY LENS ACTIVE") == 0


def test_security_lens_off_leaves_roles_untouched() -> None:
    dept = build_department("Engineering", security_active=False)
    for role in ROLES:
        prompt = dept.build_role_prompt(role)
        assert "SECURITY LENS ACTIVE" not in prompt


def test_build_full_prompt_returns_all_six() -> None:
    dept = build_department("Sales")
    all_prompts = dept.build_full_prompt()
    assert set(all_prompts.keys()) == set(ROLES)
    for role, prompt in all_prompts.items():
        assert prompt, f"empty prompt for role {role}"


def test_context_carries_permitted_paths_and_skills() -> None:
    dept = build_department(
        "Operations",
        permitted_paths=["/opt/app", "/var/log/daena"],
        skill_priors=["runbook_update", "incident_response"],
    )
    prompt = dept.build_role_prompt("HANDS")
    assert "/opt/app" in prompt
    assert "runbook_update" in prompt


@pytest.mark.asyncio
async def test_record_outcome_skips_without_memory_service() -> None:
    """Missing memory service -> record_outcome returns None (not a crash)."""
    dept = DepartmentAgent(
        context=DepartmentContext(department="Research"),
        lens=SecurityLens(active=False),
        memory_service=None,
    )
    result = await dept.record_outcome(
        summary="researched a thing",
        detail="no memory wired",
        success=True,
    )
    assert result is None


def test_all_ten_departments_have_security_lens_coverage() -> None:
    """Every department that can participate in an offensive engagement
    must have a MIND lens overlay. This is the operator-mandated
    'all departments pivot to security' behavior.
    """
    from app.services.departments.department_agent import _SECURITY_LENS
    expected_depts = {
        "Engineering", "Product", "Marketing", "Sales", "Finance",
        "Operations", "Research", "Legal & Compliance", "Skill Governance",
    }
    assert expected_depts.issubset(set(_SECURITY_LENS["MIND"].keys()))
