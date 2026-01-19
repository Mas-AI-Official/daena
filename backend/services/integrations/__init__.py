"""
Base Integration Class
All integrations inherit from this class
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class BaseIntegration(ABC):
    """Base class for all integrations"""
    
    def __init__(self, integration_id: str, credentials: Optional[Dict[str, Any]] = None):
        self.integration_id = integration_id
        self.credentials = credentials or {}
        self.connected = False
        self.error = None
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect/authenticate to the integration
        Returns: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from the integration
        Returns: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test the connection
        Returns: {success: bool, message: str, data: Any}
        """
        pass
    
    @abstractmethod
    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an action with the integration
        Args:
            action: The action to perform (e.g., "send_email", "create_sheet")
            params: Parameters for the action
        Returns: {success: bool, data: Any, error: Optional[str]}
        """
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get current integration status"""
        return {
            "integration_id": self.integration_id,
            "connected": self.connected,
            "error": self.error
        }
    
    def format_response(self, success: bool, data: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
        """Helper to format standard response"""
        return {
            "success": success,
            "data": data,
            "error": error
        }
