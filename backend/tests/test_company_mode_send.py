"""Tests for the Company Mode send endpoint + provider dispatcher.

Covers:
* Email happy path: writes an RFC-822 file to the outbox and marks sent.
* LinkedIn: returns blocked + the ToS warning (never enable).
* Unsupported channel (twitter_dm): returns failed with the fallthrough.
* Non-existent draft id: 404.
* List endpoint returns all drafts for a mission.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services import company_mode as company_mode_service
from app.services import company_mode_providers as providers


@pytest.fixture(autouse=True)
def _clear_draft_store() -> None:
    """Isolate the module-level draft store between tests."""
    company_mode_service._DRAFT_STORE.clear()
    yield
    company_mode_service._DRAFT_STORE.clear()


@pytest.fixture(autouse=True)
def _redirect_outbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the outbox directory so tests never touch repo var/outbox."""
    outbox = tmp_path / "outbox"
    monkeypatch.setattr(providers, "_OUTBOX_DIR", outbox)
    monkeypatch.setattr(
        providers,
        "_outbox_path",
        lambda draft_id: outbox / f"{draft_id}.eml",
    )
    return outbox


def _new_draft(
    *,
    channel: str,
    recipient: str = "prospect@example.com",
    body: str = "Hello from Daena.",
    subject: str | None = "Quick intro",
) -> tuple[str, str]:
    """Register a draft and return (mission_id, draft_id)."""
    mission_id = str(uuid.uuid4())
    record = company_mode_service.register_draft(
        mission_id=mission_id,
        channel=channel,
        recipient=recipient,
        body=body,
        subject=subject,
    )
    return mission_id, record.draft_id


@pytest.mark.asyncio
async def test_email_send_happy_path_writes_eml(
    client: AsyncClient,
    auth_headers: dict[str, str],
    _redirect_outbox: Path,
) -> None:
    mission_id, draft_id = _new_draft(channel="email")
    res = await client.post(
        f"/api/v1/company-mode/missions/{mission_id}/drafts/{draft_id}/send",
        headers=auth_headers,
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["outcome"]["status"] == "sent"
    assert payload["outcome"]["provider"] == "outbox-stub"
    assert payload["outcome"]["sent_at"] is not None
    assert payload["draft"]["status"] == "sent"

    expected = _redirect_outbox / f"{draft_id}.eml"
    assert expected.exists()
    content = expected.read_text(encoding="utf-8")
    assert "To: prospect@example.com" in content
    assert "Subject: Quick intro" in content
    assert f"X-Daena-Draft-Id: {draft_id}" in content
    assert "Hello from Daena." in content


@pytest.mark.asyncio
async def test_linkedin_send_returns_blocked_with_tos_warning(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    mission_id, draft_id = _new_draft(channel="linkedin")
    res = await client.post(
        f"/api/v1/company-mode/missions/{mission_id}/drafts/{draft_id}/send",
        headers=auth_headers,
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["outcome"]["status"] == "blocked"
    detail = (payload["outcome"]["detail"] or "").lower()
    assert "linkedin" in detail and "tos" in detail
    assert payload["draft"]["status"] == "blocked"
    assert payload["draft"]["error"] is not None


@pytest.mark.asyncio
async def test_unsupported_channel_falls_through_to_failed(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    mission_id, draft_id = _new_draft(channel="twitter_dm")
    res = await client.post(
        f"/api/v1/company-mode/missions/{mission_id}/drafts/{draft_id}/send",
        headers=auth_headers,
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["outcome"]["status"] == "failed"
    assert "twitter_dm" in (payload["outcome"]["detail"] or "")
    assert "no send provider" in (payload["outcome"]["detail"] or "")
    assert payload["draft"]["status"] == "failed"


@pytest.mark.asyncio
async def test_send_missing_draft_returns_404(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    mission_id = str(uuid.uuid4())
    draft_id = str(uuid.uuid4())
    res = await client.post(
        f"/api/v1/company-mode/missions/{mission_id}/drafts/{draft_id}/send",
        headers=auth_headers,
    )
    assert res.status_code == 404
    assert "draft_not_found" in res.text


@pytest.mark.asyncio
async def test_list_drafts_returns_all_for_mission(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    mission_id, draft_id_1 = _new_draft(channel="email", recipient="a@example.com")
    # Register two more drafts: one for this mission, one for another.
    company_mode_service.register_draft(
        mission_id=mission_id,
        channel="email",
        recipient="b@example.com",
        body="second",
    )
    other_mission = str(uuid.uuid4())
    company_mode_service.register_draft(
        mission_id=other_mission,
        channel="email",
        recipient="c@example.com",
        body="other-mission",
    )

    res = await client.get(
        f"/api/v1/company-mode/missions/{mission_id}/drafts",
        headers=auth_headers,
    )
    assert res.status_code == 200
    listed = res.json()
    assert len(listed) == 2
    recipients = sorted(d["recipient"] for d in listed)
    assert recipients == ["a@example.com", "b@example.com"]
    assert all(d["mission_id"] == mission_id for d in listed)
    assert any(d["draft_id"] == draft_id_1 for d in listed)
