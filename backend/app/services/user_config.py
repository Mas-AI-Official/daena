"""daena.md user configuration system.

Like CLAUDE.md for Claude Code. Power users edit a file instead of
clicking through settings. Daena reads this on startup and merges
with database settings (daena.md wins on conflict).

Location: ~/.daena/daena.md (or %USERPROFILE%\.daena\daena.md on Windows)
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

DAENA_MD_TEMPLATE = """# Daena User Configuration
# Edit this file to customize Daena's behavior.
# Changes take effect on next startup or when you run /reload.

## Identity
name: {name}
email: {email}
role: {role}

## Preferences
default_mode: cmd
default_governance: standard
default_runtime: auto
language: en
timezone: America/Toronto
currency: CAD

## Custom Rules (Daena respects these but they're not immutable)
- Always respond concisely, no filler
- Never use em dashes

## Custom Skills
# Add paths to skill files Daena should load
# skills:
#   - /path/to/my-custom-skill.md

## API Keys (optional, stored locally)
# anthropic_key: sk-ant-...
# openai_key: sk-...
# These override the Settings UI if both are set.
"""


def get_daena_md_path() -> Path:
    """Get the path to the user's daena.md file."""
    home = Path.home()
    return home / ".daena" / "daena.md"


def ensure_daena_md(
    name: str = "User",
    email: str = "",
    role: str = "user",
) -> Path:
    """Create daena.md if it doesn't exist. Returns the path."""
    path = get_daena_md_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        content = DAENA_MD_TEMPLATE.format(name=name, email=email, role=role)
        path.write_text(content, encoding="utf-8")
        logger.info("daena_md.created", path=str(path))
    return path


def read_daena_md() -> dict[str, Any]:
    """Parse daena.md into a config dict.

    Handles simple key: value pairs and list items (- prefix).
    Returns empty dict if file doesn't exist.
    """
    path = get_daena_md_path()
    if not path.exists():
        return {}

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("daena_md.read_error", error=str(exc))
        return {}

    config: dict[str, Any] = {}
    current_section = ""
    current_list: list[str] | None = None
    current_list_key = ""

    for line in content.splitlines():
        stripped = line.strip()

        # Skip comments and empty lines
        if not stripped or stripped.startswith("#"):
            continue

        # Section headers
        if stripped.startswith("## "):
            current_section = stripped[3:].strip().lower().replace(" ", "_")
            current_list = None
            continue

        # List items
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if current_list is None:
                current_list_key = f"{current_section}_rules" if current_section else "rules"
                current_list = []
                config[current_list_key] = current_list
            current_list.append(item)
            continue

        # Key: value pairs
        match = re.match(r"^(\w+)\s*:\s*(.+)$", stripped)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            current_list = None

            # Prefix with section for namespacing
            full_key = f"{current_section}.{key}" if current_section else key
            config[full_key] = value

    logger.info("daena_md.loaded", keys=len(config), path=str(path))
    return config


def get_config_value(config: dict[str, Any], key: str, default: Any = None) -> Any:
    """Get a value from the parsed config, with dotted key support."""
    return config.get(key, default)


def merge_with_settings(
    daena_md_config: dict[str, Any],
    db_settings: dict[str, Any],
) -> dict[str, Any]:
    """Merge daena.md config with database settings.

    daena.md wins on conflict (power user override).
    """
    merged = {**db_settings}

    # Map daena.md keys to settings keys
    key_map = {
        "identity.name": "display_name",
        "identity.email": "email",
        "preferences.default_mode": "default_mode",
        "preferences.default_governance": "default_governance",
        "preferences.default_runtime": "default_runtime",
        "preferences.language": "language",
        "preferences.timezone": "timezone",
        "preferences.currency": "currency",
    }

    for md_key, settings_key in key_map.items():
        if md_key in daena_md_config:
            merged[settings_key] = daena_md_config[md_key]

    # Custom rules
    if "custom_rules_rules" in daena_md_config:
        merged["custom_rules"] = daena_md_config["custom_rules_rules"]

    return merged
