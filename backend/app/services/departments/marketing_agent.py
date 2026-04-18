"""MarketingAgent: Department 3 (Marketing).

Phase H of Roadmap V2. Authors outreach drafts grounded in the Contact
record that Sales already qualified. Every draft is persisted as an
OutreachDraft row in ``DRAFT`` status so a human (or the Sales agent
under GOVERNED mode) must explicitly approve before send.

Current implementation
---------------------
Template-driven draft synthesis so the method is deterministic and
unit-testable without any LLM round-trip. The prompt-and-LLM variant
(Quintessence Council for high-value prospects) slots behind the same
public signature when the router ships.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.crm import Account, Contact, OutreachDraft
from app.services.departments.department_agent import (
    DepartmentAgent,
    DepartmentContext,
)

logger = get_logger(__name__)

# Channel -> template skeleton. Placeholders resolved per-contact.
_TEMPLATES: dict[str, dict[str, str]] = {
    "email_cold_v1": {
        "subject": "Governed security assessment for {company}",
        "body": (
            "Hi {first_name},\n\n"
            "I noticed {company} is growing its {function} team -- the kind of "
            "scaling that surfaces security blind spots the first time an "
            "auditor or breach lands. Daena runs governed offensive security "
            "with a tamper-evident audit chain, deployed air-gapped when the "
            "engagement requires sovereignty.\n\n"
            "Would a 20-minute scoping call next week be useful? I can send "
            "a sample report from a similar engagement before we chat.\n\n"
            "{signer}\n"
            "MAS-AI Technologies"
        ),
    },
    "email_governed_v1": {
        "subject": "Short note from MAS-AI Technologies",
        "body": (
            "Hi {first_name},\n\n"
            "Governed security platforms that ship reports auditors accept "
            "are rare; Daena ships them by default. Worth 15 minutes?\n\n"
            "{signer}"
        ),
    },
}


class MarketingAgent(DepartmentAgent):
    """Marketing department specialized agent."""

    def __init__(self, context: DepartmentContext, db: AsyncSession) -> None:
        super().__init__(context=context)
        self._db = db

    async def author_outreach(
        self,
        *,
        contact_id: UUID | str,
        template_id: str = "email_cold_v1",
        channel: str = "email",
        signer: str = "Masoud",
    ) -> dict[str, Any]:
        """Author an outreach draft and persist it in DRAFT status."""
        if template_id not in _TEMPLATES:
            raise ValueError(
                f"Unknown template_id {template_id!r}. "
                f"Known: {list(_TEMPLATES.keys())}"
            )

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

        # Pull account for context the template needs.
        account = None
        if contact.account_id:
            account = (
                await self._db.execute(
                    select(Account).where(Account.id == contact.account_id)
                )
            ).scalar_one_or_none()

        company = account.name if account else "your team"
        function = self._function_for_title(contact.title or "")
        first_name = (contact.full_name or "there").split()[0]

        tpl = _TEMPLATES[template_id]
        subject = tpl["subject"].format(company=company)
        body = tpl["body"].format(
            first_name=first_name,
            company=company,
            function=function,
            signer=signer,
        )

        draft = OutreachDraft(
            tenant_id=self.context.tenant_id,
            contact_id=contact.id,
            channel=channel,
            subject=subject,
            body=body,
            status="DRAFT",
            template_id=template_id,
        )
        self._db.add(draft)
        await self._db.flush()

        logger.info(
            "marketing_agent.author_outreach",
            contact_id=str(contact.id),
            draft_id=str(draft.id),
            template=template_id,
        )

        # Border Agent emit: Sales.proposal_sent so Legal + Finance +
        # Daena see the draft activity in their feeds. Draft status stays
        # DRAFT -- the send itself is gated by the approval queue.
        try:
            from app.services.departments.border_agent import (
                DepartmentEvent,
                get_border_agent,
            )
            ba = await get_border_agent(
                tenant_id=self.context.tenant_id, department="Marketing",
            )
            await ba.emit(
                DepartmentEvent.PROPOSAL_SENT,
                payload={
                    "draft_id": str(draft.id),
                    "contact_id": str(contact.id),
                    "channel": channel,
                    "template_id": template_id,
                    "status": "DRAFT",
                    "note": "Draft authored; awaiting approval before send",
                },
            )
        except Exception as exc:
            logger.debug("marketing_agent.border_emit_draft_failed", error=str(exc))

        return {
            "draft_id": str(draft.id),
            "contact_id": str(contact.id),
            "channel": channel,
            "subject": subject,
            "body": body,
            "status": "DRAFT",
            "template_id": template_id,
        }

    @staticmethod
    def _function_for_title(title: str) -> str:
        """Best-guess functional area for template personalization."""
        t = title.lower()
        if "security" in t or "compliance" in t or "risk" in t:
            return "security"
        if "engineer" in t or "platform" in t or "devops" in t:
            return "engineering"
        if "legal" in t or "counsel" in t:
            return "legal"
        if "finance" in t or "cfo" in t:
            return "finance"
        return "operations"


def create_marketing_agent(
    *,
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    governance_mode: str = "BALANCED",
) -> MarketingAgent:
    """Factory for the specialized Marketing agent."""
    ctx = DepartmentContext(
        department="Marketing",
        tenant_id=tenant_id,
        user_id=user_id,
        governance_mode=governance_mode,
    )
    return MarketingAgent(context=ctx, db=db)
