"""Tests for the reply classifier + auto-booking scaffold.

Covers:
* classify_reply: meet, unsubscribe, info, unknown.
* POST /replies/process happy path: queues a confirmation draft.
* POST /replies/process negative: no slots, no draft.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.services import company_mode as company_mode_service
from app.services.company_mode_replies import classify_reply


@pytest.fixture(autouse=True)
def _clear_draft_store() -> None:
    company_mode_service._DRAFT_STORE.clear()
    yield
    company_mode_service._DRAFT_STORE.clear()


def test_classify_positive_meet() -> None:
    result = classify_reply("I'd love to chat, book me a call")
    assert result.sentiment == "positive"
    assert result.intent == "meet"
    matched = set(result.keywords_matched)
    assert "book" in matched
    assert "call" in matched


def test_classify_negative_unsubscribe() -> None:
    result = classify_reply("please unsubscribe")
    assert result.sentiment == "negative"
    assert result.intent == "unsubscribe"
    assert "unsubscribe" in result.keywords_matched


def test_classify_positive_info() -> None:
    result = classify_reply("send me more info about the deck")
    assert result.sentiment == "positive"
    assert result.intent == "info"
    matched = set(result.keywords_matched)
    assert "send me" in matched or "info" in matched or "deck" in matched


def test_classify_neutral_unknown() -> None:
    result = classify_reply("k")
    assert result.sentiment == "neutral"
    assert result.intent == "unknown"
    assert result.keywords_matched == []


@pytest.mark.asyncio
async def test_process_reply_positive_meet_creates_confirmation_draft(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    # Seed an original draft so we can exercise the channel-inheritance path.
    mission_id = str(uuid.uuid4())
    original = company_mode_service.register_draft(
        mission_id=mission_id,
        channel="email",
        recipient="prospect@example.com",
        body="Original outreach.",
        subject="Quick intro",
    )
    payload = {
        "mission_id": mission_id,
        "draft_id": original.draft_id,
        "reply_text": "Looks great, let's talk -- happy to book a call.",
        "reply_from": "prospect@example.com",
    }
    res = await client.post(
        "/api/v1/company-mode/replies/process",
        headers=auth_headers,
        json=payload,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["classification"]["sentiment"] == "positive"
    assert body["classification"]["intent"] == "meet"
    assert len(body["suggested_slots"]) == 3
    assert body["confirmation_draft_id"] is not None

    confirmation = company_mode_service.get_draft(body["confirmation_draft_id"])
    assert confirmation is not None
    assert confirmation.mission_id == mission_id
    assert confirmation.channel == "email"
    assert confirmation.recipient == "prospect@example.com"
    assert "Hi prospect" in confirmation.body
    assert "slots open" in confirmation.body


@pytest.mark.asyncio
async def test_process_reply_negative_returns_empty_slots_and_null_draft(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    mission_id = str(uuid.uuid4())
    original = company_mode_service.register_draft(
        mission_id=mission_id,
        channel="email",
        recipient="prospect@example.com",
        body="Original outreach.",
    )
    payload = {
        "mission_id": mission_id,
        "draft_id": original.draft_id,
        "reply_text": "please unsubscribe, not interested.",
        "reply_from": "prospect@example.com",
    }
    res = await client.post(
        "/api/v1/company-mode/replies/process",
        headers=auth_headers,
        json=payload,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["classification"]["sentiment"] == "negative"
    assert body["classification"]["intent"] == "unsubscribe"
    assert body["suggested_slots"] == []
    assert body["confirmation_draft_id"] is None
