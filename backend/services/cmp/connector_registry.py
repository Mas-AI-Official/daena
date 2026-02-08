"""
CMP Connector Registry - Manages all available connectors.
Provides discovery, instantiation, and lifecycle management.
"""

from typing import Dict, Any, List, Optional, Type
from datetime import datetime
import logging
import asyncio

from .connector_base import ConnectorBase, ConnectorConfig, ConnectorStatus

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    """
    Registry for CMP connectors.
    Manages connector types, instances, and their lifecycle.
    """
    
    def __init__(self):
        # Registered connector types (class definitions)
        self._connector_types: Dict[str, Type[ConnectorBase]] = {}
        
        # Active connector instances
        self._instances: Dict[str, ConnectorBase] = {}
        
        # Load built-in connectors
        self._load_builtin_connectors()
    
    def _load_builtin_connectors(self):
        """Load built-in connector types."""
        try:
            from .connectors.slack_connector import SlackConnector
            self.register_type(SlackConnector)
        except ImportError as e:
            logger.warning(f"Slack connector not available: {e}")
        
        try:
            from .connectors.discord_connector import DiscordConnector
            self.register_type(DiscordConnector)
        except ImportError as e:
            logger.warning(f"Discord connector not available: {e}")
        
        try:
            from .connectors.github_connector import GitHubConnector
            self.register_type(GitHubConnector)
        except ImportError as e:
            logger.warning(f"GitHub connector not available: {e}")
        
        try:
            from .connectors.notion_connector import NotionConnector
            self.register_type(NotionConnector)
        except ImportError as e:
            logger.warning(f"Notion connector not available: {e}")
        
        try:
            from .connectors.email_connector import EmailConnector
            self.register_type(EmailConnector)
        except ImportError as e:
            logger.warning(f"Email connector not available: {e}")
        
        try:
            from .connectors.webhook_connector import WebhookConnector
            self.register_type(WebhookConnector)
        except ImportError as e:
            logger.warning(f"Webhook connector not available: {e}")
        
        logger.info(f"Loaded {len(self._connector_types)} connector types")
    
    # ==================== Type Registration ====================
    
    def register_type(self, connector_class: Type[ConnectorBase]):
        """Register a connector type."""
        connector_type = connector_class.connector_type
        self._connector_types[connector_type] = connector_class
        logger.info(f"Registered connector type: {connector_type}")
    
    def get_type(self, connector_type: str) -> Optional[Type[ConnectorBase]]:
        """Get a connector class by type."""
        return self._connector_types.get(connector_type)
    
    def list_types(self) -> List[Dict[str, Any]]:
        """List all registered connector types with metadata."""
        return [
            cls.get_metadata() if hasattr(cls, 'get_metadata') else {"type": name}
            for name, cls in self._connector_types.items()
        ]
    
    # ==================== Instance Management ====================
    
    def create_instance(self, config: ConnectorConfig) -> Optional[ConnectorBase]:
        """Create a new connector instance from config."""
        connector_class = self._connector_types.get(config.connector_type)
        if not connector_class:
            logger.error(f"Unknown connector type: {config.connector_type}")
            return None
        
        try:
            instance = connector_class(config)
            self._instances[config.connector_id] = instance
            logger.info(f"Created connector instance: {config.connector_id}")
            return instance
        except Exception as e:
            logger.error(f"Failed to create connector: {e}")
            return None
    
    def get_instance(self, connector_id: str) -> Optional[ConnectorBase]:
        """Get a connector instance by ID."""
        return self._instances.get(connector_id)
    
    def remove_instance(self, connector_id: str) -> bool:
        """Remove a connector instance."""
        if connector_id in self._instances:
            instance = self._instances.pop(connector_id)
            asyncio.create_task(instance.disconnect())
            logger.info(f"Removed connector instance: {connector_id}")
            return True
        return False
    
    def list_instances(self) -> List[Dict[str, Any]]:
        """List all connector instances with status."""
        return [
            instance.get_status()
            for instance in self._instances.values()
        ]
    
    # ==================== Lifecycle Management ====================
    
    async def connect_all(self) -> Dict[str, bool]:
        """Connect all enabled instances."""
        results = {}
        for connector_id, instance in self._instances.items():
            if instance.config.enabled:
                results[connector_id] = await instance.connect()
        return results
    
    async def disconnect_all(self) -> Dict[str, bool]:
        """Disconnect all instances."""
        results = {}
        for connector_id, instance in self._instances.items():
            results[connector_id] = await instance.disconnect()
        return results
    
    async def test_connection(self, connector_id: str) -> Dict[str, Any]:
        """Test connection for a specific connector."""
        instance = self._instances.get(connector_id)
        if not instance:
            return {"success": False, "error": "Connector not found"}
        return await instance.test_connection()
    
    # ==================== Action Execution ====================
    
    async def execute_action(
        self,
        connector_id: str,
        action: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an action on a connector."""
        instance = self._instances.get(connector_id)
        if not instance:
            return {"success": False, "error": "Connector not found"}
        
        if instance.status != ConnectorStatus.CONNECTED:
            return {"success": False, "error": "Connector not connected"}
        
        try:
            return await instance.execute_action(action, params)
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== Webhook Handling ====================
    
    async def handle_webhook(
        self,
        connector_id: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Route webhook to appropriate connector."""
        instance = self._instances.get(connector_id)
        if not instance:
            return {"success": False, "error": "Connector not found"}
        
        try:
            return await instance.handle_webhook(payload)
        except Exception as e:
            logger.error(f"Webhook handling failed: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== Stats ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        statuses = {}
        for instance in self._instances.values():
            status = instance.status.value
            statuses[status] = statuses.get(status, 0) + 1
        
        return {
            "registered_types": len(self._connector_types),
            "active_instances": len(self._instances),
            "statuses": statuses,
            "types": list(self._connector_types.keys())
        }


# Global registry instance
connector_registry = ConnectorRegistry()
