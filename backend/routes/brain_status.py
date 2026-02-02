"""
Brain Status API
Provides status and control endpoints for the AI brain/LLM connection

IMPORTANT: This is the SINGLE SOURCE OF TRUTH for brain status.
UI and chat must query these endpoints, never hardcode model names.
"""
from fastapi import APIRouter, Body
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from enum import Enum
import httpx
import logging
from pathlib import Path
import json

router = APIRouter(prefix="/api/v1/brain", tags=["brain"])
logger = logging.getLogger(__name__)

_CLOUD_CONFIG_KEY = "cloud_apis"


def _get_cloud_apis_config() -> Dict[str, Any]:
    """Read cloud API keys and enabled state from DB (SystemConfig)."""
    try:
        from backend.database import SessionLocal, SystemConfig
        db = SessionLocal()
        try:
            row = db.query(SystemConfig).filter(SystemConfig.config_key == _CLOUD_CONFIG_KEY).first()
            if row and row.config_value:
                return json.loads(row.config_value) if isinstance(row.config_value, str) else row.config_value
        finally:
            db.close()
    except Exception as e:
        logger.warning("cloud_apis config read failed: %s", e)
    return {}


def _ollama_url() -> str:
    """Use backend settings so brain status stays in sync with chat/LLM."""
    try:
        from backend.config.settings import get_settings
        return get_settings().ollama_base_url or "http://127.0.0.1:11434"
    except Exception:
        return "http://127.0.0.1:11434"


def _models_root_resolved() -> str:
    """Models root: DB override first, then env/settings."""
    try:
        override = _get_system_config("models_root_override")
        if override and isinstance(override, str) and override.strip():
            return override.strip()
    except Exception:
        pass
    try:
        from backend.config.settings import get_settings
        s = get_settings()
        if getattr(s, "models_root", None):
            return str(Path(s.models_root).resolve())
    except Exception:
        pass
    return ""


def _local_brain_path() -> Path:
    root = _models_root_resolved()
    if root:
        return Path(root) / "ollama"
    try:
        from backend.config.settings import get_settings
        s = get_settings()
        if getattr(s, "models_root", None):
            return Path(s.models_root) / "ollama"
    except Exception:
        pass
    return Path(__file__).parent.parent.parent / "local_brain"


def _scan_filesystem_models() -> List[Dict[str, Any]]:
    """Scan models root and ollama subfolder for model manifests; return list of {name, size_gb}. Real-time from path."""
    result = []
    root_str = _models_root_resolved()
    if not root_str:
        try:
            from backend.config.settings import get_settings
            s = get_settings()
            root_str = getattr(s, "models_root", None) or ""
        except Exception:
            root_str = ""
    if not root_str:
        return result
    root = Path(root_str)
    # Ollama layout: root/ollama/models/, root/ollama/, or root/ with manifests/registry.../library/<model>/<tag>
    candidates = [
        root / "ollama" / "models",
        root / "ollama",
        root / "models",
        root,
    ]
    seen = set()
    for base in candidates:
        if not base.exists():
            continue
        manifests = base / "manifests"
        if not manifests.exists():
            continue
        try:
            for reg in manifests.iterdir():
                if not reg.is_dir():
                    continue
                for repo in reg.iterdir():
                    if not repo.is_dir():
                        continue
                    # repo is model name; tags are dirs or files under it
                    for tag_or_file in repo.iterdir():
                        name = f"{repo.name}:{tag_or_file.name}" if tag_or_file.name != "latest" else repo.name
                        if name in seen:
                            continue
                        seen.add(name)
                        size_gb = 0.0
                        if tag_or_file.is_dir():
                            for f in tag_or_file.iterdir():
                                if f.is_file():
                                    size_gb += f.stat().st_size
                        elif tag_or_file.is_file():
                            size_gb = tag_or_file.stat().st_size
                        result.append({"name": name, "size_gb": round(size_gb / (1024 ** 3), 2)})
        except Exception as e:
            logger.debug("scan manifests %s: %s", base, e)
    return result


