"""Agent-ops REST endpoints: Sales + Marketing department actions.

Phase H of Roadmap V2. Surfaces the SalesAgent and MarketingAgent to
the frontend so a human operator (or Autopilot) can trigger prospect
discovery, qualification, and outreach drafting.

All writes persist through the CRM tables (Account, Contact,
OutreachDraft) and all actions get tenant-scoped by the agent
factories. Drafts land in ``DRAFT`` status so the existing governance
pipeline + Sidebar approval badge can gate sends.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.execution import Task
from app.services.approval import ApprovalService
from app.services.audit import AuditService
from app.services.departments.marketing_agent import create_marketing_agent
from app.services.departments.sales_agent import create_sales_agent

logger = get_logger(__name__)

sales_router = APIRouter()
marketing_router = APIRouter()
crm_router = APIRouter()


# ── Sales endpoints ──────────────────────────────────────────────


class ProspectRequest(BaseModel):
    """Body for POST /sales/prospect."""

    icp_description: str = Field(..., min_length=3, max_length=2000)
    limit: int = Field(default=5, ge=1, le=25)
    seed_company: str | None = None


class CustomerAcquisitionWorkflowRequest(BaseModel):
    """Draft-only MAS-AI customer acquisition workflow.

    Creates a deterministic dev-safe prospect, qualifies it, drafts an
    email, creates a follow-up task, opens an approval request, and logs
    an audit entry. It never sends email or touches external platforms.
    """

    icp_description: str = Field(..., min_length=3, max_length=2000)
    limit: int = Field(default=3, ge=1, le=10)
    seed_company: str | None = None
    signer: str = Field(default="Masoud", min_length=1, max_length=80)
    template_id: str = Field(default="email_cold_v1", min_length=1, max_length=100)


@sales_router.post("/prospect", status_code=status.HTTP_201_CREATED)
async def prospect(
    body: ProspectRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Build a prospect list from an ICP description."""
    agent = create_sales_agent(
        db=db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        governance_mode=getattr(user, "governance_mode", "BALANCED"),
    )
    try:
        contacts = await agent.prospect(
            icp_description=body.icp_description,
            limit=body.limit,
            seed_company=body.seed_company,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    return {"success": True, "data": contacts}


@sales_router.post(
    "/customer-acquisition/draft-workflow",
    status_code=status.HTTP_201_CREATED,
)
async def run_customer_acquisition_draft_workflow(
    body: CustomerAcquisitionWorkflowRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run the core founder demo workflow without external sends.

    Flow:
    1. Sales creates lead/contact rows from ICP.
    2. Sales qualifies the top contact.
    3. Marketing drafts outreach in ``DRAFT`` status.
    4. Execution creates a follow-up task.
    5. Governance creates an approval request for the send step.
    6. Audit logs the workflow as ``APPROVAL_REQUIRED``.

    This endpoint is deliberately draft-only: it does not send email,
    submit forms, scrape restricted platforms, or scan third-party
    systems. The approval request is for a future external send action.
    """
    sales = create_sales_agent(
        db=db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        governance_mode=getattr(user, "governance_mode", "BALANCED"),
    )
    marketing = create_marketing_agent(
        db=db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        governance_mode=getattr(user, "governance_mode", "BALANCED"),
    )
    approvals = ApprovalService(db)
    audit = AuditService(db)

    try:
        contacts = await sales.prospect(
            icp_description=body.icp_description,
            limit=body.limit,
            seed_company=body.seed_company,
        )
        if not contacts:
            raise HTTPException(
                status_code=500,
                detail="Sales agent produced no contacts for the requested ICP.",
            )

        top_contact = contacts[0]
        qualification = await sales.qualify(top_contact["contact_id"])
        draft = await marketing.author_outreach(
            contact_id=top_contact["contact_id"],
            template_id=body.template_id,
            channel="email",
            signer=body.signer,
        )

        task_row = Task(
            name=f"Follow up with {top_contact['full_name']}",
            description=(
                "Draft-only customer acquisition workflow. Review the "
                f"outreach draft {draft['draft_id']} and decide from the "
                "approval queue before any external send."
            ),
            user_id=user.id,
            tenant_id=user.tenant_id,
            session_id=None,
            status="PENDING",
            progress=0,
        )
        db.add(task_row)
        await db.flush()
        task = {
            "id": str(task_row.id),
            "user_id": str(task_row.user_id),
            "tenant_id": str(task_row.tenant_id),
            "session_id": None,
            "name": task_row.name,
            "description": task_row.description,
            "status": task_row.status,
            "progress": task_row.progress,
            "result": task_row.result,
            "error": task_row.error,
            "checkpoint_data": task_row.checkpoint_data,
            "started_at": None,
            "completed_at": None,
            "created_at": task_row.created_at.isoformat() if task_row.created_at else None,
            "updated_at": task_row.updated_at.isoformat() if task_row.updated_at else None,
        }

        approval = await approvals.request_approval(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action_type="SEND_EXTERNAL_OUTREACH_DRAFT",
            action_params={
                "draft_id": draft["draft_id"],
                "contact_id": draft["contact_id"],
                "channel": draft["channel"],
                "subject": draft["subject"],
                "external_action_sent": False,
                "requires_founder_approval": True,
            },
            risk_level="HIGH",
            governance_tier=3,
            session_id=None,
            context={
                "workflow": "customer_acquisition_draft",
                "company": body.seed_company,
                "icp_description": body.icp_description,
                "task_id": task["id"],
                "draft_id": draft["draft_id"],
                "no_external_send": True,
            },
        )

        await audit.log_decision(
            tenant_id=user.tenant_id,
            actor_id=user.id,
            actor_type="FOUNDER",
            action_type="CUSTOMER_ACQUISITION_DRAFT_WORKFLOW",
            action_params={
                "icp_description": body.icp_description,
                "contact_id": top_contact["contact_id"],
                "draft_id": draft["draft_id"],
                "approval_id": approval["id"],
                "task_id": task["id"],
                "external_action_sent": False,
            },
            result="APPROVAL_REQUIRED",
            risk_level="HIGH",
            governance_tier=3,
            session_id=None,
        )
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "success": True,
        "data": {
            "mode": "draft_only",
            "external_action_sent": False,
            "requires_founder_approval": True,
            "steps": [
                "identified_icp",
                "created_lead_research_task",
                "created_crm_contacts",
                "qualified_top_contact",
                "drafted_outreach",
                "created_follow_up_task",
                "created_approval_request",
                "logged_audit_trail",
            ],
            "contacts": contacts,
            "qualified_contact": qualification,
            "outreach_draft": draft,
            "follow_up_task": task,
            "approval_request": approval,
        },
    }


class QualifyRequest(BaseModel):
    contact_id: str


@sales_router.post("/qualify")
async def qualify(
    body: QualifyRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Score a contact against ICP and update its stage."""
    agent = create_sales_agent(
        db=db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        governance_mode=getattr(user, "governance_mode", "BALANCED"),
    )
    try:
        result = await agent.qualify(body.contact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    return {"success": True, "data": result}


# ── Marketing endpoints ──────────────────────────────────────────


class AuthorOutreachRequest(BaseModel):
    contact_id: str
    template_id: str = Field(default="email_cold_v1")
    channel: str = Field(default="email")
    signer: str = Field(default="Masoud")


# ── CRM read endpoints (PipelinePage data source) ───────────────


@crm_router.get("/accounts")
async def list_accounts(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return all Accounts for the tenant, newest first."""
    from sqlalchemy import desc, select
    from app.models.crm import Account

    result = await db.execute(
        select(Account).where(Account.tenant_id == user.tenant_id)
        .order_by(desc(Account.created_at)).limit(200)
    )
    accounts = [
        {
            "id": str(a.id),
            "name": a.name,
            "domain": a.domain,
            "industry": a.industry,
            "employee_count": a.employee_count,
            "icp_score": float(a.icp_score) if a.icp_score is not None else None,
            "source_icp": a.source_icp,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in result.scalars().all()
    ]
    return {"success": True, "data": accounts}


@crm_router.get("/contacts")
async def list_contacts(
    stage: str | None = None,
    account_id: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return Contacts for the tenant. Filter by stage and/or account_id."""
    from uuid import UUID
    from sqlalchemy import desc, select
    from app.models.crm import Contact

    stmt = select(Contact).where(Contact.tenant_id == user.tenant_id)
    if stage:
        stmt = stmt.where(Contact.stage == stage.upper())
    if account_id:
        try:
            stmt = stmt.where(Contact.account_id == UUID(account_id))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid account_id") from exc
    stmt = stmt.order_by(desc(Contact.created_at)).limit(500)
    result = await db.execute(stmt)
    contacts = [
        {
            "id": str(c.id),
            "account_id": str(c.account_id) if c.account_id else None,
            "full_name": c.full_name,
            "title": c.title,
            "email": c.email,
            "stage": c.stage,
            "source": c.source,
            "last_touched_at": c.last_touched_at.isoformat() if c.last_touched_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in result.scalars().all()
    ]
    return {"success": True, "data": contacts}


@crm_router.get("/deals")
async def list_deals(
    stage: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return Deals for the tenant, optionally filtered by stage."""
    from sqlalchemy import desc, select
    from app.models.crm import Deal

    stmt = select(Deal).where(Deal.tenant_id == user.tenant_id)
    if stage:
        stmt = stmt.where(Deal.stage == stage.upper())
    stmt = stmt.order_by(desc(Deal.created_at)).limit(200)
    result = await db.execute(stmt)
    deals = [
        {
            "id": str(d.id),
            "account_id": str(d.account_id),
            "primary_contact_id": str(d.primary_contact_id) if d.primary_contact_id else None,
            "name": d.name,
            "stage": d.stage,
            "amount_usd": float(d.amount_usd) if d.amount_usd is not None else None,
            "close_date": d.close_date.isoformat() if d.close_date else None,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in result.scalars().all()
    ]
    return {"success": True, "data": deals}


@crm_router.get("/outreach-drafts")
async def list_outreach_drafts(
    status_filter: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return OutreachDrafts. Filter by status (DRAFT | APPROVED | SENT ...)."""
    from sqlalchemy import desc, select
    from app.models.crm import OutreachDraft

    stmt = select(OutreachDraft).where(OutreachDraft.tenant_id == user.tenant_id)
    if status_filter:
        stmt = stmt.where(OutreachDraft.status == status_filter.upper())
    stmt = stmt.order_by(desc(OutreachDraft.created_at)).limit(300)
    result = await db.execute(stmt)
    drafts = [
        {
            "id": str(d.id),
            "contact_id": str(d.contact_id),
            "channel": d.channel,
            "subject": d.subject,
            "body": d.body,
            "status": d.status,
            "template_id": d.template_id,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in result.scalars().all()
    ]
    return {"success": True, "data": drafts}


@marketing_router.post("/author-outreach", status_code=status.HTTP_201_CREATED)
async def author_outreach(
    body: AuthorOutreachRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Author an outreach draft grounded in the Contact record."""
    agent = create_marketing_agent(
        db=db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        governance_mode=getattr(user, "governance_mode", "BALANCED"),
    )
    try:
        result = await agent.author_outreach(
            contact_id=body.contact_id,
            template_id=body.template_id,
            channel=body.channel,
            signer=body.signer,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    return {"success": True, "data": result}
