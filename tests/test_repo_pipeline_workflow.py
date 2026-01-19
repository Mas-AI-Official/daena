"""
Repo Pipeline + Workflow Sanity Tests (NO-AUTH, HTMX-only)

Goals:
- Catch syntax errors across backend Python files
- Catch Jinja template load/render errors across frontend templates
- Ensure core /ui pages return 200 in no-auth mode
- Exercise an end-to-end "Founder request" workflow via Daena chat endpoints
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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
    # Import inside fixture so failing imports are caught as test failures.
    from backend.main import app as fastapi_app

    return fastapi_app


@pytest.fixture(scope="session")
def client(app) -> TestClient:
    return TestClient(app)


def test_python_files_compile():
    """
    Compile (syntax-check) key Python trees without importing everything.
    This catches SyntaxError/IndentationError that would break deployments.
    """

    root = _repo_root()
    targets = [
        root / "backend",
        root / "memory_service",
        root / "self_evolve",
    ]

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


def test_templates_load_and_render():
    """
    Load and render every HTML template once to catch:
    - Jinja syntax errors
    - missing includes
    - undefined variables in layout-level shared components
    """

    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    root = _repo_root()
    templates_dir = root / "frontend" / "templates"
    assert templates_dir.exists()

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=True,
        undefined=StrictUndefined,  # fail fast on missing context
    )

    ctx: Dict[str, Any] = {
        "request": _make_starlette_request(),
        "disable_auth": True,
        "dev_founder_name": "Dev Founder",
    }

    failed = []
    for tpl in templates_dir.rglob("*.html"):
        rel = tpl.relative_to(templates_dir).as_posix()

        # Skip login template entirely (not used in no-auth mode).
        if rel == "login.html":
            continue

        try:
            template = env.get_template(rel)
            _ = template.render(**ctx)
        except Exception as e:
            failed.append((rel, repr(e)))

    assert not failed, "Template render failures:\n" + "\n".join([f"- {t}: {err}" for t, err in failed])


def test_ui_pages_ok(client: TestClient):
    """
    Required HTMX pages must work in no-auth mode.
    """

    required = [
        "/ui/dashboard",
        "/ui/departments",
        "/ui/agents",
        "/ui/council",
        "/ui/memory",
        "/ui/health",
    ]
    for path in required:
        r = client.get(path, allow_redirects=True)
        assert r.status_code == 200, f"{path} -> {r.status_code}"


def test_structure_and_registry_ok(client: TestClient):
    """
    Ensure the 8×6 structure and registry endpoints are healthy.
    """

    r = client.get("/api/v1/structure/verify")
    assert r.status_code == 200
    data = r.json()
    # Accept a few possible shapes, but require "valid" if present.
    if isinstance(data, dict) and "valid" in data:
        assert data["valid"] is True

    r = client.get("/api/v1/registry/summary")
    assert r.status_code == 200
    summary = r.json()
    assert isinstance(summary, dict)


def test_founder_workflow_build_vibeagent_app(client: TestClient):
    """
    Simulate a founder request that should route through Daena brain and produce a structured plan
    that references departments/agents (coordination).
    """

    prompt = "Build vibeagent app. Give departments orders and execution steps."

    # Prefer legacy-compatible endpoint used by UI templates
    endpoints = [
        "/api/v1/daena/chat",
        "/api/v1/chat",
    ]

    last = None
    for ep in endpoints:
        r = client.post(ep, json={"message": prompt})
        if r.status_code == 200:
            last = r
            break
    assert last is not None, "No chat endpoint responded successfully"

    payload = last.json() if "application/json" in last.headers.get("content-type", "") else {"text": last.text}
    text = (
        payload.get("response")
        or payload.get("answer")
        or payload.get("message")
        or payload.get("text")
        or ""
    )
    assert isinstance(text, str) and len(text.strip()) > 0

    # Minimal expectation: mention coordination / departments / plan.
    low = text.lower()
    assert any(k in low for k in ["department", "engineering", "product", "sales", "plan", "steps"]), text











