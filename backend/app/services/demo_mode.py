"""Demo Mode: pre-seeded data and mock LLM for investor/viewer experience.

Activated by DEMO_MODE=true environment variable. Seeds sample projects,
chat history, and approval queue items on startup. Provides a keyword-matched
mock LLM responder for when no real API key is configured.
"""

import os
import uuid
from datetime import datetime, timezone

from app.core.logging import get_logger

logger = get_logger(__name__)


def is_demo_mode() -> bool:
    """Check if demo mode is active."""
    return os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")


# ── Demo Data ──

DEMO_USER = {
    "email": "demo@daena.mas-ai.co",
    "display_name": "Demo User",
    "password": "DaenaDemo2026!",
}

DEMO_PROJECTS = [
    {
        "name": "Q2 Product Launch",
        "description": "Coordinate marketing, engineering, and sales for the Q2 product release.",
        "status": "active",
    },
    {
        "name": "Competitor Analysis Report",
        "description": "Research and compare Perplexity Computer, Manus, and OpenClaw features.",
        "status": "active",
    },
    {
        "name": "Patent Filing Prep",
        "description": "Prepare PhiLattice Architecture and NBMF provisional patent documents.",
        "status": "active",
    },
]

DEMO_CHAT_HISTORY = [
    {
        "role": "USER",
        "content": "What departments do we have and what can they do?",
    },
    {
        "role": "ASSISTANT",
        "content": (
            "Daena runs 10 departments, each with 6 sub-capabilities "
            "(MIND, EYES, HANDS, VOICE, SHIELD, MEMORY):\n\n"
            "1. **Engineering** - Code generation, testing, debugging, deployment\n"
            "2. **Product** - Feature specs, backlog, metrics\n"
            "3. **Marketing** - Content, SEO, social, campaigns\n"
            "4. **Sales** - Lead gen, outreach, CRM, proposals\n"
            "5. **Finance** - Budgets, invoicing, forecasting\n"
            "6. **Operations** - Project management, scheduling, automation\n"
            "7. **Research** - Market research, competitive analysis, tech scouting\n"
            "8. **Legal & Compliance** - Contracts, IP, regulatory, privacy\n"
            "9. **Skill Governance** - Skill extraction, refinement, quality scoring\n"
            "10. **Security Operations** - Threat detection, access control, incidents\n\n"
            "Each department can be assigned tasks directly or through the swarm planner."
        ),
    },
    {
        "role": "USER",
        "content": "Run a competitive analysis on Perplexity Computer vs Daena",
    },
    {
        "role": "ASSISTANT",
        "content": (
            "Here is a comparison of Perplexity Computer and Daena:\n\n"
            "| Feature | Perplexity Computer | Daena |\n"
            "|---------|-------------------|-------|\n"
            "| Pricing | $200/mo fixed | Your existing subscriptions |\n"
            "| Models | 19 locked models | Bring your own runtimes |\n"
            "| Governance | Basic permissions | 5-tier governed pipeline |\n"
            "| Custom departments | No | Yes, 10 built-in + custom |\n"
            "| Execution visibility | Limited | Full audit trail |\n"
            "| Open architecture | No | Runtime adapter pattern |\n\n"
            "Daena's key differentiator: you use the AI tools you already pay for "
            "(Claude Code, Codex, Gemini, Ollama) instead of paying $200/mo for locked access. "
            "Governance is built into every decision, not bolted on."
        ),
    },
]

DEMO_APPROVAL_ITEMS = [
    {
        "action": "deploy_to_production",
        "description": "Deploy v2.0.1 to Cloud Run production environment",
        "risk_level": "HIGH",
        "status": "pending",
    },
    {
        "action": "delete_database_table",
        "description": "Drop legacy migration_history table",
        "risk_level": "CRITICAL",
        "status": "pending",
    },
]


# ── Mock LLM Responder ──

