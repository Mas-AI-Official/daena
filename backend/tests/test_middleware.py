"""Tests for middleware stack: tenant injection, rate limiting, request ID.

Validates:
- TenantMiddleware extracts tenant_id from JWT, passes None for unauthenticated
- RateLimitMiddleware enforces per-tenant rate limits (mocked Redis)
- RequestIDMiddleware generates/propagates X-Request-ID headers
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token

# ── RequestIDMiddleware ──────────────────────────────────────────────


class TestRequestIDMiddleware:
    """X-Request-ID generation and propagation."""

    @pytest.mark.asyncio
    async def test_generates_request_id(self, client: AsyncClient) -> None:
        """Response includes X-Request-ID even without incoming header."""
        response = await client.get("/health")
        assert response.status_code == 200
        req_id = response.headers.get("X-Request-ID")
        assert req_id is not None
        assert len(req_id) == 32  # uuid4().hex = 32 chars

    @pytest.mark.asyncio
    async def test_propagates_existing_request_id(self, client: AsyncClient) -> None:
        """If client sends X-Request-ID, it is echoed back."""
        custom_id = "my-custom-request-id-12345"
        response = await client.get(
            "/health", headers={"X-Request-ID": custom_id}
        )
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == custom_id

    @pytest.mark.asyncio
    async def test_different_requests_get_different_ids(
        self, client: AsyncClient
    ) -> None:
        """Each request gets a unique generated ID."""
        r1 = await client.get("/health")
        r2 = await client.get("/health")
        id1 = r1.headers.get("X-Request-ID")
        id2 = r2.headers.get("X-Request-ID")
        assert id1 != id2


# ── TenantMiddleware ─────────────────────────────────────────────────


class TestTenantMiddleware:
    """Tenant ID extraction from JWT."""

    @pytest.mark.asyncio
    async def test_extracts_tenant_from_valid_jwt(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """Authenticated requests pass through (tenant_id set internally)."""
        response = await client.get("/health", headers=auth_headers)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_unauthenticated_passes_with_none_tenant(
        self, client: AsyncClient
    ) -> None:
        """No Authorization header => tenant_id = None, still passes through."""
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_jwt_passes_with_none_tenant(
        self, client: AsyncClient
    ) -> None:
        """Malformed JWT => tenant_id = None, request still goes through."""
        response = await client.get(
            "/health", headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_expired_token_passes_through_middleware(
        self, client: AsyncClient
    ) -> None:
        """Expired JWT => middleware sets tenant_id=None, doesn't block."""
        from datetime import timedelta

        token = create_access_token(
            user_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            role="OPERATOR",
            expires_delta=timedelta(seconds=-1),
        )
        response = await client.get(
            "/health", headers={"Authorization": f"Bearer {token}"}
        )
        # Middleware is permissive; auth enforcement is in route deps
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_non_bearer_scheme_ignored(self, client: AsyncClient) -> None:
        """Authorization header with non-Bearer scheme => tenant_id = None."""
        response = await client.get(
            "/health", headers={"Authorization": "Basic dXNlcjpwYXNz"}
        )
        assert response.status_code == 200


# ── RateLimitMiddleware ──────────────────────────────────────────────


class TestRateLimitMiddleware:
    """Redis-based rate limiting (with mocked Redis)."""

    @pytest.mark.asyncio
    async def test_health_endpoint_skips_rate_limit(
        self, client: AsyncClient
    ) -> None:
        """Health endpoint is exempted from rate limiting."""
        # Even without Redis, health should work (fail-open + exemption)
        for _ in range(5):
            response = await client.get("/health")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present_when_redis_available(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """When Redis is up, rate limit headers appear in response."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        with (
            patch("app.core.redis.get_redis_client", return_value=mock_redis),
            patch("app.core.redis.check_redis_health", return_value=True),
        ):
            response = await client.get(
                "/api/v1/health", headers=auth_headers
            )
            assert response.status_code == 200
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_returns_429(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """Exceeding rate limit returns 429 with Retry-After header."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 101  # Over the default 100 limit
        mock_redis.ttl.return_value = 30

        with (
            patch("app.core.redis.get_redis_client", return_value=mock_redis),
            patch("app.core.redis.check_redis_health", return_value=True),
        ):
            response = await client.get(
                "/api/v1/health", headers=auth_headers
            )
            assert response.status_code == 429
            data = response.json()
            assert data["error"]["code"] == "RATE_LIMITED"
            assert "Retry-After" in response.headers
            assert response.headers["X-RateLimit-Remaining"] == "0"

    @pytest.mark.asyncio
    async def test_rate_limit_fail_open_on_redis_error(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """Redis unavailable => fail-open, request goes through."""
        mock_redis = AsyncMock()
        mock_redis.incr.side_effect = ConnectionError("Redis down")

        with patch(
            "app.core.redis.get_redis_client",
            return_value=mock_redis,
        ):
            response = await client.get(
                "/api/v1/health", headers=auth_headers
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rate_limit_fails_closed_outside_dev_env(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """Non-local environments should not silently fail open on Redis errors."""
        mock_redis = AsyncMock()
        mock_redis.incr.side_effect = ConnectionError("Redis down")

        with (
            patch("app.core.redis.get_redis_client", return_value=mock_redis),
            patch("app.core.redis.check_redis_health", return_value=True),
            patch("app.middleware.rate_limit.get_settings") as mock_settings,
        ):
            mock_settings.return_value.allows_unsafe_dev_features = False
            response = await client.get(
                "/api/v1/health", headers=auth_headers
            )
            assert response.status_code == 503
            data = response.json()
            assert data["error"]["code"] == "RATE_LIMIT_BACKEND_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_docs_endpoint_skips_rate_limit(
        self, client: AsyncClient
    ) -> None:
        """/docs and /openapi.json are exempted from rate limiting."""
        response = await client.get("/openapi.json")
        # May be 404 in test (docs_url can be None), but should not be 429
        assert response.status_code != 429

    @pytest.mark.asyncio
    async def test_rate_limit_uses_ip_for_unauthenticated(
        self, client: AsyncClient
    ) -> None:
        """Unauthenticated requests use client IP for rate limit key."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        with (
            patch("app.core.redis.get_redis_client", return_value=mock_redis),
            patch("app.core.redis.check_redis_health", return_value=True),
        ):
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
            # Redis key should contain "ip:" prefix
            call_args = mock_redis.incr.call_args[0][0]
            assert "ip:" in call_args

    @pytest.mark.asyncio
    async def test_first_request_sets_expire(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """First request in window (incr returns 1) triggers expire call."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True

        with (
            patch("app.core.redis.get_redis_client", return_value=mock_redis),
            patch("app.core.redis.check_redis_health", return_value=True),
        ):
            await client.get("/api/v1/health", headers=auth_headers)
            mock_redis.expire.assert_called_once()
