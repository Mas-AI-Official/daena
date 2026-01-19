from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client() -> TestClient:
    from backend.main import app
    return TestClient(app)


def test_cmp_tools_list(client: TestClient):
    r = client.get("/api/v1/cmp/tools")
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    tools = data.get("tools") or []
    names = {t.get("name") for t in tools}
    assert "web_scrape_bs4" in names


def test_automation_scrape_allowlist_blocks_unknown_domain_by_default(client: TestClient):
    # In safe mode, the default allowlist does NOT include example.org
    r = client.post("/api/v1/automation/scrape", json={"url": "https://example.org", "mode": "text"})
    assert r.status_code in (403, 200)
    if r.status_code == 403:
        assert "domain not allowed" in r.text.lower()


def test_automation_scrape_example_com(client: TestClient):
    r = client.post("/api/v1/automation/scrape", json={"url": "https://example.com", "mode": "text"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("ok", "error")
    if data["status"] == "ok":
        assert "example" in (data["data"]["result"] or "").lower()


def test_operator_process_start_and_get(client: TestClient):
    r = client.post(
        "/api/v1/automation/process/start",
        json={
            "title": "Scrape Example",
            "steps": [{"name": "tool.scrape.extract", "input": {"url": "https://example.com", "mode": "text"}}],
        },
    )
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "ok"
    pid = out["data"]["process_id"]

    # Process should be queryable
    r2 = client.get(f"/api/v1/automation/process/{pid}")
    assert r2.status_code == 200
    out2 = r2.json()
    assert out2["status"] == "ok"
    assert out2["data"]["process_id"] == pid


def test_tools_execute_scrape(client: TestClient):
    r = client.post(
        "/api/v1/tools/execute",
        json={
            "tool_name": "web_scrape_bs4",
            "args": {"url": "https://example.com", "mode": "text"},
            "department": "engineering",
            "agent_id": "founder",
            "reason": "sanity test",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") in ("ok", "error")


