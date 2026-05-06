"""Sprint-16 PR-3 -- Google OAuth live readiness test contract.

Pins:
  1. Status enum classification (200=connected, 401=expired,
     403+scope=insufficient_scope, anything else=failed).
  2. probe_google_provider returns ONLY status + reason; no
     response body propagates.
  3. The 3 supported providers map to the right Google endpoints.
  4. Network errors classify as "failed" with a typed reason.
  5. Missing access_token -> "not_connected".
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# Note: only the async tests in TestProbeGoogleProvider need the
# asyncio mark. The sync tests in TestClassifyResponse and
# TestProbeUrlsAreReadOnly explicitly skip the global mark to
# avoid pytest-asyncio warnings.


class TestClassifyResponse:
    @pytest.mark.parametrize("status,body,expected", [
        (200, "irrelevant body content", "connected"),
        (204, "", "connected"),
        (401, "Invalid Credentials", "expired"),
        (403, "Insufficient Permission. Required scope: gmail.send",
         "insufficient_scope"),
        (403, "User has not granted scope", "insufficient_scope"),
        (403, "Forbidden -- some other reason", "failed"),
        (500, "internal", "failed"),
        (404, "not found", "failed"),
        (429, "rate limit", "failed"),
    ])
    def test_status_classification(self, status, body, expected):
        from app.services.google_readiness_test import _classify_response

        assert _classify_response(
            status_code=status, body_text=body,
        ) == expected


@pytest.mark.asyncio
class TestProbeGoogleProvider:
    async def test_unknown_provider_returns_failed(self):
        from app.services.google_readiness_test import probe_google_provider

        result = await probe_google_provider(
            provider="dropbox", access_token="tok",
        )
        assert result["status"] == "failed"
        assert "unknown provider" in result["reason"]

    async def test_missing_token_returns_not_connected(self):
        from app.services.google_readiness_test import probe_google_provider

        result = await probe_google_provider(
            provider="gmail", access_token="",
        )
        assert result["status"] == "not_connected"

    async def test_200_returns_connected_no_body_leak(self, monkeypatch):
        """The probe must NOT include the response body in the
        result; only status + opaque reason."""
        from app.services import google_readiness_test as mod

        # Build a fake response with sensitive-looking body content.
        secret_body = '{"emailAddress": "founder@example.com", "messagesTotal": 12345}'
        fake_response = MagicMock(status_code=200, text=secret_body)

        async def _fake_get(self, url, headers=None):
            return fake_response

        monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

        result = await mod.probe_google_provider(
            provider="gmail", access_token="tok",
        )
        assert result["status"] == "connected"
        # The reason mentions the HTTP status, NOT the body.
        assert "200" in result["reason"]
        # Paranoid: walk every value and assert no body content.
        for v in result.values():
            assert "founder@example.com" not in str(v)
            assert "messagesTotal" not in str(v)
            assert "12345" not in str(v)

    async def test_401_returns_expired(self, monkeypatch):
        from app.services import google_readiness_test as mod

        fake_response = MagicMock(status_code=401, text="Invalid Credentials")

        async def _fake_get(self, url, headers=None):
            return fake_response

        monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)
        result = await mod.probe_google_provider(
            provider="calendar", access_token="tok",
        )
        assert result["status"] == "expired"
        assert "expired" in result["reason"].lower() or "revoke" in result["reason"].lower()

    async def test_403_with_scope_returns_insufficient_scope(self, monkeypatch):
        from app.services import google_readiness_test as mod

        fake_response = MagicMock(
            status_code=403,
            text="Request had insufficient authentication scopes",
        )

        async def _fake_get(self, url, headers=None):
            return fake_response

        monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)
        result = await mod.probe_google_provider(
            provider="drive", access_token="tok",
        )
        assert result["status"] == "insufficient_scope"

    async def test_timeout_returns_failed(self, monkeypatch):
        from app.services import google_readiness_test as mod

        async def _raise_timeout(self, url, headers=None):
            raise httpx.TimeoutException("slow")

        monkeypatch.setattr(httpx.AsyncClient, "get", _raise_timeout)
        result = await mod.probe_google_provider(
            provider="gmail", access_token="tok",
        )
        assert result["status"] == "failed"
        assert "timeout" in result["reason"].lower()

    async def test_network_error_returns_failed(self, monkeypatch):
        from app.services import google_readiness_test as mod

        async def _raise_network(self, url, headers=None):
            raise httpx.ConnectError("dns fail")

        monkeypatch.setattr(httpx.AsyncClient, "get", _raise_network)
        result = await mod.probe_google_provider(
            provider="calendar", access_token="tok",
        )
        assert result["status"] == "failed"
        assert "network" in result["reason"].lower()


class TestProbeUrlsAreReadOnly:
    def test_probe_urls_are_get_metadata_only(self):
        """Lock the probe URL set so a future PR can't accidentally
        repoint it to a write surface."""
        from app.services.google_readiness_test import _PROBE_URLS

        # Exactly three providers; each URL contains only metadata
        # paths (profile / primary calendar metadata / about user).
        assert set(_PROBE_URLS.keys()) == {"gmail", "calendar", "drive"}
        assert "/profile" in _PROBE_URLS["gmail"]
        assert "/calendars/primary" in _PROBE_URLS["calendar"]
        assert "/about" in _PROBE_URLS["drive"]
        # Negative: NEVER a send / messages.send / events.insert path.
        for url in _PROBE_URLS.values():
            assert "send" not in url
            assert "events" not in url or "/events" not in url
            assert "/messages" not in url
            assert "/files" not in url
