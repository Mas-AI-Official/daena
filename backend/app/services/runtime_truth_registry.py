"""Runtime truth registry.

One durable source of truth for Daena runtime, provider, MCP, plugin,
extension, and local-model state. This registry is deliberately more
conservative than the older `/runtimes`, `/mcp-sync`, and
`/connections/*` endpoints:

* configured does not mean reachable
* imported does not mean callable
* a CLI subscription is not the same thing as an API key
* Windows-local services may not be backend-local services

The persistent store is a JSON file under `backend/var/`. It is not a
replacement for tenant DB tables such as `mcp_servers`; it is the audit
surface that records the last probe/import/health/test result across
backend restarts.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.mcp_sync.detector import CLIMCPDetector

logger = get_logger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
STORE_PATH = BACKEND_ROOT / "var" / "runtime_truth_registry.json"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _redact_path_for_missing(path: Path) -> str:
    return str(path)


def _env_present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def _explicitly_persisted(prev: dict[str, Any]) -> bool:
    """Return true only for states produced by Daena import/patch/test actions."""
    state = str(prev.get("imported_state") or "")
    return bool(prev.get("persisted", False)) and state in {
        "persisted",
        "health_checked",
        "callable",
        "failed",
        "disabled",
    }


def _command_candidates(command: str) -> list[str]:
    """Return command path candidates without executing the command."""
    candidates: list[str] = []
    which = shutil.which(command)
    if which:
        candidates.append(which)

    # Backend often runs in WSL while the tools are installed on the
    # Windows host. Add common Windows paths as hints, but do not claim
    # they are executable from the backend until `shutil.which` finds
    # them in the backend environment.
    user = os.environ.get("USERNAME") or os.environ.get("USER") or "masou"
    windows_roots = [
        Path(f"C:/Users/{user}/AppData/Roaming/npm/{command}.cmd"),
        Path(f"C:/Users/{user}/.local/bin/{command}.exe"),
        Path(f"C:/Users/{user}/AppData/Local/Programs/Ollama/{command}.exe"),
        Path(f"/mnt/c/Users/{user}/AppData/Roaming/npm/{command}.cmd"),
        Path(f"/mnt/c/Users/{user}/.local/bin/{command}.exe"),
        Path(f"/mnt/c/Users/{user}/AppData/Local/Programs/Ollama/{command}.exe"),
        Path(f"/mnt/c/Program Files/nodejs/{command}.cmd"),
        Path(f"/mnt/c/Program Files/nodejs/{command}.exe"),
    ]
    for path in windows_roots:
        try:
            if path.exists():
                candidates.append(str(path))
        except OSError:
            continue
    return list(dict.fromkeys(candidates))


async def _run_version(command_path: str) -> tuple[bool, str]:
    """Run a bounded `--version` probe for an existing binary."""
    def _run() -> tuple[bool, str]:
        try:
            proc = subprocess.run(
                [command_path, "--version"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            out = (proc.stdout.strip() or proc.stderr.strip())[:500]
            return proc.returncode == 0 and bool(out), out or f"exit={proc.returncode}"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    return await asyncio.to_thread(_run)


async def _http_get_json(url: str, timeout: float = 4.0) -> tuple[bool, Any, str]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            text = resp.text[:700]
            if resp.status_code >= 400:
                return False, None, f"HTTP {resp.status_code}: {text}"
            try:
                return True, resp.json(), ""
            except Exception:
                return True, text, ""
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)


@dataclass(slots=True)
class RuntimeTruthEvent:
    id: str
    item_id: str
    event_type: str
    message: str
    created_at: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RuntimeTruthItem:
    id: str
    display_name: str
    type: str
    source: str
    detected: bool = False
    configured: bool = False
    persisted: bool = False
    reachable_from_backend: bool = False
    reachable_from_windows_host: bool | None = None
    callable: bool = False
    authenticated: bool | str = "unknown"
    models_tools_discovered: list[str] = field(default_factory=list)
    config_path: str | None = None
    command_path: str | None = None
    endpoint: str | None = None
    last_health_check: str | None = None
    last_success: str | None = None
    last_failure_reason: str | None = None
    imported_state: str = "not_detected"
    governance_tier: int = 1
    approval_required: bool = False
    audit_log_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class RuntimeTruthRegistry:
    """Durable runtime truth service."""

    def __init__(self, store_path: Path = STORE_PATH) -> None:
        self.store_path = store_path

    async def get_truth(self, *, refresh: bool = False) -> dict[str, Any]:
        if refresh:
            return await self.refresh()
        store = await self._read_store()
        if not store.get("items"):
            return await self.refresh()
        return store

    async def refresh(self) -> dict[str, Any]:
        existing = await self._read_store()
        existing_by_id = {
            item.get("id"): item
            for item in existing.get("items", [])
            if isinstance(item, dict) and item.get("id")
        }

        items = await self._discover_items(existing_by_id)
        events = list(existing.get("events", []))[-200:]
        store = {
            "schema_version": 1,
            "updated_at": _utc_now(),
            "store_path": str(self.store_path),
            "items": [asdict(item) for item in items],
            "summary": self._summary(items),
            "events": events,
        }
        await self._write_store(store)
        return store

    async def import_item(self, item_id: str) -> dict[str, Any]:
        store = await self.get_truth(refresh=False)
        items = store.get("items", [])
        found = False
        for item in items:
            if item.get("id") != item_id:
                continue
            found = True
            item["persisted"] = True
            item["imported_state"] = (
                "callable" if item.get("callable")
                else "health_checked" if item.get("reachable_from_backend")
                else "persisted"
            )
            item["last_success"] = _utc_now()
            break
        if not found:
            raise KeyError(item_id)

        event = self._event(item_id, "import", "Runtime item marked persisted in Daena registry.")
        store.setdefault("events", []).append(asdict(event))
        store["updated_at"] = _utc_now()
        store["summary"] = self._summary([RuntimeTruthItem(**i) for i in items])
        await self._write_store(store)
        return store

    async def patch_item(self, item_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        allowed = {"governance_tier", "approval_required", "imported_state", "persisted", "metadata"}
        store = await self.get_truth(refresh=False)
        found = False
        for item in store.get("items", []):
            if item.get("id") != item_id:
                continue
            found = True
            for key, value in patch.items():
                if key in allowed:
                    item[key] = value
            break
        if not found:
            raise KeyError(item_id)
        event = self._event(item_id, "patch", "Runtime item metadata updated.", {"keys": sorted(patch)})
        store.setdefault("events", []).append(asdict(event))
        store["updated_at"] = _utc_now()
        await self._write_store(store)
        return store

    async def health_check(self, item_id: str | None = None) -> dict[str, Any]:
        store = await self.refresh()
        if item_id is None:
            return store
        filtered = [item for item in store.get("items", []) if item.get("id") == item_id]
        if not filtered:
            raise KeyError(item_id)
        return {"schema_version": 1, "updated_at": store["updated_at"], "items": filtered}

    async def test_call(self, item_id: str) -> dict[str, Any]:
        store = await self.get_truth(refresh=True)
        item = next((i for i in store.get("items", []) if i.get("id") == item_id), None)
        if item is None:
            raise KeyError(item_id)

        ok = False
        message = "No callable test is available for this item."
        if item.get("type") in {"cli", "runtime"} and item.get("command_path"):
            ok, message = await _run_version(item["command_path"])
        elif item.get("endpoint"):
            endpoint = item["endpoint"].rstrip("/")
            if item["id"] in {"ollama_backend", "ollama_windows"}:
                ok, payload, message = await _http_get_json(f"{endpoint}/api/tags")
                if ok:
                    count = len((payload or {}).get("models", [])) if isinstance(payload, dict) else 0
                    message = f"Ollama responded with {count} model(s)."
            elif item["id"].startswith("vllm"):
                ok, payload, message = await _http_get_json(f"{endpoint}/models")
                if ok:
                    data = payload.get("data", []) if isinstance(payload, dict) else []
                    message = f"OpenAI-compatible runtime responded with {len(data)} model(s)."
            else:
                message = "Endpoint exists, but no safe zero-cost test is defined."

        item["callable"] = bool(ok)
        item["last_health_check"] = _utc_now()
        if ok:
            item["last_success"] = _utc_now()
            item["last_failure_reason"] = None
            item["imported_state"] = "callable"
        elif message == "Endpoint exists, but no safe zero-cost test is defined.":
            item["last_failure_reason"] = message
            item["imported_state"] = "configured_untested" if item.get("configured") else item.get("imported_state")
        else:
            item["last_failure_reason"] = message
            item["imported_state"] = "failed"

        for index, current in enumerate(store.get("items", [])):
            if current.get("id") == item_id:
                store["items"][index] = item
                break
        store.setdefault("events", []).append(asdict(self._event(
            item_id,
            "test_call",
            "Test call succeeded." if ok else "Test call failed.",
            {"ok": ok, "message": message[:500]},
        )))
        store["updated_at"] = _utc_now()
        store["summary"] = self._summary([RuntimeTruthItem(**i) for i in store.get("items", [])])
        await self._write_store(store)
        return {"success": ok, "item": item, "message": message}

    async def events(self) -> list[dict[str, Any]]:
        store = await self._read_store()
        return list(store.get("events", []))[-200:]

    async def _discover_items(self, existing: dict[str, dict[str, Any]]) -> list[RuntimeTruthItem]:
        settings = get_settings()
        items: list[RuntimeTruthItem] = []

        for command, display, item_type in [
            ("claude", "Claude Code CLI", "cli"),
            ("codex", "Codex CLI", "cli"),
            ("gemini", "Gemini CLI", "cli"),
            ("ollama", "Ollama CLI", "local_model"),
            ("node", "Node.js", "runtime"),
            ("npm", "npm", "runtime"),
            ("npx", "npx", "runtime"),
            ("python", "Python", "runtime"),
            ("docker", "Docker CLI", "runtime"),
        ]:
            candidates = _command_candidates(command)
            backend_path = shutil.which(command)
            item_id = f"cli_{command}"
            prev = existing.get(item_id, {})
            items.append(RuntimeTruthItem(
                id=item_id,
                display_name=display,
                type=item_type,
                source="backend_path",
                detected=bool(candidates),
                configured=bool(candidates),
                persisted=bool(prev.get("persisted", False)),
                reachable_from_backend=bool(backend_path),
                callable=bool(backend_path),
                authenticated="unknown",
                command_path=backend_path or (candidates[0] if candidates else None),
                last_health_check=_utc_now(),
                last_success=_utc_now() if backend_path else prev.get("last_success"),
                last_failure_reason=None if backend_path else "Command not reachable from backend PATH.",
                imported_state=prev.get("imported_state") or ("detected" if candidates else "not_detected"),
                governance_tier=int(prev.get("governance_tier", 1)),
                approval_required=bool(prev.get("approval_required", False)),
                metadata={"candidates": candidates[:5]},
            ))

        # Local model endpoints. Test backend-local and Windows-host
        # bridge addresses separately because localhost means different
        # machines when the backend runs in WSL/container.
        endpoint_specs = [
            ("ollama_backend", "Ollama backend-local", "local_model", settings.ollama_base_url.rstrip("/")),
            ("ollama_windows", "Ollama Windows host bridge", "local_model", "http://host.docker.internal:11434"),
            ("vllm_configured", "vLLM/OpenAI-compatible configured endpoint", "local_model", settings.vllm_base_url.rstrip("/").removesuffix("/v1")),
        ]
        for item_id, display, item_type, endpoint in endpoint_specs:
            prev = existing.get(item_id, {})
            reachable = False
            models: list[str] = []
            reason = "Endpoint not configured."
            if endpoint:
                if item_id.startswith("ollama"):
                    reachable, payload, reason = await _http_get_json(f"{endpoint}/api/tags")
                    if reachable and isinstance(payload, dict):
                        models = [str(m.get("name") or m.get("model")) for m in payload.get("models", []) if isinstance(m, dict)]
                elif item_id.startswith("vllm"):
                    reachable, payload, reason = await _http_get_json(f"{endpoint}/v1/models")
                    if not reachable:
                        reachable, payload, reason = await _http_get_json(f"{endpoint}/models")
                    if reachable and isinstance(payload, dict):
                        models = [str(m.get("id")) for m in payload.get("data", []) if isinstance(m, dict)]
            items.append(RuntimeTruthItem(
                id=item_id,
                display_name=display,
                type=item_type,
                source="daena_config",
                detected=bool(endpoint),
                configured=bool(endpoint),
                persisted=bool(prev.get("persisted", False)),
                reachable_from_backend=reachable,
                # Do not run a raw socket DNS lookup here. On this
                # machine WSL/Windows networking can hang in provider
                # resolution and block the FastAPI event loop. The HTTP
                # probe above is the bounded source of truth.
                reachable_from_windows_host=reachable if "host.docker.internal" in endpoint else None,
                callable=reachable,
                authenticated=True if reachable else "unknown",
                models_tools_discovered=models,
                endpoint=endpoint or None,
                last_health_check=_utc_now(),
                last_success=_utc_now() if reachable else prev.get("last_success"),
                last_failure_reason=None if reachable else reason,
                imported_state=prev.get("imported_state") or ("health_checked" if reachable else "failed"),
                governance_tier=int(prev.get("governance_tier", 1)),
                approval_required=bool(prev.get("approval_required", False)),
            ))

        # API providers. Do not make paid calls during refresh. These
        # are configured/auth unknown until an explicit test endpoint is
        # added per provider.
        for provider_id, display, configured, source, endpoint in [
            ("provider_perplexity", "Perplexity API", bool(settings.perplexity_api_key), settings.provider_key_status["perplexity"]["source"], "https://api.perplexity.ai"),
            ("provider_gemini", "Google Gemini API", bool(settings.gemini_api_key), settings.provider_key_status["gemini"]["source"], "https://generativelanguage.googleapis.com"),
            ("provider_openai", "OpenAI API", bool(settings.openai_api_key), settings.provider_key_status["openai"]["source"], "https://api.openai.com"),
            ("provider_anthropic", "Anthropic API", bool(settings.anthropic_api_key), settings.provider_key_status["anthropic"]["source"], "https://api.anthropic.com"),
            # Sprint-12A PR-1: surface the three remaining provider keys
            # the brief asks for. These ride the same configured /
            # imported_state ladder; no paid call is made during refresh.
            ("provider_groq", "Groq API", bool(settings.groq_api_key), settings.provider_key_status["groq"]["source"], "https://api.groq.com"),
            ("provider_openrouter", "OpenRouter API", bool(settings.openrouter_api_key), settings.provider_key_status["openrouter"]["source"], "https://openrouter.ai/api"),
            ("provider_together", "Together API", bool(settings.together_api_key), settings.provider_key_status["together"]["source"], "https://api.together.xyz"),
        ]:
            prev = existing.get(provider_id, {})
            prev_state = str(prev.get("imported_state") or "")
            no_safe_test_reason = "API key configured, but no zero-cost health check has been run."
            imported_state = prev_state
            if configured and prev_state in {"", "detected", "failed"}:
                previous_reason = str(prev.get("last_failure_reason") or "")
                if not previous_reason or "zero-cost" in previous_reason or "safe zero-cost" in previous_reason:
                    imported_state = "configured_untested"
            if not configured:
                imported_state = "not_detected"
            persisted = _explicitly_persisted(prev) and imported_state != "configured_untested"
            items.append(RuntimeTruthItem(
                id=provider_id,
                display_name=display,
                type="api",
                source="env",
                detected=configured,
                configured=configured,
                persisted=persisted,
                reachable_from_backend=False,
                callable=False,
                authenticated="unknown" if configured else False,
                endpoint=endpoint,
                config_path=source,
                last_health_check=_utc_now(),
                last_failure_reason=(
                    no_safe_test_reason
                    if configured else "API key not configured."
                ),
                imported_state=imported_state or ("configured_untested" if configured else "not_detected"),
                governance_tier=int(prev.get("governance_tier", 2)),
                approval_required=bool(prev.get("approval_required", True)),
            ))

        # MCP detections, redacted. Env values are intentionally not stored.
        try:
            detected_mcps = CLIMCPDetector.deduplicate(await CLIMCPDetector().discover_all())
        except Exception as exc:  # noqa: BLE001
            logger.warning("runtime_truth.mcp_detection_failed", error=str(exc))
            detected_mcps = []
        for mcp in detected_mcps:
            item_id = f"mcp_{mcp.name}".lower().replace(" ", "_")
            prev = existing.get(item_id, {})
            command_path = shutil.which(mcp.command) if mcp.command else None
            persisted = bool(prev.get("persisted", False))
            items.append(RuntimeTruthItem(
                id=item_id,
                display_name=mcp.name,
                type="mcp",
                source=mcp.source_cli,
                detected=True,
                configured=True,
                persisted=persisted,
                reachable_from_backend=bool(command_path or mcp.url),
                callable=False,
                authenticated="unknown",
                config_path=mcp.config_path,
                command_path=command_path or mcp.command or None,
                endpoint=mcp.url or None,
                last_health_check=_utc_now(),
                last_failure_reason=(
                    "Detected in CLI config but not imported into Daena."
                    if not persisted else "Imported, but MCP handshake/callability has not been verified."
                ),
                imported_state=prev.get("imported_state") or ("persisted" if persisted else "detected"),
                governance_tier=int(prev.get("governance_tier", 2)),
                approval_required=bool(prev.get("approval_required", True)),
                metadata={
                    "args": list(mcp.args),
                    "env_keys": sorted((mcp.env or {}).keys()),
                    "notes": mcp.notes,
                },
            ))

        # Installed Daena package MCP.
        daena_mcp = BACKEND_ROOT.parent / "packages" / "daena-mcp"
        prev = existing.get("plugin_daena_mcp", {})
        persisted = _explicitly_persisted(prev)
        items.append(RuntimeTruthItem(
            id="plugin_daena_mcp",
            display_name="Daena MCP package",
            type="plugin",
            source="daena_config",
            detected=daena_mcp.exists(),
            configured=(daena_mcp / "package.json").exists(),
            persisted=persisted,
            reachable_from_backend=(daena_mcp / "package.json").exists(),
            callable=False,
            authenticated="unknown",
            config_path=_redact_path_for_missing(daena_mcp / "package.json"),
            last_health_check=_utc_now(),
            last_failure_reason="Package exists, but npm link/callability must be tested explicitly.",
            imported_state=prev.get("imported_state") or ("persisted" if persisted else "detected" if daena_mcp.exists() else "not_detected"),
            governance_tier=int(prev.get("governance_tier", 2)),
            approval_required=bool(prev.get("approval_required", True)),
        ))

        return items

    async def _read_store(self) -> dict[str, Any]:
        try:
            raw = await asyncio.to_thread(self.store_path.read_text, encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except FileNotFoundError:
            return {"schema_version": 1, "items": [], "events": []}
        except Exception as exc:  # noqa: BLE001
            logger.warning("runtime_truth.store_read_failed", error=str(exc))
        return {"schema_version": 1, "items": [], "events": []}

    async def _write_store(self, store: dict[str, Any]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(store, indent=2, sort_keys=True)
        await asyncio.to_thread(self.store_path.write_text, payload, encoding="utf-8")

    @staticmethod
    def _summary(items: list[RuntimeTruthItem]) -> dict[str, Any]:
        return {
            "total": len(items),
            "detected": sum(1 for i in items if i.detected),
            "configured": sum(1 for i in items if i.configured),
            "persisted": sum(1 for i in items if i.persisted),
            "reachable_from_backend": sum(1 for i in items if i.reachable_from_backend),
            "callable": sum(1 for i in items if i.callable),
            "failed": sum(1 for i in items if i.imported_state == "failed"),
            "by_type": {
                t: sum(1 for i in items if i.type == t)
                for t in sorted({i.type for i in items})
            },
        }

    @staticmethod
    def _event(
        item_id: str,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> RuntimeTruthEvent:
        return RuntimeTruthEvent(
            id=str(uuid.uuid4()),
            item_id=item_id,
            event_type=event_type,
            message=message,
            created_at=_utc_now(),
            payload=payload or {},
        )


runtime_truth_registry = RuntimeTruthRegistry()
