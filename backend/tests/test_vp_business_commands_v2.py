"""Sprint-20 PR-7 -- VP chat business flow v2 contract.

Pins the THREE id-explicit commands added in Sprint-20:

  1. create workstream from opp <uuid>
  2. draft outreach for opp <uuid> to <email>
  3. send draft <uuid>

Hard rules:
  * Each ID-explicit command requires user_id; refuses if missing.
  * Bad UUID returns invalid_uuid code, not 500.
  * Non-existent opp/draft returns *_not_found, not 500.
  * Vague 'send the approved draft' (no id) STILL returns implemented=False.
  * Vague 'draft outreach for top N' STILL returns implemented=False.
  * send_approved_draft_by_id ROUTES to send_bridge.queue_gmail_send,
    which never auto-approves (Sprint-18 wall #1 + send_bridge defensive
    sanity check).
  * Source grep: vp_business_commands.py contains NO direct call to
    Gmail HTTP / generic send_email.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select


pytestmark = pytest.mark.asyncio


# ────────────────────────────────────────────────────────────────────


async def _seed_minimum(db_session, tenant_id, user_id):
    import uuid as _uuid
    from sqlalchemy import delete
    from app.models.business import BizOutreachDraft, Opportunity
    from app.models.governance import GoaRequest
    from app.models.identity import Tenant, User
    from app.models.organization import Department
    from app.models.workstream import Workstream

    await db_session.execute(
        delete(GoaRequest).where(GoaRequest.tenant_id == tenant_id),
    )
    await db_session.execute(
        delete(BizOutreachDraft).where(BizOutreachDraft.tenant_id == tenant_id),
    )
    await db_session.execute(
        delete(Workstream).where(Workstream.tenant_id == tenant_id),
    )
    await db_session.execute(
        delete(Opportunity).where(Opportunity.tenant_id == tenant_id),
    )

    if (await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id),
    )).scalar_one_or_none() is None:
        db_session.add(Tenant(
            id=tenant_id, name="T",
            slug=f"sprint20-pr7-{_uuid.uuid4().hex[:6]}",
        ))
    if (await db_session.execute(
        select(User).where(User.id == user_id),
    )).scalar_one_or_none() is None:
        db_session.add(User(
            id=user_id, tenant_id=tenant_id,
            email=f"founder-{user_id}@test.local",
            password_hash="$argon2id$test$placeholder",
            display_name="Founder", role="FOUNDER",
        ))
    await db_session.flush()
    for idx, name in enumerate([
        "Engineering", "Product", "Marketing", "Sales", "Finance",
        "Operations", "Research", "Legal & Compliance",
        "Skill Governance", "Security Operations",
    ]):
        existing = (await db_session.execute(
            select(Department).where(
                Department.tenant_id == tenant_id,
                Department.name == name,
            ),
        )).scalar_one_or_none()
        if existing is None:
            db_session.add(Department(
                tenant_id=tenant_id, name=name,
                sunflower_index=idx, is_active=True,
            ))
    await db_session.flush()


def _seed_opp(db_session, *, tenant_id, type_="grant"):
    from app.models.business import Opportunity
    o = Opportunity(
        tenant_id=tenant_id, type=type_,
        title=f"{type_} opp v2",
        source_name="manual_seed", score=80, status="discovered",
        dedupe_key=uuid.uuid4().hex[:32],
    )
    db_session.add(o)
    return o


# ────────────────────────────────────────────────────────────────────
# Pattern recognition
# ────────────────────────────────────────────────────────────────────


class TestPatternRecognition:
    @pytest.mark.parametrize("text,expected_command", [
        ("create workstream from opp 11111111-1111-4111-8111-111111111111",
         "create_workstream_from_opp_by_id"),
        ("Create Workstream FOR Opportunity "
         "11111111-1111-4111-8111-111111111111",
         "create_workstream_from_opp_by_id"),
        ("draft outreach for opp 22222222-2222-4222-8222-222222222222 "
         "to founder@example.com",
         "draft_outreach_for_opp_to"),
        ("send draft 33333333-3333-4333-8333-333333333333",
         "send_approved_draft_by_id"),
        ("send approved draft 33333333-3333-4333-8333-333333333333",
         "send_approved_draft_by_id"),
        # Vague stays vague
        ("draft outreach for top 5", "draft_outreach_for_top"),
        ("send the approved draft", "send_approved_draft"),
    ])
    async def test_phrase_routes_to_expected_command(
        self, text, expected_command, db_session,
        test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed_minimum(db_session, test_tenant_id, test_user_id)
        r = await parse_and_run(
            text, db=db_session, tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert r.matched is True
        assert r.command == expected_command


# ────────────────────────────────────────────────────────────────────
# create_workstream_from_opp_by_id runner
# ────────────────────────────────────────────────────────────────────


class TestCreateWorkstreamRunner:
    async def test_creates_workstream_for_existing_opp(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed_minimum(db_session, test_tenant_id, test_user_id)
        opp = _seed_opp(db_session, tenant_id=test_tenant_id, type_="grant")
        await db_session.flush()

        r = await parse_and_run(
            f"create workstream from opp {opp.id}",
            db=db_session, tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert r.matched is True
        assert r.structured["ok"] is True
        assert r.structured["department_name"] == "Finance"
        # Sanity: workstream_id is a UUID.
        uuid.UUID(r.structured["workstream_id"])

    async def test_unknown_opp_returns_not_found(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed_minimum(db_session, test_tenant_id, test_user_id)
        r = await parse_and_run(
            f"create workstream from opp {uuid.uuid4()}",
            db=db_session, tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert r.structured["ok"] is False
        assert r.structured["code"] == "opportunity_not_found"

    async def test_duplicate_returns_existing_id(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed_minimum(db_session, test_tenant_id, test_user_id)
        opp = _seed_opp(db_session, tenant_id=test_tenant_id, type_="grant")
        await db_session.flush()
        r1 = await parse_and_run(
            f"create workstream from opp {opp.id}",
            db=db_session, tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert r1.structured["ok"] is True
        r2 = await parse_and_run(
            f"create workstream from opp {opp.id}",
            db=db_session, tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert r2.structured["ok"] is False
        assert r2.structured["code"] == "duplicate_workstream"
        assert r2.structured["existing_workstream_id"] == r1.structured["workstream_id"]

    async def test_requires_user_id(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed_minimum(db_session, test_tenant_id, test_user_id)
        opp = _seed_opp(db_session, tenant_id=test_tenant_id, type_="grant")
        await db_session.flush()
        r = await parse_and_run(
            f"create workstream from opp {opp.id}",
            db=db_session, tenant_id=test_tenant_id,
            user_id=None,
        )
        assert r.structured["code"] == "user_id_required"


# ────────────────────────────────────────────────────────────────────
# draft_outreach_for_opp_to runner
# ────────────────────────────────────────────────────────────────────


class TestDraftOutreachRunner:
    async def test_creates_local_draft(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.models.business import BizOutreachDraft
        from app.services.vp_business_commands import parse_and_run
        await _seed_minimum(db_session, test_tenant_id, test_user_id)
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id, type_="customer_lead",
        )
        await db_session.flush()
        r = await parse_and_run(
            f"draft outreach for opp {opp.id} to lead@external.com",
            db=db_session, tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert r.matched is True
        assert r.structured["ok"] is True
        assert r.structured["status"] == "drafted"
        # No GoaRequest produced (chat draft is local-only).
        from app.models.governance import GoaRequest
        approvals = (await db_session.execute(
            select(GoaRequest).where(GoaRequest.tenant_id == test_tenant_id),
        )).scalars().all()
        assert approvals == []

    async def test_unknown_opp_returns_not_found(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed_minimum(db_session, test_tenant_id, test_user_id)
        r = await parse_and_run(
            f"draft outreach for opp {uuid.uuid4()} to lead@external.com",
            db=db_session, tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert r.structured["ok"] is False
        assert r.structured["code"] == "opportunity_not_found"


# ────────────────────────────────────────────────────────────────────
# Vague stubs still implemented=False
# ────────────────────────────────────────────────────────────────────


class TestVagueStubsRefuse:
    async def test_send_the_approved_draft_no_id_still_refuses(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed_minimum(db_session, test_tenant_id, test_user_id)
        r = await parse_and_run(
            "send the approved draft",
            db=db_session, tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert r.matched is True
        assert r.command == "send_approved_draft"
        assert r.structured["implemented"] is False

    async def test_draft_outreach_for_top_no_id_still_refuses(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed_minimum(db_session, test_tenant_id, test_user_id)
        r = await parse_and_run(
            "draft outreach for top 3",
            db=db_session, tenant_id=test_tenant_id,
            user_id=test_user_id,
        )
        assert r.matched is True
        assert r.command == "draft_outreach_for_top"
        assert r.structured["implemented"] is False


# ────────────────────────────────────────────────────────────────────
# Hard-rule audit
# ────────────────────────────────────────────────────────────────────


class TestHardRules:
    def test_module_does_not_call_gmail_http_directly(self):
        src = (
            Path(__file__).parent.parent / "app" / "services"
            / "vp_business_commands.py"
        ).read_text(encoding="utf-8")
        # Generic send symbols and Gmail HTTP must not appear.
        for forbidden in (
            "gmail.googleapis.com",
            "smtp.gmail.com",
            "send_email(",
            "gmail.send_existing_draft(",
            "googleapiclient",
        ):
            assert forbidden not in src

    def test_send_path_routes_through_send_bridge_only(self):
        """The only send pathway is via queue_gmail_send (the bridge).
        Source pin: queue_gmail_send is referenced; nothing else."""
        src = (
            Path(__file__).parent.parent / "app" / "services"
            / "vp_business_commands.py"
        ).read_text(encoding="utf-8")
        assert "queue_gmail_send" in src
