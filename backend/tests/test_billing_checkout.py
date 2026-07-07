"""Tests for the Stripe checkout / subscription service (app/services/billing/
checkout_service.py) and the /billing checkout + webhook endpoints.

No real Stripe is ever contacted: `get_settings` is monkeypatched to a fake with
the Stripe fields, and `_get_stripe` is replaced by a fake SDK where needed. The
DB-writing tests use the in-memory SQLite session and seed a real Tenant via the
`seed_auth_principal` fixture (tenant_id is an enforced FK).
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.financial import Subscription
from app.services.billing import checkout_service


# ---------------------------------------------------------------------------
# Fake settings / SDK helpers
# ---------------------------------------------------------------------------
def _settings(**overrides):
    base = dict(
        stripe_enabled=False,
        stripe_secret_key="",
        stripe_webhook_secret="",
        stripe_price_pro="",
        stripe_price_max="",
        stripe_price_enterprise="",
        billing_success_url="https://app.test/ok",
        billing_cancel_url="https://app.test/cancel",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _patch_settings(monkeypatch, **overrides):
    monkeypatch.setattr(checkout_service, "get_settings", lambda: _settings(**overrides))


def _fully_configured(**extra):
    return dict(
        stripe_enabled=True,
        stripe_secret_key="sk_test_x",
        stripe_webhook_secret="whsec_x",
        stripe_price_pro="price_pro",
        stripe_price_max="price_max",
        stripe_price_enterprise="price_ent",
        **extra,
    )


# ---------------------------------------------------------------------------
# Pure mapping logic
# ---------------------------------------------------------------------------
def test_billing_not_configured_by_default(monkeypatch):
    _patch_settings(monkeypatch)
    assert checkout_service.billing_configured() is False
    assert checkout_service.purchasable_plans() == []


def test_billing_configured_when_enabled_and_keyed(monkeypatch):
    _patch_settings(monkeypatch, stripe_enabled=True, stripe_secret_key="sk_test_x")
    assert checkout_service.billing_configured() is True


def test_purchasable_plans_only_priced_tiers_ranked(monkeypatch):
    # Only PRO + ENTERPRISE have a price id -> MAX is omitted, order is by rank.
    _patch_settings(
        monkeypatch,
        stripe_price_pro="price_pro",
        stripe_price_enterprise="price_ent",
    )
    assert checkout_service.purchasable_plans() == ["PRO", "ENTERPRISE"]


def test_free_and_founder_never_purchasable(monkeypatch):
    _patch_settings(monkeypatch, **_fully_configured())
    plans = checkout_service.purchasable_plans()
    assert "FREE" not in plans
    assert "FOUNDER" not in plans
    assert plans == ["PRO", "MAX", "ENTERPRISE"]


def test_price_id_round_trips(monkeypatch):
    _patch_settings(monkeypatch, **_fully_configured())
    assert checkout_service.price_id_for_plan("pro") == "price_pro"
    assert checkout_service.plan_for_price_id("price_max") == "MAX"
    assert checkout_service.plan_for_price_id("price_nonexistent") is None


# ---------------------------------------------------------------------------
# Stripe gating
# ---------------------------------------------------------------------------
def test_create_checkout_raises_when_not_configured(monkeypatch):
    # Price exists (so PRO passes the purchasable guard) but billing is off, so
    # the SDK gate is what rejects -- proving the BillingNotConfigured path.
    _patch_settings(monkeypatch, stripe_price_pro="price_pro")
    with pytest.raises(checkout_service.BillingNotConfigured):
        checkout_service.create_checkout_session(plan="PRO", tenant_id=uuid4())


def test_create_checkout_rejects_unpurchasable_plan(monkeypatch):
    _patch_settings(monkeypatch, **_fully_configured())
    with pytest.raises(ValueError):
        checkout_service.create_checkout_session(plan="FREE", tenant_id=uuid4())


def test_create_checkout_happy_path(monkeypatch):
    _patch_settings(monkeypatch, **_fully_configured())

    captured = {}

    class _FakeSession:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(url="https://stripe.test/session/abc")

    fake_stripe = SimpleNamespace(checkout=SimpleNamespace(Session=_FakeSession))
    monkeypatch.setattr(checkout_service, "_get_stripe", lambda: fake_stripe)

    tid = uuid4()
    url = checkout_service.create_checkout_session(
        plan="PRO", tenant_id=tid, customer_email="buyer@example.com"
    )
    assert url == "https://stripe.test/session/abc"
    assert captured["mode"] == "subscription"
    assert captured["line_items"] == [{"price": "price_pro", "quantity": 1}]
    assert captured["client_reference_id"] == str(tid)
    assert captured["metadata"]["plan"] == "PRO"


def test_verify_webhook_requires_secret(monkeypatch):
    # Enabled + keyed but NO webhook secret -> still not-configured for webhooks.
    _patch_settings(monkeypatch, stripe_enabled=True, stripe_secret_key="sk_test_x")
    fake_stripe = SimpleNamespace()
    monkeypatch.setattr(checkout_service, "_get_stripe", lambda: fake_stripe)
    with pytest.raises(checkout_service.BillingNotConfigured):
        checkout_service.verify_webhook_event(b"{}", "sig")


# ---------------------------------------------------------------------------
# apply_subscription_event (DB writes; one-ACTIVE invariant)
# ---------------------------------------------------------------------------
async def _active_rows(db, tenant_id):
    rows = (
        await db.execute(
            select(Subscription).where(Subscription.tenant_id == tenant_id)
        )
    ).scalars().all()
    return [r for r in rows if r.status == "ACTIVE"]


async def test_apply_inserts_when_none(db_session, seed_auth_principal, test_tenant_id):
    sub = await checkout_service.apply_subscription_event(
        db_session, tenant_id=test_tenant_id, plan="pro", stripe_customer_id="cus_1"
    )
    assert sub.plan == "PRO"
    assert sub.status == "ACTIVE"
    assert sub.stripe_customer_id == "cus_1"
    assert len(await _active_rows(db_session, test_tenant_id)) == 1


async def test_apply_updates_existing_in_place(db_session, seed_auth_principal, test_tenant_id):
    first = await checkout_service.apply_subscription_event(
        db_session, tenant_id=test_tenant_id, plan="PRO"
    )
    second = await checkout_service.apply_subscription_event(
        db_session, tenant_id=test_tenant_id, plan="MAX", stripe_subscription_id="sub_9"
    )
    assert first.id == second.id  # same canonical row, updated in place
    assert second.plan == "MAX"
    assert second.stripe_subscription_id == "sub_9"
    assert len(await _active_rows(db_session, test_tenant_id)) == 1


async def test_apply_collapses_duplicate_active_rows(
    db_session, seed_auth_principal, test_tenant_id
):
    # Simulate a pre-existing pair of ACTIVE rows (legacy / race) for the tenant.
    db_session.add(Subscription(tenant_id=test_tenant_id, plan="FREE", status="ACTIVE"))
    db_session.add(Subscription(tenant_id=test_tenant_id, plan="PRO", status="ACTIVE"))
    await db_session.commit()

    await checkout_service.apply_subscription_event(
        db_session, tenant_id=test_tenant_id, plan="ENTERPRISE"
    )
    active = await _active_rows(db_session, test_tenant_id)
    assert len(active) == 1
    assert active[0].plan == "ENTERPRISE"


async def test_apply_does_not_clobber_existing_stripe_ids(
    db_session, seed_auth_principal, test_tenant_id
):
    await checkout_service.apply_subscription_event(
        db_session, tenant_id=test_tenant_id, plan="PRO", stripe_customer_id="cus_keep"
    )
    sub = await checkout_service.apply_subscription_event(
        db_session, tenant_id=test_tenant_id, plan="MAX"  # no customer id supplied
    )
    assert sub.stripe_customer_id == "cus_keep"


# ---------------------------------------------------------------------------
# handle_event interpretation
# ---------------------------------------------------------------------------
async def test_handle_checkout_completed_activates(
    db_session, seed_auth_principal, test_tenant_id, monkeypatch
):
    _patch_settings(monkeypatch, **_fully_configured())
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": str(test_tenant_id),
                "metadata": {"tenant_id": str(test_tenant_id), "plan": "PRO"},
                "customer": "cus_a",
                "subscription": "sub_a",
            }
        },
    }
    result = await checkout_service.handle_event(db_session, event)
    assert result == {"handled": True, "plan": "PRO", "status": "ACTIVE"}
    active = await _active_rows(db_session, test_tenant_id)
    assert active[0].stripe_subscription_id == "sub_a"


async def test_handle_subscription_updated_reverse_maps_price(
    db_session, seed_auth_principal, test_tenant_id, monkeypatch
):
    _patch_settings(monkeypatch, **_fully_configured())
    event = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_b",
                "metadata": {"tenant_id": str(test_tenant_id)},
                "customer": "cus_b",
                "status": "active",
                "items": {"data": [{"price": {"id": "price_max"}}]},
                "current_period_start": 1_700_000_000,
                "current_period_end": 1_702_000_000,
            }
        },
    }
    result = await checkout_service.handle_event(db_session, event)
    assert result["plan"] == "MAX"
    assert result["status"] == "ACTIVE"


async def test_handle_subscription_updated_past_due_downgrades(
    db_session, seed_auth_principal, test_tenant_id, monkeypatch
):
    _patch_settings(monkeypatch, **_fully_configured())
    event = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_c",
                "metadata": {"tenant_id": str(test_tenant_id)},
                "status": "past_due",
                "items": {"data": [{"price": {"id": "price_pro"}}]},
            }
        },
    }
    result = await checkout_service.handle_event(db_session, event)
    assert result["plan"] == "FREE"
    assert result["status"] == "CANCELED"


async def test_handle_subscription_deleted_downgrades_to_free(
    db_session, seed_auth_principal, test_tenant_id
):
    await checkout_service.apply_subscription_event(
        db_session, tenant_id=test_tenant_id, plan="PRO"
    )
    event = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_d", "metadata": {"tenant_id": str(test_tenant_id)}}},
    }
    result = await checkout_service.handle_event(db_session, event)
    assert result == {"handled": True, "plan": "FREE", "status": "CANCELED"}


async def test_handle_unknown_event_is_ignored(db_session):
    result = await checkout_service.handle_event(
        db_session, {"type": "invoice.paid", "data": {"object": {}}}
    )
    assert result["handled"] is False
    assert result["reason"] == "ignored"


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------
async def test_plans_endpoint_reports_disabled_by_default(
    client, auth_headers, monkeypatch
):
    _patch_settings(monkeypatch)
    resp = await client.get("/api/v1/billing/plans", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["billing_enabled"] is False
    assert body["plans"] == []


async def test_checkout_endpoint_422_on_unavailable_plan(
    client, auth_headers, monkeypatch
):
    _patch_settings(monkeypatch)  # nothing purchasable
    resp = await client.post(
        "/api/v1/billing/checkout", headers=auth_headers, json={"plan": "PRO"}
    )
    assert resp.status_code == 422


async def test_checkout_endpoint_503_when_priced_but_disabled(
    client, auth_headers, monkeypatch
):
    # Price configured (so PRO is "purchasable") but stripe_enabled False -> the
    # service raises BillingNotConfigured, which the route maps to 503.
    _patch_settings(monkeypatch, stripe_price_pro="price_pro")
    resp = await client.post(
        "/api/v1/billing/checkout", headers=auth_headers, json={"plan": "PRO"}
    )
    assert resp.status_code == 503
    assert resp.json()["detail"]["error"] == "not_configured"


async def test_webhook_endpoint_503_when_not_configured(client, monkeypatch):
    _patch_settings(monkeypatch)
    resp = await client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"Stripe-Signature": "sig"}
    )
    assert resp.status_code == 503