class RoutingMode(str, Enum):
    """Brain routing mode"""
    LOCAL_ONLY = "local_only"
    API_ONLY = "api_only"
    HYBRID = "hybrid"


# In-memory routing mode (survives restart via DB)
_current_routing_mode = RoutingMode.LOCAL_ONLY


@router.get("/status")
async def get_brain_status() -> Dict[str, Any]:
    """Get comprehensive brain/LLM status - supports multiple active models"""
    from backend.database import SessionLocal, SystemConfig
    import json
    
    # Get active models from DB (supports multiple)
    db = SessionLocal()
    active_models = []
    active_model = None
    try:
        # Try to get multiple active models first
        config = db.query(SystemConfig).filter(SystemConfig.config_key == "active_brain_models").first()
        if config:
            try:
                active_models = json.loads(config.config_value) if isinstance(config.config_value, str) else config.config_value
                if not isinstance(active_models, list):
                    active_models = []
            except:
                active_models = []
        
        # Fallback to single active model for backward compatibility
        if not active_models:
            single_config = db.query(SystemConfig).filter(SystemConfig.config_key == "active_brain_model").first()
            if single_config:
                active_model = single_config.config_value
                if active_model:
                    active_models = [active_model]
    finally:
        db.close()
    
    local_brain = _local_brain_path()
    models_root = _models_root_resolved()
    if not models_root:
        try:
            from backend.config.settings import get_settings
            s = get_settings()
            models_root = getattr(s, "models_root", None) or ""
        except Exception:
            models_root = ""
    status = {
        "connected": False,
        "ollama_available": False,
        "llm_available": False,
        "provider": "ollama",
        "models": [],
        "active_model": active_models[0] if active_models else None,  # Primary for backward compatibility
        "active_models": active_models,  # All active models
        "routing_mode": _current_routing_mode.value,
        "models_root": models_root,
        "local_brain_path": str(local_brain),
        "local_brain_exists": local_brain.exists()
    }
    
    # Try primary Ollama first; if down, use local brain fallback (daena brain on fallback port)
    ollama_url = _ollama_url()
    try:
        from backend.services.local_brain_manager import try_primary_then_fallback
        ollama_url = await try_primary_then_fallback()
        if "11435" in ollama_url:
            status["using_fallback"] = True  # UI can show "Local brain (fallback)"
    except Exception:
        pass
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ollama_url.rstrip('/')}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                status["ollama_available"] = True
                status["llm_available"] = len(models) > 0
                status["connected"] = status["ollama_available"] and status["llm_available"]  # sync with frontend
                model_list = [
                    {
                        "name": m.get("name"),
                        "size": m.get("size", 0),
                        "modified_at": m.get("modified_at"),
                        "active": m.get("name") in active_models
                    }
                    for m in models
                ]
                status["models"] = model_list
                
                # If no active models set, default to first model
                if not active_models and models:
                    status["active_model"] = models[0].get("name")
                    status["active_models"] = [models[0].get("name")]
            else:
                status["error"] = f"Ollama returned {response.status_code}"
    except Exception as e:
        logger.warning(f"Ollama not available: {e}")
        status["error"] = str(e)

    # Always merge in models from the CHOSEN folder (Brain setting) so scan syncs with selected path
    fs_models = _scan_filesystem_models()
    existing_names = {m.get("name") for m in status["models"]}
    for m in fs_models:
        name = m.get("name")
        if name and name not in existing_names:
            status["models"].append({
                "name": name,
                "size": int((m.get("size_gb") or 0) * (1024**3)),
                "modified_at": None,
                "active": name in (status.get("active_models") or [])
            })
            existing_names.add(name)
    if fs_models and not status["llm_available"]:
        status["llm_available"] = len(status["models"]) > 0

    return status

