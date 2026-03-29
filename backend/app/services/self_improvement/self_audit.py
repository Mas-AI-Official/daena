"""Self-audit system -- Daena audits her own codebase.

Runs test coverage analysis, code quality checks, performance
profiling, and security scanning. Generates improvement tasks
that can be auto-executed or queued for approval.
"""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def _run_sync(cmd: list[str], *, cwd: str | None = None, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)


@dataclass
class AuditResult:
    """Result of a self-audit check."""

    audit_type: str
    status: str  # ok, warning, error
    score: float = 0.0  # 0-100
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_type": self.audit_type,
            "status": self.status,
            "score": self.score,
            "summary": self.summary,
            "details": self.details,
            "suggestions": self.suggestions,
            "timestamp": self.timestamp.isoformat(),
        }


class SelfAudit:
    """Daena audits her own codebase and suggests improvements."""

    def __init__(self, backend_path: str = "D:/Ideas/Daena/backend") -> None:
        self._backend_path = backend_path
        self._last_audit: dict[str, AuditResult] = {}

    async def audit_test_coverage(self) -> AuditResult:
        """Run pytest to count tests and check for failures."""
        try:
            result = await asyncio.to_thread(
                _run_sync,
                ["python", "-m", "pytest", "tests/", "-q", "--tb=no", "--no-header"],
                cwd=self._backend_path,
                timeout=300.0,
            )
            output = result.stdout.strip()
            passed = failed = 0
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

            total = passed + failed
            score = (passed / total * 100) if total > 0 else 0
            suggestions = []
            if failed > 0:
                suggestions.append({
                    "type": "fix_tests",
                    "priority": "high",
                    "description": f"Fix {failed} failing tests",
                    "effort": "medium",
                })
            if total < 1000:
                suggestions.append({
                    "type": "add_tests",
                    "priority": "medium",
                    "description": f"Add more tests (currently {total}, target 1050+)",
                    "effort": "medium",
                })

            audit = AuditResult(
                audit_type="test_coverage",
                status="ok" if failed == 0 else "error",
                score=score,
                summary=f"{passed} passed, {failed} failed ({total} total)",
                details={"passed": passed, "failed": failed, "total": total},
                suggestions=suggestions,
            )
            self._last_audit["test_coverage"] = audit
            return audit

        except Exception as exc:
            return AuditResult(
                audit_type="test_coverage",
                status="error",
                summary=f"Audit failed: {exc}",
            )

    async def audit_code_quality(self) -> AuditResult:
        """Run ruff for linting issues."""
        try:
            result = await asyncio.to_thread(
                _run_sync,
                ["python", "-m", "ruff", "check", "app/", "--statistics", "--quiet"],
                cwd=self._backend_path,
                timeout=30.0,
            )
            issues = [l for l in result.stdout.strip().splitlines() if l.strip()]
            issue_count = len(issues)

            suggestions = []
            if issue_count > 0:
                suggestions.append({
                    "type": "fix_lint",
                    "priority": "low",
                    "description": f"Fix {issue_count} linting issues",
                    "effort": "low",
                    "auto_fixable": True,
                })

            return AuditResult(
                audit_type="code_quality",
                status="ok" if issue_count == 0 else "warning",
                score=max(0, 100 - issue_count * 2),
                summary=f"{issue_count} linting issues" if issue_count else "Clean",
                details={"issues": issues[:20]},
                suggestions=suggestions,
            )
        except Exception as exc:
            return AuditResult(
                audit_type="code_quality",
                status="error",
                summary=f"Ruff check failed: {exc}",
            )

    async def audit_security(self) -> AuditResult:
        """Check for potential security issues."""
        try:
            # Check for hardcoded secrets patterns
            result = await asyncio.to_thread(
                _run_sync,
                ["python", "-m", "ruff", "check", "app/", "--select", "S"],
                cwd=self._backend_path,
                timeout=30.0,
            )
            issues = [l for l in result.stdout.strip().splitlines() if l.strip()]

            return AuditResult(
                audit_type="security",
                status="ok" if not issues else "warning",
                score=100 if not issues else max(0, 100 - len(issues) * 5),
                summary=f"{len(issues)} security findings" if issues else "No issues",
                details={"findings": issues[:20]},
            )
        except Exception as exc:
            return AuditResult(
                audit_type="security",
                status="error",
                summary=f"Security audit failed: {exc}",
            )

    async def full_audit(self) -> dict[str, AuditResult]:
        """Run all audit checks."""
        results = await asyncio.gather(
            self.audit_test_coverage(),
            self.audit_code_quality(),
            self.audit_security(),
            return_exceptions=True,
        )

        audit_map = {}
        for r in results:
            if isinstance(r, AuditResult):
                audit_map[r.audit_type] = r
            elif isinstance(r, Exception):
                audit_map["error"] = AuditResult(
                    audit_type="error",
                    status="error",
                    summary=str(r),
                )

        self._last_audit = audit_map
        logger.info(
            "self_audit.complete",
            checks=len(audit_map),
            scores={k: v.score for k, v in audit_map.items()},
        )
        return audit_map

    def get_last_audit(self) -> dict[str, dict]:
        """Get last audit results as dicts."""
        return {k: v.to_dict() for k, v in self._last_audit.items()}

    def get_all_suggestions(self) -> list[dict[str, Any]]:
        """Get all improvement suggestions from last audit."""
        suggestions = []
        for audit in self._last_audit.values():
            suggestions.extend(audit.suggestions)
        return sorted(suggestions, key=lambda s: {"high": 0, "medium": 1, "low": 2}.get(s.get("priority", "low"), 3))
