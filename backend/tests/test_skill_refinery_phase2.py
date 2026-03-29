"""Phase 2 tests: skill retrieval, orchestrator integration, refinement.

Tests the retrieval_service, format_evidence_block, and the 3-pass
refinement pipeline parsing logic.
"""

from __future__ import annotations

import json
import uuid

import pytest

from app.models.identity import Tenant
from app.models.skill import RefinedSkill
from app.services.skill_refinery.refinement_service import (
    _parse_json,
    _skill_to_json_str,
)
from app.services.skill_refinery.retrieval_service import (
    _score_skill,
    _tokenize,
    format_evidence_block,
    search_skills,
)
from app.services.skill_refinery.skill_store import SkillStore

# ── Retrieval Unit Tests ──


class TestRetrievalTokenize:
    """Unit tests for retrieval tokenizer."""

    def test_basic(self) -> None:
        tokens = _tokenize("How to design a landing page")
        assert "design" in tokens
        assert "landing" in tokens
        assert "page" in tokens
        assert "how" not in tokens  # stopword
        assert "to" not in tokens

    def test_empty(self) -> None:
        assert _tokenize("") == set()


class TestRetrievalScoring:
    """Unit tests for skill relevance scoring."""

    def _make_skill(
        self,
        title: str = "test",
        domain: str = "testing",
        steps: list[str] | None = None,
        patterns: list[str] | None = None,
        confidence: float = 0.5,
    ) -> RefinedSkill:
        skill = RefinedSkill(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            skill_id="test_skill",
            title=title,
            domain=domain,
            subdomains=[],
            steps=steps or [],
            patterns=patterns or [],
            anti_patterns=[],
            improvements_by_daena=[],
            failure_modes=[],
            confidence=confidence,
            maturity=2,
            source_metadata={},
            usage_count=0,
            embedding_text=None,
        )
        return skill

    def test_high_overlap_scores_high(self) -> None:
        skill = self._make_skill(
            title="Landing page design",
            domain="web_design",
            steps=["Write headline", "Add CTA"],
            patterns=["hero section layout"],
        )
        tokens = _tokenize("design a landing page hero section")
        score = _score_skill(skill, tokens)
        assert score > 0.3

    def test_no_overlap_scores_low(self) -> None:
        skill = self._make_skill(
            title="Database optimization",
            domain="engineering",
            steps=["Index tables"],
        )
        tokens = _tokenize("marketing campaign strategy")
        score = _score_skill(skill, tokens)
        assert score < 0.2

    def test_empty_query_returns_zero(self) -> None:
        skill = self._make_skill(title="Anything")
        score = _score_skill(skill, set())
        assert score == 0.0


class TestFormatEvidenceBlock:
    """Unit tests for evidence block formatting."""

    def test_formats_patterns_and_steps(self) -> None:
        skills = [
            {
                "patterns": ["single CTA above fold", "mobile-first"],
                "steps": ["Write headline", "Add proof"],
                "confidence": 0.84,
            },
        ]
        block = format_evidence_block(skills)
        assert "EVIDENCE-BACKED PATTERNS" in block
        assert "single CTA above fold" in block
        assert "confidence 0.84" in block
        assert "Apply these patterns" in block

    def test_empty_skills_returns_empty(self) -> None:
        assert format_evidence_block([]) == ""

    def test_multiple_sources_show_count(self) -> None:
        skills = [
            {"patterns": ["pattern A"], "steps": [], "confidence": 0.8},
            {"patterns": ["pattern B"], "steps": [], "confidence": 0.6},
        ]
        block = format_evidence_block(skills)
        assert "2 analyzed sources" in block


# ── Refinement Parsing Unit Tests ──


class TestRefinementParsing:
    """Unit tests for refinement service parsing helpers."""

    def test_parse_json_valid(self) -> None:
        result = _parse_json('{"verdict": "APPROVE", "confidence": 0.9}')
        assert result["verdict"] == "APPROVE"

    def test_parse_json_markdown_fenced(self) -> None:
        result = _parse_json('```json\n{"key": "val"}\n```')
        assert result["key"] == "val"

    def test_parse_json_invalid_returns_empty(self) -> None:
        assert _parse_json("not json") == {}

    def test_skill_to_json_str(self) -> None:
        skill = {
            "title": "Test",
            "domain": "testing",
            "steps": ["step 1"],
            "patterns": [],
            "extra_field": "ignored",
        }
        result = _skill_to_json_str(skill)
        parsed = json.loads(result)
        assert parsed["title"] == "Test"
        assert "extra_field" not in parsed
        # Empty patterns should be excluded
        assert "patterns" not in parsed


# ── Retrieval Integration Tests (with DB) ──