@router.get("/models")
async def list_models() -> Dict[str, Any]:
    """List all available LLM models"""
    models = {
        "local": [],
        "trained": [],
        "cloud": []
    }
    
    # 1) Always scan the CHOSEN folder (Brain setting) first — sync with "Offline models location"
    fs_models = _scan_filesystem_models()
    name_to_fs = {m.get("name"): m for m in fs_models}
    for m in fs_models:
        models["local"].append({
            "name": m.get("name", "unknown"),
            "size_gb": m.get("size_gb", 0),
            "modified": None
        })
    # 2) Merge in what the running Ollama reports (may be from same or default path)
    try:
        from backend.services.local_brain_manager import try_primary_then_fallback
        ollama_url = await try_primary_then_fallback()
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ollama_url.rstrip('/')}/api/tags")
            if response.status_code == 200:
                data = response.json()
                for m in data.get("models", []):
                    name = m.get("name")
                    if not name or name in name_to_fs:
                        continue
                    models["local"].append({
                        "name": name,
                        "size_gb": round(m.get("size", 0) / (1024**3), 2),
                        "modified": m.get("modified_at")
                    })
    except Exception as e:
        logger.warning(f"Could not list Ollama models: {e}")
    
    # Check local_brain trained models (exclude registry placeholder entries like registry.ollama.ai/library)
    local_brain = _local_brain_path()
    if local_brain.exists():
        manifests = local_brain / "manifests"
        if manifests.exists():
            for registry in manifests.iterdir():
                if registry.is_dir():
                    for model in registry.iterdir():
                        if model.is_dir():
                            name = f"{registry.name}/{model.name}"
                            if "registry.ollama.ai" in name:
                                continue
                            models["trained"].append({
                                "name": name,
                                "path": str(model)
                            })
    
    # Cloud APIs: merge default list with DB (keys and enabled state)
    default_cloud = [
        {"name": "openai/gpt-4", "provider": "openai", "status": "not_configured", "enabled": False},
        {"name": "google/gemini-pro", "provider": "google", "status": "not_configured", "enabled": False},
        {"name": "anthropic/claude-3", "provider": "anthropic", "status": "not_configured", "enabled": False},
        {"name": "xai/grok", "provider": "xai", "status": "not_configured", "enabled": False},
        {"name": "deepseek/deepseek-chat", "provider": "deepseek", "status": "not_configured", "enabled": False},
    ]
    cloud_config = _get_cloud_apis_config()
    for entry in default_cloud:
        prov = entry.get("provider") or entry["name"].split("/")[0].lower()
        entry["provider"] = prov
        cfg = cloud_config.get(prov, {})
        has_key = bool(cfg.get("key"))
        entry["enabled"] = bool(cfg.get("enabled", False))
        entry["status"] = "configured" if has_key else "not_configured"
    models["cloud"] = default_cloud
    return models

@router.get("/cloud")
async def get_cloud_apis() -> Dict[str, Any]:
    """Get cloud API config (enabled state only; keys never returned)."""
    raw = _get_cloud_apis_config()
    out = {}
    for prov, cfg in raw.items():
        out[prov] = {"enabled": bool(cfg.get("enabled", False)), "has_key": bool(cfg.get("key"))}
    return {"success": True, "cloud": out}


_AUTOPILOT_KEY = "autopilot_enabled"
_SMART_ROUTING_KEY = "smart_routing"


def _get_system_config(key: str, default: Any = None) -> Any:
    """Read a system config value from DB."""
    try:
        from backend.database import SessionLocal, SystemConfig
        db = SessionLocal()
        try:
            row = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
            if row and row.config_value is not None:
                v = row.config_value
                if isinstance(v, str):
                    s = v.strip()
                    if s.lower() in ("true", "false"):
                        return s.lower() == "true"
                    if s.startswith(("{", "[")):
                        import json
                        return json.loads(v)
                return v
        finally:
            db.close()
    except Exception as e:
        logger.warning("config read failed %s: %s", key, e)
    return default


