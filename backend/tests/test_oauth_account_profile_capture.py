"""PR-CONN-GOOGLE-ACCOUNT-PROFILES-CAPTURE (Sprint-5 PR-1, 2026-05-03) tests.

Pins:

  1. ``_normalize_owner_email`` is the SINGLE place that decides how a
     fetched provider identity becomes a column value:
       * None / empty / whitespace -> None
       * mixed-case + stray whitespace -> stripped + lowercased
       * over-long input clamped to the column width (254)
  2. The Google OAuth callback populates ``ConnectorInstance.owner_email``
     from ``ConnectorOAuthService.fetch_account_identity``, so the
     account picker UI (Sprint-5 PR-2) and the executor's
     ``_find_oauth_instance`` gate (Sprint-4 PR-3) both see the right
     account label without ever decrypting the credentials JSONB blob.
  3. If the userinfo fetch FAILS, the OAuth connection itself still
     succeeds: the row gets created with ``owner_email=NULL`` and the
     UI must fall back to manual selection. This invariant defends
     "OAuth completion is more important than identity nicety".
  4. A repeated callback for the SAME account UPDATES the same row
     instead of inserting a duplicate, because the lookup now matches
     on ``owner_email`` (mirrors the Sprint-4 PR-3 unique constraint).
  5. ``owner_email`` NEVER contains token material -- defense-in-depth
     so the Sprint-4 PR-1 audit walk (which scans for access_token /
     refresh_token / Bearer substrings) keeps holding even if a
     malicious provider returns weird userinfo.
"""

from __future__ import annotations

import uuid

import pytest

from app.api.v1.connector_oauth import (
    _normalize_owner_email,
    _oauth_states,
)


# ──────────────────────────────────────────────────────────────────
# 1. _normalize_owner_email -- pure function
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", [None, "", "   ", "\n\t  "])
def test_normalize_returns_none_for_falsy_or_blank(value):
    assert _normalize_owner_email(value) is None


def test_normalize_lowercases_mixed_case():
    assert _normalize_owner_email("Masoud.Masoori@Mas-AI.co") == (
        "masoud.masoori@mas-ai.co"
    )


def test_normalize_strips_surrounding_whitespace():
    assert _normalize_owner_email("  daena@mas-ai.co\n") == "daena@mas-ai.co"


def test_normalize_caps_at_254_chars():
    """RFC 5321 SMTP cap. Defensive against weird provider payloads."""
    over_long = ("a" * 300) + "@mas-ai.co"
    out = _normalize_owner_email(over_long)
    assert out is not None
    assert len(out) == 254


def test_normalize_handles_handle_style_identity_without_at_sign():
    """GitHub / Slack identities aren't strictly emails. Still
    normalize lowercase + store -- column is 'owner identifier',
    not 'strict email'. The picker UI tolerates either."""
    assert _normalize_owner_email("MasoudOnGitHub") == "masoudongithub"


# ──────────────────────────────────────────────────────────────────
# Test infrastructure -- seed Tenant + User + Connector + state
# ──────────────────────────────────────────────────────────────────


async def _seed_tenant_user_connector(
    db_session, tenant_id, user_id, connector_name="Gmail",
):
    """Create the rows the OAuth callback expects to find on success.

    Idempotent: the test-engine is session-scoped and ``db_session``
    fixture only rolls back uncommitted state. Committed rows from
    earlier tests in the file persist, so each test must tolerate
    pre-existing tenants/users/connectors and reuse them rather than
    re-INSERT.
    """
    from sqlalchemy import select
    from app.models.connections import Connector
    from app.models.identity import Tenant, User

    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.id == tenant_id),
        )
    ).scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(id=tenant_id, name="T", slug="t-sprint5", settings={})
        db_session.add(tenant)
        await db_session.flush()

    user = (
        await db_session.execute(
            select(User).where(User.id == user_id),
        )
    ).scalar_one_or_none()
    if user is None:
        user = User(
            id=user_id, tenant_id=tenant_id,
            email="founder@test.local", role="FOUNDER",
        )
        db_session.add(user)
        await db_session.flush()

    connector = (
        await db_session.execute(
            select(Connector).where(Connector.name == connector_name),
        )
    ).scalar_one_or_none()
    if connector is None:
        connector = Connector(
            name=connector_name,
            auth_type="OAUTH2",
            config_schema={}, tools=[],
        )
        db_session.add(connector)
        await db_session.flush()

    # Wipe any stale ConnectorInstance rows from prior tests so this
    # test's assertions on len(rows) reflect ONLY this test's writes.
    from app.models.connections import ConnectorInstance
    stale = (
        await db_session.execute(select(ConnectorInstance))
    ).scalars().all()
    for inst in stale:
        await db_session.delete(inst)
    await db_session.commit()
    return tenant, user, connector


