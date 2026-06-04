"""Daena system constants and enumerations.

Central definition of all enums, hard laws, and system constants.
These mirror the PostgreSQL ENUM types defined in the database schema.
"""

from __future__ import annotations

import enum

# ============================================================
# Identity Enums
# ============================================================

class PlanType(str, enum.Enum):
    """Tenant subscription plan."""
    FREE = "FREE"
    PRO = "PRO"
    MAX = "MAX"
    ENTERPRISE = "ENTERPRISE"


class UserRole(str, enum.Enum):
    """RBAC role hierarchy. Higher value = more access."""
    AUDITOR = "AUDITOR"      # Level 1: read-only + audit logs
    VIEWER = "VIEWER"        # Level 2: read-only
    OPERATOR = "OPERATOR"    # Level 3: execute tools, EXE mode
    MANAGER = "MANAGER"      # Level 4: department management
    ADMIN = "ADMIN"          # Level 5: full system config
    FOUNDER = "FOUNDER"      # Level 6: absolute control

    @property
    def level(self) -> int:
        """Numeric level for comparison."""
        return {
            "AUDITOR": 1, "VIEWER": 2, "OPERATOR": 3,
            "MANAGER": 4, "ADMIN": 5, "FOUNDER": 6,
        }[self.value]

    def has_access(self, required: UserRole) -> bool:
        """Check if this role meets the minimum required role."""
        return self.level >= required.level


# ============================================================
# Organization Enums
# ============================================================

class SubCapability(str, enum.Enum):
    """The 6 sub-capabilities every department agent has."""
    MIND = "MIND"        # Reasoning, planning
    EYES = "EYES"        # Observation, monitoring
    HANDS = "HANDS"      # Execution, building
    VOICE = "VOICE"      # Communication, reporting
    SHIELD = "SHIELD"    # Protection, validation
    MEMORY = "MEMORY"    # Knowledge, recall


class ModelProvider(str, enum.Enum):
    """Supported LLM providers."""
    OLLAMA = "OLLAMA"
    PERPLEXITY = "PERPLEXITY"
    ANTHROPIC = "ANTHROPIC"
    OPENAI = "OPENAI"
    GEMINI = "GEMINI"
    OPENROUTER = "OPENROUTER"
    TOGETHER = "TOGETHER"
    GROQ = "GROQ"
    VLLM = "VLLM"
    QWEN_CLOUD = "QWEN_CLOUD"


class HealthStatus(str, enum.Enum):
    """Model/provider health state."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


# ============================================================
# Chat Enums
# ============================================================

class ChatMode(str, enum.Enum):
    """Execution mode for a chat session."""
    CMD = "CMD"  # No side effects
    EXE = "EXE"  # Tool execution with governance


class RoutingMode(str, enum.Enum):
    """How models are selected for a query."""
    STANDARD = "STANDARD"          # Best single model
    COUNCIL = "COUNCIL"            # 3+ models → synthesis
    QUINTESSENCE = "QUINTESSENCE"  # Expert × LLM matrix


class ModelTier(str, enum.Enum):
    """Model capability tier for routing and debate selection.

    SOVEREIGN: Subscription-grade flagship models (Claude Opus 4.6, Gemini 3.1 Pro,
               Codex 5.4, Perplexity Pro). Used exclusively in Council/Quintessence
               debates. These are the "combined brains" of the system.
    TACTICAL:  Mid-tier cloud models (Groq, OpenRouter, Together). Good for
               standard routing when local models are insufficient.
    LOCAL:     Free local models (Ollama, vLLM). Default for Standard mode.
               Zero cost, always available, privacy-preserving.
    """
    SOVEREIGN = "SOVEREIGN"
    TACTICAL = "TACTICAL"
    LOCAL = "LOCAL"


class GovernanceSlider(str, enum.Enum):
    """DEPRECATED: aliased to GovernanceMode for backward compatibility.

    Old 5-level slider collapsed into 3-mode system:
        YOLO        -> UNLEASHED
        LIGHT       -> BALANCED
        STANDARD    -> BALANCED
        STRICT      -> GOVERNED
        PARANOID    -> GOVERNED
    """
    YOLO = "YOLO"
    LIGHT = "LIGHT"
    STANDARD = "STANDARD"
    STRICT = "STRICT"
    PARANOID = "PARANOID"
    # New canonical values (accepted by the enum for forward compat)
    UNLEASHED = "UNLEASHED"
    BALANCED = "BALANCED"
    GOVERNED = "GOVERNED"

    def to_governance_mode(self) -> "GovernanceMode":
        """Convert legacy slider value to canonical GovernanceMode."""
        _MAP = {
            "YOLO": GovernanceMode.UNLEASHED,
            "LIGHT": GovernanceMode.BALANCED,
            "STANDARD": GovernanceMode.BALANCED,
            "STRICT": GovernanceMode.GOVERNED,
            "PARANOID": GovernanceMode.GOVERNED,
            "UNLEASHED": GovernanceMode.UNLEASHED,
            "BALANCED": GovernanceMode.BALANCED,
            "GOVERNED": GovernanceMode.GOVERNED,
        }
        return _MAP.get(self.value, GovernanceMode.BALANCED)


class MessageRole(str, enum.Enum):
    """Who authored a chat message."""
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"
    TOOL = "TOOL"


# ============================================================
# Governance Enums
# ============================================================

class GovernanceMode(str, enum.Enum):
    """Controls WHETHER governance runs (not how strict it is).

    UNLEASHED: No governance pipeline. Shield only (IP/data protection).
               Raw power. Daena finds a way. Only Laws 5+7 enforced.
    BALANCED:  Light governance -- SecurityGate + auto-proceed for most
               actions. Approval only for truly dangerous operations.
    GOVERNED:  Full 10-stage pipeline with all Hard Laws (enterprise mode).
    """
    UNLEASHED = "UNLEASHED"
    BALANCED = "BALANCED"
    GOVERNED = "GOVERNED"


class RiskLevel(str, enum.Enum):
    """Risk classification for actions."""
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ApprovalStatus(str, enum.Enum):
    """Status of a governance approval request."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    AUTO_APPROVED = "AUTO_APPROVED"
    EXPIRED = "EXPIRED"


