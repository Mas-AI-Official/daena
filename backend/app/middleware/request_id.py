"""Request ID middleware: generates unique ID per request.

Attaches a unique X-Request-ID header to every request and response.
Binds the request_id into structlog context vars so all log entries
within the request automatically include it for correlation.
"""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique request ID into every request/response cycle."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Generate or propagate request ID, bind to log context.

        If the incoming request already has an X-Request-ID header
        (e.g. from an API gateway), reuse it. Otherwise generate one.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware / route handler.

        Returns:
            Response with X-Request-ID header attached.
        """
        request_id = request.headers.get(HEADER) or uuid.uuid4().hex

        # Bind to structlog context — all logs in this request include it
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Store in request state for downstream access
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[HEADER] = request_id
        return response
