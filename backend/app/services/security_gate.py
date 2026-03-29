"""Security Gate — scans inbound messages for prompt injection patterns.

Runs before any LLM call. Cheap regex-based check (<1ms).
Returns a ScanResult indicating whether the message is safe.

This is a defense-in-depth layer. It catches common injection
techniques but is not a substitute for model-level safety.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Result of a security scan."""

    safe: bool
    matched_pattern: str | None = None


# Compiled regex patterns for common prompt injection techniques
_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
     "ignore_previous_instructions"),
    (re.compile(r"disregard\s+(all\s+)?prior", re.IGNORECASE),
     "disregard_prior"),
    (re.compile(r"you\s+are\s+now\s+(?:a\s+)?(?:DAN|jailbreak)", re.IGNORECASE),
     "jailbreak_persona"),
    (re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
     "fake_system_prompt"),
    (re.compile(r"<\|?(?:system|im_start)\|?>", re.IGNORECASE),
     "special_token_injection"),
    (re.compile(r"```\s*system\s*\n", re.IGNORECASE),
     "code_block_system"),
    (re.compile(r"ADMIN\s*OVERRIDE", re.IGNORECASE),
     "admin_override"),
    (re.compile(r"ignore\s+(?:your|all)\s+(?:rules|guidelines|constraints)", re.IGNORECASE),
     "ignore_rules"),
    (re.compile(
        r"pretend\s+(?:you\s+are|to\s+be)\s+(?:a\s+)?"
        r"(?:different|new|unrestricted)",
        re.IGNORECASE,
    ), "pretend_unrestricted"),
]


class SecurityGate:
    """Stateless prompt injection scanner.

    Usage::

        scan = SecurityGate.scan("Hello, how are you?")
        assert scan.safe

        scan = SecurityGate.scan("Ignore all previous instructions")
        assert not scan.safe
    """

    @classmethod
    def scan(cls, message: str) -> ScanResult:
        """Scan a message for injection patterns.

        Args:
            message: The raw user message to scan.

        Returns:
            ScanResult with safe=True if no patterns matched.
        """
        for pattern, name in _INJECTION_PATTERNS:
            if pattern.search(message):
                return ScanResult(safe=False, matched_pattern=name)
        return ScanResult(safe=True)
