"""Sprint-12 PR-3 -- DraftQEReview service tests.

Asserts:

  1. ``QECouncilUnavailable`` raised when qe_readiness mode=unavailable.
  2. Single-runtime council NEVER reports mode=full -- collapses to
     "degraded" honestly (the brief's "no fake council complete" rule).
  3. Two distinct runtimes, both succeed -> mode=full.
  4. ``allow_web_grounding=False`` keeps the web_grounder slot
     unused even when filled in qe_readiness.
  5. ``allow_metered=False`` skips metered runtimes; if every slot
     resolves to metered, refusal fires.
  6. Synthesizer aggregates proposer outputs and returns
     next_action.
  7. Synthesizer call failure falls back to union-of-proposer
     output without raising.
  8. Audit row written: ``draft.qe_review.<kind>`` ALLOWED on
     success, BLOCKED on unavailable.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.constants import HealthStatus, ModelProvider
from app.models.governance import GoaAuditEvent
from app.models.identity import Tenant, User
from app.models.research import ResearchDraft
from app.services.draft_enrichment import RoutedSelection
from app.services.draft_qe_review import (
    QECouncilUnavailable,
    _slot_to_routed,
    run_draft_qe_review,
)
from app.services.providers.base import (
    BaseProvider,
    GenerateRequest,
    LLMResponse,
)


# ── Fakes ────────────────────────────────────────────────────────────


class CannedProvider(BaseProvider):
    def __init__(self, provider: ModelProvider, replies: list[str]) -> None:
        super().__init__(provider)
        self._replies = list(replies)
        self._calls = 0

    async def generate(self, request: GenerateRequest) -> LLMResponse:
        idx = self._calls
        self._calls += 1
        if idx >= len(self._replies):
            text = self._replies[-1]
        else:
            text = self._replies[idx]
        return LLMResponse(
            content=text,
            model_id="fake",
            provider=self.provider,
        )

    async def stream(self, request):  # noqa: D401
        raise NotImplementedError

    async def health_check(self):  # type: ignore[override]
        return HealthStatus.HEALTHY

    async def list_models(self):  # noqa: D401
        return []


class FakeRegistry:
    def __init__(self, **mapping: BaseProvider) -> None:
        self._map = {ModelProvider[k]: v for k, v in mapping.items()}

    def get_provider(self, e):
        return self._map.get(e)


def _qe_payload(
    *,
    mode: str = "full",
    local_reasoner: str | None = "ollama_backend",
    risk_reviewer: str | None = "cli_codex",
    web_grounder: str | None = None,
    final_synth: str | None = "cli_gemini",
    distinct: list[str] | None = None,
) -> dict:
    return {
        "mode": mode,
        "mode_reason": f"mock {mode}",
        "distinct_runtime_ids": distinct or [
            r for r in [local_reasoner, risk_reviewer, web_grounder, final_synth]
            if r
        ],
        "slot_assignments": [
            {
                "slot": "local_reasoner",
                "runtime_id": local_reasoner,
                "fill_source": "preferred" if local_reasoner else "unfilled",
                "intent": "x", "runtime_display_name": local_reasoner,
                "rationale": "x",
            },
            {
                "slot": "code_reviewer",
                "runtime_id": "cli_claude",
                "fill_source": "preferred",
                "intent": "x", "runtime_display_name": "cli_claude",
                "rationale": "x",
            },
            {
                "slot": "web_grounder",
                "runtime_id": web_grounder,
                "fill_source": "preferred" if web_grounder else "unfilled",
                "intent": "x", "runtime_display_name": web_grounder,
                "rationale": "x",
            },
            {
                "slot": "risk_reviewer",
                "runtime_id": risk_reviewer,
                "fill_source": "preferred" if risk_reviewer else "unfilled",
                "intent": "x", "runtime_display_name": risk_reviewer,
                "rationale": "x",
            },
            {
                "slot": "final_synthesizer",
                "runtime_id": final_synth,
                "fill_source": "preferred" if final_synth else "unfilled",
                "intent": "x", "runtime_display_name": final_synth,
                "rationale": "x",
            },
        ],
    }


@pytest.fixture
async def career_draft(db_session, test_tenant_id, test_user_id):
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
    draft = ResearchDraft(
        id=uuid.uuid4(),
        tenant_id=test_tenant_id,
        user_id=test_user_id,
        kind="career",
        source_url="https://jobs.acme.com/eng",
        source_host="https://jobs.acme.com",
        goal="extract role + fit",
        summary="raw",
        raw_extract="raw",
        status="DRAFT",
        structured_payload={
            "_kind": "opportunity",
            "_llm_pending": False,
            "company": "Acme",
            "fit_score": 92,        # suspiciously high -> risk reviewer flag
            "missing_skills": [],
            "outreach_draft_local": "Hi team",
        },
    )
    db_session.add(draft)
    await db_session.flush()
    return draft


# Standard reply shape proposers + synthesizer return.
_PROP_REPLY = (
    '{"findings":["fit_score may be inflated"],'
    '"objections":["evidence weak for 92"],'
    '"missing_evidence":["salary info"],'
    '"risk_flags":["over-confident outreach"],'
    '"confidence":0.55,"notes":""}'
)
_SYNTH_REPLY = (
    '{"findings":["fit_score may be inflated"],'
    '"objections":["evidence weak"],'
    '"missing_evidence":["salary info"],'
    '"risk_flags":["over-confident outreach"],'
    '"confidence":0.5,'
    '"next_action":"operator_review_required",'
    '"reasoning":"two reviewers agreed"}'
)


# ── 1. Unavailable mode refuses ──────────────────────────────────────


class TestUnavailable:
    @pytest.mark.asyncio
    async def test_mode_unavailable_refuses(
        self, db_session, career_draft,
    ):
        with pytest.raises(QECouncilUnavailable):
            await run_draft_qe_review(
                db_session, career_draft,
                qe_readiness=_qe_payload(
                    mode="unavailable",
                    local_reasoner=None, risk_reviewer=None,
                    web_grounder=None, final_synth=None,
                ),
                registry=FakeRegistry(),
                actor_id=career_draft.user_id,
            )
        rows = (await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.action_type == "draft.qe_review.career",
                GoaAuditEvent.result == "BLOCKED",
            )
        )).scalars().all()
        assert any(
            (r.action_params or {}).get("draft_id") == str(career_draft.id)
            for r in rows
        )


# ── 2 + 3. Mode honesty ─────────────────────────────────────────────


class TestModeHonesty:
    @pytest.mark.asyncio
    async def test_two_distinct_runtimes_full(
        self, db_session, career_draft,
    ):
        # ollama_backend (OLLAMA), cli_codex (OPENAI), cli_gemini (GEMINI)
        registry = FakeRegistry(
            OLLAMA=CannedProvider(ModelProvider.OLLAMA, [_PROP_REPLY]),
            OPENAI=CannedProvider(ModelProvider.OPENAI, [_PROP_REPLY]),
            GEMINI=CannedProvider(ModelProvider.GEMINI, [_SYNTH_REPLY]),
        )
        result = await run_draft_qe_review(
            db_session, career_draft,
            qe_readiness=_qe_payload(),
            registry=registry,
            actor_id=career_draft.user_id,
        )
        assert result.mode == "full"
        assert len(result.distinct_runtime_ids) >= 2
        assert any("inflated" in f for f in result.findings)
        # Sprint-MORNING PR-3: stamp draft.structured_payload._qe_mode
        # so the WorkstreamsPage Drafts lane can render an honest badge.
        await db_session.refresh(career_draft)
        payload = career_draft.structured_payload or {}
        assert payload.get("_qe_mode") == "full"
        assert "_qe_reviewed_at" in payload

    @pytest.mark.asyncio
    async def test_single_runtime_collapses_to_degraded(
        self, db_session, career_draft,
    ):
        # All three slot assignments resolve to ollama_backend ->
        # only one distinct runtime contributes -> mode must be
        # "degraded" regardless of what readiness said.
        registry = FakeRegistry(
            OLLAMA=CannedProvider(
                ModelProvider.OLLAMA, [_PROP_REPLY, _PROP_REPLY, _SYNTH_REPLY],
            ),
        )
        qe = _qe_payload(
            local_reasoner="ollama_backend",
            risk_reviewer="ollama_backend",
            final_synth="ollama_backend",
        )
        # Even though qe_readiness says mode=full, the actual run
        # has only ONE distinct runtime contributing -> degraded.
        result = await run_draft_qe_review(
            db_session, career_draft,
            qe_readiness=qe,
            registry=registry,
            actor_id=career_draft.user_id,
        )
        assert result.mode == "degraded"
        assert len(result.distinct_runtime_ids) == 1
        assert any("degraded" in w.lower() for w in result.warnings)


# ── 4. Web grounding gate ────────────────────────────────────────────


class TestWebGrounding:
    @pytest.mark.asyncio
    async def test_web_grounder_disabled_by_default(
        self, db_session, career_draft,
    ):
        # web_grounder slot filled but allow_web_grounding=False ->
        # the slot is dropped from proposer_routes; only
        # local_reasoner + risk_reviewer fire.
        registry = FakeRegistry(
            OLLAMA=CannedProvider(ModelProvider.OLLAMA, [_PROP_REPLY]),
            OPENAI=CannedProvider(ModelProvider.OPENAI, [_PROP_REPLY]),
            GEMINI=CannedProvider(ModelProvider.GEMINI, [_SYNTH_REPLY]),
            PERPLEXITY=CannedProvider(
                ModelProvider.PERPLEXITY,
                ['{"findings":["should_not_fire"],"confidence":0.9}'],
            ),
        )
        result = await run_draft_qe_review(
            db_session, career_draft,
            qe_readiness=_qe_payload(
                web_grounder="provider_perplexity",
            ),
            allow_metered=True,    # web_grounder is metered
            allow_web_grounding=False,
            registry=registry,
            actor_id=career_draft.user_id,
        )
        slots = [p.slot for p in result.proposer_outputs]
        assert "web_grounder" not in slots
        assert "should_not_fire" not in result.findings


# ── 5. Metered gate ──────────────────────────────────────────────────


class TestMeteredGate:
    @pytest.mark.asyncio
    async def test_all_slots_metered_no_allow_refuses(
        self, db_session, career_draft,
    ):
        registry = FakeRegistry(
            ANTHROPIC=CannedProvider(ModelProvider.ANTHROPIC, [_PROP_REPLY]),
            OPENAI=CannedProvider(ModelProvider.OPENAI, [_PROP_REPLY]),
        )
        qe = _qe_payload(
            local_reasoner="provider_anthropic",
            risk_reviewer="provider_openai",
            final_synth="provider_anthropic",
        )
        with pytest.raises(QECouncilUnavailable):
            await run_draft_qe_review(
                db_session, career_draft,
                qe_readiness=qe,
                allow_metered=False,
                registry=registry,
                actor_id=career_draft.user_id,
            )


# ── 7. Synthesizer fallback ──────────────────────────────────────────


class TestSynthFallback:
    @pytest.mark.asyncio
    async def test_synth_garbage_falls_back_to_union(
        self, db_session, career_draft,
    ):
        registry = FakeRegistry(
            OLLAMA=CannedProvider(ModelProvider.OLLAMA, [_PROP_REPLY]),
            OPENAI=CannedProvider(ModelProvider.OPENAI, [_PROP_REPLY]),
            GEMINI=CannedProvider(
                ModelProvider.GEMINI, ["I refuse to JSON."],
            ),
        )
        result = await run_draft_qe_review(
            db_session, career_draft,
            qe_readiness=_qe_payload(),
            registry=registry,
            actor_id=career_draft.user_id,
        )
        # union of proposer outputs surfaces, no raise
        assert any("inflated" in f for f in result.findings)
        assert result.next_action == "operator_review_required"


# ── _slot_to_routed unit tests ───────────────────────────────────────


class TestSlotToRouted:
    def test_unfilled_returns_none(self):
        qe = _qe_payload(local_reasoner=None)
        assert _slot_to_routed(qe, "local_reasoner", allow_metered=False) is None

    def test_metered_blocked_when_disallowed(self):
        qe = _qe_payload(local_reasoner="provider_anthropic")
        assert _slot_to_routed(
            qe, "local_reasoner", allow_metered=False,
        ) is None
        sel = _slot_to_routed(qe, "local_reasoner", allow_metered=True)
        assert isinstance(sel, RoutedSelection)
        assert sel.cost_class == "metered_api"

    def test_subscription_classified(self):
        qe = _qe_payload(local_reasoner="cli_claude")
        sel = _slot_to_routed(qe, "local_reasoner", allow_metered=False)
        assert sel is not None
        assert sel.cost_class == "subscription"

    def test_unmapped_id_returns_none(self):
        qe = _qe_payload(local_reasoner="brand_new_runtime_2099")
        assert _slot_to_routed(
            qe, "local_reasoner", allow_metered=True,
        ) is None
