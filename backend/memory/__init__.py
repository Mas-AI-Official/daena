"""
Daena Unified Memory System
===========================

Consolidated storage layer handling:
- L1: Hot memory (Vector DB)
- L2: Warm memory (NBMF) - Primary
- L3: Cold memory (Archives)
- CAS: Content-Addressable Storage (Deduplication)

Usage:
    from backend.memory import memory, MemoryManager
    
    memory.write("key123", "financial_report", {"revenue": 1000})
    data = memory.read("key123", "financial_report")
"""

from typing import Any, Dict, List, Optional
import logging

from .config import settings
from .cas_engine import CAS
from .l1_hot import L1Index
from .l2_warm import L2Store
from .l3_cold import L3Store
from .simhash import near_duplicate

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    Unified entry point for memory operations.
    Orchestrates L1/L2/L3 tiers and CAS.
    """
    
    def __init__(self):
        self.l1 = L1Index()
        self.l2 = L2Store()
        self.l3 = L3Store()
        self.cas = CAS(settings.CAS_ROOT) if settings.CAS_ENABLED else None
        
    def write(self, key: str, cls: str, payload: Any, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Write data to memory.
        Strategy: Write to L2 (Primary) and index in L1.
        """
        meta = meta or {}
        
        # 1. Write to L2 (Primary NBMF Store)
        l2_txid = self.l2.put_record(key, cls, payload, meta)
        
        # 2. Index in L1 (Hot Vector Store)
        self.l1.index(key, payload, meta)
        
        return {
            "status": "ok",
            "key": key,
            "cls": cls,
            "l2_txid": l2_txid
        }
        
    def read(self, key: str, cls: str) -> Optional[Any]:
        """
        Read data from memory.
        Strategy: L2 -> L3 -> None.
        """
        # 1. Try L2 (Warm)
        full_record = self.l2.get_full_record(key, cls)
        
        # 2. Try L3 (Cold) if not in L2
        if not full_record:
            full_record = self.l3.get_full_record(key, cls)
            if full_record:
                # Promote to L2? (Logic can go here)
                pass
                
        if full_record:
            return full_record.get("payload")
            
        return None
        
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Semantic search across memory.
        Strategy: Search L1 keys -> Fetch L2 payloads.
        """
        results = []
        keys = self.l1.search(query, top_k)
        
        for key in keys:
            # Check L2 first
            # Note: L1 might not store class, so we might need to guess or search all classes
            # For this simple implementation, we assume L1 stores meta with class
            l1_meta = self.l1.meta(key)
            cls = l1_meta.get("cls", "general") # Default class
            
            payload = self.read(key, cls)
            if payload:
                results.append({
                    "key": key,
                    "cls": cls,
                    "payload": payload,
                    "score": 1.0 # Mock score
                })
                
        return results

# Singleton instance
memory = MemoryManager()
