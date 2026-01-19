"""
HTMX/HTML UI routes (NO React/Node).

Required pages:
- /ui/dashboard
- /ui/departments
- /ui/agents
- /ui/council
- /ui/memory
- /ui/health
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import logging

from backend.config.settings import get_settings
settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(tags=["ui"], include_in_schema=False)

# Templates live in frontend/templates
project_root = Path(__file__).parent.parent.parent
templates_dir = project_root / "frontend" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def _ctx(request: Request) -> dict:
    return {
        "request": request,
        "disable_auth": getattr(settings, "disable_auth", False),
        "dev_founder_name": getattr(settings, "dev_founder_name", "Masoud"),
    }


@router.get("/ui", include_in_schema=False)
async def ui_root():
    return RedirectResponse(url="/ui/dashboard", status_code=302)


@router.get("/ui/dashboard", response_class=HTMLResponse)
async def ui_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", _ctx(request))


@router.get("/ui/departments", response_class=HTMLResponse)
async def ui_departments(request: Request):
    # Wrapped HTMX page (includes departments fragment in a layout shell)
    return templates.TemplateResponse("ui_departments.html", _ctx(request))


@router.get("/ui/department/{slug}", response_class=HTMLResponse)
async def ui_department_slug(request: Request, slug: str):
    """
    Department office pages - use generic template with department data
    """
    try:
        from backend.utils.sunflower_registry import sunflower_registry
        
        # Get department data
        dept_data = sunflower_registry.get_department_by_id(slug)
        if not dept_data:
            return RedirectResponse(url="/ui/departments", status_code=302)
        
        # Get department icon and color
        dept_icons = {
            'engineering': 'fas fa-cog',
            'product': 'fas fa-rocket',
            'sales': 'fas fa-dollar-sign',
            'marketing': 'fas fa-bullhorn',
            'finance': 'fas fa-chart-line',
            'hr': 'fas fa-users',
            'legal': 'fas fa-gavel',
            'customer': 'fas fa-headset'
        }
        
        context = _ctx(request)
        context.update({
            'department': {
                'id': dept_data.get('id', slug),
                'name': dept_data.get('name', slug.title()),
                'description': dept_data.get('description', ''),
                'color': dept_data.get('color', '#0066cc'),
                'icon': dept_icons.get(slug, 'fas fa-building'),
                'agentCount': len(dept_data.get('agents', []))
            }
        })
        
        return templates.TemplateResponse("department_base.html", context)
    except Exception as e:
        logger.error(f"Error loading department {slug}: {e}")
        return RedirectResponse(url="/ui/departments", status_code=302)


@router.get("/ui/agents", response_class=HTMLResponse)
async def ui_agents(request: Request):
    return templates.TemplateResponse("agents.html", _ctx(request))


@router.get("/ui/agents/{agent_id}/configure", response_class=HTMLResponse)
async def ui_agent_configure(request: Request, agent_id: str):
    """Agent configuration page"""
    context = _ctx(request)
    context["agent_id"] = agent_id
    return templates.TemplateResponse("agent_config.html", context)


@router.get("/ui/workspace", response_class=HTMLResponse)
async def ui_workspace(request: Request):
    """Workspace page - file tree, preview, attach to chat"""
    return templates.TemplateResponse("workspace.html", _ctx(request))


@router.get("/ui/council", include_in_schema=False)
async def ui_council():
    return RedirectResponse(url="/ui/council-dashboard", status_code=302)


@router.get("/ui/council-dashboard", response_class=HTMLResponse)
async def ui_council_dashboard(request: Request):
    return templates.TemplateResponse("council_dashboard.html", _ctx(request))


@router.get("/ui/memory", response_class=HTMLResponse)
async def ui_memory(request: Request):
    # Best existing "memory" equivalent in this baseline
    return templates.TemplateResponse("honey_tracker.html", _ctx(request))


@router.get("/ui/health", response_class=HTMLResponse)
async def ui_health(request: Request):
    # Richest existing health/metrics UI
    return templates.TemplateResponse("enhanced_dashboard.html", _ctx(request))


# ---------------------------------------------------------------------------
# Additional UI pages (aliases) — keep everything under /ui/*
# ---------------------------------------------------------------------------

@router.get("/ui/enhanced-dashboard", response_class=HTMLResponse)
async def ui_enhanced_dashboard(request: Request):
    return templates.TemplateResponse("enhanced_dashboard.html", _ctx(request))


@router.get("/ui/daena-office", response_class=HTMLResponse)
async def ui_daena_office(request: Request):
    return templates.TemplateResponse("daena_office.html", _ctx(request))


@router.get("/ui/founder-panel", response_class=HTMLResponse)
async def ui_founder_panel(request: Request):
    return templates.TemplateResponse("founder_panel.html", _ctx(request))


@router.get("/ui/strategic-room", response_class=HTMLResponse)
async def ui_strategic_room(request: Request):
    return templates.TemplateResponse("strategic_room.html", _ctx(request))


@router.get("/ui/strategic-meetings", response_class=HTMLResponse)
async def ui_strategic_meetings(request: Request):
    return templates.TemplateResponse("strategic_meetings.html", _ctx(request))


@router.get("/ui/task-timeline", response_class=HTMLResponse)
async def ui_task_timeline(request: Request):
    return templates.TemplateResponse("task_timeline.html", _ctx(request))


@router.get("/ui/command-center", response_class=HTMLResponse)
async def ui_command_center(request: Request):
    return templates.TemplateResponse("daena_command_center.html", _ctx(request))


@router.get("/ui/analytics", response_class=HTMLResponse)
async def ui_analytics(request: Request):
    return templates.TemplateResponse("analytics.html", _ctx(request))


@router.get("/ui/voice-panel", response_class=HTMLResponse)
async def ui_voice_panel(request: Request):
    return templates.TemplateResponse("voice_panel.html", _ctx(request))

@router.get("/ui/system-monitor", response_class=HTMLResponse)
async def ui_system_monitor(request: Request):
    """System monitoring dashboard showing all backend capabilities"""
    return templates.TemplateResponse("system_monitor.html", _ctx(request))


@router.get("/ui/files", response_class=HTMLResponse)
async def ui_files(request: Request):
    return templates.TemplateResponse("files.html", _ctx(request))


@router.get("/ui/conference-room", response_class=HTMLResponse)
async def ui_conference_room(request: Request):
    return templates.TemplateResponse("conference_room.html", _ctx(request))


@router.get("/ui/cmp-voting", response_class=HTMLResponse)
async def ui_cmp_voting(request: Request):
    return templates.TemplateResponse("cmp_voting.html", _ctx(request))


@router.get("/ui/council-debate", response_class=HTMLResponse)
async def ui_council_debate(request: Request):
    return templates.TemplateResponse("council_debate.html", _ctx(request))


@router.get("/ui/council-synthesis", response_class=HTMLResponse)
async def ui_council_synthesis(request: Request):
    return templates.TemplateResponse("council_synthesis.html", _ctx(request))


@router.get("/ui/operator", response_class=HTMLResponse)
async def ui_operator(request: Request):
    """Operator tools page"""
    return templates.TemplateResponse("operator.html", _ctx(request))



@router.get("/ui/connections", response_class=HTMLResponse)
async def ui_connections(request: Request):
    """Service Connections page (Phase 4)"""
    return templates.TemplateResponse("connections.html", _ctx(request))


@router.get("/ui/department/{dept_id}", response_class=HTMLResponse)
async def ui_department_detail(request: Request, dept_id: str):
    """Department detail page"""
    context = _ctx(request)
    context["dept_id"] = dept_id
    return templates.TemplateResponse("ui_departments.html", context)

