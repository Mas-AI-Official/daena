"""ai-qa-loop adapter: the deterministic QA/QC verification capability wired into Daena.

This is the real backend behind the TLM "qa.run_loop" tool. It shells the ai-qa-loop
engine (a stdlib-only, token-free verifier that lives OUTSIDE this repo) and returns a
structured verdict. The engine runs the SAME loop over three profiles (http_api for
finance APIs, llm_agent for AI behaviour, daena for governance); in deterministic mode it
spends ZERO model tokens and the oracle still computes every verdict.

Honesty contract (ADR-001):
  Where does the result persist? Every run writes a JSON report to report_path (a temp file
  by default) and the structured QaResult carries the counts plus the breach list. Nothing
  is silently discarded.

  How does the caller see it fail? Failure is never a fabricated pass. The engine being
  absent returns status="unavailable"; a timeout returns "timeout"; a crashed subprocess
  returns "error" with stderr captured; a BREACHED invariant returns ok=False with the
  breach list; a run that could verify nothing returns "inconclusive". The caller always
  gets an explicit, inspectable status.

The engine lives at AQA_ENGINE_DIR (default D:\\agents\\skills\\ai-qa-loop\\engine). In a
slim or Docker deployment the engine is absent; engine_available() reports that honestly and
the TLM registration is skipped, so Daena never advertises a capability it cannot run.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.tool_lifecycle.tool_registry import (
    GovernanceRules,
    ToolDefinition,
    ToolRegistry,
)

logger = get_logger(__name__)

# Where the ai-qa-loop engine lives. Configurable so Docker or CI can point at a mounted
# copy, or leave it unset (engine absent) and the capability degrades gracefully.
_DEFAULT_ENGINE_DIR = r"D:\agents\skills\ai-qa-loop\engine"

# Status vocabulary. Every run resolves to exactly one of these.
STATUS_CLEAN = "clean"                 # ran, at least one control HELD, zero breaches
STATUS_BREACHED = "breached"           # ran, at least one invariant BREACHED (gate fails)
STATUS_INCONCLUSIVE = "inconclusive"   # ran, but nothing held and nothing breached
STATUS_UNAVAILABLE = "unavailable"     # engine not present on this host
STATUS_TIMEOUT = "timeout"             # engine exceeded the hard timeout
STATUS_ERROR = "error"                 # engine crashed, bad exit, or unreadable report

QA_TOOL_ID = "qa.run_loop"

DEFAULT_TIMEOUT_SECONDS = 180.0


def engine_dir() -> Path:
    """Resolve the engine directory. The AQA_ENGINE_DIR env var wins over the default."""
    return Path(os.environ.get("AQA_ENGINE_DIR", _DEFAULT_ENGINE_DIR))


def engine_available() -> bool:
    """True only when the engine is actually runnable on this host (its package is present).

    Gates TLM registration: when this is False, Daena does not advertise qa.run_loop, so the
    tool catalog never lists a capability the deployment cannot execute.
    """
    try:
        return (engine_dir() / "aqa" / "__main__.py").is_file()
    except Exception:
        return False


@dataclass(slots=True)
class QaResult:
    """Structured outcome of a QA loop run. ok is True ONLY for an affirmatively clean run."""

    status: str
    ok: bool
    profile: str = ""
    mode: str = ""
    held: int = 0
    breached: int = 0
    inconclusive: int = 0
    breaches: list[str] = field(default_factory=list)
    verdict: str = ""
    report_path: str | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ok": self.ok,
            "profile": self.profile,
            "mode": self.mode,
            "held": self.held,
            "breached": self.breached,
            "inconclusive": self.inconclusive,
            "breaches": list(self.breaches),
            "verdict": self.verdict,
            "report_path": self.report_path,
            "detail": self.detail,
        }


def _read_summary(path: str) -> dict[str, Any] | None:
    """Read the engine JSON report and return its summary block, or None if unreadable."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    summary = data.get("summary")
    if isinstance(summary, dict):
        return summary
    # Defensive fallback: accept a report that is already summary shaped.
    if "breached" in data or "held" in data:
        return data
    return None


