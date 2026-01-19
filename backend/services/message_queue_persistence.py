"""
Message Queue Persistence Layer for Daena AI.

Provides reliable message delivery with:
- Redis/RabbitMQ integration (optional)
- In-memory fallback for development
- Message persistence
- Retry logic
- Dead letter queue
"""

from __future__ import annotations

import json
import time
import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class MessageStatus(Enum):
    """Message status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass
class PersistentMessage:
    """Persistent message with metadata."""
    id: str
    topic: str
    content: Dict[str, Any]
    sender: str
    timestamp: float
    status: MessageStatus
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["status"] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PersistentMessage:
        """Create from dictionary."""
        data["status"] = MessageStatus(data["status"])
        return cls(**data)


class MessageQueuePersistence:
    """
    Persistent message queue with retry logic and dead letter queue.
    
    Supports:
    - Redis (optional)
    - RabbitMQ (optional)
    - In-memory fallback
    """
    
    def __init__(
        self,
        use_redis: bool = False,
        use_rabbitmq: bool = False,
        redis_url: Optional[str] = None,
        rabbitmq_url: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        self.use_redis = use_redis
        self.use_rabbitmq = use_rabbitmq
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # In-memory storage (fallback)
        self.messages: Dict[str, PersistentMessage] = {}
        self.pending_queue: deque = deque()
        self.dead_letter_queue: deque = deque(maxlen=1000)
        
        # Redis client (optional)
        self.redis_client = None
        if use_redis:
            self._init_redis(redis_url)
        
        # RabbitMQ connection (optional)
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None
        if use_rabbitmq:
            self._init_rabbitmq(rabbitmq_url)
        
        # Message handlers
        self.handlers: Dict[str, List[Callable]] = {}
        
        # Background task
        self._running = False
        self._retry_task = None
    
    def _init_redis(self, redis_url: Optional[str]):
        """Initialize Redis client."""
        try:
            import redis.asyncio as redis
            self.redis_client = redis.from_url(redis_url or "redis://localhost:6379/0")
            logger.info("Redis client initialized")
        except ImportError:
            logger.warning("Redis not available, using in-memory storage")
            self.use_redis = False
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            self.use_redis = False
    
    def _init_rabbitmq(self, rabbitmq_url: Optional[str]):
        """Initialize RabbitMQ connection."""
        try:
            import aio_pika
            # Will be initialized async
            self.rabbitmq_url = rabbitmq_url or "amqp://guest:guest@localhost/"
            logger.info("RabbitMQ URL configured")
        except ImportError:
            logger.warning("RabbitMQ not available, using in-memory storage")
            self.use_rabbitmq = False
        except Exception as e:
            logger.error(f"Failed to configure RabbitMQ: {e}")
            self.use_rabbitmq = False
    
    async def start(self):
        """Start the persistence layer."""
        self._running = True
        
        if self.use_rabbitmq:
            await self._start_rabbitmq()
        
        # Start retry task
        self._retry_task = asyncio.create_task(self._retry_failed_messages())
        logger.info("Message queue persistence started")
    
    async def stop(self):
        """Stop the persistence layer."""
        self._running = False
        
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass
        
        if self.redis_client:
            await self.redis_client.close()
        
        if self.rabbitmq_connection:
            await self.rabbitmq_connection.close()
        
        logger.info("Message queue persistence stopped")
    
    async def _start_rabbitmq(self):
        """Start RabbitMQ connection."""
        try:
            import aio_pika
            self.rabbitmq_connection = await aio_pika.connect_robust(self.rabbitmq_url)
            self.rabbitmq_channel = await self.rabbitmq_connection.channel()
            logger.info("RabbitMQ connection established")
        except Exception as e:
            logger.error(f"Failed to start RabbitMQ: {e}")
            self.use_rabbitmq = False
    
    async def enqueue(
        self,
        topic: str,
        content: Dict[str, Any],
        sender: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Enqueue a message for persistent delivery."""
        message_id = f"{topic}_{int(time.time() * 1000)}_{id(content)}"
        
        message = PersistentMessage(
            id=message_id,
            topic=topic,
            content=content,
            sender=sender,
            timestamp=time.time(),
            status=MessageStatus.PENDING,
            max_retries=self.max_retries,
            metadata=metadata or {}
        )
        
        # Store in appropriate backend
        if self.use_redis:
            await self._enqueue_redis(message)
        elif self.use_rabbitmq:
            await self._enqueue_rabbitmq(message)
        else:
            await self._enqueue_memory(message)
        
        return message_id
    
    async def _enqueue_redis(self, message: PersistentMessage):
        """Enqueue to Redis."""
        try:
            key = f"mq:pending:{message.topic}"
            await self.redis_client.lpush(key, json.dumps(message.to_dict()))
            await self.redis_client.set(f"mq:message:{message.id}", json.dumps(message.to_dict()))
        except Exception as e:
            logger.error(f"Failed to enqueue to Redis: {e}")
            await self._enqueue_memory(message)  # Fallback
    
    async def _enqueue_rabbitmq(self, message: PersistentMessage):
        """Enqueue to RabbitMQ."""
        try:
            exchange = await self.rabbitmq_channel.declare_exchange(
                message.topic,
                aio_pika.ExchangeType.TOPIC
            )
            await exchange.publish(
                aio_pika.Message(
                    json.dumps(message.to_dict()).encode(),
                    message_id=message.id,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=message.topic
            )
        except Exception as e:
            logger.error(f"Failed to enqueue to RabbitMQ: {e}")
            await self._enqueue_memory(message)  # Fallback
    
    async def _enqueue_memory(self, message: PersistentMessage):
        """Enqueue to in-memory storage."""
        self.messages[message.id] = message
        self.pending_queue.append(message.id)
    
    async def dequeue(self, topic: str, timeout: float = 1.0) -> Optional[PersistentMessage]:
        """Dequeue a message from the queue."""
        if self.use_redis:
            return await self._dequeue_redis(topic, timeout)
        elif self.use_rabbitmq:
            return await self._dequeue_rabbitmq(topic, timeout)
        else:
            return await self._dequeue_memory(topic)
    
    async def _dequeue_redis(self, topic: str, timeout: float) -> Optional[PersistentMessage]:
        """Dequeue from Redis."""
        try:
            key = f"mq:pending:{topic}"
            result = await self.redis_client.brpop(key, timeout=int(timeout))
            if result:
                _, data = result
                message_data = json.loads(data)
                return PersistentMessage.from_dict(message_data)
        except Exception as e:
            logger.error(f"Failed to dequeue from Redis: {e}")
        return None
    
    async def _dequeue_rabbitmq(self, topic: str, timeout: float) -> Optional[PersistentMessage]:
        """Dequeue from RabbitMQ."""
        try:
            queue = await self.rabbitmq_channel.declare_queue(topic, durable=True)
            message = await queue.get(timeout=timeout)
            if message:
                data = json.loads(message.body)
                await message.ack()
                return PersistentMessage.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to dequeue from RabbitMQ: {e}")
        return None
    
    async def _dequeue_memory(self, topic: str) -> Optional[PersistentMessage]:
        """Dequeue from in-memory storage."""
        # Find first message for this topic
        for msg_id in list(self.pending_queue):
            message = self.messages.get(msg_id)
            if message and message.topic == topic and message.status == MessageStatus.PENDING:
                message.status = MessageStatus.PROCESSING
                self.pending_queue.remove(msg_id)
                return message
        return None
    
    async def acknowledge(self, message_id: str):
        """Acknowledge successful processing of a message."""
        message = self.messages.get(message_id)
        if message:
            message.status = MessageStatus.COMPLETED
            
            if self.use_redis:
                await self.redis_client.delete(f"mq:message:{message_id}")
            elif self.use_rabbitmq:
                # Already acknowledged in dequeue
                pass
    
    async def fail(self, message_id: str, error: str):
        """Mark a message as failed and schedule retry."""
        message = self.messages.get(message_id)
        if message:
            message.status = MessageStatus.FAILED
            message.retry_count += 1
            message.last_error = error
            
            if message.retry_count >= message.max_retries:
                message.status = MessageStatus.DEAD_LETTER
                self.dead_letter_queue.append(message)
                logger.warning(f"Message {message_id} moved to dead letter queue")
            else:
                # Schedule retry
                await asyncio.sleep(self.retry_delay * message.retry_count)
                message.status = MessageStatus.PENDING
                await self.enqueue(
                    message.topic,
                    message.content,
                    message.sender,
                    message.metadata
                )
    
    async def _retry_failed_messages(self):
        """Background task to retry failed messages."""
        while self._running:
            try:
                await asyncio.sleep(5.0)  # Check every 5 seconds
                
                # Retry failed messages
                for msg_id, message in list(self.messages.items()):
                    if message.status == MessageStatus.FAILED:
                        if message.retry_count < message.max_retries:
                            await self.fail(msg_id, message.last_error or "Retry")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in retry task: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        pending = sum(1 for m in self.messages.values() if m.status == MessageStatus.PENDING)
        processing = sum(1 for m in self.messages.values() if m.status == MessageStatus.PROCESSING)
        completed = sum(1 for m in self.messages.values() if m.status == MessageStatus.COMPLETED)
        failed = sum(1 for m in self.messages.values() if m.status == MessageStatus.FAILED)
        dead_letter = len(self.dead_letter_queue)
        
        return {
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "dead_letter": dead_letter,
            "total": len(self.messages),
            "backend": "redis" if self.use_redis else ("rabbitmq" if self.use_rabbitmq else "memory")
        }


# Global instance
message_queue_persistence: Optional[MessageQueuePersistence] = None


def init_message_queue_persistence(
    use_redis: bool = False,
    use_rabbitmq: bool = False,
    redis_url: Optional[str] = None,
    rabbitmq_url: Optional[str] = None
) -> MessageQueuePersistence:
    """Initialize global message queue persistence."""
    global message_queue_persistence
    message_queue_persistence = MessageQueuePersistence(
        use_redis=use_redis,
        use_rabbitmq=use_rabbitmq,
        redis_url=redis_url,
        rabbitmq_url=rabbitmq_url
    )
    return message_queue_persistence


def get_message_queue_persistence() -> Optional[MessageQueuePersistence]:
    """Get global message queue persistence instance."""
    return message_queue_persistence

