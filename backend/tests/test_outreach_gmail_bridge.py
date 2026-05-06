"""Sprint-19 PR-4 -- outreach -> Gmail draft bridge contract.

Pins:
  1. Unknown outreach_draft_id refuses with stable code.
  2. Draft status != 'drafted' refuses.
  3. Missing Gmail OAuth refuses with gmail_oauth_not_ready.
  4. With OAuth ready, returns approval_id + payload_hash + payload.
  5. With trust ladder NOT graduated, auto_approved=False.
  6. With trust ladder GRADUATED for this template_class,
     auto_approved=True; approval row status flips to APPROVED.
  7. Scheduler-initiated dispatch never auto-approves even when
     trust would have graduated for OPERATOR.
  8. Bridge NEVER raises.
"""

from __future__ import annotations

import json
import uuid

import pytest


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


async def _seed_full_environment(
    db_session, tenant_id, user_id,
    *,
    with_gmail_oauth=True,
):
    from sqlalchemy import select
    from app.models.connections import Connector, ConnectorInstance
    from app.models.identity import Tenant, User

    if (await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id),
    )).scalar_one_or_none() is None:
        import uuid as _uuid
        tenant = Tenant(
            id=tenant_id, name="T",
            slug=f"sprint19-pr4-{_uuid.uuid4().hex[:6]}",
        )
        db_session.add(tenant)
    if (await db_session.execute(
        select(User).where(User.id == user_id),
    )).scalar_one_or_none() is None:
        user = User(
            id=user_id, tenant_id=tenant_id,
            email=f"founder-{user_id}@test.local",
            password_hash="$argon2id$test$placeholder",
            display_name="Founder", role="FOUNDER",
        )
        db_session.add(user)
    await db_session.flush()

    if with_gmail_oauth:
        conn = (await db_session.execute(
            select(Connector).where(Connector.name == "Gmail"),
        )).scalar_one_or_none()
        if conn is None:
            conn = Connector(
                id=uuid.uuid4(), name="Gmail",
                description="Gmail integration",
                category="email", auth_type="oauth2",
            )
            db_session.add(conn)
            await db_session.flush()
        instance = ConnectorInstance(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            connector_id=conn.id,
            owner_email="founder@gmail.com",
            credentials={"access_token": "fake-token-for-test"},
            status="active",
        )
        db_session.add(instance)
        await db_session.flush()


async def _make_draft(db_session, tenant_id, user_id, *, status="drafted"):
    from app.models.business import BizOutreachDraft

    draft = BizOutreachDraft(
        tenant_id=tenant_id,
        user_id=user_id,
        opportunity_id=None,
        draft_kind="customer_cold_email",
        recipient_email="prospect@externalcorp.com",
        subject="Test subject",
        body="Hello there.",
        payload_hash="0" * 64,
        needs_review=True,
        confidence=50,
        status=status,
    )
    db_session.add(draft)
    await db_session.flush()
    return draft


# ────────────────────────────────────────────────────────────────────


class TestRefusals:
    async def test_unknown_outreach_draft(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach.gmail_bridge import (
            queue_gmail_draft_creation,
        )

        await _seed_full_environment(db_session, test_tenant_id, test_user_id)
        result = await queue_gmail_draft_creation(
            db_session,
            outreach_draft_id=uuid.uuid4(),
            owner_email="founder@gmail.com",
            tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert result.success is False
        assert result.refusal_code == "outreach_draft_not_found"

    async def test_draft_status_not_drafted(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach.gmail_bridge import (
            queue_gmail_draft_creation,
        )

        await _seed_full_environment(db_session, test_tenant_id, test_user_id)
        draft = await _make_draft(
            db_session, test_tenant_id, test_user_id,
            status="blocked_recipient",
        )
        result = await queue_gmail_draft_creation(
            db_session,
            outreach_draft_id=draft.id,
            owner_email="founder@gmail.com",
            tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert result.success is False
        assert "draft_status_not_drafted" in result.refusal_code

    async def test_missing_oauth(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach.gmail_bridge import (
            queue_gmail_draft_creation,
        )

        # No Gmail oauth seeded
        await _seed_full_environment(
            db_session, test_tenant_id, test_user_id,
            with_gmail_oauth=False,
        )
        draft = await _make_draft(db_session, test_tenant_id, test_user_id)
        result = await queue_gmail_draft_creation(
            db_session,
            outreach_draft_id=draft.id,
            owner_email="founder@gmail.com",
            tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert result.success is False
        assert result.refusal_code == "gmail_oauth_not_ready"


class TestSuccessPath:
    async def test_pending_when_trust_not_graduated(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach.gmail_bridge import (
            queue_gmail_draft_creation,
        )

        await _seed_full_environment(db_session, test_tenant_id, test_user_id)
        draft = await _make_draft(db_session, test_tenant_id, test_user_id)
        result = await queue_gmail_draft_creation(
            db_session,
            outreach_draft_id=draft.id,
            owner_email="founder@gmail.com",
            tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert result.success is True
        assert result.approval_id is not None
        assert result.auto_approved is False
        assert result.payload_hash
        assert result.payload["to"] == "prospect@externalcorp.com"

        # Draft advanced to queued_create_draft
        await db_session.refresh(draft)
        assert draft.status == "queued_create_draft"
        assert draft.create_draft_approval_id is not None

    async def test_auto_approves_when_trust_graduated(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services import trust_ladder
        from app.services.outreach.draft_factory import compute_payload_hash
        from app.services.outreach.gmail_bridge import (
            queue_gmail_draft_creation,
        )
        from app.services.trust_policy import (
            TrustTier, set_max_auto_tier, compute_template_class,
        )

        await _seed_full_environment(db_session, test_tenant_id, test_user_id)
        draft = await _make_draft(db_session, test_tenant_id, test_user_id)

        # Compute the expected template_class given the payload that
        # the bridge will build, then graduate trust for that class.
        payload = {
            "to": "prospect@externalcorp.com",
            "subject": "Test subject",
            "body": "Hello there.",
        }
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

        result = await queue_gmail_draft_creation(
            db_session,
            outreach_draft_id=draft.id,
            owner_email="founder@gmail.com",
            tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert result.success is True
        assert result.auto_approved is True

    async def test_scheduler_initiator_never_graduates(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services import trust_ladder
        from app.services.outreach.gmail_bridge import (
            queue_gmail_draft_creation,
        )
        from app.services.trust_policy import (
            DispatchInitiator, TrustTier, set_max_auto_tier,
            compute_template_class,
        )

        await _seed_full_environment(db_session, test_tenant_id, test_user_id)
        draft = await _make_draft(db_session, test_tenant_id, test_user_id)
        payload = {
            "to": "prospect@externalcorp.com",
            "subject": "Test subject",
            "body": "Hello there.",
        }
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

        # Even with trust granted, SCHEDULER initiator must NOT
        # auto-approve.
        result = await queue_gmail_draft_creation(
            db_session,
            outreach_draft_id=draft.id,
            owner_email="founder@gmail.com",
            tenant_id=test_tenant_id,
            user_id=test_user_id,
            initiator=DispatchInitiator.SCHEDULER,
        )
        assert result.success is True
        assert result.auto_approved is False
