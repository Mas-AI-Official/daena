"""Guard every tool call with ``permission_resolver`` + ``ApprovalQueue``.

This is the gate between "LLM wants to call a tool" and the tool
actually running. Every agentic dispatch must pass through
``guard_tool_dispatch()`` before the dispatcher layer.

Outcome matrix (see ``permission_resolver.py`` for the full rules):

* ``AUTO_PROCEED``  -- run the tool, existing flow unchanged.
* ``REFUSE``        -- BLOCK pref or catastrophic risk. Return a
                       structured refusal. Nothing runs.
* ``REQUEST_INPUT`` -- Governance pipeline wants a human decision.
                       We create a ``GoaRequest`` + ``PendingApproval``
                       row so ``/governance/approvals`` lights up and
                       the operator can act. Tool does NOT run this
                       call; caller decides how to surface it.

Why a separate helper instead of doing it inline in
``ToolUseLoop._execute_tool``? Two reasons:

1. **Shared surface.** Stage 7.5 of ``chat_orchestrator`` sometimes
   dispatches through ``ExecutionService.execute_tool()``, not
   through the tool-use-loop. Both paths need the same guard, and
   the guard logic itself belongs in one place so it stays
   auditable.
2. **Testability.** Unit tests can exercise the outcome matrix
   without spinning up the full loop + LLM providers.

The helper always returns a ``GuardDecision`` (never raises for
permission reasons). Exceptions here would bypass the safety rail
and silently execute. If the approval system itself fails, we fall
closed: ``REFUSE`` wins so a gated tool never runs accidentally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.constants import GOVERNANCE_TIER_MAP, GovernanceMode, RiskLevel
from app.core.logging import get_logger
from app.services.permission_resolver import (
    EffectivePermission,
    ToolPermission,
    resolve_permission,
)

logger = get_logger(__name__)

# ``ToolCallClassifier`` emits risk as lowercase string. Normalise to
# the ``RiskLevel`` enum the resolver expects.
_RISK_STR_MAP: dict[str, RiskLevel] = {
    "none": RiskLevel.NONE,
    "low": RiskLevel.LOW,
    "medium": RiskLevel.MEDIUM,
    "high": RiskLevel.HIGH,
    "critical": RiskLevel.CRITICAL,
}


@dataclass
class GuardDecision:
    """What the guard decided for a single tool call."""

    outcome: EffectivePermission
    reason: str
    risk_tier: int
    risk_level: RiskLevel
    approval_id: UUID | None = None


def normalize_risk(risk_level_str: str | None) -> RiskLevel:
    """Map classifier's lowercase risk string to the ``RiskLevel`` enum.

    Unknown / missing values default to ``LOW`` rather than ``NONE`` so
    we're fail-cautious: an unclassified tool still respects governance.
    """
    if not risk_level_str:
        return RiskLevel.LOW
    return _RISK_STR_MAP.get(risk_level_str.lower(), RiskLevel.LOW)


def user_pref_from_dict(
    tool_name: str,
    extension_permissions: dict[str, Any] | None,
) -> ToolPermission | None:
    """Find the operator's per-tool preference for this tool.

    Handles the nested storage shape used by ``User.settings.extension_permissions``
    (see ``api/v1/connections.py`` and ``ExecutionService._get_user_tool_pref``)::

        {
            "<ext_slug>": {
                "default": "ALLOW" | "ASK_EACH_TIME" | "BLOCK",
                "tools":   { "<tool_name>": "ALLOW" | ... },
            },
            ...
        }

    Resolution order (most specific -> least):

    1. Any extension that explicitly names the tool in its ``tools`` map.
       This matches how the Connections UI renders per-tool pills.
    2. Flat ``{prefix: PERM}`` shorthand (for tests or simpler layouts).
    3. The extension's ``default`` when the tool name prefix matches the
       extension slug (e.g. ``file.read_file`` inherits ``filesystem``'s
       default).

    Returns ``None`` when nothing maps, so the resolver falls back to
    pure governance-mode semantics.
    """
    if not extension_permissions:
        return None

    def _coerce(raw: Any) -> ToolPermission | None:
        if raw is None:
            return None
        try:
            return ToolPermission(str(raw).upper())
        except (ValueError, AttributeError):
            return None

    # Tier 1: nested form — search every ext_slug for an explicit
    # per-tool entry. The user's intent is strongest when they named
    # the tool directly.
    for _ext_slug, cfg in extension_permissions.items():
        if isinstance(cfg, dict):
            tools = cfg.get("tools") or {}
            if tool_name in tools:
                coerced = _coerce(tools[tool_name])
                if coerced is not None:
                    return coerced

    # Tier 2: flat form — {tool_name: PERM} or {prefix: PERM}. Useful
    # for tests and simpler layouts that skip the ext_slug wrapper.
    if tool_name in extension_permissions:
        coerced = _coerce(extension_permissions[tool_name])
        if coerced is not None:
            return coerced
    prefix = tool_name.split(".", 1)[0] if "." in tool_name else tool_name
    if prefix in extension_permissions:
        raw = extension_permissions[prefix]
        if not isinstance(raw, dict):
            coerced = _coerce(raw)
            if coerced is not None:
                return coerced
        else:
            # Tier 3: extension's ``default`` fires when the prefix
            # matches the slug and the tool wasn't named explicitly.
            coerced = _coerce(raw.get("default"))
            if coerced is not None:
                return coerced

    return None


async def guard_tool_dispatch(
    *,
    db: Any,
    user_id: UUID,
    tenant_id: UUID,
    session_id: UUID | None,
    tool_name: str,
    params: dict[str, Any],
    risk_level_str: str | None,
    governance_mode: GovernanceMode,
    autopilot_active: bool,
    extension_permissions: dict[str, Any] | None,
) -> GuardDecision:
    """Run the resolver and record an approval row on ``REQUEST_INPUT``.

    This is idempotent w.r.t. the resolver: same inputs yield the same
    ``outcome``. Side effect on ``REQUEST_INPUT`` is one row written
    to ``goa_requests`` + one to ``pending_approvals``.

    Returns a ``GuardDecision``. The caller inspects ``outcome``:

    * ``AUTO_PROCEED`` -- just run the tool.
    * ``REFUSE``       -- skip execution, surface ``reason`` to caller.
    * ``REQUEST_INPUT``-- skip execution, surface ``approval_id`` + ``reason``.
                         The frontend will show an inline approval card
                         and ``/governance/approvals`` will list it.
    """
    risk = normalize_risk(risk_level_str)
    user_pref = user_pref_from_dict(tool_name, extension_permissions)

    outcome = resolve_permission(
        governance_mode=governance_mode,
        autopilot_active=autopilot_active,
        tool_risk=risk,
        user_pref=user_pref,
    )

    # Compute the tier from the same table so the reason message is
    # consistent with the resolver's decision.
    tier_map = GOVERNANCE_TIER_MAP.get(governance_mode, {})
    tier = tier_map.get(risk, 0)

    if outcome == EffectivePermission.AUTO_PROCEED:
        return GuardDecision(
            outcome=outcome,
            reason=(
                f"auto-proceed at tier {tier} "
                f"({governance_mode.value}/{risk.value})"
            ),
            risk_tier=tier,
            risk_level=risk,
        )

    if outcome == EffectivePermission.REFUSE:
        reason = (
            "Tool blocked by per-tool permission (BLOCK)."
            if user_pref == ToolPermission.BLOCK
            else f"Governance refused tool at tier {tier}."
        )
        logger.info(
            "permission_dispatch.refused",
            tool=tool_name,
            risk=risk.value,
            pref=user_pref.value if user_pref else None,
            governance_mode=governance_mode.value,
        )
        return GuardDecision(
            outcome=outcome,
            reason=reason,
            risk_tier=tier,
            risk_level=risk,
        )

    # REQUEST_INPUT: write the approval row so the operator can decide.
    # If the approval system itself is broken, fail closed to REFUSE
    # rather than leak the tool call through the gate.
    try:
        from app.services.approval import ApprovalService

        svc = ApprovalService(db)
        approval = await svc.request_approval(
            tenant_id=tenant_id,
            user_id=user_id,
            action_type=tool_name,
            action_params=params,
            risk_level=risk.value,
            governance_tier=tier,
            session_id=session_id,
            context={
                "source": "permission_dispatch",
                "user_pref": user_pref.value if user_pref else None,
                "governance_mode": governance_mode.value,
                "autopilot_active": autopilot_active,
            },
        )
        approval_id_raw = approval.get("id") if isinstance(approval, dict) else None
        approval_id: UUID | None
        if approval_id_raw is None:
            approval_id = None
        elif isinstance(approval_id_raw, UUID):
            approval_id = approval_id_raw
        else:
            try:
                approval_id = UUID(str(approval_id_raw))
            except (ValueError, TypeError):
                approval_id = None

        logger.info(
            "permission_dispatch.approval_pending",
            tool=tool_name,
            approval_id=str(approval_id) if approval_id else None,
            tier=tier,
            risk=risk.value,
        )
        return GuardDecision(
            outcome=outcome,
            reason=f"Approval required at tier {tier} ({risk.value}).",
            risk_tier=tier,
            risk_level=risk,
            approval_id=approval_id,
        )
    except Exception as exc:
        logger.error(
            "permission_dispatch.approval_write_failed",
            tool=tool_name,
            error=str(exc),
            exc_info=True,
        )
        # Fail closed. A gated tool never runs if the gate is broken.
        return GuardDecision(
            outcome=EffectivePermission.REFUSE,
            reason=(
                "Approval system unavailable; failing closed to protect "
                "governance policy. See server logs for details."
            ),
            risk_tier=tier,
            risk_level=risk,
        )
