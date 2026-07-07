"""Tests for the plan entitlement spine (app/core/entitlements.py) and the
require_tier / require_feature dependencies (app/api/deps.py).

Pure-logic assertions cover ranking, comparison, and feature lookup. Dependency tests
use a fake user + fake db (no real DB session needed) to prove the FOUNDER short-circuit,
the FREE->paid 402, and the tier ordering, including that FOUNDER never touches the DB.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.deps import CurrentUser, require_feature, require_tier
from app.core.entitlements import (
    PLAN_RANK,
    Feature,
    min_plan_for_feature,
    plan_entitlements,
    plan_has_feature,
    plan_rank,
    plan_satisfies,
    resolve_effective_plan,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDB:
    """Minimal stand-in for AsyncSession: records whether execute() was called."""

    def __init__(self, plan):
        self._plan = plan
        self.calls = 0

    async def execute(self, _stmt):
        self.calls += 1
        return _FakeResult(self._plan)


def _user(role: str = "OPERATOR") -> CurrentUser:
    return CurrentUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="user@example.com",
        role=role,
    )


# ---------------------------------------------------------------------------
# Pure logic: ranking
# ---------------------------------------------------------------------------
def test_plan_rank_ordering():
    assert plan_rank("FREE") < plan_rank("PRO") < plan_rank("MAX") < plan_rank("ENTERPRISE")
    assert plan_rank("ENTERPRISE") < plan_rank("FOUNDER")


def test_plan_rank_is_case_insensitive():
    assert plan_rank("pro") == plan_rank("PRO")


def test_plan_rank_unknown_and_none_default_to_free():
    assert plan_rank("nonsense") == plan_rank("FREE")
    assert plan_rank(None) == plan_rank("FREE")


def test_max_sits_between_pro_and_enterprise():
    # The MAX tier exists in PlanType but was missing from cost_guard's table; the
    # entitlement spine must rank it correctly between PRO and ENTERPRISE.
    assert PLAN_RANK["PRO"] < PLAN_RANK["MAX"] < PLAN_RANK["ENTERPRISE"]


# ---------------------------------------------------------------------------
# Pure logic: satisfies
# ---------------------------------------------------------------------------
def test_plan_satisfies_same_and_higher():
    assert plan_satisfies("PRO", "PRO")
    assert plan_satisfies("ENTERPRISE", "PRO")
    assert plan_satisfies("FOUNDER", "ENTERPRISE")


def test_plan_satisfies_lower_fails():
    assert not plan_satisfies("FREE", "PRO")
    assert not plan_satisfies("PRO", "MAX")
    assert not plan_satisfies("MAX", "ENTERPRISE")


# ---------------------------------------------------------------------------
# Pure logic: features
# ---------------------------------------------------------------------------
def test_min_plan_for_feature():
    assert min_plan_for_feature(Feature.COUNCIL_ROUTING) == "PRO"
    assert min_plan_for_feature(Feature.QUINTESSENCE_ROUTING) == "MAX"
    assert min_plan_for_feature(Feature.ORG_MANAGEMENT) == "ENTERPRISE"


def test_plan_has_feature_boundaries():
    assert not plan_has_feature("FREE", Feature.COUNCIL_ROUTING)
    assert plan_has_feature("PRO", Feature.COUNCIL_ROUTING)
    assert not plan_has_feature("PRO", Feature.QUINTESSENCE_ROUTING)
    assert plan_has_feature("MAX", Feature.QUINTESSENCE_ROUTING)
    assert not plan_has_feature("MAX", Feature.ORG_MANAGEMENT)
    assert plan_has_feature("ENTERPRISE", Feature.ORG_MANAGEMENT)


def test_founder_has_every_feature():
    for feature in Feature:
        assert plan_has_feature("FOUNDER", feature)


def test_plan_entitlements_grows_with_tier():
    assert plan_entitlements("FREE") == []
    assert Feature.COUNCIL_ROUTING in plan_entitlements("PRO")
    assert set(plan_entitlements("ENTERPRISE")) == set(Feature)
    assert set(plan_entitlements("FOUNDER")) == set(Feature)


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------
async def test_resolve_effective_plan_founder_short_circuits():
    db = _FakeDB("FREE")
    plan = await resolve_effective_plan(db, role="FOUNDER", tenant_id=uuid4())
    assert plan == "FOUNDER"
    assert db.calls == 0  # founder never queries the subscriptions table


async def test_resolve_effective_plan_reads_active_subscription():
    db = _FakeDB("PRO")
    plan = await resolve_effective_plan(db, role="OPERATOR", tenant_id=uuid4())
    assert plan == "PRO"
    assert db.calls == 1


async def test_resolve_effective_plan_defaults_to_free():
    db = _FakeDB(None)  # no active subscription row
    plan = await resolve_effective_plan(db, role="OPERATOR", tenant_id=uuid4())
    assert plan == "FREE"


async def test_resolve_effective_plan_normalizes_unknown_to_free():
    db = _FakeDB("legacy_garbage")
    plan = await resolve_effective_plan(db, role="OPERATOR", tenant_id=uuid4())
    assert plan == "FREE"


# ---------------------------------------------------------------------------
# require_tier dependency
# ---------------------------------------------------------------------------
def test_require_tier_rejects_unknown_plan():
    with pytest.raises(ValueError):
        require_tier("PLATINUM")


async def test_require_tier_blocks_free_user():
    dep = require_tier("PRO")
    db = _FakeDB("FREE")
    with pytest.raises(HTTPException) as exc:
        await dep(user=_user(), db=db)
    assert exc.value.status_code == 402
    assert exc.value.detail["current_plan"] == "FREE"
    assert exc.value.detail["required_plan"] == "PRO"


async def test_require_tier_allows_equal_plan():
    dep = require_tier("PRO")
    db = _FakeDB("PRO")
    user = _user()
    out = await dep(user=user, db=db)
    assert out is user


async def test_require_tier_allows_higher_plan():
    dep = require_tier("PRO")
    db = _FakeDB("ENTERPRISE")
    out = await dep(user=_user(), db=db)
    assert out.role == "OPERATOR"


async def test_require_tier_founder_bypasses_without_db():
    dep = require_tier("ENTERPRISE")
    db = _FakeDB("FREE")
    out = await dep(user=_user(role="FOUNDER"), db=db)
    assert out.role == "FOUNDER"
    assert db.calls == 0


# ---------------------------------------------------------------------------
# require_feature dependency
# ---------------------------------------------------------------------------
async def test_require_feature_blocks_when_missing():
    dep = require_feature(Feature.QUINTESSENCE_ROUTING)
    db = _FakeDB("PRO")  # PRO has council but not quintessence
    with pytest.raises(HTTPException) as exc:
        await dep(user=_user(), db=db)
    assert exc.value.status_code == 402
    assert exc.value.detail["feature"] == "quintessence_routing"
    assert exc.value.detail["required_plan"] == "MAX"


async def test_require_feature_allows_when_present():
    dep = require_feature(Feature.COUNCIL_ROUTING)
    db = _FakeDB("PRO")
    user = _user()
    out = await dep(user=user, db=db)
    assert out is user
