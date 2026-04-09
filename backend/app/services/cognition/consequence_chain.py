"""ConsequenceChain -- Howard Marks second-order thinking.

"First-level thinking says: 'It's a good company; let's buy the stock.'
Second-level thinking says: 'It's a good company, but everyone thinks
it's a great company, so it's overpriced. Let's sell.'"

Before any mutating action, Daena asks:
    "If I do X, what happens next? And then what? And then what?"

Chase consequences 2-3 levels deep. If any consequence is bad + irreversible,
flag it for governance review before proceeding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Consequence:
    """A predicted consequence of an action."""
    order: int  # 1 = first-order, 2 = second-order, etc.
    description: str
    probability: str = "likely"  # "certain", "likely", "possible", "unlikely"
    severity: str = "low"  # "none", "low", "medium", "high", "critical"
    reversible: bool = True
    governance_flag: bool = False  # True if needs governance review


class ConsequenceChain:
    """Analyze second and third-order effects of actions.

    Howard Marks: most people think first-order only.
    Daena thinks 2-3 levels deep.
    """

    async def analyze(
        self,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> list[Consequence]:
        """Predict consequences of an action 2-3 levels deep.

        Returns list of Consequence objects, ordered by severity.
        Any consequence that is high-severity + irreversible gets
        governance_flag=True.
        """
        consequences = []
        action_lower = action.lower()

        # File modification consequences
        if any(kw in action_lower for kw in ["write", "modify", "edit", "update file"]):
            consequences.extend([
                Consequence(1, "File content changes", "certain", "low", True),
                Consequence(2, "Dependent code/config may break", "possible", "medium", True),
                Consequence(3, "Users of this file may need to update", "possible", "low", True),
            ])

        # Deletion consequences
        if any(kw in action_lower for kw in ["delete", "remove", "drop"]):
            consequences.extend([
                Consequence(1, "Resource is removed", "certain", "high", False),
                Consequence(2, "References to this resource break", "likely", "high", False),
                Consequence(3, "Recovery requires backup restoration", "certain", "medium", False, True),
            ])

        # Deployment consequences
        if any(kw in action_lower for kw in ["deploy", "push", "release"]):
            consequences.extend([
                Consequence(1, "New version is live for users", "certain", "medium", True),
                Consequence(2, "Bugs in new version affect all users", "possible", "high", True),
                Consequence(3, "Rollback needed if critical issues found", "possible", "medium", True, True),
            ])

        # Installation consequences
        if any(kw in action_lower for kw in ["install", "pip install", "npm install"]):
            consequences.extend([
                Consequence(1, "New dependency added to environment", "certain", "low", True),
                Consequence(2, "Version conflict with existing packages", "possible", "medium", True),
                Consequence(3, "Supply chain risk from new dependency", "unlikely", "high", True),
            ])

        # API/external call consequences
        if any(kw in action_lower for kw in ["send", "post", "email", "message", "notify"]):
            consequences.extend([
                Consequence(1, "External system receives data", "certain", "medium", False),
                Consequence(2, "Recipients act on the information", "likely", "medium", False),
                Consequence(3, "Cannot unsend once delivered", "certain", "high", False, True),
            ])

        # Database consequences
        if any(kw in action_lower for kw in ["migrate", "alter table", "drop table", "update table"]):
            consequences.extend([
                Consequence(1, "Database schema changes", "certain", "high", False),
                Consequence(2, "Running queries may fail", "possible", "high", False),
                Consequence(3, "Data loss if migration has bugs", "possible", "critical", False, True),
            ])

        if not consequences:
            consequences.append(
                Consequence(1, "Action executes with expected result", "likely", "low", True)
            )

        # Flag high-severity + irreversible for governance
        for c in consequences:
            if c.severity in ("high", "critical") and not c.reversible:
                c.governance_flag = True

        # Sort by severity
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}
        consequences.sort(
            key=lambda c: (severity_order.get(c.severity, 0), c.order),
            reverse=True,
        )

        flagged = sum(1 for c in consequences if c.governance_flag)
        if flagged:
            logger.info(
                "consequence_chain.governance_flags",
                action=action[:100],
                flagged=flagged,
            )

        return consequences
