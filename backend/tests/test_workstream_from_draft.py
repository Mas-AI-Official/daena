"""Sprint-12 PR-4 -- POST /workstreams/from-draft contract tests.

Asserts:

  1. Career draft → workstream routed to Sales department.
  2. Content draft → workstream routed to Marketing.
  3. FormDraft → workstream routed to Operations.
  4. Legal/compliance flag in draft text → routed to Legal & Compliance.
  5. department_override (operator opts to a different dept) wins.
  6. Workstream rows carry source_type="draft" + source_ref_id=draft.id.
  7. initial_context records the draft_kind, draft_ref, and routing
     reason ("override" / "legal_flag" / "kind_default").
  8. next_step_text is populated deterministically (seeded from
     draft.next_tasks for ResearchDraft, or counts blocked/needs_review
     for FormDraft).
  9. workstream.from_draft audit row written with ALLOWED.
 10. unknown draft_kind → 400.
 11. draft_not_found → 404 (draft outside the user's scope).
 12. department_not_seeded → 409 with stable error code.

Pattern:
  Build a draft directly in DB, call the service-layer helper that
  implements /workstreams/from-draft (the API endpoint), then verify
  the workstream + audit rows. We do NOT spin up a HTTP client per
  test -- the contract is best asserted directly. Negative routes
  (no /submit /send etc) are pinned by existing test_workstream_*
  source-text scans.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.form_draft import FormDraft, FormDraftField
from app.models.governance import GoaAuditEvent
from app.models.identity import Tenant, User
from app.models.organization import Department
from app.models.research import ResearchDraft
from app.models.workstream import Workstream, WorkstreamSourceType


# ── Seeding helpers ──────────────────────────────────────────────────


_DEPT_NAMES = ("Sales", "Marketing", "Operations", "Legal & Compliance")


async def _seed_user_and_depts(db_session, test_tenant_id, test_user_id):
    existing = (await db_session.execute(
        select(Tenant).where(Tenant.id == test_tenant_id)
    )).scalar_one_or_none()
    if existing is None:
        db_session.add(Tenant(id=test_tenant_id, name="T", slug="t"))
    existing_u = (await db_session.execute(
        select(User).where(User.id == test_user_id)
    )).scalar_one_or_none()
    if existing_u is None:
        db_session.add(User(
            id=test_user_id, tenant_id=test_tenant_id,
            email="m@example.com", password_hash="x",
            role="FOUNDER", is_active=True,
        ))
    await db_session.flush()
    by_name: dict[str, Department] = {}
    for i, name in enumerate(_DEPT_NAMES):
        existing_d = (await db_session.execute(
            select(Department).where(
                Department.tenant_id == test_tenant_id,
                Department.name == name,
            )
        )).scalar_one_or_none()
        if existing_d is None:
            d = Department(
                id=uuid.uuid4(),
                tenant_id=test_tenant_id,
                name=name,
                description=f"seed-{name}",
                sunflower_index=i,
                cell_id=f"hex_{i}",
                config={},
                is_active=True,
            )
            db_session.add(d)
            await db_session.flush()
            existing_d = d
        by_name[name] = existing_d
    return by_name


async def _make_research_draft(
    db_session, *, tenant_id, user_id, kind, payload=None, goal="g",
):
    draft = ResearchDraft(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        kind=kind,
        source_url="https://example.com",
        source_host="https://example.com",
        goal=goal,
        summary="raw",
        raw_extract="raw",
        status="DRAFT",
        structured_payload=payload or {"_llm_pending": False},
    )
    db_session.add(draft)
    await db_session.flush()
    return draft


async def _make_form_draft(
    db_session, *, tenant_id, user_id, with_blocked=True,
):
    draft = FormDraft(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        title="Apply",
        source_kind="questions",
        goal="fill it out",
        status="DRAFT",
    )
    db_session.add(draft)
    await db_session.flush()
    fields = [
        FormDraftField(
            id=uuid.uuid4(), tenant_id=tenant_id,
            draft_id=draft.id, order=0,
            label="Name", field_type="text", needs_review=False,
        ),
        FormDraftField(
            id=uuid.uuid4(), tenant_id=tenant_id,
            draft_id=draft.id, order=1,
            label="Why?", field_type="textarea", needs_review=True,
        ),
    ]
    if with_blocked:
        fields.append(FormDraftField(
            id=uuid.uuid4(), tenant_id=tenant_id,
            draft_id=draft.id, order=2,
            label="Credit card", field_type="blocked_payment",
            needs_review=True,
        ))
    for f in fields:
        db_session.add(f)
    await db_session.flush()
    return draft, fields


# Direct service-layer call instead of HTTP. The endpoint logic lives
# inline in the API module (Sprint-12 PR-4). The contract assertions
# need the same path but without spinning a TestClient (which would
# need auth, DB-override, etc). We import the function directly from
# the API module.
async def _post_from_draft(
    db_session, user, *,
    draft_kind, draft_ref, goal=None, department_override=None,
):
    from app.api.v1.workstreams import (
        FromDraftRequest, post_from_draft,
    )
    body = FromDraftRequest(
        draft_kind=draft_kind, draft_ref=draft_ref,
        goal=goal, department_override=department_override,
    )
    return await post_from_draft(body=body, user=user, db=db_session)


class _FakeUser:
    """Minimal CurrentUser substitute: only id + tenant_id used."""
    def __init__(self, *, id, tenant_id):
        self.id = id
        self.tenant_id = tenant_id


# ── 1, 2, 3: Department routing by kind ─────────────────────────────


class TestDepartmentRouting:
    @pytest.mark.asyncio
    async def test_career_routes_to_sales(
        self, db_session, test_tenant_id, test_user_id,
    ):
        depts = await _seed_user_and_depts(
            db_session, test_tenant_id, test_user_id,
        )
        draft = await _make_research_draft(
            db_session, tenant_id=test_tenant_id, user_id=test_user_id,
            kind="career", goal="apply to acme",
        )
        user = _FakeUser(id=test_user_id, tenant_id=test_tenant_id)
        resp = await _post_from_draft(
            db_session, user, draft_kind="career", draft_ref=draft.id,
        )
        assert resp["success"] is True
        ws_id = uuid.UUID(resp["data"]["id"])
        ws = (await db_session.execute(
            select(Workstream).where(Workstream.id == ws_id)
        )).scalar_one()
        assert ws.department_id == depts["Sales"].id
        assert ws.source_type == WorkstreamSourceType.DRAFT
        assert ws.source_ref_id == draft.id

    @pytest.mark.asyncio
    async def test_content_routes_to_marketing(
        self, db_session, test_tenant_id, test_user_id,
    ):
        depts = await _seed_user_and_depts(
            db_session, test_tenant_id, test_user_id,
        )
        draft = await _make_research_draft(
            db_session, tenant_id=test_tenant_id, user_id=test_user_id,
            kind="content", goal="write a thread",
        )
        user = _FakeUser(id=test_user_id, tenant_id=test_tenant_id)
        resp = await _post_from_draft(
            db_session, user, draft_kind="content", draft_ref=draft.id,
        )
        ws = (await db_session.execute(
            select(Workstream).where(Workstream.id == uuid.UUID(resp["data"]["id"]))
        )).scalar_one()
        assert ws.department_id == depts["Marketing"].id

    @pytest.mark.asyncio
    async def test_form_routes_to_operations(
        self, db_session, test_tenant_id, test_user_id,
    ):
        depts = await _seed_user_and_depts(
            db_session, test_tenant_id, test_user_id,
        )
        draft, _ = await _make_form_draft(
            db_session, tenant_id=test_tenant_id, user_id=test_user_id,
        )
        user = _FakeUser(id=test_user_id, tenant_id=test_tenant_id)
        resp = await _post_from_draft(
            db_session, user, draft_kind="form", draft_ref=draft.id,
        )
        ws = (await db_session.execute(
            select(Workstream).where(Workstream.id == uuid.UUID(resp["data"]["id"]))
        )).scalar_one()
        assert ws.department_id == depts["Operations"].id


# ── 4 + 5: Legal flag + override ────────────────────────────────────


class TestLegalAndOverride:
    @pytest.mark.asyncio
    async def test_legal_flag_routes_to_legal(
        self, db_session, test_tenant_id, test_user_id,
    ):
        depts = await _seed_user_and_depts(
            db_session, test_tenant_id, test_user_id,
        )
        draft = await _make_research_draft(
            db_session, tenant_id=test_tenant_id, user_id=test_user_id,
            kind="career",
            goal="contract review for license clauses",
            payload={
                "_llm_pending": False,
                "claims_to_verify": [
                    "GDPR compliance is implied",
                    "patent licence transferable",
                ],
            },
        )
        user = _FakeUser(id=test_user_id, tenant_id=test_tenant_id)
        resp = await _post_from_draft(
            db_session, user, draft_kind="career", draft_ref=draft.id,
        )
        ws = (await db_session.execute(
            select(Workstream).where(Workstream.id == uuid.UUID(resp["data"]["id"]))
        )).scalar_one()
        assert ws.department_id == depts["Legal & Compliance"].id
        assert ws.context["department_routed_by"] == "legal_flag"

    @pytest.mark.asyncio
    async def test_override_wins(
        self, db_session, test_tenant_id, test_user_id,
    ):
        depts = await _seed_user_and_depts(
            db_session, test_tenant_id, test_user_id,
        )
        draft = await _make_research_draft(
            db_session, tenant_id=test_tenant_id, user_id=test_user_id,
            kind="career",
        )
        user = _FakeUser(id=test_user_id, tenant_id=test_tenant_id)
        resp = await _post_from_draft(
            db_session, user, draft_kind="career", draft_ref=draft.id,
            department_override="Operations",
        )
        ws = (await db_session.execute(
            select(Workstream).where(Workstream.id == uuid.UUID(resp["data"]["id"]))
        )).scalar_one()
        assert ws.department_id == depts["Operations"].id
        assert ws.context["department_routed_by"] == "override"


# ── 6, 7, 8: Source attribution + context + next_step_text ──────────


class TestSourceAttribution:
    @pytest.mark.asyncio
    async def test_research_draft_seeds_next_tasks(
        self, db_session, test_tenant_id, test_user_id,
    ):
        await _seed_user_and_depts(
            db_session, test_tenant_id, test_user_id,
        )
        draft = await _make_research_draft(
            db_session, tenant_id=test_tenant_id, user_id=test_user_id,
            kind="career",
            payload={
                "_llm_pending": False,
                "next_tasks": [
                    "Tailor resume to their stack",
                    "Draft outreach to hiring manager",
                ],
            },
        )
        user = _FakeUser(id=test_user_id, tenant_id=test_tenant_id)
        resp = await _post_from_draft(
            db_session, user, draft_kind="career", draft_ref=draft.id,
        )
        ws = (await db_session.execute(
            select(Workstream).where(Workstream.id == uuid.UUID(resp["data"]["id"]))
        )).scalar_one()
        assert ws.next_step_text == "Tailor resume to their stack"
        assert ws.context["seeded_next_tasks"][0] == "Tailor resume to their stack"
        assert ws.context["draft_kind"] == "career"
        assert ws.context["draft_ref"] == str(draft.id)

    @pytest.mark.asyncio
    async def test_form_draft_records_blocked_count(
        self, db_session, test_tenant_id, test_user_id,
    ):
        await _seed_user_and_depts(
            db_session, test_tenant_id, test_user_id,
        )
        draft, fields = await _make_form_draft(
            db_session, tenant_id=test_tenant_id, user_id=test_user_id,
            with_blocked=True,
        )
        user = _FakeUser(id=test_user_id, tenant_id=test_tenant_id)
        resp = await _post_from_draft(
            db_session, user, draft_kind="form", draft_ref=draft.id,
        )
        ws = (await db_session.execute(
            select(Workstream).where(Workstream.id == uuid.UUID(resp["data"]["id"]))
        )).scalar_one()
        assert ws.context["form_blocked_count"] == 1
        assert ws.context["form_field_count"] == len(fields)
        assert "manual fill" in (ws.next_step_text or "")


# ── 9. Audit row ─────────────────────────────────────────────────────


class TestAudit:
    @pytest.mark.asyncio
    async def test_audit_row_written(
        self, db_session, test_tenant_id, test_user_id,
    ):
        await _seed_user_and_depts(
            db_session, test_tenant_id, test_user_id,
        )
        draft = await _make_research_draft(
            db_session, tenant_id=test_tenant_id, user_id=test_user_id,
            kind="content",
        )
        user = _FakeUser(id=test_user_id, tenant_id=test_tenant_id)
        resp = await _post_from_draft(
            db_session, user, draft_kind="content", draft_ref=draft.id,
        )
        ws_id = resp["data"]["id"]
        rows = (await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.action_type == "workstream.from_draft",
                GoaAuditEvent.tenant_id == test_tenant_id,
            )
        )).scalars().all()
        assert any(
            (r.action_params or {}).get("workstream_id") == ws_id
            and r.result == "ALLOWED"
            for r in rows
        )


# ── 10, 11, 12: Negative paths ───────────────────────────────────────


class TestNegativePaths:
    @pytest.mark.asyncio
    async def test_unknown_kind_400(
        self, db_session, test_tenant_id, test_user_id,
    ):
        await _seed_user_and_depts(
            db_session, test_tenant_id, test_user_id,
        )
        user = _FakeUser(id=test_user_id, tenant_id=test_tenant_id)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await _post_from_draft(
                db_session, user,
                draft_kind="not_a_kind", draft_ref=uuid.uuid4(),
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_other_users_draft_404(
        self, db_session, test_tenant_id, test_user_id,
    ):
        await _seed_user_and_depts(
            db_session, test_tenant_id, test_user_id,
        )
        # Build a draft owned by a different user_id within the
        # SAME tenant -- the endpoint must scope to the calling user.
        other_user_id = uuid.uuid4()
        db_session.add(User(
            id=other_user_id, tenant_id=test_tenant_id,
            email="other@example.com", password_hash="x",
            role="FOUNDER", is_active=True,
        ))
        await db_session.flush()
        draft = await _make_research_draft(
            db_session,
            tenant_id=test_tenant_id, user_id=other_user_id,
            kind="career",
        )
        user = _FakeUser(id=test_user_id, tenant_id=test_tenant_id)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await _post_from_draft(
                db_session, user, draft_kind="career", draft_ref=draft.id,
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_unseeded_department_409(self, db_session):
        # Use a fresh tenant + user that have NO departments seeded --
        # the WorkstreamService.start() commits inside, so we can't
        # rely on rollback to clear other tests' seed data. A
        # never-before-seen tenant guarantees the dept lookup fails.
        fresh_tenant_id = uuid.uuid4()
        fresh_user_id = uuid.uuid4()
        db_session.add(Tenant(id=fresh_tenant_id, name="empty", slug="empty"))
        db_session.add(User(
            id=fresh_user_id, tenant_id=fresh_tenant_id,
            email="empty@example.com", password_hash="x",
            role="FOUNDER", is_active=True,
        ))
        await db_session.flush()
        draft = await _make_research_draft(
            db_session, tenant_id=fresh_tenant_id, user_id=fresh_user_id,
            kind="career",
        )
        user = _FakeUser(id=fresh_user_id, tenant_id=fresh_tenant_id)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await _post_from_draft(
                db_session, user, draft_kind="career", draft_ref=draft.id,
            )
        assert exc.value.status_code == 409
        detail = exc.value.detail
        assert (
            isinstance(detail, dict)
            and detail.get("code") == "department_not_seeded"
        )
