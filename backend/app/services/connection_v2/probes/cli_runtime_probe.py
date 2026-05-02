"""CliRuntimeProbe -- safe binary + version + auth probe for CLI runtimes.

PR-CONN-CLI-PROBE (2026-05-02): replaces the default ``probe_unavailable``
outcome for ``kind=cli_runtime`` rows with a real probe that proves:

  1. Binary present (config["binary"] OR shutil.which(name))
  2. Version command works (when safe -- gemini's --version hangs
     unauthenticated, so its spec opts out)
  3. Auth status (per-runtime safe check; never runs prompts or model
     calls)

Truth ladder for a CLI runtime:
  1. detected   = binary resolves on PATH or config["binary"] is a real file
  2. configured = trivially True once detected
  3. reachable  = version command exits 0 within timeout (or skipped
                  for runtimes where --version is unsafe)
  4. authenticated = safe auth check returns AUTHENTICATED. NEVER
                     fake-true; if no safe check exists, returns
                     ``auth_unknown`` and authenticated stays False.
  5. callable   = detected + reachable + authenticated all true.

Hard rules honored (founder):
  * NEVER runs prompts or model calls. Founder brief explicitly bans
    round-trip pings here.
  * NEVER auto-installs. Missing binary returns ``binary_not_found``.
  * NEVER reads or returns OAuth tokens / API keys. Auth checks read
    JWT structure / file presence + expiration ONLY -- the token
    string never enters Daena's logs, capabilities, or failure_reason.
  * Bounded by per-step timeouts so a hung CLI cannot block the
    request indefinitely.
  * stderr is captured server-side ONLY -- it never enters
    ``failure_reason`` (Asset Shield Hard Law 5: data exfiltration).

Failure-reason prefixes (one of these always lands in
``failure_reason`` on a non-success result):

  - binary_not_found      -- shutil.which empty AND config["binary"] missing
  - version_failed        -- version command exited non-zero
  - version_timeout       -- version command hung past timeout
  - auth_unknown          -- runtime has no safe auth check (or auth check
                             raised an exception we cannot classify)
  - auth_failed           -- auth check ran and proved no/expired login
  - command_timeout       -- generic timeout (auth check, etc.)
  - unsupported_runtime   -- _runtime_id is not one we have a spec for
  - config_missing        -- row.config has no _runtime_id and no binary

On success: ``ProbeResult(success=True, capabilities=[{name, kind, spec}])``
The single capability row carries the runtime_id, version string (when
known), and auth_user_display (e.g. plan name) -- never the token
itself.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.models.connection_v2 import ConnectionKind, ConnectionV2
from app.services.connection_v2.probe import Probe, ProbeResult

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────
# Timeouts (per-step, all bounded)
# ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CliProbeTimeouts:
    """Per-step ceilings. Total worst case = version + auth."""

    version: float = 8.0       # binary --version
    auth: float = 8.0          # auth status / token-read


DEFAULT_TIMEOUTS = CliProbeTimeouts()


# Failure-reason prefixes the frontend can match on without parsing
# free-form text. Each prefix maps 1:1 to a founder-listed state.
FAIL_BINARY_NOT_FOUND = "binary_not_found"
FAIL_VERSION_FAILED = "version_failed"
FAIL_VERSION_TIMEOUT = "version_timeout"
FAIL_AUTH_UNKNOWN = "auth_unknown"
FAIL_AUTH_FAILED = "auth_failed"
FAIL_COMMAND_TIMEOUT = "command_timeout"
FAIL_UNSUPPORTED_RUNTIME = "unsupported_runtime"
FAIL_CONFIG_MISSING = "config_missing"


# Cap stderr / message strings so failure_reason never bloats the DB
# column or smuggles secret material into logs.
_REASON_PREVIEW = 200


def _reason(prefix: str, detail: str = "") -> str:
    """Compose a structured failure reason: ``prefix: detail (truncated)``."""
    if not detail:
        return prefix
    cleaned = detail.replace("\n", " ").replace("\r", " ").strip()
    if len(cleaned) > _REASON_PREVIEW:
        cleaned = cleaned[:_REASON_PREVIEW] + "..."
    return f"{prefix}: {cleaned}"


# ──────────────────────────────────────────────────────────────────
# Per-runtime spec table
# ──────────────────────────────────────────────────────────────────
#
# Each spec describes ONE CLI runtime: binary name, version-args,
# whether `--version` is safe to run (gemini's hangs when not
# authenticated), and which auth-check strategy to use. Strategies
# are intentionally narrow -- each one is a single safe operation,
# documented in the strategy function's docstring.


@dataclass(frozen=True)
class CliRuntimeSpec:
    runtime_id: str
    display_name: str
    binary_name: str
    version_args: tuple[str, ...]
    # Some CLIs hang on --version when not authenticated. For those we
    # treat binary presence as reachable and skip the version probe.
    version_check_safe: bool
    auth_strategy: str  # 'claude_status_cmd' | 'codex_jwt_file' | 'gemini_oauth_file' | 'none'


CLAUDE_SPEC = CliRuntimeSpec(
    runtime_id="claude_code",
    display_name="Claude Code",
    binary_name="claude",
    version_args=("--version",),
    version_check_safe=True,
    auth_strategy="claude_status_cmd",
)

CODEX_SPEC = CliRuntimeSpec(
    runtime_id="codex",
    display_name="Codex CLI",
    binary_name="codex",
    version_args=("--version",),
    version_check_safe=True,
    # codex doesn't ship `auth status`; we read the JWT file the CLI
    # writes after `codex login`.
    auth_strategy="codex_jwt_file",
)

GEMINI_SPEC = CliRuntimeSpec(
    runtime_id="gemini_cli",
    display_name="Gemini CLI",
    binary_name="gemini",
    # Gemini --version is known to hang on an unauthenticated install.
    # Skip the version probe; binary presence is enough for reachable.
    version_args=(),
    version_check_safe=False,
    auth_strategy="gemini_oauth_file",
)

# Stretch: grok_cli has no published `--version` semantics yet; treat
# auth as unknown until we ship a confirmed-safe check.
GROK_SPEC = CliRuntimeSpec(
    runtime_id="grok_cli",
    display_name="Grok CLI",
    binary_name="grok",
    version_args=("--version",),
    version_check_safe=True,
    auth_strategy="none",  # honest: no documented safe auth check yet
)


SPEC_BY_RUNTIME_ID: dict[str, CliRuntimeSpec] = {
    spec.runtime_id: spec
    for spec in (CLAUDE_SPEC, CODEX_SPEC, GEMINI_SPEC, GROK_SPEC)
}


# ──────────────────────────────────────────────────────────────────
# Sync subprocess helper (Windows SelectorEventLoop compat)
# ──────────────────────────────────────────────────────────────────
#
# The CLI provider + adapters use ``asyncio.to_thread(subprocess.run)``
# instead of ``asyncio.create_subprocess_exec`` because uvicorn on
# Windows uses SelectorEventLoop which does not support subprocess
# pipes. We follow the same pattern here so probe behaviour is
# identical across Linux + Windows.


def _run_sync(
    cmd: list[str], *, timeout: float, env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Spawn a CLI synchronously. Caller wraps with asyncio.to_thread."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env or os.environ.copy(),
    )


# ──────────────────────────────────────────────────────────────────
# Auth check strategies
# ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AuthCheckResult:
    """Outcome of one auth-check strategy.

    ``status`` is one of: 'authenticated', 'auth_failed', 'auth_unknown'.
    ``user_display`` is a short human label (plan name, masked email)
    suitable for the drawer. NEVER carries the token itself.
    """

    status: str
    user_display: str = ""
    detail: str = ""


def _check_claude_status_cmd(
    bin_path: str, *, extra_args: list[str], timeout: float,
) -> AuthCheckResult:
    """Strategy: run ``<bin> auth status``, parse JSON, check loggedIn.

    Safe because ``claude auth status`` is a documented no-side-effect
    introspection command that emits a tiny JSON envelope. Network
    calls are limited to a token validity ping; no model call.

    ``extra_args`` is inserted between ``bin_path`` and the subcommand
    so tests can wrap the binary in a Python interpreter; production
    passes ``[]``.
    """
    try:
        result = _run_sync(
            [bin_path, *extra_args, "auth", "status"], timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return AuthCheckResult(
            status="auth_unknown",
            detail=_reason(FAIL_COMMAND_TIMEOUT, f"auth status > {timeout}s"),
        )
    except Exception as exc:  # noqa: BLE001
        return AuthCheckResult(
            status="auth_unknown",
            detail=_reason(FAIL_AUTH_UNKNOWN, type(exc).__name__),
        )

    if result.returncode != 0:
        return AuthCheckResult(
            status="auth_failed",
            detail=_reason(
                FAIL_AUTH_FAILED, f"claude auth status rc={result.returncode}",
            ),
        )

    try:
        data = json.loads((result.stdout or "").strip())
    except (json.JSONDecodeError, ValueError):
        return AuthCheckResult(
            status="auth_unknown",
            detail=_reason(FAIL_AUTH_UNKNOWN, "claude auth status not JSON"),
        )

    if data.get("loggedIn") is True:
        api_provider = str(data.get("apiProvider") or "")
        plan = "Claude Max" if api_provider == "firstParty" else "Claude Pro"
        return AuthCheckResult(status="authenticated", user_display=plan)

    return AuthCheckResult(
        status="auth_failed",
        detail=_reason(FAIL_AUTH_FAILED, "loggedIn=false"),
    )


def _check_codex_jwt_file(*, home: Path) -> AuthCheckResult:
    """Strategy: read ``~/.codex/auth.json`` and validate JWT structure.

    Safe because it reads a single JSON file the CLI writes after
    ``codex login``. We DECODE the JWT payload (base64url) to extract
    plan / email -- the token string itself never leaves this scope
    and never appears in logs.
    """
    auth_file = home / ".codex" / "auth.json"
    if not auth_file.exists():
        return AuthCheckResult(
            status="auth_failed",
            detail=_reason(FAIL_AUTH_FAILED, "~/.codex/auth.json missing"),
        )

    try:
        data = json.loads(auth_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return AuthCheckResult(
            status="auth_unknown",
            detail=_reason(
                FAIL_AUTH_UNKNOWN, f"~/.codex/auth.json unreadable ({type(exc).__name__})",
            ),
        )

    tokens = data.get("tokens") or {}
    id_token = tokens.get("id_token") or ""
    if not isinstance(id_token, str) or not id_token:
        # auth.json present but no token. Honor an explicit ``auth_mode``
        # if the operator has set it (some Codex installs work without
        # an inline JWT, e.g. when relying on a system credential
        # manager).
        if data.get("auth_mode"):
            return AuthCheckResult(
                status="authenticated",
                user_display=f"Codex ({data.get('auth_mode')})",
            )
        return AuthCheckResult(
            status="auth_failed",
            detail=_reason(FAIL_AUTH_FAILED, "auth.json has no id_token"),
        )

    parts = id_token.split(".")
    if len(parts) != 3:
        return AuthCheckResult(
            status="auth_unknown",
            detail=_reason(FAIL_AUTH_UNKNOWN, "id_token not a JWT"),
        )

    try:
        # Pad base64url to a multiple of 4
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    except (ValueError, json.JSONDecodeError) as exc:
        return AuthCheckResult(
            status="auth_unknown",
            detail=_reason(
                FAIL_AUTH_UNKNOWN, f"jwt decode error ({type(exc).__name__})",
            ),
        )

    # Optional expiration check -- if exp is present and past, treat as
    # auth_failed (token expired).
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp > 0:
        now_ts = datetime.now(timezone.utc).timestamp()
        if now_ts >= float(exp):
            return AuthCheckResult(
                status="auth_failed",
                detail=_reason(FAIL_AUTH_FAILED, "token expired"),
            )

    auth_info = payload.get("https://api.openai.com/auth") or {}
    plan_type = str(auth_info.get("chatgpt_plan_type") or "plus")
    return AuthCheckResult(
        status="authenticated",
        user_display=f"ChatGPT {plan_type.capitalize()}",
    )


def _check_gemini_oauth_file(*, home: Path) -> AuthCheckResult:
    """Strategy: check ``~/.gemini/oauth_creds.json`` for a token.

    Safe because it reads a single JSON file the Gemini CLI writes
    after ``gemini auth``. We check ONLY for presence of access_token
    / refresh_token keys -- never decode or transmit the values.
    """
    oauth_file = home / ".gemini" / "oauth_creds.json"
    if not oauth_file.exists():
        return AuthCheckResult(
            status="auth_failed",
            detail=_reason(
                FAIL_AUTH_FAILED, "~/.gemini/oauth_creds.json missing",
            ),
        )

    try:
        creds = json.loads(oauth_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return AuthCheckResult(
            status="auth_unknown",
            detail=_reason(
                FAIL_AUTH_UNKNOWN, f"oauth_creds.json unreadable ({type(exc).__name__})",
            ),
        )

    has_token = bool(creds.get("access_token") or creds.get("refresh_token"))
    if not has_token:
        return AuthCheckResult(
            status="auth_failed",
            detail=_reason(FAIL_AUTH_FAILED, "no access/refresh token"),
        )

    # Try to surface a friendly plan label without exposing the token.
    plan = "Google account"
    accounts_file = home / ".gemini" / "google_accounts.json"
    if accounts_file.exists():
        try:
            accts = json.loads(accounts_file.read_text(encoding="utf-8"))
            active = str(accts.get("active") or "")
            if active and "@" in active:
                # Mask local-part to avoid leaking the full address.
                local, _, domain = active.partition("@")
                masked = (local[:2] + "***") if len(local) > 2 else "***"
                plan = f"{masked}@{domain}"
        except (json.JSONDecodeError, OSError):
            pass

    return AuthCheckResult(status="authenticated", user_display=plan)


# ──────────────────────────────────────────────────────────────────
# Probe
# ──────────────────────────────────────────────────────────────────


class CliRuntimeProbe(Probe):
    """Real CLI runtime probe (binary + version + safe auth)."""

    kind = ConnectionKind.CLI_RUNTIME

    def __init__(
        self,
        timeouts: CliProbeTimeouts | None = None,
        *,
        home_override: Path | None = None,
    ) -> None:
        self.timeouts = timeouts or DEFAULT_TIMEOUTS
        # Tests inject a tmpdir as the home root so the JWT / OAuth
        # checks read fixture files instead of the real operator's
        # ~/.codex / ~/.gemini directories.
        self._home_override = home_override

    def _home(self) -> Path:
        if self._home_override is not None:
            return self._home_override
        return Path.home()

    async def run(self, row: ConnectionV2) -> ProbeResult:
        config: dict[str, Any] = row.config or {}

        # ── Dispatch on _runtime_id (seeder-stable identifier) ──
        runtime_id = str(config.get("_runtime_id") or "").strip()
        if not runtime_id:
            return ProbeResult(
                success=False,
                failure_dim="configured",
                failure_reason=_reason(
                    FAIL_CONFIG_MISSING,
                    "row.config missing '_runtime_id' -- seeder did not write CLI shape",
                ),
            )

        spec = SPEC_BY_RUNTIME_ID.get(runtime_id)
        if spec is None:
            return ProbeResult(
                success=False,
                failure_dim="configured",
                failure_reason=_reason(
                    FAIL_UNSUPPORTED_RUNTIME,
                    f"no spec for runtime_id {runtime_id!r}",
                ),
            )

        # ── Resolve binary (config first, PATH fallback) ──
        bin_path = self._resolve_binary(config, spec)
        if not bin_path:
            return ProbeResult(
                success=False,
                failure_dim="reachable",
                failure_reason=_reason(
                    FAIL_BINARY_NOT_FOUND,
                    f"{spec.binary_name!r} not found on PATH or config['binary']",
                ),
            )

        extra_args = self._extra_args(config)

        logger.info(
            "cli_probe.starting",
            connection_id=str(row.id),
            slug=row.slug,
            runtime_id=runtime_id,
            binary=bin_path,
            extra_args_count=len(extra_args),
            version_check_safe=spec.version_check_safe,
            auth_strategy=spec.auth_strategy,
        )

        # ── Dim 3: reachable (version check OR binary presence) ──
        version_str: str | None = None
        if spec.version_check_safe:
            version_outcome = await self._run_version(bin_path, spec, extra_args)
            if isinstance(version_outcome, ProbeResult):
                # Hard failure -- already shaped as a ProbeResult.
                return version_outcome
            version_str = version_outcome  # may be empty string if rc=0 but no stdout

        # ── Dim 4: authenticated (per-runtime safe check) ──
        auth_result = await self._run_auth_check(bin_path, spec, extra_args)

        if auth_result.status == "auth_failed":
            return ProbeResult(
                success=False,
                failure_dim="authenticated",
                failure_reason=auth_result.detail
                or _reason(FAIL_AUTH_FAILED, "no detail"),
            )
        if auth_result.status == "auth_unknown":
            # Honest signal: reachable, but we cannot prove auth. The
            # frontend renders the "CLI installed, but Daena cannot
            # safely verify login yet" copy.
            return ProbeResult(
                success=False,
                failure_dim="authenticated",
                failure_reason=auth_result.detail
                or _reason(
                    FAIL_AUTH_UNKNOWN,
                    f"no safe auth check for {runtime_id}",
                ),
            )

        # ── Dim 5: callable -- detected + reachable + authenticated ──
        # Per founder spec: callable=true only if runtime is installed
        # AND usable for Daena routing. We've proven all three above.
        return ProbeResult(
            success=True,
            capabilities=[{
                "name": runtime_id,
                "kind": "cli_runtime",
                "spec": _safe_spec(spec, version_str, auth_result),
            }],
        )

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _resolve_binary(
        self, config: dict[str, Any], spec: CliRuntimeSpec,
    ) -> str:
        """Resolve the CLI binary path. Config wins, PATH fallback.

        The seeder writes ``binary`` as the absolute path it found at
        seed time. If the operator installed/uninstalled the binary
        after seeding, we re-check with shutil.which so the probe
        reflects current state instead of seed-time state.
        """
        candidate = str(config.get("binary") or "").strip()
        # Reject anything that smells like a shell pipeline -- defense
        # in depth against a malicious config blob.
        if any(ch in candidate for ch in (";", "&", "|", ">", "<", "`", "$(")):
            candidate = ""
        if candidate and os.path.isfile(candidate):
            return candidate
        resolved = shutil.which(spec.binary_name)
        return resolved or ""

    def _extra_args(self, config: dict[str, Any]) -> list[str]:
        """Pre-CLI args inserted between binary and CLI subcommand.

        Production: empty list. Tests use this to wrap the binary in
        a Python interpreter when fixture scripts stand in for a real
        CLI (binary=sys.executable, extra_args=[fixture_path]).

        Each token MUST be a string and MUST NOT contain shell
        metacharacters -- defense in depth against a malicious config.
        """
        raw = config.get("extra_args") or []
        if not isinstance(raw, (list, tuple)):
            return []
        out: list[str] = []
        for token in raw:
            if not isinstance(token, str):
                continue
            if any(ch in token for ch in (";", "&", "|", ">", "<", "`", "$(")):
                continue
            out.append(token)
        return out

    async def _run_version(
        self, bin_path: str, spec: CliRuntimeSpec,
        extra_args: list[str] | None = None,
    ) -> ProbeResult | str:
        """Run the version command. Returns version string on success
        OR a structured failure ProbeResult.

        The CLI's stdout is harmlessly captured; stderr is logged
        server-side but NEVER surfaced in failure_reason (Asset Shield
        Hard Law 5).
        """
        cmd = [bin_path, *(extra_args or []), *spec.version_args]
        try:
            result = await asyncio.to_thread(
                _run_sync, cmd, timeout=self.timeouts.version,
            )
        except subprocess.TimeoutExpired:
            logger.warning(
                "cli_probe.version_timeout",
                runtime_id=spec.runtime_id,
                binary=bin_path,
                timeout=self.timeouts.version,
            )
            return ProbeResult(
                success=False,
                failure_dim="reachable",
                failure_reason=_reason(
                    FAIL_VERSION_TIMEOUT,
                    f"{spec.binary_name} --version > {self.timeouts.version}s",
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "cli_probe.version_error",
                runtime_id=spec.runtime_id,
                binary=bin_path,
                error_type=type(exc).__name__,
            )
            return ProbeResult(
                success=False,
                failure_dim="reachable",
                failure_reason=_reason(
                    FAIL_VERSION_FAILED, type(exc).__name__,
                ),
            )

        if result.returncode != 0:
            # Log stderr for the operator console but DO NOT echo it
            # back -- might contain a path with a username or token.
            logger.warning(
                "cli_probe.version_nonzero",
                runtime_id=spec.runtime_id,
                rc=result.returncode,
                stderr_preview=(result.stderr or "")[:200],
            )
            return ProbeResult(
                success=False,
                failure_dim="reachable",
                failure_reason=_reason(
                    FAIL_VERSION_FAILED,
                    f"{spec.binary_name} --version exited {result.returncode}",
                ),
            )

        return (result.stdout or "").strip()[:120]

    async def _run_auth_check(
        self, bin_path: str, spec: CliRuntimeSpec,
        extra_args: list[str] | None = None,
    ) -> AuthCheckResult:
        """Dispatch to the per-runtime auth-check strategy."""
        if spec.auth_strategy == "claude_status_cmd":
            return await asyncio.to_thread(
                _check_claude_status_cmd, bin_path,
                extra_args=extra_args or [],
                timeout=self.timeouts.auth,
            )
        if spec.auth_strategy == "codex_jwt_file":
            return await asyncio.to_thread(
                _check_codex_jwt_file, home=self._home(),
            )
        if spec.auth_strategy == "gemini_oauth_file":
            return await asyncio.to_thread(
                _check_gemini_oauth_file, home=self._home(),
            )
        # 'none' OR any future strategy we haven't implemented.
        return AuthCheckResult(
            status="auth_unknown",
            detail=_reason(
                FAIL_AUTH_UNKNOWN,
                f"runtime {spec.runtime_id!r} has no safe auth check yet",
            ),
        )


def _safe_spec(
    spec: CliRuntimeSpec,
    version_str: str | None,
    auth_result: AuthCheckResult,
) -> dict[str, Any]:
    """Build the capability spec dict.

    Carries ONLY non-secret metadata: runtime_id, display_name, version
    string (truncated), auth_user_display (plan name / masked email).
    Never includes the binary path (which can leak username) and never
    includes raw tokens.
    """
    out: dict[str, Any] = {
        "runtime_id": spec.runtime_id,
        "display_name": spec.display_name,
        "auth_strategy": spec.auth_strategy,
    }
    if version_str:
        out["version"] = version_str
    if auth_result.user_display:
        out["auth_user_display"] = auth_result.user_display
    return out


def install_cli_runtime_probe(
    timeouts: CliProbeTimeouts | None = None,
) -> None:
    """Register the CliRuntimeProbe. Idempotent (last write wins)."""
    from app.services.connection_v2.probe import register_probe
    register_probe(CliRuntimeProbe(timeouts=timeouts))


__all__ = [
    "CLAUDE_SPEC",
    "CODEX_SPEC",
    "CliProbeTimeouts",
    "CliRuntimeProbe",
    "CliRuntimeSpec",
    "DEFAULT_TIMEOUTS",
    "FAIL_AUTH_FAILED",
    "FAIL_AUTH_UNKNOWN",
    "FAIL_BINARY_NOT_FOUND",
    "FAIL_COMMAND_TIMEOUT",
    "FAIL_CONFIG_MISSING",
    "FAIL_UNSUPPORTED_RUNTIME",
    "FAIL_VERSION_FAILED",
    "FAIL_VERSION_TIMEOUT",
    "GEMINI_SPEC",
    "GROK_SPEC",
    "SPEC_BY_RUNTIME_ID",
    "AuthCheckResult",
    "install_cli_runtime_probe",
]
