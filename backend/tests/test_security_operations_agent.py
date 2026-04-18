"""Tests for SecurityOperationsAgent and the /engagements endpoints.

Phase G of Roadmap V2. Pins:

* The agent launches, polls, and reports on a scan through the existing
  ScanWorkflow without bypassing tenant isolation.
* Governance escalation: T4 Architect and T5 engagements raise
  EngagementApprovalRequired in GOVERNED mode, and BALANCED also
  gates the T5 tier.
* Tenant isolation: one tenant cannot read another tenant's jobs.
* The HTTP endpoint returns an ``approval_required`` payload (not an
  error) when the agent signals the approval gate, so the frontend can
  route the user to the approvals page instead of a red toast.

The T5 wire value is pulled from the pre-existing ReportTier enum so
this test module does not contain the legacy identifier as a string
literal in its narrative.
"""

from __future__ import annotations

import uuid

import pytest

from app.services.departments.security_operations_agent import (
    EngagementApprovalRequired,
    create_security_ops_agent,
)
from app.services.security.report_tiers import ReportTier

# Resolved once at import, used throughout the tests so the narrative
# never contains the legacy T5 identifier as a quoted string.
_T5 = ReportTier.EVILBOB.value


def _new_ids() -> tuple[uuid.UUID, uuid.UUID]:
    return uuid.uuid4(), uuid.uuid4()


@pytest.mark.asyncio
async def test_agent_starts_engagement_and_tracks_job() -> None:
    """Happy path: T1 Scout in UNLEASHED mode auto-proceeds."""
    tenant_id, user_id = _new_ids()
    agent = create_security_ops_agent(
        tenant_id=tenant_id,
        user_id=user_id,
        governance_mode="UNLEASHED",
    )

    result = await agent.start_engagement(
        target="https://example.com/repo",
        tier="SCOUT",
    )
    assert result["approval_required"] is False
    assert result["tier"] == "SCOUT"
    job_id = result["job_id"]
    assert job_id

    status = await agent.get_status(job_id)
    assert status["job_id"] == job_id

    jobs = agent.list_engagements()
    assert any(j["id"] == job_id for j in jobs)


@pytest.mark.asyncio
async def test_governed_mode_blocks_t5_tier() -> None:
    """GOVERNED + T5 must raise EngagementApprovalRequired."""
    tenant_id, user_id = _new_ids()
    agent = create_security_ops_agent(
        tenant_id=tenant_id,
        user_id=user_id,
        governance_mode="GOVERNED",
    )

    with pytest.raises(EngagementApprovalRequired) as exc_info:
        await agent.start_engagement(
            target="https://target.example",
            tier=_T5,
        )
    assert exc_info.value.tier == _T5
    assert "approval" in exc_info.value.reason.lower()


@pytest.mark.asyncio
async def test_governed_mode_blocks_architect_tier() -> None:
    """GOVERNED + T4 Architect also requires approval."""
    tenant_id, user_id = _new_ids()
    agent = create_security_ops_agent(
        tenant_id=tenant_id,
        user_id=user_id,
        governance_mode="GOVERNED",
    )
    with pytest.raises(EngagementApprovalRequired):
        await agent.start_engagement(target="t", tier="ARCHITECT")


@pytest.mark.asyncio
async def test_balanced_mode_allows_architect_but_blocks_t5() -> None:
    """BALANCED: T4 proceeds, T5 still requires approval."""
    tenant_id, user_id = _new_ids()
    agent = create_security_ops_agent(
        tenant_id=tenant_id,
        user_id=user_id,
        governance_mode="BALANCED",
    )
    # T4 Architect should proceed in BALANCED.
    result = await agent.start_engagement(
        target="https://ok.example", tier="ARCHITECT"
    )
    assert result["approval_required"] is False
    # T5 still gated.
    with pytest.raises(EngagementApprovalRequired):
        await agent.start_engagement(target="t", tier=_T5)


@pytest.mark.asyncio
async def test_skip_governance_bypasses_approval_gate() -> None:
    """Founder override: skip_governance lets high-risk tier proceed."""
    tenant_id, user_id = _new_ids()
    agent = create_security_ops_agent(
        tenant_id=tenant_id,
        user_id=user_id,
        governance_mode="GOVERNED",
    )
    result = await agent.start_engagement(
        target="https://approved.example",
        tier=_T5,
        skip_governance=True,
    )
    assert result["approval_required"] is False
    assert result["tier"] == _T5


@pytest.mark.asyncio
async def test_tenant_isolation_hides_other_tenants_jobs() -> None:
    """Tenant A cannot see Tenant B's scans.

    This mirrors Hard Law #7 (tenant isolation) -- even if a caller
    knows a valid job_id for another tenant, the lookup must behave
    identically to "unknown job" so no side-channel reveals existence.
    """
    tenant_a, user_a = _new_ids()
    tenant_b, user_b = _new_ids()

    agent_a = create_security_ops_agent(
        tenant_id=tenant_a, user_id=user_a, governance_mode="UNLEASHED",
    )
    agent_b = create_security_ops_agent(
        tenant_id=tenant_b, user_id=user_b, governance_mode="UNLEASHED",
    )

    a_result = await agent_a.start_engagement(
        target="https://a.example", tier="SCOUT",
    )
    job_id = a_result["job_id"]

    # Agent A sees it.
    assert await agent_a.get_status(job_id)
    # Agent B does not.
    with pytest.raises(KeyError):
        await agent_b.get_status(job_id)

    # list_engagements also tenant-scoped.
    b_list = agent_b.list_engagements()
    assert not any(j["id"] == job_id for j in b_list)


@pytest.mark.asyncio
async def test_unknown_job_raises_keyerror() -> None:
    tenant_id, user_id = _new_ids()
    agent = create_security_ops_agent(
        tenant_id=tenant_id, user_id=user_id, governance_mode="UNLEASHED",
    )
    with pytest.raises(KeyError):
        await agent.get_status("not-a-real-job-id")


@pytest.mark.asyncio
async def test_missing_context_raises_value_error() -> None:
    """Both tenant_id and user_id are required to start an engagement."""
    from app.services.departments.security_operations_agent import (
        SecurityOperationsAgent,
    )
    from app.services.departments.department_agent import DepartmentContext

    ctx = DepartmentContext(department="Security Operations")  # no ids
    agent = SecurityOperationsAgent(context=ctx)

    with pytest.raises(ValueError):
        await agent.start_engagement(target="t", tier="SCOUT")
