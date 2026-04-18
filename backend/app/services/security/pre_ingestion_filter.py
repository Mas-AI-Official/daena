"""Pre-Ingestion Security + Intelligence Filter.

The single gate every new artifact passes through before Daena touches
it. Runs BEFORE ``pip install``, BEFORE opening an email attachment,
BEFORE reading a downloaded file, BEFORE ingesting a skill doc. Two
parallel questions gated in one pass:

1. **Do we need this?** -- intelligence check. Is it already installed?
   Is there a safer/simpler alternative? Is the request coherent with
   the current task?
2. **Is it safe?** -- security check. Typosquat? Known-malicious?
   Recent / obscure publisher? Known CVEs? Prompt-injection payload?

Three-tier pipeline so fast rejections don't waste network:

    Tier 1 (static, no network)  -> typosquat, known-malicious
    Tier 2 (network + cache)     -> PyPI metadata, publisher history
    Tier 3 (deep scan, optional) -> safety CVE check, YARA, LLM review

Outcome is one of:

    PASS    -- proceed with ingestion (auto-install, open file, etc.)
    WARN    -- surface approval gate; operator decides
    REFUSE  -- block the ingestion entirely; log + notify

Design goal: **extensible to every ingestion surface**. Today only
pip packages are wired in. Email attachments, user-uploaded files,
skill doc ingestion, and MCP server installation follow the same
``IngestionContext`` contract.

Why this exists
---------------
The 2026-04-18 "give Daena full computer access" conversation raised
the concern: if Daena installs what she needs like OpenClaw does, what
stops a prompt-injection from installing malware? The ``_auto_install``
trigger path is already safer than LLM-initiated install because the
package name comes from a Python error object -- but "comes from an
error object" doesn't prove it's a real package. This filter is the
second line of defense: even a correctly-extracted package name is
rejected if it looks like a typosquat or lands on the malicious list.

Masoud's framing: "even for the file we receive for the email we are
receiving or book even skills we are reading all these should go
through a security and intelligent filter before get touched."

This module is that filter.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Artifact types that plug into the same filter ────────────────────
#
# Adding a new ingestion surface (email attachment, file upload, skill
# doc, MCP server) is a matter of (a) extending this enum, (b) adding
# the per-type checks in ``_run_static_checks`` / ``_run_network_checks``,
# and (c) calling ``PreIngestionFilter.evaluate(context)`` from the
# ingestion entry point.
class ArtifactType(str, Enum):
    PIP_PACKAGE = "pip_package"
    NPM_PACKAGE = "npm_package"
    FILE = "file"               # arbitrary file (download, upload)
    EMAIL_ATTACHMENT = "email_attachment"
    SKILL = "skill"             # skill doc / prompt to ingest into T2
    MCP_SERVER = "mcp_server"   # new MCP server to install + spawn
    BOOK = "book"               # long-form content for NBMF


class TriggerSource(str, Enum):
    """Who asked for this ingestion? Affects trust baseline."""

    AUTO_HEAL = "auto_heal"            # Daena's _auto_install on error
    LLM_REQUEST = "llm_request"        # LLM emitted install_system_tool
    USER_UPLOAD = "user_upload"        # operator uploaded a file
    SCHEDULED = "scheduled"            # heartbeat / cron ingestion
    MCP_INSTALL = "mcp_install"        # Connections page MCP click
    EMAIL_INBOUND = "email_inbound"    # email arrived with attachment


@dataclass
class IngestionContext:
    """What Daena wants to ingest + why + where it came from.

    Carries enough provenance that the filter can make a risk-aware
    decision without calling back to the orchestrator for more data.

    For content-based artifacts (FILE, EMAIL_ATTACHMENT, SKILL, BOOK),
    set ``content`` to the text being ingested so the prompt-injection
    scanner can run. The filter returns ``cleaned_content`` in
    ``FilterVerdict.extra["cleaned_content"]`` when the scanner
    quarantines injection payloads -- the caller uses the cleaned
    version instead of the original.
    """

    artifact_type: ArtifactType
    identifier: str              # package name, file path, URL, skill ID
    source: str = ""             # "pypi", "npm", "url:...", "email:sender@x"
    triggered_by: TriggerSource = TriggerSource.LLM_REQUEST
    reason: str = ""             # human-readable "why we need this"
    agi_mode: bool = False       # UNLEASHED + autopilot
    user_intent: str = ""        # original user prompt, if known
    # ``content`` is the text payload for content artifacts. Empty for
    # package-only artifacts (pip/npm) where the filter only needs the
    # identifier.
    content: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


Verdict = Literal["PASS", "WARN", "REFUSE"]


@dataclass
class SecuritySignal:
    """One check's output. Multiple signals combine into the final verdict."""

    check: str                   # "typosquat", "known_malicious", etc.
    verdict: Verdict
    detail: str
    confidence: float = 0.8      # 0.0-1.0 strength of this signal
    latency_ms: float = 0.0      # how long this check took (observability)