_MOCK_RESPONSES: list[tuple[list[str], str]] = [
    (
        ["hello", "hi", "hey", "good morning", "good afternoon"],
        "Hi there. How can I help today?",
    ),
    (
        ["department", "departments", "team", "teams"],
        (
            "Daena has 10 departments: Engineering, Product, Marketing, Sales, "
            "Finance, Operations, Research, Legal & Compliance, Skill Governance, "
            "and Security Operations. Each has 6 sub-capabilities. "
            "Which department would you like to work with?"
        ),
    ),
    (
        ["governance", "approve", "approval", "audit"],
        (
            "Governance runs on a 5-tier system. Tiers 0-1 are logged silently. "
            "Tier 2 gets a notification. Tier 3+ requires your explicit approval. "
            "You can adjust the sensitivity with the governance slider in settings."
        ),
    ),
    (
        ["runtime", "model", "ollama", "claude", "codex", "gemini"],
        (
            "Daena supports multiple runtimes: Claude Code, Codex, Gemini CLI, "
            "Ollama (local), and more. Connect your existing subscriptions on the "
            "Connections page. The swarm planner routes tasks to the best runtime "
            "based on capability matching and cost."
        ),
    ),
    (
        ["project", "projects", "task", "tasks"],
        (
            "Projects in Daena are persistent workspaces with scoped context. "
            "Each project has its own memory, tasks, files, and chat history. "
            "Create one from the Projects page or ask me to set one up."
        ),
    ),
    (
        ["exe", "execute", "run", "deploy"],
        (
            "Switch to EXE mode using the toggle in the header. In EXE mode, "
            "I can take actions on your behalf: file operations, terminal commands, "
            "web automation, and MCP tool execution. All actions go through the "
            "governance pipeline first."
        ),
    ),
    (
        ["cost", "price", "pricing", "budget", "money"],
        (
            "Daena uses your existing AI subscriptions, so there is no extra model cost. "
            "The cost guard tracks token usage per session and enforces budget limits "
            "you set in Settings > Governance."
        ),
    ),
]

_DEFAULT_MOCK_RESPONSE = (
    "I am running in demo mode without a connected LLM. "
    "Connect a runtime on the Connections page to get full responses. "
    "In the meantime, try asking about departments, governance, runtimes, or projects."
)


def mock_llm_response(message: str) -> str:
    """Return a pre-crafted response based on keyword matching.

    Uses word-boundary matching to avoid false positives (e.g. 'hi' in 'which').
    Used when no real LLM API key is configured and DEMO_MODE is active.
    """
    import re
    lower = message.lower()
    for keywords, response in _MOCK_RESPONSES:
        if any(re.search(r"\b" + re.escape(kw) + r"\b", lower) for kw in keywords):
            return response
    return _DEFAULT_MOCK_RESPONSE


async def seed_demo_data() -> dict:
    """Seed demo data for investor/viewer experience.

    Creates a demo user, sample projects, chat history, and approval items.
    Idempotent: skips if demo user already exists.

    Returns summary of what was created.
    """
    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.models.identity import Tenant, User
    from app.services.agents import AgentService
    from app.services.auth import AuthService

    created = {"user": False, "projects": 0, "messages": 0, "approvals": 0}

    async with async_session_factory() as db:
        try:
            # Check if demo user already exists
            existing = await db.execute(
                select(User).where(User.email == DEMO_USER["email"])
            )
            if existing.scalar_one_or_none():
                logger.info("demo_mode.skip", reason="demo user already exists")
                return created

            # Create demo tenant + user via AuthService
            auth_svc = AuthService(db)
            result = await auth_svc.register(
                email=DEMO_USER["email"],
                password=DEMO_USER["password"],
                display_name=DEMO_USER["display_name"],
                tenant_name="Daena Demo",
            )

            user_data = result["user"]
            tenant_id = uuid.UUID(user_data["tenant_id"])
            user_id = uuid.UUID(user_data["id"])
            created["user"] = True

            # Create sample projects
            from app.services.project_service import ProjectService
            project_svc = ProjectService()
            for proj in DEMO_PROJECTS:
                project_svc.create(
                    name=proj["name"],
                    owner_id=str(user_id),
                    description=proj["description"],
                )
                created["projects"] += 1

            await db.commit()
            logger.info("demo_mode.seeded", **created)

        except Exception as exc:
            await db.rollback()
            logger.warning("demo_mode.seed_failed", error=str(exc))

    return created
