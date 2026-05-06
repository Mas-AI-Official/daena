"""local.file_change_proposal handler -- Sprint-14 PR-4 (2026-05-06).

Daena PROPOSES a local file change, never directly overwrites. The
proposal is persisted as a JSON artifact under
``backend/.file_change_proposals/<uuid>.json`` (gitignored). A
separate apply tool (future sprint) consumes the proposal,
re-validates the diff against the current file, and applies it
under its own controlled-execution gate.

Locked refusals (in addition to dispatcher gates):

::

    payload_field_missing:<field>
        target_path / change_type / diff_text required.

    target_path_outside_repo
        absolute path resolves outside the project root.

    target_path_is_secret_file
        path matches a known secret-file pattern (.env, *.pem, *.key,
        secrets/*, credentials*.json, anything starting with a dot
        plus 'credentials' / 'token' / 'secret').

    change_type_delete_not_allowed_in_proposal_v1
        change_type=delete is intentionally forbidden in PR-4. A
        future apply-with-restore tool will gate deletes separately.

    change_type_invalid
        change_type is not in {"create", "modify"}.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.controlled_execution_dispatch import (
    ControlledExecutionRefused,
    HandlerContext,
    register_tool_handler,
)

logger = get_logger(__name__)


_TOOL_ID = "local.file_change_proposal"
_REQUIRED_FIELDS: tuple[str, ...] = ("target_path", "change_type", "diff_text")

# Repo root: backend/ + frontend/ + docs/ + tests/ are all under
# this anchor. The handler resolves any submitted target_path to an
# absolute path and refuses unless it is contained.
_REPO_ROOT = Path(__file__).resolve().parents[4]

# Proposal artifact directory (gitignored via .gitignore).
_PROPOSAL_DIR = Path(__file__).resolve().parents[3] / ".file_change_proposals"

# Secret-file patterns. The handler refuses any path that matches.
_SECRET_FILE_PATTERNS = (
    re.compile(r"\.env(\..+)?$", re.IGNORECASE),
    re.compile(r"\.pem$", re.IGNORECASE),
    re.compile(r"\.key$", re.IGNORECASE),
    re.compile(r"\.p12$", re.IGNORECASE),
    re.compile(r"(?:^|[\\/])(?:\.)?secrets[\\/]", re.IGNORECASE),
    re.compile(r"credentials.*\.json$", re.IGNORECASE),
    re.compile(r"\.daena_oauth_overrides\.json$", re.IGNORECASE),
    re.compile(r"\.autonomy_mode\.json$", re.IGNORECASE),
    re.compile(r"\.credentials$", re.IGNORECASE),
    re.compile(r"_token(s)?\.json$", re.IGNORECASE),
)


def _is_secret_file(path_str: str) -> bool:
    return any(p.search(path_str) for p in _SECRET_FILE_PATTERNS)


def _resolve_under_repo(target_path: str) -> Path:
    """Resolve target_path against the repo root and refuse if it
    escapes. Symlink-resolving + parent-traversal-safe via Path.resolve."""

    p = Path(target_path)
    if not p.is_absolute():
        p = _REPO_ROOT / p
    resolved = p.resolve()
    try:
        resolved.relative_to(_REPO_ROOT)
    except ValueError as exc:
        raise ControlledExecutionRefused(
            "target_path_outside_repo",
            f"{target_path!r} resolves to {resolved}, which is outside "
            f"{_REPO_ROOT}.",
        ) from exc
    return resolved


async def handle_file_change_proposal(ctx: HandlerContext) -> dict[str, Any]:
    """Persist a file change proposal artifact. Does NOT apply.

    The result carries a stable ``proposal_id`` the operator (or
    future apply tool) uses to fetch the proposal.
    """

    for field in _REQUIRED_FIELDS:
        value = ctx.payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ControlledExecutionRefused(
                f"payload_field_missing:{field}",
                f"{_TOOL_ID} payload must carry non-empty {field!r}.",
            )

    target_path = ctx.payload["target_path"]
    change_type = ctx.payload["change_type"].lower().strip()
    diff_text = ctx.payload["diff_text"]

    if change_type == "delete":
        raise ControlledExecutionRefused(
            "change_type_delete_not_allowed_in_proposal_v1",
            "PR-4 does not allow change_type=delete. A future "
            "apply-with-restore tool will gate deletes separately.",
        )
    if change_type not in ("create", "modify"):
        raise ControlledExecutionRefused(
            "change_type_invalid",
            f"change_type={change_type!r}; expected 'create' or 'modify'.",
        )

    if _is_secret_file(target_path):
        raise ControlledExecutionRefused(
            "target_path_is_secret_file",
            f"{target_path!r} matches a known secret-file pattern. "
            f"Daena refuses to propose changes to secret files; the "
            f"operator must edit those manually.",
        )

    resolved = _resolve_under_repo(target_path)

    # Persist the proposal artifact.
    proposal_id = str(uuid.uuid4())
    _PROPOSAL_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = _PROPOSAL_DIR / f"{proposal_id}.json"
    artifact = {
        "proposal_id": proposal_id,
        "tool_id": _TOOL_ID,
        "tenant_id": str(ctx.tenant_id),
        "user_id": str(ctx.user_id),
        "owner_email": ctx.request.owner_email,
        "approval_id": ctx.request.approval_id,
        "consent_grant_id": ctx.request.consent_grant_id,
        "payload_hash": ctx.request.payload_hash,
        "target_path": str(resolved),
        "target_path_repo_relative": str(
            resolved.relative_to(_REPO_ROOT)
        ).replace("\\", "/"),
        "change_type": change_type,
        "diff_text": diff_text,
        "status": "proposed",
        "applied_at": None,
        "rejected_at": None,
        "created_at": datetime.now(UTC).isoformat(),
    }
    artifact_path.write_text(
        json.dumps(artifact, indent=2), encoding="utf-8",
    )
    logger.info(
        "controlled_execution.file_change_proposal.created",
        proposal_id=proposal_id,
        target_path_repo_relative=artifact["target_path_repo_relative"],
        change_type=change_type,
        approval_id=ctx.request.approval_id,
    )

    return {
        "proposal_id": proposal_id,
        "target_path_repo_relative": artifact["target_path_repo_relative"],
        "change_type": change_type,
        "diff_preview_lines": len(diff_text.splitlines()),
        "status": "proposed",
        "tool_id": _TOOL_ID,
        "rollback_or_undo_instruction": (
            ctx.request.rollback_or_undo_instruction
            or f"Reject proposal {proposal_id} via the governance "
               f"approvals page; no changes have been applied."
        ),
    }


# Side-effect register on import.
register_tool_handler(_TOOL_ID, handle_file_change_proposal)
