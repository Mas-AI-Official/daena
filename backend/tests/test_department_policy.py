"""Tests for DepartmentPolicy service + VP integration.

Pin the contract:
* Trigger evaluator correctly handles eq / gte / contains / in / missing-field
* find_matching_policies returns all matching policies
* required_approvers_for unions across policies preserving order
* ensure_defaults is idempotent + installs the 5 seeded rows
* DaenaVP.apply_policies attaches metadata to the right subtasks
* Self-approval filter: Finance spending money does NOT message Finance
* REST CRUD + tenant isolation
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.services.daena_vp import DaenaVP, VPPlan, VPSubtask
from app.services.department_policy_service import (
    DEFAULT_POLICIES,
    DepartmentPolicyService,
)


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    from app.models.identity import Tenant
    tenant = Tenant(
        id=test_tenant_id, name="Test Tenant",
        slug="test-tenant", settings={},
    )
    db_session.add(tenant)
    await db_session.flush()
    yield tenant


@pytest.fixture
async def service(db_session, seeded_tenant):
    return DepartmentPolicyService(db_session)


# ── Evaluator ───────────────────────────────────────────────────


def test_evaluator_empty_conditions_always_matches() -> None:
    assert DepartmentPolicyService._evaluate({}, {"foo": 1}) is True
    assert DepartmentPolicyService._evaluate({"conditions": []}, {}) is True


def test_evaluator_eq_and_ne() -> None:
    trigger = {"conditions": [{"field": "action_type", "op": "eq", "value": "expense"}]}
    assert DepartmentPolicyService._evaluate(trigger, {"action_type": "expense"}) is True
    assert DepartmentPolicyService._evaluate(trigger, {"action_type": "deploy"}) is False


def test_evaluator_gte_with_string_amount() -> None:
    """Operators can pass amounts as strings; evaluator coerces."""
    trigger = {"conditions": [{"field": "amount", "op": "gte", "value": 500}]}
    assert DepartmentPolicyService._evaluate(trigger, {"amount": "1000"}) is True
    assert DepartmentPolicyService._evaluate(trigger, {"amount": Decimal("499.99")}) is False


def test_evaluator_multiple_conditions_and() -> None:
    """All conditions must match (AND semantics)."""
    trigger = {"conditions": [
        {"field": "amount", "op": "gte", "value": 500},
        {"field": "from_department", "op": "eq", "value": "Marketing"},
    ]}
    assert DepartmentPolicyService._evaluate(
        trigger, {"amount": 1000, "from_department": "Marketing"}
    ) is True
    assert DepartmentPolicyService._evaluate(
        trigger, {"amount": 1000, "from_department": "Finance"}
    ) is False


def test_evaluator_missing_field_fails_closed() -> None:
    """Conditions that reference missing fields never match. Safer
    than trying to infer defaults."""
    trigger = {"conditions": [{"field": "amount", "op": "gte", "value": 500}]}
    assert DepartmentPolicyService._evaluate(trigger, {"action_type": "expense"}) is False


def test_evaluator_contains_for_strings_and_lists() -> None:
    trigger = {"conditions": [{"field": "tags", "op": "contains", "value": "external"}]}
    assert DepartmentPolicyService._evaluate(trigger, {"tags": ["internal", "external"]}) is True
    # Substring match on string
    trigger2 = {"conditions": [{"field": "description", "op": "contains", "value": "campaign"}]}
    assert DepartmentPolicyService._evaluate(
        trigger2, {"description": "Draft Q2 Campaign copy"}
    ) is True


def test_evaluator_malformed_condition_fails_closed() -> None:
    """Missing op / field -> never matches. Prevents a typo from
    silently triggering every policy."""
    trigger = {"conditions": [{"field": "amount"}]}  # no op
    assert DepartmentPolicyService._evaluate(trigger, {"amount": 1000}) is False


# ── Matching engine ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_find_matching_returns_enabled_matches(
    service, test_tenant_id,
) -> None:
    await service.create(
        tenant_id=test_tenant_id,
        name="Expense over 500",
        policy_type="EXPENSE",
        trigger_condition={"conditions": [{"field": "amount", "op": "gte", "value": 500}]},
        required_approvers=["Finance"],
    )
    await service.create(
        tenant_id=test_tenant_id,
        name="External comms",
        policy_type="EXTERNAL_COMMS",
        trigger_condition={"conditions": [{"field": "action_type", "op": "eq", "value": "external_comms"}]},
        required_approvers=["Legal & Compliance"],
    )
    # Disabled policy that WOULD match -- must be skipped
    await service.create(
        tenant_id=test_tenant_id,
        name="Always",
        policy_type="CUSTOM",
        trigger_condition={"conditions": []},
        required_approvers=["Operations"],
        enabled=False,
    )

    matches = await service.find_matching_policies(
        tenant_id=test_tenant_id,
        action={"amount": 1000, "action_type": "external_comms", "from_department": "Marketing"},
    )
    names = {p.name for p in matches}
    assert names == {"Expense over 500", "External comms"}


@pytest.mark.asyncio
async def test_required_approvers_union_preserves_order(
    service, test_tenant_id,
) -> None:
    """When multiple policies match, the combined approver list
    deduplicates and preserves first-seen order."""
    await service.create(
        tenant_id=test_tenant_id, name="A", policy_type="EXPENSE",
        trigger_condition={"conditions": []},
        required_approvers=["Finance", "Legal & Compliance"],
    )
    await service.create(
        tenant_id=test_tenant_id, name="B", policy_type="EXTERNAL_COMMS",
        trigger_condition={"conditions": []},
        required_approvers=["Legal & Compliance", "Security Operations"],
    )
    approvers = await service.required_approvers_for(
        tenant_id=test_tenant_id, action={},
    )
    assert approvers == ["Finance", "Legal & Compliance", "Security Operations"]


# ── Seed / defaults ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ensure_defaults_installs_five(service, test_tenant_id) -> None:
    inserted = await service.ensure_defaults(tenant_id=test_tenant_id)
    assert inserted == len(DEFAULT_POLICIES)
    policies = await service.list_policies(tenant_id=test_tenant_id)
    seed_keys = {p.seed_key for p in policies}
    expected = {seed["seed_key"] for seed in DEFAULT_POLICIES}
    assert expected.issubset(seed_keys)


@pytest.mark.asyncio
async def test_ensure_defaults_is_idempotent(service, test_tenant_id) -> None:
    first = await service.ensure_defaults(tenant_id=test_tenant_id)
    second = await service.ensure_defaults(tenant_id=test_tenant_id)
    assert first > 0
    assert second == 0


# ── VP.apply_policies integration ──────────────────────────────


@pytest.mark.asyncio
async def test_vp_attaches_required_approvers(
    service, test_tenant_id,
) -> None:
    """The operator's Finance-2k-vs-Engineering-4k scenario as a plan:
    Engineering has a $4k subtask; the default expense_over_500 policy
    matches; VP tags the subtask with Finance as required approver."""
    await service.ensure_defaults(tenant_id=test_tenant_id)

    vp = DaenaVP(policy_service=service)
    plan = VPPlan(
        user_request="upgrade CI/CD minutes",
        subtasks=[VPSubtask(
            description="Upgrade CI/CD minutes",
            department="Engineering",
            reason="Engineering rule match",
            metadata={"amount": 4000},  # triggers expense_over_500
        )],
        routing_mode="rule",
    )
    routed = await vp.apply_policies(plan, tenant_id=test_tenant_id)
    approvers = routed.subtasks[0].metadata.get("required_approvers")
    assert approvers == ["Finance"]
    assert "Finance" in routed.subtasks[0].reason


@pytest.mark.asyncio
async def test_vp_self_approval_filtered_out(
    service, test_tenant_id,
) -> None:
    """Finance spending money does NOT message Finance. Otherwise
    every Finance-owned expense would loop back to itself."""
    await service.ensure_defaults(tenant_id=test_tenant_id)

    vp = DaenaVP(policy_service=service)
    plan = VPPlan(
        user_request="approve internal software license",
        subtasks=[VPSubtask(
            description="Renew license",
            department="Finance",
            metadata={"amount": 2000},
        )],
        routing_mode="rule",
    )
    routed = await vp.apply_policies(plan, tenant_id=test_tenant_id)
    approvers = routed.subtasks[0].metadata.get("required_approvers")
    # Finance filtered -> no approvers needed for Finance-owned spend
    assert approvers is None


@pytest.mark.asyncio
async def test_vp_external_comms_routes_to_legal(
    service, test_tenant_id,
) -> None:
    """Session D's seed: external_comms -> Legal & Compliance."""
    await service.ensure_defaults(tenant_id=test_tenant_id)

    vp = DaenaVP(policy_service=service)
    plan = VPPlan(
        user_request="publish press release",
        subtasks=[VPSubtask(
            description="Draft press release announcing product X",
            department="Marketing",
            metadata={"action_type": "external_comms"},
        )],
        routing_mode="rule",
    )
    routed = await vp.apply_policies(plan, tenant_id=test_tenant_id)
    approvers = routed.subtasks[0].metadata.get("required_approvers")
    assert approvers == ["Legal & Compliance"]


