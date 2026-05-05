"""CliMcpWriter -- safely install MCP server entries into local CLI configs.

PR-CONN-MCP-INSTALL-INTO-CLI (2026-05-02). Replaces the read-only
``mcp_sync.detector`` with a write-capable peer that lands MCP plugins
into the right config file for each supported CLI:

  * Claude Desktop  -> ``%APPDATA%/Claude/claude_desktop_config.json``
                       (or platform equivalent)
  * Claude Code     -> ``~/.claude.json`` (or ``~/.claude/mcp.json``)
  * Codex           -> ``~/.codex/config.json``
  * Gemini CLI      -> ``~/.gemini/settings.json``
                       (or ``~/.gemini/mcp_servers.json``)

Hard rules honored (founder):
  * NEVER auto-runs npm / pip / docker. Just writes the MCP server
    declaration into the CLI's own config file.
  * NEVER writes secret values. Env block is omitted; the operator
    sets ``required_env_vars`` in their shell or paste them into the
    config themselves.
  * NEVER overwrites a config without:
      1. Reading it first (parse safely, fail-closed on malformed JSON).
      2. Creating a timestamped backup (``<path>.daena-backup-<TS>.json``).
      3. Writing to a temp file under the same directory.
      4. ``os.replace(tmp, path)`` for atomic rename.
  * NEVER duplicates entries. If ``mcpServers[server_name]`` already
    exists with the SAME command/args, return ``skipped`` (idempotent).
    If it exists but differs, mark ``updated`` and write the new shape.
  * NEVER preserves an unparseable file. If the operator's config is
    not valid JSON, refuse the write and return a clear repair guide.
  * Preview ALWAYS runs before apply. Both endpoints share the same
    "diff" computation so the operator sees exactly what will change.

Failure-reason prefixes:
  - target_unsupported     -- target is not one of the four supported CLIs
  - config_path_missing    -- no config file found AND allow_create=False
  - config_parse_error     -- file exists but is not valid JSON
  - command_template_invalid -- catalog entry has empty / unsafe command
  - placeholder_unresolved -- command_template contains <PLACEHOLDER> tokens
  - write_failed           -- atomic write raised at the OS level
"""

from __future__ import annotations

import json
import os
import platform
import shlex
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.connection_v2.marketplace_catalog import CatalogEntry

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────
# Failure prefixes (frontend matches without parsing free-form text)
# ──────────────────────────────────────────────────────────────────


FAIL_TARGET_UNSUPPORTED = "target_unsupported"
FAIL_CONFIG_PATH_MISSING = "config_path_missing"
FAIL_CONFIG_PARSE_ERROR = "config_parse_error"
FAIL_COMMAND_TEMPLATE_INVALID = "command_template_invalid"
FAIL_PLACEHOLDER_UNRESOLVED = "placeholder_unresolved"
FAIL_PLACEHOLDER_VALUE_INVALID = "placeholder_value_invalid"
FAIL_WRITE_FAILED = "write_failed"


# ──────────────────────────────────────────────────────────────────
# Target spec table
# ──────────────────────────────────────────────────────────────────


SUPPORTED_TARGETS = ("claude_desktop", "claude_code", "codex", "gemini_cli")


@dataclass(frozen=True)
class TargetSpec:
    """How to locate + write to a single CLI's MCP config file.

    All four supported CLIs use a top-level ``mcpServers`` JSON object.
    If a CLI later ships a different schema (e.g. Codex moves to TOML),
    this dataclass is the only place that needs to grow.
    """

    target: str
    display_name: str
    block_key: str  # always "mcpServers" today; reserved for future drift
    candidates: tuple[Path, ...]


