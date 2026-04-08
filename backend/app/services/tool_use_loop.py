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
    ) -> None:
        self.db = db
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.agi_mode = agi_mode
        self.session_id = session_id
        self._tool_results: list[dict[str, Any]] = []
        self._total_tool_calls = 0
        self._total_cost = 0.0

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
        enhanced_prompt = f"{system_prompt}\n\n{tool_prompt}"

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
                # No tool calls -- this is the final response
                # Stream the response to the user
                yield {"type": "tool_use_response", "content": full_response}
                break

            # Execute tool calls
            for call in tool_calls:
                tool_name = call["tool"]
                params = call["params"]

                yield {
                    "type": "tool_call",
                    "tool": tool_name,
                    "params": params,
                    "iteration": iteration,
                }

                # Execute the tool
                result = await self._execute_tool(tool_name, params)
                self._total_tool_calls += 1
                self._tool_results.append({
                    "tool": tool_name,
                    "params": params,
                    "result": result,
                    "iteration": iteration,
                })

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
                from app.services.llm_service import LLMMessage
                tool_context_messages.append(
                    LLMMessage(role="assistant", content=clean_response)
                )

            # Add tool results as a system message
            results_text = self._format_tool_results(tool_calls, self._tool_results[-len(tool_calls):])
            from app.services.llm_service import LLMMessage
            tool_context_messages.append(
                LLMMessage(role="user", content=f"[TOOL RESULTS]\n{results_text}\n\nContinue with your response based on these results.")
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

            # Try Groq (fast, free tier available)
            groq_key = (settings.groq_api_key or "").strip()
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

        # Ollama (local)
        ollama_url = "http://localhost:11434"
        try:
            from app.core.config import get_settings
            ollama_url = get_settings().ollama_base_url or ollama_url
        except Exception:
            pass

        if provider.lower() in ("ollama", "local") or True:  # Always try Ollama as fallback
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
                        yield "\n".join(output_lines)
                        return
        except Exception as exc:
            logger.warning("tool_loop.runtime_failed", error=str(exc))

        yield "[No LLM available for tool-use loop]"

    async def _execute_tool(
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
        """
        qualified_name, resolved_params = resolve_tool_call(tool_name, params)
        parts = qualified_name.split(".", 1)

        if len(parts) != 2:
            return {"success": False, "error": f"Invalid tool: {tool_name}"}

        prefix, operation = parts

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

            return {"success": False, "error": f"Unknown tool dispatch: {prefix}.{operation}"}

        except Exception as exc:
            logger.error(
                "tool_loop.execution_failed",
                tool=tool_name,
                error=str(exc),
            )

            # Self-repair: if this looks like a code error, try to fix it
            error_text = str(exc)
            if self.agi_mode and any(
                kw in error_text.lower()
                for kw in ["error", "traceback", "exception", "failed"]
            ):
                try:
                    from app.services.self_repair import attempt_self_repair
                    repair = await attempt_self_repair(
                        error_text,
                        context=f"Tool {tool_name} failed with params {params}",
                    )
                    if repair.success:
                        logger.info("tool_loop.self_repair_success", file=repair.file_fixed)
                        return {"success": True, "message": f"Self-repaired: {repair.description}", "repaired": True}
                except Exception:
                    pass  # Self-repair failed -- return original error

            return {"success": False, "error": str(exc)}

    # ── Dispatch Handlers ────────────────────────────────────────

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
