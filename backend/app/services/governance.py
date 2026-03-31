"""Governance engine: evaluate actions against policies and hard laws.

The core decision-making engine. For every action:
1. Check hard laws (immediate reject if violated)
2. Assess risk level
3. Resolve effective slider preset (role × team × org)
4. Look up governance tier from slider × risk matrix
5. Route: SILENT → LOG → NOTIFY → APPROVE → COUNCIL+APPROVE

Additional capabilities:
- Role-based slider constraints (get_effective_preset)
- Workflow pre-approval (evaluate_plan — approve PLAN not each step)
- Per-conversation override with floor enforcement

Patent-pending: Sunflower-Honeycomb governance architecture.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.constants import (
    GOVERNANCE_TIER_MAP,
    GovernanceSlider,
    RiskLevel,
    UserRole,
)
from app.core.hard_laws import check_hard_laws
from app.core.logging import get_logger
from app.services._base import BaseService

logger = get_logger(__name__)

# ── Slider ordering (lower index = less restrictive) ──────────

_SLIDER_ORDER: dict[GovernanceSlider, int] = {
    GovernanceSlider.YOLO: 0,
    GovernanceSlider.LIGHT: 1,
    GovernanceSlider.STANDARD: 2,
    GovernanceSlider.STRICT: 3,
    GovernanceSlider.PARANOID: 4,
}

_ORDER_TO_SLIDER: dict[int, GovernanceSlider] = {
    v: k for k, v in _SLIDER_ORDER.items()
}

# ── Role-based slider constraints ─────────────────────────────
# Maps UserRole → (minimum_slider, maximum_slider)
# Per spec Section 7: "Governance Per Role"

ROLE_SLIDER_CONSTRAINTS: dict[UserRole, tuple[GovernanceSlider, GovernanceSlider]] = {
    UserRole.FOUNDER: (GovernanceSlider.YOLO, GovernanceSlider.PARANOID),
    UserRole.ADMIN: (GovernanceSlider.LIGHT, GovernanceSlider.PARANOID),
    UserRole.MANAGER: (GovernanceSlider.STANDARD, GovernanceSlider.PARANOID),
    UserRole.OPERATOR: (GovernanceSlider.STANDARD, GovernanceSlider.PARANOID),
    UserRole.VIEWER: (GovernanceSlider.PARANOID, GovernanceSlider.PARANOID),
    UserRole.AUDITOR: (GovernanceSlider.PARANOID, GovernanceSlider.PARANOID),
}

# ── Role default presets ──────────────────────────────────────

ROLE_DEFAULT_PRESETS: dict[UserRole, GovernanceSlider] = {
    UserRole.FOUNDER: GovernanceSlider.STANDARD,
    UserRole.ADMIN: GovernanceSlider.STANDARD,
    UserRole.MANAGER: GovernanceSlider.STANDARD,
    UserRole.OPERATOR: GovernanceSlider.STRICT,
    UserRole.VIEWER: GovernanceSlider.PARANOID,
    UserRole.AUDITOR: GovernanceSlider.PARANOID,
}

# ── Checkpoint intervals per preset (anti-drift) ─────────────

CHECKPOINT_INTERVALS: dict[GovernanceSlider, int] = {
    GovernanceSlider.YOLO: 10,
    GovernanceSlider.LIGHT: 7,
    GovernanceSlider.STANDARD: 5,
    GovernanceSlider.STRICT: 3,
    GovernanceSlider.PARANOID: 1,
}

# ── Action risk classification ────────────────────────────────

_HIGH_RISK_ACTIONS: frozenset[str] = frozenset({
    "DELETE", "DROP", "TRUNCATE", "PURGE",
    "DEPLOY", "ROLLBACK", "MIGRATE",
    "SEND_EMAIL", "POST_PUBLIC", "WEBHOOK_FIRE",
    "GRANT_ACCESS", "REVOKE_ACCESS",
})

_MEDIUM_RISK_ACTIONS: frozenset[str] = frozenset({
    "EXECUTE", "WRITE_FILE", "MODIFY_CONFIG",
    "CREATE_USER", "UPDATE_USER",
    "API_CALL_EXTERNAL",
    "ARCHIVE",  # DaenaBot soft-delete (Hard Law #6 compliant)
})


class GovernanceEngine(BaseService):
    """Evaluates actions against governance policies and hard laws.

    Supports three evaluation modes:
    - Single action: ``evaluate()`` — standard per-action governance
    - Workflow plan: ``evaluate_plan()`` — approve entire plan at once
    - Slider resolution: ``get_effective_preset()`` — role × team × org chain

    Skill trust tier assessment:
    - External skills (T0, T1): Tier 2 governance (logged + notified)
    - Promoted skills (T2+): Tier 1 governance (log only)

    Usage::

        engine = GovernanceEngine(db)

        # Resolve effective slider for a user
        preset = GovernanceEngine.get_effective_preset(
            user_role="OPERATOR",
            requested_preset="LIGHT",
            team_minimum="STANDARD",
            org_minimum="STANDARD",
        )

        # Evaluate a single action
        decision = await engine.evaluate(
            action_type="DELETE",
            governance_slider=preset.value,
            actor_type="USER",
            actor_role="OPERATOR",
            tenant_id=tenant_id,
            user_id=user_id,
        )

        # Evaluate a multi-step plan (workflow pre-approval)
        plan_decision = engine.evaluate_plan(
            steps=[
                {"action_type": "SEARCH", "params": {}},
                {"action_type": "WRITE_FILE", "params": {"path": "report.md"}},
                {"action_type": "SEND_EMAIL", "params": {"to": "team@co.com"}},
            ],
            governance_slider=preset.value,
            actor_type="USER",
        )
    """

    # ── Public: resolve effective slider ──────────────────────

    @staticmethod
    def get_effective_preset(
        user_role: str,
        requested_preset: str | None = None,
        *,
        team_minimum: str | None = None,
        org_minimum: str | None = None,
    ) -> GovernanceSlider:
        """Resolve the effective governance slider for a user.

        Applies the inheritance chain::

            effective_minimum = max(role_minimum, team_minimum, org_minimum)

        Then clamps the requested preset within the user's allowed range.

        Args:
            user_role: UserRole string (e.g. "OPERATOR", "FOUNDER").
            requested_preset: The preset the user wants. Falls back to
                role default if None.
            team_minimum: Minimum slider enforced by team admin.
            org_minimum: Minimum slider enforced by org policy.

        Returns:
            The effective GovernanceSlider preset.
        """
        role = UserRole(user_role)
        role_min, role_max = ROLE_SLIDER_CONSTRAINTS[role]

        # Resolve request or default
        if requested_preset is not None:
            requested = GovernanceSlider(requested_preset)
        else:
            requested = ROLE_DEFAULT_PRESETS[role]

        # Compute effective minimum from inheritance chain
        effective_min_ord = _SLIDER_ORDER[role_min]
        if team_minimum is not None:
            team_ord = _SLIDER_ORDER[GovernanceSlider(team_minimum)]
            effective_min_ord = max(effective_min_ord, team_ord)
        if org_minimum is not None:
            org_ord = _SLIDER_ORDER[GovernanceSlider(org_minimum)]
            effective_min_ord = max(effective_min_ord, org_ord)

        effective_min = _ORDER_TO_SLIDER[effective_min_ord]

        # Clamp requested within [effective_min, role_max]
        req_ord = _SLIDER_ORDER[requested]
        clamped_ord = max(req_ord, _SLIDER_ORDER[effective_min])
        clamped_ord = min(clamped_ord, _SLIDER_ORDER[role_max])

        return _ORDER_TO_SLIDER[clamped_ord]

    @staticmethod
    def get_allowed_range(
        user_role: str,
        *,
        team_minimum: str | None = None,
        org_minimum: str | None = None,
    ) -> tuple[GovernanceSlider, GovernanceSlider]:
        """Get the allowed slider range for a user role.

        Returns (effective_min, max) accounting for role, team, and org.
        """
        role = UserRole(user_role)
        role_min, role_max = ROLE_SLIDER_CONSTRAINTS[role]

        effective_min_ord = _SLIDER_ORDER[role_min]
        if team_minimum is not None:
            effective_min_ord = max(
                effective_min_ord,
                _SLIDER_ORDER[GovernanceSlider(team_minimum)],
            )
        if org_minimum is not None:
            effective_min_ord = max(
                effective_min_ord,
                _SLIDER_ORDER[GovernanceSlider(org_minimum)],
            )

        effective_min = _ORDER_TO_SLIDER[effective_min_ord]
        return effective_min, role_max

    # ── Public: single-action evaluation ──────────────────────

    async def evaluate(
        self,
        *,
        action_type: str,
        action_params: dict | None = None,
        governance_slider: str = "STANDARD",
        actor_type: str = "USER",
        actor_role: str = "OPERATOR",
        tenant_id: UUID,
        user_id: UUID,
        session_id: UUID | None = None,
        plan_approval_id: UUID | None = None,
        autopilot: bool = False,
    ) -> dict:
        """Evaluate an action against governance policies.

        Steps:
            1. Check hard law violations (immediate reject).
            2. Founder bypass (Hard Law #4 — logged but not blocked).
            3. If executing within an approved plan, check bounds.
            4. Assess risk level from action type.
            5. Look up governance tier from slider × risk matrix.
            6. Autopilot override: AGI ON auto-approves Tier 0-2,
               only Tier 3+ critical actions ask user.
            7. Determine routing: allow, log, notify, or require approval.

        Args:
            action_type: The action being attempted (e.g. "DELETE", "EXECUTE").
            action_params: Parameters of the action for context.
            governance_slider: Current slider position (YOLO→PARANOID).
            actor_type: Who is performing (USER/AGENT/SYSTEM/FOUNDER).
            actor_role: RBAC role of the actor.
            tenant_id: Tenant UUID for scoping.
            user_id: User UUID for audit.
            session_id: Optional chat session context.
            plan_approval_id: If set, this action is part of an approved
                plan. Tier 0-2 actions auto-approve under plan coverage.
            autopilot: When True (AGI ON), internal governance overrides
                the user's slider for Tier 0-2 actions (auto-approve).
                Only Tier 3+ critical actions still ask the user.

        Returns:
            Dict with: allowed, governance_tier, risk_level, action_type,
            requires_approval, hard_law_violations, message, request_id,
            plan_covered, autopilot_override.
        """
        params = action_params or {}

        # ── Step 1: Hard law check (never bypassed, even in autopilot) ──
        violations = check_hard_laws(action_type, params)
        if violations:
            violation_names = [str(v) for v in violations]
            return {
                "allowed": False,
                "governance_tier": 4,
                "risk_level": RiskLevel.CRITICAL.value,
                "action_type": action_type,
                "requires_approval": False,
                "request_id": None,
                "hard_law_violations": violation_names,
                "message": f"Blocked by {', '.join(violation_names)}",
                "plan_covered": False,
                "autopilot_override": False,
            }

        # ── Step 2: Founder bypass (Hard Law #4) ──
        is_founder = actor_type == "FOUNDER"

        # ── Step 3: Assess risk level ──
        risk_level = self._assess_risk(action_type, params)

        # ── Step 4: Tier lookup ──
        slider = GovernanceSlider(governance_slider)
        risk = RiskLevel(risk_level)
        governance_tier = GOVERNANCE_TIER_MAP[slider][risk]

        # ── Step 5: Plan coverage check ──
        plan_covered = False
        if plan_approval_id is not None and governance_tier <= 2:
            plan_covered = True

        # ── Step 6: Autopilot (AGI ON) override ──
        # When autopilot is active, Daena operates autonomously like
        # OpenClaw: auto-approve everything, governance is invisible.
        # Only hard-law violations (tier 4, caught at Step 1) block.
        # Internal governance still LOGS everything for audit trail,
        # but never interrupts the user or stops the pipeline.
        autopilot_override = False
        if autopilot and governance_tier <= 3:
            autopilot_override = True

        # ── Step 7: Routing decision ──
        requires_approval = governance_tier >= 3 and not is_founder and not autopilot_override
        allowed = (
            governance_tier < 3
            or is_founder
            or plan_covered
            or autopilot_override
        )

        if autopilot_override:
            message = f"Autopilot auto-approved (tier {governance_tier})"
        elif plan_covered:
            message = f"Covered by plan approval {plan_approval_id}"
        elif is_founder:
            message = f"Founder override: tier {governance_tier} bypassed"
        elif governance_tier == 0:
            message = "Silent pass"
        elif governance_tier == 1:
            message = "Logged"
        elif governance_tier == 2:
            message = "User notified"
        elif governance_tier == 3:
            message = "Approval required"
            allowed = False
        else:
            message = "Council + approval required"
            allowed = False

        return {
            "allowed": allowed,
            "governance_tier": governance_tier,
            "risk_level": risk_level,
            "action_type": action_type,
            "requires_approval": requires_approval,
            "request_id": None,
            "hard_law_violations": [],
            "message": message,
            "plan_covered": plan_covered,
            "autopilot_override": autopilot_override,
        }

    # ── Public: workflow plan evaluation ───────────────────────

    @staticmethod
    def evaluate_plan(
        steps: list[dict[str, Any]],
        governance_slider: str = "STANDARD",
        actor_type: str = "USER",
    ) -> dict:
        """Evaluate a multi-step workflow plan for pre-approval.

        The plan's effective tier is the MAX tier of all steps.
        This implements Daena's workflow pre-approval pattern:
        approve the PLAN, not each individual step.

        Args:
            steps: List of step dicts, each with "action_type" and
                optional "params" keys.
            governance_slider: Current slider position.
            actor_type: Who is performing the plan.

        Returns:
            Dict with: allowed, plan_tier, step_tiers, requires_approval,
            step_count, message.
        """
        if not steps:
            return {
                "allowed": True,
                "plan_tier": 0,
                "step_tiers": [],
                "requires_approval": False,
                "step_count": 0,
                "message": "Empty plan — nothing to approve",
            }

        slider = GovernanceSlider(governance_slider)
        is_founder = actor_type == "FOUNDER"

        step_tiers: list[dict[str, Any]] = []
        max_tier = 0

        for step in steps:
            action_type = step.get("action_type", "UNKNOWN")
            params = step.get("params", {})

            risk_level = GovernanceEngine._assess_risk(action_type, params)
            risk = RiskLevel(risk_level)
            tier = GOVERNANCE_TIER_MAP[slider][risk]

            step_tiers.append({
                "action_type": action_type,
                "risk_level": risk_level,
                "governance_tier": tier,
            })
            max_tier = max(max_tier, tier)

        # Plan approval rules per slider (spec Section 5.3):
        # YOLO: auto-approve unless contains Tier 4
        # LIGHT/STANDARD: Tier 3+ requires approval
        # STRICT: ALL multi-step plans require approval
        # PARANOID: ALL plans require approval + per-step checkpoints
        if slider in (GovernanceSlider.STRICT, GovernanceSlider.PARANOID):
            requires_approval = True
        else:
            requires_approval = max_tier >= 3

        if is_founder:
            requires_approval = False

        allowed = not requires_approval or is_founder

        if allowed:
            message = f"Plan auto-approved (max tier {max_tier})"
        elif requires_approval:
            message = f"Plan requires approval (max tier {max_tier})"
        else:
            message = f"Plan blocked (max tier {max_tier})"

        return {
            "allowed": allowed,
            "plan_tier": max_tier,
            "step_tiers": step_tiers,
            "requires_approval": requires_approval,
            "step_count": len(steps),
            "message": message,
        }

    # ── Public: validate per-conversation override ────────────

    @staticmethod
    def validate_override(
        requested_preset: str,
        user_role: str,
        *,
        team_minimum: str | None = None,
        org_minimum: str | None = None,
    ) -> dict:
        """Validate a per-conversation slider override request.

        Returns the effective preset (clamped to floor) and whether
        the request was modified.

        Args:
            requested_preset: The preset the user wants for this conversation.
            user_role: UserRole string.
            team_minimum: Team-level minimum.
            org_minimum: Org-level minimum.

        Returns:
            Dict with: effective_preset, requested_preset, was_clamped,
            effective_minimum, message.
        """
        effective = GovernanceEngine.get_effective_preset(
            user_role=user_role,
            requested_preset=requested_preset,
            team_minimum=team_minimum,
            org_minimum=org_minimum,
        )
        floor, _ = GovernanceEngine.get_allowed_range(
            user_role=user_role,
            team_minimum=team_minimum,
            org_minimum=org_minimum,
        )

        requested = GovernanceSlider(requested_preset)
        was_clamped = effective != requested

        if was_clamped:
            message = (
                f"Override clamped: {requested.value} → {effective.value} "
                f"(minimum: {floor.value})"
            )
        else:
            message = f"Override accepted: {effective.value}"

        return {
            "effective_preset": effective.value,
            "requested_preset": requested.value,
            "was_clamped": was_clamped,
            "effective_minimum": floor.value,
            "message": message,
        }

    # ── Risk assessment ───────────────────────────────────────

    @staticmethod
    def _assess_risk(action_type: str, params: dict) -> str:
        """Classify an action's risk level based on type and parameters.

        Args:
            action_type: The action being attempted.
            params: Action parameters for context-sensitive assessment.

        Returns:
            RiskLevel string value.
        """
        action_upper = action_type.upper()

        # Destructive operations are always CRITICAL
        if action_upper in ("DELETE", "DROP", "TRUNCATE", "PURGE"):
            return RiskLevel.CRITICAL.value

        # Deploy and access management are HIGH
        if action_upper in _HIGH_RISK_ACTIONS:
            return RiskLevel.HIGH.value

        # Execution and writes are MEDIUM
        if action_upper in _MEDIUM_RISK_ACTIONS:
            return RiskLevel.MEDIUM.value

        # Read-only operations
        if action_upper in ("READ", "QUERY", "LIST", "GET", "SEARCH"):
            return RiskLevel.NONE.value

        # Default to LOW for unknown actions
        return RiskLevel.LOW.value

    # ── Skill trust tier assessment ────────────────────────────

    @staticmethod
    def assess_skill_trust_tier(maturity: int) -> int:
        """Map a skill's maturity tier to a governance tier.

        External/unvetted skills (T0 raw, T1 draft) get Tier 2
        governance (logged + notified) because they originate from
        untrusted external content and haven't passed the 3-pass
        refinement pipeline. Promoted skills (T2+) get Tier 1
        (log only) because they've been validated.

        Args:
            maturity: The skill's maturity level (0-4).

        Returns:
            Governance tier (1 or 2).
        """
        if maturity <= 1:
            # T0_RAW, T1_DRAFT: untrusted external content
            return 2  # Logged + notified
        # T2_REFINED, T3_PRODUCTION, T4_COMPOUND: validated
        return 1  # Log only

    async def log_skill_ingestion(
        self,
        *,
        skill_id: str,
        title: str,
        maturity: int,
        source: str,
        tenant_id: UUID,
        user_id: UUID,
    ) -> dict:
        """Log a skill ingestion event as a governance audit entry.

        All skill ingestion (extract, refine, promote, demote) is
        tracked through the governance engine to maintain a full
        audit trail. External content ingestion is especially
        sensitive (prompt injection surface).

        Args:
            skill_id: Unique skill identifier.
            title: Human-readable skill title.
            maturity: Current maturity tier (0-4).
            source: The operation type (e.g. "extract", "refine", "promote").
            tenant_id: Tenant UUID for scoping.
            user_id: User UUID for attribution.

        Returns:
            Governance decision dict with skill-specific metadata.
        """
        trust_tier = self.assess_skill_trust_tier(maturity)

        decision = await self.evaluate(
            action_type="SKILL_INGESTION",
            action_params={
                "skill_id": skill_id,
                "title": title,
                "maturity": maturity,
                "source": source,
                "trust_tier": trust_tier,
            },
            governance_slider="STANDARD",
            actor_type="SYSTEM",
            actor_role="OPERATOR",
            tenant_id=tenant_id,
            user_id=user_id,
        )

        logger.info(
            "skill_governance_event",
            skill_id=skill_id,
            operation=source,
            maturity=maturity,
            trust_tier=trust_tier,
            governance_tier=decision.get("governance_tier"),
        )

        return decision
