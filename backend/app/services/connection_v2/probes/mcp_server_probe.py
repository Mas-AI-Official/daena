"""McpServerProbe -- real MCP initialize + tools/list probe for V2 rows.

PR-CONN-MCP-PROBE (2026-05-02): replaces the default
``probe_unavailable`` outcome for ``kind=mcp_server`` rows with an
actual JSON-RPC handshake against the configured MCP server. Uses the
official ``mcp`` Python SDK (already installed for the chat
orchestrator's ``mcp_invoker``) so we don't reinvent the protocol.

Truth ladder for an MCP server:
  1. detected   = config has command + args (or url for http/sse)
  2. configured = command exists on PATH and discovery imported the row
  3. reachable  = subprocess spawned, JSON-RPC initialize round-trip ok
  4. authenticated = (folded into initialize for stdio MCPs)
  5. callable   = tools/list returned at least one tool

Hard rules honored (founder):
  * NEVER auto-installs missing packages -- missing binary returns
    ``binary_not_found``, not a silent npm install.
  * NEVER returns env VALUES; ``env_var_names`` reflects what the
    catalog declared, NEVER copies from the live process env.
  * NEVER logs env values; structured logs emit name lists only.
  * Bounded by per-step timeouts so a hanging MCP cannot block the
    request indefinitely.
  * Process-tree cleanup on timeout (kills children too on POSIX +
    best-effort on Windows).
  * stdio only -- HTTP / SSE transports return a structured
    ``unsupported_transport`` failure (no 500).

Failure states (one of these always lands in ``failure_reason``):
  - binary_not_found
  - command_failed
  - initialize_timeout
  - initialize_failed
  - tools_list_timeout
  - tools_list_failed
  - no_tools
  - unsupported_transport
  - config_missing

On success: ``ProbeResult(success=True, capabilities=[{name, kind, spec}])``
Capabilities flow into ``ConnectionV2Capability`` rows via
``ConnectionRegistryV2.probe_and_record``.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.core.logging import get_logger
from app.models.connection_v2 import ConnectionKind, ConnectionV2
from app.services.connection_v2.probe import Probe, ProbeResult

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────
# Timeouts (per-step, all bounded)
# ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class McpProbeTimeouts:
    """Per-step ceilings. Total worst case = sum of all four."""

    spawn: float = 8.0          # process spawn + first byte
    initialize: float = 8.0     # MCP initialize round-trip
    tools_list: float = 8.0     # tools/list round-trip
    cleanup: float = 5.0        # graceful close window before kill


DEFAULT_TIMEOUTS = McpProbeTimeouts()


# Failure-reason prefixes the frontend can match on without parsing
# free-form text. Each prefix maps 1:1 to the founder-listed states.
FAIL_BINARY_NOT_FOUND = "binary_not_found"
FAIL_COMMAND_FAILED = "command_failed"
FAIL_INITIALIZE_TIMEOUT = "initialize_timeout"
FAIL_INITIALIZE_FAILED = "initialize_failed"
FAIL_TOOLS_LIST_TIMEOUT = "tools_list_timeout"
FAIL_TOOLS_LIST_FAILED = "tools_list_failed"
FAIL_NO_TOOLS = "no_tools"
FAIL_UNSUPPORTED_TRANSPORT = "unsupported_transport"
FAIL_CONFIG_MISSING = "config_missing"


# Most stderr / message strings have wildcards; cap at this length so
# failure_reason never bloats the DB column.
_REASON_PREVIEW = 240


def _reason(prefix: str, detail: str = "") -> str:
    """Compose a structured failure reason: ``prefix: detail (truncated)``."""
    if not detail:
        return prefix
    cleaned = detail.replace("\n", " ").replace("\r", " ").strip()
    if len(cleaned) > _REASON_PREVIEW:
        cleaned = cleaned[:_REASON_PREVIEW] + "..."
    return f"{prefix}: {cleaned}"


# ──────────────────────────────────────────────────────────────────
# Env passthrough (NAMES from catalog, VALUES from os.environ only)
# ──────────────────────────────────────────────────────────────────
#
# We DELIBERATELY do not read the source CLI's config file at probe
# time. The seeders.py importer captured env_var_names but never
# copied values; the live process env is the ONLY value source.
#
# Rationale: re-reading claude_desktop_config.json mid-probe would
# pull operator-managed secrets into Daena's process memory. The
# operator can either set the env vars in Daena's env, OR a future
# PR can add an explicit "use my CLI's secrets" opt-in flow.


def _build_env(row: ConnectionV2) -> tuple[dict[str, str], list[str]]:
    """Build the subprocess env from os.environ matching env_var_names.

    Returns (env_dict, missing_names). The env_dict is keyed by the
    NAMES the catalog declared; values come from os.environ ONLY.
    Missing names are reported but NOT considered a hard failure --
    many MCPs are happy to start without their env vars set and will
    surface a clearer auth error after initialize.
    """
    config: dict[str, Any] = row.config or {}
    declared_names: list[str] = list(config.get("env_var_names") or [])

    env: dict[str, str] = {}
    missing: list[str] = []
    parent_env = os.environ
    for name in declared_names:
        value = parent_env.get(name)
        if value:
            env[name] = value
        else:
            missing.append(name)

    # Always passthrough PATH + minimal vars so the subprocess can
    # find npx / node / python / uv etc. Without PATH, npx -y fails
    # with ENOENT before MCP even starts.
    for passthrough in ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"):
        if passthrough in parent_env and passthrough not in env:
            env[passthrough] = parent_env[passthrough]

    return env, missing


# ──────────────────────────────────────────────────────────────────
# Transport gating
# ──────────────────────────────────────────────────────────────────


def _is_stdio_transport(config: dict[str, Any]) -> bool:
    """True only if the row's config describes a stdio MCP we can spawn."""
    kind = (config.get("kind") or "").lower()
    if kind in {"mcp_stdio", "stdio"}:
        return True
    # Heuristic: command + no url -> stdio.
    if config.get("command") and not config.get("url"):
        return True
    return False


