"""Egress Filter: multi-pattern scan of every outbound byte.

Called from:
    * chat_orchestrator Stage 9 LLMStream chunk emitter
    * chat_orchestrator Stage 10 Persist + Audit
    * SSE streaming response wrapper
    * outbound HTTP client middleware
    * daena_bot tool output post-processor

Redacts any substring that matches a registered asset raw value,
replacing with ``[REDACTED:class:prefix]``. Fail-safe: if the filter
raises, the outbound text is returned unchanged AND an audit entry
is written so the failure is never silent.

Performance: the registry is typically small (dozens of secrets) so a
straight ``str.find`` loop is faster than compiling a regex or
building an Aho-Corasick automaton. If the registry grows past ~100
entries we should switch to the ``pyahocorasick`` package, but for
now KISS wins.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.security.asset_shield.vault_adapter import VaultAdapter

logger = get_logger(__name__)


@dataclass
class EgressRedaction:
    """Audit record for a single redaction event."""

    asset_id: str
    asset_class: str
    fingerprint_prefix: str
    span_start: int
    span_end: int


@dataclass
class EgressScanResult:
    redacted_text: str
    hits: list[EgressRedaction] = field(default_factory=list)

    @property
    def hit_count(self) -> int:
        return len(self.hits)


class EgressFilter:
    """Universal outbound-byte scanner + redactor."""

    def __init__(self, vault: VaultAdapter | None = None) -> None:
        self._vault = vault or VaultAdapter()

    def scan_and_redact(self, text: str) -> EgressScanResult:
        """Scan ``text`` for any registered secret and redact matches.

        Returns a result with the redacted text + a trace of each
        redaction for audit. Empty input returns an empty result with
        the original text preserved.
        """
        if not text:
            return EgressScanResult(redacted_text=text or "")

        try:
            registered = self._vault.list_registered()
        except Exception as exc:  # pragma: no cover - vault lookup should never raise
            logger.warning("egress_filter.vault_error", error=str(exc))
            return EgressScanResult(redacted_text=text)

        if not registered:
            return EgressScanResult(redacted_text=text)

        # Sort by length descending so longer secrets are redacted
        # first; otherwise a shorter prefix could mask a longer match.
        ordered = sorted(
            registered, key=lambda r: len(r.raw_value), reverse=True,
        )

        redacted = text
        hits: list[EgressRedaction] = []

        for reg in ordered:
            if not reg.raw_value:
                continue
            needle = reg.raw_value
            replacement = (
                f"[REDACTED:{reg.asset_class}:{reg.fingerprint_prefix}]"
            )
            # Find all occurrences; record audit span in the PRE-redact
            # coordinates (which is accurate enough for the span-start).
            start = 0
            while True:
                idx = redacted.find(needle, start)
                if idx == -1:
                    break
                hits.append(
                    EgressRedaction(
                        asset_id=reg.asset_id,
                        asset_class=reg.asset_class,
                        fingerprint_prefix=reg.fingerprint_prefix,
                        span_start=idx,
                        span_end=idx + len(needle),
                    )
                )
                redacted = (
                    redacted[:idx] + replacement + redacted[idx + len(needle):]
                )
                start = idx + len(replacement)

        if hits:
            logger.info(
                "egress_filter.redacted",
                hits=len(hits),
                fingerprints=[h.fingerprint_prefix for h in hits[:5]],
            )
        return EgressScanResult(redacted_text=redacted, hits=hits)

    def scan_only(self, text: str) -> bool:
        """Lightweight check: does the text contain any registered secret?"""
        if not text:
            return False
        try:
            registered = self._vault.list_registered()
        except Exception:  # pragma: no cover
            return False
        return any(
            reg.raw_value and reg.raw_value in text for reg in registered
        )
