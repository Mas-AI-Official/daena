"""Controlled Execution Design Lock -- Sprint-13 PR-8 (2026-05-06).

This module is design-only. It does NOT execute any external action,
does NOT open any write surface, does NOT lift the
``INTEGRATIONS_PHASE2_READONLY=true`` gate.

What it locks
-------------

The contract for any future Phase 3 external action. When PR-13/14
or whichever sprint enables controlled writes lands, the executor
MUST consume a ``ControlledExecutionRequest`` that carries every
field below. Missing any field is a hard refuse.

The 10-field contract
---------------------

::

    approval_id                       -> GoaRequest.id
    consent_grant_id                  -> Asset Shield consent token
    payload_hash                      -> sha256 hex of action body
    tool_id                           -> WRITE_TOOLS allowlist key
    owner_email                       -> account profile on whose
                                         behalf the action runs
                                         (None when n/a)
    asset_shield_pass                 -> bool, must be True
    policy_allowlist_pass             -> bool, must be True
    audit_preflight_row_id            -> AuditEvent.id (BEFORE exec)
    audit_result_row_id               -> AuditEvent.id (AFTER exec;
                                         filled on completion)
    rollback_or_undo_instruction      -> text plan or None

Additional locks
----------------

* WRITE_TOOLS is the closed allowlist. PR-8 ships the **empty** set;
  later sprints add specific tools (``email_send`` /
  ``linkedin_dm_send`` / etc.) one at a time, each with its own test.
* ``INTEGRATIONS_PHASE2_READONLY`` env stays at ``true``. No code
  path here flips it.
* Adding a new WRITE_TOOL requires touching:
    1. ``WRITE_TOOLS`` in this file
    2. The Asset Shield egress allowlist
    3. The plain-English policy compiler templates
    4. A dedicated negative test that proves missing fields refuse
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal


# ── Closed WRITE_TOOLS allowlist (intentionally empty) ───────────────

# Tools land in WRITE_TOOLS ONLY when:
#   1. The tool's external system is in Asset Shield egress
#      allowlist for the operator's tenant
#   2. A founder-approved policy says ALLOW for this tool
#   3. A negative test proves a missing field is refused
# Sprint-14 unlocks the first three (gmail.create_draft, calendar
# tentative event without invites, local file change proposal).
# All three are draft / proposal / tentative variants -- none of
# them sends, posts, or applies on the back of approval. PR-15
# unlocks the actual send variants.
WriteToolId = Literal[
    "gmail.create_draft",
    "calendar.create_tentative_event_without_invites",
    "local.file_change_proposal",
]

WRITE_TOOLS: Final[frozenset[str]] = frozenset({
    "gmail.create_draft",
    "calendar.create_tentative_event_without_invites",
    "local.file_change_proposal",
})


# ── 10-field locked contract ─────────────────────────────────────────


_REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "approval_id",
    "consent_grant_id",
    "payload_hash",
    "tool_id",
    "owner_email",
    "asset_shield_pass",
    "policy_allowlist_pass",
    "audit_preflight_row_id",
    "audit_result_row_id",
    "rollback_or_undo_instruction",
)


@dataclass(frozen=True)
class ControlledExecutionRequest:
    """The shape every future external action must consume.

    Every field except ``owner_email`` and
    ``rollback_or_undo_instruction`` (both nullable) is required.
    ``audit_result_row_id`` is created AFTER execution -- callers
    pre-build the request with this slot left as ``None`` and the
    executor stamps it on completion.
    """

    approval_id: str
    consent_grant_id: str
    payload_hash: str
    tool_id: str
    owner_email: str | None
    asset_shield_pass: bool
    policy_allowlist_pass: bool
    audit_preflight_row_id: str
    audit_result_row_id: str | None
    rollback_or_undo_instruction: str | None


# ── Refusal helper (design-only; does not actually execute) ──────────


class ControlledExecutionDesignError(Exception):
    """Raised when a request fails the design contract.

    PR-8 ships the validation function so future executors can call
    it as a hard wall. PR-8 itself does not execute anything.
    """


def validate_controlled_execution_request(
    req: ControlledExecutionRequest,
) -> None:
    """Validate the request against the locked contract. Raises on failure.

    This is the PURE validator. No Asset Shield call, no policy
    lookup, no DB hop -- the executor must populate the booleans by
    actually calling those services and pass the results in.
    """
    if req.tool_id not in WRITE_TOOLS:
        raise ControlledExecutionDesignError(
            f"tool_id_not_in_allowlist: {req.tool_id!r} -- WRITE_TOOLS "
            f"is currently {sorted(WRITE_TOOLS)} (Phase 3 not unlocked)"
        )
    if not req.asset_shield_pass:
        raise ControlledExecutionDesignError(
            "asset_shield_pass_required"
        )
    if not req.policy_allowlist_pass:
        raise ControlledExecutionDesignError(
            "policy_allowlist_pass_required"
        )
    if not req.approval_id:
        raise ControlledExecutionDesignError("approval_id_required")
    if not req.consent_grant_id:
        raise ControlledExecutionDesignError("consent_grant_id_required")
    if not req.payload_hash or len(req.payload_hash) != 64:
        raise ControlledExecutionDesignError(
            "payload_hash_required_sha256_hex"
        )
    if not req.audit_preflight_row_id:
        raise ControlledExecutionDesignError(
            "audit_preflight_row_id_required"
        )
    # owner_email may be None for tools not bound to an account.
    # rollback_or_undo_instruction may be None for unrecoverable
    # actions (those should be rejected by policy, not by this
    # validator).
    return None
