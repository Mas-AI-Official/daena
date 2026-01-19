"""
⚠️ DEPRECATED - DO NOT USE

This module is DEPRECATED and UNUSED. It was replaced by backend/services/llm_service.py
which provides local-first LLM routing with Ollama support.

All routing should go through:
- backend/services/llm_service.py (canonical LLM service)
- backend/daena_brain.py (uses llm_service)

This file is kept for reference only and will be removed in a future version.
"""

import os
import time
from typing import Dict, Any
import httpx
import json
from pathlib import Path

# DEPRECATED: Use backend/services/llm_service.py instead
class ModelRouter:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg

    @classmethod
    def load(cls):
        import json
        import pathlib
        p = pathlib.Path(__file__).resolve().parents[1] / "config" / "model_registry.json"
        if p.exists():
            return cls(json.loads(p.read_text()))
        else:
            # Return default config if file doesn't exist
            return cls({
                "provider": "azure",
                "azure": {
                    "endpoint_env": "AZURE_OPENAI_ENDPOINT",
                    "api_key_env": "AZURE_OPENAI_KEY",
                    "api_version_env": "AZURE_OPENAI_API_VERSION",
                    "deployments": {
                        "chat_default": "daena",
                        "summarize": "daena",
                        "ground": "daena",
                        "embed": "daena",
                        "vision": "daena",
                        "fast_tools": "daena"
                    }
                },
                "fallbacks": ["openai", "local"],
                "openai": {"api_key_env": "OPENAI_API_KEY", "models": {"chat_default": "gpt-4o"}},
                "local": {"enabled": False}
            })

    def _azure_cfg(self):
        az = self.cfg.get("azure", {})
        return {
            "endpoint": os.getenv(az.get("endpoint_env", "AZURE_OPENAI_ENDPOINT"), ""),
            "key": os.getenv(az.get("api_key_env", "AZURE_OPENAI_KEY"), ""),
            "api_version": os.getenv(az.get("api_version_env", "AZURE_OPENAI_API_VERSION"), "2024-02-01"),
            "deployments": az.get("deployments", {})
        }

    def pick(self, task: str) -> Dict[str, str]:
        if self.cfg.get("provider") == "azure":
            az = self._azure_cfg()
            dep = az["deployments"].get(task) or az["deployments"].get("chat_default")
            return {"provider": "azure", "deployment": dep, **az}
        # add openai/local if needed (fallbacks)
        return {"provider": "none", "deployment": ""}

    def health(self) -> Dict[str, Any]:
        info = self.pick("chat_default")
        ok = False
        err = None
        if info["provider"] == "azure" and info["endpoint"] and info["key"]:
            try:
                # minimal chat completion ping
                url = f'{info["endpoint"].rstrip("/")}/openai/deployments/{info["deployment"]}/chat/completions?api-version={info["api_version"]}'
                hdr = {"api-key": info["key"]}
                data = {"messages": [{"role": "user", "content": "ping"}], "temperature": 0, "max_tokens": 5}
                with httpx.Client(timeout=8.0) as client:
                    r = client.post(url, headers=hdr, json=data)
                    ok = (r.status_code // 100) == 2
                    err = None if ok else f"{r.status_code}"
            except Exception as e:
                err = str(e)
        return {"ok": ok, "provider": info["provider"], "deployments": self.cfg.get("azure", {}).get("deployments", {}), "error": err}

    def chat(self, task: str, messages: list, **opts) -> Dict[str, Any]:
        """Route chat request to appropriate model based on task."""
        info = self.pick(task)
        if info["provider"] == "azure":
            # Use existing LLM service for Azure
            try:
                from backend.services.llm_service import llm_service
                return llm_service.chat_completion(messages, **opts)
            except ImportError:
                return {"error": "LLM service not available"}
        else:
            return {"error": f"Provider {info['provider']} not implemented"}

# Global instance
model_router = ModelRouter.load() 