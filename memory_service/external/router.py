"""
Hybrid memory router coordinating legacy storage with the NBMF tiers.
"""

from __future__ import annotations

import os
import random
import time
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import nbmf_decoder, nbmf_encoder
from .adapters.l1_embeddings import L1Index
from .adapters.l2_nbmf_store import L2Store
from .adapters.l3_cold_store import L3Store
from .legacy_store import LegacyStore
from .ledger import log_event
from .memory_bootstrap import load_config
from .metrics import incr, observe
from .policy import AccessPolicy
from .quarantine_l2q import L2Quarantine
from .trust_manager import TrustManager
