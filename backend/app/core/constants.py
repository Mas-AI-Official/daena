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
