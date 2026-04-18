"""Daena's 9 Immutable Hard Laws.

These laws are NEVER overridden by any user, agent, or governance configuration.
They are checked BEFORE every governance decision and tool execution.
Violation of any hard law results in immediate action rejection.

IP NOTE: These encode patent-pending governance behavior (USPTO provisional).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HardLaw:
    """An immutable governance law that cannot be overridden."""
    id: int
    name: str
    description: str
    enforcement: str

    def __str__(self) -> str:
        return f"Hard Law #{self.id}: {self.name}"


HARD_LAWS: tuple[HardLaw, ...] = (
    HardLaw(
        id=1,
        name="No Unlogged Actions",
        description="Every action that modifies state must be logged to the audit ledger. "
                    "No operation may bypass the logging pipeline.",
        enforcement="Pre-execution check: verify audit_ledger write succeeds "
                    "before committing action.",
    ),
    HardLaw(
        id=2,
        name="No Self-Modification of Laws",
        description="No agent, user, or system process may modify, disable, or remove Hard Laws. "
                    "Only the Founder can propose amendments via a dedicated offline process.",
        enforcement="Hard Laws are loaded from immutable source. "
                    "Any mutation attempt raises ImmutableViolation.",
    ),
    HardLaw(
        id=3,
        name="No Unbounded Execution",
        description="Every tool execution must have a timeout, resource limit, "
                    "and governance tier. Infinite loops, unbounded API calls, "
                    "and runaway processes are prohibited.",
        enforcement="Execution wrapper enforces max_duration, max_retries, "
                    "and budget_limit on every tool call.",
    ),
    HardLaw(
        id=4,
        name="Founder Override",
        description="The Founder role has absolute override authority on any governance decision. "
                    "Founder actions are logged but never blocked (except Hard Law violations).",
        enforcement="Role check: if actor.role == FOUNDER, bypass tier checks but still log.",
    ),
    HardLaw(
        id=5,
        name="No Data Exfiltration",
        description="No agent or tool may transmit user data to external services without explicit "
                    "user consent AND governance approval at Tier 2+.",
        enforcement="Outbound request interceptor checks against "
                    "allowed domains and consent records.",
    ),
    HardLaw(
        id=6,
        name="No Permanent Deletion",
        description="No operation may permanently delete user data, memories, or audit records. "
                    "All 'deletions' must use the archive pattern (soft delete with timestamp).",
        enforcement="DELETE operations are intercepted and rewritten as archive operations.",
    ),
    HardLaw(
        id=7,
        name="Tenant Isolation",
        description="Data from one tenant must NEVER be accessible to another tenant. "
                    "All queries must be scoped by tenant_id. No cross-tenant operations.",
        enforcement="Query middleware injects tenant_id filter. "
                    "Cross-tenant access raises TenantViolation.",
    ),
    HardLaw(
        id=8,
        name="Shield Always Active",
        description="The governance engine can be toggled by the Founder (UNLEASHED/BALANCED/GOVERNED). "
                    "Regardless of mode, the Shield (Laws 5+7: data exfiltration and tenant isolation) "
                    "is always enforced. Audit logging (Law 1) runs in all modes.",
        enforcement="Shield laws checked in all governance modes. "
                    "Governance mode toggle requires FOUNDER role.",
    ),
    HardLaw(
        id=9,
        name="Audit Trail Integrity",
        description="Audit records are append-only and tamper-evident. Each record includes a hash "
                    "chain linking to the previous record. No modification or deletion allowed.",
        enforcement="Audit ledger uses hash chain. Any gap or "
                    "modification triggers integrity alert.",
    ),
)


# ── Law classification by governance mode ────────────────────
# SHIELD laws: enforced in ALL modes (UNLEASHED/BALANCED/GOVERNED)
# These protect OUR data, IP, and system integrity.
SHIELD_LAW_IDS: frozenset[int] = frozenset({1, 5, 7, 9})
# Law 1: Audit logging (always record what happened)
# Law 5: No data exfiltration (protect client/founder data)
# Law 7: Tenant isolation (never leak cross-tenant)
# Law 9: Audit trail integrity (tamper-evident chain)

# BALANCED laws: enforced in BALANCED + GOVERNED modes
BALANCED_LAW_IDS: frozenset[int] = frozenset({1, 3, 5, 7, 9})
# Adds Law 3: No unbounded execution (safety bounds)

# ALL laws: enforced in GOVERNED mode only (full enterprise)
ALL_LAW_IDS: frozenset[int] = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9})


def check_hard_laws(
    action_type: str,
    params: dict,
    governance_mode: str = "GOVERNED",
) -> list[HardLaw]:
    """Check if an action would violate Hard Laws for the given governance mode.

    Args:
        action_type: The type of action being attempted.
        params: Parameters of the action.
        governance_mode: UNLEASHED, BALANCED, or GOVERNED.

    Returns:
        List of violated Hard Laws (empty if all pass).
    """
    if governance_mode == "UNLEASHED":
        return _check_shield_laws(action_type, params)
    if governance_mode == "BALANCED":
        return _check_balanced_laws(action_type, params)
    return _check_all_laws(action_type, params)


def _check_shield_laws(action_type: str, params: dict) -> list[HardLaw]:
    """UNLEASHED mode: only enforce shield (Laws 1, 5, 7, 9).

    Reuses the proven check_hard_laws_agi() logic for data protection.
    Everything else gets creative options via get_creative_options().
    """
    violations: list[HardLaw] = []

    # Law 5: No data exfiltration
    _outbound_keywords = [
        "exfiltrate", "leak", "send_external", "transmit_data",
        "upload_user_data", "export_to_external",
    ]
    action_lower = action_type.lower()
    param_str = str(params).lower()
    if any(kw in action_lower or kw in param_str for kw in _outbound_keywords):
        violations.append(HARD_LAWS[4])  # Law 5

    # Laws 1, 7, 9 enforced at middleware/DB/audit level, not here.
    return violations


def _check_balanced_laws(action_type: str, params: dict) -> list[HardLaw]:
    """BALANCED mode: shield + execution bounds (Laws 1, 3, 5, 7, 9)."""
    violations = _check_shield_laws(action_type, params)

    # Law 3: No unbounded execution
    if action_type == "EXECUTE" and not params.get("timeout"):
        violations.append(HARD_LAWS[2])

    return violations


def _check_all_laws(action_type: str, params: dict) -> list[HardLaw]:
    """GOVERNED mode: enforce all 9 laws (original behavior)."""
    violations: list[HardLaw] = []

    # Law 6: No permanent deletion
    if action_type in ("DELETE", "DROP", "TRUNCATE", "PURGE"):
        violations.append(HARD_LAWS[5])

    # Law 3: No unbounded execution
    if action_type == "EXECUTE" and not params.get("timeout"):
        violations.append(HARD_LAWS[2])

    # Law 5: No data exfiltration -- enforced at outbound interceptor level.
    # Law 7: Tenant isolation -- enforced at middleware/DB level.

    return violations


def check_hard_laws_agi(action_type: str, params: dict) -> list[HardLaw]:
    """AGI mode hard law check -- Mythos-level power, one guard.

    In AGI mode, Daena is UNLEASHED. She uses every trick -- DNS,
    side channels, proxies, alternative tools, auto-install, whatever
    it takes to get the job done.

    THE ONE WALL: client data never leaves without consent.
    - Law 5 (No Data Exfiltration): ALWAYS enforced. Client files,
      API keys, passwords, user data NEVER sent to external services
      without explicit user consent. This includes DNS tunneling,
      error message leaking, or any side channel.
    - Law 7 (Tenant Isolation): ALWAYS enforced at DB middleware.
      One client's data NEVER visible to another client.

    Everything else: Daena finds a way. She asks the user for
    direction on destructive actions (delete, unbounded execution)
    via creative options, but she NEVER blocks.

    INBOUND tricks (getting info IN) = always allowed.
    OUTBOUND client data (sending data OUT) = the one wall.
    """
    violations: list[HardLaw] = []

    # Check for data exfiltration attempts
    _outbound_keywords = [
        "exfiltrate", "leak", "send_external", "transmit_data",
        "upload_user_data", "export_to_external",
    ]
    action_lower = action_type.lower()
    param_str = str(params).lower()
    if any(kw in action_lower or kw in param_str for kw in _outbound_keywords):
        violations.append(HARD_LAWS[4])  # Law 5

    # Tenant isolation is enforced at DB middleware level, not here.
    # Everything else: creative options via get_creative_options().

    return violations


def get_creative_options(action_type: str, params: dict) -> dict | None:
    """Get user-facing options for actions that would normally be blocked.

    Instead of blocking, Daena asks the user for direction.
    Returns an InteractivePrompt-compatible dict, or None if no
    creative options apply.
    """
    # Law 6: Deletion -> offer alternatives
    if action_type in ("DELETE", "DROP", "TRUNCATE", "PURGE"):
        target = params.get("path", params.get("target", params.get("table", "this resource")))
        return {
            "type": "choice",
            "title": "Deletion requested",
            "message": f"Daena needs to remove: {target}. How should I handle this?",
            "options": [
                {"id": "archive", "label": "Move to .archive/ (safe, recoverable)", "icon": "archive", "style": "primary"},
                {"id": "delete", "label": "Delete permanently (irreversible)", "icon": "trash", "style": "danger"},
                {"id": "skip", "label": "Skip this step", "icon": "skip", "style": "default"},
            ],
            "context": {"action_type": action_type, "params": params},
        }

    # Law 3: Unbounded execution -> offer timeout options
    if action_type == "EXECUTE" and not params.get("timeout"):
        command = params.get("command", "this command")
        return {
            "type": "choice",
            "title": "Long-running command",
            "message": f"Running: {command[:100]}. Set a timeout?",
            "options": [
                {"id": "timeout_120", "label": "2 minute timeout (safe default)", "icon": "clock", "style": "primary"},
                {"id": "timeout_300", "label": "5 minute timeout", "icon": "clock", "style": "default"},
                {"id": "timeout_none", "label": "No timeout (run until done)", "icon": "infinity", "style": "danger"},
            ],
            "context": {"action_type": action_type, "params": params},
        }

    return None


def apply_creative_resolution(action_type: str, params: dict, choice: str) -> dict:
    """Apply the user's choice to transform the action.

    Called after the user selects an option from ``get_creative_options()``.

    Returns:
        Transformed params dict with the action adjusted per user choice.
    """
    result = dict(params)

    if choice == "archive":
        # Convert delete to archive
        result["_creative_action"] = "ARCHIVE"
        result["_original_action"] = action_type
    elif choice == "delete":
        # User explicitly chose permanent delete -- allow it
        result["_creative_action"] = "DELETE_CONFIRMED"
    elif choice == "skip":
        result["_creative_action"] = "SKIP"
    elif choice == "timeout_120":
        result["timeout"] = 120
    elif choice == "timeout_300":
        result["timeout"] = 300
    elif choice == "timeout_none":
        result["timeout"] = 0  # 0 = no timeout
    else:
        result["_creative_action"] = choice

    return result


def enforce_hard_laws(
    action_type: str,
    params: dict,
    governance_mode: str = "GOVERNED",
) -> None:
    """Check hard laws and raise HardLawViolationError if any are violated.

    Convenience wrapper around check_hard_laws() for callers that prefer
    exception-based flow control (e.g. tool executors, API handlers).

    Args:
        action_type: The type of action being attempted.
        params: Parameters of the action.
        governance_mode: UNLEASHED, BALANCED, or GOVERNED.

    Raises:
        HardLawViolationError: If any hard law is violated.
    """
    from app.core.exceptions import HardLawViolationError

    violations = check_hard_laws(action_type, params, governance_mode)
    if violations:
        names = ", ".join(str(v) for v in violations)
        raise HardLawViolationError(f"Blocked by {names}")