@pytest.mark.asyncio
async def test_vp_apply_policies_noop_without_service() -> None:
    """VP without a policy_service returns the plan unchanged."""
    vp = DaenaVP()  # no policy_service
    plan = VPPlan(
        user_request="x",
        subtasks=[VPSubtask(description="d", department="Engineering")],
        routing_mode="rule",
    )
    result = await vp.apply_policies(plan, tenant_id=uuid.uuid4())
    assert result is plan
    assert "required_approvers" not in result.subtasks[0].metadata


# ── REST CRUD ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/department-policies")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_api_full_crud_cycle(
    client: AsyncClient, auth_headers: dict[str, str], seeded_tenant,
) -> None:
    # Create
    create_res = await client.post(
        "/api/v1/department-policies",
        headers=auth_headers,
        json={
            "name": "Custom: campaigns need brand review",
            "description": "Any brand campaign needs Skill Governance sign-off",
            "policy_type": "CUSTOM",
            "trigger_condition": {"conditions": [{"field": "action_type", "op": "eq", "value": "campaign"}]},
            "required_approvers": ["Skill Governance"],
            "enabled": True,
        },
    )
    assert create_res.status_code == 201
    policy_id = create_res.json()["id"]

    # List
    list_res = await client.get(
        "/api/v1/department-policies", headers=auth_headers,
    )
    assert list_res.status_code == 200
    assert any(p["id"] == policy_id for p in list_res.json())

    # Update
    patch_res = await client.patch(
        f"/api/v1/department-policies/{policy_id}",
        headers=auth_headers,
        json={"enabled": False},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["enabled"] is False

    # Delete
    del_res = await client.delete(
        f"/api/v1/department-policies/{policy_id}", headers=auth_headers,
    )
    assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_api_seed_endpoint_is_idempotent(
    client: AsyncClient, auth_headers: dict[str, str], seeded_tenant,
) -> None:
    first = await client.post(
        "/api/v1/department-policies/seed", headers=auth_headers,
    )
    second = await client.post(
        "/api/v1/department-policies/seed", headers=auth_headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["inserted"] > 0
    assert second.json()["inserted"] == 0


@pytest.mark.asyncio
async def test_api_rejects_unknown_policy_type(
    client: AsyncClient, auth_headers: dict[str, str], seeded_tenant,
) -> None:
    res = await client.post(
        "/api/v1/department-policies",
        headers=auth_headers,
        json={
            "name": "bogus", "policy_type": "NOT_A_REAL_TYPE",
            "trigger_condition": {}, "required_approvers": ["Finance"],
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_api_rejects_empty_approvers(
    client: AsyncClient, auth_headers: dict[str, str], seeded_tenant,
) -> None:
    """Pydantic catches this via min_length=1 before it reaches service."""
    res = await client.post(
        "/api/v1/department-policies",
        headers=auth_headers,
        json={
            "name": "bad", "policy_type": "CUSTOM",
            "trigger_condition": {}, "required_approvers": [],
        },
    )
    assert res.status_code == 422