class ActorType(str, enum.Enum):
    """Who performed a governance action."""
    USER = "USER"
    AGENT = "AGENT"
    COUNCIL = "COUNCIL"
    SYSTEM = "SYSTEM"
    FOUNDER = "FOUNDER"


# ============================================================
# Memory (NBMF) Enums
# ============================================================

class NBMFTier(int, enum.Enum):
    """NBMF Memory tier levels. Higher = more persistent + trusted."""
    WORKING = 0     # Session-scoped, discarded after
    SHORT_TERM = 1  # Hours/days, auto-decay
    LONG_TERM = 2   # Persistent, user-validated
    CORE = 3        # Identity-level, rarely changes
    IMMUTABLE = 4   # Hard-coded laws, never changes


class ContentType(str, enum.Enum):
    """Type of memory content."""
    FACT = "FACT"
    PREFERENCE = "PREFERENCE"
    LEARNING = "LEARNING"
    POLICY = "POLICY"
    DIRECTIVE = "DIRECTIVE"


class VerificationStatus(str, enum.Enum):
    """Memory entry verification state."""
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class LearningAction(str, enum.Enum):
    """Actions in the learning log."""
    CREATED = "CREATED"
    PROMOTED = "PROMOTED"
    DEMOTED = "DEMOTED"
    VERIFIED = "VERIFIED"
    ARCHIVED = "ARCHIVED"


# ============================================================
# Execution Enums
# ============================================================

class TaskStatus(str, enum.Enum):
    """Background task lifecycle state."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExecutionStatus(str, enum.Enum):
    """Tool execution state."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


# ============================================================
# Connections Enums
# ============================================================

class AuthType(str, enum.Enum):
    """Connector authentication method."""
    OAUTH2 = "OAUTH2"
    API_KEY = "API_KEY"
    NONE = "NONE"


class ConnectorStatus(str, enum.Enum):
    """Connector instance state."""
    INSTALLED = "INSTALLED"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"
    NEEDS_REAUTH = "NEEDS_REAUTH"
    # PR-CONN-OAUTH-REFRESH-DISCONNECT (2026-05-03):
    # Soft-archive lane. Hidden from default list views but the row
    # is preserved (per founder rule "never delete -- archive instead").
    ARCHIVED = "ARCHIVED"


class PermissionLevel(str, enum.Enum):
    """Per-tool permission within a connector."""
    ALWAYS_ALLOW = "ALWAYS_ALLOW"
    ASK_EACH_TIME = "ASK_EACH_TIME"
    BLOCK = "BLOCK"


# ============================================================
# Financial Enums
# ============================================================

class SecretType(str, enum.Enum):
    """Vault secret classification."""
    API_KEY = "API_KEY"
    OAUTH_TOKEN = "OAUTH_TOKEN"
    REFRESH_TOKEN = "REFRESH_TOKEN"
    CUSTOM = "CUSTOM"


class SubscriptionStatus(str, enum.Enum):
    """Tenant subscription state."""
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    PAST_DUE = "PAST_DUE"
    TRIAL = "TRIAL"


# ============================================================
# Default Departments
# ============================================================

