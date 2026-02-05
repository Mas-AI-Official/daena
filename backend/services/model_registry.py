"""
Model Registry - Single Source of Truth for Brain Status

Tracks:
- Available models (from Ollama)
- Active model
- Routing mode (local_only, api_only, hybrid)
- GPU info

This is the ONLY place model state is stored. UI and chat must query this.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class RoutingMode(str, Enum):
    LOCAL_ONLY = "local_only"
    API_ONLY = "api_only"
    HYBRID = "hybrid"


class ModelTier(str, Enum):
    STABLE = "stable"
    EXPERIMENTAL = "experimental"


@dataclass
class ModelInfo:
    """Information about a single model"""
    name: str
    size: int = 0
    family: str = ""
    parameter_size: str = ""
    quantization: str = ""
    tier: ModelTier = ModelTier.STABLE
    capabilities: List[str] = field(default_factory=list)
    is_reasoning: bool = False
    is_coding: bool = False
    last_used: Optional[datetime] = None


@dataclass
class BrainStatus:
    """Complete brain status"""
    connected: bool = False
    provider: str = "ollama"
    models: List[ModelInfo] = field(default_factory=list)
    active_model: Optional[str] = None
    routing_mode: RoutingMode = RoutingMode.LOCAL_ONLY
    gpu_info: Dict[str, Any] = field(default_factory=dict)
    last_scan: Optional[datetime] = None
    error: Optional[str] = None


class ModelRegistry:
    """
    Central registry for all model-related state.
    
    Usage:
        registry = get_model_registry()
        status = await registry.get_status()
        await registry.set_active_model("deepseek-r1:8b")
    """
    
    _instance = None
    
    def __init__(self):
        self._ollama_url = "http://127.0.0.1:11434"
        self._status = BrainStatus()
        self._stable_models = set()  # Models verified for production
        self._experimental_models = set()  # Auto-discovered, not verified
        
        # Default stable models (known good)
        self._stable_models = {
            "qwen2.5:7b-instruct",
            "qwen2.5:14b-instruct", 
            "deepseek-r1:8b",
            "deepseek-r1:14b",
            "llama3.2:latest",
            "mistral:latest",
        }
        
        # Recommended models to install
        self._recommended_models = [
            {
                "name": "deepseek-r1:8b",
                "description": "Best local reasoning model (Small)",
                "size": "4.7GB",
                "tier": "stable",
                "capabilities": ["reasoning", "logic", "math"]
            },
            {
                "name": "qwen2.5:7b-instruct",
                "description": "Best general assistant (Fast)",
                "size": "4.7GB",
                "tier": "stable",
                "capabilities": ["chat", "coding", "general"]
            },
            {
                "name": "qwen2.5-coder:7b",
                "description": "Specialized coding model",
                "size": "4.7GB",
                "tier": "stable",
                "capabilities": ["coding", "python", "javascript"]
            },
            {
                "name": "llama3.2:3b",
                "description": "Ultra-fast small model",
                "size": "2.0GB",
                "tier": "experimental",
                "capabilities": ["chat", "fast"]
            },
            {
                "name": "phi4:latest",
                "description": "Microsoft's latest small model",
                "size": "9.0GB",
                "tier": "experimental",
                "capabilities": ["reasoning", "math"]
            }
        ]
    
    def get_recommended_models(self) -> List[Dict[str, Any]]:
        """Get list of recommended models with installation status"""
        installed = {m.name for m in self._status.models}
        
        results = []
        for model in self._recommended_models:
            m = model.copy()
            m["installed"] = model["name"] in installed
            results.append(m)
            
        return results
    
    @classmethod
    def get_instance(cls) -> "ModelRegistry":
        if cls._instance is None:
            cls._instance = ModelRegistry()
        return cls._instance
    
    async def scan_models(self) -> List[ModelInfo]:
        """
        Scan Ollama & DB for available models.
        Syncs Ollama state to BrainModels table.
        """
        from backend.database import SessionLocal, BrainModel
        
        models = []
        db_models = []
        
        # 1. Get Configured Cloud/DB Models
        db = SessionLocal()
        try:
            db_rows = db.query(BrainModel).filter(BrainModel.enabled == True).all()
            for row in db_rows:
                # Convert DB row to ModelInfo
                tier = ModelTier.STABLE # Default for manually added
                info = ModelInfo(
                    name=row.model_id, # Use logical ID as name
                    size=0, # Cloud models don't have file size
                    family=row.provider,
                    tier=tier,
                    capabilities=row.capabilities or [],
                    is_reasoning="reasoning" in (row.capabilities or []),
                    is_coding="coding" in (row.capabilities or []),
                )
                models.append(info)
        except Exception as e:
            logger.error(f"DB Read Error: {e}")
        finally:
            db.close()

        # 2. Scan Ollama (Local)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._ollama_url}/api/tags")
                
                if response.status_code == 200:
                    data = response.json()
                    db = SessionLocal()
                    
                    for m in data.get("models", []):
                        name = m.get("name", "")
                        
                        # Sync to DB if missing
                        try:
                            exists = db.query(BrainModel).filter(BrainModel.model_id == name).first()
                            if not exists:
                                # Determine capabilities
                                caps = ["chat"]
                                if any(x in name.lower() for x in ["deepseek-r1", "reasoning"]): caps.append("reasoning")
                                if "coder" in name.lower(): caps.append("coding")
                                
                                new_model = BrainModel(
                                    model_id=name,
                                    name=name,
                                    provider="ollama",
                                    model_name=name,
                                    capabilities=caps,
                                    enabled=True
                                )
                                db.add(new_model)
                                db.commit()
                        except:
                            pass
                        
                        # ... (existing classification logic) ...
                        tier = ModelTier.STABLE if name in self._stable_models else ModelTier.EXPERIMENTAL
                        is_reasoning = any(x in name.lower() for x in ["deepseek-r1", "qwq", "reasoning"])
                        is_coding = any(x in name.lower() for x in ["coder", "code", "starcoder"])
                        
                        caps = []
                        if is_reasoning: caps.append("reasoning")
                        if is_coding: caps.append("coding")
                        
                        model_info = ModelInfo(
                            name=name,
                            size=m.get("size", 0),
                            family=m.get("details", {}).get("family", ""),
                            parameter_size=m.get("details", {}).get("parameter_size", ""),
                            quantization=m.get("details", {}).get("quantization_level", ""),
                            tier=tier,
                            capabilities=caps,
                            is_reasoning=is_reasoning,
                            is_coding=is_coding,
                        )
                        # Avoid duplicates if DB already added it (checked by name/id collision?)
                        # DB scan used model_id. Ollama uses name. If they match, we update/overwrite with fresh details.
                        # For list display, we prefer live Ollama stats (size, quant) over DB placeholder.
                        
                        # Remove placeholder if present
                        models = [x for x in models if x.name != name]
                        models.append(model_info)
                        
                        if tier == ModelTier.EXPERIMENTAL:
                            self._experimental_models.add(name)
                    
                    self._status.connected = True
                    db.close()
                else:
                    self._status.connected = False
        except Exception as e:
            logger.error(f"Ollama Scan Error: {e}")
            # Don't fail completely, keep DB models
        
        self._status.models = models
        self._status.last_scan = datetime.utcnow()
        return models

    async def register_model(self, model_data: Dict[str, Any]) -> bool:
        """Register a new cloud/API model"""
        from backend.database import SessionLocal, BrainModel
        db = SessionLocal()
        try:
             # Basic mapping
             m = BrainModel(
                 model_id=model_data["model_id"],
                 name=model_data.get("name"),
                 provider=model_data["provider"], # azure_openai, azure_ai_inference
                 endpoint_base=model_data.get("endpoint_base"),
                 deployment_name=model_data.get("deployment_name"),
                 model_name=model_data.get("model_name"),
                 api_version=model_data.get("api_version"),
                 capabilities=model_data.get("capabilities", []),
                 cost_per_1k_input=model_data.get("cost_per_1k_input", 0.0),
                 cost_per_1k_output=model_data.get("cost_per_1k_output", 0.0),
                 enabled=True
             )
             db.add(m)
             db.commit()
             await self.scan_models() # Refresh cache
             return True
        except Exception as e:
             logger.error(f"Register failed: {e}")
             return False
        finally:
             db.close()

    
    def set_routing_mode(self, mode: RoutingMode) -> bool:
        """Set the routing mode."""
        self._status.routing_mode = mode
        logger.info(f"✅ Routing mode set to: {mode.value}")
        return True
    
    def get_active_model(self) -> Optional[str]:
        """Get the current active model name."""
        return self._status.active_model
    
    def get_routing_mode(self) -> RoutingMode:
        """Get the current routing mode."""
        return self._status.routing_mode
    
    def get_best_model_for_task(self, task_type: str) -> Optional[str]:
        """
        Get the best model for a given task type.
        
        Args:
            task_type: One of "reasoning", "coding", "chat", "creative"
            
        Returns:
            Model name or None if no suitable model found
        """
        if not self._status.models:
            return self._status.active_model
        
        # Filter by routing mode
        available = self._status.models
        if self._status.routing_mode == RoutingMode.LOCAL_ONLY:
            # Only local models (all Ollama models are local)
            pass
        
        # Prefer stable models unless in experimental mode
        stable = [m for m in available if m.tier == ModelTier.STABLE]
        
        if task_type == "reasoning":
            # Look for reasoning models
            reasoning = [m for m in stable if m.is_reasoning]
            if reasoning:
                return reasoning[0].name
            # Fallback to experimental reasoning
            reasoning = [m for m in available if m.is_reasoning]
            if reasoning:
                return reasoning[0].name
                
        elif task_type == "coding":
            # Look for coding models
            coding = [m for m in stable if m.is_coding]
            if coding:
                return coding[0].name
            coding = [m for m in available if m.is_coding]
            if coding:
                return coding[0].name
        
        # Default to active model
        return self._status.active_model
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert status to dict for API response."""
        return {
            "connected": self._status.connected,
            "provider": self._status.provider,
            "models": [
                {
                    "name": m.name,
                    "size": m.size,
                    "family": m.family,
                    "parameter_size": m.parameter_size,
                    "tier": m.tier.value,
                    "capabilities": m.capabilities,
                    "is_reasoning": m.is_reasoning,
                    "is_coding": m.is_coding,
                }
                for m in self._status.models
            ],
            "active_model": self._status.active_model,
            "routing_mode": self._status.routing_mode.value,
            "gpu_info": self._status.gpu_info,
            "last_scan": self._status.last_scan.isoformat() if self._status.last_scan else None,
            "error": self._status.error,
        }


def get_model_registry() -> ModelRegistry:
    """Get the global model registry instance."""
    return ModelRegistry.get_instance()


# Convenience functions for backwards compatibility
async def get_active_model() -> Optional[str]:
    """Get the current active model name."""
    registry = get_model_registry()
    return registry.get_active_model()


async def get_brain_status() -> Dict[str, Any]:
    """Get brain status as dict."""
    registry = get_model_registry()
    await registry.get_status()
    return registry.to_dict()


# Module-level singleton for backwards compatibility with route imports
model_registry = get_model_registry()
