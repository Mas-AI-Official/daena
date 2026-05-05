"""PR-2 (Sprint-11): structured_payload on ResearchDraft.

Tests:
    1. build_structured_payload for kind=career emits the opportunity shape
       with all documented keys + _llm_pending flag.
    2. build_structured_payload for kind=content emits the brief shape
       with all documented keys.
    3. Bullet/URL extraction helpers behave deterministically.
    4. The host-to-company heuristic strips common ATS subdomains.
    5. Rule 2 assertion: no parallel OpportunityDraft / ContentBrief
       module exists in the codebase.
    6. ResearchDraft.structured_payload column round-trips a dict.
    7. Schema version constant is exposed for consumers.
"""

from __future__ import annotations

import importlib
import uuid

import pytest

from app.models.identity import Tenant, User
from app.models.research import ResearchDraft
from app.services.research_flow import (
    STRUCTURED_PAYLOAD_VERSION,
    _bullets,
    _company_candidate_from_host,
    _urls,
    build_structured_payload,
)


CAREER_REQUIRED_KEYS = {
    "_schema_version",
    "_kind",
    "_llm_pending",
    "company",
    "role",
    "team",
    "location",
    "compensation",
    "requirements",
    "responsibilities",
    "fit_score",
    "fit_rationale",
    "missing_skills",
    "suggested_answers",
    "outreach_draft_local",
    "next_tasks",
    "sources",
    "goal_echo",
}

CONTENT_REQUIRED_KEYS = {
    "_schema_version",
    "_kind",
    "_llm_pending",
    "audience",
    "key_points",
    "angle",
    "outline",
    "captions",
    "hooks",
    "sources",
    "risks_to_verify",
    "claims_to_verify",
    "goal_echo",
}


SAMPLE_CAREER_EXTRACT = """
About the role:
- 5+ years building distributed systems
- Expert in Python and Go
- Comfortable with on-call rotation

Apply at https://example.com/apply
References: https://blog.example.com/team
"""

SAMPLE_CONTENT_EXTRACT = """
The author argues:
* The market is shifting toward governed AI
* Open-source moats are weaker than people think
* Enterprise buyers want auditable systems

Sources:
https://arxiv.org/abs/2604.02460
https://anthropic.com/blog
"""


# ── Schema shape ──────────────────────────────────────────────────────


class TestCareerStructuredPayload:
    def test_emits_opportunity_kind(self):
        payload = build_structured_payload(
            kind="career",
            goal="Extract role + requirements",
            raw_extract=SAMPLE_CAREER_EXTRACT,
            source_url="https://jobs.acme.com/ai-engineer",
            source_host="https://jobs.acme.com",
        )
        assert payload["_kind"] == "opportunity"

    def test_all_required_keys_present(self):
        payload = build_structured_payload(
            kind="career",
            goal="x",
            raw_extract=SAMPLE_CAREER_EXTRACT,
            source_url="https://example.com",
            source_host="https://example.com",
        )
        missing = CAREER_REQUIRED_KEYS - payload.keys()
        assert not missing, f"missing keys: {missing}"

    def test_llm_pending_flag_default_true(self):
        """First-pass deterministic structuring; LLM enrichment lands later."""
        payload = build_structured_payload(
            kind="career", goal="x", raw_extract="",
            source_url="https://example.com", source_host="https://example.com",
        )
        assert payload["_llm_pending"] is True

    def test_requirements_pulled_from_bullets(self):
        payload = build_structured_payload(
            kind="career", goal="x",
            raw_extract=SAMPLE_CAREER_EXTRACT,
            source_url="https://example.com",
            source_host="https://example.com",
        )
        reqs = payload["requirements"]
        assert any("Python" in r for r in reqs)
        assert any("distributed systems" in r for r in reqs)

    def test_company_from_host_strips_ats_subdomain(self):
        payload = build_structured_payload(
            kind="career", goal="x", raw_extract="",
            source_url="https://jobs.acme.com/role/123",
            source_host="https://jobs.acme.com",
        )
        # jobs.acme.com -> acme (jobs is an ATS prefix)
        assert payload["company"] == "acme"

    def test_sources_includes_origin_url(self):
        payload = build_structured_payload(
            kind="career", goal="x",
            raw_extract=SAMPLE_CAREER_EXTRACT,
            source_url="https://jobs.acme.com/role/42",
            source_host="https://jobs.acme.com",
        )
        assert "https://jobs.acme.com/role/42" in payload["sources"]

    def test_schema_version_present(self):
        payload = build_structured_payload(
            kind="career", goal="x", raw_extract="",
            source_url="https://x.com", source_host="https://x.com",
        )
        assert payload["_schema_version"] == STRUCTURED_PAYLOAD_VERSION


