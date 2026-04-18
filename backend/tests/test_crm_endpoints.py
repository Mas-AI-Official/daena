"""CRM read-endpoint tests. Pins Phase H.4 CRM view data source.

Checks that /api/v1/crm/* endpoints return tenant-scoped rows
produced by the SalesAgent + MarketingAgent pipeline.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient) -> dict:
    unique = uuid.uuid4().hex[:8]
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"crm-{unique}@example.com",
            "password": "SecurePass123!",
            "display_name": "CRM Tester",
            "tenant_name": f"CrmOrg-{unique}",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": f"crm-{unique}@example.com", "password": "SecurePass123!"},
    )
    data = login.json()["data"]
    return {"headers": {"Authorization": f"Bearer {data['access_token']}"}}


@pytest.mark.asyncio
async def test_crm_endpoints_empty_for_new_tenant(client: AsyncClient) -> None:
    auth = await _register(client)
    for path in ("/api/v1/crm/accounts", "/api/v1/crm/contacts",
                 "/api/v1/crm/deals", "/api/v1/crm/outreach-drafts"):
        resp = await client.get(path, headers=auth["headers"])
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_crm_endpoints_return_sales_agent_output(client: AsyncClient) -> None:
    """Prospect via /sales/prospect, then fetch via /crm/*."""
    auth = await _register(client)

    prospect_resp = await client.post(
        "/api/v1/sales/prospect",
        json={"icp_description": "Mid-market fintech SOC 2 gap", "limit": 3},
        headers=auth["headers"],
    )
    assert prospect_resp.status_code == 201
    contacts_created = prospect_resp.json()["data"]
    assert len(contacts_created) == 3

    accounts_resp = await client.get("/api/v1/crm/accounts", headers=auth["headers"])
    assert accounts_resp.status_code == 200
    accounts = accounts_resp.json()["data"]
    assert len(accounts) == 1

    contacts_resp = await client.get("/api/v1/crm/contacts", headers=auth["headers"])
    assert contacts_resp.status_code == 200
    contacts = contacts_resp.json()["data"]
    assert len(contacts) == 3
    assert all(c["stage"] == "NEW" for c in contacts)

    # Filter by stage -- NEW returns all, QUALIFIED returns none yet.
    new_resp = await client.get(
        "/api/v1/crm/contacts?stage=NEW", headers=auth["headers"],
    )
    assert len(new_resp.json()["data"]) == 3
    qualified_resp = await client.get(
        "/api/v1/crm/contacts?stage=QUALIFIED", headers=auth["headers"],
    )
    assert len(qualified_resp.json()["data"]) == 0


@pytest.mark.asyncio
async def test_crm_draft_listing_reflects_marketing_agent_output(client: AsyncClient) -> None:
    auth = await _register(client)
    prospect = await client.post(
        "/api/v1/sales/prospect",
        json={"icp_description": "Test", "limit": 1},
        headers=auth["headers"],
    )
    contact_id = prospect.json()["data"][0]["contact_id"]

    draft_resp = await client.post(
        "/api/v1/marketing/author-outreach",
        json={"contact_id": contact_id},
        headers=auth["headers"],
    )
    assert draft_resp.status_code == 201

    list_resp = await client.get("/api/v1/crm/outreach-drafts", headers=auth["headers"])
    assert list_resp.status_code == 200
    drafts = list_resp.json()["data"]
    assert len(drafts) == 1
    assert drafts[0]["status"] == "DRAFT"

    # Filter by status
    draft_only = await client.get(
        "/api/v1/crm/outreach-drafts?status_filter=DRAFT",
        headers=auth["headers"],
    )
    assert len(draft_only.json()["data"]) == 1
    sent_only = await client.get(
        "/api/v1/crm/outreach-drafts?status_filter=SENT",
        headers=auth["headers"],
    )
    assert len(sent_only.json()["data"]) == 0


@pytest.mark.asyncio
async def test_crm_endpoints_tenant_isolated(client: AsyncClient) -> None:
    auth_a = await _register(client)
    auth_b = await _register(client)

    await client.post(
        "/api/v1/sales/prospect",
        json={"icp_description": "Tenant A", "limit": 2},
        headers=auth_a["headers"],
    )

    # Tenant B should see zero.
    b_contacts = await client.get("/api/v1/crm/contacts", headers=auth_b["headers"])
    assert b_contacts.json()["data"] == []
    b_accounts = await client.get("/api/v1/crm/accounts", headers=auth_b["headers"])
    assert b_accounts.json()["data"] == []