DEFAULT_DEPARTMENTS: list[dict[str, str | int]] = [
    {
        "name": "Engineering", "sunflower_index": 0,
        "description": "Code generation, testing, debugging, deployment, and repository management",
    },
    {
        "name": "Product", "sunflower_index": 1,
        "description": "Feature definition, backlog prioritization, spec writing, and metric tracking",
    },
    {
        "name": "Marketing", "sunflower_index": 2,
        "description": "Content creation, SEO optimization, social media, and email campaigns",
    },
    {
        "name": "Sales", "sunflower_index": 3,
        "description": "Lead generation, outreach, CRM updates, pipeline tracking, and proposals",
    },
    {
        "name": "Finance", "sunflower_index": 4,
        "description": "Budgets, expense tracking, invoicing, forecasting, and grant applications",
    },
    {
        "name": "Operations", "sunflower_index": 5,
        "description": "Project management, scheduling, process automation, and vendor coordination",
    },
    {
        "name": "Research", "sunflower_index": 6,
        "description": "Market research, competitive analysis, tech scouting, and deep search",
    },
    {
        "name": "Legal & Compliance", "sunflower_index": 7,
        "description": "Contract review, IP tracking, regulatory compliance, and privacy",
    },
    {
        "name": "Skill Governance", "sunflower_index": 8,
        "description": "Skill extraction, refinement, quality scoring, and knowledge curation",
    },
    {
        "name": "Security Operations", "sunflower_index": 9,
        "description": "Threat detection, access control, vulnerability scanning, and incident response",
    },
]


# ============================================================
# Default Skills (50+ pre-installed across 10 departments)
# ============================================================

