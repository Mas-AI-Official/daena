"""Approval service: manage governance approval workflows.

When a governance evaluation yields Tier 3 or 4, an approval request
is created and routed to a human for decision. This service handles
the full lifecycle: create → assign → approve/reject → expire.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select

from app.core.exceptions import NotFoundError
from app.models.governance import GoaRequest, PendingApproval
from app.services._base import BaseService

# Approvals expire after this many hours if not acted upon
_DEFAULT_EXPIRY_HOURS = 24


class ApprovalService(BaseService):
    """Manages governance approval requests and decisions.

    Usage::

        service = ApprovalService(db)
        approval = await service.request_approval(
            tenant_id=tenant_id,
            user_id=user_id,
            action_type="DEPLOY",
            risk_level="HIGH",
            governance_tier=3,
        )
    """

    async def request_approval(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        action_type: str,
        action_params: dict | None = None,
        risk_level: str,
        governance_tier: int,
        session_id: UUID | None = None,
        context: dict | None = None,
    ) -> dict:
        """Create a new governance approval request.

        Args:
            tenant_id: Tenant UUID.
            user_id: Requesting user UUID.
            action_type: Action that requires approval.
            action_params: Action parameters.
            risk_level: Assessed risk level.
            governance_tier: Resolved governance tier.
            session_id: Optional chat session context.
            context: Additional context for the reviewer.

        Returns:
            Dict with the approval request details.
        """
        expires_at = datetime.now(UTC) + timedelta(hours=_DEFAULT_EXPIRY_HOURS)

        request = GoaRequest(
            tenant_id=tenant_id,
            user_id=user_id,
            action_type=action_type,
            action_params=action_params,
            risk_level=risk_level,
            governance_tier=governance_tier,
            status="PENDING",
            expires_at=expires_at,
            session_id=session_id,
        )
        self.db.add(request)
        await self.db.flush()

        # Create pending approval entry
        pending = PendingApproval(
            tenant_id=tenant_id,
            request_id=request.id,
            priority=governance_tier,
            context=context,
        )
        self.db.add(pending)
        await self.db.flush()

        return self._request_to_dict(request)

    async def approve(
        self,
        *,
        request_id: UUID,
        tenant_id: UUID,
        decided_by: UUID,
        reason: str | None = None,
    ) -> dict:
        """Approve a pending governance request.

        Args:
            request_id: UUID of the GoaRequest.
            tenant_id: Tenant UUID (isolation check).
            decided_by: UUID of the approving user.
            reason: Optional approval reason.

        Returns:
            Updated approval request dict.

        Raises:
            NotFoundError: If request doesn't exist or wrong tenant.
        """
        request = await self._get_request_or_404(request_id, tenant_id)

        request.status = "APPROVED"
        request.decided_by = decided_by
        request.decided_at = datetime.now(UTC)
        request.decision_reason = reason

        # Clean up pending approval
        await self._delete_pending(request_id)
        await self.db.flush()
        # Refresh pulls server-generated values (e.g. updated_at via
        # onupdate=func.now()) back into the ORM object while we are
        # still in async context. Without this, the later emit work
        # yields control, SQLAlchemy lazy-loads expired attributes,
        # and the reload fails with MissingGreenlet outside the
        # greenlet-spawned async session.
        await self.db.refresh(request)

        # Border Agent emit: let peer departments see approval decisions.
        # Finance.expense_approved fires for expense-type actions so the
        # relevant rooms (Finance, Operations) see the movement in real
        # time; Governance.tier_high fires for any high-tier decision
        # (t3+) so the governance room stays current. Fail-safe pattern
        # so an emit error never rolls back the approval.
        await self._emit_decision_event(request, approved=True)

        return self._request_to_dict(request)

    async def reject(
        self,
        *,
        request_id: UUID,
        tenant_id: UUID,
        decided_by: UUID,
        reason: str | None = None,
    ) -> dict:
        """Reject a pending governance request.

        Args:
            request_id: UUID of the GoaRequest.
            tenant_id: Tenant UUID (isolation check).
            decided_by: UUID of the rejecting user.
            reason: Optional rejection reason.

        Returns:
            Updated approval request dict.

        Raises:
            NotFoundError: If request doesn't exist or wrong tenant.
        """
        request = await self._get_request_or_404(request_id, tenant_id)

        request.status = "REJECTED"
        request.decided_by = decided_by
        request.decided_at = datetime.now(UTC)
        request.decision_reason = reason

        # Clean up pending approval
        await self._delete_pending(request_id)
        await self.db.flush()
        # See approve() for why the refresh is load-bearing: eager
        # server-default fetch keeps SQLAlchemy happy when emit work
        # yields control.
        await self.db.refresh(request)

        # Border Agent emit (rejection path): peer departments get a
        # negative-signal variant so they can unblock or escalate.
        await self._emit_decision_event(request, approved=False)

        return self._request_to_dict(request)

    async def get_request(
        self,
        *,
        request_id: UUID,
        tenant_id: UUID,
    ) -> dict:
        """Get a single approval request by ID.

        Args:
            request_id: UUID of the GoaRequest.
            tenant_id: Tenant UUID.

        Returns:
            Approval request dict.

        Raises:
            NotFoundError: If not found.
        """
        request = await self._get_request_or_404(request_id, tenant_id)
        return self._request_to_dict(request)

    async def list_pending(
        self,
        *,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
    ) -> dict:
        """List approval requests for a tenant, optionally filtered by status.

        Args:
            tenant_id: Tenant UUID.
            page: 1-based page number.
            page_size: Items per page.
            status: Optional status filter (PENDING, APPROVED, REJECTED, EXPIRED).
                    Defaults to PENDING when not provided.

        Returns:
            Dict with data (list of requests), pagination metadata.
        """
        effective_status = status or "PENDING"
        stmt = (
            select(GoaRequest)
            .where(GoaRequest.tenant_id == tenant_id)
            .where(GoaRequest.status == effective_status)
            .order_by(GoaRequest.created_at.desc())
        )

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Fetch page
        offset = (page - 1) * page_size
        paginated = stmt.offset(offset).limit(page_size)
        result = await self.db.execute(paginated)
        items = list(result.scalars().all())

        return {
            "data": [self._request_to_dict(r) for r in items],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": max(1, math.ceil(total / page_size)),
            },
        }

    async def expire_stale(self, *, tenant_id: UUID) -> int:
        """Mark expired pending requests as EXPIRED.

        Args:
            tenant_id: Tenant UUID.

        Returns:
            Number of requests expired.
        """
        now = datetime.now(UTC)
        stmt = (
            select(GoaRequest)
            .where(GoaRequest.tenant_id == tenant_id)
            .where(GoaRequest.status == "PENDING")
            .where(GoaRequest.expires_at < now)
        )
        result = await self.db.execute(stmt)
        expired_requests = list(result.scalars().all())

        for req in expired_requests:
            req.status = "EXPIRED"
            await self._delete_pending(req.id)

        if expired_requests:
            await self.db.flush()

        return len(expired_requests)

    # ── Private helpers ──

    async def _emit_decision_event(
        self, request: GoaRequest, *, approved: bool
    ) -> None:
        """Emit a BorderAgent signal for an approval decision.

        Maps action_type and governance tier onto the DepartmentEvent
        catalog so peer departments (Finance, Governance, Ops) see the
        decision in their PeerSignalsPane feed. Fail-safe: any error is
        swallowed with a debug log so approvals never roll back because
        of a notification hiccup.
        """
        try:
            from app.core.logging import get_logger
            from app.services.departments.border_agent import (
                DepartmentEvent,
                get_border_agent,
            )

            log = get_logger(__name__)
            action_type = (request.action_type or "").lower()
            tier = int(request.governance_tier or 0)

            # Finance.expense_* for expense-flavored approvals
            if "expense" in action_type:
                event = (
                    DepartmentEvent.EXPENSE_APPROVED
                    if approved
                    else DepartmentEvent.EXPENSE_PROPOSAL
                )
                ba = await get_border_agent(
                    tenant_id=request.tenant_id, department="Finance"
                )
                await ba.emit(
                    event,
                    payload={
                        "task_summary": (
                            f"Expense {'approved' if approved else 'rejected'}: "
                            f"{request.action_type} (tier {tier})"
                        ),
                        "request_id": str(request.id),
                        "risk_level": request.risk_level,
                        "governance_tier": tier,
                        "approved": approved,
                    },
                )

            # Governance.tier_high whenever a high-tier decision is made
            if tier >= 3:
                ba_gov = await get_border_agent(
                    tenant_id=request.tenant_id,
                    department="Skill Governance",
                )
                await ba_gov.emit(
                    DepartmentEvent.GOV_TIER_HIGH,
                    payload={
                        "task_summary": (
                            f"Tier-{tier} {request.action_type} "
                            f"{'approved' if approved else 'rejected'}"
                        ),
                        "request_id": str(request.id),
                        "risk_level": request.risk_level,
                        "governance_tier": tier,
                        "approved": approved,
                    },
                )

            # Legal.compliance_flag for legal-flavored action types OR
            # CRITICAL risk rejections (these almost always have a legal
            # follow-up). Heuristic keeps the lens narrow -- only the
            # actual legal signal reaches the Legal room, not every
            # tier-3 decision.
            risk_str = (request.risk_level or "").upper()
            is_legal_action = any(
                token in action_type
                for token in ("contract", "legal", "compliance", "nda", "license")
            )
            is_critical_reject = risk_str == "CRITICAL" and not approved
            if is_legal_action or is_critical_reject:
                # Emit as Skill Governance -- it's the entity making
                # the call. Legal is the LISTENER via its
                # *.compliance_* pattern. Emitting as Legal would
                # trigger self-echo suppression and silence the signal.
                ba_legal = await get_border_agent(
                    tenant_id=request.tenant_id,
                    department="Skill Governance",
                )
                await ba_legal.emit(
                    DepartmentEvent.COMPLIANCE_FLAG,
                    payload={
                        "task_summary": (
                            f"Compliance flag: {request.action_type} "
                            f"({'approved' if approved else 'rejected'}, "
                            f"risk={risk_str or 'UNKNOWN'})"
                        ),
                        "request_id": str(request.id),
                        "risk_level": request.risk_level,
                        "governance_tier": tier,
                        "approved": approved,
                        "trigger": (
                            "legal_action" if is_legal_action else "critical_reject"
                        ),
                    },
                )
        except Exception as exc:  # pragma: no cover - fail-safe
            try:
                from app.core.logging import get_logger

                get_logger(__name__).debug(
                    "approval.decision.emit_failed", error=str(exc)
                )
            except Exception:
                pass

    async def _get_request_or_404(
        self, request_id: UUID, tenant_id: UUID
    ) -> GoaRequest:
        """Fetch a GoaRequest by ID with tenant check.

        Args:
            request_id: UUID of the request.
            tenant_id: Tenant UUID for isolation.

        Returns:
            GoaRequest ORM instance.

        Raises:
            NotFoundError: If not found or wrong tenant.
        """
        stmt = (
            select(GoaRequest)
            .where(GoaRequest.id == request_id)
            .where(GoaRequest.tenant_id == tenant_id)
        )
        result = await self.db.execute(stmt)
        request = result.scalar_one_or_none()
        if request is None:
            raise NotFoundError(f"Approval request not found: {request_id}")
        return request

    async def _delete_pending(self, request_id: UUID) -> None:
        """Remove the PendingApproval entry for a resolved request.

        Args:
            request_id: UUID of the GoaRequest.
        """
        stmt = select(PendingApproval).where(
            PendingApproval.request_id == request_id
        )
        result = await self.db.execute(stmt)
        pending = result.scalar_one_or_none()
        if pending:
            await self.db.delete(pending)

    @staticmethod
    def _request_to_dict(request: GoaRequest) -> dict:
        """Convert GoaRequest model to response dict.

        Args:
            request: GoaRequest ORM instance.

        Returns:
            Serializable dict.
        """
        return {
            "id": str(request.id),
            "tenant_id": str(request.tenant_id),
            "user_id": str(request.user_id),
            "action_type": request.action_type,
            "action_params": request.action_params,
            "risk_level": request.risk_level,
            "governance_tier": request.governance_tier,
            "status": request.status,
            "decided_by": str(request.decided_by) if request.decided_by else None,
            "decided_at": (
                request.decided_at.isoformat() if request.decided_at else None
            ),
            "decision_reason": request.decision_reason,
            "expires_at": (
                request.expires_at.isoformat() if request.expires_at else None
            ),
            "session_id": (
                str(request.session_id) if request.session_id else None
            ),
            "created_at": (
                request.created_at.isoformat() if request.created_at else None
            ),
            "updated_at": (
                request.updated_at.isoformat() if request.updated_at else None
            ),
        }
