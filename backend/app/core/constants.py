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


class GovernanceSlider(str, enum.Enum):
    """Governance strictness level (user-facing slider)."""
    YOLO = "YOLO"          # Minimal governance
    LIGHT = "LIGHT"        # Log only
    STANDARD = "STANDARD"  # Default — balanced
    STRICT = "STRICT"      # Require approvals
    PARANOID = "PARANOID"  # Council + approve everything


class MessageRole(str, enum.Enum):
    """Who authored a chat message."""
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"
    TOOL = "TOOL"


# ============================================================
# Governance Enums
# ============================================================

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
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"
    NEEDS_REAUTH = "NEEDS_REAUTH"


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
]


# ============================================================
# Governance Tier Mapping
# ============================================================

GOVERNANCE_TIER_MAP: dict[GovernanceSlider, dict[RiskLevel, int]] = {
    GovernanceSlider.YOLO: {
        RiskLevel.NONE: 0, RiskLevel.LOW: 0, RiskLevel.MEDIUM: 0,
        RiskLevel.HIGH: 1, RiskLevel.CRITICAL: 2,
    },
    GovernanceSlider.LIGHT: {
        RiskLevel.NONE: 0, RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1,
        RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3,
    },
    GovernanceSlider.STANDARD: {
        RiskLevel.NONE: 0, RiskLevel.LOW: 1, RiskLevel.MEDIUM: 2,
        RiskLevel.HIGH: 3, RiskLevel.CRITICAL: 4,
    },
    GovernanceSlider.STRICT: {
        RiskLevel.NONE: 0, RiskLevel.LOW: 2, RiskLevel.MEDIUM: 3,
        RiskLevel.HIGH: 3, RiskLevel.CRITICAL: 4,
    },
    GovernanceSlider.PARANOID: {
        RiskLevel.NONE: 1, RiskLevel.LOW: 2, RiskLevel.MEDIUM: 3,
        RiskLevel.HIGH: 4, RiskLevel.CRITICAL: 4,
    },
}
