"""
CMP Connector Base Class - Abstract base for all connectors.
Implements the Connected Media Protocol pattern.
"""

from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)


class ConnectorStatus(Enum):
    """Connector status states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


@dataclass
class ConnectorConfig:
    """Configuration for a connector instance"""
    connector_id: str
    connector_type: str
    name: str
    credentials: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    webhook_url: Optional[str] = None
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConnectorEvent:
    """Event received from or sent to connector"""
    event_type: str
    payload: Dict[str, Any]
    source: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    processed: bool = False
    error: Optional[str] = None


class ConnectorBase(ABC):
    """
    Abstract base class for all CMP connectors.
    Provides common functionality for authentication, webhooks, and event handling.
    """
    
    # Class-level metadata
    connector_type: str = "base"
    display_name: str = "Base Connector"
    description: str = "Abstract base connector"
    icon: str = "plug"
    category: str = "other"
    
    # Supported trigger and action types
    triggers: List[str] = []
    actions: List[str] = []
    
    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.status = ConnectorStatus.DISCONNECTED
        self.last_error: Optional[str] = None
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.callbacks: Dict[str, List[callable]] = {}
        
    # ==================== Abstract Methods ====================
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the external service. Returns True on success."""
        pass
    
    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """Test the connection and return status info."""
        pass
    
    @abstractmethod
    async def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action on the external service."""
        pass
    
    @abstractmethod
    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming webhook from external service."""
        pass
    
    # ==================== Common Methods ====================
    
    async def connect(self) -> bool:
        """Establish connection to the external service."""
        try:
            self.status = ConnectorStatus.CONNECTING
            if await self.authenticate():
                self.status = ConnectorStatus.CONNECTED
                logger.info(f"Connector {self.config.name} connected successfully")
                return True
            else:
                self.status = ConnectorStatus.ERROR
                self.last_error = "Authentication failed"
                return False
        except Exception as e:
            self.status = ConnectorStatus.ERROR
            self.last_error = str(e)
            logger.error(f"Connector {self.config.name} connection failed: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from the external service."""
        try:
            self.status = ConnectorStatus.DISCONNECTED
            logger.info(f"Connector {self.config.name} disconnected")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting {self.config.name}: {e}")
            return False
    
    def on(self, event_type: str, callback: callable):
        """Register callback for event type."""
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []
        self.callbacks[event_type].append(callback)
    
    async def emit(self, event: ConnectorEvent):
        """Emit event to registered callbacks."""
        if event.event_type in self.callbacks:
            for callback in self.callbacks[event.event_type]:
                try:
                    await callback(event)
                except Exception as e:
                    logger.error(f"Error in event callback: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current connector status."""
        return {
            "connector_id": self.config.connector_id,
            "connector_type": self.connector_type,
            "name": self.config.name,
            "status": self.status.value,
            "last_error": self.last_error,
            "enabled": self.config.enabled
        }
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get connector metadata for UI display."""
        return {
            "type": self.connector_type,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "triggers": self.triggers,
            "actions": self.actions
        }
    
    @classmethod
    def get_credentials_schema(cls) -> Dict[str, Any]:
        """Return JSON schema for required credentials."""
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    @classmethod
    def get_settings_schema(cls) -> Dict[str, Any]:
        """Return JSON schema for connector settings."""
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
