"""Custom exception hierarchy for Daena.

All exceptions inherit from DaenaError for consistent error handling.
Each exception maps to an HTTP status code and error code for API responses.
"""

from __future__ import annotations


class DaenaError(Exception):
    """Base exception for all Daena errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "An unexpected error occurred") -> None:
        self.message = message
        super().__init__(self.message)


# --- Auth ---

class AuthenticationError(DaenaError):
    """Invalid or missing credentials."""
    status_code = 401
    error_code = "AUTH_FAILED"


class TokenExpiredError(DaenaError):
    """JWT or refresh token has expired."""
    status_code = 401
    error_code = "AUTH_EXPIRED"


class InsufficientRoleError(DaenaError):
    """User role does not meet minimum required."""
    status_code = 403
    error_code = "INSUFFICIENT_ROLE"


# --- Governance ---

class GovernanceBlockedError(DaenaError):
    """Action blocked by governance policy."""
    status_code = 403
    error_code = "GOVERNANCE_BLOCKED"


class HardLawViolationError(DaenaError):
    """Action violates an immutable Hard Law."""
    status_code = 403
    error_code = "HARD_LAW_VIOLATION"


class ApprovalRequiredError(DaenaError):
    """Action requires human approval before proceeding."""
    status_code = 202
    error_code = "APPROVAL_REQUIRED"


# --- Tenant ---

class TenantNotFoundError(DaenaError):
    """Tenant does not exist."""
    status_code = 404
    error_code = "TENANT_NOT_FOUND"


class TenantIsolationError(DaenaError):
    """Cross-tenant access attempted (Hard Law #7)."""
    status_code = 403
    error_code = "TENANT_ISOLATION"


# --- Resource ---

class NotFoundError(DaenaError):
    """Requested resource not found."""
    status_code = 404
    error_code = "NOT_FOUND"


class ConflictError(DaenaError):
    """Resource already exists or state conflict."""
    status_code = 409
    error_code = "CONFLICT"


class ValidationError(DaenaError):
    """Input validation failed."""
    status_code = 422
    error_code = "VALIDATION_ERROR"


# --- LLM ---

class ProviderError(DaenaError):
    """LLM provider returned an error."""
    status_code = 502
    error_code = "PROVIDER_ERROR"


class ProviderUnavailableError(DaenaError):
    """No healthy LLM provider available."""
    status_code = 503
    error_code = "PROVIDER_UNAVAILABLE"


class BudgetExceededError(DaenaError):
    """Spending limit reached for tenant/user."""
    status_code = 429
    error_code = "BUDGET_EXCEEDED"


# --- Execution ---

class ExecutionTimeoutError(DaenaError):
    """Tool execution exceeded time limit (Hard Law #3)."""
    status_code = 408
    error_code = "EXECUTION_TIMEOUT"


class SandboxError(DaenaError):
    """Error within sandboxed execution environment."""
    status_code = 500
    error_code = "SANDBOX_ERROR"


# --- Rate Limiting ---

class RateLimitError(DaenaError):
    """Too many requests."""
    status_code = 429
    error_code = "RATE_LIMITED"
