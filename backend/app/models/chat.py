"""Chat models: ChatSession, ChatMessage, ChatCategory.

The core conversation data model. Sessions hold messages.
Categories organize sessions into user-defined groups.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.identity import User
    from app.models.organization import Department


class ChatCategory(Base, TenantMixin, TimestampMixin):
    """User-defined category for organizing chat sessions."""

    __tablename__ = "chat_categories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_chat_categories_tenant_id_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Relationships
    sessions: Mapped[list[ChatSession]] = relationship(back_populates="category")


class ChatSession(Base, TenantMixin, TimestampMixin):
    """A conversation thread between a user and Daena."""

    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mode: Mapped[str] = mapped_column(String(10), nullable=False, server_default="CMD")
    routing_mode: Mapped[str] = mapped_column(String(20), nullable=False, server_default="STANDARD")
    governance_slider: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="STANDARD"
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("chat_categories.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    autopilot: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    think_mode: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="chat_sessions")
    category: Mapped[ChatCategory | None] = relationship(back_populates="sessions")
    department: Mapped[Department] = relationship(lazy="selectin")
    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="session", cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    """Individual message within a chat session. Immutable once created."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    thinking_steps: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)
    tools_used: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    provider_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    governance_tier: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    session: Mapped[ChatSession] = relationship(back_populates="messages")
