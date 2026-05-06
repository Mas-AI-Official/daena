"""Sprint-19 PR-5 -- outreach -> Gmail send bridge contract.

Pins:
  1. Rate limit refuses 4th attempt when cap is 3.
  2. Rate limit is per-day-UTC-per-tenant.
  3. Send NEVER auto-approves (gmail.send_existing_draft is in
     TRUST_FORBIDDEN_TOOLS).
  4. Draft status precondition: gmail_draft_created.
  5. Missing gmail_draft_id refuses.
  6. Successful queue advances status to queued_send + sets
     send_approval_id linkage.
  7. Bridge NEVER raises.
"""

from __future__ import annotations

import os
import uuid

import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    from app.services import trust_ladder, trust_policy
    from app.services.outreach import send_rate_limit

    monkeypatch.setattr(
        trust_ladder, "_LADDER_FILE", tmp_path / ".trust_ladder.json",
    )
    monkeypatch.setattr(
        trust_policy, "_POLICY_FILE", tmp_path / ".trust_policy.json",
    )
    monkeypatch.setattr(
        send_rate_limit, "_STATE_FILE",
        tmp_path / ".send_rate_limit.json",
    )
    yield


async def _seed(db_session, tenant_id, user_id):
    from sqlalchemy import select
    from app.models.identity import Tenant, User

    if (await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id),
    )).scalar_one_or_none() is None:
        import uuid as _uuid
        tenant = Tenant(
            id=tenant_id, name="T",
            slug=f"sprint19-pr5-{_uuid.uuid4().hex[:6]}",
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


async def _make_draft_with_gmail_id(
    db_session, tenant_id, user_id, *, status="gmail_draft_created",
):
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
        gmail_draft_id="gmail-draft-12345",
    )
    db_session.add(draft)
    await db_session.flush()
    return draft


# ────────────────────────────────────────────────────────────────────


class TestRateLimit:
    async def test_default_cap_is_three(self, isolated_state, monkeypatch):
        from app.services.outreach import send_rate_limit
        monkeypatch.delenv(
            "DAENA_SEND_RATE_LIMIT_PER_DAY", raising=False,
        )
        assert send_rate_limit.get_cap_per_day() == 3

    async def test_env_override(self, isolated_state, monkeypatch):
        from app.services.outreach import send_rate_limit
        monkeypatch.setenv("DAENA_SEND_RATE_LIMIT_PER_DAY", "10")
        assert send_rate_limit.get_cap_per_day() == 10

    async def test_three_then_refuse(self, isolated_state):
        from app.services.outreach.send_rate_limit import (
            check_and_increment,
        )
        tid = uuid.uuid4()
        for _ in range(3):
            r = check_and_increment(tid)
            assert r.allowed is True
        # 4th call refused
        r4 = check_and_increment(tid)
        assert r4.allowed is False
        assert r4.reason == "rate_limit_exceeded"

    async def test_per_tenant_isolation(self, isolated_state):
        from app.services.outreach.send_rate_limit import (
            check_and_increment,
        )
        a, b = uuid.uuid4(), uuid.uuid4()
        for _ in range(3):
            check_and_increment(a)
        # tenant b unaffected
        r = check_and_increment(b)
        assert r.allowed is True


class TestSendBridgeRefusals:
    async def test_unknown_outreach_draft(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach.send_bridge import queue_gmail_send

        await _seed(db_session, test_tenant_id, test_user_id)
        result = await queue_gmail_send(
            db_session,
            outreach_draft_id=uuid.uuid4(),
            owner_email="founder@gmail.com",
            tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert result.success is False
        assert result.refusal_code == "outreach_draft_not_found"

    async def test_wrong_status_refused(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach.send_bridge import queue_gmail_send

        await _seed(db_session, test_tenant_id, test_user_id)
        draft = await _make_draft_with_gmail_id(
            db_session, test_tenant_id, test_user_id,
            status="drafted",  # wrong status
        )
        result = await queue_gmail_send(
            db_session,
            outreach_draft_id=draft.id,
            owner_email="founder@gmail.com",
            tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert result.success is False
        assert "draft_status_not_gmail_draft_created" in result.refusal_code

    async def test_missing_gmail_draft_id(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.models.business import BizOutreachDraft
        from app.services.outreach.send_bridge import queue_gmail_send

        await _seed(db_session, test_tenant_id, test_user_id)
        draft = BizOutreachDraft(
            tenant_id=test_tenant_id,
            user_id=test_user_id,
            opportunity_id=None,
            draft_kind="customer_cold_email",
            recipient_email="x@y.com",
            subject="x", body="x",
            payload_hash="0" * 64,
            needs_review=True, confidence=50,
            status="gmail_draft_created",
            # no gmail_draft_id !
        )
        db_session.add(draft)
        await db_session.flush()

        result = await queue_gmail_send(
            db_session,
            outreach_draft_id=draft.id,
            owner_email="founder@gmail.com",
            tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert result.success is False
        assert result.refusal_code == "gmail_draft_id_missing"


class TestSendBridgeSuccess:
    async def test_queue_advances_status_and_links(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach.send_bridge import queue_gmail_send

        await _seed(db_session, test_tenant_id, test_user_id)
        draft = await _make_draft_with_gmail_id(
            db_session, test_tenant_id, test_user_id,
        )

        result = await queue_gmail_send(
            db_session,
            outreach_draft_id=draft.id,
            owner_email="founder@gmail.com",
            tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert result.success is True
        assert result.approval_id is not None
        assert result.auto_approved is False  # send NEVER auto-approves
        assert result.rate_limit_used == 1
        assert result.rate_limit_cap == 3

        await db_session.refresh(draft)
        assert draft.status == "queued_send"
        assert draft.send_approval_id is not None

    async def test_send_never_auto_approves_even_with_forced_trust(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        """Defensive: send_existing_draft is in TRUST_FORBIDDEN_TOOLS.
        Even if the founder somehow tried to grant tier (which would
        also be refused at set_max_auto_tier time), the send bridge
        result MUST be auto_approved=False."""
        from app.services.outreach.send_bridge import queue_gmail_send

        await _seed(db_session, test_tenant_id, test_user_id)
        draft = await _make_draft_with_gmail_id(
            db_session, test_tenant_id, test_user_id,
        )

        result = await queue_gmail_send(
            db_session,
            outreach_draft_id=draft.id,
            owner_email="founder@gmail.com",
            tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert result.auto_approved is False


class TestRateLimitWiredIntoBridge:
    async def test_fourth_call_refused_with_rate_limit(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach.send_bridge import queue_gmail_send

        await _seed(db_session, test_tenant_id, test_user_id)

        # Burn 3 successful sends
        for _ in range(3):
            d = await _make_draft_with_gmail_id(
                db_session, test_tenant_id, test_user_id,
            )
            r = await queue_gmail_send(
                db_session,
                outreach_draft_id=d.id,
                owner_email="founder@gmail.com",
                tenant_id=test_tenant_id,
                user_id=test_user_id,
            )
            assert r.success is True

        # 4th refused
        d4 = await _make_draft_with_gmail_id(
            db_session, test_tenant_id, test_user_id,
        )
        r4 = await queue_gmail_send(
            db_session,
            outreach_draft_id=d4.id,
            owner_email="founder@gmail.com",
            tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert r4.success is False
        assert r4.refusal_code == "rate_limit_exceeded"
        assert r4.rate_limit_used == 3

        # Draft status reflects the refusal
        await db_session.refresh(d4)
        assert d4.status == "rate_limited"
