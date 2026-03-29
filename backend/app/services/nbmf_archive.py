"""NBMF Archive Service -- exports chats/audit to Daena-Mind vault.

Writes to the Daena-Mind vault (OUTSIDE the codebase per CLAUDE.md rule #15).
Follows the 5-tier structure:
  T0-ephemeral/  -- session-only, auto-expire 1hr
  T1-working/    -- cross-session, TTL 7 days
  T2-refined/    -- verified facts, no auto-expiry
  T3-core/       -- foundational, requires FOUNDER approval
  T4-constitutional/  -- immutable rules

Files are Obsidian-compatible markdown.
"""

from __future__ import annotations

import json
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Vault root: inside the project at data/mind/ (gitignored, user data)
# Override with DAENA_MIND_PATH env var for custom location
_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # backend/app/services -> project root
VAULT_ROOT = Path(os.environ.get("DAENA_MIND_PATH", str(_PROJECT_ROOT / "data" / "mind")))

TIER_DIRS = {
    0: "T0-ephemeral",
    1: "T1-working",
    2: "T2-refined",
    3: "T3-core",
    4: "T4-constitutional",
}


def _ensure_tier_dir(tier: int) -> Path:
    """Create tier directory if it doesn't exist."""
    tier_name = TIER_DIRS.get(tier, "T1-working")
    path = VAULT_ROOT / tier_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def archive_chat_session(
    session_id: str,
    messages: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
    tier: int = 1,
) -> Path:
    """Archive a chat session as Obsidian-compatible markdown.

    Args:
        session_id: UUID of the chat session.
        messages: List of message dicts with role, content, created_at.
        metadata: Optional session metadata (title, model, cost, etc.).
        tier: NBMF tier (0-4). Default T1 (working memory).

    Returns:
        Path to the created markdown file.
    """
    tier_dir = _ensure_tier_dir(tier)
    meta = metadata or {}
    title = meta.get("title", f"Session {session_id[:8]}")
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[:60]
    filename = f"{date_str}_{safe_title}.md"
    filepath = tier_dir / filename

    lines: list[str] = []

    # Obsidian frontmatter
    lines.append("---")
    lines.append(f"session_id: {session_id}")
    lines.append(f"archived: {datetime.now().isoformat()}")
    lines.append(f"tier: T{tier}")
    if meta.get("model"):
        lines.append(f"model: {meta['model']}")
    if meta.get("total_cost"):
        lines.append(f"cost_usd: {meta['total_cost']}")
    if meta.get("message_count"):
        lines.append(f"messages: {meta['message_count']}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")

    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        ts = msg.get("created_at", "")
        if ts:
            lines.append(f"**{role}** _{ts}_")
        else:
            lines.append(f"**{role}**")
        lines.append("")
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Archived session %s to %s (tier T%d)", session_id[:8], filepath, tier)
    return filepath


def archive_audit_entries(
    entries: list[dict[str, Any]],
    label: str = "audit-export",
    tier: int = 2,
) -> Path:
    """Archive audit log entries as markdown + JSON.

    Args:
        entries: List of audit entry dicts.
        label: Filename label.
        tier: NBMF tier. Default T2 (verified/refined).

    Returns:
        Path to the created markdown file.
    """
    tier_dir = _ensure_tier_dir(tier)
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    md_path = tier_dir / f"{date_str}_{label}.md"
    json_path = tier_dir / f"{date_str}_{label}.json"

    # JSON export (machine-readable)
    json_path.write_text(json.dumps(entries, indent=2, default=str), encoding="utf-8")

    # Markdown summary (human-readable, Obsidian-compatible)
    lines = [
        "---",
        f"type: audit-archive",
        f"archived: {datetime.now().isoformat()}",
        f"tier: T{tier}",
        f"entry_count: {len(entries)}",
        "---",
        "",
        f"# Audit Archive: {label}",
        "",
        f"**{len(entries)} entries** archived on {date_str}",
        "",
    ]

    for entry in entries[:50]:  # Cap markdown preview at 50
        action = entry.get("action_type", "?")
        result = entry.get("result", "?")
        risk = entry.get("risk_level", "?")
        ts = entry.get("created_at", "")
        lines.append(f"- [{result}] {action} (risk: {risk}) {ts}")

    if len(entries) > 50:
        lines.append(f"- ... and {len(entries) - 50} more (see JSON)")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Archived %d audit entries to %s (tier T%d)", len(entries), md_path, tier)
    return md_path


def export_vault_as_zip(tiers: list[int] | None = None) -> Path:
    """Create a zip archive of the Daena-Mind vault.

    Args:
        tiers: Optional list of tier numbers to include. None = all.

    Returns:
        Path to the created zip file.
    """
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    zip_path = VAULT_ROOT / f"daena-mind-export-{date_str}.zip"

    dirs_to_include = []
    if tiers:
        for t in tiers:
            d = VAULT_ROOT / TIER_DIRS.get(t, "")
            if d.exists():
                dirs_to_include.append(d)
    else:
        for tier_dir in TIER_DIRS.values():
            d = VAULT_ROOT / tier_dir
            if d.exists():
                dirs_to_include.append(d)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in dirs_to_include:
            for file in d.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(VAULT_ROOT))

    logger.info("Exported vault to %s (%d bytes)", zip_path, zip_path.stat().st_size)
    return zip_path
