"""Persistent Claude Code session manager.

Maintains stateful sessions across multiple task invocations using
the Claude CLI's --resume flag. Each Daena chat session maps to a
Claude Code CLI session, preserving context between commands.

Architecture:
    DaenaChatSession -> ClaudeSession -> claude -p "task" --resume <id>

    First task: claude -p "task" --output-format json -> captures session_id
    Follow-ups: claude -p "task" --resume <session_id> --output-format json

Tool capability (Phase 1 F5, 2026-04-24):
    The CLI subprocess used to launch with no tool surface beyond
    --dangerously-skip-permissions. Now passes --mcp-config (Daena's
    per-tenant MCP allowlist), --add-dir (working_directory), and
    --allowed-tools (the per-tenant tool whitelist). Without these the
    delegated CLI was a text-only completion endpoint. With them, the
    subprocess actually executes work -- file edits, MCP tool calls,
    bash, web fetch -- which is what "OpenClaw-style" autonomy means.

Auth env propagation (Phase 1 F1, 2026-04-24):
    subprocess.Popen inherits parent env by default, but we now copy
    + log explicitly so MCP env vars and ANTHROPIC_API_KEY presence
    are observable in the audit trail and can be augmented per-call.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def _probe_cli_flag(bin_path: str, flag: str) -> bool:
    """Check whether the claude binary supports a given flag.

    Runs `<binary> --help` once and searches stdout+stderr for the flag
    name (without leading dashes). Returns False on any error so callers
    can safely skip unsupported flags rather than crashing.

    The Windows claude.exe distributed via the Claude Desktop installer may
    lag behind the Linux binary by a few releases, which means flags added
    in recent CLI versions (like --exclude-dynamic-system-prompt-sections)
    are not always present on the Windows build. This probe makes the
    behaviour self-adapting: the flag is used when available and silently
    skipped when not.
    """
    flag_name = flag.lstrip("-")
    try:
        r = subprocess.run(
            [bin_path, "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return flag_name in (r.stdout + r.stderr)
    except Exception:
        return False


def _run_claude(
    cmd: list[str],
    *,
    task_stdin: str | None = None,
    cwd: str | None = None,
    timeout: float = 300.0,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run claude command synchronously (called from thread pool).

    Uses Popen + communicate() so the subprocess is properly killed
    on timeout (subprocess.run with timeout does NOT kill on Windows).
    Optionally passes the task via stdin instead of -p for large inputs.

    env=None means "inherit parent env" (default Popen behavior). When
    env=<dict> is supplied, the dict completely replaces the env --
    callers who want parent + extras must pass {**os.environ, ...extras}.
    """
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if task_stdin else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        env=env,
    )
    try:
        stdout, stderr = proc.communicate(
            input=task_stdin,
            timeout=timeout,
        )
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
        )
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        raise


