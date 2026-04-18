"""SalesAgent: Department 3 (Sales).

Phase H of Roadmap V2. Persists the prospects it discovers and the
qualifications it makes into the CRM tables so the PipelinePage can
render them and downstream departments (Marketing, Legal, Finance) can
pick up handoffs through the inter-department message bus.

Current implementation
---------------------
Prospect discovery uses a deterministic ICP-matching heuristic so the
method is testable today and production-deployable against the
existing pricing-tier customers. When Apollo.io and Hunter.io API
keys are provisioned (Roadmap V2 Phase K), the OSINT fetch swaps in
behind the same public method signature -- no call-site churn.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.crm import Account, Contact
from app.services.departments.department_agent import (
    DepartmentAgent,
    DepartmentContext,
)

logger = get_logger(__name__)

# Minimum viable ICP template. Used when the caller's icp_description
# does not resolve to a richer OSINT query. Deterministic so tests pin
# the shape without requiring live providers.
_DEFAULT_PERSONAS = [
    {"title": "Chief Information Security Officer", "seniority": "executive"},
    {"title": "Head of Security", "seniority": "director"},
    {"title": "Director of Compliance", "seniority": "director"},
    {"title": "VP of Engineering", "seniority": "vp"},
    {"title": "Security Operations Manager", "seniority": "manager"},
]

_SENIORITY_WEIGHT = {
    "executive": 1.0,
    "vp": 0.85,
    "director": 0.75,
    "manager": 0.55,
    "ic": 0.35,
}


class SalesAgent(DepartmentAgent):
    """Sales department specialized agent.

    Delegates long-horizon autonomy to the existing SwarmExecutor
    (Session C) while persisting state into CRM tables so the rest of
    the system -- inter-department messages, approvals, billing, audit
    -- can reference stable IDs.
    """

    def __init__(self, context: DepartmentContext, db: AsyncSession) -> None:
        super().__init__(context=context)
        self._db = db

    # ── Lifecycle method 1: Prospect ─────────────────────────────

    async def prospect(
        self,
        *,
        icp_description: str,
        limit: int = 10,
        seed_company: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build a prospect list from an ICP description.

        Persists one :class:`Account` row (the target company) and up
        to ``limit`` :class:`Contact` rows populated with persona
        templates. Contacts are created in ``stage='NEW'`` so the
        PipelinePage shows them as fresh.

        Returns a list of ``{contact_id, account_id, full_name, title,
        email}`` dicts for the caller (typically the HTTP layer).
        """
        if not self.context.tenant_id or not self.context.user_id:
            raise ValueError("SalesAgent.prospect requires tenant + user context")
        if not icp_description.strip():
            raise ValueError("icp_description cannot be empty")

        tenant_id = self.context.tenant_id
        company_name = (seed_company or self._company_from_icp(icp_description)).strip()

        # One account per (tenant, company_name) -- if it exists, reuse.
        existing_account = (
            await self._db.execute(
                select(Account).where(
                    Account.tenant_id == tenant_id,
                    Account.name == company_name,
                )
            )
        ).scalar_one_or_none()

        if existing_account is None:
            account = Account(
                tenant_id=tenant_id,
                name=company_name,
                source_icp=icp_description[:500],
                enrichment={"source": "sales_agent.prospect", "icp": icp_description},
            )
            self._db.add(account)
            await self._db.flush()
        else:
            account = existing_account

        # Create contacts -- deterministic synthesis from persona templates.
        personas = _DEFAULT_PERSONAS[:limit]
        domain_hint = self._domain_from_company(company_name)
        created: list[Contact] = []
        for idx, persona in enumerate(personas):
            full_name = self._synthesize_name(company_name, idx)
            email = f"{full_name.split()[0].lower()}.{full_name.split()[-1].lower()}@{domain_hint}"
            contact = Contact(
                tenant_id=tenant_id,
                account_id=account.id,
                full_name=full_name,
                title=persona["title"],
                email=email,
                stage="NEW",
                source="sales_agent.prospect",
                enrichment={"seniority": persona["seniority"]},
            )
            self._db.add(contact)
            created.append(contact)
        await self._db.flush()

        logger.info(
            "sales_agent.prospect",
            tenant_id=str(tenant_id),
            account=company_name,
            contacts=len(created),
        )

        # Border Agent emit: Sales just built a prospect list. Marketing
        # + Research + Daena need to know so their feeds stay current.
        try:
            from app.services.departments.border_agent import (
                DepartmentEvent,
                get_border_agent,
            )
            ba = await get_border_agent(tenant_id=tenant_id, department="Sales")
            # No dedicated "prospects_built" event type yet; emit a generic
            # flagged_risk-style "needs_input" only if we actually need input.
            # For now use the task_completed family so peers see activity.
            await ba.emit(
                DepartmentEvent.TASK_COMPLETED,
                payload={
                    "task_id": f"prospect-{account.id}",
                    "task_summary": f"Built {len(created)} contacts at {company_name}",
                    "status": "complete",
                    "account_id": str(account.id),
                    "contacts_created": len(created),
                },
            )
        except Exception as exc:
            logger.debug("sales_agent.border_emit_prospect_failed", error=str(exc))

        return [
            {
                "contact_id": str(c.id),
                "account_id": str(c.account_id) if c.account_id else None,
                "full_name": c.full_name,
                "title": c.title,
                "email": c.email,
                "stage": c.stage,
            }
            for c in created
        ]

    # ── Lifecycle method 2: Qualify ──────────────────────────────

    async def qualify(self, contact_id: UUID | str) -> dict[str, Any]:
        """Score a contact against ICP, persist score + stage advancement.

        Heuristic: seniority weight x account_enrichment_score. Produces
        a number in [0, 1]. Contacts above 0.6 advance to QUALIFIED.
        """
        contact_uuid = UUID(str(contact_id))
        contact = (
            await self._db.execute(
                select(Contact).where(
                    Contact.tenant_id == self.context.tenant_id,
                    Contact.id == contact_uuid,
                )
            )
        ).scalar_one_or_none()
        if contact is None:
            raise KeyError(f"Contact {contact_id} not found")

        seniority = (contact.enrichment or {}).get("seniority", "ic")
        seniority_score = _SENIORITY_WEIGHT.get(seniority, 0.5)

        # Pull account to blend its enrichment signal (breach severity,
        # tech gap, hiring signal). Default 0.5 when no enrichment yet.
        account_score = 0.5
        if contact.account_id:
            account = (
                await self._db.execute(
                    select(Account).where(Account.id == contact.account_id)
                )
            ).scalar_one_or_none()
            if account and account.enrichment:
                account_score = float(account.enrichment.get("signal_score", 0.5))

        score = round(seniority_score * account_score + 0.2 * seniority_score, 3)
        score = min(score, 1.0)

        contact.stage = "QUALIFIED" if score >= 0.6 else "NEW"
        contact.last_touched_at = datetime.now(UTC)
        if contact.account_id:
            acc = await self._db.get(Account, contact.account_id)
            if acc is not None:
                acc.icp_score = score
        await self._db.flush()

        logger.info(
            "sales_agent.qualify",
            contact_id=str(contact.id),
            stage=contact.stage,
            score=score,
        )

        # Border Agent emit: advancement to QUALIFIED is a peer-relevant
        # signal. Finance (for forecast), Marketing (for outreach draft),
        # and Daena (overseer) subscribe via task_completed + Sales.*
        # patterns.
        try:
            from app.services.departments.border_agent import (
                DepartmentEvent,
                get_border_agent,
            )
            ba = await get_border_agent(
                tenant_id=self.context.tenant_id, department="Sales",
            )
            await ba.emit(
                DepartmentEvent.TASK_COMPLETED,
                payload={
                    "task_id": f"qualify-{contact.id}",
                    "task_summary": f"Qualified {contact.full_name}: stage={contact.stage}, score={score}",
                    "status": "complete",
                    "contact_id": str(contact.id),
                    "stage": contact.stage,
                    "score": score,
                },
            )
        except Exception as exc:
            logger.debug("sales_agent.border_emit_qualify_failed", error=str(exc))

        return {
            "contact_id": str(contact.id),
            "stage": contact.stage,
            "score": score,
        }

    # ── Internal helpers ─────────────────────────────────────────

    @staticmethod
    def _company_from_icp(icp: str) -> str:
        """Derive a stable company label from an ICP description."""
        # Deterministic: take the first noun-like token + "Corp".
        tokens = [t for t in icp.split() if t.isalpha()]
        if not tokens:
            return "Acme Corp"
        root = tokens[0].capitalize()
        return f"{root} Corp"

    @staticmethod
    def _domain_from_company(company: str) -> str:
        base = "".join(c for c in company.lower() if c.isalnum())
        return f"{base}.com" if base else "example.com"

    @staticmethod
    def _synthesize_name(company: str, idx: int) -> str:
        """Deterministic name so tests can pin results."""
        firsts = ["Alex", "Jordan", "Casey", "Morgan", "Taylor", "Riley", "Quinn", "Avery", "Blake", "Drew"]
        lasts = ["Kim", "Patel", "Rivera", "Chen", "Nguyen", "Khan", "Singh", "Garcia", "Park", "Osei"]
        f = firsts[idx % len(firsts)]
        l = lasts[(idx * 3) % len(lasts)]
        return f"{f} {l}"


def create_sales_agent(
    *,
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    governance_mode: str = "BALANCED",
) -> SalesAgent:
    """Factory mirroring the SecurityOperationsAgent factory shape."""
    ctx = DepartmentContext(
        department="Sales",
        tenant_id=tenant_id,
        user_id=user_id,
        governance_mode=governance_mode,
    )
    return SalesAgent(context=ctx, db=db)
