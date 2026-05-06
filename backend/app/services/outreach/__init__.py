"""Outreach -- Sprint-19 PR-3..5.

Public re-exports of the factory + bridges.
"""

from app.services.outreach.recipient_safety import (
    RecipientSafetyResult,
    check_recipient_safety,
)
from app.services.outreach.draft_factory import (
    DraftFactoryResult,
    create_outreach_draft_for_opportunity,
)

__all__ = [
    "DraftFactoryResult",
    "RecipientSafetyResult",
    "check_recipient_safety",
    "create_outreach_draft_for_opportunity",
]
