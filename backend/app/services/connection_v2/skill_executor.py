"""Phase 2 read-only skill executor.

PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE2-READONLY (2026-05-03):
shipped the spine + audit + UI scaffold; every entry was
``execution_mode="planned_only"``.

PR-CONN-PHASE2X-FILESYSTEM-HUGGINGFACE-READONLY (2026-05-03):
arms real MCP ``tools/call`` execution for the FOUR safest
read-only skills:

  * mcp-filesystem:find_files       -> search_files
  * mcp-filesystem:summarize_directory -> list_directory
  * mcp-huggingface:find_model      -> hub_repo_search
  * mcp-huggingface:inspect_paper   -> paper_search

These four were chosen because they avoid OAuth complexity entirely,
read public data only (HuggingFace) or sandboxed local paths
(filesystem), and have zero write surface in their MCP servers.

PR-CONN-PHASE2X-GITHUB-SENTRY-READONLY (2026-05-03):
arms real MCP ``tools/call`` execution for FOUR more read-only skills
covering GitHub + Sentry. These take tokens/OAuth, so the MCP server
itself owns the auth surface -- the executor only forwards operator
inputs (repo_owner, repo_name, project_slug, ...). Token values
NEVER cross the executor boundary.

  * mcp-github:summarize_repo      -> get_repository
  * mcp-github:triage_issues       -> list_issues
  * mcp-github:inspect_ci_failure  -> get_workflow_run_logs
  * mcp-sentry:summarize_errors    -> list_issues

PR-CONN-PHASE2X-SLACK-GMAIL-DRIVE-READONLY (2026-05-03):
arms real MCP execution for the TWO Slack reads. Gmail + Drive
intentionally STAY planned_only -- their backend_surface is OAuth
(direct HTTP to Google APIs) and Daena does not yet have an
oauth-mode execution path. Promoting them today would require
either:
  (a) an OAuthInvoker service that knows how to translate the
      planned tool name (e.g. messages.list_unread) into Gmail API
      calls, OR
  (b) a stdio MCP package that wraps Gmail/Drive APIs locally.
Neither is in scope for this PR. Returning ``planned`` is the
HONEST status (per Rule 17) until one of those lands.

  * mcp-slack:summarize_channel    -> conversations_history
  * mcp-slack:find_decisions       -> conversations_history

PR-CONN-DB-DESCRIBE-SCHEMA-PROMOTE (2026-05-03):
arms real MCP execution for FOUR DB schema-introspection reads. Each
target_tool is a discrete read-only tool the vendor MCP exposes (NOT
a SQL execution path). mcp-postgres STAYS planned_only because the
archived reference Postgres MCP only ships a generic ``query`` tool;
introspection there would require constructing
``SELECT ... FROM information_schema...`` which the brief forbids
("No SQL execution beyond schema introspection tools"). Defense
test pins this decision so a future PR cannot stealth-promote it.

  * mcp-sqlite:describe_schema     -> list_tables
  * mcp-mongodb:describe_collections -> db-list-collections
  * mcp-supabase:describe_schema   -> list_tables  (schemas=['public'])
  * mcp-neon:describe_schema       -> get_database_tables

ALL OTHER allowlist entries remain ``planned_only``.

Why "spine, not engine":
  * The founder's brief explicitly says: "if actual connector
    implementation is not safely available for a skill, return
    planned/needs_connection rather than fake execution."
  * Each integration (GitHub MCP, Gmail OAuth, Drive OAuth, ...)
    needs its own per-tool argument derivation, response shape
    contract, and read-only verification. That's per-integration
    work, not a Phase 2 deliverable.
  * The spine + audit + UI are independently valuable:
      - audit row proves Daena recorded the request
      - allowlist gate proves no write skill can sneak through
      - UI "Run read-only skill" button surfaces the intent
      - planned preview shows operator EXACTLY what would happen

Hard rules enforced here (founder Phase 2 brief):
  9.  Do not execute write tools.
  10. Do not execute payment/refund/subscription tools.
  11. Do not execute browser actions.
  12. Do not auto-send chat messages.
  14. Do not promote any Phase 1 BLOCKED_* skill.
  15. Do not allow a skill unless it is explicitly in the
      Phase 2 read-only allowlist.
  16. If a tool cannot be proven read-only, block it.

Outputs are designed so a Phase 3 PR can flip ``execution_mode`` from
``planned_only`` to ``mcp_tool`` for one integration at a time
without changing the executor or the frontend contract.

Honesty (project Rule 17):
  * Every result carries an ``audit_event_id`` referencing the
    parent ``plugin.skill_invocation`` audit row.
  * No secret values cross any boundary -- the planned preview
    only describes tool names and operator-visible argument shapes.
  * If the plugin V2 row is not callable, status=needs_connection
    (no preview, no audit "executed" claim).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services.audit import AuditService

logger = get_logger(__name__)


# Real-execution timeout for promoted skills. Keep modest -- a single
# read-only MCP call should resolve well inside this window. Beyond
# this, we return blocked(reason=mcp_tool_timeout) so the operator
# never sees a hung Run button.
_MCP_EXEC_TIMEOUT_SECONDS: float = 12.0


# Trim the operator-facing summary to keep responses small and avoid
# carrying multi-MB MCP payloads back through the API. Full content
# stays inside the MCP boundary -- only a hash + summary cross.
_RESULT_SUMMARY_MAX_CHARS: int = 1200


# ──────────────────────────────────────────────────────────────────
# Types
# ──────────────────────────────────────────────────────────────────


# Status vocabulary surfaced to the operator. Matches the founder's
# Phase 2 brief output shape.
SkillExecutionStatus = Literal[
    "planned",         # spine ran, audit written, no tool fired (Phase 2 default)
    "executed",        # tool fired, result returned (NOT used in Phase 2 -- reserved)
    "blocked",         # not in allowlist OR write/browser/payment skill
    "needs_connection",  # plugin V2 row not callable
    "needs_inputs",    # required_inputs missing from operator
    "unsupported",     # plugin/skill pair not registered at all
]


# Backend surface a skill maps to. Used by the result preview so the
# operator knows what KIND of integration would be invoked.
BackendSurface = Literal["mcp", "oauth", "internal", "none"]


# Per-skill execution mode in the allowlist. Phase 2 ships
# ``planned_only`` for everything; subsequent PRs can promote.
SkillExecutionMode = Literal["planned_only", "mcp_tool"]


@dataclass(frozen=True)
class SkillToolMapping:
    """Typed entry in the Phase 2 read-only allowlist.

    One per (plugin_id, skill_id) pair we are willing to execute or
    plan in Phase 2. Skills NOT in this table return status=blocked
    with reason="not_in_phase2_allowlist".
    """

    plugin_id: str
    skill_id: str
    backend_surface: BackendSurface
    read_only: bool                       # MUST be True for any allowlist entry
    execution_mode: SkillExecutionMode    # Phase 2 = "planned_only" everywhere
    # The MCP tool name (or OAuth API method) the eventual executor
    # would call. Surfaced in the planned preview so the operator can
    # see exactly which underlying call this maps to.
    target_tool: str
    # Human-readable list of what fields the operator must provide for
    # the executor (or eventual executor) to know what to do.
    required_inputs: tuple[str, ...]
    # One-line operator-facing description of what data this skill
    # would READ (never write). Surfaced in the confirmation modal.
    reads_summary: str
    # Optional plan-only override reason (e.g. database safe_query
    # MUST stay plan-only even in later phases per Rule 16).
    plan_only_reason: str = ""


@dataclass
class PlannedToolCall:
    """One audit/preview record describing what would be called.

    NEVER carries secret values. The operator-facing preview shows
    only tool name + the SHAPE of arguments + the SOURCE of each
    argument value (operator-supplied vs catalog-defaulted), not
    the values themselves.
    """

    backend_surface: str
    tool_name: str
    argument_shape: dict[str, str]   # key -> "operator-input" | "catalog-default" | "tenant-scoped"
    read_only: bool
    plugin_id: str
    skill_id: str


@dataclass
class SkillExecutionResult:
    """Output of ``SkillExecutor.execute`` per the founder's brief shape.

    Always returns a value -- failures are statuses, not exceptions.
    Exceptions only happen for genuine programmer error (DB down,
    unhandled type) and are caught at the API boundary so the
    operator gets a clear error.
    """

    accepted: bool
    status: SkillExecutionStatus
    summary: str
    audit_event_id: str | None = None
    required_inputs: list[str] = field(default_factory=list)
    tool_calls: list[PlannedToolCall] = field(default_factory=list)
    result_preview: str = ""
    blocked_reason: str = ""

    def to_dict(self) -> dict:
        """Serialize to API response shape -- no secret values, no
        ConnectionV2 row internals, no DB IDs leaked beyond the
        audit_event_id which is intentionally exposed for traceability."""
        return {
            "accepted": self.accepted,
            "status": self.status,
            "summary": self.summary,
            "audit_event_id": self.audit_event_id,
            "required_inputs": list(self.required_inputs),
            "tool_calls": [
                {
                    "backend_surface": tc.backend_surface,
                    "tool_name": tc.tool_name,
                    "argument_shape": dict(tc.argument_shape),
                    "read_only": tc.read_only,
                    "plugin_id": tc.plugin_id,
                    "skill_id": tc.skill_id,
                }
                for tc in self.tool_calls
            ],
            "result_preview": self.result_preview,
            "blocked_reason": self.blocked_reason,
        }


# ──────────────────────────────────────────────────────────────────
# Phase 2 read-only allowlist
# ──────────────────────────────────────────────────────────────────


# Each entry MUST have read_only=True (enforced at module load below).
# The execution_mode field stays ``planned_only`` for ALL Phase 2
# entries -- subsequent PRs promote individual integrations to
# ``mcp_tool`` after end-to-end verification.
#
# Mirrors the founder's Phase 2 starter list:
#   GitHub: summarize_repo / triage_issues / inspect_ci_failure
#   Gmail: summarize_unread / search_email_context
#   Google Drive: find_documents / summarize_file
#   Slack: summarize_channel / find_decisions
#   Sentry: summarize_errors
#   HuggingFace: find_model / inspect_paper
#   Filesystem: find_files / summarize_directory
#   Databases: describe_schema only (safe_query stays plan-only forever)
PHASE2_ALLOWLIST: tuple[SkillToolMapping, ...] = (
    # ── GitHub (mcp-github, MEDIUM risk plugin, READ skills) ──
    # PROMOTED in PR-CONN-PHASE2X-GITHUB-SENTRY-READONLY:
    # all three read-only GitHub skills now run real tools/call. The
    # MCP server itself owns auth via GITHUB_PERSONAL_ACCESS_TOKEN
    # in its env -- executor only forwards operator inputs (owner,
    # repo, run_id), never the token.
    SkillToolMapping(
        plugin_id="mcp-github",
        skill_id="summarize_repo",
        backend_surface="mcp",
        read_only=True,
        execution_mode="mcp_tool",
        target_tool="get_repository",
        required_inputs=("repo_owner", "repo_name"),
        reads_summary=(
            "Public + private repo metadata: name, description, primary "
            "language, recent commits, open issue count."
        ),
    ),
    SkillToolMapping(
        plugin_id="mcp-github",
        skill_id="triage_issues",
        backend_surface="mcp",
        read_only=True,
        execution_mode="mcp_tool",
        target_tool="list_issues",
        required_inputs=("repo_owner", "repo_name"),
        reads_summary=(
            "Open issues + their labels, assignees, comment count, "
            "and last-updated timestamp."
        ),
    ),
    SkillToolMapping(
        plugin_id="mcp-github",
        skill_id="inspect_ci_failure",
        backend_surface="mcp",
        read_only=True,
        execution_mode="mcp_tool",
        target_tool="get_workflow_run_logs",
        required_inputs=("repo_owner", "repo_name", "run_id_or_sha"),
        reads_summary=(
            "GitHub Actions workflow logs for the specified run. Reads "
            "step output text -- does not retry or rerun the workflow."
        ),
    ),

    # ── Gmail (app-gmail, OAuth, READ skills) ──
    SkillToolMapping(
        plugin_id="app-gmail",
        skill_id="summarize_unread",
        backend_surface="oauth",
        read_only=True,
        execution_mode="planned_only",
        target_tool="messages.list_unread",
        required_inputs=("label_or_query", "time_window"),
        reads_summary=(
            "Subject + sender + snippet of unread Gmail messages within "
            "the requested label/time window. Does not mark messages "
            "read; does not send anything."
        ),
    ),
    SkillToolMapping(
        plugin_id="app-gmail",
        skill_id="search_email_context",
        backend_surface="oauth",
        read_only=True,
        execution_mode="planned_only",
        target_tool="messages.search",
        required_inputs=("query", "time_window"),
        reads_summary=(
            "Search Gmail by query string + time window. Returns "
            "matching message metadata + snippets for the operator "
            "to summarize. Does not modify or send."
        ),
    ),

    # ── Google Drive (app-google-drive, OAuth, READ skills) ──
    SkillToolMapping(
        plugin_id="app-google-drive",
        skill_id="find_documents",
        backend_surface="oauth",
        read_only=True,
        execution_mode="planned_only",
        target_tool="files.list",
        required_inputs=("query", "folder_id_or_root"),
        reads_summary=(
            "Drive files matching query (name, fullText, owners, "
            "lastModifiedTime). Returns metadata only -- does not open, "
            "share, or modify any file."
        ),
    ),
    SkillToolMapping(
        plugin_id="app-google-drive",
        skill_id="summarize_file",
        backend_surface="oauth",
        read_only=True,
        execution_mode="planned_only",
        target_tool="files.get_content",
        required_inputs=("file_id_or_url",),
        reads_summary=(
            "Read text content of a Google Doc or supported file type "
            "for summarization. Does not write back, comment, or share."
        ),
    ),

    # ── Slack (mcp-slack, MEDIUM risk, READ skills) ──
    # PROMOTED in PR-CONN-PHASE2X-SLACK-GMAIL-DRIVE-READONLY (2026-05-03):
    # both summarize_channel + find_decisions run real tools/call now
    # via the existing stdio MCP path. The MCP server itself owns the
    # Slack token via SLACK_BOT_TOKEN env -- executor never sees it.
    # NOTE: draft_reply is NOT in Phase 2 allowlist (founder rule 7).
    SkillToolMapping(
        plugin_id="mcp-slack",
        skill_id="summarize_channel",
        backend_surface="mcp",
        read_only=True,
        execution_mode="mcp_tool",
        target_tool="conversations_history",
        required_inputs=("channel", "time_window"),
        reads_summary=(
            "Read messages from a Slack channel within the requested "
            "time window. Does not post anything; does not mark messages "
            "read; does not modify channel state."
        ),
    ),
    SkillToolMapping(
        plugin_id="mcp-slack",
        skill_id="find_decisions",
        backend_surface="mcp",
        read_only=True,
        execution_mode="mcp_tool",
        target_tool="conversations_history",
        required_inputs=("channel", "time_window"),
        reads_summary=(
            "Same channel-history read as summarize_channel, but the "
            "summarizer extracts decision-shaped messages (owner + "
            "decision + permalink). Read-only."
        ),
    ),

    # ── Sentry (mcp-sentry, LOW risk, READ skill) ──
    # PROMOTED in PR-CONN-PHASE2X-GITHUB-SENTRY-READONLY: real exec.
    # Sentry MCP owns auth via SENTRY_AUTH_TOKEN in its env -- the
    # executor never sees the token. Required org_slug+project_slug
    # are operator-supplied; the MCP enforces tenant scoping.
    SkillToolMapping(
        plugin_id="mcp-sentry",
        skill_id="summarize_errors",
        backend_surface="mcp",
        read_only=True,
        execution_mode="mcp_tool",
        target_tool="list_issues",
        required_inputs=("project_slug", "time_window"),
        reads_summary=(
            "Sentry issues for the specified project within the time "
            "window. Read metadata: title, frequency, first/last seen, "
            "stack-trace summary. Does not assign, resolve, or create "
            "tickets."
        ),
    ),

    # ── Hugging Face (mcp-huggingface, LOW risk, READ skills) ──
    # PROMOTED in PR-CONN-PHASE2X-FILESYSTEM-HUGGINGFACE-READONLY:
    # both find_model + inspect_paper run real tools/call now. Public
    # Hub data; no private repos; no weight downloads triggered.
    SkillToolMapping(
        plugin_id="mcp-huggingface",
        skill_id="find_model",
        backend_surface="mcp",
        read_only=True,
        execution_mode="mcp_tool",
        target_tool="hub_repo_search",
        required_inputs=("task_or_keywords",),
        reads_summary=(
            "Public Hugging Face Hub model search by task + keywords. "
            "Returns metadata: model id, downloads, license, last "
            "updated. No private repos, no model weights downloaded."
        ),
    ),
    SkillToolMapping(
        plugin_id="mcp-huggingface",
        skill_id="inspect_paper",
        backend_surface="mcp",
        read_only=True,
        execution_mode="mcp_tool",
        target_tool="paper_search",
        required_inputs=("arxiv_id_or_title",),
        reads_summary=(
            "Hugging Face papers index lookup. Returns abstract + "
            "linked models + citation count. Public data only."
        ),
    ),

    # ── Filesystem (mcp-filesystem, MEDIUM risk -- sandboxed, READ skills) ──
    # PROMOTED in PR-CONN-PHASE2X-FILESYSTEM-HUGGINGFACE-READONLY:
    # both find_files + summarize_directory run real tools/call now.
    # The MCP server itself enforces the sandbox root; the operator's
    # root_path input is the search root within that sandbox.
    SkillToolMapping(
        plugin_id="mcp-filesystem",
        skill_id="find_files",
        backend_surface="mcp",
        read_only=True,
        execution_mode="mcp_tool",
        target_tool="search_files",
        required_inputs=("root_path", "name_or_glob"),
        reads_summary=(
            "Sandboxed filesystem search within an allowed root. Returns "
            "paths + sizes + last-modified. Does not read file contents "
            "and does not write anything."
        ),
    ),
    SkillToolMapping(
        plugin_id="mcp-filesystem",
        skill_id="summarize_directory",
        backend_surface="mcp",
        read_only=True,
        execution_mode="mcp_tool",
        target_tool="list_directory",
        required_inputs=("root_path",),
        reads_summary=(
            "Sandboxed listing of a directory's immediate contents. "
            "Returns names, sizes, types. Does not recurse beyond one "
            "level by default and never writes."
        ),
    ),

    # ── Databases: describe_schema ONLY ──
    # safe_query stays Phase 1 plan-only forever per founder rule 16
    # (cannot be proven read-only without per-query SQL parsing).
    #
    # PR-CONN-DB-DESCRIBE-SCHEMA-PROMOTE (2026-05-03): 4 of the 5 DB
    # entries promoted to mcp_tool. mcp-postgres STAYS planned because
    # the archived reference Postgres MCP exposes only `query` (no
    # discrete schema introspection tool), so introspection requires
    # SQL execution which the brief explicitly forbids. The other four
    # MCPs ship discrete read-only tools we can call without SQL
    # construction:
    #   - mcp-sqlite ........ list_tables
    #   - mcp-mongodb ....... db-list-collections
    #   - mcp-supabase ...... list_tables
    #   - mcp-neon .......... get_database_tables
    SkillToolMapping(
        plugin_id="mcp-postgres",
        skill_id="describe_schema",
        backend_surface="mcp",
        read_only=True,
        execution_mode="planned_only",
        target_tool="describe_schema",
        required_inputs=("database",),
        reads_summary=(
            "Postgres schema introspection: tables, columns, types, "
            "indexes. No row data read. No DDL or DML executed. "
            "Stays planned: archived ref MCP exposes only `query`, "
            "which would require SQL construction here."
        ),
    ),
    SkillToolMapping(
        plugin_id="mcp-sqlite",
        skill_id="describe_schema",
        backend_surface="mcp",
        read_only=True,
        execution_mode="mcp_tool",
        # SQLite reference MCP exposes a discrete `list_tables` tool
        # that returns the names + types of tables. Pure metadata.
        target_tool="list_tables",
        required_inputs=(),
        reads_summary=(
            "SQLite schema: list of tables in the database the MCP "
            "was launched against. Read-only metadata. The MCP owns "
            "the database path -- the operator does NOT pass it."
        ),
    ),
    SkillToolMapping(
        plugin_id="mcp-supabase",
        skill_id="describe_schema",
        backend_surface="mcp",
        read_only=True,
        execution_mode="mcp_tool",
        # Supabase vendor MCP exposes `list_tables` returning the
        # public-schema tables + columns. Read-only.
        target_tool="list_tables",
        required_inputs=("project_ref",),
        reads_summary=(
            "Supabase schema: public-schema tables + columns. No row "
            "data, no auth records, no storage objects read."
        ),
    ),
    SkillToolMapping(
        plugin_id="mcp-neon",
        skill_id="describe_schema",
        backend_surface="mcp",
        read_only=True,
        execution_mode="mcp_tool",
        # Neon vendor MCP exposes `get_database_tables` returning
        # tables for a given Neon project. Read-only metadata.
        target_tool="get_database_tables",
        required_inputs=("project_id",),
        reads_summary=(
            "Neon Postgres schema for the project's default branch. "
            "Read-only metadata. Does not list snapshots or modify "
            "branches."
        ),
    ),
    SkillToolMapping(
        plugin_id="mcp-mongodb",
        skill_id="describe_collections",
        backend_surface="mcp",
        read_only=True,
        execution_mode="mcp_tool",
        # MongoDB vendor MCP exposes `db-list-collections` returning
        # collection names + counts for a database. Pure metadata --
        # NEVER touches document content.
        target_tool="db-list-collections",
        required_inputs=("database",),
        reads_summary=(
            "MongoDB collection listing for the named database. "
            "Returns collection names only. Never reads document "
            "content, never returns sample values."
        ),
    ),
)


# Module-load invariant: every allowlist entry MUST be read-only.
# Any future maintainer who adds a write skill here will fail at
# import time, before a single request can hit the executor.
def _validate_allowlist_at_import() -> None:
    for entry in PHASE2_ALLOWLIST:
        if not entry.read_only:
            raise RuntimeError(
                f"Phase 2 allowlist entry {entry.plugin_id}:{entry.skill_id} "
                f"has read_only=False. Phase 2 cannot ship write skills. "
                f"If you need to add this skill, route it through a Phase 3+ "
                f"PR with Asset Shield consent + per-tool verification."
            )


_validate_allowlist_at_import()


# Index for O(1) lookup.
_ALLOWLIST_BY_KEY: dict[tuple[str, str], SkillToolMapping] = {
    (e.plugin_id, e.skill_id): e for e in PHASE2_ALLOWLIST
}


def is_allowlisted(plugin_id: str, skill_id: str) -> bool:
    """Public coverage check. Used by the frontend "Run read-only skill"
    button visibility logic."""
    return (plugin_id, skill_id) in _ALLOWLIST_BY_KEY


def get_allowlist_entry(
    plugin_id: str, skill_id: str,
) -> SkillToolMapping | None:
    """Return the typed mapping or None for non-allowlisted pairs."""
    return _ALLOWLIST_BY_KEY.get((plugin_id, skill_id))


def list_allowlist_for_api() -> list[dict]:
    """Display-safe allowlist dump for the frontend (no secrets, no
    backend internals -- just plugin_id, skill_id, required_inputs,
    reads_summary)."""
    return [
        {
            "plugin_id": e.plugin_id,
            "skill_id": e.skill_id,
            "backend_surface": e.backend_surface,
            "read_only": e.read_only,
            "execution_mode": e.execution_mode,
            "required_inputs": list(e.required_inputs),
            "reads_summary": e.reads_summary,
        }
        for e in PHASE2_ALLOWLIST
    ]


# ──────────────────────────────────────────────────────────────────
# Executor service
# ──────────────────────────────────────────────────────────────────


class SkillExecutor:
    """Spine for Phase 2 read-only skill execution.

    Every public ``execute`` call:
      1. Looks up the (plugin, skill) pair in PHASE2_ALLOWLIST.
      2. If absent or read_only=False -> blocked.
      3. Checks plugin V2 row truth: must be callable.
      4. If required_inputs missing -> needs_inputs.
      5. Builds a PlannedToolCall preview describing what WOULD run.
      6. Writes the parent ``plugin.skill_invocation`` audit row.
      7. Returns status="planned" with the preview.

    Phase 2 NEVER calls ``mcp_invoker.call_server_tool``. The transition
    to ``status="executed"`` happens in follow-up PRs that promote one
    integration at a time after end-to-end safety verification.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._audit = AuditService(db)

    async def execute(
        self,
        *,
        plugin_id: str,
        skill_id: str,
        tenant_id: UUID,
        user_id: UUID,
        operator_inputs: dict[str, str] | None = None,
    ) -> SkillExecutionResult:
        """Run the Phase 2 spine for one skill request.

        Returns a typed result. Never raises for invariant violations
        (allowlist miss, missing inputs, plugin not callable) -- those
        return as statuses so the audit row captures intent honestly.
        """
        operator_inputs = dict(operator_inputs or {})

        # Step 1: allowlist lookup.
        entry = get_allowlist_entry(plugin_id, skill_id)
        if entry is None:
            return await self._record_blocked(
                plugin_id=plugin_id,
                skill_id=skill_id,
                tenant_id=tenant_id,
                user_id=user_id,
                reason="not_in_phase2_allowlist",
                summary=(
                    f"Skill {plugin_id}:{skill_id} is not in the Phase 2 "
                    f"read-only allowlist. Phase 1 chat-draft is still "
                    f"available."
                ),
            )

        # Step 2: read-only gate (defense in depth -- the import-time
        # invariant should already prevent any read_only=False entry from
        # reaching here, but we re-check at execute time so a future
        # mutation of PHASE2_ALLOWLIST can't slip past).
        if not entry.read_only:
            return await self._record_blocked(
                plugin_id=plugin_id,
                skill_id=skill_id,
                tenant_id=tenant_id,
                user_id=user_id,
                reason="not_read_only",
                summary=(
                    f"Skill {plugin_id}:{skill_id} is not marked read-only. "
                    f"Phase 2 only executes proven read-only skills."
                ),
            )

        # Step 3: plugin V2 truth -- must be callable.
        callable_ok = await self._is_plugin_callable(
            plugin_id=plugin_id, tenant_id=tenant_id,
        )
        if not callable_ok:
            return await self._record_blocked(
                plugin_id=plugin_id,
                skill_id=skill_id,
                tenant_id=tenant_id,
                user_id=user_id,
                reason="plugin_not_callable",
                status_override="needs_connection",
                summary=(
                    f"Plugin {plugin_id} has not reached callable status "
                    f"in the V2 truth ladder. Connect + probe it before "
                    f"running skills."
                ),
            )

        # Step 4: required-inputs check.
        missing = [
            field for field in entry.required_inputs
            if not operator_inputs.get(field, "").strip()
        ]
        if missing:
            return await self._record_planned_or_blocked(
                entry=entry,
                tenant_id=tenant_id,
                user_id=user_id,
                operator_inputs=operator_inputs,
                final_status="needs_inputs",
                missing_inputs=missing,
                summary=(
                    f"Skill {plugin_id}:{skill_id} needs the following "
                    f"inputs before it can run: {', '.join(missing)}."
                ),
            )

        # Step 5: branch on execution_mode.
        #   * planned_only -> existing spine path (write planned audit row)
        #   * mcp_tool     -> real MCP tools/call (Phase 2.x promotions)
        if entry.execution_mode == "mcp_tool":
            return await self._execute_real_mcp_tool(
                entry=entry,
                tenant_id=tenant_id,
                user_id=user_id,
                operator_inputs=operator_inputs,
            )

        # Default planned-only path (vast majority of allowlist).
        return await self._record_planned_or_blocked(
            entry=entry,
            tenant_id=tenant_id,
            user_id=user_id,
            operator_inputs=operator_inputs,
            final_status="planned",
            summary=(
                f"Phase 2 spine accepted {plugin_id}:{skill_id}. "
                f"This run would invoke the {entry.backend_surface.upper()} "
                f"tool '{entry.target_tool}' read-only. Phase 2 returns "
                f"a planned preview only -- actual execution arms in a "
                f"follow-up PR after per-integration safety verification."
            ),
        )

    # ──────────────────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────────────────

    async def _is_plugin_callable(
        self, *, plugin_id: str, tenant_id: UUID,
    ) -> bool:
        """Check the V2 truth ladder for ``callable=True`` on this plugin.

        Resolves the catalog entry's ``matches_v2_slug`` against the
        ``ConnectionV2`` table. Failure modes (no V2 row, no match)
        return False -- conservative by design.

        Note: this does NOT trigger a fresh probe. It reads the most
        recent stored truth. The frontend ensures the operator sees
        only the current callable state.
        """
        try:
            from app.services.connection_v2.marketplace_catalog import CATALOG
            from sqlalchemy import select
            from app.models.connection_v2 import ConnectionV2

            entry = next((e for e in CATALOG if e.id == plugin_id), None)
            if entry is None or not entry.matches_v2_slug:
                return False
            row = (
                await self.db.execute(
                    select(ConnectionV2).where(
                        ConnectionV2.tenant_id == tenant_id,
                        ConnectionV2.slug == entry.matches_v2_slug,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            return bool(row.callable)
        except Exception as exc:
            # Logged but treated as not-callable. Conservative.
            logger.warning(
                "skill_executor.callable_check_failed",
                plugin_id=plugin_id, error=str(exc),
            )
            return False

    async def _record_blocked(
        self,
        *,
        plugin_id: str,
        skill_id: str,
        tenant_id: UUID,
        user_id: UUID,
        reason: str,
        summary: str,
        status_override: SkillExecutionStatus | None = None,
    ) -> SkillExecutionResult:
        """Write an audit row for a blocked attempt and return the result."""
        audit = await self._audit.log_decision(
            tenant_id=tenant_id,
            actor_id=user_id,
            actor_type="USER",
            action_type="plugin.skill_invocation",
            action_params={
                "plugin_id": plugin_id,
                "skill_id": skill_id,
                "phase": "phase2_readonly",
                "outcome": status_override or "blocked",
                "blocked_reason": reason,
                "allowlist_match": False,
                "read_only": True,
                # Never log operator_inputs values -- only their KEY NAMES,
                # and only if they were supplied. Keeps PII out of the
                # audit trail by construction.
            },
            result="BLOCKED" if not status_override else "INFO",
            risk_level="LOW",
            governance_tier=2,
        )
        return SkillExecutionResult(
            accepted=False,
            status=status_override or "blocked",
            summary=summary,
            audit_event_id=str(audit.get("id") or ""),
            blocked_reason=reason,
        )

    async def _record_planned_or_blocked(
        self,
        *,
        entry: SkillToolMapping,
        tenant_id: UUID,
        user_id: UUID,
        operator_inputs: dict[str, str],
        final_status: SkillExecutionStatus,
        summary: str,
        missing_inputs: list[str] | None = None,
    ) -> SkillExecutionResult:
        """Build the planned-tool preview, write audit, return."""
        argument_shape: dict[str, str] = {}
        for field in entry.required_inputs:
            if field in operator_inputs and operator_inputs[field].strip():
                argument_shape[field] = "operator-input"
            else:
                argument_shape[field] = "MISSING"
        # Tenant-scoping is implicit for OAuth surfaces; declare it
        # in the shape so the operator sees Daena tracks scope.
        if entry.backend_surface == "oauth":
            argument_shape["_auth_scope"] = "tenant-scoped"

        planned = PlannedToolCall(
            backend_surface=entry.backend_surface,
            tool_name=entry.target_tool,
            argument_shape=argument_shape,
            read_only=entry.read_only,
            plugin_id=entry.plugin_id,
            skill_id=entry.skill_id,
        )
        result_preview = (
            f"Would invoke {entry.backend_surface.upper()} tool "
            f"'{entry.target_tool}' to read: {entry.reads_summary}"
        )

        audit = await self._audit.log_decision(
            tenant_id=tenant_id,
            actor_id=user_id,
            actor_type="USER",
            action_type="plugin.skill_invocation",
            action_params={
                "plugin_id": entry.plugin_id,
                "skill_id": entry.skill_id,
                "phase": "phase2_readonly",
                "outcome": final_status,
                "allowlist_match": True,
                "read_only": entry.read_only,
                "execution_mode": entry.execution_mode,
                "backend_surface": entry.backend_surface,
                "target_tool": entry.target_tool,
                "argument_shape": argument_shape,
                # ^ shape only; never values
                "missing_inputs": list(missing_inputs or []),
            },
            result="ALLOWED" if final_status == "planned" else "INFO",
            risk_level="LOW",
            governance_tier=2,
        )

        return SkillExecutionResult(
            accepted=(final_status == "planned"),
            status=final_status,
            summary=summary,
            audit_event_id=str(audit.get("id") or ""),
            required_inputs=list(missing_inputs or []),
            tool_calls=[planned] if final_status == "planned" else [],
            result_preview=result_preview if final_status == "planned" else "",
        )

    # ──────────────────────────────────────────────────────────
    # Real MCP execution path (Phase 2.x promotions)
    # ──────────────────────────────────────────────────────────

    async def _execute_real_mcp_tool(
        self,
        *,
        entry: SkillToolMapping,
        tenant_id: UUID,
        user_id: UUID,
        operator_inputs: dict[str, str],
    ) -> SkillExecutionResult:
        """Run a promoted Phase 2.x MCP skill end-to-end.

        Five outcomes:
          1. MCP not installed in bootstrap registry -> needs_connection
          2. MCP call succeeded -> status=executed + summary + result_hash
          3. MCP call returned is_error=True -> blocked + reason=mcp_tool_error
          4. MCP call timed out -> blocked + reason=mcp_tool_timeout
          5. Unexpected exception -> blocked + reason=mcp_tool_exception

        Audit row carries:
          * outcome           = executed / mcp_error / mcp_timeout / needs_connection
          * executed_tool     = the actual MCP tool name we asked to call
          * server_key        = the bootstrap registry key we resolved
          * result_summary_length    = chars in operator-facing summary
          * result_content_hash_prefix = SHA256[:8] of joined raw text
            (proves we did receive content without storing the content)

        NEVER carries the raw MCP content into the audit row. The hash
        + summary lets us prove a call succeeded without persisting
        possibly-sensitive read data into governance audit storage.
        """
        # Late import to keep skill_executor import-light at module load
        # (mcp_invoker pulls in the MCP SDK + asyncio plumbing).
        from app.services.mcp_invoker import call_server_tool
        from app.services.mcp_bootstrap import get_installed_mcp

        # 1. Resolve which bootstrap registry key serves this plugin.
        server_key = _resolve_mcp_server_key(entry.plugin_id)
        if server_key is None or get_installed_mcp(server_key) is None:
            return await self._record_real_outcome(
                entry=entry,
                tenant_id=tenant_id,
                user_id=user_id,
                operator_inputs=operator_inputs,
                final_status="needs_connection",
                outcome="needs_connection",
                summary=(
                    f"Plugin {entry.plugin_id} maps to MCP server "
                    f"'{server_key or '?'}' but that server is not installed "
                    f"in the local MCP registry. Install it via the "
                    f"Connections > Plugins UI, then retry."
                ),
                blocked_reason="mcp_not_installed",
                executed_tool=entry.target_tool,
                server_key=server_key or "",
                result_text="",
            )

        # 2. Build the MCP arguments from operator inputs.
        mcp_args = _build_mcp_arguments(entry, operator_inputs)

        # 3. Invoke the tool. mcp_invoker enforces its own timeout but
        #    we pin a tighter ceiling for read-only skills here.
        try:
            invoke_result = await call_server_tool(
                server_key,
                entry.target_tool,
                mcp_args,
                timeout=_MCP_EXEC_TIMEOUT_SECONDS,
            )
        except Exception as exc:  # pragma: no cover - belt + suspenders
            logger.warning(
                "skill_executor.mcp_call_exception",
                plugin_id=entry.plugin_id,
                skill_id=entry.skill_id,
                server_key=server_key,
                tool_name=entry.target_tool,
                error=str(exc),
            )
            return await self._record_real_outcome(
                entry=entry,
                tenant_id=tenant_id,
                user_id=user_id,
                operator_inputs=operator_inputs,
                final_status="blocked",
                outcome="mcp_exception",
                summary=(
                    f"Calling {entry.plugin_id}:{entry.skill_id} failed "
                    f"unexpectedly. The MCP server raised before completing."
                ),
                blocked_reason="mcp_tool_exception",
                executed_tool=entry.target_tool,
                server_key=server_key,
                result_text="",
            )

        # 4. Classify the invoker outcome.
        if not invoke_result.get("success"):
            err = str(invoke_result.get("error") or "MCP call failed")
            timed_out = "timed out" in err.lower()
            return await self._record_real_outcome(
                entry=entry,
                tenant_id=tenant_id,
                user_id=user_id,
                operator_inputs=operator_inputs,
                final_status="blocked",
                outcome=("mcp_timeout" if timed_out else "mcp_error"),
                summary=(
                    f"{entry.plugin_id}:{entry.skill_id} could not run -- "
                    f"the MCP server returned: {err}"
                ),
                blocked_reason=("mcp_tool_timeout" if timed_out else "mcp_tool_error"),
                executed_tool=entry.target_tool,
                server_key=server_key,
                result_text="",
            )

        # 5. Success path: build summary, hash content, record.
        raw_text = _flatten_mcp_content(invoke_result.get("content") or [])
        summary_text = _summarize_mcp_result(entry, raw_text)
        return await self._record_real_outcome(
            entry=entry,
            tenant_id=tenant_id,
            user_id=user_id,
            operator_inputs=operator_inputs,
            final_status="executed",
            outcome="success",
            summary=summary_text,
            blocked_reason="",
            executed_tool=entry.target_tool,
            server_key=server_key,
            result_text=raw_text,
        )

    async def _record_real_outcome(
        self,
        *,
        entry: SkillToolMapping,
        tenant_id: UUID,
        user_id: UUID,
        operator_inputs: dict[str, str],
        final_status: SkillExecutionStatus,
        outcome: str,
        summary: str,
        blocked_reason: str,
        executed_tool: str,
        server_key: str,
        result_text: str,
    ) -> SkillExecutionResult:
        """Common audit + response builder for the real-exec path.

        Records the *parent* plugin.skill_invocation audit row with the
        execution outcome metadata. Never stores raw content -- only
        hash + length so we can prove "a real read happened" without
        persisting possibly-sensitive read data.
        """
        # Argument shape (provenance only, no values).
        argument_shape: dict[str, str] = {}
        for f in entry.required_inputs:
            argument_shape[f] = (
                "operator-input"
                if operator_inputs.get(f, "").strip()
                else "MISSING"
            )
        if entry.backend_surface == "oauth":
            argument_shape["_auth_scope"] = "tenant-scoped"

        # Hash the result text so the audit row carries proof-of-content
        # without the content itself. SHA-256[:8] is enough for an
        # operator-readable fingerprint; collisions don't matter here.
        result_hash_prefix = (
            hashlib.sha256(result_text.encode("utf-8", errors="ignore")).hexdigest()[:8]
            if result_text
            else ""
        )

        planned = PlannedToolCall(
            backend_surface=entry.backend_surface,
            tool_name=entry.target_tool,
            argument_shape=argument_shape,
            read_only=entry.read_only,
            plugin_id=entry.plugin_id,
            skill_id=entry.skill_id,
        )

        audit = await self._audit.log_decision(
            tenant_id=tenant_id,
            actor_id=user_id,
            actor_type="USER",
            action_type="plugin.skill_invocation",
            action_params={
                "plugin_id": entry.plugin_id,
                "skill_id": entry.skill_id,
                "phase": "phase2x_readonly_real_exec",
                "outcome": outcome,
                "allowlist_match": True,
                "read_only": entry.read_only,
                "execution_mode": entry.execution_mode,
                "backend_surface": entry.backend_surface,
                "target_tool": entry.target_tool,
                "executed_tool": executed_tool,
                "server_key": server_key,
                "argument_shape": argument_shape,
                # ^ shape only; never values
                "blocked_reason": blocked_reason or None,
                "result_summary_length": len(summary or ""),
                "result_content_hash_prefix": result_hash_prefix or None,
                # NEVER include result_text. Operator-facing summary OK.
            },
            result=("ALLOWED" if final_status == "executed" else "BLOCKED"),
            risk_level="LOW",
            governance_tier=2,
        )

        return SkillExecutionResult(
            accepted=(final_status == "executed"),
            status=final_status,
            summary=summary,
            audit_event_id=str(audit.get("id") or ""),
            tool_calls=[planned],
            result_preview=summary if final_status == "executed" else "",
            blocked_reason=blocked_reason,
        )


# ──────────────────────────────────────────────────────────────────
# MCP wiring helpers (server_key resolution + arg builder + summarizer)
# ──────────────────────────────────────────────────────────────────


# Map plugin_id -> bootstrap registry server_key. The bootstrap key
# comes from the user's claude_desktop_config.json mcpServers map
# (see app/services/mcp_bootstrap.py). When multiple npm packages can
# serve the same plugin we pick the most-installed one; future PRs
# can resolve dynamically by reading catalog.mcp_servers and picking
# the first installed match.
_PLUGIN_TO_SERVER_KEY: dict[str, tuple[str, ...]] = {
    # Filesystem reference MCP. Two common keys -- try the canonical
    # first, then the npm-package key, then the catalog mcp_servers tag.
    "mcp-filesystem": (
        "filesystem",                 # common claude_desktop_config key
        "mcp-filesystem",
        "server-filesystem",          # catalog mcp_servers tag
        "@modelcontextprotocol/server-filesystem",
    ),
    # Hugging Face MCP. Local npm package OR HTTP-mode (huggingface.co/mcp)
    # would register under different keys; prefer the user's existing key.
    "mcp-huggingface": (
        "huggingface-mcp",            # what the user has in their config
        "mcp-huggingface",
        "huggingface",
    ),
    # GitHub MCP (github/github-mcp-server -- official). Typical
    # claude_desktop_config keys: 'github', 'github-mcp', 'github-mcp-server'.
    "mcp-github": (
        "github",
        "github-mcp",
        "github-mcp-server",
        "mcp-github",
        "@modelcontextprotocol/server-github",
    ),
    # Sentry MCP (@sentry/mcp-server). Typical keys:
    # 'sentry', 'sentry-mcp', 'mcp-sentry'.
    "mcp-sentry": (
        "sentry",
        "sentry-mcp",
        "mcp-sentry",
        "@sentry/mcp-server",
    ),
    # Slack MCP (modelcontextprotocol/server-slack). Typical keys:
    # 'slack', 'slack-mcp', 'mcp-slack'.
    "mcp-slack": (
        "slack",
        "slack-mcp",
        "mcp-slack",
        "@modelcontextprotocol/server-slack",
    ),
    # PR-CONN-DB-DESCRIBE-SCHEMA-PROMOTE (2026-05-03):
    # SQLite reference MCP. Typical claude_desktop_config keys are
    # 'sqlite' (preferred) or the uvx package id. The MCP launches
    # against a database path passed at startup -- our describe_schema
    # call does NOT carry a path; the MCP owns it.
    "mcp-sqlite": (
        "sqlite",
        "sqlite-mcp",
        "mcp-sqlite",
        "mcp-server-sqlite",
    ),
    # MongoDB Inc. vendor MCP. Distributed as `mongodb-mcp-server`
    # via npm; typical keys 'mongodb' or the package name.
    "mcp-mongodb": (
        "mongodb",
        "mongodb-mcp",
        "mcp-mongodb",
        "mongodb-mcp-server",
    ),
    # Supabase vendor MCP. Distributed as
    # `@supabase/mcp-server-supabase`; typical keys 'supabase' or the
    # package name.
    "mcp-supabase": (
        "supabase",
        "supabase-mcp",
        "mcp-supabase",
        "@supabase/mcp-server-supabase",
    ),
    # Neon vendor MCP (`@neondatabase/mcp-server-neon`). Typical keys
    # 'neon' or the package name.
    "mcp-neon": (
        "neon",
        "neon-mcp",
        "mcp-neon",
        "@neondatabase/mcp-server-neon",
    ),
}


def _resolve_mcp_server_key(plugin_id: str) -> str | None:
    """Return the first bootstrap registry key that resolves to an
    installed MCP for this plugin. Returns None if no candidate is
    installed."""
    from app.services.mcp_bootstrap import get_installed_mcp

    candidates = _PLUGIN_TO_SERVER_KEY.get(plugin_id, (plugin_id,))
    for key in candidates:
        if get_installed_mcp(key) is not None:
            return key
    # No candidate installed; return the FIRST candidate (preferred)
    # so the operator-facing error message names a sensible target.
    return candidates[0] if candidates else None


# Per-skill argument builders. Each function takes the operator_inputs
# dict (already validated for presence by the executor) and returns
# the dict shape the underlying MCP tool expects. We keep these small
# and explicit -- a generic mapper would obscure the per-skill contract.
def _args_filesystem_search_files(operator_inputs: dict[str, str]) -> dict[str, Any]:
    """@modelcontextprotocol/server-filesystem search_files args:
    path, pattern, excludePatterns?"""
    return {
        "path": operator_inputs["root_path"],
        "pattern": operator_inputs["name_or_glob"],
    }


def _args_filesystem_list_directory(operator_inputs: dict[str, str]) -> dict[str, Any]:
    """server-filesystem list_directory args: path"""
    return {"path": operator_inputs["root_path"]}


def _args_huggingface_find_model(operator_inputs: dict[str, str]) -> dict[str, Any]:
    """HF MCP hub_repo_search args: query (free text)."""
    return {"query": operator_inputs["task_or_keywords"]}


def _args_huggingface_inspect_paper(operator_inputs: dict[str, str]) -> dict[str, Any]:
    """HF MCP paper_search args: query (arxiv id or title)."""
    return {"query": operator_inputs["arxiv_id_or_title"]}


def _args_github_get_repository(operator_inputs: dict[str, str]) -> dict[str, Any]:
    """github-mcp-server get_repository args: owner, repo."""
    return {
        "owner": operator_inputs["repo_owner"],
        "repo": operator_inputs["repo_name"],
    }


def _args_github_list_issues(operator_inputs: dict[str, str]) -> dict[str, Any]:
    """github-mcp-server list_issues args: owner, repo, state.
    We pin state='open' for triage_issues so the executor never asks
    the MCP for closed/all-issue history (read-narrowing)."""
    return {
        "owner": operator_inputs["repo_owner"],
        "repo": operator_inputs["repo_name"],
        "state": "open",
    }


def _args_github_workflow_run_logs(operator_inputs: dict[str, str]) -> dict[str, Any]:
    """github-mcp-server get_workflow_run_logs args: owner, repo, run_id.
    The operator may supply either a numeric run id or a sha; the MCP
    accepts both (the server resolves sha -> run_id internally)."""
    return {
        "owner": operator_inputs["repo_owner"],
        "repo": operator_inputs["repo_name"],
        "run_id": operator_inputs["run_id_or_sha"],
    }


def _args_sentry_list_issues(operator_inputs: dict[str, str]) -> dict[str, Any]:
    """@sentry/mcp-server list_issues args: organizationSlug + projectSlug
    (+ optional query). We pass the operator's project_slug as
    projectSlug; time_window becomes a Sentry query filter
    (e.g. age:-7d). This keeps the read narrow + scoped."""
    return {
        "organizationSlug": operator_inputs.get("organization_slug", ""),
        "projectSlug": operator_inputs["project_slug"],
        "query": f"age:-{operator_inputs['time_window']}",
    }


def _args_slack_conversations_history(
    operator_inputs: dict[str, str],
) -> dict[str, Any]:
    """server-slack conversations_history args: channel (id or name) +
    optional limit. We translate the operator's time_window into a
    'limit' parameter heuristically (last N messages) since the
    Slack MCP doesn't accept a wall-clock window directly. Pinning
    a small upper bound (200) keeps the read narrow."""
    raw = operator_inputs.get("time_window", "100").strip()
    # Heuristic: '7d' -> 200 messages cap; numeric N -> use as limit.
    try:
        limit = max(1, min(200, int(raw)))
    except ValueError:
        # Time-window strings ('7d', '24h', etc.) collapse to a sane
        # default cap. Fine-grained age filtering happens in the MCP
        # consumer's downstream summarizer.
        limit = 100
    return {
        "channel": operator_inputs["channel"],
        "limit": limit,
    }


def _args_sqlite_list_tables(
    operator_inputs: dict[str, str],
) -> dict[str, Any]:
    """SQLite reference MCP `list_tables` takes NO arguments. The
    database path is supplied at MCP launch time (-db-path flag)
    and never crosses the operator/executor boundary. We pass an
    empty arg dict; ignored operator_inputs would still be safe but
    we drop them for clarity."""
    return {}


def _args_mongodb_list_collections(
    operator_inputs: dict[str, str],
) -> dict[str, Any]:
    """MongoDB vendor MCP `db-list-collections` args: database (str).
    The MCP returns collection names + counts. NEVER touches document
    content."""
    return {"database": operator_inputs["database"]}


def _args_supabase_list_tables(
    operator_inputs: dict[str, str],
) -> dict[str, Any]:
    """Supabase vendor MCP `list_tables` args: project_id + schemas.
    We pin schemas=['public'] to keep the read narrow -- never
    queries auth.* / storage.* / private schemas."""
    return {
        "project_id": operator_inputs["project_ref"],
        "schemas": ["public"],
    }


def _args_neon_get_database_tables(
    operator_inputs: dict[str, str],
) -> dict[str, Any]:
    """Neon vendor MCP `get_database_tables` args: project_id. The
    Neon MCP resolves to the project's default branch unless
    branch_id is also passed; we keep it narrow + default-only."""
    return {"projectId": operator_inputs["project_id"]}


_ARG_BUILDERS: dict[tuple[str, str], Any] = {
    ("mcp-filesystem", "find_files"): _args_filesystem_search_files,
    ("mcp-filesystem", "summarize_directory"): _args_filesystem_list_directory,
    ("mcp-huggingface", "find_model"): _args_huggingface_find_model,
    ("mcp-huggingface", "inspect_paper"): _args_huggingface_inspect_paper,
    ("mcp-github", "summarize_repo"): _args_github_get_repository,
    ("mcp-github", "triage_issues"): _args_github_list_issues,
    ("mcp-github", "inspect_ci_failure"): _args_github_workflow_run_logs,
    ("mcp-sentry", "summarize_errors"): _args_sentry_list_issues,
    ("mcp-slack", "summarize_channel"): _args_slack_conversations_history,
    ("mcp-slack", "find_decisions"): _args_slack_conversations_history,
    # PR-CONN-DB-DESCRIBE-SCHEMA-PROMOTE (2026-05-03)
    ("mcp-sqlite", "describe_schema"): _args_sqlite_list_tables,
    ("mcp-mongodb", "describe_collections"): _args_mongodb_list_collections,
    ("mcp-supabase", "describe_schema"): _args_supabase_list_tables,
    ("mcp-neon", "describe_schema"): _args_neon_get_database_tables,
}


def _build_mcp_arguments(
    entry: SkillToolMapping, operator_inputs: dict[str, str],
) -> dict[str, Any]:
    """Dispatch to the per-skill arg builder. Falls back to passing
    operator_inputs as-is for any future entry that hasn't registered a
    custom builder yet (defensive default)."""
    builder = _ARG_BUILDERS.get((entry.plugin_id, entry.skill_id))
    if builder is None:
        return dict(operator_inputs)
    return builder(operator_inputs)


def _flatten_mcp_content(content_parts: list[dict[str, Any]]) -> str:
    """Concatenate all text-bearing content parts into a single string."""
    chunks: list[str] = []
    for part in content_parts or []:
        text = part.get("text") if isinstance(part, dict) else None
        if isinstance(text, str) and text:
            chunks.append(text)
    return "\n\n".join(chunks)


def _summarize_mcp_result(entry: SkillToolMapping, raw_text: str) -> str:
    """Build a small operator-facing summary of the MCP response.

    For Phase 2.x we keep this very simple: trim to a max length,
    prefix with the skill identifier so the operator knows which call
    produced this summary. Future PRs can run a per-skill structured
    summarizer (e.g. parse search_files output into a path table).
    """
    if not raw_text:
        return (
            f"{entry.plugin_id}:{entry.skill_id} returned no content. "
            f"The tool ran successfully but produced an empty result."
        )
    trimmed = raw_text[:_RESULT_SUMMARY_MAX_CHARS]
    truncated = " (truncated)" if len(raw_text) > _RESULT_SUMMARY_MAX_CHARS else ""
    return (
        f"{entry.plugin_id}:{entry.skill_id} executed via MCP tool "
        f"'{entry.target_tool}'. Result{truncated}:\n\n{trimmed}"
    )


__all__ = [
    "PHASE2_ALLOWLIST",
    "PlannedToolCall",
    "SkillExecutionResult",
    "SkillExecutionStatus",
    "SkillExecutor",
    "SkillToolMapping",
    "_build_mcp_arguments",
    "_flatten_mcp_content",
    "_resolve_mcp_server_key",
    "_summarize_mcp_result",
    "get_allowlist_entry",
    "is_allowlisted",
    "list_allowlist_for_api",
]
