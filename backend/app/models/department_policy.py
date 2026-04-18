"""Cross-department policies -- the rule book for the unified company.

Session D (Piece 4) of the "Daena as a Living Company" plan. Closes
the loop: Session A tracks state, Session B plans + routes, Session C
carries messages, Session D tells the VP *when* to trigger which
reviewer.

A policy answers: "given an action Daena is about to take, which
other departments need to sign off first?"

Examples encoded by the default seed:

* ``expense>=$500`` -> Finance must approve
* ``external_comms`` -> Legal & Compliance must approve
* ``prod_deploy`` -> Operations must approve
* ``external_data_export`` -> Security Operations must approve
* ``new_vendor`` -> Finance + Legal must both approve

Design decisions
----------------
* **trigger_condition is JSONB** with a small declarative schema so
  operators can edit rules in the UI without code deploys. Schema is
  documented in ``DepartmentPolicyService._evaluate``.
* **required_approvers is a JSON array of department names**, not a
  table of foreign keys. Departments are a stable enum-in-code
  (``CANONICAL_DEPARTMENTS``); FKing to a department table would
  add ceremony without benefit.
* **escalation_chain is optional** -- if set, a denial from the
  first approver falls through to the second. Most policies need
  only a primary approver.
* **Multiple policies can match a single action**. find_matching
  returns all -- the caller unions required_approvers. This lets
  "expense>=500" (Finance) and "external_comms" (Legal) BOTH fire
  when a Marketing spend hits both thresholds.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin

# Policy categories. CUSTOM escapes this enum for operator-defined
# rules that do not fit the built-in shapes.
POLICY_TYPE_VALUES = (
    "EXPENSE",
    "DEPLOYMENT",
    "EXTERNAL_COMMS",
    "EXTERNAL_DATA",
    "NEW_VENDOR",
    "CUSTOM",
)


class DepartmentPolicy(Base, TenantMixin, TimestampMixin):
    """One rule the VP consults before routing a subtask.

    Scoped to tenant -- every customer can tune their own approval
    chains without affecting other tenants.
    """

    __tablename__ = "department_policies"
    __table_args__ = (
        Index(
            "ix_department_policies_type_enabled",
            "tenant_id", "policy_type", "enabled",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    policy_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # Declarative trigger. Shape::
    #   {"conditions": [{"field": "amount", "op": "gte", "value": 500}, ...]}
    # All conditions AND together. For OR, create a second policy.
    trigger_condition: Mapped[dict] = mapped_column(
        JSONBCompat, nullable=False, server_default="{}",
    )
    # Ordered list of department names. Caller unions across policies.
    required_approvers: Mapped[list] = mapped_column(
        JSONBCompat, nullable=False, server_default="[]",
    )
    # When set, denial by required_approvers[0] escalates to these.
    # Reserved for future use -- first-pass callers ignore this.
    escalation_chain: Mapped[list] = mapped_column(
        JSONBCompat, nullable=False, server_default="[]",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true",
    )
    # Seeded rows get this marker so startup reseed logic knows not to
    # overwrite operator customizations. Empty string for operator-
    # created policies.
    seed_key: Mapped[str] = mapped_column(String(80), nullable=False, server_default="")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "policy_type": self.policy_type,
            "trigger_condition": dict(self.trigger_condition or {}),
            "required_approvers": list(self.required_approvers or []),
            "escalation_chain": list(self.escalation_chain or []),
            "enabled": self.enabled,
            "seed_key": self.seed_key,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
