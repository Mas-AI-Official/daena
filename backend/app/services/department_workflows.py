"""Department workflow definitions and execution engine.

Each of Daena's 10 departments has workflows -- composable sequences of
integration tool calls and LLM reasoning steps. Workflows are defined
as data structures so they can be extended via Skill Refinery.

Workflow execution flow:
    1. Resolve required integrations (fail fast if not connected)
    2. Execute each step (tool call or LLM reasoning)
    3. Chain step outputs as inputs to subsequent steps
    4. Return structured result with audit trail

Department workflows map to the CLAUDE.md Phase G requirements:
    - Marketing: draft content, SEO analysis
    - Sales: lead research, outreach drafts
    - Operations: daily briefing, task summary
    - Engineering: PR review queue, test status
    - Finance: cost tracking, budget alerts
    - Research: competitive analysis
    - Legal: contract review, IP tracking
    - Security: access audit, threat scan
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services.integrations.integration_router import (
    IntegrationRouter,
    NotConnectedError,
)

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """A single step in a department workflow."""

    name: str
    step_type: str  # "tool_call" | "llm_reason" | "aggregate"
    provider: str = ""  # For tool_call steps: "gmail", "calendar", etc.
    tool: str = ""  # For tool_call steps: "search_emails", etc.
    params: dict[str, Any] = field(default_factory=dict)
    prompt_template: str = ""  # For llm_reason steps
    input_from: list[str] = field(default_factory=list)  # Step names to pull input from
    optional: bool = False  # If True, failure doesn't abort workflow


@dataclass(frozen=True, slots=True)
class WorkflowDef:
    """Definition of a department workflow."""

    id: str
    name: str
    department: str
    description: str
    steps: list[WorkflowStep]
    schedule: str = ""  # cron expression for heartbeat scheduling
    required_integrations: list[str] = field(default_factory=list)


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""

    workflow_id: str
    department: str
    status: str  # "completed" | "partial" | "failed"
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    step_results: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "department": self.department,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "step_results": self.step_results,
            "summary": self.summary,
            "error": self.error,
        }


# ── Workflow Definitions ──────────────────────────────────────

WORKFLOWS: dict[str, WorkflowDef] = {}


def _register(wf: WorkflowDef) -> None:
    WORKFLOWS[wf.id] = wf


# --- Operations Department ---

_register(WorkflowDef(
    id="ops.daily_briefing",
    name="Daily Briefing",
    department="Operations",
    description="Morning briefing: unread emails, today's calendar, pending tasks",
    schedule="0 8 * * 1-5",  # 8 AM Mon-Fri
    required_integrations=["gmail", "google-calendar"],
    steps=[
        WorkflowStep(
            name="unread_emails",
            step_type="tool_call",
            provider="gmail",
            tool="search_emails",
            params={"query": "is:unread", "max_results": 15},
        ),
        WorkflowStep(
            name="todays_events",
            step_type="tool_call",
            provider="calendar",
            tool="list_events",
            params={"max_results": 10},
        ),
        WorkflowStep(
            name="briefing_summary",
            step_type="llm_reason",
            input_from=["unread_emails", "todays_events"],
            prompt_template=(
                "Generate a concise morning briefing from:\n"
                "UNREAD EMAILS:\n{unread_emails}\n\n"
                "TODAY'S EVENTS:\n{todays_events}\n\n"
                "Format: prioritized action items, key meetings, urgent emails. "
                "Keep it under 300 words."
            ),
        ),
    ],
))

_register(WorkflowDef(
    id="ops.task_summary",
    name="Task Summary",
    department="Operations",
    description="Summarize pending tasks and project status",
    schedule="0 17 * * 1-5",  # 5 PM Mon-Fri
    required_integrations=[],
    steps=[
        WorkflowStep(
            name="task_summary",
            step_type="llm_reason",
            prompt_template=(
                "Generate an end-of-day task summary. "
                "List completed work, pending items, and blockers. "
                "Keep it under 200 words."
            ),
        ),
    ],
))

# --- Marketing Department ---

_register(WorkflowDef(
    id="mkt.draft_content",
    name="Draft Content",
    department="Marketing",
    description="Draft social media and blog content based on recent activity",
    schedule="0 10 * * 1-5",
    required_integrations=[],
    steps=[
        WorkflowStep(
            name="content_draft",
            step_type="llm_reason",
            prompt_template=(
                "Draft 3 social media posts for MAS-AI Technologies. "
                "Topic: AI governance and autonomous agent orchestration. "
                "Tone: professional, forward-thinking, technical credibility. "
                "Include: 1 LinkedIn post (200 words), 1 X/Twitter post (280 chars), "
                "1 short-form hook for Instagram/TikTok. "
                "Reference Daena's governed multi-agent architecture."
            ),
        ),
    ],
))

_register(WorkflowDef(
    id="mkt.competitor_watch",
    name="Competitor Watch",
    department="Marketing",
    description="Monitor competitor email mentions and draft response content",
    schedule="0 9 * * 1",  # Monday 9 AM
    required_integrations=["gmail"],
    steps=[
        WorkflowStep(
            name="competitor_emails",
            step_type="tool_call",
            provider="gmail",
            tool="search_emails",
            params={"query": "Perplexity OR Manus OR OpenClaw OR NemoClaw", "max_results": 10},
            optional=True,
        ),
        WorkflowStep(
            name="competitor_analysis",
            step_type="llm_reason",
            input_from=["competitor_emails"],
            prompt_template=(
                "Analyze these competitor mentions and draft a competitive positioning update:\n"
                "{competitor_emails}\n\n"
                "Focus on: what they announced, how Daena differentiates, "
                "suggested messaging adjustments."
            ),
        ),
    ],
))

# --- Sales Department ---

_register(WorkflowDef(
    id="sales.lead_research",
    name="Lead Research",
    department="Sales",
    description="Research new leads from email and draft outreach",
    schedule="0 9 * * 1-5",
    required_integrations=["gmail"],
    steps=[
        WorkflowStep(
            name="prospect_emails",
            step_type="tool_call",
            provider="gmail",
            tool="search_emails",
            params={"query": "label:prospects OR subject:demo OR subject:partnership", "max_results": 10},
            optional=True,
        ),
        WorkflowStep(
            name="outreach_drafts",
            step_type="llm_reason",
            input_from=["prospect_emails"],
            prompt_template=(
                "Based on these prospect emails, draft personalized outreach responses:\n"
                "{prospect_emails}\n\n"
                "For each prospect: 1) summarize their interest, "
                "2) draft a reply highlighting Daena's relevant capabilities, "
                "3) suggest a next step (demo, call, docs link). "
                "Tone: professional, concise, value-first."
            ),
        ),
    ],
))

_register(WorkflowDef(
    id="sales.outreach_draft",
    name="Draft Outreach Email",
    department="Sales",
    description="Draft a cold outreach email for a specific prospect",
    required_integrations=["gmail"],
    steps=[
        WorkflowStep(
            name="draft_email",
            step_type="llm_reason",
            prompt_template=(
                "Draft a cold outreach email for MAS-AI Technologies (Daena). "
                "Highlight: governed multi-agent AI, multi-runtime support, "
                "transparent execution, enterprise audit trails. "
                "Keep it under 150 words. Professional but not corporate-stiff."
            ),
        ),
    ],
))

# --- Engineering Department ---

_register(WorkflowDef(
    id="eng.test_status",
    name="Test Suite Status",
    department="Engineering",
    description="Check test suite health and report failures",
    schedule="0 7 * * *",  # Daily 7 AM
    required_integrations=[],
    steps=[
        WorkflowStep(
            name="test_report",
            step_type="llm_reason",
            prompt_template=(
                "Generate a test suite health report. "
                "Summarize: total tests, pass rate, recent failures, "
                "flaky test patterns, and recommended actions."
            ),
        ),
    ],
))

# --- Finance Department ---

_register(WorkflowDef(
    id="fin.cost_report",
    name="Daily Cost Report",
    department="Finance",
    description="Summarize API costs across all providers",
    schedule="0 18 * * *",  # 6 PM daily
    required_integrations=[],
    steps=[
        WorkflowStep(
            name="cost_analysis",
            step_type="llm_reason",
            prompt_template=(
                "Generate a daily cost analysis for Daena's API usage. "
                "Break down by provider (Anthropic, OpenAI, Google, Ollama), "
                "identify cost spikes, and recommend optimizations."
            ),
        ),
    ],
))

# --- Research Department ---

_register(WorkflowDef(
    id="research.competitive_scan",
    name="Competitive Intelligence Scan",
    department="Research",
    description="Weekly scan of AI agent landscape and competitor activity",
    schedule="0 10 * * 1",  # Monday 10 AM
    required_integrations=[],
    steps=[
        WorkflowStep(
            name="competitive_report",
            step_type="llm_reason",
            prompt_template=(
                "Generate a weekly competitive intelligence report for the AI agent space. "
                "Cover: Perplexity Computer, Manus (Meta), OpenClaw/NemoClaw (NVIDIA), "
                "Claude Computer Use. "
                "For each: recent announcements, pricing changes, feature launches. "
                "End with: Daena's positioning advantages and gaps to address."
            ),
        ),
    ],
))

# --- Security Department ---

_register(WorkflowDef(
    id="sec.access_audit",
    name="Access Audit",
    department="Security Operations",
    description="Audit connected integrations and permission levels",
    schedule="0 6 * * 1",  # Monday 6 AM
    required_integrations=[],
    steps=[
        WorkflowStep(
            name="audit_report",
            step_type="llm_reason",
            prompt_template=(
                "Generate a security audit report for Daena's connected integrations. "
                "Check: which integrations are connected, permission levels set, "
                "last usage timestamps, any tools with ALWAYS_ALLOW that should be ASK_EACH_TIME. "
                "Flag any security concerns."
            ),
        ),
    ],
))


# --- Marketing Department (Web-Powered) ---

_register(WorkflowDef(
    id="mkt.seo_analysis",
    name="SEO & Content Gap Analysis",
    department="Marketing",
    description="Crawl competitor sites and identify content gaps for MAS-AI positioning",
    schedule="0 9 * * 1",  # Monday 9 AM
    required_integrations=[],
    steps=[
        WorkflowStep(
            name="competitor_perplexity",
            step_type="web_crawl",
            params={
                "operation": "extract_page",
                "url": "https://www.perplexity.ai",
            },
            optional=True,
        ),
        WorkflowStep(
            name="competitor_openclaw",
            step_type="web_crawl",
            params={
                "operation": "extract_page",
                "url": "https://github.com/openclaw/openclaw",
            },
            optional=True,
        ),
        WorkflowStep(
            name="seo_analysis",
            step_type="llm_reason",
            input_from=["competitor_perplexity", "competitor_openclaw"],
            prompt_template=(
                "Analyze these competitor pages and produce an SEO strategy for MAS-AI (Daena):\n\n"
                "PERPLEXITY.AI:\n{competitor_perplexity}\n\n"
                "OPENCLAW (GitHub):\n{competitor_openclaw}\n\n"
                "Produce:\n"
                "1. Top 10 keywords they rank for that Daena should target\n"
                "2. Content gaps: topics they cover that MAS-AI doesn't\n"
                "3. Positioning angles: where Daena's governance-first approach wins\n"
                "4. 3 blog post ideas with titles and outlines\n"
                "5. Social media hooks for each differentiator"
            ),
        ),
    ],
))

_register(WorkflowDef(
    id="mkt.product_hunt_prep",
    name="Product Hunt Launch Prep",
    department="Marketing",
    description="Research top Product Hunt AI launches and prepare Daena's launch strategy",
    required_integrations=[],
    steps=[
        WorkflowStep(
            name="ph_research",
            step_type="web_crawl",
            params={
                "operation": "extract_page",
                "url": "https://www.producthunt.com/topics/artificial-intelligence",
            },
            optional=True,
        ),
        WorkflowStep(
            name="launch_strategy",
            step_type="llm_reason",
            input_from=["ph_research"],
            prompt_template=(
                "Based on Product Hunt AI trends:\n{ph_research}\n\n"
                "Create a Product Hunt launch plan for Daena by MAS-AI Technologies:\n"
                "1. Tagline (under 60 chars) - emphasize governed AI orchestration\n"
                "2. Description (3 paragraphs)\n"
                "3. Key features to highlight (5 bullet points)\n"
                "4. First comment from maker (authentic, not salesy)\n"
                "5. Target communities to notify\n"
                "6. Best day/time to launch\n"
                "7. Response templates for common questions"
            ),
        ),
    ],
))

_register(WorkflowDef(
    id="mkt.social_content_web",
    name="Web-Powered Social Content",
    department="Marketing",
    description="Research trending AI topics and create timely social media content",
    schedule="0 8 * * 1,3,5",  # Mon/Wed/Fri 8 AM
    required_integrations=[],
    steps=[
        WorkflowStep(
            name="ai_news",
            step_type="web_crawl",
            params={
                "operation": "extract_page",
                "url": "https://news.ycombinator.com",
            },
            optional=True,
        ),
        WorkflowStep(
            name="content_creation",
            step_type="llm_reason",
            input_from=["ai_news"],
            prompt_template=(
                "Based on today's tech/AI news:\n{ai_news}\n\n"
                "Create social media content for MAS-AI Technologies:\n"
                "1. LinkedIn post (200 words): connect a trending topic to Daena's governance approach\n"
                "2. X/Twitter thread (5 tweets): explain a Daena capability through the lens of current news\n"
                "3. Short-form hook for Instagram/TikTok: 15-second script about AI governance\n\n"
                "Brand voice: professional, forward-thinking, technical credibility. "
                "Color palette: dark slate + gold + teal. "
                "Always position Daena as governed-first, not local-first."
            ),
        ),
    ],
))

# --- Sales Department (Web-Powered) ---

_register(WorkflowDef(
    id="sales.prospect_research",
    name="Prospect Company Research",
    department="Sales",
    description="Research a prospect company's website to prepare for outreach",
    required_integrations=[],
    steps=[
        WorkflowStep(
            name="company_site",
            step_type="web_crawl",
            params={
                "operation": "extract_page",
                "url": "{prospect_url}",
            },
        ),
        WorkflowStep(
            name="research_report",
            step_type="llm_reason",
            input_from=["company_site"],
            prompt_template=(
                "Based on this company's website:\n{company_site}\n\n"
                "Produce a sales research brief:\n"
                "1. Company overview (what they do, industry, size)\n"
                "2. Pain points Daena could solve (AI governance, multi-runtime, audit trails)\n"
                "3. Potential use cases for their industry\n"
                "4. Decision maker titles to target\n"
                "5. Personalized outreach email (under 150 words)\n"
                "6. Follow-up call talking points"
            ),
        ),
    ],
))

_register(WorkflowDef(
    id="sales.accelerator_research",
    name="Accelerator Application Research",
    department="Sales",
    description="Research an accelerator program and prepare application materials",
    required_integrations=[],
    steps=[
        WorkflowStep(
            name="accelerator_page",
            step_type="web_crawl",
            params={
                "operation": "extract_page",
                "url": "{accelerator_url}",
            },
        ),
        WorkflowStep(
            name="application_prep",
            step_type="llm_reason",
            input_from=["accelerator_page"],
            prompt_template=(
                "Based on this accelerator program page:\n{accelerator_page}\n\n"
                "Company: MAS-AI Technologies Inc. (Daena - governed multi-agent AI platform)\n"
                "Founder: Masoud Masoori, solo founder, Ontario Canada\n"
                "Stage: Pre-revenue, MVP complete, 1328 tests passing\n"
                "IP: 2 USPTO provisionals (PhiLattice Architecture, NBMF)\n"
                "Differentiators: Governed-first (not local-first), multi-runtime orchestration, "
                "visible execution, bring-your-own-runtimes, audit trail\n\n"
                "Produce:\n"
                "1. Program fit analysis (why Daena is a good fit)\n"
                "2. Key application talking points\n"
                "3. Draft answers for common accelerator questions:\n"
                "   - What problem do you solve?\n"
                "   - What is your unfair advantage?\n"
                "   - What is your business model?\n"
                "   - What traction do you have?\n"
                "   - What are you looking for from this program?\n"
                "4. Red flags to address proactively\n"
                "5. Follow-up strategy after submission"
            ),
        ),
    ],
))

_register(WorkflowDef(
    id="sales.competitive_battlecard",
    name="Live Competitive Battlecard",
    department="Sales",
    description="Generate an up-to-date competitive battlecard using live web data",
    schedule="0 10 * * 1",  # Monday 10 AM
    required_integrations=[],
    steps=[
        WorkflowStep(
            name="perplexity_data",
            step_type="web_crawl",
            params={
                "operation": "extract_page",
                "url": "https://www.perplexity.ai/hub/blog",
            },
            optional=True,
        ),
        WorkflowStep(
            name="manus_data",
            step_type="web_crawl",
            params={
                "operation": "extract_page",
                "url": "https://manus.im",
            },
            optional=True,
        ),
        WorkflowStep(
            name="battlecard",
            step_type="llm_reason",
            input_from=["perplexity_data", "manus_data"],
            prompt_template=(
                "Create a competitive battlecard for the sales team.\n\n"
                "PERPLEXITY LATEST:\n{perplexity_data}\n\n"
                "MANUS LATEST:\n{manus_data}\n\n"
                "For each competitor (Perplexity Computer, Manus, OpenClaw, NemoClaw):\n"
                "1. Current pricing\n"
                "2. Key features\n"
                "3. Recent announcements\n"
                "4. Daena wins against them (governance, multi-runtime, visible execution)\n"
                "5. Daena loses against them (honestly assess gaps)\n"
                "6. Objection handlers (what to say when prospect mentions them)\n\n"
                "End with: TOP 3 unique selling points for Daena that NO competitor has."
            ),
        ),
    ],
))

# --- Product Department ---

_register(WorkflowDef(
    id="product.feature_landscape",
    name="AI Agent Feature Landscape",
    department="Product",
    description="Scan the AI agent ecosystem for features Daena should prioritize",
    schedule="0 9 * * 1",  # Monday 9 AM
    required_integrations=[],
    steps=[
        WorkflowStep(
            name="hn_trends",
            step_type="web_crawl",
            params={
                "operation": "extract_page",
                "url": "https://news.ycombinator.com/",
            },
            optional=True,
        ),
        WorkflowStep(
            name="feature_analysis",
            step_type="llm_reason",
            input_from=["hn_trends"],
            prompt_template=(
                "Based on current tech trends:\n{hn_trends}\n\n"
                "Analyze the AI agent feature landscape for Daena's product roadmap:\n"
                "1. Most-requested features in the AI agent space\n"
                "2. Features that align with Daena's governed-first identity\n"
                "3. Features to avoid (would dilute positioning)\n"
                "4. Quick wins (< 1 week to implement, high user value)\n"
                "5. Strategic bets (1-3 months, could be game-changers)\n"
                "6. Priority ranking with effort/impact scores"
            ),
        ),
    ],
))

# --- Legal & Compliance Department ---

_register(WorkflowDef(
    id="legal.ip_landscape",
    name="IP Landscape Scan",
    department="Legal & Compliance",
    description="Monitor patent filings and IP activity in AI agent governance space",
    schedule="0 8 * * 1",  # Monday 8 AM
    required_integrations=[],
    steps=[
        WorkflowStep(
            name="ip_scan",
            step_type="llm_reason",
            prompt_template=(
                "Generate a weekly IP landscape report for MAS-AI Technologies:\n"
                "1. Recent patent filings in AI agent orchestration and governance\n"
                "2. Open-source projects that may affect our PhiLattice and NBMF patents\n"
                "3. Competitor IP activity (Anthropic, OpenAI, Google, NVIDIA, Meta)\n"
                "4. Recommended defensive actions\n"
                "5. Opportunities to strengthen our provisional filings\n\n"
                "Our patents: PhiLattice Architecture (sunflower-honeycomb topology), "
                "NBMF (Neural-Backed Memory Fabric with tiered trust)."
            ),
        ),
    ],
))


# ── Workflow Engine ───────────────────────────────────────────

class DepartmentWorkflowEngine:
    """Executes department workflows using integration tools and LLM reasoning.

    Usage::

        engine = DepartmentWorkflowEngine(db, user_id, tenant_id)
        result = await engine.run("ops.daily_briefing")
    """

    def __init__(
        self,
        db: AsyncSession,
        user_id: UUID,
        tenant_id: UUID,
    ) -> None:
        self.db = db
        self.user_id = user_id
        self.tenant_id = tenant_id
        self._integration_router = IntegrationRouter(db)

    async def run(
        self,
        workflow_id: str,
        extra_params: dict[str, Any] | None = None,
    ) -> WorkflowResult:
        """Execute a workflow by ID.

        Args:
            workflow_id: Workflow ID from WORKFLOWS registry.
            extra_params: Additional parameters to inject into steps.

        Returns:
            WorkflowResult with step outputs and summary.
        """
        wf = WORKFLOWS.get(workflow_id)
        if wf is None:
            return WorkflowResult(
                workflow_id=workflow_id,
                department="unknown",
                status="failed",
                error=f"Unknown workflow: {workflow_id}",
            )

        result = WorkflowResult(
            workflow_id=workflow_id,
            department=wf.department,
            status="running",
        )

        logger.info(
            "workflow.started",
            workflow_id=workflow_id,
            department=wf.department,
        )

        # Check required integrations
        for integration in wf.required_integrations:
            try:
                await self._integration_router._get_connected_instance(
                    integration, self.user_id, self.tenant_id,
                )
            except NotConnectedError:
                if not all(s.optional for s in wf.steps if s.provider == integration):
                    result.status = "failed"
                    result.error = (
                        f"Required integration '{integration}' is not connected. "
                        f"Connect it in Settings > Connections."
                    )
                    result.completed_at = datetime.now(timezone.utc)
                    return result

        # Execute steps
        step_outputs: dict[str, Any] = {}
        if extra_params:
            step_outputs.update(extra_params)

        all_succeeded = True
        for step in wf.steps:
            try:
                output = await self._execute_step(step, step_outputs)
                step_outputs[step.name] = output
                result.step_results[step.name] = {
                    "status": "completed",
                    "output": output,
                }
            except Exception as exc:
                logger.warning(
                    "workflow.step_failed",
                    workflow_id=workflow_id,
                    step=step.name,
                    error=str(exc),
                )
                if step.optional:
                    step_outputs[step.name] = f"(skipped: {exc})"
                    result.step_results[step.name] = {
                        "status": "skipped",
                        "error": str(exc),
                    }
                else:
                    all_succeeded = False
                    result.step_results[step.name] = {
                        "status": "failed",
                        "error": str(exc),
                    }
                    result.status = "failed"
                    result.error = f"Step '{step.name}' failed: {exc}"
                    break

        if all_succeeded:
            result.status = "completed"
            # Use the last step's output as summary
            last_step = wf.steps[-1]
            last_output = step_outputs.get(last_step.name, "")
            result.summary = str(last_output)[:2000] if last_output else ""

        result.completed_at = datetime.now(timezone.utc)

        logger.info(
            "workflow.completed",
            workflow_id=workflow_id,
            status=result.status,
            steps_completed=sum(
                1 for s in result.step_results.values()
                if s.get("status") == "completed"
            ),
        )

        return result

    async def _execute_step(
        self,
        step: WorkflowStep,
        context: dict[str, Any],
    ) -> Any:
        """Execute a single workflow step."""
        if step.step_type == "tool_call":
            return await self._execute_tool_step(step, context)
        elif step.step_type == "llm_reason":
            return await self._execute_llm_step(step, context)
        elif step.step_type == "web_crawl":
            return await self._execute_web_crawl_step(step, context)
        elif step.step_type == "vision_browse":
            return await self._execute_vision_browse_step(step, context)
        elif step.step_type == "aggregate":
            return self._aggregate(step, context)
        else:
            raise ValueError(f"Unknown step type: {step.step_type}")

    async def _execute_tool_step(
        self,
        step: WorkflowStep,
        context: dict[str, Any],
    ) -> Any:
        """Execute an integration tool call step."""
        # Merge step params with any context overrides
        params = {**step.params}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
                ctx_key = value[1:-1]
                if ctx_key in context:
                    params[key] = context[ctx_key]

        return await self._integration_router.execute(
            provider=step.provider,
            tool_name=step.tool,
            params=params,
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            skip_permission_check=True,  # Workflow execution is pre-approved
        )

    async def _execute_llm_step(
        self,
        step: WorkflowStep,
        context: dict[str, Any],
    ) -> str:
        """Execute an LLM reasoning step.

        Formats the prompt template with context from previous steps,
        then calls the LLM for synthesis/reasoning.
        """
        # Build prompt from template + context
        prompt = step.prompt_template
        for input_name in step.input_from:
            if input_name in context:
                value = context[input_name]
                if isinstance(value, dict):
                    import json
                    value = json.dumps(value, indent=2, default=str)
                prompt = prompt.replace(f"{{{input_name}}}", str(value))

        # Use Ollama or configured LLM for reasoning
        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "llama3.1:8b",
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                if resp.status_code == 200:
                    return resp.json().get("response", "")
        except Exception as exc:
            logger.warning("workflow.llm_fallback", error=str(exc))

        # Fallback: return the formatted prompt as the "result"
        return f"[LLM unavailable] Prompt: {prompt[:500]}"

    async def _execute_web_crawl_step(
        self,
        step: WorkflowStep,
        context: dict[str, Any],
    ) -> Any:
        """Execute a web crawling step using WebCrawlerAgent.

        Params:
            url: URL to crawl (supports {context_var} substitution)
            operation: extract_page | deep_crawl | extract_structured | research_topic
            Additional params passed to the agent operation.
        """
        from app.services.daenabot.web_crawler_agent import WebCrawlerAgent

        params = {**step.params}
        # Substitute context variables in params
        for key, value in params.items():
            if isinstance(value, str) and "{" in value and "}" in value:
                for ctx_key, ctx_val in context.items():
                    value = value.replace(f"{{{ctx_key}}}", str(ctx_val))
                params[key] = value

        operation = params.pop("operation", "extract_page")
        agent = WebCrawlerAgent()
        result = await agent.execute(operation, params)

        if result.get("success"):
            output = result.get("output", {})
            # Return markdown content for LLM steps to consume
            return output.get("markdown", "") or output.get("content", "") or str(output)
        else:
            raise RuntimeError(result.get("error", "Web crawl failed"))

    async def _execute_vision_browse_step(
        self,
        step: WorkflowStep,
        context: dict[str, Any],
    ) -> Any:
        """Execute a vision browsing step using VisionBrowserAgent.

        Params:
            url: URL to browse
            operation: browse_and_act | research_url | fill_form_smart
            goal: What to accomplish (for browse_and_act)
            question: What to answer (for research_url)
        """
        from app.services.daenabot.vision_browser_agent import VisionBrowserAgent

        params = {**step.params}
        for key, value in params.items():
            if isinstance(value, str) and "{" in value and "}" in value:
                for ctx_key, ctx_val in context.items():
                    value = value.replace(f"{{{ctx_key}}}", str(ctx_val))
                params[key] = value

        operation = params.pop("operation", "research_url")
        agent = VisionBrowserAgent()
        try:
            result = await agent.execute(operation, params)
            if result.get("success"):
                output = result.get("output", {})
                return output.get("content", "") or str(output)
            else:
                raise RuntimeError(result.get("error", "Vision browse failed"))
        finally:
            await agent.close()

    @staticmethod
    def _aggregate(step: WorkflowStep, context: dict[str, Any]) -> dict[str, Any]:
        """Aggregate outputs from multiple previous steps."""
        return {
            name: context.get(name, None)
            for name in step.input_from
        }

    @staticmethod
    def list_workflows(department: str | None = None) -> list[dict[str, Any]]:
        """List available workflows, optionally filtered by department."""
        results = []
        for wf in WORKFLOWS.values():
            if department and wf.department.lower() != department.lower():
                continue
            results.append({
                "id": wf.id,
                "name": wf.name,
                "department": wf.department,
                "description": wf.description,
                "schedule": wf.schedule,
                "required_integrations": wf.required_integrations,
                "step_count": len(wf.steps),
            })
        return results

    @staticmethod
    def get_scheduled_workflows() -> list[WorkflowDef]:
        """Get all workflows that have a cron schedule."""
        return [wf for wf in WORKFLOWS.values() if wf.schedule]
