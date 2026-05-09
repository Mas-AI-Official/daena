"""DaenaSelfAgent — Daena's tools for managing her own configuration.

The other DaenaBot agents reach OUTWARD: file system, terminal, browser,
Gmail, MCP servers, vulnerabilities. This agent reaches INWARD: changes
which mind is primary, which model the router prefers, which routing
mode is active.

Why this exists (2026-05-09 — operator's frustration with hardcoded
aliasing): "i want daena think, real-time think, not hardcoded".
This agent stays INTENTIONALLY DUMB about which model maps to which
runtime. It exposes:

  - get_runtime_state        — read the live truth from User.settings
                               + the runtime_registry. NO INTERPRETATION.
  - list_available_minds     — enumerate the LIVE registry: which
                               runtime adapters are loaded right now,
                               which models the registry knows about.
                               This is the source of truth the LLM
                               consults instead of any static map.
  - set_primary_mind         — write explicit runtime_id (+ optional
                               explicit model_id) to User.settings.
                               Validates the runtime_id exists in the
                               live registry. NO ALIAS RESOLUTION.

WHY no alias map: when the user says "switch to claude 4.7 max", the
LLM (Claude/Codex/Gemini) has the world knowledge to map that string
to runtime_id="claude_code" + model_id="claude-opus-4-7". My job is
to give the LLM the LIVE LIST and let it reason. Hardcoding aliases
would make Daena dumber than her own brain.

Governance: tier 1 (Logged). Just-an-audit-log, no approval queue.
The action is bounded to the operator's own settings; nothing else
can be affected by it.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm.attributes import flag_modified

from app.core.logging import get_logger
from app.services.daenabot._base_agent import BaseAgent

logger = get_logger(__name__)


class DaenaSelfAgent(BaseAgent):
    """Self-management agent for Daena's own runtime configuration."""

    agent_name = "settings"

    OPERATION_ACTION_MAP: dict[str, str] = {
        "get_runtime_state": "READ",
        "set_primary_mind": "WRITE_SETTINGS",
        "list_available_minds": "READ",
    }

    def __init__(
        self,
        db,
        user_id: UUID | str,
        model_registry: Any = None,
    ) -> None:
        # Stateful: the agent needs the per-request DB session and the
        # acting user's id so it can resolve and rewrite User.settings.
        self._db = db
        # Accept str (orchestrator path) or UUID (DaenaBot direct path);
        # normalize so SQL bindings always get the right type.
        self._user_id = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
        # Optional: live ModelRegistry instance from app.state. When the
        # orchestrator dispatches into us it can pass the live registry
        # so list_available_minds returns CURRENT discovered models
        # instead of a fresh-but-uninitialized instance.
        self._model_registry = model_registry

    async def execute(
        self, operation: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        ops = {
            "get_runtime_state": self.get_runtime_state,
            "set_primary_mind": self.set_primary_mind,
            "list_available_minds": self.list_available_minds,
        }
        fn = ops.get(operation)
        if fn is None:
            raise ValueError(
                f"DaenaSelfAgent: unknown operation {operation!r}. "
                f"Supported: {list(ops)}"
            )
        return await fn(**params)

    # ── operations ─────────────────────────────────────────────

    async def get_runtime_state(self) -> dict[str, Any]:
        """Read every fact about Daena's current runtime configuration.

        The single source of truth for "which mind/brain are you using?"
        questions. NEVER guess from training data; ALWAYS read this.
        """
        from app.models.identity import User

        user = await self._db.get(User, self._user_id)
        settings_blob: dict[str, Any] = {}
        if user and user.settings:
            settings_blob = dict(user.settings)

        primary_runtime = settings_blob.get("primary_runtime") or "claude_code"
        preferred_model = (
            settings_blob.get("preferred_model")
            or settings_blob.get("primary_runtime_model")
        )

        # Live online runtimes
        online: list[str] = []
        try:
            from app.core.events import get_runtime_registry
            from app.services.runtimes.base_adapter import RuntimeStatus

            reg = get_runtime_registry()
            for rid in ("claude_code", "codex", "gemini_cli", "grok_cli", "vllm", "ollama"):
                with _silent():
                    if reg.get_health(rid) == RuntimeStatus.ONLINE:
                        online.append(rid)
        except Exception:
            logger.debug("daena_self.runtime_registry_unavailable", exc_info=True)

        result = {
            "primary_runtime": primary_runtime,
            "preferred_model": preferred_model,
            "online_runtimes": online,
            "user_email": user.email if user else None,
            "tenant_id": str(user.tenant_id) if user else None,
        }
        logger.info("daena_self.runtime_state_read", **result)
        return self._result("get_runtime_state", result)

    async def list_available_minds(self) -> dict[str, Any]:
        """Enumerate every runtime Daena can switch primary to + the
        models the live model_registry knows about.

        This is the LLM's source of truth when it needs to translate
        user phrases like "claude 4.7 max" or "the cheapest gemini"
        into a concrete (runtime_id, model_id). NO STATIC ALIAS MAP —
        the answer comes from what's actually registered RIGHT NOW.

        Returns:
          {
            "runtimes": [
              {runtime_id, display_name, status, models: [model_id, ...]},
              ...
            ],
            "default_models_per_provider": {provider_value: model_id, ...}
          }
        """
        out: dict[str, Any] = {"runtimes": [], "default_models_per_provider": {}}

        # 1. Live runtime adapters
        try:
            from app.core.events import get_runtime_registry
            reg = get_runtime_registry()
            for rid in ("claude_code", "codex", "gemini_cli", "grok_cli", "vllm", "ollama"):
                adapter = reg.get_adapter(rid) if hasattr(reg, "get_adapter") else None
                if adapter is None:
                    continue
                health = "unknown"
                with _silent():
                    health = str(reg.get_health(rid))
                out["runtimes"].append({
                    "runtime_id": rid,
                    "display_name": getattr(adapter, "display_name", rid),
                    "status": health,
                    "models": [],  # filled below from model_registry
                })
        except Exception as exc:
            logger.debug("daena_self.runtime_list_failed", error=str(exc))

        # 2. Live model registry — every model_id the registry has
        # discovered, grouped by provider so the LLM can map user
        # phrases like "the new claude" to a concrete model.
        try:
            mreg = self._model_registry
            if mreg is None:
                from app.services.model_registry import ModelRegistry
                mreg = ModelRegistry()
            all_models = []
            if hasattr(mreg, "list_all_models"):
                all_models = await mreg.list_all_models()
            by_provider: dict[str, list[str]] = {}
            for m in all_models:
                pid = getattr(getattr(m, "provider", None), "value", None) or "unknown"
                mid = getattr(m, "model_id", None) or getattr(m, "id", None)
                if not mid:
                    continue
                by_provider.setdefault(pid, []).append(str(mid))
            # Map provider -> runtime_id and attach models
            provider_to_runtime = {
                "ANTHROPIC": "claude_code",
                "OPENAI": "codex",
                "GEMINI": "gemini_cli",
                "GOOGLE": "gemini_cli",
                "GROK": "grok_cli",
                "XAI": "grok_cli",
                "OLLAMA": "ollama",
                "VLLM": "vllm",
            }
            for entry in out["runtimes"]:
                rid = entry["runtime_id"]
                matching_models: list[str] = []
                for prov, models in by_provider.items():
                    if provider_to_runtime.get(prov.upper()) == rid:
                        matching_models.extend(models)
                # Dedup, stable order
                seen: set[str] = set()
                entry["models"] = [m for m in matching_models if not (m in seen or seen.add(m))]
            out["default_models_per_provider"] = {
                p: (models[0] if models else None) for p, models in by_provider.items()
            }
        except Exception as exc:
            logger.debug("daena_self.model_list_failed", error=str(exc))

        return self._result("list_available_minds", out)

    async def set_primary_mind(
        self,
        runtime_id: str,
        model_id: str | None = None,
    ) -> dict[str, Any]:
        """Write explicit runtime_id (and optional model_id) to User.settings.

        REQUIRES explicit IDs. NO alias resolution. The caller (typically
        the LLM acting on a user message like "switch to claude 4.7") is
        expected to:
          1. Call ``list_available_minds`` to see what's actually
             registered + online right now.
          2. Use its world knowledge to map the user's natural language
             to the correct runtime_id (and optionally a model_id from
             the model list).
          3. Call this with the resolved IDs.

        If you call with an unknown runtime_id, this returns an error
        listing the registered ones so the LLM can retry.

        Returns the previous + current values so the audit row can show
        what actually changed.
        """
        if not runtime_id:
            return self._error(
                "set_primary_mind",
                "runtime_id is required. Call list_available_minds first to see options.",
            )

        # Validate against live registry
        try:
            from app.core.events import get_runtime_registry
            reg = get_runtime_registry()
            registered: list[str] = []
            ri_attr = getattr(reg, "registered_ids", None)
            if callable(ri_attr):
                registered = list(ri_attr())
            elif ri_attr is not None:
                registered = list(ri_attr)
            if registered and runtime_id not in registered:
                return self._error(
                    "set_primary_mind",
                    f"Unknown runtime_id {runtime_id!r}. "
                    f"Registered runtimes: {sorted(registered)}. "
                    f"Call list_available_minds to see what's online + authenticated.",
                )
        except Exception as exc:
            logger.debug("daena_self.registry_check_skipped", error=str(exc))

        from app.models.identity import User

        user = await self._db.get(User, self._user_id)
        if user is None:
            return self._error(
                "set_primary_mind",
                f"User {self._user_id} not found.",
            )

        current = dict(user.settings or {})
        before = {
            "primary_runtime": current.get("primary_runtime"),
            "preferred_model": current.get("preferred_model"),
        }

        current["primary_runtime"] = runtime_id
        if model_id is not None:
            current["preferred_model"] = model_id
        user.settings = current
        flag_modified(user, "settings")
        await self._db.flush()
        await self._db.commit()

        after = {
            "primary_runtime": current.get("primary_runtime"),
            "preferred_model": current.get("preferred_model"),
        }
        logger.info(
            "daena_self.primary_mind_changed",
            user_id=str(self._user_id),
            before=before,
            after=after,
        )
        return self._result(
            "set_primary_mind",
            {
                "before": before,
                "after": after,
                "message": (
                    f"Primary mind set to {after['primary_runtime']}"
                    + (f" (model: {after['preferred_model']})" if after['preferred_model'] else "")
                ),
            },
        )


class _silent:
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return True
