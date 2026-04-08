"""Authentication endpoints: register, login, refresh, logout, OAuth, password reset.

Thin router layer — delegates all business logic to AuthService.
Handles HTTP concerns: status codes, cookies, response envelopes.
"""

from __future__ import annotations

import secrets
import time

from fastapi import APIRouter, Cookie, Depends, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.services.auth import AuthService
from app.services.oauth import OAuthService

# ---------------------------------------------------------------------------
# Login rate limiter: 5 attempts per IP per 60-second window (in-memory)
# ---------------------------------------------------------------------------
_login_attempts: dict[str, list[float]] = {}
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 60  # seconds


def _check_login_rate_limit(client_ip: str) -> bool:
    """Return True if the IP is within limits, False if blocked."""
    now = time.time()
    attempts = _login_attempts.get(client_ip, [])
    # Prune attempts older than the window
    attempts = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW]
    _login_attempts[client_ip] = attempts
    return len(attempts) < _RATE_LIMIT_MAX


def _record_login_attempt(client_ip: str) -> None:
    """Record a failed login attempt for rate limiting."""
    now = time.time()
    attempts = _login_attempts.get(client_ip, [])
    attempts = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW]
    attempts.append(now)
    _login_attempts[client_ip] = attempts


router = APIRouter()

# --- In-memory OAuth state stores (replaced by Redis in production) ---

# CSRF states: {state_token: expiry_timestamp}
_oauth_states: dict[str, float] = {}

# Exchange codes: one-time codes the frontend trades for JWT
# {code: {"result": {...}, "expires": timestamp}}
_oauth_exchange_codes: dict[str, dict] = {}

OAUTH_STATE_TTL = 600  # 10 minutes
OAUTH_CODE_TTL = 120  # 2 minutes


def _cleanup_expired() -> None:
    """Prune expired state and exchange entries."""
    now = time.time()
    for k in [k for k, v in _oauth_states.items() if v < now]:
        del _oauth_states[k]
    for k in [k for k, v in _oauth_exchange_codes.items() if v["expires"] < now]:
        del _oauth_exchange_codes[k]


class OAuthExchangeRequest(BaseModel):
    """Frontend sends this to trade a one-time code for JWT tokens."""
    code: str


# --- Dependency: AuthService per-request ---


async def get_auth_service(
    db: AsyncSession = Depends(get_db),
) -> AuthService:
    """FastAPI dependency that creates AuthService per request."""
    return AuthService(db)


# --- Endpoints ---


@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> dict:
    """Create a new user account and tenant.

    First user in a tenant is auto-assigned Founder role.
    Returns JWT access token in body and sets refresh token as httpOnly cookie
    (same shape as /login for seamless frontend handling).
    """
    settings = get_settings()

    result = await service.register(
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        tenant_name=body.tenant_name,
    )

    # Extract raw refresh token before building response
    raw_refresh = result.pop("raw_refresh_token")

    # Set refresh token as httpOnly cookie (mirrors /login exactly)
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/api/v1/auth",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
    )

    return {"success": True, "data": result}


@router.post("/login", response_model=None)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    """Authenticate with email/password.

    Returns JWT access token in body and sets refresh token as httpOnly cookie.
    Rate-limited to 5 attempts per IP per 60-second window.
    """
    client_ip = request.client.host if request.client else "unknown"

    if not _check_login_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "Too many login attempts. Try again in 60 seconds.",
                },
            },
        )

    settings = get_settings()

    try:
        result = await service.login(email=body.email, password=body.password)
    except Exception:
        _record_login_attempt(client_ip)
        raise

    # Extract raw refresh token before building response
    raw_refresh = result.pop("raw_refresh_token")

    # Set refresh token as httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/api/v1/auth",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
    )

    return {"success": True, "data": result}


@router.post("/refresh")
async def refresh_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    service: AuthService = Depends(get_auth_service),
) -> dict:
    """Exchange a valid refresh token for new access + refresh tokens.

    Reads refresh token from httpOnly cookie. Implements token rotation:
    old token is revoked, new one issued.
    """
    if not refresh_token:
        raise AuthenticationError("No refresh token provided")

    settings = get_settings()
    result = await service.refresh_token(raw_token=refresh_token)

    # Rotate cookie with new refresh token
    raw_refresh = result.pop("raw_refresh_token")
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/api/v1/auth",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
    )

    return {"success": True, "data": result}


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    service: AuthService = Depends(get_auth_service),
) -> dict:
    """Logout current session by revoking the refresh token.

    Clears the refresh cookie regardless of token validity.
    """
    if refresh_token:
        await service.logout(raw_token=refresh_token)

    # Always clear the cookie
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth",
    )

    return {"success": True, "data": {"message": "Logged out successfully"}}


@router.post("/logout-all")
async def logout_all(
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> dict:
    """Revoke all refresh tokens for the current user (logout everywhere).

    Requires valid access token for authentication.
    """
    revoked = await service.revoke_all_tokens(user_id=user.id)

    # Clear current cookie
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth",
    )

    return {
        "success": True,
        "data": {"message": f"Revoked {revoked} session(s)", "revoked_count": revoked},
    }


