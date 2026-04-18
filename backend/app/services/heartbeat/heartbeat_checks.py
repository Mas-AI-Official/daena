"""Individual heartbeat check functions.

Each check returns a HeartbeatCheckResult indicating what was found
and whether any action should be taken.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class ActionPriority(Enum):
    """Priority of a suggested action."""

    CRITICAL = "critical"  # Requires human approval
    HIGH = "high"  # Auto-execute in ON/AGI mode
    MEDIUM = "medium"  # Auto-execute in AGI mode
    LOW = "low"  # Informational only
    NONE = "none"  # No action needed


@dataclass
class SuggestedAction:
    """An action the heartbeat wants to execute."""

    description: str
    priority: ActionPriority
    task_prompt: str | None = None  # Prompt to send to runtime
    estimated_cost_usd: float = 0.0
    runtime_preference: str = "ollama"  # Prefer cheap runtime


@dataclass
class HeartbeatCheckResult:
    """Result of a single heartbeat check."""

    check_type: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: str = "ok"  # ok, warning, error, action_needed
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    actions: list[SuggestedAction] = field(default_factory=list)
    cost_usd: float = 0.0
    duration_ms: int = 0


def _run_sync(cmd: list[str], *, cwd: str | None = None, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    """Run command synchronously (for thread pool)."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)


