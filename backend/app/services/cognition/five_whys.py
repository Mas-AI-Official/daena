"""FiveWhys -- Toyota root cause analysis.

Taiichi Ohno (Toyota Production System): When something fails, don't fix
the symptom. Ask WHY five times to find the root cause.

Example:
    Error: Permission denied writing to /etc/config
    Why 1: File requires root permissions
    Why 2: We're writing to a system directory
    Why 3: The path was hardcoded as absolute
    Why 4: The config assumed deployment to a specific directory
    Why 5: ROOT CAUSE -- no workspace-relative path resolution

Fix the ROOT CAUSE (add path resolution), not the symptom (sudo).
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class FiveWhys:
    """Drill to root cause of a failure.

    Does NOT use LLM by default -- uses pattern matching on common error
    types for speed. Falls back to LLM analysis for unknown patterns.
    """

    # Common root cause patterns (fast path, no LLM needed)
    _PATTERNS: list[dict[str, Any]] = [
        {
            "error_contains": ["permission denied", "access denied", "forbidden", "403"],
            "root_causes": [
                "Wrong file/directory permissions",
                "Wrong user context (need elevation or different account)",
                "Path is outside allowed workspace",
                "API key missing or expired",
            ],
            "category": "access",
        },
        {
            "error_contains": ["not found", "no such file", "404", "does not exist"],
            "root_causes": [
                "Path is wrong (typo, wrong directory, absolute vs relative)",
                "Resource was deleted or moved",
                "Dependency not installed",
                "Service not running",
            ],
            "category": "missing_resource",
        },
        {
            "error_contains": ["timeout", "timed out", "deadline exceeded"],
            "root_causes": [
                "Service is down or unreachable",
                "Network connectivity issue",
                "Operation takes longer than timeout allows",
                "Resource contention (too many concurrent requests)",
            ],
            "category": "timeout",
        },
        {
            "error_contains": ["connection refused", "connection reset", "econnrefused"],
            "root_causes": [
                "Service is not running on expected port",
                "Firewall blocking connection",
                "Wrong host/port configuration",
                "Service crashed and needs restart",
            ],
            "category": "connection",
        },
        {
            "error_contains": ["syntax error", "parse error", "unexpected token"],
            "root_causes": [
                "Malformed code or configuration",
                "Wrong format (JSON vs YAML, etc.)",
                "Missing closing bracket/quote/tag",
                "Encoding issue (BOM, wrong charset)",
            ],
            "category": "syntax",
        },
        {
            "error_contains": ["out of memory", "oom", "memory", "heap"],
            "root_causes": [
                "Data too large for available memory",
                "Memory leak in long-running process",
                "Need to process in chunks/batches",
                "Wrong model size for available hardware",
            ],
            "category": "resource_exhaustion",
        },
        {
            "error_contains": ["import error", "module not found", "no module named"],
            "root_causes": [
                "Package not installed in active environment",
                "Wrong Python environment activated",
                "Circular import",
                "Package version mismatch",
            ],
            "category": "dependency",
        },
        {
            "error_contains": ["type error", "attribute error", "key error"],
            "root_causes": [
                "Wrong data type passed to function",
                "API response format changed",
                "Missing field in data structure",
                "None/null where value expected",
            ],
            "category": "type_mismatch",
        },
    ]

    async def analyze(
        self,
        task: str,
        error: str,
        strategy: str = "",
        context: Any = None,
    ) -> str:
        """Run 5 Whys analysis on a failure.

        Returns a root cause description that can be used to generate
        an alternative strategy.

        Args:
            task: What we were trying to do.
            error: The error message or description.
            strategy: Which strategy was being used.
            context: Additional context (Observation from OODA).

        Returns:
            Root cause analysis string.
        """
        error_lower = error.lower()

        # Fast path: pattern matching
        for pattern in self._PATTERNS:
            for keyword in pattern["error_contains"]:
                if keyword in error_lower:
                    category = pattern["category"]
                    causes = pattern["root_causes"]
                    logger.info(
                        "five_whys.pattern_match",
                        category=category,
                        error_snippet=error[:200],
                    )

                    # Build the 5 Whys chain
                    analysis = self._build_chain(task, error, strategy, category, causes)
                    return analysis

        # No pattern match -- use generic analysis
        return self._generic_analysis(task, error, strategy)

    def _build_chain(
        self,
        task: str,
        error: str,
        strategy: str,
        category: str,
        possible_causes: list[str],
    ) -> str:
        """Build a 5 Whys chain from pattern match.

        Format:
            WHY 1: Immediate cause
            WHY 2: Underlying cause
            ...
            ROOT CAUSE: <actionable root cause>
            SUGGESTION: <what to do differently>
        """
        # Select most likely cause based on error content
        primary_cause = possible_causes[0]

        chain = [
            f"Task: {task}",
            f"Strategy: {strategy}",
            f"Error: {error[:300]}",
            f"Category: {category}",
            f"---",
            f"WHY 1 (immediate): {error[:200]}",
            f"WHY 2 (underlying): {primary_cause}",
        ]

        # Category-specific deeper analysis
        suggestions = _CATEGORY_SUGGESTIONS.get(category, {})
        why3 = suggestions.get("why3", "Configuration or environment mismatch")
        why4 = suggestions.get("why4", "Assumptions about the environment are wrong")
        root = suggestions.get("root", "Approach needs to account for actual environment state")
        suggestion = suggestions.get("suggestion", "Verify environment state before acting")

        chain.extend([
            f"WHY 3 (deeper): {why3}",
            f"WHY 4 (systemic): {why4}",
            f"WHY 5 (ROOT CAUSE): {root}",
            f"---",
            f"SUGGESTION: {suggestion}",
        ])

        return "\n".join(chain)

    def _generic_analysis(self, task: str, error: str, strategy: str) -> str:
        """Generic analysis when no pattern matches."""
        return (
            f"WHY 1: Action failed with: {error[:200]}\n"
            f"WHY 2: Strategy '{strategy}' assumptions may not match reality\n"
            f"WHY 3: Need to verify actual system state before acting\n"
            f"WHY 4: Prior approach may have wrong mental model of the problem\n"
            f"WHY 5 (ROOT CAUSE): Need to re-observe actual state and try different approach\n"
            f"SUGGESTION: Re-observe, verify assumptions, try alternative path"
        )


# Category-specific deep analysis templates
_CATEGORY_SUGGESTIONS: dict[str, dict[str, str]] = {
    "access": {
        "why3": "Security model of the target system is more restrictive than assumed",
        "why4": "Strategy assumed access that doesn't exist in this context",
        "root": "Need to work within actual permission boundaries or request elevation",
        "suggestion": "Check actual permissions first. If insufficient, use workspace-relative paths or request access via governance",
    },
    "missing_resource": {
        "why3": "Resource location assumptions are wrong (path, URL, package name)",
        "why4": "Strategy used assumed paths instead of discovered paths",
        "root": "Need to DISCOVER resource locations instead of assuming them",
        "suggestion": "Search for the resource first (find, which, pip show, etc.) then use the discovered path",
    },
    "timeout": {
        "why3": "Service or network is slower/unavailable than assumed",
        "why4": "Strategy assumed instant availability of external dependencies",
        "root": "Need to verify service health before depending on it, with fallback",
        "suggestion": "Check service health first. If unavailable: wait and retry, use local alternative, or report blocker",
    },
    "connection": {
        "why3": "Service is not running or listening on expected port",
        "why4": "Strategy assumed service is always running",
        "root": "Need to start/verify the service before connecting",
        "suggestion": "Check if service is running. Start it if needed. Verify port/host before connecting",
    },
    "syntax": {
        "why3": "Generated or modified content has format errors",
        "why4": "Content generation didn't validate output format",
        "root": "Need to validate generated content before using it",
        "suggestion": "Validate the file/content format after writing, fix syntax errors before proceeding",
    },
    "resource_exhaustion": {
        "why3": "Workload exceeds available hardware resources",
        "why4": "Strategy didn't account for resource constraints",
        "root": "Need to work within actual resource limits (chunking, smaller model, streaming)",
        "suggestion": "Process in smaller batches, use streaming, reduce model size, or request more resources",
    },
    "dependency": {
        "why3": "Package not available in current environment",
        "why4": "Strategy assumed dependencies are pre-installed",
        "root": "Need to install dependencies before importing them",
        "suggestion": "Check if package is installed. If not, install it (pip install). Verify the right venv is active",
    },
    "type_mismatch": {
        "why3": "Data format doesn't match what the code expects",
        "why4": "Strategy assumed a specific data shape that reality doesn't match",
        "root": "Need to inspect actual data format before processing",
        "suggestion": "Read and inspect the actual data first (type, shape, keys). Adapt processing to actual format",
    },
}
