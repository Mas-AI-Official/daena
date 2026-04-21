"""Markdown-first skill loader (OpenClaw pattern).

Loads SKILL.md files from the skills/ directory and injects a compact
manifest into the system prompt.  The LLM reads individual SKILL.md
files on demand when a task matches a skill.

This runs alongside the DB-backed Skill Refinery.  Filesystem skills
provide actionable instructions (commands, patterns); DB skills provide
evidence-backed patterns extracted from conversations.

Usage in chat_orchestrator.py:
    from app.services.skills.skill_loader import get_skill_manifest
    manifest = get_skill_manifest()
    system_prompt += manifest
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.core.logging import get_logger

logger = get_logger(__name__)

# Resolve skills/ directory relative to project root (backend/../skills)
# __file__ is at backend/app/services/skills/skill_loader.py
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent  # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent  # Daena/
_SKILLS_DIR = _PROJECT_ROOT / "skills"

# Limits to prevent excessive prompt injection.
# _MAX_SKILLS raised 100 -> 200 in TICKET-S15 to fit the sales +
# support + Hormozi frameworks without alphabetic-cutoff. Raised
# again 200 -> 300 in 2026-04-18 to accommodate the 38 gstack
# skills (Garry Tan's phase-based thinking framework: CEO review,
# plan-eng-review, design-review, QA, retro, etc.) alongside
# existing libraries.
#
# _MAX_MANIFEST_CHARS bumped 12k -> 16k for the same reason. The
# LLM needs to SEE gstack skills in the manifest to know they're
# available and invoke them -- a truncated manifest means the
# model never considers the phase-based mental models Tan's pack
# provides. 16k is ~4k tokens of system prompt overhead, which
# is modest relative to the upside.
_MAX_SKILLS = 300
_MAX_SKILL_FILE_BYTES = 256_000
_MAX_MANIFEST_CHARS = 16_000

# Skill-name prefixes that get sort priority in the manifest.
# Gstack (Garry Tan's phase-thinking framework) forces distinct
# cognitive modes for plan / build / review / QA / ship / retro --
# these should be at the TOP of the manifest so the LLM always
# knows they're the primary thinking gears before scanning the
# rest of the library. Anthropic's own skills come next as they're
# the canonical reasoning + artifact patterns.
_PRIORITY_PREFIXES: tuple[str, ...] = (
    "gstack-",
    "anthropic-",
    "plan-",
    "office-hours",
    "design-",
    "investigate",
    "retro",
    "review",
    "qa",
    "ship",
)


@dataclass
class SkillMeta:
    """Parsed SKILL.md frontmatter."""
    name: str
    description: str
    department: str = ""
    cost_tier: str = "low"
    requires: dict = field(default_factory=dict)
    path: str = ""


def _parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    try:
        return yaml.safe_load(content[3:end]) or {}
    except yaml.YAMLError:
        return {}


def _priority_key(dir_name: str) -> int:
    """Lower-value key => appears earlier in sorted output.

    gstack-prefixed directories get -1, anthropic-prefixed get 0,
    other priority prefixes get 1, everything else gets 2. The
    directory-name comparison is lowercased so "Gstack-Foo" still
    sorts ahead of random user skills.
    """
    low = dir_name.lower()
    for i, prefix in enumerate(_PRIORITY_PREFIXES):
        if low.startswith(prefix):
            return i
    return len(_PRIORITY_PREFIXES)


def load_skills(skills_dir: Path | None = None) -> list[SkillMeta]:
    """Scan skills directory for SKILL.md files and parse metadata."""
    root = skills_dir or _SKILLS_DIR
    if not root.is_dir():
        logger.debug("skill_loader.no_dir", path=str(root))
        return []

    skills: list[SkillMeta] = []
    # Sort by priority first (gstack, anthropic, design, etc.), then
    # alphabetically. This guarantees the phase-thinking skills
    # always make it into the manifest even when we hit the 16KB cap.
    entries = sorted(
        root.iterdir(),
        key=lambda p: (_priority_key(p.name), p.name.lower()),
    )
    for entry in entries:
        if not entry.is_dir():
            continue
        skill_file = entry / "SKILL.md"
        if not skill_file.is_file():
            continue
        if skill_file.stat().st_size > _MAX_SKILL_FILE_BYTES:
            logger.warning("skill_loader.too_large", path=str(skill_file))
            continue

        try:
            content = skill_file.read_text(encoding="utf-8")
            fm = _parse_frontmatter(content)
            if not fm.get("name") or not fm.get("description"):
                continue

            skills.append(SkillMeta(
                name=fm["name"],
                description=fm["description"],
                department=fm.get("department", ""),
                cost_tier=fm.get("cost_tier", "low"),
                requires=fm.get("requires", {}),
                path=str(skill_file.relative_to(_PROJECT_ROOT)),
            ))
        except Exception as exc:
            logger.warning("skill_loader.parse_error", path=str(skill_file), error=str(exc))

        if len(skills) >= _MAX_SKILLS:
            break

    logger.info("skill_loader.loaded", count=len(skills), dir=str(root))
    return skills


def read_skill(skill_name: str, skills_dir: Path | None = None) -> str | None:
    """Read the full SKILL.md content for a specific skill."""
    root = skills_dir or _SKILLS_DIR
    skill_file = root / skill_name / "SKILL.md"
    if not skill_file.is_file():
        return None
    if skill_file.stat().st_size > _MAX_SKILL_FILE_BYTES:
        return None
    return skill_file.read_text(encoding="utf-8")


def get_skill_manifest(skills_dir: Path | None = None) -> str:
    """Build a compact skill manifest for system prompt injection.

    Returns an XML-like block listing available skills that the LLM
    can reference.  Keeps total size under _MAX_MANIFEST_CHARS.
    """
    skills = load_skills(skills_dir)
    if not skills:
        return ""

    lines = ["\n<available_skills>"]
    total = len(lines[0])

    for skill in skills:
        line = (
            f'  <skill name="{skill.name}" department="{skill.department}" '
            f'cost="{skill.cost_tier}">'
            f'{skill.description}</skill>'
        )
        if total + len(line) + 30 > _MAX_MANIFEST_CHARS:
            lines.append(f"  <!-- {len(skills) - len(lines) + 1} more skills truncated -->")
            break
        lines.append(line)
        total += len(line)

    lines.append("</available_skills>")
    lines.append(
        "When a task matches a skill above, follow the skill's documented "
        "instructions and commands.  Use EXE mode tools (terminal, file, browser) "
        "to execute the steps."
    )
    return "\n".join(lines)
