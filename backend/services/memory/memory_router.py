"""
Memory Router — Policy-Based Routing for NBMF Memory System

Routes data to appropriate memory tier based on classification and policy.
Implements aging, promotion, and demotion between tiers.

Part of Daena's NBMF (Neural Bytecode Memory Format) architecture.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
import json
import yaml
import hashlib

logger = logging.getLogger(__name__)


class DataClass(Enum):
    """Data classification for memory routing"""
    LEGAL = "legal"
    FINANCE = "finance"
    PII = "pii"
    CHAT = "chat"
    OPS_LOG = "ops_log"
    RESEARCH_NOTE = "research_note"
    TRAINING_CHUNK = "training_chunk"
    SKILL = "skill"
    PACKAGE = "package"
    OUTCOME = "outcome"
    THREAT = "threat"
    CONFIG = "config"
    UNKNOWN = "unknown"


class Fidelity(Enum):
    """Reconstruction fidelity modes"""
    LOSSLESS = "lossless"           # Exact reconstruction
    LOSSLESS_EDGE = "lossless_edge"  # Lossless, kept on device
    SEMANTIC = "semantic"           # Meaning-preserving, may change phrasing


class MemoryTier(Enum):
    """Memory storage tiers"""
    HOT = "hot"       # L1 - Vector DB, fast recall
    WARM = "warm"     # L2 - NBMF encoded
    COLD = "cold"     # L3 - Summarized archive


@dataclass
class MemoryPolicy:
    """Policy for a data class"""
    fidelity: Fidelity = Fidelity.SEMANTIC
    retention_days: int = 180
    hot_cache_days: int = 14
    on_device: bool = False
    encrypt: bool = True
    federated: bool = False
    promote_on_access: bool = False


@dataclass
class MemoryItem:
    """An item stored in memory"""
    item_id: str
    data_class: str
    content_hash: str
    tier: str
    fidelity: str
    created_at: str
    last_accessed: str
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    compressed_size: int = 0
    original_size: int = 0


# Default policies per data class
DEFAULT_POLICIES: Dict[str, MemoryPolicy] = {
    DataClass.LEGAL.value: MemoryPolicy(
        fidelity=Fidelity.LOSSLESS,
        retention_days=2555,  # 7 years
        hot_cache_days=30,
        encrypt=True,
        promote_on_access=True
    ),
    DataClass.FINANCE.value: MemoryPolicy(
        fidelity=Fidelity.LOSSLESS,
        retention_days=2555,
        hot_cache_days=30,
        encrypt=True,
        promote_on_access=True
    ),
    DataClass.PII.value: MemoryPolicy(
        fidelity=Fidelity.LOSSLESS_EDGE,
        retention_days=2555,
        on_device=True,
        encrypt=True
    ),
    DataClass.CHAT.value: MemoryPolicy(
        fidelity=Fidelity.SEMANTIC,
        retention_days=180,
        hot_cache_days=14
    ),
    DataClass.OPS_LOG.value: MemoryPolicy(
        fidelity=Fidelity.SEMANTIC,
        retention_days=90
    ),
    DataClass.RESEARCH_NOTE.value: MemoryPolicy(
        fidelity=Fidelity.SEMANTIC,
        retention_days=365,
        hot_cache_days=30
    ),
    DataClass.TRAINING_CHUNK.value: MemoryPolicy(
        fidelity=Fidelity.SEMANTIC,
        retention_days=730,
        federated=True
    ),
    DataClass.SKILL.value: MemoryPolicy(
        fidelity=Fidelity.LOSSLESS,
        retention_days=3650,  # 10 years
        hot_cache_days=90
    ),
    DataClass.OUTCOME.value: MemoryPolicy(
        fidelity=Fidelity.SEMANTIC,
        retention_days=365,
        hot_cache_days=14
    ),
    DataClass.THREAT.value: MemoryPolicy(
        fidelity=Fidelity.LOSSLESS,
        retention_days=1825,  # 5 years
        hot_cache_days=30,
        encrypt=True
    ),
}


class MemoryRouter:
    """
    Routes data to appropriate memory tier based on classification and policy.
    
    Features:
    - Policy-based routing per data class
    - Automatic tier progression (hot → warm → cold)
    - Access-based promotion
    - Time-based demotion (aging)
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        self._policies = dict(DEFAULT_POLICIES)
        self._items: Dict[str, MemoryItem] = {}
        
        # Storage paths
        self._storage_dir = Path(__file__).parent.parent.parent.parent / ".l2_store"
        self._index_path = self._storage_dir / "memory_index.json"
        
        # Load external config if provided
        if config_path and config_path.exists():
            self._load_config(config_path)
        
        # Load index
        self._load_index()
        
        # Initialize tier handlers
        self._hot = None
        self._warm = None
        self._cold = None
    
    def _load_config(self, path: Path):
        """Load memory policy configuration."""
        try:
            with open(path, "r") as f:
                config = yaml.safe_load(f)
            
            for name, policy_data in config.get("classes", {}).items():
                self._policies[name] = MemoryPolicy(
                    fidelity=Fidelity(policy_data.get("fidelity", "semantic")),
                    retention_days=policy_data.get("retention", 180),
                    hot_cache_days=policy_data.get("hot_cache_days", 14),
                    on_device=policy_data.get("on_device", False),
                    encrypt=policy_data.get("encrypt", True),
                    federated=policy_data.get("federated", False),
                    promote_on_access=policy_data.get("promote_on_access", False)
                )
        except Exception as e:
            logger.error(f"Failed to load memory config: {e}")
    
    def _load_index(self):
        """Load memory item index."""
        if self._index_path.exists():
            try:
                with open(self._index_path, "r") as f:
                    data = json.load(f)
                for item_data in data.get("items", []):
                    item = MemoryItem(**item_data)
                    self._items[item.item_id] = item
            except Exception as e:
                logger.error(f"Failed to load memory index: {e}")
    
    def _save_index(self):
        """Save memory item index."""
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        try:
            data = {
                "items": [i.__dict__ for i in self._items.values()],
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            with open(self._index_path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save memory index: {e}")
    
    def get_policy(self, data_class: str) -> MemoryPolicy:
        """Get the policy for a data class."""
        return self._policies.get(data_class, MemoryPolicy())
    
    def route(self, content: str, data_class: str, metadata: Optional[Dict] = None) -> str:
        """
        Route content to appropriate memory tier.
        
        Returns: item_id
        """
        now = datetime.now(timezone.utc).isoformat()
        policy = self.get_policy(data_class)
        
        # Generate content hash and ID
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:32]
        item_id = f"{data_class[:4]}_{content_hash[:12]}"
        
        # Determine initial tier
        if policy.fidelity in [Fidelity.LOSSLESS, Fidelity.LOSSLESS_EDGE]:
            # High-value data starts in HOT and WARM
            initial_tier = MemoryTier.HOT
        else:
            # Semantic data can start in WARM
            initial_tier = MemoryTier.HOT if policy.hot_cache_days > 0 else MemoryTier.WARM
        
        # Create memory item
        item = MemoryItem(
            item_id=item_id,
            data_class=data_class,
            content_hash=content_hash,
            tier=initial_tier.value,
            fidelity=policy.fidelity.value,
            created_at=now,
            last_accessed=now,
            access_count=1,
            metadata=metadata or {},
            original_size=len(content.encode())
        )
        
        # Store in appropriate tier
        self._store_to_tier(item, content, policy)
        
        # Update index
        self._items[item_id] = item
        self._save_index()
        
        return item_id
    
    def _store_to_tier(self, item: MemoryItem, content: str, policy: MemoryPolicy):
        """Store content in the appropriate tier."""
        tier = MemoryTier(item.tier)
        
        if tier == MemoryTier.HOT:
            self._store_hot(item, content, policy)
        elif tier == MemoryTier.WARM:
            self._store_warm(item, content, policy)
        else:
            self._store_cold(item, content, policy)
    
    def _store_hot(self, item: MemoryItem, content: str, policy: MemoryPolicy):
        """Store in L1 HOT tier (vector DB)."""
        try:
            from .hot_memory import HotMemory
            if self._hot is None:
                self._hot = HotMemory()
            self._hot.store(item.item_id, content, item.metadata)
            logger.debug(f"Stored {item.item_id} in HOT tier")
        except ImportError:
            # Fallback: store in warm tier
            self._store_warm(item, content, policy)
    
    def _store_warm(self, item: MemoryItem, content: str, policy: MemoryPolicy):
        """Store in L2 WARM tier (NBMF encoded)."""
        try:
            from .warm_memory import WarmMemory
            if self._warm is None:
                self._warm = WarmMemory()
            compressed = self._warm.store(
                item.item_id, 
                content, 
                policy.fidelity == Fidelity.LOSSLESS,
                policy.encrypt
            )
            item.compressed_size = compressed
            item.tier = MemoryTier.WARM.value
            logger.debug(f"Stored {item.item_id} in WARM tier ({compressed} bytes)")
        except ImportError:
            # Fallback: store raw
            self._store_raw(item, content)
    
    def _store_cold(self, item: MemoryItem, content: str, policy: MemoryPolicy):
        """Store in L3 COLD tier (summarized archive)."""
        try:
            from .cold_memory import ColdMemory
            if self._cold is None:
                self._cold = ColdMemory()
            self._cold.store(item.item_id, content, item.metadata)
            item.tier = MemoryTier.COLD.value
            logger.debug(f"Stored {item.item_id} in COLD tier")
        except ImportError:
            # Fallback: store raw
            self._store_raw(item, content)
    
    def _store_raw(self, item: MemoryItem, content: str):
        """Fallback raw storage."""
        path = self._storage_dir / f"{item.item_id}.json"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"content": content, "item": item.__dict__}, f)
    
    def recall(self, item_id: str) -> Optional[str]:
        """
        Recall content from memory.
        
        Automatically promotes frequently accessed items.
        """
        if item_id not in self._items:
            return None
        
        item = self._items[item_id]
        item.last_accessed = datetime.now(timezone.utc).isoformat()
        item.access_count += 1
        
        # Check for promotion
        policy = self.get_policy(item.data_class)
        if policy.promote_on_access and item.tier != MemoryTier.HOT.value:
            self._promote(item)
        
        # Recall from appropriate tier
        tier = MemoryTier(item.tier)
        content = None
        
        if tier == MemoryTier.HOT:
            content = self._recall_hot(item_id)
        elif tier == MemoryTier.WARM:
            content = self._recall_warm(item_id)
        else:
            content = self._recall_cold(item_id)
        
        if content is None:
            # Try fallback raw
            content = self._recall_raw(item_id)
        
        self._save_index()
        return content
    
    def _recall_hot(self, item_id: str) -> Optional[str]:
        """Recall from HOT tier."""
        try:
            from .hot_memory import HotMemory
            if self._hot is None:
                self._hot = HotMemory()
            return self._hot.recall(item_id)
        except ImportError:
            return None
    
    def _recall_warm(self, item_id: str) -> Optional[str]:
        """Recall from WARM tier."""
        try:
            from .warm_memory import WarmMemory
            if self._warm is None:
                self._warm = WarmMemory()
            return self._warm.recall(item_id)
        except ImportError:
            return None
    
    def _recall_cold(self, item_id: str) -> Optional[str]:
        """Recall from COLD tier."""
        try:
            from .cold_memory import ColdMemory
            if self._cold is None:
                self._cold = ColdMemory()
            return self._cold.recall(item_id)
        except ImportError:
            return None
    
    def _recall_raw(self, item_id: str) -> Optional[str]:
        """Fallback raw recall."""
        path = self._storage_dir / f"{item_id}.json"
        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
                return data.get("content")
        return None
    
    def _promote(self, item: MemoryItem):
        """Promote item to higher tier."""
        current = MemoryTier(item.tier)
        
        if current == MemoryTier.COLD:
            # Cold → Warm (re-encode)
            content = self._recall_cold(item.item_id)
            if content:
                item.tier = MemoryTier.WARM.value
                self._store_warm(item, content, self.get_policy(item.data_class))
                logger.info(f"Promoted {item.item_id} COLD → WARM")
        elif current == MemoryTier.WARM:
            # Warm → Hot (add to vector cache)
            content = self._recall_warm(item.item_id)
            if content:
                item.tier = MemoryTier.HOT.value
                self._store_hot(item, content, self.get_policy(item.data_class))
                logger.info(f"Promoted {item.item_id} WARM → HOT")
    
    def run_aging(self):
        """
        Run aging process to demote old items.
        
        Should be called periodically (e.g., daily).
        """
        now = datetime.now(timezone.utc)
        demoted = 0
        
        for item in self._items.values():
            policy = self.get_policy(item.data_class)
            last_accessed = datetime.fromisoformat(item.last_accessed.replace("Z", "+00:00"))
            age_days = (now - last_accessed).days
            
            current = MemoryTier(item.tier)
            
            # Check for demotion
            if current == MemoryTier.HOT and age_days > policy.hot_cache_days:
                # Hot → Warm
                content = self._recall_hot(item.item_id)
                if content:
                    item.tier = MemoryTier.WARM.value
                    self._store_warm(item, content, policy)
                    demoted += 1
                    logger.info(f"Demoted {item.item_id} HOT → WARM (age: {age_days}d)")
            
            elif current == MemoryTier.WARM and age_days > 90:
                # Warm → Cold (summarize)
                content = self._recall_warm(item.item_id)
                if content:
                    item.tier = MemoryTier.COLD.value
                    self._store_cold(item, content, policy)
                    demoted += 1
                    logger.info(f"Demoted {item.item_id} WARM → COLD (age: {age_days}d)")
        
        self._save_index()
        return demoted
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        by_tier = {"hot": 0, "warm": 0, "cold": 0}
        by_class = {}
        total_original = 0
        total_compressed = 0
        
        for item in self._items.values():
            by_tier[item.tier] = by_tier.get(item.tier, 0) + 1
            by_class[item.data_class] = by_class.get(item.data_class, 0) + 1
            total_original += item.original_size
            total_compressed += item.compressed_size
        
        compression_ratio = (
            total_original / total_compressed if total_compressed > 0 else 0
        )
        
        return {
            "total_items": len(self._items),
            "by_tier": by_tier,
            "by_class": by_class,
            "total_original_bytes": total_original,
            "total_compressed_bytes": total_compressed,
            "compression_ratio": round(compression_ratio, 2)
        }


# Singleton
_router: Optional[MemoryRouter] = None


def get_memory_router() -> MemoryRouter:
    """Get the global memory router instance."""
    global _router
    if _router is None:
        _router = MemoryRouter()
    return _router
