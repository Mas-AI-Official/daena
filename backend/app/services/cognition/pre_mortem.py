"""PreMortem -- Imagine failure before it happens.

Gary Klein's Pre-Mortem technique: Before executing a strategy, imagine
it's 1 hour from now and the strategy FAILED completely. Why?

This surfaces risks that optimistic planning misses. Particularly valuable
for deployment, configuration, and irreversible actions.

Differs from risk assessment:
    Risk assessment: "What COULD go wrong?"
    Pre-mortem: "It DID go wrong. WHY?" (more vivid, catches more issues)
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# Common failure scenarios by action type
_FAILURE_SCENARIOS: dict[str, list[str]] = {
    "deploy": [
        "Missing environment variables in production",
        "Database migration failed or schema mismatch",
        "Health check fails after deploy (wrong port, missing dependency)",
        "Old version cached, new version not serving",
        "SSL/TLS certificate issue",
    ],
    "file_write": [
        "File was overwritten without backup",
        "Wrong encoding caused data corruption",
        "Path doesn't exist (parent directory missing)",
        "Disk full or quota exceeded",
        "Race condition with another process writing same file",
    ],
    "install": [
        "Package version conflict with existing dependencies",
        "Post-install script fails (needs build tools)",
        "Package not available for current platform/architecture",
        "Network timeout during download",
        "Installed to wrong environment (system vs venv)",
    ],
    "api_call": [
        "API key expired or rate-limited",
        "Response format changed from expected schema",
        "Endpoint URL changed or deprecated",
        "Payload too large for API limits",
        "Authentication token not refreshed",
    ],
    "database": [
        "Migration destroys existing data",
        "Schema change breaks active queries",
        "Connection pool exhausted under load",
        "Transaction deadlock with concurrent access",
        "Backup wasn't verified before destructive change",
    ],
    "terminal": [
        "Command not found (tool not installed)",
        "Wrong shell environment (bash vs powershell)",
        "Command hangs waiting for interactive input",
        "Exit code ignored, failure treated as success",
        "Working directory wrong (relative paths fail)",
    ],
    "configuration": [
        "Config format invalid (JSON vs YAML mismatch)",
        "Required fields missing from config",
        "Config not reloaded after change (service restart needed)",
        "Environment-specific config not separated from defaults",
        "Secrets exposed in config file",
    ],
    "default": [
        "Assumptions about system state are wrong",
        "Dependencies not available",
        "Permissions insufficient for required operations",
        "Concurrent modification by another process",
        "Network connectivity issues",
    ],
}


class PreMortem:
    """Imagine failure before executing.

    Before Daena acts on a strategy, she asks:
    "Imagine this failed completely. What went wrong?"

    Then adds safeguards for each identified risk.
    """

    async def analyze(
        self,
        strategy: Any,
        state: Any,
    ) -> list[str]:
        """Run pre-mortem analysis on a strategy.

        Returns list of risk descriptions that should be watched during execution.
        """
        risks = []

        # Determine action types from strategy steps
        steps = strategy.steps if hasattr(strategy, "steps") else []
        action_types = self._detect_action_types(steps, strategy.description)

        # Get failure scenarios for each action type
        for action_type in action_types:
            scenarios = _FAILURE_SCENARIOS.get(action_type, _FAILURE_SCENARIOS["default"])
            # Take top 2 most relevant scenarios per action type
            risks.extend(scenarios[:2])

        # Check for irreversibility (Bezos reversibility check)
        if not getattr(strategy, "reversible", True):
            risks.append("IRREVERSIBLE ACTION: Verify all preconditions before proceeding")

        # Check for prior failure context
        if hasattr(state, "attempted_strategies") and state.attempted_strategies:
            risks.append(
                f"Previous {len(state.attempted_strategies)} strategies failed. "
                "Ensure this approach is fundamentally different."
            )

        # Deduplicate and cap
        unique_risks = list(dict.fromkeys(risks))[:5]

        logger.info(
            "pre_mortem.risks_identified",
            strategy=getattr(strategy, "name", "unknown"),
            count=len(unique_risks),
        )

        return unique_risks

    def _detect_action_types(self, steps: list[str], description: str) -> list[str]:
        """Detect action types from strategy steps and description."""
        text = " ".join(steps).lower() + " " + description.lower()
        types = []

        if any(kw in text for kw in ["deploy", "ship", "release", "push", "production"]):
            types.append("deploy")
        if any(kw in text for kw in ["write", "create file", "save", "update file"]):
            types.append("file_write")
        if any(kw in text for kw in ["install", "pip", "npm", "apt", "brew"]):
            types.append("install")
        if any(kw in text for kw in ["api", "http", "request", "fetch", "endpoint"]):
            types.append("api_call")
        if any(kw in text for kw in ["database", "sql", "migration", "query", "table"]):
            types.append("database")
        if any(kw in text for kw in ["command", "terminal", "shell", "bash", "run"]):
            types.append("terminal")
        if any(kw in text for kw in ["config", "settings", "environment", "env"]):
            types.append("configuration")

        return types or ["default"]