class TestContentStructuredPayload:
    def test_emits_brief_kind(self):
        payload = build_structured_payload(
            kind="content", goal="Summarize",
            raw_extract=SAMPLE_CONTENT_EXTRACT,
            source_url="https://blog.example.com/post",
            source_host="https://blog.example.com",
        )
        assert payload["_kind"] == "brief"

    def test_all_required_keys_present(self):
        payload = build_structured_payload(
            kind="content", goal="x",
            raw_extract=SAMPLE_CONTENT_EXTRACT,
            source_url="https://x.com", source_host="https://x.com",
        )
        missing = CONTENT_REQUIRED_KEYS - payload.keys()
        assert not missing, f"missing keys: {missing}"

    def test_outline_uses_bullets(self):
        payload = build_structured_payload(
            kind="content", goal="x",
            raw_extract=SAMPLE_CONTENT_EXTRACT,
            source_url="https://x.com", source_host="https://x.com",
        )
        outline = payload["outline"]
        assert any("governed" in line for line in outline)

    def test_sources_extracted_from_text(self):
        payload = build_structured_payload(
            kind="content", goal="x",
            raw_extract=SAMPLE_CONTENT_EXTRACT,
            source_url="https://blog.example.com/post",
            source_host="https://blog.example.com",
        )
        assert "https://arxiv.org/abs/2604.02460" in payload["sources"]


# ── Helpers ──────────────────────────────────────────────────────────


class TestExtractionHelpers:
    def test_bullets_handles_dash_star_dot(self):
        text = "- one\n* two\n3. three\n• four"
        out = _bullets(text)
        assert out == ["one", "two", "three", "four"]

    def test_bullets_dedups(self):
        text = "- same\n- same\n- different"
        assert _bullets(text) == ["same", "different"]

    def test_bullets_caps(self):
        text = "\n".join(f"- item-{i}" for i in range(50))
        out = _bullets(text, limit=5)
        assert len(out) == 5

    def test_urls_extracts_http_and_https(self):
        text = "see http://x.com and https://y.com/path"
        urls = _urls(text)
        assert "http://x.com" in urls
        assert "https://y.com/path" in urls

    def test_urls_strips_trailing_punctuation(self):
        text = "ref: https://x.com)"
        assert "https://x.com" in _urls(text)

    def test_company_candidate_strips_jobs_prefix(self):
        assert _company_candidate_from_host("https://jobs.acme.com") == "acme"
        assert _company_candidate_from_host("https://careers.bigco.io") == "bigco"
        assert _company_candidate_from_host("https://boards.greenhouse.io") == "greenhouse"


# ── Rule 2 assertion: no parallel models ─────────────────────────────


class TestNoDuplicateModels:
    """CLAUDE.md Rule 2: one canonical file per concern.

    PR-2 must not introduce parallel OpportunityDraft / ContentBrief
    tables. The structured shape lives on ResearchDraft.structured_payload.
    """

    def test_no_opportunity_draft_module(self):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("app.models.opportunity_draft")

    def test_no_content_brief_module(self):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("app.models.content_brief")

    def test_research_draft_has_structured_payload_column(self):
        cols = {c.name for c in ResearchDraft.__table__.columns}
        assert "structured_payload" in cols


# ── Round-trip persistence ───────────────────────────────────────────


class TestPersistence:
    @pytest.mark.asyncio
    async def test_structured_payload_round_trips_through_db(
        self, db_session, test_tenant_id, test_user_id,
    ):
        # Seed minimal tenant + user (idempotent)
        from sqlalchemy import select
        existing_tenant = (await db_session.execute(
            select(Tenant).where(Tenant.id == test_tenant_id)
        )).scalar_one_or_none()
        if existing_tenant is None:
            db_session.add(Tenant(id=test_tenant_id, name="T", slug="t"))
        existing_user = (await db_session.execute(
            select(User).where(User.id == test_user_id)
        )).scalar_one_or_none()
        if existing_user is None:
            db_session.add(User(
                id=test_user_id, tenant_id=test_tenant_id,
                email="x@example.com", password_hash="x",
                role="FOUNDER", is_active=True,
            ))
        await db_session.flush()

        payload = build_structured_payload(
            kind="career", goal="x",
            raw_extract=SAMPLE_CAREER_EXTRACT,
            source_url="https://jobs.acme.com/role/1",
            source_host="https://jobs.acme.com",
        )
        draft_id = uuid.uuid4()
        draft = ResearchDraft(
            id=draft_id,
            tenant_id=test_tenant_id,
            user_id=test_user_id,
            kind="career",
            source_url="https://jobs.acme.com/role/1",
            source_host="https://jobs.acme.com",
            goal="x",
            summary="s",
            raw_extract=SAMPLE_CAREER_EXTRACT,
            status="DRAFT",
            structured_payload=payload,
        )
        db_session.add(draft)
        await db_session.flush()
        db_session.expire_all()

        loaded = (await db_session.execute(
            select(ResearchDraft).where(ResearchDraft.id == draft_id)
        )).scalar_one()
        assert loaded.structured_payload is not None
        assert loaded.structured_payload["_kind"] == "opportunity"
        assert loaded.structured_payload["company"] == "acme"
        assert loaded.structured_payload["_llm_pending"] is True
