"""PR-SCAN-ADD-TO-SCOPE-INLINE-CTA (Sprint-9 PR-1).

Pins the contract of the founder-only ``POST /api/v1/security/
authorized-scope/add`` endpoint that backs the /scan page's
"Add this target to Scan Scope" CTA.

Hard rules from the brief:

  1. Non-founder roles cannot call the add endpoint (require_role
     gate is enforced server-side; clients can't bypass).
  2. Founder can add an exact host from a URL target.
  3. Wildcard is NEVER the default. ``scope_type`` defaults to
     ``exact_url`` (host-only).
  4. Scan is still blocked BEFORE the scope add (sanity that PR-1
     never weakens the existing target_matches_scope gate).
  5. Scan is allowed AFTER the scope add (proves the gate now sees
     the freshly-appended entry on the very next call -- no caching
     stale state).
  6. The add endpoint NEVER auto-runs a scan. Each test path that
     adds a target must explicitly post to /scans/start to trigger
     dispatch (or assert the previous 403 cleared, in our case).
  7. Audit row uses action_type="security.scope.added_from_scan"
     and never includes secrets.
  8. Wildcard rejected for non-domain targets (IP, repo path).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.governance import GoaAuditEvent
from app.services.security.yellow_runtime_gate import (
    AuthorizedScope,
    _SCOPES_JSON_PATH,
    target_matches_scope,
)


pytestmark = pytest.mark.asyncio


@pytest.fixture
def isolated_scopes_path(monkeypatch, tmp_path: Path) -> Path:
    """Repoint the scope JSON to a tmp file so each test starts empty
    and never touches the operator's real on-disk scope file."""
    fake = tmp_path / "authorized_scopes.json"
    monkeypatch.setattr(
        "app.services.security.yellow_runtime_gate._SCOPES_JSON_PATH",
        fake,
    )
    monkeypatch.setattr(
        "app.api.v1.security_authorized_scope._SCOPES_JSON_PATH",
        fake,
    )
    return fake


# ──────────────────────────────────────────────────────────────────
# 1. Non-founder cannot add (route role gate)
# ──────────────────────────────────────────────────────────────────


async def test_add_endpoint_rejects_non_founder(client: AsyncClient, db_session):
    """A MANAGER-role user must not be able to call the add endpoint.
    The require_role("FOUNDER") dependency is the only gate; this test
    pins that the endpoint is on the founder side of the role line."""
    from app.models.identity import Tenant, User
    from app.core.security import create_access_token
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db_session.add(Tenant(id=tenant_id, name="NF", slug=f"nf-{tenant_id.hex[:6]}"))
    await db_session.flush()
    db_session.add(User(
        id=user_id, tenant_id=tenant_id,
        email=f"{user_id.hex[:6]}@example.com",
        password_hash="$2b$12$dummydummydummydummydummydummydummydummydummydummydu",
        role="MANAGER", email_verified=True,
    ))
    await db_session.flush()
    await db_session.commit()
    token = create_access_token(
        user_id=str(user_id), tenant_id=str(tenant_id), role="MANAGER",
        email=f"{user_id.hex[:6]}@example.com", display_name="NF",
    )
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.post(
        "/api/v1/security/authorized-scope/add",
        headers=headers,
        json={"target": "example.com", "scope_type": "exact_url"},
    )
    assert res.status_code == 403, res.text


# ──────────────────────────────────────────────────────────────────
# 2. Founder can add an exact host from a URL target
# ──────────────────────────────────────────────────────────────────


