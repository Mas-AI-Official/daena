"""Pins the founder auto-seed so Masoud can always log in after restart.

Runs the ``_seed_founder_accounts`` function with a monkey-patched
``async_session_factory`` that yields the test db_session. Verifies:

* Both FOUNDER_EMAIL and FOUNDER_PERSONAL_EMAIL get User rows.
* Role is FOUNDER on both.
* terms_accepted_at is set (founder authored the terms).
* A tenant is created with the configured slug (idempotent: second
  run does not duplicate).
* Missing FOUNDER_DEFAULT_PASSWORD skips silently (no-op).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select

from app.main import _seed_founder_accounts
from app.models.identity import Tenant, User


@pytest.mark.asyncio
async def test_founder_seed_creates_both_accounts(db_session, monkeypatch) -> None:
    from app.core.config import get_settings
    settings = get_settings()
    # Make sure the .env-configured values are present for this test.
    monkeypatch.setattr(settings, "founder_email", "founder-primary@mas-ai.co")
    monkeypatch.setattr(settings, "founder_personal_email", "founder-personal@example.com")
    monkeypatch.setattr(settings, "founder_default_password", "Daena-Test-Pass-2026!")
    monkeypatch.setattr(settings, "founder_tenant_name", "Test MAS-AI")

    # Bypass async_session_factory so the seed writes to the test db.
    @asynccontextmanager
    async def _fake_factory():
        yield db_session

    monkeypatch.setattr(
        "app.core.database.async_session_factory", _fake_factory,
    )

    await _seed_founder_accounts()

    users = (await db_session.execute(
        select(User).where(User.email.in_([
            "founder-primary@mas-ai.co",
            "founder-personal@example.com",
        ]))
    )).scalars().all()
    assert len(users) == 2
    for u in users:
        assert u.role == "FOUNDER"
        assert u.terms_accepted_at is not None
        assert u.password_hash  # hashed, not stored raw
        assert u.email_verified is True

    # Tenant exists with the expected slug.
    tenant = (await db_session.execute(
        select(Tenant).where(Tenant.slug == "test-mas-ai")
    )).scalar_one_or_none()
    assert tenant is not None


@pytest.mark.asyncio
async def test_founder_seed_is_idempotent(db_session, monkeypatch) -> None:
    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "founder_email", "founder-idem@mas-ai.co")
    monkeypatch.setattr(settings, "founder_personal_email", "")
    monkeypatch.setattr(settings, "founder_default_password", "test-pass")
    monkeypatch.setattr(settings, "founder_tenant_name", "Idem MAS-AI")

    @asynccontextmanager
    async def _fake_factory():
        yield db_session

    monkeypatch.setattr(
        "app.core.database.async_session_factory", _fake_factory,
    )

    await _seed_founder_accounts()
    await _seed_founder_accounts()  # second call must not duplicate

    users = (await db_session.execute(
        select(User).where(User.email == "founder-idem@mas-ai.co")
    )).scalars().all()
    assert len(users) == 1


@pytest.mark.asyncio
async def test_founder_seed_skips_when_password_missing(db_session, monkeypatch) -> None:
    """No-op when FOUNDER_DEFAULT_PASSWORD is empty."""
    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "founder_email", "founder-skip@mas-ai.co")
    monkeypatch.setattr(settings, "founder_personal_email", "")
    monkeypatch.setattr(settings, "founder_default_password", "")  # empty
    monkeypatch.setattr(settings, "founder_tenant_name", "Skip MAS-AI")

    @asynccontextmanager
    async def _fake_factory():
        yield db_session

    monkeypatch.setattr(
        "app.core.database.async_session_factory", _fake_factory,
    )

    await _seed_founder_accounts()

    users = (await db_session.execute(
        select(User).where(User.email == "founder-skip@mas-ai.co")
    )).scalars().all()
    assert len(users) == 0
