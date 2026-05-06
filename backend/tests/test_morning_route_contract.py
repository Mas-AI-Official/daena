"""Sprint-MORNING PR-2 -- route contract test.

Pins the exact paths the frontend WorkstreamsPage.DraftActions now
calls. If any of these route names drift, the buttons would silently
404; this test catches that at CI time.

Endpoints under contract:
  POST /api/v1/research/drafts/{draft_id}/enrich
  POST /api/v1/research/drafts/{draft_id}/qe-review
  POST /api/v1/form-drafts/{draft_id}/enrich
  POST /api/v1/form-drafts/{draft_id}/qe-review
  POST /api/v1/workstreams/from-draft
  POST /api/v1/vp-commands

Plus the readiness routes BrainReadinessPanel reads:
  GET  /api/v1/system/runtime-readiness
  GET  /api/v1/system/router-readiness
  GET  /api/v1/system/qe-readiness
  GET  /api/v1/system/router-policy
"""

from __future__ import annotations

import pytest


def _v1_paths():
    from app.api.v1 import router as api_v1_router
    return [getattr(r, "path", "") for r in api_v1_router.routes]


_ACTION_PATHS = (
    ("POST", "/research/drafts/{draft_id}/enrich"),
    ("POST", "/research/drafts/{draft_id}/qe-review"),
    ("POST", "/form-drafts/{draft_id}/enrich"),
    ("POST", "/form-drafts/{draft_id}/qe-review"),
    ("POST", "/workstreams/from-draft"),
    ("POST", "/vp-commands"),
)

_READINESS_PATHS = (
    "/system/runtime-readiness",
    "/system/router-readiness",
    "/system/qe-readiness",
    "/system/router-policy",
)


@pytest.mark.parametrize("method,path", _ACTION_PATHS)
def test_action_routes_mounted(method, path):
    paths = _v1_paths()
    assert path in paths, (
        f"frontend depends on {method} {path} but it is not mounted"
    )


@pytest.mark.parametrize("path", _READINESS_PATHS)
def test_readiness_routes_mounted(path):
    paths = _v1_paths()
    assert path in paths, (
        f"BrainReadinessPanel depends on GET {path} but it is not mounted"
    )


def test_no_banned_verbs_on_workstreams():
    """No /workstreams/.../send /submit /apply /post /publish endpoints."""
    paths = _v1_paths()
    bad = [
        p for p in paths
        if p.startswith("/workstreams")
        and any(v in p for v in ("/send", "/submit", "/apply", "/publish"))
    ]
    assert bad == [], f"banned verb route under /workstreams: {bad}"


def test_no_banned_verbs_on_research_drafts():
    paths = _v1_paths()
    bad = [
        p for p in paths
        if p.startswith("/research/drafts")
        and any(v in p for v in ("/send", "/submit", "/apply", "/publish", "/dispatch"))
    ]
    assert bad == [], f"banned verb route under /research/drafts: {bad}"


def test_no_banned_verbs_on_form_drafts():
    paths = _v1_paths()
    bad = [
        p for p in paths
        if p.startswith("/form-drafts")
        and any(v in p for v in ("/send", "/submit", "/publish", "/dispatch"))
    ]
    # /form-drafts itself is a noun and the words "send/submit/publish/dispatch"
    # must never appear as path verbs underneath it.
    assert bad == [], f"banned verb route under /form-drafts: {bad}"
