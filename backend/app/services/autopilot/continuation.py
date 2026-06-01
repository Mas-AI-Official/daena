"""Autopilot Controller: manages the continuation loop.

When Autopilot is ON, this controller executes plan steps sequentially,
checking criticality before each step, pausing for approval on critical
actions, enforcing cost ceilings, and pushing WebSocket notifications.

Key design decisions:
    1. Fail-safe: Unknown actions always PAUSE_FOR_APPROVAL
    2. Cost ceiling: Default $1.00 per autopilot run
    3. 5-minute approval timeout: Pauses (doesn't auto-approve)
    4. Kill switch is instant: Flag checked before every step
    5. WebSocket notifications for every state change
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.autopilot.criticality_classifier import (
    CriticalityClassifier,
    CriticalityLevel,
)
from app.services.swarm.executor import SwarmExecutor
from app.services.swarm.planner import SubTask

logger = get_logger(__name__)

# Timeout for user approval of a paused step
APPROVAL_TIMEOUT_SECONDS = 300.0  # 5 minutes

# Default cost ceiling per autopilot run
DEFAULT_COST_CEILING_USD = 1.0

# Synthetic gate id for the initial plan-review pause on goal-derived runs.
# Approving this gate (via /autopilot/approve) begins execution; rejecting it
# stops the run before any step executes or budget is spent.
PLAN_REVIEW_GATE = "__plan_review__"


@dataclass
class AutopilotState:
    """Tracks Autopilot state per session.

    Serializable for WebSocket transmission and API responses.
    The _approval_event is transient and not serialized.
    """

    enabled: bool = False
    session_id: str = ""
    current_plan_id: str | None = None
    completed_steps: list[str] = field(default_factory=list)
    pending_steps: list[str] = field(default_factory=list)
    paused_step: str | None = None
    total_cost_usd: float = 0.0
    cost_ceiling_usd: float = DEFAULT_COST_CEILING_USD
    killed: bool = False
    awaiting_plan_approval: bool = False
    plan: list[dict] = field(default_factory=list)
    notifications: list[dict] = field(default_factory=list)
    _approval_event: asyncio.Event | None = field(
        default=None, repr=False, compare=False,
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API/WebSocket (excludes internal event)."""
        return {
            "enabled": self.enabled,
            "session_id": self.session_id,
            "current_plan_id": self.current_plan_id,
            "completed_steps": self.completed_steps,
            "pending_steps": self.pending_steps,
            "paused_step": self.paused_step,
            "total_cost_usd": self.total_cost_usd,
            "cost_ceiling_usd": self.cost_ceiling_usd,
            "killed": self.killed,
            "awaiting_plan_approval": self.awaiting_plan_approval,
            "plan": self.plan,
            "total_notifications": len(self.notifications),
        }


