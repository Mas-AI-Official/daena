"""Durable record of a completed security scan report (PR-9 Klyntar Hardening).

Context
-------
Completed scans used to persist to disk JSON only
(``{SECURITY_REPORTS_DIR}/{job_id}.json`` via
``ScanWorkflow._persist_report``). Rule 17 (ADR-001) requires every feature to
answer "where does this persist?" with a database, not just a file that a disk
loss or container rebuild wipes. This additive, tenant-scoped table is the
durable mirror: one row per completed scan, queryable per tenant, surviving
process restart and disk loss.

The disk JSON remains the primary artifact (it carries the full round-trip
payload). This row is a best-effort durable mirror written fail-safe by
``ScanWorkflow._persist_report_db`` -- a write failure logs and is swallowed so
it never breaks the scan completion path. Lossless detail (findings,
severity_counts) is stored as JSON; the scalar columns mirror the most-queried
fields for cheap tenant-scoped lookups.

Cross-dialect: ``GUID`` (UUID on Postgres, String(36) on SQLite) and
``JSONBCompat`` (JSONB on Postgres, JSON on SQLite); other columns are stdlib
SQLAlchemy types that round-trip identically.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Float, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin


class ScanReportRecord(Base, TenantMixin, TimestampMixin):
    """One row per completed scan report, scoped to its owning tenant."""

    __tablename__ = "scan_reports"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tier: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="scout",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="complete",
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings: Mapped[list] = mapped_column(
        JSONBCompat(), nullable=False, default=list, server_default="[]",
    )
    severity_counts: Mapped[dict] = mapped_column(
        JSONBCompat(), nullable=False, default=dict, server_default="{}",
    )
    cost_usd: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0",
    )
    duration_secs: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0",
    )
    report_pdf_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "job_id", name="uq_scan_reports_tenant_id_job_id"),
        Index("ix_scan_reports_tenant_id_created_at", "tenant_id", "created_at"),
    )
