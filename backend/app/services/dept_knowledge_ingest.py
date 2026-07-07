"""Ingest completed EXE artifacts into per-department ragx collections.

This closes the PR-6 memory loop: an EXE tool run is summarised to a small
markdown file and indexed into its department's tenant-scoped ragx collection,
so a later CMD turn in the same department semantically recalls it (Stage 6.55).

Design constraints honoured here:
  * ragx indexes filesystem PATHS, not inline text, and dedupes by SHA per
    file path. We therefore write a DETERMINISTIC markdown file (content keyed
    on the execution's persisted ``created_at``, never ``now()``) at a stable
    per-execution path, so re-running ingest is idempotent: identical bytes ->
    identical SHA -> ragx skips the re-index.
  * Isolation is by collection NAME (ragx has no metadata filter). The write
    target is the single tenant-scoped name from ``department_collection_name``.
    If no department is resolved we SKIP entirely rather than write to a global
    collection, so tenant data can never leak into a shared name.
  * Fails OPEN (ADR-001 / Rule 17): every failure is logged, none is raised
    into the execution path. A ragx outage leaves the summary file on disk for
    a later cron re-index; it never breaks the tool call.
  * Runs in its OWN background DB session (async_session_factory), never the
    request's shared session, because it is scheduled fire-and-forget after the
    execution has already committed.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models.chat import ChatSession
from app.models.execution import ToolExecution
from app.models.organization import Department
from app.services.ragx_bridge import RAGX_URL, department_collection_name

logger = get_logger(__name__)

# Indexing is a background write; give ragx room to chew on a file without ever
# blocking anything user-visible (this never runs on the request path).
_INDEX_TIMEOUT_S = 15.0

# Keep a strong reference to in-flight fire-and-forget tasks. asyncio only holds
# a weak reference to tasks created via create_task; without this set a task can
# be garbage-collected mid-run. Discarded in the done callback.
_INFLIGHT: set[asyncio.Task] = set()


def schedule_execution_ingest(
    *, execution_id: UUID, session_id: UUID | None, tenant_id: UUID
) -> None:
    """Fire-and-forget schedule of ``ingest_execution`` on the running loop.

    Never raises into the caller: the execution has already succeeded and
    committed by the time this runs, so ingestion must never be able to turn a
    successful tool call into a failure.
    """
    try:
        task = asyncio.create_task(
            ingest_execution(
                execution_id=execution_id,
                session_id=session_id,
                tenant_id=tenant_id,
            )
        )
        _INFLIGHT.add(task)
        task.add_done_callback(_INFLIGHT.discard)
    except RuntimeError:
        # No running event loop (e.g. called from a sync context). Nothing to
        # schedule; skip silently rather than crash the caller.
        logger.debug("dept_knowledge_ingest_no_loop", exc_info=True)
    except Exception:
        logger.debug("dept_knowledge_ingest_schedule_failed", exc_info=True)


async def ingest_execution(
    *,
    execution_id: UUID,
    session_id: UUID | None,
    tenant_id: UUID,
    session_factory=None,
) -> None:
    """Resolve the execution -> session -> department chain in a fresh session,
    write a deterministic summary file, and index it into the department's
    tenant-scoped ragx collection.

    ``session_factory`` is injectable for tests (the request-time conftest
    override only rebinds ``get_db``, not ``async_session_factory``). Defaults
    to the real ``async_session_factory``.
    """
    try:
        factory = session_factory or async_session_factory
        async with factory() as session:
            execution = (
                await session.execute(
                    select(ToolExecution).where(
                        ToolExecution.id == execution_id,
                        ToolExecution.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if execution is None:
                return

            if session_id is None:
                # A session-less execution has no department to scope to.
                return

            chat_session = (
                await session.execute(
                    select(ChatSession).where(
                        ChatSession.id == session_id,
                        ChatSession.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if chat_session is None or chat_session.department_id is None:
                # Company-wide session: no department collection to write to.
                # SKIP rather than fall back to a global name (leak guard).
                return

            department = (
                await session.execute(
                    select(Department).where(
                        Department.id == chat_session.department_id,
                        Department.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if department is None:
                return

            # Capture plain values before the session closes so we never touch a
            # detached ORM instance after the context exits.
            dept_name = department.name
            tool_name = execution.tool_name
            tool_result = execution.tool_result
            status = execution.status
            created_at = execution.created_at

        collection = department_collection_name(dept_name, tenant_id)
        if collection is None:
            return

        content = _render_markdown(
            execution_id=execution_id,
            dept_name=dept_name,
            tool_name=tool_name,
            status=status,
            created_at=created_at,
            tool_result=tool_result,
        )
        path = _knowledge_dir() / collection / f"exec-{execution_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        indexed = await _index_path(collection, path)
        if indexed:
            logger.info(
                "dept_knowledge_indexed",
                collection=collection,
                execution_id=str(execution_id),
            )
    except Exception:
        logger.warning("dept_knowledge_ingest_failed", exc_info=True)


def schedule_task_artifact_ingest(
    *, task_id: UUID, tenant_id: UUID, department: str | None, result: dict
) -> None:
    """Fire-and-forget schedule of ``ingest_task_artifact`` on the running loop.

    Same never-raise contract as ``schedule_execution_ingest``: the delegated
    task has already COMPLETED and committed by the time this runs, so
    ingestion must never be able to turn that success into a failure.
    """
    try:
        task = asyncio.create_task(
            ingest_task_artifact(
                task_id=task_id,
                tenant_id=tenant_id,
                department=department,
                result=result,
            )
        )
        _INFLIGHT.add(task)
        task.add_done_callback(_INFLIGHT.discard)
    except RuntimeError:
        logger.debug("dept_knowledge_ingest_no_loop", exc_info=True)
    except Exception:
        logger.debug("dept_knowledge_ingest_schedule_failed", exc_info=True)


async def ingest_task_artifact(
    *, task_id: UUID, tenant_id: UUID, department: str | None, result: dict
) -> None:
    """Write a delegated step's artifact to the department's knowledge dir and
    index it into the tenant-scoped ragx collection.

    Session-free by design (like experience_ingest): ``_background_run`` passes
    the already-persisted ``task.result`` values in, so there is nothing to
    re-read. No department -> SKIP entirely rather than write to a global
    collection (leak guard). Content is keyed only on persisted result values
    (``executed_at`` is stamped before COMPLETED commits, never ``now()`` here)
    so the file SHA is stable and re-ingest is idempotent.
    """
    try:
        artifact = str((result or {}).get("artifact") or "").strip()
        if not artifact or not department:
            return

        collection = department_collection_name(department, tenant_id)
        if collection is None:
            return

        content = _render_task_markdown(
            task_id=task_id,
            department=department,
            result=result,
            artifact=artifact,
        )
        path = _knowledge_dir() / collection / f"task-{task_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        indexed = await _index_path(collection, path)
        if indexed:
            logger.info(
                "dept_knowledge_indexed",
                collection=collection,
                task_id=str(task_id),
            )
    except Exception:
        logger.warning("dept_knowledge_ingest_failed", exc_info=True)


async def _index_path(collection: str, path: Path) -> bool:
    """POST the file path to ragx for indexing. Fails open: logs and returns
    False on any HTTP failure so a ragx outage never breaks ingest. ragx
    auto-creates the collection on first index, so no pre-registration needed.
    Note: the collection is in the URL path here; the body carries sources."""
    url = f"{RAGX_URL}/collections/{collection}/index"
    try:
        async with httpx.AsyncClient(timeout=_INDEX_TIMEOUT_S) as client:
            resp = await client.post(url, json={"sources": [str(path)]})
        if resp.status_code != 200:
            logger.warning(
                "dept_knowledge_index_http_error",
                collection=collection,
                status=resp.status_code,
            )
            return False
        return True
    except httpx.RequestError:
        logger.warning(
            "dept_knowledge_index_unreachable", collection=collection, exc_info=True
        )
        return False


def _render_markdown(
    *,
    execution_id: UUID,
    dept_name: str,
    tool_name: str,
    status: str,
    created_at,
    tool_result,
) -> str:
    """Render a deterministic summary. Content is keyed only on persisted
    values (no ``now()``) so the file SHA is stable across retries."""
    when = created_at.isoformat() if created_at is not None else ""
    lines = [
        f"# Execution {execution_id}",
        "",
        f"- department: {dept_name}",
        f"- tool: {tool_name}",
        f"- status: {status}",
        f"- created_at: {when}",
        "",
        "## Result",
        "",
        _result_preview(tool_result),
        "",
    ]
    return "\n".join(lines)


def _render_task_markdown(*, task_id, department, result, artifact) -> str:
    """Deterministic: keyed ONLY on persisted result values (executed_at was
    stamped by _background_run before COMPLETED committed) -- no now()."""
    lines = [
        f"# Delegated step {task_id}",
        "",
        f"- department: {department}",
        f"- executor: {result.get('executor', '')}",
        f"- goal: {result.get('goal', '')}",
        f"- model: {result.get('model_id', '')}",
        f"- executed_at: {result.get('executed_at', '')}",
        "",
        "## Artifact",
        "",
        artifact,
        "",
    ]
    return "\n".join(lines)


def _result_preview(tool_result, max_chars: int = 2000) -> str:
    """Compact, deterministic text rendering of a tool result for indexing."""
    if tool_result is None:
        return "(no result)"
    if isinstance(tool_result, str):
        text = tool_result
    else:
        import json

        try:
            text = json.dumps(
                tool_result,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=str,
            )
        except (TypeError, ValueError):
            text = str(tool_result)
    text = text.strip()
    if not text:
        return "(empty result)"
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (truncated)"
    return text


def _knowledge_dir() -> Path:
    """Base directory for department knowledge files. Honours an optional
    ``dept_knowledge_dir`` setting; otherwise backend/var/dept_knowledge.
    var/ is a durable artifact dir (never deleted), correct for these files."""
    configured = getattr(get_settings(), "dept_knowledge_dir", None)
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "var" / "dept_knowledge"
