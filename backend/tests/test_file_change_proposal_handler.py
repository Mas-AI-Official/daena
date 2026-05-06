"""Sprint-14 PR-4 -- file change proposal handler contract.

Pins:
  1. Handler registered after package import.
  2. Required payload fields: target_path, change_type, diff_text.
  3. change_type=delete refused (PR-4 v1).
  4. change_type other than create|modify refused.
  5. Secret-file paths refused (.env, *.pem, *.key, secrets/*,
     credentials*.json, .autonomy_mode.json, etc.).
  6. Paths outside repo root refused.
  7. Success path writes a JSON artifact to .file_change_proposals/
     with status="proposed", never "applied".
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest


pytestmark = pytest.mark.asyncio


def _make_request(**overrides):
    from app.services.controlled_execution_design import ControlledExecutionRequest

    base = dict(
        approval_id="00000000-0000-0000-0000-000000000000",
        consent_grant_id="grant-x",
        payload_hash="0" * 64,
        tool_id="local.file_change_proposal",
        owner_email="founder@example.com",
        asset_shield_pass=True,
        policy_allowlist_pass=True,
        audit_preflight_row_id="audit-pre",
        audit_result_row_id=None,
        rollback_or_undo_instruction=None,
    )
    base.update(overrides)
    return ControlledExecutionRequest(**base)


def _make_ctx(*, request, payload):
    from app.services.controlled_execution_dispatch import HandlerContext

    return HandlerContext(
        request=request,
        approval=MagicMock(),
        payload=payload,
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        db=MagicMock(),
    )


class TestRegistered:
    async def test_handler_in_registry_after_import(self):
        import app.services.controlled_execution_handlers  # noqa: F401
        from app.services.controlled_execution_dispatch import registered_tool_ids

        assert "local.file_change_proposal" in registered_tool_ids()


class TestPayloadValidation:
    @pytest.mark.parametrize("missing", ["target_path", "change_type", "diff_text"])
    async def test_required_field_missing(self, missing):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers.file_change_proposal import (
            handle_file_change_proposal,
        )

        payload = {
            "target_path": "backend/tests/scratch_for_test.txt",
            "change_type": "modify",
            "diff_text": "--- a\n+++ b\n@@ ...",
        }
        del payload[missing]
        req = _make_request()
        ctx = _make_ctx(request=req, payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await handle_file_change_proposal(ctx)
        assert ei.value.code == f"payload_field_missing:{missing}"


class TestChangeTypeRules:
    async def test_delete_refused(self):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers.file_change_proposal import (
            handle_file_change_proposal,
        )

        req = _make_request()
        ctx = _make_ctx(request=req, payload={
            "target_path": "backend/tests/scratch_for_test.txt",
            "change_type": "delete",
            "diff_text": "irrelevant",
        })
        with pytest.raises(ControlledExecutionRefused) as ei:
            await handle_file_change_proposal(ctx)
        assert ei.value.code == "change_type_delete_not_allowed_in_proposal_v1"

    async def test_invalid_change_type_refused(self):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers.file_change_proposal import (
            handle_file_change_proposal,
        )

        req = _make_request()
        ctx = _make_ctx(request=req, payload={
            "target_path": "backend/tests/scratch_for_test.txt",
            "change_type": "rewrite_everything",
            "diff_text": "irrelevant",
        })
        with pytest.raises(ControlledExecutionRefused) as ei:
            await handle_file_change_proposal(ctx)
        assert ei.value.code == "change_type_invalid"


class TestSecretFiles:
    @pytest.mark.parametrize("secret_path", [
        ".env",
        "backend/.env",
        ".env.production",
        "backend/secrets/google.json",
        "backend/credentials_2026.json",
        "config/server.pem",
        "private.key",
        ".daena_oauth_overrides.json",
        ".autonomy_mode.json",
        "auth_tokens.json",
    ])
    async def test_secret_path_refused(self, secret_path):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers.file_change_proposal import (
            handle_file_change_proposal,
        )

        req = _make_request()
        ctx = _make_ctx(request=req, payload={
            "target_path": secret_path,
            "change_type": "modify",
            "diff_text": "irrelevant",
        })
        with pytest.raises(ControlledExecutionRefused) as ei:
            await handle_file_change_proposal(ctx)
        assert ei.value.code == "target_path_is_secret_file"


class TestOutsideRepo:
    async def test_absolute_outside_path_refused(self, tmp_path):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers.file_change_proposal import (
            handle_file_change_proposal,
        )

        outside = tmp_path / "evil.txt"
        outside.write_text("payload", encoding="utf-8")
        req = _make_request()
        ctx = _make_ctx(request=req, payload={
            "target_path": str(outside),
            "change_type": "create",
            "diff_text": "+payload",
        })
        with pytest.raises(ControlledExecutionRefused) as ei:
            await handle_file_change_proposal(ctx)
        assert ei.value.code == "target_path_outside_repo"


class TestSuccessPath:
    async def test_proposal_artifact_written(self, tmp_path, monkeypatch):
        from app.services.controlled_execution_handlers import (
            file_change_proposal as mod,
        )

        monkeypatch.setattr(mod, "_PROPOSAL_DIR", tmp_path / ".file_change_proposals")

        req = _make_request()
        ctx = _make_ctx(request=req, payload={
            "target_path": "backend/tests/scratch_for_test.txt",
            "change_type": "create",
            "diff_text": "--- /dev/null\n+++ scratch\n@@ -0,0 +1 @@\n+hello\n",
        })
        result = await mod.handle_file_change_proposal(ctx)

        assert result["status"] == "proposed"
        assert result["change_type"] == "create"
        assert result["tool_id"] == "local.file_change_proposal"
        assert result["proposal_id"]
        assert result["target_path_repo_relative"].startswith("backend/")

        # Artifact persisted as JSON
        proposal_files = list((tmp_path / ".file_change_proposals").glob("*.json"))
        assert len(proposal_files) == 1
        artifact = json.loads(proposal_files[0].read_text(encoding="utf-8"))
        assert artifact["status"] == "proposed"
        assert artifact["applied_at"] is None
        assert artifact["rejected_at"] is None
        assert artifact["change_type"] == "create"
        assert artifact["proposal_id"] == result["proposal_id"]