async def test_founder_can_add_exact_host_from_url(
    client: AsyncClient, auth_headers, isolated_scopes_path,
):
    res = await client.post(
        "/api/v1/security/authorized-scope/add",
        headers=auth_headers,
        json={"target": "https://dashboard.rapyd.net/login", "scope_type": "exact_url"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["bucket"] == "exact_domains"
    # The path component is dropped; only the host is stored.
    assert body["stored_value"] == "dashboard.rapyd.net"
    assert body["already_present"] is False
    assert body["scope_type"] == "exact_url"
    assert "dashboard.rapyd.net" in body["scope"]["exact_domains"]
    assert body["scope"]["has_any_entry"] is True


async def test_founder_add_is_idempotent(
    client: AsyncClient, auth_headers, isolated_scopes_path,
):
    json_body = {"target": "https://dashboard.rapyd.net/login", "scope_type": "exact_url"}
    first = await client.post(
        "/api/v1/security/authorized-scope/add",
        headers=auth_headers, json=json_body,
    )
    second = await client.post(
        "/api/v1/security/authorized-scope/add",
        headers=auth_headers, json=json_body,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["already_present"] is False
    assert second.json()["already_present"] is True
    # Bucket must still contain exactly one entry (no duplicate write).
    raw = json.loads(isolated_scopes_path.read_text(encoding="utf-8"))
    keys = list(raw.keys())
    assert len(keys) == 1
    bucket = raw[keys[0]]["exact_domains"]
    assert bucket.count("dashboard.rapyd.net") == 1


# ──────────────────────────────────────────────────────────────────
# 3. Default is exact_url (NEVER wildcard)
# ──────────────────────────────────────────────────────────────────


async def test_default_scope_type_is_exact_not_wildcard(
    client: AsyncClient, auth_headers, isolated_scopes_path,
):
    """If the request omits scope_type, the server must default to
    exact_url -- not wildcard. Wildcard auth is too broad for a single
    one-click CTA add."""
    res = await client.post(
        "/api/v1/security/authorized-scope/add",
        headers=auth_headers,
        json={"target": "https://api.example.com"},  # no scope_type
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["scope_type"] == "exact_url"
    assert body["bucket"] == "exact_domains"
    # Wildcard list must not have grown.
    assert body["scope"]["wildcard_domains"] == []


async def test_wildcard_subdomain_lands_in_wildcard_bucket(
    client: AsyncClient, auth_headers, isolated_scopes_path,
):
    """If the founder explicitly opts into wildcard, the entry goes
    into the wildcard_domains bucket -- not exact_domains."""
    res = await client.post(
        "/api/v1/security/authorized-scope/add",
        headers=auth_headers,
        json={"target": "https://api.example.com", "scope_type": "wildcard_subdomain"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["bucket"] == "wildcard_domains"
    assert "api.example.com" in body["scope"]["wildcard_domains"]
    # Exact list stays empty; wildcard alone is the founder's intent.
    assert body["scope"]["exact_domains"] == []


# ──────────────────────────────────────────────────────────────────
# 4. Scan still blocked BEFORE add; allowed AFTER add
# ──────────────────────────────────────────────────────────────────


async def test_scan_blocked_before_add_and_allowed_after(
    client: AsyncClient, auth_headers, isolated_scopes_path,
):
    """The brief's pivot test: the gate must continue to block until
    the operator explicitly adds the target via the CTA, and only
    then accept the scan dispatch. Nothing about PR-1 weakens the
    existing target_matches_scope contract."""
    target = "https://acceptance.example.com/dashboard"

    # 1. Gate blocks (empty scope == deny-by-default).
    res_block = await client.post(
        "/api/v1/security/scans/start",
        headers=auth_headers,
        json={"target": target, "tier": "SCOUT"},
    )
    assert res_block.status_code == 403, res_block.text
    assert res_block.json()["detail"]["code"] == "target_not_in_scope"

    # 2. Founder hits the CTA: add the target's host as exact_url.
    res_add = await client.post(
        "/api/v1/security/authorized-scope/add",
        headers=auth_headers,
        json={"target": target, "scope_type": "exact_url"},
    )
    assert res_add.status_code == 200, res_add.text
    assert res_add.json()["bucket"] == "exact_domains"

    # 3. Same scan call now passes the gate. Workflow may still 5xx
    #    in the unit-test environment; what we forbid is the 403
    #    firing again with target_not_in_scope.
    res_after = await client.post(
        "/api/v1/security/scans/start",
        headers=auth_headers,
        json={"target": target, "tier": "SCOUT"},
    )
    if res_after.status_code == 403:
        # Only acceptable if the code is not target_not_in_scope.
        detail = res_after.json().get("detail")
        if isinstance(detail, dict):
            assert detail.get("code") != "target_not_in_scope", res_after.text


async def test_add_does_not_auto_start_a_scan(
    client: AsyncClient, auth_headers, isolated_scopes_path,
):
    """The add endpoint must NEVER cascade into starting a scan.
    Validates by inspecting the response shape: no job_id, no
    scan_dispatched flag, no kind of scan-side surface."""
    res = await client.post(
        "/api/v1/security/authorized-scope/add",
        headers=auth_headers,
        json={"target": "https://noscan.example.com", "scope_type": "exact_url"},
    )
    assert res.status_code == 200
    body = res.json()
    forbidden_keys = {"job_id", "scan_id", "scan", "scan_dispatched", "started_at"}
    assert forbidden_keys.isdisjoint(body.keys()), (
        f"add response leaked scan-side fields: {forbidden_keys & set(body.keys())}"
    )


# ──────────────────────────────────────────────────────────────────
# 5. Audit row written on add
# ──────────────────────────────────────────────────────────────────


async def test_add_writes_audit_row_with_no_secrets(
    client: AsyncClient, auth_headers, db_session, isolated_scopes_path,
    test_tenant_id, test_user_id,
):
    # The auth_headers fixture issues a JWT for (test_tenant_id,
    # test_user_id) but does NOT seed those rows. The audit log's
    # actor_id has a User FK; without seeding, the insert silently
    # fails inside the endpoint's try/except and no row gets written.
    # Seed the prerequisites so the audit path actually completes.
    from sqlalchemy import select
    from app.models.identity import Tenant, User
    if not (await db_session.execute(
        select(Tenant).where(Tenant.id == test_tenant_id)
    )).scalar_one_or_none():
        db_session.add(Tenant(id=test_tenant_id, name="T", slug="t"))
        await db_session.flush()
    if not (await db_session.execute(
        select(User).where(User.id == test_user_id)
    )).scalar_one_or_none():
        db_session.add(User(
            id=test_user_id, tenant_id=test_tenant_id,
            email="t@example.com",
            password_hash="$2b$12$dummydummydummydummydummydummydummydummydummydummydu",
            role="FOUNDER", email_verified=True,
        ))
        await db_session.flush()
    await db_session.commit()

    target = "https://audit.example.com/login"
    res = await client.post(
        "/api/v1/security/authorized-scope/add",
        headers=auth_headers,
        json={"target": target, "scope_type": "exact_url"},
    )
    assert res.status_code == 200

    rows = (
        await db_session.execute(
            select(GoaAuditEvent)
            .where(GoaAuditEvent.tenant_id == test_tenant_id)
            .where(GoaAuditEvent.action_type == "security.scope.added_from_scan"),
        )
    ).scalars().all()
    assert len(rows) >= 1
    row = rows[-1]
    assert row.actor_type == "FOUNDER"
    assert row.result == "ALLOWED"
    assert row.governance_tier == 4
    params = row.action_params or {}
    assert params.get("target") == target
    assert params.get("scope_type") == "exact_url"
    assert params.get("bucket") == "exact_domains"
    serialized = json.dumps(params).lower()
    for forbidden in ("password", "secret", "bearer", "token", "sk-", "pplx-", "xai-"):
        assert forbidden not in serialized, (
            f"audit_params leaked forbidden substring: {forbidden!r}"
        )


# ──────────────────────────────────────────────────────────────────
# 6. Reject unparseable + scope_type/kind mismatches
# ──────────────────────────────────────────────────────────────────


async def test_unparseable_target_is_rejected(
    client: AsyncClient, auth_headers, isolated_scopes_path,
):
    res = await client.post(
        "/api/v1/security/authorized-scope/add",
        headers=auth_headers,
        json={"target": "not a url or hostname", "scope_type": "exact_url"},
    )
    assert res.status_code == 400, res.text
    assert res.json()["detail"]["code"] == "target_unparseable"


async def test_wildcard_rejected_for_ip_target(
    client: AsyncClient, auth_headers, isolated_scopes_path,
):
    res = await client.post(
        "/api/v1/security/authorized-scope/add",
        headers=auth_headers,
        json={"target": "10.0.0.5", "scope_type": "wildcard_subdomain"},
    )
    assert res.status_code == 400, res.text
    assert res.json()["detail"]["code"] == "scope_type_mismatch"


# ──────────────────────────────────────────────────────────────────
# 7. Frontend contract pins (source-grep)
# ──────────────────────────────────────────────────────────────────


def test_scan_page_renders_scope_cta_for_founder():
    """The /scan page must render an 'Add this target to Scan Scope'
    CTA when (a) the response is 403 target_not_in_scope AND (b) the
    user has the FOUNDER role. Non-founders must NOT see the button."""
    page = (
        Path(__file__).resolve().parents[1].parent
        / "frontend" / "src" / "pages" / "ScanPage.tsx"
    )
    src = page.read_text(encoding="utf-8")
    assert "target_not_in_scope" in src
    # The CTA must reference the founder-gated path explicitly so a
    # future refactor can't accidentally widen the audience.
    assert "FOUNDER" in src or "founder" in src
    # The CTA testid lets the live smoke pin the surface.
    assert 'data-testid="scan-scope-cta-add"' in src
    # The modal must exist alongside the CTA.
    assert 'data-testid="scan-scope-cta-modal"' in src


def test_scope_modal_does_not_default_to_wildcard():
    """Frontend default must agree with backend default: exact_url."""
    page = (
        Path(__file__).resolve().parents[1].parent
        / "frontend" / "src" / "pages" / "ScanPage.tsx"
    )
    src = page.read_text(encoding="utf-8")
    # The state initializer must default to exact_url, not wildcard.
    assert "useState<ScopeType>('exact_url')" in src or "useState('exact_url')" in src


def test_scope_modal_does_not_auto_start_scan():
    """After a successful add, the modal must show success and let
    the operator click Start Scan again. It must NOT cascade into a
    scans/start call by itself."""
    page = (
        Path(__file__).resolve().parents[1].parent
        / "frontend" / "src" / "pages" / "ScanPage.tsx"
    )
    src = page.read_text(encoding="utf-8")
    # Hard-coded forbidden: the success handler must not POST to scans/start.
    forbidden_patterns = (
        "handleScopeAddSuccess.*scans/start",
        "onScopeAdded.*scans/start",
        "after add.*startScan",
    )
    for pat in forbidden_patterns:
        import re
        assert not re.search(pat, src, re.I | re.S), (
            f"modal auto-starts a scan after add: matched {pat!r}"
        )
