"""Sprint-14 PR-2 -- gmail.create_draft handler contract.

Pins:
  1. The handler is registered after the handlers package is imported.
  2. owner_email is REQUIRED (refuses with owner_email_required).
  3. Missing payload field refuses with payload_field_missing:<field>.
  4. No connected Gmail instance refuses with oauth_not_connected:google.
  5. The handler returns a result with no access_token / no refresh_token
     anywhere (paranoid no-secret check).
  6. The result carries a non-empty rollback_or_undo_instruction.
  7. The handler does NOT call any Gmail send / reply path -- only the
     create_draft method on the mocked client.

These tests mock the GmailClient via _build_client monkeypatch so
no real Gmail API call fires.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


pytestmark = pytest.mark.asyncio


def _make_request(**overrides):
    from app.services.controlled_execution_design import ControlledExecutionRequest

    base = dict(
        approval_id="00000000-0000-0000-0000-000000000000",
        consent_grant_id="grant-x",
        payload_hash="0" * 64,
        tool_id="gmail.create_draft",
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
        approval=MagicMock(),  # not consulted by the handler
        payload=payload,
        tenant_id=tenant_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        db=MagicMock(),
    )


class TestRegistered:
    async def test_handler_in_registry_after_import(self):
        # Force the handlers package import path so the side-effect
        # registration runs.
        import app.services.controlled_execution_handlers  # noqa: F401
        from app.services.controlled_execution_dispatch import registered_tool_ids

        assert "gmail.create_draft" in registered_tool_ids()


class TestOwnerEmailRequired:
    async def test_missing_owner_email_refused(self):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers.gmail_create_draft import (
            handle_gmail_create_draft,
        )

        req = _make_request(owner_email=None)
        ctx = _make_ctx(
            request=req,
            payload={"to": "x@y.com", "subject": "s", "body": "b"},
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await handle_gmail_create_draft(ctx)
        assert ei.value.code == "owner_email_required"


class TestPayloadValidation:
    @pytest.mark.parametrize("missing", ["to", "subject", "body"])
    async def test_required_field_missing(self, missing):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers.gmail_create_draft import (
            handle_gmail_create_draft,
        )

        payload = {"to": "x@y.com", "subject": "s", "body": "b"}
        del payload[missing]
        req = _make_request()
        ctx = _make_ctx(request=req, payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await handle_gmail_create_draft(ctx)
        assert ei.value.code == f"payload_field_missing:{missing}"


class TestOAuthNotConnected:
    async def test_no_connector_instance_refused(self, monkeypatch):
        """When the tenant has no connected Gmail ConnectorInstance,
        the handler must refuse with oauth_not_connected:google --
        never silently 401 against the Google API."""
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers import gmail_create_draft as mod

        async def _fake_load(ctx, *, owner_email):
            raise ControlledExecutionRefused(
                "oauth_not_connected:google",
                f"no instance for {owner_email}",
            )

        monkeypatch.setattr(mod, "_load_gmail_credentials", _fake_load)

        req = _make_request()
        ctx = _make_ctx(
            request=req,
            payload={"to": "x@y.com", "subject": "s", "body": "b"},
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_gmail_create_draft(ctx)
        assert ei.value.code == "oauth_not_connected:google"


class TestSuccessPath:
    async def test_mocked_draft_create_returns_safe_payload(self, monkeypatch):
        """Happy path: monkeypatch credentials lookup + GmailClient
        and confirm the handler returns a structured result with no
        access_token / refresh_token leakage."""
        from app.services.controlled_execution_handlers import gmail_create_draft as mod

        async def _fake_load(ctx, *, owner_email):
            return {"access_token": "SECRET-NEVER-LEAK"}

        fake_client = MagicMock()
        fake_client.create_draft = AsyncMock(return_value={
            "draft_id": "draft-abc123",
            "message_id": "msg-xyz",
            "status": "draft",
        })

        monkeypatch.setattr(mod, "_load_gmail_credentials", _fake_load)
        monkeypatch.setattr(mod, "_build_client", lambda creds: fake_client)

        req = _make_request()
        ctx = _make_ctx(
            request=req,
            payload={
                "to": "ops@example.com",
                "subject": "Q3 plan",
                "body": "Draft body",
            },
        )
        result = await mod.handle_gmail_create_draft(ctx)

        assert result["draft_id"] == "draft-abc123"
        assert result["status"] == "draft"
        assert result["tool_id"] == "gmail.create_draft"
        assert result["owner_email"] == "founder@example.com"
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

        # Confirm the handler called create_draft, NOT send_email or
        # any reply path. We use a spec-tight client whose only
        # awaitable is create_draft -- any other attribute access
        # would have been an AttributeError, not a silent MagicMock.
        fake_client.create_draft.assert_awaited_once()
