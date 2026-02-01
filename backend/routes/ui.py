"""
backend/routes/ui.py
────────────────────
Serves all frontend HTML pages.
Single source of truth for template → URL mapping.

ACTIVE ROUTES:
  /ui/control-plane   → control_plane_v2.html   (unified VP dashboard)
  /ui/daena-office    → daena_office.html        (chat interface)
  /ui/dashboard       → dashboard.html           (overview widget)
  /                   → redirect → /ui/control-plane

LEGACY REDIRECTS (all point to Control Plane):
  /ui/skills, /ui/execution, /ui/proactive, /ui/tasks,
  /ui/runbook, /ui/approvals, /ui/system-monitor,
  /ui/integrations, /ui/provider-onboarding, /ui/analytics
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from pathlib import Path

router = APIRouter(tags=["ui"], include_in_schema=False)

# ── Template root ──────────────────────────────────────────
TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "templates"


def _read(template_name: str) -> str:
    """Read a template file and return its content."""
    path = TEMPLATES_DIR / template_name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"<h1>Template not found: {template_name}</h1>"


# ── ROOT ────────────────────────────────────────────────────
@router.get("/")
async def root():
    return RedirectResponse(url="/ui/control-plane")


# ── CONTROL PLANE (unified VP dashboard — the main interface) ──
@router.get("/ui/control-plane", response_class=HTMLResponse)
async def control_plane():
    return HTMLResponse(_read("control_plane_v2.html"))


# ── DAENA OFFICE (chat interface) ──────────────────────────
@router.get("/ui/daena-office", response_class=HTMLResponse)
async def daena_office():
    return HTMLResponse(_read("daena_office.html"))


# ── DASHBOARD (overview / landing widget) ─────────────────
@router.get("/ui/dashboard", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(_read("dashboard.html"))


# ── LEGACY REDIRECTS ────────────────────────────────────────
# These pages no longer exist as separate views.
# All their functionality lives inside Control Plane tabs.
# Keeping redirects so any bookmarks or links don't 404.

_LEGACY_ROUTES = [
    "/ui/skills",
    "/ui/execution",
    "/ui/proactive",
    "/ui/tasks",
    "/ui/runbook",
    "/ui/approvals",
    "/ui/system-monitor",
    "/ui/integrations",
    "/ui/provider-onboarding",
    "/ui/analytics",
    "/ui/agents",
    "/ui/councils",
    "/ui/workspace",
    "/ui/incident-room",
    "/ui/control-plane-v1",
    "/control-plane",          # no /ui prefix variant
]

# Map legacy routes to specific Control Plane tab anchors
_TAB_HINTS = {
    "/ui/skills":              "#skills",
    "/ui/execution":           "#governance",
    "/ui/proactive":           "#governance",
    "/ui/tasks":               "#agents",
    "/ui/runbook":             "#governance",
    "/ui/approvals":           "#governance",
    "/ui/system-monitor":      "#agents",
    "/ui/analytics":           "#agents",
    "/ui/agents":              "#agents",
    "/ui/councils":            "#council",
    "/ui/incident-room":       "#shadow",
}


def _make_redirect(path: str):
    hint = _TAB_HINTS.get(path, "")
    async def _redirect():
        return RedirectResponse(url=f"/ui/control-plane{hint}")
    _redirect.__name__ = f"redirect_{path.replace('/', '_')}"
    return _redirect


for _path in _LEGACY_ROUTES:
    router.add_api_route(_path, _make_redirect(_path), methods=["GET"], response_class=RedirectResponse, include_in_schema=False)
