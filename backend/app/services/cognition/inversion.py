"""Inversion -- Charlie Munger / Carl Jacobi thinking.

"Invert, always invert." -- Carl Jacobi (mathematician)

Instead of asking "How do I succeed?", ask "What would cause failure?"
Then remove those failure causes. What's left is the path to success.

Munger: "It's not about being brilliant every day. It's about avoiding
being stupid. Avoiding mistakes is easier than forcing brilliance."

This is particularly powerful for:
    - Pre-mortem analysis (what would cause this deployment to fail?)
    - Debugging (what conditions would produce this error?)
    - Decision-making (what would make each option a disaster?)
    - Security (what would an attacker try?)
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# Common failure modes by task category
_FAILURE_MODES: dict[str, list[dict[str, str]]] = {
    "file_operations": [
        {"mode": "Path doesn't exist", "prevention": "Check path exists before operating"},
        {"mode": "No write permissions", "prevention": "Verify permissions before writing"},
        {"mode": "File is locked", "prevention": "Check for locks, use temp file + rename"},
        {"mode": "Disk full", "prevention": "Check available space for large operations"},
        {"mode": "Encoding mismatch", "prevention": "Specify encoding explicitly (UTF-8)"},
    ],
    "network": [
        {"mode": "Service unreachable", "prevention": "Health check before calling"},
        {"mode": "Auth expired", "prevention": "Refresh credentials before use"},
        {"mode": "Rate limited", "prevention": "Check rate limits, add backoff"},
        {"mode": "Response schema changed", "prevention": "Validate response before parsing"},
        {"mode": "DNS resolution fails", "prevention": "Use IP fallback or check connectivity"},
    ],
    "execution": [
        {"mode": "Tool not installed", "prevention": "Check tool exists before calling"},
        {"mode": "Wrong environment", "prevention": "Verify active environment (venv, PATH)"},
        {"mode": "Command hangs", "prevention": "Set timeout on all external commands"},
        {"mode": "Exit code ignored", "prevention": "Always check exit codes"},
        {"mode": "Working dir wrong", "prevention": "Use absolute paths, or cd first"},
    ],
    "deployment": [
        {"mode": "Missing env vars", "prevention": "Validate all required env vars before deploy"},
        {"mode": "Port already in use", "prevention": "Check port availability before binding"},
        {"mode": "Health check fails", "prevention": "Test health endpoint locally first"},
        {"mode": "Old cache served", "prevention": "Invalidate caches during deploy"},
        {"mode": "Rollback not possible", "prevention": "Create backup/snapshot before deploying"},
    ],
    "data": [
        {"mode": "Data corruption", "prevention": "Validate data integrity before and after"},
        {"mode": "Schema mismatch", "prevention": "Check schema matches expected before processing"},
        {"mode": "Null/missing values", "prevention": "Handle null cases explicitly"},
        {"mode": "Encoding issues", "prevention": "Detect and normalize encoding first"},
        {"mode": "Data too large", "prevention": "Check size, process in chunks if needed"},
    ],
    "generic": [
        {"mode": "Assumptions about state are wrong", "prevention": "Verify state before acting"},
        {"mode": "Dependencies missing", "prevention": "Check all deps before starting"},
        {"mode": "Concurrent modification", "prevention": "Use locking or optimistic concurrency"},
        {"mode": "Error swallowed silently", "prevention": "Log and propagate all errors"},
        {"mode": "Governance violation", "prevention": "Check governance tier before action"},
    ],
}


class Inversion:
    """Analyze a task by asking what would cause it to fail.

    Steps:
        1. Classify the task into action categories
        2. List all known failure modes for those categories
        3. For each failure mode: can we prevent it?
        4. Build a prevention checklist
        5. Return the inverted approach (prevent all failures = success)
    """

    async def analyze(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run inversion analysis.

        Returns:
            {
                "failure_modes": [...],
                "preventions": [...],
                "inverted_approach": "...",
                "checklist": [...]
            }
        """
        categories = self._classify_task(task)
        failure_modes = []
        preventions = []
        checklist = []

        for category in categories:
            modes = _FAILURE_MODES.get(category, _FAILURE_MODES["generic"])
            for fm in modes:
                failure_modes.append(fm["mode"])
                preventions.append(fm["prevention"])
                checklist.append(f"[ ] {fm['prevention']}")

        # Deduplicate
        seen = set()
        unique_checklist = []
        for item in checklist:
            if item not in seen:
                seen.add(item)
                unique_checklist.append(item)

        inverted_approach = (
            f"Instead of just trying to do '{task}', first prevent all known failure modes: "
            + "; ".join(preventions[:5])
            + ". Then execute with these safeguards in place."
        )

        logger.info(
            "inversion.analyzed",
            task=task[:100],
            categories=categories,
            failure_modes=len(failure_modes),
        )

        return {
            "failure_modes": failure_modes,
            "preventions": preventions,
            "inverted_approach": inverted_approach,
            "checklist": unique_checklist[:8],  # Cap at 8 items
        }

    def _classify_task(self, task: str) -> list[str]:
        """Classify task into action categories for failure mode lookup."""
        task_lower = task.lower()
        categories = []

        if any(kw in task_lower for kw in ["file", "write", "read", "path", "save", "copy"]):
            categories.append("file_operations")
        if any(kw in task_lower for kw in ["api", "http", "fetch", "download", "url", "web"]):
            categories.append("network")
        if any(kw in task_lower for kw in ["run", "execute", "command", "install", "terminal"]):
            categories.append("execution")
        if any(kw in task_lower for kw in ["deploy", "production", "server", "docker", "cloud"]):
            categories.append("deployment")
        if any(kw in task_lower for kw in ["data", "csv", "json", "database", "query"]):
            categories.append("data")

        return categories or ["generic"]
