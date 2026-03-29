"""Chat endpoints: session CRUD, message management, and SSE streaming.

Thin router — CRUD via ChatService, streaming via ChatOrchestrator.
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.schemas.chat import (
    CreateSessionRequest,
    SendMessageRequest,
    StreamMessageRequest,
    TruncateMessagesRequest,
    UpdateSessionRequest,
)
from app.services.chat import ChatService

router = APIRouter()

import logging as _logging

_chat_logger = _logging.getLogger(__name__)


async def _run_memory_writeback(wb: dict) -> None:
    """Background task: write memory with a fresh DB session.

    Called after the SSE stream yields a _memory_writeback event.
    Uses its own DB connection so the SSE generator's session
    doesn't need to be alive.
    """
    try:
        from uuid import UUID as _UUID

        from app.core.database import async_session_factory
        from app.services.memory import MemoryService

        async with async_session_factory() as db:
            mem = MemoryService(db)
            tid = _UUID(wb["tenant_id"])
            uid = _UUID(wb["user_id"])
            sid = _UUID(wb["session_id"])

            # (1) Session interaction memory
            summary = f"Q: {wb['user_content'][:80]}... A: {wb['collected_content'][:120]}..."
            await mem.store(
                tenant_id=tid,
                user_id=uid,
                content=f"{wb['user_content']}\n---\n{wb['collected_content']}",
                content_type="INTERACTION",
                summary=summary,
                tags=[wb["intent"], wb["model"]],
                source="chat_pipeline",
                confidence=0.5,
                tier=0,
                scope="SESSION",
                session_id=sid,
                metadata={
                    "model": wb["model"],
                    "provider": wb["provider"],
                    "governance_tier": wb["governance_tier"],
                    "latency_ms": wb["latency_ms"],
                },
            )

            # (2) Agent experience (quarantined in L2Q)
            exp_content = (
                f"Intent: {wb['intent']}\n"
                f"Complexity: {wb['complexity']}\n"
                f"Routing: {wb['routing']}\n"
                f"Model: {wb['model']}\n"
                f"Provider: {wb['provider']}\n"
                f"Governance tier: {wb['governance_tier']}\n"
                f"Latency: {wb['latency_ms']}ms\n"
                f"Skills injected: {wb['skill_count']}"
            )
            await mem.store_experience(
                tenant_id=tid,
                user_id=uid,
                agent_id=uid,
                content=exp_content,
                content_type="AGENT_DECISION",
                summary=f"{wb['intent']} routed to {wb['model']} via {wb['routing']}",
                success_flag=True,
                confidence=0.6,
                tags=[wb["intent"], wb["routing"], wb["model"]],
                metadata={
                    "session_id": wb["session_id"],
                    "latency_ms": wb["latency_ms"],
                    "skill_count": wb["skill_count"],
                },
            )

            await db.commit()
            _chat_logger.info("memory_writeback.success", extra={"model": wb["model"]})
    except Exception as err:
        _chat_logger.warning("memory_writeback.failed", extra={"error": str(err)})


async def get_chat_service(
    db: AsyncSession = Depends(get_db),
) -> ChatService:
    """Factory dependency for ChatService."""
    return ChatService(db)


def get_model_registry(request: Request):
    """Get the ModelRegistry singleton from app state."""
    return request.app.state.model_registry


async def _resolve_stream_session(
    *,
    session_id: UUID | None,
    body: StreamMessageRequest,
    user: CurrentUser,
    chat_svc: ChatService,
) -> tuple[UUID, dict | None]:
    """Return an existing session ID or create a new session for first turn."""
    resolved_session_id = session_id or body.session_id
    if resolved_session_id is not None:
        return resolved_session_id, None

    created_session = await chat_svc.create_session(
        user_id=user.id,
        tenant_id=user.tenant_id,
        title=body.title,
        mode=body.mode or "CMD",
        routing_mode=body.routing_mode or "STANDARD",
        governance_slider=body.governance_slider or "STANDARD",
        category_id=body.category_id,
        department_id=body.department_id,
        autopilot=body.autopilot,
        think_mode=body.think_mode,
    )
    return UUID(created_session["id"]), created_session


async def _stream_message_response(
    *,
    session_id: UUID | None,
    body: StreamMessageRequest,
    request: Request,
    user: CurrentUser,
    db: AsyncSession,
) -> StreamingResponse:
    """Canonical stream response for existing-session and first-turn chat."""
    chat_svc = ChatService(db)
    resolved_session_id, created_session = await _resolve_stream_session(
        session_id=session_id,
        body=body,
        user=user,
        chat_svc=chat_svc,
    )

    user_msg = await chat_svc.add_message(
        session_id=resolved_session_id,
        tenant_id=user.tenant_id,
        role=body.role,
        content=body.content,
    )
    if created_session is not None:
        created_session["message_count"] = 1

    registry = get_model_registry(request)

    # ── Slash command routing ──
    content_stripped = body.content.strip()
    slash_command = None
    slash_arg = ""
    if content_stripped.startswith("/fix "):
        slash_command = "fix"
        slash_arg = content_stripped[5:].strip()
    elif content_stripped.startswith("/improve "):
        slash_command = "improve"
        slash_arg = content_stripped[9:].strip()
    elif content_stripped == "/audit":
        slash_command = "audit"

    if slash_command:
        from app.services.self_fix import run_audit, run_fix, run_improve

        async def slash_event_generator():
            if created_session is not None:
                yield f"data: {json.dumps({'type': 'session_created', 'data': created_session})}\n\n"
            yield f"data: {json.dumps({'type': 'user_message', 'data': user_msg})}\n\n"

            if slash_command == "audit":
                yield f"data: {json.dumps({'type': 'thinking', 'stage': 'self_improvement', 'command': 'audit'})}\n\n"
                result = await run_audit()
                # Stream result as chunks
                report_lines = [f"## System Audit Report\n"]
                for step in result.steps:
                    icon = "pass" if step["status"] == "pass" else ("fail" if step["status"] == "fail" else "skip")
                    report_lines.append(f"- **{step['name']}**: {icon} {step['output']}")
                report_text = "\n".join(report_lines)
                yield f"data: {json.dumps({'type': 'chunk', 'content': report_text})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'model_id': 'self-improvement', 'provider': 'DAENA'})}\n\n"

            elif slash_command == "fix":
                async for event in run_fix(slash_arg):
                    yield f"data: {json.dumps(event)}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'model_id': 'self-improvement', 'provider': 'DAENA'})}\n\n"

            elif slash_command == "improve":
                async for event in run_improve(slash_arg):
                    yield f"data: {json.dumps(event)}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'model_id': 'self-improvement', 'provider': 'DAENA'})}\n\n"

        return StreamingResponse(
            slash_event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    # ── Normal chat flow ──
    from app.services.chat_orchestrator import ChatOrchestrator

    orchestrator = ChatOrchestrator(db, registry)

    # Collect memory writeback data to schedule as background task
    _pending_writeback: list[dict] = []

    async def event_generator():
        if created_session is not None:
            yield f"data: {json.dumps({'type': 'session_created', 'data': created_session})}\n\n"

        yield f"data: {json.dumps({'type': 'user_message', 'data': user_msg})}\n\n"

        async for event in orchestrator.stream_reply(
            session_id=resolved_session_id,
            tenant_id=user.tenant_id,
            user_id=user.id,
            user_role=user.role,
            preferred_model=body.preferred_model,
            governance_slider=body.governance_slider or "STANDARD",
            routing_mode_override=body.routing_mode,
            action_mode_override=body.mode,
        ):
            # Intercept memory writeback events (not sent to client)
            if isinstance(event, dict) and event.get("type") == "_memory_writeback":
                _pending_writeback.append(event)
                continue
            yield f"data: {json.dumps(event)}\n\n"

    async def _stream_and_writeback():
        """Yield all SSE events, then run memory writeback with fresh session."""
        async for chunk in event_generator():
            yield chunk
        # After stream completes, write memory with a fresh DB session
        _chat_logger.info(
            "memory_writeback.pending",
            extra={"count": len(_pending_writeback)},
        )
        for wb in _pending_writeback:
            await _run_memory_writeback(wb)

    return StreamingResponse(
        _stream_and_writeback(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )


@router.get("/model-registry")
async def get_live_model_registry(
    request: Request,
    response: Response,
    refresh: bool = Query(True),
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return the live backend source of truth for providers and models.

    Includes both LLM models (Ollama, Anthropic API, etc.) and CLI runtimes
    (Claude Code, Codex, Gemini CLI) so the frontend can show all options
    in the chat model selector.
    """
    registry = get_model_registry(request)
    snapshot = await registry.snapshot(force_refresh=refresh)

    # Merge CLI runtimes into the model list so they appear in the selector
    try:
        from app.core.events import get_runtime_registry

        rt_registry = get_runtime_registry()
        rt_data = rt_registry.to_dict()
        cli_models = []

        for rt in rt_data.get("runtimes", []):
            # Only include installed + authenticated CLI runtimes
            if not rt.get("installed"):
                continue
            sub = rt.get("subscription") or {}
            if not sub.get("is_authenticated") and rt["runtime_id"] != "ollama":
                continue
            # Skip Ollama (its individual models are already in the registry)
            if rt["runtime_id"] == "ollama":
                continue

            plan_label = sub.get("plan_name") or ""
            display = rt["display_name"]
            if plan_label:
                display = f"{display} ({plan_label})"

            cli_models.append({
                "model_id": rt["runtime_id"],
                "display_name": display,
                "provider": "CLI_RUNTIME",
                "provider_display_name": "Runtimes",
                "selectable": True,
                "availability_reason": None,
                "tags": ["runtime", "cli", rt["runtime_id"]],
                "context_window": 200000,
                "cost_per_1m_input": 0.0,
                "cost_per_1m_output": 0.0,
                "is_runtime": True,
                "runtime_id": rt["runtime_id"],
            })

        if cli_models:
            existing_models = snapshot.get("models", [])
            snapshot["models"] = cli_models + existing_models
            summary = snapshot.get("summary", {})
            summary["selectable_model_count"] = (
                summary.get("selectable_model_count", 0) + len(cli_models)
            )
    except Exception:
        pass  # Graceful: if runtime registry unavailable, return models only

    response.headers["Cache-Control"] = "private, max-age=30, stale-while-revalidate=60"
    return {"success": True, "data": snapshot}


