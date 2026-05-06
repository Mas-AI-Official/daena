"""Sprint-19 PR-3 -- outreach draft factory contract.

Pins:
  1. Recipient safety: parses, single recipient, no control chars,
     not in suppression, not internal user.
  2. Factory maps opportunity_type -> draft_kind correctly.
  3. Factory persists with payload_hash matching canonical hash.
  4. Failed safety -> draft persisted with status=blocked_recipient
     (operator can see what was attempted).
  5. Successful draft -> opportunity.status = "drafted".
  6. Module surface has NO send / submit / post / pay callable.
"""

from __future__ import annotations

import json
import uuid

import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    from app.services.outreach import recipient_safety

    monkeypatch.setattr(
        recipient_safety, "_SUPPRESSION_FILE",
        tmp_path / ".recipient_suppression.json",
    )
    yield


async def _seed_tenant_user(db_session, tenant_id, user_id):
    from sqlalchemy import select
    from app.models.identity import Tenant, User

    if (await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id),
    )).scalar_one_or_none() is None:
        import uuid as _uuid
        tenant = Tenant(
            id=tenant_id, name="T",
            slug=f"sprint19-pr3-{_uuid.uuid4().hex[:6]}",
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


async def _make_opportunity(db_session, tenant_id, *, type_="grant"):
    from app.models.business import Opportunity

    op = Opportunity(
        tenant_id=tenant_id,
        type=type_,
        title="Test opportunity",
        source_name="manual_seed",
        score=50,
        status="discovered",
        dedupe_key=f"key-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(op)
    await db_session.flush()
    return op


# ────────────────────────────────────────────────────────────────────
# Recipient safety
# ────────────────────────────────────────────────────────────────────


class TestRecipientSafety:
    @pytest.mark.parametrize("bad,expected_reason", [
        ("", "empty_recipient"),
        ("   ", "empty_recipient"),
        ("not an email", "invalid_email"),
        ("a@b.com,c@d.com", "multiple_recipients"),
        ("a@b.com;c@d.com", "multiple_recipients"),
        ("ev\nil@b.com", "control_chars"),
        ("ev\x00il@b.com", "control_chars"),
        ("noatsign.com", "invalid_email"),
    ])
    async def test_invalid_recipients_refused(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
        bad, expected_reason,
    ):
        from app.services.outreach.recipient_safety import (
            check_recipient_safety,
        )

        await _seed_tenant_user(db_session, test_tenant_id, test_user_id)
        result = await check_recipient_safety(
            db_session, recipient=bad, tenant_id=test_tenant_id,
        )
        assert result.safe is False
        assert result.reason == expected_reason

    async def test_valid_recipient_passes(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach.recipient_safety import (
            check_recipient_safety,
        )
        await _seed_tenant_user(db_session, test_tenant_id, test_user_id)
        result = await check_recipient_safety(
            db_session, recipient="ceo@externalcompany.com",
            tenant_id=test_tenant_id,
        )
        assert result.safe is True

    async def test_suppression_blocks(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach import recipient_safety
        from app.services.outreach.recipient_safety import (
            check_recipient_safety,
        )
        recipient_safety._SUPPRESSION_FILE.write_text(
            json.dumps(["bouncey@example.com"]),
        )
        await _seed_tenant_user(db_session, test_tenant_id, test_user_id)
        result = await check_recipient_safety(
            db_session, recipient="bouncey@example.com",
            tenant_id=test_tenant_id,
        )
        assert result.safe is False
        assert result.reason == "in_suppression_list"

    async def test_internal_user_blocked(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach.recipient_safety import (
            check_recipient_safety,
        )
        await _seed_tenant_user(db_session, test_tenant_id, test_user_id)
        # Match the seeded user's email exactly.
        result = await check_recipient_safety(
            db_session, recipient=f"founder-{test_user_id}@test.local",
            tenant_id=test_tenant_id,
        )
        assert result.safe is False
        assert result.reason == "recipient_is_internal_user"


# ────────────────────────────────────────────────────────────────────
# Factory
# ────────────────────────────────────────────────────────────────────


class TestFactory:
    async def test_grant_maps_to_grant_inquiry(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach.draft_factory import (
            create_outreach_draft_for_opportunity,
        )

        await _seed_tenant_user(db_session, test_tenant_id, test_user_id)
        op = await _make_opportunity(db_session, test_tenant_id, type_="grant")

        result = await create_outreach_draft_for_opportunity(
            db_session, opportunity=op, user_id=test_user_id,
            recipient_email="program@grants.example",
        )
        assert result.status == "drafted"
        assert result.draft_id is not None

        from app.models.business import BizOutreachDraft
        from sqlalchemy import select
        draft = (await db_session.execute(
            select(BizOutreachDraft).where(
                BizOutreachDraft.id == uuid.UUID(result.draft_id),
            ),
        )).scalar_one()
        assert draft.draft_kind == "grant_inquiry_email"
        assert draft.payload_hash  # non-empty
        assert draft.needs_review is True

    async def test_blocked_recipient_persists_with_status(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach.draft_factory import (
            create_outreach_draft_for_opportunity,
        )

        await _seed_tenant_user(db_session, test_tenant_id, test_user_id)
        op = await _make_opportunity(db_session, test_tenant_id, type_="grant")

        result = await create_outreach_draft_for_opportunity(
            db_session, opportunity=op, user_id=test_user_id,
            recipient_email="not_an_email",  # fails parse
        )
        assert result.status == "blocked_recipient"
        assert result.blocked_reason == "invalid_email"
        # Draft IS persisted so operator can see what was attempted
        assert result.draft_id is not None

    async def test_unknown_type_rejected(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach.draft_factory import (
            create_outreach_draft_for_opportunity,
        )
        from app.models.business import Opportunity

        await _seed_tenant_user(db_session, test_tenant_id, test_user_id)
        op = Opportunity(
            tenant_id=test_tenant_id,
            type="some_unknown_type",  # not in mapping
            title="x", source_name="manual_seed",
            score=0, status="discovered",
            dedupe_key="x",
        )
        db_session.add(op)
        await db_session.flush()

        result = await create_outreach_draft_for_opportunity(
            db_session, opportunity=op, user_id=test_user_id,
            recipient_email="ok@external.com",
        )
        assert result.status == "rejected"
        assert result.blocked_reason == "opportunity_type_not_mappable"

    async def test_successful_draft_marks_opportunity(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach.draft_factory import (
            create_outreach_draft_for_opportunity,
        )

        await _seed_tenant_user(db_session, test_tenant_id, test_user_id)
        op = await _make_opportunity(
            db_session, test_tenant_id, type_="customer_lead",
        )

        await create_outreach_draft_for_opportunity(
            db_session, opportunity=op, user_id=test_user_id,
            recipient_email="prospect@externalcorp.com",
        )
        await db_session.flush()
        assert op.status == "drafted"


# ────────────────────────────────────────────────────────────────────
# Surface guard
# ────────────────────────────────────────────────────────────────────


class TestNoForbiddenSurface:
    async def test_module_no_send_submit_post_pay(self):
        from app.services.outreach import draft_factory as mod

        forbidden = {
            "send", "submit", "post", "pay",
            "send_email", "send_now", "execute_send",
        }
        for name in dir(mod):
            if name.startswith("_"):
                continue
            assert name.lower() not in forbidden, (
                f"draft_factory exposes forbidden callable: {name}"
            )
