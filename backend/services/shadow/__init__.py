"""
Shadow Department — Daena's Defensive Deception Layer

Implements honeypots, canary tokens, and threat intelligence
to detect and log unauthorized access attempts.

Per DAENA_NEW_BLUEPRINT.html: "Defense That Bites Back"
"""

from .shadow_agent import ShadowAgent, get_shadow_agent
from .honeypot import HoneypotManager, CanaryToken, HoneypotHit
from .threat_intel import ThreatIntel, AttackerProfile, TTP

__all__ = [
    "ShadowAgent",
    "get_shadow_agent",
    "HoneypotManager",
    "CanaryToken",
    "HoneypotHit",
    "ThreatIntel",
    "AttackerProfile",
    "TTP",
]
