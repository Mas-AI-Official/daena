"""Merge the two alembic heads into one (S-02 prerequisite).

Revision ID: 014_merge_heads
Revises: 013_add_research_draft_structured_payload, 010_add_error_events
Create Date: 2026-06-03

Context
-------
Revision 007 branched into two chains that never reconverged:
  * notifications chain: 008_add_notifications -> 009_add_workstream_spine_fields
    -> 010_add_connector_instance_owner_email -> 011_add_consent_grants
    -> 012_add_plugin_policy_overrides -> 013_add_research_draft_structured_payload
  * quota/error chain:  008_add_user_quotas -> 009_user_quota_month_anchor
    -> 010_add_error_events
With two heads, ``alembic upgrade head`` fails on a fresh production Postgres
("Multiple head revisions are present"). This is an empty merge revision -- it
reconciles the DAG so there is a single head again. NO schema or data change.
"""
from __future__ import annotations

from collections.abc import Sequence

revision: str = "014_merge_heads"
down_revision: tuple[str, str] = (
    "013_add_research_draft_structured_payload",
    "010_add_error_events",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op: this revision only reconciles two heads."""


def downgrade() -> None:
    """No-op: splitting back into two heads is not meaningful."""
