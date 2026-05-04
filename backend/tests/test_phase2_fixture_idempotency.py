"""PR-CONN-PHASE2-FLAKE-CLEANUP (Sprint-7 PR-6) test.

Pins the idempotent-fixture contract for ``seeded_jwt_user`` in
``test_skill_executor_phase2.py``. The fixture must:

  1. Probe the database for the (tenant_id, user_id) before INSERT.
  2. Skip the INSERT when the row already exists (this is what
     prevents the UNIQUE-constraint flake when other tests commit
     the same shared test_tenant_id earlier in the suite).

This is a SOURCE-LEVEL pin because the integration "did the flake
go away?" check would itself be flaky (it depends on test ordering).
A static check that the fixture's body contains the probe-then-insert
shape catches any future regression where someone removes the
idempotency.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_EXEC_TESTS = REPO_ROOT / "tests" / "test_skill_executor_phase2.py"


def test_seeded_jwt_user_fixture_is_idempotent():
    src = SKILL_EXEC_TESTS.read_text(encoding="utf-8")
    # The fixture must call select().where(Tenant.id == test_tenant_id)
    # AND check scalar_one_or_none() before adding the row.
    fixture_idx = src.index("async def seeded_jwt_user")
    fixture_end = src.index("@pytest.mark", fixture_idx)
    fixture_body = src[fixture_idx:fixture_end]

    assert "scalar_one_or_none()" in fixture_body, (
        "seeded_jwt_user must probe scalar_one_or_none() before insert"
    )
    assert "select(Tenant)" in fixture_body, (
        "seeded_jwt_user must SELECT Tenant before deciding to INSERT"
    )
    assert "select(User)" in fixture_body, (
        "seeded_jwt_user must SELECT User before deciding to INSERT"
    )
    # Both inserts must be guarded by `if ... is None`.
    none_guards = fixture_body.count("is None")
    assert none_guards >= 2, (
        f"seeded_jwt_user must guard BOTH inserts with `is None`; "
        f"found {none_guards} guards in fixture body"
    )
