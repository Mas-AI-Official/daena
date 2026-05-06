"""Sprint-13 PR-2 -- business opportunity discovery contract.

Pins:
  1. ALLOWED_KINDS includes 'business_opportunity'.
  2. ALLOWED_OPPORTUNITY_TYPES is a closed 10-element set.
  3. build_structured_payload(kind='business_opportunity', ...) produces
     the locked shape with all required keys.
  4. create_research_draft refuses kind='business_opportunity' without
     opportunity_type.
  5. create_research_draft refuses opportunity_type for non-opportunity
     kinds.
  6. create_research_draft refuses unknown opportunity_type values.
  7. The endpoint /research/opportunity is mounted under /research.
  8. The opportunity payload NEVER references a send/submit/apply field.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


_REQUIRED_KEYS = {
    "_schema_version",
    "_kind",
    "_llm_pending",
    "title",
    "opportunity_type",
    "deadline",
    "fit_score",
    "revenue_potential",
    "effort_estimate",
    "risk_level",
    "next_action",
    "suggested_department",
    "evidence",
    "source_notes",
    "confidence",
    "sources",
    "goal_echo",
}

_FORBIDDEN_KEY_SUBSTRINGS = (
    "send",
    "submit",
    "apply",
    "post_to_",
    "publish",
    "pay",
)


_REQUIRED_TYPES = {
    "grant",
    "accelerator",
    "hackathon",
    "freelance",
    "customer",
    "partnership",
    "security_bounty",
    "rfp",
    "content",
    "startup_program",
}


class TestKindAdded:
    async def test_business_opportunity_in_allowed_kinds(self):
        from app.services.research_flow import ALLOWED_KINDS

        assert "business_opportunity" in ALLOWED_KINDS

    async def test_opportunity_types_closed_set(self):
        from app.services.research_flow import ALLOWED_OPPORTUNITY_TYPES

        assert set(ALLOWED_OPPORTUNITY_TYPES) == _REQUIRED_TYPES


class TestStructuredPayload:
    async def test_shape_locked(self):
        from app.services.research_flow import build_structured_payload

        payload = build_structured_payload(
            kind="business_opportunity",
            goal="evaluate eligibility",
            raw_extract="* 50k grant for ai safety\n* deadline mar 2027",
            source_url="https://example.org/grant",
            source_host="https://example.org",
        )
        actual_keys = set(payload.keys())
        missing = _REQUIRED_KEYS - actual_keys
        assert not missing, f"missing keys: {sorted(missing)}"

        # Locked metadata
        assert payload["_kind"] == "business_opportunity"
        assert payload["_llm_pending"] is True
        assert payload["evidence"] == ["https://example.org/grant"]
        assert "https://example.org/grant" in payload["sources"]
        assert payload["goal_echo"] == "evaluate eligibility"

    async def test_no_send_or_submit_field(self):
        from app.services.research_flow import build_structured_payload

        payload = build_structured_payload(
            kind="business_opportunity",
            goal="x",
            raw_extract="",
            source_url="https://example.org/x",
            source_host="https://example.org",
        )
        for key in payload.keys():
            lowered = key.lower()
            for forbidden in _FORBIDDEN_KEY_SUBSTRINGS:
                assert forbidden not in lowered, (
                    f"opportunity payload exposes forbidden field: {key}"
                )


class TestCreateValidation:
    async def test_business_opportunity_requires_type(self, monkeypatch):
        from app.services import research_flow as rf

        async def _fake_extract(url, goal, max_chars):  # pragma: no cover -- not called
            class R:
                success = True
                result = ""
                error = None
            return R()

        monkeypatch.setattr(rf, "extract_from_url", _fake_extract)

        import uuid
        with pytest.raises(rf.ResearchFlowError) as ei:
            await rf.create_research_draft(
                db=None,
                kind="business_opportunity",
                url="https://example.org/x",
                goal="test",
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
            )
        assert "opportunity_type_required" in str(ei.value)

    async def test_career_refuses_opportunity_type(self, monkeypatch):
        from app.services import research_flow as rf

        async def _fake_extract(url, goal, max_chars):  # pragma: no cover
            class R:
                success = True
                result = ""
                error = None
            return R()

        monkeypatch.setattr(rf, "extract_from_url", _fake_extract)

        import uuid
        with pytest.raises(rf.ResearchFlowError) as ei:
            await rf.create_research_draft(
                db=None,
                kind="career",
                url="https://example.org/x",
                goal="test",
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                opportunity_type="grant",
            )
        assert "only_with_business_opportunity" in str(ei.value)

    async def test_unknown_opportunity_type_refused(self, monkeypatch):
        from app.services import research_flow as rf

        async def _fake_extract(url, goal, max_chars):  # pragma: no cover
            class R:
                success = True
                result = ""
                error = None
            return R()

        monkeypatch.setattr(rf, "extract_from_url", _fake_extract)

        import uuid
        with pytest.raises(rf.ResearchFlowError) as ei:
            await rf.create_research_draft(
                db=None,
                kind="business_opportunity",
                url="https://example.org/x",
                goal="test",
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                opportunity_type="not_a_type",  # type: ignore[arg-type]
            )
        assert "opportunity_type_invalid" in str(ei.value)


class TestEndpointMounted:
    async def test_opportunity_route_under_v1(self):
        from app.api.v1 import router as api_v1_router

        paths = [getattr(r, "path", "") for r in api_v1_router.routes]
        assert "/research/opportunity" in paths
