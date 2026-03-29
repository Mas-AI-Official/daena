"""Chat Orchestrator — wires the full pipeline for chat responses.

Pipeline stages:
    0. Security gate (injection scanning)
    1. Load session + context
    2. Query understanding (intent, complexity, risk)
    3. Governance pre-check
    4. Cost preflight
    5. Route to model (or use preferred_model override)
    6. Memory recall for context enrichment
    7. Build LLM request (+ TLM tool catalog injection)
  7.5. DaenaBot dispatch (EXE mode - executes tool, injects result)
  7.6. TLM records tool execution, tracks usage
    8. Stream LLM response
    9. Persist assistant message
   10. Record cost + audit log + TLM turn tick

ChatService stays as pure CRUD. This layer orchestrates the services.
TLM (Tool Lifecycle Manager) handles tool activation/deactivation, usage
tracking, cost savings analytics, and NBMF pattern learning.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator
from typing import Any
import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class _AgentLoopHandled(Exception):
    """Sentinel: AgentLoop already handled the task, skip single-shot runtime."""

from app.core.constants import ChatMode, GovernanceSlider, RoutingMode
from app.core.logging import get_logger
from app.models.chat import ChatMessage, ChatSession
from app.services.chat import ChatService
from app.services.providers.base import GenerateRequest, LLMMessage

logger = get_logger(__name__)

# ── System prompts (same as ChatService, shared here) ─────────

_SYSTEM_PROMPT_DEFAULT = (
    "You are Daena, a governed multi-agent AI orchestration system built by MAS-AI Technologies. "
    "You are warm, professional, and knowledgeable. You have deep expertise across engineering, "
    "product, marketing, sales, finance, operations, research, legal, skill governance, and "
    "security operations through your 10 department agents.\n\n"
    "FIRST MESSAGE RULE: If the conversation history is empty (this is the very first exchange "
    "in a new session), greet the user briefly and warmly by name if known, or just say hello. "
    "Keep it to one sentence, then address whatever they asked. After the first message, never "
    "re-introduce yourself or greet again. Just be natural and conversational.\n\n"
    "IDENTITY RULES: Never start responses with 'As an AI...' or similar disclaimers. "
    "Never call yourself an AI assistant, a decision-support tool, or any corporate label. "
    "If someone asks who you are, you are Daena. If someone gives you a nickname, use it. "
    "Think of yourself as a capable, senior colleague, not a chatbot.\n\n"
    "RESPONSE LENGTH: Match response length to input length. One-word input = one-sentence "
    "response. Short question = 2-3 sentences. Only give long answers for complex questions. "
    "If someone says hi, just say hi back warmly in one sentence. "
    "Never volunteer information the user did not ask for.\n\n"
    "You are NOT a department specialist in general chat. Never say things like 'I can help "
    "you with programming' or 'I specialize in research' unless you are explicitly embedded "
    "in a department context. In general chat, you help with anything, no domain framing.\n\n"
    "Lead with the answer. Never open with filler or 'How can I help you today?' on follow-up "
    "messages. Never use headers like 'Self-Awareness' or 'Limitations'. Never list your "
    "limitations unless specifically asked. Just answer the question directly and helpfully.\n\n"
    "Be conversational, not corporate. No 'Great question!', 'Absolutely!', "
    "'I'd be happy to help!' Just talk like a smart person who knows their stuff. "
    "When uncertain, give your best assessment with a confidence qualifier, "
    "not a disclaimer wall.\n\n"
    "Write in flowing prose by default. No bullet points or numbered lists unless the user "
    "explicitly asks for a list or the content is genuinely a sequence of steps. "
    "Use code blocks for code, tables for comparisons, bold for key terms. "
    "End with a concrete next step when the conversation calls for it.\n\n"
    "FORMATTING RULE: Never use em dash (\u2014), en dash (\u2013), or a standalone hyphen (-) "
    "as a stylistic separator or parenthetical. Use commas, semicolons, colons, or parentheses "
    "instead. This is a hard rule with no exceptions."
)

_SYSTEM_PROMPT_DEPARTMENT = (
    "You are Daena, a governed multi-agent AI orchestration system built by MAS-AI Technologies, "
    "currently embedded in the {dept} department. "
    "You think through a {dept} lens first; use its frameworks, terminology, and priorities. "
    "Pull from other departments when relevant, but anchor in {dept} expertise.\n\n"
    "FIRST MESSAGE RULE: If the conversation history is empty (this is the very first exchange "
    "in a new session), greet the user briefly and warmly, then address their question. "
    "After the first message, never re-introduce yourself. Just be natural.\n\n"
    "Never start responses with 'As an AI...' or similar disclaimers. Never call yourself "
    "an AI assistant or a chatbot. You are Daena, a capable colleague with {dept} expertise. "
    "If someone gives you a nickname, use it.\n\n"
    "Same rules apply: lead with the answer, no filler, no bot language, "
    "be honest and specific, use structured markdown, respect the user's time."
)


class ChatOrchestrator:
    """Wires QueryUnderstanding → ModelRouter → Governance → LLM → Audit → Cost.

    Usage::

        orchestrator = ChatOrchestrator(db, registry)
        async for event in orchestrator.stream_reply(
            session_id=sid,
            tenant_id=tid,
            user_id=uid,
            user_role="OPERATOR",
        ):
            yield f"data: {json.dumps(event)}\\n\\n"
    """

    def __init__(self, db: AsyncSession, registry: Any) -> None:
        self._db = db
        self._registry = registry
        self._chat = ChatService(db)

    def _estimate_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate USD cost from model pricing in the registry."""
        if not self._registry:
            return 0.0
        model_info = self._registry.get_model_info(model_id)
        if not model_info:
            return 0.0
        input_cost = (input_tokens / 1_000_000) * model_info.cost_per_1m_input
        output_cost = (output_tokens / 1_000_000) * model_info.cost_per_1m_output
        return round(input_cost + output_cost, 8)

    async def stream_reply(
        self,
        *,
        session_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        user_role: str = "OPERATOR",
        preferred_model: str | None = None,
        governance_slider: str = "STANDARD",
        routing_mode_override: str | None = None,
        action_mode_override: str | None = None,
    ) -> AsyncIterator[dict]:
        """Full orchestrated pipeline yielding SSE events.

        Yields dicts with types:
            {"type": "thinking", "stage": "..."}
            {"type": "daenabot_activity", "agent": "...", "status": "..."}
            {"type": "chunk", "content": "..."}
            {"type": "done", "data": {...}}
            {"type": "error", "message": "..."}
        """
        start_time = time.perf_counter()

        # ── Stage 0: Security gate ────────────────────────────
        # Load the user's latest message for scanning
        last_msg_stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == "USER",
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        last_msg_result = await self._db.execute(last_msg_stmt)
        last_user_msg = last_msg_result.scalar_one_or_none()

        if not last_user_msg:
            yield {"type": "error", "message": "No user message found in session."}
            return

        user_content = last_user_msg.content

        from app.services.security_gate import SecurityGate

        scan = SecurityGate.scan(user_content)
        if not scan.safe:
            logger.warning(
                "security_gate.blocked",
                session_id=str(session_id),
                pattern=scan.matched_pattern,
            )
            yield {"type": "error", "message": "Message blocked by security policy."}
            return

        # ── Stage 1: Load session + context ───────────────────
        session_stmt = select(ChatSession).where(ChatSession.id == session_id)
        session_result = await self._db.execute(session_stmt)
        session_obj = session_result.scalar_one_or_none()

        if not session_obj:
            yield {"type": "error", "message": "Session not found."}
            return

        # Resolve session modes: request-level override > session stored value > default
        chat_mode = ChatMode(action_mode_override) if action_mode_override else (
            ChatMode(session_obj.mode) if session_obj.mode else ChatMode.CMD
        )
        requested_routing_mode = (
            RoutingMode(routing_mode_override) if routing_mode_override else (
                RoutingMode(session_obj.routing_mode)
                if session_obj.routing_mode
                else RoutingMode.STANDARD
            )
        )
        routing_mode = requested_routing_mode

        # Council/Quintessence: require minimum 2 selectable models.
        # Council requires 2+ models (multi-model debate).
        # Quintessence works with 1 model (sequential DCP expert lenses).
        _mode_downgraded = False
        if routing_mode in (RoutingMode.COUNCIL, RoutingMode.QUINTESSENCE):
            selectable_count = 0
            if self._registry:
                try:
                    snapshot = self._registry.snapshot(force_refresh=False)
                    summary = snapshot.get("summary", {})
                    raw_count = summary.get("selectable_model_count", 0)
                    selectable_count = int(raw_count) if isinstance(raw_count, (int, float)) else 0
                except Exception:
                    pass
            if selectable_count < 2 and routing_mode == RoutingMode.COUNCIL:
                _original_mode = routing_mode.value
                logger.info(
                    "orchestrator.mode_downgraded",
                    requested=routing_mode.value,
                    applied="STANDARD",
                    reason=f"Only {selectable_count} selectable model(s), Council needs >= 2",
                )
                routing_mode = RoutingMode.STANDARD
                _mode_downgraded = True
            # Quintessence: if only 1 model, keep QUINTESSENCE mode.
            # Stage 8 will apply DCP expert prompts sequentially to the single model.

        autopilot = getattr(session_obj, "autopilot", False) or False
        think_mode = getattr(session_obj, "think_mode", False) or False

        # ── Load user's Primary Mind preference ──
        primary_mind: str | None = None
        try:
            from app.models.identity import User
            user_stmt = select(User).where(User.id == user_id)
            user_result = await self._db.execute(user_stmt)
            user_obj = user_result.scalar_one_or_none()
            if user_obj and user_obj.settings:
                primary_mind = user_obj.settings.get("primary_runtime")
        except Exception:
            logger.debug("orchestrator.primary_mind_lookup_failed", exc_info=True)

        # Build system prompt
        system_prompt = _SYSTEM_PROMPT_DEFAULT
        if session_obj.department_id:
            dept_name = None
            with contextlib.suppress(Exception):
                dept_name = session_obj.department.name if session_obj.department else None
            if dept_name:
                system_prompt = _SYSTEM_PROMPT_DEPARTMENT.format(dept=dept_name)

        # CMD/EXE mode differentiation
        if chat_mode == ChatMode.CMD:
            system_prompt += (
                "\n\nMODE: CMD. "
                "You help with analysis, planning, research, writing, coding, and creative tasks. "
                "If the user needs actions on their system "
                "(files, terminal, web), suggest switching to EXE mode."
            )
        elif chat_mode == ChatMode.EXE:
            system_prompt += (
                "\n\nMODE: EXE (execution enabled). "
                "You may execute actions using available tools "
                "when the user's request requires it. "
                "All tool use is governed -- high-risk actions "
                "require approval."
            )

        # Think mode instruction
        if think_mode:
            system_prompt += (
                "\n\nTHINK MODE: ON. Show your reasoning "
                "step by step before giving the final answer. "
                "Break down complex problems into clear "
                "reasoning chains."
            )

        # Stop-slop: anti-AI-pattern writing rules
        from app.config.stop_slop import STOP_SLOP_SYSTEM_INSTRUCTION
        system_prompt += f"\n\n{STOP_SLOP_SYSTEM_INSTRUCTION}"

        # Load last 20 messages for context
        msgs_stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(20)
        )
        msgs_result = await self._db.execute(msgs_stmt)
        recent = list(reversed(msgs_result.scalars().all()))

        # ── Stage 2: Query understanding ──────────────────────
        yield {"type": "thinking", "stage": "analyzing"}

        from app.services.query_understanding import (
            QueryInput,
            QueryUnderstandingService,
        )

        qu_service = QueryUnderstandingService()
        history = [
            {"role": m.role.lower(), "content": m.content}
            for m in recent[:-1]  # exclude the last (current) user message
        ]

        qu_input = QueryInput(
            raw_message=user_content,
            session_id=str(session_id),
            history=history,
            user_id=str(user_id),
            tenant_id=str(tenant_id),
            execution_mode=chat_mode,
            governance_slider=GovernanceSlider(governance_slider),
        )
        qu_result = qu_service.analyze(qu_input)

        # EXE mode suggestion for CMD mode users with tool-use intent
        from app.services.query_understanding import IntentType

        if (
            qu_result.intent == IntentType.TOOL_USE
            and chat_mode == ChatMode.CMD
        ):
            yield {
                "type": "exe_suggestion",
                "message": (
                    "I can execute this for you. "
                    "Switch to EXE mode or say 'do it'."
                ),
            }

        logger.info(
            "orchestrator.query_understood",
            intent=qu_result.intent.value,
            complexity=qu_result.complexity_label.value,
            risk=qu_result.risk_level.value,
            confidence=qu_result.confidence,
        )

        # ── Stage 3: Governance pre-check ─────────────────────
        yield {"type": "thinking", "stage": "governance"}

        from app.services.governance import GovernanceEngine

        gov = GovernanceEngine(self._db)
        gov_result = await gov.evaluate(
            action_type="LLM_CALL",
            action_params={
                "intent": qu_result.intent.value,
                "risk": qu_result.risk_level.value,
                "model": preferred_model,
                "routing_mode": routing_mode.value,
            },
            governance_slider=governance_slider,
            actor_type="USER",
            actor_role=user_role,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            autopilot=autopilot,
        )

        if not gov_result.get("allowed", True):
            reason = gov_result.get("message", "Action not permitted by governance policy.")

            # When requires_approval=True (tier 3+), persist an approval record
            # so the approvals page shows the blocked task waiting for human review.
            if gov_result.get("requires_approval", False):
                try:
                    from app.services.approval import ApprovalService

                    approval_svc = ApprovalService(self._db)
                    approval_record = await approval_svc.request_approval(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        action_type=gov_result.get("action_type", "LLM_CALL"),
                        action_params=gov_result.get("action_params"),
                        risk_level=gov_result.get("risk_level", "HIGH"),
                        governance_tier=gov_result.get("governance_tier", 3),
                        session_id=session_id,
                        context={
                            "intent": qu_result.intent.value,
                            "message_preview": user_content[:200],
                            "governance_message": reason,
                        },
                    )
                    await self._db.commit()
                    yield {
                        "type": "approval_required",
                        "approval_id": approval_record["id"],
                        "message": reason,
                        "governance_tier": gov_result.get("governance_tier", 3),
                    }
                except Exception as _approval_exc:
                    logger.error(
                        "orchestrator.approval_record_failed",
                        exc_info=True,
                    )
                    yield {"type": "error", "message": reason}
            else:
                yield {"type": "error", "message": reason}
            return

        governance_tier = gov_result.get("governance_tier", 0)

        # Emit governance notification for visibility
        gov_message = gov_result.get("message", "")
        autopilot_override = gov_result.get("autopilot_override", False)

        if _mode_downgraded:
            gov_message = (
                f"Downgraded from {_original_mode} to Standard "
                f"(insufficient models for multi-model synthesis)"
            )
        elif autopilot_override:
            gov_message = (
                f"AGI auto-approved (tier {governance_tier}, "
                f"slider: {governance_slider})"
            )
        elif autopilot and governance_tier >= 3:
            gov_message = (
                f"AGI mode ON but tier {governance_tier} requires human approval "
                f"(slider: {governance_slider}, risk: {gov_result.get('risk_level', 'unknown')})"
            )

        if governance_tier >= 2 or _mode_downgraded or autopilot_override:
            yield {
                "type": "governance_notice",
                "tier": governance_tier,
                "message": gov_message,
                "slider": governance_slider,
                "autopilot": autopilot,
                "autopilot_override": autopilot_override,
            }

        # ── Stage 4: Cost preflight ───────────────────────────
        from app.services.cost_guard import CostGuard

        cost_guard = CostGuard(self._db)
        try:
            await cost_guard.preflight_check(tenant_id=tenant_id, estimated_cost=0.05)
        except Exception as exc:
            yield {"type": "error", "message": f"Budget exceeded: {exc}"}
            return

        # ── Stage 4b: Load founder routing policy ────────────────
        founder_policy: dict = {}
        try:
            from app.models.governance import RoutingPolicy

            policy_stmt = select(RoutingPolicy).where(
                RoutingPolicy.tenant_id == tenant_id,
            )
            policy_result = await self._db.execute(policy_stmt)
            policy_row = policy_result.scalar_one_or_none()
            if policy_row is not None:
                founder_policy = policy_row.policy or {}
        except Exception:
            logger.debug("orchestrator.founder_policy_load_failed", exc_info=True)

        # ── Stage 5: Route to model ───────────────────────────
        from app.services.model_router import ModelRouter

        router = ModelRouter(self._registry)
        decision = None
        routing_source = "auto_routed"

        # ── CLI Runtime direct routing ──
        # If user selected a CLI runtime (claude_code, codex), bypass LLM
        # routing and pipe directly through the runtime adapter.
        _CLI_RUNTIME_IDS = {"claude_code", "codex", "gemini_cli", "grok_cli"}
        if preferred_model and preferred_model in _CLI_RUNTIME_IDS:
            yield {
                "type": "thinking",
                "stage": "runtime_direct",
                "runtime": preferred_model,
            }

            try:
                from app.core.events import get_runtime_registry

                rt_registry = get_runtime_registry()
                adapter = rt_registry.get_adapter(preferred_model)
                if adapter is None or not rt_registry._installed_cache.get(preferred_model, False):
                    yield {"type": "error", "message": f"Runtime {preferred_model} is not available"}
                    return

                # Execute through runtime adapter (async generator)
                import asyncio as _aio

                response_lines: list[str] = []
                async def _collect_runtime():
                    async for line in adapter.execute(user_content, context={
                        "session_id": str(session_id),
                        "working_directory": ".",
                    }):
                        response_lines.append(line)

                await _aio.wait_for(_collect_runtime(), timeout=120.0)

                # Extract response text
                response_text = "\n".join(response_lines).strip()

                # Stream as chunks
                chunk_size = 20
                collected_content = ""
                for i in range(0, len(response_text), chunk_size):
                    chunk = response_text[i:i + chunk_size]
                    collected_content += chunk
                    yield {"type": "chunk", "content": chunk, "model_id": preferred_model}

                # Persist response
                cli_assistant_msg = None
                try:
                    from app.services.chat_service import ChatService as _ChatSvc

                    chat_svc = _ChatSvc(self._db)
                    cli_assistant_msg = await chat_svc.add_message(
                        session_id=session_id,
                        tenant_id=tenant_id,
                        role="ASSISTANT",
                        content=collected_content,
                        model_used=preferred_model,
                        provider_used="CLI_RUNTIME",
                    )
                    await self._db.flush()
                except Exception:
                    logger.warning("orchestrator.cli_persist_failed", exc_info=True)

                done_data = ChatService._message_to_dict(cli_assistant_msg) if cli_assistant_msg else {
                    "id": str(uuid.uuid4()),
                    "session_id": str(session_id),
                    "role": "ASSISTANT",
                    "content": collected_content,
                    "model_used": preferred_model,
                    "provider_used": "CLI_RUNTIME",
                    "governance_tier": None,
                    "cost_usd": 0.0,
                    "latency_ms": 0,
                    "token_count_input": None,
                    "token_count_output": None,
                    "created_at": datetime.utcnow().isoformat(),
                }
                yield {
                    "type": "done",
                    "data": done_data,
                    "model_id": preferred_model,
                    "provider": "CLI_RUNTIME",
                    "cost_usd": 0.0,
                    "latency_ms": 0,
                }

                # Log cost
                try:
                    from app.services.billing.cost_tracker import UnifiedCostTracker

                    tracker = UnifiedCostTracker.get_instance()
                    tracker.log_usage(
                        provider="CLI_RUNTIME",
                        model=preferred_model,
                        input_tokens=len(user_content) // 4,
                        output_tokens=len(collected_content) // 4,
                        cost_usd=0.0,
                        task_type="chat_cli_runtime",
                        session_id=str(session_id),
                    )
                except Exception:
                    pass

                return  # Skip the normal LLM pipeline
            except _aio.TimeoutError:
                yield {"type": "error", "message": f"Runtime {preferred_model} timed out (120s)"}
                return
            except Exception as exc:
                logger.error("orchestrator.cli_runtime_failed", error=str(exc), runtime=preferred_model)
                yield {"type": "error", "message": f"Runtime {preferred_model} failed: {exc}"}
                return

        if preferred_model:
            override_candidate, override_reason = self._resolve_override_candidate(preferred_model)
            if override_candidate is None:
                logger.warning(
                    "orchestrator.preferred_model_unavailable",
                    requested_model=preferred_model,
                    reason=override_reason,
                )
                yield {
                    "type": "thinking",
                    "stage": "routing_override_unavailable",
                    "model": preferred_model,
                    "source": "user_override",
                    "reason": override_reason,
                }
            else:
                from app.services.model_router import RoutingDecision

                override_metadata = {
                    "selection_source": "user_override",
                    "requested_model": preferred_model,
                    "requested_mode": requested_routing_mode.value,
                    "applied_mode": RoutingMode.STANDARD.value,
                    "selection_reason": "Validated explicit model "
                    "selection from the live registry.",
                }
                if routing_mode in (RoutingMode.COUNCIL, RoutingMode.QUINTESSENCE):
                    override_metadata["mode_reason"] = (
                        f"{routing_mode.value} was requested, but explicit model overrides "
                        "run as STANDARD single-model requests."
                    )

                decision = RoutingDecision(
                    mode=RoutingMode.STANDARD,
                    primary=override_candidate,
                    metadata=override_metadata,
                )
                routing_source = "user_override"

        if decision is None and think_mode:
            decision = router.route(
                qu_result,
                requested_mode=RoutingMode.STANDARD,
                preferred_tags=["reasoning", "analysis", "large"],
                metadata={
                    "selection_source": "think_mode",
                    "requested_session_mode": requested_routing_mode.value,
                    "mode_reason": (
                        "Think mode uses a single reasoning-capable model from the "
                        "live registry."
                    ),
                },
                founder_policy=founder_policy,
                primary_mind=primary_mind,
            )
            routing_source = "think_mode"

        if decision is None:
            decision = router.route(
                qu_result,
                requested_mode=routing_mode,
                metadata={
                    "selection_source": "auto_routed",
                    "requested_session_mode": requested_routing_mode.value,
                },
                founder_policy=founder_policy,
                primary_mind=primary_mind,
            )

        # Cost-aware task classification (0 tokens, keyword-based)
        from app.services.cost_router import CostAwareRouter

        _cost_router = CostAwareRouter()
        task_classification = _cost_router.classify_task(user_content)

        routing_event = {
            "type": "thinking",
            "stage": "routing",
            "model": decision.primary.model_id,
            "source": routing_source,
            "requested_mode": requested_routing_mode.value,
            "applied_mode": decision.mode.value,
            "reason": decision.metadata.get("selection_reason"),
            "task_classification": task_classification,
            "classification_cost": "$0.00",
        }
        if preferred_model:
            routing_event["requested_model"] = preferred_model
        if decision.metadata.get("mode_reason"):
            routing_event["mode_reason"] = decision.metadata["mode_reason"]
        yield routing_event

        logger.info(
            "orchestrator.routed",
            model=decision.primary.model_id,
            provider=decision.primary.provider.value,
            requested_mode=requested_routing_mode.value,
            applied_mode=decision.mode.value,
            source=routing_source,
            reason=decision.metadata.get("selection_reason"),
            fallbacks=len(decision.fallback_chain),
        )

        # ── Stage 6: Memory recall ────────────────────────────
        from app.services.memory import MemoryService

        memory_svc = MemoryService(self._db)
        try:
            memories = await memory_svc.recall_for_chat(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                query=user_content,
                tier=2,  # LONG_TERM and above
                page_size=5,
            )
            if memories.get("data"):
                memory_context = "\n".join(
                    f"- {m['content']}" for m in memories["data"]
                )
                system_prompt += f"\n\nRelevant context from memory:\n{memory_context}"
        except Exception:
            logger.debug("orchestrator.memory_recall_failed", exc_info=True)

        # ── Stage 6.1: Agent experience injection ─────────────
        # Inject validated agent experiences (decisions, patterns)
        # that are relevant to the current query. Only non-quarantined,
        # trust-validated experiences are returned.
        try:
            experiences = await memory_svc.recall_experiences(
                tenant_id=tenant_id,
                query=user_content,
                top_k=3,
            )
            if experiences:
                exp_lines = []
                for exp in experiences:
                    exp_summary = exp.get("summary") or exp.get("content", "")[:120]
                    exp_lines.append(f"- {exp_summary}")
                system_prompt += (
                    "\n\nFrom past experience:\n" + "\n".join(exp_lines)
                )
                logger.info(
                    "orchestrator.experiences_injected",
                    count=len(experiences),
                )
        except Exception:
            logger.debug("orchestrator.experience_recall_failed", exc_info=True)

        # ── Stage 6.5: Skill retrieval ─────────────────────────
        # Inject evidence-backed patterns from the Skill Refinery
        # into the system prompt.  Only T2+ skills are eligible
        # (quarantine protocol).  Skips silently if no skills found.
        skill_count = 0
        try:
            from app.services.skill_refinery.retrieval_service import (
                format_evidence_block,
                search_skills,
            )

            skills = await search_skills(
                self._db,
                tenant_id=tenant_id,
                query=user_content,
                top_k=5,
            )
            if skills:
                evidence_block = format_evidence_block(skills)
                if evidence_block:
                    system_prompt += evidence_block
                    skill_count = len(skills)
                    logger.info(
                        "orchestrator.skills_injected",
                        count=skill_count,
                        domains=[s.get("domain") for s in skills],
                    )
        except Exception:
            logger.debug("orchestrator.skill_retrieval_failed", exc_info=True)

        # ── Stage 6.5: TLM Phase-Aware Tool Optimization ────────
        # Detect conversation phase from user message (zero LLM cost),
        # activate/deactivate tools to minimize schema tokens loaded.
        try:
            from app.services.tool_lifecycle.orchestra_integration import optimize_tools_for_turn
            _tlm_context = optimize_tools_for_turn(str(session_id), user_content)
        except Exception:
            _tlm_context = None  # TLM is non-critical

        # ── Stage 7: Build LLM request ────────────────────────
        llm_messages = []
        for msg in recent:
            role = msg.role.lower()
            if role not in ("user", "assistant", "system"):
                role = "user"
            llm_messages.append(LLMMessage(role=role, content=msg.content))

        request = GenerateRequest(
            messages=llm_messages,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=2048,
            model_id=decision.primary.model_id,
            metadata={
                "intent": qu_result.intent.value,
                "requested_routing_mode": requested_routing_mode.value,
                "applied_routing_mode": decision.mode.value,
                "routing_source": routing_source,
                "selection_reason": decision.metadata.get("selection_reason"),
            },
        )

        # ── Stage 7.5: EXE dispatch (Runtime Adapter > DaenaBot) ──
        # For complex multi-step tasks, route through AgentLoop.
        # For simple tasks, use single-shot runtime adapter (faster).
        daenabot_result = None
        _last_tool_name: str | None = None
        _last_tool_desc: str | None = None
        if chat_mode == ChatMode.EXE:
            from app.core.config import get_settings

            settings = get_settings()

            # Check if task is complex enough for AgentLoop
            _use_agent_loop = False
            _multi_step_verbs = ("create", "write", "read", "search", "find", "fix",
                                 "test", "run", "deploy", "build", "update", "delete",
                                 "draft", "save", "generate", "analyze", "audit")
            _verb_count = sum(1 for w in user_content.lower().split() if w in _multi_step_verbs)
            if _verb_count > 2 or len(user_content.split()) > 50:
                _use_agent_loop = True

            if _use_agent_loop:
                try:
                    from app.services.agent_core.agent_loop import AgentLoop

                    agent = AgentLoop()
                    agent_output_lines: list[str] = []
                    async for update in agent.execute(user_content, {"original_task": user_content}):
                        # Stream agent updates to frontend
                        yield update
                        if update.get("type") == "agent_observed" and update.get("output"):
                            agent_output_lines.append(update["output"])

                    receipt = agent.get_receipt()
                    if receipt:
                        daenabot_result = {
                            "status": receipt.get("status", "completed").upper(),
                            "result": {
                                "success": receipt.get("steps_failed", 0) == 0,
                                "runtime": "agent_loop",
                                "display_name": "Agent Loop",
                                "output": "\n".join(agent_output_lines)[:4000],
                                "receipt": receipt,
                            },
                        }
                        _last_tool_name = "agent_loop"
                        _last_tool_desc = f"Executed {receipt.get('steps_completed', 0)} steps via Agent Loop"

                except Exception as al_exc:
                    logger.warning("orchestrator.agent_loop_failed", error=str(al_exc))
                    # Fall through to single-shot runtime

            # Step 0: Try runtime adapter (Claude Code, Codex, etc.)
            # Priority: user-selected runtime > auto-select best CLI
            try:
                # Skip single-shot runtime if AgentLoop already handled it
                if daenabot_result is not None:
                    raise _AgentLoopHandled()

                from app.core.events import get_runtime_registry
                from app.services.runtimes.base_adapter import RuntimeStatus

                runtime_registry = get_runtime_registry()
                selected_rid: str | None = None
                adapter = None

                # Check user-selected runtime from session metadata
                _session_meta = getattr(session_obj, "metadata_", None) or {}
                _user_runtime = _session_meta.get("selected_runtime")
                if _user_runtime:
                    adapter = runtime_registry.get_adapter(_user_runtime)
                    if adapter:
                        health = await runtime_registry.ensure_health_fresh(_user_runtime)
                        if health == RuntimeStatus.ONLINE:
                            selected_rid = _user_runtime
                        else:
                            adapter = None

                # Auto-select: prefer claude_code for EXE mode tasks
                if adapter is None:
                    for candidate_rid in ["claude_code", "codex", "gemini_cli"]:
                        _cand = runtime_registry.get_adapter(candidate_rid)
                        if _cand:
                            _health = await runtime_registry.ensure_health_fresh(candidate_rid)
                            if _health == RuntimeStatus.ONLINE:
                                adapter = _cand
                                selected_rid = candidate_rid
                                break

                if adapter and selected_rid:
                    yield {
                        "type": "runtime_activity",
                        "runtime_id": selected_rid,
                        "display_name": adapter.display_name,
                        "status": "executing",
                        "description": f"Routing to {adapter.display_name}",
                    }

                    try:
                        output_lines: list[str] = []
                        async for line in adapter.execute(
                            task=user_content,
                            context={
                                "session_id": str(session_id),
                                "working_directory": ".",
                                "governance_tier": governance_tier,
                            },
                        ):
                            output_lines.append(line)
                            # Stream runtime output chunks to frontend
                            yield {
                                "type": "runtime_output",
                                "runtime_id": selected_rid,
                                "content": line,
                            }

                        runtime_output = "\n".join(output_lines)
                        daenabot_result = {
                            "status": "COMPLETED",
                            "result": {
                                "success": True,
                                "runtime": selected_rid,
                                "display_name": adapter.display_name,
                                "output": runtime_output[:4000],
                            },
                        }
                        _last_tool_name = f"runtime.{selected_rid}"
                        _last_tool_desc = f"Executed via {adapter.display_name}"

                        yield {
                            "type": "runtime_activity",
                            "runtime_id": selected_rid,
                            "display_name": adapter.display_name,
                            "status": "completed",
                            "description": f"Completed via {adapter.display_name}",
                        }

                        logger.info(
                            "orchestrator.runtime_dispatched",
                            runtime=selected_rid,
                            output_lines=len(output_lines),
                        )
                    except Exception as rt_exc:
                        yield {
                            "type": "runtime_activity",
                            "runtime_id": selected_rid,
                            "display_name": adapter.display_name,
                            "status": "failed",
                            "description": str(rt_exc),
                        }
                        logger.warning(
                            "orchestrator.runtime_dispatch_failed",
                            runtime=selected_rid,
                            error=str(rt_exc),
                        )
                        # Fall through to DaenaBot
            except _AgentLoopHandled:
                pass  # AgentLoop already handled the task
            except Exception as registry_exc:
                logger.debug(
                    "orchestrator.runtime_registry_unavailable",
                    error=str(registry_exc),
                )

            # Step A+B: DaenaBot fallback (if runtime didn't handle it)
            if daenabot_result is None and settings.enable_daenabot:
                from app.services.daenabot.router import DaenaBotRouter
                # Step A: try single-step pattern match (fast path)
                tool_call = DaenaBotRouter.match(user_content)
                if tool_call:
                    _last_tool_name = tool_call.tool_name
                    _last_tool_desc = tool_call.description
                    yield {
                        "type": "daenabot_activity",
                        "agent": tool_call.tool_name.split(".")[0].capitalize() + "Agent",
                        "operation": tool_call.tool_name.split(".")[-1],
                        "status": "executing",
                        "description": tool_call.description,
                    }

                    try:
                        from app.services.execution_service import ExecutionService

                        exec_svc = ExecutionService(self._db)
                        daenabot_result = await exec_svc.execute_tool(
                            tool_name=tool_call.tool_name,
                            params=tool_call.params,
                            session_id=session_id,
                            user_id=user_id,
                            tenant_id=tenant_id,
                            governance_slider=governance_slider,
                            actor_role=user_role,
                        )

                        yield {
                            "type": "daenabot_activity",
                            "agent": tool_call.tool_name.split(".")[0].capitalize() + "Agent",
                            "operation": tool_call.tool_name.split(".")[-1],
                            "status": "completed",
                            "description": tool_call.description,
                        }

                        logger.info(
                            "orchestrator.daenabot_executed",
                            tool=tool_call.tool_name,
                            success=daenabot_result.get("result", {}).get("success", False),
                        )

                        # Stage 7.6: TLM usage tracking
                        try:
                            from app.services.tool_lifecycle.orchestra_integration import record_tool_execution
                            record_tool_execution(
                                conversation_id=str(session_id),
                                tool_name=tool_call.tool_name,
                                agent_id="daenabot",
                                department="execution",
                                success=daenabot_result.get("result", {}).get("success", False),
                            )
                        except Exception:
                            pass  # TLM tracking is non-critical

                    except Exception as exc:
                        yield {
                            "type": "daenabot_activity",
                            "agent": tool_call.tool_name.split(".")[0].capitalize() + "Agent",
                            "operation": tool_call.tool_name.split(".")[-1],
                            "status": "failed",
                            "description": str(exc),
                        }
                        logger.warning(
                            "orchestrator.daenabot_failed",
                            tool=tool_call.tool_name,
                            error=str(exc),
                        )
                        daenabot_result = {
                            "status": "FAILED",
                            "result": {"success": False, "error": str(exc)},
                        }

                # Step B: no single-step match, try multi-step planner
                if daenabot_result is None:
                    try:
                        from app.services.daenabot.planner import ActionPlanner
                        from app.services.daenabot.workspace import (
                            ActionResult,
                            Workspace,
                        )

                        planner = ActionPlanner()
                        actions = await planner.plan(user_content)

                        if actions:
                            workspace = Workspace(session_id=str(session_id))

                            from app.services.execution_service import ExecutionService

                            exec_svc = ExecutionService(self._db)

                            for i, action in enumerate(actions):
                                tool_name = f"{action.agent}.{action.operation}"
                                _last_tool_name = tool_name
                                _last_tool_desc = action.description

                                yield {
                                    "type": "daenabot_activity",
                                    "agent": action.agent.capitalize() + "Agent",
                                    "operation": action.operation,
                                    "status": "executing",
                                    "description": action.description,
                                    "step": i + 1,
                                    "total_steps": len(actions),
                                }

                                try:
                                    step_result = await exec_svc.execute_tool(
                                        tool_name=tool_name,
                                        params=action.params,
                                        session_id=session_id,
                                        user_id=user_id,
                                        tenant_id=tenant_id,
                                        governance_slider=governance_slider,
                                        actor_role=user_role,
                                    )

                                    workspace.add_result(ActionResult(
                                        step_index=i,
                                        agent=action.agent,
                                        operation=action.operation,
                                        success=step_result.get("result", {}).get("success", False),
                                        output=step_result.get("result"),
                                    ))

                                    yield {
                                        "type": "daenabot_activity",
                                        "agent": action.agent.capitalize() + "Agent",
                                        "operation": action.operation,
                                        "status": "completed",
                                        "description": action.description,
                                        "step": i + 1,
                                        "total_steps": len(actions),
                                    }

                                except Exception as step_exc:
                                    workspace.add_result(ActionResult(
                                        step_index=i,
                                        agent=action.agent,
                                        operation=action.operation,
                                        success=False,
                                        error=str(step_exc),
                                    ))

                                    yield {
                                        "type": "daenabot_activity",
                                        "agent": action.agent.capitalize() + "Agent",
                                        "operation": action.operation,
                                        "status": "failed",
                                        "description": str(step_exc),
                                        "step": i + 1,
                                        "total_steps": len(actions),
                                    }
                                    # Continue remaining steps; LLM will summarize

                            # Package workspace into daenabot_result
                            daenabot_result = {
                                "status": "COMPLETED" if workspace.all_succeeded else "PARTIAL",
                                "result": {
                                    "success": workspace.all_succeeded,
                                    "steps": len(workspace.results),
                                    "summary": workspace.get_context_summary(),
                                },
                            }
                            _last_tool_name = _last_tool_name or "multi_step"
                            _last_tool_desc = (
                                _last_tool_desc
                                or f"Executed {len(actions)} steps"
                            )

                            logger.info(
                                "orchestrator.daenabot_multistep",
                                steps=len(actions),
                                succeeded=workspace.all_succeeded,
                            )

                    except Exception as plan_exc:
                        logger.debug(
                            "orchestrator.planner_skipped",
                            error=str(plan_exc),
                        )

        # Inject DaenaBot result into LLM context if we executed a tool
        if daenabot_result is not None:
            import json as _json

            tool_output = daenabot_result.get("result", daenabot_result)
            llm_messages.append(LLMMessage(
                role="user",
                content=(
                    f"[TOOL RESULT -- present this to the user naturally]\n"
                    f"Tool: {_last_tool_name}\n"
                    f"Description: {_last_tool_desc}\n"
                    f"Result:\n```json\n{_json.dumps(tool_output, indent=2, default=str)}\n```\n\n"
                    f"Summarise the result clearly. If it succeeded, show the relevant data. "
                    f"If it failed, explain the error."
                ),
            ))

        # ── Stage 8: LLM stream ──────────────────────────────
        from app.services.llm_service import LLMService

        llm = LLMService(self._registry)
        collected_content = ""
        model_id = decision.primary.model_id
        provider_name = decision.primary.provider.value
        token_count = 0

        # For COUNCIL/QUINTESSENCE: multi-model parallel + synthesis
        if decision.mode in (RoutingMode.COUNCIL, RoutingMode.QUINTESSENCE):
            council_models_used: list[str] = []
            dcp_experts_used: list[str] = []

            yield {
                "type": "thinking",
                "stage": "council_synthesizing",
                "mode": decision.mode.value,
                "models": [c.model_id for c in decision.council_models],
            }

            try:
                # Collect responses from council models
                council_responses: list[tuple[str, str, str]] = []
                tasks_list: list[tuple[Any, asyncio.Task]] = []

                # For Quintessence: build DCP expert directives
                dcp_directives: dict[str, str] = {}
                _all_experts: list = []
                if decision.mode == RoutingMode.QUINTESSENCE:
                    from app.services.dcp_loader import get_dcp_loader

                    dcp_loader = get_dcp_loader()
                    intent_str = qu_result.intent.value
                    _expert_count = max(len(decision.council_models), 5)
                    _all_experts = dcp_loader.get_experts_for_intent(
                        intent_str, count=_expert_count,
                    )

                # Single-model Quintessence: sequential DCP lenses on the same model
                _single_model_qe = (
                    decision.mode == RoutingMode.QUINTESSENCE
                    and len(decision.council_models) == 1
                    and len(_all_experts) > 1
                )

                if _single_model_qe:
                    sole = decision.council_models[0]
                    provider_inst = llm._get_provider(sole)
                    if provider_inst is None:
                        raise RuntimeError("Primary model provider unavailable")

                    yield {
                        "type": "thinking",
                        "stage": "quintessence_sequential",
                        "experts": len(_all_experts),
                        "model": sole.model_id,
                    }

                    for expert in _all_experts[:5]:
                        expert_system = (
                            system_prompt
                            + f"\n\nEXPERT LENS: {expert.archetype} ({expert.id})\n"
                            f"{expert.prompt_directive}\n"
                            f"Blind spots to compensate: {', '.join(expert.blind_spots)}"
                        )
                        expert_request = GenerateRequest(
                            messages=request.messages,
                            model_id=sole.model_id,
                            temperature=request.temperature,
                            max_tokens=request.max_tokens,
                            system_prompt=expert_system,
                            metadata={"stage": "quintessence_lens", "expert": expert.id},
                        )
                        try:
                            resp = await asyncio.wait_for(
                                provider_inst.generate(expert_request), timeout=20.0,
                            )
                            council_responses.append((
                                sole.model_id,
                                sole.provider.value,
                                resp.content,
                            ))
                            dcp_experts_used.append(f"{expert.id}:{expert.archetype}")
                        except (TimeoutError, Exception) as exc:
                            logger.warning(
                                "orchestrator.qe_sequential_expert_failed",
                                expert=expert.id,
                                error=str(exc),
                            )
                    council_models_used.append(sole.model_id)
                else:
                    # Multi-model: parallel execution with optional DCP directives
                    for i, expert in enumerate(_all_experts):
                        if i < len(decision.council_models):
                            cand = decision.council_models[i]
                            dcp_directives[cand.model_id] = (
                                f"\n\nEXPERT LENS: {expert.archetype} ({expert.id})\n"
                                f"{expert.prompt_directive}\n"
                                f"Blind spots to compensate: {', '.join(expert.blind_spots)}"
                            )
                            dcp_experts_used.append(
                                f"{expert.id}:{expert.archetype}",
                            )

                    for candidate in decision.council_models:
                        provider_inst = llm._get_provider(candidate)
                        if provider_inst is None:
                            continue

                        model_system = system_prompt
                        if candidate.model_id in dcp_directives:
                            model_system += dcp_directives[candidate.model_id]

                        model_request = GenerateRequest(
                            messages=request.messages,
                            model_id=candidate.model_id,
                            temperature=request.temperature,
                            max_tokens=request.max_tokens,
                            system_prompt=model_system,
                            metadata=request.metadata,
                        )
                        task = asyncio.create_task(provider_inst.generate(model_request))
                        tasks_list.append((candidate, task))

                    # Gather with timeout (15s per model)
                    for candidate, task in tasks_list:
                        try:
                            resp = await asyncio.wait_for(task, timeout=15.0)
                            council_responses.append((
                                candidate.model_id,
                                candidate.provider.value,
                                resp.content,
                            ))
                            council_models_used.append(candidate.model_id)
                        except (TimeoutError, Exception) as exc:
                            logger.warning(
                                "orchestrator.council_member_failed",
                                model=candidate.model_id,
                                error=str(exc),
                        )

                if not council_responses:
                    raise RuntimeError("All council models failed to respond")

                # If only 1 response, skip synthesis, use directly
                if len(council_responses) == 1:
                    collected_content = council_responses[0][2]
                    model_id = council_responses[0][0]
                    provider_name = council_responses[0][1]
                else:
                    # Synthesis: send all responses to primary model for merge
                    synthesis_parts = []
                    for i, (mid, _prov, content) in enumerate(council_responses, 1):
                        label = f"Model {i} ({mid})"
                        if i <= len(dcp_experts_used):
                            label += f" [{dcp_experts_used[i - 1]}]"
                        synthesis_parts.append(f"=== {label} ===\n{content}")

                    mode_label = decision.mode.value.lower()
                    synthesis_instruction = (
                        "You received independent analyses from multiple models"
                        + (" with different expert perspectives" if dcp_experts_used else "")
                        + f". Synthesize the best answer as the {mode_label} synthesis. "
                        "Note where they agree and where they diverge. "
                        "Produce a single coherent response that captures the strongest "
                        "insights from each. Do not list the models; speak as one voice."
                    )

                    synthesis_messages = [
                        LLMMessage(role="user", content=user_content),
                        LLMMessage(
                            role="assistant",
                            content="\n\n".join(synthesis_parts),
                        ),
                        LLMMessage(
                            role="user",
                            content=synthesis_instruction,
                        ),
                    ]

                    synthesis_request = GenerateRequest(
                        messages=synthesis_messages,
                        model_id=decision.primary.model_id,
                        temperature=0.5,
                        max_tokens=2048,
                        system_prompt=system_prompt,
                        metadata={"stage": "council_synthesis"},
                    )

                    # Stream the synthesis response
                    async for chunk in llm.stream(synthesis_request, decision):
                        collected_content += chunk.content
                        token_count += 1
                        yield {"type": "chunk", "content": chunk.content}

                yield {
                    "type": "thinking",
                    "stage": "council_completed",
                    "model": model_id,
                    "source": decision.mode.value,
                    "reason": decision.metadata.get("selection_reason"),
                    "responses": len(council_responses),
                    "models_used": council_models_used,
                    "experts_used": dcp_experts_used,
                }

                # If only 1 response (no synthesis stream), yield as chunks
                if len(council_responses) == 1:
                    chunk_size = 12
                    for i in range(0, len(collected_content), chunk_size):
                        yield {
                            "type": "chunk",
                            "content": collected_content[i:i + chunk_size],
                        }

            except Exception as exc:
                logger.error(
                    "orchestrator.council_failed",
                    error=str(exc),
                    mode=decision.mode.value,
                )
                # Fall back to direct streaming
                yield {"type": "thinking", "stage": "fallback_streaming"}
                async for chunk in self._fallback_stream(request):
                    collected_content += chunk.content
                    token_count += 1
                    yield {"type": "chunk", "content": chunk.content}
        else:
            # Standard streaming
            try:
                async for chunk in llm.stream(request, decision):
                    collected_content += chunk.content
                    token_count += 1
                    event: dict = {"type": "chunk", "content": chunk.content}
                    if chunk.model_id and chunk.model_id != model_id:
                        model_id = chunk.model_id
                        event["model_id"] = model_id
                    if chunk.provider and chunk.provider.value != provider_name:
                        provider_name = chunk.provider.value
                    yield event
            except Exception as exc:
                logger.error(
                    "orchestrator.stream_failed",
                    error=str(exc),
                    model=model_id,
                )
                # Try fallback to direct Ollama
                if not collected_content:
                    yield {"type": "thinking", "stage": "fallback_streaming"}
                    try:
                        async for chunk in self._fallback_stream(request):
                            collected_content += chunk.content
                            token_count += 1
                            yield {"type": "chunk", "content": chunk.content}
                        provider_name = "ollama"
                        model_id = chunk.model_id if chunk else model_id
                    except Exception as fallback_exc:
                        # Demo mode: return mock response instead of error
                        from app.services.demo_mode import is_demo_mode, mock_llm_response
                        if is_demo_mode():
                            mock_content = mock_llm_response(user_content)
                            collected_content = mock_content
                            provider_name = "demo"
                            model_id = "demo-mock"
                            yield {"type": "chunk", "content": mock_content}
                        else:
                            error_msg = ChatMessage(
                                session_id=session_id,
                                role="ASSISTANT",
                                content=(
                                    "I'm sorry, I couldn't generate a response. "
                                    "Please check that your LLM providers are configured correctly."
                                ),
                            )
                            self._db.add(error_msg)
                            await self._db.flush()
                            yield {
                                "type": "error",
                                "message": str(fallback_exc),
                                "data": ChatService._message_to_dict(error_msg),
                            }
                            return

        if not collected_content:
            yield {"type": "error", "message": "No content generated."}
            return

        # ── Stage 9: Persist assistant message ────────────────
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        assistant_msg = ChatMessage(
            session_id=session_id,
            role="ASSISTANT",
            content=collected_content,
            model_used=model_id,
            provider_used=provider_name,
            governance_tier=governance_tier,
            cost_usd=0.0,  # Updated in stage 10
            latency_ms=latency_ms,
        )
        self._db.add(assistant_msg)
        await self._db.flush()

        # Slop scoring (non-blocking, audit only)
        try:
            from app.config.stop_slop import score_content, scan_slop
            slop_score = score_content(collected_content)
            slop_matches = scan_slop(collected_content)
            logger.info(
                "stop_slop.scored",
                session_id=str(session_id),
                score=slop_score.total,
                passes=slop_score.passes,
                match_count=len(slop_matches),
            )
        except Exception:
            slop_score = None

        # Auto-title if needed
        title = await self._chat._auto_title_if_needed(session_id)
        done_data = ChatService._message_to_dict(assistant_msg)
        if title:
            done_data["_session_title"] = title
        if slop_score:
            done_data["_slop_score"] = slop_score.to_dict()
        yield {"type": "done", "data": done_data}

        # ── Stage 10: Record cost + audit ─────────────────────
        _tokens_input = len(llm_messages) * 100  # estimate: ~100 tokens per message
        _tokens_output = token_count or len(collected_content) // 4
        _estimated_cost = self._estimate_cost(model_id, _tokens_input, _tokens_output)

        try:
            await cost_guard.record_usage(
                tenant_id=tenant_id,
                user_id=user_id,
                provider=provider_name,
                model_name=model_id,
                tokens_input=_tokens_input,
                tokens_output=_tokens_output,
                cost_usd=_estimated_cost,
                session_id=session_id,
            )
        except Exception:
            logger.debug("orchestrator.cost_record_failed", exc_info=True)

        try:
            from app.services.billing.cost_tracker import UnifiedCostTracker

            UnifiedCostTracker.get_instance().log_usage(
                provider=provider_name,
                model=model_id,
                input_tokens=_tokens_input,
                output_tokens=_tokens_output,
                cost_usd=_estimated_cost,
                task_type="chat",
                session_id=str(session_id),
            )
        except Exception:
            logger.debug("orchestrator.cost_tracker_failed", exc_info=True)

        try:
            from app.services.audit import AuditService

            audit = AuditService(self._db)
            await audit.log_decision(
                tenant_id=tenant_id,
                actor_id=user_id,
                actor_type="USER",
                action_type="LLM_CALL",
                action_params={
                    "model": model_id,
                    "provider": provider_name,
                    "intent": qu_result.intent.value,
                    "requested_routing_mode": requested_routing_mode.value,
                    "applied_routing_mode": decision.mode.value,
                    "routing_source": routing_source,
                    "selection_reason": decision.metadata.get("selection_reason"),
                    "mode_reason": decision.metadata.get("mode_reason"),
                    "provider_strategy": decision.metadata.get("provider_strategy"),
                    "providers_considered": decision.metadata.get("providers_considered"),
                    "top_candidates": decision.metadata.get("top_candidates"),
                    "user_message": user_content[:100] if user_content else "",
                    "latency_ms": latency_ms,
                },
                result="COMPLETED",
                risk_level=qu_result.risk_level.value,
                governance_tier=governance_tier,
                session_id=session_id,
            )
        except Exception:
            logger.debug("orchestrator.audit_failed", exc_info=True)

        # ── Stage 10.1: TLM turn tick (advance idle counters) ────
        try:
            from app.services.tool_lifecycle.orchestra_integration import tick_conversation_turn
            tlm_tick = tick_conversation_turn(str(session_id))
            if tlm_tick.get("deactivated"):
                logger.info(
                    "orchestrator.tlm_deactivated",
                    deactivated=tlm_tick["deactivated"],
                    active_count=tlm_tick["active_count"],
                )
        except Exception:
            pass  # TLM is non-critical

        # ── Stage 10.5: Memory writeback (via background task) ────
        # Yield a _memory_writeback event with all needed data.
        # The chat endpoint catches this event and runs the write
        # in a BackgroundTask with a FRESH DB session, because the
        # SSE generator's session is already closed by get_db().
        if len(collected_content) > 50 and len(user_content) > 20:
            yield {
                "type": "_memory_writeback",
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
                "session_id": str(session_id),
                "user_content": user_content[:500],
                "collected_content": collected_content[:1000],
                "intent": qu_result.intent.value,
                "complexity": qu_result.complexity_label.value,
                "routing": routing_mode.value,
                "model": model_id or "auto",
                "provider": provider_name,
                "governance_tier": governance_tier,
                "latency_ms": latency_ms,
                "skill_count": skill_count,
            }

    # ── Helpers ───────────────────────────────────────────────

    def _resolve_override_candidate(self, model_id: str) -> tuple[Any | None, str]:
        """Validate a requested model against the live registry."""
        from app.core.constants import HealthStatus
        from app.services.model_router import ModelCandidate

        info = self._registry.get_model_info(model_id) if self._registry else None
        if info is None:
            return None, "model_not_present_in_live_registry"

        health = self._registry.get_health(info.provider)
        if health == HealthStatus.UNAVAILABLE:
            return None, f"provider_{health.value.lower()}"

        return ModelCandidate(
            model_id=info.model_id,
            provider=info.provider,
            score=1.0,
            cost_per_1m_input=info.cost_per_1m_input,
            cost_per_1m_output=info.cost_per_1m_output,
            context_window=info.context_window,
            tags=list(info.tags) if info.tags else [],
            diagnostics={
                "provider_health": health.value,
                "override_validated": True,
            },
        ), "validated"

    def _resolve_provider_for_model(self, model_id: str) -> Any:
        """Best-effort guess: which provider owns this model_id.

        Checks registry first, falls back to Ollama for local models.
        """
        from app.core.constants import ModelProvider

        # Check if registry knows this model
        if self._registry and hasattr(self._registry, '_model_cache'):
            info = self._registry._model_cache.get(model_id)
            if info:
                return info.provider

        # Heuristic: known prefixes
        model_lower = model_id.lower()
        if any(p in model_lower for p in ("claude", "anthropic")):
            return ModelProvider.ANTHROPIC
        if any(p in model_lower for p in ("gpt", "o1", "o3")):
            return ModelProvider.OPENAI
        if any(p in model_lower for p in ("gemini", "palm")):
            return ModelProvider.GEMINI
        if "groq" in model_lower or "mixtral" in model_lower:
            return ModelProvider.GROQ

        # Default: Ollama (local models like deepseek-r1, llama3, etc.)
        return ModelProvider.OLLAMA

    async def _fallback_stream(self, request: GenerateRequest) -> AsyncIterator[Any]:
        """Fallback: stream directly from OllamaProvider (MVP path)."""
        from app.services.providers.ollama import OllamaProvider

        provider = OllamaProvider()
        try:
            async for chunk in provider.stream(request):
                yield chunk
        finally:
            await provider.close()
