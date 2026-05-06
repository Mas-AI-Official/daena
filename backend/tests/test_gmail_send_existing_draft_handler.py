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


def _make_ctx(*, request, payload, tenant_id=None, user_id=None):
    import uuid

    from app.services.controlled_execution_dispatch import HandlerContext

    return HandlerContext(
        request=request,
        approval=MagicMock(),
        payload=payload,
        tenant_id=tenant_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        db=MagicMock(),
    )


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
        ctx = _make_ctx(request=req, payload={"draft_id": "draft-abc"})
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
        ctx = _make_ctx(request=req, payload={"draft_id": "draft-abc"})
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_gmail_send_existing_draft(ctx)
        assert ei.value.code == "draft_owner_email_mismatch"


class TestSuccessPath:
    async def test_mocked_send_returns_safe_payload(self, monkeypatch):
        from app.services.controlled_execution_handlers import (
            gmail_send_existing_draft as mod,
        )

        async def _fake_load(ctx, *, owner_email):
            return {"access_token": "SECRET-NEVER-LEAK"}

        fake_client = MagicMock()
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
        ctx = _make_ctx(request=req, payload={"draft_id": "draft-abc"})
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
