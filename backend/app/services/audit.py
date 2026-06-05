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
from datetime import datetime, timedelta
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
        # AUD-002: guarantee a strictly-monotonic created_at per tenant so the
        # hash chain has exactly ONE tail. datetime.utcnow() is only ~15.6ms-
        # resolution on Windows, so a burst of log_decision calls ties on
        # created_at; _get_last_hash orders by created_at and under ties could
        # pick a non-tail row -> two events share a prev_hash -> the tamper-
        # evident ledger FORKS. Clamp to last+1us to remove the tie at source
        # (the read-path verify already walks prev_hash links, not timestamps).
        last_created_at = await self._get_last_created_at(tenant_id)
        if last_created_at is not None:
            last_naive = last_created_at.replace(tzinfo=None)
            if now_dt <= last_naive:
                now_dt = last_naive + timedelta(microseconds=1)
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
        # AUD-001 fix: ``id`` added as tie-breaker. datetime.utcnow()
        # on Windows has ~15.6ms resolution; rapid inserts land on
        # identical created_at values, which makes pagination ordering
        # non-deterministic without a secondary key. UUIDs are not
        # strictly monotonic but they ARE total-ordered, which is what
        # the presentation layer needs for stable paginated output.
        stmt = (
            select(GoaAuditEvent)
            .where(GoaAuditEvent.tenant_id == tenant_id)
            .order_by(
                GoaAuditEvent.created_at.desc(),
                GoaAuditEvent.id.desc(),
            )
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

    async def verify_chain_integrity(
        self, *, tenant_id: UUID, deep: bool = False,
    ) -> dict:
        """Verify the hash chain integrity for a tenant's audit trail.

        Two checks compose:

        1. **Structural walk** (always): follow ``prev_hash`` links from
           GENESIS (the AUD-001 algorithm). Catches tampering that breaks
           the chain topology -- mutated ``prev_hash``, missing entries,
           injected entries, forked chains, multiple GENESIS rows.

        2. **Payload recompute** (``deep=True`` only): re-derive
           SHA-256(actor_id|action_type|result|prev_hash|timestamp) for
           each row and compare to the stored ``entry_hash``. Catches
           content tampering that the structural walk misses -- e.g. an
           attacker who flips ``result`` from BLOCKED to ALLOWED while
           leaving the chain links untouched. The structural walker has
           no way to detect this because the prev_hash pointers still
           form a valid chain; only recomputing the hash from payload
           reveals the lie.

        ``deep=False`` is the default for backwards compatibility with
        existing callers (frontend bell, GovernanceAuditPage) that
        pre-date this PR. PR-AUDIT-VERIFY frontend now calls with
        ``deep=true``; CLI / future operators should also.

        Returns:
            {
                valid: bool,                    # both checks pass
                total_entries: int,
                first_broken_id: str | None,    # structural defect id, or None
                first_corrupt_id: str | None,   # content tamper id (deep only),
                                                # None when deep=False or all
                                                # payloads recompute correctly
            }
        """
        stmt = select(GoaAuditEvent).where(
            GoaAuditEvent.tenant_id == tenant_id
        )
        result = await self.db.execute(stmt)
        events = list(result.scalars().all())

        if not events:
            return {
                "valid": True,
                "total_entries": 0,
                "first_broken_id": None,
                "first_corrupt_id": None,
            }

        total = len(events)
        structural = self._structural_walk(events)

        # Deep payload check (additive). Sort by (created_at, id) so the
        # "first" corrupt id is deterministic across SQLite + Postgres
        # even when timestamps tie on Windows' low-resolution clock.
        first_corrupt_id: str | None = None
        if deep:
            ordered = sorted(
                events,
                key=lambda e: (e.created_at or datetime.min, str(e.id)),
            )
            for event in ordered:
                recomputed = self._recompute_event_hash(event)
                if recomputed != event.entry_hash:
                    first_corrupt_id = str(event.id)
                    break

        return {
            "valid": structural["valid"] and first_corrupt_id is None,
            "total_entries": total,
            "first_broken_id": structural["first_broken_id"],
            "first_corrupt_id": first_corrupt_id,
        }

    @staticmethod
    def _structural_walk(events: list[GoaAuditEvent]) -> dict:
        """Walk the chain via prev_hash links (AUD-001 algorithm).

        Pulled out of ``verify_chain_integrity`` so the deep mode can
        compose structural + payload checks without duplicating the walk
        logic. Returns ``{valid, first_broken_id}`` -- ``total_entries``
        is supplied by the caller (it already has ``len(events)`` in
        scope).

        Detects:
            * Zero GENESIS entries (every row claims a predecessor)
            * >1 GENESIS entries (chain forked at the root)
            * Forks mid-chain (>1 successor for some prev_hash)
            * Orphans (entries whose prev_hash points outside the chain)
        """
        # Index events by prev_hash: each row is the successor of its
        # prev_hash. Multiple successors = fork = tamper.
        successors_by_prev: dict[str | None, list[GoaAuditEvent]] = {}
        for ev in events:
            successors_by_prev.setdefault(ev.prev_hash, []).append(ev)

        genesis_list = successors_by_prev.get(None, [])
        if len(genesis_list) == 0:
            # No GENESIS = oldest visible row is the broken link.
            return {"valid": False, "first_broken_id": str(events[0].id)}
        if len(genesis_list) > 1:
            return {"valid": False, "first_broken_id": str(genesis_list[0].id)}

        current = genesis_list[0]
        visited = 1
        while True:
            next_list = successors_by_prev.get(current.entry_hash, [])
            if len(next_list) == 0:
                break
            if len(next_list) > 1:
                return {"valid": False, "first_broken_id": str(next_list[0].id)}
            current = next_list[0]
            visited += 1

        if visited != len(events):
            walked_hashes: set[str] = set()
            cur2 = genesis_list[0]
            walked_hashes.add(cur2.entry_hash)
            while True:
                nxt = successors_by_prev.get(cur2.entry_hash, [])
                if not nxt:
                    break
                cur2 = nxt[0]
                walked_hashes.add(cur2.entry_hash)
            orphans = [e for e in events if e.entry_hash not in walked_hashes]
            return {"valid": False, "first_broken_id": str(orphans[0].id)}

        return {"valid": True, "first_broken_id": None}

    async def verify_chain_with_diagnostic(
        self, *, tenant_id: UUID,
    ) -> dict:
        """Walk the chain in order and on the first break return rich
        diagnostic info: row_id, kind (structural/content), previous_hash,
        expected_hash, actual_hash, plus the chain index of the break.

        Distinct from ``verify_chain_integrity``: that returns minimal
        boolean+id results for the existing GET endpoint and frontend
        badge. This method is the engine behind the new POST endpoint
        and surfaces the diagnostic fields an operator needs to triage
        a tamper (which row, which kind, what was expected).

        Walks in chain order (genesis -> ... -> tail) and combines
        structural + content checks in a single pass:

        1. Find GENESIS (prev_hash IS NULL). Zero or many GENESIS rows
           are themselves structural breaks.
        2. For the current row, recompute SHA-256 from payload. Mismatch
           = content break at this index.
        3. Look up the successor by ``successors_by_prev[entry_hash]``.
           Zero successors = end of chain. Two+ successors = fork =
           structural break.
        4. After the walk, ``visited != total`` indicates orphans
           (entries whose prev_hash doesn't link into the walked set).

        Returns:
            {
                verified: bool,
                total_entries: int,
                tenant_id: str,
                first_break_index: int | None,
                first_break: {
                    row_id: str,
                    kind: "structural" | "content",
                    previous_hash: str | None,
                    expected_hash: str,
                    actual_hash: str,
                } | None,
            }
        """
        stmt = select(GoaAuditEvent).where(
            GoaAuditEvent.tenant_id == tenant_id
        )
        result = await self.db.execute(stmt)
        events = list(result.scalars().all())
        total = len(events)

        if not events:
            return {
                "verified": True,
                "total_entries": 0,
                "tenant_id": str(tenant_id),
                "first_break_index": None,
                "first_break": None,
            }

        successors_by_prev: dict[str | None, list[GoaAuditEvent]] = {}
        for ev in events:
            successors_by_prev.setdefault(ev.prev_hash, []).append(ev)

        # Genesis check.
        genesis_list = successors_by_prev.get(None, [])
        if len(genesis_list) == 0:
            first = events[0]
            return {
                "verified": False,
                "total_entries": total,
                "tenant_id": str(tenant_id),
                "first_break_index": 0,
                "first_break": {
                    "row_id": str(first.id),
                    "kind": "structural",
                    "previous_hash": first.prev_hash,
                    "expected_hash": "<no predecessor row found>",
                    "actual_hash": first.entry_hash,
                },
            }
        if len(genesis_list) > 1:
            first = genesis_list[0]
            return {
                "verified": False,
                "total_entries": total,
                "tenant_id": str(tenant_id),
                "first_break_index": 0,
                "first_break": {
                    "row_id": str(first.id),
                    "kind": "structural",
                    "previous_hash": None,
                    "expected_hash": "<single GENESIS expected>",
                    "actual_hash": first.entry_hash,
                },
            }

        # Walk from genesis, content-check each row, structural-check edges.
        current = genesis_list[0]
        index = 0
        while True:
            recomputed = self._recompute_event_hash(current)
            if recomputed != current.entry_hash:
                return {
                    "verified": False,
                    "total_entries": total,
                    "tenant_id": str(tenant_id),
                    "first_break_index": index,
                    "first_break": {
                        "row_id": str(current.id),
                        "kind": "content",
                        "previous_hash": current.prev_hash,
                        "expected_hash": recomputed,
                        "actual_hash": current.entry_hash,
                    },
                }

            next_list = successors_by_prev.get(current.entry_hash, [])
            if len(next_list) == 0:
                break  # End of chain.
            if len(next_list) > 1:
                offender = next_list[0]
                return {
                    "verified": False,
                    "total_entries": total,
                    "tenant_id": str(tenant_id),
                    "first_break_index": index + 1,
                    "first_break": {
                        "row_id": str(offender.id),
                        "kind": "structural",
                        "previous_hash": offender.prev_hash,
                        "expected_hash": "<single successor expected>",
                        "actual_hash": offender.entry_hash,
                    },
                }
            current = next_list[0]
            index += 1

        visited = index + 1
        if visited != total:
            walked_hashes: set[str] = {genesis_list[0].entry_hash}
            cur2 = genesis_list[0]
            while True:
                nxt = successors_by_prev.get(cur2.entry_hash, [])
                if not nxt:
                    break
                cur2 = nxt[0]
                walked_hashes.add(cur2.entry_hash)
            orphans = [e for e in events if e.entry_hash not in walked_hashes]
            first = orphans[0]
            return {
                "verified": False,
                "total_entries": total,
                "tenant_id": str(tenant_id),
                "first_break_index": visited,
                "first_break": {
                    "row_id": str(first.id),
                    "kind": "structural",
                    "previous_hash": first.prev_hash,
                    "expected_hash": "<entry_hash matching this row's prev_hash>",
                    "actual_hash": first.entry_hash,
                },
            }

        return {
            "verified": True,
            "total_entries": total,
            "tenant_id": str(tenant_id),
            "first_break_index": None,
            "first_break": None,
        }

    @staticmethod
    def _recompute_event_hash(event: GoaAuditEvent) -> str:
        """Recompute SHA-256 from event payload (deep-mode primitive).

        Uses the same payload format as ``log_decision`` (pipe-joined
        actor_id | action_type | result | prev_hash | timestamp). When
        the recomputed value differs from ``event.entry_hash``, the row
        was tampered with after the original write -- regardless of
        whether the structural chain still walks cleanly.

        Cross-dialect timestamp normalization: ``log_decision`` writes
        ``datetime.utcnow()`` (naive). SQLite round-trips naive;
        Postgres returns tz-aware. Strip tz info on read so isoformat()
        produces the same string the original hash consumed.
        """
        timestamp = ""
        if event.created_at is not None:
            ts = event.created_at
            if ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
            timestamp = ts.isoformat()
        return AuditService._compute_hash(
            actor_id=event.actor_id,
            action_type=event.action_type,
            result=event.result,
            prev_hash=event.prev_hash,
            timestamp=timestamp,
        )

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
            .order_by(GoaAuditEvent.created_at.desc(), GoaAuditEvent.id.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_last_created_at(self, tenant_id: UUID):
        """Max created_at for a tenant.

        Used by log_decision to keep created_at strictly monotonic per tenant
        (AUD-002) so the hash chain has a single unambiguous tail. Returns None
        when the tenant has no audit events yet.
        """
        stmt = select(func.max(GoaAuditEvent.created_at)).where(
            GoaAuditEvent.tenant_id == tenant_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

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
