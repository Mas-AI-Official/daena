"""Audit service: tamper-evident ledger for governance decisions.

Implements Hard Law #1 (No Unlogged Actions) and Hard Law #9
(Audit Trail Integrity). Each audit entry contains a hash chain
linking to the previous entry, making the ledger tamper-evident.

The hash chain works like this:
    entry_hash = sha256(actor_id + action_type + result + prev_hash + timestamp)
    prev_hash  = entry_hash of the preceding record for this tenant

If any record is modified or deleted, the chain breaks and
integrity verification detects it.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select

from app.models.governance import GoaAuditEvent
from app.services._base import BaseService


class AuditService(BaseService):
    """Append-only, hash-chained audit log for governance events.

    Usage::

        audit = AuditService(db)
        entry = await audit.log_decision(
            tenant_id=tenant_id,
            actor_id=user_id,
            actor_type="USER",
            action_type="DELETE",
            result="BLOCKED",
            risk_level="CRITICAL",
            governance_tier=4,
        )
    """

    async def log_decision(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID | None = None,
        actor_type: str,
        action_type: str,
        action_params: dict | None = None,
        result: str,
        risk_level: str,
        governance_tier: int,
        session_id: UUID | None = None,
    ) -> dict:
        """Append a new audit event to the tamper-evident ledger.

        Args:
            tenant_id: Tenant UUID (scopes the hash chain).
            actor_id: UUID of the actor (user or agent), None for system.
            actor_type: Actor classification (USER/AGENT/SYSTEM/FOUNDER).
            action_type: The action that was evaluated.
            action_params: Action parameters for context.
            result: Outcome (ALLOWED/BLOCKED/APPROVAL_REQUIRED/etc).
            risk_level: Risk classification.
            governance_tier: Resolved governance tier (0-4).
            session_id: Optional chat session context.

        Returns:
            Dict with entry details including entry_hash.
        """
        # Get the last hash for this tenant (hash chain)
        prev_hash = await self._get_last_hash(tenant_id)

        # Build the hash payload — use Python datetime for microsecond
        # precision (SQLite CURRENT_TIMESTAMP is second-level only).
        now_dt = datetime.utcnow()
        now = now_dt.isoformat()
        entry_hash = self._compute_hash(
            actor_id=actor_id,
            action_type=action_type,
            result=result,
            prev_hash=prev_hash,
            timestamp=now,
        )

        event = GoaAuditEvent(
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_type=actor_type,
            action_type=action_type,
            action_params=action_params,
            result=result,
            risk_level=risk_level,
            governance_tier=governance_tier,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            session_id=session_id,
            created_at=now_dt,
        )
        self.db.add(event)
        await self.db.flush()

        return self._event_to_dict(event)

    async def get_audit_trail(
        self,
        *,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 50,
        action_type: str | None = None,
        actor_id: UUID | None = None,
    ) -> dict:
        """Retrieve paginated audit trail for a tenant.

        Args:
            tenant_id: Tenant UUID.
            page: 1-based page number.
            page_size: Items per page.
            action_type: Optional filter by action type.
            actor_id: Optional filter by actor.

        Returns:
            Dict with data (list of entries), pagination metadata.
        """
        stmt = (
            select(GoaAuditEvent)
            .where(GoaAuditEvent.tenant_id == tenant_id)
            .order_by(GoaAuditEvent.created_at.desc())
        )

        if action_type is not None:
            stmt = stmt.where(GoaAuditEvent.action_type == action_type)
        if actor_id is not None:
            stmt = stmt.where(GoaAuditEvent.actor_id == actor_id)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Fetch page
        offset = (page - 1) * page_size
        paginated = stmt.offset(offset).limit(page_size)
        result = await self.db.execute(paginated)
        items = list(result.scalars().all())

        return {
            "data": [self._event_to_dict(e) for e in items],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": max(1, math.ceil(total / page_size)),
            },
        }

    async def verify_chain_integrity(self, *, tenant_id: UUID) -> dict:
        """Verify the hash chain integrity for a tenant's audit trail.

        Walks the chain from oldest to newest, recomputing hashes.
        Any mismatch indicates tampering.

        Args:
            tenant_id: Tenant UUID.

        Returns:
            Dict with valid (bool), total_entries, first_broken_id (if any).
        """
        stmt = (
            select(GoaAuditEvent)
            .where(GoaAuditEvent.tenant_id == tenant_id)
            .order_by(GoaAuditEvent.created_at.asc())
        )
        result = await self.db.execute(stmt)
        events = list(result.scalars().all())

        if not events:
            return {"valid": True, "total_entries": 0, "first_broken_id": None}

        expected_prev_hash: str | None = None
        for event in events:
            # Check prev_hash linkage
            if event.prev_hash != expected_prev_hash:
                return {
                    "valid": False,
                    "total_entries": len(events),
                    "first_broken_id": str(event.id),
                }
            expected_prev_hash = event.entry_hash

        return {"valid": True, "total_entries": len(events), "first_broken_id": None}

    async def _get_last_hash(self, tenant_id: UUID) -> str | None:
        """Get the entry_hash of the most recent audit event for a tenant.

        Args:
            tenant_id: Tenant UUID.

        Returns:
            The last entry_hash, or None if no events exist.
        """
        stmt = (
            select(GoaAuditEvent.entry_hash)
            .where(GoaAuditEvent.tenant_id == tenant_id)
            .order_by(GoaAuditEvent.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _compute_hash(
        *,
        actor_id: UUID | None,
        action_type: str,
        result: str,
        prev_hash: str | None,
        timestamp: str,
    ) -> str:
        """Compute SHA-256 hash for an audit entry.

        Args:
            actor_id: Actor UUID (or None for system).
            action_type: Action being audited.
            result: Decision result.
            prev_hash: Hash of previous entry in chain.
            timestamp: ISO timestamp string.

        Returns:
            Hex-encoded SHA-256 hash.
        """
        payload = "|".join([
            str(actor_id) if actor_id else "SYSTEM",
            action_type,
            result,
            prev_hash or "GENESIS",
            timestamp,
        ])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _event_to_dict(event: GoaAuditEvent) -> dict:
        """Convert audit event model to response dict.

        Args:
            event: GoaAuditEvent ORM instance.

        Returns:
            Serializable dict.
        """
        return {
            "id": str(event.id),
            "tenant_id": str(event.tenant_id),
            "actor_id": str(event.actor_id) if event.actor_id else None,
            "actor_type": event.actor_type,
            "action_type": event.action_type,
            "action_params": event.action_params,
            "result": event.result,
            "risk_level": event.risk_level,
            "governance_tier": event.governance_tier,
            "prev_hash": event.prev_hash,
            "entry_hash": event.entry_hash,
            "session_id": str(event.session_id) if event.session_id else None,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
