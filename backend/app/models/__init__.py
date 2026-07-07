"""SQLAlchemy ORM models for Daena.

All models are imported here for Alembic auto-discovery.
"""

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin
from app.models.chat import ChatCategory, ChatMessage, ChatSession
from app.models.cognition import CkgInsight, CkgTransferEdge
from app.models.connection_v2 import (
    AuthMethod,
    ConnectionKind,
    ConnectionV2,
    ConnectionV2Capability,
    ConnectionV2OpLock,
    OpKind,
    TrustTier,
)
from app.models.connections import Connector, ConnectorInstance, ConnectorPermission
from app.models.business import BizOutreachDraft, Opportunity
from app.models.crm import Account, Contact, Deal, OutreachDraft
from app.models.research import ResearchDraft
from app.models.form_draft import FormDraft, FormDraftField
from app.models.department_budget import DepartmentBudget, ExpenseProposal
from app.models.department_message import DepartmentMessage
from app.models.department_policy import DepartmentPolicy
from app.models.department_state import DepartmentState
from app.models.department_task import DepartmentTask
from app.models.execution import Skill, Task, ToolExecution
from app.models.experience import ExperienceLog
from app.models.files import FileRecord
from app.models.error_event import ErrorEvent
from app.models.financial import Subscription, UsageLedger, UserQuota, VaultSecret
from app.models.heartbeat_config import HeartbeatConfigRow
from app.models.run_trace_event import RunTraceEvent
from app.models.governance import GoaAuditEvent, GoaPolicyState, GoaRequest, PendingApproval
from app.models.identity import RefreshToken, Tenant, User
from app.models.memory import LearningLog, MemoryEntry
from app.models.organization import Agent, BrainModel, Department
from app.models.pipeline import ProjectPipeline
from app.models.project import Project
from app.models.skill import RefinedSkill
from app.models.api_key import ApiKey
from app.models.background_task import BackgroundTask
from app.models.consent_grant import ConsentGrant
from app.models.cron_run import CronRun
from app.models.mcp_server import McpServer
from app.models.notification import Notification
from app.models.plugin_policy_override import PluginPolicyOverride
from app.models.push_subscription import PushSubscription
from app.models.secret import Secret
from app.models.waitlist import WaitlistEntry
from app.models.workstream import (
    Workstream,
    WorkstreamEscalationLevel,
    WorkstreamEvent,
    WorkstreamEventKind,
    WorkstreamStatus,
)

__all__ = [
    "Base", "TimestampMixin", "TenantMixin", "SoftDeleteMixin",
    "Tenant", "User", "RefreshToken",
    "Department", "Agent", "BrainModel",
    "ChatSession", "ChatMessage", "ChatCategory",
    "CkgInsight", "CkgTransferEdge",
    "GoaRequest", "GoaPolicyState", "GoaAuditEvent", "PendingApproval",
    "MemoryEntry", "LearningLog",
    "Task", "ToolExecution", "Skill", "DepartmentTask", "FileRecord",
    "RefinedSkill",
    "Connector", "ConnectorInstance", "ConnectorPermission",
    "ConnectionV2", "ConnectionV2Capability", "ConnectionV2OpLock",
    "ConnectionKind", "AuthMethod", "TrustTier", "OpKind",
    "Account", "Contact", "Deal", "OutreachDraft",
    "ResearchDraft",
    "FormDraft", "FormDraftField",
    "DepartmentBudget", "ExpenseProposal", "DepartmentState", "DepartmentMessage", "DepartmentPolicy",
    "UsageLedger", "VaultSecret", "Subscription", "UserQuota", "ErrorEvent",
    "HeartbeatConfigRow",
    "RunTraceEvent",
    "ExperienceLog",
    "ProjectPipeline",
    "Project",
    "ApiKey",
    "BackgroundTask",
    "ConsentGrant",
    "CronRun",
    "McpServer",
    "Notification",
    "PluginPolicyOverride",
    "PushSubscription",
    "Secret",
    "WaitlistEntry",
    "Workstream", "WorkstreamEvent",
    "WorkstreamStatus", "WorkstreamEscalationLevel", "WorkstreamEventKind",
]
