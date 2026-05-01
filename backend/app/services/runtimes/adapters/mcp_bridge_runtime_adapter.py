"""MCP Bridge adapter.

Generic adapter for Model Context Protocol servers. Bridges external
MCP tools into Daena's runtime layer, enabling tool discovery,
capability assessment, and governed execution.

MCP servers can expose tools via stdio or HTTP transports. This adapter
wraps both patterns and presents them as a runtime.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from app.core.logging import get_logger
from app.services.runtimes.base_adapter import (
    BaseRuntimeAdapter,
    RuntimeCapability,
    RuntimeProbeResult,
    RuntimeStatus,
)

logger = get_logger(__name__)

# Phase 4b PR 2: real MCP handshake constants. The handshake requires a
# valid JSON-RPC initialize call followed by a response containing
# ``serverInfo`` / ``protocolVersion``. We're conservative: 6s for
# stdio spawn + initialize, 8s for HTTP requests.
_PROBE_INIT_STDIO_TIMEOUT = 6.0
_PROBE_INIT_HTTP_TIMEOUT = 8.0
_PROBE_LIST_TOOLS_TIMEOUT = 8.0
# Daena identifies as a stable MCP client. Bump version when wire
# format changes.
_PROBE_CLIENT_INFO = {
    "name": "daena-runtime-probe",
    "version": "0.1.0",
}
# Per MCP spec the protocol version is server-decided; we send a hint
# the server accepts or downgrades. Use the spec's published version.
_PROBE_PROTOCOL_VERSION = "2024-11-05"


class MCPBridgeAdapter(BaseRuntimeAdapter):
    """Generic MCP server adapter.

    Can wrap any MCP-compliant tool server. Configuration specifies
    how to connect (stdio command or HTTP URL) and what tools it
    exposes.
    """

    def __init__(
        self,
        server_name: str,
        command: list[str] | None = None,
        url: str | None = None,
        capabilities: RuntimeCapability | None = None,
    ) -> None:
        """Initialize MCP bridge.

        Args:
            server_name: Unique name for this MCP server.
            command: Subprocess command for stdio transport (e.g. ["node", "server.js"]).
            url: HTTP URL for HTTP transport.
            capabilities: Override default capability scores.
        """
        super().__init__(
            runtime_id=f"mcp_{server_name}",
            display_name=f"MCP: {server_name}",
        )
        self._command = command
        self._url = url
        self._custom_capabilities = capabilities
        self._process: asyncio.subprocess.Process | None = None
        self._tools: list[dict[str, Any]] = []

    async def check_installed(self) -> bool:
        """Check if the MCP server can be started."""
        if self._url:
            # HTTP transport: check if URL is reachable
            import httpx
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(self._url, timeout=5.0)
                    return resp.status_code < 500
            except (httpx.ConnectError, httpx.TimeoutException, OSError):
                return False

        if self._command:
            # stdio transport: check if command exists
            try:
                proc = await asyncio.create_subprocess_exec(
                    self._command[0], "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.wait(), timeout=5.0)
                return True  # command exists, even if --version is not supported
            except (TimeoutError, FileNotFoundError, OSError):
                return False

        return False

    async def check_health(self) -> RuntimeStatus:
        """Check if MCP server is responsive."""
        installed = await self.check_installed()
        if not installed:
            return RuntimeStatus.NOT_INSTALLED
        return RuntimeStatus.ONLINE

    async def get_capabilities(self) -> RuntimeCapability:
        """MCP servers have domain-specific capabilities."""
        if self._custom_capabilities:
            return self._custom_capabilities
        # Default: moderate scores, no cost (depends on underlying tool)
        return RuntimeCapability(
            complex_reasoning=3.0,
            code_generation=3.0,
            code_editing=3.0,
            file_operations=5.0,
            web_research=3.0,
            data_analysis=3.0,
            browser_automation=3.0,
            simple_chat=2.0,
            bulk_operations=5.0,
            cost_per_1k_tokens=0.0,
        )

    async def execute(
        self, task: str, context: dict[str, Any],
    ) -> AsyncIterator[str]:
        """Execute an MCP tool call.

        For stdio transport, spawns the MCP server and communicates
        via JSON-RPC over stdin/stdout. For HTTP transport, makes
        tool call requests to the server URL.
        """
        tool_name = context.get("tool_name", "")
        tool_args = context.get("tool_args", {})

        if self._url:
            # HTTP transport
            async for chunk in self._execute_http(tool_name, tool_args):
                yield chunk
        elif self._command:
            # stdio transport
            async for chunk in self._execute_stdio(tool_name, tool_args):
                yield chunk
        else:
            yield "[ERROR] MCP server has no transport configured"

    async def _execute_http(
        self, tool_name: str, tool_args: dict,
    ) -> AsyncIterator[str]:
        """Execute tool via HTTP transport."""
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._url}/tools/{tool_name}",
                    json=tool_args,
                    timeout=60.0,
                )
                resp.raise_for_status()
                yield resp.text
        except httpx.HTTPError as e:
            yield f"[ERROR] MCP HTTP call failed: {e}"

    async def _execute_stdio(
        self, tool_name: str, tool_args: dict,
    ) -> AsyncIterator[str]:
        """Execute tool via stdio transport (JSON-RPC)."""
        assert self._command is not None
        try:
            proc = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._process = proc

            # Send JSON-RPC tool call
            request = json.dumps({
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": tool_args,
                },
                "id": 1,
            }) + "\n"

            assert proc.stdin is not None
            proc.stdin.write(request.encode())
            await proc.stdin.drain()
            proc.stdin.close()

            # Read response
            assert proc.stdout is not None
            async for line in proc.stdout:
                decoded = line.decode("utf-8", errors="replace").strip()
                if decoded:
                    yield decoded

            await proc.wait()
        except OSError as e:
            yield f"[ERROR] MCP stdio execution failed: {e}"
        finally:
            self._process = None

    async def cancel(self, session_id: str) -> bool:
        """Cancel a running MCP execution."""
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=3.0)
            except TimeoutError:
                self._process.kill()
            return True
        return False

    def get_auth_requirements(self) -> dict[str, Any]:
        return {
            "type": "varies",
            "description": f"MCP server '{self.display_name}' may require configuration",
            "transport": "http" if self._url else "stdio",
            "command": self._command,
            "url": self._url,
        }

    async def probe(self) -> RuntimeProbeResult:
        """Real MCP handshake probe (Phase 4b PR 2).

        Replaces the lying ``check_installed`` (which treated "GET /url
        returns < 500" or "binary exists" as proof of life) with a real
        JSON-RPC initialize handshake.

        Truth ladder:
          1. detected = transport configured (command or url present)
          2. configured = command/url shape passes basic validation
          3. reachable = transport-level OK (stdio process spawns; HTTP
             server returns < 500 to a HEAD probe)
          4. authenticated = MCP initialize returns serverInfo without
             error -- if the server raises "missing API key" / "missing
             OAuth" during init, this is False
          5. callable = ``tools/list`` returns >= 0 tools without error
             (tool count of 0 is callable but non-useful; we record it
             as callable=true with empty capabilities)

        No secret material is included in failure_reason (Asset Shield).
        """
        import time as _time

        start = _time.perf_counter()
        result = RuntimeProbeResult()

        # Dim 1+2: detected + configured (transport is wired)
        if not self._command and not self._url:
            result.failure_dim = "configured"
            result.failure_reason = (
                "no transport configured (need command for stdio or url for HTTP)"
            )
            result.duration_ms = int((_time.perf_counter() - start) * 1000)
            return result

        if self._url:
            # Basic shape: must look like http(s) URL.
            if not (
                self._url.startswith("http://") or self._url.startswith("https://")
            ):
                result.failure_dim = "configured"
                result.failure_reason = "url must start with http:// or https://"
                result.duration_ms = int((_time.perf_counter() - start) * 1000)
                return result
            result.detected = True
            result.configured = True
            await self._probe_http(result)
        else:
            # stdio
            assert self._command is not None
            if not self._command:
                result.failure_dim = "configured"
                result.failure_reason = "command list is empty"
                result.duration_ms = int((_time.perf_counter() - start) * 1000)
                return result
            result.detected = True
            result.configured = True
            await self._probe_stdio(result)

        result.duration_ms = int((_time.perf_counter() - start) * 1000)
        if result.callable:
            result.failure_dim = None
            result.failure_reason = None
        return result

    async def _probe_http(self, result: RuntimeProbeResult) -> None:
        """Run reachable+initialize+tools/list against an HTTP MCP server."""
        import httpx

        # Dim 3: reachable -- HEAD or GET on base URL.
        try:
            async with httpx.AsyncClient(timeout=_PROBE_INIT_HTTP_TIMEOUT) as client:
                try:
                    resp = await client.get(self._url)  # type: ignore[arg-type]
                except (httpx.ConnectError, httpx.TimeoutException) as exc:
                    result.failure_dim = "reachable"
                    result.failure_reason = (
                        f"HTTP transport unreachable: {type(exc).__name__}"
                    )
                    return
                if resp.status_code >= 500:
                    result.failure_dim = "reachable"
                    result.failure_reason = f"HTTP {resp.status_code} from MCP server"
                    return
                result.reachable = True

                # Dim 4: authenticated -- send initialize.
                try:
                    init_resp = await client.post(
                        self._url,  # type: ignore[arg-type]
                        json={
                            "jsonrpc": "2.0",
                            "method": "initialize",
                            "params": {
                                "protocolVersion": _PROBE_PROTOCOL_VERSION,
                                "capabilities": {},
                                "clientInfo": _PROBE_CLIENT_INFO,
                            },
                            "id": 1,
                        },
                    )
                except httpx.HTTPError as exc:
                    result.authenticated = False
                    result.failure_dim = "authenticated"
                    result.failure_reason = (
                        f"initialize POST failed: {type(exc).__name__}"
                    )
                    return
                if init_resp.status_code >= 400:
                    result.authenticated = False
                    result.failure_dim = "authenticated"
                    result.failure_reason = (
                        f"initialize returned HTTP {init_resp.status_code}"
                    )
                    return
                try:
                    init_payload = init_resp.json()
                except Exception:
                    result.authenticated = False
                    result.failure_dim = "authenticated"
                    result.failure_reason = "initialize response not JSON"
                    return
                if init_payload.get("error"):
                    err = init_payload["error"]
                    result.authenticated = False
                    result.failure_dim = "authenticated"
                    result.failure_reason = (
                        f"initialize error: {str(err.get('message', err))[:200]}"
                    )
                    return
                if not (init_payload.get("result") or {}).get("serverInfo"):
                    result.authenticated = False
                    result.failure_dim = "authenticated"
                    result.failure_reason = (
                        "initialize result missing serverInfo"
                    )
                    return
                result.authenticated = True

                # Dim 5: callable -- tools/list
                try:
                    tools_resp = await client.post(
                        self._url,  # type: ignore[arg-type]
                        json={
                            "jsonrpc": "2.0",
                            "method": "tools/list",
                            "params": {},
                            "id": 2,
                        },
                    )
                except httpx.HTTPError as exc:
                    result.failure_dim = "callable"
                    result.failure_reason = (
                        f"tools/list failed: {type(exc).__name__}"
                    )
                    return
                if tools_resp.status_code >= 400:
                    result.failure_dim = "callable"
                    result.failure_reason = (
                        f"tools/list returned HTTP {tools_resp.status_code}"
                    )
                    return
                try:
                    tools_payload = tools_resp.json()
                except Exception:
                    result.failure_dim = "callable"
                    result.failure_reason = "tools/list response not JSON"
                    return
                if tools_payload.get("error"):
                    err = tools_payload["error"]
                    result.failure_dim = "callable"
                    result.failure_reason = (
                        f"tools/list error: {str(err.get('message', err))[:200]}"
                    )
                    return
                tools = (tools_payload.get("result") or {}).get("tools") or []
                result.callable = True
                result.capabilities = [
                    {
                        "kind": "mcp_tool",
                        "name": str(t.get("name", "")).strip(),
                        "spec": {"description": t.get("description", "")},
                    }
                    for t in tools
                    if t.get("name")
                ]
        except Exception as exc:  # noqa: BLE001
            result.failure_dim = result.failure_dim or "callable"
            result.failure_reason = (
                result.failure_reason or f"http probe error: {type(exc).__name__}"
            )

    async def _probe_stdio(self, result: RuntimeProbeResult) -> None:
        """Run reachable+initialize+tools/list against a stdio MCP server."""
        assert self._command is not None
        proc: asyncio.subprocess.Process | None = None
        try:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *self._command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except (FileNotFoundError, OSError) as exc:
                result.failure_dim = "reachable"
                result.failure_reason = (
                    f"stdio spawn failed: {type(exc).__name__}: {exc}"
                )
                return
            result.reachable = True

            # Send initialize then tools/list back-to-back, then close stdin.
            requests = [
                {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": _PROBE_PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": _PROBE_CLIENT_INFO,
                    },
                    "id": 1,
                },
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                },
                {
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "params": {},
                    "id": 2,
                },
            ]
            payload = "\n".join(json.dumps(r) for r in requests) + "\n"

            assert proc.stdin is not None and proc.stdout is not None
            proc.stdin.write(payload.encode("utf-8"))
            try:
                await proc.stdin.drain()
            except Exception:
                pass
            proc.stdin.close()

            # Drain stdout up to total timeout. Read all available lines.
            init_payload: dict | None = None
            tools_payload: dict | None = None
            try:
                stdout_b, _stderr_b = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=_PROBE_INIT_STDIO_TIMEOUT + _PROBE_LIST_TOOLS_TIMEOUT,
                )
            except TimeoutError:
                proc.kill()
                result.failure_dim = "authenticated"
                result.failure_reason = (
                    "initialize+tools/list timed out (server hung or didn't speak MCP)"
                )
                return

            for line in (stdout_b or b"").decode("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("id") == 1:
                    init_payload = obj
                elif obj.get("id") == 2:
                    tools_payload = obj

            # Dim 4: authenticated
            if init_payload is None:
                result.authenticated = False
                result.failure_dim = "authenticated"
                result.failure_reason = "no initialize response received"
                return
            if init_payload.get("error"):
                err = init_payload["error"]
                result.authenticated = False
                result.failure_dim = "authenticated"
                result.failure_reason = (
                    f"initialize error: {str(err.get('message', err))[:200]}"
                )
                return
            if not (init_payload.get("result") or {}).get("serverInfo"):
                result.authenticated = False
                result.failure_dim = "authenticated"
                result.failure_reason = "initialize result missing serverInfo"
                return
            result.authenticated = True

            # Dim 5: callable
            if tools_payload is None:
                result.failure_dim = "callable"
                result.failure_reason = "no tools/list response received"
                return
            if tools_payload.get("error"):
                err = tools_payload["error"]
                result.failure_dim = "callable"
                result.failure_reason = (
                    f"tools/list error: {str(err.get('message', err))[:200]}"
                )
                return
            tools = (tools_payload.get("result") or {}).get("tools") or []
            result.callable = True
            result.capabilities = [
                {
                    "kind": "mcp_tool",
                    "name": str(t.get("name", "")).strip(),
                    "spec": {"description": t.get("description", "")},
                }
                for t in tools
                if t.get("name")
            ]
        except Exception as exc:  # noqa: BLE001
            result.failure_dim = result.failure_dim or "callable"
            result.failure_reason = (
                result.failure_reason or f"stdio probe error: {type(exc).__name__}"
            )
        finally:
            if proc is not None and proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