def _set_system_config(key: str, value: Any, config_type: str = "json") -> None:
    """Write a system config value to DB."""
    from backend.database import SessionLocal, SystemConfig
    from datetime import datetime
    db = SessionLocal()
    try:
        import json
        json_val = json.dumps(value) if not isinstance(value, str) else value
        row = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
        if row:
            row.config_value = json_val
            row.updated_at = datetime.utcnow()
        else:
            db.add(SystemConfig(
                config_key=key,
                config_value=json_val,
                config_type=config_type,
                description=f"Config: {key}",
            ))
        db.commit()
    finally:
        db.close()


@router.get("/autopilot")
async def get_autopilot() -> Dict[str, Any]:
    """Get autopilot enabled state. Single source of truth: governance loop (used by chat), then DB."""
    try:
        from backend.services.governance_loop import get_governance_loop
        loop = get_governance_loop()
        enabled = getattr(loop, "autopilot", None)
        if enabled is not None:
            _set_system_config(_AUTOPILOT_KEY, enabled, "boolean")
            return {"enabled": bool(enabled)}
    except Exception:
        pass
    enabled = _get_system_config(_AUTOPILOT_KEY, False)
    if isinstance(enabled, str):
        enabled = enabled.lower() in ("true", "1", "yes")
    return {"enabled": bool(enabled)}


