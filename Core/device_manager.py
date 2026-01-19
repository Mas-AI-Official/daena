"""
DeviceManager: Hardware Abstraction Layer for CPU, GPU, and TPU

Provides unified interface for tensor operations across different compute devices.
Supports automatic device detection, selection, and batching optimization.
"""

from __future__ import annotations

import os
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class DeviceType(str, Enum):
    """Supported compute device types"""
    CPU = "cpu"
    GPU = "gpu"
    TPU = "tpu"
    AUTO = "auto"


@dataclass
class DeviceInfo:
    """Information about a compute device"""
    device_type: DeviceType
    device_id: str
    name: str
    memory_gb: Optional[float] = None
    compute_capability: Optional[str] = None
    available: bool = True
    cost_per_hour: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchConfig:
    """Configuration for batch processing"""
    batch_size: int
    max_batch_size: int
    min_batch_size: int = 1
    prefetch_factor: int = 2


class DeviceManager:
    """
    Hardware abstraction layer for CPU, GPU, and TPU operations.
    
    Features:
    - Automatic device detection (CPU, GPU, TPU)
    - Device selection based on configuration
    - Batch size optimization for TPU
    - Memory management
    - Cost tracking
    """
    
    def __init__(
        self,
        prefer: str = "auto",
        allow_tpu: bool = True,
        tpu_batch_factor: int = 128,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize DeviceManager.
        
        Args:
            prefer: Device preference ("auto", "cpu", "gpu", "tpu")
            allow_tpu: Whether to allow TPU usage
            tpu_batch_factor: Batch size multiplier for TPU (default 128)
            config: Optional configuration dictionary
        """
        self.prefer = DeviceType(prefer.lower()) if prefer else DeviceType.AUTO
        self.allow_tpu = allow_tpu
        self.tpu_batch_factor = tpu_batch_factor
        self.config = config or {}
        
        # Device detection
        self.devices: Dict[str, DeviceInfo] = {}
        self.current_device: Optional[DeviceInfo] = None
        self._detected_devices: List[DeviceInfo] = []
        
        # Framework availability
        self._torch_available = False
        self._tensorflow_available = False
        self._jax_available = False
        
        # Initialize
        self._detect_frameworks()
        self._detect_devices()
        self._select_device()
    
    def _detect_frameworks(self) -> None:
        """Detect available ML frameworks"""
        try:
            import torch
            self._torch_available = True
            logger.info("✅ PyTorch detected")
        except ImportError:
            logger.debug("PyTorch not available")
        
        try:
            import tensorflow as tf
            self._tensorflow_available = True
            logger.info("✅ TensorFlow detected")
        except ImportError:
            logger.debug("TensorFlow not available")
        
        try:
            import jax
            self._jax_available = True
            logger.info("✅ JAX detected (TPU support available)")
        except ImportError:
            logger.debug("JAX not available (TPU support unavailable)")
    
    def _detect_devices(self) -> None:
        """Detect all available compute devices"""
        self._detected_devices = []
        
        # Always add CPU
        cpu_info = DeviceInfo(
            device_type=DeviceType.CPU,
            device_id="cpu:0",
            name="CPU",
            memory_gb=self._get_cpu_memory(),
            available=True,
            cost_per_hour=0.0
        )
        self._detected_devices.append(cpu_info)
        self.devices["cpu:0"] = cpu_info
        
        # Detect GPU
        gpu_devices = self._detect_gpu()
        for gpu in gpu_devices:
            self._detected_devices.append(gpu)
            self.devices[gpu.device_id] = gpu
        
        # Detect TPU
        if self.allow_tpu:
            tpu_devices = self._detect_tpu()
            for tpu in tpu_devices:
                self._detected_devices.append(tpu)
                self.devices[tpu.device_id] = tpu
        
        logger.info(f"Detected {len(self._detected_devices)} compute devices")
    
    def _get_cpu_memory(self) -> float:
        """Get CPU memory in GB"""
        try:
            import psutil
            return psutil.virtual_memory().total / (1024 ** 3)
        except ImportError:
            return 16.0  # Default assumption
    
    def _detect_gpu(self) -> List[DeviceInfo]:
        """Detect available GPU devices"""
        gpus = []
        
        # Try PyTorch CUDA
        if self._torch_available:
            try:
                import torch
                if torch.cuda.is_available():
                    for i in range(torch.cuda.device_count()):
                        props = torch.cuda.get_device_properties(i)
                        memory_gb = props.total_memory / (1024 ** 3)
                        gpu = DeviceInfo(
                            device_type=DeviceType.GPU,
                            device_id=f"cuda:{i}",
                            name=props.name,
                            memory_gb=memory_gb,
                            compute_capability=f"{props.major}.{props.minor}",
                            available=True,
                            cost_per_hour=0.5,  # Estimated cost
                            metadata={"torch_device": f"cuda:{i}"}
                        )
                        gpus.append(gpu)
                        logger.info(f"✅ GPU detected: {props.name} ({memory_gb:.1f}GB)")
            except Exception as e:
                logger.debug(f"PyTorch GPU detection failed: {e}")
        
        # Try TensorFlow GPU
        if self._tensorflow_available and not gpus:
            try:
                import tensorflow as tf
                physical_gpus = tf.config.list_physical_devices('GPU')
                for i, gpu in enumerate(physical_gpus):
                    gpu_info = DeviceInfo(
                        device_type=DeviceType.GPU,
                        device_id=f"gpu:{i}",
                        name=gpu.name,
                        available=True,
                        cost_per_hour=0.5,
                        metadata={"tf_device": gpu.name}
                    )
                    gpus.append(gpu_info)
                    logger.info(f"✅ GPU detected via TensorFlow: {gpu.name}")
            except Exception as e:
                logger.debug(f"TensorFlow GPU detection failed: {e}")
        
        # Try nvidia-smi as fallback
        if not gpus:
            try:
                import subprocess
                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    for i, line in enumerate(result.stdout.strip().split('\n')):
                        if line.strip():
                            parts = line.split(',')
                            name = parts[0].strip()
                            memory_str = parts[1].strip() if len(parts) > 1 else "0 MiB"
                            # Parse memory (e.g., "8192 MiB")
                            memory_mb = float(memory_str.replace('MiB', '').strip())
                            memory_gb = memory_mb / 1024
                            
                            gpu = DeviceInfo(
                                device_type=DeviceType.GPU,
                                device_id=f"gpu:{i}",
                                name=name,
                                memory_gb=memory_gb,
                                available=True,
                                cost_per_hour=0.5
                            )
                            gpus.append(gpu)
                            logger.info(f"✅ GPU detected via nvidia-smi: {name} ({memory_gb:.1f}GB)")
            except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
                logger.debug(f"nvidia-smi detection failed: {e}")
        
        return gpus
    
    def _detect_tpu(self) -> List[DeviceInfo]:
        """Detect available TPU devices"""
        tpus = []
        
        # Check for JAX TPU
        if self._jax_available:
            try:
                import jax
                devices = jax.devices()
                tpu_devices = [d for d in devices if d.device_kind == 'tpu']
                
                if tpu_devices:
                    # Group TPUs by platform
                    platforms = {}
                    for device in tpu_devices:
                        platform = device.platform
                        if platform not in platforms:
                            platforms[platform] = []
                        platforms[platform].append(device)
                    
                    for platform, platform_devices in platforms.items():
                        # Estimate memory (TPU v4: 32GB per chip, v5: 64GB per chip)
                        memory_per_chip = 32.0  # Default to v4
                        if 'v5' in platform.lower() or 'trillium' in platform.lower():
                            memory_per_chip = 64.0
                        
                        total_memory = memory_per_chip * len(platform_devices)
                        
                        tpu = DeviceInfo(
                            device_type=DeviceType.TPU,
                            device_id=f"tpu:{platform}",
                            name=f"TPU {platform}",
                            memory_gb=total_memory,
                            available=True,
                            cost_per_hour=2.0,  # Estimated cost per hour
                            metadata={
                                "platform": platform,
                                "device_count": len(platform_devices),
                                "jax_devices": [str(d) for d in platform_devices]
                            }
                        )
                        tpus.append(tpu)
                        logger.info(f"✅ TPU detected: {platform} ({len(platform_devices)} devices, {total_memory:.1f}GB)")
            except Exception as e:
                logger.debug(f"JAX TPU detection failed: {e}")
        
        # Check for Cloud TPU via environment variables
        if not tpus:
            tpu_name = os.getenv('TPU_NAME')
            tpu_zone = os.getenv('TPU_ZONE')
            if tpu_name:
                tpu = DeviceInfo(
                    device_type=DeviceType.TPU,
                    device_id="tpu:cloud",
                    name=f"Cloud TPU ({tpu_name})",
                    available=True,
                    cost_per_hour=2.0,
                    metadata={"tpu_name": tpu_name, "tpu_zone": tpu_zone}
                )
                tpus.append(tpu)
                logger.info(f"✅ Cloud TPU detected: {tpu_name}")
        
        return tpus
    
    def _select_device(self) -> None:
        """Select the optimal device based on preference"""
        if self.prefer == DeviceType.AUTO:
            # Auto-select: TPU > GPU > CPU
            if self.allow_tpu:
                tpus = [d for d in self._detected_devices if d.device_type == DeviceType.TPU]
                if tpus:
                    self.current_device = tpus[0]
                    logger.info(f"Auto-selected: {self.current_device.name}")
                    return
            
            gpus = [d for d in self._detected_devices if d.device_type == DeviceType.GPU]
            if gpus:
                self.current_device = gpus[0]
                logger.info(f"Auto-selected: {self.current_device.name}")
                return
            
            self.current_device = self.devices["cpu:0"]
            logger.info("Auto-selected: CPU")
            return
        
        # Explicit preference
        preferred_devices = [
            d for d in self._detected_devices
            if d.device_type == self.prefer
        ]
        
        if preferred_devices:
            self.current_device = preferred_devices[0]
            logger.info(f"Selected: {self.current_device.name} (preference: {self.prefer})")
        else:
            # Fallback to CPU
            self.current_device = self.devices["cpu:0"]
            logger.warning(f"Preferred device {self.prefer} not available, falling back to CPU")
    
    def get_device(self) -> DeviceInfo:
        """Get the current active device"""
        return self.current_device or self.devices["cpu:0"]
    
    def get_device_for_tensor(self, tensor: Any = None) -> DeviceInfo:
        """
        Get the appropriate device for a tensor operation.
        
        Args:
            tensor: Optional tensor to check device placement
        
        Returns:
            DeviceInfo for the device to use
        """
        # If tensor has device info, use it
        if tensor is not None:
            try:
                # PyTorch tensor
                if hasattr(tensor, 'device'):
                    device_str = str(tensor.device)
                    if 'cuda' in device_str:
                        gpus = [d for d in self._detected_devices if d.device_type == DeviceType.GPU]
                        if gpus:
                            return gpus[0]
            except Exception:
                pass
        
        return self.get_device()
    
    def get_batch_config(self, base_batch_size: int = 1) -> BatchConfig:
        """
        Get batch configuration optimized for current device.
        
        Args:
            base_batch_size: Base batch size for CPU/GPU
        
        Returns:
            BatchConfig with optimized batch sizes
        """
        device = self.get_device()
        
        if device.device_type == DeviceType.TPU:
            # TPUs require larger batches for efficiency
            optimal_batch = base_batch_size * self.tpu_batch_factor
            # Round to nearest power of 2 for TPU efficiency
            optimal_batch = 2 ** (optimal_batch.bit_length() - 1) if optimal_batch > 1 else 1
            return BatchConfig(
                batch_size=optimal_batch,
                max_batch_size=optimal_batch * 4,
                min_batch_size=max(1, optimal_batch // 4)
            )
        elif device.device_type == DeviceType.GPU:
            # GPU: moderate batching
            optimal_batch = base_batch_size * 4
            return BatchConfig(
                batch_size=optimal_batch,
                max_batch_size=optimal_batch * 8,
                min_batch_size=1
            )
        else:
            # CPU: small batches
            return BatchConfig(
                batch_size=base_batch_size,
                max_batch_size=base_batch_size * 2,
                min_batch_size=1
            )
    
    def create_tensor(self, data: Any, dtype: Optional[str] = None) -> Any:
        """
        Create a tensor on the current device.
        
        Args:
            data: Data to convert to tensor
            dtype: Optional data type
        
        Returns:
            Tensor on the appropriate device
        """
        device = self.get_device()
        
        if device.device_type == DeviceType.TPU and self._jax_available:
            try:
                import jax.numpy as jnp
                return jnp.array(data, dtype=dtype)
            except Exception as e:
                logger.warning(f"JAX tensor creation failed: {e}, falling back to CPU")
        
        if device.device_type == DeviceType.GPU and self._torch_available:
            try:
                import torch
                tensor = torch.tensor(data, dtype=dtype)
                if device.device_id.startswith("cuda"):
                    return tensor.to(device.device_id)
                return tensor
            except Exception as e:
                logger.warning(f"PyTorch GPU tensor creation failed: {e}, falling back to CPU")
        
        # Fallback to CPU
        if self._torch_available:
            import torch
            return torch.tensor(data, dtype=dtype)
        elif self._tensorflow_available:
            import tensorflow as tf
            return tf.constant(data, dtype=dtype)
        else:
            import numpy as np
            return np.array(data, dtype=dtype)
    
    def move_to_device(self, tensor: Any, device_id: Optional[str] = None) -> Any:
        """
        Move tensor to specified device.
        
        Args:
            tensor: Tensor to move
            device_id: Target device ID (None = current device)
        
        Returns:
            Tensor on target device
        """
        if device_id is None:
            device = self.get_device()
            device_id = device.device_id
        
        # PyTorch
        if hasattr(tensor, 'to'):
            if device_id.startswith("cuda"):
                return tensor.to(device_id)
            elif device_id == "cpu:0":
                return tensor.cpu()
        
        # JAX (TPU)
        if device_id.startswith("tpu") and self._jax_available:
            try:
                import jax
                return jax.device_put(tensor, jax.devices()[0])
            except Exception:
                pass
        
        return tensor
    
    def get_all_devices(self) -> List[DeviceInfo]:
        """Get list of all detected devices"""
        return self._detected_devices.copy()
    
    def get_device_report(self) -> Dict[str, Any]:
        """
        Get comprehensive device report for diagnostics.
        
        Returns:
            Dictionary with device information, costs, and routing mode
        """
        device = self.get_device()
        
        return {
            "current_device": {
                "type": device.device_type.value,
                "id": device.device_id,
                "name": device.name,
                "memory_gb": device.memory_gb,
                "available": device.available,
                "cost_per_hour": device.cost_per_hour
            },
            "all_devices": [
                {
                    "type": d.device_type.value,
                    "id": d.device_id,
                    "name": d.name,
                    "memory_gb": d.memory_gb,
                    "available": d.available,
                    "cost_per_hour": d.cost_per_hour
                }
                for d in self._detected_devices
            ],
            "configuration": {
                "prefer": self.prefer.value,
                "allow_tpu": self.allow_tpu,
                "tpu_batch_factor": self.tpu_batch_factor
            },
            "frameworks": {
                "pytorch": self._torch_available,
                "tensorflow": self._tensorflow_available,
                "jax": self._jax_available
            },
            "routing_mode": "auto" if self.prefer == DeviceType.AUTO else "manual"
        }


# Global device manager instance
_device_manager: Optional[DeviceManager] = None


def get_device_manager(
    prefer: str = "auto",
    allow_tpu: bool = True,
    tpu_batch_factor: int = 128,
    config: Optional[Dict[str, Any]] = None
) -> DeviceManager:
    """
    Get or create global DeviceManager instance.
    
    Args:
        prefer: Device preference ("auto", "cpu", "gpu", "tpu")
        allow_tpu: Whether to allow TPU usage
        tpu_batch_factor: Batch size multiplier for TPU
        config: Optional configuration dictionary
    
    Returns:
        DeviceManager instance
    """
    global _device_manager
    
    if _device_manager is None:
        _device_manager = DeviceManager(
            prefer=prefer,
            allow_tpu=allow_tpu,
            tpu_batch_factor=tpu_batch_factor,
            config=config
        )
    
    return _device_manager


def reset_device_manager() -> None:
    """Reset global device manager (useful for testing)"""
    global _device_manager
    _device_manager = None