class AutopilotController:
    """Manages the continuation loop for Autopilot ON mode.

    Usage::

        controller = AutopilotController(executor, classifier)
        state = await controller.start(session_id, plan, context)
        # ... later ...
        await controller.kill(session_id)

    The controller runs the continuation loop as an asyncio background
    task. Each step is checked for criticality before execution. Critical
    steps pause and wait for user approval via WebSocket.
    """

    def __init__(
        self,
        swarm_executor: SwarmExecutor,
        criticality_classifier: CriticalityClassifier,
        ws_manager: Any = None,
    ) -> None:
        """Initialize the controller.

        Args:
            swarm_executor: Executor for running individual subtasks.
            criticality_classifier: Classifies action criticality.
            ws_manager: WebSocket ConnectionManager for push notifications.
                        If None, notifications are logged but not pushed.
        """
        self._executor = swarm_executor
        self._classifier = criticality_classifier
        self._ws = ws_manager
        self._active_sessions: dict[str, AutopilotState] = {}
        self._background_tasks: dict[str, asyncio.Task] = {}

    async def start(
        self,
        session_id: str,
        plan: list[SubTask],
        context: dict[str, Any] | None = None,
    ) -> AutopilotState:
        """Start Autopilot continuation for a session.

        Args:
            session_id: Chat session ID.
            plan: List of SubTask objects from SwarmPlanner.
            context: Execution context (cost_ceiling, governance_preset, etc.)

        Returns:
            AutopilotState tracking the session's autopilot progress.
        """
        ctx = context or {}
        state = AutopilotState(
            enabled=True,
            session_id=session_id,
            pending_steps=[step.id for step in plan],
            cost_ceiling_usd=ctx.get("cost_ceiling", DEFAULT_COST_CEILING_USD),
            plan=[
                {
                    "id": step.id,
                    "description": step.description,
                    "task_type": step.task_type,
                    "estimated_cost_usd": getattr(step, "estimated_cost_usd", 0.0),
                }
                for step in plan
            ],
        )
        self._active_sessions[session_id] = state

        # Run the continuation loop as a background task
        task = asyncio.create_task(
            self._continuation_loop(state, plan, ctx),
        )
        self._background_tasks[session_id] = task

        await self._notify(state, "autopilot_started", {
            "session_id": session_id,
            "total_steps": len(plan),
            "cost_ceiling": state.cost_ceiling_usd,
        })

        return state

    async def kill(self, session_id: str) -> bool:
        """Emergency stop for Autopilot. Instant effect.

        Args:
            session_id: Session to stop.

        Returns:
            True if session was found and killed.
        """
        state = self._active_sessions.get(session_id)
        if state:
            state.killed = True
            # If waiting for approval, release the wait
            if state._approval_event:
                state._approval_event.set()
            logger.info("autopilot.killed", session_id=session_id)
            return True
        return False

    async def approve_step(self, session_id: str, step_id: str) -> bool:
        """User approves a paused step.

        Args:
            session_id: Session ID.
            step_id: The paused step to approve.

        Returns:
            True if approval was accepted.
        """
        state = self._active_sessions.get(session_id)
        if state and state.paused_step == step_id and state._approval_event:
            state._approval_event.set()
            logger.info(
                "autopilot.step_approved",
                session_id=session_id,
                step_id=step_id,
            )
            return True
        return False

    async def reject_step(self, session_id: str, step_id: str) -> bool:
        """User rejects a paused step, stopping autopilot.

        Args:
            session_id: Session ID.
            step_id: The paused step to reject.

        Returns:
            True if rejection was accepted.
        """
        state = self._active_sessions.get(session_id)
        if state and state.paused_step == step_id:
            state.killed = True
            if state._approval_event:
                state._approval_event.set()
            logger.info(
                "autopilot.step_rejected",
                session_id=session_id,
                step_id=step_id,
            )
            return True
        return False

    def get_state(self, session_id: str) -> AutopilotState | None:
        """Get current autopilot state for a session."""
        return self._active_sessions.get(session_id)

    @property
    def active_session_ids(self) -> list[str]:
        """All session IDs with active autopilot."""
        return [
            sid for sid, state in self._active_sessions.items()
            if state.enabled
        ]

    async def _continuation_loop(
        self,
        state: AutopilotState,
        plan: list[SubTask],
        context: dict[str, Any],
    ) -> None:
        """Core loop: execute steps until done, paused, killed, or over budget.

        This runs as an asyncio background task. It processes each step
        sequentially, checking criticality, cost ceiling, and kill switch
        before each execution.
        """
        try:
            # Governed-first (council DECISION-002): a goal-derived plan pauses
            # for founder review BEFORE any step executes or budget is spent.
            # The plan is the first criticality gate. Approving the synthetic
            # PLAN_REVIEW_GATE via /autopilot/approve begins execution.
            if context.get("require_initial_approval") and plan:
                state.paused_step = PLAN_REVIEW_GATE
                state.awaiting_plan_approval = True
                await self._notify(state, "plan_ready_for_review", {
                    "total_steps": len(plan),
                    "message": "Plan generated. Review and approve to begin execution.",
                })
                approved = await self._wait_for_approval(state, PLAN_REVIEW_GATE)
                state.awaiting_plan_approval = False
                if not approved:
                    return
                state.paused_step = None

            for step in plan:
                # Check kill switch
                if state.killed:
                    await self._notify(state, "autopilot_killed", {
                        "message": "Autopilot stopped by user",
                    })
                    break

                # Check cost ceiling
                if state.total_cost_usd >= state.cost_ceiling_usd:
                    await self._notify(state, "cost_ceiling_hit", {
                        "spent": state.total_cost_usd,
                        "ceiling": state.cost_ceiling_usd,
                    })
                    break

                # Classify this step
                criticality = self._classifier.classify(
                    step.task_type,
                    {"governance_preset": context.get("governance_preset", "BALANCED")},
                )

                if criticality == CriticalityLevel.PAUSE_FOR_APPROVAL:
                    state.paused_step = step.id
                    await self._notify(state, "approval_needed", {
                        "step_id": step.id,
                        "description": step.description,
                        "task_type": step.task_type,
                        "reason": f"Action '{step.task_type}' requires approval",
                    })

                    # Wait for approval (or kill)
                    approved = await self._wait_for_approval(state, step.id)
                    if not approved:
                        break
                    state.paused_step = None

                # Execute the step
                try:
                    receipt = await self._executor.execute_single(step, context)
                    state.completed_steps.append(step.id)
                    if step.id in state.pending_steps:
                        state.pending_steps.remove(step.id)
                    state.total_cost_usd += receipt.estimated_cost_usd

                    # Notification type depends on criticality
                    event_type = "step_completed"
                    if criticality == CriticalityLevel.NOTIFY_AFTER:
                        event_type = "step_completed_notify"

                    await self._notify(state, event_type, {
                        "step_id": step.id,
                        "description": step.description,
                        "runtime": receipt.runtime_id,
                        "status": receipt.status,
                        "cost": receipt.estimated_cost_usd,
                        "duration_ms": receipt.duration_ms,
                    })

                except Exception as exc:
                    await self._notify(state, "step_failed", {
                        "step_id": step.id,
                        "error": str(exc),
                    })
                    break

        finally:
            # Autopilot complete (regardless of how we exited)
            state.enabled = False
            await self._notify(state, "autopilot_complete", {
                "completed": len(state.completed_steps),
                "total": len(state.completed_steps) + len(state.pending_steps),
                "total_cost": state.total_cost_usd,
            })

            # Cleanup
            self._background_tasks.pop(state.session_id, None)

    async def _wait_for_approval(
        self, state: AutopilotState, step_id: str,
    ) -> bool:
        """Block until user approves, rejects, or kills. 5-minute timeout."""
        state._approval_event = asyncio.Event()
        try:
            await asyncio.wait_for(
                state._approval_event.wait(),
                timeout=APPROVAL_TIMEOUT_SECONDS,
            )
            return not state.killed
        except TimeoutError:
            await self._notify(state, "approval_timeout", {
                "step_id": step_id,
                "message": "Approval timed out after 5 minutes. Autopilot paused.",
            })
            return False
        finally:
            state._approval_event = None

    async def _notify(
        self, state: AutopilotState, event_type: str, data: Any,
    ) -> None:
        """Push notification to user via WebSocket (if available)."""
        notification = {
            "type": event_type,
            "session_id": state.session_id,
            "data": data,
        }
        state.notifications.append(notification)

        if self._ws:
            try:
                await self._ws.broadcast(state.session_id, notification)
            except Exception as exc:
                logger.warning(
                    "autopilot.ws_notify_failed",
                    error=str(exc),
                    event_type=event_type,
                )

        logger.info(
            "autopilot.notification",
            event_type=event_type,
            session_id=state.session_id,
        )
