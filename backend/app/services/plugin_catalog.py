"""Plugin catalog -- single source of truth for Daena's plugin inventory.

Mirrors the Codex-desktop plugin directory so every caller (frontend
rendering, backend installer, Daena's self-service plugin-admin tools)
reads from the same structured definitions.

A plugin:
  * belongs to a category (Coding / Design / Lifestyle / Productivity /
    Research)
  * exposes one or more skills (name + description + action-type)
  * optionally ships with an MCP package (stdio ``npx -y <pkg>``) so
    the Option-A stdio-bridge can spawn the server on startup
  * declares an auth kind (oauth / api_key / token / none)

Adding a plugin:
  1. Append a PluginDefinition to ``PLUGIN_CATALOG`` below.
  2. Add a matching entry to ``frontend/src/pages/ConnectionsPage.tsx``
     (we keep the frontend array for offline rendering; the API
     endpoint lets it swap to backend-driven as soon as the frontend
     fetch lands).

No code paths should hard-code a plugin id outside this file. The
orchestrator's tool discovery, the extensions installer, and Daena's
plugin-admin DaenaBot tools all read from here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


AuthKind = str  # "oauth" | "api_key" | "token" | "none"


@dataclass(frozen=True)
class PluginSkill:
    """One skill a plugin exposes (the Codex 'Skill' row)."""

    id: str          # Tool id used by permission system + orchestrator
    name: str        # Human-readable ("Search Files")
    description: str # One-line caption shown in the UI skill card


@dataclass(frozen=True)
class PluginDefinition:
    """One plugin the user can install + connect."""

    id: str                 # Stable id, e.g. "netlify"
    name: str               # Display name, e.g. "Netlify"
    subtitle: str           # One-line summary for the plugin row
    category: str           # Codex-style category
    auth_kind: AuthKind     # How the user authenticates
    skills: list[PluginSkill] = field(default_factory=list)
    # Optional stdio MCP package (npm). When set, the Option-A bridge
    # will spawn ``npx -y <package>`` and register its tools.
    mcp_package: str | None = None
    # Optional short description shown on the install modal.
    install_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "skill_count": len(self.skills),
        }


def _skill(id: str, name: str, description: str) -> PluginSkill:
    return PluginSkill(id=id, name=name, description=description)


# ─────────────────────────────────────────────────────────────────
# Catalog
# ─────────────────────────────────────────────────────────────────

PLUGIN_CATALOG: dict[str, PluginDefinition] = {
    # ── Coding ──
    "hugging-face": PluginDefinition(
        id="hugging-face", name="Hugging Face",
        subtitle="Inspect models, datasets, Spaces, and research",
        category="Coding", auth_kind="api_key",
        skills=[
            _skill("search_models", "Search Models",
                   "Search public models by task, library, or author."),
            _skill("model_info", "Model Info",
                   "Fetch metadata, tags, and usage info for a specific model."),
            _skill("run_inference", "Run Inference",
                   "Run inference against a hosted Hugging Face model."),
            _skill("search_datasets", "Search Datasets",
                   "Search datasets by task, license, or language."),
        ],
    ),
    "netlify": PluginDefinition(
        id="netlify", name="Netlify",
        subtitle="Deploy projects and manage releases",
        category="Coding", auth_kind="token",
        skills=[
            _skill("netlify_deploy", "Netlify Deploy",
                   "Deploy a site or trigger a new build."),
            _skill("netlify_list_sites", "List Sites",
                   "List sites connected to this Netlify team."),
            _skill("netlify_env", "Env Vars",
                   "Inspect or update environment variables for a site."),
            _skill("netlify_logs", "Logs",
                   "Stream deploy logs and function execution traces."),
        ],
    ),
    "vercel": PluginDefinition(
        id="vercel", name="Vercel",
        subtitle="Build and deploy web apps and agents",
        category="Coding", auth_kind="token",
        skills=[
            _skill("vercel_deploy", "Vercel Deploy",
                   "Deploy a project to Vercel production or a preview."),
            _skill("vercel_list_projects", "List Projects",
                   "List projects accessible to this Vercel account."),
            _skill("vercel_logs", "Logs",
                   "Fetch build + runtime logs from a deployment."),
            _skill("vercel_env", "Env Vars",
                   "Manage environment variables across Vercel environments."),
        ],
    ),
    "github": PluginDefinition(
        id="github", name="GitHub",
        subtitle="Triage PRs, issues, CI, and publish flows",
        category="Coding", auth_kind="token",
        mcp_package="@modelcontextprotocol/server-github",
        skills=[
            _skill("search_repos", "Search Repos",
                   "Search public and private repositories by name or topic."),
            _skill("read_file", "Read File",
                   "Read the content of a file you own or have access to."),
            _skill("list_issues", "List Issues",
                   "List open or closed issues in a repository."),
            _skill("create_issue", "Create Issue",
                   "Open a new issue with title, body, and labels."),
            _skill("create_pr", "Create PR",
                   "Create a pull request from a branch to the base."),
        ],
    ),
    "cloudflare": PluginDefinition(
        id="cloudflare", name="Cloudflare",
        subtitle="Cloudflare platform guidance with official MCP",
        category="Coding", auth_kind="token",
        mcp_package="@cloudflare/mcp-server-cloudflare",
        skills=[
            _skill("list_zones", "List Zones",
                   "List Cloudflare zones (domains) on this account."),
            _skill("update_dns", "Update DNS",
                   "Add or update a DNS record on a Cloudflare zone."),
            _skill("deploy_worker", "Deploy Worker",
                   "Deploy a Cloudflare Worker script."),
        ],
    ),
    "sentry": PluginDefinition(
        id="sentry", name="Sentry",
        subtitle="Inspect recent Sentry issues and events",
        category="Coding", auth_kind="token",
        mcp_package="@sentry/mcp-server",
        skills=[
            _skill("list_issues_sentry", "List Issues",
                   "List recent Sentry issues with frequency + severity."),
            _skill("get_event", "Get Event",
                   "Fetch a specific Sentry event with stack trace."),
            _skill("search_events", "Search Events",
                   "Search Sentry events by query, release, or environment."),
        ],
    ),
    "neon": PluginDefinition(
        id="neon", name="Neon Postgres",
        subtitle="Manage Neon Serverless Postgres projects and databases",
        category="Coding", auth_kind="api_key",
        mcp_package="@neondatabase/mcp-server-neon",
        skills=[
            _skill("list_neon_projects", "List Projects",
                   "List Neon projects available to this account."),
            _skill("run_query", "Run Query",
                   "Run a SQL query against a Neon branch."),
            _skill("create_branch", "Create Branch",
                   "Create a Neon database branch for safe iteration."),
        ],
    ),
    "cloudinary": PluginDefinition(
        id="cloudinary", name="Cloudinary",
        subtitle="Manage, search, and transform your media library",
        category="Coding", auth_kind="api_key",
        skills=[
            _skill("upload_media", "Upload Media",
                   "Upload an image or video to Cloudinary."),
            _skill("search_media", "Search Media",
                   "Search the Cloudinary library by tag or metadata."),
            _skill("transform_image", "Transform",
                   "Apply a Cloudinary transformation recipe."),
        ],
    ),
    "sendgrid": PluginDefinition(
        id="sendgrid", name="SendGrid",
        subtitle="Connector for the SendGrid email API",
        category="Coding", auth_kind="api_key",
        skills=[
            _skill("send_email_sg", "Send Email",
                   "Send an email via SendGrid."),
            _skill("list_templates", "List Templates",
                   "List dynamic email templates."),
            _skill("get_stats_sg", "Stats",
                   "Fetch delivery + engagement stats."),
        ],
    ),
    "render": PluginDefinition(
        id="render", name="Render",
        subtitle="Deploy, debug, monitor, and migrate apps on Render",
        category="Coding", auth_kind="api_key",
        skills=[
            _skill("render_deploy", "Render Deploy",
                   "Trigger a deploy on a Render service."),
            _skill("render_logs", "Logs",
                   "Stream logs from a Render service."),
            _skill("render_list_services", "List Services",
                   "List services in your Render account."),
        ],
    ),
    # ── Design ──
    "canva": PluginDefinition(
        id="canva", name="Canva",
        subtitle="Search, create, edit designs",
        category="Design", auth_kind="oauth",
        skills=[
            _skill("list_designs", "List Designs",
                   "List designs in your Canva workspace."),
            _skill("create_design", "Create Design",
                   "Create a new design from a template or blank canvas."),
            _skill("export_design", "Export",
                   "Export a design as PDF, PNG, or other formats."),
        ],
    ),
    "figma": PluginDefinition(
        id="figma", name="Figma",
        subtitle="Design-to-code workflows powered by Figma",
        category="Design", auth_kind="token",
        mcp_package="figma-mcp",
        skills=[
            _skill("get_file", "Get File",
                   "Fetch a Figma file tree (pages, frames, components)."),
            _skill("get_components", "Get Components",
                   "List reusable components from a Figma file."),
            _skill("export_assets", "Export Assets",
                   "Export assets (PNG, SVG, PDF) from a Figma file."),
        ],
    ),
    # ── Productivity (selected high-value subset) ──
    "google-drive": PluginDefinition(
        id="google-drive", name="Google Drive",
        subtitle="Work across Drive, Docs, Sheets, and Slides",
        category="Productivity", auth_kind="oauth",
        mcp_package="@modelcontextprotocol/server-gdrive",
        install_note="Official Google Drive MCP. One-click install.",
        skills=[
            _skill("search_files", "Search Files",
                   "Search files, folders, and shared drives by keyword."),
            _skill("read_file", "Read File",
                   "Read the content of a file you own or have access to."),
            _skill("upload_file", "Upload File",
                   "Upload a new file or new version to Drive."),
            _skill("list_folders", "List Folders",
                   "List folders in a drive or parent folder."),
        ],
    ),
    "gmail": PluginDefinition(
        id="gmail", name="Gmail",
        subtitle="Read and manage Gmail",
        category="Productivity", auth_kind="oauth",
        mcp_package="@modelcontextprotocol/server-gmail",
        skills=[
            _skill("search_emails", "Search Emails",
                   "Search the inbox by sender, subject, date, or label."),
            _skill("read_email", "Read Email",
                   "Read the body and metadata of a specific email."),
            _skill("send_email", "Send Email",
                   "Compose and send an email to one or more recipients."),
            _skill("create_draft", "Create Draft",
                   "Save a draft email without sending."),
        ],
    ),
    "google-calendar": PluginDefinition(
        id="google-calendar", name="Google Calendar",
        subtitle="Manage Google Calendar events and schedules",
        category="Productivity", auth_kind="oauth",
        skills=[
            _skill("list_events", "List Events",
                   "List upcoming calendar events in a time window."),
            _skill("create_event", "Create Event",
                   "Create a new event with attendees and meeting link."),
            _skill("update_event", "Update Event",
                   "Change time, attendees, or details of an existing event."),
            _skill("find_free_time", "Find Free Time",
                   "Find free slots in one or more calendars."),
        ],
    ),
    "slack": PluginDefinition(
        id="slack", name="Slack",
        subtitle="Read and manage Slack",
        category="Productivity", auth_kind="oauth",
        mcp_package="@modelcontextprotocol/server-slack",
        skills=[
            _skill("search_messages", "Search Messages",
                   "Search across channels and DMs for keywords."),
            _skill("send_message", "Send Message",
                   "Post a message to a channel or thread."),
            _skill("list_channels", "List Channels",
                   "List channels you are a member of."),
            _skill("read_channel", "Read Channel",
                   "Read recent messages from a specific channel."),
        ],
    ),
    "notion": PluginDefinition(
        id="notion", name="Notion",
        subtitle="Notion workflows for specs, research, meetings",
        category="Productivity", auth_kind="token",
        mcp_package="@modelcontextprotocol/server-notion",
        skills=[
            _skill("search_pages", "Search Pages",
                   "Search pages and databases by keyword."),
            _skill("read_page", "Read Page",
                   "Read the full content of a page including blocks."),
            _skill("create_page", "Create Page",
                   "Create a new page under a parent page or database."),
            _skill("query_database", "Query Database",
                   "Query a Notion database with filters and sorting."),
        ],
    ),
    "linear": PluginDefinition(
        id="linear", name="Linear",
        subtitle="Find and reference issues and projects",
        category="Productivity", auth_kind="api_key",
        mcp_package="mcp-linear",
        skills=[
            _skill("list_issues", "List Issues",
                   "List Linear issues with filters."),
            _skill("create_issue", "Create Issue",
                   "Open a new Linear issue."),
            _skill("update_issue", "Update Issue",
                   "Update a Linear issue status, assignee, or description."),
            _skill("list_projects", "List Projects",
                   "List projects in your Linear workspace."),
        ],
    ),
    "hubspot": PluginDefinition(
        id="hubspot", name="HubSpot",
        subtitle="Work with your HubSpot CRM data",
        category="Productivity", auth_kind="oauth",
        skills=[
            _skill("search_hubspot", "Search CRM",
                   "Search HubSpot CRM records."),
            _skill("create_hs_contact", "Create Contact",
                   "Create a new HubSpot contact."),
            _skill("update_hs_deal", "Update Deal",
                   "Update a HubSpot deal stage or fields."),
        ],
    ),
    "stripe": PluginDefinition(
        id="stripe", name="Stripe",
        subtitle="Payments and business tools",
        category="Productivity", auth_kind="api_key",
        mcp_package="@stripe/mcp-server",
        skills=[
            _skill("list_charges", "List Charges",
                   "List Stripe charges with status, amount, and customer."),
            _skill("list_subscriptions", "List Subscriptions",
                   "List active subscriptions and their customers."),
            _skill("create_invoice", "Create Invoice",
                   "Create and send a Stripe invoice to a customer."),
        ],
    ),
    # ── Research (selected) ──
    "life-science-research": PluginDefinition(
        id="life-science-research", name="Life Science Research",
        subtitle="Life-sciences research with evidence synthesis",
        category="Research", auth_kind="api_key",
        skills=[
            _skill("search_papers", "Search Papers",
                   "Search biomedical / life-sciences literature."),
            _skill("synthesize_evidence", "Synthesize Evidence",
                   "Synthesize evidence across multiple papers."),
            _skill("run_parallel_analysis", "Parallel Analysis",
                   "Run parallel subagent analysis on a research question."),
        ],
    ),
    "readwise": PluginDefinition(
        id="readwise", name="Readwise",
        subtitle="Official app for Readwise and Reader",
        category="Research", auth_kind="oauth",
        skills=[
            _skill("list_highlights", "List Highlights",
                   "List Readwise highlights."),
            _skill("get_book", "Get Book",
                   "Fetch a Readwise book summary."),
            _skill("search_readwise", "Search",
                   "Search Readwise content."),
        ],
    ),
    "scite": PluginDefinition(
        id="scite", name="Scite",
        subtitle="Answers grounded in peer-reviewed research",
        category="Research", auth_kind="api_key",
        skills=[
            _skill("search_scite", "Search Scite",
                   "Search Scite for peer-reviewed answers."),
            _skill("get_citation_context", "Citation Context",
                   "Fetch the citation context around a claim."),
            _skill("verify_claim", "Verify Claim",
                   "Verify a claim against peer-reviewed research."),
        ],
    ),
}


# ─────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────

def list_plugins() -> list[dict[str, Any]]:
    """Return the full catalog as a JSON-friendly list."""
    return [p.to_dict() for p in PLUGIN_CATALOG.values()]


def list_plugins_by_category() -> dict[str, list[dict[str, Any]]]:
    """Return the catalog grouped by category (preserves insert order)."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for plugin in PLUGIN_CATALOG.values():
        groups.setdefault(plugin.category, []).append(plugin.to_dict())
    return groups


def get_plugin(plugin_id: str) -> PluginDefinition | None:
    """Lookup a plugin definition by id."""
    return PLUGIN_CATALOG.get(plugin_id)


def plugins_with_mcp() -> list[PluginDefinition]:
    """Return plugins that ship an MCP package (stdio-installable)."""
    return [p for p in PLUGIN_CATALOG.values() if p.mcp_package]


def skill_description(tool_id: str) -> str | None:
    """Lookup the description for any skill tool id across all plugins.

    Used by the chat orchestrator when it needs a human-readable label
    for a skill that was just invoked.
    """
    for plugin in PLUGIN_CATALOG.values():
        for skill in plugin.skills:
            if skill.id == tool_id:
                return skill.description
    return None