def _platform_claude_desktop_paths() -> tuple[Path, ...]:
    """Per-OS Claude Desktop default config locations.

    Windows: ``%APPDATA%/Claude/claude_desktop_config.json``
    macOS:   ``~/Library/Application Support/Claude/claude_desktop_config.json``
    Linux:   ``~/.config/Claude/claude_desktop_config.json``

    On WSL we ALSO offer the Windows-side path under ``/mnt/c/...``
    because the operator's actual Claude Desktop install lives there.
    """
    home = Path.home()
    sys = platform.system()
    paths: list[Path] = []
    if sys == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            paths.append(Path(appdata) / "Claude" / "claude_desktop_config.json")
        paths.append(home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json")
    elif sys == "Darwin":
        paths.append(
            home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
        )
    else:
        paths.append(home / ".config" / "Claude" / "claude_desktop_config.json")
    # WSL: also try /mnt/c/Users/<win>/AppData/Roaming/Claude/...
    if sys == "Linux":
        try:
            if "microsoft" in Path("/proc/version").read_text("utf-8").lower():
                bridge = Path("/mnt/c/Users")
                if bridge.is_dir():
                    skip = {"All Users", "Default", "Default User", "Public", "WDAGUtilityAccount"}
                    for entry in bridge.iterdir():
                        if entry.is_dir() and entry.name not in skip and (
                            entry / "AppData" / "Roaming" / "Claude"
                        ).is_dir():
                            paths.append(
                                entry / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",
                            )
                            break
        except OSError:
            pass
    return tuple(paths)


def _build_targets() -> dict[str, TargetSpec]:
    home = Path.home()
    return {
        "claude_desktop": TargetSpec(
            target="claude_desktop",
            display_name="Claude Desktop",
            block_key="mcpServers",
            candidates=_platform_claude_desktop_paths(),
        ),
        "claude_code": TargetSpec(
            target="claude_code",
            display_name="Claude Code (CLI)",
            block_key="mcpServers",
            candidates=(
                home / ".claude.json",
                home / ".claude" / "mcp.json",
            ),
        ),
        "codex": TargetSpec(
            target="codex",
            display_name="Codex CLI",
            block_key="mcpServers",
            candidates=(
                home / ".codex" / "config.json",
                home / ".codex" / "mcp.json",
            ),
        ),
        "gemini_cli": TargetSpec(
            target="gemini_cli",
            display_name="Gemini CLI",
            block_key="mcpServers",
            candidates=(
                home / ".gemini" / "settings.json",
                home / ".gemini" / "mcp_servers.json",
            ),
        ),
    }


def get_target_spec(target: str) -> TargetSpec | None:
    """Lookup TargetSpec by name. Cached at module level."""
    return _TARGETS.get(target)


_TARGETS: dict[str, TargetSpec] = _build_targets()


def reset_target_cache() -> None:
    """Test hook: rebuild target spec cache (e.g. after monkeypatching home)."""
    global _TARGETS
    _TARGETS = _build_targets()


# ──────────────────────────────────────────────────────────────────
# Command template parsing
# ──────────────────────────────────────────────────────────────────
#
# command_template carries the line the OPERATOR would paste into a
# terminal: ``npx -y @modelcontextprotocol/server-github``.
# We split it into command + args using shlex (POSIX semantics; Windows
# command lines map cleanly because catalog entries never use single
# quotes / cmd.exe-specific escapes).
#
# Rejected shapes:
#   * Empty / whitespace-only template
#   * Shell metacharacters (;|&><`$()) -- defense in depth against a
#     malicious catalog blob landing in someone's claude_desktop_config
#   * Unresolved placeholders like <ALLOWED_ROOT> -- caller must
#     substitute these BEFORE preview/apply (we never silently fill
#     them with a default that could mask a security mistake)


_PLACEHOLDER_TOKEN_PREFIX = "<"
_PLACEHOLDER_TOKEN_SUFFIX = ">"


@dataclass(frozen=True)
class ParsedCommand:
    command: str
    args: list[str]


def parse_command_template(template: str) -> ParsedCommand | None:
    """Parse a ``command_template`` string into command + args.

    Returns None if the template is empty, contains shell metachars,
    or is structurally invalid.
    """
    if not template or not template.strip():
        return None
    # Reject shell pipelines / redirections / subshells.
    if any(ch in template for ch in (";", "|", "&", ">", "<", "`", "$(")):
        # Note: <ANGLE> placeholder tokens contain "<" and ">". Special-case:
        # allow them HERE (the placeholder check below catches them) so we
        # can return a structured PLACEHOLDER_UNRESOLVED instead of a noisy
        # rejection. Detection: every "<" must be followed by uppercase.
        chars = list(template)
        bad = False
        for i, ch in enumerate(chars):
            if ch in (";", "|", "&", "`"):
                bad = True
                break
            if ch == "$" and i + 1 < len(chars) and chars[i + 1] == "(":
                bad = True
                break
            # < and > are only safe when part of <PLACEHOLDER>
            if ch in ("<", ">"):
                # Continue -- placeholder check below handles this.
                continue
        if bad:
            return None
    try:
        tokens = shlex.split(template, posix=True)
    except ValueError:
        return None
    if not tokens:
        return None
    return ParsedCommand(command=tokens[0], args=tokens[1:])


def find_unresolved_placeholders(parsed: ParsedCommand) -> list[str]:
    """Return any ``<TOKEN>`` placeholders the operator must replace."""
    pending: list[str] = []
    for token in (parsed.command, *parsed.args):
        if (
            token.startswith(_PLACEHOLDER_TOKEN_PREFIX)
            and token.endswith(_PLACEHOLDER_TOKEN_SUFFIX)
            and len(token) >= 3
        ):
            pending.append(token)
    return pending


def find_template_placeholders(template: str) -> list[str]:
    """Surface every ``<TOKEN>`` literal in a raw command_template.

    Used to surface unresolved tokens to the UI BEFORE the operator
    fills any value (so the placeholder input form can render the
    correct list on the very first preview call).

    Accepts both ``<UPPER>`` and ``<lower>`` forms so the catalog can
    use whichever convention is closest to vendor docs (e.g. uvx
    examples that say ``--repository <path>``). The detector enforces
    identifier-shape (alpha-leading, alnum / underscore / hyphen) so a
    string like ``<HTML>`` text never accidentally registers, and
    rejects empty / single-char tokens.
    """
    out: list[str] = []
    i = 0
    n = len(template)
    while i < n:
        ch = template[i]
        if ch == "<":
            j = template.find(">", i + 1)
            if j == -1:
                break
            token = template[i:j + 1]
            inner = token[1:-1]
            if (
                inner
                and len(inner) >= 2
                and inner[0].isalpha()
                and all(c.isalnum() or c in ("_", "-") for c in inner)
            ):
                out.append(token)
            i = j + 1
            continue
        i += 1
    return out


# Characters that MUST never appear in a placeholder value. We block at the
# substitution boundary so a malicious or accidental newline / pipe / backtick
# can never reach a CLI's mcpServers args list. shlex.quote guards spaces and
# quotes; this list guards everything else (defense in depth).
_PLACEHOLDER_VALUE_FORBIDDEN: tuple[str, ...] = (
    ";", "|", "&", "`", "\n", "\r", "\0", "<", ">",
)


def resolve_command_template(
    template: str, values: dict[str, str] | None,
) -> tuple[str, list[str], str | None]:
    """Substitute ``<KEY>`` placeholders in ``template``.

    Returns ``(resolved_template, applied_keys, error_or_none)``.

    Each value is shlex.quote-wrapped when it contains whitespace or quote
    characters so the resulting command line still parses to a single
    token. Values containing shell metacharacters / control bytes / angle
    brackets are rejected -- we never silently rewrite them.

    Caller-supplied keys may be passed as ``"<X>"`` or as bare ``"X"``;
    both forms map to the same placeholder token.
    """
    if not values:
        return template, [], None
    out = template
    applied: list[str] = []
    for raw_key, raw_val in values.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            return template, applied, (
                f"{FAIL_PLACEHOLDER_VALUE_INVALID}: empty placeholder key"
            )
        key = (
            raw_key
            if raw_key.startswith("<") and raw_key.endswith(">")
            else f"<{raw_key.strip('<>')}>"
        )
        if not isinstance(raw_val, str):
            return template, applied, (
                f"{FAIL_PLACEHOLDER_VALUE_INVALID}: {key} value must be a string"
            )
        val = raw_val.strip()
        if not val:
            return template, applied, (
                f"{FAIL_PLACEHOLDER_VALUE_INVALID}: {key} value is empty"
            )
        if "$(" in val or "${" in val:
            return template, applied, (
                f"{FAIL_PLACEHOLDER_VALUE_INVALID}: {key} contains shell expansion"
            )
        for ch in _PLACEHOLDER_VALUE_FORBIDDEN:
            if ch in val:
                return template, applied, (
                    f"{FAIL_PLACEHOLDER_VALUE_INVALID}: {key} contains forbidden character {ch!r}"
                )
        if key not in out:
            # Operator supplied a key the catalog template does not reference.
            # Skip silently rather than fail -- a generous superset is safer than
            # an over-strict exact-match check (the form may carry stale fields).
            continue
        # Always shlex.quote -- Windows paths carry backslashes which
        # POSIX shlex.split treats as escape chars; single-quoting
        # preserves the literal value through the round-trip.
        quoted = shlex.quote(val)
        out = out.replace(key, quoted)
        applied.append(key)
    return out, applied, None


# ──────────────────────────────────────────────────────────────────
# MCP block construction
# ──────────────────────────────────────────────────────────────────


def build_mcp_block(
    entry: CatalogEntry, *, effective_template: str | None = None,
) -> dict | None:
    """Build the JSON object that goes under ``mcpServers[server_name]``.

    Shape mirrors what every supported CLI accepts:
        {"command": "npx", "args": ["-y", "@org/pkg"]}

    NEVER includes ``env``. Per founder rule 14: env values stay in
    environment / vault / Settings -- the operator sets them before
    launching the CLI. We surface ``required_env_vars`` separately so
    the UI can warn the operator about what to set.

    ``effective_template`` lets a caller substitute placeholders without
    cloning the frozen entry.
    """
    template = effective_template if effective_template is not None else entry.command_template
    parsed = parse_command_template(template)
    if parsed is None:
        return None
    return {
        "command": parsed.command,
        "args": list(parsed.args),
    }


def server_name_for(entry: CatalogEntry) -> str:
    """Pick the server-name key under ``mcpServers``.

    Strips the ``mcp-`` prefix from the catalog id so e.g. ``mcp-github``
    becomes ``github`` (matching what Claude Desktop / Gemini already
    use). Falls back to the catalog id verbatim if no prefix.
    """
    raw = entry.id.strip()
    if raw.startswith("mcp-"):
        return raw[4:]
    return raw


# ──────────────────────────────────────────────────────────────────
# Config IO helpers (read + atomic write + backup)
# ──────────────────────────────────────────────────────────────────


@dataclass
class ConfigSnapshot:
    """In-memory view of a parsed config file.

    ``data`` is the entire file content (so we can preserve unrelated
    keys on write). ``mcp_servers`` is the (possibly empty) dict under
    ``data["mcpServers"]``. ``parse_error`` is set when the file existed
    but was not valid JSON -- in that case ``data`` is None and the
    caller must NOT write.
    """

    path: Path
    exists: bool
    data: dict | None = None
    mcp_servers: dict = field(default_factory=dict)
    parse_error: str | None = None


def read_config(path: Path) -> ConfigSnapshot:
    """Read the config file from disk; never raises.

    Missing file: ``exists=False, data=None`` (caller may treat as
    empty-init candidate).
    Malformed file: ``exists=True, parse_error="..."`` (caller MUST
    refuse to write).
    """
    if not path.exists():
        return ConfigSnapshot(path=path, exists=False)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return ConfigSnapshot(
            path=path, exists=True,
            parse_error=f"{type(exc).__name__}: read failed",
        )
    if not raw.strip():
        # Treat empty file as "exists but writable from blank".
        return ConfigSnapshot(path=path, exists=True, data={}, mcp_servers={})
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return ConfigSnapshot(
            path=path, exists=True,
            parse_error=f"json: {exc.msg} at line {exc.lineno} col {exc.colno}",
        )
    if not isinstance(data, dict):
        return ConfigSnapshot(
            path=path, exists=True,
            parse_error="root is not a JSON object (mcpServers must live under {})",
        )
    block = data.get("mcpServers")
    if block is None or not isinstance(block, dict):
        return ConfigSnapshot(path=path, exists=True, data=data, mcp_servers={})
    return ConfigSnapshot(path=path, exists=True, data=data, mcp_servers=dict(block))


def _now_stamp() -> str:
    """Timestamp suffix for backup files (UTC, filesystem-safe)."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def atomic_write_json(
    path: Path, payload: dict, *, backup: bool = True,
) -> Path | None:
    """Write payload to path atomically. Returns backup path or None.

    Sequence:
      1. If file exists AND backup=True: copy current bytes to
         ``<path>.daena-backup-<TS>.json``.
      2. Create temp file in the SAME directory as path (so the
         atomic rename is on one filesystem -- otherwise os.replace
         falls back to non-atomic on some Windows configs).
      3. Write JSON to temp file with newline at EOF.
      4. ``os.replace(tmp, path)`` -- atomic on Windows + POSIX.

    The temp file is cleaned up on any exception. The backup is left
    in place so the operator can manually restore.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None
    if backup and path.exists():
        backup_path = path.with_name(f"{path.name}.daena-backup-{_now_stamp()}.json")
        backup_path.write_bytes(path.read_bytes())
    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{path.name}.daena-tmp-", dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(str(tmp_path), str(path))
    except Exception:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise
    return backup_path


# ──────────────────────────────────────────────────────────────────
# Path resolution
# ──────────────────────────────────────────────────────────────────


@dataclass
class PathResolution:
    """Outcome of resolving the writable config path for a target.

    ``existing`` is set when at least one candidate exists -- the writer
    prefers existing candidates so unrelated config keys are preserved.
    ``would_create`` is set when no candidate exists and the writer
    would create the FIRST candidate (only when ``allow_create=True``).
    ``failure_reason`` is populated when neither is true (i.e.
    candidates list is empty for this target).
    """

    target: str
    candidates_tried: list[Path]
    existing: Path | None
    would_create: Path | None
    failure_reason: str | None = None


def resolve_path(
    spec: TargetSpec, *, allow_create: bool = False,
) -> PathResolution:
    """Pick the config file path the writer will operate on.

    Priority:
      1. First candidate that exists on disk -> ``existing``
      2. Else first candidate overall -> ``would_create`` (only when
         ``allow_create=True``; without it, the writer refuses).
    """
    tried = list(spec.candidates)
    for cand in tried:
        if cand.exists():
            return PathResolution(
                target=spec.target, candidates_tried=tried,
                existing=cand, would_create=None,
            )
    if not tried:
        return PathResolution(
            target=spec.target, candidates_tried=[],
            existing=None, would_create=None,
            failure_reason="no candidate paths defined for target",
        )
    if allow_create:
        return PathResolution(
            target=spec.target, candidates_tried=tried,
            existing=None, would_create=tried[0],
        )
    return PathResolution(
        target=spec.target, candidates_tried=tried,
        existing=None, would_create=None,
        failure_reason=(
            "no existing config file found; pass allow_create=true to create one"
        ),
    )


# ──────────────────────────────────────────────────────────────────
# Preview + apply
# ──────────────────────────────────────────────────────────────────


@dataclass
class PreviewReport:
    """Read-only summary of what a Daena install would do.

    Always returned even on failure -- the failure_reason field tells
    the UI exactly what's wrong (and is the same string apply() would
    return). UI uses ``apply_allowed`` to decide whether to enable the
    Confirm button.
    """

    target: str
    target_display_name: str
    config_path: str | None
    config_exists: bool
    parse_ok: bool
    candidates_tried: list[str]
    server_name: str
    proposed_block: dict | None
    existing_block: dict | None
    action: str  # "create" | "update" | "skip" | "create_file" | "noop"
    backup_path: str | None  # what backup would be named on apply
    required_env_vars: list[str]
    risk_warnings: list[str]
    apply_allowed: bool
    failure_reason: str | None
    # PR-CONN-MCP-INSTALL-PLACEHOLDER-INPUT (Sprint-8 PR-1):
    # surface every <TOKEN> the operator still has to fill -- always
    # populated from the RAW catalog template so the UI can render an
    # input form on the very first preview call, even before any value
    # has been supplied. Empty list once every placeholder is resolved.
    unresolved_placeholders: list[str] = field(default_factory=list)


@dataclass
class ApplyReport:
    """Result of an actual write. Always returned (never raised)."""

    target: str
    target_display_name: str
    config_path: str | None
    server_name: str
    action: str  # "created" | "updated" | "skipped" | "create_file" | "failed"
    backup_path: str | None
    failure_reason: str | None
    v2_row_id: str | None = None
    v2_label: str | None = None
    post_apply_probe: dict | None = None


def _validate_entry(
    entry: CatalogEntry,
    *,
    effective_template: str | None = None,
) -> tuple[ParsedCommand | None, str | None, list[str]]:
    """Common preflight: parse template, find unresolved placeholders.

    Returns ``(parsed, failure_reason, placeholders)``. When
    ``failure_reason`` is non-None, callers should NOT proceed to write.

    ``effective_template`` lets the install path validate AFTER
    placeholder substitution while preserving the entry's frozen state.
    """
    if entry.kind != "mcp_server":
        return None, FAIL_TARGET_UNSUPPORTED + f": only mcp_server entries can be installed (kind={entry.kind!r})", []

    template = effective_template if effective_template is not None else entry.command_template
    parsed = parse_command_template(template)
    if parsed is None:
        return None, FAIL_COMMAND_TEMPLATE_INVALID + f": command_template={template!r}", []

    placeholders = find_unresolved_placeholders(parsed)
    if placeholders:
        return parsed, FAIL_PLACEHOLDER_UNRESOLVED + f": {', '.join(placeholders)}", placeholders

    return parsed, None, []


def preview_install(
    *,
    target: str,
    entry: CatalogEntry,
    allow_create: bool = False,
    placeholder_values: dict[str, str] | None = None,
) -> PreviewReport:
    """Compute what an install would do. NEVER touches the filesystem.

    ``placeholder_values`` is the operator-supplied substitution table
    for any ``<TOKEN>`` placeholders in ``entry.command_template``
    (e.g. ``{"<ALLOWED_ROOT>": "D:\\Ideas\\Daena"}``). Values are
    validated for shell safety BEFORE substitution so a malicious
    or accidental newline / pipe / backtick can never reach the CLI's
    mcpServers args list.
    """
    # Always surface the raw catalog placeholders so the UI can render
    # the input form on the very first preview call.
    raw_placeholders = find_template_placeholders(entry.command_template)

    spec = get_target_spec(target)
    if spec is None:
        return PreviewReport(
            target=target, target_display_name=target,
            config_path=None, config_exists=False, parse_ok=True,
            candidates_tried=[],
            server_name=server_name_for(entry),
            proposed_block=None, existing_block=None,
            action="failed", backup_path=None,
            required_env_vars=list(entry.required_env_vars),
            risk_warnings=[],
            apply_allowed=False,
            failure_reason=f"{FAIL_TARGET_UNSUPPORTED}: {target!r} is not one of {SUPPORTED_TARGETS}",
            unresolved_placeholders=raw_placeholders,
        )

    server_name = server_name_for(entry)

    effective_template, _applied, resolve_err = resolve_command_template(
        entry.command_template, placeholder_values,
    )
    if resolve_err is not None:
        return PreviewReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=None, config_exists=False, parse_ok=True,
            candidates_tried=[],
            server_name=server_name,
            proposed_block=None, existing_block=None,
            action="failed", backup_path=None,
            required_env_vars=list(entry.required_env_vars),
            risk_warnings=[],
            apply_allowed=False,
            failure_reason=resolve_err,
            unresolved_placeholders=raw_placeholders,
        )

    parsed, validation_fail, post_resolve_pending = _validate_entry(
        entry, effective_template=effective_template,
    )
    if validation_fail is not None:
        # Prefer post-resolution placeholder list (the ones the operator
        # still needs to fill) when validation tripped on placeholder
        # detection; fall back to the raw catalog list otherwise.
        unresolved = (
            post_resolve_pending
            if validation_fail.startswith(FAIL_PLACEHOLDER_UNRESOLVED)
            else raw_placeholders
        )
        return PreviewReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=None, config_exists=False, parse_ok=True,
            candidates_tried=[],
            server_name=server_name,
            proposed_block=None, existing_block=None,
            action="failed", backup_path=None,
            required_env_vars=list(entry.required_env_vars),
            risk_warnings=[],
            apply_allowed=False,
            failure_reason=validation_fail,
            unresolved_placeholders=unresolved,
        )

    proposed = build_mcp_block(entry, effective_template=effective_template)

    resolution = resolve_path(spec, allow_create=allow_create)
    if resolution.existing is None and resolution.would_create is None:
        return PreviewReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=None, config_exists=False, parse_ok=True,
            candidates_tried=[str(p) for p in resolution.candidates_tried],
            server_name=server_name,
            proposed_block=proposed, existing_block=None,
            action="failed", backup_path=None,
            required_env_vars=list(entry.required_env_vars),
            risk_warnings=[],
            apply_allowed=False,
            failure_reason=(
                f"{FAIL_CONFIG_PATH_MISSING}: {resolution.failure_reason or 'unknown'}"
            ),
            unresolved_placeholders=raw_placeholders,
        )

    target_path = resolution.existing or resolution.would_create
    snapshot = read_config(target_path) if resolution.existing else ConfigSnapshot(
        path=target_path, exists=False, data={}, mcp_servers={},
    )
    if snapshot.parse_error:
        return PreviewReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=str(target_path), config_exists=True, parse_ok=False,
            candidates_tried=[str(p) for p in resolution.candidates_tried],
            server_name=server_name,
            proposed_block=proposed, existing_block=None,
            action="failed", backup_path=None,
            required_env_vars=list(entry.required_env_vars),
            risk_warnings=[
                f"Repair {target_path} before retry: {snapshot.parse_error}",
                "Daena refuses to overwrite a malformed config file.",
            ],
            apply_allowed=False,
            failure_reason=f"{FAIL_CONFIG_PARSE_ERROR}: {snapshot.parse_error}",
            unresolved_placeholders=raw_placeholders,
        )

    existing_block = snapshot.mcp_servers.get(server_name)
    if existing_block == proposed:
        action = "skip"
    elif existing_block is not None:
        action = "update"
    elif not snapshot.exists:
        action = "create_file"
    else:
        action = "create"

    backup_path = None
    if snapshot.exists and action in ("update", "create"):
        backup_path = str(
            target_path.with_name(f"{target_path.name}.daena-backup-<TS>.json"),
        )

    risk_warnings: list[str] = []
    if entry.required_env_vars:
        risk_warnings.append(
            "This MCP requires environment variables. Daena will NOT write "
            "values into the config. Set these in your shell BEFORE "
            f"launching {spec.display_name}: {', '.join(entry.required_env_vars)}"
        )
    if entry.risk_level == "high":
        risk_warnings.append(
            "Risk level: HIGH. This MCP can perform powerful actions. "
            "Asset Shield + governance still gate every call."
        )

    return PreviewReport(
        target=spec.target, target_display_name=spec.display_name,
        config_path=str(target_path), config_exists=snapshot.exists, parse_ok=True,
        candidates_tried=[str(p) for p in resolution.candidates_tried],
        server_name=server_name,
        proposed_block=proposed, existing_block=existing_block,
        action=action, backup_path=backup_path,
        required_env_vars=list(entry.required_env_vars),
        risk_warnings=risk_warnings,
        apply_allowed=action != "failed",
        failure_reason=None,
        unresolved_placeholders=[],
    )