def _resolve_command(config: dict[str, Any]) -> str | None:
    """Resolve the launch command using shutil.which.

    Returns the absolute path, or None when the binary is not on PATH.
    Accepts the raw command exactly as the catalog declares it -- the
    Daena seeder + catalog ship strings (`npx`, `python`, `node`),
    never shell pipelines.
    """
    raw = config.get("command")
    if not raw:
        return None
    if not isinstance(raw, str):
        return None
    # Reject anything that smells like a shell pipeline.
    if any(ch in raw for ch in (";", "&", "|", ">", "<", "`", "$(")):
        return None
    resolved = shutil.which(raw)
    return resolved or raw if os.path.isabs(raw) else resolved


def _normalize_args(config: dict[str, Any]) -> list[str]:
    raw = config.get("args") or []
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(a) for a in raw]


# ──────────────────────────────────────────────────────────────────
# Probe
# ──────────────────────────────────────────────────────────────────


class McpServerProbe(Probe):
    """Real stdio MCP probe (initialize + tools/list).

    Implementations details:
      * Spawn via the official ``mcp`` SDK's ``stdio_client`` context
        manager. The SDK handles framing + cleanup + child-process
        teardown on context exit.
      * Each step (spawn-to-initialize, initialize-to-handshake-done,
        tools/list) is wrapped in ``asyncio.wait_for`` so a hung MCP
        does not block the request.
      * Empty tools list is treated as ``no_tools`` failure -- per
        founder spec, ``callable=True`` requires the server to expose
        at least one usable tool.
    """

    kind = ConnectionKind.MCP_SERVER

    def __init__(self, timeouts: McpProbeTimeouts | None = None) -> None:
        self.timeouts = timeouts or DEFAULT_TIMEOUTS

    async def run(self, row: ConnectionV2) -> ProbeResult:
        config: dict[str, Any] = row.config or {}

        # ── Transport gate ──
        if not _is_stdio_transport(config):
            return ProbeResult(
                success=False,
                failure_dim="reachable",
                failure_reason=_reason(
                    FAIL_UNSUPPORTED_TRANSPORT,
                    "only stdio MCP is supported in this probe; "
                    "http / sse transports require a future PR",
                ),
            )

        # ── Config gate ──
        if not config.get("command"):
            return ProbeResult(
                success=False,
                failure_dim="configured",
                failure_reason=_reason(
                    FAIL_CONFIG_MISSING,
                    "command is empty -- expected stdio MCP launch path",
                ),
            )

        resolved = _resolve_command(config)
        if not resolved:
            # Sprint-9 PR-2 honesty polish: the bare "not found on PATH"
            # message left the operator stuck. Spell out what to install
            # for the most common bins so the error is actionable.
            cmd = config.get("command", "")
            hint = ""
            if cmd in ("npx", "npm", "node"):
                hint = " Install Node.js (https://nodejs.org) or ensure npx is on PATH."
            elif cmd in ("uvx", "uv"):
                hint = " Install uv (https://docs.astral.sh/uv) or ensure uvx is on PATH."
            elif cmd == "docker":
                hint = " Install Docker Desktop or ensure docker is on PATH."
            elif cmd in ("python", "python3", "pip", "pipx"):
                hint = " Ensure Python is on PATH."
            return ProbeResult(
                success=False,
                failure_dim="reachable",
                failure_reason=_reason(
                    FAIL_BINARY_NOT_FOUND,
                    f"command {cmd!r} not found on PATH.{hint}",
                ),
            )

        args = _normalize_args(config)
        env, missing_env = _build_env(row)

        # Structured log -- env_var_names ONLY, never values.
        logger.info(
            "mcp_probe.starting",
            connection_id=str(row.id),
            slug=row.slug,
            command=resolved,
            args_count=len(args),
            env_present_names=sorted(env.keys()),
            env_missing_names=sorted(missing_env),
        )

        params = StdioServerParameters(
            command=resolved,
            args=args,
            env=env,
        )

        try:
            return await self._handshake(params, row)
        except Exception as exc:  # noqa: BLE001 - probe contract: never raise
            logger.warning(
                "mcp_probe.unhandled_failure",
                connection_id=str(row.id),
                slug=row.slug,
                error_type=type(exc).__name__,
            )
            return ProbeResult(
                success=False,
                failure_dim="callable",
                failure_reason=_reason(
                    FAIL_COMMAND_FAILED,
                    f"{type(exc).__name__}: {str(exc)[:160]}",
                ),
            )

    async def _handshake(
        self, params: StdioServerParameters, row: ConnectionV2,
    ) -> ProbeResult:
        """Perform the MCP initialize + tools/list handshake.

        Total worst-case time: spawn + initialize + tools_list +
        cleanup. The cleanup happens implicitly via the async-context
        managers when ``stdio_client`` exits.
        """
        spawn_t = self.timeouts.spawn
        init_t = self.timeouts.initialize
        list_t = self.timeouts.tools_list

        async def _inner() -> ProbeResult:
            try:
                async with stdio_client(params) as (read, write):
                    try:
                        async with ClientSession(read, write) as session:
                            try:
                                await asyncio.wait_for(
                                    session.initialize(), timeout=init_t,
                                )
                            except asyncio.TimeoutError:
                                # Sprint-9 PR-2 honesty polish: a first-run
                                # MCP often spends 10-25s warming/caching the
                                # npm/uvx package. Tell the operator to retry
                                # in 10s instead of leaving them to guess.
                                return ProbeResult(
                                    success=False,
                                    failure_dim="reachable",
                                    failure_reason=_reason(
                                        FAIL_INITIALIZE_TIMEOUT,
                                        f"initialize did not complete in {init_t}s. "
                                        "Package may still be downloading/warming "
                                        "on first run. Retry probe in ~10s.",
                                    ),
                                )
                            except Exception as exc:  # noqa: BLE001
                                return ProbeResult(
                                    success=False,
                                    failure_dim="reachable",
                                    failure_reason=_reason(
                                        FAIL_INITIALIZE_FAILED,
                                        f"{type(exc).__name__}: {str(exc)[:160]}",
                                    ),
                                )

                            # initialize ok -> tools/list
                            try:
                                tools_resp = await asyncio.wait_for(
                                    session.list_tools(), timeout=list_t,
                                )
                            except asyncio.TimeoutError:
                                return ProbeResult(
                                    success=False,
                                    failure_dim="callable",
                                    failure_reason=_reason(
                                        FAIL_TOOLS_LIST_TIMEOUT,
                                        f"tools/list did not complete in {list_t}s",
                                    ),
                                )
                            except Exception as exc:  # noqa: BLE001
                                return ProbeResult(
                                    success=False,
                                    failure_dim="callable",
                                    failure_reason=_reason(
                                        FAIL_TOOLS_LIST_FAILED,
                                        f"{type(exc).__name__}: {str(exc)[:160]}",
                                    ),
                                )

                            tools = list(tools_resp.tools or [])
                            if not tools:
                                return ProbeResult(
                                    success=False,
                                    failure_dim="callable",
                                    failure_reason=_reason(
                                        FAIL_NO_TOOLS,
                                        "server initialized but exposed 0 tools",
                                    ),
                                )

                            return ProbeResult(
                                success=True,
                                capabilities=_capabilities_from_tools(tools),
                            )
                    except Exception as exc:  # noqa: BLE001
                        # Inner ClientSession failure -- treat as command
                        # failed if we never got past initialize. Errors
                        # from tools_list_*/initialize_*/no_tools branches
                        # already returned above.
                        return ProbeResult(
                            success=False,
                            failure_dim="reachable",
                            failure_reason=_reason(
                                FAIL_COMMAND_FAILED,
                                f"{type(exc).__name__}: {str(exc)[:160]}",
                            ),
                        )
            except Exception as exc:  # noqa: BLE001
                # stdio_client failure -- subprocess died before MCP
                # client could attach. Common cause: command exited with
                # error before reading stdin (missing dependency,
                # missing env var causing immediate crash).
                return ProbeResult(
                    success=False,
                    failure_dim="reachable",
                    failure_reason=_reason(
                        FAIL_COMMAND_FAILED,
                        f"{type(exc).__name__}: {str(exc)[:160]}",
                    ),
                )

        # Outermost wait_for covers the spawn budget. If the SDK
        # never makes it to initialize within spawn_t + init_t, we
        # still timeout cleanly. This guards against the SDK hanging
        # internally during the AnyIO connect dance.
        try:
            return await asyncio.wait_for(
                _inner(), timeout=spawn_t + init_t + list_t + 1.0,
            )
        except asyncio.TimeoutError:
            return ProbeResult(
                success=False,
                failure_dim="reachable",
                failure_reason=_reason(
                    FAIL_INITIALIZE_TIMEOUT,
                    f"total handshake exceeded {spawn_t + init_t + list_t + 1.0}s",
                ),
            )


