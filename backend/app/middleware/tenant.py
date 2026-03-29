"""Tenant injection middleware: extracts tenant_id from JWT.

Parses the Authorization header to extract tenant_id from the JWT
payload and injects it into ``request.state.tenant_id`` for use by
downstream middleware (e.g. rate limiter) and route handlers.

This does NOT enforce authentication — unauthenticated requests pass
through with ``tenant_id = None``. Auth enforcement is handled by
the ``get_current_user`` dependency in route definitions.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    """Extract tenant_id from JWT and bind to request state."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Parse JWT for tenant_id, store in request.state.

        Does not block unauthenticated requests — just sets
        ``request.state.tenant_id`` to None if no valid JWT present.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware / route handler.

        Returns:
            Response from downstream handlers.
        """
        tenant_id: str | None = None

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                from app.core.security import decode_access_token

                payload = decode_access_token(token)
                tenant_id = payload.get("tenant_id")
            except Exception:
                # Invalid/expired token — not our concern here.
                # Auth enforcement happens in get_current_user dependency.
                pass

        request.state.tenant_id = tenant_id
        return await call_next(request)
