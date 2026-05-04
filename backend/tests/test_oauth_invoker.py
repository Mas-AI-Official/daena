"""PR-CONN-OAUTH-INVOKER-FOUNDATION (2026-05-03) tests.

Pins:

  1. The allowlist set is exactly the four scoped reads (Gmail messages
     list_unread + search; Drive files.list + get_metadata) -- a future
     PR adding a method MUST update this test.
  2. Every entry is GET + HTTPS + non-zero caps.
  3. Bearer token NEVER appears in any return value or log scrub
     output.
  4. Method-not-allowlisted -> raises BEFORE any network call.
  5. Required input missing -> raises BEFORE any network call.
  6. Instance-not-found / no-access-token / refresh-token-missing all
     raise / return safe errors.
  7. 401 -> refresh -> retry path persists the new token + sets
     refreshed_token=True.
  8. 401 -> refresh -> still 401 returns auth_expired CLEANLY (no
     token leak).
  9. Response > byte cap returns truncated=True with no parsed payload.
 10. Response list > item cap is sliced with truncated=True.
 11. Path-template substitution rejects values containing '/' or
     control chars (URL-component injection defense).

NO REAL google.com NETWORK -- the AsyncClient mock seam in
``OAuthInvoker(http_client=...)`` keeps everything in-process.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connections import Connector, ConnectorInstance
from app.models.identity import Tenant, User
from app.services.connection_v2.oauth_invoker import (
    DEFAULT_RESPONSE_CAP_BYTES,
    DEFAULT_RESPONSE_CAP_ITEMS,
    OAUTH_METHOD_ALLOWLIST,
    InvokeOutcome,
    OAuthCredentialsMissingError,
    OAuthInstanceNotFoundError,
    OAuthInvoker,
    OAuthInvokerError,
    OAuthMethodNotAllowedError,
    _scrub,
)


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_oauth_instance(
    db_session: AsyncSession,
) -> tuple[UUID, UUID, UUID]:
    """Insert a tenant + user + connector + instance with a fake
    OAuth credentials blob. Returns (tenant_id, user_id, instance_id).
    """
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    connector_id = uuid.uuid4()
    instance_id = uuid.uuid4()

    tenant = Tenant(
        id=tenant_id,
        name=f"OAuth Test {tenant_id.hex[:6]}",
        slug=f"oauth-test-{tenant_id.hex[:8]}",
    )
    db_session.add(tenant)
    await db_session.flush()

    user = User(
        id=user_id, tenant_id=tenant_id,
        email=f"{user_id.hex[:8]}@oauth.local",
        password_hash="$2b$12$dummydummydummydummydummydummydummydummydummydummydu",
        role="FOUNDER", email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    connector = Connector(
        id=connector_id,
        name=f"oauth-test-connector-{connector_id.hex[:6]}",
        auth_type="oauth2",
        config_schema={},
        tools=[],
    )
    db_session.add(connector)
    await db_session.flush()

    instance = ConnectorInstance(
        id=instance_id,
        tenant_id=tenant_id,
        connector_id=connector_id,
        user_id=user_id,
        status="CONNECTED",
        credentials={
            "access_token": "ya29.c.fake_access_token_for_test",
            "refresh_token": "1//0g_fake_refresh_token_for_test",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    db_session.add(instance)
    await db_session.flush()
    return tenant_id, user_id, instance_id


def _mock_response(
    status: int, body: dict | bytes | None = None,
) -> MagicMock:
    """Build a minimal httpx-compatible Response mock."""
    m = MagicMock()
    m.status_code = status
    if isinstance(body, dict):
        b = json.dumps(body).encode("utf-8")
        m.content = b
        m.json = MagicMock(return_value=body)
        m.text = b.decode()
    elif isinstance(body, bytes):
        m.content = body
        m.json = MagicMock(side_effect=ValueError("not json"))
        m.text = body.decode("utf-8", errors="replace")
    else:
        m.content = b""
        m.json = MagicMock(return_value={})
        m.text = ""
    return m


def _make_mock_client(*responses: MagicMock) -> MagicMock:
    """Mock httpx.AsyncClient whose .get() returns the responses in
    order. Multiple responses simulate the 401 -> refresh -> retry path.
    """
    client = MagicMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=list(responses))
    client.aclose = AsyncMock()
    return client


# ──────────────────────────────────────────────────────────────────
# 1. Allowlist contract
# ──────────────────────────────────────────────────────────────────


def test_allowlist_set_is_pinned():
    """The four scoped reads -- a future PR adding a method MUST
    update this test, surfacing the diff to a code reviewer."""
    keys = {(m.plugin_id, m.method_id) for m in OAUTH_METHOD_ALLOWLIST}
    assert keys == {
        ("app-gmail", "messages.list_unread"),
        ("app-gmail", "messages.search"),
        ("app-google-drive", "files.list"),
        ("app-google-drive", "files.get_metadata"),
    }, f"Allowlist drifted: {keys}"


def test_every_method_is_get_and_https():
    """Module-load already enforces this; the test pins it explicitly
    so the contract is searchable by name."""
    for m in OAUTH_METHOD_ALLOWLIST:
        assert m.http_method == "GET"
        assert m.base_url.startswith("https://")
        assert m.response_cap_bytes > 0
        assert m.response_cap_items > 0


def test_no_write_method_id_in_allowlist():
    """Forbidden method-id substrings; defense-in-depth name check."""
    forbidden = {"send", "create", "update", "delete", "draft", "post", "patch"}
    for m in OAUTH_METHOD_ALLOWLIST:
        for f in forbidden:
            assert f not in m.method_id.lower(), (
                f"OAuthMethod {m.plugin_id}:{m.method_id} contains "
                f"forbidden write substring {f!r}."
            )


def test_is_allowed_pure_function():
    assert OAuthInvoker.is_allowed("app-gmail", "messages.list_unread")
    assert OAuthInvoker.is_allowed("app-google-drive", "files.list")
    assert not OAuthInvoker.is_allowed("app-gmail", "messages.send")
    assert not OAuthInvoker.is_allowed("nope", "nope")


# ──────────────────────────────────────────────────────────────────
# 2. Token-leak defense
# ──────────────────────────────────────────────────────────────────


def test_scrub_redacts_bearer_token():
    text = "Authorization: Bearer ya29.c.LongTokenString_With.Dashes-here"
    scrubbed = _scrub(text)
    assert "ya29" not in scrubbed
    assert "Bearer [REDACTED]" in scrubbed


def test_invoke_outcome_never_carries_token_field():
    """Defensive structural check -- InvokeOutcome dataclass must NOT
    have any field whose name suggests it could carry a token."""
    forbidden = {"access_token", "refresh_token", "token", "authorization", "bearer"}
    fields = {
        f for f in InvokeOutcome.__dataclass_fields__.keys()
    }
    assert fields & forbidden == set(), (
        f"InvokeOutcome has token-shaped field(s): {fields & forbidden}"
    )


# ──────────────────────────────────────────────────────────────────
# 3. Error paths (no network)
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_method_not_allowlisted_raises_before_network(db_session):
    invoker = OAuthInvoker(db_session)
    with pytest.raises(OAuthMethodNotAllowedError):
        await invoker.invoke(
            tenant_id=uuid.uuid4(),
            instance_id=uuid.uuid4(),
            plugin_id="app-gmail",
            method_id="messages.send",   # WRITE -- not allowed
            operator_inputs={},
        )


@pytest.mark.asyncio
async def test_required_input_missing_raises_before_network(db_session):
    invoker = OAuthInvoker(db_session)
    with pytest.raises(OAuthInvokerError) as excinfo:
        await invoker.invoke(
            tenant_id=uuid.uuid4(),
            instance_id=uuid.uuid4(),
            plugin_id="app-gmail",
            method_id="messages.search",  # requires 'query'
            operator_inputs={},  # missing
        )
    assert "query" in str(excinfo.value)


@pytest.mark.asyncio
async def test_instance_not_found_raises_clean(db_session):
    invoker = OAuthInvoker(db_session)
    with pytest.raises(OAuthInstanceNotFoundError):
        await invoker.invoke(
            tenant_id=uuid.uuid4(),
            instance_id=uuid.uuid4(),
            plugin_id="app-gmail",
            method_id="messages.list_unread",
            operator_inputs={},
        )


@pytest.mark.asyncio
async def test_credentials_missing_access_token_raises(
    db_session, seeded_oauth_instance,
):
    tenant_id, _, instance_id = seeded_oauth_instance
    # Strip the access_token from the persisted credentials.
    from sqlalchemy import select
    inst = (await db_session.execute(
        select(ConnectorInstance).where(ConnectorInstance.id == instance_id)
    )).scalar_one()
    inst.credentials = {"refresh_token": "x"}  # no access_token
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(inst, "credentials")
    await db_session.flush()

    invoker = OAuthInvoker(db_session)
    with pytest.raises(OAuthCredentialsMissingError):
        await invoker.invoke(
            tenant_id=tenant_id,
            instance_id=instance_id,
            plugin_id="app-gmail",
            method_id="messages.list_unread",
            operator_inputs={},
        )


# ──────────────────────────────────────────────────────────────────
# 4. URL/path-substitution defense
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_path_template_rejects_slash_in_substitution(
    db_session, seeded_oauth_instance,
):
    tenant_id, _, instance_id = seeded_oauth_instance
    invoker = OAuthInvoker(db_session)
    with pytest.raises(OAuthInvokerError) as excinfo:
        await invoker.invoke(
            tenant_id=tenant_id,
            instance_id=instance_id,
            plugin_id="app-google-drive",
            method_id="files.get_metadata",  # path has {file_id}
            operator_inputs={"file_id": "abc/../../etc"},  # contains /
        )
    assert "forbidden characters" in str(excinfo.value)


@pytest.mark.asyncio
async def test_path_template_rejects_control_chars(
    db_session, seeded_oauth_instance,
):
    tenant_id, _, instance_id = seeded_oauth_instance
    invoker = OAuthInvoker(db_session)
    with pytest.raises(OAuthInvokerError):
        await invoker.invoke(
            tenant_id=tenant_id,
            instance_id=instance_id,
            plugin_id="app-google-drive",
            method_id="files.get_metadata",
            operator_inputs={"file_id": "abc\ndef"},  # newline = control char
        )


# ──────────────────────────────────────────────────────────────────
# 5. Network-mocked happy path
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_happy_path_gmail_list_unread(db_session, seeded_oauth_instance):
    tenant_id, _, instance_id = seeded_oauth_instance
    body = {
        "messages": [{"id": f"m-{i}"} for i in range(5)],
        "resultSizeEstimate": 5,
    }
    client = _make_mock_client(_mock_response(200, body))
    invoker = OAuthInvoker(db_session, http_client=client)

    outcome = await invoker.invoke(
        tenant_id=tenant_id,
        instance_id=instance_id,
        plugin_id="app-gmail",
        method_id="messages.list_unread",
        operator_inputs={},
    )

    assert outcome.ok is True
    assert outcome.status_code == 200
    assert outcome.payload == body
    assert outcome.truncated is False
    assert outcome.refreshed_token is False

    # Check the GET was called with the right URL + has Bearer header
    call_args = client.get.call_args
    args, kwargs = call_args
    url = args[0]
    headers = kwargs["headers"]
    params = kwargs["params"]
    assert url == "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    assert params == {"q": "is:unread", "maxResults": "20"}
    assert headers["Authorization"].startswith("Bearer ya29.c.fake")


@pytest.mark.asyncio
async def test_happy_path_drive_get_metadata_with_path_substitution(
    db_session, seeded_oauth_instance,
):
    tenant_id, _, instance_id = seeded_oauth_instance
    body = {"id": "1abc", "name": "report.pdf", "mimeType": "application/pdf"}
    client = _make_mock_client(_mock_response(200, body))
    invoker = OAuthInvoker(db_session, http_client=client)

    outcome = await invoker.invoke(
        tenant_id=tenant_id,
        instance_id=instance_id,
        plugin_id="app-google-drive",
        method_id="files.get_metadata",
        operator_inputs={"file_id": "1abc"},
    )

    assert outcome.ok is True
    url = client.get.call_args[0][0]
    assert url == "https://www.googleapis.com/drive/v3/files/1abc"


# ──────────────────────────────────────────────────────────────────
# 6. 401 -> refresh -> retry
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_401_then_refresh_then_retry_persists_new_token(
    db_session, seeded_oauth_instance, monkeypatch,
):
    tenant_id, _, instance_id = seeded_oauth_instance
    # First GET 401, second GET 200 (after refresh).
    client = _make_mock_client(
        _mock_response(401, {"error": "invalid_token"}),
        _mock_response(200, {"messages": [{"id": "m1"}]}),
    )
    invoker = OAuthInvoker(db_session, http_client=client)

    # Mock the refresh_token call so it returns a new token without
    # hitting Google.
    new_expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    async def fake_refresh(refresh_token: str, provider: str = "gmail"):
        return {
            "access_token": "ya29.NEW_TOKEN_AFTER_REFRESH",
            "expires_at": new_expires,
        }

    monkeypatch.setattr(
        invoker._oauth_service, "refresh_token", fake_refresh,
    )
    # Also short-circuit check_and_refresh so it doesn't refresh
    # proactively (not under test here).

    async def fake_check_and_refresh(creds):
        return creds

    monkeypatch.setattr(
        invoker._oauth_service, "check_and_refresh", fake_check_and_refresh,
    )

    outcome = await invoker.invoke(
        tenant_id=tenant_id,
        instance_id=instance_id,
        plugin_id="app-gmail",
        method_id="messages.list_unread",
        operator_inputs={},
    )

    assert outcome.ok is True
    assert outcome.refreshed_token is True
    assert client.get.await_count == 2
    # Persisted creds carry the new token
    from sqlalchemy import select
    inst = (await db_session.execute(
        select(ConnectorInstance).where(ConnectorInstance.id == instance_id)
    )).scalar_one()
    assert inst.credentials["access_token"] == "ya29.NEW_TOKEN_AFTER_REFRESH"


@pytest.mark.asyncio
async def test_401_then_refresh_then_401_returns_auth_expired_safely(
    db_session, seeded_oauth_instance, monkeypatch,
):
    tenant_id, _, instance_id = seeded_oauth_instance
    # Both GETs 401.
    client = _make_mock_client(
        _mock_response(401, {"error": "invalid_token"}),
        _mock_response(401, {"error": "invalid_token"}),
    )
    invoker = OAuthInvoker(db_session, http_client=client)

    async def fake_refresh(refresh_token, provider="gmail"):
        return {
            "access_token": "still-bad",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }

    async def fake_check_and_refresh(creds):
        return creds

    monkeypatch.setattr(invoker._oauth_service, "refresh_token", fake_refresh)
    monkeypatch.setattr(
        invoker._oauth_service, "check_and_refresh", fake_check_and_refresh,
    )

    outcome = await invoker.invoke(
        tenant_id=tenant_id,
        instance_id=instance_id,
        plugin_id="app-gmail",
        method_id="messages.list_unread",
        operator_inputs={},
    )

    # 401 + refresh + 401 again -> outcome.ok=False, status_code=401
    # No exception; no token leak.
    assert outcome.ok is False
    assert outcome.status_code == 401
    assert outcome.reason and "auth_expired" in outcome.reason
    # Reason text MUST NOT contain the token.
    assert "ya29" not in (outcome.reason or "")
    assert "Bearer" not in (outcome.reason or "")


@pytest.mark.asyncio
async def test_401_with_refresh_failure_returns_auth_expired(
    db_session, seeded_oauth_instance, monkeypatch,
):
    tenant_id, _, instance_id = seeded_oauth_instance
    client = _make_mock_client(_mock_response(401, {"error": "invalid_token"}))
    invoker = OAuthInvoker(db_session, http_client=client)

    async def failing_refresh(refresh_token, provider="gmail"):
        raise ValueError("Token refresh failed for gmail: refresh_token expired")

    async def fake_check_and_refresh(creds):
        return creds

    monkeypatch.setattr(invoker._oauth_service, "refresh_token", failing_refresh)
    monkeypatch.setattr(
        invoker._oauth_service, "check_and_refresh", fake_check_and_refresh,
    )

    outcome = await invoker.invoke(
        tenant_id=tenant_id,
        instance_id=instance_id,
        plugin_id="app-gmail",
        method_id="messages.list_unread",
        operator_inputs={},
    )

    assert outcome.ok is False
    assert outcome.status_code == 401
    assert "auth_expired" in (outcome.reason or "")


# ──────────────────────────────────────────────────────────────────
# 7. Response capping
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_response_byte_cap_truncates(
    db_session, seeded_oauth_instance, monkeypatch,
):
    tenant_id, _, instance_id = seeded_oauth_instance

    async def fake_check_and_refresh(creds):
        return creds

    huge = b"X" * (DEFAULT_RESPONSE_CAP_BYTES + 1024)
    client = _make_mock_client(_mock_response(200, huge))
    invoker = OAuthInvoker(db_session, http_client=client)
    monkeypatch.setattr(
        invoker._oauth_service, "check_and_refresh", fake_check_and_refresh,
    )

    outcome = await invoker.invoke(
        tenant_id=tenant_id,
        instance_id=instance_id,
        plugin_id="app-gmail",
        method_id="messages.list_unread",
        operator_inputs={},
    )
    assert outcome.ok is False  # truncation -> ok=False with reason
    assert outcome.truncated is True
    assert "response_too_large" in (outcome.reason or "")


@pytest.mark.asyncio
async def test_response_item_cap_slices_list(
    db_session, seeded_oauth_instance, monkeypatch,
):
    tenant_id, _, instance_id = seeded_oauth_instance

    async def fake_check_and_refresh(creds):
        return creds

    # Drive files.list cap is 30; return 100 items.
    body = {"files": [{"id": f"f-{i}"} for i in range(100)]}
    client = _make_mock_client(_mock_response(200, body))
    invoker = OAuthInvoker(db_session, http_client=client)
    monkeypatch.setattr(
        invoker._oauth_service, "check_and_refresh", fake_check_and_refresh,
    )

    outcome = await invoker.invoke(
        tenant_id=tenant_id,
        instance_id=instance_id,
        plugin_id="app-google-drive",
        method_id="files.list",
        operator_inputs={},
    )
    assert outcome.ok is True
    assert outcome.truncated is True
    assert len(outcome.payload["files"]) == 30


# ──────────────────────────────────────────────────────────────────
# 8. Vendor 5xx
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_vendor_5xx_returns_safe_outcome(
    db_session, seeded_oauth_instance, monkeypatch,
):
    tenant_id, _, instance_id = seeded_oauth_instance

    async def fake_check_and_refresh(creds):
        return creds

    client = _make_mock_client(_mock_response(503, {"error": "Service Unavailable"}))
    invoker = OAuthInvoker(db_session, http_client=client)
    monkeypatch.setattr(
        invoker._oauth_service, "check_and_refresh", fake_check_and_refresh,
    )

    outcome = await invoker.invoke(
        tenant_id=tenant_id,
        instance_id=instance_id,
        plugin_id="app-gmail",
        method_id="messages.list_unread",
        operator_inputs={},
    )
    assert outcome.ok is False
    assert outcome.status_code == 503
    assert "vendor_error" in (outcome.reason or "")


# ──────────────────────────────────────────────────────────────────
# 9. Foundation invariant: NO Phase 2 entry promotes to oauth-mode yet
# ──────────────────────────────────────────────────────────────────


def test_phase2_oauth_entries_still_planned():
    """Wire-up safety: PR-4 ships the OAuth invoker FOUNDATION but
    does NOT yet promote any backend_surface=oauth allowlist entry.
    This invariant fails the moment a future PR flips Gmail/Drive
    without first wiring the executor to call OAuthInvoker."""
    from app.services.connection_v2.skill_executor import PHASE2_ALLOWLIST

    oauth_entries = [
        e for e in PHASE2_ALLOWLIST if e.backend_surface == "oauth"
    ]
    assert oauth_entries, "Phase2 allowlist has no oauth entries"
    for e in oauth_entries:
        assert e.execution_mode == "planned_only", (
            f"{e.plugin_id}:{e.skill_id} promoted to {e.execution_mode!r} "
            f"but the executor does NOT yet route through OAuthInvoker. "
            f"Wire the dispatch first, THEN promote."
        )