DEFAULT_SKILLS: list[dict] = [
    # ── Engineering (dept 0) ──
    {"name": "code_review", "description": "Automated code review with style, security, and performance checks", "category": "Engineering", "governance_tier": 1},
    {"name": "generate_tests", "description": "Generate unit and integration tests for a given module or function", "category": "Engineering", "governance_tier": 1},
    {"name": "debug_analysis", "description": "Analyze error traces and logs to identify root cause of bugs", "category": "Engineering", "governance_tier": 1},
    {"name": "refactor_code", "description": "Suggest and apply code refactoring for improved readability and performance", "category": "Engineering", "governance_tier": 2},
    {"name": "deploy_checklist", "description": "Generate pre-deployment verification checklist for a release", "category": "Engineering", "governance_tier": 2},
    {"name": "dependency_audit", "description": "Scan project dependencies for vulnerabilities and outdated packages", "category": "Engineering", "governance_tier": 1},

    # ── Product (dept 1) ──
    {"name": "write_spec", "description": "Draft a product requirements document from a feature idea or user story", "category": "Product", "governance_tier": 1},
    {"name": "prioritize_backlog", "description": "Score and rank backlog items using RICE or weighted scoring framework", "category": "Product", "governance_tier": 1},
    {"name": "user_story_generator", "description": "Generate user stories with acceptance criteria from a feature brief", "category": "Product", "governance_tier": 0},
    {"name": "competitive_analysis", "description": "Research and compare competitor features, pricing, and positioning", "category": "Product", "governance_tier": 1},
    {"name": "metrics_dashboard", "description": "Define and track key product metrics with trend analysis", "category": "Product", "governance_tier": 1},
    {"name": "release_notes", "description": "Generate user-facing release notes from commit history and tickets", "category": "Product", "governance_tier": 0},

    # ── Marketing (dept 2) ──
    {"name": "seo_audit", "description": "Analyze page content for SEO optimization opportunities and keyword gaps", "category": "Marketing", "governance_tier": 1},
    {"name": "blog_draft", "description": "Draft a blog post from a topic outline with SEO-optimized structure", "category": "Marketing", "governance_tier": 0},
    {"name": "social_media_calendar", "description": "Plan and schedule social media posts across platforms", "category": "Marketing", "governance_tier": 1},
    {"name": "email_campaign", "description": "Design and draft multi-step email marketing sequences", "category": "Marketing", "governance_tier": 1},
    {"name": "brand_voice_check", "description": "Evaluate content against brand voice guidelines for tone and consistency", "category": "Marketing", "governance_tier": 0},
    {"name": "landing_page_copy", "description": "Write conversion-optimized landing page copy with A/B test variants", "category": "Marketing", "governance_tier": 1},

    # ── Sales (dept 3) ──
    {"name": "lead_research", "description": "Research a prospect company and key contacts for sales outreach", "category": "Sales", "governance_tier": 1},
    {"name": "outreach_draft", "description": "Draft personalized cold outreach emails based on prospect context", "category": "Sales", "governance_tier": 1},
    {"name": "proposal_generator", "description": "Generate a tailored sales proposal from deal parameters and templates", "category": "Sales", "governance_tier": 2},
    {"name": "crm_update", "description": "Summarize call notes and update CRM records with next steps", "category": "Sales", "governance_tier": 1},
    {"name": "pipeline_analysis", "description": "Analyze sales pipeline health with deal velocity and conversion metrics", "category": "Sales", "governance_tier": 1},

    # ── Finance (dept 4) ──
    {"name": "budget_forecast", "description": "Build monthly or quarterly budget forecasts with variance analysis", "category": "Finance", "governance_tier": 2},
    {"name": "expense_categorize", "description": "Categorize and tag expenses from transaction data for reporting", "category": "Finance", "governance_tier": 1},
    {"name": "invoice_generator", "description": "Generate professional invoices from billing data and templates", "category": "Finance", "governance_tier": 2},
    {"name": "financial_report", "description": "Compile financial summary reports with key ratios and trends", "category": "Finance", "governance_tier": 2},
    {"name": "cost_optimization", "description": "Identify cost reduction opportunities across infrastructure and services", "category": "Finance", "governance_tier": 1},

    # ── Operations (dept 5) ──
    {"name": "project_status_report", "description": "Generate project status reports with milestones, risks, and blockers", "category": "Operations", "governance_tier": 0},
    {"name": "meeting_agenda", "description": "Create structured meeting agendas with time allocations and action items", "category": "Operations", "governance_tier": 0},
    {"name": "process_documentation", "description": "Document operational processes with flowcharts and SOPs", "category": "Operations", "governance_tier": 1},
    {"name": "vendor_evaluation", "description": "Evaluate and compare vendors using weighted scoring criteria", "category": "Operations", "governance_tier": 1},
    {"name": "resource_allocation", "description": "Plan and optimize team resource allocation across projects", "category": "Operations", "governance_tier": 1},

    # ── Research (dept 6) ──
    {"name": "market_research", "description": "Conduct market research with industry trends, sizing, and opportunity analysis", "category": "Research", "governance_tier": 1},
    {"name": "tech_scouting", "description": "Scout emerging technologies and evaluate relevance to current projects", "category": "Research", "governance_tier": 1},
    {"name": "literature_review", "description": "Summarize academic papers and technical publications on a topic", "category": "Research", "governance_tier": 0},
    {"name": "data_analysis", "description": "Perform exploratory data analysis with statistical summaries and visualizations", "category": "Research", "governance_tier": 1},
    {"name": "patent_search", "description": "Search and analyze patent filings related to a technology or invention", "category": "Research", "governance_tier": 1},

    # ── Legal & Compliance (dept 7) ──
    {"name": "contract_review", "description": "Review contracts for risk clauses, missing terms, and compliance issues", "category": "Legal & Compliance", "governance_tier": 3},
    {"name": "privacy_audit", "description": "Audit data handling practices against GDPR, CCPA, and PIPEDA requirements", "category": "Legal & Compliance", "governance_tier": 3},
    {"name": "ip_tracker", "description": "Track intellectual property filings, deadlines, and renewal dates", "category": "Legal & Compliance", "governance_tier": 2},
    {"name": "regulatory_check", "description": "Check business actions against applicable regulatory frameworks", "category": "Legal & Compliance", "governance_tier": 3},
    {"name": "nda_triage", "description": "Classify incoming NDAs as standard, modified, or high-risk for review", "category": "Legal & Compliance", "governance_tier": 2},
    {"name": "terms_generator", "description": "Draft terms of service and privacy policy documents from templates", "category": "Legal & Compliance", "governance_tier": 3},

    # ── Skill Governance (dept 8) ──
    {"name": "skill_extraction", "description": "Extract reusable skills from conversation transcripts and documents", "category": "Skill Governance", "governance_tier": 1},
    {"name": "skill_quality_score", "description": "Score skill quality on completeness, clarity, and reusability metrics", "category": "Skill Governance", "governance_tier": 1},
    {"name": "skill_dedup", "description": "Detect and merge duplicate or overlapping skills in the catalog", "category": "Skill Governance", "governance_tier": 2},
    {"name": "skill_promotion", "description": "Evaluate skills for tier promotion based on usage and quality thresholds", "category": "Skill Governance", "governance_tier": 2},
    {"name": "knowledge_gap_finder", "description": "Identify gaps in the skill catalog by analyzing query patterns and failures", "category": "Skill Governance", "governance_tier": 1},

    # ── Security Operations (dept 9) ──
    {"name": "threat_detection", "description": "Scan inputs and outputs for prompt injection, data exfiltration, and adversarial patterns", "category": "Security Operations", "governance_tier": 3},
    {"name": "access_audit", "description": "Audit user access patterns and flag anomalous permission usage", "category": "Security Operations", "governance_tier": 3},
    {"name": "vulnerability_scan", "description": "Scan codebase and dependencies for known security vulnerabilities", "category": "Security Operations", "governance_tier": 2},
    {"name": "incident_report", "description": "Generate structured incident reports with timeline, impact, and remediation", "category": "Security Operations", "governance_tier": 2},
    {"name": "secret_rotation", "description": "Check and enforce rotation schedules for API keys, tokens, and credentials", "category": "Security Operations", "governance_tier": 3},

    # ── System Tools (built-in capabilities) ──
    {"name": "file_manager", "description": "Read, write, search, copy, move, and organize files on the computer", "category": "System", "governance_tier": 1},
    {"name": "terminal", "description": "Execute shell commands, run scripts, install packages, and manage processes", "category": "System", "governance_tier": 2},
    {"name": "python_executor", "description": "Run Python code for data processing, calculations, scripting, and automation", "category": "System", "governance_tier": 2},
    {"name": "desktop_control", "description": "Control the desktop: mouse clicks, keyboard typing, screenshots, hotkeys, scrolling", "category": "System", "governance_tier": 3},
    {"name": "computer_use", "description": "Autonomously complete visual tasks on the desktop using AI vision and screen interaction", "category": "System", "governance_tier": 3},
    {"name": "package_installer", "description": "Install Python (pip) and JavaScript (npm) packages", "category": "System", "governance_tier": 2},

    # ── Web Tools ──
    {"name": "web_search", "description": "Search the web for current information, documentation, news, and answers", "category": "Web", "governance_tier": 0},
    {"name": "web_browser", "description": "Navigate websites, take screenshots, extract text, fill forms, and click elements", "category": "Web", "governance_tier": 1},
    {"name": "http_client", "description": "Make HTTP GET and POST requests to any API endpoint", "category": "Web", "governance_tier": 1},
    {"name": "web_scraper", "description": "Extract structured data from web pages for analysis and automation", "category": "Web", "governance_tier": 1},

    # ── Communication ──
    {"name": "email_send", "description": "Send emails via Gmail with subject, body, and recipients", "category": "Communication", "governance_tier": 3},
    {"name": "email_draft", "description": "Create email drafts in Gmail without sending", "category": "Communication", "governance_tier": 1},
    {"name": "email_search", "description": "Search Gmail inbox using query syntax (from, subject, labels, etc.)", "category": "Communication", "governance_tier": 0},
    {"name": "calendar_manage", "description": "List, create, and manage Google Calendar events and find free time", "category": "Communication", "governance_tier": 2},
    {"name": "notion_workspace", "description": "Search, read, and create pages in Notion workspaces", "category": "Communication", "governance_tier": 1},

    # ── Custom/Local ──
    {"name": "mcp_bridge", "description": "Connect to any MCP server and use its tools with governance", "category": "Custom", "governance_tier": 2},
    {"name": "workflow_runner", "description": "Run department workflows: daily briefings, competitor analysis, lead research, and more", "category": "Custom", "governance_tier": 1},
    {"name": "skill_creator", "description": "Create new reusable skills from conversations or documents", "category": "Custom", "governance_tier": 1},
    {"name": "report_generator", "description": "Generate formatted reports from data, analysis, or conversation history", "category": "Custom", "governance_tier": 0},

    # ══════════════════════════════════════════════════════════
    # Extended Skill Catalog (generic, no company-specific data)
    # ══════════════════════════════════════════════════════════

    # ── Engineering (extended) ──
    {"name": "architecture_review", "description": "Create or evaluate architecture decision records (ADRs) for technical choices", "category": "Engineering", "governance_tier": 1},
    {"name": "incident_response", "description": "Run incident response workflow: triage, communicate, and write postmortem", "category": "Engineering", "governance_tier": 2},
    {"name": "system_design", "description": "Design systems, services, and architectures with diagrams and trade-off analysis", "category": "Engineering", "governance_tier": 1},
    {"name": "tech_debt_tracker", "description": "Identify, categorize, and prioritize technical debt across the codebase", "category": "Engineering", "governance_tier": 1},
    {"name": "testing_strategy", "description": "Design test strategies and test plans with coverage analysis", "category": "Engineering", "governance_tier": 1},
    {"name": "documentation_writer", "description": "Write and maintain technical documentation for APIs, systems, and processes", "category": "Engineering", "governance_tier": 0},
    {"name": "standup_generator", "description": "Generate standup updates from recent git activity and task progress", "category": "Engineering", "governance_tier": 0},
    {"name": "mutation_testing", "description": "Evaluate test suite quality by introducing code mutations and verifying tests catch them", "category": "Engineering", "governance_tier": 2},

    # ── Product (extended) ──
    {"name": "product_brainstorm", "description": "Brainstorm product ideas, explore problem spaces, and challenge assumptions", "category": "Product", "governance_tier": 0},
    {"name": "competitive_brief", "description": "Create competitive analysis brief with positioning and messaging comparison", "category": "Product", "governance_tier": 1},
    {"name": "sprint_planning", "description": "Plan sprints: scope work, estimate capacity, set goals, and draft sprint plan", "category": "Product", "governance_tier": 1},
    {"name": "stakeholder_update", "description": "Generate stakeholder updates tailored to audience and cadence", "category": "Product", "governance_tier": 0},
    {"name": "roadmap_planner", "description": "Create, update, and reprioritize product roadmaps with milestone tracking", "category": "Product", "governance_tier": 1},
    {"name": "research_synthesis", "description": "Synthesize user research from interviews, surveys, and feedback into insights", "category": "Product", "governance_tier": 1},

    # ── Marketing (extended) ──
    {"name": "content_creator", "description": "Draft marketing content across channels: blog posts, social media, newsletters", "category": "Marketing", "governance_tier": 1},
    {"name": "campaign_planner", "description": "Generate campaign briefs with objectives, audience, messaging, and channel strategy", "category": "Marketing", "governance_tier": 1},
    {"name": "performance_report", "description": "Build marketing performance reports with key metrics, trends, and recommendations", "category": "Marketing", "governance_tier": 0},
    {"name": "email_sequence_builder", "description": "Design multi-email sequences with copy, timing, branching logic, and A/B variants", "category": "Marketing", "governance_tier": 1},
    {"name": "brand_review", "description": "Review content against brand voice and style guide, flagging inconsistencies", "category": "Marketing", "governance_tier": 0},

    # ── Sales (extended) ──
    {"name": "call_prep", "description": "Prepare for sales calls with account context, attendee research, and suggested agenda", "category": "Sales", "governance_tier": 1},
    {"name": "call_summary", "description": "Process call notes: extract action items, draft follow-up email, update pipeline", "category": "Sales", "governance_tier": 1},
    {"name": "daily_briefing", "description": "Start the day with a prioritized sales briefing on deals, tasks, and follow-ups", "category": "Sales", "governance_tier": 0},
    {"name": "forecast_builder", "description": "Generate weighted sales forecast with best/likely/worst scenarios", "category": "Sales", "governance_tier": 1},
    {"name": "competitive_intelligence", "description": "Research competitors and build interactive battlecards for sales enablement", "category": "Sales", "governance_tier": 1},
    {"name": "sales_asset_creator", "description": "Generate tailored sales assets: landing pages, decks, one-pagers, workflow demos", "category": "Sales", "governance_tier": 1},

    # ── Finance (extended) ──
    {"name": "reconciliation", "description": "Reconcile accounts by comparing GL balances to subledgers and bank statements", "category": "Finance", "governance_tier": 2},
    {"name": "variance_analysis", "description": "Decompose financial variances into drivers with narrative explanations", "category": "Finance", "governance_tier": 1},
    {"name": "financial_statements", "description": "Generate income statements, balance sheets, and cash flow reports", "category": "Finance", "governance_tier": 2},
    {"name": "journal_entry_prep", "description": "Prepare journal entries with proper debits, credits, and supporting documentation", "category": "Finance", "governance_tier": 2},
    {"name": "close_management", "description": "Manage month-end close process with task sequencing and status tracking", "category": "Finance", "governance_tier": 2},
    {"name": "audit_support", "description": "Support SOX compliance with control testing, sample selection, and documentation", "category": "Finance", "governance_tier": 3},

    # ── Operations (extended) ──
    {"name": "runbook_creator", "description": "Create or update operational runbooks for recurring tasks and procedures", "category": "Operations", "governance_tier": 1},
    {"name": "risk_assessment", "description": "Identify, assess, and mitigate operational risks with severity scoring", "category": "Operations", "governance_tier": 2},
    {"name": "compliance_tracking", "description": "Track compliance requirements and audit readiness across regulations", "category": "Operations", "governance_tier": 2},
    {"name": "capacity_planning", "description": "Plan resource capacity with workload analysis and utilization forecasting", "category": "Operations", "governance_tier": 1},
    {"name": "change_request", "description": "Create change management requests with impact analysis and rollback plans", "category": "Operations", "governance_tier": 2},
    {"name": "status_reporter", "description": "Generate status reports with KPIs, risks, and action items for stakeholders", "category": "Operations", "governance_tier": 0},

    # ── Design ──
    {"name": "ux_copy_writer", "description": "Write or review UX copy: microcopy, error messages, empty states, CTAs", "category": "Design", "governance_tier": 0},
    {"name": "design_critique", "description": "Get structured design feedback on usability, hierarchy, and consistency", "category": "Design", "governance_tier": 0},
    {"name": "accessibility_audit", "description": "Run WCAG 2.1 AA accessibility audit on designs or web pages", "category": "Design", "governance_tier": 1},
    {"name": "design_system_manager", "description": "Audit, document, or extend design system components and tokens", "category": "Design", "governance_tier": 1},
    {"name": "design_handoff", "description": "Generate developer handoff specs from designs with measurements and tokens", "category": "Design", "governance_tier": 0},
    {"name": "user_research_planner", "description": "Plan, conduct, and synthesize user research with interview guides and reports", "category": "Design", "governance_tier": 1},

    # ── Data & Analytics ──
    {"name": "data_analyzer", "description": "Answer data questions from quick lookups to full exploratory analysis", "category": "Data", "governance_tier": 1},
    {"name": "visualization_creator", "description": "Create publication-quality charts and visualizations with Python", "category": "Data", "governance_tier": 1},
    {"name": "sql_writer", "description": "Write optimized SQL across dialects (Snowflake, BigQuery, Postgres, MySQL)", "category": "Data", "governance_tier": 1},
    {"name": "dashboard_builder", "description": "Build interactive HTML dashboards with charts, filters, and tables", "category": "Data", "governance_tier": 1},
    {"name": "data_validator", "description": "QA analysis before sharing: methodology, accuracy, and bias checks", "category": "Data", "governance_tier": 1},
    {"name": "data_explorer", "description": "Profile and explore datasets to understand shape, quality, and patterns", "category": "Data", "governance_tier": 0},
    {"name": "statistical_analysis", "description": "Apply statistical methods: descriptive stats, trend analysis, outlier detection", "category": "Data", "governance_tier": 1},

    # ── Human Resources ──
    {"name": "onboarding_planner", "description": "Generate onboarding checklists and first-week plans for new hires", "category": "Human Resources", "governance_tier": 0},
    {"name": "interview_prep", "description": "Create structured interview plans with competency-based questions and scorecards", "category": "Human Resources", "governance_tier": 1},
    {"name": "performance_review", "description": "Structure performance reviews with self-assessment and manager templates", "category": "Human Resources", "governance_tier": 1},
    {"name": "offer_letter_draft", "description": "Draft offer letters with compensation details and employment terms", "category": "Human Resources", "governance_tier": 3},
    {"name": "policy_lookup", "description": "Find and explain company policies in plain language", "category": "Human Resources", "governance_tier": 0},
    {"name": "comp_analysis", "description": "Analyze compensation benchmarking, band placement, and equity modeling", "category": "Human Resources", "governance_tier": 2},
    {"name": "org_planning", "description": "Headcount planning, org design, and team structure optimization", "category": "Human Resources", "governance_tier": 2},
    {"name": "recruiting_pipeline", "description": "Track and manage recruiting pipeline stages with status updates", "category": "Human Resources", "governance_tier": 1},

    # ── Customer Support ──
    {"name": "ticket_triage", "description": "Triage and prioritize support tickets with severity classification", "category": "Customer Support", "governance_tier": 1},
    {"name": "kb_article_writer", "description": "Draft knowledge base articles from resolved issues or common questions", "category": "Customer Support", "governance_tier": 0},
    {"name": "customer_escalation", "description": "Package escalations for engineering, product, or leadership with full context", "category": "Customer Support", "governance_tier": 2},
    {"name": "response_drafter", "description": "Draft professional customer-facing responses tailored to situation and tone", "category": "Customer Support", "governance_tier": 1},
    {"name": "customer_research", "description": "Multi-source research on customer questions with source attribution", "category": "Customer Support", "governance_tier": 1},

    # ── Productivity ──
    {"name": "task_manager", "description": "Create, track, and manage tasks with priorities and due dates", "category": "Productivity", "governance_tier": 0},
    {"name": "meeting_prep", "description": "Prepare meeting briefs with agenda, attendees, and linked documents", "category": "Productivity", "governance_tier": 0},
    {"name": "weekly_digest", "description": "Generate weekly summary of meetings, tasks, and unread messages", "category": "Productivity", "governance_tier": 0},
    {"name": "standup_report", "description": "Create daily standup summaries from meetings and open tasks", "category": "Productivity", "governance_tier": 0},

    # ── PDF & Documents ──
    {"name": "pdf_viewer", "description": "Open, view, and annotate PDF documents with interactive controls", "category": "Documents", "governance_tier": 0},
    {"name": "pdf_form_filler", "description": "Fill PDF form fields interactively with visual feedback", "category": "Documents", "governance_tier": 1},
    {"name": "pdf_extractor", "description": "Extract text, tables, and data from PDF documents", "category": "Documents", "governance_tier": 0},
    {"name": "document_creator", "description": "Create Word documents, presentations, and spreadsheets", "category": "Documents", "governance_tier": 1},

    # ── Video & Media ──
    {"name": "video_production", "description": "Cinematic video production: FFmpeg, compositing, B-roll, captions, and export", "category": "Media", "governance_tier": 2},
    {"name": "presentation_builder", "description": "Create and manage slide presentations with structured content", "category": "Media", "governance_tier": 1},

    # ── Enterprise Search ──
    {"name": "cross_source_search", "description": "Search across all connected sources (email, docs, chat, files) in one query", "category": "Enterprise Search", "governance_tier": 0},
    {"name": "knowledge_synthesis", "description": "Combine search results from multiple sources into coherent, deduplicated answers", "category": "Enterprise Search", "governance_tier": 0},
    {"name": "daily_digest", "description": "Generate daily or weekly digest of activity across all connected sources", "category": "Enterprise Search", "governance_tier": 0},

    # ── Project Management ──
    {"name": "project_planner", "description": "Create detailed project plans with task breakdown, dependencies, and milestones", "category": "Project Management", "governance_tier": 1},
    {"name": "project_tracker", "description": "Track project progress with status updates, blockers, and completion metrics", "category": "Project Management", "governance_tier": 0},
    {"name": "phase_executor", "description": "Execute project phases with atomic commits, deviation handling, and checkpoints", "category": "Project Management", "governance_tier": 2},
    {"name": "codebase_mapper", "description": "Analyze codebase architecture, quality, and concerns across the project", "category": "Project Management", "governance_tier": 0},
    {"name": "integration_checker", "description": "Verify cross-phase integration and end-to-end workflow completion", "category": "Project Management", "governance_tier": 1},
]


