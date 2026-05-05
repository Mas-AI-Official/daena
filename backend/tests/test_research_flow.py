"""PR-CAREEROPS-READONLY-RESEARCH-FLOW (Sprint-10 PR-3, 2026-05-05).
PR-CONTENTOPS-READONLY-RESEARCH-FLOW (Sprint-10 PR-4, 2026-05-05).

Pins the contract for the supervised read-only research flow.

Hard guarantees:

  1. POST /research/career produces a LOCAL ResearchDraft, status=DRAFT.
  2. POST /research/content produces a LOCAL ResearchDraft, status=DRAFT.
  3. SSRF guard fires on the source URL via the underlying scrape
     service -- localhost / RFC1918 / link-local URLs are refused.
  4. The endpoints NEVER expose any send / post / submit verb.
     Source-grep test pins this.
  5. List / read endpoints are tenant + user scoped (cross-user
     drafts are not visible).
  6. Unknown kind value is rejected.
  7. The model has NO ``sent_at`` / ``submitted_at`` / ``posted_at``
     columns -- the schema itself forbids "this draft went somewhere".
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.identity import Tenant, User
from app.models.research import ResearchDraft
from app.services.scrape import ExtractResult


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def seeded_tenant_user(db_session) -> tuple[str, str, str]:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db_session.add(Tenant(
        id=tenant_id, name=f"R {tenant_id.hex[:6]}",
        slug=f"r-{tenant_id.hex[:8]}",
    ))
    await db_session.flush()
    db_session.add(User(
        id=user_id, tenant_id=tenant_id,
        email=f"{user_id.hex[:8]}@r.local",
        password_hash="$2b$12$x" * 4,
        role="FOUNDER", email_verified=True,
    ))
    await db_session.commit()
    token = create_access_token(
        user_id=str(user_id), tenant_id=str(tenant_id),
        role="FOUNDER", email="r@r.local", display_name="R",
    )
    return token, str(user_id), str(tenant_id)


def _stub_scrape(monkeypatch, *, success=True, result="Sample summary",
                  error=None, truncated=False):
    async def fake_extract(url, goal, *, max_chars=8000, **_):
        return ExtractResult(
            success=success, result=result, truncated=truncated,
            error=error, worker_version="1.0.0",
        )
    monkeypatch.setattr(
        "app.services.research_flow.extract_from_url", fake_extract,
    )


# ──────────────────────────────────────────────────────────────────
# 1. Happy path -- career
# ──────────────────────────────────────────────────────────────────


async def test_career_research_creates_local_draft(
    client: AsyncClient, seeded_tenant_user, monkeypatch,
):
    token, _, _ = seeded_tenant_user
    _stub_scrape(monkeypatch, result="Role: Senior Eng. Comp: $200k.")
    res = await client.post(
        "/api/v1/research/career",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "url": "https://jobs.example.com/posting/123",
            "goal": "extract role title and comp",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    draft = body["draft"]
    assert draft["kind"] == "career"
    assert draft["status"] == "DRAFT"
    assert draft["source_url"] == "https://jobs.example.com/posting/123"
    assert draft["source_host"] == "https://jobs.example.com"
    assert "Senior Eng" in draft["summary"]


async def test_content_research_creates_local_draft(
    client: AsyncClient, seeded_tenant_user, monkeypatch,
):
    token, _, _ = seeded_tenant_user
    _stub_scrape(monkeypatch, result="Thesis: AI agents need governance.")
    res = await client.post(
        "/api/v1/research/content",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "url": "https://blog.example.com/agents",
            "goal": "summarize thesis + 3 strongest claims",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    draft = body["draft"]
    assert draft["kind"] == "content"
    assert draft["status"] == "DRAFT"
    assert "governance" in draft["summary"]


# ──────────────────────────────────────────────────────────────────
# 2. SSRF block parity
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/api/v1/research/career", "/api/v1/research/content"])
async def test_research_endpoint_refuses_unsafe_url(
    client: AsyncClient, seeded_tenant_user, path,
):
    token, _, _ = seeded_tenant_user
    res = await client.post(
        path, headers={"Authorization": f"Bearer {token}"},
        json={"url": "http://localhost/admin", "goal": "extract"},
    )
    assert res.status_code == 400
    body = res.json()
    detail = body.get("detail", {})
    assert detail.get("code") == "url_safety"


# ──────────────────────────────────────────────────────────────────
# 3. Auth gate
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/api/v1/research/career", "/api/v1/research/content"])
async def test_research_create_requires_founder(client: AsyncClient, path):
    res = await client.post(
        path, json={"url": "https://example.com/", "goal": "x"},
    )
    assert res.status_code in (401, 403)


# ──────────────────────────────────────────────────────────────────
# 4. List + read drafts
# ──────────────────────────────────────────────────────────────────


async def test_list_drafts_filters_by_kind(
    client: AsyncClient, seeded_tenant_user, monkeypatch,
):
    token, _, _ = seeded_tenant_user
    _stub_scrape(monkeypatch, result="Career one")
    await client.post(
        "/api/v1/research/career", headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://jobs.example.com/a", "goal": "extract"},
    )
    _stub_scrape(monkeypatch, result="Content one")
    await client.post(
        "/api/v1/research/content", headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://blog.example.com/a", "goal": "extract"},
    )

    res = await client.get(
        "/api/v1/research/drafts?kind=career",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    drafts = res.json()["drafts"]
    assert len(drafts) >= 1
    assert all(d["kind"] == "career" for d in drafts)


async def test_get_draft_404_for_other_user(
    client: AsyncClient, seeded_tenant_user, db_session, monkeypatch,
):
    """Cross-user isolation: another tenant cannot read this user's draft."""
    token, _, _ = seeded_tenant_user
    _stub_scrape(monkeypatch, result="Mine")
    res = await client.post(
        "/api/v1/research/career", headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://jobs.example.com/x", "goal": "extract"},
    )
    draft_id = res.json()["draft"]["id"]

    # Forge a token for a DIFFERENT user.
    other_tenant = uuid.uuid4()
    other_user = uuid.uuid4()
    db_session.add(Tenant(
        id=other_tenant, name=f"Other {other_tenant.hex[:6]}",
        slug=f"o-{other_tenant.hex[:8]}",
    ))
    await db_session.flush()
    db_session.add(User(
        id=other_user, tenant_id=other_tenant,
        email=f"{other_user.hex[:8]}@o.local",
        password_hash="$2b$12$x" * 4,
        role="FOUNDER", email_verified=True,
    ))
    await db_session.commit()
    other_token = create_access_token(
        user_id=str(other_user), tenant_id=str(other_tenant),
        role="FOUNDER", email="o@o.local", display_name="O",
    )
    res2 = await client.get(
        f"/api/v1/research/drafts/{draft_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert res2.status_code == 404


# ──────────────────────────────────────────────────────────────────
# 5. Schema-level + source-level guards against external dispatch
# ──────────────────────────────────────────────────────────────────


def test_research_draft_model_has_no_send_or_submit_columns():
    """A schema row called sent_at / submitted_at / posted_at would
    imply Daena dispatched the draft externally. The brief explicitly
    forbids that. Pin the column set."""
    cols = {c.name for c in ResearchDraft.__table__.columns}
    forbidden = {
        "sent_at", "submitted_at", "posted_at", "delivered_at",
        "applied_at", "published_at",
    }
    leaked = cols & forbidden
    assert not leaked, f"forbidden columns present: {leaked}"


def test_research_api_source_has_no_send_post_submit_verbs():
    """The API source must contain none of the dispatch-shaped verbs.
    A future PR adding (e.g.) ``POST /research/drafts/{id}/send`` would
    break this test until the brief is amended."""
    src = (
        Path(__file__).resolve().parents[1]
        / "app" / "api" / "v1" / "research.py"
    ).read_text(encoding="utf-8")
    # Defense-grade source-grep: the literal strings would appear in
    # any added send/submit/post endpoint or service call.
    forbidden_paths = (
        "/send", "/submit", "/apply", "/post", "/publish", "/dispatch",
    )
    for path in forbidden_paths:
        assert path not in src, (
            f"forbidden verb path {path!r} present in research.py"
        )
    # No SMTP / requests.post / sendmail / playwright call shape.
    forbidden_calls = (
        "smtplib", "requests.post(", "httpx.post(", "playwright",
        "sendgrid", "gmail.send",
    )
    for call in forbidden_calls:
        assert call not in src, (
            f"forbidden dispatch call {call!r} present in research.py"
        )


def test_research_flow_source_has_no_dispatch_verbs():
    src = (
        Path(__file__).resolve().parents[1]
        / "app" / "services" / "research_flow.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "smtplib", "requests.post(", "httpx.post(", "playwright",
        "send_message", "post_to_", "publish_to_",
    ):
        assert forbidden not in src
