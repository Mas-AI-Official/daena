"""Founder diagnostics and routing policy schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RoutingPreviewRequest(BaseModel):
    """Non-executing routing preview for founder diagnostics."""

    message: str = Field(..., min_length=1, max_length=100_000)
    governance_slider: str = Field(
        "STANDARD",
        pattern="^(YOLO|LIGHT|STANDARD|STRICT|PARANOID)$",
    )
    chat_mode: str = Field("CMD", pattern="^(CMD|EXE)$")
    routing_mode: str | None = Field(
        None,
        pattern="^(STANDARD|COUNCIL|QUINTESSENCE)$",
    )
    think_mode: bool = False


class RoutingPolicyUpdate(BaseModel):
    """Founder routing policy update.

    All fields are optional.  Absent fields retain system defaults.
    """

    preferred_models: dict[str, str] | None = Field(
        None,
        description=(
            "Intent -> model_id overrides. "
            "Keys: SIMPLE, SEARCH, CODING, ANALYSIS, CREATIVE, MULTI_STEP."
        ),
    )
    provider_priority: list[str] | None = Field(
        None,
        description="Ordered list of preferred provider names (e.g. ['ollama', 'anthropic']).",
    )
    cost_ceiling: float | None = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Max USD per single LLM request. None = no limit.",
    )
    blocked_models: list[str] | None = Field(
        None,
        description="Model IDs that must never be selected.",
    )
    blocked_providers: list[str] | None = Field(
        None,
        description="Provider names that must never be selected.",
    )
    default_model: str | None = Field(
        None,
        description="Override global default fallback model.",
    )
    enforce_local_only: bool | None = Field(
        None,
        description="If true, only local Ollama models are allowed.",
    )
