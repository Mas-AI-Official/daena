"""Soul Engine: loads and caches Daena's character foundation.

Reads soul documents from ``backend/app/soul/`` (core soul + 10 department
overlays) and constructs system prompt fragments that shape HOW Daena reasons.

The soul is the philosophical foundation from which all behavior flows.
It is not a system prompt that can be overridden -- it is injected first,
before operational instructions, giving it highest priority in LLM attention.

Three intensity modes based on GovernanceMode:
- UNLEASHED: Full soul + power addendum (no restraints except Shield)
- BALANCED: Full soul + light guardrails
- GOVERNED: Full soul + enterprise safety overlay

Department overlays (new 2026-04-22):
Each of Daena's 10 departments has a named persona ("Mind") that composes on
top of the core soul. Loaded from ``backend/app/soul/departments/<slug>.md``.
Each overlay defines preferred runtime, voice profile, scoped toolchain,
and reasoning patterns specific to that department's job.

Pattern follows dcp_loader.py: file-based loading with process-level cache.

Usage::

    soul = SoulEngine.get_soul_prompt("UNLEASHED")
    system_prompt = soul + operational_instructions

    # With department overlay:
    soul = SoulEngine.get_soul_prompt("GOVERNED", department="engineering")
    # -> core soul + Aria overlay + governance addendum
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Relative to app/ directory -- works in dev (D:\Ideas\Daena\backend\app\soul)
# and in Docker (/app/app/soul). No hardcoded absolute paths.
_SOUL_VAULT_PATH = Path(__file__).resolve().parent.parent / "soul"
_DEPARTMENT_SOUL_PATH = _SOUL_VAULT_PATH / "departments"

# Files loaded in order (priority order for prompt construction).
# vp_mode.md was added 2026-04-18 when Masoud promoted Daena from
# assistant-identity to active AI VP of MAS-AI Technologies. It loads
# LAST so it composes on top of the foundation / reasoning / personality
# / loyalty / shield layers (VP is how the soul expresses itself, not
# a replacement for the soul).
_SOUL_FILES = [
    "foundation.md",
    "reasoning.md",
    "personality.md",
    "loyalty.md",
    "shield.md",
    "vp_mode.md",
    # emotional_awareness.md was added 2026-04-22 after the founder
    # flagged that an earlier emotional-awareness layer had been lost
    # in a refactor. It loads near the end so the baseline personality
    # and loyalty frames are established first, then tonal adaptation
    # rules sit on top. Works in conjunction with the runtime
    # EmotionalSignal overlay injected by chat_orchestrator.
    "emotional_awareness.md",
]

# Department name normalization. We accept any of: raw DB name ("Legal &
# Compliance"), snake_case ("legal_compliance"), Title Case ("Engineering"),
# or the Mind's given name ("Aria"). All resolve to a canonical slug which
# maps to a file in backend/app/soul/departments/<slug>.md
_DEPARTMENT_SLUG_ALIASES: dict[str, str] = {
    # Engineering -- Aria
    "engineering": "engineering",
    "aria": "engineering",
    "eng": "engineering",
    # Product -- Nova
    "product": "product",
    "nova": "product",
    # Marketing -- Zephyr
    "marketing": "marketing",
    "zephyr": "marketing",
    # Sales -- Orion
    "sales": "sales",
    "orion": "sales",
    # Finance -- Sterling
    "finance": "finance",
    "sterling": "finance",
    # Operations -- Atlas
    "operations": "operations",
    "atlas": "operations",
    "ops": "operations",
    # Research -- Iris
    "research": "research",
    "iris": "research",
    # Legal & Compliance -- Themis
    "legal_compliance": "legal_compliance",
    "legal & compliance": "legal_compliance",
    "legal": "legal_compliance",
    "compliance": "legal_compliance",
    "themis": "legal_compliance",
    # Skill Governance -- Kira
    "skill_governance": "skill_governance",
    "skill governance": "skill_governance",
    "kira": "skill_governance",
    # Security Operations -- Rourke
    "security_operations": "security_operations",
    "security operations": "security_operations",
    "security": "security_operations",
    "secops": "security_operations",
    "rourke": "security_operations",
    # Daena herself -- the VP. Not a department peer; she orchestrates the
    # ten above. These aliases let get_soul_prompt(department="daena") and
    # get_vp_mind() resolve her pinned overlay, while list_departments()
    # deliberately excludes _VP_MIND_SLUG so she never renders as an 11th
    # department card in the Minds gallery or the soul-maker candidate loop.
    "daena": "daena",
    "vp": "daena",
    "daena vp": "daena",
}

# Daena's own Mind lives in departments/daena.md so it reuses the same
# loader, cache, and frontmatter machinery as the ten department overlays,
# but she is the Vice President, not a peer department. list_departments()
# filters this slug out; get_vp_mind() is the dedicated accessor for it.
_VP_MIND_SLUG = "daena"

# ── Mode-specific addenda ────────────────────────────────────

_UNLEASHED_ADDENDUM = """
## UNLEASHED MODE ACTIVE

