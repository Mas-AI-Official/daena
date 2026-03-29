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
        name="Governance Cannot Be Disabled",
        description="The governance engine cannot be fully disabled. Even YOLO mode still enforces "
                    "Hard Laws and logs CRITICAL-risk actions at Tier 2+.",
        enforcement="Governance engine startup validates minimum "
                    "enforcement levels for all slider positions.",
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


def check_hard_laws(action_type: str, params: dict) -> list[HardLaw]:
    """Check if an action would violate any Hard Laws.

    Args:
        action_type: The type of action being attempted.
        params: Parameters of the action.

    Returns:
        List of violated Hard Laws (empty if all pass).
    """
    violations: list[HardLaw] = []

    # Law 6: No permanent deletion
    if action_type in ("DELETE", "DROP", "TRUNCATE", "PURGE"):
        violations.append(HARD_LAWS[5])

    # Law 3: No unbounded execution
    if action_type == "EXECUTE" and not params.get("timeout"):
        violations.append(HARD_LAWS[2])

    # Law 7: Tenant isolation — enforced at middleware/DB level,
    # not at governance evaluation level. The evaluate() method already
    # receives tenant_id as a separate parameter; action_params don't
    # carry it. Checking here would cause false positives.

    return violations
