"""PII Guard — the only governance UNLEASHED mode keeps active.

Phase 1 F6 (2026-04-24). Masoud's governance mandate: "I want full power.
The only governance is matter is not leaking my personal data and
information and my bank information address etc."

This module is the implementation of that mandate. In UNLEASHED mode,
SecurityGate runs PII detection on every outbound payload (LLM
prompts, tool calls, browser/email/social-media posts). Hits are
classified into two severities:

* ``BLOCK`` -- credit cards, SSN/SIN, IBAN, bank routing numbers, the
  founder's home address / bank account / personal email exact strings.
  These are halted before the request leaves Daena.
* ``REDACT`` -- generic PII (name, email, phone, location). The string
  is replaced with a typed token like ``<EMAIL>`` and the call proceeds.

The blocklist file is intentionally split into two layers:

1. Public regex pack at ``backend/app/config/pii_blocklist.yaml`` --
   credit cards, SSNs, IBANs, generic regex. Safe to commit.
2. Founder-private values at ``D:/Ideas/Daena-Mind/soul/T4-founder-private/
   pii_blocklist_values.yaml`` -- the actual addresses, account numbers,
   passwords, etc. NEVER read into LLM context. Loaded once at startup
   into the matcher's exact-string list.

We deliberately do NOT depend on Microsoft Presidio for v1 -- adding the
spacy model + analyzer dependencies would block Phase 1 ship behind a
3-5 minute install. The regex pack covers the 95% case (financial +
government IDs + the founder's exact strings). Phase 2 can layer
Presidio on for fuzzy NER if the founder asks for it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from app.core.logging import get_logger

logger = get_logger(__name__)


class Severity(str, Enum):
    BLOCK = "block"
    REDACT = "redact"


@dataclass
class PiiHit:
    name: str  # e.g. "credit_card", "founder_address"
    severity: Severity
    matched_text: str  # always truncated for logging
    span_start: int
    span_end: int


@dataclass
class PiiScanResult:
    hits: list[PiiHit] = field(default_factory=list)
    redacted_text: str = ""

    @property
    def has_block(self) -> bool:
        return any(h.severity == Severity.BLOCK for h in self.hits)

    @property
    def has_redact(self) -> bool:
        return any(h.severity == Severity.REDACT for h in self.hits)

    def summary(self) -> dict[str, Any]:
        return {
            "block_count": sum(1 for h in self.hits if h.severity == Severity.BLOCK),
            "redact_count": sum(1 for h in self.hits if h.severity == Severity.REDACT),
            "names": sorted({h.name for h in self.hits}),
        }


# Default regex pack -- fallback used when YAML config is missing.
# Patterns chosen for high precision, low false-positive rate; we'd
# rather miss a borderline case than false-block a legitimate post.
_DEFAULT_REGEX_PATTERNS: list[dict[str, Any]] = [
    {
        "name": "credit_card_visa",
        "pattern": r"\b4\d{3}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b",
        "severity": "block",
    },
    {
        "name": "credit_card_mastercard",
        "pattern": r"\b5[1-5]\d{2}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b",
        "severity": "block",
    },
    {
        "name": "credit_card_amex",
        "pattern": r"\b3[47]\d{2}[ -]?\d{6}[ -]?\d{5}\b",
        "severity": "block",
    },
    {
        "name": "us_ssn",
        "pattern": r"\b\d{3}-\d{2}-\d{4}\b",
        "severity": "block",
    },
    {
        "name": "ca_sin",
        "pattern": r"\b\d{3}[ -]\d{3}[ -]\d{3}\b",
        "severity": "block",
    },
    {
        "name": "iban",
        "pattern": r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b",
        "severity": "block",
    },
    {
        "name": "us_bank_routing_account",
        # 9-digit routing followed by 4-17 digit account, with separator
        "pattern": r"\b\d{9}[ \-/]\d{4,17}\b",
        "severity": "block",
    },
    {
        "name": "email_generic",
        "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "severity": "redact",
    },
    {
        "name": "phone_na",
        # +1 (xxx) xxx-xxxx, 1-xxx-xxx-xxxx, xxx-xxx-xxxx
        "pattern": r"(?:\+?1[ \-.])?\(?\d{3}\)?[ \-.]\d{3}[ \-.]\d{4}\b",
        "severity": "redact",
    },
    {
        "name": "us_passport",
        "pattern": r"\b[A-Z]\d{8}\b",
        "severity": "block",
    },
]


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning("pii_guard.yaml_load_failed", path=str(path), error=str(exc))
        return {}


class PiiGuard:
    """Per-tenant PII matcher.

    Holds compiled patterns + an exact-string blocklist (for the
    founder's address / bank account / personal email values that
    should never appear in any outbound payload). Both lists hot-reload
    when ``reload()`` is called -- callers should re-emit on policy
    edits so a redaction rule change takes effect without restart.
    """

    def __init__(
        self,
        *,
        public_yaml: Path | None = None,
        private_yaml: Path | None = None,
    ) -> None:
        self._public_yaml = public_yaml
        self._private_yaml = private_yaml
        self._compiled: list[tuple[str, re.Pattern[str], Severity]] = []
        self._exact_blocks: list[tuple[str, str]] = []  # (name, lowercase_value)
        self.reload()

    def reload(self) -> None:
        """Rebuild the matcher state from disk."""
        public_cfg = _load_yaml(self._public_yaml) if self._public_yaml else {}
        regex_specs: list[dict[str, Any]] = list(public_cfg.get("regex") or [])
        if not regex_specs:
            regex_specs = _DEFAULT_REGEX_PATTERNS

        compiled: list[tuple[str, re.Pattern[str], Severity]] = []
        for spec in regex_specs:
            try:
                name = str(spec["name"])
                pattern = re.compile(spec["pattern"], re.IGNORECASE)
                severity = Severity(spec.get("severity", "redact"))
                compiled.append((name, pattern, severity))
            except Exception as exc:
                logger.warning(
                    "pii_guard.bad_regex", name=spec.get("name"), error=str(exc),
                )
        self._compiled = compiled

        # Founder-private exact-string blocks. These are the values you
        # never want to leak: home address, bank account number, family
        # member names, real-world phone, government ID numbers.
        private_cfg = _load_yaml(self._private_yaml) if self._private_yaml else {}
        exacts: list[tuple[str, str]] = []
        for entry in (private_cfg.get("exact_block") or []):
            if isinstance(entry, dict):
                name = str(entry.get("name", "founder_private"))
                value = str(entry.get("value", "")).lower().strip()
            elif isinstance(entry, str):
                name = "founder_private"
                value = entry.lower().strip()
            else:
                continue
            if value:
                exacts.append((name, value))
        self._exact_blocks = exacts

        logger.info(
            "pii_guard.loaded",
            regex_count=len(self._compiled),
            exact_count=len(self._exact_blocks),
        )

    def scan(self, text: str) -> PiiScanResult:
        """Detect PII in ``text``. Returns hits + redacted text."""
        if not text:
            return PiiScanResult(redacted_text=text or "")

        hits: list[PiiHit] = []
        # Exact-string founder blocklist (case-insensitive). We do not
        # redact -- presence alone is BLOCK because these strings should
        # never travel through any outbound payload.
        lower_text = text.lower()
        for name, value in self._exact_blocks:
            idx = 0
            while True:
                pos = lower_text.find(value, idx)
                if pos < 0:
                    break
                hits.append(PiiHit(
                    name=name,
                    severity=Severity.BLOCK,
                    matched_text=text[pos:pos + len(value)][:40],
                    span_start=pos,
                    span_end=pos + len(value),
                ))
                idx = pos + len(value)

        # Regex pack
        for name, pattern, severity in self._compiled:
            for match in pattern.finditer(text):
                hits.append(PiiHit(
                    name=name,
                    severity=severity,
                    matched_text=match.group(0)[:40],
                    span_start=match.start(),
                    span_end=match.end(),
                ))

        # Build redacted text by replacing REDACT spans with typed tokens.
        # BLOCK hits do NOT redact -- the SecurityGate will halt the call.
        redacted = text
        if hits:
            # Sort by span_start descending so substitutions don't shift
            # later indices.
            sorted_hits = sorted(hits, key=lambda h: h.span_start, reverse=True)
            for h in sorted_hits:
                if h.severity == Severity.REDACT:
                    token = f"<{h.name.upper()}>"
                    redacted = redacted[: h.span_start] + token + redacted[h.span_end:]

        return PiiScanResult(hits=hits, redacted_text=redacted)


def _resolve_default_paths() -> tuple[Path, Path]:
    """Resolve the two YAML paths the singleton uses."""
    public = (
        Path(__file__).resolve().parent.parent / "config" / "pii_blocklist.yaml"
    )
    # Founder-private vault. Lives outside the repo, gitignored by design.
    # Daena-Mind path is canonical per CLAUDE.md.
    private = Path("D:/Ideas/Daena-Mind/soul/T4-founder-private/pii_blocklist_values.yaml")
    return public, private


# Singleton -- callers import this and use scan_text() / reload() directly.
_public_path, _private_path = _resolve_default_paths()
pii_guard = PiiGuard(public_yaml=_public_path, private_yaml=_private_path)


def scan_text(text: str) -> PiiScanResult:
    """Convenience wrapper: scan via the singleton."""
    return pii_guard.scan(text)
