"""Policy service -- evaluate trigger conditions + manage CRUD.

Session D. Used by:

* ``DaenaVP.apply_policies(plan)`` -- attaches ``required_approvers``
  to each subtask in a plan based on matching policies.
* ``/api/v1/department-policies`` REST -- operator UI for rule editing.
* First-run seeder at startup / migration time -- installs 5 default
  policies so a brand-new tenant has reasonable approval chains from
  day one.

Trigger condition schema
------------------------
::

    {
      "conditions": [
        {"field": "amount", "op": "gte", "value": 500},
        {"field": "from_department", "op": "eq", "value": "Marketing"}
      ]
    }

All conditions AND together. Supported operators:

* ``eq`` / ``ne`` -- exact equality on scalars
* ``gt`` / ``gte`` / ``lt`` / ``lte`` -- numeric comparison
* ``in`` -- value is in a list
* ``contains`` -- for strings: substring match (case-insensitive);
  for lists: element-in-list

For OR semantics, create multiple policies. Keeps the evaluator
trivial to reason about and fast to execute.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.department_policy import POLICY_TYPE_VALUES, DepartmentPolicy

logger = get_logger(__name__)


# ── Default seed policies ───────────────────────────────────────

# Each seed has a ``seed_key`` so subsequent startups can detect
# already-installed rows and skip them. Operators can edit a seeded
# policy freely -- we match on seed_key, not on full content equality.

DEFAULT_POLICIES: list[dict[str, Any]] = [
    {
        "seed_key": "expense_over_500",
        "name": "Expense over $500 requires Finance",
        "description": (
            "Any spend of $500 or more must be reviewed by Finance before "
            "execution. Matches the operator's Finance-2k-vs-Engineering-4k "
            "scenario as the primary approval gate."
        ),
        "policy_type": "EXPENSE",
        "trigger_condition": {"conditions": [{"field": "amount", "op": "gte", "value": 500}]},
        "required_approvers": ["Finance"],
    },
    {
        "seed_key": "external_comms_legal",
        "name": "External communications require Legal",
        "description": (
            "Any copy, claim, or asset that ships to external audiences "
            "(customers, partners, press) must be reviewed by Legal & "
            "Compliance for defensibility."
        ),
        "policy_type": "EXTERNAL_COMMS",
        "trigger_condition": {"conditions": [{"field": "action_type", "op": "eq", "value": "external_comms"}]},
        "required_approvers": ["Legal & Compliance"],
    },
    {
        "seed_key": "prod_deploy_operations",
        "name": "Production deploys require Operations",
        "description": (
            "Any change that reaches a production environment must be "
            "reviewed by Operations. Staging / dev deploys are unaffected."
        ),
        "policy_type": "DEPLOYMENT",
        "trigger_condition": {"conditions": [{"field": "action_type", "op": "eq", "value": "prod_deploy"}]},
        "required_approvers": ["Operations"],
    },
    {
        "seed_key": "data_export_security",
        "name": "External data export requires Security Operations",
        "description": (
            "Any operation that moves customer or proprietary data outside "
            "Daena's environment (public APIs, downloads, exports) must be "
            "reviewed by Security Operations."
        ),
        "policy_type": "EXTERNAL_DATA",
        "trigger_condition": {"conditions": [{"field": "action_type", "op": "eq", "value": "external_data_export"}]},
        "required_approvers": ["Security Operations"],
    },
    {
        "seed_key": "new_vendor_finance_legal",
        "name": "New vendor requires Finance + Legal",
        "description": (
            "Adding a new external vendor (SaaS subscription, contractor, "
            "data provider) needs both Finance and Legal to sign off on "
            "contract terms and budget impact."
        ),
        "policy_type": "NEW_VENDOR",
        "trigger_condition": {"conditions": [{"field": "action_type", "op": "eq", "value": "new_vendor"}]},
        "required_approvers": ["Finance", "Legal & Compliance"],
    },
]


class DepartmentPolicyService:
    """Policy CRUD + matching engine."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── CRUD ────────────────────────────────────────────────────

    async def create(
        self,
        *,
        tenant_id: UUID,
        name: str,
        policy_type: str,
        trigger_condition: dict,
        required_approvers: list[str],
        description: str = "",
        escalation_chain: list[str] | None = None,
        enabled: bool = True,
        seed_key: str = "",
    ) -> DepartmentPolicy:
        if policy_type not in POLICY_TYPE_VALUES:
            raise ValueError(
                f"policy_type must be one of {list(POLICY_TYPE_VALUES)}",
            )
        if not required_approvers:
            raise ValueError("required_approvers must list at least one department")
        policy = DepartmentPolicy(
            tenant_id=tenant_id,
            name=name[:120],
            description=description[:500],
            policy_type=policy_type,
            trigger_condition=trigger_condition,
            required_approvers=list(required_approvers),
            escalation_chain=list(escalation_chain or []),
            enabled=enabled,
            seed_key=seed_key,
        )
        self._db.add(policy)
        await self._db.flush()
        return policy

    async def list_policies(
        self,
        *,
        tenant_id: UUID,
        include_disabled: bool = False,
    ) -> list[DepartmentPolicy]:
        stmt = select(DepartmentPolicy).where(DepartmentPolicy.tenant_id == tenant_id)
        if not include_disabled:
            stmt = stmt.where(DepartmentPolicy.enabled.is_(True))
        stmt = stmt.order_by(DepartmentPolicy.created_at.asc())
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        *,
        policy_id: UUID,
        updates: dict[str, Any],
    ) -> DepartmentPolicy:
        stmt = select(DepartmentPolicy).where(DepartmentPolicy.id == policy_id)
        policy = (await self._db.execute(stmt)).scalar_one_or_none()
        if policy is None:
            raise ValueError(f"Policy {policy_id} not found")
        allowed = {
            "name", "description", "trigger_condition",
            "required_approvers", "escalation_chain", "enabled",
        }
        for k, v in updates.items():
            if k in allowed:
                setattr(policy, k, v)
        await self._db.flush()
        # Refresh so server-managed columns (created_at / updated_at)
        # are eagerly loaded before the caller serializes -- otherwise
        # accessing them later triggers a lazy load outside the async
        # greenlet context and raises MissingGreenlet.
        await self._db.refresh(policy)
        return policy

    async def delete(self, *, policy_id: UUID) -> None:
        stmt = select(DepartmentPolicy).where(DepartmentPolicy.id == policy_id)
        policy = (await self._db.execute(stmt)).scalar_one_or_none()
        if policy is None:
            return
        await self._db.delete(policy)
        await self._db.flush()

    # ── Matching engine ────────────────────────────────────────

    async def find_matching_policies(
        self,
        *,
        tenant_id: UUID,
        action: dict[str, Any],
    ) -> list[DepartmentPolicy]:
        """Return all enabled policies whose trigger_condition matches.

        ``action`` is a free-form dict produced by DaenaVP / chat
        orchestrator. Fields referenced by the seeded policies:
          * ``action_type``: "expense" | "external_comms" | "prod_deploy" | ...
          * ``amount``: numeric (in USD, no currency conversion for v1)
          * ``from_department``: string
          * ``tags``: list[str]

        Evaluator ignores unknown fields so a partial action dict
        can still match policies whose conditions cover only the
        known keys.
        """
        policies = await self.list_policies(
            tenant_id=tenant_id, include_disabled=False,
        )
        return [p for p in policies if self._evaluate(p.trigger_condition or {}, action)]

    async def required_approvers_for(
        self,
        *,
        tenant_id: UUID,
        action: dict[str, Any],
    ) -> list[str]:
        """Union of approvers across all matching policies. Preserves
        first-match ordering so deterministic for tests + UI."""
        matches = await self.find_matching_policies(tenant_id=tenant_id, action=action)
        out: list[str] = []
        seen: set[str] = set()
        for policy in matches:
            for dept in policy.required_approvers or []:
                if dept not in seen:
                    seen.add(dept)
                    out.append(dept)
        return out

    # ── Seed / first-run ───────────────────────────────────────

    async def ensure_defaults(self, *, tenant_id: UUID) -> int:
        """Install default policies for a tenant that does not have
        them yet. Idempotent via seed_key match. Returns the number
        of policies inserted (0 on subsequent calls)."""
        existing_stmt = select(DepartmentPolicy.seed_key).where(
            DepartmentPolicy.tenant_id == tenant_id,
            DepartmentPolicy.seed_key != "",
        )
        existing = {
            row[0] for row in (await self._db.execute(existing_stmt)).all()
        }
        inserted = 0
        for seed in DEFAULT_POLICIES:
            if seed["seed_key"] in existing:
                continue
            await self.create(
                tenant_id=tenant_id,
                name=seed["name"],
                description=seed["description"],
                policy_type=seed["policy_type"],
                trigger_condition=seed["trigger_condition"],
                required_approvers=seed["required_approvers"],
                seed_key=seed["seed_key"],
            )
            inserted += 1
        if inserted:
            logger.info("dept_policy.seed_installed", count=inserted)
        return inserted

    # ── Internal: evaluator ────────────────────────────────────

    @staticmethod
    def _evaluate(trigger: dict, action: dict) -> bool:
        """Return True iff every condition in ``trigger`` is satisfied
        by ``action``.

        Empty conditions list = always true (useful for "apply to
        everything" rules). Missing field in action = condition fails
        safe (never matches).
        """
        conditions = trigger.get("conditions") or []
        if not conditions:
            return True

        for cond in conditions:
            field = cond.get("field")
            op = cond.get("op")
            target = cond.get("value")
            if field is None or op is None:
                return False  # malformed condition fails closed
            if field not in action:
                return False

            actual = action[field]
            if not _apply_operator(op, actual, target):
                return False
        return True


def _apply_operator(op: str, actual: Any, target: Any) -> bool:
    """Evaluate one condition. Coerces numeric strings to Decimal so
    callers can pass "500" or 500 or 500.0 interchangeably."""
    try:
        if op == "eq":
            return actual == target
        if op == "ne":
            return actual != target
        if op in ("gt", "gte", "lt", "lte"):
            a = _to_decimal(actual)
            b = _to_decimal(target)
            if a is None or b is None:
                return False
            if op == "gt":
                return a > b
            if op == "gte":
                return a >= b
            if op == "lt":
                return a < b
            if op == "lte":
                return a <= b
        if op == "in":
            if isinstance(target, (list, tuple, set)):
                return actual in target
            return False
        if op == "contains":
            # Both string-contains and list-contains
            if isinstance(actual, str) and isinstance(target, str):
                return target.lower() in actual.lower()
            if isinstance(actual, (list, tuple, set)):
                return target in actual
            return False
    except (TypeError, ValueError):
        return False
    return False


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None
