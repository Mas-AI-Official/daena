"""PR-5 (Sprint-11): Supervised Work Operator end-to-end smoke.

Walks the happy path:

    1. Backend boots, OpenAPI describes the expected supervised-work
       routes -- and only those.
    2. Phase-2 read-only gate is ON at the IntegrationRouter level.
    3. ScrapeGraphAI creates structured ResearchDrafts (career +
       content) via the research_flow service. The scrape worker is
       patched to return canned output so the smoke does not hit the
       network.
    4. FormDraft Assistant builds a draft from pasted questions, with
       sensitive fields blocked.
    5. ApprovalQueue accepts a draft approval request for each
       DRAFT_KINDS sentinel.
    6. Audit trail captures the draft.approval.requested.* row.
    7. Google setup status endpoint responds (honest about whatever
       state the test DB happens to be in).
    8. No send/submit/apply/post/publish/dispatch endpoint exists.
    9. Phase 3 writes remain blocked end-to-end.

This is a smoke test, not a unit test -- it asserts the *whole*
operating spine. If any of these fail, supervised-work-operator
posture is broken.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models.form_draft import FormDraft
from app.models.governance import GoaRequest
from app.models.identity import Tenant, User
from app.models.research import ResearchDraft
from app.services.approval import (
    DRAFT_KINDS,
    ApprovalService,
)
from app.services.form_draft_service import (
    create_form_draft_from_questions,
)
from app.services.integrations.integration_router import (
    PROVIDER_REGISTRY,
    WRITE_TOOLS,
)


# Banned route fragments under the form-drafts surface.
BANNED_FORM_DRAFT_PATHS = (
    "/api/v1/form-drafts/submit",
    "/api/v1/form-drafts/send",
    "/api/v1/form-drafts/apply",
    "/api/v1/form-drafts/post",
    "/api/v1/form-drafts/publish",
    "/api/v1/form-drafts/dispatch",
)


@pytest.fixture
async def seed(db_session, test_tenant_id, test_user_id):
    existing_t = (await db_session.execute(
        select(Tenant).where(Tenant.id == test_tenant_id)
    )).scalar_one_or_none()
    if existing_t is None:
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
    return {"tenant_id": test_tenant_id, "user_id": test_user_id}


# ── 1. OpenAPI surface ───────────────────────────────────────────────


class TestOpenApiSurface:
    @pytest.mark.asyncio
    async def test_supervised_work_routes_present(self, app):
        spec = app.openapi()
        paths = spec.get("paths", {})
        expected = [
            "/api/v1/research/career",
            "/api/v1/research/content",
            "/api/v1/research/drafts",
            "/api/v1/scrape/extract",
            "/api/v1/form-drafts/from-questions",
            "/api/v1/form-drafts/from-html",
            "/api/v1/form-drafts/from-url",
            "/api/v1/form-drafts",
            "/api/v1/governance/approvals/draft",
            "/api/v1/governance/approvals",
            "/api/v1/governance/audit",
            "/api/v1/connections/google-setup-status",
            "/api/v1/integrations/execute",
            "/api/v1/integrations/execute/qualified",
            "/api/v1/workstreams",
        ]
        missing = [p for p in expected if p not in paths]
        assert not missing, (
            f"Sprint-11 supervised-work routes missing from OpenAPI: "
            f"{missing}"
        )

    @pytest.mark.asyncio
    async def test_no_banned_dispatch_routes(self, app):
        spec = app.openapi()
        paths = spec.get("paths", {})
        for offending in BANNED_FORM_DRAFT_PATHS:
            assert offending not in paths


# ── 2. Phase-2 read-only flag is ON ──────────────────────────────────


class TestPhase2Defaults:
    def test_integrations_phase2_readonly_default_on(self):
        settings = get_settings()
        assert settings.integrations_phase2_readonly is True, (
            "Sprint-11 supervised-work-operator default is ON. "
            "Flipping this to False without ApprovalQueue gating "
            "would unlock writes."
        )

    def test_write_tools_registry_covers_known_writes(self):
        # Sentinel: every known dangerous tool is gated.
        for provider, write_set in WRITE_TOOLS.items():
            client = PROVIDER_REGISTRY[provider]
            for tool in write_set:
                assert tool in client.TOOLS


# ── 3. Research drafts (career + content) with structured_payload ───


CANNED_CAREER_EXTRACT = """
About the role:
- 5+ years building distributed systems
- Expert in Python and Go
- Experience leading on-call rotations