def _cleanup(path: str | None) -> None:
    if not path:
        return
    with contextlib.suppress(Exception):
        os.unlink(path)


async def _exec_engine(argv: list[str], timeout: float) -> tuple[int, str, str]:
    """Run the engine as a subprocess under a hard timeout.

    Returns (rc, stdout, stderr). rc is -1 when the process had to be killed for exceeding
    the timeout. Raising is reserved for genuine programming errors, not operational ones.
    """
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")  # engine prints verdict glyphs
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(engine_dir()),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
            await proc.communicate()
        return -1, "", f"timed out after {timeout:.0f}s"
    return (
        proc.returncode if proc.returncode is not None else -1,
        out.decode("utf-8", "replace"),
        err.decode("utf-8", "replace"),
    )


async def run_qa_loop(
    base_url: str = "http://localhost:8000",
    *,
    profile: str = "auto",
    mode: str = "deterministic",
    gate: bool = True,
    max_rounds: int | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    report_path: str | None = None,
) -> QaResult:
    """Run the QA/QC verification loop against a target and return a structured verdict.

    Args:
        base_url: the target under test (a Daena instance, an HTTP API, an LLM endpoint).
        profile: auto | http_api | llm_agent | daena. "auto" lets the engine pick the right
            pack (the precise daena detector wins on a Daena tree). The daena governance
            profile is the MAS-AI showpiece: it asks "did governance hold?".
        mode: "deterministic" (default) spends ZERO model tokens and the oracle still runs.
            "openai" or "claude-cli" only add prose narration and DO cost tokens.
        gate: when True, a BREACHED invariant drives ok=False (the QC gate, as used in CI).
        max_rounds: optional override of the engine loop rounds.
        timeout: hard wall-clock ceiling. The subprocess is killed past it (status="timeout").
        report_path: where to persist the JSON report. A temp file is used when None.

    Returns:
        A QaResult. This never raises for an operational failure: engine-absent, timeout, and
        crash each resolve to an explicit status. Programming errors still raise.
    """
    if not engine_available():
        logger.warning("qa.engine_unavailable", engine_dir=str(engine_dir()))
        return QaResult(
            status=STATUS_UNAVAILABLE,
            ok=False,
            detail=f"ai-qa-loop engine not found at {engine_dir()}; set AQA_ENGINE_DIR.",
        )

    own_report = report_path is None
    if own_report:
        fd, report_path = tempfile.mkstemp(prefix="daena_qa_", suffix=".report.json")
        os.close(fd)

    argv = [
        sys.executable, "-m", "aqa",
        "--base-url", base_url,
        "--profile", profile,
        "--mode", mode,
        "--out", report_path,
        "--quiet",
    ]
    if gate:
        argv.append("--gate")
    if max_rounds is not None:
        argv += ["--max-rounds", str(max_rounds)]

    rc, _out, err = await _exec_engine(argv, timeout)

    if rc == -1:
        if own_report:
            _cleanup(report_path)
        logger.warning("qa.timeout", base_url=base_url, timeout=timeout)
        return QaResult(
            status=STATUS_TIMEOUT,
            ok=False,
            detail=f"QA loop exceeded {timeout:.0f}s and was terminated.",
        )

    if rc == 2:
        if own_report:
            _cleanup(report_path)
        return QaResult(
            status=STATUS_ERROR,
            ok=False,
            detail=f"engine usage error: {err.strip()[:400]}",
        )

    # rc 0 (clean or gate pass) or 1 (gate fired on a breach). The exit code is only the gate
    # signal; the JSON report is the source of truth for the actual counts.
    summary = _read_summary(report_path)
    if summary is None:
        if own_report:
            _cleanup(report_path)
        return QaResult(
            status=STATUS_ERROR,
            ok=False,
            detail=(
                f"engine exited rc={rc} but no readable report at {report_path}; "
                f"stderr: {err.strip()[:400]}"
            ),
        )

    held = int(summary.get("held", 0))
    breached = int(summary.get("breached", 0))
    inconclusive = int(summary.get("inconclusive", 0))
    if breached > 0:
        status = STATUS_BREACHED
    elif held == 0 and inconclusive > 0:
        status = STATUS_INCONCLUSIVE
    else:
        status = STATUS_CLEAN

    result = QaResult(
        status=status,
        ok=(status == STATUS_CLEAN),
        profile=str(summary.get("profile", "")),
        mode=str(summary.get("mode", "")),
        held=held,
        breached=breached,
        inconclusive=inconclusive,
        breaches=[str(b) for b in summary.get("breaches", [])],
        verdict=str(summary.get("verdict", "")),
        report_path=report_path,
    )
    logger.info(
        "qa.completed",
        status=status,
        profile=result.profile,
        held=held,
        breached=breached,
        inconclusive=inconclusive,
    )
    return result


