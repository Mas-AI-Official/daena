"""TerminalAgent — governed shell command execution.

Executes commands in a sandboxed subprocess with mandatory timeouts
(Hard Law #3).  Dangerous commands (rm, format, shutdown …) are
classified at CRITICAL risk so governance blocks or requires approval.

All output (stdout, stderr, return code) is captured and returned.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.core.logging import get_logger
from app.services.daenabot._base_agent import BaseAgent

logger = get_logger(__name__)

# Commands that are destructive — governance action_type = DELETE (CRITICAL)
DANGEROUS_COMMANDS: frozenset[str] = frozenset({
    "rm", "rmdir", "del", "erase",
    "format", "mkfs", "dd",
    "shutdown", "reboot", "halt", "poweroff",
    "fdisk", "diskpart",
    "kill", "taskkill", "pkill", "killall",
    "reg", "regedit",
    "net", "sc",
    "chmod", "chown",  # permission changes can be destructive
})

# Commands that only read state — governance action_type = READ (NONE)
READ_ONLY_COMMANDS: frozenset[str] = frozenset({
    "ls", "dir", "cat", "type", "echo", "print",
    "pwd", "cd",
    "whoami", "hostname", "date", "time",
    "head", "tail", "wc", "sort", "uniq",
    "find", "grep", "rg", "ag",
    "which", "where", "whereis",
    "env", "printenv", "set",
    "uname", "df", "du", "free",
    "ps", "top", "htop",
    "systeminfo", "ver", "lsb_release",
    "git", "node", "python", "pip",  # read-only invocations
})


class TerminalAgent(BaseAgent):
    """Governed shell-command agent for Daena's EXE mode."""

    agent_name = "terminal"

    OPERATION_ACTION_MAP: dict[str, str] = {
        "execute_command": "EXECUTE",  # default; refined by classify_command_risk
    }

    def __init__(
        self,
        default_timeout: int = 30,
        max_timeout: int = 300,
        allowed_cwd: str | None = None,
    ) -> None:
        self.default_timeout = default_timeout
        self.max_timeout = max_timeout
        self.allowed_cwd = allowed_cwd

    # ── dispatch ───────────────────────────────────────────────

    async def execute(
        self, operation: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        if operation != "execute_command":
            raise ValueError(
                f"TerminalAgent: unknown operation '{operation}'. "
                f"Supported: ['execute_command']"
            )
        return await self.execute_command(**params)

    # ── main operation ─────────────────────────────────────────

    async def execute_command(
        self,
        command: str,
        timeout: int | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute a shell command in a subprocess.

        Args:
            command: The shell command string to execute.
            timeout: Max seconds (clamped to ``max_timeout``).
                     Defaults to ``default_timeout``.
            cwd: Working directory (validated if ``allowed_cwd`` set).
            env: Extra environment variables merged on top of minimal env.

        Returns:
            Result dict with stdout, stderr, return_code, duration_ms.
        """
        # Hard Law #3: mandatory timeout
        effective_timeout = min(
            timeout if timeout is not None else self.default_timeout,
            self.max_timeout,
        )

        # Validate cwd
        if cwd and self.allowed_cwd:
            from pathlib import Path
            resolved_cwd = Path(cwd).resolve()
            allowed = Path(self.allowed_cwd).resolve()
            try:
                resolved_cwd.relative_to(allowed)
            except ValueError:
                return self._error(
                    "execute_command",
                    f"Working directory '{cwd}' outside allowed path '{self.allowed_cwd}'",
                )

        start = time.monotonic()
        timed_out = False

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=effective_timeout,
                )
            except TimeoutError:
                timed_out = True
                proc.kill()
                stdout_bytes, stderr_bytes = await proc.communicate()

            duration_ms = int((time.monotonic() - start) * 1000)
            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

            logger.info(
                "terminal_agent.executed",
                command=command[:100],
                return_code=proc.returncode,
                timed_out=timed_out,
                duration_ms=duration_ms,
            )

            return self._result("execute_command", {
                "command": command,
                "stdout": stdout,
                "stderr": stderr,
                "return_code": proc.returncode,
                "timed_out": timed_out,
                "duration_ms": duration_ms,
            })

        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception("terminal_agent.error", command=command[:100])
            return self._error(
                "execute_command",
                f"Command execution failed: {exc}",
            )

    # ── risk classification ────────────────────────────────────

    @classmethod
    def classify_command_risk(cls, command: str) -> str:
        """Classify a command's governance action_type.

        Called by ``_resolve_action_type()`` BEFORE governance so the
        correct risk level is evaluated.

        Returns:
            ``"DELETE"`` for dangerous commands (CRITICAL risk),
            ``"READ"`` for read-only commands (NONE risk),
            ``"EXECUTE"`` for everything else (MEDIUM risk).
        """
        first_token = cls._extract_first_token(command)
        if not first_token:
            return "EXECUTE"

        token_lower = first_token.lower()

        if token_lower in DANGEROUS_COMMANDS:
            return "DELETE"
        if token_lower in READ_ONLY_COMMANDS:
            return "READ"
        return "EXECUTE"

    @staticmethod
    def _extract_first_token(command: str) -> str:
        """Extract the first meaningful token from a command string."""
        stripped = command.strip()
        if not stripped:
            return ""
        # Handle env var prefixes like "FOO=bar command"
        # Handle sudo/doas prefix
        tokens = stripped.split()
        for token in tokens:
            if "=" in token:
                continue  # skip env assignments
            if token in ("sudo", "doas"):
                continue  # skip privilege escalation prefix
            return token.split("/")[-1]  # basename only
        return tokens[-1] if tokens else ""