# ============================================================
# Governance Tier Mapping
# ============================================================

GOVERNANCE_TIER_MAP: dict[GovernanceMode, dict[RiskLevel, int]] = {
    # UNLEASHED: Shield only. Everything is tier 0 (logged) except
    # CRITICAL actions which escalate to tier 4 so the approval gate
    # still fires. Matches permission_resolver's intent ("We only
    # pause on tier 4, reached for CRITICAL risk") and closes the
    # self-audit finding that CRITICAL=2 in UNLEASHED was below the
    # tier>=3 REQUEST_INPUT threshold, leaving arbitrary-code tools
    # like ``create_tool`` auto-proceeding.
    GovernanceMode.UNLEASHED: {
        RiskLevel.NONE: 0, RiskLevel.LOW: 0, RiskLevel.MEDIUM: 0,
        RiskLevel.HIGH: 0, RiskLevel.CRITICAL: 4,
    },
    # BALANCED: Auto-approve most. HIGH needs approval (tier 3),
    # CRITICAL strict approval (tier 4). Previous HIGH=2 meant HIGH
    # tools auto-proceeded unless per-tool ASK was set.
    GovernanceMode.BALANCED: {
        RiskLevel.NONE: 0, RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1,
        RiskLevel.HIGH: 3, RiskLevel.CRITICAL: 4,
    },
    # GOVERNED: Full pipeline. MEDIUM+ escalates. HIGH/CRITICAL need approval.
    GovernanceMode.GOVERNED: {
        RiskLevel.NONE: 0, RiskLevel.LOW: 1, RiskLevel.MEDIUM: 2,
        RiskLevel.HIGH: 3, RiskLevel.CRITICAL: 4,
    },
}