def _capabilities_from_tools(tools: list[Any]) -> list[dict]:
    """Map MCP tool descriptors to ConnectionV2Capability rows.

    Each tool becomes one capability row keyed by ``name`` with
    ``kind="mcp_tool"`` and a small spec containing the description +
    input schema. NEVER copies env / token material -- tool descriptors
    only carry name + description + input schema.
    """
    out: list[dict] = []
    for t in tools:
        name = getattr(t, "name", None) or ""
        if not name:
            continue
        description = getattr(t, "description", None) or ""
        input_schema = getattr(t, "inputSchema", None)
        spec: dict[str, Any] = {"description": description}
        if isinstance(input_schema, dict):
            spec["input_schema"] = input_schema
        out.append({
            "name": str(name),
            "kind": "mcp_tool",
            "spec": spec,
        })
    return out


def install_mcp_server_probe(timeouts: McpProbeTimeouts | None = None) -> None:
    """Register the McpServerProbe. Idempotent (last write wins)."""
    from app.services.connection_v2.probe import register_probe
    register_probe(McpServerProbe(timeouts=timeouts))


__all__ = [
    "DEFAULT_TIMEOUTS",
    "FAIL_BINARY_NOT_FOUND",
    "FAIL_COMMAND_FAILED",
    "FAIL_CONFIG_MISSING",
    "FAIL_INITIALIZE_FAILED",
    "FAIL_INITIALIZE_TIMEOUT",
    "FAIL_NO_TOOLS",
    "FAIL_TOOLS_LIST_FAILED",
    "FAIL_TOOLS_LIST_TIMEOUT",
    "FAIL_UNSUPPORTED_TRANSPORT",
    "McpProbeTimeouts",
    "McpServerProbe",
    "install_mcp_server_probe",
]