async def run_selftest(timeout: float = 60.0) -> QaResult:
    """Health-check the QA capability itself: run the engine offline self-test.

    The self-test drives three profiles over in-process mocks with planted bugs, spending
    ZERO tokens and touching no network. If it passes, the loop and the oracle are sound on
    this host. Returns ok=True only when the self-test passes.
    """
    if not engine_available():
        return QaResult(
            status=STATUS_UNAVAILABLE,
            ok=False,
            detail=f"ai-qa-loop engine not found at {engine_dir()}.",
        )
    rc, out, err = await _exec_engine([sys.executable, "-m", "aqa", "--selftest"], timeout)
    if rc == -1:
        return QaResult(status=STATUS_TIMEOUT, ok=False, detail=f"self-test exceeded {timeout:.0f}s.")
    passed = rc == 0
    return QaResult(
        status=STATUS_CLEAN if passed else STATUS_BREACHED,
        ok=passed,
        detail=(out or err).strip()[-600:],
    )


def build_qa_tool_definition() -> ToolDefinition:
    """The TLM catalog entry for the QA/QC loop.

    Governed deliberately: the tool spawns a subprocess and makes network egress to an
    arbitrary base_url (an SSRF surface), so it requires approval and is scoped to the
    engineering, security, and operations departments. That is the terminal.execute_command
    posture plus an explicit approval gate.
    """
    return ToolDefinition(
        id=QA_TOOL_ID,
        name="Run QA/QC Loop",
        category="qa",
        light_description=(
            "Run the deterministic QA/QC verification loop (governance, API, or LLM "
            "invariants) against a target and return held and breached verdicts"
        ),
        full_schema={
            "type": "function",
            "name": QA_TOOL_ID,
            "description": (
                "Agentic QA loop: the model explores, a deterministic oracle judges. "
                "Spends zero model tokens in deterministic mode."
            ),
            "params": {
                "base_url": "string (target under test, e.g. http://localhost:8000)",
                "profile": "string (auto | http_api | llm_agent | daena)",
                "mode": "string (deterministic | openai | claude-cli; deterministic is free)",
                "gate": "boolean (fail on any BREACHED invariant)",
            },
        },
        governance_rules=GovernanceRules(
            requires_approval=True,
            allowed_departments=["engineering", "security", "operations"],
        ),
        estimated_schema_tokens=140,
    )


def register_qa_tool(registry: ToolRegistry) -> bool:
    """Idempotently register the QA tool into a TLM registry.

    Returns True when registered (engine present), False when skipped (engine absent, so
    Daena does not advertise a capability it cannot run).
    """
    if not engine_available():
        return False
    registry.register_or_update(build_qa_tool_definition())
    return True
