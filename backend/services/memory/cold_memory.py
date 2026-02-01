"""
L3 COLD Memory — Summarized Archive Storage

Long-term storage with automatic summarization.
Minimal storage footprint, can reconstruct gist but not exact text.

Part of NBMF (Neural Bytecode Memory Format) architecture.
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import gzip
import hashlib
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ColdMemory:
    """
    L3 COLD tier - Summarized archive storage.
    
    Features:
    - Automatic summarization
    - Maximum compression
    - Reference-based recall (may need external source)
    - Batch pack archiving
    """
    
    def __init__(self):
        self._storage_dir = Path(__file__).parent.parent.parent.parent / ".l3_store"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Index
        self._index_path = self._storage_dir / "cold_index.json"
        self._index: Dict[str, Dict[str, Any]] = {}
        self._load_index()
        
        # Archive packs (multiple items in one file)
        self._current_pack: List[Dict[str, Any]] = []
        self._max_pack_size = 100
    
    def _load_index(self):
        """Load archive index."""
        if self._index_path.exists():
            try:
                with open(self._index_path, "r") as f:
                    self._index = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load COLD index: {e}")
    
    def _save_index(self):
        """Save archive index."""
        try:
            with open(self._index_path, "w") as f:
                json.dump(self._index, f)
        except Exception as e:
            logger.error(f"Failed to save COLD index: {e}")
    
    def store(self, item_id: str, content: str, metadata: Optional[Dict] = None):
        """
        Store content in COLD tier.
        
        Content is summarized and added to current pack.
        """
        # Generate summary
        summary = self._summarize(content)
        
        # Create archive entry
        entry = {
            "item_id": item_id,
            "summary": summary,
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "original_length": len(content),
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        
        # Add to current pack
        self._current_pack.append(entry)
        
        # Update index
        self._index[item_id] = {
            "pack_id": self._get_current_pack_id(),
            "summary": summary[:200],
            "archived_at": entry["archived_at"],
            "original_length": len(content)
        }
        self._save_index()
        
        # Flush pack if full
        if len(self._current_pack) >= self._max_pack_size:
            self._flush_pack()
    
    def _summarize(self, content: str, max_length: int = 500) -> str:
        """
        Summarize content for cold storage.
        
        In production, use LLM for intelligent summarization.
        For now, uses extractive approach.
        """
        # Split into sentences (simplified)
        sentences = []
        current = ""
        for char in content:
            current += char
            if char in ".!?" and len(current) > 10:
                sentences.append(current.strip())
                current = ""
        if current.strip():
            sentences.append(current.strip())
        
        if not sentences:
            return content[:max_length]
        
        # Score sentences by position and keywords
        scored = []
        keywords = {"important", "critical", "key", "main", "summary", "result", "conclusion"}
        
        for i, sentence in enumerate(sentences):
            score = 0
            # Position score (first and last sentences are important)
            if i < 3:
                score += 3 - i
            if i >= len(sentences) - 2:
                score += 1
            # Keyword score
            for kw in keywords:
                if kw in sentence.lower():
                    score += 2
            # Length score (prefer medium-length sentences)
            if 50 < len(sentence) < 200:
                score += 1
            
            scored.append((sentence, score))
        
        # Sort by score and take top sentences
        scored.sort(key=lambda x: x[1], reverse=True)
        
        summary = ""
        for sentence, _ in scored:
            if len(summary) + len(sentence) > max_length:
                break
            summary += sentence + " "
        
        return summary.strip() or content[:max_length]
    
    def _get_current_pack_id(self) -> str:
        """Get current pack ID based on date."""
        return datetime.now(timezone.utc).strftime("pack_%Y%m%d")
    
    def _flush_pack(self):
        """Flush current pack to disk."""
        if not self._current_pack:
            return
        
        pack_id = self._get_current_pack_id()
        pack_path = self._storage_dir / f"{pack_id}.json.gz"
        
        # Append to existing pack or create new
        existing = []
        if pack_path.exists():
            try:
                with gzip.open(pack_path, "rt", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load existing pack: {e}")
        
        existing.extend(self._current_pack)
        
        try:
            with gzip.open(pack_path, "wt", encoding="utf-8") as f:
                json.dump(existing, f)
            logger.info(f"Flushed {len(self._current_pack)} items to {pack_id}")
        except Exception as e:
            logger.error(f"Failed to flush pack: {e}")
        
        self._current_pack = []
    
    def recall(self, item_id: str) -> Optional[str]:
        """
        Recall content from COLD tier.
        
        Returns the summary, not the original content.
        Full content would need to be retrieved from backup/source.
        """
        # First check current pack
        for entry in self._current_pack:
            if entry.get("item_id") == item_id:
                return entry.get("summary", "")
        
        # Check index for pack location
        if item_id not in self._index:
            return None
        
        meta = self._index[item_id]
        pack_id = meta.get("pack_id")
        
        if not pack_id:
            return meta.get("summary")
        
        # Load from pack
        pack_path = self._storage_dir / f"{pack_id}.json.gz"
        if not pack_path.exists():
            return meta.get("summary")
        
        try:
            with gzip.open(pack_path, "rt", encoding="utf-8") as f:
                pack = json.load(f)
            
            for entry in pack:
                if entry.get("item_id") == item_id:
                    return entry.get("summary", "")
                    
        except Exception as e:
            logger.error(f"Failed to recall from pack: {e}")
        
        return meta.get("summary")
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search COLD archive by keywords.
        
        Returns matching items with their summaries.
        """
        query_lower = query.lower()
        results = []
        
        for item_id, meta in self._index.items():
            summary = meta.get("summary", "")
            if query_lower in summary.lower():
                results.append({
                    "item_id": item_id,
                    "summary": summary,
                    "archived_at": meta.get("archived_at"),
                    "original_length": meta.get("original_length", 0)
                })
        
        return results[:20]  # Limit results
    
    def cleanup_old(self, days_old: int = 365) -> int:
        """
        Clean up archives older than specified days.
        
        Returns number of items removed.
        """
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
        cutoff_str = cutoff.isoformat()
        
        removed = 0
        items_to_remove = []
        
        for item_id, meta in self._index.items():
            archived_at = meta.get("archived_at", "")
            if archived_at < cutoff_str:
                items_to_remove.append(item_id)
        
        for item_id in items_to_remove:
            del self._index[item_id]
            removed += 1
        
        self._save_index()
        logger.info(f"Cleaned up {removed} old archive items")
        
        return removed
    
    def flush(self):
        """Force flush current pack."""
        self._flush_pack()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get COLD tier statistics."""
        # Count pack files
        pack_files = list(self._storage_dir.glob("pack_*.json.gz"))
        total_size = sum(f.stat().st_size for f in pack_files)
        
        return {
            "items": len(self._index),
            "pack_files": len(pack_files),
            "total_size_bytes": total_size,
            "current_pack_items": len(self._current_pack),
            "oldest_item": min(
                (m.get("archived_at", "") for m in self._index.values()), 
                default=""
            )
        }
