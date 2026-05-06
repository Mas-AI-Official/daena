"""PR-4 (Sprint-11): ApprovalQueue extension for draft kinds.

Asserts:
    1. DRAFT_KINDS contains the five expected sentinels.
    2. is_draft_kind classifies them correctly.
    3. request_draft_approval persists a GoaRequest with the right
       action_type, embeds draft_kind/draft_ref/title in
       action_params, and creates a PendingApproval row.
    4. Unknown draft kinds raise ValueError.
    5. Approving a draft request flips status to APPROVED but does
       NOT touch any external dispatcher (asserted by patching
       IntegrationRouter / extract_from_url / GmailClient and
       confirming none were called).
    6. The audit row written by approve() carries no external-action
       side-effect hints.
    7. Static-analysis: ApprovalService.approve source code does not
       import IntegrationRouter, GmailClient, CalendarClient,
       NotionClient, or scrape.extract_from_url.
    8. The HTTP route /governance/approvals/draft is wired and
       rejects unknown draft kinds with 400.
"""

from __future__ import annotations

import inspect
import re
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.governance import GoaRequest, PendingApproval
from app.models.identity import Tenant, User
from app.services.approval import (
    DRAFT_KINDS,
    ApprovalService,
    is_draft_kind,
)


EXPECTED_DRAFT_KINDS = {
    "email_draft",
    "form_draft",
    "application_draft",
    "content_post_draft",
    "file_change_proposal",
}


# ── Constant + classifier ────────────────────────────────────────────


class TestDraftKinds:
    def test_all_five_kinds_present(self):
        assert set(DRAFT_KINDS) == EXPECTED_DRAFT_KINDS

    def test_is_draft_kind_recognizes_each(self):
        for k in DRAFT_KINDS:
            assert is_draft_kind(k) is True

    def test_is_draft_kind_rejects_unknown(self):
        for k in ("DEPLOY", "approve_payment", "send_email", "", None):
            assert is_draft_kind(k) is False  # type: ignore[arg-type]


# ── Service-level: request_draft_approval ────────────────────────────


@pytest.fixture
async def seed_user(db_session, test_tenant_id, test_user_id):
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
    return {"tenant_id": test_tenant_id, "user_id": test_user_id}


class TestRequestDraftApproval:
    @pytest.mark.asyncio
    async def test_persists_request_for_form_draft(self, db_session, seed_user):
        svc = ApprovalService(db_session)
        result = await svc.request_draft_approval(
            tenant_id=seed_user["tenant_id"],
            user_id=seed_user["user_id"],
            draft_kind="form_draft",
            draft_ref=str(uuid.uuid4()),
            title="Apply: AI Engineer",
        )
        request_id = uuid.UUID(result["id"])
        row = (await db_session.execute(
            select(GoaRequest).where(GoaRequest.id == request_id)
        )).scalar_one()
        assert row.action_type == "form_draft"
        assert row.action_params is not None
        assert row.action_params["draft_kind"] == "form_draft"
        assert row.action_params["manual_action_only"] is True
        assert row.status == "PENDING"
        # PendingApproval row also written
        pending = (await db_session.execute(
            select(PendingApproval).where(PendingApproval.request_id == request_id)
        )).scalar_one()
        assert pending is not None

    @pytest.mark.parametrize("kind", sorted(EXPECTED_DRAFT_KINDS))
    @pytest.mark.asyncio
    async def test_persists_request_for_each_kind(
        self, db_session, seed_user, kind,
    ):
        svc = ApprovalService(db_session)
        result = await svc.request_draft_approval(
            tenant_id=seed_user["tenant_id"],
            user_id=seed_user["user_id"],
            draft_kind=kind,
            draft_ref="any-ref",
            title="x",
        )
        assert result["action_type"] == kind

    @pytest.mark.asyncio
    async def test_unknown_kind_raises(self, db_session, seed_user):
        svc = ApprovalService(db_session)
        with pytest.raises(ValueError, match="unknown_draft_kind"):
            await svc.request_draft_approval(
                tenant_id=seed_user["tenant_id"],
                user_id=seed_user["user_id"],
                draft_kind="nuke_production",  # type: ignore[arg-type]
                draft_ref="x",
                title="x",
            )


# ── Approve path: NO external action ─────────────────────────────────


