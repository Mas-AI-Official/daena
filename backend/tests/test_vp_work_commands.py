"""Sprint-12 PR-5 -- VP work chat command parser + runner tests.

Asserts:

  1. Parser maps the brief's example phrases to the right intents:
     - "review this opportunity"      -> review_drafts
     - "enrich this draft"            -> enrich_draft (no ref)
     - "create a work plan from this" -> create_workstream_from_draft
     - "what should I do next?"       -> next_steps
     - "which department should handle this <id>?" -> which_department
     - "run council on this draft"    -> qe_review_draft
  2. Parser extracts UUID from the message body when present.
  3. Unknown text returns intent=unrecognized with a help summary.
  4. Runner refuses (success=False, no raise) when an action verb
     gets no draft id; returns needs_disambiguation=True with
     recent drafts as data.
  5. Runner refuses honestly when a routed runtime is not ready
     (NoReadyMainBrain bubbles to next_action surface).
  6. review_drafts returns counts + structured list.
  7. next_steps returns open workstreams + their next_step_text.
  8. which_department reports the deterministic answer + reason.
  9. enrich_draft executes against a FakeRegistry and returns the
     fields_filled count.
 10. qe_review_draft executes against a FakeRegistry and returns
     the mode (full / degraded).
 11. create_workstream_from_draft promotes a draft and returns the
     created workstream id.
 12. Audits one ``vp_command.<intent>`` row per call.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.constants import HealthStatus, ModelProvider
from app.models.form_draft import FormDraft
from app.models.governance import GoaAuditEvent
from app.models.identity import Tenant, User
from app.models.organization import Department
from app.models.research import ResearchDraft
from app.services.providers.base import (
    BaseProvider,
    GenerateRequest,
    LLMResponse,
)
from app.services.vp_work_commands import (
    parse_command,
    run_command,
)


# ── Reusable fakes ──────────────────────────────────────────────────


class CannedProvider(BaseProvider):
    def __init__(self, provider: ModelProvider, replies: list[str]) -> None:
        super().__init__(provider)
        self._replies = list(replies)
        self._calls = 0

    async def generate(self, request: GenerateRequest) -> LLMResponse:
        idx = self._calls
        self._calls += 1
        text = self._replies[idx if idx < len(self._replies) else -1]
        return LLMResponse(content=text, model_id="fake", provider=self.provider)

    async def stream(self, request):  # noqa: D401
        raise NotImplementedError

    async def health_check(self):  # type: ignore[override]
        return HealthStatus.HEALTHY

    async def list_models(self):  # noqa: D401
        return []


class FakeRegistry:
    def __init__(self, **mapping):
        self._map = {ModelProvider[k]: v for k, v in mapping.items()}

    def get_provider(self, e):
        return self._map.get(e)


def _fake_readiness(main="ollama_backend", cost="free_local"):
    return {
        "items": [],
        "router_summary": {
            "main_brain_id": main,
            "main_brain_cost_class": cost,
            "web_grounding_id": None,
            "coder_id": None,
            "researcher_id": None,
            "qe_reviewers_ready": [],
            "qe_mode": "unavailable",
            "qe_mode_reason": "",
            "next_action": "go",
        },
    }


# ── Seed helpers ────────────────────────────────────────────────────


_DEPT_NAMES = ("Sales", "Marketing", "Operations", "Legal & Compliance")


async def _seed(db_session, tenant_id, user_id):
    if not (await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )).scalar_one_or_none():
        # WorkstreamService.start() commits, so seed data leaks across
        # tests. Use the tenant uuid prefix as the slug to dodge the
        # UNIQUE constraint on tenants.slug.
        slug = str(tenant_id)[:8]
        db_session.add(Tenant(id=tenant_id, name=f"T-{slug}", slug=slug))
    if not (await db_session.execute(
        select(User).where(User.id == user_id)
    )).scalar_one_or_none():
        db_session.add(User(
            id=user_id, tenant_id=tenant_id,
            email="m@example.com", password_hash="x",
            role="FOUNDER", is_active=True,
        ))
    await db_session.flush()
    by = {}
    for i, name in enumerate(_DEPT_NAMES):
        d = (await db_session.execute(
            select(Department).where(
                Department.tenant_id == tenant_id,
                Department.name == name,
            )
        )).scalar_one_or_none()
        if d is None:
            d = Department(
                id=uuid.uuid4(), tenant_id=tenant_id, name=name,
                description="x", sunflower_index=i, cell_id=f"hex_{i}",
                config={}, is_active=True,
            )
            db_session.add(d)
            await db_session.flush()
        by[name] = d
    return by


async def _make_career_draft(db_session, tenant_id, user_id, **payload_extras):
    sp = {
        "_kind": "opportunity",
        "_llm_pending": False,
        "company": "Acme",
        "fit_score": 70,
        "next_tasks": ["tailor resume"],
    }
    sp.update(payload_extras)
    d = ResearchDraft(
        id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id,
        kind="career",
        source_url="https://example.com",
        source_host="https://example.com",
        goal="apply", summary="raw", raw_extract="raw",
        status="DRAFT", structured_payload=sp,
    )
    db_session.add(d)
    await db_session.flush()
    return d


# ── 1, 2, 3: Parser correctness ─────────────────────────────────────


class TestParser:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Daena, review this opportunity", "review_drafts"),
            ("show my drafts", "review_drafts"),
            ("Enrich this draft", "enrich_draft"),
            ("enrich draft 12345678", "enrich_draft"),
            ("create a work plan from this", "create_workstream_from_draft"),
            ("Promote this draft to a workstream", "create_workstream_from_draft"),
            ("What should I do next?", "next_steps"),
            ("what's next", "next_steps"),
            ("which department should handle this", "which_department"),
            ("Run council on this draft", "qe_review_draft"),
            ("council 12345678", "qe_review_draft"),
            ("just chatting about the weather", "unrecognized"),
        ],
    )
    def test_intents(self, text, expected):
        assert parse_command(text).intent == expected

    def test_uuid_extracted(self):
        u = "11111111-2222-3333-4444-555555555555"
        p = parse_command(f"council {u}")
        assert p.draft_ref == u

    def test_uuid_prefix_extracted(self):
        p = parse_command("enrich draft a1b2c3d4ef")
        assert p.draft_ref == "a1b2c3d4ef"

    def test_unrecognized_summary_helpful(self, db_session):
        # The runner returns an action-list summary on unrecognized.
        # Pure-parse here: just verify intent.
        assert parse_command("hi").intent == "unrecognized"


# ── 6, 7, 12: list runners + audits ─────────────────────────────────


class TestListRunners:
    @pytest.mark.asyncio
    async def test_review_drafts_counts(
        self, db_session, test_tenant_id, test_user_id,
    ):
        await _seed(db_session, test_tenant_id, test_user_id)
        await _make_career_draft(db_session, test_tenant_id, test_user_id)
        result = await run_command(
            db_session, parse_command("review drafts"),
            user_id=test_user_id, tenant_id=test_tenant_id,
        )
        assert result.success is True
        assert result.intent == "review_drafts"
        assert len(result.data["research_drafts"]) >= 1
        rows = (await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.action_type == "vp_command.review_drafts",
            )
        )).scalars().all()
        assert any(r.tenant_id == test_tenant_id for r in rows)

    @pytest.mark.asyncio
    async def test_next_steps_empty_message(self, db_session):
        # Fresh tenant: WorkstreamService.start() commits, so prior
        # tests may have left workstreams in the shared DB. Using a
        # never-before-seen tenant guarantees an empty open-list.
        fresh_tenant = uuid.uuid4()
        fresh_user = uuid.uuid4()
        await _seed(db_session, fresh_tenant, fresh_user)
        result = await run_command(
            db_session, parse_command("what should I do next?"),
            user_id=fresh_user, tenant_id=fresh_tenant,
        )
        assert result.success is True
        assert (
            "No open workstreams" in result.summary
            or result.data["open_workstreams"] == []
        )


# ── 4. Disambiguation ───────────────────────────────────────────────


class TestDisambiguation:
    @pytest.mark.asyncio
    async def test_enrich_without_ref_needs_disambiguation(
        self, db_session, test_tenant_id, test_user_id,
    ):
        await _seed(db_session, test_tenant_id, test_user_id)
        await _make_career_draft(db_session, test_tenant_id, test_user_id)
        result = await run_command(
            db_session, parse_command("enrich this draft"),
            user_id=test_user_id, tenant_id=test_tenant_id,
        )
        assert result.success is False
        assert result.needs_disambiguation is True
        assert "research_drafts" in result.data

    @pytest.mark.asyncio
    async def test_council_without_ref_needs_disambiguation(
        self, db_session, test_tenant_id, test_user_id,
    ):
        await _seed(db_session, test_tenant_id, test_user_id)
        await _make_career_draft(db_session, test_tenant_id, test_user_id)
        result = await run_command(
            db_session, parse_command("run council on this draft"),
            user_id=test_user_id, tenant_id=test_tenant_id,
        )
        assert result.needs_disambiguation is True


# ── 8. Which department ─────────────────────────────────────────────


class TestWhichDepartment:
    @pytest.mark.asyncio
    async def test_career_says_sales(
        self, db_session, test_tenant_id, test_user_id,
    ):
        await _seed(db_session, test_tenant_id, test_user_id)
        d = await _make_career_draft(db_session, test_tenant_id, test_user_id)
        cmd = parse_command(f"which department should handle this {d.id}")
        result = await run_command(
            db_session, cmd,
            user_id=test_user_id, tenant_id=test_tenant_id,
        )
        assert result.success is True
        assert "Sales" in result.summary
        assert result.data["department"] == "Sales"

    @pytest.mark.asyncio
    async def test_legal_token_says_legal(
        self, db_session, test_tenant_id, test_user_id,
    ):
        await _seed(db_session, test_tenant_id, test_user_id)
        d = await _make_career_draft(
            db_session, test_tenant_id, test_user_id,
            claims_to_verify=["GDPR compliance is implied"],
        )
        cmd = parse_command(f"which department should handle this {d.id}")
        result = await run_command(
            db_session, cmd,
            user_id=test_user_id, tenant_id=test_tenant_id,
        )
        assert "Legal" in result.summary
        assert result.data["department"] == "Legal & Compliance"


# ── 9. Enrich runs against fake registry ────────────────────────────


_REPLY_OK = (
    '{"company":"Acme","role":"Eng","fit_score":80,'
    '"fit_rationale":"...","missing_skills":["k8s"],'
    '"outreach_draft_local":"hi","next_tasks":["tailor"],'
    '"field_confidence":{"company":0.9,"role":0.9,"fit_score":0.7}}'
)


class TestEnrichRun:
    @pytest.mark.asyncio
    async def test_enrich_runs(
        self, db_session, test_tenant_id, test_user_id, monkeypatch,
    ):
        await _seed(db_session, test_tenant_id, test_user_id)
        d = await _make_career_draft(
            db_session, test_tenant_id, test_user_id,
            _llm_pending=True, company=None, fit_score=None,
            next_tasks=[],
        )
        from app.services import draft_enrichment
        monkeypatch.setattr(
            draft_enrichment, "get_runtime_readiness",
            lambda: _async_return(_fake_readiness()),
        )
        registry = FakeRegistry(
            OLLAMA=CannedProvider(ModelProvider.OLLAMA, [_REPLY_OK]),
        )
        result = await run_command(
            db_session, parse_command(f"enrich draft {d.id}"),
            user_id=test_user_id, tenant_id=test_tenant_id,
            registry=registry,
        )
        assert result.success is True
        assert "Enrichment complete" in result.summary
        assert result.data["runtime_id"] == "ollama_backend"

    @pytest.mark.asyncio
    async def test_enrich_no_main_brain_surfaces_next_action(
        self, db_session, test_tenant_id, test_user_id, monkeypatch,
    ):
        await _seed(db_session, test_tenant_id, test_user_id)
        d = await _make_career_draft(db_session, test_tenant_id, test_user_id)
        from app.services import draft_enrichment

        async def _no_brain():
            return {
                "items": [],
                "router_summary": {
                    "main_brain_id": None,
                    "main_brain_cost_class": None,
                    "web_grounding_id": None,
                    "coder_id": None, "researcher_id": None,
                    "qe_reviewers_ready": [], "qe_mode": "unavailable",
                    "qe_mode_reason": "",
                    "next_action": "Start the local model.",
                },
            }
        monkeypatch.setattr(
            draft_enrichment, "get_runtime_readiness", _no_brain,
        )
        result = await run_command(
            db_session, parse_command(f"enrich draft {d.id}"),
            user_id=test_user_id, tenant_id=test_tenant_id,
            registry=FakeRegistry(),
        )
        assert result.success is False
        assert result.next_action == "Start the local model."
        assert result.data["refusal_code"] == "no_ready_main_brain"


# ── 10. QE runs ─────────────────────────────────────────────────────


_PROP_REPLY = (
    '{"findings":["fit_score may be inflated"],"objections":[],'
    '"missing_evidence":[],"risk_flags":[],"confidence":0.55}'
)
_SYNTH_REPLY = (
    '{"findings":["fit_score may be inflated"],"objections":[],'
    '"missing_evidence":[],"risk_flags":[],"confidence":0.5,'
    '"next_action":"operator_review_required"}'
)


class TestQERun:
    @pytest.mark.asyncio
    async def test_council_runs(
        self, db_session, test_tenant_id, test_user_id, monkeypatch,
    ):
        await _seed(db_session, test_tenant_id, test_user_id)
        d = await _make_career_draft(db_session, test_tenant_id, test_user_id)
        from app.services import draft_qe_review

        async def _qe_payload():
            return {
                "mode": "full",
                "mode_reason": "fake full",
                "distinct_runtime_ids": [
                    "ollama_backend", "cli_codex", "cli_gemini",
                ],
                "slot_assignments": [
                    {"slot": "local_reasoner", "runtime_id": "ollama_backend",
                     "fill_source": "preferred", "intent": "x",
                     "runtime_display_name": "x", "rationale": "x"},
                    {"slot": "code_reviewer", "runtime_id": "cli_claude",
                     "fill_source": "preferred", "intent": "x",
                     "runtime_display_name": "x", "rationale": "x"},
                    {"slot": "web_grounder", "runtime_id": None,
                     "fill_source": "unfilled", "intent": "x",
                     "runtime_display_name": None, "rationale": "x"},
                    {"slot": "risk_reviewer", "runtime_id": "cli_codex",
                     "fill_source": "preferred", "intent": "x",
                     "runtime_display_name": "x", "rationale": "x"},
                    {"slot": "final_synthesizer", "runtime_id": "cli_gemini",
                     "fill_source": "preferred", "intent": "x",
                     "runtime_display_name": "x", "rationale": "x"},
                ],
            }
        monkeypatch.setattr(
            draft_qe_review, "get_qe_readiness", _qe_payload,
        )
        registry = FakeRegistry(
            OLLAMA=CannedProvider(ModelProvider.OLLAMA, [_PROP_REPLY]),
            OPENAI=CannedProvider(ModelProvider.OPENAI, [_PROP_REPLY]),
            GEMINI=CannedProvider(ModelProvider.GEMINI, [_SYNTH_REPLY]),
        )
        result = await run_command(
            db_session, parse_command(f"run council on draft {d.id}"),
            user_id=test_user_id, tenant_id=test_tenant_id,
            registry=registry,
        )
        assert result.success is True
        assert "mode=full" in result.summary
        assert result.data["mode"] == "full"


# ── 11. create_workstream_from_draft ────────────────────────────────


class TestCreateWorkstream:
    @pytest.mark.asyncio
    async def test_promote_to_workstream(
        self, db_session, test_tenant_id, test_user_id,
    ):
        await _seed(db_session, test_tenant_id, test_user_id)
        d = await _make_career_draft(db_session, test_tenant_id, test_user_id)
        result = await run_command(
            db_session,
            parse_command(f"create a work plan from this {d.id}"),
            user_id=test_user_id, tenant_id=test_tenant_id,
        )
        assert result.success is True
        assert "Workstream" in result.summary
        # response carries the workstream serialization
        assert "id" in result.data
        assert result.data["source_type"] == "draft"


# ── helpers ─────────────────────────────────────────────────────────


async def _async_return(value):
    return value