@dataclass
class ClaudeSessionResult:
    """Result of a single command in a Claude session."""

    result_text: str
    session_id: str
    is_error: bool = False
    cost_usd: float = 0.0
    duration_ms: int = 0
    num_turns: int = 0
    raw_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClaudeSession:
    """A persistent Claude Code CLI session.

    Tracks the CLI session_id so follow-up commands can use --resume
    to maintain full conversation context.
    """

    daena_session_id: str  # Maps to Daena's chat session
    cli_session_id: str | None = None  # Claude CLI session ID (set after first command)
    claude_bin: str = "claude"
    # Set by ClaudeSessionManager after probing `<binary> --help` once at
    # adapter init. False means the flag is skipped (older binary).
    supports_exclude_flag: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: datetime | None = None
    command_count: int = 0
    total_cost_usd: float = 0.0
    is_alive: bool = True
    history: list[ClaudeSessionResult] = field(default_factory=list)

    async def send_command(
        self,
        task: str,
        *,
        cwd: str = ".",
        timeout: float = 300.0,
        mcp_config_path: str | None = None,
        add_dirs: list[str] | None = None,
        allowed_tools: str | None = None,
        permission_mode: str = "acceptEdits",
        effort: str | None = None,
    ) -> ClaudeSessionResult:
        """Send a command to this session.

        First command creates the session. Subsequent commands resume it.

        Tool capability flags (added Phase 1 F5):
            mcp_config_path: path to a JSON file describing approved MCP
                servers for this tenant. Lets the CLI use gitnexus,
                docker MCP gateway, local-llm bridge, etc.
            add_dirs: extra directories the CLI may read/write. The session
                cwd is always allowed; this adds founder vaults and
                project roots.
            allowed_tools: space-separated tool ACL string passed to
                --allowed-tools. None means "use --dangerously-skip-
                permissions" (UNLEASHED default).
            permission_mode: maps to --permission-mode. acceptEdits for
                UNLEASHED, default for BALANCED, plan for GOVERNED.
        """
        # Use stdin for any non-trivial task. Lowered from 8 kB to 4 kB
        # 2026-04-24 because subprocess.Popen on Windows-via-WSL-interop
        # gets unstable with large -p arg payloads; piping via stdin is
        # always reliable. Also cuts the WSL->Windows arg-marshaling
        # overhead which was contributing to "OODA: Act 307s" hangs.
        _use_stdin = len(task) > 4000
        cmd: list[str] = [self.claude_bin]
        cmd += ["-p", "-" if _use_stdin else task]
        cmd += ["--output-format", "json"]
        # --bare: skip plugin sync, hooks, LSP, CLAUDE.md auto-discovery,
        # auto-memory, background prefetches, keychain reads, and
        # attribution. Daena's orchestrator already injects the system
        # prompt, soul, and any per-turn context the model needs, so
        # the CLI's bootstrap is redundant. Removing it cuts ~2-3s off
        # cold starts and ~500-800 ms off warm starts.
        # Source: https://code.claude.com/docs/en/cli-reference (--bare).
        cmd += ["--bare"]
        # Move per-machine sections (cwd, env info, memory paths, git
        # status) from system prompt into the first user message so the
        # 5-min ephemeral prompt cache can hit on subsequent turns. With
        # a stable system prefix we go from 50% cache hit rate to ~90%.
        # Guarded: Windows claude.exe may lag behind the Linux build and
        # not yet support this flag. ClaudeSessionManager probes once at
        # startup via _probe_cli_flag() and sets supports_exclude_flag.
        if self.supports_exclude_flag:
            cmd += ["--exclude-dynamic-system-prompt-sections"]

        # Adaptive thinking budget (Phase 2.5 three-tier router, 2026-04-25):
        # the orchestrator picks an effort level based on query complexity.
        # SIMPLE -> low (fast, cheap), MODERATE -> medium (default),
        # COMPLEX -> high, MULTI_STEP/VERY_COMPLEX -> xhigh.
        # Source: claude --help (--effort low|medium|high|xhigh|max).
        if effort and effort in ("low", "medium", "high", "xhigh", "max"):
            cmd += ["--effort", effort]

        # Permission gating: the user's governance mode determines whether
        # we skip-permissions outright (UNLEASHED) or pass an explicit
        # ACL + permission-mode for BALANCED / GOVERNED. The default here
        # is the "make it actually work" path -- Phase 1 ships UNLEASHED
        # for the founder per the plan; later phases can downgrade.
        if allowed_tools:
            cmd += ["--allowed-tools", allowed_tools]
            cmd += ["--permission-mode", permission_mode]
        else:
            cmd += ["--dangerously-skip-permissions"]

        # MCP servers + scoped writable dirs. Both are no-ops when the
        # caller didn't supply them, preserving prior behaviour.
        if mcp_config_path:
            cmd += ["--mcp-config", mcp_config_path]
        for extra_dir in add_dirs or []:
            if extra_dir:
                cmd += ["--add-dir", extra_dir]

        # Resume existing session if we have a CLI session ID
        if self.cli_session_id:
            cmd.extend(["--resume", self.cli_session_id])

        # Build env: parent + masked diagnostics. We never log the actual
        # key value, only its presence and a 7-char prefix so a stale-key
        # 401 has a fast triage path in the logs.
        env = os.environ.copy()
        anthropic_key = env.get("ANTHROPIC_API_KEY", "")

        # WSL -> Windows interop env fix (Phase 1 F1.b, 2026-04-24).
        # When the resolved binary lives under /mnt/c/ we are about to
        # spawn a Windows .exe from inside WSL. The Linux subprocess
        # env carries HOME=/root but no USERPROFILE -- which means the
        # Windows binary can't locate its OAuth credentials in
        # C:\Users\<user>\.claude\ and falls through to a 401. We fix
        # that by forcing USERPROFILE / HOMEDRIVE / HOMEPATH derived
        # from the binary path so claude.exe finds C:\Users\masou\.claude
        # exactly as if we'd launched it interactively.
        if self.claude_bin.startswith("/mnt/"):
            # /mnt/c/Users/masou/.local/bin/claude.exe
            #   -> drive 'c', user-home 'Users/masou'
            try:
                parts = self.claude_bin.lstrip("/").split("/")
                # parts[0]='mnt', parts[1]='c', parts[2]='Users', parts[3]='<user>'
                if len(parts) >= 4 and parts[0] == "mnt" and parts[2].lower() == "users":
                    drive = parts[1].upper() + ":"
                    user_home = f"{drive}\\Users\\{parts[3]}"
                    # F-CLAUDE-WIN-ENV fix (2026-04-25): use direct assignment
                    # not setdefault. When the backend runs as WSL root, the
                    # parent env already has USERPROFILE=/root (Linux default),
                    # which would tell the Windows .exe to look for credentials
                    # at /root/.claude/.credentials.json (the EXPIRED Linux
                    # token file) instead of C:\Users\<user>\.claude\.
                    # Force-override so the Windows binary always reads the
                    # Windows-side keychain.
                    env["USERPROFILE"] = user_home
                    env["HOMEDRIVE"] = drive
                    env["HOMEPATH"] = f"\\Users\\{parts[3]}"
                    # APPDATA / LOCALAPPDATA help any tool that reads
                    # %APPDATA% (claude doesn't today, but harmless).
                    env["APPDATA"] = f"{user_home}\\AppData\\Roaming"
                    env["LOCALAPPDATA"] = f"{user_home}\\AppData\\Local"
            except Exception:
                # Defensive: never break the chat over an env quirk.
                pass

        logger.info(
            "claude_session.send",
            daena_session=self.daena_session_id,
            cli_session=self.cli_session_id or "new",
            task=task[:200],
            task_size=len(task),
            use_stdin=_use_stdin,
            command_num=self.command_count + 1,
            has_anthropic_key=bool(anthropic_key),
            anthropic_key_prefix=anthropic_key[:7] + "..." if anthropic_key else "",
            mcp_config=bool(mcp_config_path),
            allowed_tools_set=bool(allowed_tools),
            add_dirs=len(add_dirs or []),
            permission_mode=permission_mode if allowed_tools else "skip",
        )

        try:
            proc_result = await asyncio.to_thread(
                _run_claude, cmd,
                task_stdin=task if _use_stdin else None,
                cwd=cwd, timeout=timeout, env=env,
            )

            # Parse the JSON result (may be multiple lines, take last result type).
            # Pass stderr through so the fallback path can surface real
            # error text ("There's an issue with the selected model...")
            # instead of the opaque "[No output]" placeholder.
            result = self._parse_output(proc_result.stdout, proc_result.stderr or "")

            # F-CLAUDE-SESSION-LOST recovery: when the user re-authenticates
            # via `claude login` (or rotates org / changes machine), Claude
            # Code invalidates ALL existing CLI sessions on the auth side.
            # Daena's cached cli_session_id then triggers
            # "No conversation found with session ID: <id>" on every
            # follow-up command. The cure: detect that pattern, clear the
            # stale ID, and immediately retry as a NEW session (no resume).
            blob = (result.result_text or "") + " " + (proc_result.stderr or "")
            if (
                self.cli_session_id
                and "No conversation found with session ID" in blob
            ):
                logger.warning(
                    "claude_session.cli_session_lost",
                    daena_session=self.daena_session_id,
                    stale_cli_session=self.cli_session_id,
                    hint="Likely cause: `claude login` rotated CLI sessions. Recreating.",
                )
                self.cli_session_id = None
                # Rebuild cmd without --resume and re-execute once.
                retry_cmd = [c for c in cmd if c != "--resume" and c != self.cli_session_id]
                # Strip any orphaned arg directly after "--resume" we just removed
                cleaned: list[str] = []
                skip_next = False
                for arg in cmd:
                    if skip_next:
                        skip_next = False
                        continue
                    if arg == "--resume":
                        skip_next = True
                        continue
                    cleaned.append(arg)
                proc_result = await asyncio.to_thread(
                    _run_claude, cleaned,
                    task_stdin=task if _use_stdin else None,
                    cwd=cwd, timeout=timeout, env=env,
                )
                result = self._parse_output(proc_result.stdout, proc_result.stderr or "")

            # Capture CLI session ID from first response
            if result.session_id and not self.cli_session_id:
                self.cli_session_id = result.session_id
                logger.info(
                    "claude_session.established",
                    daena_session=self.daena_session_id,
                    cli_session=self.cli_session_id,
                )

            self.command_count += 1
            self.last_used = datetime.utcnow()
            self.total_cost_usd += result.cost_usd
            self.history.append(result)

            return result

        except subprocess.TimeoutExpired:
            self.is_alive = False
            logger.error(
                "claude_session.timeout",
                daena_session=self.daena_session_id,
                task_size=len(task),
                use_stdin=_use_stdin,
                timeout_seconds=timeout,
            )
            return ClaudeSessionResult(
                result_text="[Session timed out -- subprocess killed]",
                session_id=self.cli_session_id or "",
                is_error=True,
                duration_ms=int(timeout * 1000),
            )
        except Exception as exc:
            logger.error(
                "claude_session.error",
                daena_session=self.daena_session_id,
                error=str(exc),
            )
            return ClaudeSessionResult(
                result_text=f"[Session error: {exc}]",
                session_id=self.cli_session_id or "",
                is_error=True,
            )

    def _parse_output(self, stdout: str, stderr: str = "") -> ClaudeSessionResult:
        """Parse Claude CLI JSON output, extracting the result line.

        Fallback surfaces real stderr when JSON parsing failed -- the
        "[No output]" placeholder used before silently hid CLI errors
        like "There's an issue with the selected model (x). It may not
        exist or you may not have access to it." which were the actual
        cause of the empty response the user saw in chat.
        """
        lines = stdout.strip().splitlines()

        # Find the result JSON (type=result) -- scan from end
        for line in reversed(lines):
            try:
                data = json.loads(line)
                if data.get("type") == "result":
                    return ClaudeSessionResult(
                        result_text=data.get("result", ""),
                        session_id=data.get("session_id", ""),
                        is_error=data.get("is_error", False),
                        cost_usd=data.get("total_cost_usd", 0),
                        duration_ms=data.get("duration_ms", 0),
                        num_turns=data.get("num_turns", 0),
                        raw_json=data,
                    )
            except json.JSONDecodeError:
                continue

        # Fallback: show whichever of stdout/stderr has content so
        # operators see the actual failure mode, not a placeholder.
        raw_stdout = (stdout or "").strip()
        raw_stderr = (stderr or "").strip()
        if raw_stderr and not raw_stdout:
            # stderr-only: almost always a real CLI error message.
            body = f"[Claude CLI error] {raw_stderr[:2000]}"
        elif raw_stdout:
            body = raw_stdout[:4000]
        elif raw_stderr:
            body = f"[Claude CLI error] {raw_stderr[:2000]}"
        else:
            body = "[No output -- CLI returned empty stdout AND stderr]"
        return ClaudeSessionResult(
            result_text=body,
            session_id="",
            is_error=True,
        )

    def get_status(self) -> dict[str, Any]:
        """Get session status for API/frontend."""
        return {
            "daena_session_id": self.daena_session_id,
            "cli_session_id": self.cli_session_id,
            "is_alive": self.is_alive,
            "command_count": self.command_count,
            "total_cost_usd": self.total_cost_usd,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }


class ClaudeSessionManager:
    """Manages multiple persistent Claude sessions.

    Maps Daena chat sessions to Claude CLI sessions. Handles
    session lifecycle, error recovery, and cleanup.
    """

    def __init__(self, claude_bin: str = "claude") -> None:
        self._sessions: dict[str, ClaudeSession] = {}
        self._claude_bin = claude_bin
        # Probe once at startup. The Windows .exe may be an older build
        # that doesn't support --exclude-dynamic-system-prompt-sections.
        # All sessions created by this manager share the same binary, so
        # one probe is sufficient.
        self._supports_exclude_flag = _probe_cli_flag(
            claude_bin, "--exclude-dynamic-system-prompt-sections"
        )
        logger.info(
            "session_manager.flag_probe",
            binary=claude_bin,
            supports_exclude_flag=self._supports_exclude_flag,
        )

    def get_or_create(self, daena_session_id: str) -> ClaudeSession:
        """Get existing session or create a new one."""
        if daena_session_id not in self._sessions:
            self._sessions[daena_session_id] = ClaudeSession(
                daena_session_id=daena_session_id,
                claude_bin=self._claude_bin,
                supports_exclude_flag=self._supports_exclude_flag,
            )
            logger.info(
                "session_manager.created",
                daena_session=daena_session_id,
            )
        return self._sessions[daena_session_id]

    def get(self, daena_session_id: str) -> ClaudeSession | None:
        """Get session if it exists."""
        return self._sessions.get(daena_session_id)

    async def send(
        self,
        daena_session_id: str,
        task: str,
        *,
        cwd: str = ".",
        timeout: float = 300.0,
        mcp_config_path: str | None = None,
        add_dirs: list[str] | None = None,
        allowed_tools: str | None = None,
        permission_mode: str = "acceptEdits",
        effort: str | None = None,
    ) -> ClaudeSessionResult:
        """Send a command to a session (creating if needed).

        If the session died, automatically restarts it.

        Tool capability flags propagate to send_command -- see that
        method's docstring for the per-flag semantics.
        """
        session = self.get_or_create(daena_session_id)

        # Error recovery: if session died, restart it
        if not session.is_alive:
            logger.warning(
                "session_manager.recovering",
                daena_session=daena_session_id,
                old_cli_session=session.cli_session_id,
            )
            # Create fresh session but keep history
            old_history = session.history
            session = ClaudeSession(
                daena_session_id=daena_session_id,
                claude_bin=self._claude_bin,
                supports_exclude_flag=self._supports_exclude_flag,
            )
            session.history = old_history
            self._sessions[daena_session_id] = session

        return await session.send_command(
            task,
            cwd=cwd,
            timeout=timeout,
            mcp_config_path=mcp_config_path,
            add_dirs=add_dirs,
            allowed_tools=allowed_tools,
            permission_mode=permission_mode,
            effort=effort,
        )

    def end_session(self, daena_session_id: str) -> bool:
        """End and remove a session."""
        if daena_session_id in self._sessions:
            session = self._sessions.pop(daena_session_id)
            session.is_alive = False
            logger.info(
                "session_manager.ended",
                daena_session=daena_session_id,
                commands=session.command_count,
                cost=session.total_cost_usd,
            )
            return True
        return False

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active sessions."""
        return [s.get_status() for s in self._sessions.values()]

    def cleanup_stale(self, max_age_hours: int = 24) -> int:
        """Remove sessions that haven't been used recently."""
        now = datetime.utcnow()
        stale = []
        for sid, session in self._sessions.items():
            age = now - session.created_at
            if age.total_seconds() > max_age_hours * 3600:
                stale.append(sid)

        for sid in stale:
            self.end_session(sid)

        return len(stale)