@dataclass
class FilterVerdict:
    """Aggregate decision across all signals.

    For content-bearing artifacts, ``content_scan`` holds the
    prompt-injection scanner's output: the scanner's own verdict
    (CLEAN / CONTAMINATED / HOSTILE), the recommended decision
    (USE_CLEAN / USE_ORIGINAL_WITH_WARNING / REFUSE_ENTIRELY), and
    ``cleaned_content`` -- the quarantine-stripped text the caller
    should use when the decision says USE_CLEAN.
    """

    decision: Verdict
    confidence: float             # weighted average of signal confidences
    signals: list[SecuritySignal]
    reason: str                   # one-line operator-facing summary
    need_analysis: str = ""       # "do we need this?" output
    total_latency_ms: float = 0.0
    # Populated for content-bearing artifacts; None for package-only.
    content_scan: dict[str, Any] | None = None


# ── Static data ──────────────────────────────────────────────────────
#
# Typosquat check compares the requested name against this set using
# Levenshtein distance. Most common PyPI targets for squatters, plus
# the packages Daena commonly installs.
_TYPOSQUAT_TARGETS: set[str] = {
    # Top PyPI by downloads (partial list; extend as we see new attacks)
    "requests", "urllib3", "setuptools", "certifi", "charset-normalizer",
    "idna", "wheel", "pip", "six", "cryptography", "pyyaml", "python-dateutil",
    "numpy", "pandas", "pillow", "packaging", "markupsafe", "jinja2",
    "werkzeug", "flask", "django", "fastapi", "starlette", "pydantic",
    "sqlalchemy", "aiohttp", "httpx", "tenacity", "click", "rich",
    "typer", "structlog", "pytest", "pytest-asyncio", "anyio", "attrs",
    "platformdirs", "tomli", "tomlkit", "virtualenv", "distlib",
    "openai", "anthropic", "google-generativeai", "groq", "ollama",
    "langchain", "llama-index", "transformers", "torch", "tensorflow",
    "scipy", "matplotlib", "scikit-learn", "huggingface-hub",
    "beautifulsoup4", "lxml", "selenium", "playwright", "pyautogui",
    "mss", "opencv-python", "pyperclip", "pypdf", "reportlab",
    "weasyprint", "python-multipart", "authlib", "pyjwt", "bcrypt",
    "passlib", "python-jose", "greenlet", "asyncpg", "aiosqlite",
    "redis", "celery", "boto3", "azure-identity", "google-cloud-storage",
}

# Known-malicious packages (seed list). In production, sync from
# https://github.com/pypa/advisory-database or MalwarePy.
_KNOWN_MALICIOUS: set[str] = {
    # Historic typosquats published by security researchers
    "colourama",         # colorama typosquat, malicious
    "djanga",            # django typosquat
    "python-dateutil2",  # python-dateutil typosquat
    "crypt",             # cryptography typosquat
    "urlib3",            # urllib3 typosquat
    "reqests",           # requests typosquat
    "request",           # also bad (singular)
    "jeilyfish",         # jellyfish typosquat (used in a real attack)
    # Add more as we see them
}

# Packages whose install IS our intended behavior -- skip the filter
# to avoid false-positives when Daena auto-heals her own missing
# dependencies.
_ALLOWLIST: set[str] = {
    "cowsay",  # used in dogfood tests; safe
    # Add popular-and-trusted packages here if needed
}