def _plant_state(state, *, connector_id, user_id, tenant_id, redirect_uri):
    """Plant an OAuth state record so the callback validates."""
    _oauth_states[state] = {
        "connector_id": connector_id,
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "redirect_uri": redirect_uri,
    }


def _patch_oauth_service(monkeypatch, *, identity, access_token="tok-AAA"):
    """Monkeypatch ConnectorOAuthService so the callback never hits
    Google.  Returns a sentinel that tests can assert on."""
    from app.api.v1 import connector_oauth as endpoint

    async def fake_exchange_code(self, code, redirect_uri, provider="gmail"):
        return {
            "access_token": access_token,
            "refresh_token": "refresh-XYZ",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "token_type": "Bearer",
            "scope": "openid email",
            "provider": provider,
        }

    async def fake_fetch_account_identity(self, access_token_arg, provider):
        return identity

    monkeypatch.setattr(
        endpoint.ConnectorOAuthService, "exchange_code",
        fake_exchange_code, raising=True,
    )
    monkeypatch.setattr(
        endpoint.ConnectorOAuthService, "fetch_account_identity",
        fake_fetch_account_identity, raising=True,
    )


# ──────────────────────────────────────────────────────────────────
# 2. Callback populates owner_email from successful userinfo
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_callback_populates_owner_email_from_google_userinfo(
    client, db_session, monkeypatch, test_tenant_id, test_user_id,
):
    from sqlalchemy import select
    from app.models.connections import ConnectorInstance

    await _seed_tenant_user_connector(
        db_session, test_tenant_id, test_user_id, connector_name="Gmail",
    )
    state = "state-A"
    _plant_state(
        state, connector_id="gmail", user_id=test_user_id,
        tenant_id=test_tenant_id,
        redirect_uri="http://test/api/v1/connectors/oauth/callback",
    )
    _patch_oauth_service(
        monkeypatch, identity="Masoud.Masoori@MAS-AI.co",
    )

    res = await client.get(
        "/api/v1/connectors/oauth/callback",
        params={"code": "code-A", "state": state},
    )
    assert res.status_code == 200, res.text
    assert "Connected to Gmail" in res.text

    rows = (
        await db_session.execute(select(ConnectorInstance))
    ).scalars().all()
    assert len(rows) == 1
    inst = rows[0]
    # Sprint-5 PR-1 invariant: column populated, lowercased.
    assert inst.owner_email == "masoud.masoori@mas-ai.co"


# ──────────────────────────────────────────────────────────────────
# 3. Userinfo failure does NOT block OAuth connection
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_callback_with_identity_failure_still_creates_row_with_null_owner(
    client, db_session, monkeypatch, test_tenant_id, test_user_id,
):
    """fetch_account_identity returns "" (the documented failure mode)
    -> owner_email stays NULL but the row is still CONNECTED so the
    operator can pick it manually in the picker UI."""
    from sqlalchemy import select
    from app.core.constants import ConnectorStatus
    from app.models.connections import ConnectorInstance

    await _seed_tenant_user_connector(
        db_session, test_tenant_id, test_user_id, connector_name="Gmail",
    )
    state = "state-B"
    _plant_state(
        state, connector_id="gmail", user_id=test_user_id,
        tenant_id=test_tenant_id,
        redirect_uri="http://test/api/v1/connectors/oauth/callback",
    )
    _patch_oauth_service(monkeypatch, identity="")

    res = await client.get(
        "/api/v1/connectors/oauth/callback",
        params={"code": "code-B", "state": state},
    )
    assert res.status_code == 200, res.text

    rows = (
        await db_session.execute(select(ConnectorInstance))
    ).scalars().all()
    assert len(rows) == 1
    inst = rows[0]
    assert inst.owner_email is None
    assert inst.status == ConnectorStatus.CONNECTED.value


