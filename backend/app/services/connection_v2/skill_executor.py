"""Phase 2 read-only skill executor.

PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE2-READONLY (2026-05-03).

Phase 2 ships the EXECUTOR SPINE -- a typed allowlist + audit log
parent row + frontend "Run read-only skill" affordance -- but NEVER
fires a real MCP ``tools/call`` in this PR. Every allowlisted skill
returns ``status="planned"`` with a full preview of which tool would
be invoked and what arguments would be derived. Actual execution
arms in follow-up PRs as each integration is individually proven safe
end-to-end.

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

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services.audit import AuditService

logger = get_logger(__name__)


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
    SkillToolMapping(
        plugin_id="mcp-github",
        skill_id="summarize_repo",
        backend_surface="mcp",
        read_only=True,
        execution_mode="planned_only",
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
        execution_mode="planned_only",
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
        execution_mode="planned_only",
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
    # NOTE: draft_reply is NOT in Phase 2 allowlist even though it's
    # a "draft" skill -- founder rule 7 (no message drafts that risk
    # auto-send) keeps it Phase 1 chat-draft only.
    SkillToolMapping(
        plugin_id="mcp-slack",
        skill_id="summarize_channel",
        backend_surface="mcp",
        read_only=True,
        execution_mode="planned_only",
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
        execution_mode="planned_only",
        target_tool="conversations_history",
        required_inputs=("channel", "time_window"),
        reads_summary=(
            "Same channel-history read as summarize_channel, but the "
            "summarizer extracts decision-shaped messages (owner + "
            "decision + permalink). Read-only."
        ),
    ),

    # ── Sentry (mcp-sentry, LOW risk, READ skill) ──
    SkillToolMapping(
        plugin_id="mcp-sentry",
        skill_id="summarize_errors",
        backend_surface="mcp",
        read_only=True,
        execution_mode="planned_only",
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
    SkillToolMapping(
        plugin_id="mcp-huggingface",
        skill_id="find_model",
        backend_surface="mcp",
        read_only=True,
        execution_mode="planned_only",
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
        execution_mode="planned_only",
        target_tool="paper_search",
        required_inputs=("arxiv_id_or_title",),
        reads_summary=(
            "Hugging Face papers index lookup. Returns abstract + "
            "linked models + citation count. Public data only."
        ),
    ),

    # ── Filesystem (mcp-filesystem, MEDIUM risk -- sandboxed, READ skills) ──
    SkillToolMapping(
        plugin_id="mcp-filesystem",
        skill_id="find_files",
        backend_surface="mcp",
        read_only=True,
        execution_mode="planned_only",
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
        execution_mode="planned_only",
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
            "indexes. No row data read. No DDL or DML executed."
        ),
    ),
    SkillToolMapping(
        plugin_id="mcp-sqlite",
        skill_id="describe_schema",
        backend_surface="mcp",
        read_only=True,
        execution_mode="planned_only",
        target_tool="describe_schema",
        required_inputs=("database_path",),
        reads_summary=(
            "SQLite schema: tables + columns. Read-only metadata only."
        ),
    ),
    SkillToolMapping(
        plugin_id="mcp-supabase",
        skill_id="describe_schema",
        backend_surface="mcp",
        read_only=True,
        execution_mode="planned_only",
        target_tool="describe_schema",
        required_inputs=("project_ref",),
        reads_summary=(
            "Supabase schema: tables, columns, RLS policies. No row "
            "data, no auth records, no storage objects read."
        ),
    ),
    SkillToolMapping(
        plugin_id="mcp-neon",
        skill_id="describe_schema",
        backend_surface="mcp",
        read_only=True,
        execution_mode="planned_only",
        target_tool="describe_schema",
        required_inputs=("database", "branch_id_or_default"),
        reads_summary=(
            "Neon Postgres schema for the named branch. Read-only "
            "metadata. Does not list snapshots or modify branches."
        ),
    ),
    SkillToolMapping(
        plugin_id="mcp-mongodb",
        skill_id="describe_collections",
        backend_surface="mcp",
        read_only=True,
        execution_mode="planned_only",
        target_tool="describe_collections",
        required_inputs=("database",),
        reads_summary=(
            "MongoDB collection listing + a sample document SHAPE per "
            "collection (field names + types only, never sample values)."
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

        # Step 5 + 6 + 7: build the planned preview, write audit, return.
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


__all__ = [
    "PHASE2_ALLOWLIST",
    "PlannedToolCall",
    "SkillExecutionResult",
    "SkillExecutionStatus",
    "SkillExecutor",
    "SkillToolMapping",
    "get_allowlist_entry",
    "is_allowlisted",
    "list_allowlist_for_api",
]
