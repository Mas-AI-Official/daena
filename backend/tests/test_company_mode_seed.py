"""Tests for the Company Mode seed brief persistence endpoints.

Covers:
* GET returns exists=false when the seed file does not yet exist.
* POST then GET round-trips the brief with a non-null updated_at.
* POST overwrites the previous seed and bumps the timestamp.
* Non-founder role gets 403.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.api.v1 import company_mode as company_mode_api


_SAMPLE_BRIEF = {
    "company_name": "MAS-AI Technologies",
    "company_one_liner": "Governed multi-agent AI orchestration.",
    "target_customer": "SMB CISOs 10-100 employees US/CA",
    "customer_pain": "Drowning in security alerts.",
    "our_promise": "Governed AI SecOps in under an hour.",
    "proof_points": ["PhiLattice filed", "Zero-FP gate"],
    "channels": ["linkedin", "email"],
    "prospect_limit_per_mission": 10,
    "tone": "warm-direct",
    "auto_send": False,
    "require_founder_approval": True,
    "notes": None,
}


@pytest.fixture(autouse=True)
def _isolate_seed_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``_seed_path`` to a temp file so tests never clobber real IP."""
    fake_path = tmp_path / "company_seed.md"
    monkeypatch.setattr(company_mode_api, "_seed_path", lambda: fake_path)
    return fake_path


@pytest.mark.asyncio
async def test_get_seed_returns_exists_false_when_missing(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    res = await client.get("/api/v1/company-mode/seed-brief", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["exists"] is False
    assert body["brief"] is None
    assert body["updated_at"] is None


@pytest.mark.asyncio
async def test_post_then_get_round_trips_brief(
    client: AsyncClient, auth_headers: dict[str, str], _isolate_seed_file: Path,
) -> None:
    post_res = await client.post(
        "/api/v1/company-mode/seed-brief",
        headers=auth_headers,
        json=_SAMPLE_BRIEF,
    )
    assert post_res.status_code == 200
    post_body = post_res.json()
    assert post_body["exists"] is True
    assert post_body["updated_at"] is not None
    assert _isolate_seed_file.exists()

    get_res = await client.get(
        "/api/v1/company-mode/seed-brief", headers=auth_headers,
    )
    assert get_res.status_code == 200
    got = get_res.json()
    assert got["exists"] is True
    assert got["updated_at"] is not None
    assert got["brief"]["company_name"] == _SAMPLE_BRIEF["company_name"]
    assert got["brief"]["channels"] == ["linkedin", "email"]
    assert got["brief"]["proof_points"] == ["PhiLattice filed", "Zero-FP gate"]


@pytest.mark.asyncio
async def test_post_overwrites_previous_seed(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    first = await client.post(
        "/api/v1/company-mode/seed-brief",
        headers=auth_headers,
        json=_SAMPLE_BRIEF,
    )
    assert first.status_code == 200
    first_ts = first.json()["updated_at"]

    # Sleep just long enough for mtime to tick on all filesystems.
    await asyncio.sleep(1.05)

    updated = dict(_SAMPLE_BRIEF)
    updated["company_name"] = "MAS-AI Technologies v2"
    updated["tone"] = "crisp-executive"

    second = await client.post(
        "/api/v1/company-mode/seed-brief",
        headers=auth_headers,
        json=updated,
    )
    assert second.status_code == 200
    second_ts = second.json()["updated_at"]
    assert second_ts != first_ts

    get_res = await client.get(
        "/api/v1/company-mode/seed-brief", headers=auth_headers,
    )
    body = get_res.json()
    assert body["brief"]["company_name"] == "MAS-AI Technologies v2"
    assert body["brief"]["tone"] == "crisp-executive"


@pytest.mark.asyncio
async def test_non_founder_gets_403(
    client: AsyncClient,
    test_user_id: uuid.UUID,
    test_tenant_id: uuid.UUID,
) -> None:
    operator_token = create_access_token(
        user_id=str(test_user_id),
        tenant_id=str(test_tenant_id),
        role="OPERATOR",
    )
    headers = {"Authorization": f"Bearer {operator_token}"}

    get_res = await client.get("/api/v1/company-mode/seed-brief", headers=headers)
    assert get_res.status_code == 403

    post_res = await client.post(
        "/api/v1/company-mode/seed-brief",
        headers=headers,
        json=_SAMPLE_BRIEF,
    )
    assert post_res.status_code == 403
