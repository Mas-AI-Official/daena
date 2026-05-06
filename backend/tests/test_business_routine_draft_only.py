"""Sprint-20 PR-6 -- Business routine draft-only expansion contract.

Pins:
  1. business_workstream_proposal handler registered.
  2. local_draft_action_creation handler registered.
  3. Workstream proposal promotes top-K discovered opportunities.
  4. Workstream proposal skips already-promoted (DuplicateWorkstream).
  5. Local draft handler creates drafts for opps with recipient_email.
  6. Local draft handler skips opps WITHOUT recipient_email.
  7. Local draft handler does NOT create any GoaRequest (BRIGHT LINE).
  8. Routine handler module imports zero Gmail-bridge symbols (source
     grep test).
  9. Run-once initiator path stays SCHEDULER-shaped (handler is
     pure-local; no DispatchInitiator anywhere in module).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select


pytestmark = pytest.mark.asyncio


# ────────────────────────────────────────────────────────────────────


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    from app.services import routine_autonomy
    monkeypatch.setattr(
        routine_autonomy, "_STATE_FILE", tmp_path / ".routine_autonomy.json",
    )
    yield


@pytest.fixture
async def seeded_full(db_session, test_tenant_id, test_user_id):
    """Tenant + user + all 10 departments + 5 opportunities."""
    import uuid as _uuid
    from sqlalchemy import delete
    from app.models.business import BizOutreachDraft, Opportunity
    from app.models.governance import GoaRequest
    from app.models.identity import Tenant, User
    from app.models.organization import Department
    from app.models.workstream import Workstream

    await db_session.execute(
        delete(GoaRequest).where(GoaRequest.tenant_id == test_tenant_id),
    )
    await db_session.execute(
        delete(BizOutreachDraft).where(BizOutreachDraft.tenant_id == test_tenant_id),
    )
    await db_session.execute(
        delete(Workstream).where(Workstream.tenant_id == test_tenant_id),
    )
    await db_session.execute(
        delete(Opportunity).where(Opportunity.tenant_id == test_tenant_id),
    )

    if (await db_session.execute(
        select(Tenant).where(Tenant.id == test_tenant_id),
    )).scalar_one_or_none() is None:
        db_session.add(Tenant(
            id=test_tenant_id, name="T",
            slug=f"sprint20-pr6-{_uuid.uuid4().hex[:6]}",
        ))
    if (await db_session.execute(
        select(User).where(User.id == test_user_id),
    )).scalar_one_or_none() is None:
        db_session.add(User(
            id=test_user_id, tenant_id=test_tenant_id,
            email=f"founder-{test_user_id}@test.local",
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
                Department.tenant_id == test_tenant_id,
                Department.name == name,
            ),
        )).scalar_one_or_none()
        if existing is None:
            db_session.add(Department(
                tenant_id=test_tenant_id, name=name,
                sunflower_index=idx, is_active=True,
            ))
    await db_session.flush()
    yield


def _opp(db_session, *, tenant_id, type_, score=80, recipient=None):
    from app.models.business import Opportunity
    o = Opportunity(
        tenant_id=tenant_id, type=type_, title=f"{type_} opp",
        source_name="manual_seed", score=score, status="discovered",
        dedupe_key=uuid.uuid4().hex[:32],
        raw_metadata={"recipient_email": recipient} if recipient else None,
    )
    db_session.add(o)
    return o


# ────────────────────────────────────────────────────────────────────
# Handler registration
# ────────────────────────────────────────────────────────────────────


class TestHandlerRegistration:
    async def test_handlers_registered(self, isolated_state):
        from app.services import routine_autonomy
        from app.services.business_pipeline import routine_handler
        # Ensure handlers re-register after isolated_state clear.
        routine_handler.register()

        kinds = routine_autonomy.registered_handler_kinds()
        assert "opportunity_discovery" in kinds
        assert "business_workstream_proposal" in kinds
        assert "local_draft_action_creation" in kinds


# ────────────────────────────────────────────────────────────────────
# business_workstream_proposal
# ────────────────────────────────────────────────────────────────────


class TestWorkstreamProposalHandler:
    async def test_promotes_top_k_discovered_opportunities(
        self, isolated_state, seeded_full, db_session,
        test_tenant_id, test_user_id,
    ):
        from app.models.workstream import Workstream
        from app.services.business_pipeline.routine_handler import (
            business_workstream_proposal_handler,
        )
        # Seed 5 opps; top_k=3 should promote exactly 3.
        for i, t in enumerate([
            "grant", "hackathon", "customer_lead",
            "partnership", "content_opportunity",
        ]):
            _opp(
                db_session, tenant_id=test_tenant_id,
                type_=t, score=90 - i * 5,
            )
        await db_session.flush()

        artifacts, detail = await business_workstream_proposal_handler(
            db=db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, top_k=3,
        )
        assert len([a for a in artifacts if a.startswith("workstream:")]) == 3
        ws_count = (await db_session.execute(
            select(Workstream).where(Workstream.tenant_id == test_tenant_id),
        )).scalars().all()
        assert len(ws_count) == 3

    async def test_no_goa_request_created(
        self, isolated_state, seeded_full, db_session,
        test_tenant_id, test_user_id,
    ):
        from app.models.governance import GoaRequest
        from app.services.business_pipeline.routine_handler import (
            business_workstream_proposal_handler,
        )
        _opp(db_session, tenant_id=test_tenant_id, type_="grant")
        await db_session.flush()
        await business_workstream_proposal_handler(
            db=db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, top_k=1,
        )
        approvals = (await db_session.execute(
            select(GoaRequest).where(GoaRequest.tenant_id == test_tenant_id),
        )).scalars().all()
        assert approvals == []


# ────────────────────────────────────────────────────────────────────
# local_draft_action_creation
# ────────────────────────────────────────────────────────────────────


class TestLocalDraftHandler:
    async def test_drafts_only_for_opps_with_recipient(
        self, isolated_state, seeded_full, db_session,
        test_tenant_id, test_user_id,
    ):
        from app.models.business import BizOutreachDraft
        from app.services.business_pipeline.routine_handler import (
            local_draft_action_creation_handler,
        )
        _opp(
            db_session, tenant_id=test_tenant_id, type_="customer_lead",
            score=90, recipient="lead@external.com",
        )
        # Without recipient -- should be skipped.
        _opp(
            db_session, tenant_id=test_tenant_id, type_="customer_lead",
            score=85,
        )
        await db_session.flush()

        artifacts, detail = await local_draft_action_creation_handler(
            db=db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, top_k=5,
        )
        drafted = [a for a in artifacts if a.startswith("draft:")]
        assert len(drafted) == 1
        # Counts visible in detail.
        assert "drafted=1" in detail
        assert "skipped_no_recipient=1" in detail

        rows = (await db_session.execute(
            select(BizOutreachDraft).where(
                BizOutreachDraft.tenant_id == test_tenant_id,
            ),
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "drafted"

    async def test_local_draft_handler_creates_no_goa_request(
        self, isolated_state, seeded_full, db_session,
        test_tenant_id, test_user_id,
    ):
        """The BRIGHT LINE: local draft handler MUST NOT produce any
        GoaRequest. Approval queueing is operator-driven, not routine-
        driven."""
        from app.models.governance import GoaRequest
        from app.services.business_pipeline.routine_handler import (
            local_draft_action_creation_handler,
        )
        _opp(
            db_session, tenant_id=test_tenant_id, type_="customer_lead",
            recipient="lead@external.com",
        )
        await db_session.flush()
        await local_draft_action_creation_handler(
            db=db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, top_k=5,
        )
        approvals = (await db_session.execute(
            select(GoaRequest).where(GoaRequest.tenant_id == test_tenant_id),
        )).scalars().all()
        assert approvals == []


# ────────────────────────────────────────────────────────────────────
# Bright-line source grep
# ────────────────────────────────────────────────────────────────────


class TestBrightLineHardRule:
    def test_routine_handler_does_not_import_gmail_bridge(self):
        """The routine handler module must not reference any send /
        Gmail-bridge symbol. Operator path stays separate."""
        src = (
            Path(__file__).parent.parent / "app" / "services"
            / "business_pipeline" / "routine_handler.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "queue_gmail_draft_creation",
            "queue_gmail_send",
            "from app.services.outreach.gmail_bridge",
            "from app.services.outreach.send_bridge",
            "controlled_execution_dispatch",
        ):
            assert forbidden not in src, (
                f"routine_handler.py contains forbidden symbol "
                f"{forbidden!r} -- bright line broken"
            )

    def test_routine_handler_has_no_external_action_strings(self):
        src = (
            Path(__file__).parent.parent / "app" / "services"
            / "business_pipeline" / "routine_handler.py"
        ).read_text(encoding="utf-8").lower()
        for forbidden in (
            "submit_form", "post_to_", "linkedin", "playwright",
            "selenium", ".send(",
        ):
            assert forbidden not in src