@router.post("/autopilot")
async def set_autopilot(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Set autopilot on/off. Syncs to governance loop (chat pipeline) and DB."""
    enabled = bool(body.get("enabled", False))
    _set_system_config(_AUTOPILOT_KEY, enabled, "boolean")
    try:
        from backend.services.governance_loop import get_governance_loop
        loop = get_governance_loop()
        loop.autopilot = enabled
    except Exception:
        pass
    return {"success": True, "enabled": enabled}


@router.get("/smart_routing")
async def get_smart_routing() -> Dict[str, Any]:
    """Get smart routing config: router model (e.g. R1) decides which model to use per request."""
    raw = _get_system_config(_SMART_ROUTING_KEY)
    if not isinstance(raw, dict):
        raw = {}
    return {
        "enabled": bool(raw.get("enabled", False)),
        "router_model": raw.get("router_model") or "deepseek-r1:8b",
    }


@router.post("/smart_routing")
async def set_smart_routing(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Set smart routing: enabled and optional router_model (e.g. deepseek-r1:8b)."""
    raw = _get_system_config(_SMART_ROUTING_KEY) or {}
    if not isinstance(raw, dict):
        raw = {}
    if "enabled" in body:
        raw["enabled"] = bool(body["enabled"])
    if "router_model" in body:
        raw["router_model"] = str(body["router_model"]).strip() or "deepseek-r1:8b"
    _set_system_config(_SMART_ROUTING_KEY, raw)
    return {"success": True, "enabled": raw.get("enabled", False), "router_model": raw.get("router_model", "deepseek-r1:8b")}


class CloudKeyBody(BaseModel):
    key: str = ""


@router.post("/cloud/{provider}/key")
async def set_cloud_api_key(provider: str, body: CloudKeyBody = Body(...)) -> Dict[str, Any]:
    """Save or clear API key for a cloud provider (openai, google, anthropic, xai). Syncs to backend."""
    from backend.database import SessionLocal, SystemConfig
    from datetime import datetime
    provider = provider.lower()
    if provider not in ("openai", "google", "anthropic", "xai", "deepseek"):
        return {"success": False, "error": f"Unknown provider: {provider}"}
    key_value = (body.key or "").strip()
    db = SessionLocal()
    try:
        config = db.query(SystemConfig).filter(SystemConfig.config_key == _CLOUD_CONFIG_KEY).first()
        data = _get_cloud_apis_config()
        if provider not in data:
            data[provider] = {"enabled": False, "key": ""}
        data[provider]["key"] = key_value
        if not key_value:
            data[provider]["enabled"] = False
        json_val = json.dumps(data)
        if config:
            config.config_value = json_val
            config.updated_at = datetime.utcnow()
        else:
            config = SystemConfig(
                config_key=_CLOUD_CONFIG_KEY,
                config_value=json_val,
                config_type="json",
                description="Cloud LLM API keys and enabled state",
            )
            db.add(config)
        db.commit()
        return {"success": True, "provider": provider, "message": "API key saved" if key_value else "API key cleared"}
    finally:
        db.close()


class CloudToggleBody(BaseModel):
    enabled: bool = True


@router.post("/cloud/{provider}/toggle")
async def set_cloud_api_toggle(provider: str, body: CloudToggleBody = Body(...)) -> Dict[str, Any]:
    """Enable or disable a cloud provider in the pipeline. Syncs to backend."""
    from backend.database import SessionLocal, SystemConfig
    from datetime import datetime
    provider = provider.lower()
    if provider not in ("openai", "google", "anthropic", "xai", "deepseek"):
        return {"success": False, "error": f"Unknown provider: {provider}"}
    db = SessionLocal()
    try:
        data = _get_cloud_apis_config()
        if provider not in data:
            data[provider] = {"enabled": False, "key": ""}
        data[provider]["enabled"] = body.enabled
        if body.enabled and not data[provider].get("key"):
            return {"success": False, "error": "Set an API key first before enabling"}
        json_val = json.dumps(data)
        config = db.query(SystemConfig).filter(SystemConfig.config_key == _CLOUD_CONFIG_KEY).first()
        if config:
            config.config_value = json_val
            config.updated_at = datetime.utcnow()
        else:
            config = SystemConfig(
                config_key=_CLOUD_CONFIG_KEY,
                config_value=json_val,
                config_type="json",
                description="Cloud LLM API keys and enabled state",
            )
            db.add(config)
        db.commit()
        return {"success": True, "provider": provider, "enabled": body.enabled}
    finally:
        db.close()


@router.get("/models_root")
async def get_models_root() -> Dict[str, Any]:
    """Get current models root (DB override or settings)."""
    root = _models_root_resolved()
    if not root:
        try:
            from backend.config.settings import get_settings
            s = get_settings()
            root = getattr(s, "models_root", None) or ""
        except Exception:
            root = ""
    return {"success": True, "models_root": root or ""}


class ModelsRootBody(BaseModel):
    models_root: str = ""


def _sync_ollama_models_env():
    """Sync OLLAMA_MODELS env from Brain setting (DB override) so brain/Ollama use the chosen folder."""
    import os
    root = _models_root_resolved()
    if root:
        ollama_path = str(Path(root).resolve() / "ollama")
        os.environ["OLLAMA_MODELS"] = ollama_path
        logger.info("OLLAMA_MODELS set from Brain setting: %s", ollama_path)
    else:
        try:
            from backend.config.settings import get_settings
            s = get_settings()
            if getattr(s, "ollama_models_path", None):
                os.environ["OLLAMA_MODELS"] = s.ollama_models_path
        except Exception:
            pass


@router.post("/models_root")
async def set_models_root(body: ModelsRootBody = Body(...)) -> Dict[str, Any]:
    """Set offline models root; updates backend so brain/LLM use this path. Real-time sync."""
    path = (body.models_root or "").strip()
    _set_system_config("models_root_override", path, "string")  # store "" to clear override
    _sync_ollama_models_env()
    return {"success": True, "models_root": path or _models_root_resolved()}


@router.post("/open-models-folder")
async def open_models_folder(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Open the models root folder in the OS file manager (Explorer / Finder)."""
    import subprocess
    import sys
    path = (body.get("path") or "").strip() or _models_root_resolved()
    if not path:
        try:
            from backend.config.settings import get_settings
            s = get_settings()
            path = getattr(s, "models_root", None) or ""
        except Exception:
            path = ""
    path = path.strip()
    if not path:
        return {"success": False, "error": "No models root path configured"}
    p = Path(path)
    if not p.exists():
        return {"success": False, "error": f"Path does not exist: {path}"}
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(p.resolve())], shell=False)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p.resolve())])
        else:
            subprocess.Popen(["xdg-open", str(p.resolve())])
        return {"success": True, "path": str(p.resolve())}
    except Exception as e:
        logger.warning("open-models-folder failed: %s", e)
        return {"success": False, "error": str(e)}


@router.get("/list-models")
async def list_all_models() -> Dict[str, Any]:
    """List ALL available local models from Ollama (primary or fallback)"""
    try:
        from backend.services.local_brain_manager import try_primary_then_fallback
        ollama_url = await try_primary_then_fallback()
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ollama_url.rstrip('/')}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                
                return {
                    "success": True,
                    "count": len(models),
                    "models": [{"name": m.get("name"), "size": m.get("size", 0)} for m in models]
                }
            else:
                return {"success": False, "error": "Ollama not responding", "models": []}
    except Exception as e:
        return {"success": False, "error": str(e), "models": []}

@router.get("/recommended")
async def list_recommended_models() -> List[Dict[str, Any]]:
    """List recommended models for installation"""
    from backend.services.model_registry import get_model_registry
    registry = get_model_registry()
    # Ensure we have latest status
    await registry.get_status()
    return registry.get_recommended_models()

@router.post("/routing_mode")
async def set_routing_mode(mode: str = Body(..., embed=True)) -> Dict[str, Any]:
    """Set the brain routing mode (local_only, api_only, hybrid)"""
    global _current_routing_mode
    try:
        _current_routing_mode = RoutingMode(mode)
        return {
            "success": True,
            "routing_mode": _current_routing_mode.value
        }
    except ValueError:
        return {
            "success": False,
            "error": f"Invalid mode. Must be one of: {[m.value for m in RoutingMode]}"
        }

@router.post("/scan")
async def scan_models() -> Dict[str, Any]:
    """Force scan of available models"""
    try:
        from backend.services.model_registry import get_model_registry
        registry = get_model_registry()
        models = await registry.scan_models()
        return {
            "success": True,
            "count": len(models),
            "models": [m.name for m in models]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

class TestBrainRequest(BaseModel):
    model_name: Optional[str] = None


@router.post("/test")
async def test_brain_connection(request: Optional[TestBrainRequest] = Body(None)) -> Dict[str, Any]:
    """Test the brain connection with a simple prompt. Uses model_name from body if provided, else ACTIVE model from DB."""
    from backend.database import SessionLocal, SystemConfig
    import json

    active_model = getattr(request, "model_name", None) if request else None
    if not active_model:
        db = SessionLocal()
        try:
            config = db.query(SystemConfig).filter(SystemConfig.config_key == "active_brain_model").first()
            if config and config.config_value:
                active_model = config.config_value
        finally:
            db.close()
        if not active_model:
            active_model = "qwen2.5:7b-instruct"

    try:
        from backend.services.local_brain_manager import try_primary_then_fallback
        ollama_url = await try_primary_then_fallback()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ollama_url.rstrip('/')}/api/generate",
                json={
                    "model": active_model,
                    "prompt": "Say 'Hello, I am Daena's brain and I am working!' in one sentence.",
                    "stream": False
                }
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "response": data.get("response", ""),
                    "model": active_model
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "error": f"Model '{active_model}' not found. Please pull it or select a different model.",
                    "model": active_model
                }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "hint": "Make sure Ollama is running: ollama serve"
        }
    
    return {"success": False, "error": "Unknown error"}

class PullModelRequest(BaseModel):
    model_name: str = "qwen2.5:7b-instruct"

@router.post("/pull")
async def pull_model(request: PullModelRequest = Body(...)) -> Dict[str, Any]:
    """Pull/download a model from Ollama (primary or fallback)"""
    model_name = request.model_name
    try:
        from backend.services.local_brain_manager import try_primary_then_fallback
        ollama_url = await try_primary_then_fallback()
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{ollama_url.rstrip('/')}/api/pull",
                json={"name": model_name}
            )
            return {
                "success": response.status_code == 200,
                "model": model_name,
                "message": f"Started pulling {model_name}"
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/models/{model_name}/select")
async def select_model(model_name: str, enabled: bool = True) -> Dict[str, Any]:
    """Select/set active model(s) for the system - supports multiple active models"""
    from backend.database import SessionLocal, SystemConfig
    from datetime import datetime
    import json
    
    db = SessionLocal()
    try:
        # Get or create active models config (JSON array)
        config = db.query(SystemConfig).filter(SystemConfig.config_key == "active_brain_models").first()
        
        if config:
            try:
                active_models = json.loads(config.config_value) if isinstance(config.config_value, str) else config.config_value
                if not isinstance(active_models, list):
                    active_models = []
            except:
                active_models = []
        else:
            active_models = []
            config = SystemConfig(
                config_key="active_brain_models",
                config_value=json.dumps([]),
                config_type="json",
                description="List of active brain models (supports multiple)"
            )
            db.add(config)
        
        # Add or remove model from active list
        if enabled:
            if model_name not in active_models:
                active_models.append(model_name)
        else:
            if model_name in active_models:
                active_models.remove(model_name)
                # Ensure at least one model is active
                if not active_models:
                    return {
                        "success": False,
                        "error": "Cannot disable all models. At least one model must be active."
                    }
        
        # Update config
        config.config_value = json.dumps(active_models)
        config.updated_at = datetime.utcnow()
        
        # Also update single active_brain_model for backward compatibility
        single_config = db.query(SystemConfig).filter(SystemConfig.config_key == "active_brain_model").first()
        if single_config:
            single_config.config_value = active_models[0] if active_models else ""
            single_config.updated_at = datetime.utcnow()
        elif active_models:
            single_config = SystemConfig(
                config_key="active_brain_model",
                config_value=active_models[0],
                config_type="string",
                description="Primary active brain model (for backward compatibility)"
            )
            db.add(single_config)
        
        db.commit()
        
        # Verify model exists in Ollama (primary or fallback)
        try:
            from backend.services.local_brain_manager import try_primary_then_fallback
            ollama_url = await try_primary_then_fallback()
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{ollama_url.rstrip('/')}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    if model_name not in models:
                        return {
                            "success": False,
                            "error": f"Model {model_name} not found in Ollama. Available: {', '.join(models)}"
                        }
        except Exception as e:
            logger.warning(f"Could not verify model in Ollama: {e}")
        
        return {
            "success": True,
            "model": model_name,
            "enabled": enabled,
            "active_models": active_models,
            "message": f"Model {model_name} {'enabled' if enabled else 'disabled'}. Active models: {', '.join(active_models)}"
        }
    finally:
        db.close()

@router.delete("/models/{model_name}")
async def delete_model(model_name: str) -> Dict[str, Any]:
    """Delete a model from Ollama (primary or fallback)"""
    try:
        from backend.services.local_brain_manager import try_primary_then_fallback
        ollama_url = await try_primary_then_fallback()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{ollama_url.rstrip('/')}/api/delete",
                json={"name": model_name}
            )
            return {
                "success": response.status_code == 200,
                "model": model_name,
                "message": f"Deleted {model_name}" if response.status_code == 200 else "Failed to delete"
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/models/usage")
async def get_model_usage() -> Dict[str, Any]:
    """Get usage statistics for models from database"""
    from backend.database import SessionLocal, ChatMessage
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    db = SessionLocal()
    try:
        # Get usage stats for last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # Count messages by model
        usage_stats = db.query(
            ChatMessage.model,
            func.count(ChatMessage.id).label('call_count'),
            func.sum(ChatMessage.tokens).label('total_tokens')
        ).filter(
            ChatMessage.created_at >= thirty_days_ago,
            ChatMessage.model.isnot(None)
        ).group_by(ChatMessage.model).all()
        
        stats = {}
        for model, calls, tokens in usage_stats:
            stats[model or "unknown"] = {
                "calls": calls or 0,
                "tokens": tokens or 0
            }
        
        return {
            "success": True,
            "period": "30_days",
            "stats": stats
        }
    finally:
        db.close()