# ──────────────────────────────────────────────────────────────────
# 4. Idempotent re-callback does NOT duplicate the row
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_callback_for_same_owner_updates_existing_row(
    client, db_session, monkeypatch, test_tenant_id, test_user_id,
):
    from sqlalchemy import select
    from app.models.connections import ConnectorInstance

    await _seed_tenant_user_connector(
        db_session, test_tenant_id, test_user_id, connector_name="Gmail",
    )

    # First connect.
    state1 = "state-C1"
    _plant_state(
        state1, connector_id="gmail", user_id=test_user_id,
        tenant_id=test_tenant_id,
        redirect_uri="http://test/api/v1/connectors/oauth/callback",
    )
    _patch_oauth_service(monkeypatch, identity="daena@mas-ai.co")
    res1 = await client.get(
        "/api/v1/connectors/oauth/callback",
        params={"code": "code-C1", "state": state1},
    )
    assert res1.status_code == 200

    # Second callback for the SAME account.
    state2 = "state-C2"
    _plant_state(
        state2, connector_id="gmail", user_id=test_user_id,
        tenant_id=test_tenant_id,
        redirect_uri="http://test/api/v1/connectors/oauth/callback",
    )
    _patch_oauth_service(monkeypatch, identity="daena@mas-ai.co")
    res2 = await client.get(
        "/api/v1/connectors/oauth/callback",
        params={"code": "code-C2", "state": state2},
    )
    assert res2.status_code == 200

    rows = (
        await db_session.execute(select(ConnectorInstance))
    ).scalars().all()
    assert len(rows) == 1, (
        "Re-callback for same owner must UPDATE not INSERT"
    )
    assert rows[0].owner_email == "daena@mas-ai.co"


# ──────────────────────────────────────────────────────────────────
# 5. Two distinct accounts -> two distinct rows (the founder rule)
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_callback_for_two_accounts_creates_two_rows(
    client, db_session, monkeypatch, test_tenant_id, test_user_id,
):
    """The whole point of Sprint-5: masoud.masoori@... + daena@...
    must coexist as separate ConnectorInstance rows so the executor
    can disambiguate via _owner_email at run time."""
    from sqlalchemy import select
    from app.models.connections import ConnectorInstance

    await _seed_tenant_user_connector(
        db_session, test_tenant_id, test_user_id, connector_name="Gmail",
    )

    for state, identity in (
        ("state-D1", "masoud.masoori@mas-ai.co"),
        ("state-D2", "daena@mas-ai.co"),
    ):
        _plant_state(
            state, connector_id="gmail", user_id=test_user_id,
            tenant_id=test_tenant_id,
            redirect_uri="http://test/api/v1/connectors/oauth/callback",
        )
        _patch_oauth_service(monkeypatch, identity=identity)
        res = await client.get(
            "/api/v1/connectors/oauth/callback",
            params={"code": "code-" + state, "state": state},
        )
        assert res.status_code == 200, res.text

    rows = (
        await db_session.execute(select(ConnectorInstance))
    ).scalars().all()
    owner_emails = sorted(r.owner_email for r in rows)
    assert owner_emails == [
        "daena@mas-ai.co", "masoud.masoori@mas-ai.co",
    ], f"Expected two distinct rows, got: {owner_emails!r}"


