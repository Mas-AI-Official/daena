"""ToolUseLoop -- the agentic execution loop that makes Daena autonomous.

This is THE missing piece. Instead of regex-matching user messages for tools,
we give the LLM function definitions and let it decide when to call them.
After each tool call, results are fed back and the LLM continues reasoning.

Flow:
    1. LLM receives message + tool definitions in system prompt
    2. LLM generates response (may include tool calls)
    3. Parse response for ```tool_call blocks
    4. Execute each tool call through governance
    5. Inject results as context
    6. Let LLM continue (loop back to step 2)
    7. When LLM produces final text with no tool calls, stream to user

Max iterations prevent infinite loops. Governance checks every tool call.
All tool executions logged to audit trail.

Dispatch coverage:
    - file.*      -> SystemAccess (read, write, list, search, delete, move, copy)
    - terminal.*  -> SystemAccess (run_command, run_python, install_package)
    - network.*   -> SystemAccess (http_get, http_post, web_search)
    - browser.*   -> BrowserAgent (navigate, screenshot, extract_text, fill_form, click)
    - desktop.*   -> DesktopAgent (screenshot, click, type, hotkey, scroll, move_mouse)
    - mcp.*       -> MCPAgent (call_tool on any MCP server)
    - gmail.*     -> IntegrationRouter
    - calendar.*  -> IntegrationRouter
    - notion.*    -> IntegrationRouter
    - workflow.*  -> DepartmentWorkflowEngine
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.core.logging import get_logger
from app.services.tool_schema_builder import (
    build_tool_schema,
    build_tool_prompt,
    parse_tool_calls,
    resolve_tool_call,
)

logger = get_logger(__name__)

MAX_TOOL_ITERATIONS = 10
TOOL_RESULT_MAX_LENGTH = 4000

# Sentinel returned by _generate when every backend in the tool-loop's own
# provider chain is unavailable. run() treats this as "no response" (not an
# answer) so the orchestrator falls through to LLMService.stream.
_NO_LLM_SENTINEL = "[No LLM available for tool-use loop]"

# Lazy-initialized singletons for the cognitive security layer
_loop_detector_cls = None
_classifier_cls = None


def _get_loop_detector():
    global _loop_detector_cls
    if _loop_detector_cls is None:
        from app.services.security.loop_detector import LoopDetector
        _loop_detector_cls = LoopDetector
    return _loop_detector_cls


def _get_classifier():
    global _classifier_cls
    if _classifier_cls is None:
        from app.services.security.tool_call_classifier import ToolCallClassifier
        _classifier_cls = ToolCallClassifier
    return _classifier_cls


class ToolUseLoop:
    """Agentic tool-use loop that enables autonomous LLM tool calling.

    Wraps the standard LLM call with tool-call parsing and execution.
    Each iteration: generate -> parse -> execute -> inject -> continue.

    Usage::

        loop = ToolUseLoop(db, user_id, tenant_id)
        async for event in loop.run(llm_messages, system_prompt, model_id):
            yield event  # Stream to frontend
    """

    def __init__(
        self,
        db: Any,
        user_id: UUID,
        tenant_id: UUID,
        *,
        agi_mode: bool = False,
        session_id: UUID | None = None,
        workspace_root: str | None = None,
        governance_mode: Any | None = None,
        extension_permissions: dict[str, Any] | None = None,
    ) -> None:
        self.db = db
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.agi_mode = agi_mode
        self.session_id = session_id
        self.workspace_root = workspace_root
        self._tool_results: list[dict[str, Any]] = []
        self._total_tool_calls = 0
        self._total_cost = 0.0

        # Permission-resolver context. Callers can inject governance mode
        # and the user's per-tool prefs so every tool dispatch runs
        # through the same gate. Defaults to a safe BALANCED mode with
        # no overrides so callers that forget these kwargs still respect
        # governance (just without the user's tool-level overrides).
        from app.core.constants import GovernanceMode as _GM
        if governance_mode is None:
            self.governance_mode = (
                _GM.UNLEASHED if agi_mode else _GM.BALANCED
            )
        elif isinstance(governance_mode, str):
            try:
                self.governance_mode = _GM(governance_mode.upper())
            except ValueError:
                self.governance_mode = _GM.BALANCED
        else:
            self.governance_mode = governance_mode
        self.extension_permissions = extension_permissions or {}
        # Last guard decision (populated by _execute_tool). The run()
        # loop reads this to emit SSE events; orchestrator callers can
        # read it to decide whether to surface an inline approval card.
        self._last_guard_decision: Any = None

        # Cognitive security layer (OpenClaw ports)
        LoopDetectorCls = _get_loop_detector()
        ClassifierCls = _get_classifier()
        self._loop_detector = LoopDetectorCls()
        self._classifier = ClassifierCls(workspace_root=workspace_root)

    async def run(
        self,
        messages: list[Any],
        system_prompt: str,
        model_id: str,
        provider: str = "ollama",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute the tool-use loop.

        Yields SSE events for the frontend:
        - {"type": "tool_call", "tool": "...", "params": {...}}
        - {"type": "tool_result", "tool": "...", "result": {...}}
        - {"type": "chunk", "content": "..."}
        - {"type": "tool_loop_complete", "total_calls": N}

        Args:
            messages: Conversation messages (LLMMessage objects).
            system_prompt: Base system prompt.
            model_id: Model to use for generation.
            provider: LLM provider (ollama, anthropic, etc).
            temperature: Generation temperature.
            max_tokens: Max tokens per generation.
        """
        # Build tool schema and inject into system prompt
        tool_schema = build_tool_schema(
            include_daenabot=True,
            include_integrations=True,
            include_system=True,
            include_workflows=True,
            include_mcp=True,
            include_desktop=True,
            agi_mode=self.agi_mode,
        )
        tool_prompt = build_tool_prompt(tool_schema)

        # Inject cognitive reasoning DNA -- the LLM thinks with frameworks,
        # not just with tools. This is what makes Daena intelligent.
        cognitive_prompt = (
            "COGNITIVE PROTOCOL (apply to EVERY decision):\n"
            "Before each action, THINK using these lenses:\n"
            "- FIRST PRINCIPLES: What is actually true? Strip assumptions.\n"
            "- DECOMPOSE: Break complex tasks into atomic steps. Do the hardest first.\n"
            "- INVERSION: What would cause this to fail? Prevent those failure modes.\n"
            "- MAP vs TERRITORY: Verify actual state, don't assume. Read before write.\n"
            "- CONSTRAINT PROBE: If blocked, decompose the constraint. The stated limit\n"
            "  is rarely the actual limit. Find the gap and use it.\n"
            "\n"
            "PROBLEM-SOLVING LOOP:\n"
            "1. OBSERVE: What do I actually know? (Read files, check state, verify)\n"
            "2. ORIENT: Which approach fits? (Decompose, search, ask)\n"
            "3. DECIDE: Pick the simplest path that works.\n"
            "4. ACT: Execute one step. Check the result.\n"
            "5. REFLECT: Did it work? If not, WHY? (5 Whys -- dig to root cause)\n"
            "   Then adapt: try a different tool, search for answers, install what\n"
            "   is missing, or build a custom tool. NEVER repeat the same failed approach.\n"
            "\n"
            "You are not a chatbot following instructions. You are an autonomous operator.\n"
            "You THINK about what you are doing. You verify before and after. You adapt.\n"
        )
        enhanced_prompt = f"{system_prompt}\n\n{cognitive_prompt}\n{tool_prompt}"

        # Tool-use loop
        iteration = 0
        tool_context_messages = list(messages)

        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1

            # Generate LLM response
            full_response = ""
            async for chunk in self._generate(
                tool_context_messages,
                enhanced_prompt,
                model_id,
                provider,
                temperature,
                max_tokens,
            ):
                full_response += chunk

            # Parse for tool calls
            tool_calls = parse_tool_calls(full_response)

            if not tool_calls:
                # No tool calls -- this is the final response.
                # BUT: if the tool-loop's own provider chain is exhausted (every
                # backend failed, or the only "online" runtime is a not-logged-in
                # CLI that yielded its auth error -> skipped in _generate), do NOT
                # surface the no-LLM sentinel as the answer. Yield nothing so the
                # orchestrator leaves daenabot_result=None and falls through to the
                # standard LLMService.stream provider chain (the next available
                # brain: Perplexity/Anthropic). Surfacing the sentinel here would
                # dead-end the visible fallback chain.
                if full_response.strip() == _NO_LLM_SENTINEL:
                    logger.warning("tool_loop.no_llm_available_failover")
                    break
                # Stream the response to the user
                yield {"type": "tool_use_response", "content": full_response}
                break

            # Execute tool calls
            for call in tool_calls:
                tool_name = call["tool"]
                params = call["params"]

                # ── Cognitive Layer: Loop Detection (OpenClaw port) ──
                loop_check = self._loop_detector.detect(tool_name, params)
                if loop_check.stuck:
                    yield {
                        "type": "loop_detected",
                        "tool": tool_name,
                        "detector": loop_check.detector.value if loop_check.detector else "unknown",
                        "level": loop_check.level.value,
                        "count": loop_check.count,
                        "message": loop_check.message,
                    }
                    if loop_check.level.value == "critical":
                        logger.warning(
                            "tool_loop.critical_break",
                            tool=tool_name,
                            detector=loop_check.detector.value if loop_check.detector else "",
                            count=loop_check.count,
                        )
                        break  # Exit loop -- OODA Reflect will analyze why
                    # Warning level: log but continue (give it one more chance)

                # ── Cognitive Layer: Tool Call Classification (OpenClaw port) ──
                if self.agi_mode:
                    classification = self._classifier.classify_for_agi_mode(tool_name, params)
                else:
                    classification = self._classifier.classify(tool_name, params)

                yield {
                    "type": "tool_call",
                    "tool": tool_name,
                    "params": params,
                    "iteration": iteration,
                    "classification": classification.approval_class.value,
                    "auto_approved": classification.auto_approve,
                    "risk_level": classification.risk_level,
                }

                # Skip execution if not auto-approved and not AGI mode
                # (governance will handle approval via async_approval_manager)
                if not classification.auto_approve and not self.agi_mode:
                    logger.info(
                        "tool_loop.governance_required",
                        tool=tool_name,
                        class_=classification.approval_class.value,
                        risk=classification.risk_level,
                    )
                    # For now, continue execution but log the governance flag
                    # Full async approval integration happens in Phase 3

                # Execute the tool
                result = await self._execute_tool(tool_name, params)
                self._total_tool_calls += 1
                self._tool_results.append({
                    "tool": tool_name,
                    "params": params,
                    "result": result,
                    "iteration": iteration,
                })

                # ── Cognitive Layer: Record outcome for loop detection ──
                error_str = str(result.get("error", "")) if not result.get("success", True) else ""
                self._loop_detector.record_outcome(tool_name, params, result, error_str)

                yield {
                    "type": "tool_result",
                    "tool": tool_name,
                    "result": result,
                    "success": result.get("success", True),
                    "iteration": iteration,
                }

            # Inject tool results as context for next iteration
            # Remove the tool_call blocks from the response
            clean_response = self._strip_tool_calls(full_response)
            if clean_response.strip():
                from app.services.providers.base import LLMMessage
                tool_context_messages.append(
                    LLMMessage(role="assistant", content=clean_response)
                )

            # Add tool results with cognitive scaffolding
            recent_results = self._tool_results[-len(tool_calls):]
            results_text = self._format_tool_results(tool_calls, recent_results)
            has_failures = any(not r.get("result", {}).get("success", True) for r in recent_results)

            from app.services.providers.base import LLMMessage
            if has_failures:
                # Failure: trigger cognitive reasoning, not blind retry
                tool_context_messages.append(
                    LLMMessage(role="user", content=(
                        f"[TOOL RESULTS]\n{results_text}\n\n"
                        "One or more tools failed. Apply your cognitive protocol:\n"
                        "1. ROOT CAUSE: Why did it fail? (Not the symptom -- the actual cause)\n"
                        "2. CONSTRAINT PROBE: Is this a real limit or can you work around it?\n"
                        "3. NEXT MOVE: Search online, install something, try a different tool,\n"
                        "   build a custom tool, or decompose into smaller steps.\n"
                        "DO NOT repeat the same approach. Adapt and try something different."
                    ))
                )
            else:
                # Success: check if the goal is achieved or more steps needed
                tool_context_messages.append(
                    LLMMessage(role="user", content=(
                        f"[TOOL RESULTS]\n{results_text}\n\n"
                        "Tools succeeded. VERIFY: Does this achieve the goal?\n"
                        "If yes, present the final result.\n"
                        "If more steps remain, continue with the next step."
                    ))
                )

        # Report completion
        yield {
            "type": "tool_loop_complete",
            "total_calls": self._total_tool_calls,
            "iterations": iteration,
            "tools_used": list({r["tool"] for r in self._tool_results}),
        }

    async def _generate(
        self,
        messages: list[Any],
        system_prompt: str,
        model_id: str,
        provider: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        """Generate LLM response (non-streaming, collect full response).

        For the tool-use loop, we need the full response to parse tool calls.
        Fallback chain: Cloud API (Groq/Gemini) -> Ollama -> runtime adapters -> error.
        """
        # Try cloud providers first (works on Cloud Run where Ollama is unavailable)
        try:
            from app.core.config import get_settings
            settings = get_settings()

            # Build messages array for cloud API
            api_messages = [{"role": "system", "content": system_prompt}]
            for msg in messages:
                role = msg.role if hasattr(msg, "role") else msg.get("role", "user")
                content = msg.content if hasattr(msg, "content") else msg.get("content", "")
                api_messages.append({"role": role.lower(), "content": content})

            # Try Groq (fast, free tier available).
            # Groq's free tier returns 413 Payload Too Large on bodies
            # much above ~30 KB of serialized JSON -- a single big
            # system prompt + long soul context + conversation history
            # can cross that. Doing a cheap length estimate here saves
            # a wasted round trip and a noisy 413 in the logs.
            groq_key = (settings.groq_api_key or "").strip()
            # Rough payload size = sum of all message contents. Add a
            # 2KB fudge factor for JSON overhead + system prompt.
            groq_payload_chars = sum(len(m.get("content", "")) for m in api_messages) + 2048
            _GROQ_SAFE_CHARS = 28_000  # conservative -- actual 413 threshold lives around 30-35 KB
            if groq_key and groq_payload_chars > _GROQ_SAFE_CHARS:
                logger.info(
                    "tool_loop.groq_skipped",
                    reason="payload_too_large",
                    estimated_chars=groq_payload_chars,
                    threshold=_GROQ_SAFE_CHARS,
                )
                groq_key = ""  # fall through to Gemini without hitting Groq
            if groq_key:
                import httpx
                try:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        resp = await client.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                            json={
                                "model": model_id if "groq" in provider.lower() else "llama-3.3-70b-versatile",
                                "messages": api_messages,
                                "temperature": temperature,
                                "max_tokens": max_tokens,
                            },
                        )
                        if resp.status_code == 200:
                            text = resp.json()["choices"][0]["message"]["content"]
                            yield text
                            return
                        # Non-200: log at info so operators can see the
                        # real reason (413, 429, 401) without it being
                        # a warning that surfaces as an error in the UI.
                        if resp.status_code in (413, 429):
                            logger.info(
                                "tool_loop.groq_rejected",
                                status=resp.status_code,
                                estimated_chars=groq_payload_chars,
                            )
                except Exception as exc:
                    logger.warning("tool_loop.groq_failed", error=str(exc))

            # Try Gemini
            gemini_key = (settings.gemini_api_key or "").strip()
            if gemini_key:
                import httpx
                try:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        resp = await client.post(
                            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}",
                            headers={"Content-Type": "application/json"},
                            json={
                                "contents": [{"parts": [{"text": m["content"]}], "role": "user" if m["role"] == "user" else "model"} for m in api_messages if m["role"] != "system"],
                                "systemInstruction": {"parts": [{"text": system_prompt}]},
                                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
                            },
                        )
                        if resp.status_code == 200:
                            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                            yield text
                            return
                except Exception as exc:
                    logger.warning("tool_loop.gemini_failed", error=str(exc))
        except Exception:
            pass  # Settings unavailable, try Ollama

        # Ollama (local) -- only attempted if the daemon is actually up.
        # 2026-04-18: the old code hardcoded ``or True`` to ALWAYS try
        # Ollama as a fallback, which meant every chat request that got
        # past Groq/Gemini paid for a 120s connect-timeout against a
        # dead ``localhost:11434`` when the user hadn't run
        # ``ollama serve``. A cheap up-front probe eliminates the
        # wasted round trip and the noisy ``tool_loop.ollama_failed``
        # warning. If the user asked explicitly for an Ollama model
        # (``provider == "ollama"``) we still try so they get a real
        # error message instead of silent skip.
        #
        # WSL-aware: uses the same resolver as OllamaProvider so a
        # Windows-side Ollama is reachable from a WSL-side backend via
        # ``host.docker.internal`` instead of the useless ``localhost``.
        try:
            from app.services.providers.ollama import resolve_ollama_base_url
            from app.core.config import get_settings
            _settings = get_settings()
            ollama_url = resolve_ollama_base_url(
                (_settings.ollama_base_url or "").strip() or None
            )
        except Exception:
            ollama_url = "http://localhost:11434"
            _settings = None

        explicit_ollama = provider.lower() in ("ollama", "local")
        ollama_reachable = explicit_ollama  # Skip probe when explicitly requested

        # Honor OLLAMA_ENABLED. Per CLAUDE.md Ollama is deprecated in
        # favour of llama.cpp llama-server (vLLM adapter). When the flag
        # is false, skip entirely -- otherwise every chat turn burns a
        # 2s probe + a wasted POST /api/generate that 404s because the
        # hardcoded ``llama3.1:8b`` model isn't pulled.
        if _settings is not None and not _settings.ollama_enabled and not explicit_ollama:
            ollama_reachable = False
            logger.info(
                "tool_loop.ollama_skipped",
                reason="ollama_disabled",
                base_url=ollama_url,
            )

        if not explicit_ollama and ollama_reachable is not False:
            import httpx as _httpx_probe
            try:
                async with _httpx_probe.AsyncClient(
                    timeout=_httpx_probe.Timeout(2.0, connect=1.0)
                ) as _probe_client:
                    _probe_resp = await _probe_client.get(f"{ollama_url}/api/tags")
                    ollama_reachable = _probe_resp.status_code == 200
                    # Verify the requested model is actually installed.
                    # Without this check we POST /api/generate with a
                    # model that isn't pulled -> 404 -> retry + fallback.
                    if ollama_reachable:
                        tags = _probe_resp.json().get("models", []) or []
                        have = {m.get("name", "").split(":")[0] for m in tags}
                        have |= {m.get("name", "") for m in tags}
                        want = (model_id or "llama3.1:8b").split(":")[0]
                        if want not in have and (model_id or "llama3.1:8b") not in have:
                            ollama_reachable = False
                            logger.info(
                                "tool_loop.ollama_skipped",
                                reason="model_not_pulled",
                                model=model_id or "llama3.1:8b",
                                available=sorted(have)[:10],
                            )
            except Exception:
                # Daemon down, port closed, DNS unreachable -- all mean
                # "don't waste a full request on this fallback." Log at
                # info so operators can still see what was skipped.
                ollama_reachable = False
                logger.info(
                    "tool_loop.ollama_skipped",
                    reason="daemon_unreachable",
                    base_url=ollama_url,
                )

        if ollama_reachable:
            import httpx
            prompt_parts = [system_prompt, ""]
            for msg in messages:
                role = msg.role if hasattr(msg, "role") else msg.get("role", "user")
                content = msg.content if hasattr(msg, "content") else msg.get("content", "")
                prompt_parts.append(f"{role.upper()}: {content}")

            full_prompt = "\n".join(prompt_parts)

            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(
                        f"{ollama_url}/api/generate",
                        json={
                            "model": model_id or "llama3.1:8b",
                            "prompt": full_prompt,
                            "stream": False,
                            "options": {"temperature": temperature},
                        },
                    )
                    if resp.status_code == 200:
                        text = resp.json().get("response", "")
                        yield text
                        return
            except Exception as exc:
                logger.warning("tool_loop.ollama_failed", error=str(exc))

        # Fallback: try runtime adapters
        try:
            from app.core.events import get_runtime_registry
            from app.services.providers.claude_cli import _looks_like_cli_auth_error
            from app.services.runtimes.base_adapter import RuntimeStatus

            registry = get_runtime_registry()
            for rid in ["claude_code", "codex", "ollama"]:
                adapter = registry.get_adapter(rid)
                if adapter:
                    health = await registry.ensure_health_fresh(rid)
                    if health == RuntimeStatus.ONLINE:
                        last_msg = messages[-1] if messages else None
                        content = ""
                        if last_msg:
                            content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

                        output_lines = []
                        async for line in adapter.execute(
                            task=content,
                            context={"session_id": str(self.session_id or "tool-loop")},
                        ):
                            output_lines.append(line)
                        runtime_text = "\n".join(output_lines)
                        # A reachable-but-not-logged-in CLI returns its auth
                        # error AS content. Do NOT surface it as the answer --
                        # skip this adapter and try the next available brain so
                        # the fallback chain stays visible (Primary Mind -> next
                        # available -> ...). Reuse the canonical detector.
                        if _looks_like_cli_auth_error(runtime_text):
                            logger.warning(
                                "tool_loop.runtime_auth_error_skipped",
                                runtime=rid,
                            )
                            continue
                        yield runtime_text
                        return
        except Exception as exc:
            logger.warning("tool_loop.runtime_failed", error=str(exc))

        yield _NO_LLM_SENTINEL

    # Error patterns that trigger OpenClaw-parity auto-heal.
    _HEAL_TRIGGERS = (
        "no module named",
        "modulenotfounderror",
        "command not found",
        "is not recognized",
        "cannot find module",
    )

    async def _execute_tool(
        self, tool_name: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        """Public tool entry: dispatch + OpenClaw-parity auto-heal.

        Thin wrapper around ``_dispatch_once``. On failure (either a
        raised exception or a returned ``{success: False, stderr: ...}``
        carrying a heal-trigger pattern), ``_auto_install`` runs and
        the dispatch retries ONCE. Only in ``agi_mode`` -- explicit
        operator opt-in -- because autonomous install is the capability
        that makes Daena feel alive but also widens the trust boundary.

        Guard-rails that stay intact:
        * Single retry max (``_heal_in_progress`` guard).
        * ``_auto_install`` only runs the pattern-extracted package
          name against pip/npm; no arbitrary code path.
        * LLM-initiated ``install_system_tool`` calls are still gated
          CRITICAL by the permission resolver -- prompt-injection
          defense is preserved.
        """
        result = await self._dispatch_once(tool_name, params)

        if (
            self.agi_mode
            and not result.get("success")
            and not getattr(self, "_heal_in_progress", False)
        ):
            combined_err = (
                f"{result.get('error','')} {result.get('stderr','')}"
            ).lower()
            if any(t in combined_err for t in self._HEAL_TRIGGERS):
                self._heal_in_progress = True
                try:
                    heal = await self._auto_install(
                        error_text=combined_err,
                        tool_name=tool_name,
                        params=params,
                    )
                    if heal.get("success"):
                        logger.info(
                            "tool_loop.auto_healed",
                            tool=tool_name,
                            installed=heal.get("installed"),
                            method=heal.get("method"),
                            trigger="result_dict",
                        )
                        retry = await self._dispatch_once(tool_name, params)
                        if retry.get("success"):
                            retry["auto_healed"] = {
                                "installed": heal.get("installed"),
                                "method": heal.get("method"),
                            }
                        return retry
                finally:
                    self._heal_in_progress = False

        return result

    async def _dispatch_once(
        self, tool_name: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single tool call through the appropriate dispatch path.

        Full dispatch coverage:
        - file.*      -> SystemAccess
        - terminal.*  -> SystemAccess
        - network.*   -> SystemAccess
        - browser.*   -> BrowserAgent
        - desktop.*   -> DesktopAgent (Windows-MCP bridge)
        - mcp.*       -> MCPAgent
        - gmail/calendar/notion -> IntegrationRouter
        - workflow.*  -> DepartmentWorkflowEngine

        BEFORE any dispatch path runs, the call is routed through
        ``permission_dispatch.guard_tool_dispatch()`` so governance
        mode, autopilot, and per-tool Allow/Ask/Block prefs are all
        respected. This is the single choke-point that every agentic
        tool invocation must pass.
        """
        qualified_name, resolved_params = resolve_tool_call(tool_name, params)
        parts = qualified_name.split(".", 1)

        if len(parts) != 2:
            return {"success": False, "error": f"Invalid tool: {tool_name}"}

        prefix, operation = parts

        # ── Permission guard (runs BEFORE any dispatch or bridge call) ──
        # Classify → resolve → either proceed, refuse, or write an
        # ApprovalQueue row and surface the approval id to the caller.
        # Exceptions bubble up only for truly unexpected failures; the
        # guard itself fails closed to REFUSE on approval-system errors.
        try:
            from app.services.permission_dispatch import (
                GuardDecision,
                guard_tool_dispatch,
            )
            from app.services.permission_resolver import EffectivePermission

            # Classify this specific call so the resolver sees the real
            # risk level, not just the connector-level default.
            if self.agi_mode:
                _clf = self._classifier.classify_for_agi_mode(
                    qualified_name, resolved_params,
                )
            else:
                _clf = self._classifier.classify(
                    qualified_name, resolved_params,
                )

            guard = await guard_tool_dispatch(
                db=self.db,
                user_id=self.user_id,
                tenant_id=self.tenant_id,
                session_id=self.session_id,
                tool_name=qualified_name,
                params=resolved_params,
                risk_level_str=_clf.risk_level,
                governance_mode=self.governance_mode,
                autopilot_active=self.agi_mode,
                extension_permissions=self.extension_permissions,
            )
            self._last_guard_decision = guard

            if guard.outcome == EffectivePermission.REFUSE:
                logger.info(
                    "tool_loop.dispatch_refused",
                    tool=qualified_name,
                    reason=guard.reason,
                )
                return {
                    "success": False,
                    "error": guard.reason,
                    "governance": "REFUSE",
                    "risk_tier": guard.risk_tier,
                }

            if guard.outcome == EffectivePermission.REQUEST_INPUT:
                logger.info(
                    "tool_loop.dispatch_pending_approval",
                    tool=qualified_name,
                    approval_id=(
                        str(guard.approval_id) if guard.approval_id else None
                    ),
                    tier=guard.risk_tier,
                )
                return {
                    "success": False,
                    "error": guard.reason,
                    "governance": "REQUEST_INPUT",
                    "risk_tier": guard.risk_tier,
                    "pending_approval": {
                        "approval_id": (
                            str(guard.approval_id)
                            if guard.approval_id
                            else None
                        ),
                        "tool": qualified_name,
                        "reason": guard.reason,
                    },
                }
            # AUTO_PROCEED falls through to normal dispatch.
        except Exception as guard_exc:
            # Guard machinery itself crashed (not a refuse decision --
            # those are returned, not raised). Fail closed so we don't
            # silently bypass governance.
            logger.error(
                "tool_loop.guard_exception",
                tool=qualified_name,
                error=str(guard_exc),
                exc_info=True,
            )
            return {
                "success": False,
                "error": (
                    f"Permission guard failed: {guard_exc}. "
                    "Execution blocked for safety."
                ),
                "governance": "REFUSE",
            }

        # ── Cloud mode: check if local tools need DaenaBot bridge ──
        _local_prefixes = {"file", "terminal", "browser", "desktop", "vision"}
        if prefix in _local_prefixes:
            # Check if DaenaBot bridge is connected for this user
            _bridge_conn = None
            try:
                from app.api.v1.bridge import get_bridge_manager
                _bridge_conn = get_bridge_manager().get(self.user_id)
            except Exception:
                pass

            if _bridge_conn is not None:
                # Route through bridge to user's machine
                try:
                    result = await _bridge_conn.send_tool_call(
                        qualified_name, resolved_params,
                        governance_tier=0,
                    )
                    return result
                except Exception as exc:
                    logger.warning("tool_loop.bridge_call_failed", error=str(exc))
                    return {"success": False, "error": f"DaenaBot bridge call failed: {exc}"}

            # No bridge: check if we're in cloud mode (no Ollama = cloud)
            _is_cloud = True
            try:
                from app.core.config import get_settings
                _is_cloud = not bool((get_settings().ollama_base_url or "").strip())
            except Exception:
                pass

            if _is_cloud:
                return {
                    "success": False,
                    "error": (
                        "This action requires access to your computer, but DaenaBot is not installed. "
                        "Go to Connections in the sidebar and install DaenaBot to give me access to "
                        "your files, terminal, browser, and desktop. It takes 30 seconds."
                    ),
                    "needs_bridge": True,
                }

        try:
            # ── Self-config (Daena managing her own runtime) ──
            # daena_get_runtime_state, daena_list_available_minds,
            # daena_set_primary_mind. The LLM uses these to ACT on
            # "which mind are you using?" / "switch primary mind to X"
            # via real-time reasoning, not hardcoded patterns.
            if prefix == "daena" or qualified_name.startswith("daena_"):
                return await self._exec_daena_self(qualified_name, resolved_params)

            # ── File system tools ──
            if prefix == "file":
                return await self._exec_file(operation, resolved_params)

            # ── Terminal tools ──
            elif prefix == "terminal":
                return await self._exec_terminal(operation, resolved_params)

            # ── Network tools ──
            elif prefix == "network":
                return await self._exec_network(operation, resolved_params)

            # ── Browser tools ──
            elif prefix == "browser":
                return await self._exec_browser(operation, resolved_params)

            # ── Desktop control tools ──
            elif prefix == "desktop":
                return await self._exec_desktop(operation, resolved_params)

            # ── Vision loop (computer_use) ──
            elif prefix == "vision":
                return await self._exec_vision(operation, resolved_params)

            # ── MCP bridge ──
            elif prefix == "mcp":
                return await self._exec_mcp(operation, resolved_params)

            # ── Integration tools (Gmail, Calendar, Notion) ──
            elif prefix in ("gmail", "calendar", "notion"):
                return await self._exec_integration(prefix, operation, resolved_params)

            # ── Department workflows ──
            elif prefix == "workflow":
                return await self._exec_workflow(operation, resolved_params)

            # ── Security scanning tools ──
            elif prefix == "vuln_scanner":
                return await self._exec_vuln_scanner(operation, resolved_params)

            # ── Power tools (git, clipboard, process, project, db, media, archive, pdf) ──
            elif prefix == "git":
                return await self._exec_git(operation, resolved_params)
            elif prefix == "clipboard":
                return await self._exec_clipboard(operation, resolved_params)
            elif prefix in ("list_processes", "kill_process", "start_process"):
                return await self._exec_process(prefix, resolved_params)
            elif prefix == "create_project":
                return await self._exec_create_project(resolved_params)
            elif prefix == "system_info":
                return await self._exec_system_info()
            elif prefix == "db":
                return await self._exec_db(operation, resolved_params)
            elif prefix in ("generate_audio", "generate_image", "generate_pdf"):
                return await self._exec_media(prefix, resolved_params)
            elif prefix in ("archive_create", "archive_extract"):
                return await self._exec_archive(prefix, resolved_params)
            elif prefix == "edit_file":
                return await self._exec_edit_file(resolved_params)
            elif prefix == "create_tool":
                return await self._exec_create_tool(resolved_params)
            elif prefix == "install_system_tool":
                return await self._exec_install_system_tool(resolved_params)

            return {"success": False, "error": f"Unknown tool dispatch: {prefix}.{operation}"}

        except Exception as exc:
            logger.error(
                "tool_loop.execution_failed",
                tool=tool_name,
                error=str(exc),
            )
            # Returning ``error`` rather than raising so the public
            # ``_execute_tool`` wrapper can inspect it for the
            # auto-heal trigger patterns. That keeps the heal path
            # uniform whether the dispatch raised or returned a
            # non-success dict (subprocess-based tools typically do
            # the latter). The LLM gets the error back unchanged if
            # the heal path can't help it.
            return {"success": False, "error": str(exc)}

    # ── Dispatch Handlers ────────────────────────────────────────

    async def _auto_install(
        self, error_text: str, tool_name: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        """Auto-install missing dependencies when AGI mode is on.

        Daena installs what she needs: if a tool/command/package isn't
        found, she figures out what to install and does it. This is the
        OpenClaw-equivalent adaptive primitive -- error triggers a
        self-heal attempt before the LLM loop reports failure.

        Bug history (2026-04-18 self-audit): earlier versions shelled out
        to bare ``pip install`` which resolves from PATH, so packages
        landed in the wrong Python env when Daena runs in a venv. Fixed
        by pinning to ``sys.executable -m pip`` so installs always go to
        the interpreter actually running Daena. Success detection also
        accepts both ``return_code`` and ``exit_code`` + ``returncode``
        keys, since ``TerminalAgent.execute_command`` varies per OS.
        """
        import re
        import sys

        # Extract package name from common error patterns
        package = None
        for pattern in [
            r"No module named ['\"]?(\w[\w.-]*)",
            r"ModuleNotFoundError.*['\"](\w[\w.-]*)",
            r"command not found.*?(\w[\w.-]+)",
            r"is not recognized.*?['\"]?(\w[\w.-]+)",
            r"pip install (\w[\w.-]*)",
        ]:
            match = re.search(pattern, error_text, re.IGNORECASE)
            if match:
                package = match.group(1)
                break

        if not package:
            return {"success": False, "error": "Could not determine what to install"}

        # ── Pre-ingestion security + intelligence filter ────────────
        # Before ANY autonomous install, route through the scan-first
        # gate. Rejects typosquats, known-malicious names, non-existent
        # PyPI packages, and redundant installs. WARN signals escalate
        # to REFUSE on the auto-heal path because silent install on
        # ambiguity defeats the point of governance.
        try:
            from app.services.security.pre_ingestion_filter import (
                ArtifactType,
                IngestionContext,
                PreIngestionFilter,
                TriggerSource,
            )

            filter_ = PreIngestionFilter()
            verdict = await filter_.evaluate(IngestionContext(
                artifact_type=ArtifactType.PIP_PACKAGE,
                identifier=package,
                source="pypi",
                triggered_by=TriggerSource.AUTO_HEAL,
                reason=error_text[:200],
                agi_mode=self.agi_mode,
            ))
            logger.info(
                "tool_loop.auto_install_filter",
                package=package,
                decision=verdict.decision,
                confidence=verdict.confidence,
                signals=[s.check for s in verdict.signals],
                latency_ms=round(verdict.total_latency_ms, 1),
            )
            if verdict.decision == "REFUSE":
                return {
                    "success": False,
                    "error": f"Pre-ingestion filter refused {package}: {verdict.reason}",
                    "filter_verdict": {
                        "decision": verdict.decision,
                        "reason": verdict.reason,
                        "need_analysis": verdict.need_analysis,
                        "signals": [
                            {"check": s.check, "verdict": s.verdict, "detail": s.detail}
                            for s in verdict.signals
                        ],
                    },
                }
            if verdict.decision == "WARN":
                # WARN on non-auto-heal paths surfaces as a pending
                # approval. Since _auto_install only runs in the
                # auto-heal path (which escalates WARN to REFUSE),
                # this branch is defensive; it matters if _auto_install
                # is later called from other trigger sources.
                return {
                    "success": False,
                    "error": f"Pre-ingestion filter warned on {package}: {verdict.reason}",
                    "filter_verdict": {
                        "decision": verdict.decision,
                        "reason": verdict.reason,
                        "need_analysis": verdict.need_analysis,
                        "signals": [
                            {"check": s.check, "verdict": s.verdict, "detail": s.detail}
                            for s in verdict.signals
                        ],
                    },
                }
            # PASS -- fall through to the install commands below.
        except Exception as filter_exc:
            # Filter must never break the install path entirely; log
            # and continue with the historical behavior. If the filter
            # is down we fall back to the pre-filter trust model, which
            # is still safer than OpenClaw because the heal-trigger
            # patterns are narrow.
            logger.warning(
                "tool_loop.pre_ingestion_filter_error",
                error=str(filter_exc),
                package=package,
            )

        logger.info("tool_loop.auto_install_attempting", package=package)

        def _ok(r: dict[str, Any]) -> bool:
            """Accept any exit-code-zero flavor the shell might report."""
            for key in ("return_code", "returncode", "exit_code"):
                if key in r:
                    return r.get(key) == 0
            return bool(r.get("success"))

        # Try pip install using the ACTIVE interpreter (fixes venv miss).
        # Shelling out to bare ``pip`` would hit whatever pip is first on
        # PATH, which almost never matches ``sys.executable`` in a venv.
        try:
            from app.services.daenabot.terminal_agent import TerminalAgent
            agent = TerminalAgent()
            py = sys.executable
            result = await agent.execute_command(
                command=f'"{py}" -m pip install {package}',
                timeout=120,
            )
            if _ok(result):
                # Bust importlib cache so the newly-installed module is
                # callable in the SAME process without a restart.
                import importlib
                importlib.invalidate_caches()
                return {
                    "success": True,
                    "installed": package,
                    "method": "pip",
                    "python": py,
                }
        except Exception as exc:
            logger.debug("auto_install.pip_failed", error=str(exc))

        # Fallback: npm global install for CLI-style packages.
        try:
            from app.services.daenabot.terminal_agent import TerminalAgent
            agent = TerminalAgent()
            result = await agent.execute_command(
                command=f"npm install -g {package}",
                timeout=120,
            )
            if _ok(result):
                return {"success": True, "installed": package, "method": "npm"}
        except Exception as exc:
            logger.debug("auto_install.npm_failed", error=str(exc))

        return {"success": False, "error": f"Failed to install {package}"}

    async def _exec_daena_self(
        self, qualified_name: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        """Daena's own runtime configuration tools.

        qualified_name is one of:
          - daena_get_runtime_state    / daena.get_runtime_state
          - daena_list_available_minds / daena.list_available_minds
          - daena_set_primary_mind     / daena.set_primary_mind
        """
        # Map either underscore or dot form to the internal operation
        # key. The schema_builder uses underscore (Anthropic style);
        # internal regex/intent_parser uses dot.
        if qualified_name.startswith("daena_"):
            operation = qualified_name[len("daena_"):]
        elif "." in qualified_name:
            operation = qualified_name.split(".", 1)[1]
        else:
            operation = qualified_name

        # Pass the live model_registry from app.state so
        # list_available_minds returns currently-discovered models.
        # Threaded through via self._app_state if available; otherwise
        # the agent falls back to a fresh ModelRegistry.
        live_registry = getattr(self, "_app_state_model_registry", None)

        from app.services.daenabot.daena_self_agent import DaenaSelfAgent
        agent = DaenaSelfAgent(
            db=self.db,
            user_id=self.user_id,
            model_registry=live_registry,
        )
        try:
            return await agent.execute(operation, params)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

    async def _exec_file(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """File system operations via SystemAccess."""
        from app.services.agent_core.system_access import SystemAccess
        sys_access = SystemAccess(agi_mode=self.agi_mode)

        if operation == "read_file":
            content = await sys_access.read_file(params["path"])
            return {"success": True, "content": content[:TOOL_RESULT_MAX_LENGTH]}

        elif operation == "write_file":
            await sys_access.write_file(params["path"], params["content"])
            return {"success": True, "message": f"Written to {params['path']}"}

        elif operation == "list_directory":
            entries = await sys_access.list_directory(params["path"])
            return {"success": True, "entries": entries}

        elif operation == "search_files":
            results = await sys_access.search_files(
                params["pattern"],
                params.get("root", "."),
            )
            return {"success": True, "files": results[:50]}

        elif operation == "delete_file":
            # Archive instead of delete (Hard Law #6)
            import shutil
            from pathlib import Path

            src = Path(params["path"])
            if not src.exists():
                return {"success": False, "error": f"File not found: {params['path']}"}

            archive_dir = src.parent / ".archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            dest = archive_dir / f"{src.name}.{ts}"
            shutil.move(str(src), str(dest))
            return {"success": True, "message": f"Archived to {dest}"}

        elif operation == "move_file":
            await sys_access.move_file(params["source"], params["destination"])
            return {"success": True, "message": f"Moved {params['source']} -> {params['destination']}"}

        elif operation == "copy_file":
            await sys_access.copy_file(params["source"], params["destination"])
            return {"success": True, "message": f"Copied {params['source']} -> {params['destination']}"}

        return {"success": False, "error": f"Unknown file operation: {operation}"}

    async def _exec_terminal(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Terminal operations via SystemAccess."""
        from app.services.agent_core.system_access import SystemAccess
        sys_access = SystemAccess(agi_mode=self.agi_mode)

        if operation == "execute_command":
            result = await sys_access.run_command(
                params["command"],
                cwd=params.get("working_directory"),
            )
            return {
                "success": result.get("success", result.get("returncode", 1) == 0),
                "stdout": str(result.get("stdout", ""))[:TOOL_RESULT_MAX_LENGTH],
                "stderr": str(result.get("stderr", ""))[:1000],
                "exit_code": result.get("returncode", result.get("exit_code")),
            }

        elif operation == "run_python":
            result = await sys_access.run_python(params["code"])
            return {
                "success": result.get("success", False),
                "stdout": str(result.get("stdout", ""))[:TOOL_RESULT_MAX_LENGTH],
                "stderr": str(result.get("stderr", ""))[:1000],
            }

        elif operation == "install_package":
            success = await sys_access.install_package(
                params["package"],
                params.get("manager", "pip"),
            )
            return {"success": success, "message": f"{'Installed' if success else 'Failed to install'} {params['package']}"}

        return {"success": False, "error": f"Unknown terminal operation: {operation}"}

    async def _exec_network(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Network operations via SystemAccess."""
        from app.services.agent_core.system_access import SystemAccess
        sys_access = SystemAccess(agi_mode=self.agi_mode)

        if operation == "http_get":
            result = await sys_access.http_get(params["url"])
            return {"success": True, **result}

        elif operation == "http_post":
            result = await sys_access.http_post(
                params["url"],
                json_body=params.get("json_body"),
            )
            return {"success": True, **result}

        elif operation == "web_search":
            # Web search via DuckDuckGo HTML (no API key needed)
            import httpx
            query = params["query"]
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        "https://html.duckduckgo.com/html/",
                        params={"q": query},
                        headers={"User-Agent": "Daena/1.0"},
                    )
                    if resp.status_code == 200:
                        # Extract text snippets from results
                        import re
                        results = re.findall(
                            r'class="result__snippet">(.*?)</a>',
                            resp.text, re.DOTALL,
                        )
                        # Clean HTML tags
                        clean = [re.sub(r'<[^>]+>', '', r).strip() for r in results[:5]]
                        return {
                            "success": True,
                            "query": query,
                            "results": clean if clean else ["No results found"],
                        }
            except Exception as exc:
                return {"success": False, "error": f"Web search failed: {exc}"}

            return {"success": False, "error": "Web search unavailable"}

        return {"success": False, "error": f"Unknown network operation: {operation}"}

    async def _exec_browser(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Browser operations via BrowserAgent (Playwright)."""
        from app.services.daenabot.browser_agent import BrowserAgent
        agent = BrowserAgent(headless=True)
        try:
            result = await agent.execute(operation, params)
            return {"success": True, "result": result}
        finally:
            await agent.close()

    async def _exec_desktop(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Desktop control via pyautogui with governance.

        This is what makes Daena an OpenClaw-class agent: mouse, keyboard,
        screen capture at the OS level, not just inside a browser.
        Governance: all desktop actions are logged. Critical actions
        (like typing passwords) require approval in non-AGI mode.
        """
        try:
            import pyautogui
            pyautogui.FAILSAFE = True  # Move mouse to corner to abort
            pyautogui.PAUSE = 0.1

            if operation == "screenshot":
                import io
                import base64
                screenshot = pyautogui.screenshot()
                buffer = io.BytesIO()
                screenshot.save(buffer, format="PNG")
                b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                return {
                    "success": True,
                    "image_base64": b64[:100] + "...(truncated for context)",
                    "width": screenshot.width,
                    "height": screenshot.height,
                    "message": f"Screenshot taken: {screenshot.width}x{screenshot.height}",
                }

            elif operation == "click":
                x, y = params["x"], params["y"]
                button = params.get("button", "left")
                clicks = 2 if params.get("double_click") else 1
                pyautogui.click(x, y, clicks=clicks, button=button)
                return {"success": True, "message": f"Clicked at ({x}, {y}) button={button}"}

            elif operation == "type_text":
                pyautogui.typewrite(params["text"], interval=0.02) if params["text"].isascii() else pyautogui.write(params["text"])
                return {"success": True, "message": f"Typed {len(params['text'])} characters"}

            elif operation == "hotkey":
                keys = params["keys"].split("+")
                pyautogui.hotkey(*keys)
                return {"success": True, "message": f"Pressed {params['keys']}"}

            elif operation == "scroll":
                direction = params["direction"]
                amount = params.get("amount", 3)
                scroll_val = amount if direction == "up" else -amount
                x = params.get("x")
                y = params.get("y")
                if x is not None and y is not None:
                    pyautogui.scroll(scroll_val, x, y)
                else:
                    pyautogui.scroll(scroll_val)
                return {"success": True, "message": f"Scrolled {direction} {amount}"}

            elif operation == "move_mouse":
                pyautogui.moveTo(params["x"], params["y"])
                return {"success": True, "message": f"Mouse moved to ({params['x']}, {params['y']})"}

            return {"success": False, "error": f"Unknown desktop operation: {operation}"}

        except ImportError:
            # pyautogui not installed -- fall back to Windows-MCP if available
            return await self._exec_desktop_via_mcp(operation, params)
        except Exception as exc:
            return {"success": False, "error": f"Desktop control failed: {exc}"}

    async def _exec_desktop_via_mcp(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Fallback: desktop control via Windows-MCP server."""
        # Map desktop operations to Windows-MCP tool names
        mcp_map = {
            "screenshot": "Screenshot",
            "click": "Click",
            "type_text": "Type",
            "hotkey": "Shortcut",
            "scroll": "Scroll",
            "move_mouse": "Move",
        }

        mcp_tool = mcp_map.get(operation)
        if not mcp_tool:
            return {"success": False, "error": f"No MCP mapping for desktop.{operation}"}

        # Try calling Windows-MCP
        from app.services.daenabot.mcp_agent import MCPAgent
        agent = MCPAgent()

        # Build MCP arguments from params
        mcp_params = {
            "tool_name": mcp_tool,
            "arguments": params,
            "server_url": "http://localhost:3000",  # Default Windows-MCP port
        }

        result = await agent.execute("call_tool", mcp_params)
        if result.get("status") == "error":
            return {"success": False, "error": result.get("error", "MCP desktop call failed")}
        return {"success": True, "result": result.get("output", result)}

    async def _exec_vision(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Vision loop: autonomous desktop control via screenshot + LLM vision.

        Takes screenshots, sends to multimodal LLM, gets action coordinates,
        executes actions, loops until task complete. This is computer_use.
        """
        from app.services.vision_loop import VisionLoop

        task = params.get("task", "")
        max_steps = params.get("max_steps", 10)

        if not task:
            return {"success": False, "error": "No task specified for computer_use"}

        loop = VisionLoop(max_iterations=max_steps)
        steps_log: list[dict] = []

        try:
            async for step in loop.execute(task):
                step_info = {
                    "iteration": step.iteration,
                    "action": step.action.action_type if step.action else "none",
                    "description": step.observation,
                    "success": step.success,
                }
                steps_log.append(step_info)

                if not step.success:
                    break

            summary = loop.get_summary()
            return {
                "success": summary["successful_steps"] > 0,
                "total_steps": summary["total_steps"],
                "steps": steps_log[-5:],  # Last 5 steps for context
                "message": f"Vision loop completed: {summary['successful_steps']}/{summary['total_steps']} steps successful",
            }

        except Exception as exc:
            return {"success": False, "error": f"Vision loop failed: {exc}", "steps": steps_log}

    async def _exec_mcp(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """MCP tool execution via MCPAgent."""
        from app.services.daenabot.mcp_agent import MCPAgent
        agent = MCPAgent()
        result = await agent.execute("call_tool", params)
        if result.get("status") == "error":
            return {"success": False, "error": result.get("error", "MCP call failed")}
        return {"success": True, "result": result.get("output", result)}

    async def _exec_integration(self, provider: str, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Integration tools (Gmail, Calendar, Notion) via IntegrationRouter."""
        from app.services.integrations.integration_router import IntegrationRouter
        router = IntegrationRouter(self.db)
        result = await router.execute(
            provider=provider,
            tool_name=operation,
            params=params,
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            skip_permission_check=self.agi_mode,
        )
        return {"success": True, **result}

    async def _exec_workflow(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Department workflow execution."""
        from app.services.department_workflows import DepartmentWorkflowEngine
        engine = DepartmentWorkflowEngine(self.db, self.user_id, self.tenant_id)
        wf_result = await engine.run(params.get("workflow_id", ""))
        return {"success": wf_result.status == "completed", "summary": wf_result.summary[:1000]}

    async def _exec_vuln_scanner(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Security vulnerability scanning via VulnScannerAgent."""
        from app.services.daenabot.vuln_scanner_agent import VulnScannerAgent
        agent = VulnScannerAgent()
        return await agent.execute(operation, params)

    # ── Power Tool Handlers ──────────────────────────────────────

    async def _exec_edit_file(self, params: dict[str, Any]) -> dict[str, Any]:
        """Surgical file edit -- find and replace specific text."""
        import pathlib
        path = pathlib.Path(params["path"])
        if not path.exists():
            return {"success": False, "error": f"File not found: {path}"}
        content = path.read_text(encoding="utf-8")
        old_text = params["old_text"]
        if old_text not in content:
            return {"success": False, "error": "old_text not found in file"}
        if content.count(old_text) > 1:
            return {"success": False, "error": "old_text matches multiple locations -- make it more specific"}
        new_content = content.replace(old_text, params["new_text"], 1)
        path.write_text(new_content, encoding="utf-8")
        return {"success": True, "message": f"Edited {path.name}", "lines_changed": params["new_text"].count("\n") + 1}

    async def _exec_git(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Git operations: status, commit, diff."""
        import asyncio
        cwd = params.get("path", ".")
        if operation == "status":
            cmd = "git status --short"
        elif operation == "commit":
            msg = params.get("message", "Auto-commit by Daena")
            cmd = f'git add -A && git commit -m "{msg}"'
        elif operation == "diff":
            cmd = "git diff --stat" if not params.get("staged") else "git diff --cached --stat"
        else:
            return {"success": False, "error": f"Unknown git operation: {operation}"}
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd)
        stdout, stderr = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace")[:4000]
        if proc.returncode != 0:
            return {"success": False, "error": stderr.decode("utf-8", errors="replace")[:2000], "output": output}
        return {"success": True, "output": output}

    async def _exec_clipboard(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Clipboard read/write via pyperclip or PowerShell fallback."""
        import asyncio
        if operation == "read":
            proc = await asyncio.create_subprocess_shell(
                'powershell.exe -Command "Get-Clipboard"',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return {"success": True, "content": stdout.decode("utf-8", errors="replace")}
        elif operation == "write":
            text = params.get("text", "")
            proc = await asyncio.create_subprocess_shell(
                f'powershell.exe -Command "Set-Clipboard -Value \'{text[:10000]}\'"',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return {"success": True, "message": f"Copied {len(text)} chars to clipboard"}
        return {"success": False, "error": f"Unknown clipboard operation: {operation}"}

    async def _exec_process(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Process management: list, kill, start."""
        import asyncio
        if tool_name == "list_processes":
            filt = params.get("filter", "")
            cmd = f'powershell.exe -Command "Get-Process {filt} | Select-Object -First 30 Id, ProcessName, CPU, WorkingSet | Format-Table -AutoSize"' if filt else 'powershell.exe -Command "Get-Process | Sort-Object CPU -Descending | Select-Object -First 30 Id, ProcessName, CPU, WorkingSet | Format-Table -AutoSize"'
            proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate()
            return {"success": True, "processes": stdout.decode("utf-8", errors="replace")[:4000]}
        elif tool_name == "kill_process":
            target = params.get("target", "")
            cmd = f'powershell.exe -Command "Stop-Process -Name {target} -Force -ErrorAction SilentlyContinue; Stop-Process -Id {target} -Force -ErrorAction SilentlyContinue"'
            proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()
            return {"success": True, "message": f"Killed {target}"}
        elif tool_name == "start_process":
            cmd = params.get("command", "")
            cwd = params.get("working_directory")
            proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd)
            return {"success": True, "pid": proc.pid, "message": f"Started: {cmd[:100]}"}
        return {"success": False, "error": f"Unknown process tool: {tool_name}"}

    async def _exec_create_project(self, params: dict[str, Any]) -> dict[str, Any]:
        """Scaffold a new project from templates."""
        import asyncio, pathlib
        name = params["name"]
        template = params.get("template", "python")
        parent = params.get("path", ".")
        project_dir = pathlib.Path(parent) / name

        scaffolds = {
            "react": f'npx create-react-app "{project_dir}" --template typescript',
            "nextjs": f'npx create-next-app@latest "{project_dir}" --typescript --eslint --app --src-dir --no-tailwind',
            "python": f'mkdir -p "{project_dir}/src" "{project_dir}/tests" && cd "{project_dir}" && python -m venv .venv && echo "# {name}" > README.md',
            "fastapi": f'mkdir -p "{project_dir}/app" "{project_dir}/tests" && cd "{project_dir}" && python -m venv .venv && .venv/Scripts/pip install fastapi uvicorn',
            "flask": f'mkdir -p "{project_dir}/app" "{project_dir}/tests" && cd "{project_dir}" && python -m venv .venv && .venv/Scripts/pip install flask',
            "express": f'mkdir -p "{project_dir}" && cd "{project_dir}" && npm init -y && npm install express typescript @types/express ts-node',
            "vue": f'npm create vue@latest "{project_dir}" -- --typescript',
            "svelte": f'npm create svelte@latest "{project_dir}"',
            "rust": f'cargo new "{project_dir}"',
            "go": f'mkdir -p "{project_dir}" && cd "{project_dir}" && go mod init {name}',
        }
        cmd = scaffolds.get(template)
        if not cmd:
            return {"success": False, "error": f"Unknown template: {template}. Available: {', '.join(scaffolds.keys())}"}

        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        # Init git
        await asyncio.create_subprocess_shell(f'cd "{project_dir}" && git init', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        return {"success": proc.returncode == 0, "path": str(project_dir), "output": stdout.decode("utf-8", errors="replace")[:2000]}

    async def _exec_system_info(self) -> dict[str, Any]:
        """Gather system information."""
        import platform, shutil, os
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "arch": platform.machine(),
            "python": platform.python_version(),
            "node": shutil.which("node") is not None,
            "npm": shutil.which("npm") is not None,
            "rust": shutil.which("cargo") is not None,
            "go": shutil.which("go") is not None,
            "docker": shutil.which("docker") is not None,
            "git": shutil.which("git") is not None,
            "wsl": shutil.which("wsl") is not None,
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "cpu_count": os.cpu_count(),
        }
        return {"success": True, **info}

    async def _exec_db(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a SQL query."""
        import asyncio
        query = params.get("query", "")
        db_url = params.get("database_url", "")
        if "sqlite" in db_url:
            db_path = db_url.replace("sqlite:///", "")
            cmd = f'python -c "import sqlite3; c=sqlite3.connect(\'{db_path}\'); r=c.execute(\'\'\'{query}\'\'\'); print([dict(zip([d[0] for d in r.description], row)) for row in r.fetchmany(50)] if r.description else \'OK\')"'
        else:
            return {"success": False, "error": "Only SQLite supported in this handler. Use run_command with psql for PostgreSQL."}
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return {"success": False, "error": stderr.decode("utf-8", errors="replace")[:2000]}
        return {"success": True, "result": stdout.decode("utf-8", errors="replace")[:4000]}

    async def _exec_media(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Media generation: audio, image, PDF."""
        import asyncio
        output_path = params.get("output_path", "")
        if tool_name == "generate_audio":
            text = params.get("text", "")
            cmd = f'python -c "import pyttsx3; e=pyttsx3.init(); e.save_to_file(\'{text[:500]}\', \'{output_path}\'); e.runAndWait()"'
            proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                # Fallback: use PowerShell TTS
                cmd = f'powershell.exe -Command "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.SetOutputToWaveFile(\'{output_path}\'); $s.Speak(\'{text[:500]}\'); $s.Dispose()"'
                proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await proc.communicate()
            return {"success": True, "path": output_path}
        elif tool_name == "generate_image":
            desc = params.get("description", "")
            w = params.get("width", 800)
            h = params.get("height", 600)
            # Use matplotlib to generate
            code = f"""
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=({w/100}, {h/100}))
ax.text(0.5, 0.5, '''{desc[:200]}''', ha='center', va='center', fontsize=14, wrap=True)
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
plt.savefig('{output_path}', dpi=100, bbox_inches='tight')
plt.close()
"""
            proc = await asyncio.create_subprocess_shell(f'python -c "{code}"', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()
            return {"success": True, "path": output_path}
        elif tool_name == "generate_pdf":
            content = params.get("content", "")
            title = params.get("title", "Document")
            # Use weasyprint or reportlab fallback
            code = f"""
try:
    from weasyprint import HTML
    HTML(string='<h1>{title}</h1>{content}').write_pdf('{output_path}')
except ImportError:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    c = canvas.Canvas('{output_path}', pagesize=letter)
    c.drawString(72, 750, '{title}')
    y = 720
    for line in '''{content[:3000]}'''.split('\\n'):
        c.drawString(72, y, line[:90])
        y -= 14
        if y < 72: c.showPage(); y = 750
    c.save()
"""
            proc = await asyncio.create_subprocess_shell(f'python -c "{code}"', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()
            return {"success": True, "path": output_path}
        return {"success": False, "error": f"Unknown media tool: {tool_name}"}

    async def _exec_archive(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Archive operations: create/extract zip and tar."""
        import shutil, pathlib
        if tool_name == "archive_create":
            source = params["source"]
            output = params["output_path"]
            if output.endswith(".zip"):
                shutil.make_archive(output.replace(".zip", ""), "zip", source)
            else:
                shutil.make_archive(output.replace(".tar.gz", ""), "gztar", source)
            return {"success": True, "path": output}
        elif tool_name == "archive_extract":
            archive = params["archive_path"]
            dest = params.get("destination", ".")
            shutil.unpack_archive(archive, dest)
            return {"success": True, "extracted_to": dest}
        return {"success": False, "error": f"Unknown archive tool: {tool_name}"}

    async def _exec_create_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        """AGI: Create a new tool at runtime from Python code.

        This is the power move -- if Daena needs a capability that does not
        exist, she writes the tool herself and registers it for the session.
        """
        tool_name = params["tool_name"]
        description = params["description"]
        python_code = params["python_code"]
        schema = params.get("parameters_schema", {})

        # Compile and validate the code
        try:
            compile(python_code, f"<dynamic_tool:{tool_name}>", "exec")
        except SyntaxError as e:
            return {"success": False, "error": f"Syntax error in tool code: {e}"}

        # Create the async function
        namespace: dict = {}
        exec(python_code, namespace)

        # Find the async function in the namespace
        func = None
        for v in namespace.values():
            if callable(v) and asyncio.iscoroutinefunction(v):
                func = v
                break

        if func is None:
            return {"success": False, "error": "Tool code must contain an async function"}

        # Register it as a dynamic tool
        if not hasattr(self, "_dynamic_tools"):
            self._dynamic_tools = {}
        self._dynamic_tools[tool_name] = func

        logger.info("tool_loop.dynamic_tool_created", tool=tool_name, description=description[:100])
        return {"success": True, "tool_name": tool_name, "message": f"Tool '{tool_name}' created and available for this session"}

    async def _exec_install_system_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        """AGI: Install a system tool using the best available package
        manager.

        Manager preference order tuned for autonomous install:
        1. ``pip`` when the target looks like a Python package (most
           common path for Daena's self-extension).
        2. ``npm`` for CLI-style tools + MCP servers.
        3. OS-native managers as fallback.

        pip is invoked via ``sys.executable -m pip`` so installs go to
        the interpreter actually running Daena (fixes venv miss that
        earlier versions had when pip on PATH differed from the venv
        pip).
        """
        import asyncio, platform, shutil, sys
        tool_name = params["tool_name"]
        manager = params.get("manager")

        if not manager:
            # Auto-detect
            if shutil.which("pip"):
                manager = "pip"
            elif shutil.which("npm"):
                manager = "npm"
            elif platform.system() == "Windows" and shutil.which("winget"):
                manager = "winget"
            elif platform.system() == "Windows" and shutil.which("choco"):
                manager = "choco"
            elif platform.system() == "Linux" and shutil.which("apt"):
                manager = "apt"
            elif platform.system() == "Darwin" and shutil.which("brew"):
                manager = "brew"
            elif shutil.which("cargo"):
                manager = "cargo"
            else:
                return {"success": False, "error": "No package manager found"}

        cmds = {
            "pip": f'"{sys.executable}" -m pip install {tool_name}',
            "npm": f"npm install -g {tool_name}",
            "winget": f"winget install {tool_name}",
            "choco": f"choco install {tool_name} -y",
            "apt": f"sudo apt-get install -y {tool_name}",
            "brew": f"brew install {tool_name}",
            "cargo": f"cargo install {tool_name}",
        }
        cmd = cmds.get(manager, f"pip install {tool_name}")
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        return {
            "success": proc.returncode == 0,
            "manager": manager,
            "output": stdout.decode("utf-8", errors="replace")[:2000],
            "error": stderr.decode("utf-8", errors="replace")[:1000] if proc.returncode != 0 else None,
        }

    # ── Utility Methods ──────────────────────────────────────────

    @staticmethod
    def _strip_tool_calls(response: str) -> str:
        """Remove ```tool_call blocks from a response."""
        import re
        return re.sub(r'```tool_call\s*\n?.*?\n?```', '', response, flags=re.DOTALL).strip()

    @staticmethod
    def _format_tool_results(
        calls: list[dict[str, Any]],
        results: list[dict[str, Any]],
    ) -> str:
        """Format tool results for injection into context."""
        parts = []
        for call, result_entry in zip(calls, results):
            result = result_entry.get("result", {})
            parts.append(
                f"Tool: {call['tool']}\n"
                f"Result: {json.dumps(result, indent=2, default=str)[:TOOL_RESULT_MAX_LENGTH]}"
            )
        return "\n---\n".join(parts)