# ── Sessions ──


@router.post("/sessions", status_code=201)
async def create_session(
    body: CreateSessionRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    """Create a new chat session for the current user."""
    result = await service.create_session(
        user_id=user.id,
        tenant_id=user.tenant_id,
        title=body.title,
        mode=body.mode,
        routing_mode=body.routing_mode,
        governance_slider=body.governance_slider,
        category_id=body.category_id,
        department_id=body.department_id,
        autopilot=body.autopilot,
        think_mode=body.think_mode,
    )
    return {"success": True, "data": result}


@router.get("/sessions")
async def list_sessions(
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    include_archived: bool = Query(False),
) -> dict:
    """List chat sessions for the current user."""
    result = await service.list_sessions(
        tenant_id=user.tenant_id,
        user_id=user.id,
        page=page,
        page_size=page_size,
        include_archived=include_archived,
    )
    response.headers["Cache-Control"] = "private, max-age=5, stale-while-revalidate=15"
    return {"success": True, "data": result["items"], "pagination": result["pagination"]}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    """Get a single chat session by ID."""
    result = await service.get_session(
        session_id=session_id, tenant_id=user.tenant_id
    )
    return {"success": True, "data": result}


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: UUID,
    body: UpdateSessionRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    """Update session metadata (title, mode, archive status)."""
    result = await service.update_session(
        session_id=session_id,
        tenant_id=user.tenant_id,
        title=body.title,
        mode=body.mode,
        routing_mode=body.routing_mode,
        governance_slider=body.governance_slider,
        is_archived=body.is_archived,
        autopilot=body.autopilot,
        think_mode=body.think_mode,
    )
    return {"success": True, "data": result}


@router.delete("/sessions/{session_id}", status_code=200)
async def delete_session(
    session_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    """Soft-delete a chat session (sets is_archived=True)."""
    await service.delete_session(
        session_id=session_id,
        tenant_id=user.tenant_id,
    )
    return {"success": True}


# ── Messages ──


@router.post("/sessions/{session_id}/messages", status_code=201)
async def send_message(
    session_id: UUID,
    body: SendMessageRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    """Add a user message and generate an ASSISTANT reply via Ollama.

    Flow:
        1. Persist the USER message
        2. Call Ollama with recent conversation context
        3. Persist and return the ASSISTANT reply

    Returns both messages: user_message + assistant_message.
    """
    # 1. Persist user message
    user_msg = await service.add_message(
        session_id=session_id,
        tenant_id=user.tenant_id,
        role=body.role,
        content=body.content,
    )

    # 2. Generate ASSISTANT reply (calls Ollama, persists response)
    assistant_msg = await service.generate_reply(
        session_id=session_id,
        tenant_id=user.tenant_id,
    )

    return {
        "success": True,
        "data": {
            "user_message": user_msg,
            "assistant_message": assistant_msg,
        },
    }


@router.post("/sessions/{session_id}/messages/stream")
async def stream_message(
    session_id: UUID,
    body: StreamMessageRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Compatibility route for streaming an existing session reply."""
    return await _stream_message_response(
        session_id=session_id,
        body=body,
        request=request,
        user=user,
        db=db,
    )


@router.post("/messages/stream")
async def stream_message_canonical(
    body: StreamMessageRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Canonical streaming route for existing-session and first-turn chat."""
    return await _stream_message_response(
        session_id=None,
        body=body,
        request=request,
        user=user,
        db=db,
    )


@router.delete("/sessions/{session_id}/messages/truncate", status_code=200)
async def truncate_messages(
    session_id: UUID,
    body: TruncateMessagesRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    """Delete all messages from from_message_id onwards (inclusive).

    Used by the message-edit flow: client truncates DB state, then
    resends the edited message through the stream endpoint.
    """
    deleted = await service.truncate_messages(
        session_id=session_id,
        tenant_id=user.tenant_id,
        from_message_id=body.from_message_id,
    )
    return {"success": True, "data": {"deleted": deleted}}


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
) -> dict:
    """Retrieve messages for a chat session."""
    result = await service.get_messages(
        session_id=session_id,
        tenant_id=user.tenant_id,
        page=page,
        page_size=page_size,
    )
    return {"success": True, "data": result["items"], "pagination": result["pagination"]}
