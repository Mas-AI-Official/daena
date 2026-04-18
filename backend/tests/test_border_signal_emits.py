"""Tests for the remaining BorderAgent signal emits.

Covers two chokepoints added in the border-agent hardening pass:

1. ``GovernanceEngine.evaluate`` -> ``department.flagged_risk`` when a
   decision lands at tier >= 3. Peer departments (SecOps, Legal,
   Finance) use this to track risk surfacing in real time.

2. ``ApprovalService.approve()/reject()`` -> ``Legal.compliance_flag``
   when the action_type is legal-flavored (contract / nda / license /
   legal / compliance) OR the decision rejects a CRITICAL-risk request.
   Legal room gets visibility without having to poll the approvals
   table.

Fail-safe emit pattern means any emit error is swallowed -- these
tests guard the HAPPY path so a silent regression doesn't leave the
peer rooms dark.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.governance import GoaRequest
from app.models.identity import Tenant, User
from app.services.approval import ApprovalService
from app.services.departments.border_agent import (
    DepartmentEvent,
    get_border_agent,
    reset_registry,
)
from app.services.governance import GovernanceEngine


# ── Fixtures ──


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    """Insert the FK target row so GoaRequest / related inserts succeed."""
    tenant = Tenant(
        id=test_tenant_id,
        name="SignalEmitTestOrg",
        slug=f"sig-{uuid.uuid4().hex[:6]}",
    )
    db_session.add(tenant)
    await db_session.flush()
    return test_tenant_id


# ── Helpers ──


async def _seed_user(db, tenant_id: uuid.UUID) -> uuid.UUID:
    """Create a real User row -- GoaRequest.user_id has a NOT NULL FK
    that cannot be satisfied by a random uuid."""
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=f"signal-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Signal Test User",
        password_hash="unused",
        role="OPERATOR",
    )
    db.add(user)
    await db.flush()
    return user.id


async def _seed_approval_request(
    db,
    tenant_id: uuid.UUID,
    *,
    action_type: str,
    risk_level: str = "HIGH",
    governance_tier: int = 3,
) -> GoaRequest:
    """Persist a GoaRequest so ApprovalService.approve / reject has
    something to act on. Requires a valid User FK."""
    user_id = await _seed_user(db, tenant_id)
    request = GoaRequest(
        tenant_id=tenant_id,
        user_id=user_id,
        action_type=action_type,
        action_params={},
        risk_level=risk_level,
        governance_tier=governance_tier,
        status="PENDING",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db.add(request)
    await db.flush()
    return request


# ── department.flagged_risk via GovernanceEngine.evaluate ──


class TestFlaggedRiskEmit:
    @pytest.mark.asyncio
    async def test_tier_3_action_emits_flagged_risk(
        self, db_session, seeded_tenant, test_user_id
    ) -> None:
        """A HIGH-risk DEPLOY under GOVERNED mode lands at tier 3, which
        should trigger the flagged_risk emit so peer rooms see the risk.
        Finance is in DEPARTMENT_RELEVANCE for department.flagged_risk,
        so its BorderAgent is the correct listener to assert against.
        """
        await reset_registry()
        finance = await get_border_agent(
            tenant_id=seeded_tenant, department="Finance"
        )
        finance.clear()

        engine = GovernanceEngine(db_session)
        result = await engine.evaluate(
            action_type="DEPLOY",
            action_params={"timeout": 60},
            governance_slider="GOVERNED",
            actor_type="AGENT",
            actor_role="OPERATOR",
            tenant_id=seeded_tenant,
            user_id=test_user_id,
        )
        assert result["governance_tier"] >= 3

        types = [s.get("event_type") for s in finance.recent_signals(limit=5)]
        assert DepartmentEvent.FLAGGED_RISK in types, (
            f"Finance should see flagged_risk for tier-3 DEPLOY, got: {types}"
        )

    @pytest.mark.asyncio
    async def test_tier_0_action_does_not_emit_flagged_risk(
        self, db_session, seeded_tenant, test_user_id
    ) -> None:
        """A low-risk READ under UNLEASHED stays below tier 3 -- no
        flagged_risk emit. Protects the feed from noise."""
        await reset_registry()
        finance = await get_border_agent(
            tenant_id=seeded_tenant, department="Finance"
        )
        finance.clear()

        engine = GovernanceEngine(db_session)
        result = await engine.evaluate(
            action_type="READ",
            action_params={},
            governance_slider="UNLEASHED",
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=seeded_tenant,
            user_id=test_user_id,
        )
        assert result["governance_tier"] < 3

        types = [s.get("event_type") for s in finance.recent_signals(limit=5)]
        assert DepartmentEvent.FLAGGED_RISK not in types, (
            f"Low-tier action should NOT emit flagged_risk, got: {types}"
        )


# ── Legal.compliance_flag via ApprovalService ──


class TestComplianceFlagEmit:
    @pytest.mark.asyncio
    async def test_legal_action_type_emits_compliance_flag(
        self, db_session, seeded_tenant
    ) -> None:
        """action_type containing 'contract' routes to Legal regardless
        of approve/reject outcome -- Legal has to track all
        contract-flavored decisions."""
        await reset_registry()
        legal = await get_border_agent(
            tenant_id=seeded_tenant, department="Legal & Compliance"
        )
        legal.clear()

        req = await _seed_approval_request(
            db_session, seeded_tenant,
            action_type="sign_contract",
            risk_level="HIGH",
            governance_tier=3,
        )

        decider_id = await _seed_user(db_session, seeded_tenant)
        service = ApprovalService(db_session)
        await service.approve(
            request_id=req.id,
            tenant_id=seeded_tenant,
            decided_by=decider_id,
            reason="standard NDA terms",
        )

        types = [s.get("event_type") for s in legal.recent_signals(limit=5)]
        assert DepartmentEvent.COMPLIANCE_FLAG in types, (
            f"Legal room should see compliance_flag for sign_contract, "
            f"got: {types}"
        )

    @pytest.mark.asyncio
    async def test_critical_reject_emits_compliance_flag(
        self, db_session, seeded_tenant
    ) -> None:
        """A CRITICAL-risk rejection fires compliance_flag even for
        non-legal action types -- those usually have a compliance
        follow-up regardless of wording."""
        await reset_registry()
        legal = await get_border_agent(
            tenant_id=seeded_tenant, department="Legal & Compliance"
        )
        legal.clear()

        req = await _seed_approval_request(
            db_session, seeded_tenant,
            action_type="send_external_comms",
            risk_level="CRITICAL",
            governance_tier=4,
        )

        decider_id = await _seed_user(db_session, seeded_tenant)
        service = ApprovalService(db_session)
        await service.reject(
            request_id=req.id,
            tenant_id=seeded_tenant,
            decided_by=decider_id,
            reason="brand risk too high",
        )

        types = [s.get("event_type") for s in legal.recent_signals(limit=5)]
        assert DepartmentEvent.COMPLIANCE_FLAG in types, (
            f"Legal room should see compliance_flag for CRITICAL reject, "
            f"got: {types}"
        )

    @pytest.mark.asyncio
    async def test_standard_approve_does_not_emit_compliance_flag(
        self, db_session, seeded_tenant
    ) -> None:
        """An ordinary HIGH-risk non-legal approval should NOT spam the
        Legal room -- only legal-flavored or CRITICAL-reject events do.
        This keeps the Legal feed high-signal."""
        await reset_registry()
        legal = await get_border_agent(
            tenant_id=seeded_tenant, department="Legal & Compliance"
        )
        legal.clear()

        req = await _seed_approval_request(
            db_session, seeded_tenant,
            action_type="bulk_delete",
            risk_level="HIGH",
            governance_tier=3,
        )

        decider_id = await _seed_user(db_session, seeded_tenant)
        service = ApprovalService(db_session)
        await service.approve(
            request_id=req.id,
            tenant_id=seeded_tenant,
            decided_by=decider_id,
            reason="approved by ops",
        )

        types = [s.get("event_type") for s in legal.recent_signals(limit=5)]
        assert DepartmentEvent.COMPLIANCE_FLAG not in types, (
            f"Legal room should NOT see compliance_flag for ordinary "
            f"HIGH approve, got: {types}"
        )
