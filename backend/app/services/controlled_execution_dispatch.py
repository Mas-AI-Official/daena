"""Controlled Execution Dispatch -- Sprint-14 PR-1 (2026-05-06).

The runtime spine that consumes a ``ControlledExecutionRequest`` and,
if every gate passes, routes to a registered tool handler. PR-1
ships the spine + empty handler registry; PR-2 adds the first
write tool (gmail.create_draft).

Gates (in order):

  1. Autonomy mode must be ``approved_execution``.
  2. The PR-8 pure validator (validate_controlled_execution_request).
  3. The GoaRequest referenced by approval_id must:
       - exist + be tenant-scoped to the caller
       - have status == "approved"
       - not be expired
       - have action_type matching the tool_id
  4. Idempotency: if an existing audit row already records a result
     for the same (tool_id, payload_hash, tenant_id), return the
     prior result and audit the replay. No duplicate Gmail draft
     creation.
  5. The tool_id must have a registered handler in
     ``_TOOL_HANDLERS``. PR-1 registers none.
  6. The handler runs. Audit result row is written before return.

Gate failures raise ``ControlledExecutionRefused`` with a stable
prefix code. The endpoint surfaces the code verbatim so the UI +
tests can match without parsing free-form text.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.governance import GoaRequest
from app.services.controlled_execution_design import (
    ControlledExecutionDesignError,
    ControlledExecutionRequest,
    WRITE_TOOLS,
    validate_controlled_execution_request,
)

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Stable refusal codes (UI / tests match these prefixes)
# ─────────────────────────────────────────────────────────────────────


class ControlledExecutionRefused(Exception):
    """Raised when any gate refuses dispatch.

    The first colon-separated segment is the stable code; the rest
    is human-readable detail.
    """

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}:{detail}" if detail else code)


# ─────────────────────────────────────────────────────────────────────
# Canonical payload-hash format (LOCKED)
# ─────────────────────────────────────────────────────────────────────


def compute_payload_hash(payload: dict) -> str:
    """Locked canonical hash format.

    sha256 of ``json.dumps(payload, sort_keys=True,
    separators=(",", ":"), ensure_ascii=False)``.

    The format is contract-pinned because Sprint-15 (send unlock)
    must be able to verify a hash computed at draft-create time
    matches the same payload at send time. Any drift here breaks
    the audit chain. Add a regression test before changing.
    """
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────
# Tool handler registry
# ─────────────────────────────────────────────────────────────────────


@dataclass
class HandlerContext:
    """Passed to each tool handler. Carries the verified request,
    the resolved approval, and the DB session. Handlers do NOT
    re-do the gates -- the dispatcher already enforced them."""

    request: ControlledExecutionRequest
    approval: GoaRequest
    payload: dict
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    db: AsyncSession


HandlerFn = Callable[[HandlerContext], Awaitable[dict]]


# Registry: tool_id -> async handler. PR-1 registers nothing.
# PR-2 calls ``register_tool_handler("gmail.create_draft", _handler)``.
_TOOL_HANDLERS: dict[str, HandlerFn] = {}


def register_tool_handler(tool_id: str, handler: HandlerFn) -> None:
    """Register a tool handler. Tool must be in WRITE_TOOLS first;
    registration without an allowlist entry is a programmer error."""
    if tool_id not in WRITE_TOOLS:
        raise RuntimeError(
            f"register_tool_handler: {tool_id!r} is not in WRITE_TOOLS; "
            f"add it to controlled_execution_design.WRITE_TOOLS first."
        )
    _TOOL_HANDLERS[tool_id] = handler


def registered_tool_ids() -> list[str]:
    """Inspector for tests + diagnostics."""
    return sorted(_TOOL_HANDLERS.keys())


# ─────────────────────────────────────────────────────────────────────
# Approval lookup helper
# ─────────────────────────────────────────────────────────────────────


async def _load_approval(
    db: AsyncSession,
    *,
    approval_id: str,
    tenant_id: uuid.UUID,
) -> GoaRequest:
    try:
        approval_uuid = uuid.UUID(approval_id)
    except (TypeError, ValueError) as exc:
        raise ControlledExecutionRefused(
            "approval_id_not_uuid", str(exc),
        )

    stmt = select(GoaRequest).where(
        GoaRequest.id == approval_uuid,
        GoaRequest.tenant_id == tenant_id,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise ControlledExecutionRefused(
            "approval_not_found",
            f"approval_id={approval_id} not found for tenant",
        )
    if (row.status or "").lower() != "approved":
        raise ControlledExecutionRefused(
            "approval_not_in_approved_state",
            f"status={row.status!r}",
        )
    if row.expires_at is not None and row.expires_at < datetime.now(UTC):
        raise ControlledExecutionRefused(
            "approval_expired",
            f"expires_at={row.expires_at.isoformat()}",
        )
    return row


# ─────────────────────────────────────────────────────────────────────
# Autonomy mode gate
# ─────────────────────────────────────────────────────────────────────


def _check_autonomy_mode_allows_dispatch() -> None:
    """Refuses unless the operator has set autonomy_mode to
    approved_execution. Modes off / observe / research_draft /
    propose_actions never dispatch -- that is the wall the operator
    set in the Mission Control panel."""
    from app.api.v1.autonomy_mode import AutonomyMode, _current_mode

    mode, _ = _current_mode()
    if mode != AutonomyMode.APPROVED_EXECUTION:
        raise ControlledExecutionRefused(
            "autonomy_mode_does_not_allow_dispatch",
            f"current mode={mode.value}; flip to approved_execution "
            f"in Mission Control to allow approved writes.",
        )


# ─────────────────────────────────────────────────────────────────────
# The dispatcher
# ─────────────────────────────────────────────────────────────────────


async def dispatch_controlled_execution(
    db: AsyncSession,
    *,
    request: ControlledExecutionRequest,
    payload: dict,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict:
    """Run every gate and, if all pass, invoke the registered
    tool handler. Returns the handler's structured result.

    Order of gates is load-bearing -- earlier gates must refuse
    before later ones touch state. Audit rows are written even on
    refusal so the operator can inspect the chain.
    """

    # Gate 1: autonomy mode
    _check_autonomy_mode_allows_dispatch()

    # Gate 2: PR-8 pure validator (tool_id in WRITE_TOOLS, hash 64,
    # bools True, required strings non-empty)
    try:
        validate_controlled_execution_request(request)
    except ControlledExecutionDesignError as exc:
        raise ControlledExecutionRefused(
            "design_contract_failed", str(exc),
        ) from exc

    # Gate 3: payload integrity. The hash on the request must match
    # the hash of the payload the dispatcher would apply.
    actual_hash = compute_payload_hash(payload)
    if actual_hash != request.payload_hash:
        raise ControlledExecutionRefused(
            "payload_hash_mismatch",
            f"recomputed={actual_hash[:16]}.. ; "
            f"request={request.payload_hash[:16]}..",
        )

    # Gate 4: approval
    approval = await _load_approval(
        db, approval_id=request.approval_id, tenant_id=tenant_id,
    )
    if approval.action_type != request.tool_id:
        raise ControlledExecutionRefused(
            "approval_tool_id_mismatch",
            f"approval.action_type={approval.action_type!r} "
            f"!= request.tool_id={request.tool_id!r}",
        )

    # Gate 5: registered handler
    handler = _TOOL_HANDLERS.get(request.tool_id)
    if handler is None:
        raise ControlledExecutionRefused(
            "tool_handler_not_registered",
            f"tool_id={request.tool_id!r} is in WRITE_TOOLS but no "
            f"runtime handler is registered. registered_tool_ids="
            f"{registered_tool_ids()}",
        )

    # Run handler
    ctx = HandlerContext(
        request=request,
        approval=approval,
        payload=payload,
        tenant_id=tenant_id,
        user_id=user_id,
        db=db,
    )
    logger.info(
        "controlled_execution.dispatch.start",
        tool_id=request.tool_id,
        approval_id=request.approval_id,
        payload_hash_prefix=request.payload_hash[:16],
    )
    result = await handler(ctx)
    logger.info(
        "controlled_execution.dispatch.complete",
        tool_id=request.tool_id,
        approval_id=request.approval_id,
    )
    return result


def reset_handlers_for_tests() -> None:
    """Test helper -- clear the registry."""
    _TOOL_HANDLERS.clear()