# --- OAuth Endpoints ---


SUPPORTED_PROVIDERS = {"google", "github"}


@router.get("/oauth/{provider}/authorize")
async def oauth_authorize(provider: str) -> dict:
    """Generate OAuth authorization URL for the given provider.

    Returns a URL to redirect the user to the provider's consent screen,
    plus a state token for CSRF validation on callback.
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise AuthenticationError(f"Unsupported OAuth provider: {provider}")

    settings = get_settings()

    # Validate provider is configured
    if provider == "google" and not settings.google_client_id:
        raise AuthenticationError("Google OAuth is not configured")
    if provider == "github" and not settings.github_client_id:
        raise AuthenticationError("GitHub OAuth is not configured")

    _cleanup_expired()
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = time.time() + OAUTH_STATE_TTL

    if provider == "google":
        url = OAuthService.get_google_auth_url(state)
    else:
        url = OAuthService.get_github_auth_url(state)

    return {"success": True, "data": {"url": url, "state": state}}


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    service: AuthService = Depends(get_auth_service),
) -> RedirectResponse:
    """Handle OAuth provider callback.

    Validates state, exchanges code for user info, creates/links user,
    generates a one-time exchange code, and redirects to the frontend.
    """
    settings = get_settings()

    if provider not in SUPPORTED_PROVIDERS:
        raise AuthenticationError(f"Unsupported OAuth provider: {provider}")

    _cleanup_expired()

    # Validate CSRF state
    if state not in _oauth_states:
        raise AuthenticationError("Invalid or expired OAuth state")
    del _oauth_states[state]

    # Exchange code with provider
    if provider == "google":
        user_info = await OAuthService.exchange_google_code(code)
    else:
        user_info = await OAuthService.exchange_github_code(code)

    # Login or register via AuthService
    result = await service.oauth_login_or_register(info=user_info)

    # Generate one-time exchange code for frontend
    exchange_code = secrets.token_urlsafe(48)
    _oauth_exchange_codes[exchange_code] = {
        "result": result,
        "expires": time.time() + OAUTH_CODE_TTL,
    }

    # Redirect to frontend callback page
    base = settings.oauth_redirect_base_url
    redirect_url = f"{base}/auth/callback?code={exchange_code}&provider={provider}"
    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/oauth/exchange")
async def oauth_exchange(
    body: OAuthExchangeRequest,
    response: Response,
) -> dict:
    """Exchange a one-time OAuth code for JWT tokens.

    The frontend receives this code via the callback redirect URL
    and trades it for the same token payload as /login.
    """
    _cleanup_expired()

    entry = _oauth_exchange_codes.pop(body.code, None)
    if not entry:
        raise AuthenticationError("Invalid or expired exchange code")

    if entry["expires"] < time.time():
        raise AuthenticationError("Exchange code has expired")

    result = entry["result"]
    settings = get_settings()

    # Set refresh cookie (same as login)
    raw_refresh = result.pop("raw_refresh_token")
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/api/v1/auth",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
    )

    return {"success": True, "data": result}


# --- Complete Profile (OAuth users missing terms acceptance) ---


class CompleteProfileRequest(BaseModel):
    """Complete profile after OAuth sign-up: accept terms and optionally set company name."""
    agreed_to_terms: bool
    tenant_name: str | None = None


@router.patch("/complete-profile")
async def complete_profile(
    body: CompleteProfileRequest,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> dict:
    """Complete profile for OAuth users who haven't accepted terms yet.

    Requires authentication. Sets terms_accepted_at and optionally renames
    the tenant. Returns new JWT tokens with profile_complete=True.
    """
    settings = get_settings()

    result = await service.complete_profile(
        user_id=user.id,
        tenant_name=body.tenant_name,
        agreed_to_terms=body.agreed_to_terms,
    )

    # Set refresh cookie (same as login)
    raw_refresh = result.pop("raw_refresh_token")
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/api/v1/auth",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
    )

    return {"success": True, "data": result}


# --- Password Reset Endpoints ---


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> dict:
    """Request a password reset link.

    Always returns success — no email enumeration.
    In dev mode, returns the raw token for testing.
    In production, the token would be sent via email.
    """
    settings = get_settings()
    raw_token = await service.request_password_reset(email=body.email)

    response_data: dict = {
        "message": "If that email exists, a reset link has been sent.",
    }

    # Dev mode: include token for testing (no SMTP configured)
    if not settings.is_production and raw_token:
        response_data["dev_reset_token"] = raw_token
        base = settings.oauth_redirect_base_url
        response_data["dev_reset_url"] = (
            f"{base}/reset-password?token={raw_token}"
        )

    return {"success": True, "data": response_data}


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
) -> dict:
    """Reset password using a valid reset token.

    Token is single-use and expires after 30 minutes.
    On success, all existing sessions are revoked.
    """
    await service.reset_password(
        token=body.token,
        new_password=body.password,
    )

    return {
        "success": True,
        "data": {
            "message": "Password reset successfully. Please sign in.",
        },
    }
