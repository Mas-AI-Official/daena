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
        
        # Sunflower × Honeycomb routing
        self.neighbors: Dict[str, List[str]] = {}
        self.cmp_fallback: Optional[Callable] = None
        self.routing_stats = {
            "local_routes": 0,
            "cmp_fallbacks": 0,
            "total_messages": 0,
            "neighbor_routes": 0
        }
        
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
        
    def set_neighbors(self, cell_id: str, neighbor_ids: List[str]):
        """Set neighbors for a cell (Sunflower × Honeycomb)."""
        self.neighbors[cell_id] = neighbor_ids
        logger.info(f"Set {len(neighbor_ids)} neighbors for {cell_id}")
        
    def set_cmp_fallback(self, fallback_handler: Callable):
        """Set the CMP fallback handler."""
        self.cmp_fallback = fallback_handler
        logger.info("Set CMP fallback handler")
        
    async def route(self, message: Message, neighbors: Optional[List[str]] = None) -> bool:
        """Route message using neighbor-first strategy with CMP fallback."""
        self.routing_stats["total_messages"] += 1
        
        # Try local route first
        if message.message_type in [MessageType.LOCAL_NEIGHBOR, MessageType.TASK]:
            try:
                # Local processing
                self.routing_stats["local_routes"] += 1
                logger.info(f"Message {message.id} routed locally")
                return True
            except Exception as e:
                logger.warning(f"Local route failed for {message.id}: {e}")
        
        # Try neighbor routing (Sunflower × Honeycomb)
        if neighbors or (message.recipient and message.recipient in self.neighbors):
            target_neighbors = neighbors or self.neighbors.get(message.recipient, [])
            for neighbor_id in target_neighbors:
                try:
                    # Route to neighbor
                    await self._send_to_neighbor(neighbor_id, message)
                    self.routing_stats["neighbor_routes"] += 1
                    logger.info(f"Message {message.id} routed to neighbor {neighbor_id}")
                    return True
                except Exception as e:
                    logger.warning(f"Neighbor routing failed for {message.id} to {neighbor_id}: {e}")
        
        # CMP fallback
        if self.cmp_fallback:
            try:
                result = await self.cmp_fallback(message)
                self.routing_stats["cmp_fallbacks"] += 1
                logger.info(f"Message {message.id} routed via CMP fallback")
                return result
            except Exception as e:
                logger.error(f"CMP fallback failed for {message.id}: {e}")
        
        logger.error(f"Message {message.id} could not be routed")
        return False
        
    async def send_local_neighbors(self, sender: str, content: Any, message_type: MessageType = MessageType.LOCAL_NEIGHBOR) -> List[str]:
        """Send message to all local neighbors."""
        if sender not in self.neighbors:
            return []
        
        neighbor_ids = self.neighbors[sender]
        successful_sends = []
        
        for neighbor_id in neighbor_ids:
            message = Message(
                id=str(uuid.uuid4()),
                topic="neighbor_communication",
                content=content,
                sender=sender,
                recipient=neighbor_id,
                message_type=message_type
            )
            if await self.route(message, [neighbor_id]):
                successful_sends.append(neighbor_id)
        
        return successful_sends
        
    async def send_cmp_fallback(self, sender: str, content: Any, message_type: MessageType = MessageType.CMP_FALLBACK) -> bool:
        """Send message via CMP fallback."""
        message = Message(
            id=str(uuid.uuid4()),
            topic="cmp_fallback",
            content=content,
            sender=sender,
            message_type=message_type
        )
        return await self.route(message)
        
    async def _send_to_neighbor(self, neighbor_id: str, message: Message):
        """Send message to a specific neighbor."""
        if neighbor_id in self.queues:
            await self.queues[neighbor_id].put(message)
        else:
            # Simulate neighbor processing
            logger.info(f"Simulating neighbor {neighbor_id} processing message {message.id}")
            
    async def _process_messages(self):
        """Process messages in the main queue."""
        self._processing = True
        while self._running:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self._handle_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}")
        self._processing = False
        
    async def _handle_message(self, message: Message):
        """Handle a single message."""
        try:
            # Route based on message type
            if message.message_type == MessageType.LOCAL_NEIGHBOR:
                await self._handle_local_neighbor(message)
            elif message.message_type == MessageType.CMP_FALLBACK:
                await self._handle_cmp_fallback(message)
            else:
                await self._handle_standard(message)
        except Exception as e:
            logger.error(f"Error handling message {message.id}: {e}")
            
    async def _handle_local_neighbor(self, message: Message):
        """Handle local neighbor message."""
        logger.info(f"Processing local neighbor message: {message.id}")
        # Add to history
        self.message_history.append(message)
        if len(self.message_history) > self.max_history:
            self.message_history.pop(0)
            
    async def _handle_cmp_fallback(self, message: Message):
        """Handle CMP fallback message."""
        logger.info(f"Processing CMP fallback message: {message.id}")
        # Add to history
        self.message_history.append(message)
        if len(self.message_history) > self.max_history:
            self.message_history.pop(0)
            
    async def _handle_standard(self, message: Message):
        """Handle standard message."""
        logger.info(f"Processing standard message: {message.id}")
        # Add to history
        self.message_history.append(message)
        if len(self.message_history) > self.max_history:
            self.message_history.pop(0)
            
    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        return {
            **self.routing_stats,
            "neighbor_count": sum(len(neighbors) for neighbors in self.neighbors.values()),
            "agent_count": len(self.agents),
            "queue_count": len(self.queues),
            "has_cmp_fallback": self.cmp_fallback is not None,
            "running": self._running,
            "processing": self._processing
        }
        
    def get_message_history(self, limit: int = 100) -> List[Message]:
        """Get recent message history."""
        return self.message_history[-limit:] if self.message_history else []

# Global message bus instance
message_bus = MessageBus() 