def _levenshtein(a: str, b: str) -> int:
    """Classic two-row Levenshtein. Small strings so this is cheap."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            ins = current[-1] + 1
            dele = previous[j] + 1
            sub = previous[j - 1] + (ca != cb)
            current.append(min(ins, dele, sub))
        previous = current
    return previous[-1]


# ── Filter ───────────────────────────────────────────────────────────


class PreIngestionFilter:
    """Evaluate an ingestion context and return a verdict.

    Stateless; safe to instantiate per-call. Network-backed checks have
    a short timeout so slow PyPI doesn't block Daena.

    Usage::

        filter_ = PreIngestionFilter()
        verdict = await filter_.evaluate(IngestionContext(
            artifact_type=ArtifactType.PIP_PACKAGE,
            identifier="requests",
            source="pypi",
            triggered_by=TriggerSource.AUTO_HEAL,
            reason="ModuleNotFoundError: No module named 'requests'",
            agi_mode=True,
        ))
        if verdict.decision == "REFUSE":
            return {"blocked": verdict.reason}
    """

    def __init__(self, network_timeout_s: float = 5.0) -> None:
        self._timeout = network_timeout_s

    async def evaluate(self, context: IngestionContext) -> FilterVerdict:
        """Run all applicable checks and synthesize the verdict."""
        import time
        t0 = time.perf_counter()

        signals: list[SecuritySignal] = []

        # Allowlist bypass -- Daena's own known-safe dependencies.
        if context.artifact_type in (ArtifactType.PIP_PACKAGE, ArtifactType.NPM_PACKAGE):
            if context.identifier.lower() in _ALLOWLIST:
                signals.append(SecuritySignal(
                    check="allowlist",
                    verdict="PASS",
                    detail=f"{context.identifier} is on Daena's internal allowlist",
                    confidence=1.0,
                ))
                return FilterVerdict(
                    decision="PASS",
                    confidence=1.0,
                    signals=signals,
                    reason="Allowlisted package",
                    need_analysis="Allowlisted -- need-analysis skipped",
                    total_latency_ms=(time.perf_counter() - t0) * 1000,
                )

        # Tier 1: static checks. Fast, offline, fail-closed on refuse.
        signals.extend(await self._run_static_checks(context))
        if any(s.verdict == "REFUSE" for s in signals):
            return self._synthesize(context, signals, t0)

        # Tier 2: network-backed provenance (parallel, timeout-bounded).
        signals.extend(await self._run_network_checks(context))

        # Tier 3: need-analysis (intelligence side of the filter).
        need_signal, need_text = await self._need_analysis(context)
        signals.append(need_signal)

        # Tier 4: prompt-injection scan for content-bearing artifacts.
        # Runs on FILE / EMAIL_ATTACHMENT / SKILL / BOOK / MCP_TOOL_OUTPUT
        # so a file on disk or an email attachment that carries hidden
        # instructions gets quarantined (or the whole artifact refused)
        # before the content reaches Daena's memory or reasoning loop.
        content_scan_data: dict[str, Any] | None = None
        if context.content:
            scan_signal, content_scan_data = self._content_scan(context)
            signals.append(scan_signal)

        verdict = self._synthesize(context, signals, t0)
        verdict.need_analysis = need_text
        verdict.content_scan = content_scan_data
        return verdict

    # ── Static checks ───────────────────────────────────────────────

    async def _run_static_checks(
        self, context: IngestionContext,
    ) -> list[SecuritySignal]:
        """Offline checks. Typosquat, known-malicious, name sanity."""
        signals: list[SecuritySignal] = []
        if context.artifact_type not in (
            ArtifactType.PIP_PACKAGE,
            ArtifactType.NPM_PACKAGE,
            ArtifactType.MCP_SERVER,
        ):
            # Other types (file, email, skill) will land here with
            # their own static checks once those pathways are wired.
            return signals

        name = context.identifier.lower().strip()

        # Sanity: package name must match PEP 503 / npm naming shape.
        if not re.match(r"^[a-z0-9][a-z0-9._-]*$", name) or len(name) > 100:
            signals.append(SecuritySignal(
                check="name_sanity",
                verdict="REFUSE",
                detail=f"Invalid package name shape: {name!r}",
                confidence=1.0,
            ))
            return signals

        # Known-malicious: hard refuse.
        if name in _KNOWN_MALICIOUS:
            signals.append(SecuritySignal(
                check="known_malicious",
                verdict="REFUSE",
                detail=f"{name} is on Daena's known-malicious list",
                confidence=1.0,
            ))
            return signals

        # Typosquat: if the name is close to a popular target but not
        # the target itself, WARN (not REFUSE -- may be a legitimate
        # derivative / fork).
        if name not in _TYPOSQUAT_TARGETS:
            closest, distance = self._closest_popular(name)
            if closest and 0 < distance <= 2:
                signals.append(SecuritySignal(
                    check="typosquat",
                    verdict="WARN",
                    detail=(
                        f"Name {name!r} is {distance} edit(s) from {closest!r}. "
                        "Could be typosquat; verify intent."
                    ),
                    confidence=0.7,
                ))

        return signals

    @staticmethod
    def _closest_popular(name: str) -> tuple[str | None, int]:
        """Find the closest popular-package match by Levenshtein."""
        best: tuple[str | None, int] = (None, 99)
        # Skip very short names -- too many false positives
        # (e.g. "six" is close to "six").
        if len(name) < 4:
            return best
        for target in _TYPOSQUAT_TARGETS:
            d = _levenshtein(name, target)
            if d < best[1]:
                best = (target, d)
        return best

    # ── Network checks ──────────────────────────────────────────────

    async def _run_network_checks(
        self, context: IngestionContext,
    ) -> list[SecuritySignal]:
        """Network-backed provenance. Timeout-bounded; failures are
        soft (WARN, not REFUSE) so network blips don't block Daena."""
        signals: list[SecuritySignal] = []
        if context.artifact_type != ArtifactType.PIP_PACKAGE:
            return signals

        try:
            result = await asyncio.wait_for(
                self._pypi_metadata(context.identifier),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            signals.append(SecuritySignal(
                check="pypi_metadata",
                verdict="WARN",
                detail="PyPI metadata lookup timed out; skipping provenance check",
                confidence=0.3,
            ))
            return signals
        except Exception as exc:
            signals.append(SecuritySignal(
                check="pypi_metadata",
                verdict="WARN",
                detail=f"PyPI lookup failed: {exc}",
                confidence=0.3,
            ))
            return signals

        if result is None:
            # No entry on PyPI -- could be typo, private index, or
            # malicious. REFUSE for auto-heal (we should only install
            # known real packages autonomously); WARN for LLM-initiated
            # (the LLM might be installing from an alt index).
            verdict: Verdict = (
                "REFUSE" if context.triggered_by == TriggerSource.AUTO_HEAL else "WARN"
            )
            signals.append(SecuritySignal(
                check="pypi_existence",
                verdict=verdict,
                detail=f"{context.identifier} not found on PyPI",
                confidence=0.9,
            ))
            return signals

        # Age check: very new packages are riskier.
        age_days = result.get("age_days", 0)
        if age_days < 30:
            signals.append(SecuritySignal(
                check="package_age",
                verdict="WARN",
                detail=(
                    f"Package is only {age_days} days old on PyPI. "
                    "New packages with few downloads are higher-risk."
                ),
                confidence=0.5,
            ))
        else:
            signals.append(SecuritySignal(
                check="package_age",
                verdict="PASS",
                detail=f"Package is {age_days} days old on PyPI",
                confidence=0.8,
            ))

        return signals

    async def _pypi_metadata(self, package: str) -> dict[str, Any] | None:
        """Fetch minimal metadata from PyPI JSON API.

        Returns a dict with ``age_days``, ``version``, ``home_page`` or
        ``None`` if the package doesn't exist.
        """
        import httpx
        url = f"https://pypi.org/pypi/{package}/json"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()

        info = data.get("info", {}) or {}
        releases = data.get("releases", {}) or {}

        # Age = days since the FIRST release, not the latest.
        first_upload = None
        for _, files in releases.items():
            if not isinstance(files, list):
                continue
            for f in files:
                upload_time = f.get("upload_time")
                if upload_time and (first_upload is None or upload_time < first_upload):
                    first_upload = upload_time

        age_days = 0
        if first_upload:
            from datetime import datetime, timezone
            try:
                # ISO format "2021-01-15T12:34:56"
                ts = datetime.fromisoformat(first_upload.rstrip("Z")).replace(
                    tzinfo=timezone.utc,
                )
                age_days = (datetime.now(timezone.utc) - ts).days
            except Exception:
                age_days = 0

        return {
            "age_days": age_days,
            "version": info.get("version"),
            "home_page": info.get("home_page"),
            "summary": info.get("summary", "")[:200],
        }

    # ── Need analysis (intelligence side) ───────────────────────────

    async def _need_analysis(
        self, context: IngestionContext,
    ) -> tuple[SecuritySignal, str]:
        """Do we need this ingestion?

        Heuristic first, LLM-backed synthesis when signals disagree.
        For MVP this is pattern-based; future versions should call the
        OODA engine with the ingestion context and the current task.
        """
        if context.artifact_type == ArtifactType.PIP_PACKAGE:
            # Check if already importable -- most common "don't need"
            # signal. If the module is already installed, the original
            # error was probably about a different issue.
            name = context.identifier.lower()
            already = self._already_installed(name)
            if already:
                return (
                    SecuritySignal(
                        check="need_analysis",
                        verdict="REFUSE",
                        detail=(
                            f"{name} is already installed; install would be "
                            "redundant. Original error likely stems from "
                            "path / env mismatch, not a missing module."
                        ),
                        confidence=0.9,
                    ),
                    (
                        f"Not needed: {name} is already available to the "
                        "running interpreter. Re-installing wouldn't fix "
                        "the underlying error."
                    ),
                )

        # Default: we probably need it. The security signals carry the
        # weight; need-analysis contributes a PASS unless we have reason
        # to doubt.
        return (
            SecuritySignal(
                check="need_analysis",
                verdict="PASS",
                detail=(
                    f"Triggered by {context.triggered_by.value}: "
                    f"{context.reason[:140] or 'no specific reason given'}"
                ),
                confidence=0.7,
            ),
            (
                f"Appears needed: {context.triggered_by.value} path with "
                f"reason {context.reason[:140] or '<no reason>'}"
            ),
        )

    # ── Content scan (prompt-injection defense) ─────────────────────

    def _content_scan(
        self, context: IngestionContext,
    ) -> tuple[SecuritySignal, dict[str, Any]]:
        """Run the prompt-injection scanner against ``context.content``.

        Maps the artifact type to the appropriate ``ScanContext`` so
        skill ingestion is strict (memory contamination is expensive
        to reverse) and chat-input-like surfaces are lenient (LLM sees
        the content at Stage 8 anyway and can reason about it).

        Returns ``(SecuritySignal, content_scan_dict)`` where the dict
        carries the scanner's verdict + decision + cleaned_content +
        quarantined fragments for the caller to act on.
        """
        from app.services.security.prompt_injection_scanner import (
            PromptInjectionScanner,
            ScanContext as _SC,
        )

        # Map artifact type -> scanner trust context.
        artifact_to_scan_ctx = {
            ArtifactType.SKILL: _SC.SKILL_INGESTION,
            ArtifactType.BOOK: _SC.BOOK_INGESTION,
            ArtifactType.FILE: _SC.FILE_CONTENT,
            ArtifactType.EMAIL_ATTACHMENT: _SC.EMAIL_ATTACHMENT,
        }
        scan_ctx = artifact_to_scan_ctx.get(context.artifact_type, _SC.CHAT_INPUT)

        scanner = PromptInjectionScanner()
        result = scanner.scan(context.content, scan_ctx)

        # Map scanner verdict -> filter signal.
        signal_verdict: Verdict
        if result.decision == "REFUSE_ENTIRELY":
            signal_verdict = "REFUSE"
        elif result.decision == "USE_CLEAN" and result.verdict != "CLEAN":
            signal_verdict = "WARN"
        elif result.decision == "USE_ORIGINAL_WITH_WARNING":
            signal_verdict = "WARN"
        else:
            signal_verdict = "PASS"

        signal = SecuritySignal(
            check="prompt_injection_scan",
            verdict=signal_verdict,
            detail=(
                f"scan_verdict={result.verdict} "
                f"decision={result.decision} "
                f"findings={len(result.findings)} "
                f"quarantined={len(result.quarantined)} "
                f"-- {result.reason}"
            ),
            confidence=0.85,
            latency_ms=result.total_ms,
        )
        scan_payload = {
            "verdict": result.verdict,
            "decision": result.decision,
            "findings": [
                {
                    "category": f.category,
                    "severity": f.severity.value,
                    "pattern": f.pattern,
                    "start": f.start,
                    "end": f.end,
                    "confidence": f.confidence,
                    "matched_text": f.matched_text[:120],
                }
                for f in result.findings
            ],
            "cleaned_content": result.cleaned_content,
            "quarantined": result.quarantined,
            "reason": result.reason,
            "total_ms": result.total_ms,
            "original_length": result.original_length,
            "cleaned_length": result.cleaned_length,
        }
        return signal, scan_payload

    @staticmethod
    def _already_installed(package: str) -> bool:
        """Check if a package is already importable."""
        import importlib.util
        try:
            # Try both the given name and its normalized import name.
            # E.g. "python-dateutil" imports as "dateutil".
            candidates = {package, package.replace("-", "_"), package.replace("-", "")}
            for name in candidates:
                if importlib.util.find_spec(name) is not None:
                    return True
        except Exception:
            pass
        return False

    # ── Synthesis ───────────────────────────────────────────────────

    def _synthesize(
        self,
        context: IngestionContext,
        signals: list[SecuritySignal],
        t0: float,
    ) -> FilterVerdict:
        """Combine signals into a single verdict.

        Rules:
        * Any REFUSE -> REFUSE.
        * Any WARN and no REFUSE:
            - In AGI mode + AUTO_HEAL: escalate to REFUSE (safer default
              for autonomous install).
            - Otherwise: WARN (surfaces approval gate).
        * All PASS -> PASS.
        """
        import time
        refuses = [s for s in signals if s.verdict == "REFUSE"]
        warns = [s for s in signals if s.verdict == "WARN"]
        passes = [s for s in signals if s.verdict == "PASS"]

        total_ms = (time.perf_counter() - t0) * 1000

        if refuses:
            strongest = max(refuses, key=lambda s: s.confidence)
            return FilterVerdict(
                decision="REFUSE",
                confidence=strongest.confidence,
                signals=signals,
                reason=strongest.detail,
                total_latency_ms=total_ms,
            )

        if warns:
            # AUTO_HEAL is the one path where WARN escalates to REFUSE:
            # the whole point of auto-heal is silent self-recovery, and
            # an ambiguous signal there means we should NOT silently
            # install -- better to fall back to the LLM-initiated path
            # which surfaces the approval gate explicitly.
            if context.triggered_by == TriggerSource.AUTO_HEAL:
                strongest = max(warns, key=lambda s: s.confidence)
                return FilterVerdict(
                    decision="REFUSE",
                    confidence=strongest.confidence,
                    signals=signals,
                    reason=(
                        f"Auto-heal refused: {strongest.detail} "
                        "(AUTO_HEAL escalates WARN to REFUSE for safety; "
                        "use install_system_tool to request explicitly)"
                    ),
                    total_latency_ms=total_ms,
                )

            strongest = max(warns, key=lambda s: s.confidence)
            avg_conf = sum(s.confidence for s in signals) / max(len(signals), 1)
            return FilterVerdict(
                decision="WARN",
                confidence=avg_conf,
                signals=signals,
                reason=strongest.detail,
                total_latency_ms=total_ms,
            )

        avg_conf = sum(s.confidence for s in passes) / max(len(passes), 1)
        return FilterVerdict(
            decision="PASS",
            confidence=avg_conf,
            signals=signals,
            reason="All security + intelligence checks passed",
            total_latency_ms=total_ms,
        )
