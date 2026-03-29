"""Skill Refinery models: RefinedSkill.

Department 9 -- knowledge extraction and governance.
Stores structured skills extracted from external content,
refined through the gap-finder/improver/critic pipeline,
and versioned for DCP augmentation at runtime.

Maturity tiers map to Daena-Mind vault:
    T0_RAW       -> ~/Daena-Mind/T0-raw/
    T1_DRAFT     -> ~/Daena-Mind/T1-draft/
    T2_REFINED   -> ~/Daena-Mind/T2-refined/
    T3_PRODUCTION -> ~/Daena-Mind/T3-production/
    T4_COMPOUND  -> ~/Daena-Mind/T4-compound/
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin

# Maturity tier enum values (stored as SmallInteger for DB efficiency)
MATURITY_TIERS = {
    "T0_RAW": 0,
    "T1_DRAFT": 1,
    "T2_REFINED": 2,
    "T3_PRODUCTION": 3,
    "T4_COMPOUND": 4,
}

MATURITY_LABELS = {v: k for k, v in MATURITY_TIERS.items()}


class RefinedSkill(Base, TenantMixin, TimestampMixin):
    """A structured skill extracted and refined by the Skill Refinery.

    Unlike the MCP-style ``Skill`` in execution.py, a RefinedSkill
    is a knowledge object: patterns, methods, anti-patterns, and
    evidence extracted from external content and refined through
    the 3-pass pipeline (gap finder, improver, critic).

    These augment Quintessence DCP prompts as evidence-backed
    patterns at Stage 7.5 of the chat_orchestrator pipeline.
    """

    __tablename__ = "refined_skills"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Identity
    skill_id: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True,
    )
    version: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="1.0",
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    # Classification
    domain: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
    )
    subdomains: Mapped[list] = mapped_column(
        JSONBCompat, nullable=False, server_default="[]",
    )
    maturity: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="0",
    )

    # Source lineage (quarantine-critical)
    source_metadata: Mapped[dict] = mapped_column(
        JSONBCompat, nullable=False, server_default="{}",
    )

    # Structured content
    steps: Mapped[list] = mapped_column(
        JSONBCompat, nullable=False, server_default="[]",
    )
    patterns: Mapped[list] = mapped_column(
        JSONBCompat, nullable=False, server_default="[]",
    )
    anti_patterns: Mapped[list] = mapped_column(
        JSONBCompat, nullable=False, server_default="[]",
    )
    improvements_by_daena: Mapped[list] = mapped_column(
        JSONBCompat, nullable=False, server_default="[]",
    )
    failure_modes: Mapped[list] = mapped_column(
        JSONBCompat, nullable=False, server_default="[]",
    )

    # Quality signals
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.0",
    )
    usage_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0",
    )
    success_rate: Mapped[float | None] = mapped_column(
        Float, nullable=True,
    )
    last_validated: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Embedding/search text (pre-computed for retrieval)
    embedding_text: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )

    # Soft delete (Rule 2: never delete, only archive)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
