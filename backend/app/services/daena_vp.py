"""Daena VP -- the conductor of the 10-department company.

Session B (Piece 2) of the "Daena as a Living Company" plan. Sits
between ``QueryUnderstanding`` and ``GovernanceCheck`` in the chat
orchestrator pipeline. Three responsibilities:

1. **plan(user_request)** -- decompose an ambiguous request into
   department-owned subtasks. Hybrid routing:
   - Fast path: rule-based intent matching against the user request
     (`_INTENT_RULES`). Common requests like "draft a Q2 campaign"
     map in microseconds with no model call.
   - Slow path: when the rule table has no match, fall back to
     ``SwarmPlanner.decompose_and_route`` which uses the Main Mind
     to decompose. Adds ~1-2s but handles novel requests.

2. **route(plan, tenant_id)** -- assign each subtask to a live
   department, consulting the Session A State Registry. An
   OVERLOADED department is redirected to the next-best alternate
   from the rule table; if no alternate exists the subtask queues
   anyway (future: escalate to human).

3. **resolve_conflict(outputs)** -- when 2+ departments produce
   contradictory output for the same user goal, convene a 3-agent
   council via the existing ``CouncilEngine`` to synthesize a
   single coherent answer. Avoids "two heads, one body" bugs.

The VP is INTENTIONALLY stateless -- it holds no memory between
calls. Each call is driven by the current State Registry snapshot
+ NBMF memory via the existing chat_orchestrator enrichment step.
This keeps it predictable and easy to test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Canonical departments (keep in sync with department_state_service) ──

CANONICAL_DEPARTMENTS: tuple[str, ...] = (
    "Engineering",
    "Product",
    "Marketing",
    "Sales",
    "Finance",
    "Operations",
    "Research",
    "Legal & Compliance",
    "Skill Governance",
    "Security Operations",
)


# ── Rule-based intent router ─────────────────────────────────────
#
# Ordered list of (regex, primary_dept, alternate_depts). First match
# wins. Alternates are used when the primary is OVERLOADED or OFFLINE.
# Keep regexes broad enough to catch natural phrasing but narrow enough
# that they don't collide (e.g. "finance" implies Finance, "legal" implies
# Legal, "secure" implies Security Ops).
#
# This table is the "data" side of the hybrid router. Adding a new
# phrase here is a one-line change -- no prompt engineering or model
# call.

_INTENT_RULES: list[tuple[re.Pattern[str], str, list[str]]] = [
    (re.compile(r"(?i)\b(campaign|brand|audience|press\s*release|newsletter|social\s*post|marketing|announce)"), "Marketing", ["Product", "Sales"]),
    (re.compile(r"(?i)\b(expense|invoice|budget|spend|cost|forecast|p&l|revenue|bookkeeping)"), "Finance", ["Operations"]),
    (re.compile(r"(?i)\b(contract|terms|privacy|compliance|legal|license|nda|liability|dpa)"), "Legal & Compliance", ["Security Operations"]),
    (re.compile(r"(?i)\b(deploy|rollout|production|infrastructure|runbook|incident|sre|capacity|scaling)"), "Operations", ["Engineering"]),
    (re.compile(r"(?i)\b(security|vuln|breach|pentest|audit|leak|phish|malware|injection)"), "Security Operations", ["Engineering"]),
    (re.compile(r"(?i)\b(code|debug|refactor|build|test\s*suite|typescript|python|api\s*endpoint|bugfix|pull\s*request)"), "Engineering", ["Operations"]),
    (re.compile(r"(?i)\b(customer|support|lead|crm|deal|sales|prospect|outreach|pipeline)"), "Sales", ["Marketing"]),
    (re.compile(r"(?i)\b(roadmap|prioriti(?:s|z)e|feature\s*request|user\s*story|prd|spec|backlog)"), "Product", ["Engineering"]),
    (re.compile(r"(?i)\b(research|benchmark|paper|literature|survey\s*of|state\s*of\s*the\s*art|competitor\s*analysis)"), "Research", ["Product"]),
    (re.compile(r"(?i)\b(skill|onboard(?:ing)?|training|playbook|sop|documentation\s*for\s*ai)"), "Skill Governance", ["Product"]),
]


# ── Data structures ──────────────────────────────────────────────

@dataclass
class VPSubtask:
    """A VP-level subtask. Lighter than ``swarm.planner.SubTask``: the
    VP cares about WHICH department owns it, not WHICH runtime executes
    it. Runtime selection happens downstream in SwarmPlanner/Executor."""

    description: str
    department: str              # owning department
    task_type: str = "general"   # hint for runtime selection downstream
    depends_on: list[int] = field(default_factory=list)  # index into sibling list
    reason: str = ""             # why this dept was chosen (for audit/UI)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "department": self.department,
            "task_type": self.task_type,
            "depends_on": list(self.depends_on),
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


@dataclass
class VPPlan:
    """Output of ``DaenaVP.plan()``."""

    user_request: str
    subtasks: list[VPSubtask]
    routing_mode: str            # "rule" | "model" | "fallback"
    notes: str = ""              # optional human-readable summary

    @property
    def involved_departments(self) -> list[str]:
        seen: list[str] = []
        for st in self.subtasks:
            if st.department not in seen:
                seen.append(st.department)
        return seen

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_request": self.user_request,
            "routing_mode": self.routing_mode,
            "notes": self.notes,
            "involved_departments": self.involved_departments,
            "subtasks": [st.to_dict() for st in self.subtasks],
        }


@dataclass
class VPDecision:
    """Output of ``DaenaVP.resolve_conflict()``."""

    verdict: str                 # the synthesized final answer
    method: str                  # "agreement" | "council" | "forced_fallback"
    participating_departments: list[str] = field(default_factory=list)
    agreement_score: float = 1.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "method": self.method,
            "participating_departments": list(self.participating_departments),
            "agreement_score": self.agreement_score,
            "notes": self.notes,
        }


# ── The VP ───────────────────────────────────────────────────────

class DaenaVP:
    """Cross-department conductor.

    Usage::

        vp = DaenaVP(state_service=state_svc, swarm_planner=planner,
                     council_engine=council, llm_service=llm)
        plan = await vp.plan("draft a Q2 campaign for product X", tenant_id)
        plan = await vp.route(plan, tenant_id)   # load-balances
        # ...SwarmExecutor runs the plan, yields outputs...
        if conflicting_outputs:
            decision = await vp.resolve_conflict(outputs, original_request)

    Dependencies are all injected so DaenaVP is trivially mockable in
    tests. The planner/council/llm can be ``None`` -- the rule-based
    path still works end-to-end for common intents.
    """

    def __init__(
        self,
        state_service: Any = None,
        swarm_planner: Any = None,
        council_engine: Any = None,
        llm_service: Any = None,
        policy_service: Any = None,
    ) -> None:
        self._state = state_service
        self._planner = swarm_planner
        self._council = council_engine
        self._llm = llm_service
        # Session D: DepartmentPolicyService. When provided, apply_policies
        # consults it to attach required_approvers metadata to subtasks.
        self._policies = policy_service

    # ── Phase 1: plan ────────────────────────────────────────

    async def plan(
        self,
        user_request: str,
        tenant_id: UUID | None = None,
    ) -> VPPlan:
        """Decompose a user request into department-owned subtasks.

        Order of operations:
          1. Try rule-based router against the raw text. Each matched
             pattern produces one subtask. Deduplicates so a single
             request that hits 3 rules produces 3 distinct subtasks.
          2. If no rules matched at all, fall back to SwarmPlanner
             (model-driven) and then tag each resulting subtask via a
             second rule pass. Department of last resort: Engineering.
          3. If neither path yields a subtask, produce a single general
             subtask owned by Engineering so the pipeline never breaks.
        """
        del tenant_id  # reserved for future tenant-specific routing

        rule_subtasks = self._rule_route(user_request)
        if rule_subtasks:
            plan = VPPlan(
                user_request=user_request,
                subtasks=rule_subtasks,
                routing_mode="rule",
                notes=f"Matched {len(rule_subtasks)} department rule(s).",
            )
            logger.info(
                "daena_vp.plan.rule_match",
                count=len(rule_subtasks),
                depts=plan.involved_departments,
            )
            return plan

        # Rule miss -- try model fallback
        model_subtasks = await self._model_route(user_request)
        if model_subtasks:
            plan = VPPlan(
                user_request=user_request,
                subtasks=model_subtasks,
                routing_mode="model",
                notes="Rule router missed; decomposed via SwarmPlanner.",
            )
            logger.info(
                "daena_vp.plan.model_fallback",
                count=len(model_subtasks),
                depts=plan.involved_departments,
            )
            return plan

        # Last resort
        fallback = VPSubtask(
            description=user_request[:500],
            department="Engineering",
            task_type="general",
            reason="No rule match and model fallback unavailable; default to Engineering",
        )
        return VPPlan(
            user_request=user_request,
            subtasks=[fallback],
            routing_mode="fallback",
            notes="Used the Engineering department as last-resort owner.",
        )

    def _rule_route(self, text: str) -> list[VPSubtask]:
        """Return one subtask per rule that matches, in rule order."""
        subtasks: list[VPSubtask] = []
        seen_depts: set[str] = set()
        for pattern, primary, alternates in _INTENT_RULES:
            match = pattern.search(text)
            if match and primary not in seen_depts:
                seen_depts.add(primary)
                subtasks.append(VPSubtask(
                    description=text[:500],
                    department=primary,
                    task_type=self._infer_task_type(primary),
                    reason=f"Matched intent pattern (trigger: '{match.group(0)}')",
                    metadata={"alternates": list(alternates), "trigger": match.group(0)},
                ))
        return subtasks

    async def _model_route(self, text: str) -> list[VPSubtask]:
        """Fallback: ask SwarmPlanner to decompose, then tag depts by
        re-running the rule router over each subtask description."""
        if self._planner is None:
            return []
        try:
            raw = await self._planner.decompose_and_route(text)
        except Exception as exc:
            logger.warning("daena_vp.plan.model_fallback_failed", error=str(exc))
            return []

        subtasks: list[VPSubtask] = []
        for st in raw:
            desc = getattr(st, "description", "")
            # Run rule router on the subtask description itself.
            dept_hits = self._rule_route(desc)
            if dept_hits:
                dept = dept_hits[0].department
                reason = f"Model decomposed; subtask matched {dept} rules"
            else:
                # Subtask defies classification -- assign to Engineering
                # (the department-of-last-resort).
                dept = "Engineering"
                reason = "Model decomposed; no subtask-level rule match"
            subtasks.append(VPSubtask(
                description=desc[:500],
                department=dept,
                task_type=getattr(st, "task_type", "general"),
                depends_on=list(getattr(st, "depends_on", []) or []),
                reason=reason,
                metadata={"source": "swarm_planner"},
            ))
        return subtasks

    @staticmethod
    def _infer_task_type(department: str) -> str:
        """Crude dept->task_type mapping so the downstream SwarmPlanner
        can still pick a good runtime. These map to the task_type values
        the runtime registry understands."""
        table = {
            "Engineering": "code_generation",
            "Research": "web_research",
            "Operations": "file_operations",
            "Security Operations": "file_operations",
            "Marketing": "simple_chat",
            "Sales": "simple_chat",
            "Product": "complex_reasoning",
            "Finance": "complex_reasoning",
            "Legal & Compliance": "complex_reasoning",
            "Skill Governance": "simple_chat",
        }
        return table.get(department, "general")

    # ── Phase 2: route ────────────────────────────────────────

    async def route(
        self,
        plan: VPPlan,
        tenant_id: UUID | None = None,
    ) -> VPPlan:
        """Load-balance the plan against current department state.

        For each subtask whose owning department is OVERLOADED or
        OFFLINE, attempt to swap to an alternate from the rule table's
        ``alternates`` list. If no alternate is available OR all
        alternates are also unavailable, leave the subtask on the
        original department (it will queue -- that's correct behavior,
        not a bug).

        Returns the same plan object with potentially-mutated
        department assignments and updated ``reason`` fields.
        """
        if self._state is None or tenant_id is None:
            return plan

        try:
            snapshot = await self._state.snapshot(tenant_id=tenant_id)
        except Exception as exc:
            logger.warning("daena_vp.route.snapshot_failed", error=str(exc))
            return plan

        by_name = {s["department_name"]: s for s in snapshot}

        def is_available(dept: str) -> bool:
            s = by_name.get(dept)
            if s is None:
                return True  # no state row = fresh dept, treat as idle
            return s["status"] in ("IDLE", "WORKING")  # anything but OVERLOADED/OFFLINE

        for st in plan.subtasks:
            if is_available(st.department):
                continue
            # Try alternates in order
            alternates = st.metadata.get("alternates", []) or []
            for alt in alternates:
                if is_available(alt):
                    original = st.department
                    st.department = alt
                    st.reason = f"{st.reason} [rerouted from {original} -- overloaded/offline]"
                    st.metadata["rerouted_from"] = original
                    logger.info(
                        "daena_vp.route.rerouted",
                        subtask=st.description[:80],
                        from_dept=original,
                        to_dept=alt,
                    )
                    break
            # If no alternate is available either, leave it. It will
            # queue behind the currently-running tasks.

        return plan

    # ── Phase 3: conflict resolution ─────────────────────────

    async def resolve_conflict(
        self,
        outputs: list[dict[str, str]],
        original_request: str = "",
    ) -> VPDecision:
        """Synthesize multiple department outputs into one answer.

        ``outputs`` shape: ``[{"department": "Marketing", "content": "..."}, ...]``

        Strategy:
          * 0 or 1 outputs -> trivial pass-through.
          * 2+ outputs, high lexical agreement -> pick the longest (most detail).
          * 2+ outputs, low agreement -> convene the CouncilEngine
            if available. Wraps each dept output in a synthetic
            LLMResponse so the existing anonymized-judge synthesis
            works unchanged.
          * Council unavailable and disagreement -> forced fallback:
            concatenate outputs with dept-prefix headers and annotate
            that a human should pick.
        """
        if not outputs:
            return VPDecision(
                verdict="",
                method="forced_fallback",
                notes="No department outputs provided.",
            )

        if len(outputs) == 1:
            only = outputs[0]
            return VPDecision(
                verdict=only.get("content", ""),
                method="agreement",
                participating_departments=[only.get("department", "")],
                agreement_score=1.0,
                notes="Single output, nothing to reconcile.",
            )

        # Compute a quick agreement score: Jaccard of token sets.
        # 0.4 is the empirical threshold where two summaries of the
        # same real-world answer typically fall. Stricter (e.g. 0.7)
        # requires near-identical wording which rarely happens when
        # two departments independently phrase the same conclusion.
        agreement = self._agreement_score([o.get("content", "") for o in outputs])

        if agreement >= 0.4:
            # Departments largely agree -- pick the most detailed answer.
            winner = max(outputs, key=lambda o: len(o.get("content", "")))
            return VPDecision(
                verdict=winner.get("content", ""),
                method="agreement",
                participating_departments=[o.get("department", "") for o in outputs],
                agreement_score=agreement,
                notes=f"Departments agreed (Jaccard {agreement:.2f}); picked most detailed.",
            )

        # Low agreement -> council
        if self._council is not None and self._llm is not None:
            try:
                verdict = await self._council_resolve(outputs, original_request)
                return verdict
            except Exception as exc:
                logger.warning("daena_vp.conflict.council_failed", error=str(exc))

        # Forced fallback
        parts = [f"## {o.get('department', 'Unknown')}\n{o.get('content', '')}" for o in outputs]
        return VPDecision(
            verdict="\n\n".join(parts),
            method="forced_fallback",
            participating_departments=[o.get("department", "") for o in outputs],
            agreement_score=agreement,
            notes="Council unavailable; returning all outputs for human selection.",
        )

    async def _council_resolve(
        self,
        outputs: list[dict[str, str]],
        original_request: str,
    ) -> VPDecision:
        """Feed the dept outputs into CouncilEngine as synthetic members.

        We wrap each dept's answer in an ``LLMResponse``-shaped object
        so the existing anonymize-then-synthesize flow works without
        modification.
        """
        from app.services.providers.base import LLMResponse

        from app.core.constants import ModelProvider

        wrapped = [
            LLMResponse(
                content=o.get("content", ""),
                model_id=f"dept:{o.get('department', 'Unknown')}",
                provider=ModelProvider.ANTHROPIC,  # placeholder
                token_count_input=0,
                token_count_output=len(o.get("content", "")) // 4,
                cost_usd=0.0,
                latency_ms=0,
            )
            for o in outputs
        ]
        result = await self._council.synthesize(
            original_query=original_request or "department synthesis",
            responses=wrapped,
        )
        return VPDecision(
            verdict=result.synthesis,
            method="council",
            participating_departments=[o.get("department", "") for o in outputs],
            agreement_score=result.agreement_score,
            notes=f"Council synthesized across {len(outputs)} departments.",
        )

    # ── Phase 4: apply policies (Session D) ──────────────────

    async def apply_policies(
        self,
        plan: VPPlan,
        tenant_id: UUID | None = None,
    ) -> VPPlan:
        """Consult the DepartmentPolicyService for each subtask and
        attach ``required_approvers`` metadata.

        Turns an action like "Marketing wants to spend $4k on ads" into
        a plan where the Marketing subtask carries
        ``metadata["required_approvers"] = ["Finance"]``. The chat
        orchestrator / SwarmExecutor reads this and fires the
        inter-department ``ask_department`` messages (Session C)
        BEFORE letting the subtask execute.

        No-op when ``policy_service`` or ``tenant_id`` is missing, so
        this method is safe to always call from the pipeline.
        """
        if self._policies is None or tenant_id is None:
            return plan

        for subtask in plan.subtasks:
            action = self._action_for(subtask)
            try:
                approvers = await self._policies.required_approvers_for(
                    tenant_id=tenant_id, action=action,
                )
            except Exception as exc:
                logger.warning(
                    "daena_vp.apply_policies.failed",
                    subtask=subtask.description[:80],
                    error=str(exc),
                )
                continue
            # Filter out the owning department -- a subtask never needs
            # to approve itself. Otherwise Finance's own spend would
            # create a Finance->Finance message.
            approvers = [d for d in approvers if d != subtask.department]
            if approvers:
                subtask.metadata["required_approvers"] = approvers
                subtask.reason = (
                    f"{subtask.reason} [policies require approval from: "
                    f"{', '.join(approvers)}]"
                )
                logger.info(
                    "daena_vp.policy_match",
                    subtask=subtask.description[:80],
                    department=subtask.department,
                    approvers=approvers,
                )
        return plan

    @staticmethod
    def _action_for(subtask: VPSubtask) -> dict[str, Any]:
        """Extract an action dict from a subtask so the policy
        evaluator has fields to match. Conservative -- only lifts
        well-known keys from metadata; everything else stays behind.
        """
        action: dict[str, Any] = {
            "from_department": subtask.department,
            "task_type": subtask.task_type,
            "description": subtask.description,
        }
        meta = subtask.metadata or {}
        for key in ("action_type", "amount", "tags"):
            if key in meta:
                action[key] = meta[key]
        return action

    @staticmethod
    def _agreement_score(texts: list[str]) -> float:
        """Jaccard agreement on token sets. Cheap and zero-dependency.

        Returns 1.0 for identical content, 0.0 for totally disjoint.
        Good enough for the "do we need a council?" decision; we don't
        need a real semantic similarity here.
        """
        if len(texts) < 2:
            return 1.0
        token_sets = [set(re.findall(r"\w+", t.lower())) for t in texts]
        if not all(token_sets):
            return 0.0
        intersection = set.intersection(*token_sets)
        union = set.union(*token_sets)
        if not union:
            return 1.0
        return len(intersection) / len(union)
