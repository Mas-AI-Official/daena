"""DaenaSelfAgent — Daena's tools for managing her own configuration.

The other DaenaBot agents reach OUTWARD: file system, terminal, browser,
Gmail, MCP servers, vulnerabilities. This agent reaches INWARD: changes
which mind is primary, which model the router prefers, which routing
mode is active.

Why this exists (2026-05-09): the operator complaint was "I asked Daena
to switch primary mind to claude-4.7 and she replied 'go to Settings
> Model' — that's a chatbot answer, not an agent answer." The agentic
answer is "done, primary_mind = claude_code, model = claude-opus-4-7"
backed by a real settings write.

Operations are LOW-RISK by design:
  - get_runtime_state   READ-ONLY. Returns the live truth: which runtime
                        is primary, which model, what's online, what
                        subscriptions are valid. Drives "which mind are
                        you using?" honestly.
  - set_primary_mind    Updates User.settings JSONB primary_runtime +
                        preferred_model. Does NOT touch external state,
                        does NOT escape the tenant, does NOT write to
                        provider configs. Reversible at any time by
                        re-calling with the previous values.
  - list_available_minds READ-ONLY. Returns runtime_id + display_name +
                        installed/online/authenticated for each known
                        runtime. The set the operator can switch to.

Governance: tier 1 (Logged). Just-an-audit-log, no approval queue.
The action is bounded to the operator's own settings; nothing else
can be affected by it.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.logging import get_logger
from app.services.daenabot._base_agent import BaseAgent

logger = get_logger(__name__)


# Aliases the user may type in chat. Maps any token to the canonical
# runtime_id Daena uses internally. Kept here (not in intent_parser)
# so the agent can self-report the supported aliases via list_available_minds.
_RUNTIME_ALIASES: dict[str, str] = {
    # Anthropic / Claude
    "claude": "claude_code",
    "claude code": "claude_code",
    "claude-code": "claude_code",
    "claude_code": "claude_code",
    "claude cli": "claude_code",
    "anthropic": "claude_code",
    # OpenAI / Codex
    "codex": "codex",
    "openai": "codex",
    "chatgpt": "codex",
    "gpt": "codex",
    # Google / Gemini
    "gemini": "gemini_cli",
    "gemini cli": "gemini_cli",
    "gemini_cli": "gemini_cli",
    "google": "gemini_cli",
    # xAI / Grok
    "grok": "grok_cli",
    "grok_cli": "grok_cli",
    "xai": "grok_cli",
    # Local
    "ollama": "ollama",
    "vllm": "vllm",
    "llama": "vllm",
    "local": "vllm",
    "llama-server": "vllm",
}


# Map model-name shorthand to (runtime_id, canonical_model_id) so
# "switch to claude-opus-4-7" or "use claude 4.7" set BOTH the runtime
# and the model preference.
_MODEL_ALIASES: dict[str, tuple[str, str]] = {
    "claude-opus-4-7": ("claude_code", "claude-opus-4-7"),
    "claude opus 4.7": ("claude_code", "claude-opus-4-7"),
    "claude 4.7": ("claude_code", "claude-opus-4-7"),
    "opus 4.7": ("claude_code", "claude-opus-4-7"),
    "claude-sonnet-4-6": ("claude_code", "claude-sonnet-4-6"),
    "claude 4.6": ("claude_code", "claude-sonnet-4-6"),
    "sonnet 4.6": ("claude_code", "claude-sonnet-4-6"),
    "claude-haiku-4-5": ("claude_code", "claude-haiku-4-5-20251001"),
    "haiku 4.5": ("claude_code", "claude-haiku-4-5-20251001"),
    "gpt-5.5": ("codex", "gpt-5.5"),
    "gpt 5.5": ("codex", "gpt-5.5"),
    "gemini 2.5 pro": ("gemini_cli", "gemini-2.5-pro"),
    "gemini-2.5-pro": ("gemini_cli", "gemini-2.5-pro"),
}


def resolve_mind_alias(text: str) -> tuple[str, str | None]:
    """Resolve a free-text mind name to (runtime_id, model_id_or_None).

    Returns the runtime_id and an optional model_id. Raises ValueError
    if the alias can't be resolved.
    """
    norm = text.strip().lower().replace("_", " ").replace("-", " ")
    # Tightest match first: full model alias
    if norm in _MODEL_ALIASES:
        rt, mid = _MODEL_ALIASES[norm]
        return rt, mid
    # Then runtime aliases
    norm_token = norm.replace(" ", "_")
    if norm_token in _RUNTIME_ALIASES:
        return _RUNTIME_ALIASES[norm_token], None
    if norm in _RUNTIME_ALIASES:
        return _RUNTIME_ALIASES[norm], None
    # Last try: substring match on common keywords
    for alias, runtime_id in _RUNTIME_ALIASES.items():
        if alias in norm:
            return runtime_id, None
    raise ValueError(
        f"Unknown mind/brain alias: {text!r}. "
        f"Try one of: claude, codex, gemini, grok, ollama, vllm."
    )


class DaenaSelfAgent(BaseAgent):
    """Self-management agent for Daena's own runtime configuration."""

    agent_name = "settings"

    OPERATION_ACTION_MAP: dict[str, str] = {
        "get_runtime_state": "READ",
        "set_primary_mind": "WRITE_SETTINGS",
        "list_available_minds": "READ",
    }

    def __init__(self, db, user_id: UUID | str) -> None:
        # Stateful: the agent needs the per-request DB session and the
        # acting user's id so it can resolve and rewrite User.settings.
        self._db = db
        # Accept str (orchestrator path) or UUID (DaenaBot direct path);
        # normalize so SQL bindings always get the right type.
        self._user_id = user_id if isinstance(user_id, UUID) else UUID(str(user_id))

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
        """Enumerate every runtime Daena can switch primary to.

        Returns runtime_id + display_name + installed/online/authenticated
        flags. The UI uses this to render a picker; the LLM uses it to
        validate a switch request before calling set_primary_mind.
        """
        try:
            from app.core.events import get_runtime_registry
            reg = get_runtime_registry()
            entries = []
            for rid in ("claude_code", "codex", "gemini_cli", "grok_cli", "vllm", "ollama"):
                adapter = reg.get_adapter(rid) if hasattr(reg, "get_adapter") else None
                if adapter is None:
                    continue
                health = "unknown"
                with _silent():
                    health = str(reg.get_health(rid))
                entries.append({
                    "runtime_id": rid,
                    "display_name": getattr(adapter, "display_name", rid),
                    "installed": True,
                    "status": health,
                })
            return self._result("list_available_minds", {"runtimes": entries})
        except Exception as exc:
            logger.warning("daena_self.list_failed", error=str(exc))
            return self._error("list_available_minds", str(exc))

    async def set_primary_mind(
        self,
        runtime_id: str | None = None,
        model_id: str | None = None,
        mind_alias: str | None = None,
    ) -> dict[str, Any]:
        """Update primary_runtime + preferred_model in User.settings JSONB.

        Accepts either an explicit runtime_id (and optional model_id)
        OR a free-text alias like "claude 4.7" or "gpt-5.5". Resolves
        the alias via the module-level alias table, validates that the
        runtime exists, then writes the JSONB and returns the new state.

        Returns the previous + current values so the audit row can show
        what actually changed.
        """
        # Resolve free-text alias if explicit values weren't given
        resolved_runtime = runtime_id
        resolved_model = model_id
        if not resolved_runtime:
            if not mind_alias:
                return self._error(
                    "set_primary_mind",
                    "Either runtime_id or mind_alias is required.",
                )
            try:
                resolved_runtime, alias_model = resolve_mind_alias(mind_alias)
                if not resolved_model:
                    resolved_model = alias_model
            except ValueError as exc:
                return self._error("set_primary_mind", str(exc))

        # Validate the runtime exists
        try:
            from app.core.events import get_runtime_registry
            reg = get_runtime_registry()
            registered = list(getattr(reg, "registered_ids", lambda: [])() if callable(getattr(reg, "registered_ids", None)) else getattr(reg, "registered_ids", []))
            if registered and resolved_runtime not in registered:
                return self._error(
                    "set_primary_mind",
                    f"Unknown runtime_id: {resolved_runtime!r}. "
                    f"Available: {sorted(registered)}",
                )
        except Exception as exc:
            # Registry not populated (e.g. tests); fall through and trust
            # the alias map. The setting write is reversible anyway.
            logger.debug("daena_self.registry_check_skipped", error=str(exc))

        # Read current state, write new state, persist
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

        current["primary_runtime"] = resolved_runtime
        if resolved_model:
            current["preferred_model"] = resolved_model
        user.settings = current
        # JSONB columns require explicit dirty marking on SQLAlchemy
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
