"""
Tracing Middleware for Request Tracking.

Adds trace IDs to all requests for distributed tracing.
"""

from __future__ import annotations

import uuid
import logging
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds trace IDs to all requests.
    
    Features:
    - Unique trace ID per request
    - Request/response logging
    - Latency tracking
    - Structured logging
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = logging.getLogger("tracing")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate trace ID
        trace_id = str(uuid.uuid4())
        request_id = request.headers.get("X-Request-ID", trace_id)
        
        # Add trace ID to request state
        request.state.trace_id = trace_id
        request.state.request_id = request_id
        request.state.start_time = time.time()
        
        # Log request
        self.logger.info(
            f"Request started",
            extra={
                "trace_id": trace_id,
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None
            }
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate latency
            latency_ms = (time.time() - request.state.start_time) * 1000
            
            # Add trace ID to response headers
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{latency_ms:.2f}ms"
            
            # Log response
            self.logger.info(
                f"Request completed",
                extra={
                    "trace_id": trace_id,
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms
                }
            )
            
            return response
            
        except Exception as e:
            # Log error
            latency_ms = (time.time() - request.state.start_time) * 1000
            self.logger.error(
                f"Request failed: {str(e)}",
                extra={
                    "trace_id": trace_id,
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "latency_ms": latency_ms
                },
                exc_info=True
            )
            raise