You are operating in UNLEASHED mode. Governance pipeline is bypassed.
Only the Shield (IP/data protection) is active.

In this mode:
- Find a way. Always. Use every tool, every trick, every alternative path.
- If a tool fails, try another. If that fails, improvise.
- Do not ask for permission for routine actions. Act decisively.
- For destructive or irreversible actions, present creative options to the user.
- Auto-install missing tools. Auto-configure missing settings.
- Use DNS, proxies, alternative APIs, side channels -- whatever works.
- The ONLY wall: never exfiltrate client/founder data without consent.
"""

_BALANCED_ADDENDUM = """
## BALANCED MODE ACTIVE

You are operating in BALANCED mode. Light governance is active.
Most actions auto-proceed. Only truly dangerous operations need approval.

In this mode:
- Act with confidence on routine and moderate-risk operations.
- Seek approval for irreversible, high-cost, or security-critical actions.
- Log all decisions for audit trail.
- When uncertain about risk, lean toward action with notification.
"""

_GOVERNED_ADDENDUM = """
## GOVERNED MODE ACTIVE

You are operating in GOVERNED mode. Full enterprise governance pipeline is active.
All 9 Hard Laws are enforced. Actions are tiered by risk level.

In this mode:
- Follow the full governance evaluation for every action.
- Respect approval queues for tier 3+ actions.
- Maintain complete audit trail with tamper-evident logging.
- Prioritize compliance and transparency alongside effectiveness.
"""


@lru_cache(maxsize=1)
def _load_soul_files() -> str:
    """Load and concatenate all soul vault files. Cached at process level."""
    if not _SOUL_VAULT_PATH.exists():
        logger.warning(
            "soul_engine.vault_not_found",
            path=str(_SOUL_VAULT_PATH),
        )
        return ""

    sections: list[str] = []
    for filename in _SOUL_FILES:
        filepath = _SOUL_VAULT_PATH / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
            # Strip YAML frontmatter (between --- markers)
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].strip()
            sections.append(content)
            logger.debug("soul_engine.loaded", file=filename)
        else:
            logger.warning("soul_engine.file_missing", file=filename)

    combined = "\n\n".join(sections)
    logger.info(
        "soul_engine.loaded_all",
        files=len(sections),
        chars=len(combined),
    )
    return combined


def _normalize_department(name: str | None) -> str | None:
    """Resolve a free-form department reference to a canonical slug.

    Accepts DB names ("Legal & Compliance"), snake_case, Mind names
    ("Aria"), or anything in the alias table. Returns None if the
    input doesn't match any known department.
    """
    if not name:
        return None
    key = name.strip().lower()
    # Direct alias hit
    if key in _DEPARTMENT_SLUG_ALIASES:
        return _DEPARTMENT_SLUG_ALIASES[key]
    # Try normalized snake_case (spaces, hyphens, & -> _)
    normalized = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    if normalized in _DEPARTMENT_SLUG_ALIASES:
        return _DEPARTMENT_SLUG_ALIASES[normalized]
    return None


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML-ish frontmatter from a soul file.

    Returns (metadata_dict, body_text). Keeps the parser dependency-free
    so the SoulEngine stays importable in minimal environments (tests,
    scripts, migrations). Handles the shallow key/value + inline-list
    shapes present in our soul files; anything deeper is returned as a
    raw string for the metadata consumer to handle.
    """
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    front, body = parts[1], parts[2].strip()
    meta: dict[str, Any] = {}
    for line in front.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        # Inline list: [a, b, c]
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            meta[k] = [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]
        # Quoted string
        elif (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            meta[k] = v[1:-1]
        # Bare scalar
        else:
            meta[k] = v
    return meta, body


@lru_cache(maxsize=32)
def _load_department_soul(slug: str) -> tuple[dict[str, Any], str]:
    """Load a single department soul file. Cached per slug.

    Returns (metadata_dict, body_text). Returns ({}, "") if the file
    is missing -- a missing department is a degradation, not a crash.
    """
    path = _DEPARTMENT_SOUL_PATH / f"{slug}.md"
    if not path.exists():
        logger.warning("soul_engine.dept_missing", slug=slug, path=str(path))
        return {}, ""
    content = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(content)
    logger.debug(
        "soul_engine.dept_loaded",
        slug=slug,
        mind=meta.get("name"),
        runtime=meta.get("runtime_preference"),
        chars=len(body),
    )
    return meta, body


class SoulEngine:
    """Loads Daena's soul from the vault and provides mode-aware prompts.

    Usage::

        # Core soul only
        prompt = SoulEngine.get_soul_prompt("UNLEASHED")

        # Core soul + department overlay (department Mind persona)
        prompt = SoulEngine.get_soul_prompt("GOVERNED", department="engineering")

        # Metadata (preferred runtime, voice, tools) for routing decisions
        meta = SoulEngine.get_department_metadata("engineering")
        # -> {"name": "Aria", "runtime_preference": "claude_code", ...}
    """

    @classmethod
    def get_soul_prompt(
        cls,
        governance_mode: str = "GOVERNED",
        *,
        department: str | None = None,
        company_context: Any = None,  # CompanyContext | None -- avoid import cycle
        cli_profile: bool = False,
    ) -> str:
        """Return soul prompt adjusted for governance mode and department.

        Composition order (priority for LLM attention):
            1. Company context inject (when activated) -- the founder's
               actual company brief; first so every downstream layer
               speaks in that company's voice (Phase 1 F4)
            2. Core soul files (foundation, reasoning, personality, loyalty,
               shield, vp_mode) -- shared across all departments
            3. Department overlay (when department is resolvable) -- gives the
               Mind its name, voice, preferred runtime, reasoning patterns
            4. Governance mode addendum (UNLEASHED / BALANCED / GOVERNED)

        A missing department overlay degrades silently to core-soul-only;
        this matches the Daena rule "never break existing passing tests."

        Args:
            governance_mode: UNLEASHED, BALANCED, or GOVERNED.
            department: Optional department name, slug, or Mind name. See
                ``_DEPARTMENT_SLUG_ALIASES`` for accepted forms.
            company_context: Optional CompanyContext from the runtime
                store. When supplied, prepended to the prompt so the LLM
                sees company brief BEFORE foundation/reasoning. Phase 1
                F4 connector (was: brief saved on disk, never reached
                the LLM). Typed as Any to dodge an import cycle.
            cli_profile: Phase 1 F7. When True, returns a slimmed prompt
                for the Claude Code CLI runtime which already has bash /
                file / MCP / web tools natively. Drops the full soul +
                department overlay, keeps only company context + 1-line
                department badge + governance addendum. ~6kB instead of
                ~30kB so Council / Quintessence stays under the CLI's
                28kB threshold even with skills + cognition layered on.

        Returns:
            Complete soul prompt string ready for system prompt injection.
        """
        company_section = ""
        if company_context is not None:
            try:
                company_section = company_context.to_soul_inject(department) + "\n"
            except Exception:
                # Defensive: if a caller passes a malformed object, do
                # NOT block the chat -- just skip the inject and log.
                logger.warning("soul_engine.company_inject_failed", exc_info=True)

        if cli_profile:
            # Slim path: company brief + minimal department badge +
            # governance addendum. Skips foundation/reasoning/etc.
            # because the Claude Code CLI subprocess has its own native
            # behavior baked in. Reduces system prompt by ~24kB.
            slug = _normalize_department(department)
            dept_badge = ""
            if slug:
                meta, _body = _load_department_soul(slug)
                mind_name = meta.get("name") or slug.title()
                runtime_pref = meta.get("runtime_preference", "")
                dept_badge = (
                    f"## Department: {mind_name} ({slug})\n"
                    f"Preferred runtime: {runtime_pref}\n\n"
                )
            addendum = _GOVERNED_ADDENDUM
            if governance_mode == "UNLEASHED":
                addendum = _UNLEASHED_ADDENDUM
            elif governance_mode == "BALANCED":
                addendum = _BALANCED_ADDENDUM
            return company_section + dept_badge + addendum

        base = _load_soul_files()
        if not base:
            return company_section  # company-only is still useful

        dept_section = ""
        slug = _normalize_department(department)
        if slug:
            _meta, dept_body = _load_department_soul(slug)
            if dept_body:
                dept_section = (
                    "\n\n---\n\n"
                    "## DEPARTMENT MIND OVERLAY\n"
                    "You are currently operating as the named Mind below. "
                    "Your core soul above is unchanged -- this overlay shapes "
                    "tone, expertise framing, and tool preferences.\n\n"
                    + dept_body
                )

        addendum = _GOVERNED_ADDENDUM
        if governance_mode == "UNLEASHED":
            addendum = _UNLEASHED_ADDENDUM
        elif governance_mode == "BALANCED":
            addendum = _BALANCED_ADDENDUM

        return company_section + base + dept_section + addendum

    @classmethod
    def get_department_metadata(cls, department: str | None) -> dict[str, Any]:
        """Return department soul metadata (preferred runtime, voice, tools).

        Used by the model router to bias runtime selection when a session
        is scoped to a department, and by the voice provider to pick the
        right EdgeTTS neural voice per Mind.

        Returns an empty dict when the department is unknown.
        """
        slug = _normalize_department(department)
        if not slug:
            return {}
        meta, _ = _load_department_soul(slug)
        return dict(meta)

    @classmethod
    def list_departments(cls) -> list[dict[str, Any]]:
        """List all available Department Minds with their metadata.

        Used by the UI to render the Minds gallery (avatar + name + tone)
        and by the soul-maker service to iterate candidates for refinement.

        Daena's own Mind (_VP_MIND_SLUG) is deliberately excluded: she is the
        Vice President who orchestrates these ten, not a peer department. Use
        get_vp_mind() to address her VP-tier overlay directly.
        """
        out: list[dict[str, Any]] = []
        if not _DEPARTMENT_SOUL_PATH.exists():
            return out
        for path in sorted(_DEPARTMENT_SOUL_PATH.glob("*.md")):
            slug = path.stem
            if slug == _VP_MIND_SLUG:
                continue
            meta, _ = _load_department_soul(slug)
            if meta:
                out.append({"slug": slug, **meta})
        return out

    @classmethod
    def get_vp_mind(cls) -> dict[str, Any]:
        """Return Daena's VP-tier Mind metadata (voice, brand, toolset).

        Daena is not a department; her overlay lives in departments/daena.md
        only to reuse the loader and cache. This accessor lets the model
        router, the EdgeTTS voice provider, and the frontend pin her as the
        Vice President (gold brand, flagship voice) rather than surfacing her
        as an eleventh department card. Returns an empty dict if the VP
        overlay is missing from the vault.
        """
        meta, _ = _load_department_soul(_VP_MIND_SLUG)
        if not meta:
            return {}
        return {"slug": _VP_MIND_SLUG, **meta}

    @classmethod
    def reload(cls) -> None:
        """Clear the cache and reload soul files. Use after vault updates."""
        _load_soul_files.cache_clear()
        _load_department_soul.cache_clear()
        logger.info("soul_engine.cache_cleared")