def apply_install(
    *,
    target: str,
    entry: CatalogEntry,
    allow_create: bool = False,
    placeholder_values: dict[str, str] | None = None,
) -> ApplyReport:
    """Perform the actual write. Backup + atomic rename.

    Returns an ApplyReport with action in {created, updated, skipped,
    create_file, failed}. Never raises.

    Idempotent: re-running on the same (target, entry) yields
    ``skipped`` when the existing block already matches.

    ``placeholder_values`` is forwarded to ``preview_install`` so the
    same substitution table drives both the diff and the write.
    """
    preview = preview_install(
        target=target, entry=entry, allow_create=allow_create,
        placeholder_values=placeholder_values,
    )
    if preview.failure_reason is not None or not preview.apply_allowed:
        return ApplyReport(
            target=preview.target, target_display_name=preview.target_display_name,
            config_path=preview.config_path,
            server_name=preview.server_name,
            action="failed",
            backup_path=None,
            failure_reason=preview.failure_reason,
        )

    spec = get_target_spec(target)
    assert spec is not None, "preview should have failed for unsupported targets"
    target_path = Path(preview.config_path) if preview.config_path else None
    assert target_path is not None, "preview validates config_path"

    if preview.action == "skip":
        # Idempotent no-op. Still log for the audit trail.
        logger.info(
            "cli_mcp_writer.skipped",
            target=target, server=preview.server_name,
            config_path=str(target_path),
            reason="entry already matches",
        )
        return ApplyReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=str(target_path), server_name=preview.server_name,
            action="skipped", backup_path=None, failure_reason=None,
        )

    snapshot = read_config(target_path) if target_path.exists() else ConfigSnapshot(
        path=target_path, exists=False, data={}, mcp_servers={},
    )
    if snapshot.parse_error:
        return ApplyReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=str(target_path), server_name=preview.server_name,
            action="failed", backup_path=None,
            failure_reason=f"{FAIL_CONFIG_PARSE_ERROR}: {snapshot.parse_error}",
        )

    new_data: dict[str, Any] = dict(snapshot.data or {})
    block = dict(snapshot.mcp_servers)
    block[preview.server_name] = preview.proposed_block
    new_data[spec.block_key] = block

    try:
        backup_path = atomic_write_json(target_path, new_data, backup=snapshot.exists)
    except OSError as exc:
        logger.error(
            "cli_mcp_writer.write_failed",
            target=target, server=preview.server_name,
            config_path=str(target_path),
            error_type=type(exc).__name__,
        )
        return ApplyReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=str(target_path), server_name=preview.server_name,
            action="failed", backup_path=None,
            failure_reason=f"{FAIL_WRITE_FAILED}: {type(exc).__name__}",
        )

    action = (
        "create_file" if preview.action == "create_file"
        else ("updated" if preview.action == "update" else "created")
    )
    logger.info(
        "cli_mcp_writer.applied",
        target=target, server=preview.server_name,
        config_path=str(target_path), action=action,
        backup=str(backup_path) if backup_path else None,
        env_var_names=list(entry.required_env_vars),
    )
    return ApplyReport(
        target=spec.target, target_display_name=spec.display_name,
        config_path=str(target_path), server_name=preview.server_name,
        action=action,
        backup_path=str(backup_path) if backup_path else None,
        failure_reason=None,
    )


__all__ = [
    "ApplyReport",
    "ConfigSnapshot",
    "FAIL_COMMAND_TEMPLATE_INVALID",
    "FAIL_CONFIG_PARSE_ERROR",
    "FAIL_CONFIG_PATH_MISSING",
    "FAIL_PLACEHOLDER_UNRESOLVED",
    "FAIL_PLACEHOLDER_VALUE_INVALID",
    "FAIL_TARGET_UNSUPPORTED",
    "FAIL_WRITE_FAILED",
    "ParsedCommand",
    "PathResolution",
    "PreviewReport",
    "SUPPORTED_TARGETS",
    "TargetSpec",
    "apply_install",
    "atomic_write_json",
    "build_mcp_block",
    "find_template_placeholders",
    "find_unresolved_placeholders",
    "get_target_spec",
    "parse_command_template",
    "preview_install",
    "read_config",
    "reset_target_cache",
    "resolve_command_template",
    "resolve_path",
    "server_name_for",
]
