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
# support + Hormozi frameworks without alphabetic-cutoff. The real
# prompt-budget gate is _MAX_MANIFEST_CHARS (12k) which trims the
# rendered manifest regardless of skill count.
_MAX_SKILLS = 200
_MAX_SKILL_FILE_BYTES = 256_000
_MAX_MANIFEST_CHARS = 12_000


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


def load_skills(skills_dir: Path | None = None) -> list[SkillMeta]:
    """Scan skills directory for SKILL.md files and parse metadata."""
    root = skills_dir or _SKILLS_DIR
    if not root.is_dir():
        logger.debug("skill_loader.no_dir", path=str(root))
        return []

    skills: list[SkillMeta] = []
    for entry in sorted(root.iterdir()):
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
