"""Self-Healing Apply/Test/Rollback Loop -- Sprint-17 PR-4 (2026-05-06).

Wraps the controlled-execution dispatch for
``local.file_change_proposal.apply`` with the audit-before / audit-
after stamping and the blocker-workstream emission rule from the
brief:

  * Audit row written BEFORE dispatch (always).
  * Audit row written AFTER dispatch (success / refused / raised).
  * If the apply handler refuses with ``rollback_failed``, the
    loop emits a P0 blocker workstream payload so the operator
    sees the manual-cleanup task at the top of their queue.

This module does NOT:

  * call any LLM
  * generate a patch
  * create the upstream proposal artifact
  * raise an approval (the operator does, via the approvals page)
  * commit (PR-5 of this sprint)

It is a THIN ORCHESTRATOR: caller provides an already-approved
``ControlledExecutionRequest`` + payload, the loop runs the
dispatch, and the caller gets a typed result describing what
happened next.

Why a separate module: keeping this layer thin lets PR-7 + future
autonomous loops compose it without re-implementing the audit +
blocker-emission rules. The dispatch spine itself (Sprint-14 PR-1)
stays pure -- gates fire, handler runs, result returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.services.controlled_execution_design import ControlledExecutionRequest
from app.services.controlled_execution_dispatch import (
    ControlledExecutionRefused,
    dispatch_controlled_execution,
)


# Outcome classification. ``Outcome`` literals are the audit-row
# tags so the audit viewer's filter can group apply attempts by
# their final state.
SelfHealingApplyOutcome = (
    "success"               # apply landed, tests passed
    " | tests_rolled_back"  # tests failed, file restored from backup
    " | rollback_failed"    # CRITICAL: tests failed AND rollback raised
    " | refused"            # any other gate refusal (drift, secret...)
    " | crashed"            # handler raised an unexpected exception
)


@dataclass
class SelfHealingApplyResult:
    """Typed descriptor returned to the caller."""

    outcome: str
    refusal_code: str | None
    refusal_detail: str | None
    handler_result: dict[str, Any] | None
    audit_preflight: dict[str, Any]
    audit_result: dict[str, Any]
    blocker_workstream: dict[str, Any] | None = field(default=None)


def _audit_row(
    *, when: str, request: ControlledExecutionRequest, outcome: str | None,
    code: str | None, detail: str | None,
) -> dict[str, Any]:
    """Build a structured audit row. The caller (or the Phase 4
    AuditEvent writer) is responsible for actually persisting it.
    Keeping the writer out of this module preserves testability."""
    return {
        "when": when,                # "preflight" | "result"
        "tool_id": request.tool_id,
        "approval_id": request.approval_id,
        "consent_grant_id": request.consent_grant_id,
        "payload_hash_prefix": (request.payload_hash or "")[:16],
        "owner_email": request.owner_email,
        "outcome": outcome,
        "refusal_code": code,
        "refusal_detail": detail,
        "stamped_at": datetime.now(UTC).isoformat(),
    }


def _blocker_workstream_payload(
    *, request: ControlledExecutionRequest, refusal_detail: str,
) -> dict[str, Any]:
    """Build the workstream payload the orchestrator emits when
    ``rollback_failed`` fires. The operator sees this at the top
    of the approvals queue with severity=blocker.

    Reuses the locked shape of ``self_healing_service.repair_workstream_payload``
    but stamps the failure as a ``self_repair_blocker`` so the
    queue can route it to the founder (not to a brain)."""
    return {
        "goal": (
            "BLOCKER: self-healing rollback FAILED -- manual file "
            "inspection required."
        )[:500],
        "department_hint": "Engineering",
        "next_step_text": (
            f"local.file_change_proposal.apply rolled back the file "
            f"after a test failure, but the rollback ITSELF raised. "
            f"Inspect the target file manually before any further "
            f"apply; the backup directory contains the pre-apply "
            f"bytes. detail={refusal_detail[:200]}"
        )[:500],
        "initial_context": {
            "self_repair_blocker": {
                "approval_id": request.approval_id,
                "tool_id": request.tool_id,
                "owner_email": request.owner_email,
                "severity": "blocker",
                "delivery": "manual_only",
                "requires_human_review": True,
                "refusal_detail": refusal_detail,
            },
        },
    }


async def run_apply_cycle(
    *,
    db,
    request: ControlledExecutionRequest,
    payload: dict,
    tenant_id,
    user_id,
) -> SelfHealingApplyResult:
    """Audit-before -> dispatch -> classify -> audit-after.

    Returns a typed result. NEVER raises -- gate refusals and
    handler crashes both surface as fields on the returned
    ``SelfHealingApplyResult``. The caller decides whether to
    propagate or recover."""

    audit_pre = _audit_row(
        when="preflight", request=request, outcome=None,
        code=None, detail=None,
    )

    try:
        handler_result = await dispatch_controlled_execution(
            db,
            request=request,
            payload=payload,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    except ControlledExecutionRefused as exc:
        # Classify the refusal.
        if exc.code == "tests_failed_rolled_back":
            outcome = "tests_rolled_back"
            blocker = None
        elif exc.code == "rollback_failed":
            outcome = "rollback_failed"
            # CRITICAL: emit blocker workstream payload.
            blocker = _blocker_workstream_payload(
                request=request, refusal_detail=str(exc),
            )
        else:
            outcome = "refused"
            blocker = None
        audit_post = _audit_row(
            when="result", request=request, outcome=outcome,
            code=exc.code, detail=str(exc)[:300],
        )
        return SelfHealingApplyResult(
            outcome=outcome,
            refusal_code=exc.code,
            refusal_detail=str(exc)[:300],
            handler_result=None,
            audit_preflight=audit_pre,
            audit_result=audit_post,
            blocker_workstream=blocker,
        )
    except Exception as exc:  # noqa: BLE001 - bare-broad catch is intentional
        # Handler crashed unexpectedly. Surface as ``crashed`` and
        # treat as a blocker (operator must inspect).
        audit_post = _audit_row(
            when="result", request=request, outcome="crashed",
            code="handler_crashed", detail=f"{type(exc).__name__}: {exc}",
        )
        return SelfHealingApplyResult(
            outcome="crashed",
            refusal_code="handler_crashed",
            refusal_detail=f"{type(exc).__name__}: {exc}"[:300],
            handler_result=None,
            audit_preflight=audit_pre,
            audit_result=audit_post,
            blocker_workstream=_blocker_workstream_payload(
                request=request,
                refusal_detail=f"handler raised: {type(exc).__name__}",
            ),
        )

    # Success.
    audit_post = _audit_row(
        when="result", request=request, outcome="success",
        code=None, detail=None,
    )
    return SelfHealingApplyResult(
        outcome="success",
        refusal_code=None,
        refusal_detail=None,
        handler_result=handler_result,
        audit_preflight=audit_pre,
        audit_result=audit_post,
        blocker_workstream=None,
    )
