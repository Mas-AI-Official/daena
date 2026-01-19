"""
Sanity Pipeline + Workflow Tests (NO-AUTH, HTMX-only)

This suite is intentionally small and stable.
It is meant to be the default `pytest` suite for local development.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _make_starlette_request(path: str = "/ui/dashboard"):
    from starlette.requests import Request

    scope = {
        "type": "http",
        "asgi": {"spec_version": "2.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [],
        "client": ("testclient", 123),
        "server": ("testserver", 80),
    }
    return Request(scope)


@pytest.fixture(scope="session")
def app():
    from backend.main import app as fastapi_app
    return fastapi_app


@pytest.fixture(scope="session")
def client(app) -> TestClient:
    return TestClient(app)


def test_python_files_compile():
    root = _repo_root()
    targets = [root / "backend", root / "memory_service"]

    bad = []
    for base in targets:
        if not base.exists():
            continue
        for py in base.rglob("*.py"):
            try:
                code = py.read_text(encoding="utf-8")
                compile(code, str(py), "exec")
            except Exception as e:
                bad.append((str(py), repr(e)))

    assert not bad, "Python compile errors:\n" + "\n".join([f"- {p}: {err}" for p, err in bad])


def test_templates_load():
    """
    Load each template to ensure there are no Jinja syntax/include errors.
    (We don't enforce StrictUndefined because many templates are pure HTML pages.)
    """
    from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError, TemplateNotFound

    root = _repo_root()
    templates_dir = root / "frontend" / "templates"
    assert templates_dir.exists()

    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)
    failed = []
    for tpl in templates_dir.rglob("*.html"):
        rel = tpl.relative_to(templates_dir).as_posix()
        if rel == "login.html":
            continue
        try:
            # Only load/compile templates; do not render (many partials require runtime context)
            _ = env.get_template(rel)
        except (TemplateSyntaxError, TemplateNotFound) as e:
            failed.append((rel, repr(e)))

    assert not failed, "Template failures:\n" + "\n".join([f"- {t}: {err}" for t, err in failed])


def test_required_ui_pages_ok(client: TestClient):
    """
    Verification checklist: all /ui/* pages must return 200 with DISABLE_AUTH=1.
    """
    required = [
        "/ui/dashboard",
        "/ui/departments",
        "/ui/agents",
        "/ui/council",
        "/ui/memory",
        "/ui/health",
    ]
    failures = []
    for path in required:
        r = client.get(path, follow_redirects=True)
        if r.status_code != 200:
            failures.append(f"{path} -> {r.status_code}")
    assert not failures, "UI pages failed:\n" + "\n".join(failures)


def test_registry_and_structure_ok(client: TestClient):
    r = client.get("/api/v1/structure/verify")
    assert r.status_code == 200

    r = client.get("/api/v1/registry/summary")
    assert r.status_code == 200


def test_api_agents_and_departments_work_no_auth(client: TestClient):
    r = client.get("/api/v1/agents/?limit=10")
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    assert isinstance(data.get("agents"), list)
    assert len(data["agents"]) > 0

    r = client.get("/api/v1/departments/?limit=20")
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    assert isinstance(data.get("departments"), list)
    assert len(data["departments"]) >= 8


def test_founder_workflow_build_vibeagent_app(client: TestClient):
    """
    Verification: POST /api/v1/daena/chat must route through canonical Daena brain
    and return a text response (no mocks, no dead endpoints).
    """
    prompt = "Build vibeagent app. Give departments orders and execution steps."
    r = client.post("/api/v1/daena/chat", json={"message": prompt})
    assert r.status_code == 200, f"Daena chat endpoint returned {r.status_code}"
    data = r.json()
    assert isinstance(data.get("response"), str) and data["response"].strip(), "Daena must return non-empty text"
    low = data["response"].lower()
    assert any(k in low for k in ["department", "engineering", "product", "plan", "steps"]), f"Response too generic: {data['response'][:200]}"


