"""Phase 10 commit-1 — verify the three P0 UNSAFE gates land correctly.

Coverage:
- U1: ``POST /api/v1/company-mode/activate`` refuses ``auto_send=true``
  combined with ``require_founder_approval=false`` with HTTP 422.
- U2: ``POST /api/v1/security/scans/start`` refuses out-of-scope targets
  at the REST boundary with HTTP 403 ``code=target_not_in_scope``.
- U3: ``POST /api/v1/engagements`` enforces the same scope gate at the
  REST boundary with HTTP 403.

Each test patches :func:`load_authorized_scope` so the scope reflects an
explicit fixture, not the on-disk JSON. That keeps the test hermetic and
matches the gate's documented dependency-injection seam.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.services.security.yellow_runtime_gate import AuthorizedScope


# ---------------------------------------------------------------------------
# U1 — Company Mode auto_send + require_founder_approval contradiction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_u1_company_mode_autosend_without_approval_returns_422(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Refuse the contradictory combination at the REST boundary."""
    body = {
        "company_name": "Test Co",
        "company_one_liner": "We test things.",
        "target_customer": "QA engineers",
        "customer_pain": "Untested gates",
        "our_promise": "Tested gates",
        "proof_points": ["Phase 10 audit"],
        "channels": ["email"],
        "prospect_limit_per_mission": 1,
        "tone": "warm-direct",
        "auto_send": True,
        "require_founder_approval": False,
        "notes": None,
    }
    resp = await client.post("/api/v1/company-mode/activate", json=body, headers=auth_headers)
    assert resp.status_code == 422, resp.text
    data = resp.json()
    detail = data.get("detail")
    # FastAPI may wrap or unwrap depending on validation source; accept either.
    if isinstance(detail, dict):
        assert detail.get("code") == "auto_send_requires_founder_approval"
    else:
        assert "auto_send_requires_founder_approval" in str(detail)


@pytest.mark.asyncio
async def test_u1_company_mode_safe_combinations_pass_guard(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Any non-contradictory combination passes the new guard.

    The activation may still 5xx for downstream reasons (real LLM not
    wired in tests). We only assert the new 422 guard does NOT fire.
    """
    base = {
        "company_name": "Test Co",
        "company_one_liner": "We test things.",
        "target_customer": "QA engineers",
        "customer_pain": "Untested gates",
        "our_promise": "Tested gates",
        "proof_points": [],
        "channels": ["email"],
        "prospect_limit_per_mission": 1,
        "tone": "warm-direct",
        "notes": None,
    }
    safe_combos = [
        {"auto_send": False, "require_founder_approval": True},
        {"auto_send": False, "require_founder_approval": False},
        {"auto_send": True, "require_founder_approval": True},
    ]
    for combo in safe_combos:
        resp = await client.post(
            "/api/v1/company-mode/activate",
            json={**base, **combo},
            headers=auth_headers,
        )
        # The new guard must NOT 422 with the contradictory-combo code.
        if resp.status_code == 422:
            detail = resp.json().get("detail")
            if isinstance(detail, dict):
                assert detail.get("code") != "auto_send_requires_founder_approval", (
                    f"safe combo {combo} blocked by U1 guard"
                )


# ---------------------------------------------------------------------------
# U2 — Scan REST scope gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_u2_scan_start_blocks_out_of_scope_target(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """REST boundary refuses out-of-scope target with HTTP 403.

    Patches :func:`load_authorized_scope` to return an empty scope
    (deny-by-default), then asserts the scan-start route refuses any
    target before it ever reaches the workflow.
    """
    empty_scope = AuthorizedScope()
    with patch(
        "app.api.v1.security_dashboard.load_authorized_scope",
        return_value=empty_scope,
    ):
        resp = await client.post(
            "/api/v1/security/scans/start",
            json={"target": "out-of-scope-target.example.com", "tier": "SCOUT"},
            headers=auth_headers,
        )
    assert resp.status_code == 403, resp.text
    detail = resp.json().get("detail")
    assert isinstance(detail, dict), detail
    assert detail["code"] == "target_not_in_scope"
    assert detail["target"] == "out-of-scope-target.example.com"


@pytest.mark.asyncio
async def test_u2_scan_start_allows_in_scope_target(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """In-scope target passes the gate (and may proceed to workflow).

    The downstream workflow may itself error in a unit-test environment
    where dispatch dependencies are not seeded. We only assert that the
    REST gate does NOT short-circuit with 403.
    """
    in_scope = AuthorizedScope(
        exact_domains=frozenset({"in-scope.example.com"}),
    )
    with patch(
        "app.api.v1.security_dashboard.load_authorized_scope",
        return_value=in_scope,
    ):
        resp = await client.post(
            "/api/v1/security/scans/start",
            json={"target": "in-scope.example.com", "tier": "SCOUT"},
            headers=auth_headers,
        )
    # 200 if the workflow is happy; 5xx if dispatch deps aren't seeded.
    # Either is fine — what we forbid is the new 403 firing.
    assert resp.status_code != 403, resp.text


# ---------------------------------------------------------------------------
# U3 — Engagements REST scope gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_u3_engagement_start_blocks_out_of_scope_target(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """REST boundary refuses out-of-scope target on engagements too."""
    empty_scope = AuthorizedScope()
    with patch(
        "app.api.v1.engagements.load_authorized_scope",
        return_value=empty_scope,
    ):
        resp = await client.post(
            "/api/v1/engagements",
            json={"target": "out-of-scope-target.example.com", "tier": "SCOUT"},
            headers=auth_headers,
        )
    assert resp.status_code == 403, resp.text
    detail = resp.json().get("detail")
    assert isinstance(detail, dict), detail
    assert detail["code"] == "target_not_in_scope"
