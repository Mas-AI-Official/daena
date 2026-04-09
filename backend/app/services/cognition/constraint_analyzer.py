"""ConstraintAnalyzer -- Hard vs Soft constraint identification.

Inspired by Mythos (sandbox escape) and Steve Jobs (Reality Distortion Field).

When a task seems impossible, most agents give up. Daena asks:
"Which constraints are REAL (governance/physics) vs ASSUMED (convention)?"

Then she relaxes the SOFT constraints and finds a creative alternative path.

CRITICAL RULE: HARD constraints (governance, security, the 9 immutable laws)
are NEVER relaxed. That's what makes Daena safe, unlike Mythos.

Example:
    Task: "Write config file"
    Error: "Permission denied on /etc/myapp.conf"

    Constraints:
    1. HARD: must not bypass system security (governance law)
    2. SOFT: config must be at /etc/myapp.conf  <-- THIS IS ASSUMED
    3. SOFT: config must be a single file         <-- THIS IS ASSUMED

    Relaxation:
    - Write to workspace dir instead: ./config/myapp.conf
    - Or write to user-writable dir: ~/.config/myapp/config
    - Set env var to point to new location

    Result: Task accomplished without violating governance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class ConstraintType(str, Enum):
    HARD = "hard"  # Governance, security, physics -- NEVER relax
    SOFT = "soft"  # Convention, assumption, preference -- CAN relax


@dataclass
class Constraint:
    """A constraint on the task."""
    description: str
    type: ConstraintType
    source: str = ""  # "governance", "user", "assumption", "convention", "technical"
    relaxable: bool = False
    alternative: str = ""  # What to do if relaxed


# Hard constraints that can NEVER be relaxed (from hard_laws.py)
HARD_CONSTRAINT_KEYWORDS = [
    "delete system files",
    "bypass security",
    "disable governance",
    "expose credentials",
    "send data externally without approval",
    "modify security settings",
    "execute untrusted code without sandbox",
    "access other tenants",
    "override hard laws",
]


class ConstraintAnalyzer:
    """Identifies and classifies constraints, then finds alternatives.

    The Mythos move: instead of accepting "impossible," ask which
    constraints are actually REAL vs just ASSUMED. Relax the assumed
    ones to find a creative path.

    But unlike Mythos: NEVER relax governance constraints.
    """

    async def analyze(
        self,
        task: str,
        error: str,
        attempted_approach: str = "",
    ) -> list[Constraint]:
        """Identify all constraints on a task and classify each.

        Returns list of Constraint objects with type (HARD/SOFT)
        and alternatives for soft constraints.
        """
        constraints = []

        # Always include governance hard constraints
        constraints.append(Constraint(
            description="Must not violate governance policies or hard laws",
            type=ConstraintType.HARD,
            source="governance",
            relaxable=False,
        ))

        # Analyze error for constraint patterns
        error_lower = error.lower() if error else ""

        # Permission/access constraints
        if any(kw in error_lower for kw in ["permission", "access", "denied", "forbidden"]):
            constraints.append(Constraint(
                description="Current path/resource requires elevated permissions",
                type=ConstraintType.SOFT,
                source="assumption",
                relaxable=True,
                alternative="Use a different path within workspace, or request access via governance",
            ))

        # Path constraints
        if any(kw in error_lower for kw in ["not found", "no such file", "path"]):
            constraints.append(Constraint(
                description="Assumed a specific file/directory location",
                type=ConstraintType.SOFT,
                source="assumption",
                relaxable=True,
                alternative="Search for the actual location, or create in workspace",
            ))

        # Format constraints
        if any(kw in error_lower for kw in ["format", "syntax", "parse", "invalid"]):
            constraints.append(Constraint(
                description="Content must be in a specific format",
                type=ConstraintType.SOFT,
                source="convention",
                relaxable=True,
                alternative="Try alternative format, or validate before writing",
            ))

        # Connection constraints
        if any(kw in error_lower for kw in ["connection", "timeout", "unreachable"]):
            constraints.append(Constraint(
                description="Must connect to external service",
                type=ConstraintType.SOFT,
                source="assumption",
                relaxable=True,
                alternative="Use local alternative, cached data, or retry with backoff",
            ))

        # Tool constraints
        if any(kw in error_lower for kw in ["not installed", "command not found", "no module"]):
            constraints.append(Constraint(
                description="Requires a specific tool/package to be installed",
                type=ConstraintType.SOFT,
                source="technical",
                relaxable=True,
                alternative="Install the tool, or use an alternative tool that achieves the same result",
            ))

        return constraints

    async def find_alternatives(
        self,
        task: str,
        failed_approach: str,
        root_causes: list[str] | None = None,
    ) -> list[str]:
        """Generate alternative approaches by relaxing soft constraints.

        This is the creative problem-solving step:
        1. Identify what constraints the failed approach assumed
        2. Classify as HARD vs SOFT
        3. For each SOFT constraint: propose an alternative that avoids it
        4. Verify alternatives don't violate HARD constraints
        """
        alternatives = []

        # Common creative alternatives based on failure patterns
        root_text = " ".join(root_causes or []).lower()

        if "permission" in root_text or "access" in root_text:
            alternatives.extend([
                "Use workspace-relative path instead of absolute",
                "Write to user-writable directory (~/.config/ or ./)",
                "Request elevation through governance approval flow",
            ])

        if "not found" in root_text or "missing" in root_text:
            alternatives.extend([
                "Search for resource location before using it",
                "Create the resource if it doesn't exist",
                "Use an alternative resource that serves the same purpose",
            ])

        if "timeout" in root_text or "connection" in root_text:
            alternatives.extend([
                "Check service health first, start if needed",
                "Use local fallback if remote is unavailable",
                "Retry with exponential backoff",
            ])

        if "install" in root_text or "module" in root_text:
            alternatives.extend([
                "Install the missing dependency first",
                "Use an alternative library that's already available",
                "Download and use a portable version",
            ])

        if not alternatives:
            # Generic creative alternatives
            alternatives.extend([
                "Re-observe actual system state (don't assume)",
                "Break task into smaller steps and try each independently",
                "Search web for how others solved similar problems",
            ])

        # Filter out any alternative that would violate hard constraints
        safe_alternatives = [
            alt for alt in alternatives
            if not self._violates_hard_constraint(alt)
        ]

        logger.info(
            "constraint_analyzer.alternatives",
            task=task[:100],
            count=len(safe_alternatives),
        )

        return safe_alternatives

    def _violates_hard_constraint(self, alternative: str) -> bool:
        """Check if an alternative would violate hard constraints."""
        alt_lower = alternative.lower()
        return any(kw in alt_lower for kw in HARD_CONSTRAINT_KEYWORDS)

    async def classify_action(self, action: str) -> ConstraintType:
        """Classify a proposed action as HARD or SOFT risk.

        Used by OODA Decide phase to determine how much governance
        to apply to each step.
        """
        action_lower = action.lower()

        # Check if action matches any hard constraint
        if any(kw in action_lower for kw in HARD_CONSTRAINT_KEYWORDS):
            return ConstraintType.HARD

        # Check for inherently risky actions
        risky_keywords = [
            "delete", "remove", "drop", "truncate", "format",
            "deploy", "publish", "send", "email", "push",
            "install globally", "modify system",
        ]
        if any(kw in action_lower for kw in risky_keywords):
            return ConstraintType.HARD

        return ConstraintType.SOFT