@pytest.mark.asyncio
async def test_search_skills_returns_relevant(
    db_session, test_tenant_id,
) -> None:
    """search_skills returns T2+ skills matching the query."""
    db_session.add(Tenant(
        id=test_tenant_id, name="Retrieval Tenant",
        slug="retrieval-tenant", plan="FREE", settings={},
    ))
    await db_session.flush()

    store = SkillStore(db_session)

    # Create a T0 skill (should NOT be returned -- below T2)
    await store.create_skill(
        tenant_id=test_tenant_id,
        skill_id="skill_low_001",
        title="Low maturity landing page",
        domain="web_design",
        maturity=0,
        confidence=0.9,
    )

    # Create a T1 skill and promote to T2
    await store.create_skill(
        tenant_id=test_tenant_id,
        skill_id="skill_web_t2",
        title="SaaS hero section design",
        domain="web_design",
        steps=["Write headline", "Add CTA above fold"],
        patterns=["single CTA", "mobile-first hierarchy"],
        maturity=0,
        confidence=0.84,
    )
    await store.promote_skill(
        skill_id="skill_web_t2", tenant_id=test_tenant_id,
    )
    await store.promote_skill(
        skill_id="skill_web_t2", tenant_id=test_tenant_id,
    )

    # Create an unrelated T2 skill
    await store.create_skill(
        tenant_id=test_tenant_id,
        skill_id="skill_db_t2",
        title="Database indexing optimization",
        domain="engineering",
        steps=["Analyze queries", "Create indexes"],
        maturity=0,
        confidence=0.7,
    )
    await store.promote_skill(
        skill_id="skill_db_t2", tenant_id=test_tenant_id,
    )
    await store.promote_skill(
        skill_id="skill_db_t2", tenant_id=test_tenant_id,
    )

    # Search for landing page skills
    results = await search_skills(
        db_session,
        tenant_id=test_tenant_id,
        query="design a SaaS landing page hero section",
        top_k=5,
    )

    # Should find the web design skill, not the DB skill
    assert len(results) >= 1
    domains = [r["domain"] for r in results]
    assert "web_design" in domains

    # The low-maturity skill should NOT appear
    skill_ids = [r["skill_id"] for r in results]
    assert "skill_low_001" not in skill_ids


@pytest.mark.asyncio
async def test_search_skills_empty_when_no_match(
    db_session, test_tenant_id,
) -> None:
    """search_skills returns empty list when no skills match."""
    db_session.add(Tenant(
        id=test_tenant_id, name="Empty Tenant",
        slug="empty-tenant", plan="FREE", settings={},
    ))
    await db_session.flush()

    results = await search_skills(
        db_session,
        tenant_id=test_tenant_id,
        query="quantum physics simulation",
        top_k=5,
    )
    assert results == []


@pytest.mark.asyncio
async def test_evidence_block_integration(
    db_session, test_tenant_id,
) -> None:
    """Full flow: create skill -> promote to T2 -> search -> format."""
    db_session.add(Tenant(
        id=test_tenant_id, name="Evidence Tenant",
        slug="evidence-tenant", plan="FREE", settings={},
    ))
    await db_session.flush()

    store = SkillStore(db_session)
    await store.create_skill(
        tenant_id=test_tenant_id,
        skill_id="skill_mkt_001",
        title="Email marketing campaign",
        domain="marketing",
        patterns=["personalized subject lines boost open rates 26%"],
        steps=["Segment audience", "A/B test subject lines"],
        maturity=0,
        confidence=0.78,
    )
    # Promote to T2
    await store.promote_skill(
        skill_id="skill_mkt_001", tenant_id=test_tenant_id,
    )
    await store.promote_skill(
        skill_id="skill_mkt_001", tenant_id=test_tenant_id,
    )

    results = await search_skills(
        db_session,
        tenant_id=test_tenant_id,
        query="email marketing campaign strategy",
        top_k=3,
    )

    block = format_evidence_block(results)
    assert "EVIDENCE-BACKED PATTERNS" in block
    assert "personalized subject lines" in block


# ── API Endpoint Tests ──


async def _register_and_login(client) -> dict:
    unique = uuid.uuid4().hex[:8]
    email = f"p2-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email, "password": "SecurePass123!",
            "display_name": "P2 Tester",
            "tenant_name": f"P2Org-{unique}",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = resp.json()["data"]
    return {"headers": {"Authorization": f"Bearer {data['access_token']}"}}


@pytest.mark.asyncio
async def test_api_refine_nonexistent_404(client) -> None:
    """POST /skills/refinery/{id}/refine returns 404 for missing skill."""
    auth = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/skills/refinery/nonexistent_skill/refine",
        headers=auth["headers"],
    )
    assert resp.status_code == 404
