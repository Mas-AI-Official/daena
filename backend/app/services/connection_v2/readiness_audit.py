"""PR-CONN-MCP-READINESS-AUDIT-AND-INSTALL-POLISH (Sprint-9 PR-2).

Deterministic readiness classifier over the marketplace catalog.

Every catalog entry is sorted into exactly one of these statuses:

  * ``ready_to_install``    -- install path wired, no operator inputs,
                                no required env vars; one-click installable.
  * ``needs_token``          -- install path wired but the entry declares
                                ``required_env_vars`` (operator must set
                                their own token before launching).
  * ``needs_placeholder``    -- install path wired but the catalog
                                ``command_template`` carries a ``<TOKEN>``
                                the operator must fill (Sprint-8 PR-1
                                surfaces this in the install drawer).
  * ``setup_guide_only``     -- catalogued, ``install_method != mcp_*``;
                                we render a Setup Guide instead of an
                                Install button (oauth apps, CLIs, local
                                model files, browser tools, computer-use).
  * ``coming_soon``          -- install_method=="coming-soon" or
                                officiality=="coming-soon".
  * ``broken``               -- install path is wired but malformed
                                (empty command_template, etc.).

This module is the single source of truth for the audit table the
report quotes verbatim and the contract the readiness tests pin.

NEVER reads / prints / commits secret values. ``required_env_vars``
is treated as NAMES ONLY (the catalog's invariant since 2026-05-02).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from app.services.connection_v2.cli_mcp_writer import (
    find_template_placeholders,
    parse_command_template,
)
from app.services.connection_v2.marketplace_catalog import (
    CATALOG,
    CatalogEntry,
)


ReadinessStatus = Literal[
    "ready_to_install",
    "needs_token",
    "needs_placeholder",
    "setup_guide_only",
    "coming_soon",
    "broken",
]


@dataclass(frozen=True)
class ReadinessRow:
    """One row of the audit table.

    Mirrors the shape the report renders + the test fixture pins.
    Field order matches the brief's requested table columns.
    """

    plugin_id: str
    display_name: str
    category: str
    kind: str
    install_command_exists: bool
    placeholders_required: tuple[str, ...]
    auth_env_names: tuple[str, ...]
    probe_implementation_exists: bool
    execution_path_exists: bool
    status: ReadinessStatus
    rationale: str


def _has_probe_implementation(entry: CatalogEntry) -> bool:
    """True when the catalog declares a probe Daena ships today."""
    # Map probe_type onto whether a real Probe class exists in the
    # registry. Keep this conservative: anything we don't ship today
    # gets recorded as not-yet-implemented even if the catalog string
    # is plausible.
    return entry.probe_type in {"mcp_initialize", "oauth_token", "http_get", "binary_check"}


def _has_execution_path(entry: CatalogEntry) -> bool:
    """True when the skill executor has at least one ``execution_mode=mcp_tool``
    entry for this plugin (real read-only call wired)."""
    if entry.kind != "mcp_server":
        return False
    # Late import to avoid a heavyweight import cycle at module load.
    from app.services.connection_v2.skill_executor import PHASE2_ALLOWLIST
    return any(
        e.plugin_id == entry.id and e.execution_mode == "mcp_tool"
        for e in PHASE2_ALLOWLIST
    )


def classify_entry(entry: CatalogEntry) -> ReadinessRow:
    """Classify one catalog entry. Pure function; no I/O."""
    placeholders: tuple[str, ...] = tuple(
        find_template_placeholders(entry.command_template)
    )
    install_command_exists = bool(entry.command_template.strip())
    probe_ok = _has_probe_implementation(entry)
    exec_ok = _has_execution_path(entry)

    # ── Status classification (precedence top -> bottom) ──
    if (
        entry.install_method == "coming-soon"
        or entry.officiality == "coming-soon"
    ):
        status: ReadinessStatus = "coming_soon"
        rationale = "install_method or officiality is 'coming-soon'."
    elif entry.kind == "mcp_server" and (
        not install_command_exists
        or entry.command_template.strip().lower().startswith(("http://", "https://"))
    ):
        # Hosted / vendor-managed MCP. Two shapes land here:
        #   (a) install_method=manual + empty command_template (e.g.
        #       Notion's hosted MCP -- operator connects via the
        #       vendor's own integrations UI), and
        #   (b) command_template is an https:// URL (Cloudflare, Vercel,
        #       Linear, Figma, Slack, Jira hosted MCP endpoints) --
        #       Daena does not write URLs into stdio mcpServers entries;
        #       the operator authorizes through the vendor UI.
        # Both surfaces render a Setup Guide, never an Install button.
        status = "setup_guide_only"
        rationale = (
            "Hosted / vendor-managed MCP. Operator connects through the "
            "vendor's own UI; Daena does not write hosted-URL MCPs into "
            "the local Claude Desktop config. The card surfaces "
            "setup_notes instead of an install command."
        )
    elif entry.kind == "mcp_server" and install_command_exists:
        # Validate the template parses; if not, the entry is broken.
        parsed = parse_command_template(entry.command_template)
        if parsed is None:
            status = "broken"
            rationale = (
                "command_template is non-empty but does not parse "
                "(shell metachars / unbalanced quotes)."
            )
        elif placeholders:
            status = "needs_placeholder"
            rationale = (
                f"Catalog command_template carries unresolved placeholder(s) "
                f"{', '.join(placeholders)}. Operator supplies value(s) via "
                "the MCP install drawer (Sprint-8 PR-1)."
            )
        elif entry.required_env_vars:
            status = "needs_token"
            rationale = (
                f"Install command is wired, but operator must set "
                f"{len(entry.required_env_vars)} env var(s) BEFORE launching the "
                f"host CLI: {', '.join(entry.required_env_vars)}. "
                "Daena never writes values into the CLI config (founder rule 14)."
            )
        else:
            status = "ready_to_install"
            rationale = (
                "One-click install: command_template parses cleanly, no "
                "placeholders, no required env vars."
            )
    elif entry.kind == "mcp_server":
        # MCP entry without an install command is a broken catalog row.
        status = "broken"
        rationale = "MCP entry has no command_template."
    elif entry.kind in {"oauth_app"}:
        status = "setup_guide_only"
        rationale = (
            "OAuth integration: marketplace shows a Setup Guide pointing "
            "the operator at the connector's OAuth start URL. No CLI install."
        )
    elif entry.kind in {"cli_runtime", "local_model"}:
        status = "setup_guide_only"
        rationale = (
            "External runtime: operator installs via the vendor's own "
            "installer / model download. Daena detects + probes the "
            "binary or HTTP endpoint, never installs."
        )
    elif entry.kind in {"browser_tool", "computer_use"}:
        # Browser / computer-use cards have no install command in the
        # catalog today; render a Setup Guide unless flagged coming_soon.
        status = "setup_guide_only"
        rationale = (
            "Browser / computer-use surface: requires Playwright or "
            "vendor SDK setup outside the MCP install path."
        )
    elif entry.kind == "api_provider":
        status = "needs_token"
        rationale = (
            "Cloud LLM provider: connect by pasting an API key into "
            "Settings -> Vault. No CLI install. Vault stores under "
            "named env-var names only; values stay encrypted."
        )
    elif entry.kind == "skill_pack":
        status = "setup_guide_only"
        rationale = "Skill pack: capability bundle, not a callable plugin."
    else:
        status = "broken"
        rationale = f"Unknown kind: {entry.kind!r}."

    return ReadinessRow(
        plugin_id=entry.id,
        display_name=entry.display_name,
        category=entry.category,
        kind=entry.kind,
        install_command_exists=install_command_exists,
        placeholders_required=placeholders,
        auth_env_names=tuple(entry.required_env_vars),
        probe_implementation_exists=probe_ok,
        execution_path_exists=exec_ok,
        status=status,
        rationale=rationale,
    )


def audit_catalog() -> list[ReadinessRow]:
    """Classify every catalog entry. Stable ordering by (kind, plugin_id)."""
    return sorted(
        (classify_entry(e) for e in CATALOG),
        key=lambda r: (r.kind, r.plugin_id),
    )


def status_counts(rows: list[ReadinessRow]) -> dict[str, int]:
    """Aggregate counts per status -- useful for the report header."""
    out: dict[str, int] = {}
    for row in rows:
        out[row.status] = out.get(row.status, 0) + 1
    return out


def render_markdown_table(rows: list[ReadinessRow]) -> str:
    """Render the audit rows as a GitHub-flavored markdown table.

    Used by the report script + by tests that pin the table renders
    every catalog entry verbatim. NEVER includes env values -- only
    NAMES (operator-visible by design).
    """
    header = (
        "| plugin_id | name | kind | category | install? | placeholders | env vars | probe | exec | status |\n"
        "|---|---|---|---|---|---|---|---|---|---|"
    )
    lines = [header]
    for row in rows:
        lines.append(
            "| `{pid}` | {name} | {kind} | {cat} | {inst} | {ph} | {env} | {probe} | {exec_} | **{status}** |".format(
                pid=row.plugin_id,
                name=row.display_name,
                kind=row.kind,
                cat=row.category,
                inst="yes" if row.install_command_exists else "no",
                ph=", ".join(row.placeholders_required) or "-",
                env=", ".join(row.auth_env_names) or "-",
                probe="yes" if row.probe_implementation_exists else "no",
                exec_="yes" if row.execution_path_exists else "no",
                status=row.status,
            ),
        )
    return "\n".join(lines)


__all__ = [
    "ReadinessRow",
    "ReadinessStatus",
    "audit_catalog",
    "classify_entry",
    "render_markdown_table",
    "status_counts",
]
