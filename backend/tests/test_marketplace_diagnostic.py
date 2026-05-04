"""PR-CONN-CALLABILITY-DIAGNOSTIC-PANEL (Sprint-6 PR-2, 2026-05-04) tests.

Pins the contract for the diagnostic surface that explains "0 of N callable":

  1. Pure classifier maps each lifecycle/kind combo to the right blocker
     reason (or None if the card is callable).
  2. ``build_diagnostic_summary`` rolls up cards into stable totals + a
     ranked top_blockers list, with bounded examples.
  3. The HTTP endpoint requires auth, returns the totals + blockers, and
     never leaks token / secret / config substrings.
  4. The fully-empty-tenant baseline (no V2 rows seeded) yields the
     expected "not_imported / coming_soon / needs_oauth / needs_api_key"
     mix that the operator sees on first boot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.models.identity import Tenant
from app.services.connection_v2.marketplace_service import (
    BLOCKER_REASON_ARCHIVED,
    BLOCKER_REASON_COMING_SOON,
    BLOCKER_REASON_DISABLED,
    BLOCKER_REASON_NEEDS_API_KEY,
    BLOCKER_REASON_NEEDS_OAUTH,
    BLOCKER_REASON_NEEDS_PROBE,
    BLOCKER_REASON_NOT_IMPORTED,
    BLOCKER_REASON_PROBE_FAILED,
    BLOCKER_REASON_SKILL_PACK,
    MarketplaceCard,
    MarketplaceService,
    _classify_card_blocker,
    build_diagnostic_summary,
)


pytestmark = pytest.mark.asyncio


# ──────────────────────────────────────────────────────────────────
# Helpers (build a synthetic MarketplaceCard quickly)
# ──────────────────────────────────────────────────────────────────


def _card(
    *,
    entry_id: str = "dummy",
    display_name: str = "Dummy",
    kind: str = "mcp_server",
    install_method: str = "npm",
    lifecycle: str = "available",
    has_v2_row: bool = False,
    provider_key_present: bool | None = None,
    truth: dict | None = None,
) -> MarketplaceCard:
    catalog = {
        "id": entry_id,
        "display_name": display_name,
        "kind": kind,
        "install_method": install_method,
    }
    card = MarketplaceCard(catalog=catalog)
    card.lifecycle = lifecycle
    card.provider_key_present = provider_key_present
    if has_v2_row:
        card.v2_row_id = "00000000-0000-0000-0000-000000000001"
        card.v2_truth = truth or {}
    return card


# ──────────────────────────────────────────────────────────────────
# 1. Classifier
# ──────────────────────────────────────────────────────────────────


class TestClassifier:
    async def test_callable_card_has_no_blocker(self):
        c = _card(lifecycle="callable", has_v2_row=True)
        assert _classify_card_blocker(c) is None

    async def test_enabled_card_has_no_blocker(self):
        c = _card(lifecycle="enabled", has_v2_row=True)
        assert _classify_card_blocker(c) is None

    async def test_failed_lifecycle_maps_to_probe_failed(self):
        c = _card(lifecycle="failed", has_v2_row=True)
        assert _classify_card_blocker(c) == BLOCKER_REASON_PROBE_FAILED

    async def test_archived_lifecycle_maps_to_archived(self):
        c = _card(lifecycle="archived", has_v2_row=True)
        assert _classify_card_blocker(c) == BLOCKER_REASON_ARCHIVED

    async def test_disabled_lifecycle_maps_to_disabled(self):
        c = _card(lifecycle="disabled", has_v2_row=True)
        assert _classify_card_blocker(c) == BLOCKER_REASON_DISABLED

    async def test_skill_pack_lifecycle_maps_to_skill_pack(self):
        c = _card(lifecycle="skill_pack", has_v2_row=True, kind="skill_pack")
        assert _classify_card_blocker(c) == BLOCKER_REASON_SKILL_PACK

    async def test_coming_soon_no_v2_row_maps_to_coming_soon(self):
        c = _card(install_method="coming-soon", lifecycle="needs_setup")
        assert _classify_card_blocker(c) == BLOCKER_REASON_COMING_SOON

    async def test_api_provider_missing_key_maps_to_needs_api_key(self):
        c = _card(
            kind="api_provider",
            lifecycle="available",
            provider_key_present=False,
        )
        assert _classify_card_blocker(c) == BLOCKER_REASON_NEEDS_API_KEY

    async def test_oauth_app_no_v2_row_maps_to_needs_oauth(self):
        c = _card(kind="oauth_app", lifecycle="available")
        assert _classify_card_blocker(c) == BLOCKER_REASON_NEEDS_OAUTH

    async def test_oauth_app_unauthenticated_maps_to_needs_oauth(self):
        c = _card(
            kind="oauth_app",
            lifecycle="configured",
            has_v2_row=True,
            truth={"authenticated": {"value": False}},
        )
        assert _classify_card_blocker(c) == BLOCKER_REASON_NEEDS_OAUTH

    async def test_configured_mcp_maps_to_needs_probe(self):
        c = _card(
            kind="mcp_server",
            lifecycle="configured",
            has_v2_row=True,
        )
        assert _classify_card_blocker(c) == BLOCKER_REASON_NEEDS_PROBE

    async def test_available_no_v2_row_maps_to_not_imported(self):
        c = _card(kind="mcp_server", lifecycle="available")
        assert _classify_card_blocker(c) == BLOCKER_REASON_NOT_IMPORTED


# ──────────────────────────────────────────────────────────────────
# 2. Aggregator
# ──────────────────────────────────────────────────────────────────


class TestAggregator:
    async def test_empty_card_list_yields_zero_totals(self):
        out = build_diagnostic_summary([])
        assert out["totals"]["catalog"] == 0
        assert out["totals"]["callable"] == 0
        assert out["totals"]["blocked"] == 0
        assert out["top_blockers"] == []

    async def test_totals_sum_correctly(self):
        cards = [
            _card(lifecycle="callable", has_v2_row=True),
            _card(lifecycle="callable", has_v2_row=True),
            _card(lifecycle="failed", has_v2_row=True),
            _card(lifecycle="skill_pack", has_v2_row=True, kind="skill_pack"),
            _card(install_method="coming-soon", lifecycle="needs_setup"),
            _card(lifecycle="available"),
            _card(lifecycle="available"),
        ]
        out = build_diagnostic_summary(cards)
        assert out["totals"]["catalog"] == 7
        assert out["totals"]["callable"] == 2
        assert out["totals"]["failed"] == 1
        assert out["totals"]["skill_packs"] == 1
        assert out["totals"]["coming_soon"] == 1
        assert out["totals"]["available"] == 2
        assert out["totals"]["blocked"] == 5

    async def test_top_blockers_ordered_by_count_desc(self):
        cards = [
            _card(entry_id=f"app-{i}", kind="oauth_app", lifecycle="available")
            for i in range(5)
        ] + [
            _card(entry_id="x1", install_method="coming-soon", lifecycle="needs_setup"),
        ]
        out = build_diagnostic_summary(cards)
        assert out["top_blockers"][0]["reason"] == BLOCKER_REASON_NEEDS_OAUTH
        assert out["top_blockers"][0]["count"] == 5
        # second is coming_soon with count 1
        assert any(
            b["reason"] == BLOCKER_REASON_COMING_SOON and b["count"] == 1
            for b in out["top_blockers"]
        )

    async def test_examples_capped_to_three_per_blocker(self):
        cards = [
            _card(
                entry_id=f"e-{i}", display_name=f"E{i}",
                kind="oauth_app", lifecycle="available",
            )
            for i in range(8)
        ]
        out = build_diagnostic_summary(cards)
        oauth = next(
            b for b in out["top_blockers"]
            if b["reason"] == BLOCKER_REASON_NEEDS_OAUTH
        )
        assert oauth["count"] == 8
        assert len(oauth["examples"]) == 3
        # Examples carry only entry_id + display_name, no other fields
        for ex in oauth["examples"]:
            assert set(ex.keys()) == {"entry_id", "display_name"}

    async def test_blocker_payload_carries_no_secret_substring(self):
        cards = [
            _card(
                entry_id="provider-anthropic",
                kind="api_provider",
                lifecycle="available",
                provider_key_present=False,
            ),
        ]
        out = build_diagnostic_summary(cards)
        import json as _json
        raw = _json.dumps(out)
        for forbidden in (
            "access_token", "refresh_token", "Bearer",
            "client_secret", "vault", "credentials", "sk-", "sk_",
        ):
            assert forbidden not in raw, (
                f"diagnostic payload leaked '{forbidden}'"
            )


# ──────────────────────────────────────────────────────────────────
# 3. HTTP endpoint
# ──────────────────────────────────────────────────────────────────


async def _seed_user(db_session, tenant_id, user_id):
    from sqlalchemy import select
    from app.models.identity import Tenant, User
    if (
        await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none() is None:
        db_session.add(Tenant(
            id=tenant_id, name="T", slug="t-diag", settings={},
        ))
        await db_session.flush()
    if (
        await db_session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none() is None:
        db_session.add(User(
            id=user_id, tenant_id=tenant_id,
            email="founder@test.local", role="FOUNDER",
        ))
        await db_session.flush()
    await db_session.commit()


class TestHTTPEndpoint:
    async def test_endpoint_requires_auth(self, client):
        res = await client.get(
            "/api/v1/connections/v2/marketplace/diagnostic",
        )
        assert res.status_code in (401, 403)

    async def test_endpoint_returns_totals_and_blockers(
        self, client, auth_headers, db_session, test_tenant_id, test_user_id,
    ):
        await _seed_user(db_session, test_tenant_id, test_user_id)
        res = await client.get(
            "/api/v1/connections/v2/marketplace/diagnostic",
            headers=auth_headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        data = body["data"]
        # Totals shape
        for key in (
            "catalog", "callable", "configured", "failed",
            "skill_packs", "coming_soon", "available", "blocked",
        ):
            assert key in data["totals"], f"totals missing {key}"
        # Brand-new tenant: catalog > 0, callable should be 0
        assert data["totals"]["catalog"] > 0
        assert data["totals"]["callable"] == 0
        # blocked = catalog - callable
        assert data["totals"]["blocked"] == (
            data["totals"]["catalog"] - data["totals"]["callable"]
        )
        # At least one blocker bucket
        assert len(data["top_blockers"]) >= 1
        for blocker in data["top_blockers"]:
            assert set(blocker.keys()) == {
                "reason", "label", "next_action", "count", "examples",
            }
            assert blocker["count"] > 0
            assert len(blocker["examples"]) <= 3

    async def test_endpoint_payload_carries_no_secret_substring(
        self, client, auth_headers, db_session, test_tenant_id, test_user_id,
    ):
        await _seed_user(db_session, test_tenant_id, test_user_id)
        res = await client.get(
            "/api/v1/connections/v2/marketplace/diagnostic",
            headers=auth_headers,
        )
        raw = res.text
        for forbidden in (
            "access_token", "refresh_token", "Bearer",
            "client_secret", "vault", "credentials",
        ):
            assert forbidden not in raw, (
                f"diagnostic payload leaked '{forbidden}'"
            )
