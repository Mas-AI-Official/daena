"""Sprint-17 PR-6 -- Gmail send full controlled-dispatch integration.

Sprint-16 PR-4 (live drill) proves the GmailClient HTTP path
against real Google. The MOCKED unit tests prove each handler
gate refuses correctly. What's missing was an integration test
that exercises the FULL dispatch spine end-to-end with:

  * a real DB (sqlite + aiosqlite)
  * a seeded GoaRequest in approved state
  * a seeded ConnectorInstance with credentials
  * a draft_snapshot in action_params
  * autonomy mode = approved_execution
  * mocked Gmail HTTP (no external calls)

This test plugs the gap. It does NOT hit Google. It DOES exercise
all six dispatch gates + the Sprint-16 snapshot wall + the result
shape that PR-5 of Sprint-16 polished into the audit viewer.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest


pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────────────


async def _seed_minimal_tenant_user(db_session, tenant_id, user_id):
    """Insert just enough Tenant + User rows for FK-enforced tests."""
    from app.models.identity import Tenant, User

    tenant = Tenant(
        id=tenant_id,
        name="Sprint-17 Test Tenant",
        slug="sprint17-test",
    )
    db_session.add(tenant)
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="founder@example.com",
        password_hash="$argon2id$test$placeholder",
        display_name="Founder",
        role="FOUNDER",
    )
    db_session.add(user)
    await db_session.flush()


async def _seed_gmail_connector_and_instance(
    db_session, *, tenant_id, user_id, owner_email, access_token,
):
    from app.models.connections import Connector, ConnectorInstance

    connector = Connector(
        id=uuid.uuid4(),
        name="Gmail",
        description="Gmail integration",
        category="email",
        auth_type="oauth2",
    )
    db_session.add(connector)
    await db_session.flush()

    instance = ConnectorInstance(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        connector_id=connector.id,
        owner_email=owner_email,
        status="CONNECTED",
        credentials={"access_token": access_token},
    )
    db_session.add(instance)
    await db_session.flush()
    return connector, instance


async def _seed_send_approval(
    db_session, *,
    tenant_id, user_id, payload, payload_hash, owner_email,
    draft_snapshot, expires_in_seconds=3600,
    action_type="gmail.send_existing_draft",
    status="approved",
):
    """Insert a GoaRequest carrying the approved Sprint-16 send shape."""
    from app.models.governance import GoaRequest

    req_id = uuid.uuid4()
    expires = datetime.now(UTC) + timedelta(seconds=expires_in_seconds)
    row = GoaRequest(
        id=req_id,
        tenant_id=tenant_id,
        user_id=user_id,
        action_type=action_type,
        action_params={
            "owner_email": owner_email,
            "payload": payload,
            "payload_hash": payload_hash,
            "draft_snapshot": draft_snapshot,
        },
        risk_level="MEDIUM",
        governance_tier=2,
        status=status,
        expires_at=expires,
    )
    db_session.add(row)
    await db_session.flush()
    return row


def _build_request(
    *, approval_id, payload_hash, owner_email,
    rollback="Email cannot be unsent.",
):
    from app.services.controlled_execution_design import ControlledExecutionRequest
    return ControlledExecutionRequest(
        approval_id=str(approval_id),
        consent_grant_id="grant-x",
        payload_hash=payload_hash,
        tool_id="gmail.send_existing_draft",
        owner_email=owner_email,
        asset_shield_pass=True,
        policy_allowlist_pass=True,
        audit_preflight_row_id="audit-pre",
        audit_result_row_id=None,
        rollback_or_undo_instruction=rollback,
    )


def _matching_snapshot(*, draft_id, owner_email):
    return {
        "draft_id": draft_id,
        "owner_email": owner_email,
        "to": "ops@example.com",
        "from_value": "Founder <founder@example.com>",
        "subject": "Q3 plan",
        "body_snippet": "",
        "captured_at": "2026-05-06T12:00:00+00:00",
        "message_id": "msg-xyz",
        "thread_id": None,
    }


def _gmail_get_draft_response(*, draft_id):
    return {
        "id": draft_id,
        "message": {
            "id": "msg-xyz",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Founder <founder@example.com>"},
                    {"name": "To", "value": "ops@example.com"},
                    {"name": "Subject", "value": "Q3 plan"},
                ],
            },
        },
    }


# ── Tests ────────────────────────────────────────────────────────────


class TestFullDispatchHappyPath:
    async def test_approved_send_dispatches_to_handler(
        self, db_session, test_tenant_id, test_user_id, monkeypatch,
    ):
        """End-to-end: real DB, seeded approval + connector + draft
        snapshot, autonomy mode flipped, mocked Gmail HTTP. Assert
        the handler actually got invoked and the success result
        carries the message_id from the mocked send."""
        from app.services.controlled_execution_dispatch import (
            compute_payload_hash,
            dispatch_controlled_execution,
        )
        from app.services.controlled_execution_handlers import (
            gmail_send_existing_draft as send_mod,
        )
        from app.api.v1 import autonomy_mode as auto_mod

        await _seed_minimal_tenant_user(db_session, test_tenant_id, test_user_id)
        await _seed_gmail_connector_and_instance(
            db_session,
            tenant_id=test_tenant_id, user_id=test_user_id,
            owner_email="founder@example.com",
            access_token="ya29.fake-token",
        )

        # Build payload + hash
        owner_email = "founder@example.com"
        draft_id = "draft-abc"
        payload = {"draft_id": draft_id, "owner_email": owner_email}
        payload_hash = compute_payload_hash(payload)
        snapshot = _matching_snapshot(draft_id=draft_id, owner_email=owner_email)

        approval = await _seed_send_approval(
            db_session,
            tenant_id=test_tenant_id, user_id=test_user_id,
            payload=payload, payload_hash=payload_hash,
            owner_email=owner_email, draft_snapshot=snapshot,
        )

        # Flip autonomy mode to approved_execution
        monkeypatch.setattr(
            auto_mod, "_current_mode",
            lambda: (auto_mod.AutonomyMode.APPROVED_EXECUTION, {}),
        )

        # Mock GmailClient
        fake_client = MagicMock()
        fake_client.get_draft = AsyncMock(
            return_value=_gmail_get_draft_response(draft_id=draft_id),
        )
        fake_client.send_existing_draft = AsyncMock(return_value={
            "message_id": "msg-sent-XYZ",
            "thread_id": "thr-1",
            "status": "sent",
        })
        monkeypatch.setattr(
            send_mod, "_build_client", lambda creds: fake_client,
        )

        request = _build_request(
            approval_id=approval.id, payload_hash=payload_hash,
            owner_email=owner_email,
        )
        result = await dispatch_controlled_execution(
            db_session,
            request=request, payload=payload,
            tenant_id=test_tenant_id, user_id=test_user_id,
        )

        assert result["status"] == "sent"
        assert result["message_id"] == "msg-sent-XYZ"
        assert result["tool_id"] == "gmail.send_existing_draft"
        # Sprint-16 PR-5: BOTH snapshot hashes surfaced
        assert isinstance(result["approved_snapshot_hash"], str)
        assert len(result["approved_snapshot_hash"]) == 64
        assert result["approved_snapshot_hash"] == result["verified_snapshot_hash"]
        # The handler called BOTH get_draft and send_existing_draft
        fake_client.get_draft.assert_awaited_once_with(draft_id)
        fake_client.send_existing_draft.assert_awaited_once_with(draft_id)


class TestGateRefusals:
    async def test_autonomy_mode_off_refuses(
        self, db_session, test_tenant_id, test_user_id, monkeypatch,
    ):
        """Gate 1: autonomy mode != approved_execution refuses."""
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
            compute_payload_hash,
            dispatch_controlled_execution,
        )
        from app.api.v1 import autonomy_mode as auto_mod

        await _seed_minimal_tenant_user(db_session, test_tenant_id, test_user_id)

        payload = {"draft_id": "x", "owner_email": "founder@example.com"}
        payload_hash = compute_payload_hash(payload)

        # Mode is RESEARCH_DRAFT (default), not APPROVED_EXECUTION
        monkeypatch.setattr(
            auto_mod, "_current_mode",
            lambda: (auto_mod.AutonomyMode.RESEARCH_DRAFT, {}),
        )

        request = _build_request(
            approval_id=uuid.uuid4(), payload_hash=payload_hash,
            owner_email="founder@example.com",
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await dispatch_controlled_execution(
                db_session, request=request, payload=payload,
                tenant_id=test_tenant_id, user_id=test_user_id,
            )
        assert ei.value.code == "autonomy_mode_does_not_allow_dispatch"

    async def test_payload_hash_mismatch_refuses(
        self, db_session, test_tenant_id, test_user_id, monkeypatch,
    ):
        """Gate 3: recomputed hash != request's payload_hash refuses."""
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
            compute_payload_hash,
            dispatch_controlled_execution,
        )
        from app.api.v1 import autonomy_mode as auto_mod

        await _seed_minimal_tenant_user(db_session, test_tenant_id, test_user_id)

        payload = {"draft_id": "x", "owner_email": "founder@example.com"}
        actual_hash = compute_payload_hash(payload)
        wrong_hash = "f" * 64  # not the actual hash

        monkeypatch.setattr(
            auto_mod, "_current_mode",
            lambda: (auto_mod.AutonomyMode.APPROVED_EXECUTION, {}),
        )

        request = _build_request(
            approval_id=uuid.uuid4(), payload_hash=wrong_hash,
            owner_email="founder@example.com",
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await dispatch_controlled_execution(
                db_session, request=request, payload=payload,
                tenant_id=test_tenant_id, user_id=test_user_id,
            )
        assert ei.value.code == "payload_hash_mismatch"

    async def test_expired_approval_refuses(
        self, db_session, test_tenant_id, test_user_id, monkeypatch,
    ):
        """Gate 4: approval.expires_at in the past refuses."""
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
            compute_payload_hash,
            dispatch_controlled_execution,
        )
        from app.api.v1 import autonomy_mode as auto_mod

        await _seed_minimal_tenant_user(db_session, test_tenant_id, test_user_id)

        payload = {"draft_id": "x", "owner_email": "founder@example.com"}
        payload_hash = compute_payload_hash(payload)

        approval = await _seed_send_approval(
            db_session, tenant_id=test_tenant_id, user_id=test_user_id,
            payload=payload, payload_hash=payload_hash,
            owner_email="founder@example.com",
            draft_snapshot=_matching_snapshot(
                draft_id="x", owner_email="founder@example.com",
            ),
            expires_in_seconds=-3600,  # expired an hour ago
        )

        monkeypatch.setattr(
            auto_mod, "_current_mode",
            lambda: (auto_mod.AutonomyMode.APPROVED_EXECUTION, {}),
        )

        request = _build_request(
            approval_id=approval.id, payload_hash=payload_hash,
            owner_email="founder@example.com",
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await dispatch_controlled_execution(
                db_session, request=request, payload=payload,
                tenant_id=test_tenant_id, user_id=test_user_id,
            )
        assert ei.value.code == "approval_expired"

    async def test_wrong_action_type_refuses(
        self, db_session, test_tenant_id, test_user_id, monkeypatch,
    ):
        """Gate 4: approval.action_type != request.tool_id refuses.
        Sprint-15 invariant: a create-draft approval cannot
        authorize a send."""
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
            compute_payload_hash,
            dispatch_controlled_execution,
        )
        from app.api.v1 import autonomy_mode as auto_mod

        await _seed_minimal_tenant_user(db_session, test_tenant_id, test_user_id)

        payload = {"draft_id": "x", "owner_email": "founder@example.com"}
        payload_hash = compute_payload_hash(payload)
        approval = await _seed_send_approval(
            db_session, tenant_id=test_tenant_id, user_id=test_user_id,
            payload=payload, payload_hash=payload_hash,
            owner_email="founder@example.com",
            draft_snapshot=_matching_snapshot(
                draft_id="x", owner_email="founder@example.com",
            ),
            action_type="gmail.create_draft",  # wrong tool!
        )

        monkeypatch.setattr(
            auto_mod, "_current_mode",
            lambda: (auto_mod.AutonomyMode.APPROVED_EXECUTION, {}),
        )

        request = _build_request(
            approval_id=approval.id, payload_hash=payload_hash,
            owner_email="founder@example.com",
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await dispatch_controlled_execution(
                db_session, request=request, payload=payload,
                tenant_id=test_tenant_id, user_id=test_user_id,
            )
        assert ei.value.code == "approval_tool_id_mismatch"

    async def test_snapshot_drift_refuses(
        self, db_session, test_tenant_id, test_user_id, monkeypatch,
    ):
        """Sprint-16 PR-2 wall: snapshot recipient drifts -> refuse
        with draft_recipient_mismatch even though all 5 dispatch
        gates passed."""
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
            compute_payload_hash,
            dispatch_controlled_execution,
        )
        from app.services.controlled_execution_handlers import (
            gmail_send_existing_draft as send_mod,
        )
        from app.api.v1 import autonomy_mode as auto_mod

        await _seed_minimal_tenant_user(db_session, test_tenant_id, test_user_id)
        await _seed_gmail_connector_and_instance(
            db_session,
            tenant_id=test_tenant_id, user_id=test_user_id,
            owner_email="founder@example.com",
            access_token="ya29.fake",
        )

        owner_email = "founder@example.com"
        draft_id = "draft-abc"
        payload = {"draft_id": draft_id, "owner_email": owner_email}
        payload_hash = compute_payload_hash(payload)

        # Approved snapshot says To: ops@example.com
        approved_snapshot = _matching_snapshot(
            draft_id=draft_id, owner_email=owner_email,
        )
        # Current draft has been edited: To: attacker@evil.com
        current_draft = _gmail_get_draft_response(draft_id=draft_id)
        current_draft["message"]["payload"]["headers"] = [
            {"name": "From", "value": "Founder <founder@example.com>"},
            {"name": "To", "value": "attacker@evil.com"},
            {"name": "Subject", "value": "Q3 plan"},
        ]

        approval = await _seed_send_approval(
            db_session, tenant_id=test_tenant_id, user_id=test_user_id,
            payload=payload, payload_hash=payload_hash,
            owner_email=owner_email, draft_snapshot=approved_snapshot,
        )

        monkeypatch.setattr(
            auto_mod, "_current_mode",
            lambda: (auto_mod.AutonomyMode.APPROVED_EXECUTION, {}),
        )

        fake_client = MagicMock()
        fake_client.get_draft = AsyncMock(return_value=current_draft)
        # send_existing_draft must NEVER be called
        monkeypatch.setattr(
            send_mod, "_build_client", lambda creds: fake_client,
        )

        request = _build_request(
            approval_id=approval.id, payload_hash=payload_hash,
            owner_email=owner_email,
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await dispatch_controlled_execution(
                db_session, request=request, payload=payload,
                tenant_id=test_tenant_id, user_id=test_user_id,
            )
        assert ei.value.code == "draft_recipient_mismatch"
        # The send must NEVER have fired.
        assert not fake_client.send_existing_draft.called