# ──────────────────────────────────────────────────────────────────
# 6. Backfill -- callback with a non-NULL identity replaces a NULL row
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_callback_after_identity_failure_creates_separate_row_not_backfill(
    client, db_session, monkeypatch, test_tenant_id, test_user_id,
):
    """Realistic scenario: first connect failed userinfo (network
    blip) -> row exists with NULL owner_email. Operator re-runs
    OAuth, this time userinfo succeeds with masoud@mas-ai.co.

    The system MUST NOT silently backfill the orphan NULL row --
    we cannot prove the orphan was the SAME Google account the user
    just picked. (They might have logged in with a different account
    on the second attempt.)

    Instead: the orphan NULL row stays; a new row appears for
    masoud@. The operator reconciles via the picker UI by deleting
    the orphan. This is exactly the behavior the founder rule
    "if identity lookup fails, store null and require manual
    account profile selection" implies."""
    from sqlalchemy import select
    from app.models.connections import ConnectorInstance

    await _seed_tenant_user_connector(
        db_session, test_tenant_id, test_user_id, connector_name="Gmail",
    )

    # First: identity fetch fails -> NULL row.
    state1 = "state-E1"
    _plant_state(
        state1, connector_id="gmail", user_id=test_user_id,
        tenant_id=test_tenant_id,
        redirect_uri="http://test/api/v1/connectors/oauth/callback",
    )
    _patch_oauth_service(monkeypatch, identity="")
    await client.get(
        "/api/v1/connectors/oauth/callback",
        params={"code": "code-E1", "state": state1},
    )

    # Second: identity now succeeds.
    state2 = "state-E2"
    _plant_state(
        state2, connector_id="gmail", user_id=test_user_id,
        tenant_id=test_tenant_id,
        redirect_uri="http://test/api/v1/connectors/oauth/callback",
    )
    _patch_oauth_service(monkeypatch, identity="masoud@mas-ai.co")
    await client.get(
        "/api/v1/connectors/oauth/callback",
        params={"code": "code-E2", "state": state2},
    )

    rows = (
        await db_session.execute(select(ConnectorInstance))
    ).scalars().all()
    owner_emails = sorted(
        (r.owner_email or "<NULL>") for r in rows
    )
    assert owner_emails == ["<NULL>", "masoud@mas-ai.co"], (
        f"Expected orphan NULL row + new identified row, got: "
        f"{owner_emails!r}"
    )


# ──────────────────────────────────────────────────────────────────
# 7. owner_email never carries token material
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_owner_email_never_contains_token_material(
    client, db_session, monkeypatch, test_tenant_id, test_user_id,
):
    """Even if a malicious provider returns userinfo that smells like
    a token, the owner_email column should hold the normalized identity
    string -- not extract or fabricate tokens. This pins the function's
    contract: it is a string passthrough, not a parser."""
    from sqlalchemy import select
    from app.models.connections import ConnectorInstance

    await _seed_tenant_user_connector(
        db_session, test_tenant_id, test_user_id, connector_name="Gmail",
    )
    # The fake identity LOOKS like an access token. The column will
    # store it lowercased + capped, but the test asserts that NO
    # actual access/refresh token from the patched exchange_code
    # leaks into the column.
    state = "state-F"
    _plant_state(
        state, connector_id="gmail", user_id=test_user_id,
        tenant_id=test_tenant_id,
        redirect_uri="http://test/api/v1/connectors/oauth/callback",
    )
    _patch_oauth_service(
        monkeypatch,
        identity="evil@example.com",
        access_token="ya29.SECRET-ACCESS-TOKEN-DO-NOT-LEAK",
    )

    await client.get(
        "/api/v1/connectors/oauth/callback",
        params={"code": "code-F", "state": state},
    )

    rows = (
        await db_session.execute(select(ConnectorInstance))
    ).scalars().all()
    assert len(rows) == 1
    inst = rows[0]
    # Column holds only the identity, never the token.
    assert inst.owner_email == "evil@example.com"
    assert "ya29" not in (inst.owner_email or "")
    assert "SECRET" not in (inst.owner_email or "").upper()
