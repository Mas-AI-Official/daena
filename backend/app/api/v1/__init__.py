"""API v1 router — aggregates all domain routers.

Each domain module defines its own APIRouter, which is
included here under the /api/v1 prefix.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    agents,
    analytics,
    api_keys,
    auth,
    autopilot,
    benchmark,
    billing,
    bridge,
    chat,
    connections,
    connector_oauth,
    daenabot,
    dynamic_models,
    execution,
    files,
    founder,
    governance,
    health,
    heartbeat,
    integrations,
    mcp_server,
    memory,
    mobile,
    org,
    pipeline,
    projects,
    prompts,
    runtimes,
    self_improvement,
    settings,
    skill_refinery,
    skills,
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
router.include_router(skills.router, prefix="/skills", tags=["skills"])
router.include_router(skill_refinery.router, prefix="/skills/refinery", tags=["skill-refinery"])
router.include_router(connections.router, prefix="/connections", tags=["connections"])
router.include_router(dynamic_models.router, prefix="/dynamic-models", tags=["dynamic-models"])
router.include_router(settings.router, prefix="/settings", tags=["settings"])
router.include_router(autopilot.router, prefix="/autopilot", tags=["autopilot"])
router.include_router(mcp_server.router, prefix="/mcp", tags=["mcp"])
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
router.include_router(ws.router, tags=["websocket"])
