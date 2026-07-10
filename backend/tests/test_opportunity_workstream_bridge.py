"""Sprint-20 PR-3 -- Opportunity-to-Workstream bridge contract.

Pins:
  1. WorkstreamSourceType.OPPORTUNITY exists.
  2. Type-to-department map covers EVERY opportunity type.
  3. Promote routes grant -> Finance.
  4. Promote routes hackathon -> Engineering.
  5. Promote routes customer_lead -> Sales.
  6. Promote routes bug_bounty_program -> Security Operations.
  7. Promote routes content_opportunity -> Marketing.
  8. Refuses unknown opportunity type with stable code.
  9. Refuses missing department with stable code.
 10. Refuses second promotion with duplicate code + existing_id.
 11. Workstream context snapshots opportunity fields.
 12. Workstream STARTED event is appended.
 13. Opportunity.assigned_department + status=queued stamped.
 14. Bridge does NOT create approval rows / send / post.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select


pytestmark = pytest.mark.asyncio


# ────────────────────────────────────────────────────────────────────


@pytest.fixture
async def bridge_seeded(db_session, test_tenant_id, test_user_id):
    """Idempotent tenant+user+10-departments seed for the bridge."""
    from sqlalchemy import delete
    from app.models.business import Opportunity
    from app.models.workstream import Workstream
    from app.models.organization import Department
    from app.models.identity import Tenant, User
    import uuid as _uuid

    # Wipe rows for a clean slate.
    await db_session.execute(
        delete(Workstream).where(Workstream.tenant_id == test_tenant_id),
    )
    await db_session.execute(
        delete(Opportunity).where(Opportunity.tenant_id == test_tenant_id),
    )
    # Tenant / user / departments idempotent.
    existing_t = (await db_session.execute(
        select(Tenant).where(Tenant.id == test_tenant_id),
    )).scalar_one_or_none()
    if existing_t is None:
        db_session.add(Tenant(
            id=test_tenant_id, name="T",
            slug=f"sprint20-pr3-{_uuid.uuid4().hex[:6]}",
        ))
    existing_u = (await db_session.execute(
        select(User).where(User.id == test_user_id),
    )).scalar_one_or_none()
    if existing_u is None:
        db_session.add(User(
            id=test_user_id, tenant_id=test_tenant_id,
            email=f"founder-{test_user_id}@test.local",
            password_hash="$argon2id$test$placeholder",
            display_name="Founder", role="FOUNDER",
        ))
    await db_session.flush()
    # Seed all departments referenced in the routing map.
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


def _seed_opp(
    db_session, *, tenant_id, type_, title="Test", status="discovered",
):
    from app.models.business import Opportunity
    o = Opportunity(
        tenant_id=tenant_id, type=type_, title=title,
        source_name="manual_seed", source_url="https://example.com/x",
        score=70, status=status, dedupe_key=uuid.uuid4().hex[:32],
    )
    db_session.add(o)
    return o


# ────────────────────────────────────────────────────────────────────


class TestRoutingMap:
    async def test_every_opportunity_type_maps_to_a_department(self):
        from app.models.business import OPPORTUNITY_TYPES
        from app.services.business_pipeline.workstream_bridge import (
            OPP_TYPE_TO_PRIMARY_DEPT,
        )
        for t in OPPORTUNITY_TYPES:
            assert t in OPP_TYPE_TO_PRIMARY_DEPT, (
                f"opportunity type {t!r} has no department mapping"
            )

    async def test_routing_anchors(self):
        from app.services.business_pipeline.workstream_bridge import (
            OPP_TYPE_TO_PRIMARY_DEPT,
        )
        assert OPP_TYPE_TO_PRIMARY_DEPT["grant"] == "Finance"
        assert OPP_TYPE_TO_PRIMARY_DEPT["accelerator"] == "Finance"
        assert OPP_TYPE_TO_PRIMARY_DEPT["hackathon"] == "Engineering"
        assert OPP_TYPE_TO_PRIMARY_DEPT["customer_lead"] == "Sales"
        assert OPP_TYPE_TO_PRIMARY_DEPT["partnership"] == "Sales"
        assert OPP_TYPE_TO_PRIMARY_DEPT["bug_bounty_program"] == "Security Operations"
        assert OPP_TYPE_TO_PRIMARY_DEPT["content_opportunity"] == "Marketing"


class TestPromote:
    async def test_grant_promoted_to_finance(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.business_pipeline.workstream_bridge import (
            create_workstream_for_opportunity,
        )
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id, type_="grant",
        )
        await db_session.flush()
        result = await create_workstream_for_opportunity(
            db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, opportunity_id=opp.id,
        )
        assert result.department_name == "Finance"
        assert "Founder Office" in result.collaborators
        assert result.opportunity_id == opp.id
        # Opportunity stamped + status advanced.
        await db_session.refresh(opp)
        assert opp.assigned_department == "Finance"
        assert opp.status == "queued"

    async def test_hackathon_promoted_to_engineering(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.business_pipeline.workstream_bridge import (
            create_workstream_for_opportunity,
        )
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id, type_="hackathon",
        )
        await db_session.flush()
        r = await create_workstream_for_opportunity(
            db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, opportunity_id=opp.id,
        )
        assert r.department_name == "Engineering"
        assert "Product" in r.collaborators

    async def test_customer_lead_promoted_to_sales(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.business_pipeline.workstream_bridge import (
            create_workstream_for_opportunity,
        )
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id, type_="customer_lead",
        )
        await db_session.flush()
        r = await create_workstream_for_opportunity(
            db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, opportunity_id=opp.id,
        )
        assert r.department_name == "Sales"

    async def test_bug_bounty_promoted_to_security_ops(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.business_pipeline.workstream_bridge import (
            create_workstream_for_opportunity,
        )
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id,
            type_="bug_bounty_program",
        )
        await db_session.flush()
        r = await create_workstream_for_opportunity(
            db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, opportunity_id=opp.id,
        )
        assert r.department_name == "Security Operations"

    async def test_content_promoted_to_marketing(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.business_pipeline.workstream_bridge import (
            create_workstream_for_opportunity,
        )
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id,
            type_="content_opportunity",
        )
        await db_session.flush()
        r = await create_workstream_for_opportunity(
            db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, opportunity_id=opp.id,
        )
        assert r.department_name == "Marketing"


class TestRefusals:
    async def test_unknown_opportunity_type(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
    ):
        from app.models.business import Opportunity
        from app.services.business_pipeline.workstream_bridge import (
            UnknownOpportunityType, create_workstream_for_opportunity,
        )
        opp = Opportunity(
            tenant_id=test_tenant_id, type="bogus_type",
            title="x", source_name="manual_seed",
            score=10, status="discovered",
            dedupe_key=uuid.uuid4().hex[:32],
        )
        db_session.add(opp)
        await db_session.flush()
        with pytest.raises(UnknownOpportunityType):
            await create_workstream_for_opportunity(
                db_session, tenant_id=test_tenant_id,
                user_id=test_user_id, opportunity_id=opp.id,
            )

    async def test_missing_department(
        self, db_session, test_tenant_id, test_user_id,
    ):
        """Bridge refuses if the routed department is not seeded for
        this tenant. Stable code so the API can surface it."""
        from sqlalchemy import delete
        from app.models.business import Opportunity
        from app.models.workstream import Workstream
        from app.models.identity import Tenant, User
        from app.services.business_pipeline.workstream_bridge import (
            DepartmentNotFound, create_workstream_for_opportunity,
        )
        # Seed tenant/user but NOT departments.
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
                slug=f"sprint20-pr3miss-{uuid.uuid4().hex[:6]}",
            ))
        if (await db_session.execute(
            select(User).where(User.id == test_user_id),
        )).scalar_one_or_none() is None:
            db_session.add(User(
                id=test_user_id, tenant_id=test_tenant_id,
                email=f"u-{test_user_id}@t.local",
                password_hash="$argon2id$test$placeholder",
                display_name="U", role="FOUNDER",
            ))
        await db_session.flush()
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id, type_="grant",
        )
        await db_session.flush()
        with pytest.raises(DepartmentNotFound):
            await create_workstream_for_opportunity(
                db_session, tenant_id=test_tenant_id,
                user_id=test_user_id, opportunity_id=opp.id,
            )

    async def test_duplicate_promotion_refused(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.business_pipeline.workstream_bridge import (
            DuplicateWorkstream, create_workstream_for_opportunity,
        )
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id, type_="grant",
        )
        await db_session.flush()
        first = await create_workstream_for_opportunity(
            db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, opportunity_id=opp.id,
        )
        with pytest.raises(DuplicateWorkstream) as exc_info:
            await create_workstream_for_opportunity(
                db_session, tenant_id=test_tenant_id,
                user_id=test_user_id, opportunity_id=opp.id,
            )
        assert exc_info.value.existing_workstream_id == first.workstream_id

    async def test_unknown_opportunity_id(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
    ):
        from app.services.business_pipeline.workstream_bridge import (
            OpportunityNotFound, create_workstream_for_opportunity,
        )
        with pytest.raises(OpportunityNotFound):
            await create_workstream_for_opportunity(
                db_session, tenant_id=test_tenant_id,
                user_id=test_user_id, opportunity_id=uuid.uuid4(),
            )


class TestWorkstreamArtifact:
    async def test_workstream_carries_snapshot_context(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
    ):
        from app.models.workstream import Workstream
        from app.services.business_pipeline.workstream_bridge import (
            create_workstream_for_opportunity,
        )
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id,
            type_="grant", title="ABC Foundation Grant",
        )
        opp.deadline_at = datetime(2026, 6, 1, tzinfo=UTC)
        opp.estimated_value_usd = 50000
        await db_session.flush()

        result = await create_workstream_for_opportunity(
            db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, opportunity_id=opp.id,
        )
        ws = (await db_session.execute(
            select(Workstream).where(Workstream.id == result.workstream_id),
        )).scalar_one()
        assert ws.context["opportunity_type"] == "grant"
        assert ws.context["opportunity_title"] == "ABC Foundation Grant"
        assert ws.context["estimated_value_usd"] == 50000
        assert ws.context["score_at_promotion"] == 70
        assert "Finance" == result.department_name

    async def test_started_event_appended(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
    ):
        from app.models.workstream import (
            WorkstreamEvent, WorkstreamEventKind,
        )
        from app.services.business_pipeline.workstream_bridge import (
            create_workstream_for_opportunity,
        )
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id, type_="hackathon",
        )
        await db_session.flush()
        r = await create_workstream_for_opportunity(
            db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, opportunity_id=opp.id,
        )
        events = list((await db_session.execute(
            select(WorkstreamEvent).where(
                WorkstreamEvent.workstream_id == r.workstream_id,
            ),
        )).scalars().all())
        assert any(
            e.kind == WorkstreamEventKind.STARTED for e in events
        )


class TestNoExternalAction:
    async def test_bridge_does_not_create_goa_request(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
    ):
        """Promotion is local-only. NO approval row created here.
        External action stays separate (Sprint-19 Gmail bridge)."""
        from app.models.governance import GoaRequest
        from app.services.business_pipeline.workstream_bridge import (
            create_workstream_for_opportunity,
        )
        before = (await db_session.execute(
            select(GoaRequest).where(
                GoaRequest.tenant_id == test_tenant_id,
            ),
        )).scalars().all()
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id, type_="grant",
        )
        await db_session.flush()
        await create_workstream_for_opportunity(
            db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, opportunity_id=opp.id,
        )
        after = (await db_session.execute(
            select(GoaRequest).where(
                GoaRequest.tenant_id == test_tenant_id,
            ),
        )).scalars().all()
        assert len(after) == len(before)

    async def test_bridge_source_grep_for_forbidden_calls(self):
        """Defense-in-depth: bridge module must not import any
        outbound-action surface."""
        from pathlib import Path
        src = (
            Path(__file__).parent.parent / "app" / "services"
            / "business_pipeline" / "workstream_bridge.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "send_existing_draft", "create_draft", "controlled_execution",
            "queue_gmail", "queue_send", "post_to_", "submit_form",
        ):
            assert forbidden not in src, (
                f"workstream_bridge.py contains forbidden symbol "
                f"{forbidden!r}"
            )


class TestPhase4ValidationGate:
    """Phase 4 Venture Studio gate: a startup_idea Opportunity cannot be
    promoted to a Workstream until a validation score is persisted in
    raw_metadata['validation']. The bridge only enforces that validation
    RAN (has_persisted_validation) -- the GO/NO-GO verdict stays the
    human's call downstream, never the bridge's."""

    async def test_startup_idea_without_validation_refused(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
    ):
        """Negative path: _seed_opp leaves raw_metadata=None, so
        validation never ran -> the gate refuses promotion."""
        from app.services.business_pipeline.workstream_bridge import (
            ValidationRequired, create_workstream_for_opportunity,
        )
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id, type_="startup_idea",
        )
        await db_session.flush()
        with pytest.raises(ValidationRequired):
            await create_workstream_for_opportunity(
                db_session, tenant_id=test_tenant_id,
                user_id=test_user_id, opportunity_id=opp.id,
            )

    async def test_startup_idea_with_persisted_validation_promoted(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
    ):
        """Positive path: a persisted validation score opens the gate;
        Research owns the idea, Product + Finance collaborate."""
        from app.services.business_pipeline.workstream_bridge import (
            create_workstream_for_opportunity,
        )
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id, type_="startup_idea",
            title="AI copilot for grant writers",
        )
        opp.raw_metadata = {"validation": {"score": 80}}
        await db_session.flush()
        result = await create_workstream_for_opportunity(
            db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, opportunity_id=opp.id,
        )
        assert result.department_name == "Research"
        assert "Product" in result.collaborators
        assert "Finance" in result.collaborators

    async def test_no_go_score_still_counts_as_validated(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
    ):
        """Presence-not-verdict: a no_go (score 0) still RAN validation,
        so the gate opens. Whether to actually pursue is the human's
        GO/NO-GO decision, made after promotion -- not a silent block
        here (Rule 17: no fake gating disguised as validation)."""
        from app.services.business_pipeline.workstream_bridge import (
            create_workstream_for_opportunity,
        )
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id, type_="startup_idea",
        )
        opp.raw_metadata = {"validation": {"score": 0}}
        await db_session.flush()
        result = await create_workstream_for_opportunity(
            db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, opportunity_id=opp.id,
        )
        assert result.department_name == "Research"

    async def test_gate_is_startup_idea_only(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
    ):
        """The gate must not leak onto other types. A grant with
        raw_metadata=None still promotes without any validation."""
        from app.services.business_pipeline.workstream_bridge import (
            create_workstream_for_opportunity,
        )
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id, type_="grant",
        )
        await db_session.flush()
        result = await create_workstream_for_opportunity(
            db_session, tenant_id=test_tenant_id,
            user_id=test_user_id, opportunity_id=opp.id,
        )
        assert result.department_name == "Finance"


# ────────────────────────────────────────────────────────────────────
# API endpoint contract
# ────────────────────────────────────────────────────────────────────


class TestApiEndpoint:
    async def test_promote_endpoint_returns_workstream_id(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
        client, auth_headers,
    ):
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id, type_="grant",
        )
        await db_session.flush()
        await db_session.commit()

        r = await client.post(
            f"/api/v1/opportunities/{opp.id}/create-workstream",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["department_name"] == "Finance"
        assert "Founder Office" in body["collaborators"]
        # Sanity: returned workstream_id parseable as UUID.
        uuid.UUID(body["workstream_id"])

    async def test_promote_returns_409_on_duplicate(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
        client, auth_headers,
    ):
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id, type_="grant",
        )
        await db_session.flush()
        await db_session.commit()
        r1 = await client.post(
            f"/api/v1/opportunities/{opp.id}/create-workstream",
            headers=auth_headers,
        )
        assert r1.status_code == 200
        r2 = await client.post(
            f"/api/v1/opportunities/{opp.id}/create-workstream",
            headers=auth_headers,
        )
        assert r2.status_code == 409
        body = r2.json()
        assert body["detail"]["code"] == "duplicate_workstream"

    async def test_promote_returns_404_for_unknown_opportunity(
        self, bridge_seeded, client, auth_headers,
    ):
        r = await client.post(
            f"/api/v1/opportunities/{uuid.uuid4()}/create-workstream",
            headers=auth_headers,
        )
        assert r.status_code == 404

    async def test_promote_returns_400_for_bad_uuid(
        self, bridge_seeded, client, auth_headers,
    ):
        r = await client.post(
            "/api/v1/opportunities/not-a-uuid/create-workstream",
            headers=auth_headers,
        )
        assert r.status_code == 400

    async def test_promote_startup_idea_returns_400_validation_required(
        self, bridge_seeded, db_session, test_tenant_id, test_user_id,
        client, auth_headers,
    ):
        """Phase 4: an unvalidated startup_idea surfaces the bridge's
        ValidationRequired as HTTP 400 {"code":"validation_required"}
        through the generic WorkstreamBridgeError handler."""
        opp = _seed_opp(
            db_session, tenant_id=test_tenant_id, type_="startup_idea",
        )
        await db_session.flush()
        await db_session.commit()
        r = await client.post(
            f"/api/v1/opportunities/{opp.id}/create-workstream",
            headers=auth_headers,
        )
        assert r.status_code == 400, r.text
        body = r.json()
        assert body["detail"]["code"] == "validation_required"
