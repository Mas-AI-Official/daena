"""Tests for the Company Mode orchestrator.

Covers:
- Brief -> Missions structure (Sales + Marketing both spawned).
- SalesAgent and MarketingAgent are invoked with correct args.
- Drafts land AWAITING_APPROVAL by default, COMPLETED on auto_send.
- LinkedIn + auto_send emits a governance warning upstream (checked
  at the API layer in test_company_mode_api).
- Summary string renders for both happy and partially-failed paths.
- Activation result round-trips to dict cleanly.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.company_mode import (
    ActivationBrief,
    MissionChannel,
    MissionStatus,
    _build_icp,
    _format_next_steps,
    _format_summary,
    activate,
)


def _make_brief(**overrides: Any) -> ActivationBrief:
    defaults = {
        "company_name": "MAS-AI Technologies",
        "company_one_liner": "Governed multi-agent AI orchestration.",
        "target_customer": "SMB CISOs 10-100 employees US/CA",
        "customer_pain": "Drowning in security alerts.",
        "our_promise": "Governed AI SecOps in under an hour.",
        "proof_points": ["PhiLattice filed", "Zero-FP gate"],
        "channels": [MissionChannel.LINKEDIN, MissionChannel.EMAIL],
        "prospect_limit_per_mission": 3,
    }
    defaults.update(overrides)
    return ActivationBrief(**defaults)


def test_build_icp_string_includes_all_core_fields() -> None:
    icp = _build_icp(_make_brief())
    assert "CISOs" in icp
    assert "security alerts" in icp.lower()
    assert "Governed AI SecOps" in icp
    assert "PhiLattice" in icp


@pytest.mark.asyncio
async def test_activate_spawns_sales_then_marketing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sales runs first, marketing consumes its prospects, result has both missions."""
    from app.services import company_mode

    fake_contacts = [
        {"id": str(uuid4()), "name": f"Contact {i}"} for i in range(3)
    ]

    sales = MagicMock()
    sales.prospect = AsyncMock(return_value=fake_contacts)

    marketing = MagicMock()
    marketing.author_outreach = AsyncMock(
        side_effect=[{"id": str(uuid4()), "preview": f"draft {i}"} for i in range(3)],
    )

    monkeypatch.setattr(company_mode, "create_sales_agent", lambda **_kw: sales)
    monkeypatch.setattr(company_mode, "create_marketing_agent", lambda **_kw: marketing)

    db = MagicMock()
    db.commit = AsyncMock()

    result = await activate(
        db,
        tenant_id=uuid4(),
        user_id=uuid4(),
        brief=_make_brief(),
    )

    assert len(result.missions) == 2
    assert result.missions[0].department_slug == "sales"
    assert result.missions[0].mind_name == "Orion"
    assert result.missions[0].prospects_found == 3
    assert result.missions[1].department_slug == "marketing"
    assert result.missions[1].mind_name == "Zephyr"
    assert result.missions[1].drafts_generated == 3

    # Default brief has auto_send=False -> drafts await approval
    assert result.missions[1].drafts_awaiting_approval == 3
    assert result.missions[1].status == MissionStatus.AWAITING_APPROVAL

    # Sales got the ICP we built
    sales.prospect.assert_awaited_once()
    assert "CISOs" in sales.prospect.await_args.kwargs["icp_description"]

    # DB commit was called to persist CRM writes
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_activate_auto_send_marks_missions_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import company_mode

    sales = MagicMock()
    sales.prospect = AsyncMock(return_value=[{"id": str(uuid4())}])
    marketing = MagicMock()
    marketing.author_outreach = AsyncMock(return_value={"id": str(uuid4()), "preview": "x"})
    monkeypatch.setattr(company_mode, "create_sales_agent", lambda **_kw: sales)
    monkeypatch.setattr(company_mode, "create_marketing_agent", lambda **_kw: marketing)
    db = MagicMock()
    db.commit = AsyncMock()

    brief = _make_brief(auto_send=True)
    result = await activate(db, tenant_id=uuid4(), user_id=uuid4(), brief=brief)
    mkt = result.missions[1]
    assert mkt.status == MissionStatus.COMPLETED
    assert mkt.drafts_awaiting_approval == 0


