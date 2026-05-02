"""PR-GOV-01: field-level Founder guard on governance preference fields.

Hard Law 8 (backend/app/core/hard_laws.py) requires the governance mode
toggle to flow through the FOUNDER role. Before this PR, PUT
/api/v1/settings/user accepted ``default_governance_mode`` from any
authenticated caller -- so any user could flip a tenant from GOVERNED
to UNLEASHED via the public preferences API. This test file pins the
new field-level guard inside ``_update_user_preferences_impl``.

The guard is at the impl layer (not the endpoint dependency) so the
same endpoint can keep serving normal preference edits (theme,
notifications, display name) for non-Founder roles. Only the
governance-sensitive fields are gated.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException


def _make_user(role: str = "OPERATOR"):
    """Build a mock CurrentUser with the requested role.

    Roles below FOUNDER (AUDITOR, VIEWER, OPERATOR, MANAGER, ADMIN) all
    must fail the governance guard. FOUNDER must pass.
    """
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = uuid.uuid4()
    user.email = f"{role.lower()}@example.com"
    user.role = role
    user.display_name = f"{role.title()} User"
    return user


def _make_db_no_user():
    """Return an async db mock whose User lookup yields None.

    The impl handles the no-User-row branch (it falls through to the
    response builder using defaults). We use this to test the guard in
    isolation -- DB integrity is not the subject under test here.
    """
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


class TestSensitiveFieldsConstant:
    """The SENSITIVE_PREF_FIELDS constant is the public contract that
    callers, tests, and future PRs depend on. Pin its membership."""

    def test_constant_includes_governance_mode(self):
        from app.api.v1.settings import SENSITIVE_PREF_FIELDS

        assert "default_governance_mode" in SENSITIVE_PREF_FIELDS

    def test_constant_includes_deprecated_slider(self):
        from app.api.v1.settings import SENSITIVE_PREF_FIELDS

        # The deprecated slider field still maps to governance mode
        # through the to_governance_mode() backward-compat helper.
        # Failing to gate it would let an attacker bypass the guard
        # by posting the old field name.
        assert "default_governance_slider" in SENSITIVE_PREF_FIELDS

    def test_constant_includes_routing_mode(self):
        from app.api.v1.settings import SENSITIVE_PREF_FIELDS

        # COUNCIL/QUINTESSENCE multiply LLM cost; the *default* should
        # not be self-elevated by non-Founders even though per-request
        # routing is selectable from the chat composer.
        assert "default_routing_mode" in SENSITIVE_PREF_FIELDS

    def test_constant_does_not_overcollect(self):
        from app.api.v1.settings import SENSITIVE_PREF_FIELDS

        # Anti-overreach: theme, display_name, notification flags must
        # NOT be in the sensitive set. If a future change accidentally
        # adds them, this test fails loudly.
        for benign in (
            "dark_mode", "display_name", "notif_desktop",
            "preferred_model", "monthly_budget",
        ):
            assert benign not in SENSITIVE_PREF_FIELDS


class TestFieldLevelGovernanceGuard:
    """Hard Law 8: only FOUNDER can change governance-sensitive prefs."""

    @pytest.mark.asyncio
    async def test_non_founder_blocked_from_governance_mode(self):
        from app.api.v1.settings import (
            UserPreferencesUpdate,
            _update_user_preferences_impl,
        )

        user = _make_user("OPERATOR")
        db = _make_db_no_user()
        body = UserPreferencesUpdate(default_governance_mode="UNLEASHED")

        with pytest.raises(HTTPException) as exc_info:
            await _update_user_preferences_impl(body, user, db)

        assert exc_info.value.status_code == 403
        detail = exc_info.value.detail
        assert detail["error"]["code"] == "FOUNDER_ROLE_REQUIRED"
        assert "default_governance_mode" in detail["error"]["rejected_fields"]

    @pytest.mark.asyncio
    async def test_admin_blocked_too(self):
        """ADMIN is below FOUNDER in the role hierarchy and is gated."""
        from app.api.v1.settings import (
            UserPreferencesUpdate,
            _update_user_preferences_impl,
        )

        user = _make_user("ADMIN")
        db = _make_db_no_user()
        body = UserPreferencesUpdate(default_governance_mode="UNLEASHED")

        with pytest.raises(HTTPException) as exc_info:
            await _update_user_preferences_impl(body, user, db)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_non_founder_blocked_from_deprecated_slider(self):
        """The legacy field name must be gated too -- otherwise a
        client could bypass the guard by posting the deprecated field."""
        from app.api.v1.settings import (
            UserPreferencesUpdate,
            _update_user_preferences_impl,
        )

        user = _make_user("OPERATOR")
        db = _make_db_no_user()
        body = UserPreferencesUpdate(default_governance_slider="YOLO")

        with pytest.raises(HTTPException) as exc_info:
            await _update_user_preferences_impl(body, user, db)
        rejected = exc_info.value.detail["error"]["rejected_fields"]
        assert "default_governance_slider" in rejected

    @pytest.mark.asyncio
    async def test_non_founder_blocked_from_routing_council(self):
        from app.api.v1.settings import (
            UserPreferencesUpdate,
            _update_user_preferences_impl,
        )

        user = _make_user("MANAGER")
        db = _make_db_no_user()
        body = UserPreferencesUpdate(default_routing_mode="QUINTESSENCE")

        with pytest.raises(HTTPException) as exc_info:
            await _update_user_preferences_impl(body, user, db)
        rejected = exc_info.value.detail["error"]["rejected_fields"]
        assert "default_routing_mode" in rejected

    @pytest.mark.asyncio
    async def test_non_founder_can_update_normal_prefs(self):
        """Theme, notifications, display name must remain self-editable
        for any authenticated user. This is the whole point of the
        field-level guard vs an endpoint-level one."""
        from app.api.v1.settings import (
            UserPreferencesUpdate,
            _update_user_preferences_impl,
        )

        user = _make_user("OPERATOR")
        db = _make_db_no_user()
        body = UserPreferencesUpdate(
            display_name="Updated Name",
            dark_mode=False,
            notif_desktop=True,
        )

        # Must NOT raise.
        result = await _update_user_preferences_impl(body, user, db)
        assert result is not None
        assert result.role == "OPERATOR"

    @pytest.mark.asyncio
    async def test_founder_can_update_governance_mode(self):
        from app.api.v1.settings import (
            UserPreferencesUpdate,
            _update_user_preferences_impl,
        )

        user = _make_user("FOUNDER")
        db = _make_db_no_user()
        body = UserPreferencesUpdate(default_governance_mode="UNLEASHED")

        # Founder bypass per Hard Law 4 -- must NOT raise.
        result = await _update_user_preferences_impl(body, user, db)
        assert result.role == "FOUNDER"

    @pytest.mark.asyncio
    async def test_founder_can_update_routing_council(self):
        from app.api.v1.settings import (
            UserPreferencesUpdate,
            _update_user_preferences_impl,
        )

        user = _make_user("FOUNDER")
        db = _make_db_no_user()
        body = UserPreferencesUpdate(default_routing_mode="COUNCIL")

        result = await _update_user_preferences_impl(body, user, db)
        assert result.role == "FOUNDER"

    @pytest.mark.asyncio
    async def test_mixed_payload_is_all_or_nothing_reject(self, monkeypatch):
        """Mixed payload (governance + theme): reject the whole request,
        do NOT partially apply the theme update. Avoids the trap where
        a client thinks "well at least the theme landed" while the
        governance field silently failed.

        We patch AuditService to a no-op so the assertion can isolate
        the User-row write path from the audit-write path. The audit
        write IS expected to fire on rejection -- that is tested in
        TestAuditLogOnRejection. Here we only need to prove the User
        row was never touched."""
        from app.api.v1.settings import (
            UserPreferencesUpdate,
            _update_user_preferences_impl,
        )

        class NoopAudit:
            def __init__(self, _db):
                pass

            async def log_decision(self, **_kwargs):
                return {"id": str(uuid.uuid4())}

        import app.services.audit as audit_module
        monkeypatch.setattr(audit_module, "AuditService", NoopAudit)

        user = _make_user("OPERATOR")
        db = _make_db_no_user()
        body = UserPreferencesUpdate(
            default_governance_mode="UNLEASHED",
            dark_mode=False,
        )

        with pytest.raises(HTTPException) as exc_info:
            await _update_user_preferences_impl(body, user, db)

        # With the audit writer no-op'd, the User-row write path is the
        # only thing that could have called db.execute / db.flush. The
        # guard runs FIRST, so neither should have been touched.
        db.execute.assert_not_called()
        db.flush.assert_not_called()
        rejected = exc_info.value.detail["error"]["rejected_fields"]
        assert "default_governance_mode" in rejected

    @pytest.mark.asyncio
    async def test_multiple_sensitive_fields_all_listed(self):
        """If the payload tries to set 2+ sensitive fields, ALL of them
        appear in rejected_fields (sorted, deterministic)."""
        from app.api.v1.settings import (
            UserPreferencesUpdate,
            _update_user_preferences_impl,
        )

        user = _make_user("OPERATOR")
        db = _make_db_no_user()
        body = UserPreferencesUpdate(
            default_governance_mode="UNLEASHED",
            default_routing_mode="QUINTESSENCE",
        )

        with pytest.raises(HTTPException) as exc_info:
            await _update_user_preferences_impl(body, user, db)
        rejected = exc_info.value.detail["error"]["rejected_fields"]
        assert "default_governance_mode" in rejected
        assert "default_routing_mode" in rejected
        # Sorted for determinism
        assert rejected == sorted(rejected)


class TestAuditLogOnRejection:
    """Reject paths must write a BLOCKED audit row with field names but
    NEVER the attempted values (the value itself could be a probe vector
    or contain PII)."""

    @pytest.mark.asyncio
    async def test_audit_log_emitted_with_field_names(self, monkeypatch):
        from app.api.v1.settings import (
            UserPreferencesUpdate,
            _update_user_preferences_impl,
        )

        user = _make_user("OPERATOR")
        db = _make_db_no_user()

        log_calls: list[dict] = []

        class FakeAudit:
            def __init__(self, _db):
                pass

            async def log_decision(self, **kwargs):
                log_calls.append(kwargs)
                return {"id": str(uuid.uuid4())}

        import app.services.audit as audit_module
        monkeypatch.setattr(audit_module, "AuditService", FakeAudit)

        body = UserPreferencesUpdate(default_governance_mode="UNLEASHED")
        with pytest.raises(HTTPException):
            await _update_user_preferences_impl(body, user, db)

        assert len(log_calls) == 1
        call = log_calls[0]
        assert call["actor_id"] == user.id
        assert call["actor_type"] == "USER"
        assert call["action_type"] == "GOVERNANCE_PREF_UPDATE_REJECTED"
        assert call["result"] == "BLOCKED"
        assert call["risk_level"] == "HIGH"
        assert call["governance_tier"] == 4

    @pytest.mark.asyncio
    async def test_audit_log_does_not_leak_attempted_values(self, monkeypatch):
        """The rejection audit row must capture WHICH fields were
        rejected (so an operator can investigate) but must NOT contain
        the attempted VALUES. A malicious payload could embed PII or a
        probe payload designed to land in the audit ledger as a side
        channel."""
        from app.api.v1.settings import (
            UserPreferencesUpdate,
            _update_user_preferences_impl,
        )

        user = _make_user("OPERATOR")
        db = _make_db_no_user()

        log_calls: list[dict] = []

        class FakeAudit:
            def __init__(self, _db):
                pass

            async def log_decision(self, **kwargs):
                log_calls.append(kwargs)
                return {"id": str(uuid.uuid4())}

        import app.services.audit as audit_module
        monkeypatch.setattr(audit_module, "AuditService", FakeAudit)

        body = UserPreferencesUpdate(default_governance_mode="UNLEASHED")
        with pytest.raises(HTTPException):
            await _update_user_preferences_impl(body, user, db)

        params = log_calls[0]["action_params"]
        # Field names recorded
        assert "default_governance_mode" in params["attempted_fields"]
        assert params["user_role"] == "OPERATOR"
        # Value NOT recorded -- the string "UNLEASHED" must not appear
        # anywhere in the audit row params.
        assert "UNLEASHED" not in json.dumps(params)

    @pytest.mark.asyncio
    async def test_audit_failure_does_not_unblock_request(self, monkeypatch):
        """If the audit subsystem is broken, the rejection MUST still
        fire. Audit failure cannot become a backdoor that allows a
        guard-failed request through."""
        from app.api.v1.settings import (
            UserPreferencesUpdate,
            _update_user_preferences_impl,
        )

        user = _make_user("OPERATOR")
        db = _make_db_no_user()

        class BrokenAudit:
            def __init__(self, _db):
                pass

            async def log_decision(self, **_kwargs):
                raise RuntimeError("audit ledger offline")

        import app.services.audit as audit_module
        monkeypatch.setattr(audit_module, "AuditService", BrokenAudit)

        body = UserPreferencesUpdate(default_governance_mode="UNLEASHED")
        with pytest.raises(HTTPException) as exc_info:
            await _update_user_preferences_impl(body, user, db)
        # Still 403, even though the audit write blew up.
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_no_audit_when_founder_passes(self, monkeypatch):
        """Founder updates are NOT audited via the rejection path (Hard
        Law 4: Founder Override is logged separately at the action
        execution layer, not at the role-check layer)."""
        from app.api.v1.settings import (
            UserPreferencesUpdate,
            _update_user_preferences_impl,
        )

        user = _make_user("FOUNDER")
        db = _make_db_no_user()

        log_calls: list[dict] = []

        class FakeAudit:
            def __init__(self, _db):
                pass

            async def log_decision(self, **kwargs):
                log_calls.append(kwargs)
                return {"id": str(uuid.uuid4())}

        import app.services.audit as audit_module
        monkeypatch.setattr(audit_module, "AuditService", FakeAudit)

        body = UserPreferencesUpdate(default_governance_mode="UNLEASHED")
        await _update_user_preferences_impl(body, user, db)

        # No rejection audit row -- the request was allowed.
        assert log_calls == []
