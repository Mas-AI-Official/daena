"""Sprint-13 PR-3 -- workstream generator for business opportunities.

Pins:
  1. Opportunity-type -> department map covers every value in
     research_flow.ALLOWED_OPPORTUNITY_TYPES.
  2. The map points only at department names that exist in the seed
     constants list (no orphan department references).
  3. Adding a new opportunity_type without extending the dept map
     would leave the workstream router on the kind default; the
     contract test catches that.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


_VALID_DEPARTMENTS = {
    "Engineering",
    "Product",
    "Marketing",
    "Sales",
    "Finance",
    "Operations",
    "Research",
    "Legal & Compliance",
    "Skill Governance",
    "Security Operations",
}


class TestOpportunityDepartmentMap:
    async def test_covers_every_opportunity_type(self):
        from app.api.v1.workstreams import _OPPORTUNITY_TYPE_TO_DEPARTMENT_NAME
        from app.services.research_flow import ALLOWED_OPPORTUNITY_TYPES

        missing = set(ALLOWED_OPPORTUNITY_TYPES) - set(_OPPORTUNITY_TYPE_TO_DEPARTMENT_NAME)
        assert not missing, (
            f"opportunity_type values without a department mapping: "
            f"{sorted(missing)}"
        )

    async def test_no_orphan_department_names(self):
        from app.api.v1.workstreams import _OPPORTUNITY_TYPE_TO_DEPARTMENT_NAME

        bad = {
            (k, v)
            for k, v in _OPPORTUNITY_TYPE_TO_DEPARTMENT_NAME.items()
            if v not in _VALID_DEPARTMENTS
        }
        assert not bad, f"opportunity types pointing at unknown depts: {bad}"

    async def test_security_bounty_routes_to_security_ops(self):
        from app.api.v1.workstreams import _OPPORTUNITY_TYPE_TO_DEPARTMENT_NAME

        assert (
            _OPPORTUNITY_TYPE_TO_DEPARTMENT_NAME["security_bounty"]
            == "Security Operations"
        )

    async def test_grant_routes_to_finance(self):
        from app.api.v1.workstreams import _OPPORTUNITY_TYPE_TO_DEPARTMENT_NAME

        assert _OPPORTUNITY_TYPE_TO_DEPARTMENT_NAME["grant"] == "Finance"


class TestKindAccepted:
    async def test_business_opportunity_in_kind_default_map(self):
        from app.api.v1.workstreams import _DRAFT_KIND_TO_DEPARTMENT_NAME

        assert "business_opportunity" in _DRAFT_KIND_TO_DEPARTMENT_NAME
