"""Stripe checkout + subscription lifecycle for tenant monetization.

This is the only place that talks to Stripe. It is OFF by default: unless
`settings.stripe_enabled` is True AND `settings.stripe_secret_key` is set, every
entry point raises `BillingNotConfigured`, which the API layer maps to HTTP 503
`not_configured`. The `stripe` SDK is imported lazily INSIDE the functions that
need it, so importing this module (and therefore `app.main`) never requires the
package to be installed -- a deployment that does not sell never carries the
dependency or the keys.

What it does:
  * `create_checkout_session` -- hand a tenant off to Stripe-hosted Checkout for
    a purchasable plan. Daena never sees card data; payment happens on Stripe.
  * `verify_webhook_event` -- authenticate a webhook via the Stripe-Signature
    header (the webhook endpoint is unauthenticated by JWT on purpose; the
    signature IS its auth).
  * `apply_subscription_event` / `handle_event` -- the ONLY writers of
    `Subscription.plan` / status / stripe ids. They enforce one ACTIVE row per
    tenant and never touch the Numeric budget columns.

No money is moved by this code; Stripe processes the payment and we record the
resulting plan. Real keys are supplied via env / .env, never committed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.entitlements import PLAN_RANK
from app.models.financial import Subscription

# Plans that can never be bought through Checkout: FREE is the default floor and
# FOUNDER is an internal role, not a sellable SKU.
_NON_PURCHASABLE = {"FREE", "FOUNDER"}

_ACTIVE = "ACTIVE"
_CANCELED = "CANCELED"

# Stripe subscription statuses that should map to an ACTIVE Daena plan. Anything
# else (past_due, canceled, unpaid, incomplete_expired, ...) downgrades.
_STRIPE_ACTIVE_STATUSES = {"active", "trialing"}


class BillingNotConfigured(RuntimeError):
    """Raised when a Stripe operation is attempted while billing is disabled or
    its secrets / SDK are absent. The API layer maps this to HTTP 503."""


# ---------------------------------------------------------------------------
# Configuration / plan <-> price mapping (pure, no Stripe needed)
# ---------------------------------------------------------------------------
def billing_configured() -> bool:
    """True only when monetization is switched on AND a secret key is present."""
    s = get_settings()
    return bool(s.stripe_enabled and s.stripe_secret_key)


def _price_map() -> dict[str, str]:
    """Plan tier -> configured Stripe Price id. Tiers with a blank price are
    omitted, so they report as not-purchasable rather than half-configured."""
    s = get_settings()
    raw = {
        "PRO": s.stripe_price_pro,
        "MAX": s.stripe_price_max,
        "ENTERPRISE": s.stripe_price_enterprise,
    }
    return {plan: price for plan, price in raw.items() if price}


def purchasable_plans() -> list[str]:
    """Plans a tenant can actually buy: not FREE/FOUNDER, ranked, AND wired to a
    configured Stripe price id. Ordered low tier -> high tier for the UI."""
    priced = _price_map()
    plans = [
        plan
        for plan in PLAN_RANK
        if plan not in _NON_PURCHASABLE and plan in priced
    ]
    return sorted(plans, key=lambda p: PLAN_RANK[p])


def price_id_for_plan(plan: str) -> str | None:
    """Configured Stripe Price id for a plan tier, or None if not purchasable."""
    return _price_map().get(plan.upper())


def plan_for_price_id(price_id: str) -> str | None:
    """Reverse map a Stripe Price id back to its Daena plan tier (None if not
    ours -- e.g. a stale price from a previous catalog)."""
    for plan, configured in _price_map().items():
        if configured == price_id:
            return plan
    return None


# ---------------------------------------------------------------------------
# Stripe SDK access (lazy import)
# ---------------------------------------------------------------------------
def _get_stripe():
    """Import + configure the Stripe SDK on demand.

    Raises BillingNotConfigured if billing is off, the secret key is missing, or
    the package is not installed -- so a missing dependency surfaces as a clean
    503 instead of an ImportError at module load.
    """
    if not billing_configured():
        raise BillingNotConfigured("Billing is not enabled or stripe_secret_key is unset")
    try:
        import stripe  # noqa: PLC0415 -- lazy on purpose; see module docstring
    except ImportError as exc:  # pragma: no cover - exercised only without the SDK
        raise BillingNotConfigured("The 'stripe' package is not installed") from exc
    stripe.api_key = get_settings().stripe_secret_key
    return stripe


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------
def create_checkout_session(
    *,
    plan: str,
    tenant_id: uuid.UUID | str,
    customer_email: str | None = None,
) -> str:
    """Create a Stripe-hosted Checkout Session for `plan` and return its URL.

    Raises:
        BillingNotConfigured: billing off / secrets missing / SDK absent.
        ValueError: `plan` is not a purchasable, priced tier.
    """
    normalized = plan.upper()
    price_id = price_id_for_plan(normalized)
    if normalized in _NON_PURCHASABLE or price_id is None:
        raise ValueError(f"Plan '{plan}' is not purchasable")

    stripe = _get_stripe()
    settings = get_settings()
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.billing_success_url,
        cancel_url=settings.billing_cancel_url,
        client_reference_id=str(tenant_id),
        customer_email=customer_email or None,
        metadata={"tenant_id": str(tenant_id), "plan": normalized},
        subscription_data={"metadata": {"tenant_id": str(tenant_id), "plan": normalized}},
    )
    return session.url


# ---------------------------------------------------------------------------
# Webhook verification
# ---------------------------------------------------------------------------
def verify_webhook_event(payload: bytes, sig_header: str | None) -> dict[str, Any]:
    """Authenticate + parse a Stripe webhook using the signing secret.

    Raises:
        BillingNotConfigured: billing off / SDK absent / no webhook secret set.
        stripe.error.SignatureVerificationError / ValueError: bad signature or
        malformed payload (the API layer maps these to HTTP 400).
    """
    stripe = _get_stripe()
    webhook_secret = get_settings().stripe_webhook_secret
    if not webhook_secret:
        raise BillingNotConfigured("stripe_webhook_secret is unset")
    return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)


# ---------------------------------------------------------------------------
# Subscription writes (the one-ACTIVE-per-tenant invariant lives here)
# ---------------------------------------------------------------------------
def _as_uuid(value: uuid.UUID | str) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _unix_to_dt(ts: int | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(int(ts), tz=timezone.utc)


async def apply_subscription_event(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID | str,
    plan: str,
    status: str = _ACTIVE,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
    current_period_start: datetime | None = None,
    current_period_end: datetime | None = None,
) -> Subscription:
    """Upsert the tenant's subscription, enforcing exactly one ACTIVE row.

    Strategy: load every subscription row for the tenant. Reuse the first as the
    canonical record (update in place); mark any other rows CANCELED so a tenant
    can never end up with two ACTIVE plans. If none exist, insert one. Stripe id
    and period fields are only overwritten when a non-None value is supplied, so
    a later event that omits them does not clobber what an earlier one set. The
    Numeric budget columns are never touched here.
    """
    tid = _as_uuid(tenant_id)
    normalized_plan = plan.upper()

    rows = (
        await db.execute(
            select(Subscription)
            .where(Subscription.tenant_id == tid)
            .order_by(Subscription.created_at.asc())
        )
    ).scalars().all()

    if rows:
        sub = rows[0]
        sub.plan = normalized_plan
        sub.status = status
        if stripe_customer_id is not None:
            sub.stripe_customer_id = stripe_customer_id
        if stripe_subscription_id is not None:
            sub.stripe_subscription_id = stripe_subscription_id
        if current_period_start is not None:
            sub.current_period_start = current_period_start
        if current_period_end is not None:
            sub.current_period_end = current_period_end
        # Collapse any duplicate rows so only the canonical one stays ACTIVE.
        for extra in rows[1:]:
            if extra.status == _ACTIVE:
                extra.status = _CANCELED
    else:
        sub = Subscription(
            tenant_id=tid,
            plan=normalized_plan,
            status=status,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
        )
        db.add(sub)

    await db.commit()
    await db.refresh(sub)
    return sub


def _first_price_id(subscription_obj: dict[str, Any]) -> str | None:
    """Pull the first line-item price id out of a Stripe subscription object."""
    items = (subscription_obj.get("items") or {}).get("data") or []
    if not items:
        return None
    price = items[0].get("price") or {}
    return price.get("id")


def _event_tenant_id(obj: dict[str, Any]) -> str | None:
    """Recover our tenant id from an event object's metadata / client ref."""
    meta = obj.get("metadata") or {}
    return (
        meta.get("tenant_id")
        or obj.get("client_reference_id")
        or None
    )


