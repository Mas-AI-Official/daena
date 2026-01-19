"""
Hardware abstraction layer for CPU/GPU/ROCm/TPU/Google TPUs compute.
Provides clean device abstraction with auto-detection and XLA support for TPU.
Supports both general TPU architectures and Google's specialized TPUs (Trillium, Ironwood, etc.).
"""

import os
import logging
from typing import Optional, Literal, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class DeviceType(str, Enum):
    """Supported device types."""
    AUTO = "auto"
    CPU = "cpu"
    CUDA = "cuda"
    ROCM = "rocm"
    TPU = "tpu"


class ComputeAdapter:
    """
    Hardware abstraction for compute operations.
    Supports CPU, GPU (CUDA), ROCm, TPU, and Google TPUs (Trillium, Ironwood, etc.) via XLA.
    Automatically detects and adapts to available hardware, including Google Cloud TPU infrastructure.
    """
    
    def __init__(self, device: Optional[DeviceType] = None):
        """
        Initialize compute adapter.
        
        Args:
            device: Device type (auto, cpu, cuda, rocm, tpu). If None, uses DAENA_DEVICE env var.
        """
        self.device_type = device or DeviceType(os.getenv("DAENA_DEVICE", "auto"))
        self._device = None
        self._backend = None
        self._memory_limit = None
        
        self._initialize_device()
    
    def _initialize_device(self):
        """Initialize the compute device."""
        if self.device_type == DeviceType.AUTO:
            self.device_type = self._auto_detect_device()
        
        if self.device_type == DeviceType.CUDA:
            self._init_cuda()
        elif self.device_type == DeviceType.ROCM:
            self._init_rocm()
        elif self.device_type == DeviceType.TPU:
            self._init_tpu()
        else:
            self._init_cpu()
    
    def _auto_detect_device(self) -> DeviceType:
        """Auto-detect available device."""
        # Check CUDA
        try:
            import torch
            if torch.cuda.is_available():
                logger.info("CUDA device detected")
                return DeviceType.CUDA
        except ImportError:
            pass
        
        # Check ROCm
        try:
            import torch
            if hasattr(torch.version, 'hip') and torch.version.hip:
                logger.info("ROCm device detected")
                return DeviceType.ROCM
        except ImportError:
            pass
        
        # Check TPU
        try:
            import torch_xla
            if torch_xla._XLAC._xla_get_default_device():
                logger.info("TPU device detected")
                return DeviceType.TPU
        except (ImportError, AttributeError):
            pass
        
        logger.info("Using CPU (no GPU/TPU detected)")
        return DeviceType.CPU
    
    def _init_cuda(self):
        """Initialize CUDA device."""
        try:
            import torch
            if torch.cuda.is_available():
                self._device = torch.device("cuda")
                self._backend = "cuda"
                self._memory_limit = torch.cuda.get_device_properties(0).total_memory
                logger.info(f"CUDA initialized: {torch.cuda.get_device_name(0)} ({self._memory_limit / 1e9:.2f} GB)")
            else:
                logger.warning("CUDA requested but not available, falling back to CPU")
                self._init_cpu()
        except ImportError:
            logger.warning("PyTorch not available, falling back to CPU")
            self._init_cpu()
    
    def _init_rocm(self):
        """Initialize ROCm device."""
        try:
            import torch
            if hasattr(torch.version, 'hip') and torch.version.hip:
                self._device = torch.device("cuda")  # ROCm uses CUDA API
                self._backend = "rocm"
                # Get memory info if available
                try:
                    self._memory_limit = torch.cuda.get_device_properties(0).total_memory
                except:
                    self._memory_limit = None
                logger.info("ROCm initialized")
            else:
                logger.warning("ROCm requested but not available, falling back to CPU")
                self._init_cpu()
        except ImportError:
            logger.warning("PyTorch not available, falling back to CPU")
            self._init_cpu()
    
    def _init_tpu(self):
        """Initialize TPU device via XLA."""
        try:
            import torch_xla
            import torch_xla.core.xla_model as xm
            
            # Get default TPU device
            device = xm.xla_device()
            self._device = device
            self._backend = "tpu"
            
            # Check for BF16 support
            use_bf16 = os.getenv("XLA_USE_BF16", "false").lower() == "true"
            if use_bf16:
                logger.info("TPU initialized with BF16 support")
            else:
                logger.info("TPU initialized")
        except ImportError:
            logger.warning("PyTorch XLA not available, falling back to CPU")
            self._init_cpu()
        except Exception as e:
            logger.warning(f"TPU initialization failed: {e}, falling back to CPU")
            self._init_cpu()
    
    def _init_cpu(self):
        """Initialize CPU device."""
        try:
            import torch
            self._device = torch.device("cpu")
            self._backend = "cpu"
            # Get system RAM (approximate)
            import psutil
            self._memory_limit = psutil.virtual_memory().total
            logger.info(f"CPU initialized ({self._memory_limit / 1e9:.2f} GB RAM)")
        except ImportError:
            self._device = None
            self._backend = "cpu"
            logger.info("CPU initialized (no PyTorch)")
    
    @property
    def device(self):
        """Get the device object."""
        return self._device
    
    @property
    def backend(self) -> str:
        """Get the backend name."""
        return self._backend or "cpu"
    
    @property
    def device_type(self) -> DeviceType:
        """Get the device type."""
        return self._device_type
    
    @property
    def memory_limit(self) -> Optional[int]:
        """Get memory limit in bytes."""
        return self._memory_limit
    
    def get_device_info(self) -> Dict[str, Any]:
        """Get device information."""
        info = {
            "device_type": self.device_type.value,
            "backend": self.backend,
            "memory_limit_bytes": self.memory_limit,
            "memory_limit_gb": self.memory_limit / 1e9 if self.memory_limit else None
        }
        
        if self.backend == "cuda":
            try:
                import torch
                if torch.cuda.is_available():
                    info["cuda_device_name"] = torch.cuda.get_device_name(0)
                    info["cuda_version"] = torch.version.cuda
            except:
                pass
        
        return info
    
    def to(self, tensor_or_model):
        """Move tensor or model to this device."""
        if self._device is None:
            return tensor_or_model
        
        try:
            import torch
            if isinstance(tensor_or_model, torch.nn.Module):
                return tensor_or_model.to(self._device)
            elif isinstance(tensor_or_model, torch.Tensor):
                return tensor_or_model.to(self._device)
            else:
                return tensor_or_model
        except ImportError:
            return tensor_or_model
    
    def __repr__(self) -> str:
        return f"ComputeAdapter(device={self.device_type.value}, backend={self.backend})"


# Global singleton
_compute_adapter: Optional[ComputeAdapter] = None


def get_compute_adapter(device: Optional[DeviceType] = None) -> ComputeAdapter:
    """Get or create the global compute adapter instance."""
    global _compute_adapter
    if _compute_adapter is None:
        _compute_adapter = ComputeAdapter(device)
    return _compute_adapter


def verify_device_stack() -> Dict[str, Any]:
    """Verify device stack and print detected backends."""
    adapter = get_compute_adapter()
    info = adapter.get_device_info()
    
    print("=" * 60)
    print("DEVICE STACK VERIFICATION")
    print("=" * 60)
    print(f"Device Type: {info['device_type']}")
    print(f"Backend: {info['backend']}")
    if info['memory_limit_gb']:
        print(f"Memory Limit: {info['memory_limit_gb']:.2f} GB")
    if 'cuda_device_name' in info:
        print(f"CUDA Device: {info['cuda_device_name']}")
    print("=" * 60)
    
    return info


if __name__ == "__main__":
    verify_device_stack()

