"""Execution service: CMD/EXE mode enforcement + tool execution lifecycle.

Orchestrates the execute-with-governance loop:
1. Validate session is in EXE mode (CMD blocks tool execution)
2. Resolve tool → governance tier via GovernanceEngine
3. On approval: execute, record ToolExecution, return result
4. On block: return governance decision with approval request

Also manages background Tasks for Autopilot mode.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.constants import ChatMode, ExecutionStatus, GovernanceMode, RiskLevel, TaskStatus
from app.core.exceptions import (
    GovernanceBlockedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.sse_channels import publish_graph_changed
from app.models.chat import ChatSession
from app.models.execution import Task, ToolExecution
from app.models.identity import User
from app.services._base import BaseService
from app.services.approval import ApprovalService
from app.services.governance import GovernanceEngine
from app.services.permission_resolver import (
    EffectivePermission,
    ToolPermission,
    resolve_permission,
)

logger = get_logger(__name__)


class ExecutionService(BaseService):
    """Manages tool execution with governance and task lifecycle.

    CMD vs EXE mode enforcement:
    - CMD: read-only queries, no tool execution allowed
    - EXE: tools execute through governance pipeline

    Usage::

        svc = ExecutionService(db)

        # Execute a tool in EXE mode
        result = await svc.execute_tool(
            tool_name="write_file",
            params={"path": "report.md", "content": "..."},
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            governance_mode="BALANCED",
            actor_role="OPERATOR",
        )

        # Create a background task
        task = await svc.create_task(
            name="Generate quarterly report",
            user_id=user_id,
            tenant_id=tenant_id,
        )
    """

    @staticmethod
    def _task_to_dict(task: Task) -> dict:
        """Convert a Task ORM instance to a JSON-serializable dict."""
        return {
            "id": str(task.id),
            "user_id": str(task.user_id),
            "tenant_id": str(task.tenant_id),
            "session_id": str(task.session_id) if task.session_id else None,
            "name": task.name,
            "description": task.description,
            "status": task.status,
            "progress": task.progress,
            "result": task.result,
            "error": task.error,
            "checkpoint_data": task.checkpoint_data,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        }

    @staticmethod
    def _execution_to_dict(exe: ToolExecution) -> dict:
        """Convert a ToolExecution ORM instance to a JSON-serializable dict."""
        return {
            "id": str(exe.id),
            "task_id": str(exe.task_id) if exe.task_id else None,
            "session_id": str(exe.session_id),
            "tenant_id": str(exe.tenant_id),
            "tool_name": exe.tool_name,
            "tool_params": exe.tool_params,
            "tool_result": exe.tool_result,
            "status": exe.status,
            "governance_tier": exe.governance_tier,
            "latency_ms": exe.latency_ms,
            "error": exe.error,
            "created_at": exe.created_at.isoformat() if exe.created_at else None,
        }

    # ── Governance Pre-Check ─────────────────────────────────

    async def check_governance(
        self,
        *,
        tool_name: str,
        params: dict,
        session_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        governance_mode: str = "BALANCED",
        actor_role: str = "OPERATOR",
        plan_approval_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Pre-check governance for a tool without executing it.

        Returns the governance decision dict including allowed, tier,
        risk_level, action_type, requires_approval, and message.
        """
        resolved_action = self._resolve_action_type(tool_name, params)
        engine = GovernanceEngine(self.db)
        decision = await engine.evaluate(
            action_type=resolved_action,
            action_params=params,
            governance_slider=governance_mode,
            actor_type="USER",
            actor_role=actor_role,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            plan_approval_id=plan_approval_id,
        )
        decision["action_type"] = resolved_action
        return decision

    # ── Per-Tool User Preference Resolution ─────────────────

    async def _get_user_tool_pref(
        self,
        *,
        user_id: UUID,
        tool_name: str,
    ) -> ToolPermission | None:
        """Fetch the user's per-tool ALLOW / ASK / BLOCK override.

        Reads ``User.settings.extension_permissions``. Shape (see
        ``api.v1.connections``):

            {
                "<ext_slug>": {
                    "default": "ALLOW" | "ASK_EACH_TIME" | "BLOCK",
                    "tools": { "<tool_name>": "ALLOW" | ... },
                },
                ...
            }

        Returns ``None`` when no explicit preference exists so the
        resolver falls back to pure governance-mode semantics.
        """
        try:
            result = await self.db.execute(select(User).where(User.id == user_id))
            db_user = result.scalar_one_or_none()
            if not db_user or not db_user.settings:
                return None
            ext_perms = db_user.settings.get("extension_permissions", {}) or {}
            # Scan all extensions for a direct tool override, then fall
            # back to any extension default that claims this tool.
            for _ext_slug, cfg in ext_perms.items():
                if not isinstance(cfg, dict):
                    continue
                tools = cfg.get("tools") or {}
                if tool_name in tools:
                    raw = tools[tool_name]
                    try:
                        return ToolPermission(raw)
                    except ValueError:
                        continue
            return None
        except Exception:
            # Permission lookup must never break tool execution. Fall
            # back to governance-mode defaults when storage hiccups.
            return None

    @staticmethod
    def _infer_tool_risk(resolved_action: str, decision: dict) -> RiskLevel:
        """Pick a RiskLevel for the permission resolver.

        Prefers the risk already computed by ``GovernanceEngine`` when
        available, otherwise falls back to MEDIUM so BALANCED mode
        treats unknown tools conservatively.
        """
        raw = decision.get("risk_level")
        if raw:
            try:
                return RiskLevel(raw)
            except ValueError:
                pass
        return RiskLevel.MEDIUM

    # ── Tool Execution ────────────────────────────────────────

    async def execute_tool(
        self,
        *,
        tool_name: str,
        params: dict,
        session_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        governance_mode: str = "BALANCED",
        actor_role: str = "OPERATOR",
        plan_approval_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Execute a tool with full governance pipeline.

        Args:
            tool_name: Name of the tool/skill to execute.
            params: Tool parameters.
            session_id: Chat session context.
            user_id: Executing user.
            tenant_id: Tenant scope.
            governance_mode: Current governance mode (UNLEASHED/BALANCED/GOVERNED).
            actor_role: RBAC role of the user.
            plan_approval_id: If set, tool runs under pre-approved plan.

        Returns:
            Dict with execution result, governance decision, and metadata.

        Raises:
            ValidationError: If session is in CMD mode.
            GovernanceBlockedError: If governance blocks the action.
        """
        # Step 1: Validate session is in EXE mode
        session = await self._get_session(session_id, tenant_id)
        if session.mode == ChatMode.CMD.value:
            raise ValidationError(
                "Tool execution requires EXE mode. "
                "Current session is in CMD (read-only) mode."
            )

        # Step 1b: YELLOW-tier security-tool runtime gate.
        # Only engages when the tool is registered in the security
        # ToolCatalog (nmap, sqlmap, BloodHound, ...). Non-security
        # tools (email_send, slack_post, etc.) are not in the catalog
        # and skip the gate entirely -- they continue through the
        # standard governance path below.
        #
        # The gate enforces:
        #   - RED hard-deny (defense-in-depth with register-time gate)
        #   - Unknown catalog tool -> deny
        #   - GREEN -> auto-allow (still audited)
        #   - YELLOW -> role match + authorized_scope match
        #     (FOUNDER-only for active-exploitation subset)
        #   - First-run-in-project -> requires_approval=True (caller
        #     writes the approval record)
        #
        # On deny the gate raises ValidationError with the human-
        # readable reason; no governance evaluate is spent on a call
        # that would have been blocked anyway.
        try:
            from app.services.security.tool_catalog import ToolCatalog
            from app.services.security.yellow_runtime_gate import (
                check_yellow_runtime,
            )

            _sec_catalog = ToolCatalog()
            _is_security_tool = (
                tool_name in _sec_catalog._tools  # noqa: SLF001 - public enum
            )
            if _is_security_tool:
                _target = (
                    params.get("target")
                    or params.get("url")
                    or params.get("host")
                    or params.get("domain")
                    or ""
                )
                _gate = check_yellow_runtime(
                    tool_name=tool_name,
                    target=str(_target),
                    user_role=actor_role,
                    tenant_id=str(tenant_id),
                    user_id=str(user_id),
                    session_id=str(session_id),
                    # First-run detection is out of scope for this
                    # commit -- the gate still computes
                    # `requires_approval` when the caller sets this
                    # True. Leaving False until TICKET-FIRST-RUN-
                    # DETECT adds proper per-(tenant, tool, project)
                    # state lookup.
                    is_first_run_in_project=False,
                    catalog=_sec_catalog,
                )
                logger.info(
                    "execution.yellow_gate_decision",
                    tool=tool_name,
                    target=str(_target)[:100],
                    tier=(_gate.tier.value if _gate.tier else None),
                    allow=_gate.allow,
                    user_role=actor_role,
                    tenant_id=str(tenant_id),
                    user_id=str(user_id),
                )
                if not _gate.allow:
                    raise ValidationError(_gate.reason)
        except ValidationError:
            raise
        except Exception as _gate_exc:
            # Fail-safe: if the gate itself errors (e.g. the JSON
            # catalog is corrupt), log loudly but do NOT block
            # execution. The downstream governance check still runs
            # and may block on its own grounds.
            logger.error(
                "execution.yellow_gate_error",
                tool=tool_name,
                error=str(_gate_exc),
                exc_info=True,
            )

        # Step 2: Governance evaluation — resolve correct action_type
        #         for DaenaBot agents (operation-aware risk classification)
        resolved_action = self._resolve_action_type(tool_name, params)
        engine = GovernanceEngine(self.db)
        decision = await engine.evaluate(
            action_type=resolved_action,
            action_params=params,
            governance_slider=governance_mode,
            actor_type="USER",
            actor_role=actor_role,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            plan_approval_id=plan_approval_id,
        )

        # Step 2b: Per-tool user override via permission_resolver.
        # Governance mode stays the source of truth; an explicit BLOCK
        # from the user always wins, and an explicit ASK promotes the
        # action to requires_approval regardless of tier. AUTO_PROCEED
        # (default) leaves the engine decision untouched.
        user_pref = await self._get_user_tool_pref(
            user_id=user_id, tool_name=tool_name
        )
        try:
            gov_mode_enum = GovernanceMode(governance_mode)
        except ValueError:
            gov_mode_enum = GovernanceMode.BALANCED
        tool_risk = self._infer_tool_risk(resolved_action, decision)
        effective = resolve_permission(
            governance_mode=gov_mode_enum,
            autopilot_active=bool(decision.get("autopilot_override")),
            tool_risk=tool_risk,
            user_pref=user_pref,
        )
        if effective == EffectivePermission.REFUSE:
            decision["allowed"] = False
            decision["requires_approval"] = False
            decision["message"] = (
                f"User blocked tool '{tool_name}' via per-tool permission"
            )
            decision["user_override"] = "BLOCK"
        elif effective == EffectivePermission.REQUEST_INPUT:
            # Force the approval path even if engine tier was below 3.
            if decision.get("allowed"):
                decision["allowed"] = False
            decision["requires_approval"] = True
            decision["user_override"] = "ASK_EACH_TIME"

        # Step 3: Record execution attempt
        execution = ToolExecution(
            session_id=session_id,
            tenant_id=tenant_id,
            tool_name=tool_name,
            tool_params=params,
            status=ExecutionStatus.PENDING.value,
            governance_tier=decision["governance_tier"],
        )
        self.db.add(execution)
        await self.db.flush()

        # Step 4: Check governance decision.
        #
        # Previously this raised GovernanceBlockedError without persisting
        # anything visible to the user. That meant the frontend's
        # /governance/approvals page stayed empty even when tools were
        # gated on tier 3+, which is why Masoud never saw approvals
        # surface in the UI. Now any action flagged requires_approval
        # creates a PendingApproval row via ApprovalService so the
        # Approvals page and Sidebar badge light up immediately.
        if not decision["allowed"]:
            execution.status = ExecutionStatus.BLOCKED.value
            execution.error = decision["message"]

            approval_request_id: str | None = None
            if decision.get("requires_approval"):
                try:
                    approval_svc = ApprovalService(self.db)
                    approval = await approval_svc.request_approval(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        action_type=resolved_action,
                        action_params=params,
                        risk_level=decision.get(
                            "risk_level", RiskLevel.MEDIUM.value
                        ),
                        governance_tier=decision["governance_tier"],
                        session_id=session_id,
                        context={
                            "tool_name": tool_name,
                            "execution_id": str(execution.id),
                            "user_override": decision.get("user_override"),
                        },
                    )
                    approval_request_id = approval["id"]
                    decision["request_id"] = approval_request_id
                    logger.info(
                        "execution.approval_persisted",
                        tool=tool_name,
                        request_id=approval_request_id,
                        tier=decision["governance_tier"],
                    )
                except Exception as approval_exc:
                    # Never let approval persistence failure swallow the
                    # underlying governance block. Log and continue to raise.
                    logger.warning(
                        "execution.approval_persist_failed",
                        tool=tool_name,
                        error=str(approval_exc),
                    )

            await self.db.commit()

            suffix = (
                f" (approval {approval_request_id})"
                if approval_request_id
                else ""
            )
            raise GovernanceBlockedError(
                f"Tool '{tool_name}' blocked: {decision['message']}{suffix}"
            )

        # Step 5: Execute the tool
        start_time = time.monotonic()
        try:
            execution.status = ExecutionStatus.RUNNING.value
            await self.db.flush()

            # Actual tool execution would be dispatched here.
            # For now, we record the attempt and return a stub.
            # 2026-05-09: pass user_id so settings.* agent can scope
            # to User.settings JSONB without re-querying.
            result = await self._dispatch_tool(tool_name, params, user_id=user_id)

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            execution.status = ExecutionStatus.COMPLETED.value
            execution.tool_result = result
            execution.latency_ms = elapsed_ms
            await self.db.commit()

            # PR-6 memory loop: index this completed execution into the
            # department's tenant-scoped ragx collection. Fire-and-forget,
            # fail-open -- can never turn a committed success into a
            # failure. Lazy import keeps the module off the hot import
            # path (NEVER-4).
            from app.services.dept_knowledge_ingest import (
                schedule_execution_ingest,
            )
            schedule_execution_ingest(
                execution_id=execution.id,
                session_id=session_id,
                tenant_id=tenant_id,
            )

            logger.info(
                "tool_executed",
                tool=tool_name,
                tier=decision["governance_tier"],
                latency_ms=elapsed_ms,
                session_id=str(session_id),
            )

            return {
                "execution_id": str(execution.id),
                "tool_name": tool_name,
                "status": ExecutionStatus.COMPLETED.value,
                "result": result,
                "governance": decision,
                "latency_ms": elapsed_ms,
            }

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            execution.status = ExecutionStatus.FAILED.value
            execution.error = str(exc)
            execution.latency_ms = elapsed_ms
            await self.db.commit()

            logger.error(
                "tool_execution_failed",
                tool=tool_name,
                error=str(exc),
                session_id=str(session_id),
            )
            raise

    async def get_execution(
        self, execution_id: UUID, tenant_id: UUID
    ) -> dict:
        """Get a tool execution record by ID (serialized for API)."""
        exe = await self._get_or_404(
            ToolExecution, execution_id, "Tool execution",
            tenant_id=tenant_id,
        )
        return self._execution_to_dict(exe)

    async def _get_task_orm(
        self, task_id: UUID, tenant_id: UUID
    ) -> Task:
        """Get a task ORM object by ID (for internal use)."""
        return await self._get_or_404(
            Task, task_id, "Task", tenant_id=tenant_id,
        )

    async def list_executions(
        self,
        *,
        session_id: UUID,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ):
        """List tool executions for a session."""
        from app.schemas.execution import ToolExecutionResponse

        stmt = (
            select(ToolExecution)
            .where(ToolExecution.session_id == session_id)
            .where(ToolExecution.tenant_id == tenant_id)
            .order_by(ToolExecution.created_at.desc())
        )
        return await self._paginate(
            stmt, ToolExecution, page, page_size,
            response_schema=ToolExecutionResponse,
        )

    # ── Task Management (Autopilot) ───────────────────────────

    async def create_task(
        self,
        *,
        name: str,
        user_id: UUID,
        tenant_id: UUID,
        description: str | None = None,
        session_id: UUID | None = None,
        also_create_workstream: bool = False,
        department_id: UUID | None = None,
        checkpoint_data: dict | None = None,
    ) -> dict:
        """Create a background task for Autopilot mode.

        Args:
            name: Human-readable task name.
            user_id: Owner of the task.
            tenant_id: Tenant scope.
            description: Optional detailed description.
            session_id: Optional chat session context.
            also_create_workstream: PR-5 opt-in. When True, also create a
                Workstream shell with source_type=task and source_ref_id
                pointing at this task's id. The workstream id is returned
                in the response dict so the frontend can deep-link.
            department_id: Owner department for the spawned workstream.
                Optional even when also_create_workstream=True; falls
                back to the first active department for the tenant.
            checkpoint_data: Optional durable metadata stored on the Task
                row. G5 delegated goals store their delegation envelope
                here; ``run_task`` reads it to enforce the approval gate.

        Returns:
            Dict shape (matches ``_task_to_dict``) with an extra
            ``workstream_id`` key when one was spawned.
        """
        task = Task(
            name=name,
            description=description,
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_id,
            status=TaskStatus.PENDING.value,
            progress=0,
            checkpoint_data=checkpoint_data,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        logger.info(
            "task_created",
            task_id=str(task.id),
            name=name,
            user_id=str(user_id),
        )

        result = self._task_to_dict(task)

        # PR-5: optional workstream spawn. Wrapped so a ws-creation
        # failure NEVER fails the task -- the task is the contract,
        # the workstream is the optional observability layer.
        if also_create_workstream:
            try:
                ws_id = await self._spawn_workstream_for_task(
                    task=task, department_id=department_id,
                )
                if ws_id is not None:
                    result["workstream_id"] = str(ws_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "task.workstream_spawn_failed",
                    task_id=str(task.id),
                    error=str(exc),
                )

        return result

    async def _spawn_workstream_for_task(
        self,
        *,
        task: Task,
        department_id: UUID | None,
    ) -> UUID | None:
        """Create a Workstream shell linked to the task. Returns ws.id.

        Resolves the department: if explicit, validates it. Otherwise
        falls back to the tenant's first active department by sunflower
        index. Returns None when no active department is available
        (caller logs at WARNING; task creation is not affected).
        """
        # Local imports keep WorkstreamService out of the global scope
        # so import order issues do not bite the autopilot path.
        from sqlalchemy import select

        from app.models.organization import Department
        from app.models.workstream import WorkstreamSourceType
        from app.services.workstream_service import (
            StartParams,
            WorkstreamService,
        )

        if department_id is not None:
            stmt = select(Department).where(
                Department.id == department_id,
                Department.tenant_id == task.tenant_id,
                Department.is_active.is_(True),
            )
            row = (await self.db.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None
            resolved_dept_id = row.id
        else:
            stmt = (
                select(Department)
                .where(
                    Department.tenant_id == task.tenant_id,
                    Department.is_active.is_(True),
                )
                .order_by(Department.sunflower_index.asc())
                .limit(1)
            )
            row = (await self.db.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None
            resolved_dept_id = row.id

        ws_svc = WorkstreamService(self.db)
        ws = await ws_svc.start(
            StartParams(
                tenant_id=task.tenant_id,
                user_id=task.user_id,
                department_id=resolved_dept_id,
                goal=task.name,
                next_step_text=task.description,
                initial_context={
                    "spawned_from": "manual_task",
                    "task_id": str(task.id),
                },
                source_type=WorkstreamSourceType.TASK,
                source_ref_id=task.id,
            ),
        )
        return ws.id

    async def get_task(self, task_id: UUID, tenant_id: UUID) -> dict:
        """Get a task by ID (serialized dict for API responses)."""
        task = await self._get_task_orm(task_id, tenant_id)
        return self._task_to_dict(task)

    async def list_tasks(
        self,
        *,
        user_id: UUID,
        tenant_id: UUID,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ):
        """List tasks for a user, optionally filtered by status."""
        from app.schemas.execution import TaskResponse

        stmt = (
            select(Task)
            .where(Task.user_id == user_id)
            .where(Task.tenant_id == tenant_id)
        )
        if status is not None:
            stmt = stmt.where(Task.status == status)
        stmt = stmt.order_by(Task.created_at.desc())

        return await self._paginate(
            stmt, Task, page, page_size,
            response_schema=TaskResponse,
        )

    async def update_task_status(
        self,
        task_id: UUID,
        tenant_id: UUID,
        *,
        status: str | None = None,
        progress: int | None = None,
        result: dict | None = None,
        error: str | None = None,
        checkpoint_data: dict | None = None,
    ) -> Task:
        """Update task status, progress, or checkpoint.

        Used by the task runner to report progress and by users
        to pause/cancel tasks.
        """
        task = await self._get_task_orm(task_id, tenant_id)
        prior_status = task.status

        if status is not None:
            task.status = status
            if status == TaskStatus.RUNNING.value and task.started_at is None:
                task.started_at = datetime.now(UTC)
            elif status in (
                TaskStatus.COMPLETED.value,
                TaskStatus.FAILED.value,
                TaskStatus.CANCELLED.value,
            ):
                task.completed_at = datetime.now(UTC)

        if progress is not None:
            task.progress = min(max(progress, 0), 100)
        if result is not None:
            task.result = result
        if error is not None:
            task.error = error
        if checkpoint_data is not None:
            task.checkpoint_data = checkpoint_data

        await self.db.commit()
        await self.db.refresh(task)

        # PR-SPINE-04: mirror the status change into a linked Workstream.
        # Only fires when status was provided AND actually changed; the
        # helper itself short-circuits on no link / no transition.
        if status is not None and status != prior_status:
            await self._sync_linked_workstream(task, status)
            # Live Brain doorbell (best-effort): a task node just changed
            # status, so nudge the canvas to re-pull GET /graph. The helper
            # swallows its own failures and never gates this write.
            await publish_graph_changed(
                "task_status_changed",
                task_id=str(task.id),
                status=status,
            )

        return self._task_to_dict(task)

    async def _sync_linked_workstream(
        self, task: Task, new_status: str,
    ) -> None:
        """PR-SPINE-04: mirror a Task status change into its Workstream.

        Lookup priority (see ``find_workstream_linked_to_task``):
          1. Workstream with source_type=TASK + source_ref_id=task.id
          2. Workstream with source_type=SCAN + artifact_refs.task_ids
             contains str(task.id)

        Mapping (lifecycle):
          - RUNNING  -> bump progress to >=25 (no transition; the workstream
                        was created in RUNNING by the spawn path)
          - COMPLETED / SUCCESS -> complete() + progress=100
          - FAILED / CANCELLED  -> fail() with task.error or task.name reason
          - PENDING / PAUSED    -> no transition

        Always emits a DECISION timeline event tagged
        ``payload.kind="task_status_changed"`` so the operator sees the
        cause on the timeline regardless of whether the workstream
        actually changed state. Future PR-SPINE-04+ can introduce a
        dedicated TASK_STATUS_CHANGED enum when an SSE consumer needs to
        filter on it without parsing payload.

        Best-effort: a workstream sync failure NEVER raises into the
        Task update path. The Task is the source of truth for its own
        state; the Workstream is the spine artifact mirror. Failures
        log at WARNING.
        """
        from app.models.workstream import (
            WorkstreamEventKind, WorkstreamStatus,
        )
        from app.services.workstream_service import (
            TASK_STATUS_TO_WS_INTENT,
            WorkstreamService,
            WorkstreamTransitionError,
            find_workstream_linked_to_task,
        )

        try:
            ws = await find_workstream_linked_to_task(
                self.db, tenant_id=task.tenant_id, task_id=task.id,
            )
            if ws is None:
                return  # No tracked workstream; nothing to sync.

            ws_svc = WorkstreamService(self.db)
            normalized = (new_status or "").upper()
            intent = TASK_STATUS_TO_WS_INTENT.get(normalized, "noop")

            # 1. Always emit the timeline marker for operator visibility.
            await ws_svc.append_timeline_event(
                ws.id,
                tenant_id=task.tenant_id,
                kind=WorkstreamEventKind.DECISION,
                summary=f"Linked task transitioned to {normalized}",
                payload={
                    "kind": "task_status_changed",
                    "task_id": str(task.id),
                    "task_name": task.name,
                    "to_status": normalized,
                },
            )

            # 2. Apply the lifecycle change when the intent maps to one.
            if intent == "running":
                # Workstream was already RUNNING from spawn; we only bump
                # progress. The state machine forbids RUNNING -> RUNNING
                # transition, which is correct.
                if (
                    ws.status == WorkstreamStatus.RUNNING
                    and ws.progress_percent < 25
                ):
                    await ws_svc.update_progress(
                        ws.id, tenant_id=task.tenant_id, percent=25,
                    )
            elif intent == "complete":
                if ws.status not in (
                    WorkstreamStatus.COMPLETE, WorkstreamStatus.FAILED,
                ):
                    try:
                        await ws_svc.complete(
                            ws.id,
                            tenant_id=task.tenant_id,
                            summary=f"Linked task completed: {task.name}",
                        )
                        await ws_svc.update_progress(
                            ws.id, tenant_id=task.tenant_id, percent=100,
                        )
                    except WorkstreamTransitionError:
                        # Concurrent terminal transition; idempotent skip.
                        pass
            elif intent == "fail":
                if ws.status not in (
                    WorkstreamStatus.COMPLETE, WorkstreamStatus.FAILED,
                ):
                    reason_detail = task.error or task.name
                    try:
                        await ws_svc.fail(
                            ws.id,
                            tenant_id=task.tenant_id,
                            reason=(
                                f"Linked task {normalized.lower()}: "
                                f"{reason_detail}"
                            ),
                        )
                    except WorkstreamTransitionError:
                        pass
            # intent == "noop": only the timeline event was emitted.
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "task.workstream_sync_failed",
                task_id=str(task.id),
                new_status=new_status,
                error=str(exc),
            )

    async def delete_task(self, task_id: UUID, tenant_id: UUID) -> None:
        """Permanently delete a task owned by the tenant."""
        task = await self._get_task_orm(task_id, tenant_id)
        await self.db.delete(task)
        await self.db.commit()

    async def run_task(self, task_id: UUID, tenant_id: UUID) -> dict:
        """Kick off execution for a PENDING / FAILED / CANCELLED task.

        There is no long-lived autopilot worker yet; without an explicit
        kick-off, tasks sit in PENDING forever. This method flips the
        task to RUNNING and fires an asyncio background task that
        simulates progress through 0 -> 100 and marks COMPLETED on
        success or FAILED on exception.

        The background task uses a fresh async session (not ``self.db``
        which belongs to the request lifecycle); otherwise the session
        would be closed before the background task finishes.

        Returns the task in its new RUNNING state so the UI can start
        polling progress immediately.

        Raises:
            ValidationError: when the task is already RUNNING or
                COMPLETED (use delete/retry for those).
        """
        import asyncio as _asyncio

        task = await self._get_task_orm(task_id, tenant_id)

        # Guard against double-dispatch. Only resume states are runnable.
        runnable = {
            TaskStatus.PENDING.value,
            TaskStatus.FAILED.value,
            TaskStatus.CANCELLED.value,
            TaskStatus.PAUSED.value,
        }
        if task.status not in runnable:
            raise ValidationError(
                f"Task is {task.status}; only {sorted(runnable)} can be run"
            )

        # G5 delegation gate: a delegated spend/outward step must be
        # human-approved before dispatch. Tasks without a "delegation"
        # envelope (Stage 2.85 VP tasks, normal tasks) are unaffected.
        delegation = (task.checkpoint_data or {}).get("delegation") or {}
        approval_ref = delegation.get("approval_request_id")
        if approval_ref:
            from app.models.governance import GoaRequest

            try:
                approval_uuid = UUID(str(approval_ref))
            except ValueError:
                approval_uuid = None
            goa = None
            if approval_uuid is not None:
                goa = (
                    await self.db.execute(
                        select(GoaRequest).where(
                            GoaRequest.id == approval_uuid,
                            GoaRequest.tenant_id == tenant_id,
                        )
                    )
                ).scalar_one_or_none()
            status = goa.status if goa is not None else "MISSING"
            if status != "APPROVED":
                raise ValidationError(
                    f"Delegated task is gated on approval {approval_ref} "
                    f"(status={status}); approve it in "
                    "/governance/approvals before running"
                )

        # Flip to RUNNING immediately so the UI reflects state on the
        # POST response, not on the next poll.
        prior_status = task.status
        task.status = TaskStatus.RUNNING.value
        task.started_at = datetime.now(UTC)
        task.completed_at = None
        task.error = None
        task.progress = 0
        await self.db.commit()
        await self.db.refresh(task)

        # PR-SPINE-04: mirror the RUNNING flip into the linked Workstream
        # since this path bypasses ``update_task_status``. Best-effort.
        if prior_status != TaskStatus.RUNNING.value:
            await self._sync_linked_workstream(task, TaskStatus.RUNNING.value)
            # Live Brain doorbell (best-effort): the node flipped to RUNNING
            # on this fast path that bypasses update_task_status, so announce
            # the change for the canvas to re-pull. Never gates the dispatch.
            await publish_graph_changed(
                "task_status_changed",
                task_id=str(task.id),
                status=TaskStatus.RUNNING.value,
            )

        # Snapshot the fields the background task needs BEFORE the
        # request session closes. Re-fetching by id inside the bg task
        # will use a fresh session.
        payload = self._task_to_dict(task)
        captured_id = task.id
        captured_tenant = tenant_id
        captured_user_id = task.user_id
        captured_name = task.name
        captured_desc = task.description or ""
        # Plain copy of the delegation envelope (if any) so the bg task
        # can pick the real executor without re-reading the row.
        captured_delegation = dict(
            (task.checkpoint_data or {}).get("delegation") or {}
        )

        # Bind the bg session factory to the SAME engine the request
        # used (``self.db.bind``) instead of the app-global factory.
        # Tests override ``get_db`` to an in-memory SQLite; pointing
        # the bg task at the global (file-backed) factory would make
        # it miss rows committed by the request. In production both
        # factories resolve to the same engine so behavior is identical.
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        bg_factory = async_sessionmaker(
            self.db.bind, class_=AsyncSession, expire_on_commit=False,
        )

        async def _background_run() -> None:
            """Run the task body in a detached session."""
            logger.info(
                "task_run.started",
                task_id=str(captured_id),
                name=captured_name,
            )
            async with bg_factory() as bg_db:
                bg_service = ExecutionService(bg_db)
                try:
                    if captured_delegation.get("origin") == "delegated":
                        # Real executor (delegated-llm-v1): one governed
                        # model call produces the step's work product.
                        # Raises on provider failure / timeout / empty
                        # output, so the outer except marks the task
                        # FAILED (retryable) -- never a fake COMPLETED.
                        # The G5 approval gate in run_task already fired
                        # for spend/outward steps before we got here.
                        from app.services.delegated_executor import (
                            execute_delegated_step,
                        )
                        await bg_service.update_task_status(
                            captured_id, captured_tenant,
                            progress=25,
                        )
                        result = await execute_delegated_step(
                            name=captured_name,
                            description=captured_desc,
                            delegation=captured_delegation,
                            tenant_id=captured_tenant,
                        )
                        result["executed_at"] = (
                            datetime.now(UTC).isoformat()
                        )
                        await bg_service.update_task_status(
                            captured_id, captured_tenant,
                            progress=90,
                        )
                    else:
                        # Non-delegated tasks have no defined body yet:
                        # simulate work in three slices so the UI can
                        # show real progress bars.
                        for pct in (25, 60, 90):
                            await _asyncio.sleep(0.8)
                            await bg_service.update_task_status(
                                captured_id, captured_tenant,
                                progress=pct,
                            )
                        result = {
                            "summary": f"Task '{captured_name}' executed.",
                            "description_used": captured_desc[:500],
                            "executed_at": datetime.now(UTC).isoformat(),
                            "executor": "minimal-run-task-v1",
                            "note": (
                                "This is the minimal task executor for "
                                "tasks without a delegation envelope; "
                                "'run' cycles through RUNNING -> COMPLETED "
                                "so operators can exercise the lifecycle."
                            ),
                        }
                    await bg_service.update_task_status(
                        captured_id, captured_tenant,
                        status=TaskStatus.COMPLETED.value,
                        progress=100,
                        result=result,
                    )
                    logger.info(
                        "task_run.completed",
                        task_id=str(captured_id),
                    )
                    # P2 knowledge loop: a delegated step's artifact becomes
                    # department knowledge. Fire-and-forget + fail-open; the
                    # COMPLETED row above is already committed. Lazy import
                    # (NEVER-4).
                    if (
                        captured_delegation.get("origin") == "delegated"
                        and result.get("artifact")
                    ):
                        from app.services.dept_knowledge_ingest import (
                            schedule_task_artifact_ingest,
                        )
                        schedule_task_artifact_ingest(
                            task_id=captured_id,
                            tenant_id=captured_tenant,
                            department=captured_delegation.get("department"),
                            result=result,
                        )
                    # Phase 11 PR-S2.1: in-app notification on successful
                    # completion. Best-effort — must NEVER raise from the
                    # background task. Gated by users.settings.notif_task_complete.
                    # update_task_status above already committed the COMPLETED
                    # row, so the bg_db session is in a fresh transaction.
                    # We add the notification then commit explicitly so the
                    # row is visible to the API layer that reads it.
                    try:
                        from app.services.notification_service import (
                            NotificationService,
                        )
                        await NotificationService(bg_db).emit(
                            tenant_id=captured_tenant,
                            user_id=captured_user_id,
                            type="task_complete",
                            title=f"Task completed: {captured_name}",
                            message=(
                                result.get("summary")
                                or f"Task '{captured_name}' finished."
                            ),
                            severity="success",
                            source="execution_service.background_run",
                        )
                        await bg_db.commit()
                    except Exception as _notif_exc:  # noqa: BLE001
                        logger.warning(
                            "task_run.notify_failed",
                            task_id=str(captured_id),
                            error=str(_notif_exc),
                        )
                        # Roll back the failed notification add so the
                        # session can be cleanly closed by the bg_factory.
                        try:
                            await bg_db.rollback()
                        except Exception:  # noqa: BLE001
                            pass
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "task_run.failed",
                        task_id=str(captured_id),
                        error=str(exc),
                    )
                    try:
                        await bg_service.update_task_status(
                            captured_id, captured_tenant,
                            status=TaskStatus.FAILED.value,
                            error=str(exc)[:500],
                        )
                    except Exception as inner:  # noqa: BLE001
                        logger.exception(
                            "task_run.status_update_failed",
                            task_id=str(captured_id),
                            error=str(inner),
                        )

        _asyncio.create_task(_background_run())
        return payload

    # ── Private helpers ───────────────────────────────────────

    async def _get_session(
        self, session_id: UUID, tenant_id: UUID
    ) -> ChatSession:
        """Fetch chat session, enforcing tenant isolation."""
        return await self._get_or_404(
            ChatSession, session_id, "Chat session",
            tenant_id=tenant_id,
        )

    async def _dispatch_tool(
        self, tool_name: str, params: dict, user_id: UUID | None = None,
    ) -> dict:
        """Dispatch tool execution to the appropriate DaenaBot agent.

        Tool names use dot notation: ``file.read_file``,
        ``terminal.execute_command``, ``browser.navigate``.
        The prefix selects the agent; the suffix selects the operation.

        ``user_id`` is required for agents that mutate per-user state
        (currently: ``settings``). Other agents ignore it.

        Gated by the ``enable_daenabot`` feature flag.
        """
        from app.core.config import get_settings

        settings = get_settings()
        if not settings.enable_daenabot:
            return {
                "agent": "disabled",
                "success": False,
                "operation": tool_name,
                "output": None,
                "error": "DaenaBot is not enabled. Set enable_daenabot=True.",
            }

        # Parse agent.operation from tool_name
        if "." in tool_name:
            agent_prefix, operation = tool_name.split(".", 1)
        else:
            agent_prefix, operation = tool_name, tool_name

        agent_prefix = agent_prefix.lower()

        if agent_prefix == "file":
            from app.services.daenabot.file_agent import FileAgent

            agent = FileAgent(
                allowed_paths=settings.daenabot_allowed_paths,
            )
            return await agent.execute(operation, params)

        elif agent_prefix == "settings":
            # 2026-05-09: self-config tool surface. Lets Daena answer
            # "which mind are you using?" with truth, and act on
            # "switch primary mind to X" instead of replying like a
            # chatbot. Stays local to User.settings JSONB; never
            # touches external state.
            if user_id is None:
                return {
                    "agent": "settings",
                    "success": False,
                    "operation": operation,
                    "output": None,
                    "error": (
                        "settings.* tools require user_id at dispatch time. "
                        "Caller did not provide one."
                    ),
                }
            from app.services.daenabot.daena_self_agent import DaenaSelfAgent

            agent = DaenaSelfAgent(db=self.db, user_id=user_id)
            return await agent.execute(operation, params)

        elif agent_prefix == "terminal":
            from app.services.daenabot.terminal_agent import TerminalAgent

            agent = TerminalAgent(
                default_timeout=settings.daenabot_terminal_timeout,
                max_timeout=settings.daenabot_terminal_max_timeout,
            )
            return await agent.execute(operation, params)

        elif agent_prefix == "browser":
            from app.services.daenabot.browser_agent import BrowserAgent

            agent = BrowserAgent(headless=True)
            try:
                return await agent.execute(operation, params)
            finally:
                await agent.close()

        elif agent_prefix == "vision_browser":
            from app.services.daenabot.vision_browser_agent import VisionBrowserAgent

            agent = VisionBrowserAgent()
            try:
                return await agent.execute(operation, params)
            finally:
                await agent.close()

        elif agent_prefix == "web_crawler":
            from app.services.daenabot.web_crawler_agent import WebCrawlerAgent

            agent = WebCrawlerAgent()
            return await agent.execute(operation, params)

        elif agent_prefix == "target_interaction":
            from app.services.daenabot.target_interaction_agent import (
                TargetInteractionAgent,
            )

            agent = TargetInteractionAgent()
            try:
                return await agent.execute(operation, params)
            finally:
                await agent.close()

        elif agent_prefix == "security":
            # Security scan dispatch -- cognitive scan engine
            # BACKGROUND PATH ONLY -- never import in hot path
            from app.services.security.cognitive_scan_engine import (
                CognitiveScanEngine,
            )

            target = params.get("target", "")
            program = params.get("program", "")
            offensive = params.get("offensive_mode", False)
            agi = params.get("agi_mode", False)

            # If offensive requested, activate global /3vilbob mode
            if offensive:
                from app.services.security.evilbob_mode import activate, is_active
                if not is_active():
                    evilbob_key = os.environ.get("EVILBOB_KEY", "")
                    state = activate(key=evilbob_key, user_id="founder")
                    if not state.active:
                        return {
                            "agent": "SecurityAgent",
                            "success": False,
                            "operation": tool_name,
                            "output": None,
                            "error": f"/3vilbob activation failed: {state.reason_denied}",
                        }

            engine = CognitiveScanEngine(
                agi_mode=agi,
                offensive_mode=offensive,
            )

            if operation == "evilbob_toggle":
                from app.services.security.evilbob_mode import (
                    activate, deactivate, get_state, is_active,
                )
                action = params.get("action", "STATUS")
                if action == "ON":
                    evilbob_key = os.environ.get("EVILBOB_KEY", "")
                    state = activate(key=evilbob_key, user_id="founder")
                    return {
                        "agent": "SecurityAgent",
                        "success": state.active,
                        "operation": tool_name,
                        "output": {
                            "active": state.active,
                            "capabilities": state.capabilities,
                            "environment": state.environment,
                            "message": (
                                "Full spectrum mode active. Defensive + offensive."
                                if state.active
                                else f"Activation failed: {state.reason_denied}"
                            ),
                        },
                        "error": state.reason_denied if not state.active else None,
                    }
                elif action == "OFF":
                    state = deactivate()
                    return {
                        "agent": "SecurityAgent",
                        "success": True,
                        "operation": tool_name,
                        "output": {
                            "active": False,
                            "message": "Defensive mode only. Offensive capabilities deactivated.",
                        },
                        "error": None,
                    }
                else:  # STATUS
                    state = get_state()
                    return {
                        "agent": "SecurityAgent",
                        "success": True,
                        "operation": tool_name,
                        "output": {
                            "active": state.active,
                            "capabilities": state.capabilities,
                            "environment": state.environment,
                            "activated_at": state.activated_at,
                            "activated_by": state.activated_by,
                        },
                        "error": None,
                    }

            if operation in ("cognitive_scan", "cognitive_scan_offensive"):
                result = await engine.scan(target, program=program)
                return {
                    "agent": "SecurityAgent",
                    "success": True,
                    "operation": tool_name,
                    "output": {
                        "target": result.target,
                        "findings": result.total_findings,
                        "cycles": result.cycles_used,
                        "strategies": result.strategies_tried,
                        "report_path": result.report_path,
                        "evidence_summary": result.evidence_summary,
                        "offensive_mode": result.offensive_mode,
                        "thinking_log": result.thinking_log[-10:],
                    },
                    "error": None,
                }
            elif operation == "view_report":
                import glob as glob_mod
                reports_dir = os.environ.get("SECURITY_REPORTS_DIR", "D:\\SecurityTools\\reports")
                safe_target = target.replace(".", "_")[:30]
                pattern = os.path.join(reports_dir, f"{safe_target}_*.pdf")
                matches = sorted(glob_mod.glob(pattern), reverse=True)
                if not matches:
                    pattern = os.path.join(reports_dir, f"{safe_target}_*.md")
                    matches = sorted(glob_mod.glob(pattern), reverse=True)
                return {
                    "agent": "SecurityAgent",
                    "success": bool(matches),
                    "operation": tool_name,
                    "output": {"report_path": matches[0] if matches else "", "all_reports": matches[:5]},
                    "error": None if matches else f"No reports found for {target}",
                }
            elif operation == "view_evidence":
                from app.services.security.evidence_capture import EvidenceCapture
                vaults = EvidenceCapture.list_vault_contents()
                if target:
                    safe = target.replace(".", "_")
                    vaults = [v for v in vaults if safe in v.get("name", "")]
                return {
                    "agent": "SecurityAgent",
                    "success": True,
                    "operation": tool_name,
                    "output": {"vaults": vaults},
                    "error": None,
                }
            elif operation == "decrypt_token":
                from app.services.security.evidence_capture import EvidenceCapture
                vault_path = params.get("vault_path", "")
                try:
                    decrypted = EvidenceCapture.decrypt_token(vault_path)
                    return {
                        "agent": "SecurityAgent",
                        "success": True,
                        "operation": tool_name,
                        "output": {"decrypted_value": decrypted, "path": vault_path},
                        "error": None,
                    }
                except ValueError as exc:
                    return {
                        "agent": "SecurityAgent",
                        "success": False,
                        "operation": tool_name,
                        "output": None,
                        "error": str(exc),
                    }
            else:
                return {
                    "agent": "SecurityAgent",
                    "success": False,
                    "operation": tool_name,
                    "output": None,
                    "error": f"Unknown security operation: {operation}",
                }

        elif agent_prefix == "plugin":
            # Plugin self-service: Daena can install / diagnose / fix
            # / list her own plugins via this surface. Routes through
            # governance like every other DaenaBot agent -- the
            # PluginAdminAgent.OPERATION_ACTION_MAP controls the
            # tier classification.
            from app.services.daenabot.plugin_admin_agent import (
                PluginAdminAgent,
            )

            agent = PluginAdminAgent()
            return await agent.execute(operation, params)

        elif agent_prefix in ("gmail", "calendar", "google-calendar", "notion"):
            # External integration -- route through IntegrationRouter
            from app.services.integrations.integration_router import IntegrationRouter

            router = IntegrationRouter(self.db)
            result = await router.execute(
                provider=agent_prefix,
                tool_name=operation,
                params=params,
                user_id=params.pop("_user_id", None) or params.get("user_id"),
                tenant_id=params.pop("_tenant_id", None) or params.get("tenant_id"),
            )
            return {
                "agent": f"integration.{agent_prefix}",
                "success": True,
                "operation": f"{agent_prefix}.{operation}",
                "output": result,
                "error": None,
            }

        return {
            "agent": "unknown",
            "success": False,
            "operation": tool_name,
            "output": None,
            "error": f"Unknown agent: '{agent_prefix}'",
        }

    @staticmethod
    def _resolve_action_type(tool_name: str, params: dict) -> str:
        """Resolve the governance action_type for a tool call.

        For DaenaBot agents, maps the operation to the correct
        action_type for risk classification.  For terminal commands
        the risk depends on the actual command being run.
        """
        if "." not in tool_name:
            return tool_name.upper()  # legacy behaviour

        agent_prefix, operation = tool_name.split(".", 1)
        agent_prefix = agent_prefix.lower()

        if agent_prefix == "file":
            from app.services.daenabot.file_agent import FileAgent
            return FileAgent.OPERATION_ACTION_MAP.get(operation, "EXECUTE")

        if agent_prefix == "terminal":
            from app.services.daenabot.terminal_agent import TerminalAgent
            if operation == "execute_command":
                command = params.get("command", "")
                return TerminalAgent.classify_command_risk(command)
            return "EXECUTE"

        if agent_prefix == "browser":
            from app.services.daenabot.browser_agent import BrowserAgent
            return BrowserAgent.OPERATION_ACTION_MAP.get(operation, "EXECUTE")

        if agent_prefix == "vision_browser":
            from app.services.daenabot.vision_browser_agent import VisionBrowserAgent
            return VisionBrowserAgent.OPERATION_ACTION_MAP.get(operation, "EXECUTE")

        if agent_prefix == "web_crawler":
            from app.services.daenabot.web_crawler_agent import WebCrawlerAgent
            return WebCrawlerAgent.OPERATION_ACTION_MAP.get(operation, "READ")

        # External integrations -- classify by operation risk
        if agent_prefix in ("gmail", "calendar", "google-calendar", "notion"):
            # Read operations are low-risk (Tier 0-1)
            read_ops = {
                "search_emails", "read_email", "list_events",
                "find_free_time", "search_pages", "read_page",
                "query_database",
            }
            # Write operations are medium-risk (Tier 2)
            write_ops = {
                "create_draft", "create_event", "update_event",
                "create_page",
            }
            # Send operations are high-risk (Tier 3)
            send_ops = {"send_email"}

            if operation in read_ops:
                return "READ_EXTERNAL"
            if operation in write_ops:
                return "WRITE_EXTERNAL"
            if operation in send_ops:
                return "SEND_EXTERNAL"
            return "EXECUTE"

        return tool_name.upper()
