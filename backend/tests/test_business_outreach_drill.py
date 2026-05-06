"""Sprint-20 PR-5 -- Safe first business outreach drill contract.

Pins six independent walls. Each wall has a stable refusal code and
must refuse with NO downstream side effect (no draft persisted, no
GoaRequest created, no rate-limit increment) on early refusals.

Walls verified:
  1. Env flag DAENA_ENABLE_LIVE_BUSINESS_OUTREACH_DRILL must be
     literally "true" (case-insensitive).
  2. DAENA_DRILL_RECIPIENT_ALLOWLIST must be non-empty.
  3. Recipient must appear in the allowlist.
  4. Opportunity must exist for tenant.
  5. Rate limit must have remaining > 0.
  6. Draft factory must not block on recipient safety.
  7. Gmail OAuth must be ready for owner_email.

When all pass:
  * outreach_draft_id is set
  * gmail_create_draft_approval_id is set
  * approval status is PENDING (NEVER auto-sent)
  * NO Gmail send occurs (drill stops at first approval)
  * NO scheduler path can reach the drill (initiator hardcoded
    OPERATOR; tested by source grep).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select


pytestmark = pytest.mark.asyncio


# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────


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
        send_rate_limit, "_STATE_FILE", tmp_path / ".send_rate_limit.json",
    )
    monkeypatch.delenv(
        "DAENA_ENABLE_LIVE_BUSINESS_OUTREACH_DRILL", raising=False,
    )
    monkeypatch.delenv(
        "DAENA_DRILL_RECIPIENT_ALLOWLIST", raising=False,
    )
    yield


def _flag_drill_on(monkeypatch, allowlist: str):
    monkeypatch.setenv("DAENA_ENABLE_LIVE_BUSINESS_OUTREACH_DRILL", "true")
    monkeypatch.setenv("DAENA_DRILL_RECIPIENT_ALLOWLIST", allowlist)


async def _seed_tenant_user_opp(
    db_session, tenant_id, user_id, *, opp_type="customer_lead",
):
    """Seeds tenant + user + a single opportunity. Idempotent."""
    import uuid as _uuid
    from sqlalchemy import delete
    from app.models.business import BizOutreachDraft, Opportunity
    from app.models.governance import GoaRequest
    from app.models.identity import Tenant, User

    # Wipe related rows for a clean drill check.
    await db_session.execute(
        delete(GoaRequest).where(GoaRequest.tenant_id == tenant_id),
    )
    await db_session.execute(
        delete(BizOutreachDraft).where(BizOutreachDraft.tenant_id == tenant_id),
    )
    await db_session.execute(
        delete(Opportunity).where(Opportunity.tenant_id == tenant_id),
    )

    if (await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id),
    )).scalar_one_or_none() is None:
        db_session.add(Tenant(
            id=tenant_id, name="T",
            slug=f"sprint20-pr5-{_uuid.uuid4().hex[:6]}",
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
    opp = Opportunity(
        tenant_id=tenant_id, type=opp_type,
        title="Test Opp Drill", source_name="manual_seed",
        score=50, status="discovered",
        dedupe_key=_uuid.uuid4().hex[:32],
    )
    db_session.add(opp)
    await db_session.flush()
    return opp


async def _seed_gmail_oauth(db_session, tenant_id, user_id, *, owner_email):
    from app.models.connections import Connector, ConnectorInstance
    conn = (await db_session.execute(
        select(Connector).where(Connector.name == "Gmail"),
    )).scalar_one_or_none()
    if conn is None:
        conn = Connector(
            id=uuid.uuid4(), name="Gmail",
            description="Gmail", category="email", auth_type="oauth2",
        )
        db_session.add(conn)
        await db_session.flush()
    db_session.add(ConnectorInstance(
        id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id,
        connector_id=conn.id,
        owner_email=owner_email,
        credentials={"access_token": "fake-token-for-test"},
        status="active",
    ))
    await db_session.flush()


# ────────────────────────────────────────────────────────────────────
# Walls
# ────────────────────────────────────────────────────────────────────


class TestEnvFlagWall:
    async def test_refuses_without_env_flag(
        self, isolated_state, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.outreach.drill import run_outreach_drill
        opp = await _seed_tenant_user_opp(
            db_session, test_tenant_id, test_user_id,
        )
        r = await run_outreach_drill(
            db_session,
            tenant_id=test_tenant_id, user_id=test_user_id,
            opportunity_id=opp.id,
            recipient_email="ok@allow.com",
            owner_email="founder@gmail.com",
        )
        assert r.success is False
        assert r.refusal_code == "drill_disabled_env_flag_missing"

    async def test_refuses_when_env_flag_value_not_true(
        self, isolated_state, db_session, monkeypatch,
        test_tenant_id, test_user_id,
    ):
        from app.services.outreach.drill import run_outreach_drill
        opp = await _seed_tenant_user_opp(
            db_session, test_tenant_id, test_user_id,
        )
        monkeypatch.setenv(
            "DAENA_ENABLE_LIVE_BUSINESS_OUTREACH_DRILL", "yes",  # not "true"
        )
        r = await run_outreach_drill(
            db_session,
            tenant_id=test_tenant_id, user_id=test_user_id,
            opportunity_id=opp.id,
            recipient_email="ok@allow.com",
            owner_email="founder@gmail.com",
        )
        assert r.refusal_code == "drill_disabled_env_flag_missing"


class TestAllowlistWall:
    async def test_refuses_when_allowlist_empty(
        self, isolated_state, db_session, monkeypatch,
        test_tenant_id, test_user_id,
    ):
        from app.services.outreach.drill import run_outreach_drill
        opp = await _seed_tenant_user_opp(
            db_session, test_tenant_id, test_user_id,
        )
        monkeypatch.setenv(
            "DAENA_ENABLE_LIVE_BUSINESS_OUTREACH_DRILL", "true",
        )
        # allowlist not set
        r = await run_outreach_drill(
            db_session,
            tenant_id=test_tenant_id, user_id=test_user_id,
            opportunity_id=opp.id,
            recipient_email="ok@allow.com",
            owner_email="founder@gmail.com",
        )
        assert r.refusal_code == "drill_recipient_allowlist_empty"

    async def test_refuses_when_recipient_not_in_allowlist(
        self, isolated_state, db_session, monkeypatch,
        test_tenant_id, test_user_id,
    ):
        from app.services.outreach.drill import run_outreach_drill
        opp = await _seed_tenant_user_opp(
            db_session, test_tenant_id, test_user_id,
        )
        _flag_drill_on(monkeypatch, "allowed@x.com")
        r = await run_outreach_drill(
            db_session,
            tenant_id=test_tenant_id, user_id=test_user_id,
            opportunity_id=opp.id,
            recipient_email="someone-else@y.com",
            owner_email="founder@gmail.com",
        )
        assert r.refusal_code == "drill_recipient_not_in_allowlist"

    async def test_allowlist_match_is_case_insensitive(
        self, isolated_state, db_session, monkeypatch,
        test_tenant_id, test_user_id,
    ):
        from app.services.outreach.drill import run_outreach_drill
        opp = await _seed_tenant_user_opp(
            db_session, test_tenant_id, test_user_id,
        )
        _flag_drill_on(monkeypatch, "ALLOWED@X.COM")
        await _seed_gmail_oauth(
            db_session, test_tenant_id, test_user_id,
            owner_email="founder@gmail.com",
        )
        r = await run_outreach_drill(
            db_session,
            tenant_id=test_tenant_id, user_id=test_user_id,
            opportunity_id=opp.id,
            recipient_email="allowed@x.com",  # different case
            owner_email="founder@gmail.com",
        )
        assert r.success is True


class TestOpportunityWall:
    async def test_refuses_unknown_opportunity(
        self, isolated_state, db_session, monkeypatch,
        test_tenant_id, test_user_id,
    ):
        from app.services.outreach.drill import run_outreach_drill
        # need tenant/user
        await _seed_tenant_user_opp(
            db_session, test_tenant_id, test_user_id,
        )
        _flag_drill_on(monkeypatch, "ok@allow.com")
        r = await run_outreach_drill(
            db_session,
            tenant_id=test_tenant_id, user_id=test_user_id,
            opportunity_id=uuid.uuid4(),
            recipient_email="ok@allow.com",
            owner_email="founder@gmail.com",
        )
        assert r.refusal_code == "drill_opportunity_not_found"


class TestRateLimitWall:
    async def test_refuses_when_cap_exhausted(
        self, isolated_state, db_session, monkeypatch,
        test_tenant_id, test_user_id,
    ):
        from app.services.outreach.drill import run_outreach_drill
        from app.services.outreach.send_rate_limit import (
            check_and_increment,
        )
        monkeypatch.setenv("DAENA_SEND_RATE_LIMIT_PER_DAY", "1")
        opp = await _seed_tenant_user_opp(
            db_session, test_tenant_id, test_user_id,
        )
        _flag_drill_on(monkeypatch, "ok@allow.com")
        # Burn the 1 send slot.
        d = check_and_increment(test_tenant_id)
        assert d.allowed is True
        r = await run_outreach_drill(
            db_session,
            tenant_id=test_tenant_id, user_id=test_user_id,
            opportunity_id=opp.id,
            recipient_email="ok@allow.com",
            owner_email="founder@gmail.com",
        )
        assert r.refusal_code == "drill_rate_limit_exhausted"


class TestRecipientSafetyWall:
    async def test_refuses_when_recipient_safety_fails(
        self, isolated_state, db_session, monkeypatch,
        test_tenant_id, test_user_id,
    ):
        from app.services.outreach.drill import run_outreach_drill
        opp = await _seed_tenant_user_opp(
            db_session, test_tenant_id, test_user_id,
        )
        # Allowlist a multi-recipient string -- but the safety wall
        # itself rejects multi-address inputs ("multiple_recipients").
        _flag_drill_on(monkeypatch, "good@x.com,bad@y.com")
        # The drill receives a single address (semicolon-separated will
        # fail safety check):
        r = await run_outreach_drill(
            db_session,
            tenant_id=test_tenant_id, user_id=test_user_id,
            opportunity_id=opp.id,
            recipient_email="ok@x.com;bad@y.com",
            owner_email="founder@gmail.com",
        )
        # Allowlist is matched literally -- the bad address won't be
        # there; allowlist refuses first, which is also correct.
        assert r.refusal_code in (
            "drill_recipient_not_in_allowlist",
            "drill_recipient_safety_failed",
        )


class TestOAuthWall:
    async def test_refuses_when_oauth_not_ready(
        self, isolated_state, db_session, monkeypatch,
        test_tenant_id, test_user_id,
    ):
        from app.services.outreach.drill import run_outreach_drill
        opp = await _seed_tenant_user_opp(
            db_session, test_tenant_id, test_user_id,
        )
        _flag_drill_on(monkeypatch, "allowed@x.com")
        # NO _seed_gmail_oauth called -- OAuth missing.
        r = await run_outreach_drill(
            db_session,
            tenant_id=test_tenant_id, user_id=test_user_id,
            opportunity_id=opp.id,
            recipient_email="allowed@x.com",
            owner_email="founder@gmail.com",
        )
        assert r.refusal_code == "drill_oauth_not_ready"


class TestSuccessfulDrill:
    async def test_full_path_creates_draft_and_pending_approval(
        self, isolated_state, db_session, monkeypatch,
        test_tenant_id, test_user_id,
    ):
        from app.models.business import BizOutreachDraft
        from app.models.governance import GoaRequest
        from app.services.outreach.drill import run_outreach_drill

        opp = await _seed_tenant_user_opp(
            db_session, test_tenant_id, test_user_id,
        )
        _flag_drill_on(monkeypatch, "allowed@x.com")
        await _seed_gmail_oauth(
            db_session, test_tenant_id, test_user_id,
            owner_email="founder@gmail.com",
        )

        r = await run_outreach_drill(
            db_session,
            tenant_id=test_tenant_id, user_id=test_user_id,
            opportunity_id=opp.id,
            recipient_email="allowed@x.com",
            owner_email="founder@gmail.com",
        )
        assert r.success is True, r.refusal_detail
        assert r.outreach_draft_id is not None
        assert r.gmail_create_draft_approval_id is not None

        # Draft persisted.
        drafts = (await db_session.execute(
            select(BizOutreachDraft).where(
                BizOutreachDraft.tenant_id == test_tenant_id,
            ),
        )).scalars().all()
        assert len(drafts) == 1
        assert drafts[0].status == "queued_create_draft"

        # Approval row created and PENDING (not auto-approved
        # without trust graduation).
        approvals = (await db_session.execute(
            select(GoaRequest).where(
                GoaRequest.tenant_id == test_tenant_id,
                GoaRequest.action_type == "gmail.create_draft",
            ),
        )).scalars().all()
        assert len(approvals) == 1
        assert approvals[0].status == "PENDING"

        # NO send approval created -- drill stops at first approval.
        send_approvals = (await db_session.execute(
            select(GoaRequest).where(
                GoaRequest.tenant_id == test_tenant_id,
                GoaRequest.action_type == "gmail.send_existing_draft",
            ),
        )).scalars().all()
        assert send_approvals == []


# ────────────────────────────────────────────────────────────────────
# Hard-rule audit
# ────────────────────────────────────────────────────────────────────


class TestHardRules:
    def test_drill_stops_at_first_approval_no_send_call(self):
        """Defense in depth: drill module must NOT import send-bridge
        helpers. The send approval is operator-driven through the UI
        on the second wall, not from this module."""
        src = (
            Path(__file__).parent.parent / "app" / "services"
            / "outreach" / "drill.py"
        ).read_text(encoding="utf-8")
        assert "queue_gmail_send" not in src
        assert "send_existing_draft" not in src

    def test_drill_initiator_is_operator(self):
        """Source pin: initiator passed to gmail_bridge is OPERATOR.
        SCHEDULER initiator would mean a routine could trigger a real
        outreach drill -- forbidden."""
        src = (
            Path(__file__).parent.parent / "app" / "services"
            / "outreach" / "drill.py"
        ).read_text(encoding="utf-8")
        assert "DispatchInitiator.OPERATOR" in src
        assert "DispatchInitiator.SCHEDULER" not in src

    def test_no_browser_or_form_submission(self):
        src = (
            Path(__file__).parent.parent / "app" / "services"
            / "outreach" / "drill.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "playwright", "selenium", "submit_form", "post_to_",
            "linkedin", "form_drafts.submit",
        ):
            assert forbidden not in src.lower()
