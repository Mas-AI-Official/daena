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

from app.core.constants import ChatMode, ExecutionStatus, TaskStatus
from app.core.exceptions import (
    GovernanceBlockedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.models.chat import ChatSession
from app.models.execution import Task, ToolExecution
from app.services._base import BaseService
from app.services.governance import GovernanceEngine

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
            governance_slider="STANDARD",
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
        governance_slider: str = "STANDARD",
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
            governance_slider=governance_slider,
            actor_type="USER",
            actor_role=actor_role,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            plan_approval_id=plan_approval_id,
        )
        decision["action_type"] = resolved_action
        return decision

    # ── Tool Execution ────────────────────────────────────────

    async def execute_tool(
        self,
        *,
        tool_name: str,
        params: dict,
        session_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        governance_slider: str = "STANDARD",
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
            governance_slider: Current governance preset.
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

        # Step 2: Governance evaluation — resolve correct action_type
        #         for DaenaBot agents (operation-aware risk classification)
        resolved_action = self._resolve_action_type(tool_name, params)
        engine = GovernanceEngine(self.db)
        decision = await engine.evaluate(
            action_type=resolved_action,
            action_params=params,
            governance_slider=governance_slider,
            actor_type="USER",
            actor_role=actor_role,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            plan_approval_id=plan_approval_id,
        )

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

        # Step 4: Check governance decision
        if not decision["allowed"]:
            execution.status = ExecutionStatus.BLOCKED.value
            execution.error = decision["message"]
            await self.db.commit()

            raise GovernanceBlockedError(
                f"Tool '{tool_name}' blocked: {decision['message']}"
            )

        # Step 5: Execute the tool
        start_time = time.monotonic()
        try:
            execution.status = ExecutionStatus.RUNNING.value
            await self.db.flush()

            # Actual tool execution would be dispatched here.
            # For now, we record the attempt and return a stub.
            result = await self._dispatch_tool(tool_name, params)

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            execution.status = ExecutionStatus.COMPLETED.value
            execution.tool_result = result
            execution.latency_ms = elapsed_ms
            await self.db.commit()

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
    ) -> Task:
        """Create a background task for Autopilot mode.

        Args:
            name: Human-readable task name.
            user_id: Owner of the task.
            tenant_id: Tenant scope.
            description: Optional detailed description.
            session_id: Optional chat session context.

        Returns:
            The created Task model instance.
        """
        task = Task(
            name=name,
            description=description,
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_id,
            status=TaskStatus.PENDING.value,
            progress=0,
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
        return self._task_to_dict(task)

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
        return self._task_to_dict(task)

    async def delete_task(self, task_id: UUID, tenant_id: UUID) -> None:
        """Permanently delete a task owned by the tenant."""
        task = await self._get_task_orm(task_id, tenant_id)
        await self.db.delete(task)
        await self.db.commit()

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
        self, tool_name: str, params: dict,
    ) -> dict:
        """Dispatch tool execution to the appropriate DaenaBot agent.

        Tool names use dot notation: ``file.read_file``,
        ``terminal.execute_command``, ``browser.navigate``.
        The prefix selects the agent; the suffix selects the operation.

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
