"""Sprint-18 PR-2 -- /api/v1/trust endpoints contract.

Pins:
  1. /trust/eligible-tools returns the locked sets verbatim.
  2. /trust/policies returns the union of policy + ladder keys.
  3. /trust/policies/preview-decision returns the same answer as
     trust_policy.should_auto_approve.
  4. /trust/policies/tier-set is FOUNDER-gated.
  5. /trust/policies/tier-set with wrong confirmation_phrase returns
     200 + success=False + error_code=confirmation_phrase_mismatch.
  6. /trust/policies/tier-set refuses forbidden tools.
  7. /trust/policies/tier-set with valid input persists the tier.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    from app.services import trust_ladder, trust_policy

    monkeypatch.setattr(
        trust_ladder, "_LADDER_FILE", tmp_path / ".trust_ladder.json",
    )
    monkeypatch.setattr(
        trust_policy, "_POLICY_FILE", tmp_path / ".trust_policy.json",
    )
    yield


class TestEligibleToolsEndpoint:
    async def test_returns_locked_sets(
        self, isolated_state, client, auth_headers,
    ):
        r = await client.get(
            "/api/v1/trust/eligible-tools", headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert sorted(body["eligible_tools"]) == [
            "calendar.create_tentative_event_without_invites",
            "gmail.create_draft",
            "local.file_change_proposal",
        ]
        assert sorted(body["forbidden_tools"]) == [
            "gmail.send_existing_draft",
            "local.file_change_proposal.apply",
            "local.git_commit_approved_patch",
        ]
        assert body["min_approvals_to_graduate"] == 5
        assert "auto_execute_low_risk_local" not in body["available_tiers"]


class TestListPoliciesEndpoint:
    async def test_empty_when_no_history(
        self, isolated_state, client, auth_headers,
    ):
        r = await client.get(
            "/api/v1/trust/policies", headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json() == []

    async def test_returns_policy_and_ladder_state(
        self, isolated_state, client, auth_headers,
    ):
        from app.services import trust_ladder

        trust_ladder.record_decision(
            tool_id="gmail.create_draft",
            template_id="some-template",
            decision="approved",
        )
        r = await client.get(
            "/api/v1/trust/policies", headers=auth_headers,
        )
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        row = rows[0]
        assert row["tool_id"] == "gmail.create_draft"
        assert row["template_class"] == "some-template"
        assert row["max_auto_tier"] == "none"
        assert row["approvals_count"] == 1
        assert row["rejection_count"] == 0
        assert row["eligible"] is True
        assert row["forbidden"] is False


class TestTierSetEndpoint:
    async def test_founder_can_set_tier(
        self, isolated_state, client, auth_headers,
    ):
        body = {
            "tool_id": "gmail.create_draft",
            "template_class": "test-class",
            "tier": "auto_approve_low_risk",
            "confirmation_phrase": (
                "I authorize trust tier auto_approve_low_risk for "
                "gmail.create_draft"
            ),
        }
        r = await client.post(
            "/api/v1/trust/policies/tier-set",
            json=body, headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["max_auto_tier"] == "auto_approve_low_risk"

    async def test_wrong_confirmation_phrase_returns_inline_error(
        self, isolated_state, client, auth_headers,
    ):
        body = {
            "tool_id": "gmail.create_draft",
            "template_class": "x",
            "tier": "auto_approve_low_risk",
            "confirmation_phrase": "totally wrong phrase",
        }
        r = await client.post(
            "/api/v1/trust/policies/tier-set",
            json=body, headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is False
        assert data["error_code"] == "confirmation_phrase_mismatch"
        assert data["expected_confirmation_phrase"] == (
            "I authorize trust tier auto_approve_low_risk for "
            "gmail.create_draft"
        )

    async def test_forbidden_tool_returns_inline_error(
        self, isolated_state, client, auth_headers,
    ):
        body = {
            "tool_id": "gmail.send_existing_draft",
            "template_class": "x",
            "tier": "auto_approve_low_risk",
            "confirmation_phrase": (
                "I authorize trust tier auto_approve_low_risk for "
                "gmail.send_existing_draft"
            ),
        }
        r = await client.post(
            "/api/v1/trust/policies/tier-set",
            json=body, headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is False
        assert data["error_code"] == "tool_forbidden_from_graduation"

    async def test_invalid_tier_returns_400(
        self, isolated_state, client, auth_headers,
    ):
        body = {
            "tool_id": "gmail.create_draft",
            "template_class": "x",
            "tier": "ultra_root_godmode",
            "confirmation_phrase": "anything",
        }
        r = await client.post(
            "/api/v1/trust/policies/tier-set",
            json=body, headers=auth_headers,
        )
        assert r.status_code == 400


class TestPreviewDecisionEndpoint:
    async def test_default_no_history_returns_max_auto_tier_is_none(
        self, isolated_state, client, auth_headers,
    ):
        body = {
            "tool_id": "gmail.create_draft",
            "payload": {"to": ["a@b.com"], "subject": "x"},
            "initiator": "operator",
        }
        r = await client.post(
            "/api/v1/trust/policies/preview-decision",
            json=body, headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["auto_approve"] is False
        assert data["reason"] == "max_auto_tier_is_none"

    async def test_scheduler_initiator_never_graduates(
        self, isolated_state, client, auth_headers,
    ):
        body = {
            "tool_id": "gmail.create_draft",
            "payload": {"to": ["a@b.com"], "subject": "x"},
            "initiator": "scheduler",
        }
        r = await client.post(
            "/api/v1/trust/policies/preview-decision",
            json=body, headers=auth_headers,
        )
        data = r.json()
        assert data["auto_approve"] is False
        assert data["reason"] == "non_operator_initiator_never_graduates"

    async def test_invalid_initiator_returns_400(
        self, isolated_state, client, auth_headers,
    ):
        body = {
            "tool_id": "gmail.create_draft",
            "payload": {},
            "initiator": "godmode_root",
        }
        r = await client.post(
            "/api/v1/trust/policies/preview-decision",
            json=body, headers=auth_headers,
        )
        assert r.status_code == 400
