"""
Configuration for Daena Memory System.
"""
import os
from pathlib import Path
from dataclasses import dataclass
from pathlib import Path
import os

@dataclass
class MemorySettings:
    # Storage Paths
    MEMORY_ROOT: Path = Path("local_brain/memory")
    CAS_ROOT: Path = Path("local_brain/cas")
    L1_PATH: Path = Path("local_brain/l1_hot")
    L2_PATH: Path = Path("local_brain/l2_warm")
    L3_PATH: Path = Path("local_brain/l3_cold")
    
    # Performance
    CAS_ENABLED: bool = True
    SIMHASH_BITS: int = 64
    SIMHASH_THRESHOLD: int = 10
    
    # NBMF Settings
    NBMF_COMPRESSION_TARGET: float = 0.4  # Target 40% of original size

    def __post_init__(self):
        # Allow env overrides
        if os.getenv("DAENA_MEMORY_ROOT"):
            self.MEMORY_ROOT = Path(os.getenv("DAENA_MEMORY_ROOT"))

settings = MemorySettings()

# Ensure directories exist
for path in [settings.MEMORY_ROOT, settings.CAS_ROOT, settings.L1_PATH, settings.L2_PATH, settings.L3_PATH]:
    path.mkdir(parents=True, exist_ok=True)
