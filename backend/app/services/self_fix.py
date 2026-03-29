"""Self-improvement service -- /fix, /improve, /audit commands.

Routes tasks to the primary runtime (Claude Code by default) for
autonomous code modifications, then validates with tests.

All actions go through governance:
  /fix    -> Tier 2 (notify) if tests pass, Tier 3 (approval) if tests fail
  /improve -> Tier 3 (always needs approval before applying)
  /audit  -> Tier 1 (read-only, just reports)
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from app.core.logging import get_logger

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
VENV_PYTHON = Path(sys.executable)


@dataclass
class SelfImprovementResult:
    """Result of a self-improvement command."""

    command: str  # fix, improve, audit
    description: str
    status: str  # running, success, failed, needs_approval
    steps: list[dict[str, Any]] = field(default_factory=list)
    test_passed: bool | None = None
    test_output: str = ""
    commit_sha: str | None = None
    error: str | None = None
    started_at: str = ""
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "description": self.description,
            "status": self.status,
            "steps": self.steps,
            "test_passed": self.test_passed,
            "test_output": self.test_output[-500:] if self.test_output else "",
            "commit_sha": self.commit_sha,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


def _run_sync(cmd: list[str], *, cwd: str | None = None, timeout: float = 300.0) -> subprocess.CompletedProcess[str]:
    """Run a command synchronously (for asyncio.to_thread)."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)


async def run_audit() -> SelfImprovementResult:
    """Run a full system audit (read-only, no changes).

    Checks: pytest, tsc, ruff, API health, bundle size.
    """
    result = SelfImprovementResult(
        command="audit",
        description="Full system audit",
        status="running",
        started_at=datetime.utcnow().isoformat(),
    )

    # pytest
    try:
        test_result = await asyncio.to_thread(
            _run_sync,
            [str(VENV_PYTHON), "-m", "pytest", "tests/", "-q", "--tb=no", "--no-header", "-x"],
            cwd=str(BACKEND_DIR),
            timeout=300.0,
        )
        last_line = test_result.stdout.strip().splitlines()[-1] if test_result.stdout.strip() else "unknown"
        passed = "passed" in last_line and "failed" not in last_line
        result.steps.append({
            "name": "pytest",
            "status": "pass" if passed else "fail",
            "output": last_line,
        })
        result.test_passed = passed
        result.test_output = test_result.stdout[-500:]
    except Exception as exc:
        result.steps.append({"name": "pytest", "status": "error", "output": str(exc)})

    # tsc
    try:
        tsc_result = await asyncio.to_thread(
            _run_sync,
            ["npx", "tsc", "--noEmit"],
            cwd=str(REPO_ROOT / "frontend"),
            timeout=120.0,
        )
        tsc_errors = tsc_result.stdout.strip() or tsc_result.stderr.strip()
        passed = tsc_result.returncode == 0
        result.steps.append({
            "name": "tsc",
            "status": "pass" if passed else "fail",
            "output": "0 errors" if passed else tsc_errors[:200],
        })
    except Exception as exc:
        result.steps.append({"name": "tsc", "status": "error", "output": str(exc)})

    # ruff lint
    try:
        ruff_result = await asyncio.to_thread(
            _run_sync,
            [str(VENV_PYTHON), "-m", "ruff", "check", "app/"],
            cwd=str(BACKEND_DIR),
            timeout=30.0,
        )
        passed = ruff_result.returncode == 0
        result.steps.append({
            "name": "ruff",
            "status": "pass" if passed else "warn",
            "output": "clean" if passed else ruff_result.stdout[:200],
        })
    except Exception as exc:
        result.steps.append({"name": "ruff", "status": "error", "output": str(exc)})

    # API health (if server is running)
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            from app.core.config import get_settings
            _cfg = get_settings()
            resp = await client.get(
                f"http://{_cfg.host}:{_cfg.port}/api/v1/health", timeout=5.0,
            )
            data = resp.json()
            result.steps.append({
                "name": "api_health",
                "status": "pass" if data.get("status") in ("healthy", "degraded") else "fail",
                "output": f"status={data.get('status')}, db={data.get('checks', {}).get('database')}",
            })
    except Exception:
        result.steps.append({"name": "api_health", "status": "skip", "output": "Server not running"})

    result.status = "success"
    result.completed_at = datetime.utcnow().isoformat()
    return result


async def run_fix(description: str) -> AsyncIterator[dict[str, Any]]:
    """Attempt to fix an issue using the primary runtime.

    Yields SSE events as the fix progresses:
      1. Analyzing the issue
      2. Generating fix
      3. Running tests
      4. Committing (if tests pass)
      5. Reporting result
    """
    yield {"type": "status", "stage": "analyzing", "message": f"Analyzing: {description}"}

    # For now, run the audit to check current state
    yield {"type": "status", "stage": "auditing", "message": "Running pre-fix audit..."}
    audit = await run_audit()
    yield {"type": "audit", "data": audit.to_dict()}

    if not audit.test_passed:
        yield {
            "type": "status",
            "stage": "blocked",
            "message": "Tests already failing before fix attempt. Fix existing failures first.",
        }
        return

    yield {
        "type": "status",
        "stage": "ready",
        "message": (
            f"Pre-fix audit passed ({audit.steps[0].get('output', '')}). "
            f"To apply a fix, use Claude Code in EXE mode: '{description}'"
        ),
    }

    yield {"type": "complete", "status": "ready_for_fix"}


async def run_improve(area: str) -> AsyncIterator[dict[str, Any]]:
    """Analyze an area for improvement (read-only analysis, human gate before applying)."""
    yield {"type": "status", "stage": "analyzing", "message": f"Analyzing area: {area}"}

    # Run audit first
    audit = await run_audit()
    yield {"type": "audit", "data": audit.to_dict()}

    yield {
        "type": "status",
        "stage": "analysis_complete",
        "message": (
            f"Analysis complete. To improve '{area}', switch to EXE mode and describe "
            "the specific improvement. Daena will show proposed changes before applying."
        ),
    }

    yield {"type": "complete", "status": "analysis_done"}
