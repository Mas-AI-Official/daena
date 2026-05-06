"""API v1 router — aggregates all domain routers.

Each domain module defines its own APIRouter, which is
included here under the /api/v1 prefix.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    account_oauth_clients,
    account_provider_keys,
    agent_ops,
    agents,
    analytics,
    api_keys,
    auth,
    autopilot,
    connections_v2,
    benchmark,
    billing,
    bridge,
    chat,
    company_mode,
    connections,
    connector_install,
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
    notifications,
    org,
    pipeline,
    policies,
    projects,
    prompts,
    runtime,
    runtimes,
    workstreams,
    security_authorized_scope,
    security_dashboard,
    security_mode,
    self_improvement,
    settings,
    plugin_governance_presets_api,
    google_setup,
    research,
    form_drafts,
    scrape,
    skill_consent_api,
    skill_execution,
    skill_refinery,
    skills,
    souls,
    system_self_diagnostic,
    tts,
    voice_ws,
    vp_commands,
    waitlist,
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
# PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE2-READONLY (2026-05-03):
# Phase 2 read-only skill execution spine. GET /allowlist returns the
# display-safe allowlist; POST /execute runs the planned-only spine
# (no real tool invocation in Phase 2 -- status is always one of
# planned / blocked / needs_connection / needs_inputs / unsupported).
router.include_router(
    skill_execution.router,
    prefix="/connections/v2/skills",
    tags=["connections-v2-skills"],
)
# PR-CONN-CONSENT-API-AND-UI (Sprint-5 PR-4, 2026-05-03):
# operator-facing surface for the Asset Shield consent gate. Mints
# short-lived grants the executor consumes; metadata-only categories
# endpoint for the modal copy. Phase 2 read_only defense remains the
# actual hard wall on writes -- consent only flips the consent gate.
router.include_router(
    skill_consent_api.router,
    prefix="/connections/v2/skill-consent",
    tags=["connections-v2-skill-consent"],
)
# PR-CONN-GOV-PRESETS-API-UI (Sprint-5 PR-5, 2026-05-03):
# vendor governance recommendations per plugin (ALLOW / ASK / DENY
# tiers per skill class). Metadata-only; the consent gate +
# read_only defense remain the actual enforcement.
router.include_router(
    plugin_governance_presets_api.router,
    prefix="/connections/v2/governance",
    tags=["connections-v2-governance"],
)
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
# PR-GOOGLE-OAUTH-LIVE-SETUP-HELPERS (Sprint-10 PR-1, 2026-05-05):
# Live read-only checklist for the two pinned Google accounts.
# Mounted under /connections so the frontend hook stays adjacent to
# the rest of the connections surface. Endpoint: GET
# /api/v1/connections/google-setup-status. NO write surface; NEVER
# starts an OAuth flow.
router.include_router(
    google_setup.router, prefix="/connections", tags=["connections-google-setup"],
)
# PR-SCRAPEGRAPH-GOVERNED-READONLY-SKILL (Sprint-10 PR-2, 2026-05-05):
# Governed read-only ScrapeGraphAI surface. FOUNDER-only. Spawns the
# venv_daena worker, returns capped extracted text. Every call writes
# a plugin.skill_invocation audit row carrying url_host (not the full
# URL value) + result length + truncated flag. NO write surface.
router.include_router(
    scrape.router, prefix="/scrape", tags=["scrape"],
)
# PR-CAREEROPS-READONLY-RESEARCH-FLOW (Sprint-10 PR-3, 2026-05-05).
# PR-CONTENTOPS-READONLY-RESEARCH-FLOW (Sprint-10 PR-4, 2026-05-05).
# Supervised read-only research flows producing local-only
# ResearchDraft rows. POST /career + POST /content + GET /drafts.
# NEVER sends, posts, emails, or otherwise dispatches a draft.
router.include_router(
    research.router, prefix="/research", tags=["research"],
)
# PR-FORM-DRAFT-ASSISTANT (Sprint-11 PR-3, 2026-05-05):
# Local-only form draft assistant. Three input surfaces: pasted
# questions, pasted HTML, opportunity URL. Output: editable suggested
# answers with confidence + NEEDS_REVIEW. NO submit/send/apply/post
# endpoint exists. Sensitive (passport/SSN/SIN/visa) and payment
# (CC/CVV/billing) field types refuse auto-population.
router.include_router(
    form_drafts.router, prefix="/form-drafts", tags=["form-drafts"],
)
router.include_router(
    connections_v2.router, prefix="/connections/v2", tags=["connections-v2"],
)
router.include_router(dynamic_models.router, prefix="/dynamic-models", tags=["dynamic-models"])
router.include_router(settings.router, prefix="/settings", tags=["settings"])
router.include_router(autopilot.router, prefix="/autopilot", tags=["autopilot"])
router.include_router(mcp_server.router, prefix="/mcp", tags=["mcp"])
router.include_router(mcp_sync.router, prefix="/mcp-sync", tags=["mcp-sync"])
# approval_dashboard removed -- dead code (in-memory duplicate of governance/approvals).
# Archived to .archive/dead_approval_queue/. Real approvals live at /governance/approvals.
router.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])
# Workstreams -- Daena's visible unit of autonomy (Council R3 lock,
# 2026-04-25). Department -> Workstream -> Task hierarchy. Every backend
# primitive (Council/QE, OODA-R, NBMF, sub-agent spawner, Plain-English
# Policy Compiler, Shield, completeness probe) serves the workstream.
router.include_router(workstreams.router, prefix="/workstreams", tags=["workstreams"])
# Plain-English policy compiler (Phase 2 F8, 2026-04-24). Founder writes
# governance rules in natural English; Claude CLI compiles to structured
# YAML stored under backend/app/config/policies/<tenant>/. SecurityGate
# evaluates these alongside the legacy department_policies table. The
# UI lives at /policies (frontend route).
router.include_router(policies.router, prefix="/policies", tags=["policies"])
router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
router.include_router(runtime.router, prefix="/runtime", tags=["runtime-truth"])
router.include_router(runtimes.router, prefix="/runtimes", tags=["runtimes"])
router.include_router(heartbeat.router, prefix="/heartbeat", tags=["heartbeat"])
router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
router.include_router(connector_oauth.router, tags=["connector-oauth"])
router.include_router(connector_install.router, tags=["connector-install"])
router.include_router(bridge.router, tags=["bridge"])
router.include_router(self_improvement.router, prefix="/self-improvement", tags=["self-improvement"])
router.include_router(waitlist.router, prefix="/waitlist", tags=["waitlist"])
router.include_router(mobile.router)
router.include_router(benchmark.router)
router.include_router(files.router, prefix="/files", tags=["files"])
router.include_router(api_keys.router, prefix="/api-keys", tags=["api-keys"])
# PR-CONN-PROVIDER-KEY-INPUT-IN-ACCOUNT (2026-05-03): paste-and-save
# LLM provider keys (Anthropic, OpenAI, Gemini, Groq, Perplexity,
# OpenRouter, Together). Persists via provider_keys_store + applies
# live via DynamicModelService. Sibling of /api-keys (which manages
# Daena's outbound dna_ keys for the public API surface).
router.include_router(
    account_provider_keys.router,
    prefix="/account/provider-keys",
    tags=["account-provider-keys"],
)
# PR-CONN-OAUTH-CLIENT-CONFIG-IN-SETTINGS (2026-05-03): paste-and-save
# OAuth client_id + client_secret for Google / GitHub / Slack / Figma /
# Canva. Persists via oauth_client_config_store (which writes through to
# the existing oauth_credentials_store that oauth_service already reads).
# Sibling of /account/provider-keys (LLM API keys). NEVER returns secrets.
router.include_router(
    account_oauth_clients.router,
    prefix="/account/oauth-clients",
    tags=["account-oauth-clients"],
)
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
# Phase 11 PR-S2 (2026-05-01): in-app notifications.
# GET /notifications + POST /notifications/test. Backend-only emit
# (NotificationService); no client-side type override (no spam).
router.include_router(notifications.router, tags=["notifications"])
# Note: ws.router (Phase 5 placeholder /ws/{session_id}) was removed 2026-04-29.
# It only echoed "LLM routing not yet active" with zero consumers (no frontend
# WebSocket client, no tests). Chat SSE at /api/v1/chat/messages/stream is the
# canonical streaming surface. The ConnectionManager at app/core/websocket.py
# is retained for future LLM-pipeline streaming reuse. voice_ws is independent.
# Sprint-6 PR-7: system self-diagnostic. Single read-only endpoint
# that aggregates backend / DB / migration / frontend / local-model
# / connector-callability state into one payload Daena can speak to
# in chat. Never modifies state.
router.include_router(
    system_self_diagnostic.router,
    prefix="/system",
    tags=["system-self-diagnostic"],
)
router.include_router(voice_ws.router, tags=["voice-websocket"])
# Sprint-12 PR-5 (2026-05-05): VP work chat commands. Natural-English
# parser + runner that drives the draft + workstream pipeline. NO
# external action; tenant + user-scoped; runtime-not-ready refusals
# surface the readiness next_action verbatim.
router.include_router(
    vp_commands.router, prefix="/vp-commands", tags=["vp-commands"],
)
