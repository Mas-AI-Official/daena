"""Enhanced Message Bus for Daena's messaging system with Sunflower × Honeycomb routing."""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class MessageType(Enum):
    TASK = "task"
    RESULT = "result"
    STATUS = "status"
    ALERT = "alert"
    METRIC = "metric"
    COMMAND = "command"
    LOCAL_NEIGHBOR = "local_neighbor"
    CMP_FALLBACK = "cmp_fallback"

class MessagePriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

class AgentStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"

@dataclass
class Message:
    id: str
    topic: str
    content: Dict[str, Any]
    sender: str
    recipient: Optional[str] = None
    message_type: MessageType = MessageType.TASK
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: str = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
        if self.metadata is None:
            self.metadata = {}

class MessageBus:
    """Enhanced message bus with Sunflower × Honeycomb routing capabilities."""
    
    def __init__(self):
        """Initialize the enhanced message bus."""
        self.agents: Dict[str, Any] = {}
        self.queues: Dict[str, asyncio.Queue] = {}
        self.subscribers: Dict[str, List[asyncio.Queue]] = {}
        self.topic_subscribers: Dict[str, List[Callable]] = {}
        self.message_history: List[Message] = []
        self.max_history = 1000
        self._running = False
        self._processing = False
        self.message_queue = asyncio.Queue()
        
    async def start(self):
        """Start the message bus."""
        self._running = True
        asyncio.create_task(self._process_messages())
        logger.info("Enhanced message bus started")
        
    async def stop(self):
        """Stop the message bus."""
        self._running = False
        self._processing = False
        # Clear all queues
        while not self.message_queue.empty():
            await self.message_queue.get()
        for queues in self.subscribers.values():
            for queue in queues:
                while not queue.empty():
                    await queue.get()
        logger.info("Message bus stopped")
        
    async def register_agent(self, agent: Any):
        """Register a new agent."""
        if agent.id in self.agents:
            raise ValueError(f"Agent {agent.id} already registered")
            
        self.agents[agent.id] = agent
        self.queues[agent.id] = asyncio.Queue()
        self.subscribers[agent.id] = []
        logger.info(f"Agent {agent.id} registered")
        
    async def unregister_agent(self, agent_id: str):
        """Unregister an agent."""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not registered")
            
        del self.agents[agent_id]
        del self.queues[agent_id]
        del self.subscribers[agent_id]
        logger.info(f"Agent {agent_id} unregistered")
        
    async def subscribe(self, agent_id: str, queue: asyncio.Queue):
        """Subscribe an agent to messages."""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not registered")
            
        self.subscribers[agent_id].append(queue)
        logger.info(f"Agent {agent_id} subscribed")
        
    async def unsubscribe(self, agent_id: str, queue: asyncio.Queue):
        """Unsubscribe an agent from messages."""
        if agent_id in self.agents and queue in self.subscribers[agent_id]:
            self.subscribers[agent_id].remove(queue)
            logger.info(f"Agent {agent_id} unsubscribed")
            
    async def subscribe_topic(self, topic: str, callback: Callable):
        """Subscribe to a topic with callback."""
        if topic not in self.topic_subscribers:
            self.topic_subscribers[topic] = []
        self.topic_subscribers[topic].append(callback)
        logger.info(f"New topic subscription to {topic}")
        
    async def unsubscribe_topic(self, topic: str, callback: Callable):
        """Unsubscribe from a topic."""
        if topic in self.topic_subscribers and callback in self.topic_subscribers[topic]:
            self.topic_subscribers[topic].remove(callback)
            logger.info(f"Unsubscribed from topic {topic}")

    async def send_local_neighbors(self, message: Message, neighbor_ids: List[str]):
        """Send message to local neighbors first (Sunflower routing)."""
        if not self._running:
            raise RuntimeError("Message bus is not running")
            
        message.message_type = MessageType.LOCAL_NEIGHBOR
        message.metadata["routing"] = "local_neighbors"
        message.metadata["neighbor_count"] = len(neighbor_ids)
        
        # Send to neighbors
        for neighbor_id in neighbor_ids:
            if neighbor_id in self.subscribers:
                for queue in self.subscribers[neighbor_id]:
                    await queue.put(message)
                    
        logger.info(f"Message {message.id} sent to {len(neighbor_ids)} local neighbors")
        return len(neighbor_ids)

    async def send_cmp_fallback(self, message: Message):
        """Send message to CMP fallback system."""
        if not self._running:
            raise RuntimeError("Message bus is not running")
            
        message.message_type = MessageType.CMP_FALLBACK
        message.metadata["routing"] = "cmp_fallback"
        
        # Send to CMP subscribers
        if "cmp" in self.topic_subscribers:
            for callback in self.topic_subscribers["cmp"]:
                try:
                    await callback(message)
                except Exception as e:
                    logger.error(f"Error in CMP fallback: {e}")
                    
        logger.info(f"Message {message.id} sent to CMP fallback")
        return True

    async def route(self, message: Message, neighbor_ids: List[str] = None):
        """Route message: neighbor-first → CMP fallback."""
        if not self._running:
            raise RuntimeError("Message bus is not running")
            
        # Try local neighbors first
        if neighbor_ids:
            try:
                neighbor_count = await self.send_local_neighbors(message, neighbor_ids)
                if neighbor_count > 0:
                    message.metadata["routing_result"] = "local_success"
                    return "local_success"
            except Exception as e:
                logger.warning(f"Local neighbor routing failed: {e}")
                
        # Fallback to CMP
        try:
            await self.send_cmp_fallback(message)
            message.metadata["routing_result"] = "cmp_fallback"
            return "cmp_fallback"
        except Exception as e:
            logger.error(f"CMP fallback failed: {e}")
            message.metadata["routing_result"] = "routing_failed"
            return "routing_failed"

    async def publish(self, message: Message):
        """Publish a message to all subscribers."""
        if not self._running:
            raise RuntimeError("Message bus is not running")
            
        # Store in history
        self.message_history.append(message)
        if len(self.message_history) > self.max_history:
            self.message_history.pop(0)
            
        # Send to agent subscribers
        for agent_id, queues in self.subscribers.items():
            for queue in queues:
                await queue.put(message)
                
        # Send to topic subscribers
        if message.topic in self.topic_subscribers:
            for callback in self.topic_subscribers[message.topic]:
                try:
                    await callback(message)
                except Exception as e:
                    logger.error(f"Error in topic callback: {e}")
                    
        logger.info(f"Message {message.id} published to topic {message.topic}")
        
    async def _process_messages(self):
        """Process messages from the queue."""
        self._processing = True
        while self._processing and self._running:
            try:
                message = await self.message_queue.get()
                
                # Process message based on type
                if message.message_type == MessageType.LOCAL_NEIGHBOR:
                    # Already handled by send_local_neighbors
                    pass
                elif message.message_type == MessageType.CMP_FALLBACK:
                    # Already handled by send_cmp_fallback
                    pass
                else:
                    # Standard message processing
                    await self.publish(message)
                    
            except Exception as e:
                logger.error(f"Error in message processing loop: {e}")
                await asyncio.sleep(1)
                
    async def get_all_agents(self) -> List[Any]:
        """Get all registered agents."""
        return list(self.agents.values())
        
    async def get_message_history(self, limit: int = 100) -> List[Message]:
        """Get recent message history."""
        return self.message_history[-limit:] if self.message_history else [] 