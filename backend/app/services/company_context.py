"""Runtime company-context store.

Phase 1 F4 (2026-04-24). Bridges the Company Mode form (founder activates
Daena as VP of MAS-AI Technologies Inc.) and the Soul Engine (which builds
every chat system prompt). Before this module existed the founder could
fill the form, hit Activate, see a confirmation toast -- and then chat
with a Daena that had no idea who its company was. The brief lived on
disk at ``backend/app/soul/company_seed.md`` but soul_engine never
loaded it. Masoud surfaced it as "you load something else, it's not
loading my company set up." This is the connector.

Lifecycle:
1. On activation (POST /company-mode/activate), the API writes the
   brief to disk AND calls ``company_context_store.set(tenant_id, ctx)``.
2. On startup, ``hydrate_from_disk()`` walks the soul directory for
   any saved company_seed.md and re-populates the store so a server
   restart doesn't lose the founder's company identity.
3. On every chat request, the orchestrator calls
   ``company_context_store.get(tenant_id)`` and passes the result into
   ``SoulEngine.get_soul_prompt(..., company_context=ctx)``.
4. On logout / explicit deactivate, callers may invoke ``clear``.

Thread safety: the store is in-process and protected by an RLock so
async tasks across worker threads don't race.

This is intentionally NOT a database table for the v1 connector. The
brief is small, mutates rarely, and lives on disk in a gitignored path
(founder IP per CLAUDE.md rule 15). The store is the runtime cache.
"""

from __future__ import annotations

from pathlib import Path
from threading import RLock

from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)


class CompanyContext(BaseModel):
    """The compact company brief carried into every system prompt.

    Mirrors the form fields in CompanyModePage, but flattened to the
    minimum a soul prompt actually needs. We do not pass governance
    flags (auto_send, require_founder_approval) -- those are runtime
    policy concerns, not soul-prompt context.
    """

    company_name: str
    one_liner: str
    target_customer: str
    pain: str
    promise: str
    proof_points: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    tone: str = "professional"

    def to_soul_inject(self, department: str | None = None) -> str:
        """Render the inject string the soul engine prepends."""
        actor = department or "the founder"
        proofs = " | ".join(self.proof_points) if self.proof_points else "(none yet)"
        chans = ", ".join(self.channels) if self.channels else "(unset)"
        return (
            "## Company Context (founder mode)\n"
            f"Company: {self.company_name}\n"
            f"Mission: {self.one_liner}\n"
            f"Target customer: {self.target_customer}\n"
            f"Pain we solve: {self.pain}\n"
            f"Our promise: {self.promise}\n"
            f"Proof points: {proofs}\n"
            f"Channels: {chans}\n"
            f"Tone: {self.tone}\n\n"
            f"When operating as {actor}, prioritize this company's GTM "
            "strategy and customer context above generic department behaviors. "
            "Speak in first person on behalf of the company when appropriate.\n"
        )


class CompanyContextStore:
    """Thread-safe per-tenant company context cache."""

    def __init__(self) -> None:
        self._store: dict[str, CompanyContext] = {}
        self._lock = RLock()

    def set(self, tenant_id: str, ctx: CompanyContext) -> None:
        with self._lock:
            self._store[tenant_id] = ctx
        logger.info(
            "company_context.set",
            tenant_id=tenant_id,
            company=ctx.company_name,
        )

    def get(self, tenant_id: str) -> CompanyContext | None:
        with self._lock:
            return self._store.get(tenant_id)

    def clear(self, tenant_id: str) -> None:
        with self._lock:
            removed = self._store.pop(tenant_id, None)
        if removed:
            logger.info(
                "company_context.cleared",
                tenant_id=tenant_id,
                company=removed.company_name,
            )

    def hydrate_from_disk(self, soul_root: Path) -> int:
        """Best-effort hydration. Walks ``soul_root`` for ``company_seed.md``.

        v1 only handles the founder-tenant single-seed file at
        ``soul_root/company_seed.md`` (matches the seed_path in
        company_mode.py). Future tenants will live at
        ``soul_root/tenants/<tenant_id>/company_seed.md`` and the same
        loader will pick them up.
        """
        loaded = 0
        try:
            single = soul_root / "company_seed.md"
            if single.exists():
                ctx = _parse_seed_file(single)
                if ctx:
                    # Founder tenant uses tenant_id="founder" as the bootstrap
                    # key. The api layer remaps to the real tenant UUID on
                    # first activate; the on-disk seed is per-instance not
                    # per-tenant for the single-tenant founder build.
                    self._store["founder"] = ctx
                    loaded += 1
                    logger.info(
                        "company_context.hydrated",
                        path=str(single),
                        company=ctx.company_name,
                    )

            tenants_dir = soul_root / "tenants"
            if tenants_dir.exists():
                for tenant_dir in tenants_dir.iterdir():
                    if not tenant_dir.is_dir():
                        continue
                    seed = tenant_dir / "company_seed.md"
                    if seed.exists():
                        ctx = _parse_seed_file(seed)
                        if ctx:
                            self._store[tenant_dir.name] = ctx
                            loaded += 1
        except Exception as exc:
            logger.warning("company_context.hydrate_failed", error=str(exc))

        return loaded


def _parse_seed_file(path: Path) -> CompanyContext | None:
    """Parse the YAML-frontmatter seed file written by company_mode.py.

    Tolerates the v0 schema (which used company_one_liner / customer_pain
    / our_promise) and remaps to the canonical CompanyContext fields. We
    keep the legacy field names usable so existing on-disk seeds still
    hydrate without forcing the founder to rewrite the file.
    """
    try:
        import yaml

        raw = path.read_text(encoding="utf-8")
        if not raw.startswith("---"):
            return None
        parts = raw.split("---", 2)
        if len(parts) < 3:
            return None
        data = yaml.safe_load(parts[1].strip()) or {}
        if not isinstance(data, dict):
            return None
        return CompanyContext(
            company_name=str(data.get("company_name", "")),
            one_liner=str(data.get("one_liner") or data.get("company_one_liner", "")),
            target_customer=str(data.get("target_customer", "")),
            pain=str(data.get("pain") or data.get("customer_pain", "")),
            promise=str(data.get("promise") or data.get("our_promise", "")),
            proof_points=list(data.get("proof_points") or []),
            channels=list(data.get("channels") or []),
            tone=str(data.get("tone", "professional")),
        )
    except Exception as exc:
        logger.warning("company_context.parse_failed", path=str(path), error=str(exc))
        return None


# Singleton instance imported by soul_engine and chat_orchestrator.
company_context_store = CompanyContextStore()