@pytest.mark.asyncio
async def test_activate_sales_failure_still_returns_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sales crash must not prevent marketing from recording the no-prospect reason."""
    from app.services import company_mode

    sales = MagicMock()
    sales.prospect = AsyncMock(side_effect=RuntimeError("osint_provider_down"))
    marketing = MagicMock()
    marketing.author_outreach = AsyncMock()
    monkeypatch.setattr(company_mode, "create_sales_agent", lambda **_kw: sales)
    monkeypatch.setattr(company_mode, "create_marketing_agent", lambda **_kw: marketing)
    db = MagicMock()
    db.commit = AsyncMock()

    result = await activate(db, tenant_id=uuid4(), user_id=uuid4(), brief=_make_brief())
    sales_m = result.missions[0]
    mkt_m = result.missions[1]
    assert sales_m.status == MissionStatus.FAILED
    assert any("sales_dispatch_failed" in e for e in sales_m.errors)
    # Marketing should not have been called (no prospects)
    marketing.author_outreach.assert_not_awaited()
    assert mkt_m.status == MissionStatus.COMPLETED
    assert "no_prospects_from_sales" in mkt_m.errors


def test_format_summary_happy_path() -> None:
    brief = _make_brief()
    missions = [
        MagicMock(status=MissionStatus.AWAITING_APPROVAL, drafts_awaiting_approval=5, mind_name="Orion", department_slug="sales"),
        MagicMock(status=MissionStatus.AWAITING_APPROVAL, drafts_awaiting_approval=5, mind_name="Zephyr", department_slug="marketing"),
    ]
    s = _format_summary(brief, missions, prospect_count=5, draft_count=5)
    assert "MAS-AI Technologies" in s
    assert "Orion" in s and "Zephyr" in s
    assert "approval queue" in s


def test_format_summary_partial_failure() -> None:
    brief = _make_brief()
    failed = MagicMock(status=MissionStatus.FAILED, mind_name="Orion", department_slug="sales")
    ok = MagicMock(status=MissionStatus.AWAITING_APPROVAL, drafts_awaiting_approval=0, mind_name="Zephyr", department_slug="marketing")
    s = _format_summary(brief, [failed, ok], prospect_count=0, draft_count=0)
    assert "with issues" in s
    assert "Orion" in s


def test_next_steps_warn_linkedin_autosend() -> None:
    brief = _make_brief(auto_send=True, channels=[MissionChannel.LINKEDIN])
    steps = _format_next_steps(brief, missions=[])
    joined = " ".join(steps).lower()
    assert "linkedin" in joined and "tos" in joined


def test_next_steps_default_includes_review_and_pipeline() -> None:
    brief = _make_brief()
    missions = [MagicMock(drafts_awaiting_approval=1)]
    steps = _format_next_steps(brief, missions)
    text = " ".join(steps).lower()
    assert "approval queue" in text
    assert "pipeline" in text


@pytest.mark.asyncio
async def test_activation_result_to_dict_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import company_mode

    sales = MagicMock()
    sales.prospect = AsyncMock(return_value=[{"id": str(uuid4())}])
    marketing = MagicMock()
    marketing.author_outreach = AsyncMock(return_value={"id": str(uuid4())})
    monkeypatch.setattr(company_mode, "create_sales_agent", lambda **_kw: sales)
    monkeypatch.setattr(company_mode, "create_marketing_agent", lambda **_kw: marketing)
    db = MagicMock()
    db.commit = AsyncMock()

    result = await activate(db, tenant_id=uuid4(), user_id=uuid4(), brief=_make_brief())
    d = result.to_dict()
    assert d["activation_id"] == result.activation_id
    assert d["brief"]["company_name"] == "MAS-AI Technologies"
    assert isinstance(d["missions"], list) and len(d["missions"]) == 2
    assert d["prospects_count"] == 1
    assert isinstance(d["next_steps"], list) and len(d["next_steps"]) >= 1
