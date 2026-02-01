"""
Unified Memory System for Daena

This is the SINGLE API that all Daena memory operations go through.
It unifies:
- .dna_storage/ (persistent memory)
- .cas/ (content-addressed storage / deduplication)
- .ledger/ (trust ledger, outcomes)

Benefits:
- CAS deduplication saves API costs
- Consistent interface for all agents
- Semantic search across all memory
- Insight extraction from patterns
"""

import os
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Storage paths (relative to project root)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DNA_STORAGE = PROJECT_ROOT / ".dna_storage"
CAS_STORAGE = PROJECT_ROOT / ".cas"
LEDGER_STORAGE = PROJECT_ROOT / ".ledger"
INSIGHTS_STORAGE = DNA_STORAGE / "insights"
CALIBRATION_STORAGE = DNA_STORAGE / "calibration"


@dataclass
class MemoryEntry:
    """A single memory entry with metadata."""
    key: str
    value: Any
    category: str
    content_hash: str
    created_at: str
    updated_at: str
    ttl: Optional[int] = None  # Time to live in seconds
    access_count: int = 0
    last_accessed_at: Optional[str] = None


class UnifiedMemory:
    """
    The ONE public API for all memory operations in Daena.
    
    Usage:
        memory = get_unified_memory()
        memory.store("user_preference_theme", "dark", "preferences")
        value = memory.retrieve("user_preference_theme")
        results = memory.search("user preferences", top_k=5)
    """
    
    def __init__(self):
        self._ensure_dirs()
        self._index: Dict[str, MemoryEntry] = {}
        self._cas_index: Dict[str, str] = {}  # content_hash → key
        self._load_index()
        self._stats = {
            "total_stores": 0,
            "total_retrieves": 0,
            "cas_hits": 0,
            "cas_saves": 0
        }
    
    def _ensure_dirs(self):
        """Ensure storage directories exist."""
        for dir_path in [DNA_STORAGE, CAS_STORAGE, LEDGER_STORAGE, 
                        INSIGHTS_STORAGE, CALIBRATION_STORAGE]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _load_index(self):
        """Load the memory index from disk."""
        index_file = DNA_STORAGE / "memory_index.json"
        if index_file.exists():
            try:
                with open(index_file, "r") as f:
                    data = json.load(f)
                    for key, entry_data in data.items():
                        self._index[key] = MemoryEntry(**entry_data)
            except Exception as e:
                logger.error(f"Failed to load memory index: {e}")
    
    def _save_index(self):
        """Save the memory index to disk."""
        index_file = DNA_STORAGE / "memory_index.json"
        try:
            data = {k: asdict(v) for k, v in self._index.items()}
            with open(index_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save memory index: {e}")
    
    def _compute_hash(self, value: Any) -> str:
        """Compute content hash for deduplication."""
        content = json.dumps(value, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    # ============================================
    # PUBLIC API
    # ============================================
    
    def store(self, key: str, value: Any, category: str = "general", 
              ttl: Optional[int] = None) -> Dict[str, Any]:
        """
        Store a value in unified memory.
        
        Uses CAS for deduplication — if the exact same content exists,
        we don't duplicate storage.
        
        Args:
            key: Unique identifier for this memory
            value: The data to store (any JSON-serializable value)
            category: Category for organization (preferences, insights, context, etc.)
            ttl: Optional time-to-live in seconds
        
        Returns:
            Result with status and CAS info
        """
        now = datetime.now(timezone.utc).isoformat()
        content_hash = self._compute_hash(value)
        
        self._stats["total_stores"] += 1
        
        # Check for CAS hit
        was_deduplicated = False
        if content_hash in self._cas_index:
            existing_key = self._cas_index[content_hash]
            if existing_key != key:
                was_deduplicated = True
                self._stats["cas_hits"] += 1
                logger.debug(f"CAS hit: {key} duplicates {existing_key}")
        
        # Store content in CAS
        cas_file = CAS_STORAGE / f"{content_hash}.json"
        if not cas_file.exists():
            with open(cas_file, "w") as f:
                json.dump(value, f, indent=2, default=str)
            self._stats["cas_saves"] += 1
        
        # Update index
        existing = self._index.get(key)
        entry = MemoryEntry(
            key=key,
            value=value,
            category=category,
            content_hash=content_hash,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            ttl=ttl,
            access_count=existing.access_count if existing else 0
        )
        self._index[key] = entry
        self._cas_index[content_hash] = key
        
        # Also store in category-specific file
        self._store_by_category(category, key, value)
        
        self._save_index()
        
        return {
            "key": key,
            "content_hash": content_hash,
            "category": category,
            "deduplicated": was_deduplicated,
            "stored_at": now
        }
    
    def retrieve(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from unified memory.
        
        Returns None if not found or expired.
        """
        entry = self._index.get(key)
        if not entry:
            return None
        
        # Check TTL expiration
        if entry.ttl:
            created = datetime.fromisoformat(entry.created_at.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            age_seconds = (now - created).total_seconds()
            if age_seconds > entry.ttl:
                # Expired
                self.delete(key)
                return None
        
        # Update access stats
        entry.access_count += 1
        entry.last_accessed_at = datetime.now(timezone.utc).isoformat()
        self._stats["total_retrieves"] += 1
        
        # Retrieve from CAS
        cas_file = CAS_STORAGE / f"{entry.content_hash}.json"
        if cas_file.exists():
            with open(cas_file, "r") as f:
                return json.load(f)
        
        # Fallback to inline value
        return entry.value
    
    def delete(self, key: str) -> bool:
        """Delete a memory entry."""
        if key in self._index:
            entry = self._index.pop(key)
            # Note: CAS content is NOT deleted (might be used by other keys)
            self._save_index()
            return True
        return False
    
    def search(self, query: str, top_k: int = 5, 
               category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search across all memory using semantic matching.
        
        Currently uses simple substring matching.
        TODO: Integrate with embeddings for true semantic search.
        """
        results = []
        query_lower = query.lower()
        
        for key, entry in self._index.items():
            if category and entry.category != category:
                continue
            
            # Simple substring matching on key and value
            score = 0
            if query_lower in key.lower():
                score += 10
            
            value_str = json.dumps(entry.value, default=str).lower()
            if query_lower in value_str:
                score += 5
            
            if entry.category and query_lower in entry.category.lower():
                score += 3
            
            if score > 0:
                results.append({
                    "key": key,
                    "value": entry.value,
                    "category": entry.category,
                    "score": score,
                    "created_at": entry.created_at,
                    "access_count": entry.access_count
                })
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def get_insights(self, topic: str) -> List[Dict[str, Any]]:
        """
        Get consolidated insights for a topic.
        
        Insights are generated by the memory consolidation process.
        """
        insights_file = INSIGHTS_STORAGE / f"{topic}.json"
        if insights_file.exists():
            with open(insights_file, "r") as f:
                return json.load(f)
        return []
    
    def store_insight(self, topic: str, insight: str, 
                      source: str = "learning_loop") -> Dict[str, Any]:
        """Store a new insight for a topic."""
        insights_file = INSIGHTS_STORAGE / f"{topic}.json"
        
        insights = []
        if insights_file.exists():
            with open(insights_file, "r") as f:
                insights = json.load(f)
        
        now = datetime.now(timezone.utc).isoformat()
        new_insight = {
            "insight": insight,
            "source": source,
            "created_at": now
        }
        insights.append(new_insight)
        
        with open(insights_file, "w") as f:
            json.dump(insights, f, indent=2)
        
        return {"topic": topic, "insight_count": len(insights)}
    
    def get_calibration(self, council: str, expert: str) -> Dict[str, Any]:
        """
        Get expert calibration scores.
        
        Calibration tracks how accurate each expert has been on different topics.
        """
        calibration_file = CALIBRATION_STORAGE / council / f"{expert}.json"
        if calibration_file.exists():
            with open(calibration_file, "r") as f:
                return json.load(f)
        
        # Default calibration for new expert
        return {
            "expert_id": expert,
            "council": council,
            "overall_accuracy": 0.5,
            "by_topic": {},
            "total_decisions": 0,
            "correct_decisions": 0
        }
    
    def update_calibration(self, council: str, expert: str, topic: str,
                          was_correct: bool) -> Dict[str, Any]:
        """Update expert calibration based on outcome."""
        cal = self.get_calibration(council, expert)
        
        cal["total_decisions"] = cal.get("total_decisions", 0) + 1
        if was_correct:
            cal["correct_decisions"] = cal.get("correct_decisions", 0) + 1
        
        # Update overall accuracy
        if cal["total_decisions"] > 0:
            cal["overall_accuracy"] = cal["correct_decisions"] / cal["total_decisions"]
        
        # Update topic-specific accuracy
        if topic not in cal["by_topic"]:
            cal["by_topic"][topic] = {"total": 0, "correct": 0, "accuracy": 0.5}
        
        cal["by_topic"][topic]["total"] += 1
        if was_correct:
            cal["by_topic"][topic]["correct"] += 1
        
        topic_data = cal["by_topic"][topic]
        topic_data["accuracy"] = topic_data["correct"] / topic_data["total"]
        
        # Save
        calibration_dir = CALIBRATION_STORAGE / council
        calibration_dir.mkdir(parents=True, exist_ok=True)
        calibration_file = calibration_dir / f"{expert}.json"
        
        with open(calibration_file, "w") as f:
            json.dump(cal, f, indent=2)
        
        return cal
    
    def list_by_category(self, category: str) -> List[Dict[str, Any]]:
        """List all memories in a category."""
        results = []
        for key, entry in self._index.items():
            if entry.category == category:
                results.append({
                    "key": key,
                    "content_hash": entry.content_hash,
                    "created_at": entry.created_at,
                    "access_count": entry.access_count
                })
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        # Count CAS files
        cas_files = list(CAS_STORAGE.glob("*.json"))
        
        # Estimate storage savings
        total_refs = len(self._index)
        unique_content = len(cas_files)
        savings_percent = ((total_refs - unique_content) / max(total_refs, 1)) * 100
        
        return {
            "total_memories": len(self._index),
            "unique_content_blocks": unique_content,
            "deduplication_savings_percent": round(savings_percent, 2),
            "total_stores": self._stats["total_stores"],
            "total_retrieves": self._stats["total_retrieves"],
            "cas_hits": self._stats["cas_hits"],
            "cas_saves": self._stats["cas_saves"],
            "by_category": self._count_by_category()
        }
    
    def _count_by_category(self) -> Dict[str, int]:
        """Count memories by category."""
        counts = {}
        for entry in self._index.values():
            cat = entry.category or "uncategorized"
            counts[cat] = counts.get(cat, 0) + 1
        return counts
    
    def _store_by_category(self, category: str, key: str, value: Any):
        """Store in category-specific index for fast lookup."""
        category_file = DNA_STORAGE / f"category_{category}.json"
        
        data = {}
        if category_file.exists():
            try:
                with open(category_file, "r") as f:
                    data = json.load(f)
            except:
                pass
        
        data[key] = {
            "stored_at": datetime.now(timezone.utc).isoformat(),
            "preview": str(value)[:100] if value else None
        }
        
        with open(category_file, "w") as f:
            json.dump(data, f, indent=2)


# ============================================
# SINGLETON
# ============================================

_memory: Optional[UnifiedMemory] = None


def get_unified_memory() -> UnifiedMemory:
    """Get the global unified memory instance."""
    global _memory
    if _memory is None:
        _memory = UnifiedMemory()
    return _memory
