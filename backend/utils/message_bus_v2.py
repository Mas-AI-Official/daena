"""
Enhanced Message Bus V2 with Topic-Based Pub/Sub for Hex-Mesh Communication.

This implements the brain-like communication pattern with structured topics:
- cell/{dept}/{cell_id}: Local cell communication
- ring/{k}: Ring-level communication (k = ring number)
- radial/{arm}: Radial communication to hub (north/south/east/west)
- global/cmp: Global CMP fallback

Backward compatible with MessageBus V1.

Backpressure: Prevents queue overflow with max_queue_size and queue depth monitoring.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict, deque
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from dataclasses import dataclass

from backend.utils.tracing import get_tracing_service, trace_message_bus

logger = logging.getLogger(__name__)


class TopicType(Enum):
    """Topic type enumeration."""
    CELL = "cell"
    RING = "ring"
    RADIAL = "radial"
    GLOBAL = "global"


@dataclass
class TopicMessage:
    """Message for topic-based pub/sub."""
    id: str
    topic: str
    content: Dict[str, Any]
    sender: str
    timestamp: str = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat() + "Z"
        if self.metadata is None:
            self.metadata = {}


class TopicManager:
    """Manages topic subscriptions and routing."""
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.wildcard_subscribers: Dict[str, List[Callable]] = defaultdict(list)
        
    def subscribe(self, topic_pattern: str, handler: Callable) -> None:
        """
        Subscribe to a topic pattern.
        
        Patterns:
        - Exact: "cell/engineering/A1"
        - Wildcard: "cell/engineering/*" (all agents in engineering)
        - Ring: "ring/1" (all cells in ring 1)
        - Radial: "radial/north" (all cells in north arm)
        """
        if "*" in topic_pattern or "{" in topic_pattern:
            # Wildcard subscription
            pattern_key = topic_pattern.replace("*", "").replace("{", "").replace("}", "")
            self.wildcard_subscribers[pattern_key].append(handler)
        else:
            # Exact subscription
            self.subscribers[topic_pattern].append(handler)
        logger.info(f"Subscribed to topic pattern: {topic_pattern}")
    
    def unsubscribe(self, topic_pattern: str, handler: Callable) -> None:
        """Unsubscribe from a topic pattern."""
        if topic_pattern in self.subscribers:
            if handler in self.subscribers[topic_pattern]:
                self.subscribers[topic_pattern].remove(handler)
        # Also check wildcard
        pattern_key = topic_pattern.replace("*", "").replace("{", "").replace("}", "")
        if pattern_key in self.wildcard_subscribers:
            if handler in self.wildcard_subscribers[pattern_key]:
                self.wildcard_subscribers[pattern_key].remove(handler)
    
    def _match_wildcard(self, topic: str, pattern: str) -> bool:
        """Check if topic matches wildcard pattern."""
        if "*" in pattern:
            prefix = pattern.split("*")[0]
            return topic.startswith(prefix)
        return False
    
    def get_handlers(self, topic: str) -> List[Callable]:
        """Get all handlers for a topic (exact + wildcard matches)."""
        handlers = []
        
        # Exact matches
        if topic in self.subscribers:
            handlers.extend(self.subscribers[topic])
        
        # Wildcard matches
        for pattern_key, pattern_handlers in self.wildcard_subscribers.items():
            if self._match_wildcard(topic, pattern_key + "*"):
                handlers.extend(pattern_handlers)
        
        return handlers


class MessageBusV2:
    """
    Enhanced message bus with topic-based pub/sub and backpressure.
    
    Features:
    - Topic-based routing (cell/ring/radial/global)
    - Backpressure with max_queue_size
    - Queue depth monitoring
    - Message history tracking
    """
    
    def __init__(self, max_queue_size: int = 10000):
        """
        Initialize MessageBus V2.
        
        Args:
            max_queue_size: Maximum queue size before backpressure kicks in
        """
        self.topic_manager = TopicManager()
        self.message_history: deque = deque(maxlen=1000)  # Keep last 1000 messages
        self.max_queue_size = max_queue_size
        self._queue_depth = 0
        self._running = False
        self._stats = {
            "messages_published": 0,
            "messages_delivered": 0,
            "messages_dropped": 0,
            "backpressure_events": 0
        }
    
    async def start(self):
        """Start the message bus."""
        self._running = True
        logger.info(f"MessageBus V2 started (max_queue_size: {self.max_queue_size})")
    
    async def stop(self):
        """Stop the message bus."""
        self._running = False
        logger.info("MessageBus V2 stopped")
    
    def _check_backpressure(self) -> bool:
        """
        Check if backpressure should be applied.
        
        Returns:
            True if queue is at capacity (backpressure needed)
        """
        queue_utilization = self._queue_depth / self.max_queue_size if self.max_queue_size > 0 else 0
        
        if queue_utilization >= 0.9:  # 90% capacity threshold
            self._stats["backpressure_events"] += 1
            logger.warning(f"Backpressure: Queue at {queue_utilization:.1%} capacity ({self._queue_depth}/{self.max_queue_size})")
            return True
        
        return False
    
    async def publish(
        self,
        topic: str,
        content: Dict[str, Any],
        sender: str = "system",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publish a message to a topic.
        
        Args:
            topic: Topic name (e.g., "cell/engineering/A1")
            content: Message content
            sender: Sender identifier
            metadata: Optional metadata
        
        Returns:
            True if published, False if dropped due to backpressure
        """
        if not self._running:
            logger.warning("MessageBus V2 not running, message dropped")
            return False
        
        # Check backpressure
        if self._check_backpressure():
            self._stats["messages_dropped"] += 1
            logger.warning(f"Message dropped due to backpressure: {topic} from {sender}")
            return False
        
        # Create message
        message = TopicMessage(
            id=str(uuid.uuid4()),
            topic=topic,
            content=content,
            sender=sender,
            metadata=metadata or {}
        )
        
        # Add to history
        self.message_history.append(message)
        self._queue_depth += 1
        self._stats["messages_published"] += 1
        
        # Get handlers
        handlers = self.topic_manager.get_handlers(topic)
        
        if not handlers:
            # No subscribers, but message is still published
            logger.debug(f"Message published to {topic} but no subscribers")
            self._queue_depth -= 1
            return True
        
        # Deliver to handlers
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
                self._stats["messages_delivered"] += 1
            except Exception as e:
                logger.error(f"Error delivering message to handler: {e}")
        
        self._queue_depth -= 1
        return True
    
    def subscribe(self, topic_pattern: str, handler: Callable) -> None:
        """Subscribe to a topic pattern."""
        self.topic_manager.subscribe(topic_pattern, handler)
    
    def unsubscribe(self, topic_pattern: str, handler: Callable) -> None:
        """Unsubscribe from a topic pattern."""
        self.topic_manager.unsubscribe(topic_pattern, handler)
    
    async def publish_to_ring(
        self,
        ring_number: int,
        content: Dict[str, Any],
        sender: str = "system",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish to a ring topic."""
        topic = f"ring/{ring_number}"
        return await self.publish(topic, content, sender, metadata)
    
    async def publish_to_radial(
        self,
        arm: str,
        content: Dict[str, Any],
        sender: str = "system",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Publish to a radial topic."""
        topic = f"radial/{arm}"
        return await self.publish(topic, content, sender, metadata)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get message bus statistics."""
        queue_utilization = self._queue_depth / self.max_queue_size if self.max_queue_size > 0 else 0
        
        return {
            "queue_depth": self._queue_depth,
            "max_queue_size": self.max_queue_size,
            "queue_utilization": queue_utilization,
            "backpressure_active": queue_utilization >= 0.9,
            "messages_published": self._stats["messages_published"],
            "messages_delivered": self._stats["messages_delivered"],
            "messages_dropped": self._stats["messages_dropped"],
            "backpressure_events": self._stats["backpressure_events"],
            "history_size": len(self.message_history)
        }


# Global instance
message_bus_v2 = MessageBusV2(max_queue_size=10000)

# Backward compatibility alias
message_bus = message_bus_v2
