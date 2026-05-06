"""Sprint-19 PR-7 -- VP business chat commands contract.

Pins:
  1. Eight canonical phrases recognized.
  2. Unrelated text returns matched=False.
  3. find_grants returns only grant-typed opps.
  4. find_hackathons returns only hackathon-typed opps.
  5. find_customer_leads returns only customer_lead-typed opps.
  6. find_ways_to_make_money returns top-10 of any type.
  7. what_needs_approval lists pending GoaRequests.
  8. draft_outreach_for_top returns implemented=False (v1).
  9. send_approved_draft returns implemented=False (v1).
 10. NO command output contains "sent" / "applied" / "commit_sha".
 11. Summary is deterministic (no exclamation, no hedging).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest


pytestmark = pytest.mark.asyncio


async def _seed(db_session, tenant_id, user_id):
    from sqlalchemy import select
    from app.models.identity import Tenant, User

    if (await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id),
    )).scalar_one_or_none() is None:
        import uuid as _uuid
        tenant = Tenant(
            id=tenant_id, name="T",
            slug=f"sprint19-pr7-{_uuid.uuid4().hex[:6]}",
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


async def _seed_opps(db_session, tenant_id):
    from app.models.business import Opportunity

    rows = [
        Opportunity(
            tenant_id=tenant_id, type="grant", title="Grant A",
            source_name="manual_seed", score=80,
            status="discovered", dedupe_key="g1",
        ),
        Opportunity(
            tenant_id=tenant_id, type="hackathon", title="Hack B",
            source_name="manual_seed", score=50,
            status="discovered", dedupe_key="h1",
        ),
        Opportunity(
            tenant_id=tenant_id, type="customer_lead", title="Lead C",
            source_name="manual_seed", score=70,
            status="discovered", dedupe_key="l1",
        ),
    ]
    for r in rows:
        db_session.add(r)
    await db_session.flush()


# ────────────────────────────────────────────────────────────────────


class TestPatternMatch:
    @pytest.mark.parametrize("text,expected", [
        ("find ways to make money today", "find_ways_to_make_money"),
        ("Find a way to make money", "find_ways_to_make_money"),
        ("find grants for MAS-AI", "find_grants"),
        ("find grant", "find_grants"),
        ("find hackathons we can join", "find_hackathons"),
        ("Find Customer Leads", "find_customer_leads"),
        ("find leads", "find_customer_leads"),
        ("draft outreach for top 3", "draft_outreach_for_top"),
        ("Draft Outreach For Top 5", "draft_outreach_for_top"),
        ("what needs my approval?", "what_needs_approval"),
        ("what still needs approval", "what_needs_approval"),
        ("send the approved draft", "send_approved_draft"),
        ("what did you do today?", "what_did_you_do_today"),
    ])
    async def test_phrase_recognized(
        self, text, expected, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed(db_session, test_tenant_id, test_user_id)
        r = await parse_and_run(text, db=db_session, tenant_id=test_tenant_id)
        assert r.matched is True
        assert r.command == expected

    async def test_unrelated_text(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed(db_session, test_tenant_id, test_user_id)
        r = await parse_and_run(
            "hello how are you", db=db_session, tenant_id=test_tenant_id,
        )
        assert r.matched is False


class TestFindCommands:
    async def test_find_grants_filters_to_grants(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed(db_session, test_tenant_id, test_user_id)
        await _seed_opps(db_session, test_tenant_id)

        r = await parse_and_run(
            "find grants", db=db_session, tenant_id=test_tenant_id,
        )
        assert r.matched is True
        rows = r.structured.get("rows", [])
        assert len(rows) == 1
        assert rows[0]["type"] == "grant"

    async def test_find_hackathons(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed(db_session, test_tenant_id, test_user_id)
        await _seed_opps(db_session, test_tenant_id)

        r = await parse_and_run(
            "find hackathons", db=db_session, tenant_id=test_tenant_id,
        )
        rows = r.structured.get("rows", [])
        assert len(rows) == 1
        assert rows[0]["type"] == "hackathon"

    async def test_find_customer_leads(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed(db_session, test_tenant_id, test_user_id)
        await _seed_opps(db_session, test_tenant_id)

        r = await parse_and_run(
            "find customer leads", db=db_session, tenant_id=test_tenant_id,
        )
        rows = r.structured.get("rows", [])
        assert len(rows) == 1
        assert rows[0]["type"] == "customer_lead"

    async def test_find_ways_to_make_money_returns_all_types(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed(db_session, test_tenant_id, test_user_id)
        await _seed_opps(db_session, test_tenant_id)

        r = await parse_and_run(
            "find ways to make money today", db=db_session,
            tenant_id=test_tenant_id,
        )
        # 3 seeded; should all show
        assert r.structured.get("found_count", 0) == 3


class TestNotImplementedCommands:
    async def test_draft_outreach_returns_not_implemented(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed(db_session, test_tenant_id, test_user_id)

        r = await parse_and_run(
            "draft outreach for top 3", db=db_session,
            tenant_id=test_tenant_id,
        )
        assert r.matched is True
        assert r.structured.get("implemented") is False

    async def test_send_returns_not_implemented(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run
        await _seed(db_session, test_tenant_id, test_user_id)

        r = await parse_and_run(
            "send the approved draft", db=db_session,
            tenant_id=test_tenant_id,
        )
        assert r.matched is True
        assert r.structured.get("implemented") is False


class TestApprovalQueueCommand:
    async def test_what_needs_approval_lists_pending(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.models.governance import GoaRequest
        from app.services.vp_business_commands import parse_and_run

        await _seed(db_session, test_tenant_id, test_user_id)

        # Seed one pending controlled-tool approval and one non-controlled
        controlled = GoaRequest(
            tenant_id=test_tenant_id, user_id=test_user_id,
            action_type="gmail.create_draft",
            action_params=None,
            risk_level="LOW", governance_tier=2,
            status="PENDING",
        )
        other = GoaRequest(
            tenant_id=test_tenant_id, user_id=test_user_id,
            action_type="some.other.action",
            action_params=None,
            risk_level="LOW", governance_tier=2,
            status="PENDING",
        )
        db_session.add_all([controlled, other])
        await db_session.flush()

        r = await parse_and_run(
            "what needs my approval?", db=db_session,
            tenant_id=test_tenant_id,
        )
        assert r.matched is True
        assert r.structured.get("pending_count", 0) == 2
        assert r.structured.get("controlled_count", 0) == 1


class TestNoForbiddenSurfaceLeak:
    async def test_no_command_output_contains_sent_or_applied(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run

        await _seed(db_session, test_tenant_id, test_user_id)
        for phrase in (
            "find ways to make money",
            "find grants",
            "find hackathons",
            "find customer leads",
            "draft outreach for top 3",
            "what needs my approval",
            "send the approved draft",
            "what did you do today",
        ):
            r = await parse_and_run(
                phrase, db=db_session, tenant_id=test_tenant_id,
            )
            blob = str(r.structured).lower()
            assert "sent_at" not in blob
            assert "applied_at" not in blob
            assert "commit_sha" not in blob


class TestDeterministicSummary:
    async def test_no_hedging_in_summary(
        self, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.vp_business_commands import parse_and_run

        await _seed(db_session, test_tenant_id, test_user_id)
        for phrase in (
            "find grants",
            "what needs my approval",
            "what did you do today",
        ):
            r = await parse_and_run(
                phrase, db=db_session, tenant_id=test_tenant_id,
            )
            assert "!" not in r.summary
            assert "..." not in r.summary
            assert "i think" not in r.summary.lower()
            assert "maybe" not in r.summary.lower()
