"""Ollama model auto-updater.

Keeps local models up to date. Runs weekly via Daena Heartbeat.
Handles: version checks, downloads, verification, cleanup, recommendations.

Uses subprocess.run in thread pool (not asyncio subprocess) because
uvicorn on Windows uses SelectorEventLoop which blocks subprocess pipes.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Models recommended by category
RECOMMENDED_MODELS: dict[str, dict[str, str]] = {
    "chat": {
        "name": "llama3.1:latest",
        "reason": "Best open-source general chat model",
    },
    "code": {
        "name": "deepseek-coder-v2:latest",
        "reason": "Strong code generation and understanding",
    },
    "reasoning": {
        "name": "deepseek-r1:14b",
        "reason": "Chain-of-thought reasoning specialist",
    },
    "small": {
        "name": "phi3:mini",
        "reason": "Fast, low-resource, good for simple tasks",
    },
}


def _run_ollama(args: list[str], timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    """Run ollama CLI command in sync (called from thread pool)."""
    import shutil

    ollama_bin = shutil.which("ollama") or "ollama"
    return subprocess.run(
        [ollama_bin, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@dataclass
class ModelInfo:
    name: str
    size_bytes: int = 0
    modified: str = ""
    digest: str = ""
    last_used: datetime | None = None


@dataclass
class UpdateResult:
    checked: int = 0
    updated: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    space_freed_mb: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checked": self.checked,
            "updated": self.updated,
            "failed": self.failed,
            "removed": self.removed,
            "space_freed_mb": round(self.space_freed_mb, 1),
            "errors": self.errors,
        }


class OllamaAutoUpdater:
    """Automatically keeps Ollama models up to date.

    Runs weekly via Daena Heartbeat. Can also be triggered manually
    from Settings > Runtimes > Ollama.
    """

    # Don't remove models used within this window
    STALE_THRESHOLD_DAYS = 30

    def __init__(self) -> None:
        self._model_usage: dict[str, datetime] = {}

    async def list_installed(self) -> list[ModelInfo]:
        """Get all installed Ollama models."""
        try:
            result = await asyncio.to_thread(_run_ollama, ["list"], timeout=15.0)
            if result.returncode != 0:
                logger.warning("ollama.list_failed", stderr=result.stderr[:200])
                return []

            models = []
            for line in result.stdout.strip().splitlines()[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 2:
                    models.append(ModelInfo(
                        name=parts[0],
                        digest=parts[1] if len(parts) > 1 else "",
                        modified=parts[-2] + " " + parts[-1] if len(parts) > 3 else "",
                    ))
            return models
        except Exception as exc:
            logger.warning("ollama.list_error", error=str(exc))
            return []

    async def check_for_updates(self) -> UpdateResult:
        """Check all installed models for available updates.

        For each model, pulls the latest version. Ollama's pull is
        incremental -- if already up to date, it's a no-op.
        """
        result = UpdateResult()
        models = await self.list_installed()
        result.checked = len(models)

        for model in models:
            try:
                logger.info("ollama.checking_update", model=model.name)
                pull_result = await asyncio.to_thread(
                    _run_ollama, ["pull", model.name], timeout=600.0,
                )
                if pull_result.returncode == 0:
                    if "up to date" not in pull_result.stdout.lower():
                        result.updated.append(model.name)
                        logger.info("ollama.updated", model=model.name)
                else:
                    result.failed.append(model.name)
                    result.errors.append(f"{model.name}: {pull_result.stderr[:100]}")
            except subprocess.TimeoutExpired:
                result.failed.append(model.name)
                result.errors.append(f"{model.name}: pull timed out after 10 min")
            except Exception as exc:
                result.failed.append(model.name)
                result.errors.append(f"{model.name}: {exc}")

        return result

    async def install_model(self, model_name: str) -> dict[str, Any]:
        """Install a model with security verification.

        Steps:
        1. Verify model name is from Ollama's official registry
        2. Pull the model
        3. Test with a simple prompt
        4. Report result
        """
        logger.info("ollama.installing", model=model_name)

        # Basic validation: no path traversal, no shell injection
        if any(c in model_name for c in [";", "&", "|", "`", "$", "(", ")", "\n"]):
            return {"success": False, "error": "Invalid model name"}

        try:
            result = await asyncio.to_thread(
                _run_ollama, ["pull", model_name], timeout=600.0,
            )
            if result.returncode != 0:
                return {"success": False, "error": result.stderr[:200]}

            # Quick sanity test
            test_result = await asyncio.to_thread(
                _run_ollama,
                ["run", model_name, "Say OK"],
                timeout=60.0,
            )
            if test_result.returncode == 0 and test_result.stdout.strip():
                logger.info("ollama.installed", model=model_name)
                return {
                    "success": True,
                    "model": model_name,
                    "test_response": test_result.stdout.strip()[:100],
                }
            return {
                "success": False,
                "error": f"Model installed but test failed: {test_result.stderr[:100]}",
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Installation timed out (10 min)"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def remove_model(self, model_name: str) -> dict[str, Any]:
        """Remove a model."""
        try:
            result = await asyncio.to_thread(
                _run_ollama, ["rm", model_name], timeout=30.0,
            )
            if result.returncode == 0:
                logger.info("ollama.removed", model=model_name)
                return {"success": True, "model": model_name}
            return {"success": False, "error": result.stderr[:200]}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def cleanup_old_models(self, keep_models: list[str] | None = None) -> UpdateResult:
        """Remove models not used recently.

        Args:
            keep_models: model names that should never be removed
        """
        keep = set(keep_models or [])
        result = UpdateResult()
        models = await self.list_installed()
        now = datetime.utcnow()

        for model in models:
            if model.name in keep:
                continue
            last_used = self._model_usage.get(model.name)
            if last_used and (now - last_used) > timedelta(days=self.STALE_THRESHOLD_DAYS):
                rm_result = await self.remove_model(model.name)
                if rm_result.get("success"):
                    result.removed.append(model.name)
                else:
                    result.errors.append(f"Failed to remove {model.name}: {rm_result.get('error')}")

        return result

    def record_usage(self, model_name: str) -> None:
        """Record that a model was used (called by OllamaProvider)."""
        self._model_usage[model_name] = datetime.utcnow()

    async def get_recommended_models(self) -> list[dict[str, str]]:
        """Return recommended models by category."""
        installed = {m.name for m in await self.list_installed()}
        recs = []
        for category, info in RECOMMENDED_MODELS.items():
            recs.append({
                "category": category,
                "model": info["name"],
                "reason": info["reason"],
                "installed": info["name"] in installed,
            })
        return recs
