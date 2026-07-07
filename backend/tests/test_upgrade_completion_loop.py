"""Upgrade-completion loop: billing WRITE-side -> entitlement READ-side join.

This is the integration test that closes the highest-severity uncovered
monetization failure: "charge the card, then deny the feature."

The two halves of the loop are each well-tested in isolation:
  * test_billing_checkout.py proves the Stripe webhook WRITES a Subscription
    (status="ACTIVE", plan upper-cased) -- asserting checkout_service's own
    result dict.
  * test_routing_entitlement_gate.py / test_org_entitlement_gate.py prove the
    gates READ an ACTIVE Subscription correctly -- but they SEED that row by
    hand and assume it has the shape the billing side produces.

Nothing crosses the boundary. billing writes status=_ACTIVE ("ACTIVE") and
plan.upper(); entitlements filters the INLINE literal "ACTIVE" (entitlements.py
line ~124) plus plan rank. Those two literals live in two modules with no
shared constant. If either drifts (status casing, plan casing), BOTH suites
stay green while a paying customer stays gated. This file is the only test
that fails on that drift.

Method (mirrors Stripe's canonical provisioning test -- assert the CAPABILITY
unlocks, not just that a row was written): drive checkout_service.handle_event
with the exact event dict the live POST /webhook hands it after signature
verification, then resolve the entitlement read-side.

CRITICAL: every resolution uses a NON-FOUNDER role ("MEMBER"). The FOUNDER role
short-circuits resolve_effective_plan to "FOUNDER" WITHOUT reading the database
(entitlements.py ~line 119), so a FOUNDER-role test would pass vacuously even if
the billing->entitlement join were completely broken. Only a non-FOUNDER role
actually consults the Subscription the webhook just wrote.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.entitlements import (
    Feature,
    plan_has_feature,
    resolve_effective_plan,
)
from app.models.financial import Subscription
from app.services.billing import checkout_service


# --- Stripe-shaped event builders (identical to what /webhook passes through) -

def _checkout_completed(tenant_id, plan: str) -> dict:
    """A verified `checkout.session.completed` event for `plan`."""
    return {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"tenant_id": str(tenant_id), "plan": plan},
                "customer": "cus_test",
                "subscription": "sub_test",
            }
        },
    }


def _subscription_deleted(tenant_id) -> dict:
    """A verified `customer.subscription.deleted` event (cancel / churn)."""
    return {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "metadata": {"tenant_id": str(tenant_id)},
                "customer": "cus_test",
                "id": "sub_test",
            }
        },
    }


async def _member_plan(db, tenant_id) -> str:
    """Resolve the tenant's effective plan as a NON-FOUNDER user.

    Using a non-FOUNDER role is the whole point: it forces the Subscription
    read so a broken join is observable.
    """
    return await resolve_effective_plan(db, role="MEMBER", tenant_id=tenant_id)


# --- The loop --------------------------------------------------------------

async def test_free_tenant_has_no_paid_features(
    db_session, seed_auth_principal, test_tenant_id
):
    """Precondition: a brand-new tenant with no Subscription is FREE and gated.

    Proves the gate is genuinely CLOSED before purchase -- otherwise the
    "it opens after purchase" assertions below would be meaningless.
    """
    plan = await _member_plan(db_session, test_tenant_id)
    assert plan == "FREE"
    assert plan_has_feature(plan, Feature.COUNCIL_ROUTING) is False
    assert plan_has_feature(plan, Feature.QUINTESSENCE_ROUTING) is False
    assert plan_has_feature(plan, Feature.ORG_MANAGEMENT) is False


async def test_checkout_completion_unlocks_council_for_pro(
    db_session, seed_auth_principal, test_tenant_id
):
    """PRO checkout -> COUNCIL opens, QUINTESSENCE/ORG stay shut. The join proof.

    This single test exhibits BOTH literals and their join:
      * the WRITE literal -- the row carries status "ACTIVE" + plan "PRO";
      * the READ literal  -- resolve_effective_plan finds exactly that row.
    Drift on either side fails here.
    """
    result = await checkout_service.handle_event(
        db_session, _checkout_completed(test_tenant_id, "PRO")
    )
    assert result["handled"] is True

    # WRITE literal: the persisted row is exactly what the entitlement read filters on.
    row = (
        await db_session.execute(
            select(Subscription).where(Subscription.tenant_id == test_tenant_id)
        )
    ).scalar_one()
    assert row.status == "ACTIVE", "billing must write the literal entitlements filters on"
    assert row.plan == "PRO", "billing must write the upper-cased plan entitlements ranks"

    # READ literal: a real (non-FOUNDER) user now resolves to PRO and unlocks COUNCIL.
    plan = await _member_plan(db_session, test_tenant_id)
    assert plan == "PRO"
    assert plan_has_feature(plan, Feature.COUNCIL_ROUTING) is True
    # Per-FEATURE, not "any paid plan unlocks everything": PRO does NOT reach MAX/ENTERPRISE.
    assert plan_has_feature(plan, Feature.QUINTESSENCE_ROUTING) is False
    assert plan_has_feature(plan, Feature.ORG_MANAGEMENT) is False


async def test_checkout_completion_unlocks_quintessence_for_max(
    db_session, seed_auth_principal, test_tenant_id
):
    """MAX checkout -> COUNCIL and QUINTESSENCE both open, ORG still shut."""
    await checkout_service.handle_event(
        db_session, _checkout_completed(test_tenant_id, "MAX")
    )
    plan = await _member_plan(db_session, test_tenant_id)
    assert plan == "MAX"
    assert plan_has_feature(plan, Feature.COUNCIL_ROUTING) is True
    assert plan_has_feature(plan, Feature.QUINTESSENCE_ROUTING) is True
    assert plan_has_feature(plan, Feature.ORG_MANAGEMENT) is False


async def test_checkout_completion_unlocks_org_for_enterprise(
    db_session, seed_auth_principal, test_tenant_id
):
    """ENTERPRISE checkout -> all three features open (closes the full matrix)."""
    await checkout_service.handle_event(
        db_session, _checkout_completed(test_tenant_id, "ENTERPRISE")
    )
    plan = await _member_plan(db_session, test_tenant_id)
    assert plan == "ENTERPRISE"
    assert plan_has_feature(plan, Feature.COUNCIL_ROUTING) is True
    assert plan_has_feature(plan, Feature.QUINTESSENCE_ROUTING) is True
    assert plan_has_feature(plan, Feature.ORG_MANAGEMENT) is True


async def test_upgrade_then_downgrade_walks_the_gate(
    db_session, seed_auth_principal, test_tenant_id
):
    """A second checkout upgrades in place (PRO -> MAX) and reopens the right gate.

    Guards the apply_subscription_event "exactly one ACTIVE row, update in place"
    path against the entitlement read: after the upgrade event the tenant must
    resolve to the NEW plan, not the stale one or a duplicate ACTIVE row.
    """
    await checkout_service.handle_event(
        db_session, _checkout_completed(test_tenant_id, "PRO")
    )
    assert plan_has_feature(await _member_plan(db_session, test_tenant_id),
                            Feature.QUINTESSENCE_ROUTING) is False

    await checkout_service.handle_event(
        db_session, _checkout_completed(test_tenant_id, "MAX")
    )
    plan = await _member_plan(db_session, test_tenant_id)
    assert plan == "MAX"
    assert plan_has_feature(plan, Feature.QUINTESSENCE_ROUTING) is True

    # Exactly one row total -- the upgrade reused the canonical record, no duplicate.
    rows = (
        await db_session.execute(
            select(Subscription).where(Subscription.tenant_id == test_tenant_id)
        )
    ).scalars().all()
    assert len(rows) == 1


async def test_subscription_deletion_recloses_all_gates(
    db_session, seed_auth_principal, test_tenant_id
):
    """Cancel reverses the loop: a deleted subscription drops the tenant to FREE.

    The "cancel-but-keep-the-feature" leak is the mirror of charge-but-deny;
    this proves the gate closes again when the active row is canceled.
    """
    await checkout_service.handle_event(
        db_session, _checkout_completed(test_tenant_id, "PRO")
    )
    assert plan_has_feature(await _member_plan(db_session, test_tenant_id),
                            Feature.COUNCIL_ROUTING) is True

    result = await checkout_service.handle_event(
        db_session, _subscription_deleted(test_tenant_id)
    )
    assert result["handled"] is True

    plan = await _member_plan(db_session, test_tenant_id)
    assert plan == "FREE"
    assert plan_has_feature(plan, Feature.COUNCIL_ROUTING) is False
    assert plan_has_feature(plan, Feature.QUINTESSENCE_ROUTING) is False
    assert plan_has_feature(plan, Feature.ORG_MANAGEMENT) is False


async def test_founder_role_bypasses_the_join_entirely(
    db_session, seed_auth_principal, test_tenant_id
):
    """Documents WHY the tests above use MEMBER, not FOUNDER.

    A FOUNDER resolves to "FOUNDER" with NO database read, so every feature is
    unlocked even though this tenant has no Subscription at all. If the join
    tests above had used FOUNDER, they would pass no matter how broken the
    billing->entitlement link was. This asserts that vacuous path explicitly so
    a future reader does not "simplify" the suite onto it.
    """
    plan = await resolve_effective_plan(db_session, role="FOUNDER", tenant_id=test_tenant_id)
    assert plan == "FOUNDER"
    assert plan_has_feature(plan, Feature.COUNCIL_ROUTING) is True
    assert plan_has_feature(plan, Feature.QUINTESSENCE_ROUTING) is True
    assert plan_has_feature(plan, Feature.ORG_MANAGEMENT) is True

    # ...and there is genuinely no subscription -- the unlock came from the role,
    # not from any persisted plan. A MEMBER on this same tenant is FREE.
    member_plan = await _member_plan(db_session, test_tenant_id)
    assert member_plan == "FREE"
