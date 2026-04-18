"""Soul Engine: loads and caches Daena's character foundation.

Reads soul documents from the Daena-Mind vault (D:/Ideas/Daena-Mind/soul/)
and constructs system prompt fragments that shape HOW Daena reasons.

The soul is the philosophical foundation from which all behavior flows.
It is not a system prompt that can be overridden -- it is injected first,
before operational instructions, giving it highest priority in LLM attention.

Three intensity modes based on GovernanceMode:
- UNLEASHED: Full soul + power addendum (no restraints except Shield)
- BALANCED: Full soul + light guardrails
- GOVERNED: Full soul + enterprise safety overlay

Pattern follows dcp_loader.py: file-based loading with process-level cache.

Usage::

    soul = SoulEngine.get_soul_prompt("UNLEASHED")
    system_prompt = soul + operational_instructions
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

# Relative to app/ directory -- works in dev (D:\Ideas\Daena\backend\app\soul)
# and in Docker (/app/app/soul). No hardcoded absolute paths.
_SOUL_VAULT_PATH = Path(__file__).resolve().parent.parent / "soul"

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
]

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


class SoulEngine:
    """Loads Daena's soul from the vault and provides mode-aware prompts.

    Usage::

        prompt = SoulEngine.get_soul_prompt("UNLEASHED")
    """

    @classmethod
    def get_soul_prompt(cls, governance_mode: str = "GOVERNED") -> str:
        """Return soul prompt adjusted for governance mode.

        Args:
            governance_mode: UNLEASHED, BALANCED, or GOVERNED.

        Returns:
            Complete soul prompt string ready for system prompt injection.
        """
        base = _load_soul_files()
        if not base:
            return ""

        if governance_mode == "UNLEASHED":
            return base + _UNLEASHED_ADDENDUM
        if governance_mode == "BALANCED":
            return base + _BALANCED_ADDENDUM
        return base + _GOVERNED_ADDENDUM

    @classmethod
    def reload(cls) -> None:
        """Clear the cache and reload soul files. Use after vault updates."""
        _load_soul_files.cache_clear()
        logger.info("soul_engine.cache_cleared")
