"""Tests for the neutrally-named elevated security mode REST API.

The underlying module is the same singleton that the existing internal
test module covers at the unit level. These tests focus on the HTTP
surface the frontend talks to: founder role check, activate with good
and bad keys, state reflection. The test module deliberately does not
reference the hidden activation command string anywhere.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.security import create_access_token
from app.services.security import evilbob_mode


_TEST_KEY = "test-secret-key-123"


@pytest.fixture(autouse=True)
def _reset_mode_between_tests():
    """Ensure the singleton state does not leak across tests."""
    evilbob_mode.deactivate()
    yield
    evilbob_mode.deactivate()


@pytest.fixture
def _local_env():
    """Force the environment detector to say 'local' for every gate."""
    # Clear any cloud markers, leave app_env untouched (get_settings reads it).
    cloud_vars = [
        "K_SERVICE", "GAE_ENV", "AWS_LAMBDA_FUNCTION_NAME",
        "AZURE_FUNCTIONS_ENVIRONMENT", "RENDER",
        "RAILWAY_ENVIRONMENT", "FLY_APP_NAME",
    ]
    original = {k: os.environ.get(k) for k in cloud_vars}
    for k in cloud_vars:
        os.environ.pop(k, None)
    try:
        yield
    finally:
        for k, v in original.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _non_founder_headers() -> dict[str, str]:
    """JWT for a USER role account (not FOUNDER)."""
    token = create_access_token(
        user_id=str(uuid.UUID("33333333-3333-3333-3333-333333333333")),
        tenant_id=str(uuid.UUID("11111111-1111-1111-1111-111111111111")),
        role="USER",
    )
    return {"Authorization": f"Bearer {token}"}


# ----------------------------------------------------------------------
# Auth gate
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_founder_cannot_activate(
    app: FastAPI, client: AsyncClient, _local_env
):
    """Non-FOUNDER role receives 403 on the activate endpoint."""
    resp = await client.post(
        "/api/v1/security/mode/activate",
        json={"key": _TEST_KEY},
        headers=_non_founder_headers(),
    )
    # InsufficientRoleError -> 403 via DaenaError exception handler.
    assert resp.status_code == 403


# ----------------------------------------------------------------------
# Activate / deactivate happy path
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_founder_activate_with_valid_key(
    app: FastAPI,
    client: AsyncClient,
    auth_headers,
    _local_env,
):
    """Founder with correct key flips the singleton to active."""
    with patch.dict(os.environ, {"EVILBOB_KEY": _TEST_KEY}):
        resp = await client.post(
            "/api/v1/security/mode/activate",
            json={"key": _TEST_KEY},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["active"] is True
    assert payload["environment"] == "local"
    assert "offensive_exploitation" in payload["capabilities"]
    assert evilbob_mode.is_active() is True


@pytest.mark.asyncio
async def test_founder_activate_with_wrong_key(
    app: FastAPI,
    client: AsyncClient,
    auth_headers,
    _local_env,
):
    """Wrong key yields 400 with reason_denied populated."""
    with patch.dict(os.environ, {"EVILBOB_KEY": _TEST_KEY}):
        resp = await client.post(
            "/api/v1/security/mode/activate",
            json={"key": "wrong"},
            headers=auth_headers,
        )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["active"] is False
    assert "Invalid activation key" in detail["reason_denied"]
    assert evilbob_mode.is_active() is False


@pytest.mark.asyncio
async def test_founder_deactivate_returns_inactive(
    app: FastAPI,
    client: AsyncClient,
    auth_headers,
    _local_env,
):
    """Deactivate endpoint flips the singleton off."""
    with patch.dict(os.environ, {"EVILBOB_KEY": _TEST_KEY}):
        # First activate.
        evilbob_mode.activate(key=_TEST_KEY, user_id="test-founder")
        assert evilbob_mode.is_active() is True

        resp = await client.post(
            "/api/v1/security/mode/deactivate",
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert resp.json()["active"] is False
    assert evilbob_mode.is_active() is False


# ----------------------------------------------------------------------
# State endpoint
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_state_reflects_current_singleton_inactive(
    app: FastAPI,
    client: AsyncClient,
    auth_headers,
):
    """GET /state returns active=False when singleton is off."""
    resp = await client.get(
        "/api/v1/security/mode/state",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is False


@pytest.mark.asyncio
async def test_state_reflects_current_singleton_active(
    app: FastAPI,
    client: AsyncClient,
    auth_headers,
    _local_env,
):
    """GET /state mirrors an activated singleton."""
    with patch.dict(os.environ, {"EVILBOB_KEY": _TEST_KEY}):
        evilbob_mode.activate(key=_TEST_KEY, user_id="test-founder")

        resp = await client.get(
            "/api/v1/security/mode/state",
            headers=auth_headers,
        )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["active"] is True
    assert len(payload["capabilities"]) >= 5


@pytest.mark.asyncio
async def test_state_available_to_non_founder(
    app: FastAPI,
    client: AsyncClient,
    _local_env,
):
    """State endpoint is open to any authenticated user for UI badge."""
    resp = await client.get(
        "/api/v1/security/mode/state",
        headers=_non_founder_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is False