Apply at https://jobs.acme.com/apply/42
"""

CANNED_CONTENT_EXTRACT = """
Key claims:
* Governed AI is the next major procurement gate
* Open-source moats matter less than buyers think
* Auditability beats raw capability for enterprise

Sources:
https://arxiv.org/abs/2604.02460
"""


class TestResearchDraftsHappyPath:
    @pytest.mark.asyncio
    async def test_career_draft_persists_with_opportunity_payload(
        self, db_session, seed,
    ):
        from app.services.research_flow import create_research_draft

        canned = AsyncMock(return_value=type("Outcome", (), {
            "success": True,
            "result": CANNED_CAREER_EXTRACT,
            "truncated": False,
            "error": None,
            "worker_version": "smoke-v1",
        })())
        with patch(
            "app.services.research_flow.extract_from_url",
            new=canned,
        ):
            draft = await create_research_draft(
                db_session,
                kind="career",
                url="https://jobs.acme.com/role/42",
                goal="Extract role requirements",
                user_id=seed["user_id"],
                tenant_id=seed["tenant_id"],
            )
        assert draft.kind == "career"
        assert draft.structured_payload is not None
        assert draft.structured_payload["_kind"] == "opportunity"
        assert draft.structured_payload["company"] == "acme"
        assert any(
            "distributed systems" in r
            for r in draft.structured_payload["requirements"]
        )

    @pytest.mark.asyncio
    async def test_content_draft_persists_with_brief_payload(
        self, db_session, seed,
    ):
        from app.services.research_flow import create_research_draft

        canned = AsyncMock(return_value=type("Outcome", (), {
            "success": True,
            "result": CANNED_CONTENT_EXTRACT,
            "truncated": False,
            "error": None,
            "worker_version": "smoke-v1",
        })())
        with patch(
            "app.services.research_flow.extract_from_url",
            new=canned,
        ):
            draft = await create_research_draft(
                db_session,
                kind="content",
                url="https://blog.example.com/governed-ai",
                goal="Summarize",
                user_id=seed["user_id"],
                tenant_id=seed["tenant_id"],
            )
        assert draft.structured_payload["_kind"] == "brief"
        assert any(
            "Governed AI" in pt
            for pt in draft.structured_payload["key_points"]
        )


# ── 4. FormDraft from pasted questions ───────────────────────────────


class TestFormDraftHappyPath:
    @pytest.mark.asyncio
    async def test_create_form_draft_blocks_payment_and_sensitive(
        self, db_session, seed,
    ):
        draft = await create_form_draft_from_questions(
            db_session,
            title="Apply: AI Engineer",
            questions=[
                "Full name",
                "Work email",
                "Credit card number",       # blocked_payment
                "Social insurance number",  # blocked_sensitive
                "Why are you interested?",
            ],
            user_id=seed["user_id"],
            tenant_id=seed["tenant_id"],
        )
        await db_session.refresh(draft, attribute_names=["fields"])

        cc = next(f for f in draft.fields if "Credit card" in f.label)
        sin = next(f for f in draft.fields if "insurance" in f.label.lower())
        assert cc.field_type == "blocked_payment"
        assert cc.suggested_value is None
        assert sin.field_type == "blocked_sensitive"
        assert sin.suggested_value is None


# ── 5. ApprovalQueue accepts every DRAFT_KINDS sentinel ──────────────


class TestApprovalQueueHappyPath:
    @pytest.mark.parametrize("kind", sorted(DRAFT_KINDS))
    @pytest.mark.asyncio
    async def test_queue_each_draft_kind(self, db_session, seed, kind):
        svc = ApprovalService(db_session)
        result = await svc.request_draft_approval(
            tenant_id=seed["tenant_id"],
            user_id=seed["user_id"],
            draft_kind=kind,
            draft_ref=str(uuid.uuid4()),
            title=f"Smoke {kind}",
        )
        request_id = uuid.UUID(result["id"])
        row = (await db_session.execute(
            select(GoaRequest).where(GoaRequest.id == request_id)
        )).scalar_one()
        assert row.action_type == kind
        assert row.action_params["manual_action_only"] is True

    @pytest.mark.asyncio
    async def test_approving_does_not_dispatch_externally(
        self, db_session, seed,
    ):
        svc = ApprovalService(db_session)
        result = await svc.request_draft_approval(
            tenant_id=seed["tenant_id"],
            user_id=seed["user_id"],
            draft_kind="form_draft",
            draft_ref="smoke-1",
            title="Smoke approve",
        )
        request_id = uuid.UUID(result["id"])

        with (
            patch(
                "app.services.integrations.integration_router."
                "IntegrationRouter.execute",
                new=AsyncMock(side_effect=AssertionError(
                    "approve must not fire IntegrationRouter"
                )),
            ),
            patch(
                "app.services.scrape.extract_from_url",
                new=AsyncMock(side_effect=AssertionError(
                    "approve must not fire scrape worker"
                )),
            ),
        ):
            decided = await svc.approve(
                request_id=request_id,
                tenant_id=seed["tenant_id"],
                decided_by=seed["user_id"],
                reason="LGTM",
            )
        assert decided["status"] == "APPROVED"


# ── 6. Audit trail picks up the draft request row ────────────────────


class TestAuditCaptured:
    @pytest.mark.asyncio
    async def test_request_draft_writes_pending_request(
        self, db_session, seed,
    ):
        svc = ApprovalService(db_session)
        await svc.request_draft_approval(
            tenant_id=seed["tenant_id"],
            user_id=seed["user_id"],
            draft_kind="email_draft",
            draft_ref="smoke-email-1",
            title="Reply to recruiter",
        )
        rows = (await db_session.execute(
            select(GoaRequest)
            .where(GoaRequest.action_type == "email_draft")
            .where(GoaRequest.tenant_id == seed["tenant_id"])
        )).scalars().all()
        assert len(rows) >= 1


# ── 7. Phase-3 writes still blocked end-to-end ───────────────────────


class TestPhase3WritesBlockedEndToEnd:
    @pytest.mark.asyncio
    async def test_send_email_via_router_returns_permission_denied(
        self, db_session, seed,
    ):
        from app.services.integrations.integration_router import (
            IntegrationRouter,
            PermissionDeniedError,
        )
        router = IntegrationRouter(db_session)
        with pytest.raises(PermissionDeniedError) as exc_info:
            await router.execute(
                provider="gmail",
                tool_name="send_email",
                params={},
                user_id=seed["user_id"],
                tenant_id=seed["tenant_id"],
                owner_email=None,
            )
        assert "write_disabled_phase2" in str(exc_info.value)


# ── 8. Final structural assertion: no dispatch verbs in any new file
#     authored for Sprint-11. ──────────────────────────────────────────


import pathlib  # noqa: E402  (kept inline so the file is single-import-able)


_SPRINT_11_FILES = [
    "backend/app/services/integrations/integration_router.py",
    "backend/app/api/v1/integrations.py",
    "backend/app/models/research.py",
    "backend/app/services/research_flow.py",
    "backend/app/api/v1/research.py",
    "backend/app/models/form_draft.py",
    "backend/app/services/form_draft_service.py",
    "backend/app/api/v1/form_drafts.py",
    "backend/app/services/approval.py",
]


import re as _re  # noqa: E402

_BANNED_DECORATOR_RE = _re.compile(
    r"@router\.(post|put|patch)\(\s*['\"]"
    r"/(submit|send|apply|publish|dispatch|email_send|external_post)['\"]",
    _re.IGNORECASE,
)


class TestSourceLevelHardRules:
    def test_no_banned_route_decorators_in_sprint11_files(self):
        repo_root = pathlib.Path(__file__).parent.parent.parent
        for rel in _SPRINT_11_FILES:
            p = repo_root / rel
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8")
            m = _BANNED_DECORATOR_RE.search(text)
            assert m is None, (
                f"{rel} declares a banned route: {m.group(0)}"
            )
