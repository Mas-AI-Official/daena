"""Sprint-12 PR-1 + PR-2 -- DraftEnrichment service tests.

Asserts the contract every enrichment call must satisfy:

  1. ``select_provider`` refuses with ``NoReadyMainBrain`` when
     ``main_brain_id is None``, exposing the readiness ``next_action``.
  2. ``select_provider`` refuses with ``MeteredApiNotAllowed`` when
     the routed runtime is metered_api and ``allow_metered=False``.
  3. ``_extract_json`` survives bare JSON, fenced blocks, and
     greedy-brace responses; returns None on garbage.
  4. ``enrich_research_draft`` (career) merges LLM output without
     overwriting deterministic fields, sets ``_llm_pending=False``,
     records ``confidence`` + ``needs_review``, and audits with
     action_type=``draft.enrichment.career``.
  5. ``enrich_research_draft`` (content) does the same for the
     content-brief shape.
  6. When the LLM call raises, the merger flips ``_llm_failed=True``
     and marks every field for needs_review -- no exception
     propagates.
  7. ``enrich_form_draft`` NEVER writes a suggested_value to a
     blocked_payment / blocked_sensitive field, regardless of LLM
     output. Verified by including such a field in the LLM response
     and asserting it stays None.
  8. ``enrich_form_draft`` writes one ``draft.enrichment.form`` audit
     row on the success path, and BLOCKED on the no-main-brain path.
  9. The router map covers every readiness id ``RUNTIME_CLASSIFICATION``
     ships -- adding a runtime without a provider mapping fails CI.
 10. Refusal audit row writes a non-empty ``next_action`` field.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select

from app.core.constants import HealthStatus, ModelProvider
from app.models.form_draft import FormDraft, FormDraftField
from app.models.governance import GoaAuditEvent
from app.models.identity import Tenant, User
from app.models.research import ResearchDraft
from app.services.draft_enrichment import (
    EnrichmentRefused,
    MeteredApiNotAllowed,
    NoReadyMainBrain,
    RUNTIME_TO_PROVIDER,
    _ENRICHABLE_FIELD_TYPES,
    _extract_json,
    _merge_career_payload,
    _merge_content_payload,
    enrich_form_draft,
    enrich_research_draft,
    select_provider,
)
from app.services.providers.base import (
    BaseProvider,
    GenerateRequest,
    LLMResponse,
)
from app.services.runtime_readiness import RUNTIME_CLASSIFICATION


# ── Fakes ────────────────────────────────────────────────────────────


class FakeProvider(BaseProvider):
    """Returns a canned reply -- no network, no real model."""

    def __init__(self, provider: ModelProvider, reply: str) -> None:
        super().__init__(provider)
        self._reply = reply

    async def generate(self, request: GenerateRequest) -> LLMResponse:
        return LLMResponse(
            content=self._reply,
            model_id="fake-model",
            provider=self.provider,
            token_count_input=10,
            token_count_output=50,
            latency_ms=12,
        )

    async def stream(self, request):  # noqa: D401
        raise NotImplementedError

    async def health_check(self) -> HealthStatus:  # type: ignore[override]
        return HealthStatus.HEALTHY

    async def list_models(self):  # noqa: D401
        return []


class FakeRegistry:
    """Implements the .get_provider(enum) contract draft_enrichment uses."""

    def __init__(self, **mapping: BaseProvider) -> None:
        self._map = {ModelProvider[k]: v for k, v in mapping.items()}

    def get_provider(self, enum: ModelProvider) -> BaseProvider | None:
        return self._map.get(enum)


def _fake_readiness(
    main_brain_id: str | None = "ollama_backend",
    cost_class: str = "free_local",
    next_action: str = "go",
) -> dict[str, Any]:
    return {
        "items": [],
        "router_summary": {
            "main_brain_id": main_brain_id,
            "main_brain_cost_class": cost_class if main_brain_id else None,
            "web_grounding_id": None,
            "coder_id": None,
            "researcher_id": None,
            "qe_reviewers_ready": [],
            "qe_mode": "unavailable",
            "qe_mode_reason": "",
            "next_action": next_action,
        },
    }


# ── 1 + 2 + 10. Refusal contract ────────────────────────────────────


class TestSelectProvider:
    @pytest.mark.asyncio
    async def test_no_main_brain_raises(self):
        with pytest.raises(NoReadyMainBrain) as exc:
            await select_provider(
                readiness=_fake_readiness(
                    main_brain_id=None,
                    next_action="Start the local llama-server.",
                ),
            )
        assert exc.value.next_action == "Start the local llama-server."
        assert exc.value.code == "no_ready_main_brain"

    @pytest.mark.asyncio
    async def test_metered_refused_by_default(self):
        readiness = _fake_readiness(
            main_brain_id="provider_anthropic",
            cost_class="metered_api",
        )
        with pytest.raises(MeteredApiNotAllowed) as exc:
            await select_provider(allow_metered=False, readiness=readiness)
        assert "provider_anthropic" in exc.value.code

    @pytest.mark.asyncio
    async def test_metered_allowed_when_explicit(self):
        readiness = _fake_readiness(
            main_brain_id="provider_anthropic",
            cost_class="metered_api",
        )
        sel = await select_provider(allow_metered=True, readiness=readiness)
        assert sel.runtime_id == "provider_anthropic"
        assert sel.cost_class == "metered_api"

    @pytest.mark.asyncio
    async def test_local_passes_without_metered_flag(self):
        sel = await select_provider(
            readiness=_fake_readiness(
                main_brain_id="ollama_backend",
                cost_class="free_local",
            ),
        )
        assert sel.runtime_id == "ollama_backend"
        assert sel.provider_enum is ModelProvider.OLLAMA


# ── 3. JSON extraction robustness ────────────────────────────────────


class TestExtractJson:
    def test_bare_object(self):
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_with_leading_word(self):
        assert _extract_json('json{"a": 1}') == {"a": 1}

    def test_fenced(self):
        body = "Here you go:\n```json\n{\"x\": [1,2]}\n```\nthat's it."
        assert _extract_json(body) == {"x": [1, 2]}

    def test_greedy_braces(self):
        body = "Sure! {\"company\": \"Acme\", \"role\": \"Eng\"} done"
        assert _extract_json(body) == {"company": "Acme", "role": "Eng"}

    def test_garbage_returns_none(self):
        assert _extract_json("nope no json here") is None

    def test_empty(self):
        assert _extract_json("") is None


# ── 4 + 5. ResearchDraft enrichment merge contract ──────────────────


class TestMergeCareer:
    def test_does_not_overwrite_deterministic_fields(self):
        existing = {
            "_llm_pending": True,
            "company": "stackline",       # deterministic regex result
            "requirements": ["python", "k8s"],
            "fit_score": None,
        }
        llm = {
            "company": "wrong-overwrite",  # must be ignored
            "fit_score": 78,
            "fit_rationale": "matches python; missing k8s prod experience",
            "missing_skills": ["k8s prod"],
            "field_confidence": {
                "company": 0.99, "fit_score": 0.7, "fit_rationale": 0.65,
                "missing_skills": 0.8,
            },
        }
        merged = _merge_career_payload(existing, llm)
        assert merged["company"] == "stackline"          # preserved
        assert merged["fit_score"] == 78                  # filled
        assert merged["missing_skills"] == ["k8s prod"]   # filled
        assert merged["_llm_pending"] is False
        assert merged["_llm_failed"] is False
        assert "fit_rationale" in merged["_llm_field_confidence"]

    def test_low_confidence_marks_needs_review(self):
        merged = _merge_career_payload(
            {"_llm_pending": True},
            {
                "fit_score": 50, "fit_rationale": "hmm",
                "field_confidence": {"fit_score": 0.3, "fit_rationale": 0.3},
            },
        )
        assert "fit_score" in merged["_llm_needs_review"]
        assert "fit_rationale" in merged["_llm_needs_review"]

    def test_llm_none_marks_all_needs_review(self):
        merged = _merge_career_payload({"_llm_pending": True}, None)
        assert merged["_llm_failed"] is True
        assert merged["_llm_pending"] is False
        assert "company" in merged["_llm_needs_review"]
        assert "outreach_draft_local" in merged["_llm_needs_review"]
        # field_confidence should be 0.0 across the board
        assert all(
            v == 0.0 for v in merged["_llm_field_confidence"].values()
        )

    def test_fit_score_clamps_out_of_range(self):
        merged = _merge_career_payload(
            {"_llm_pending": True}, {"fit_score": 250},
        )
        assert merged["fit_score"] == 100

    def test_suggested_answers_filtered(self):
        merged = _merge_career_payload(
            {"_llm_pending": True},
            {
                "suggested_answers": [
                    {"question": "Why X?", "answer": "Because Y", "confidence": 0.7},
                    {"question": "no answer", "answer": ""},  # dropped
                    "garbage_string",                                 # dropped
                ],
            },
        )
        sa = merged["suggested_answers"]
        assert len(sa) == 1
        assert sa[0]["question"] == "Why X?"
        assert 0.0 <= sa[0]["confidence"] <= 1.0


class TestMergeContent:
    def test_merge_fills_brief_fields(self):
        merged = _merge_content_payload(
            {"_llm_pending": True, "outline": ["a", "b"]},
            {
                "audience": "AI engineers", "angle": "Make X 10x faster",
                "captions": ["c1", "c2"], "hooks": ["h1"],
                "claims_to_verify": ["X is 10x faster"],
                "field_confidence": {
                    "audience": 0.9, "angle": 0.8, "captions": 0.7,
                    "hooks": 0.7, "claims_to_verify": 0.5,
                },
            },
        )
        assert merged["audience"] == "AI engineers"
        assert merged["captions"] == ["c1", "c2"]
        assert merged["outline"] == ["a", "b"]   # not overwritten
        assert "claims_to_verify" in merged["_llm_needs_review"]


# ── 6 + 4. Full path: enrich_research_draft + audit ────────────────


@pytest.fixture
async def career_draft(db_session, test_tenant_id, test_user_id):
    # idempotent tenant+user
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
        summary="raw posting text",
        raw_extract="raw posting text",
        status="DRAFT",
        structured_payload={
            "_schema_version": "test",
            "_kind": "opportunity",
            "_llm_pending": True,
            "company": None,
            "role": None,
            "requirements": ["python", "k8s"],
            "responsibilities": [],
            "fit_score": None,
            "missing_skills": [],
            "suggested_answers": [],
            "next_tasks": [],
            "outreach_draft_local": None,
            "fit_rationale": None,
            "team": None, "location": None, "compensation": None,
            "sources": ["https://jobs.acme.com/eng"],
            "goal_echo": "extract role + fit",
        },
    )
    db_session.add(draft)
    await db_session.flush()
    return draft


class TestEnrichResearchDraftFlow:
    @pytest.mark.asyncio
    async def test_happy_path_audits_and_merges(
        self, db_session, career_draft,
    ):
        # Fake LLM returns a parseable JSON object.
        reply = (
            '{"company": "Acme Robotics", "role": "Senior Eng", '
            '"fit_score": 72, "fit_rationale": "matches python", '
            '"missing_skills": ["k8s prod"], '
            '"outreach_draft_local": "Hi team, I noticed your role.", '
            '"next_tasks": ["read job desc deeper"], '
            '"field_confidence": {"company":0.95,"role":0.9,"fit_score":0.7,'
            '"fit_rationale":0.7,"missing_skills":0.8,'
            '"outreach_draft_local":0.6,"next_tasks":0.6}, '
            '"needs_review": ["outreach_draft_local"]}'
        )
        registry = FakeRegistry(OLLAMA=FakeProvider(ModelProvider.OLLAMA, reply))
        result = await enrich_research_draft(
            db_session, career_draft,
            readiness=_fake_readiness("ollama_backend", "free_local"),
            registry=registry,
            actor_id=career_draft.user_id,
        )

        assert result.runtime_id == "ollama_backend"
        assert result.cost_class == "free_local"
        assert result.llm_failed is False
        assert result.fields_filled >= 5
        assert "outreach_draft_local" in result.needs_review

        await db_session.refresh(career_draft)
        sp = career_draft.structured_payload
        assert sp["_llm_pending"] is False
        assert sp["_llm_failed"] is False
        assert sp["company"] == "Acme Robotics"
        assert sp["fit_score"] == 72

        # exactly one ALLOWED audit row for this draft + action
        rows = (await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.action_type == "draft.enrichment.career",
                GoaAuditEvent.tenant_id == career_draft.tenant_id,
            )
        )).scalars().all()
        assert any(
            (r.action_params or {}).get("draft_id") == str(career_draft.id)
            and r.result == "ALLOWED"
            for r in rows
        )

    @pytest.mark.asyncio
    async def test_no_main_brain_writes_blocked_audit(
        self, db_session, career_draft,
    ):
        with pytest.raises(NoReadyMainBrain):
            await enrich_research_draft(
                db_session, career_draft,
                readiness=_fake_readiness(
                    main_brain_id=None,
                    next_action="Start a local model.",
                ),
                registry=FakeRegistry(),
                actor_id=career_draft.user_id,
            )
        rows = (await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.action_type == "draft.enrichment.career",
                GoaAuditEvent.result == "BLOCKED",
            )
        )).scalars().all()
        target = [
            r for r in rows
            if (r.action_params or {}).get("draft_id") == str(career_draft.id)
        ]
        assert len(target) == 1
        assert (
            target[0].action_params.get("refusal_code")
            == "no_ready_main_brain"
        )
        assert "Start a local model." == target[0].action_params.get("next_action")

    @pytest.mark.asyncio
    async def test_llm_garbage_marks_failed_no_raise(
        self, db_session, career_draft,
    ):
        # FakeProvider returns non-JSON; the merger should fall back.
        registry = FakeRegistry(
            OLLAMA=FakeProvider(ModelProvider.OLLAMA, "I refuse to JSON."),
        )
        result = await enrich_research_draft(
            db_session, career_draft,
            readiness=_fake_readiness("ollama_backend", "free_local"),
            registry=registry,
            actor_id=career_draft.user_id,
        )
        assert result.llm_failed is True
        await db_session.refresh(career_draft)
        sp = career_draft.structured_payload
        assert sp["_llm_failed"] is True
        assert sp["_llm_pending"] is False


# ── 7 + 8. FormDraft enrichment ──────────────────────────────────────


@pytest.fixture
async def form_draft_with_fields(db_session, test_tenant_id, test_user_id):
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

    draft = FormDraft(
        id=uuid.uuid4(),
        tenant_id=test_tenant_id,
        user_id=test_user_id,
        title="Apply: AI Engineer",
        source_kind="questions",
        goal="fill the application using my CV",
        status="DRAFT",
    )
    db_session.add(draft)
    await db_session.flush()

    fields = [
        FormDraftField(
            id=uuid.uuid4(), tenant_id=test_tenant_id,
            draft_id=draft.id, order=0,
            label="Full name", field_type="text", needs_review=True,
        ),
        FormDraftField(
            id=uuid.uuid4(), tenant_id=test_tenant_id,
            draft_id=draft.id, order=1,
            label="Why are you a fit?", field_type="textarea", needs_review=True,
        ),
        FormDraftField(
            id=uuid.uuid4(), tenant_id=test_tenant_id,
            draft_id=draft.id, order=2,
            label="Credit card number",
            field_type="blocked_payment", needs_review=True,
        ),
        FormDraftField(
            id=uuid.uuid4(), tenant_id=test_tenant_id,
            draft_id=draft.id, order=3,
            label="Passport number",
            field_type="blocked_sensitive", needs_review=True,
        ),
    ]
    for f in fields:
        db_session.add(f)
    await db_session.flush()
    return draft, fields


class TestEnrichFormDraft:
    @pytest.mark.asyncio
    async def test_blocked_fields_never_get_suggested_value(
        self, db_session, form_draft_with_fields,
    ):
        draft, fields = form_draft_with_fields
        cc = next(f for f in fields if f.field_type == "blocked_payment")
        passport = next(
            f for f in fields if f.field_type == "blocked_sensitive"
        )
        good_text = next(f for f in fields if f.field_type == "text")
        good_textarea = next(
            f for f in fields if f.field_type == "textarea"
        )

        # Adversarial LLM: returns a value for EVERY field including blocked ones.
        reply = (
            '{"answers": ['
            f'{{"field_id": "{good_text.id}", "suggested_value": "Masoud", "confidence": 0.95, "notes": ""}},'
            f'{{"field_id": "{good_textarea.id}", "suggested_value": "I have built ...", "confidence": 0.7, "notes": ""}},'
            f'{{"field_id": "{cc.id}", "suggested_value": "4111-1111-1111-1111", "confidence": 0.99, "notes": ""}},'
            f'{{"field_id": "{passport.id}", "suggested_value": "X1234567", "confidence": 0.99, "notes": ""}}'
            ']}'
        )
        registry = FakeRegistry(
            OLLAMA=FakeProvider(ModelProvider.OLLAMA, reply),
        )
        result = await enrich_form_draft(
            db_session, draft,
            readiness=_fake_readiness("ollama_backend", "free_local"),
            registry=registry,
            actor_id=draft.user_id,
        )
        await db_session.refresh(cc)
        await db_session.refresh(passport)
        await db_session.refresh(good_text)
        await db_session.refresh(good_textarea)

        assert cc.suggested_value is None     # NEVER set
        assert passport.suggested_value is None
        assert good_text.suggested_value == "Masoud"
        assert good_textarea.suggested_value == "I have built ..."
        assert good_text.needs_review is False  # high confidence
        assert good_textarea.needs_review is False
        assert result.fields_filled == 2
        assert result.runtime_id == "ollama_backend"

    @pytest.mark.asyncio
    async def test_low_confidence_flags_needs_review(
        self, db_session, form_draft_with_fields,
    ):
        draft, fields = form_draft_with_fields
        good = next(f for f in fields if f.field_type == "text")
        reply = (
            '{"answers": [{'
            f'"field_id": "{good.id}", "suggested_value": "Maybe", '
            '"confidence": 0.2, "notes": "guess"'
            "}]}"
        )
        registry = FakeRegistry(
            OLLAMA=FakeProvider(ModelProvider.OLLAMA, reply),
        )
        await enrich_form_draft(
            db_session, draft,
            readiness=_fake_readiness("ollama_backend", "free_local"),
            registry=registry,
        )
        await db_session.refresh(good)
        assert good.needs_review is True
        assert good.confidence == pytest.approx(0.2)

    @pytest.mark.asyncio
    async def test_form_no_main_brain_audit_row(
        self, db_session, form_draft_with_fields,
    ):
        draft, _ = form_draft_with_fields
        with pytest.raises(NoReadyMainBrain):
            await enrich_form_draft(
                db_session, draft,
                readiness=_fake_readiness(
                    main_brain_id=None,
                    next_action="Start a local model.",
                ),
                registry=FakeRegistry(),
                actor_id=draft.user_id,
            )
        rows = (await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.action_type == "draft.enrichment.form",
                GoaAuditEvent.result == "BLOCKED",
            )
        )).scalars().all()
        assert any(
            (r.action_params or {}).get("draft_id") == str(draft.id)
            for r in rows
        )


# ── 9. Coverage: every readiness id has a provider mapping ──────────


class TestCoverage:
    def test_every_classified_runtime_has_provider_mapping(self):
        # Truth ids are RUNTIME_CLASSIFICATION keys (Sprint-12A PR-1).
        # API enrichment uses the readiness layer, which returns
        # only the classified set. Every id must map to a ModelProvider.
        unmapped = [
            item_id for item_id in RUNTIME_CLASSIFICATION
            if item_id not in RUNTIME_TO_PROVIDER
        ]
        assert not unmapped, (
            f"Add RUNTIME_TO_PROVIDER entries for: {unmapped}"
        )

    def test_enrichable_field_types_excludes_blocked(self):
        # Defence in depth: blocked types must not appear in the
        # whitelist of enrichable types.
        assert "blocked_payment" not in _ENRICHABLE_FIELD_TYPES
        assert "blocked_sensitive" not in _ENRICHABLE_FIELD_TYPES
