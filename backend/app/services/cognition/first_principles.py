"""FirstPrinciples -- Elon Musk / Aristotle decomposition.

"I tend to approach things from a physics framework. Physics teaches you
to reason from first principles rather than by analogy." -- Elon Musk

Instead of "how is this usually done?" (analogy), ask:
"What is ACTUALLY true? What are the fundamental constraints?"

Then rebuild the solution from those truths only, discarding
all assumptions that aren't provably true.

SpaceX example: Instead of buying rockets at $65M each (analogy thinking),
Musk asked: "What are rockets made of?" (aluminum, titanium, copper, carbon fiber)
Raw materials cost: ~2% of the rocket price. First principles said rockets
could be built for a fraction of the market price. SpaceX proved it.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class FirstPrinciples:
    """Decompose problems to fundamental truths.

    Steps:
        1. List all assumptions about the problem
        2. Challenge each: is this PROVABLY true or just convention?
        3. Remove unproven assumptions
        4. Build solution from remaining truths only
    """

    async def decompose(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        prior_failures: list[str] | None = None,
    ) -> dict[str, Any]:
        """Decompose a task into first principles.

        Returns a structured analysis with:
        - assumptions: list of identified assumptions
        - truths: list of provably true constraints
        - false_assumptions: assumptions that can be challenged
        - rebuilt_approach: approach built from truths only
        """
        analysis = {
            "task": task,
            "assumptions": [],
            "truths": [],
            "false_assumptions": [],
            "rebuilt_approach": "",
        }

        # Identify common assumptions based on task patterns
        task_lower = task.lower()

        # File/path assumptions
        if any(kw in task_lower for kw in ["file", "write", "read", "path", "directory"]):
            analysis["assumptions"].extend([
                "File must be at a specific absolute path",
                "File must exist already",
                "File must be in a specific format",
                "Current user has write permissions",
            ])
            analysis["truths"].extend([
                "File needs to be readable by the consuming system",
                "Content must be valid for its purpose",
            ])

        # Deployment assumptions
        if any(kw in task_lower for kw in ["deploy", "production", "server", "cloud"]):
            analysis["assumptions"].extend([
                "Must deploy to a specific cloud provider",
                "Must use a specific deployment tool (Docker, K8s, etc.)",
                "Must deploy the entire application at once",
                "Must have a specific CI/CD pipeline",
            ])
            analysis["truths"].extend([
                "Application code must be accessible to the runtime",
                "Dependencies must be available in the runtime environment",
                "Health checks must pass after deployment",
            ])

        # Installation assumptions
        if any(kw in task_lower for kw in ["install", "setup", "configure"]):
            analysis["assumptions"].extend([
                "Must use the official installation method",
                "Must install system-wide",
                "Must use the latest version",
                "Must follow the documentation exactly",
            ])
            analysis["truths"].extend([
                "The tool must be executable in the current environment",
                "Required dependencies must be satisfied",
            ])

        # API/integration assumptions
        if any(kw in task_lower for kw in ["api", "connect", "integrate"]):
            analysis["assumptions"].extend([
                "Must use the official SDK/client",
                "Must authenticate with a specific method",
                "Must use a specific API version",
            ])
            analysis["truths"].extend([
                "Must communicate with the service endpoint",
                "Must provide valid credentials",
                "Must handle the response format",
            ])

        # Generic assumptions for any task
        analysis["assumptions"].extend([
            "Must follow the conventional approach",
            "Must complete in a single step",
            "Previous approach was fundamentally correct (just had a bug)",
        ])
        analysis["truths"].extend([
            "Task must achieve the stated goal",
            "Must not violate governance policies",
            "Must be verifiable (we can check if it worked)",
        ])

        # Mark assumptions challenged by prior failures
        if prior_failures:
            analysis["false_assumptions"].append(
                "Previous approach was correct -- it wasn't (it failed)"
            )
            analysis["false_assumptions"].append(
                "Conventional method works in this environment -- it didn't"
            )

        # Build approach from truths only
        truths_text = "; ".join(analysis["truths"])
        analysis["rebuilt_approach"] = (
            f"Build solution satisfying only proven constraints: {truths_text}. "
            f"Discard assumptions: {'; '.join(analysis['false_assumptions'] or analysis['assumptions'][:2])}. "
            f"Find the simplest path that satisfies the truths."
        )

        logger.info(
            "first_principles.decomposed",
            task=task[:100],
            assumptions=len(analysis["assumptions"]),
            truths=len(analysis["truths"]),
        )

        return analysis
