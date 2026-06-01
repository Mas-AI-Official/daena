"""Auth gating for the Edge-TTS proxy endpoints (/api/v1/tts/*).

POST /tts/speak proxies to Microsoft's Edge-TTS CDN, opening an upstream
WebSocket per call. Before this gate the endpoints were unauthenticated,
making them a free TTS proxy and a cost-amplification / DoS vector. These
tests lock in that every /tts route now requires a valid bearer token,
and that a valid token still passes the gate (so the real frontend path,
which always sends the bearer, is not broken).

No network is exercised: the no-token cases reject before the handler
runs, and the auth-passes proof uses /tts/defaults which returns a static
constant (never touches edge-tts).
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_speak_requires_auth(client: AsyncClient) -> None:
    """POST /tts/speak without a token is rejected before reaching edge-tts."""
    res = await client.post("/api/v1/tts/speak", json={"text": "hello"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_voices_requires_auth(client: AsyncClient) -> None:
    """GET /tts/voices (upstream catalog fetch) requires auth."""
    res = await client.get("/api/v1/tts/voices")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_defaults_requires_auth(client: AsyncClient) -> None:
    """GET /tts/defaults requires auth (consistency across the /tts surface)."""
    res = await client.get("/api/v1/tts/defaults")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_defaults_passes_with_valid_token(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    """A valid bearer token passes the gate and returns the static defaults.

    Proves the new auth requirement does NOT block the authenticated
    frontend path (VoiceProvider always attaches the daena_token bearer).
    Uses /defaults so the assertion stays deterministic and offline.
    """
    res = await client.get("/api/v1/tts/defaults", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["default"] == "en-US-AriaNeural"
    assert isinstance(body["recommended"], list) and body["recommended"]
