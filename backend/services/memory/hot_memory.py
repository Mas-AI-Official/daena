"""
L1 HOT Memory — Fast Vector Cache

High-speed in-memory cache for recently accessed data.
Target: p95 < 25ms recall time.

Part of NBMF (Neural Bytecode Memory Format) architecture.
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import hashlib
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class HotMemory:
    """
    L1 HOT tier - Vector database cache for fast recall.
    
    In production, this would connect to:
    - Qdrant
    - Pinecone
    - Weaviate
    - Milvus
    
    For now, uses a simple in-memory cache with disk persistence.
    """
    
    def __init__(self, max_items: int = 10000):
        self.max_items = max_items
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._embeddings: Dict[str, List[float]] = {}
        
        # Persistence
        self._storage_path = Path(__file__).parent.parent.parent.parent / ".l2_store" / "hot_cache.json"
        self._load()
    
    def _load(self):
        """Load cache from disk."""
        if self._storage_path.exists():
            try:
                with open(self._storage_path, "r") as f:
                    data = json.load(f)
                self._cache = data.get("cache", {})
                logger.info(f"Loaded {len(self._cache)} items into HOT cache")
            except Exception as e:
                logger.error(f"Failed to load HOT cache: {e}")
    
    def _save(self):
        """Save cache to disk."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._storage_path, "w") as f:
                json.dump({
                    "cache": self._cache,
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }, f)
        except Exception as e:
            logger.error(f"Failed to save HOT cache: {e}")
    
    def store(self, item_id: str, content: str, metadata: Optional[Dict] = None) -> bool:
        """
        Store content in HOT cache.
        
        Returns True if successfully stored.
        """
        # Evict if at capacity
        if len(self._cache) >= self.max_items:
            self._evict_lru()
        
        # Store content
        self._cache[item_id] = {
            "content": content,
            "metadata": metadata or {},
            "stored_at": datetime.now(timezone.utc).isoformat(),
            "access_count": 1
        }
        
        # Generate embedding (simplified - in production use real embedding model)
        embedding = self._generate_embedding(content)
        self._embeddings[item_id] = embedding
        
        self._save()
        return True
    
    def recall(self, item_id: str) -> Optional[str]:
        """Recall content from HOT cache."""
        if item_id not in self._cache:
            return None
        
        item = self._cache[item_id]
        item["access_count"] = item.get("access_count", 0) + 1
        item["last_accessed"] = datetime.now(timezone.utc).isoformat()
        
        return item.get("content")
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Semantic search across HOT cache.
        
        Uses cosine similarity on embeddings.
        """
        if not self._cache:
            return []
        
        # Generate query embedding
        query_embedding = self._generate_embedding(query)
        
        # Calculate similarities
        similarities = []
        for item_id, embedding in self._embeddings.items():
            sim = self._cosine_similarity(query_embedding, embedding)
            similarities.append((item_id, sim))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Return top_k results
        results = []
        for item_id, sim in similarities[:top_k]:
            if item_id in self._cache:
                results.append({
                    "item_id": item_id,
                    "similarity": sim,
                    "content": self._cache[item_id].get("content", "")[:200],
                    "metadata": self._cache[item_id].get("metadata", {})
                })
        
        return results
    
    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.
        
        In production, use:
        - OpenAI embeddings
        - Sentence transformers
        - Ollama embeddings
        
        For now, use a simple hash-based pseudo-embedding.
        """
        # Simple 128-dim pseudo-embedding based on character frequencies
        embedding = [0.0] * 128
        text_lower = text.lower()
        
        for i, char in enumerate(text_lower):
            if i >= 128:
                break
            embedding[i % 128] += ord(char) / 256.0
        
        # Normalize
        magnitude = sum(x*x for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]
        
        return embedding
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        
        dot_product = sum(x*y for x, y in zip(a, b))
        mag_a = sum(x*x for x in a) ** 0.5
        mag_b = sum(x*x for x in b) ** 0.5
        
        if mag_a == 0 or mag_b == 0:
            return 0.0
        
        return dot_product / (mag_a * mag_b)
    
    def _evict_lru(self):
        """Evict least recently used items."""
        if not self._cache:
            return
        
        # Sort by last access time
        sorted_items = sorted(
            self._cache.items(),
            key=lambda x: x[1].get("last_accessed", x[1].get("stored_at", ""))
        )
        
        # Remove oldest 10%
        evict_count = max(1, len(self._cache) // 10)
        for item_id, _ in sorted_items[:evict_count]:
            del self._cache[item_id]
            if item_id in self._embeddings:
                del self._embeddings[item_id]
        
        logger.info(f"Evicted {evict_count} items from HOT cache")
    
    def delete(self, item_id: str) -> bool:
        """Delete an item from cache."""
        if item_id in self._cache:
            del self._cache[item_id]
            if item_id in self._embeddings:
                del self._embeddings[item_id]
            self._save()
            return True
        return False
    
    def clear(self):
        """Clear all items from cache."""
        self._cache.clear()
        self._embeddings.clear()
        self._save()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "items": len(self._cache),
            "max_items": self.max_items,
            "utilization": len(self._cache) / self.max_items if self.max_items > 0 else 0,
            "embeddings": len(self._embeddings)
        }
