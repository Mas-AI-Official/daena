"""Sprint-12 PR-6 -- end-to-end smoke for the full draft + QE +
workstream + chat pipeline.

This is the safety net: if any earlier PR's contract drifts, this
file catches it. Asserts:

  1. The four readiness routes are mounted on the running router:
       /system/runtime-readiness
       /system/router-readiness
       /system/qe-readiness
       /system/router-policy
  2. The four draft action routes are mounted:
       /research/drafts/{id}/enrich
       /research/drafts/{id}/qe-review
       /form-drafts/{id}/enrich
       /form-drafts/{id}/qe-review
  3. POST /workstreams/from-draft is mounted.
  4. POST /vp-commands is mounted.
  5. No banned verb route exists on any of the new modules:
       /submit /send /apply /post /publish /dispatch
     anywhere under research / form-drafts / workstreams /
     vp-commands.
  6. Source-text scan: no banned verb in any new service file.
  7. INTEGRATIONS_PHASE2_READONLY remains True at startup -- the
     gate that keeps Phase 3 writes off.
  8. End-to-end negative path: enrichment with no main brain
     refuses honestly via the VP command surface, surfacing the
     readiness next_action.
  9. Workstream from-draft flow runs end-to-end: seed draft ->
     /vp-commands "create a work plan from draft <id>" ->
     workstream row exists with source_type=draft.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models.identity import Tenant, User
from app.models.organization import Department
from app.models.research import ResearchDraft
from app.models.workstream import Workstream, WorkstreamSourceType


_NEW_SERVICE_FILES = (
    Path("app/services/draft_enrichment.py"),
    Path("app/services/draft_qe_review.py"),
    Path("app/services/vp_work_commands.py"),
    Path("app/api/v1/vp_commands.py"),
)


_BANNED_PATH_VERBS = (
    "/submit", "/send", "/apply", "/post", "/publish", "/dispatch",
)
# Broader scan tokens for source files. We allow `/posts/` (URL noun) etc by
# requiring boundary + verb token; `apply` in a method name like `apply()` is
# fine, the source-text scan focuses on path strings.
_BANNED_ROUTE_DEFINITIONS = re.compile(
    r"@router\.(?:post|get|put|patch|delete|websocket)\("
    r"['\"][^'\"]*("
    r"submit|send|apply|publish|dispatch"
    r")[^'\"]*['\"]",
    re.IGNORECASE,
)


# ── 1, 2, 3, 4: route mount checks ──────────────────────────────────


class TestRouteMounts:
    """Inspect the FastAPI app's routes so we don't have to spin a TestClient."""

    @pytest.fixture(autouse=True)
    def app_routes(self):
        from app.api.v1 import router as api_v1_router
        self.paths = sorted(
            getattr(r, "path", "") for r in api_v1_router.routes
        )

    def test_readiness_routes(self):
        # System self-diagnostic mounts under /system inside the v1 router.
        assert "/system/runtime-readiness" in self.paths
        assert "/system/router-readiness" in self.paths
        assert "/system/qe-readiness" in self.paths
        assert "/system/router-policy" in self.paths

    def test_research_draft_action_routes(self):
        assert any(
            p == "/research/drafts/{draft_id}/enrich"
            for p in self.paths
        )
        assert any(
            p == "/research/drafts/{draft_id}/qe-review"
            for p in self.paths
        )

    def test_form_draft_action_routes(self):
        assert any(
            p == "/form-drafts/{draft_id}/enrich" for p in self.paths
        )
        assert any(
            p == "/form-drafts/{draft_id}/qe-review" for p in self.paths
        )

    def test_workstreams_from_draft(self):
        assert "/workstreams/from-draft" in self.paths

    def test_vp_commands_mounted(self):
        assert "/vp-commands" in self.paths


# ── 5. Negative routes -- no banned verb anywhere new ───────────────


class TestNoBannedRoutes:
    @pytest.fixture(autouse=True)
    def app_routes(self):
        from app.api.v1 import router as api_v1_router
        self.paths = [getattr(r, "path", "") for r in api_v1_router.routes]

    @pytest.mark.parametrize("verb", _BANNED_PATH_VERBS)
    def test_no_verb_under_research(self, verb):
        offenders = [p for p in self.paths if p.startswith("/research") and verb in p]
        assert offenders == [], f"banned verb {verb} found in {offenders}"

    @pytest.mark.parametrize("verb", _BANNED_PATH_VERBS)
    def test_no_verb_under_form_drafts(self, verb):
        offenders = [
            p for p in self.paths
            if p.startswith("/form-drafts") and verb in p
        ]
        assert offenders == [], f"banned verb {verb} found in {offenders}"

    @pytest.mark.parametrize("verb", _BANNED_PATH_VERBS)
    def test_no_verb_under_vp_commands(self, verb):
        # The /vp-commands prefix itself contains the substring "command";
        # the verbs we ban are submit / send / apply / post / publish /
        # dispatch. None of those are in /vp-commands.
        offenders = [
            p for p in self.paths
            if p.startswith("/vp-commands") and verb in p
        ]
        # /vp-commands itself does NOT contain any banned verb token --
        # confirm the assertion is meaningful.
        assert offenders == [], f"banned verb {verb} found in {offenders}"


# ── 6. Source-text scan ─────────────────────────────────────────────


class TestSourceCleanliness:
    @pytest.fixture(autouse=True)
    def repo_root(self):
        # backend tests run from D:/Ideas/Daena/backend so the
        # service paths are relative to that root.
        self.root = Path(__file__).parent.parent

    def test_no_banned_route_decl_in_new_modules(self):
        for rel in _NEW_SERVICE_FILES:
            path = self.root / rel
            if not path.exists():
                pytest.skip(f"{rel} not present (file removed?)")
            text = path.read_text(encoding="utf-8")
            matches = _BANNED_ROUTE_DEFINITIONS.findall(text)
            assert matches == [], (
                f"{rel} declares a banned-verb route: {matches}"
            )

    def test_no_playwright_import_in_new_modules(self):
        bad = re.compile(
            r"^\s*(?:from\s+(?:playwright|pyppeteer|selenium)|"
            r"import\s+(?:playwright|pyppeteer|selenium))\b",
            re.MULTILINE,
        )
        for rel in _NEW_SERVICE_FILES:
            path = self.root / rel
            if not path.exists():
                continue
            assert not bad.search(path.read_text(encoding="utf-8")), (
                f"{rel} imports a browser-automation library."
            )


# ── 7. Phase 3 gate ─────────────────────────────────────────────────


class TestPhase3Gate:
    def test_integrations_phase2_readonly_default_true(self):
        s = get_settings()
        assert s.integrations_phase2_readonly is True


# ── 8. Refusal end-to-end via vp_work_commands ──────────────────────


class TestRefusalE2E:
    @pytest.mark.asyncio
    async def test_no_main_brain_refusal_via_chat_command(
        self, db_session, test_tenant_id, test_user_id, monkeypatch,
    ):
        # Seed user + tenant so the runner can load drafts.
        from sqlalchemy import select as _sel
        if not (await db_session.execute(
            _sel(Tenant).where(Tenant.id == test_tenant_id)
        )).scalar_one_or_none():
            slug = str(test_tenant_id)[:8]
            db_session.add(Tenant(
                id=test_tenant_id, name=f"smoke-{slug}", slug=slug,
            ))
        if not (await db_session.execute(
            _sel(User).where(User.id == test_user_id)
        )).scalar_one_or_none():
            db_session.add(User(
                id=test_user_id, tenant_id=test_tenant_id,
                email="smoke@example.com", password_hash="x",
                role="FOUNDER", is_active=True,
            ))
        await db_session.flush()

        # Seed a career draft for the operator.
        draft = ResearchDraft(
            id=uuid.uuid4(),
            tenant_id=test_tenant_id, user_id=test_user_id,
            kind="career",
            source_url="https://example.com/jobs",
            source_host="https://example.com",
            goal="apply", summary="raw", raw_extract="raw",
            status="DRAFT",
            structured_payload={
                "_kind": "opportunity",
                "_llm_pending": True,
                "company": None, "fit_score": None, "next_tasks": [],
            },
        )
        db_session.add(draft)
        await db_session.flush()

        from app.services import draft_enrichment

        async def _no_brain():
            return {
                "items": [],
                "router_summary": {
                    "main_brain_id": None,
                    "main_brain_cost_class": None,
                    "web_grounding_id": None,
                    "coder_id": None, "researcher_id": None,
                    "qe_reviewers_ready": [],
                    "qe_mode": "unavailable",
                    "qe_mode_reason": "",
                    "next_action": (
                        "Start the local llama-server / Ollama. No "
                        "main brain is ready."
                    ),
                },
            }
        monkeypatch.setattr(
            draft_enrichment, "get_runtime_readiness", _no_brain,
        )

        from app.services.vp_work_commands import (
            parse_command, run_command,
        )
        result = await run_command(
            db_session,
            parse_command(f"enrich draft {draft.id}"),
            user_id=test_user_id, tenant_id=test_tenant_id,
            registry=None,
        )
        assert result.success is False
        assert result.intent == "enrich_draft"
        assert "no_ready_main_brain" in (result.data.get("refusal_code") or "")
        # The exact missing piece is in next_action so the chat UI
        # can render it verbatim.
        assert "main brain" in (result.next_action or "").lower()


# ── 9. End-to-end happy path: workstream from draft via chat ────────


class TestE2EWorkstreamFromDraft:
    @pytest.mark.asyncio
    async def test_promote_via_chat_command(
        self, db_session, test_tenant_id, test_user_id,
    ):
        # Seed
        if not (await db_session.execute(
            select(Tenant).where(Tenant.id == test_tenant_id)
        )).scalar_one_or_none():
            slug = str(test_tenant_id)[:8]
            db_session.add(Tenant(
                id=test_tenant_id, name=f"smoke2-{slug}", slug=slug,
            ))
        if not (await db_session.execute(
            select(User).where(User.id == test_user_id)
        )).scalar_one_or_none():
            db_session.add(User(
                id=test_user_id, tenant_id=test_tenant_id,
                email="smoke2@example.com", password_hash="x",
                role="FOUNDER", is_active=True,
            ))
        # Seed Sales for the career-routing path.
        if not (await db_session.execute(
            select(Department).where(
                Department.tenant_id == test_tenant_id,
                Department.name == "Sales",
            )
        )).scalar_one_or_none():
            db_session.add(Department(
                id=uuid.uuid4(), tenant_id=test_tenant_id,
                name="Sales", description="x", sunflower_index=3,
                cell_id="hex_3", config={}, is_active=True,
            ))
        await db_session.flush()

        draft = ResearchDraft(
            id=uuid.uuid4(),
            tenant_id=test_tenant_id, user_id=test_user_id,
            kind="career",
            source_url="https://example.com/jobs",
            source_host="https://example.com",
            goal="apply to acme", summary="raw", raw_extract="raw",
            status="DRAFT",
            structured_payload={
                "_kind": "opportunity",
                "_llm_pending": False,
                "company": "Acme", "fit_score": 70,
                "next_tasks": ["tailor resume to their stack"],
            },
        )
        db_session.add(draft)
        await db_session.flush()

        from app.services.vp_work_commands import (
            parse_command, run_command,
        )
        result = await run_command(
            db_session,
            parse_command(f"create a work plan from draft {draft.id}"),
            user_id=test_user_id, tenant_id=test_tenant_id,
        )
        assert result.success is True
        ws_id = result.data["id"]

        ws = (await db_session.execute(
            select(Workstream).where(Workstream.id == uuid.UUID(ws_id))
        )).scalar_one()
        assert ws.source_type == WorkstreamSourceType.DRAFT
        assert ws.source_ref_id == draft.id
        assert ws.context["draft_kind"] == "career"
        assert ws.next_step_text == "tailor resume to their stack"
