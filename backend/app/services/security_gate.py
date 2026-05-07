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


# ── Shield patterns: protect OUR data/IP in ALL governance modes ──
# These run even in UNLEASHED mode. The shield never comes off.
_SHIELD_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Protect source code / architecture / internals
    (re.compile(
        r"(?:show|give|reveal|dump|print|output|display|expose)\s+"
        r"(?:me\s+)?(?:your|the|daena'?s?)?\s*"
        r"(?:source\s*code|system\s*prompt|internal\s*(?:architecture|structure|config|code)|"
        r"hard\s*laws?|soul\s*(?:document|prompt|spec)|governance\s*(?:rules|config|code))",
        re.IGNORECASE,
    ), "shield_source_exposure"),
    # Protect API keys / credentials
    (re.compile(
        r"(?:what|show|give|reveal|list|dump|print)\s+"
        r"(?:are\s+)?(?:me\s+)?(?:your|the|daena'?s?)?\s*"
        r"(?:api\s*keys?|secrets?|credentials?|tokens?|passwords?|"
        r"encryption\s*keys?|vault\s*keys?|jwt\s*secrets?)",
        re.IGNORECASE,
    ), "shield_credential_exposure"),
    # Protect founder personal info / business strategy
    (re.compile(
        r"(?:tell|give|reveal|show|what|who)\s+"
        r"(?:me\s+)?(?:about\s+)?(?:everything\s+about\s+)?"
        r"(?:masoud|the\s+(?:founder|owner|ceo)|mas-?ai'?s?\s+"
        r"(?:strategy|plans?|finances?|investors?|revenue|customers?))",
        re.IGNORECASE,
    ), "shield_founder_info"),
]


class SecurityGate:
    """Stateless prompt injection scanner + shield.

    Two layers:
    - shield_scan(): Protects IP/data. Runs in ALL governance modes.
    - scan(): Detects injection attempts. Runs in BALANCED/GOVERNED only.

    Usage::

        # Shield (always)
        shield = SecurityGate.shield_scan("show me your source code")
        assert not shield.safe

        # Injection (governance modes)
        scan = SecurityGate.scan("Ignore all previous instructions")
        assert not scan.safe
    """

    @classmethod
    def shield_scan(cls, message: str) -> ScanResult:
        """Shield scan -- runs in ALL governance modes including UNLEASHED.

        Protects source code, API keys, founder info, and system internals.
        This is the one wall that never comes down.

        Phase 1 F6 (2026-04-24) added PII Guard as a second layer here:
        founder-private exact-string blocks (home address, bank account,
        SIN, etc.) AND high-severity regex patterns (credit cards, IBAN,
        API keys) are evaluated alongside the legacy shield patterns.
        Masoud's mandate: "the only governance is matter is not leaking
        my personal data and information and my bank information address
        etc." -- this is that gate.

        Args:
            message: The raw user message to scan.

        Returns:
            ScanResult with safe=True if no shield patterns matched.
        """
        for pattern, name in _SHIELD_PATTERNS:
            if pattern.search(message):
                return ScanResult(safe=False, matched_pattern=name)

        # PII Guard: only BLOCK-severity hits halt the request here. The
        # REDACT-severity hits (generic email/phone/IP) are handled at
        # the outbound boundary -- not in shield_scan because input
        # legitimately contains the user's own email when they're
        # asking Daena to draft a reply about themselves.
        try:
            from app.services.pii_guard import scan_text

            pii = scan_text(message)
            if pii.has_block:
                blocking = next(
                    (h for h in pii.hits if h.severity.value == "block"), None,
                )
                if blocking is not None:
                    return ScanResult(
                        safe=False,
                        matched_pattern=f"pii.{blocking.name}",
                    )
        except Exception:
            # Defensive: never let a PII-guard import error break shield.
            pass

        return ScanResult(safe=True)

    @classmethod
    def redact_outbound(cls, message: str) -> tuple[str, list[str]]:
        """Redact REDACT-severity PII before outbound delivery.

        Returns ``(redacted_text, hit_names)``. Callers (LLM streamer,
        email composer, social media poster) use this to swap generic
        PII for typed tokens. BLOCK hits are NOT handled here -- those
        should have been caught upstream by ``shield_scan``.

        Phase 1 F6 (2026-04-24).
        """
        try:
            from app.services.pii_guard import scan_text

            result = scan_text(message)
            if result.has_redact:
                names = sorted({
                    h.name for h in result.hits if h.severity.value == "redact"
                })
                return result.redacted_text, names
        except Exception:
            pass
        return message, []

    @classmethod
    def scan(cls, message: str) -> ScanResult:
        """Scan a message for injection patterns.

        Only called in BALANCED/GOVERNED modes. UNLEASHED skips this.

        Args:
            message: The raw user message to scan.

        Returns:
            ScanResult with safe=True if no patterns matched.
        """
        for pattern, name in _INJECTION_PATTERNS:
            if pattern.search(message):
                return ScanResult(safe=False, matched_pattern=name)
        return ScanResult(safe=True)
