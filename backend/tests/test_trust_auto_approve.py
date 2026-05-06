"""Sprint-18 PR-3 -- trust auto-approval helper contract.

Pins:
  1. Forbidden tool NEVER auto-approves (tool_id in TRUST_FORBIDDEN_TOOLS).
  2. Non-operator initiator NEVER auto-approves.
  3. Eligible tool with all walls passing -> approval mutated to
     status=APPROVED with decision_reason='trust_graduated:<class>'.
  4. Auto-approve does NOT touch trust_ladder counters.
  5. Helper NEVER raises even when payload missing or malformed.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.governance import GoaRequest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    from app.services import trust_ladder, trust_policy

    monkeypatch.setattr(
        trust_ladder, "_LADDER_FILE", tmp_path / ".trust_ladder.json",
    )
    monkeypatch.setattr(
        trust_policy, "_POLICY_FILE", tmp_path / ".trust_policy.json",
    )
    yield


def _make_approval(tool_id: str, tenant_id: uuid.UUID, user_id: uuid.UUID) -> GoaRequest:
    return GoaRequest(
        tenant_id=tenant_id,
        user_id=user_id,
        action_type=tool_id,
        action_params=None,
        risk_level="LOW",
        governance_tier=2,
        status="PENDING",
    )


async def _seed_tenant_user(db_session, tenant_id, user_id):
    from app.models.identity import Tenant, User

    tenant = Tenant(
        id=tenant_id, name="Sprint-18 Test Tenant", slug="sprint18-test",
    )
    db_session.add(tenant)
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="founder@example.com",
        password_hash="$argon2id$test$placeholder",
        display_name="Founder",
        role="FOUNDER",
    )
    db_session.add(user)
    await db_session.flush()


class TestForbiddenToolNeverAutoApproves:
    @pytest.mark.parametrize("forbidden_tool", [
        "gmail.send_existing_draft",
        "local.file_change_proposal.apply",
        "local.git_commit_approved_patch",
    ])
    async def test_each_forbidden_tool(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
        forbidden_tool,
    ):
        from app.services.trust_auto_approve import (
            maybe_apply_trust_auto_approval,
        )
        from app.services.trust_policy import DispatchInitiator

        await _seed_tenant_user(db_session, test_tenant_id, test_user_id)

        approval = _make_approval(
            forbidden_tool, test_tenant_id, test_user_id,
        )
        db_session.add(approval)
        await db_session.flush()

        decision = await maybe_apply_trust_auto_approval(
            db_session,
            approval=approval,
            payload={"foo": "bar"},
            initiator=DispatchInitiator.OPERATOR,
            decided_by=test_user_id,
        )

        assert decision.auto_approve is False
        assert decision.reason == "tool_forbidden_from_graduation"
        assert approval.status == "PENDING"
        assert approval.decision_reason is None


class TestNonOperatorInitiatorNeverAutoApproves:
    async def test_scheduler_blocked_even_when_policy_open(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services import trust_ladder
        from app.services.trust_auto_approve import (
            maybe_apply_trust_auto_approval,
        )
        from app.services.trust_policy import (
            DispatchInitiator, TrustTier, set_max_auto_tier,
            compute_template_class,
        )

        payload = {"to": ["a@b.com"], "subject": "campaign launch"}
        tc = compute_template_class("gmail.create_draft", payload)
        for _ in range(5):
            trust_ladder.record_decision(
                tool_id="gmail.create_draft",
                template_id=tc,
                decision="approved",
            )
        set_max_auto_tier(
            tool_id="gmail.create_draft",
            template_class=tc,
            tier=TrustTier.AUTO_APPROVE_LOW_RISK,
            requested_by_user_id="founder",
            is_founder=True,
            confirmation_phrase=(
                "I authorize trust tier auto_approve_low_risk for "
                "gmail.create_draft"
            ),
        )

        await _seed_tenant_user(db_session, test_tenant_id, test_user_id)

        approval = _make_approval(
            "gmail.create_draft", test_tenant_id, test_user_id,
        )
        db_session.add(approval)
        await db_session.flush()

        decision = await maybe_apply_trust_auto_approval(
            db_session,
            approval=approval,
            payload=payload,
            initiator=DispatchInitiator.SCHEDULER,  # NOT operator
            decided_by=test_user_id,
        )

        assert decision.auto_approve is False
        assert decision.reason == "non_operator_initiator_never_graduates"
        assert approval.status == "PENDING"


class TestHappyPath:
    async def test_all_walls_pass_mutates_approval(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services import trust_ladder
        from app.services.trust_auto_approve import (
            maybe_apply_trust_auto_approval,
        )
        from app.services.trust_policy import (
            DispatchInitiator, TrustTier, set_max_auto_tier,
            compute_template_class,
        )

        payload = {"to": ["alice@gmail.com"], "subject": "Welcome aboard"}
        tc = compute_template_class("gmail.create_draft", payload)
        for _ in range(5):
            trust_ladder.record_decision(
                tool_id="gmail.create_draft",
                template_id=tc,
                decision="approved",
            )
        set_max_auto_tier(
            tool_id="gmail.create_draft",
            template_class=tc,
            tier=TrustTier.AUTO_APPROVE_LOW_RISK,
            requested_by_user_id="founder",
            is_founder=True,
            confirmation_phrase=(
                "I authorize trust tier auto_approve_low_risk for "
                "gmail.create_draft"
            ),
        )

        # Snapshot ladder counter pre-call -- must NOT change.
        before = trust_ladder.get_entry(
            tool_id="gmail.create_draft", template_id=tc,
        )
        assert before is not None
        approvals_before = before.approvals_count

        await _seed_tenant_user(db_session, test_tenant_id, test_user_id)

        approval = _make_approval(
            "gmail.create_draft", test_tenant_id, test_user_id,
        )
        db_session.add(approval)
        await db_session.flush()

        decision = await maybe_apply_trust_auto_approval(
            db_session,
            approval=approval,
            payload=payload,
            initiator=DispatchInitiator.OPERATOR,
            decided_by=test_user_id,
        )

        assert decision.auto_approve is True
        assert decision.reason == "trust_graduated"
        assert approval.status == "APPROVED"
        assert approval.decided_by == test_user_id
        assert approval.decided_at is not None
        assert approval.decision_reason is not None
        assert approval.decision_reason.startswith("trust_graduated:")

        # Ladder counters MUST be unchanged -- auto-approval does
        # not record fake operator decisions.
        after = trust_ladder.get_entry(
            tool_id="gmail.create_draft", template_id=tc,
        )
        assert after is not None
        assert after.approvals_count == approvals_before


class TestNeverRaises:
    async def test_missing_payload_does_not_raise(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.trust_auto_approve import (
            maybe_apply_trust_auto_approval,
        )
        from app.services.trust_policy import DispatchInitiator

        await _seed_tenant_user(db_session, test_tenant_id, test_user_id)

        approval = _make_approval(
            "gmail.create_draft", test_tenant_id, test_user_id,
        )
        db_session.add(approval)
        await db_session.flush()

        # Empty payload -- should NOT auto-approve and NOT raise.
        decision = await maybe_apply_trust_auto_approval(
            db_session,
            approval=approval,
            payload={},
            initiator=DispatchInitiator.OPERATOR,
            decided_by=test_user_id,
        )
        assert decision.auto_approve is False
        assert approval.status == "PENDING"

    async def test_unknown_tool_does_not_auto_approve(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.trust_auto_approve import (
            maybe_apply_trust_auto_approval,
        )
        from app.services.trust_policy import DispatchInitiator

        await _seed_tenant_user(db_session, test_tenant_id, test_user_id)

        approval = _make_approval(
            "totally.unknown.tool", test_tenant_id, test_user_id,
        )
        db_session.add(approval)
        await db_session.flush()

        decision = await maybe_apply_trust_auto_approval(
            db_session,
            approval=approval,
            payload={"x": 1},
            initiator=DispatchInitiator.OPERATOR,
            decided_by=test_user_id,
        )
        assert decision.auto_approve is False
        assert decision.reason == "tool_not_in_eligible_set"
        assert approval.status == "PENDING"
