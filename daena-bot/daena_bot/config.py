"""Configuration management for DaenaBot bridge.

Config is stored at ~/.daena/config.json and created on first `daena-bot connect`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".daena"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class BotConfig:
    """DaenaBot configuration."""

    server_url: str = "https://daena-596551989073.us-central1.run.app"
    auth_token: str = ""
    version: str = "0.1.0"
    auto_approve: bool = False
    allowed_tools: list[str] = field(default_factory=list)
    blocked_paths: list[str] = field(default_factory=lambda: [
        # Never access these paths
        "/etc/shadow", "/etc/passwd",
        "C:\\Windows\\System32\\config",
    ])
    max_file_size_mb: int = 50
    command_timeout_seconds: int = 120
    working_directory: str = ""

    def save(self) -> None:
        """Persist config to disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(self.__dict__, indent=2, default=str),
            encoding="utf-8",
        )

    @classmethod
    def load(cls) -> "BotConfig":
        """Load config from disk, or return defaults."""
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                return cls(**{
                    k: v for k, v in data.items()
                    if k in cls.__dataclass_fields__
                })
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()


def load_config() -> BotConfig:
    """Load or create config."""
    return BotConfig.load()