async def handle_event(db: AsyncSession, event: dict[str, Any]) -> dict[str, Any]:
    """Interpret a verified Stripe event and apply the resulting plan change.

    Handles the three events that move a tenant between plans:
      * checkout.session.completed   -> ACTIVE on the purchased plan
      * customer.subscription.updated-> reverse-map the price id; active/trialing
                                          stays ACTIVE, anything else downgrades
      * customer.subscription.deleted-> downgrade to FREE / CANCELED

    Unknown event types are acknowledged and ignored (return result "ignored")
    so Stripe does not retry them.
    """
    event_type = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}

    if event_type == "checkout.session.completed":
        tenant_id = _event_tenant_id(obj)
        plan = (obj.get("metadata") or {}).get("plan")
        if not tenant_id or not plan:
            return {"handled": False, "reason": "missing_tenant_or_plan"}
        sub = await apply_subscription_event(
            db,
            tenant_id=tenant_id,
            plan=plan,
            status=_ACTIVE,
            stripe_customer_id=obj.get("customer"),
            stripe_subscription_id=obj.get("subscription"),
        )
        return {"handled": True, "plan": sub.plan, "status": sub.status}

    if event_type == "customer.subscription.updated":
        tenant_id = _event_tenant_id(obj)
        price_id = _first_price_id(obj)
        plan = plan_for_price_id(price_id) if price_id else None
        if not tenant_id or not plan:
            return {"handled": False, "reason": "unmapped_price_or_tenant"}
        active = obj.get("status") in _STRIPE_ACTIVE_STATUSES
        sub = await apply_subscription_event(
            db,
            tenant_id=tenant_id,
            plan=plan if active else "FREE",
            status=_ACTIVE if active else _CANCELED,
            stripe_customer_id=obj.get("customer"),
            stripe_subscription_id=obj.get("id"),
            current_period_start=_unix_to_dt(obj.get("current_period_start")),
            current_period_end=_unix_to_dt(obj.get("current_period_end")),
        )
        return {"handled": True, "plan": sub.plan, "status": sub.status}

    if event_type == "customer.subscription.deleted":
        tenant_id = _event_tenant_id(obj)
        if not tenant_id:
            return {"handled": False, "reason": "missing_tenant"}
        sub = await apply_subscription_event(
            db,
            tenant_id=tenant_id,
            plan="FREE",
            status=_CANCELED,
            stripe_customer_id=obj.get("customer"),
            stripe_subscription_id=obj.get("id"),
        )
        return {"handled": True, "plan": sub.plan, "status": sub.status}

    return {"handled": False, "reason": "ignored", "type": event_type}
