"""Criticality Classifier: gates actions for Autopilot mode.

Every action gets classified before auto-execution. This is the decision
boundary separating safe autonomous operation from actions that require
human confirmation.

Three levels:
    AUTO_PROCEED:       Safe, non-destructive, reversible. Execute immediately.
    NOTIFY_AFTER:       Safe but user should know. Execute then notify.
    PAUSE_FOR_APPROVAL: Needs explicit human approval before execution.

Governance slider interaction:
    YOLO:     NOTIFY_AFTER promoted to AUTO_PROCEED
    LOCKDOWN: Everything promoted to PAUSE_FOR_APPROVAL
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CriticalityLevel(str, Enum):
    """Classification level for autopilot actions."""
    AUTO_PROCEED = "auto_proceed"
    NOTIFY_AFTER = "notify_after"
    PAUSE_FOR_APPROVAL = "pause"


@dataclass(frozen=True)
class CriticalityRule:
    """Classification rule for a specific action type."""
    action_type: str
    level: CriticalityLevel
    reason: str


# Default classification matrix.
# Covers the common action types from DaenaBot agents and swarm subtasks.
CRITICALITY_MATRIX: list[CriticalityRule] = [
    # AUTO-PROCEED: non-critical, reversible, no side effects
    CriticalityRule("read_file", CriticalityLevel.AUTO_PROCEED, "Read-only, no side effects"),
    CriticalityRule("search", CriticalityLevel.AUTO_PROCEED, "Read-only query"),
    CriticalityRule("analyze", CriticalityLevel.AUTO_PROCEED, "Internal computation"),
    CriticalityRule(
        "generate_draft", CriticalityLevel.AUTO_PROCEED, "Creates draft, not published",
    ),
    CriticalityRule("skill_retrieve", CriticalityLevel.AUTO_PROCEED, "Internal knowledge lookup"),
    CriticalityRule("memory_read", CriticalityLevel.AUTO_PROCEED, "Read-only memory access"),
    CriticalityRule("code_generate", CriticalityLevel.AUTO_PROCEED, "Generates code in workspace"),
    CriticalityRule("summarize", CriticalityLevel.AUTO_PROCEED, "Internal computation"),
    CriticalityRule("complex_reasoning", CriticalityLevel.AUTO_PROCEED, "Internal reasoning"),
    CriticalityRule(
        "simple_chat", CriticalityLevel.AUTO_PROCEED, "Conversational, no side effects",
    ),
    CriticalityRule("data_analysis", CriticalityLevel.AUTO_PROCEED, "Internal computation"),

    # NOTIFY-AFTER: safe but user should know
    CriticalityRule("write_file", CriticalityLevel.NOTIFY_AFTER, "Creates/modifies local file"),
    CriticalityRule("code_editing", CriticalityLevel.NOTIFY_AFTER, "Modifies code files"),
    CriticalityRule("file_operations", CriticalityLevel.NOTIFY_AFTER, "File system changes"),
    CriticalityRule("run_command", CriticalityLevel.NOTIFY_AFTER, "Executes shell command"),
    CriticalityRule("memory_write", CriticalityLevel.NOTIFY_AFTER, "Persists to memory"),
    CriticalityRule("web_scrape", CriticalityLevel.NOTIFY_AFTER, "External web access"),
    CriticalityRule("web_research", CriticalityLevel.NOTIFY_AFTER, "External web access"),
    CriticalityRule("bulk_operations", CriticalityLevel.NOTIFY_AFTER, "Batch file changes"),
    CriticalityRule("browser_automation", CriticalityLevel.NOTIFY_AFTER, "Browser interaction"),

    # PAUSE-FOR-APPROVAL: critical, irreversible, or has external side effects
    CriticalityRule("delete_file", CriticalityLevel.PAUSE_FOR_APPROVAL, "Irreversible data loss"),
    CriticalityRule("send_email", CriticalityLevel.PAUSE_FOR_APPROVAL, "External communication"),
    CriticalityRule("send_message", CriticalityLevel.PAUSE_FOR_APPROVAL, "External communication"),
    CriticalityRule("execute_payment", CriticalityLevel.PAUSE_FOR_APPROVAL, "Financial action"),
    CriticalityRule(
        "modify_production", CriticalityLevel.PAUSE_FOR_APPROVAL, "Production system change",
    ),
    CriticalityRule("submit_form", CriticalityLevel.PAUSE_FOR_APPROVAL, "External form submission"),
    CriticalityRule(
        "api_write", CriticalityLevel.PAUSE_FOR_APPROVAL, "External API with side effects",
    ),
    CriticalityRule("credential_change", CriticalityLevel.PAUSE_FOR_APPROVAL, "Security-sensitive"),
    CriticalityRule("git_push", CriticalityLevel.PAUSE_FOR_APPROVAL, "Irreversible remote change"),
    CriticalityRule("deploy", CriticalityLevel.PAUSE_FOR_APPROVAL, "Production deployment"),
]


class CriticalityClassifier:
    """Classifies actions by criticality for Autopilot mode.

    Unknown action types default to PAUSE_FOR_APPROVAL (fail-safe).
    Custom rules can override defaults. Governance slider can promote
    or demote criticality levels.

    Usage::

        classifier = CriticalityClassifier()
        level = classifier.classify("read_file")
        # -> CriticalityLevel.AUTO_PROCEED

        level = classifier.classify("delete_file")
        # -> CriticalityLevel.PAUSE_FOR_APPROVAL

        level = classifier.classify(
            "write_file",
            context={"governance_preset": "YOLO"},
        )
        # -> CriticalityLevel.AUTO_PROCEED  (promoted from NOTIFY_AFTER)
    """

    def __init__(self, custom_rules: list[CriticalityRule] | None = None) -> None:
        """Initialize with default matrix, optionally overridden by custom rules.

        Args:
            custom_rules: Rules that override the defaults for matching action types.
        """
        self._rules: dict[str, CriticalityRule] = {
            r.action_type: r for r in CRITICALITY_MATRIX
        }
        if custom_rules:
            for rule in custom_rules:
                self._rules[rule.action_type] = rule

    def classify(
        self,
        action_type: str,
        context: dict | None = None,
    ) -> CriticalityLevel:
        """Classify an action's criticality level.

        Unknown action types always get PAUSE_FOR_APPROVAL (fail-safe).
        Governance slider can promote/demote levels.

        Args:
            action_type: The type of action to classify.
            context: Optional context with governance_preset, etc.

        Returns:
            CriticalityLevel for the action.
        """
        rule = self._rules.get(action_type)
        if not rule:
            return CriticalityLevel.PAUSE_FOR_APPROVAL  # fail-safe

        level = rule.level

        # Governance slider override
        if context:
            preset = context.get("governance_preset", "").upper()
            if preset == "YOLO":
                if level == CriticalityLevel.NOTIFY_AFTER:
                    return CriticalityLevel.AUTO_PROCEED
            elif (
                preset in ("LOCKDOWN", "PARANOID")
                and level != CriticalityLevel.PAUSE_FOR_APPROVAL
            ):
                return CriticalityLevel.PAUSE_FOR_APPROVAL

        return level

    def get_rule(self, action_type: str) -> CriticalityRule | None:
        """Get the classification rule for an action type."""
        return self._rules.get(action_type)

    def add_rule(self, rule: CriticalityRule) -> None:
        """Add or override a classification rule."""
        self._rules[rule.action_type] = rule

    @property
    def known_action_types(self) -> list[str]:
        """All action types with defined rules."""
        return list(self._rules.keys())

    def to_dict(self) -> dict[str, dict]:
        """Serialize all rules for API/frontend display."""
        return {
            action_type: {
                "level": rule.level.value,
                "reason": rule.reason,
            }
            for action_type, rule in self._rules.items()
        }