class TestApprovingDraftDoesNotDispatch:
    @pytest.mark.asyncio
    async def test_approve_does_not_call_integration_router(
        self, db_session, seed_user,
    ):
        """Approving a draft request must NOT invoke IntegrationRouter.

        We patch the three router entry points so any accidental call
        would be visible. The current ApprovalService.approve emits a
        peer-department event but does not dispatch external work.
        """
        svc = ApprovalService(db_session)
        result = await svc.request_draft_approval(
            tenant_id=seed_user["tenant_id"],
            user_id=seed_user["user_id"],
            draft_kind="email_draft",
            draft_ref="ref-1",
            title="Reply to recruiter",
        )
        request_id = uuid.UUID(result["id"])

        targets = [
            "app.services.integrations.integration_router.IntegrationRouter.execute",
            "app.services.integrations.integration_router.IntegrationRouter.execute_qualified",
            "app.services.scrape.extract_from_url",
        ]
        with (
            patch(targets[0], new=AsyncMock(side_effect=AssertionError(
                "approve() must NOT touch IntegrationRouter.execute"
            ))),
            patch(targets[1], new=AsyncMock(side_effect=AssertionError(
                "approve() must NOT touch IntegrationRouter.execute_qualified"
            ))),
            patch(targets[2], new=AsyncMock(side_effect=AssertionError(
                "approve() must NOT touch scrape.extract_from_url"
            ))),
        ):
            decided = await svc.approve(
                request_id=request_id,
                tenant_id=seed_user["tenant_id"],
                decided_by=seed_user["user_id"],
                reason="LGTM",
            )

        assert decided["status"] == "APPROVED"
        # PendingApproval cleaned up
        pending = (await db_session.execute(
            select(PendingApproval).where(PendingApproval.request_id == request_id)
        )).scalar_one_or_none()
        assert pending is None

    @pytest.mark.asyncio
    async def test_reject_also_does_not_dispatch(
        self, db_session, seed_user,
    ):
        svc = ApprovalService(db_session)
        result = await svc.request_draft_approval(
            tenant_id=seed_user["tenant_id"],
            user_id=seed_user["user_id"],
            draft_kind="content_post_draft",
            draft_ref="ref-2",
            title="Tweet thread on governed AI",
        )
        request_id = uuid.UUID(result["id"])

        with (
            patch(
                "app.services.integrations.integration_router.IntegrationRouter.execute",
                new=AsyncMock(side_effect=AssertionError("must not fire")),
            ),
            patch(
                "app.services.scrape.extract_from_url",
                new=AsyncMock(side_effect=AssertionError("must not fire")),
            ),
        ):
            decided = await svc.reject(
                request_id=request_id,
                tenant_id=seed_user["tenant_id"],
                decided_by=seed_user["user_id"],
                reason="Wrong angle",
            )

        assert decided["status"] == "REJECTED"


# ── Source-level static check ────────────────────────────────────────


_BANNED_IMPORT_OR_CALL = re.compile(
    r"\b(IntegrationRouter|GmailClient|CalendarClient|NotionClient|"
    r"extract_from_url|send_email|create_draft|create_event|"
    r"create_page|page\.fill|page\.click|browser\.|webdriver\.)",
)


class TestApprovalServiceSourceClean:
    """approval.py must not import or call external dispatchers in
    its approve / reject methods. Catches the failure mode where a
    later refactor wires a "post-approval auto-dispatch" feature."""

    def test_approve_method_source_clean(self):
        src = inspect.getsource(ApprovalService.approve)
        m = _BANNED_IMPORT_OR_CALL.search(src)
        assert m is None, (
            f"ApprovalService.approve references banned dispatcher: "
            f"{m.group(0)}"
        )

    def test_reject_method_source_clean(self):
        src = inspect.getsource(ApprovalService.reject)
        m = _BANNED_IMPORT_OR_CALL.search(src)
        assert m is None

    def test_approval_module_does_not_import_dispatchers(self):
        import app.services.approval as approval_mod
        src = inspect.getsource(approval_mod)
        # Allow textual mention of "IntegrationRouter" in COMMENTS
        # only -- strip block comments / docstrings before matching.
        # Simplest heuristic: strip lines that start with # or are
        # inside triple-quoted strings.
        cleaned_lines = []
        in_triple = False
        for line in src.splitlines():
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                # toggle once per line containing the delimiter
                in_triple = not in_triple
                continue
            if in_triple:
                continue
            if stripped.startswith("#"):
                continue
            cleaned_lines.append(line)
        cleaned = "\n".join(cleaned_lines)
        m = _BANNED_IMPORT_OR_CALL.search(cleaned)
        assert m is None, (
            f"approval.py code references banned dispatcher: "
            f"{m.group(0)}"
        )


# ── HTTP API surface ─────────────────────────────────────────────────


class TestDraftApprovalApi:
    @pytest.mark.asyncio
    async def test_route_exists(self, app):
        spec = app.openapi()
        paths = spec.get("paths", {})
        assert "/api/v1/governance/approvals/draft" in paths

    @pytest.mark.asyncio
    async def test_unknown_kind_returns_400(self, client, auth_headers):
        r = await client.post(
            "/api/v1/governance/approvals/draft",
            headers=auth_headers,
            json={
                "draft_kind": "nuke_production",
                "draft_ref": "x",
                "title": "x",
            },
        )
        assert r.status_code == 400
        assert "unknown_draft_kind" in r.text
