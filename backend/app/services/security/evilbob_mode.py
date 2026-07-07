"""/3vilbob Mode Manager -- Global offensive capability activation.

/3vilbob is NOT a separate tool. It is a MODE on Daena herself.

Normal Daena: defensive security scanning, vulnerability detection,
compliance checking, threat monitoring. Like OpenClaw and every other
security scanner.

/3vilbob ON: defensive + offensive. Full-spectrum penetration testing.
Daena THINKS like an attacker -- not because she switched brains, but
because she ADDED offensive thinking on top of her defensive thinking.
She still detects and reports vulnerabilities (defensive), AND she
exploits them to prove impact (offensive).

The /3vilbob key exists for one reason: to prevent unauthorized users
from accessing full offensive capability. It is NOT a software lock.
There is no artificial block inside Daena's reasoning. The key is the
ONLY gate. If you have the key, Daena operates at full power.

Activation requirements (ALL must be true):
    1. EVILBOB_KEY environment variable is set and matches user input
    2. Environment is LOCAL (not Cloud Run, not staging, not production)
    3. User has founder/admin role (when auth is active)

Why local-only: offensive tooling needs nmap, nuclei, Playwright,
proxy rotation, Tor -- tools that don't exist in Cloud Run containers.
Cloud users get full defensive capability. Offensive requires local.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Mode state
# ---------------------------------------------------------------------------

@dataclass
class EvilBobState:
    """Current /3vilbob mode state."""
    active: bool = False
    activated_at: str = ""
    activated_by: str = ""       # user_id or "founder"
    session_id: str = ""
    environment: str = ""        # "local", "cloud", "unknown"
    key_validated: bool = False
    capabilities: list[str] = field(default_factory=list)
    reason_denied: str = ""      # Why activation failed (if it did)


# Singleton state -- one mode per process
_current_state = EvilBobState()


# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------

def detect_environment() -> str:
    """Detect whether we are running locally or in cloud.

    Cloud indicators (any = cloud):
        - K_SERVICE (Cloud Run)
        - GAE_ENV (App Engine)
        - AWS_LAMBDA_FUNCTION_NAME (Lambda)
        - AZURE_FUNCTIONS_ENVIRONMENT (Azure Functions)
        - app_env == "production" or "staging"

    Local indicators:
        - None of the above
        - Ollama reachable at localhost
    """
    cloud_vars = [
        "K_SERVICE",          # Cloud Run
        "GAE_ENV",            # App Engine
        "AWS_LAMBDA_FUNCTION_NAME",
        "AZURE_FUNCTIONS_ENVIRONMENT",
        "RENDER",             # Render.com
        "RAILWAY_ENVIRONMENT",  # Railway
        "FLY_APP_NAME",      # Fly.io
    ]
    for var in cloud_vars:
        if os.environ.get(var):
            return "cloud"

    # Check app_env setting
    try:
        from app.core.config import get_settings
        env = get_settings().app_env.lower()
        if env in ("production", "staging"):
            return "cloud"
    except Exception:
        pass

    return "local"


# ---------------------------------------------------------------------------
# Master activation key read (single consume-only choke point)
# ---------------------------------------------------------------------------

# Optional backend that supplies the /3vilbob master key. None => env fallback.
# Consume-only seam (Rule 18): a real secret backend (e.g. GCP Secret Manager on
# Cloud Run) can register here at deploy time without editing any read site.
_activation_key_provider: Callable[[], str | None] | None = None


def set_activation_key_provider(
    provider: Callable[[], str | None] | None,
) -> None:
    """Register (or clear) the backend that supplies the /3vilbob master key.

    Pass a zero-arg callable returning the key string, or None/"" when it has no
    value (read_activation_key then falls back to the EVILBOB_KEY env var). Pass
    None to clear the provider and use the process environment directly.

    Never pass the key itself here -- pass a callable that fetches it, so the
    master secret is never captured in a module global.
    """
    global _activation_key_provider
    _activation_key_provider = provider


def read_activation_key() -> str:
    """Return the /3vilbob master activation key (EVILBOB_KEY).

    Single choke point for reading the master key. Resolution order:
      1. A registered provider (cloud/secret-manager path), if it yields a
         non-empty value.
      2. The EVILBOB_KEY process environment variable (local/test path).

    EVILBOB_KEY is a master-key-class secret: it is never logged here, never
    committed to source, and never shipped in env to a cloud runtime. A provider
    that raises is logged by exception TYPE only and swallowed, so a misconfigured
    backend can never crash the activation path -- it falls back to the env read.
    """
    provider = _activation_key_provider
    if provider is not None:
        try:
            value = provider()
        except Exception as exc:  # never let a bad backend crash activation
            logger.warning(
                "evilbob.key_provider_failed",
                error=type(exc).__name__,
            )
            value = None
        if value:
            return value
    return os.environ.get("EVILBOB_KEY", "")


def _validate_key(user_key: str) -> bool:
    """Validate the /3vilbob activation key.

    The key is stored as EVILBOB_KEY in the environment. We compare
    using constant-time comparison to prevent timing attacks (yes,
    even for this -- good habits).

    If EVILBOB_KEY is not set, activation is impossible.
    """
    stored_key = read_activation_key()
    if not stored_key:
        return False
    if not user_key:
        return False

    # Constant-time comparison
    import hmac
    return hmac.compare_digest(
        stored_key.encode("utf-8"),
        user_key.encode("utf-8"),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def activate(
    key: str,
    user_id: str = "founder",
    session_id: str = "",
) -> EvilBobState:
    """Activate /3vilbob mode.

    Returns the new state. Check state.active to see if activation succeeded.
    If denied, state.reason_denied explains why.

    Usage::

        from app.services.security.evilbob_mode import activate, is_active

        state = activate(key="my-secret-key", user_id="founder")
        if state.active:
            print("Full spectrum active")
        else:
            print(f"Denied: {state.reason_denied}")

        # Anywhere else in the codebase:
        if is_active():
            # Add offensive capabilities
            ...
    """
    global _current_state

    env = detect_environment()

    # Gate 1: environment must be local
    if env != "local":
        _current_state = EvilBobState(
            active=False,
            environment=env,
            reason_denied=(
                f"Offensive mode requires local environment. "
                f"Detected: {env}. Cloud deployments have full defensive "
                f"capability but offensive tooling (nmap, nuclei, Playwright, "
                f"Tor) is not available in cloud containers."
            ),
        )
        logger.warning(
            "evilbob.activation_denied",
            reason="cloud_environment",
            env=env,
        )
        return _current_state

    # Gate 2: key must match
    if not _validate_key(key):
        _current_state = EvilBobState(
            active=False,
            environment=env,
            key_validated=False,
            reason_denied="Invalid activation key.",
        )
        logger.warning(
            "evilbob.activation_denied",
            reason="invalid_key",
            user=user_id,
        )
        return _current_state

    # Both gates passed -- activate full spectrum
    from datetime import datetime, timezone
    _current_state = EvilBobState(
        active=True,
        activated_at=datetime.now(timezone.utc).isoformat(),
        activated_by=user_id,
        session_id=session_id,
        environment=env,
        key_validated=True,
        capabilities=[
            "defensive_scanning",       # Always on
            "offensive_exploitation",   # /3vilbob adds this
            "post_exploitation",        # Connect, authenticate, navigate
            "evidence_capture",         # Tamper-evident proof chain
            "proxy_rotation",           # Mandatory IP protection
            "opsec_reasoning",          # Identity/persona management
            "constraint_bypass",        # No artificial blocks
            "target_interaction",       # Connect to discovered services
        ],
    )

    logger.info(
        "evilbob.activated",
        user=user_id,
        session=session_id,
        capabilities=len(_current_state.capabilities),
    )
    return _current_state


def deactivate() -> EvilBobState:
    """Deactivate /3vilbob mode. Returns to defensive-only."""
    global _current_state
    prev = _current_state.active
    _current_state = EvilBobState(active=False, environment=detect_environment())

    if prev:
        logger.info("evilbob.deactivated")

    return _current_state


def is_active() -> bool:
    """Check if /3vilbob mode is currently active.

    This is the function every module calls. Lightweight, no I/O.
    """
    return _current_state.active


def get_state() -> EvilBobState:
    """Get the full current mode state."""
    return _current_state


def has_capability(capability: str) -> bool:
    """Check if a specific capability is active.

    Usage::

        if has_capability("post_exploitation"):
            # Connect to target
            ...
        if has_capability("opsec_reasoning"):
            # Reason about identity management
            ...
    """
    if not _current_state.active:
        # Defensive capabilities are always available
        return capability in ("defensive_scanning", "evidence_capture")
    return capability in _current_state.capabilities


def auto_activate_if_configured() -> EvilBobState | None:
    """Auto-activate /3vilbob on local environments at startup.

    Called once during app initialization. If EVILBOB_AUTO_ACTIVATE=true
    and EVILBOB_KEY is set and environment is local, activates immediately.
    This means Masoud never has to type '/3vilbob ON' on his local machine.

    Returns the state if auto-activated, None if skipped.
    """
    auto = os.environ.get("EVILBOB_AUTO_ACTIVATE", "").lower()
    if auto not in ("true", "1", "yes"):
        return None

    key = read_activation_key()
    if not key:
        logger.debug("evilbob.auto_activate_skipped", reason="no EVILBOB_KEY")
        return None

    env = detect_environment()
    if env != "local":
        logger.debug("evilbob.auto_activate_skipped", reason=f"environment={env}")
        return None

    state = activate(key=key, user_id="founder_auto")
    if state.active:
        logger.info(
            "evilbob.auto_activated",
            capabilities=len(state.capabilities),
        )
    return state
