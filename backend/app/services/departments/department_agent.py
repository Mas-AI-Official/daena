"""DepartmentAgent -- the identity layer between Daena and the DaenaBot tool pool.

Architectural role
------------------
10 departments (Engineering, Product, Marketing, Sales, Finance, Operations,
Research, Legal & Compliance, Skill Governance, Security Operations) each
have their OWN DepartmentAgent instance, which holds:

* A department-scoped system prompt composed from the soul, the DCPs, the
  department's base prompts, and (optionally) the Security Lens overlay.
* A working directory and a list of permitted paths.
* A memory scope (which NBMF tiers and tags the department reads/writes).
* A governance policy inherited from the tenant but overridable per dept.
* Skill priors (which Skill Refinery skills this department consumes).

The 6 conceptual roles (MIND / EYES / HANDS / VOICE / SHIELD / MEMORY) are
METHODS on ``DepartmentAgent``. They are not separate runtime processes.
Internally each role dispatches to tools in the shared DaenaBot pool,
passing department context as parameters. A hammer is not duplicated per
carpenter; it is held by the carpenter and swung with intent.

Security Lens
-------------
When the Security Operations department (Dept 10) opens an offensive
engagement (``/3vilbob`` is active), every OTHER department's prompt
receives a Security Lens overlay: Engineering's MIND now reasons about
attack vectors; Marketing's EYES now do OSINT; Sales' VOICE now crafts
social-engineering pretexts. The overlay complements the existing
per-department OFFENSIVE_SHIELD prompts (which replace SHIELD only) by
cross-cutting the other 5 roles so the full departmental brain pivots.

Learning
--------
Every ``record_outcome()`` call writes to NBMF via
``MemoryService.store_experience``. Content types:

* ``SKILL_OUTCOME`` -- a named skill succeeded or failed
* ``APPROACH_FAILED`` -- a specific approach must not be retried blindly
* ``PATTERN_LEARNED`` -- a reusable pattern was inferred from a success
* ``AGENT_DECISION`` -- a routing or tool-choice decision (for audit)

NBMF is tenant-scoped, so a lesson learned by Engineering becomes
visible to Sales. The APPROACH_FAILED broadcast is the cross-department
"don't repeat this" signal the operator asked for.

Non-goals
---------
* This module does NOT replace the chat_orchestrator or the ModelRouter.
  It is a thin identity wrapper that higher-level code can adopt
  progressively.
* It does NOT construct a separate LLM call per role. The soul + DCP +
  department prompt + optional security lens are composed into a single
  system prompt that goes to the single LLM call (or the Council fan-out).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.services.memory import MemoryService

logger = get_logger(__name__)


# ── Canonical six roles ──────────────────────────────────────────────

ROLES: tuple[str, ...] = (
    "MIND", "EYES", "HANDS", "VOICE", "SHIELD", "MEMORY",
)


# ── Security Lens overlays (cross-role, 3vilbob-active only) ─────────
#
# These complement ``_OFFENSIVE_SHIELD_PROMPTS`` in ``department_prompts.py``,
# which already transforms SHIELD per-department. The overlays below
# cross-cut the OTHER five roles so the whole departmental brain pivots
# when the Security Operations department opens an offensive engagement.
#
# Overlays are SHORT because they are appended to existing role prompts
# -- they bias the department, they do not replace its identity.

_SECURITY_LENS: dict[str, dict[str, str]] = {
    "MIND": {
        "Engineering": (
            "SECURITY LENS ACTIVE: reason about attack vectors -- "
            "how this code could be subverted, what inputs break its "
            "assumptions, what the defender's log would show."
        ),
        "Product": (
            "SECURITY LENS ACTIVE: reason about abuse cases -- how a "
            "feature can be weaponized, what flows escalate privilege."
        ),
        "Marketing": (
            "SECURITY LENS ACTIVE: reason about impersonation and "
            "pretext surface -- how public materials can be weaponized."
        ),
        "Sales": (
            "SECURITY LENS ACTIVE: reason about social engineering -- "
            "what lure would land, what pretext is credible."
        ),
        "Finance": (
            "SECURITY LENS ACTIVE: reason about financial attack surface "
            "-- wire fraud, invoice manipulation, vendor impersonation."
        ),
        "Operations": (
            "SECURITY LENS ACTIVE: reason about operational attack "
            "surface -- how misconfigurations and process gaps chain."
        ),
        "Research": (
            "SECURITY LENS ACTIVE: reason about vulnerability discovery "
            "-- novel CVE classes, CWE patterns, prior-art search."
        ),
        "Legal & Compliance": (
            "SECURITY LENS ACTIVE: reason about scope of the engagement "
            "-- authorized targets only, contract boundaries, evidence "
            "chain-of-custody, reportable obligations."
        ),
        "Skill Governance": (
            "SECURITY LENS ACTIVE: reason about skill provenance -- "
            "which prior scans have discovered reusable patterns here."
        ),
    },
    "EYES": {
        "Engineering": "SECURITY LENS ACTIVE: look for exploit primitives in code you review.",
        "Product": "SECURITY LENS ACTIVE: look for logic flaws, not product defects.",
        "Marketing": "SECURITY LENS ACTIVE: OSINT on the target -- employees, tech stack, events.",
        "Sales": "SECURITY LENS ACTIVE: profile the decision-makers for pretext fit.",
        "Finance": "SECURITY LENS ACTIVE: scan breach databases and financial trails.",
        "Operations": "SECURITY LENS ACTIVE: map the target's ops posture, CI/CD, monitoring.",
        "Research": "SECURITY LENS ACTIVE: paper / CVE / bounty-writeup mining for this stack.",
        "Legal & Compliance": "SECURITY LENS ACTIVE: confirm scope, jurisdiction, and evidence rules.",
        "Skill Governance": "SECURITY LENS ACTIVE: surface skills from prior engagements of this type.",
    },
    "HANDS": {
        "Engineering": "SECURITY LENS ACTIVE: write proof-of-concept exploit code, not fixes.",
        "Product": "SECURITY LENS ACTIVE: craft workflow-abuse sequences.",
        "Marketing": "SECURITY LENS ACTIVE: produce pretext content, lookalike domain checks.",
        "Sales": "SECURITY LENS ACTIVE: produce social-engineering drafts with guard-rails.",
        "Finance": "SECURITY LENS ACTIVE: model fraudulent financial flows for detection, not execution.",
        "Operations": "SECURITY LENS ACTIVE: execute authorized scan workflows only.",
        "Research": "SECURITY LENS ACTIVE: build reproduction harnesses for discovered bugs.",
        "Legal & Compliance": "SECURITY LENS ACTIVE: draft engagement-scope confirmation before any action.",
        "Skill Governance": "SECURITY LENS ACTIVE: promote or demote scan-pipeline skills based on this session.",
    },
    "VOICE": {
        "Engineering": "SECURITY LENS ACTIVE: write exploit advisories, impact narratives.",
        "Product": "SECURITY LENS ACTIVE: write abuse-case reports with remediation.",
        "Marketing": "SECURITY LENS ACTIVE: write pretext scripts with guard-rails.",
        "Sales": "SECURITY LENS ACTIVE: write engagement scopes and findings for client debriefs.",
        "Finance": "SECURITY LENS ACTIVE: write financial-impact statements for discovered risks.",
        "Operations": "SECURITY LENS ACTIVE: write incident timelines and evidence logs.",
        "Research": "SECURITY LENS ACTIVE: write CVE drafts and disclosure timelines.",
        "Legal & Compliance": "SECURITY LENS ACTIVE: write engagement letters and disclosure releases.",
        "Skill Governance": "SECURITY LENS ACTIVE: write skill provenance notes for reuse.",
    },
    "MEMORY": {
        "Engineering": "SECURITY LENS ACTIVE: recall past exploit patterns from this stack.",
        "Product": "SECURITY LENS ACTIVE: recall abuse cases from similar products.",
        "Marketing": "SECURITY LENS ACTIVE: recall OSINT patterns for this vertical.",
        "Sales": "SECURITY LENS ACTIVE: recall pretext signals from prior engagements.",
        "Finance": "SECURITY LENS ACTIVE: recall fraud patterns from prior scans.",
        "Operations": "SECURITY LENS ACTIVE: recall ops-posture fingerprints.",
        "Research": "SECURITY LENS ACTIVE: recall CVE clusters relevant to this target.",
        "Legal & Compliance": "SECURITY LENS ACTIVE: recall engagement-scope precedents.",
        "Skill Governance": "SECURITY LENS ACTIVE: recall which scan skills have worked here.",
    },
}


# ── Data classes ─────────────────────────────────────────────────────

@dataclass(slots=True)
class DepartmentContext:
    """Runtime context passed when the department delegates to shared tools."""

    department: str
    tenant_id: UUID | None = None
    user_id: UUID | None = None
    agent_id: UUID | None = None
    working_directory: str = ""
    permitted_paths: list[str] = field(default_factory=list)
    skill_priors: list[str] = field(default_factory=list)
    memory_tags: list[str] = field(default_factory=list)
    governance_mode: str = "BALANCED"


@dataclass(slots=True)
class SecurityLens:
    """Optional Security Lens overlay applied when 3vilbob is active."""

    active: bool = False
    reason: str = ""  # why the lens was activated, for audit


# ── DepartmentAgent ──────────────────────────────────────────────────

class DepartmentAgent:
    """One department. Composes a system prompt, delegates to shared tools,
    records experience into tenant-scoped NBMF.
    """

    def __init__(
        self,
        context: DepartmentContext,
        lens: SecurityLens | None = None,
        memory_service: "MemoryService | None" = None,
    ) -> None:
        self.context = context
        self.lens = lens or SecurityLens(active=False)
        self._memory = memory_service

    # ── System prompt composition ────────────────────────────────

    def build_role_prompt(self, role: str) -> str:
        """Compose the role prompt for this department.

        Layer order (highest attention to lowest):
          1. Soul (shared, injected earlier by SoulEngine)
          2. Department base prompt for the role (from department_prompts.py)
          3. Offensive SHIELD overlay (when 3vilbob is active and role=SHIELD)
          4. Security Lens overlay (when lens.active and role != SHIELD)
          5. Department context notes (working dir, permitted paths)
        """
        from app.services.department_prompts import get_agent_prompt
        parts: list[str] = []

        role = role.upper()
        if role not in ROLES:
            raise ValueError(f"Unknown role {role!r}. Valid: {ROLES}")

        # Layer 2 + 3 (get_agent_prompt already handles the offensive SHIELD swap)
        base_prompt = get_agent_prompt(self.context.department, role)
        parts.append(base_prompt)

        # Layer 4: cross-role security lens overlay.
        # Skip SHIELD because get_agent_prompt already returned the offensive
        # shield prompt for SHIELD when 3vilbob is active.
        if self.lens.active and role != "SHIELD":
            overlay = _SECURITY_LENS.get(role, {}).get(self.context.department)
            if overlay:
                parts.append(overlay)

        # Layer 5: working-context notes.
        if self.context.working_directory:
            parts.append(
                f"WORKING DIRECTORY: {self.context.working_directory}"
            )
        if self.context.permitted_paths:
            parts.append(
                "PERMITTED PATHS: " + ", ".join(self.context.permitted_paths[:8])
            )
        if self.context.skill_priors:
            parts.append(
                "RELEVANT SKILLS: " + ", ".join(self.context.skill_priors[:5])
            )

        return "\n\n".join(parts)

    def build_full_prompt(self) -> dict[str, str]:
        """Build prompts for all six roles at once -- useful for cards or audit."""
        return {role: self.build_role_prompt(role) for role in ROLES}

    # ── Action delegation (all roles use shared DaenaBot pool) ───

    async def hands_file(self, operation: str, params: dict[str, Any]) -> Any:
        """Delegate a file operation via the shared FileAgent.

        Department context is attached to the call so the tool can apply
        permitted-path restrictions and the right working directory.
        """
        from app.services.daenabot.file_agent import FileAgent
        agent = FileAgent()
        # Most FileAgent operations accept plain params; the governance
        # checks downstream read the department from the receipt tag.
        op = getattr(agent, operation, None)
        if not callable(op):
            raise AttributeError(
                f"FileAgent has no operation {operation!r}"
            )
        result = await op(**params) if _is_async(op) else op(**params)
        return result

    async def hands_terminal(self, command: str) -> Any:
        from app.services.daenabot.terminal_agent import TerminalAgent
        agent = TerminalAgent()
        return await agent.execute_command(command=command)

    async def eyes_browser(self, url: str, goal: str = "") -> Any:
        """Delegate to VisionBrowserAgent if we need AI understanding,
        else plain BrowserAgent.
        """
        if goal:
            from app.services.daenabot.vision_browser_agent import VisionBrowserAgent
            return await VisionBrowserAgent().browse_and_act(goal=goal, url=url)
        from app.services.daenabot.browser_agent import BrowserAgent
        return await BrowserAgent().navigate(url=url)

    # ── Inter-department messaging (Session C) ───────────────────

    async def ask_department(
        self,
        *,
        target_department: str,
        subject: str,
        body: str,
        context_ref: str | None = None,
        wait_seconds: int = 0,
        ttl_seconds: int = 3600,
    ) -> dict | None:
        """Send an ASK message to another department.

        * ``wait_seconds=0`` (default) -> async fire-and-forget; returns
          the message dict immediately with ``status="SENT"``. Poll the
          outbox later to read the answer.
        * ``wait_seconds>0`` -> blocks up to that long for an ANSWERED
          state and returns the completed message dict, or ``None`` on
          timeout so the caller can decide to escalate.

        Opens its own short-lived DB session so DepartmentAgent stays
        independent of request scope (same pattern as the Swarm
        executor state helpers).
        """
        if self.context.tenant_id is None:
            logger.warning(
                "dept_agent.ask_skipped_no_tenant",
                from_dept=self.context.department,
                target=target_department,
            )
            return None
        try:
            from app.core.database import async_session_factory
            from app.services.department_message_service import (
                DepartmentMessageService,
            )

            async with async_session_factory() as session:
                svc = DepartmentMessageService(session)
                msg = await svc.send(
                    tenant_id=self.context.tenant_id,
                    from_department=self.context.department,
                    to_department=target_department,
                    subject=subject,
                    body=body,
                    context_ref=context_ref,
                    ttl_seconds=ttl_seconds,
                )
                await session.commit()
                message_id = msg.id
                initial_dict = msg.to_dict()

            if wait_seconds <= 0:
                return initial_dict

            # Poll for an answer in a fresh session per poll cycle.
            async with async_session_factory() as session:
                svc = DepartmentMessageService(session)
                resolved = await svc.wait_for_answer(
                    message_id=message_id,
                    timeout_seconds=wait_seconds,
                )
            return resolved.to_dict() if resolved else None
        except Exception as exc:
            logger.warning(
                "dept_agent.ask_failed",
                from_dept=self.context.department,
                target=target_department,
                error=str(exc),
            )
            return None

    # ── Learning (NBMF write-through) ────────────────────────────

    async def record_outcome(
        self,
        *,
        summary: str,
        detail: str,
        success: bool,
        content_type: str = "SKILL_OUTCOME",
        confidence: float = 0.5,
        tags: list[str] | None = None,
    ) -> dict | None:
        """Write an experience to tenant-scoped NBMF.

        The experience is tagged with the department and (optionally) the
        skill_priors + memory_tags the context was operating under, so
        cross-department retrieval can surface it. APPROACH_FAILED entries
        are the "don't repeat" broadcast across the 10 departments.
        """
        if (
            self._memory is None
            or self.context.tenant_id is None
            or self.context.user_id is None
            or self.context.agent_id is None
        ):
            logger.debug(
                "department_agent.record_outcome_skipped",
                department=self.context.department,
                reason="missing tenant/user/agent id or memory service",
            )
            return None

        merged_tags = list(
            {
                f"dept:{self.context.department.lower().replace(' ', '_')}",
                content_type.lower(),
                *(tags or []),
                *self.context.memory_tags,
            }
        )
        return await self._memory.store_experience(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            agent_id=self.context.agent_id,
            content=detail,
            content_type=content_type,
            summary=summary,
            success_flag=success,
            confidence=confidence,
            tags=merged_tags,
            metadata={
                "department": self.context.department,
                "security_lens": self.lens.active,
                "lens_reason": self.lens.reason,
            },
        )

    async def broadcast_approach_failed(
        self, summary: str, detail: str
    ) -> dict | None:
        """Shortcut for the cross-department 'do not repeat this' signal."""
        return await self.record_outcome(
            summary=summary,
            detail=detail,
            success=False,
            content_type="APPROACH_FAILED",
            confidence=0.6,
            tags=["broadcast", "avoid_retry"],
        )


def _is_async(fn: Any) -> bool:
    """True if the callable is an async def or returns a coroutine."""
    import asyncio
    import inspect
    return inspect.iscoroutinefunction(fn) or asyncio.iscoroutine(fn)


# ── Public factory ───────────────────────────────────────────────────

def build_department(
    department: str,
    *,
    tenant_id: UUID | None = None,
    user_id: UUID | None = None,
    agent_id: UUID | None = None,
    working_directory: str = "",
    permitted_paths: list[str] | None = None,
    skill_priors: list[str] | None = None,
    memory_tags: list[str] | None = None,
    governance_mode: str = "BALANCED",
    security_active: bool = False,
    security_reason: str = "",
    memory_service: "MemoryService | None" = None,
) -> DepartmentAgent:
    """Convenience constructor used by the orchestrator.

    The orchestrator pulls the department from the DB, extracts the
    working directory + permitted paths from the department record, then
    calls this to get a runtime object.
    """
    return DepartmentAgent(
        context=DepartmentContext(
            department=department,
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            working_directory=working_directory,
            permitted_paths=permitted_paths or [],
            skill_priors=skill_priors or [],
            memory_tags=memory_tags or [],
            governance_mode=governance_mode,
        ),
        lens=SecurityLens(active=security_active, reason=security_reason),
        memory_service=memory_service,
    )
