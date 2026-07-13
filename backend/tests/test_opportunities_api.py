"""Sprint-19 PR-2 -- /api/v1/opportunities contract.

Pins:
  1. GET / lists tenant-scoped, score-desc.
  2. GET / filters by status / type, refuses bad enum.
  3. POST /run-discovery executes orchestrator + commits rows.
  4. POST /{id}/archive sets status=archived.
  5. POST /{id}/reject sets status=rejected.
  6. NO /send / /submit / /post / /pay endpoints exist.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    from app.services.business_pipeline import discoverer

    monkeypatch.setattr(
        discoverer, "_SEED_FILE", tmp_path / ".opportunity_seed.json",
    )
    discoverer._reset_for_tests()
    yield


@pytest.fixture
async def seeded(db_session, test_tenant_id, test_user_id):
    from sqlalchemy import delete, select
    from app.models.business import Opportunity
    from app.models.identity import Tenant, User

    # Wipe stale opportunities so tests start with a clean inbox.
    await db_session.execute(
        delete(Opportunity).where(Opportunity.tenant_id == test_tenant_id),
    )
    # Idempotent tenant/user seed.
    existing_tenant = (await db_session.execute(
        select(Tenant).where(Tenant.id == test_tenant_id),
    )).scalar_one_or_none()
    if existing_tenant is None:
        import uuid as _uuid
        tenant = Tenant(
            id=test_tenant_id, name="T",
            slug=f"sprint19-pr2-{_uuid.uuid4().hex[:6]}",
        )
        db_session.add(tenant)
    existing_user = (await db_session.execute(
        select(User).where(User.id == test_user_id),
    )).scalar_one_or_none()
    if existing_user is None:
        user = User(
            id=test_user_id, tenant_id=test_tenant_id,
            email=f"founder-{test_user_id}@test.local",
            password_hash="$argon2id$test$placeholder",
            display_name="Founder", role="FOUNDER",
        )
        db_session.add(user)
    await db_session.flush()
    yield


class TestListEndpoint:
    async def test_empty_initially(
        self, isolated_state, seeded, client, auth_headers,
    ):
        r = await client.get(
            "/api/v1/opportunities/", headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json() == []

    async def test_invalid_status_400(
        self, isolated_state, seeded, client, auth_headers,
    ):
        r = await client.get(
            "/api/v1/opportunities/?status=yolo",
            headers=auth_headers,
        )
        assert r.status_code == 400

    async def test_invalid_type_400(
        self, isolated_state, seeded, client, auth_headers,
    ):
        r = await client.get(
            "/api/v1/opportunities/?type=send_money_now",
            headers=auth_headers,
        )
        assert r.status_code == 400


class TestRunDiscovery:
    async def test_seeded_file_creates_rows(
        self, isolated_state, seeded, client, auth_headers,
    ):
        import json
        from app.services.business_pipeline import discoverer

        discoverer._SEED_FILE.write_text(json.dumps([
            {
                "type": "grant",
                "title": "MAS-AI grant 2026",
                "source_name": "manual_seed",
                "estimated_value_usd": 25000,
                "effort_hours": 8,
            },
            {
                "type": "hackathon",
                "title": "Devpost",
                "source_name": "manual_seed",
            },
        ]))

        r = await client.post(
            "/api/v1/opportunities/run-discovery",
            json={"top_n": 10},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["discovered_count"] == 2
        assert data["persisted_count"] == 2
        assert "manual_seed" in data["sources_queried"]

        # And listing now shows them
        listing = await client.get(
            "/api/v1/opportunities/", headers=auth_headers,
        )
        rows = listing.json()
        assert len(rows) == 2
        # Score-desc -- the grant scores higher than hackathon
        assert rows[0]["type"] == "grant"


class TestStatusMutations:
    async def test_archive_and_reject(
        self, isolated_state, seeded, client, auth_headers,
    ):
        import json
        import uuid as _uuid
        from app.services.business_pipeline import discoverer

        # Unique titles per test invocation so we can find them in
        # a list that may carry rows from other tests.
        u = _uuid.uuid4().hex[:6]
        t1 = f"archive-test-{u}-a"
        t2 = f"archive-test-{u}-b"
        discoverer._SEED_FILE.write_text(json.dumps([
            {"type": "grant", "title": t1, "source_name": "manual_seed"},
            {"type": "grant", "title": t2, "source_name": "manual_seed"},
        ]))
        await client.post(
            "/api/v1/opportunities/run-discovery", json={"top_n": 10},
            headers=auth_headers,
        )
        rows = (await client.get(
            "/api/v1/opportunities/", headers=auth_headers,
        )).json()
        ours = [r for r in rows if r["title"] in (t1, t2)]
        assert len(ours) == 2
        a, b = ours[0]["id"], ours[1]["id"]

        archive_resp = await client.post(
            f"/api/v1/opportunities/{a}/archive", headers=auth_headers,
        )
        assert archive_resp.status_code == 200
        assert archive_resp.json()["status"] == "archived"

        reject_resp = await client.post(
            f"/api/v1/opportunities/{b}/reject", headers=auth_headers,
        )
        assert reject_resp.status_code == 200
        assert reject_resp.json()["status"] == "rejected"

    async def test_invalid_uuid_400(
        self, isolated_state, seeded, client, auth_headers,
    ):
        r = await client.post(
            "/api/v1/opportunities/not-a-uuid/archive",
            headers=auth_headers,
        )
        assert r.status_code == 400


class TestValidateEndpoint:
    """Phase-4 Venture Studio: deterministic validation surface.

    The endpoint runs the checklist, persists the score, and surfaces
    the advisory GO / REVIEW / NO-GO verdict WITHOUT promoting or
    changing status. The human still owns the final GO/NO-GO.
    """

    async def test_validate_scores_and_surfaces(
        self, isolated_state, seeded, client, auth_headers,
    ):
        import json
        import uuid as _uuid
        from app.services.business_pipeline import discoverer

        u = _uuid.uuid4().hex[:6]
        title = f"validate-test-{u}"
        # A well-formed idea: hits every checklist item so the verdict
        # lands on the GO side (score >= 70).
        discoverer._SEED_FILE.write_text(json.dumps([
            {
                "type": "startup_idea",
                "title": title,
                "description": (
                    "Founders lose hours reconciling scattered brand "
                    "assets across five SaaS tools before every launch."
                ),
                "source_name": "manual_seed",
                "source_url": "https://news.ycombinator.com/item?id=1",
                "estimated_value_usd": 120000,
                "effort_hours": 40,
                "risk_label": "medium",
                "next_action": "Interview 5 design-ops leads this week.",
            },
        ]))
        await client.post(
            "/api/v1/opportunities/run-discovery", json={"top_n": 10},
            headers=auth_headers,
        )
        rows = (await client.get(
            "/api/v1/opportunities/", headers=auth_headers,
        )).json()
        ours = [r for r in rows if r["title"] == title]
        assert len(ours) == 1
        oid = ours[0]["id"]
        # Not yet validated -- the inbox exposes the key as null.
        assert ours[0]["validation"] is None

        resp = await client.post(
            f"/api/v1/opportunities/{oid}/validate", headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        # Validation ran and did NOT promote or change status.
        assert body["status"] == "discovered"
        v = body["validation"]
        assert v is not None
        assert isinstance(v["score"], int)
        assert 0 <= v["score"] <= 100
        assert v["verdict"] in ("go", "review", "no_go")
        assert v["score"] >= 70
        assert v["verdict"] == "go"
        # Seven weighted checks, each with a pass/fail flag.
        assert len(v["checks"]) == 7
        assert all("passed" in c and "weight" in c for c in v["checks"])
        assert v["validated_at"] is not None

        # The persisted score is now visible on the list endpoint too.
        after = (await client.get(
            "/api/v1/opportunities/", headers=auth_headers,
        )).json()
        mine = [r for r in after if r["id"] == oid]
        assert len(mine) == 1
        assert mine[0]["validation"] is not None
        assert mine[0]["validation"]["score"] == v["score"]

    async def test_validate_thin_idea_scores_low(
        self, isolated_state, seeded, client, auth_headers,
    ):
        import json
        import uuid as _uuid
        from app.services.business_pipeline import discoverer

        u = _uuid.uuid4().hex[:6]
        title = f"validate-thin-{u}"
        # A bare idea: only a title. The checklist has little to reward,
        # so the deterministic verdict must NOT be an unearned GO.
        discoverer._SEED_FILE.write_text(json.dumps([
            {
                "type": "startup_idea",
                "title": title,
                "source_name": "manual_seed",
            },
        ]))
        await client.post(
            "/api/v1/opportunities/run-discovery", json={"top_n": 10},
            headers=auth_headers,
        )
        rows = (await client.get(
            "/api/v1/opportunities/", headers=auth_headers,
        )).json()
        oid = next(r["id"] for r in rows if r["title"] == title)

        resp = await client.post(
            f"/api/v1/opportunities/{oid}/validate", headers=auth_headers,
        )
        assert resp.status_code == 200
        v = resp.json()["validation"]
        assert v["verdict"] != "go"
        assert v["score"] < 70

    async def test_validate_bad_uuid_400(
        self, isolated_state, seeded, client, auth_headers,
    ):
        r = await client.post(
            "/api/v1/opportunities/not-a-uuid/validate",
            headers=auth_headers,
        )
        assert r.status_code == 400

    async def test_validate_missing_404(
        self, isolated_state, seeded, client, auth_headers,
    ):
        import uuid as _uuid

        r = await client.post(
            f"/api/v1/opportunities/{_uuid.uuid4()}/validate",
            headers=auth_headers,
        )
        assert r.status_code == 404


class TestNoForbiddenEndpoints:
    async def test_no_send_submit_post_pay_routes(
        self, isolated_state, seeded, client, auth_headers,
    ):
        for verb in ("send", "submit", "post-form", "pay"):
            r = await client.post(
                f"/api/v1/opportunities/{verb}",
                json={},
                headers=auth_headers,
            )
            # 404 (route doesn't exist) or 405 (no POST handler)
            # is the only acceptable response. NEVER 200.
            assert r.status_code in (404, 405)
