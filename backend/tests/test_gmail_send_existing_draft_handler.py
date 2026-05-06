"""Sprint-15 PR-2 -- gmail.send_existing_draft handler contract.

Pins:
  1. The handler is registered after the handlers package is imported.
  2. owner_email is REQUIRED (refuses with owner_email_required).
  3. Missing draft_id refuses with payload_field_missing:draft_id.
  4. No connected Gmail instance refuses with oauth_not_connected:google.
  5. A 404 / failed draft fetch refuses with draft_not_found.
  6. A draft whose From: header doesn't match owner_email refuses with
     draft_owner_email_mismatch -- the lock against draft-substitution
     from another connected account.
  7. Success path returns a safe result that:
      - carries message_id / status="sent" / tool_id / owner_email
      - extracts audit_to + audit_subject from the FETCHED draft headers
      - never includes access_token / refresh_token / draft body
      - calls send_existing_draft, NOT send_email or any other path
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


pytestmark = pytest.mark.asyncio


def _make_request(**overrides):
    from app.services.controlled_execution_design import ControlledExecutionRequest

    base = dict(
        approval_id="00000000-0000-0000-0000-000000000000",
        consent_grant_id="grant-x",
        payload_hash="0" * 64,
        tool_id="gmail.send_existing_draft",
        owner_email="founder@example.com",
        asset_shield_pass=True,
        policy_allowlist_pass=True,
        audit_preflight_row_id="audit-pre",
        audit_result_row_id=None,
        rollback_or_undo_instruction=None,
    )
    base.update(overrides)
    return ControlledExecutionRequest(**base)


def _make_ctx(
    *, request, payload, tenant_id=None, user_id=None,
    approval_params=None,
):
    """Build a HandlerContext with a configurable approval row.

    Sprint-16 PR-2 makes the handler consult
    ``ctx.approval.action_params`` so tests must opt-in to a
    realistic approval row by passing ``approval_params``. When None,
    the approval is a bare MagicMock whose ``action_params`` attr
    returns ``None`` (matching the legacy / missing-snapshot case
    intentionally tested by ``TestSnapshotRequired``).
    """
    import uuid

    from app.services.controlled_execution_dispatch import HandlerContext

    approval = MagicMock()
    approval.action_params = approval_params  # may be None
    return HandlerContext(
        request=request,
        approval=approval,
        payload=payload,
        tenant_id=tenant_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        db=MagicMock(),
    )


def _matching_snapshot_dict(*, owner_email="founder@example.com",
                            to="ops@example.com",
                            from_value="Founder <founder@example.com>",
                            subject="Q3 plan", body_snippet="",
                            draft_id="draft-abc",
                            message_id=None, thread_id=None):
    """Build a draft_snapshot dict that EXACTLY matches what
    build_snapshot_from_gmail_draft would produce from
    _draft_meta(...) -- so first_drift_field returns None and the
    handler proceeds to send.
    """
    return {
        "draft_id": draft_id,
        "owner_email": owner_email,
        "to": to,
        "from_value": from_value,
        "subject": subject,
        "body_snippet": body_snippet,
        "captured_at": "2026-05-06T12:00:00+00:00",
        "message_id": message_id,
        "thread_id": thread_id,
    }


def _approval_with_snapshot(snapshot=None, **snap_overrides):
    """Build an approval action_params dict carrying a snapshot."""
    if snapshot is None:
        snapshot = _matching_snapshot_dict(**snap_overrides)
    return {"draft_snapshot": snapshot}


def _draft_meta(*, from_value: str, to: str = "ops@example.com",
                subject: str = "Q3 plan") -> dict:
    """Build a Gmail draft metadata payload for the mocked client."""
    return {
        "id": "draft-abc",
        "message": {
            "id": "msg-xyz",
            "payload": {
                "headers": [
                    {"name": "From", "value": from_value},
                    {"name": "To", "value": to},
                    {"name": "Subject", "value": subject},
                ],
            },
        },
    }


class TestRegistered:
    async def test_handler_in_registry_after_import(self):
        import app.services.controlled_execution_handlers  # noqa: F401
        from app.services.controlled_execution_dispatch import registered_tool_ids

        assert "gmail.send_existing_draft" in registered_tool_ids()

    async def test_send_tool_in_write_tools(self):
        from app.services.controlled_execution_design import WRITE_TOOLS

        assert "gmail.send_existing_draft" in WRITE_TOOLS


class TestOwnerEmailRequired:
    async def test_missing_owner_email_refused(self):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers.gmail_send_existing_draft import (
            handle_gmail_send_existing_draft,
        )

        req = _make_request(owner_email=None)
        ctx = _make_ctx(request=req, payload={"draft_id": "draft-abc"})
        with pytest.raises(ControlledExecutionRefused) as ei:
            await handle_gmail_send_existing_draft(ctx)
        assert ei.value.code == "owner_email_required"


class TestPayloadValidation:
    @pytest.mark.parametrize("payload", [
        {},
        {"draft_id": ""},
        {"draft_id": "   "},
        {"draft_id": None},
        {"draft_id": 123},
    ])
    async def test_missing_or_invalid_draft_id_refused(self, payload):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers.gmail_send_existing_draft import (
            handle_gmail_send_existing_draft,
        )

        req = _make_request()
        ctx = _make_ctx(request=req, payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await handle_gmail_send_existing_draft(ctx)
        assert ei.value.code == "payload_field_missing:draft_id"


class TestOAuthNotConnected:
    async def test_no_connector_instance_refused(self, monkeypatch):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers import (
            gmail_send_existing_draft as mod,
        )

        async def _fake_load(ctx, *, owner_email):
            raise ControlledExecutionRefused(
                "oauth_not_connected:google",
                f"no instance for {owner_email}",
            )

        monkeypatch.setattr(mod, "_load_gmail_credentials", _fake_load)

        req = _make_request()
        ctx = _make_ctx(request=req, payload={"draft_id": "draft-abc"})
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_gmail_send_existing_draft(ctx)
        assert ei.value.code == "oauth_not_connected:google"


class TestDraftNotFound:
    async def test_404_refused(self, monkeypatch):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers import (
            gmail_send_existing_draft as mod,
        )

        async def _fake_load(ctx, *, owner_email):
            return {"access_token": "tok"}

        fake_response = MagicMock(status_code=404)
        fake_client = MagicMock()
        fake_client.get_draft = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "not found",
                request=MagicMock(),
                response=fake_response,
            ),
        )

        monkeypatch.setattr(mod, "_load_gmail_credentials", _fake_load)
        monkeypatch.setattr(mod, "_build_client", lambda c: fake_client)

        req = _make_request()
        ctx = _make_ctx(request=req, payload={"draft_id": "draft-abc"})
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_gmail_send_existing_draft(ctx)
        assert ei.value.code == "draft_not_found"
        # Paranoid: send_existing_draft must NOT have fired.
        assert not fake_client.send_existing_draft.called

    async def test_arbitrary_exception_during_fetch_refused(self, monkeypatch):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers import (
            gmail_send_existing_draft as mod,
        )

        async def _fake_load(ctx, *, owner_email):
            return {"access_token": "tok"}

        fake_client = MagicMock()
        fake_client.get_draft = AsyncMock(side_effect=RuntimeError("boom"))

        monkeypatch.setattr(mod, "_load_gmail_credentials", _fake_load)
        monkeypatch.setattr(mod, "_build_client", lambda c: fake_client)

        req = _make_request()
        ctx = _make_ctx(request=req, payload={"draft_id": "draft-abc"})
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_gmail_send_existing_draft(ctx)
        assert ei.value.code == "draft_not_found"


class TestDraftOwnerEmailMismatch:
    async def test_other_account_refused(self, monkeypatch):
        """Lock against draft-substitution: a draft whose From: header
        is for a DIFFERENT account on the same connector must not
        send under owner_email = founder."""
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers import (
            gmail_send_existing_draft as mod,
        )

        async def _fake_load(ctx, *, owner_email):
            return {"access_token": "tok"}

        fake_client = MagicMock()
        # The draft is from daena@mas-ai.co but request's owner_email
        # is founder@example.com -- this is the substitution scenario.
        fake_client.get_draft = AsyncMock(return_value=_draft_meta(
            from_value="Daena <daena@mas-ai.co>",
        ))

        monkeypatch.setattr(mod, "_load_gmail_credentials", _fake_load)
        monkeypatch.setattr(mod, "_build_client", lambda c: fake_client)

        req = _make_request()
        # Snapshot present but the From: check fires FIRST (Sprint-15
        # invariant) so this still surfaces draft_owner_email_mismatch
        # before the snapshot wall.
        ctx = _make_ctx(
            request=req,
            payload={"draft_id": "draft-abc"},
            approval_params=_approval_with_snapshot(),
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_gmail_send_existing_draft(ctx)
        assert ei.value.code == "draft_owner_email_mismatch"
        assert not fake_client.send_existing_draft.called

    async def test_empty_from_header_refused(self, monkeypatch):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers import (
            gmail_send_existing_draft as mod,
        )

        async def _fake_load(ctx, *, owner_email):
            return {"access_token": "tok"}

        fake_client = MagicMock()
        fake_client.get_draft = AsyncMock(return_value={
            "id": "draft-abc",
            "message": {"payload": {"headers": []}},
        })

        monkeypatch.setattr(mod, "_load_gmail_credentials", _fake_load)
        monkeypatch.setattr(mod, "_build_client", lambda c: fake_client)

        req = _make_request()
        ctx = _make_ctx(
            request=req,
            payload={"draft_id": "draft-abc"},
            approval_params=_approval_with_snapshot(),
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_gmail_send_existing_draft(ctx)
        assert ei.value.code == "draft_owner_email_mismatch"


class TestSnapshotRequired:
    """Sprint-16 PR-2: send approval MUST carry a draft_snapshot."""

    async def test_no_action_params_refused(self, monkeypatch):
        """When the approval row's action_params is None (legacy /
        Sprint-15-era approval), the handler refuses with
        draft_snapshot_required BEFORE sending."""
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers import (
            gmail_send_existing_draft as mod,
        )

        async def _fake_load(ctx, *, owner_email):
            return {"access_token": "tok"}

        fake_client = MagicMock()
        fake_client.get_draft = AsyncMock(return_value=_draft_meta(
            from_value="Founder <founder@example.com>",
        ))
        monkeypatch.setattr(mod, "_load_gmail_credentials", _fake_load)
        monkeypatch.setattr(mod, "_build_client", lambda c: fake_client)

        req = _make_request()
        ctx = _make_ctx(
            request=req,
            payload={"draft_id": "draft-abc"},
            approval_params=None,  # legacy approval
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_gmail_send_existing_draft(ctx)
        assert ei.value.code == "draft_snapshot_required"
        assert not fake_client.send_existing_draft.called

    async def test_snapshot_not_dict_refused(self, monkeypatch):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers import (
            gmail_send_existing_draft as mod,
        )

        async def _fake_load(ctx, *, owner_email):
            return {"access_token": "tok"}

        fake_client = MagicMock()
        fake_client.get_draft = AsyncMock(return_value=_draft_meta(
            from_value="Founder <founder@example.com>",
        ))
        monkeypatch.setattr(mod, "_load_gmail_credentials", _fake_load)
        monkeypatch.setattr(mod, "_build_client", lambda c: fake_client)

        req = _make_request()
        # action_params is a dict but draft_snapshot is a string,
        # not a dict. The handler refuses cleanly rather than
        # crashing.
        ctx = _make_ctx(
            request=req,
            payload={"draft_id": "draft-abc"},
            approval_params={"draft_snapshot": "not-a-dict"},
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_gmail_send_existing_draft(ctx)
        assert ei.value.code == "draft_snapshot_required"


class TestSnapshotDriftRefusals:
    """Sprint-16 PR-2: every locked snapshot field that drifts must
    refuse with the right stable code."""

    async def test_recipient_drift_refused(self, monkeypatch):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers import (
            gmail_send_existing_draft as mod,
        )

        async def _fake_load(ctx, *, owner_email):
            return {"access_token": "tok"}

        fake_client = MagicMock()
        # Current Gmail draft has been edited: To: was changed.
        fake_client.get_draft = AsyncMock(return_value=_draft_meta(
            from_value="Founder <founder@example.com>",
            to="attacker@evil.com",  # drifted from approved
            subject="Q3 plan",
        ))
        monkeypatch.setattr(mod, "_load_gmail_credentials", _fake_load)
        monkeypatch.setattr(mod, "_build_client", lambda c: fake_client)

        req = _make_request()
        # Approved snapshot says ops@example.com.
        ctx = _make_ctx(
            request=req,
            payload={"draft_id": "draft-abc"},
            approval_params=_approval_with_snapshot(to="ops@example.com"),
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_gmail_send_existing_draft(ctx)
        assert ei.value.code == "draft_recipient_mismatch"
        assert not fake_client.send_existing_draft.called

    async def test_subject_drift_refused(self, monkeypatch):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers import (
            gmail_send_existing_draft as mod,
        )

        async def _fake_load(ctx, *, owner_email):
            return {"access_token": "tok"}

        fake_client = MagicMock()
        fake_client.get_draft = AsyncMock(return_value=_draft_meta(
            from_value="Founder <founder@example.com>",
            to="ops@example.com",
            subject="WIRE $50K NOW",  # drifted from approved
        ))
        monkeypatch.setattr(mod, "_load_gmail_credentials", _fake_load)
        monkeypatch.setattr(mod, "_build_client", lambda c: fake_client)

        req = _make_request()
        ctx = _make_ctx(
            request=req,
            payload={"draft_id": "draft-abc"},
            approval_params=_approval_with_snapshot(subject="Q3 plan"),
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_gmail_send_existing_draft(ctx)
        assert ei.value.code == "draft_subject_mismatch"
        assert not fake_client.send_existing_draft.called

    async def test_message_id_drift_refused(self, monkeypatch):
        """When only message_id drifts, the snapshot helper reports
        message_id, which maps to draft_metadata_hash_mismatch (we
        don't surface message-id-specific refusal -- the operator
        sees 'something changed' and re-approves)."""
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers import (
            gmail_send_existing_draft as mod,
        )

        async def _fake_load(ctx, *, owner_email):
            return {"access_token": "tok"}

        fake_client = MagicMock()
        # Build a draft_meta that includes a different message_id
        meta = _draft_meta(
            from_value="Founder <founder@example.com>",
            to="ops@example.com",
            subject="Q3 plan",
        )
        meta["message"]["id"] = "different-message-id"
        fake_client.get_draft = AsyncMock(return_value=meta)
        monkeypatch.setattr(mod, "_load_gmail_credentials", _fake_load)
        monkeypatch.setattr(mod, "_build_client", lambda c: fake_client)

        req = _make_request()
        ctx = _make_ctx(
            request=req,
            payload={"draft_id": "draft-abc"},
            approval_params=_approval_with_snapshot(message_id="msg-xyz"),
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_gmail_send_existing_draft(ctx)
        assert ei.value.code == "draft_metadata_hash_mismatch"
        assert not fake_client.send_existing_draft.called


class TestSuccessPath:
    async def test_mocked_send_returns_safe_payload(self, monkeypatch):
        from app.services.controlled_execution_handlers import (
            gmail_send_existing_draft as mod,
        )

        async def _fake_load(ctx, *, owner_email):
            return {"access_token": "SECRET-NEVER-LEAK"}

        fake_client = MagicMock()
        # The fetched draft's metadata MUST match the approved
        # snapshot exactly (Sprint-16 PR-2 wall) -- we use the
        # _draft_meta default _AND_ the matching snapshot helper.
        fake_client.get_draft = AsyncMock(return_value=_draft_meta(
            from_value="Founder <founder@example.com>",
            to="ops@example.com",
            subject="Q3 plan",
        ))
        fake_client.send_existing_draft = AsyncMock(return_value={
            "message_id": "msg-sent-123",
            "thread_id": "thr-abc",
            "status": "sent",
        })

        monkeypatch.setattr(mod, "_load_gmail_credentials", _fake_load)
        monkeypatch.setattr(mod, "_build_client", lambda c: fake_client)

        req = _make_request()
        # Build a snapshot that matches the fetched draft byte-for-
        # byte. The _draft_meta helper in this file builds Gmail
        # metadata WITHOUT a message id by default; the snapshot
        # helper mirrors that.
        ctx = _make_ctx(
            request=req,
            payload={"draft_id": "draft-abc"},
            approval_params=_approval_with_snapshot(
                draft_id="draft-abc",
                owner_email="founder@example.com",
                to="ops@example.com",
                from_value="Founder <founder@example.com>",
                subject="Q3 plan",
                body_snippet="",
                # _draft_meta sets message.id = "msg-xyz" by default
                # (see the helper at the top of this file). The
                # approved snapshot must mirror it; otherwise PR-2's
                # snapshot wall would refuse with
                # draft_metadata_hash_mismatch.
                message_id="msg-xyz",
                thread_id=None,
            ),
        )
        result = await mod.handle_gmail_send_existing_draft(ctx)

        assert result["draft_id"] == "draft-abc"
        assert result["message_id"] == "msg-sent-123"
        assert result["status"] == "sent"
        assert result["tool_id"] == "gmail.send_existing_draft"
        assert result["owner_email"] == "founder@example.com"
        assert result["audit_to"] == "ops@example.com"
        assert result["audit_subject"] == "Q3 plan"
        assert isinstance(result["rollback_or_undo_instruction"], str)
        assert len(result["rollback_or_undo_instruction"]) > 0
        # Sprint-16 PR-2: surface BOTH hashes for the audit row.
        assert isinstance(result["approved_snapshot_hash"], str)
        assert len(result["approved_snapshot_hash"]) == 64
        assert isinstance(result["verified_snapshot_hash"], str)
        assert len(result["verified_snapshot_hash"]) == 64
        # Hashes match because the fetched draft and the approved
        # snapshot agree (the dispatch wouldn't have proceeded
        # otherwise).
        assert result["approved_snapshot_hash"] == result["verified_snapshot_hash"]

        # Paranoid: walk every value and assert no secret string.
        def _walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    assert "access_token" not in str(k).lower()
                    assert "refresh_token" not in str(k).lower()
                    _walk(v)
            elif isinstance(o, list):
                for x in o:
                    _walk(x)
            elif isinstance(o, str):
                assert "SECRET-NEVER-LEAK" not in o, (
                    "handler leaked the access_token in the result!"
                )

        _walk(result)

        # Send was called exactly once with the draft_id.
        fake_client.send_existing_draft.assert_awaited_once_with("draft-abc")
        # send_email (the BROAD verb) must NOT have been called.
        assert not fake_client.send_email.called
