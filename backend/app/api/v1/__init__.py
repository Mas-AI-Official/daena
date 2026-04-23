"""API v1 router — aggregates all domain routers.

Each domain module defines its own APIRouter, which is
included here under the /api/v1 prefix.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    agent_ops,
    agents,
    analytics,
    api_keys,
    auth,
    autopilot,
    benchmark,
    billing,
    bridge,
    chat,
    company_mode,
    connections,
    connector_oauth,
    daenabot,
    department_budget,
    department_messages,
    department_policies,
    department_states,
    dynamic_models,
    engagements,
    execution,
    files,
    founder,
    governance,
    health,
    heartbeat,
    integrations,
    mcp_server,
    mcp_sync,
    memory,
    missions,
    mobile,
    org,
    pipeline,
    projects,
    prompts,
    runtimes,
    security_authorized_scope,
    security_dashboard,
    security_mode,
    self_improvement,
    settings,
    skill_refinery,
    skills,
    souls,
    tts,
    voice_ws,
    waitlist,
    ws,
)

router = APIRouter()

# Include sub-routers
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
router.include_router(billing.router, prefix="/billing", tags=["billing"])
router.include_router(health.router, prefix="/health", tags=["health"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(governance.router, prefix="/governance", tags=["governance"])
router.include_router(founder.router, prefix="/founder", tags=["founder"])
router.include_router(memory.router, prefix="/memory", tags=["memory"])
router.include_router(execution.router, prefix="/execution", tags=["execution"])
router.include_router(daenabot.router, prefix="/daenabot", tags=["daenabot"])
router.include_router(department_budget.router, prefix="/department-budget", tags=["department-budget"])
router.include_router(department_states.router, prefix="/department-states", tags=["department-states"])
router.include_router(department_messages.router, prefix="/department-messages", tags=["department-messages"])
router.include_router(department_policies.router, prefix="/department-policies", tags=["department-policies"])
router.include_router(skills.router, prefix="/skills", tags=["skills"])
router.include_router(skill_refinery.router, prefix="/skills/refinery", tags=["skill-refinery"])
# Department Minds (souls) -- persona overlays for the 10 departments +
# founder-gated refinement pipeline (/souls list/get, /souls/{dept}/refine,
# /souls/proposals/{id}/approve|reject). Mounted BEFORE /security so the
# path tree matches the frontend router exactly.
router.include_router(souls.router, tags=["souls"])
# Company Mode -- founder activates Daena as an AI marketing+sales agency
# from a brief (ICP / pain / promise / channels). Spawns Sales + Marketing
# missions; outbound drafts land in approval queue unless auto_send is set.
router.include_router(company_mode.router, prefix="/company-mode", tags=["company-mode"])
router.include_router(connections.router, prefix="/connections", tags=["connections"])
router.include_router(dynamic_models.router, prefix="/dynamic-models", tags=["dynamic-models"])
router.include_router(settings.router, prefix="/settings", tags=["settings"])
router.include_router(autopilot.router, prefix="/autopilot", tags=["autopilot"])
router.include_router(mcp_server.router, prefix="/mcp", tags=["mcp"])
router.include_router(mcp_sync.router, prefix="/mcp-sync", tags=["mcp-sync"])
# approval_dashboard removed -- dead code (in-memory duplicate of governance/approvals).
# Archived to .archive/dead_approval_queue/. Real approvals live at /governance/approvals.
router.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])
router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
router.include_router(runtimes.router, prefix="/runtimes", tags=["runtimes"])
router.include_router(heartbeat.router, prefix="/heartbeat", tags=["heartbeat"])
router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
router.include_router(connector_oauth.router, tags=["connector-oauth"])
router.include_router(bridge.router, tags=["bridge"])
router.include_router(self_improvement.router, prefix="/self-improvement", tags=["self-improvement"])
router.include_router(waitlist.router, prefix="/waitlist", tags=["waitlist"])
router.include_router(mobile.router)
router.include_router(benchmark.router)
router.include_router(files.router, prefix="/files", tags=["files"])
router.include_router(api_keys.router, prefix="/api-keys", tags=["api-keys"])
router.include_router(org.router, prefix="/org", tags=["org"])
router.include_router(security_dashboard.router, prefix="/security", tags=["security-dashboard"])
# Note: authorized_scope router is NOT mounted under /security prefix
# because its paths already start with /security/authorized-scope.
# Mounting under / keeps the paths as declared in the file.
router.include_router(security_authorized_scope.router, tags=["security-authorized-scope"])
router.include_router(tts.router, prefix="/tts", tags=["tts"])
router.include_router(security_mode.router, prefix="/security/mode", tags=["security-mode"])
router.include_router(engagements.router, prefix="/engagements", tags=["engagements"])
router.include_router(agent_ops.sales_router, prefix="/sales", tags=["sales"])
router.include_router(agent_ops.marketing_router, prefix="/marketing", tags=["marketing"])
router.include_router(agent_ops.crm_router, prefix="/crm", tags=["crm"])
router.include_router(missions.router, prefix="/missions", tags=["missions"])
router.include_router(ws.router, tags=["websocket"])
router.include_router(voice_ws.router, tags=["voice-websocket"])
