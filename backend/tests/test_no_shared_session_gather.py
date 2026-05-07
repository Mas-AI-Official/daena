"""AST guard: forbid `asyncio.gather(coro_using_db, coro_using_db, ...)`
where the same request-scoped ``db: AsyncSession`` is passed to all
coroutines.

Why: SQLAlchemy 2.0's ``AsyncSession`` is not concurrency-safe. Two
awaits that touch the same session race on the underlying connection
provisioning step, raising ``InvalidRequestError: This session is
provisioning a new connection; concurrent operations are not permitted``.

This is the failure mode the user reported in the analytics dashboard
on 2026-04-29. Codex's fix in ``analytics.py`` was correct but narrow
-- this test enforces the rule globally so the same bug never reaches
production from another endpoint.

The test scans every ``backend/app/api/v1/*.py`` file. Inside any
``async def`` whose signature contains ``db: AsyncSession`` (or
similar), it walks the body for ``asyncio.gather(...)`` (or
``asyncio.TaskGroup``) calls. For every gathered call it inspects the
arguments: if the same ``db`` name from the enclosing function appears
in two or more gathered coroutines, the file fails the test.

Allowed patterns:
  * ``asyncio.gather`` over LLM/httpx calls that don't touch the session
    (just don't pass the session in)
  * ``asyncio.create_task`` for fire-and-forget background work (the
    spawned coroutine should use ``async with async_session_factory()``
    or ``session_scope()`` from ``app.core.db_concurrent``)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

API_V1_ROOT = Path(__file__).resolve().parent.parent / "app" / "api" / "v1"


def _collect_session_param_names(func: ast.AsyncFunctionDef | ast.FunctionDef) -> set[str]:
    """Return the names of parameters that are likely AsyncSession bindings."""
    names: set[str] = set()
    for arg in (
        list(func.args.args)
        + list(func.args.kwonlyargs)
        + list(func.args.posonlyargs)
    ):
        if arg.arg in {"db", "session", "async_db", "db_session"}:
            names.add(arg.arg)
            continue
        # Annotation-based detection: ``db: AsyncSession``, ``s: "AsyncSession"``
        ann = arg.annotation
        ann_text: str | None = None
        if isinstance(ann, ast.Name):
            ann_text = ann.id
        elif isinstance(ann, ast.Attribute):
            ann_text = ann.attr
        elif isinstance(ann, ast.Constant) and isinstance(ann.value, str):
            ann_text = ann.value
        elif isinstance(ann, ast.Subscript):
            # e.g. Annotated[AsyncSession, Depends(get_db)]
            value = ann.value
            if isinstance(value, ast.Name):
                ann_text = value.id
        if ann_text and "Session" in ann_text:
            names.add(arg.arg)
    return names


def _is_asyncio_gather_or_taskgroup(call: ast.Call) -> bool:
    """Return True if this Call is asyncio.gather(...) or asyncio.TaskGroup()."""
    func = call.func
    if isinstance(func, ast.Attribute):
        if func.attr in {"gather", "TaskGroup"}:
            value = func.value
            if isinstance(value, ast.Name) and value.id in {"asyncio", "_asyncio"}:
                return True
            if isinstance(value, ast.Attribute) and value.attr in {"asyncio"}:
                return True
    if isinstance(func, ast.Name) and func.id in {"gather", "TaskGroup"}:
        # bare imported gather -- still flag
        return True
    return False


def _arguments_pass_session(call: ast.Call, session_names: set[str]) -> int:
    """Count how many gathered arguments use one of the session names."""
    hits = 0
    for arg in call.args:
        if isinstance(arg, ast.Starred):
            arg = arg.value
        if isinstance(arg, ast.Call):
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Name) and sub.id in session_names:
                    hits += 1
                    break
        elif isinstance(arg, (ast.GeneratorExp, ast.ListComp)):
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Name) and sub.id in session_names:
                    hits += 1
                    break
    return hits


def _scan_function(
    func: ast.AsyncFunctionDef | ast.FunctionDef,
    file_path: Path,
) -> list[str]:
    """Return list of violation messages found inside this function body."""
    session_names = _collect_session_param_names(func)
    if not session_names:
        return []

    violations: list[str] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and _is_asyncio_gather_or_taskgroup(node):
            hits = _arguments_pass_session(node, session_names)
            if hits >= 2:
                line = getattr(node, "lineno", "?")
                violations.append(
                    f"{file_path}:{line} — "
                    f"asyncio.gather/TaskGroup with shared session "
                    f"({sorted(session_names)}) detected. "
                    f"Use app.core.db_concurrent.gather_with_sessions instead."
                )
    return violations


def _collect_violations() -> list[str]:
    violations: list[str] = []
    for path in API_V1_ROOT.rglob("*.py"):
        if path.name.startswith("__"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                violations.extend(_scan_function(node, path))
    return violations


def test_no_shared_session_gather_in_api_v1() -> None:
    """No endpoint should fan out queries against the same AsyncSession."""
    violations = _collect_violations()
    assert not violations, (
        "Found shared-session asyncio.gather usages -- these will raise "
        "InvalidRequestError under load. Fix by using "
        "app.core.db_concurrent.gather_with_sessions:\n\n"
        + "\n".join(violations)
    )


def test_helper_module_importable() -> None:
    """Smoke test that the helper imports cleanly."""
    from app.core.db_concurrent import gather_with_sessions, session_scope

    assert callable(gather_with_sessions)
    assert callable(session_scope)


def test_ast_scanner_detects_intentional_violation() -> None:
    """The scanner itself works: a known bad snippet must be flagged."""
    bad_source = """
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

async def bad_endpoint(db: AsyncSession):
    a, b, c = await asyncio.gather(
        _q1(db),
        _q2(db),
        _q3(db),
    )
    return a, b, c
"""
    tree = ast.parse(bad_source)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef))
    violations = _scan_function(func, Path("<test>"))
    assert len(violations) == 1, (
        f"Scanner should flag exactly one violation, got {violations}"
    )
    assert "shared session" in violations[0]


def test_ast_scanner_allows_separate_sessions() -> None:
    """Gather of coroutines that don't share `db` is allowed."""
    good_source = """
import asyncio

async def good_endpoint(db):
    # Sequential awaits -- analytics.py pattern
    a = await _q1(db)
    b = await _q2(db)
    return a, b

async def good_gather(db):
    # gather of LLM calls that don't touch the session
    results = await asyncio.gather(
        llm_call_1(prompt),
        llm_call_2(prompt),
    )
    return results
"""
    tree = ast.parse(good_source)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            violations.extend(_scan_function(node, Path("<test>")))
    assert violations == [], (
        f"Scanner produced false positives: {violations}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
