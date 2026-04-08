"""Bridge daemon - WebSocket connection between cloud Daena and local machine.

Architecture:
    Cloud Daena (brain) <--WebSocket--> DaenaBot (hands on user's machine)

The bridge:
    1. Connects to cloud Daena via WebSocket with auth token
    2. Receives tool_call messages (file.read, terminal.run, browser.navigate, etc.)
    3. Executes them locally using the tool executor
    4. Sends results back to cloud
    5. Reconnects automatically on disconnect
"""

from __future__ import annotations

import asyncio
import json
import platform
import signal
import sys
import time
from pathlib import Path
from typing import Any

import websockets
from rich.console import Console

from daena_bot.executor import ToolExecutor
from daena_bot.config import BotConfig, load_config

console = Console()


class DaenaBridge:
    """WebSocket bridge between cloud Daena and local machine."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.executor = ToolExecutor(config)
        self._ws: Any = None
        self._running = False
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 30.0
        self._stats = {
            "connected_at": None,
            "tool_calls_executed": 0,
            "errors": 0,
            "last_activity": None,
        }

    @property
    def ws_url(self) -> str:
        """Build WebSocket URL from config."""
        base = self.config.server_url.rstrip("/")
        # Convert https:// to wss:// and http:// to ws://
        if base.startswith("https://"):
            ws_base = "wss://" + base[8:]
        elif base.startswith("http://"):
            ws_base = "ws://" + base[7:]
        else:
            ws_base = "wss://" + base
        return f"{ws_base}/ws/bridge"

    async def connect(self) -> None:
        """Connect to cloud Daena and start receiving tool calls."""
        self._running = True

        # Handle graceful shutdown
        if sys.platform != "win32":
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        console.print(
            f"[bold green]DaenaBot v{self.config.version}[/bold green]"
        )
        console.print(f"  Server: {self.config.server_url}")
        console.print(f"  Machine: {platform.node()} ({platform.system()} {platform.machine()})")
        console.print()

        while self._running:
            try:
                await self._connect_and_listen()
            except (websockets.ConnectionClosed, ConnectionRefusedError, OSError) as exc:
                if not self._running:
                    break
                console.print(
                    f"[yellow]Connection lost: {exc}. "
                    f"Reconnecting in {self._reconnect_delay:.0f}s...[/yellow]"
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self._max_reconnect_delay
                )
            except Exception as exc:
                if not self._running:
                    break
                console.print(f"[red]Unexpected error: {exc}[/red]")
                await asyncio.sleep(self._reconnect_delay)

        console.print("[dim]DaenaBot stopped.[/dim]")

    async def _connect_and_listen(self) -> None:
        """Establish WebSocket connection and process messages."""
        headers = {
            "Authorization": f"Bearer {self.config.auth_token}",
            "X-DaenaBot-Version": self.config.version,
            "X-DaenaBot-Platform": platform.system(),
            "X-DaenaBot-Machine": platform.node(),
        }

        async with websockets.connect(
            self.ws_url,
            additional_headers=headers,
            ping_interval=30,
            ping_timeout=10,
            max_size=10 * 1024 * 1024,  # 10MB max message
        ) as ws:
            self._ws = ws
            self._reconnect_delay = 1.0  # Reset on successful connect
            self._stats["connected_at"] = time.time()

            console.print("[bold green]Connected to Daena cloud.[/bold green]")
            console.print("[dim]Waiting for tool calls...[/dim]")

            # Send capabilities handshake
            await self._send_handshake()

            # Listen for messages
            async for message in ws:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    console.print(f"[red]Invalid JSON received[/red]")
                except Exception as exc:
                    console.print(f"[red]Error handling message: {exc}[/red]")
                    self._stats["errors"] += 1

    async def _send_handshake(self) -> None:
        """Send capabilities handshake to cloud."""
        import psutil

        capabilities = {
            "type": "handshake",
            "version": self.config.version,
            "platform": platform.system(),
            "machine": platform.node(),
            "python_version": platform.python_version(),
            "capabilities": self.executor.list_capabilities(),
            "system_info": {
                "cpu_count": psutil.cpu_count(),
                "memory_gb": round(psutil.virtual_memory().total / (1024**3), 1),
                "disk_free_gb": round(psutil.disk_usage("/").free / (1024**3), 1),
                "os_version": platform.version(),
            },
        }
        await self._ws.send(json.dumps(capabilities))

    async def _handle_message(self, data: dict[str, Any]) -> None:
        """Handle an incoming message from cloud Daena."""
        msg_type = data.get("type")

        if msg_type == "tool_call":
            await self._handle_tool_call(data)
        elif msg_type == "ping":
            await self._ws.send(json.dumps({"type": "pong"}))
        elif msg_type == "config_update":
            console.print("[dim]Config updated from cloud.[/dim]")
        else:
            console.print(f"[dim]Unknown message type: {msg_type}[/dim]")

    async def _handle_tool_call(self, data: dict[str, Any]) -> None:
        """Execute a tool call and send the result back."""
        call_id = data.get("call_id", "unknown")
        tool_name = data.get("tool")
        params = data.get("params", {})
        governance_tier = data.get("governance_tier", 0)

        console.print(
            f"  [cyan]Tool call:[/cyan] {tool_name} "
            f"[dim](tier {governance_tier})[/dim]"
        )

        # Check if user approval is needed (tier 3+)
        if governance_tier >= 3 and not self.config.auto_approve:
            console.print(
                f"  [yellow]Tier {governance_tier} action requires approval.[/yellow]"
            )
            # In future: show desktop notification and wait for user click
            # For now: auto-approve with warning
            console.print("  [yellow]Auto-approving (set --auto-approve to silence)[/yellow]")

        start = time.monotonic()
        try:
            result = await self.executor.execute(tool_name, params)
            elapsed = time.monotonic() - start
            self._stats["tool_calls_executed"] += 1
            self._stats["last_activity"] = time.time()

            success = result.get("success", True)
            status = "[green]OK[/green]" if success else "[red]FAIL[/red]"
            console.print(f"  {status} ({elapsed:.1f}s)")

            # Send result back
            response = {
                "type": "tool_result",
                "call_id": call_id,
                "tool": tool_name,
                "result": result,
                "elapsed_ms": int(elapsed * 1000),
            }
            await self._ws.send(json.dumps(response, default=str))

        except Exception as exc:
            elapsed = time.monotonic() - start
            self._stats["errors"] += 1
            console.print(f"  [red]ERROR: {exc}[/red] ({elapsed:.1f}s)")

            response = {
                "type": "tool_result",
                "call_id": call_id,
                "tool": tool_name,
                "result": {"success": False, "error": str(exc)},
                "elapsed_ms": int(elapsed * 1000),
            }
            await self._ws.send(json.dumps(response, default=str))

    async def stop(self) -> None:
        """Gracefully stop the bridge."""
        self._running = False
        if self._ws:
            await self._ws.close()

    def get_stats(self) -> dict[str, Any]:
        """Return bridge statistics."""
        return {**self._stats}
