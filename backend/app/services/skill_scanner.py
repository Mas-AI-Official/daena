"""Skill scanner -- discovers SKILL.md files from multiple sources.

Scans:
  1. <project_root>/skills/  (project skills)
  2. ~/.claude/skills/ (Claude Code skills)
  3. Any custom paths from config

Skill format (SKILL.md):
  ---
  name: Skill Name
  description: What this skill does
  trigger: When to activate
  ---
  Instructions for the AI when this skill is active.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

_SKILL_DIRS = [
    _PROJECT_ROOT / "skills",
    Path.home() / ".claude" / "skills",
]


@dataclass
class SkillInfo:
    """Metadata about a discovered skill."""

    name: str
    description: str
    source: str  # file path
    source_dir: str  # which directory it came from
    trigger: str | None = None
    category: str = "Local"  # Local, System, Web, Custom
    status: str = "active"  # active, quarantined, disabled
    last_modified: str | None = None
    size_bytes: int = 0
    content_preview: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "source_dir": self.source_dir,
            "trigger": self.trigger,
            "category": self.category,
            "status": self.status,
            "last_modified": self.last_modified,
            "size_bytes": self.size_bytes,
            "content_preview": self.content_preview,
        }


def _parse_skill_frontmatter(content: str) -> dict[str, str]:
    """Extract YAML frontmatter from a SKILL.md file."""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    frontmatter = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip()
    return frontmatter


def scan_skills(extra_dirs: list[str] | None = None) -> list[SkillInfo]:
    """Scan all skill directories and return discovered skills."""
    dirs = list(_SKILL_DIRS)
    if extra_dirs:
        dirs.extend(Path(d) for d in extra_dirs)

    skills: list[SkillInfo] = []

    for skill_dir in dirs:
        if not skill_dir.exists():
            continue

        for path in skill_dir.rglob("*.md"):
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                meta = _parse_skill_frontmatter(content)
                stat = path.stat()

                name = meta.get("name", path.stem.replace("-", " ").replace("_", " ").title())
                description = meta.get("description", "")
                trigger = meta.get("trigger")

                # Determine status from filename prefix
                status = "active"
                if path.name.startswith("QUARANTINED"):
                    status = "quarantined"
                elif path.name.startswith("DISABLED"):
                    status = "disabled"

                # Content preview (first 200 chars after frontmatter)
                body = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL).strip()
                preview = body[:200]

                # Auto-categorize based on source path
                path_str = str(path).lower()
                if ".claude" in path_str:
                    category = "Local"
                elif str(skill_dir) == str(_SKILL_DIRS[0]):
                    category = "System"
                else:
                    category = "Custom"

                skills.append(SkillInfo(
                    name=name,
                    description=description,
                    source=str(path),
                    source_dir=str(skill_dir),
                    trigger=trigger,
                    category=category,
                    status=status,
                    last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    size_bytes=stat.st_size,
                    content_preview=preview,
                ))
            except Exception as exc:
                logger.warning("skill_scanner.read_failed", path=str(path), error=str(exc))

    logger.info("skill_scanner.complete", total=len(skills), dirs=len(dirs))
    return skills


def create_skill(
    name: str,
    description: str,
    instructions: str,
    trigger: str | None = None,
    target_dir: str | None = None,
) -> SkillInfo:
    """Create a new SKILL.md file.

    Args:
        name: Skill name.
        description: What the skill does.
        instructions: Instructions for the AI.
        trigger: When to activate (optional).
        target_dir: Directory to save to. Default: project skills dir.

    Returns:
        SkillInfo for the created skill.
    """
    skill_dir = Path(target_dir) if target_dir else _SKILL_DIRS[0]
    skill_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "-").lower()
    filename = f"{safe_name}.md"
    filepath = skill_dir / filename

    # Build SKILL.md content
    lines = ["---", f"name: {name}", f"description: {description}"]
    if trigger:
        lines.append(f"trigger: {trigger}")
    lines.append("---")
    lines.append("")
    lines.append(instructions)

    filepath.write_text("\n".join(lines), encoding="utf-8")

    return SkillInfo(
        name=name,
        description=description,
        source=str(filepath),
        source_dir=str(skill_dir),
        trigger=trigger,
        status="active",
        last_modified=datetime.now().isoformat(),
        size_bytes=filepath.stat().st_size,
        content_preview=instructions[:200],
    )
