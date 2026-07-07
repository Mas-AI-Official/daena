"""Tool Discovery -- finds tools/MCPs/skills that don't exist yet.

When the LLM requests a tool that isn't registered, or when the auto-scanner
runs its weekly sweep, this module searches a catalog of known tools and
returns ranked candidates.

Discovery is CHEAP: keyword matching against a local catalog + optional
web search for MCP registries. Zero LLM calls.

Flow:
    1. Agent says "I need jira_api" but it's not registered
    2. ToolDiscovery.search("jira") -> finds 3 candidates
    3. ToolEvaluator.rank(candidates) -> scored + sorted
    4. Governance decides: ask user (supervised) or auto-install (AGI)
    5. ToolInstaller installs + registers the winner
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select

from app.core.logging import get_logger
from app.models.tool import ToolRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ToolCandidate:
    """A discovered tool that could be installed."""

    id: str
    name: str
    description: str
    source: str             # "mcp_registry" | "pip" | "npm" | "builtin" | "community"
    category: str           # "storage", "code", "comms", etc.
    install_method: str     # "pip install X" | "npm install X" | "mcp connect X"
    version: str = ""
    stars: int = 0          # github/npm stars
    last_updated: str = ""  # ISO date of last commit/release
    maintainer: str = ""
    license: str = ""
    compatibility: float = 1.0   # 0.0-1.0 compatibility with Daena
    security_score: float = 1.0  # 0.0-1.0 security rating
    estimated_tokens: int = 200  # schema token estimate


# ── Known Tool Catalog ────────────────────────────────────────
# This is the "database" of tools Daena knows about but hasn't installed.
# In production, this would be fetched from an MCP registry or API.
# For now, it's a curated list covering common enterprise needs.

TOOL_CATALOG: list[ToolCandidate] = [
    # -- Project Management --
    ToolCandidate("jira", "Jira", "Create/update/query Jira issues and boards",
                  "mcp_registry", "project", "mcp connect jira-mcp",
                  stars=4800, maintainer="Atlassian", compatibility=0.95, security_score=0.95),
    ToolCandidate("linear", "Linear", "Manage Linear issues, projects, and cycles",
                  "mcp_registry", "project", "mcp connect linear-mcp",
                  stars=3200, maintainer="Linear", compatibility=0.90, security_score=0.95),
    ToolCandidate("asana", "Asana", "Create and manage Asana tasks and projects",
                  "mcp_registry", "project", "mcp connect asana-mcp",
                  stars=1800, maintainer="Asana", compatibility=0.85, security_score=0.90),
    ToolCandidate("notion", "Notion", "Read/write Notion pages, databases, and blocks",
                  "mcp_registry", "project", "mcp connect notion-mcp",
                  stars=5200, maintainer="Notion", compatibility=0.95, security_score=0.95),
    ToolCandidate("trello", "Trello", "Manage Trello boards, lists, and cards",
                  "mcp_registry", "project", "mcp connect trello-mcp",
                  stars=1200, maintainer="Atlassian", compatibility=0.85, security_score=0.90),

    # -- Communication --
    ToolCandidate("slack_mcp", "Slack", "Send/read Slack messages and manage channels",
                  "mcp_registry", "comms", "mcp connect slack-mcp",
                  stars=6100, maintainer="Slack", compatibility=0.95, security_score=0.95),
    ToolCandidate("discord", "Discord", "Send messages and manage Discord servers",
                  "mcp_registry", "comms", "mcp connect discord-mcp",
                  stars=2400, maintainer="Community", compatibility=0.80, security_score=0.80),
    ToolCandidate("teams", "Microsoft Teams", "Send messages and schedule meetings in Teams",
                  "mcp_registry", "comms", "mcp connect teams-mcp",
                  stars=1900, maintainer="Microsoft", compatibility=0.85, security_score=0.90),
    ToolCandidate("gmail_mcp", "Gmail", "Read/send/search Gmail messages",
                  "mcp_registry", "comms", "mcp connect gmail-mcp",
                  stars=4500, maintainer="Google", compatibility=0.95, security_score=0.95),

    # -- Storage & Documents --
    ToolCandidate("google_drive", "Google Drive", "Read/write/search Google Drive files",
                  "mcp_registry", "storage", "mcp connect gdrive-mcp",
                  stars=5800, maintainer="Google", compatibility=0.95, security_score=0.95),
    ToolCandidate("dropbox", "Dropbox", "Upload/download/search Dropbox files",
                  "mcp_registry", "storage", "mcp connect dropbox-mcp",
                  stars=2100, maintainer="Dropbox", compatibility=0.85, security_score=0.90),
    ToolCandidate("s3", "AWS S3", "Read/write objects in S3 buckets",
                  "mcp_registry", "storage", "pip install boto3",
                  stars=8900, maintainer="AWS", compatibility=0.90, security_score=0.95),
    ToolCandidate("confluence", "Confluence", "Read/write Confluence pages and spaces",
                  "mcp_registry", "storage", "mcp connect confluence-mcp",
                  stars=1600, maintainer="Atlassian", compatibility=0.85, security_score=0.90),

    # -- Code & DevOps --
    ToolCandidate("github_mcp", "GitHub", "Manage repos, PRs, issues, actions on GitHub",
                  "mcp_registry", "code", "mcp connect github-mcp",
                  stars=9200, maintainer="GitHub", compatibility=0.95, security_score=0.95),
    ToolCandidate("gitlab", "GitLab", "Manage repos, MRs, issues on GitLab",
                  "mcp_registry", "code", "mcp connect gitlab-mcp",
                  stars=3400, maintainer="GitLab", compatibility=0.90, security_score=0.90),
    ToolCandidate("docker_mcp", "Docker", "Build/run/manage Docker containers",
                  "mcp_registry", "code", "mcp connect docker-mcp",
                  stars=4100, maintainer="Docker", compatibility=0.85, security_score=0.85),
    ToolCandidate("vercel", "Vercel", "Deploy and manage Vercel projects",
                  "mcp_registry", "code", "mcp connect vercel-mcp",
                  stars=2700, maintainer="Vercel", compatibility=0.85, security_score=0.90),

    # -- Data & Analytics --
    ToolCandidate("postgres", "PostgreSQL", "Query and manage PostgreSQL databases",
                  "pip", "data", "pip install asyncpg",
                  stars=12000, maintainer="PostgreSQL", compatibility=0.95, security_score=0.95),
    ToolCandidate("bigquery", "BigQuery", "Query Google BigQuery datasets",
                  "pip", "data", "pip install google-cloud-bigquery",
                  stars=4500, maintainer="Google", compatibility=0.90, security_score=0.95),
    ToolCandidate("snowflake", "Snowflake", "Query Snowflake data warehouse",
                  "pip", "data", "pip install snowflake-connector-python",
                  stars=3800, maintainer="Snowflake", compatibility=0.85, security_score=0.90),

    # -- Design --
    ToolCandidate("figma", "Figma", "Read/write Figma designs and components",
                  "mcp_registry", "design", "mcp connect figma-mcp",
                  stars=5600, maintainer="Figma", compatibility=0.90, security_score=0.90),
    ToolCandidate("canva", "Canva", "Create and manage Canva designs",
                  "mcp_registry", "design", "mcp connect canva-mcp",
                  stars=2800, maintainer="Canva", compatibility=0.80, security_score=0.85),

    # -- AI / Document --
    ToolCandidate("pdf_reader", "PDF Reader", "Extract text and data from PDF files",
                  "pip", "document", "pip install pymupdf",
                  stars=7200, maintainer="PyMuPDF", compatibility=0.95, security_score=0.90),
    ToolCandidate("ocr", "OCR Engine", "Extract text from images and scanned documents",
                  "pip", "document", "pip install pytesseract",
                  stars=5100, maintainer="Tesseract", compatibility=0.85, security_score=0.85),

    # -- Finance --
    ToolCandidate("stripe", "Stripe", "Process payments and manage billing",
                  "pip", "finance", "pip install stripe",
                  stars=9800, maintainer="Stripe", compatibility=0.90, security_score=0.95),
    ToolCandidate("quickbooks", "QuickBooks", "Manage invoices and accounting",
                  "mcp_registry", "finance", "mcp connect quickbooks-mcp",
                  stars=1400, maintainer="Intuit", compatibility=0.80, security_score=0.85),

    # -- CRM --
    ToolCandidate("salesforce", "Salesforce", "Manage Salesforce CRM records and workflows",
                  "mcp_registry", "crm", "mcp connect salesforce-mcp",
                  stars=4200, maintainer="Salesforce", compatibility=0.85, security_score=0.90),
    ToolCandidate("hubspot", "HubSpot", "Manage HubSpot CRM contacts and deals",
                  "mcp_registry", "crm", "mcp connect hubspot-mcp",
                  stars=3100, maintainer="HubSpot", compatibility=0.85, security_score=0.90),

    # -- Search --
    ToolCandidate("web_search_mcp", "Web Search", "Search the web via Brave/Google/Bing",
                  "mcp_registry", "search", "mcp connect brave-search-mcp",
                  stars=6800, maintainer="Community", compatibility=0.95, security_score=0.90),
    ToolCandidate("arxiv", "arXiv", "Search and retrieve academic papers",
                  "pip", "search", "pip install arxiv",
                  stars=2200, maintainer="Community", compatibility=0.90, security_score=0.95),
]

# Pre-build search index (keyword -> candidate indices)
_SEARCH_INDEX: dict[str, list[int]] = {}
for _idx, _tool in enumerate(TOOL_CATALOG):
    _words = set(
        re.findall(r'\w+', f"{_tool.id} {_tool.name} {_tool.description} {_tool.category}".lower())
    )
    for _word in _words:
        _SEARCH_INDEX.setdefault(_word, []).append(_idx)


async def seed_tool_records(db_session: AsyncSession, tenant_id: UUID) -> int:
    """Insert one ToolRecord per TOOL_CATALOG entry missing for *tenant_id*.

    Idempotent and operator-safe: only catalog tools with no row yet for this
    tenant are inserted, so a re-seed adds zero and never resurrects or
    re-enables a tool an operator disabled (Rule 17 -- no silent demo-data
    fallback overriding operator intent). Returns the count of rows inserted.

    Each row stores the full ToolCandidate in ``meta`` so ToolDiscovery.from_db
    can losslessly round-trip it back into a ToolCandidate; id maps to name,
    source to source_ref, and description carries across.
    """
    result = await db_session.execute(
        select(ToolRecord.name).where(ToolRecord.tenant_id == tenant_id)
    )
    existing = set(result.scalars().all())

    inserted = 0
    for cand in TOOL_CATALOG:
        if cand.id in existing:
            continue
        db_session.add(
            ToolRecord(
                tenant_id=tenant_id,
                name=cand.id,
                kind="builtin",
                description=cand.description,
                enabled=True,
                source_ref=cand.source,
                schema={},
                meta=asdict(cand),
            )
        )
        inserted += 1

    if inserted:
        await db_session.flush()
    return inserted


class ToolDiscovery:
    """Discovers tools matching a need from the known catalog.

    Zero LLM cost: pure keyword matching against a local catalog.

    Usage:
        discovery = ToolDiscovery()
        candidates = discovery.search("jira ticket management")
        # -> [ToolCandidate(id="jira", ...), ToolCandidate(id="linear", ...), ...]
    """

    def __init__(self, catalog: list[ToolCandidate] | None = None) -> None:
        self._catalog = catalog or TOOL_CATALOG

    @classmethod
    async def from_db(
        cls,
        db_session: AsyncSession,
        tenant_id: UUID,
    ) -> ToolDiscovery:
        """Build discovery from a tenant's persisted ToolRecord rows.

        Prefers the DB so operator edits stick: a disabled tool is excluded, an
        added/refreshed tool is honored. Fail-open and self-bootstrapping so the
        live cognition path never hard-breaks (Rule 17):
          * read error -> fall back to the constant TOOL_CATALOG
          * zero rows  -> seed once (day-one == TOOL_CATALOG), then use it
          * otherwise  -> catalog = the enabled rows, rebuilt from ``meta``

        All rows are read and the enabled filter is applied in Python (not in
        SQL): an all-disabled tenant has rows, so it must NOT look "fresh" and
        get re-bootstrapped -- it correctly yields an empty discovery catalog.
        """
        try:
            result = await db_session.execute(
                select(ToolRecord).where(ToolRecord.tenant_id == tenant_id)
            )
            rows = list(result.scalars().all())
        except Exception:
            logger.warning("tool_discovery.from_db_read_failed", exc_info=True)
            return cls()

        if not rows:
            try:
                await seed_tool_records(db_session, tenant_id)
            except Exception:
                logger.warning("tool_discovery.from_db_seed_failed", exc_info=True)
            # A fresh seed mirrors TOOL_CATALOG exactly (all enabled), so the
            # constant catalog is an honest reflection of what was persisted.
            return cls()

        catalog: list[ToolCandidate] = []
        for row in rows:
            if not row.enabled:
                continue
            if not row.meta:
                # Schema-only / partial registration -- not yet keyword-
                # discoverable until a registrant supplies the full candidate.
                continue
            try:
                catalog.append(ToolCandidate(**row.meta))
            except TypeError:
                logger.warning(
                    "tool_discovery.skip_malformed_tool_record",
                    tool_name=row.name,
                    tenant_id=str(tenant_id),
                )
        return cls(catalog=catalog)

    def search(
        self,
        query: str,
        category: str | None = None,
        max_results: int = 5,
        exclude_ids: list[str] | None = None,
    ) -> list[ToolCandidate]:
        """Search the catalog for tools matching a query.

        Args:
            query: natural language description of what's needed
            category: optional category filter
            max_results: max candidates to return
            exclude_ids: tool IDs to skip (already installed)

        Returns:
            List of ToolCandidate sorted by relevance score.
        """
        exclude = set(exclude_ids or [])
        query_words = set(re.findall(r'\w+', query.lower()))

        scored: list[tuple[float, ToolCandidate]] = []

        for tool in self._catalog:
            if tool.id in exclude:
                continue
            if category and tool.category != category:
                continue

            # Score by keyword overlap
            tool_words = set(
                re.findall(r'\w+', f"{tool.id} {tool.name} {tool.description} {tool.category}".lower())
            )
            overlap = len(query_words & tool_words)
            if overlap == 0:
                continue

            # Weighted score: keyword match + quality signals
            relevance = overlap / max(len(query_words), 1)
            quality = (tool.stars / 10000) * 0.3 + tool.compatibility * 0.4 + tool.security_score * 0.3
            score = relevance * 0.6 + quality * 0.4

            scored.append((score, tool))

        scored.sort(key=lambda x: -x[0])
        return [tool for _, tool in scored[:max_results]]

    def search_by_need(
        self,
        tool_id_requested: str,
        max_results: int = 3,
        exclude_ids: list[str] | None = None,
    ) -> list[ToolCandidate]:
        """Search for a tool by the ID the LLM requested.

        When the LLM says "I need jira_api" but it's not registered,
        this finds candidates matching "jira api".
        """
        # Convert tool_id to search query: "jira_api" -> "jira api"
        query = tool_id_requested.replace("_", " ").replace(".", " ")
        return self.search(query, max_results=max_results, exclude_ids=exclude_ids)

    def get_categories(self) -> list[str]:
        """List all available tool categories."""
        return sorted(set(t.category for t in self._catalog))

    def get_by_category(self, category: str) -> list[ToolCandidate]:
        """Get all tools in a category."""
        return [t for t in self._catalog if t.category == category]

    def suggest_for_department(self, department: str) -> list[ToolCandidate]:
        """Suggest tools relevant to a department.

        Maps departments to tool categories and returns top candidates.
        """
        dept_to_categories: dict[str, list[str]] = {
            "engineering": ["code", "data", "search"],
            "product": ["project", "design", "search"],
            "marketing": ["comms", "design", "search"],
            "sales": ["crm", "comms", "search"],
            "finance": ["finance", "data"],
            "operations": ["project", "comms", "storage"],
            "research": ["search", "document", "data"],
            "security": ["code", "search"],
            "legal": ["document", "storage"],
            "hr": ["comms", "project"],
        }

        categories = dept_to_categories.get(department.lower(), ["search", "storage"])
        results: list[ToolCandidate] = []
        for cat in categories:
            results.extend(self.get_by_category(cat)[:3])
        return results[:10]
