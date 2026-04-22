"""Reply-driven auto-booking scaffold for Company Mode.

When a prospect replies to a draft, Daena classifies intent with a
deterministic keyword matcher and -- if the reply reads positive and
meeting-seeking -- suggests calendar slots and queues a confirmation
draft in the module-level draft store.

This is intentionally a scaffold, not a real calendar integration.
``suggest_booking_slots`` returns deterministic UTC datetimes so tests
stay stable; real availability querying (gws-calendar MCP, Calendly,
Cal.com) is tracked as a follow-up P2. The scaffold exists so the
frontend + approval pipeline can be wired end-to-end now, and the
availability backend can be swapped without shape changes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal


@dataclass
class ReplyClassification:
    """Deterministic intent + sentiment for a single reply.

    ``keywords_matched`` returns the actual keyword strings that
    triggered the classification so the founder UI can show evidence
    instead of an opaque "positive" label.
    """

    sentiment: Literal["positive", "neutral", "negative"]
    intent: Literal["meet", "info", "unsubscribe", "unknown"]
    keywords_matched: list[str] = field(default_factory=list)


# Keyword tables are ordered by intent. The first table to match wins;
# ordering encodes precedence so "unsubscribe me, but it looks great"
# is still treated as unsubscribe (safety > engagement).
_UNSUBSCRIBE_KEYWORDS = ("unsubscribe", "remove", "stop", "no thanks")
_MEET_KEYWORDS = (
    "interested",
    "happy to",
    "let's talk",
    "looks great",
    "book",
    "calendar",
    "schedule",
    "call",
    "sure",
)
_INFO_KEYWORDS = ("info", "deck", "more details", "send me")


def _find_matches(text: str, keywords: tuple[str, ...]) -> list[str]:
    """Return keywords that appear in ``text`` at word-boundary positions.

    Case-insensitive. Multi-word keywords are matched literally (whole
    phrase). Single-word keywords use ``\\b`` boundaries so ``"info"``
    does not match inside ``"information"``.
    """
    matches: list[str] = []
    lowered = text.lower()
    for kw in keywords:
        if " " in kw or "'" in kw:
            if kw in lowered:
                matches.append(kw)
        else:
            if re.search(rf"\b{re.escape(kw)}\b", lowered):
                matches.append(kw)
    return matches


def classify_reply(text: str) -> ReplyClassification:
    """Classify the reply into (sentiment, intent, keywords).

    Precedence (safety first):
        1. Unsubscribe keywords -> negative / unsubscribe.
        2. Meet keywords -> positive / meet.
        3. Info keywords -> positive / info.
        4. Otherwise -> neutral / unknown.
    """
    if not text or not text.strip():
        return ReplyClassification(sentiment="neutral", intent="unknown")

    unsubscribe_hits = _find_matches(text, _UNSUBSCRIBE_KEYWORDS)
    if unsubscribe_hits:
        return ReplyClassification(
            sentiment="negative",
            intent="unsubscribe",
            keywords_matched=unsubscribe_hits,
        )

    meet_hits = _find_matches(text, _MEET_KEYWORDS)
    if meet_hits:
        return ReplyClassification(
            sentiment="positive",
            intent="meet",
            keywords_matched=meet_hits,
        )

    info_hits = _find_matches(text, _INFO_KEYWORDS)
    if info_hits:
        return ReplyClassification(
            sentiment="positive",
            intent="info",
            keywords_matched=info_hits,
        )

    return ReplyClassification(sentiment="neutral", intent="unknown")


def suggest_booking_slots(
    from_when: datetime,
    count: int = 3,
) -> list[datetime]:
    """Return ``count`` naive-UTC datetime slots at 15:00 UTC.

    Deterministic: slots are ``from_when + 2d``, ``from_when + 3d``,
    ``from_when + 4d``, ... each normalized to 15:00 UTC. Real
    availability querying is a future ticket; this scaffold exists so
    the end-to-end flow (reply -> classify -> suggest -> confirm draft)
    can be exercised today.
    """
    if count <= 0:
        return []
    base = from_when if from_when.tzinfo else from_when.replace(tzinfo=UTC)
    base = base.astimezone(UTC)
    slots: list[datetime] = []
    for i in range(count):
        day = (base + timedelta(days=2 + i)).date()
        slot = datetime(day.year, day.month, day.day, 15, 0, 0, tzinfo=UTC)
        slots.append(slot)
    return slots
