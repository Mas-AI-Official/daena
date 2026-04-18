"""Chat request/response schemas.

Defines typed models for session CRUD and message operations.
All responses use the StandardResponse envelope from _base.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas._base import DaenaSchema

# ── Requests ──


class CreateSessionRequest(BaseModel):
    """Create a new chat session."""

    title: str | None = Field(None, max_length=500)
    mode: str = Field("CMD", pattern="^(CMD|EXE)$")
    routing_mode: str = Field("STANDARD", pattern="^(STANDARD|COUNCIL|QUINTESSENCE)$")
    governance_mode: str = Field(
        "BALANCED",
        pattern="^(YOLO|LIGHT|STANDARD|STRICT|PARANOID|UNLEASHED|BALANCED|GOVERNED)$",
    )
    autopilot: bool = False
    think_mode: bool = False
    category_id: UUID | None = None
    department_id: UUID | None = None


class UpdateSessionRequest(BaseModel):
    """Update session metadata (title, mode, archive status)."""

    title: str | None = Field(None, max_length=500)
    mode: str | None = Field(None, pattern="^(CMD|EXE)$")
    routing_mode: str | None = Field(
        None, pattern="^(STANDARD|COUNCIL|QUINTESSENCE)$"
    )
    governance_mode: str | None = Field(
        None,
        pattern="^(YOLO|LIGHT|STANDARD|STRICT|PARANOID|UNLEASHED|BALANCED|GOVERNED)$",
    )
    autopilot: bool | None = None
    think_mode: bool | None = None
    is_archived: bool | None = None


class SendMessageRequest(BaseModel):
    """Send a message in a chat session."""

    role: str = Field("USER", pattern="^(USER|SYSTEM)$")
    content: str = Field(..., min_length=1, max_length=100_000)
    preferred_model: str | None = Field(None, max_length=200)
    governance_mode: str | None = Field(
        None,
        pattern="^(YOLO|LIGHT|STANDARD|STRICT|PARANOID|UNLEASHED|BALANCED|GOVERNED)$",
    )


class StreamMessageRequest(SendMessageRequest):
    """Canonical streaming request for existing or first-turn chat."""

    session_id: UUID | None = None
    title: str | None = Field(None, max_length=500)
    mode: str | None = Field(None, pattern="^(CMD|EXE)$")
    routing_mode: str | None = Field(None, pattern="^(STANDARD|COUNCIL|QUINTESSENCE)$")
    governance_mode: str | None = Field(
        None,
        pattern="^(YOLO|LIGHT|STANDARD|STRICT|PARANOID|UNLEASHED|BALANCED|GOVERNED)$",
    )
    autopilot: bool = False
    think_mode: bool = False
    category_id: UUID | None = None
    department_id: UUID | None = None


class TruncateMessagesRequest(BaseModel):
    """Truncate session messages from a given message onwards (inclusive)."""

    from_message_id: UUID


# ── Responses ──


class SessionResponse(DaenaSchema):
    """Chat session summary (no messages)."""

    id: UUID
    user_id: UUID
    tenant_id: UUID
    title: str | None = None
    mode: str
    routing_mode: str
    governance_mode: str
    autopilot: bool = False
    think_mode: bool = False
    category_id: UUID | None = None
    department_id: UUID | None = None
    department_name: str | None = None
    is_archived: bool
    created_at: str | None = None
    updated_at: str | None = None
    message_count: int = 0


class MessageResponse(DaenaSchema):
    """Individual chat message."""

    id: UUID
    session_id: UUID
    role: str
    content: str
    model_used: str | None = None
    provider_used: str | None = None
    governance_tier: int | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None
    token_count_input: int | None = None
    token_count_output: int | None = None
    created_at: str | None = None
