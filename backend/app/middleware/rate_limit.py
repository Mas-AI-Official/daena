"""Rate limiting middleware: Redis-based sliding window.

Applies per-tenant, per-endpoint rate limits using a fixed-window
counter in Redis. Gracefully degrades: if Redis is unavailable,
requests are allowed through (fail-open) to avoid blocking production.

Default: 100 requests per 60 seconds per tenant per endpoint.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Defaults -- overridable per-tenant via governance config in future phases
DEFAULT_RATE_LIMIT = 100
DEFAULT_WINDOW_SECONDS = 60

# Endpoint-specific rate limits (path prefix -> (limit, window_seconds))
# Tighter limits for sensitive endpoints, looser for high-throughput ones.
ENDPOINT_RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/auth/login": (10, 60),        # 10 login attempts/min per IP
    "/api/v1/auth/register": (5, 60),       # 5 registrations/min per IP
    "/api/v1/auth/refresh": (20, 60),       # 20 refreshes/min per user
    "/api/v1/auth/oauth": (10, 60),         # 10 OAuth attempts/min per IP
    "/api/v1/chat/stream": (30, 60),        # 30 chat messages/min per user
    "/api/v1/governance/approvals": (60, 60),  # 60 req/min for admin
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limiter using Redis INCR + EXPIRE."""

    def __init__(
        self,
        app: object,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        """Initialize rate limiter.

        Args:
            app: ASGI application.
            rate_limit: Max requests per window.
            window_seconds: Window duration in seconds.
        """
        super().__init__(app)
        self.rate_limit = rate_limit
        self.window_seconds = window_seconds

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Check rate limit before passing request through.

        Rate limit key: ``rl:{tenant_id}:{method}:{path}``
        If no tenant_id is available (unauthenticated), uses client IP.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware / route handler.

        Returns:
            Response, or 429 if rate limited.
        """
        # Skip rate limiting for health checks and docs
        if request.url.path in ("/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        # Build rate limit key
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id is None:
            # Fall back to client IP for unauthenticated requests
            client_host = request.client.host if request.client else "unknown"
            identity = f"ip:{client_host}"
        else:
            identity = f"t:{tenant_id}"

        path = request.url.path
        method = request.method

        # Resolve endpoint-specific rate limit
        effective_limit = self.rate_limit
        effective_window = self.window_seconds
        for prefix, (limit, window) in ENDPOINT_RATE_LIMITS.items():
            if path.startswith(prefix):
                effective_limit = limit
                effective_window = window
                break

        key = f"rl:{identity}:{method}:{path}"

        try:
            from app.core.redis import check_redis_health, get_redis_client

            # Fast-fail: skip Redis entirely if it's known to be down
            redis_up = await check_redis_health()
            if not redis_up:
                return await call_next(request)

            redis_client = get_redis_client()
            current = await redis_client.incr(key)

            if current == 1:
                # First request in this window -- set expiry
                await redis_client.expire(key, effective_window)

            if current > effective_limit:
                ttl = await redis_client.ttl(key)
                logger.warning(
                    "rate_limit_exceeded",
                    identity=identity,
                    path=path,
                    method=method,
                    current=current,
                    limit=effective_limit,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": (
                                f"Rate limit exceeded. "
                                f"Try again in {max(ttl, 1)} seconds."
                            ),
                        },
                    },
                    headers={
                        "Retry-After": str(max(ttl, 1)),
                        "X-RateLimit-Limit": str(effective_limit),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(effective_limit)
            response.headers["X-RateLimit-Remaining"] = str(
                max(effective_limit - current, 0)
            )
            return response

        except Exception:
            settings = get_settings()
            if settings.allows_unsafe_dev_features:
                logger.warning("rate_limit_redis_unavailable", path=path, mode="fail_open")
                return await call_next(request)

            logger.error("rate_limit_redis_unavailable", path=path, mode="fail_closed")
            return JSONResponse(
                status_code=503,
                content={
                    "success": False,
                    "error": {
                        "code": "RATE_LIMIT_BACKEND_UNAVAILABLE",
                        "message": "Rate limiting backend unavailable.",
                    },
                },
            )