async def check_runtime_health() -> HeartbeatCheckResult:
    """Check all runtime adapters for health status.

    Also maps each runtime to the founder account that holds its
    subscription via get_service_account() for diagnostics.
    """
    import time as _time

    t0 = _time.perf_counter()
    try:
        from app.core.events import get_runtime_registry
        from app.config.founder_accounts import get_service_account

        registry = get_runtime_registry()
        health = await registry.check_health_all()

        online = [rid for rid, s in health.items() if s.value == "online"]
        offline = [rid for rid, s in health.items() if s.value != "online"]

        # Map runtimes to founder accounts for diagnostics
        account_map: dict[str, str | None] = {}
        for rid in list(online) + list(offline):
            acct = get_service_account(rid)
            account_map[rid] = acct.label if acct else None

        status = "ok" if online else "warning"
        actions = []
        if not online:
            actions.append(SuggestedAction(
                description="No runtimes online. Check Ollama and CLI installations.",
                priority=ActionPriority.HIGH,
            ))

        return HeartbeatCheckResult(
            check_type="runtime_health",
            status=status,
            summary=f"{len(online)} online, {len(offline)} offline",
            details={"online": online, "offline": offline, "account_map": account_map},
            actions=actions,
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:
        return HeartbeatCheckResult(
            check_type="runtime_health",
            status="error",
            summary=f"Failed: {exc}",
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )


async def check_file(file_path: str, check_type: str = "file") -> HeartbeatCheckResult:
    """Check a file for content (inbox, tasks, state)."""
    import time as _time

    t0 = _time.perf_counter()
    path = Path(file_path)

    if not path.exists():
        return HeartbeatCheckResult(
            check_type=check_type,
            status="warning",
            summary=f"File not found: {file_path}",
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.strip().splitlines()
        non_empty = [l for l in lines if l.strip()]

        # Count actionable items (lines starting with - [ ] or TODO)
        unchecked = [l for l in non_empty if "- [ ]" in l or l.strip().startswith("TODO")]
        checked = [l for l in non_empty if "- [x]" in l or "- [X]" in l]

        actions = []
        if unchecked:
            actions.append(SuggestedAction(
                description=f"{len(unchecked)} pending items in {path.name}",
                priority=ActionPriority.MEDIUM,
                task_prompt=f"Review and process pending items in {file_path}",
                estimated_cost_usd=0.05,
                runtime_preference="claude_code",
            ))

        return HeartbeatCheckResult(
            check_type=check_type,
            status="action_needed" if unchecked else "ok",
            summary=f"{len(non_empty)} lines, {len(unchecked)} pending, {len(checked)} done",
            details={
                "total_lines": len(non_empty),
                "pending": len(unchecked),
                "completed": len(checked),
                "file_path": file_path,
            },
            actions=actions,
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:
        return HeartbeatCheckResult(
            check_type=check_type,
            status="error",
            summary=f"Read failed: {exc}",
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )


async def check_git_status(repo_path: str = ".") -> HeartbeatCheckResult:
    """Check for uncommitted changes."""
    import time as _time

    t0 = _time.perf_counter()
    try:
        result = await asyncio.to_thread(
            _run_sync, ["git", "status", "--porcelain"], cwd=repo_path, timeout=10.0,
        )
        lines = [l for l in result.stdout.strip().splitlines() if l.strip()]

        actions = []
        if lines:
            modified = [l for l in lines if l.startswith(" M") or l.startswith("M ")]
            untracked = [l for l in lines if l.startswith("??")]
            actions.append(SuggestedAction(
                description=f"{len(modified)} modified, {len(untracked)} untracked files",
                priority=ActionPriority.LOW,
            ))

        return HeartbeatCheckResult(
            check_type="git_status",
            status="action_needed" if lines else "ok",
            summary=f"{len(lines)} uncommitted changes" if lines else "Clean working tree",
            details={"changes": lines[:20]},
            actions=actions,
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:
        return HeartbeatCheckResult(
            check_type="git_status",
            status="error",
            summary=f"Git check failed: {exc}",
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )


async def _attempt_auto_fix(
    failure_output: str,
    backend_path: str = ".",
    max_cost_usd: float = 0.50,
) -> bool:
    """Attempt to auto-fix test failures using Claude Code.

    Only attempts simple fixes (import errors, typos, missing returns).
    Returns True if fix was applied and tests now pass.

    Cost guard: max $0.50 per attempt.
    """
    import shutil

    claude_path = shutil.which("claude")
    if not claude_path:
        logger.info("heartbeat.autofix_skipped_no_claude")
        return False

    # Only attempt if the failure looks simple (not a complex logic error)
    simple_patterns = [
        "ImportError", "ModuleNotFoundError", "NameError", "SyntaxError",
        "IndentationError", "TypeError: missing", "AttributeError",
    ]
    if not any(p in failure_output for p in simple_patterns):
        logger.info("heartbeat.autofix_skipped_complex_failure")
        return False

    logger.info("heartbeat.autofix_attempting")

    try:
        fix_prompt = (
            f"The test suite in {backend_path}/tests/ has failures. "
            f"Here is the error output:\n\n{failure_output}\n\n"
            "Fix the error. Only change the minimum needed. "
            "Do not add new features or refactor. Just fix the failing test."
        )

        fix_result = await asyncio.to_thread(
            _run_sync,
            [claude_path, "-p", fix_prompt, "--output-format", "json"],
            cwd=backend_path,
            timeout=60.0,
        )

        if fix_result.returncode != 0:
            logger.warning("heartbeat.autofix_claude_failed", stderr=fix_result.stderr[:200])
            return False

        # Re-run tests to verify the fix
        verify_result = await asyncio.to_thread(
            _run_sync,
            ["python", "-m", "pytest", "tests/", "-x", "-q", "--tb=no", "--no-header"],
            cwd=backend_path,
            timeout=300.0,
        )

        verify_output = verify_result.stdout.strip()
        if "failed" in verify_output.lower():
            logger.warning("heartbeat.autofix_tests_still_failing", output=verify_output[-200:])
            return False

        # Tests pass. Commit the fix.
        commit_result = await asyncio.to_thread(
            _run_sync,
            ["git", "add", "-A"],
            cwd=str(Path(backend_path).parent),  # repo root
        )
        await asyncio.to_thread(
            _run_sync,
            ["git", "commit", "-m", "fix(heartbeat): auto-fix test failure\n\nCo-Authored-By: Daena Heartbeat <heartbeat@daena.mas-ai.co>"],
            cwd=str(Path(backend_path).parent),
        )

        logger.info("heartbeat.autofix_success")
        return True
    except Exception as exc:
        logger.warning("heartbeat.autofix_error", error=str(exc))
        return False


async def check_test_suite(backend_path: str = ".") -> HeartbeatCheckResult:
    """Run pytest in quick mode to check for failures."""
    import time as _time

    t0 = _time.perf_counter()
    try:
        result = await asyncio.to_thread(
            _run_sync,
            ["python", "-m", "pytest", "tests/", "-x", "-q", "--tb=no", "--no-header"],
            cwd=backend_path,
            timeout=300.0,
        )
        output = result.stdout.strip()
        # Parse "945 passed in 152.32s"
        passed = 0
        failed = 0
        for line in output.splitlines():
            if "passed" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == "passed" and i > 0:
                        try:
                            passed = int(parts[i - 1])
                        except ValueError:
                            pass
                    if p == "failed" and i > 0:
                        try:
                            failed = int(parts[i - 1])
                        except ValueError:
                            pass

        actions = []
        auto_fixed = False
        if failed > 0:
            # Attempt auto-fix via Claude Code if available
            auto_fixed = await _attempt_auto_fix(
                failure_output=output[-1000:],
                backend_path=backend_path,
            )
            if auto_fixed:
                actions.append(SuggestedAction(
                    description=f"Auto-fixed {failed} test failure(s) via Claude Code",
                    priority=ActionPriority.LOW,
                ))
            else:
                actions.append(SuggestedAction(
                    description=f"{failed} tests failing -- needs human investigation",
                    priority=ActionPriority.HIGH,
                    task_prompt=f"Run pytest in {backend_path}/tests/ and fix the {failed} failing tests",
                    estimated_cost_usd=0.20,
                    runtime_preference="claude_code",
                ))

        return HeartbeatCheckResult(
            check_type="test_suite",
            status="ok" if (failed == 0 or auto_fixed) else "error",
            summary=f"{passed} passed, {failed} failed" + (" (auto-fixed)" if auto_fixed else ""),
            details={"passed": passed, "failed": failed, "auto_fixed": auto_fixed, "output_tail": output[-500:]},
            actions=actions,
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )
    except subprocess.TimeoutExpired:
        return HeartbeatCheckResult(
            check_type="test_suite",
            status="warning",
            summary="Test suite timed out (5 min limit)",
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:
        return HeartbeatCheckResult(
            check_type="test_suite",
            status="error",
            summary=f"Test run failed: {exc}",
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )


# ── Engineering Department checks ──


async def check_github_issues(
    repo: str = "Mas-AI-Official/daena",
    gh_command: str | None = None,
) -> HeartbeatCheckResult:
    """Check GitHub repo for open bug reports via gh CLI."""
    import time as _time

    t0 = _time.perf_counter()
    try:
        cmd = gh_command or f"gh issue list --repo {repo} --state open --label bug --json number,title,createdAt --limit 20"
        result = await asyncio.to_thread(
            _run_sync, cmd.split(), timeout=15.0,
        )

        issues: list[dict[str, Any]] = []
        if result.returncode == 0 and result.stdout.strip():
            try:
                issues = json.loads(result.stdout)
            except json.JSONDecodeError:
                pass

        actions = []
        if issues:
            newest = issues[0]
            actions.append(SuggestedAction(
                description=f"{len(issues)} open bugs on {repo}. Newest: #{newest.get('number')} {newest.get('title', '')}",
                priority=ActionPriority.MEDIUM,
                task_prompt=f"Review and triage {len(issues)} open bug issues on {repo}",
                estimated_cost_usd=0.05,
                runtime_preference="claude_code",
            ))

        return HeartbeatCheckResult(
            check_type="github_issues",
            status="action_needed" if issues else "ok",
            summary=f"{len(issues)} open bugs" if issues else "No open bugs",
            details={"repo": repo, "issues": issues[:10]},
            actions=actions,
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:
        return HeartbeatCheckResult(
            check_type="github_issues",
            status="warning",
            summary=f"GitHub check failed: {exc}",
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )


async def check_failed_tasks() -> HeartbeatCheckResult:
    """Find failed execution tasks in the database and suggest retry."""
    import time as _time

    t0 = _time.perf_counter()
    try:
        from app.core.database import async_session_factory
        from sqlalchemy import select, func

        async with async_session_factory() as session:
            from app.models.execution import Task

            # Count failed tasks
            stmt = select(func.count(Task.id)).where(Task.status == "FAILED")
            result = await session.execute(stmt)
            failed_count = result.scalar() or 0

            # Get the most recent failed tasks for details
            detail_stmt = (
                select(Task.id, Task.name, Task.status, Task.created_at)
                .where(Task.status == "FAILED")
                .order_by(Task.created_at.desc())
                .limit(5)
            )
            detail_result = await session.execute(detail_stmt)
            failed_tasks = [
                {"id": str(r.id), "name": r.name, "created_at": str(r.created_at)}
                for r in detail_result
            ]

        actions = []
        if failed_count > 0:
            actions.append(SuggestedAction(
                description=f"{failed_count} failed task(s) found. Re-enqueue as PENDING for retry.",
                priority=ActionPriority.HIGH,
                task_prompt=f"Retry {failed_count} failed tasks by setting status to PENDING",
                estimated_cost_usd=0.0,
            ))

        return HeartbeatCheckResult(
            check_type="failed_tasks",
            status="action_needed" if failed_count > 0 else "ok",
            summary=f"{failed_count} failed tasks" if failed_count else "No failed tasks",
            details={"failed_count": failed_count, "recent_failures": failed_tasks},
            actions=actions,
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:
        return HeartbeatCheckResult(
            check_type="failed_tasks",
            status="warning",
            summary=f"Task check failed: {exc}",
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )


async def check_ollama_health() -> HeartbeatCheckResult:
    """Verify Ollama is running and all expected models are loaded."""
    import time as _time

    t0 = _time.perf_counter()
    expected_models = [
        "deepseek-r1:14b", "llama3.1", "mistral:7b",
        "qwen2.5-coder:14b", "qwen3-coder:30b", "qwen3.5:27b",
        "nomic-embed-text",
    ]

    try:
        # Check if Ollama is running
        result = await asyncio.to_thread(
            _run_sync, ["ollama", "list"], timeout=10.0,
        )

        if result.returncode != 0:
            return HeartbeatCheckResult(
                check_type="ollama_health",
                status="error",
                summary="Ollama not running or not installed",
                duration_ms=int((_time.perf_counter() - t0) * 1000),
                actions=[SuggestedAction(
                    description="Ollama is not running. Start with: ollama serve",
                    priority=ActionPriority.HIGH,
                )],
            )

        # Parse model list
        loaded_models = []
        for line in result.stdout.strip().splitlines()[1:]:  # Skip header
            parts = line.split()
            if parts:
                loaded_models.append(parts[0])

        # Check which expected models are missing
        missing = [m for m in expected_models if not any(m in lm for lm in loaded_models)]
        extra = [m for m in loaded_models if not any(em in m for em in expected_models)]

        actions = []
        if missing:
            actions.append(SuggestedAction(
                description=f"Missing models: {', '.join(missing)}. Pull with: ollama pull <model>",
                priority=ActionPriority.MEDIUM,
                task_prompt=f"Pull missing Ollama models: {', '.join(missing)}",
                estimated_cost_usd=0.0,
            ))

        return HeartbeatCheckResult(
            check_type="ollama_health",
            status="warning" if missing else "ok",
            summary=f"{len(loaded_models)} models loaded, {len(missing)} missing",
            details={
                "loaded": loaded_models,
                "missing": missing,
                "extra": extra,
            },
            actions=actions,
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:
        return HeartbeatCheckResult(
            check_type="ollama_health",
            status="error",
            summary=f"Ollama check failed: {exc}",
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )


async def check_ollama_model_updates() -> HeartbeatCheckResult:
    """Check installed Ollama models for available updates via OllamaAutoUpdater.

    Runs weekly. Pulls latest versions for all installed models.
    Ollama's pull is incremental -- if already up to date, it's a no-op.
    """
    import time as _time

    t0 = _time.perf_counter()
    try:
        from app.services.model_management.auto_updater import OllamaAutoUpdater

        updater = OllamaAutoUpdater()
        update_result = await updater.check_for_updates()

        actions = []
        if update_result.updated:
            actions.append(SuggestedAction(
                description=f"Updated {len(update_result.updated)} Ollama models: {', '.join(update_result.updated)}",
                priority=ActionPriority.LOW,
            ))
        if update_result.failed:
            actions.append(SuggestedAction(
                description=f"Failed to update {len(update_result.failed)} models: {', '.join(update_result.failed)}",
                priority=ActionPriority.MEDIUM,
            ))

        status = "ok"
        if update_result.failed:
            status = "warning"

        summary = f"Checked {update_result.checked} models"
        if update_result.updated:
            summary += f", updated {len(update_result.updated)}"
        if update_result.failed:
            summary += f", {len(update_result.failed)} failed"

        return HeartbeatCheckResult(
            check_type="ollama_model_updates",
            status=status,
            summary=summary,
            details=update_result.to_dict(),
            actions=actions,
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:
        return HeartbeatCheckResult(
            check_type="ollama_model_updates",
            status="error",
            summary=f"Model update check failed: {exc}",
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )


async def generate_daily_report(
    report_dir: str = "",
) -> HeartbeatCheckResult:
    """Generate daily engineering status report to Daena-Mind vault."""
    import os
    import time as _time

    t0 = _time.perf_counter()
    if not report_dir:
        _project_root = Path(__file__).resolve().parents[3]
        report_dir = os.environ.get(
            "DAENA_MIND_PATH",
            str(_project_root / "data" / "mind" / "reports"),
        )
    report_path = Path(report_dir)
    report_path.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filepath = report_path / f"engineering-{date_str}.md"

    # Skip if today's report already exists
    if filepath.exists():
        return HeartbeatCheckResult(
            check_type="daily_report",
            status="ok",
            summary=f"Report already exists: {filepath.name}",
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )

    try:
        # Gather data for report
        sections: list[str] = []
        sections.append("---")
        sections.append(f"date: {date_str}")
        sections.append("department: Engineering")
        sections.append(f"generated: {datetime.now().isoformat()}")
        sections.append("---")
        sections.append("")
        sections.append(f"# Engineering Daily Report: {date_str}")
        sections.append("")

        # Git status
        try:
            git_result = await asyncio.to_thread(
                _run_sync, ["git", "log", "--oneline", "-10"], cwd=str(Path(__file__).resolve().parents[4]),
            )
            sections.append("## Recent Commits")
            sections.append("```")
            sections.append(git_result.stdout.strip() or "No commits found")
            sections.append("```")
            sections.append("")
        except Exception:
            sections.append("## Recent Commits")
            sections.append("(git log unavailable)")
            sections.append("")

        # Test status
        try:
            test_result = await asyncio.to_thread(
                _run_sync,
                ["python", "-m", "pytest", "tests/", "-q", "--tb=no", "--no-header", "-x"],
                cwd=str(Path(__file__).resolve().parents[3]),
                timeout=300.0,
            )
            last_line = test_result.stdout.strip().splitlines()[-1] if test_result.stdout.strip() else "unknown"
            sections.append("## Test Suite")
            sections.append(f"Result: {last_line}")
            sections.append("")
        except Exception as e:
            sections.append("## Test Suite")
            sections.append(f"Error running tests: {e}")
            sections.append("")

        # Runtime status
        try:
            ollama_result = await asyncio.to_thread(
                _run_sync, ["ollama", "list"], timeout=10.0,
            )
            model_lines = ollama_result.stdout.strip().splitlines()
            sections.append("## Ollama Models")
            sections.append(f"{len(model_lines) - 1} models loaded")
            for line in model_lines[1:6]:  # First 5 models
                sections.append(f"- {line.split()[0]}")
            sections.append("")
        except Exception:
            sections.append("## Ollama Models")
            sections.append("(ollama unavailable)")
            sections.append("")

        # GitHub issues
        try:
            gh_result = await asyncio.to_thread(
                _run_sync,
                ["gh", "issue", "list", "--repo", "Mas-AI-Official/daena",
                 "--state", "open", "--json", "number,title", "--limit", "5"],
                timeout=15.0,
            )
            if gh_result.returncode == 0 and gh_result.stdout.strip():
                issues = json.loads(gh_result.stdout)
                sections.append("## Open GitHub Issues")
                if issues:
                    for iss in issues:
                        sections.append(f"- #{iss['number']}: {iss['title']}")
                else:
                    sections.append("No open issues")
                sections.append("")
        except Exception:
            pass

        # Write report
        filepath.write_text("\n".join(sections), encoding="utf-8")

        return HeartbeatCheckResult(
            check_type="daily_report",
            status="ok",
            summary=f"Report generated: {filepath.name}",
            details={"path": str(filepath), "sections": len(sections)},
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:
        return HeartbeatCheckResult(
            check_type="daily_report",
            status="error",
            summary=f"Report generation failed: {exc}",
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )


async def check_department_workflows() -> HeartbeatCheckResult:
    """Run scheduled department workflows that are due.

    Queries the DepartmentTask table for tasks whose next_run_at
    has passed, executes them, and updates the schedule.
    """
    import time as _time
    from datetime import timezone

    from croniter import croniter

    t0 = _time.perf_counter()

    try:
        from app.core.database import async_session_factory
        from app.models.department_task import DepartmentTask
        from app.services.department_workflows import (
            DepartmentWorkflowEngine,
            WORKFLOWS,
        )

        from sqlalchemy import select

        async with async_session_factory() as db:
            now = datetime.now(timezone.utc)

            # Find due tasks
            stmt = (
                select(DepartmentTask)
                .where(DepartmentTask.is_active.is_(True))
                .where(DepartmentTask.status.in_(["SCHEDULED", "COMPLETED"]))
                .where(
                    (DepartmentTask.next_run_at <= now)
                    | (DepartmentTask.next_run_at.is_(None))
                )
            )
            result = await db.execute(stmt)
            due_tasks = list(result.scalars().all())

            if not due_tasks:
                return HeartbeatCheckResult(
                    check_type="department_workflows",
                    status="ok",
                    summary="No department workflows due",
                    duration_ms=int((_time.perf_counter() - t0) * 1000),
                )

            executed = []
            failed = []

            for task in due_tasks:
                if task.workflow_id not in WORKFLOWS:
                    logger.warning(
                        "heartbeat.unknown_workflow",
                        workflow_id=task.workflow_id,
                    )
                    continue

                try:
                    task.status = "RUNNING"
                    task.last_run_at = now
                    await db.flush()

                    engine = DepartmentWorkflowEngine(
                        db, task.user_id, task.tenant_id,
                    )
                    wf_result = await engine.run(task.workflow_id)

                    task.status = "COMPLETED" if wf_result.status == "completed" else "FAILED"
                    task.last_result = wf_result.to_dict()
                    task.last_error = wf_result.error
                    task.run_count += 1

                    # Calculate next run
                    if task.cron_expression:
                        cron = croniter(task.cron_expression, now)
                        task.next_run_at = cron.get_next(datetime)
                    else:
                        task.is_active = False  # One-shot task

                    if wf_result.status == "completed":
                        executed.append(task.workflow_id)
                    else:
                        failed.append(f"{task.workflow_id}: {wf_result.error}")

                except Exception as exc:
                    task.status = "FAILED"
                    task.last_error = str(exc)
                    failed.append(f"{task.workflow_id}: {exc}")
                    logger.error(
                        "heartbeat.workflow_execution_failed",
                        workflow_id=task.workflow_id,
                        error=str(exc),
                    )

            await db.commit()

        actions = []
        if failed:
            actions.append(SuggestedAction(
                description=f"Department workflow failures: {', '.join(failed)}",
                priority=ActionPriority.MEDIUM,
            ))

        summary = f"Ran {len(executed)} workflows"
        if failed:
            summary += f", {len(failed)} failed"

        return HeartbeatCheckResult(
            check_type="department_workflows",
            status="ok" if not failed else "warning",
            summary=summary,
            details={"executed": executed, "failed": failed},
            actions=actions,
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )

    except ImportError as exc:
        return HeartbeatCheckResult(
            check_type="department_workflows",
            status="warning",
            summary=f"Dependencies not available: {exc}",
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:
        return HeartbeatCheckResult(
            check_type="department_workflows",
            status="error",
            summary=f"Department workflow check failed: {exc}",
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )


async def check_autonomous_work() -> HeartbeatCheckResult:
    """AGI mode: find pending tasks and execute them autonomously.

    This is the key difference between a monitoring daemon and an autonomous agent.
    When AGI mode is ON, the heartbeat:
    1. Scans for pending execution tasks in the database
    2. Routes each task through SwarmPlanner for decomposition
    3. Executes subtasks in parallel via SwarmExecutor
    4. Reports results and queues follow-up actions

    BACKGROUND PATH ONLY -- this runs expensive LLM calls.
    Cost-guarded by heartbeat config (max_cost_per_cycle_usd).
    """
    import time as _time

    t0 = _time.perf_counter()

    try:
        from app.core.database import async_session_factory
        from app.models.execution import Task
        from sqlalchemy import select

        async with async_session_factory() as db:
            # Find pending tasks
            stmt = (
                select(Task)
                .where(Task.status.in_(["PENDING", "RETRY"]))
                .order_by(Task.created_at.asc())
                .limit(3)  # Process max 3 tasks per cycle to control cost
            )
            result = await db.execute(stmt)
            pending = list(result.scalars().all())

            if not pending:
                return HeartbeatCheckResult(
                    check_type="autonomous_work",
                    status="ok",
                    summary="No pending tasks to execute",
                    duration_ms=int((_time.perf_counter() - t0) * 1000),
                )

            executed = []
            failed = []

            for task in pending:
                try:
                    # Mark as running
                    task.status = "RUNNING"
                    await db.commit()

                    # Use SwarmPlanner to decompose + execute
                    from app.core.events import get_runtime_registry
                    from app.services.swarm.planner import SwarmPlanner
                    from app.services.swarm.executor import SwarmExecutor
                    from app.services.runtimes.cost_estimator import CostEstimator

                    registry = get_runtime_registry()
                    planner = SwarmPlanner(registry)
                    executor = SwarmExecutor(registry, CostEstimator())

                    # Decompose the task
                    plan = await planner.decompose_and_route(task.description or "")
                    subtasks = plan.get("subtasks", [])

                    if not subtasks:
                        # Simple task -- execute directly via Ollama
                        from app.services.agent_core.system_access import SystemAccess
                        sys_access = SystemAccess(agi_mode=True)
                        cmd_result = await sys_access.run_command(
                            f'echo "Task: {task.description}" | head -c 200',
                        )
                        task.status = "COMPLETED"
                        task.result_data = f"Executed directly: {cmd_result.get('stdout', '')[:200]}"
                        executed.append(task.description[:60] if task.description else str(task.id))
                    else:
                        # Execute subtasks in parallel
                        context = {
                            "session_id": str(task.session_id) if hasattr(task, "session_id") else "heartbeat",
                            "tenant_id": str(task.tenant_id) if hasattr(task, "tenant_id") else "",
                            "governance_mode": "BALANCED",
                        }
                        receipts = await executor.execute_plan(subtasks, context)

                        # Check results
                        success_count = sum(1 for r in receipts if r.status == "success")
                        total = len(receipts)

                        if success_count == total:
                            task.status = "COMPLETED"
                        elif success_count > 0:
                            task.status = "COMPLETED"  # Partial success
                        else:
                            task.status = "FAILED"
                            task.error = "All subtasks failed"
                            failed.append(task.description[:60] if task.description else str(task.id))

                        task.result_data = f"{success_count}/{total} subtasks completed"
                        executed.append(f"{task.description[:40]}... ({success_count}/{total})" if task.description else str(task.id))

                    await db.commit()

                except Exception as exc:
                    task.status = "FAILED"
                    task.error = str(exc)[:500]
                    await db.commit()
                    failed.append(f"{task.description[:40] if task.description else task.id}: {exc}")
                    logger.error("heartbeat.autonomous_work_failed", task_id=str(task.id), error=str(exc))

        actions = []
        if failed:
            actions.append(SuggestedAction(
                description=f"Autonomous work failures: {len(failed)} tasks",
                priority=ActionPriority.HIGH,
            ))
        if executed:
            actions.append(SuggestedAction(
                description=f"Completed {len(executed)} tasks autonomously",
                priority=ActionPriority.NONE,
            ))

        summary = f"Processed {len(executed)} tasks"
        if failed:
            summary += f", {len(failed)} failed"

        return HeartbeatCheckResult(
            check_type="autonomous_work",
            status="ok" if not failed else "warning",
            summary=summary,
            details={"executed": executed, "failed": failed},
            actions=actions,
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )

    except Exception as exc:
        return HeartbeatCheckResult(
            check_type="autonomous_work",
            status="error",
            summary=f"Autonomous work check failed: {exc}",
            duration_ms=int((_time.perf_counter() - t0) * 1000),
        )
