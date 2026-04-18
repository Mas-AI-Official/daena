"""Integration tests for SalesAgent + MarketingAgent (Phase H).

Proves the end-to-end flow Masoud asked for: agents find customers,
qualify them, author outreach, and everything lands in the CRM tables
so the PipelinePage and Approvals flow can render + gate sends.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.crm import Account, Contact, OutreachDraft
from app.models.identity import Tenant, User
from app.services.departments.marketing_agent import create_marketing_agent
from app.services.departments.sales_agent import create_sales_agent


async def _seed_tenant_and_user(db) -> tuple[uuid.UUID, uuid.UUID]:
    """Minimum rows for the agents to operate."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="AgentOpsOrg",
        slug=f"aops-{uuid.uuid4().hex[:6]}",
    )
    db.add(tenant)
    await db.flush()
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=f"ops-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Agent Ops Tester",
        password_hash="unused",
        role="OPERATOR",
    )
    db.add(user)
    await db.flush()
    return tenant.id, user.id


# ── SalesAgent.prospect ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_prospect_creates_account_and_contacts(db_session) -> None:
    """Happy path: prospect() persists exactly one Account + N Contacts."""
    tenant_id, user_id = await _seed_tenant_and_user(db_session)
    agent = create_sales_agent(
        db=db_session, tenant_id=tenant_id, user_id=user_id,
    )
    result = await agent.prospect(
        icp_description="Mid-market fintech with SOC 2 gap",
        limit=3,
    )
    assert len(result) == 3
    assert all(r["stage"] == "NEW" for r in result)

    accounts = (await db_session.execute(
        select(Account).where(Account.tenant_id == tenant_id)
    )).scalars().all()
    contacts = (await db_session.execute(
        select(Contact).where(Contact.tenant_id == tenant_id)
    )).scalars().all()
    assert len(accounts) == 1
    assert len(contacts) == 3
    # Contacts must all point at the single Account.
    assert all(c.account_id == accounts[0].id for c in contacts)


@pytest.mark.asyncio
async def test_prospect_reuses_existing_account_for_same_company(db_session) -> None:
    """A second prospect call against the same derived company name
    reuses the Account row -- no duplicates."""
    tenant_id, user_id = await _seed_tenant_and_user(db_session)
    agent = create_sales_agent(db=db_session, tenant_id=tenant_id, user_id=user_id)

    await agent.prospect(icp_description="Mid-market fintech", limit=2, seed_company="Acme Corp")
    await agent.prospect(icp_description="Different angle", limit=2, seed_company="Acme Corp")

    accounts = (await db_session.execute(
        select(Account).where(
            Account.tenant_id == tenant_id,
            Account.name == "Acme Corp",
        )
    )).scalars().all()
    assert len(accounts) == 1  # not duplicated


@pytest.mark.asyncio
async def test_prospect_rejects_empty_icp(db_session) -> None:
    tenant_id, user_id = await _seed_tenant_and_user(db_session)
    agent = create_sales_agent(db=db_session, tenant_id=tenant_id, user_id=user_id)
    with pytest.raises(ValueError):
        await agent.prospect(icp_description="  ", limit=1)


# ── SalesAgent.qualify ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_qualify_advances_executive_to_qualified(db_session) -> None:
    """Executive seniority should score >= 0.6 and advance to QUALIFIED."""
    tenant_id, user_id = await _seed_tenant_and_user(db_session)
    agent = create_sales_agent(db=db_session, tenant_id=tenant_id, user_id=user_id)
    contacts = await agent.prospect(icp_description="test", limit=5)
    # The first persona template is executive seniority.
    executive_contact = contacts[0]

    result = await agent.qualify(executive_contact["contact_id"])
    assert result["score"] >= 0.6
    assert result["stage"] == "QUALIFIED"


@pytest.mark.asyncio
async def test_qualify_unknown_contact_raises_keyerror(db_session) -> None:
    tenant_id, user_id = await _seed_tenant_and_user(db_session)
    agent = create_sales_agent(db=db_session, tenant_id=tenant_id, user_id=user_id)
    with pytest.raises(KeyError):
        await agent.qualify(uuid.uuid4())


@pytest.mark.asyncio
async def test_qualify_enforces_tenant_isolation(db_session) -> None:
    """Qualifying a contact from another tenant must raise KeyError."""
    tenant_a, user_a = await _seed_tenant_and_user(db_session)
    tenant_b, user_b = await _seed_tenant_and_user(db_session)

    agent_a = create_sales_agent(db=db_session, tenant_id=tenant_a, user_id=user_a)
    contacts_a = await agent_a.prospect(icp_description="a", limit=1)

    agent_b = create_sales_agent(db=db_session, tenant_id=tenant_b, user_id=user_b)
    with pytest.raises(KeyError):
        await agent_b.qualify(contacts_a[0]["contact_id"])


# ── MarketingAgent.author_outreach ───────────────────────────────


@pytest.mark.asyncio
async def test_author_outreach_creates_draft_in_draft_status(db_session) -> None:
    """Drafts must land in DRAFT so the approval flow can gate sends."""
    tenant_id, user_id = await _seed_tenant_and_user(db_session)

    sales = create_sales_agent(db=db_session, tenant_id=tenant_id, user_id=user_id)
    contacts = await sales.prospect(icp_description="test", limit=1)

    marketing = create_marketing_agent(
        db=db_session, tenant_id=tenant_id, user_id=user_id,
    )
    draft_result = await marketing.author_outreach(
        contact_id=contacts[0]["contact_id"],
    )
    assert draft_result["status"] == "DRAFT"
    assert "subject" in draft_result
    assert contacts[0]["full_name"].split()[0] in draft_result["body"]

    drafts = (await db_session.execute(
        select(OutreachDraft).where(OutreachDraft.tenant_id == tenant_id)
    )).scalars().all()
    assert len(drafts) == 1
    assert drafts[0].status == "DRAFT"
    assert drafts[0].channel == "email"


@pytest.mark.asyncio
async def test_author_outreach_rejects_unknown_template(db_session) -> None:
    tenant_id, user_id = await _seed_tenant_and_user(db_session)
    sales = create_sales_agent(db=db_session, tenant_id=tenant_id, user_id=user_id)
    contacts = await sales.prospect(icp_description="t", limit=1)

    marketing = create_marketing_agent(
        db=db_session, tenant_id=tenant_id, user_id=user_id,
    )
    with pytest.raises(ValueError):
        await marketing.author_outreach(
            contact_id=contacts[0]["contact_id"],
            template_id="does_not_exist",
        )


@pytest.mark.asyncio
async def test_author_outreach_enforces_tenant_isolation(db_session) -> None:
    tenant_a, user_a = await _seed_tenant_and_user(db_session)
    tenant_b, user_b = await _seed_tenant_and_user(db_session)

    sales_a = create_sales_agent(db=db_session, tenant_id=tenant_a, user_id=user_a)
    contacts_a = await sales_a.prospect(icp_description="a", limit=1)

    marketing_b = create_marketing_agent(
        db=db_session, tenant_id=tenant_b, user_id=user_b,
    )
    with pytest.raises(KeyError):
        await marketing_b.author_outreach(contact_id=contacts_a[0]["contact_id"])