def resolve_governance_tier(
    governance_mode: GovernanceMode,
    risk: RiskLevel,
    *,
    legacy_slider: str | None = None,
) -> int:
    """Compute governance tier from mode + risk.

    Accepts optional legacy_slider for backward compatibility with
    stored sessions that still have YOLO/LIGHT/STANDARD/STRICT/PARANOID.
    Converts to GovernanceMode before lookup.
    """
    if legacy_slider and legacy_slider not in ("UNLEASHED", "BALANCED", "GOVERNED"):
        try:
            governance_mode = GovernanceSlider(legacy_slider).to_governance_mode()
        except ValueError:
            pass  # Unknown value, use governance_mode as-is
    tier_map = GOVERNANCE_TIER_MAP.get(governance_mode, GOVERNANCE_TIER_MAP[GovernanceMode.BALANCED])
    return tier_map.get(risk, 0)


# ============================================================
# Vault V2 (Phase 4a-2) -- envelope-encryption KEK env vars
# ============================================================
#
# DAENA_KEK is the new master KEK env var (per ADR-002 D-003).
# LEGACY_VAULT_KEK_ENV is honored as fallback during the migration
# window; remove post-V2.
#
# KEK_BYTE_LENGTH = 32 (AES-256). Env value is encoded as 64-char hex
# OR 44-char base64 (since binary 32 bytes can't live in env vars).
#
# PLACEHOLDER_KEK_VALUES are recognized as "not set" -- prevents the
# legacy "CHANGE-ME" placeholder from accidentally being treated as
# a real KEK by load_kek_from_env() in production.

DAENA_KEK_ENV: str = "DAENA_KEK"
LEGACY_VAULT_KEK_ENV: str = "VAULT_ENCRYPTION_KEY"
KEK_BYTE_LENGTH: int = 32
PLACEHOLDER_KEK_VALUES: frozenset[str] = frozenset({
    "",
    "CHANGE-ME-32-byte-key-for-aes256",
    "CHANGE-ME",
    "PLACEHOLDER",
    "PLACEHOLDER-DEV-KEY",
})
