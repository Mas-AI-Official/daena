"""
ModelGateway: Hardware-Aware Model Client Abstraction

Provides a unified interface for model inference across different hardware backends
(CPU, GPU, TPU) and model providers (Azure, OpenAI, HuggingFace, local).

This abstraction allows switching hardware backends without changing model client code.
"""

from __future__ import annotations

import os
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ModelProvider(str, Enum):
    """Supported model providers"""
    AZURE = "azure"
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class HardwareBackend(str, Enum):
    """Supported hardware backends"""
    CPU = "cpu"
    GPU = "gpu"
    TPU = "tpu"
    AUTO = "auto"


@dataclass
class ModelRequest:
    """Request for model inference"""
    prompt: str
    model_name: Optional[str] = None
    provider: Optional[ModelProvider] = None
    hardware_backend: Optional[HardwareBackend] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ModelResponse:
    """Response from model inference"""
    text: str
    provider: ModelProvider
    hardware_backend: HardwareBackend
    model_name: str
    tokens_used: Optional[int] = None
    latency_ms: Optional[float] = None
    cost_estimate: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class ModelGateway:
    """
    Hardware-aware model gateway that abstracts model clients.
    
    Features:
    - Automatic hardware backend selection (CPU/GPU/TPU)
    - Provider abstraction (Azure, OpenAI, HuggingFace, local)
    - DeviceManager integration for hardware routing
    - Cost tracking and latency monitoring
    """
    
    def __init__(
        self,
        hardware_backend: Union[str, HardwareBackend] = HardwareBackend.AUTO,
        default_provider: Union[str, ModelProvider] = ModelProvider.AZURE,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize ModelGateway.
        
        Args:
            hardware_backend: Preferred hardware backend (auto, cpu, gpu, tpu)
            default_provider: Default model provider
            config: Optional configuration dictionary
        """
        self.hardware_backend = HardwareBackend(hardware_backend) if isinstance(hardware_backend, str) else hardware_backend
        self.default_provider = ModelProvider(default_provider) if isinstance(default_provider, str) else default_provider
        self.config = config or {}
        
        # Initialize DeviceManager for hardware abstraction
        try:
            from Core.device_manager import DeviceManager, get_device_manager
            self.device_manager = get_device_manager(
                prefer=self.hardware_backend.value if self.hardware_backend != HardwareBackend.AUTO else "auto",
                allow_tpu=self.hardware_backend == HardwareBackend.TPU or self.hardware_backend == HardwareBackend.AUTO
            )
            self._actual_backend = HardwareBackend(self.device_manager.current_device.device_type.value)
        except Exception as e:
            logger.warning(f"DeviceManager not available, falling back to CPU: {e}")
            self.device_manager = None
            self._actual_backend = HardwareBackend.CPU
        
        # Initialize provider clients (lazy loading)
        self._providers: Dict[ModelProvider, Any] = {}
        
        logger.info(f"ModelGateway initialized: backend={self._actual_backend.value}, provider={self.default_provider.value}")
    
    def _get_provider_client(self, provider: ModelProvider) -> Any:
        """Get or create provider client (lazy loading)"""
        if provider in self._providers:
            return self._providers[provider]
        
        # Lazy load provider clients
        if provider == ModelProvider.AZURE:
            try:
                from backend.llm.model_router import ModelRouter
                router = ModelRouter.load()
                self._providers[provider] = router
            except Exception as e:
                logger.warning(f"Azure provider not available: {e}")
                return None
        elif provider == ModelProvider.OPENAI:
            try:
                import openai
                self._providers[provider] = openai
            except ImportError:
                logger.warning("OpenAI SDK not installed")
                return None
        elif provider == ModelProvider.HUGGINGFACE:
            try:
                from transformers import pipeline
                self._providers[provider] = {"pipeline": pipeline}
            except ImportError:
                logger.warning("HuggingFace transformers not installed")
                return None
        elif provider == ModelProvider.LOCAL:
            try:
                from Core.llm.model_integration import ModelIntegration
                self._providers[provider] = ModelIntegration()
            except Exception as e:
                logger.warning(f"Local model integration not available: {e}")
                return None
        
        return self._providers.get(provider)
    
    async def generate(
        self,
        request: ModelRequest,
        **kwargs
    ) -> ModelResponse:
        """
        Generate response using the specified or default provider and hardware backend.
        
        Args:
            request: Model request
            **kwargs: Additional provider-specific arguments
        
        Returns:
            ModelResponse with generated text and metadata
        """
        import time
        start_time = time.time()
        
        # Determine provider
        provider = request.provider or self.default_provider
        
        # Determine hardware backend
        backend = request.hardware_backend or self._actual_backend
        
        # Get provider client
        client = self._get_provider_client(provider)
        if client is None:
            raise ValueError(f"Provider {provider.value} not available")
        
        # Route to appropriate hardware backend
        if backend == HardwareBackend.TPU and self.device_manager:
            # TPU-specific batching and routing
            response_text = await self._generate_tpu(client, provider, request, **kwargs)
        elif backend == HardwareBackend.GPU and self.device_manager:
            # GPU-specific routing
            response_text = await self._generate_gpu(client, provider, request, **kwargs)
        else:
            # CPU fallback
            response_text = await self._generate_cpu(client, provider, request, **kwargs)
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Estimate cost (simplified)
        cost_estimate = self._estimate_cost(provider, request, len(response_text))
        
        return ModelResponse(
            text=response_text,
            provider=provider,
            hardware_backend=backend,
            model_name=request.model_name or "default",
            latency_ms=latency_ms,
            cost_estimate=cost_estimate,
            metadata={
                "device_id": self.device_manager.current_device.device_id if self.device_manager else "cpu",
                "device_type": backend.value
            }
        )
    
    async def _generate_tpu(self, client: Any, provider: ModelProvider, request: ModelRequest, **kwargs) -> str:
        """Generate using TPU backend"""
        # TPU-specific logic: batch processing, JAX routing, etc.
        logger.info(f"Generating on TPU via {provider.value}")
        # For now, delegate to CPU/GPU logic with TPU-aware batching
        return await self._generate_cpu(client, provider, request, **kwargs)
    
    async def _generate_gpu(self, client: Any, provider: ModelProvider, request: ModelRequest, **kwargs) -> str:
        """Generate using GPU backend"""
        logger.info(f"Generating on GPU via {provider.value}")
        # GPU-specific logic: CUDA routing, batch optimization, etc.
        return await self._generate_cpu(client, provider, request, **kwargs)
    
    async def _generate_cpu(self, client: Any, provider: ModelProvider, request: ModelRequest, **kwargs) -> str:
        """Generate using CPU backend (fallback)"""
        logger.info(f"Generating on CPU via {provider.value}")
        
        if provider == ModelProvider.AZURE:
            # Use ModelRouter for Azure
            task = request.metadata.get("task", "chat_default") if request.metadata else "chat_default"
            cfg = client.pick(task)
            # Simplified: would call actual Azure API here
            return f"[Azure/{cfg.get('deployment', 'default')}] Response to: {request.prompt[:50]}..."
        elif provider == ModelProvider.OPENAI:
            # Use OpenAI SDK
            # Simplified: would call actual OpenAI API here
            return f"[OpenAI] Response to: {request.prompt[:50]}..."
        elif provider == ModelProvider.LOCAL:
            # Use local ModelIntegration
            if hasattr(client, "generate_response"):
                result = await client.generate_response(request.prompt, request.context)
                return result.get("response", "No response")
            return f"[Local] Response to: {request.prompt[:50]}..."
        else:
            return f"[{provider.value}] Response to: {request.prompt[:50]}..."
    
    def _estimate_cost(self, provider: ModelProvider, request: ModelRequest, response_length: int) -> float:
        """Estimate cost for the request (simplified)"""
        # Simplified cost estimation
        # In production, would use actual pricing tables
        base_costs = {
            ModelProvider.AZURE: 0.002,  # per 1k tokens
            ModelProvider.OPENAI: 0.003,
            ModelProvider.HUGGINGFACE: 0.001,
            ModelProvider.LOCAL: 0.0,
        }
        
        base_cost = base_costs.get(provider, 0.002)
        estimated_tokens = (len(request.prompt) + response_length) / 4  # Rough token estimate
        return (estimated_tokens / 1000) * base_cost
    
    def get_hardware_info(self) -> Dict[str, Any]:
        """Get current hardware backend information"""
        if self.device_manager:
            return self.device_manager.get_device_report()
        return {
            "backend": "cpu",
            "device_id": "cpu",
            "available": True
        }


# Global ModelGateway instance
_model_gateway: Optional[ModelGateway] = None


def get_model_gateway(
    hardware_backend: Union[str, HardwareBackend] = HardwareBackend.AUTO,
    default_provider: Union[str, ModelProvider] = ModelProvider.AZURE,
    config: Optional[Dict[str, Any]] = None
) -> ModelGateway:
    """
    Get or create global ModelGateway instance.
    
    Args:
        hardware_backend: Preferred hardware backend
        default_provider: Default model provider
        config: Optional configuration
    
    Returns:
        ModelGateway instance
    """
    global _model_gateway
    
    if _model_gateway is None:
        _model_gateway = ModelGateway(
            hardware_backend=hardware_backend,
            default_provider=default_provider,
            config=config
        )
    
    return _model_gateway


def reset_model_gateway() -> None:
    """Reset global ModelGateway (useful for testing)"""
    global _model_gateway
    _model_gateway = None

