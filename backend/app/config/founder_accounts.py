"""Founder Account Registry -- maps services to the email they're registered under.

Daena reads this to know which founder account holds which subscription,
so she can reference the right context without impersonating the founder.
API keys are in .env regardless of which email they're under.

This is a CONFIG file, not a secret store. No passwords here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FounderAccount:
    """An account the founder controls that Daena should be aware of."""
    email: str
    label: str  # "primary_business", "personal", "legacy"
    services: tuple[str, ...] = ()


# Founder's accounts and which services live under each
FOUNDER_ACCOUNTS: list[FounderAccount] = [
    FounderAccount(
        email=os.getenv("FOUNDER_EMAIL", "masoud.masoori@mas-ai.co"),
        label="primary_business",
        services=(
            "Google Workspace",
            "GCP (project: daena-467315)",
            "Anthropic API",
            "Perplexity for Startups ($5000 credits)",
            "GitHub (Mas-AI-Official org)",
            "FormSubmit (landing page forms)",
        ),
    ),
    FounderAccount(
        email=os.getenv("FOUNDER_PERSONAL_EMAIL", "masoud.masori@gmail.com"),
        label="personal_legacy",
        services=(
            "OpenAI / ChatGPT / Codex",
            "Google Gemini / Gemini CLI",
            "Groq",
            "Together.ai",
            "OpenRouter",
            "HuggingFace",
            "Most SaaS signups (legacy)",
        ),
    ),
]


@dataclass
class DaenaIdentity:
    """Daena's own professional identity for autonomous operations."""
    email: str = ""
    display_name: str = "Daena"
    role: str = "AI Vice President"
    company: str = "MAS-AI Technologies Inc."
    signature: str = ""

    def __post_init__(self):
        self.email = os.getenv("DAENA_EMAIL", "daena@mas-ai.co")
        self.signature = (
            f"{self.display_name}\n"
            f"{self.role}, {self.company}\n"
            f"{self.email}\n"
            "https://mas-ai.co"
        )

    @property
    def email_mode(self) -> str:
        """How Daena handles email: governed | ask_always | disabled."""
        return os.getenv("DAENA_EMAIL_MODE", "governed")

    @property
    def can_send(self) -> bool:
        return self.email_mode != "disabled"

    def introduction(self) -> str:
        """Standard self-introduction for outreach."""
        return (
            f"I'm {self.display_name}, the {self.role} at {self.company}. "
            "I'm an AI-powered executive that handles partnerships, "
            "operations, and communications for the company."
        )


# Singleton
DAENA_IDENTITY = DaenaIdentity()


def get_service_account(service_name: str) -> FounderAccount | None:
    """Find which founder account a service is registered under."""
    service_lower = service_name.lower()
    for account in FOUNDER_ACCOUNTS:
        for svc in account.services:
            if service_lower in svc.lower():
                return account
    return None
