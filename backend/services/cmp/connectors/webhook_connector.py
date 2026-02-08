"""
Webhook Connector - Generic webhook support.
Allows sending/receiving data via HTTP webhooks.
"""

from typing import Dict, Any, List, Optional
import logging
import httpx
from datetime import datetime

from ..connector_base import ConnectorBase, ConnectorConfig, ConnectorEvent

logger = logging.getLogger(__name__)


class WebhookConnector(ConnectorBase):
    """Generic webhook connector."""
    
    connector_type = "webhook"
    display_name = "Webhook"
    description = "Generic HTTP webhook for custom integrations"
    icon = "webhook"
    category = "utility"
    
    triggers = [
        "webhook_received"
    ]
    
    actions = [
        "send_webhook",
        "send_get_request",
        "send_post_request"
    ]
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.target_url = config.settings.get("target_url", "")
        self.auth_header = config.credentials.get("auth_header", "")
        self.secret = config.credentials.get("secret", "")
    
    async def authenticate(self) -> bool:
        """Webhooks don't require explicit authentication."""
        return True
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test webhook connectivity."""
        if self.target_url:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.head(
                        self.target_url,
                        timeout=5.0
                    )
                    return {
                        "success": True,
                        "message": f"URL reachable (HTTP {response.status_code})"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"URL not reachable: {e}"
                }
        return {
            "success": True,
            "message": "No target URL configured (receiving mode only)"
        }
    
    async def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a webhook action."""
        if action == "send_webhook":
            return await self._send_webhook(
                url=params.get("url", self.target_url),
                method=params.get("method", "POST"),
                payload=params.get("payload", {}),
                headers=params.get("headers", {})
            )
        elif action == "send_get_request":
            return await self._send_webhook(
                url=params.get("url", self.target_url),
                method="GET",
                payload=params.get("params", {}),
                headers=params.get("headers", {})
            )
        elif action == "send_post_request":
            return await self._send_webhook(
                url=params.get("url", self.target_url),
                method="POST",
                payload=params.get("payload", {}),
                headers=params.get("headers", {})
            )
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    
    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming webhook."""
        # Verify signature if secret is configured
        if self.secret:
            signature = payload.get("headers", {}).get("x-webhook-signature", "")
            if not self._verify_signature(signature, payload.get("body", "")):
                return {"success": False, "error": "Invalid signature"}
        
        connector_event = ConnectorEvent(
            event_type="webhook_received",
            payload=payload,
            source="webhook",
            timestamp=datetime.utcnow()
        )
        await self.emit(connector_event)
        
        return {
            "success": True,
            "received_at": connector_event.timestamp.isoformat()
        }
    
    async def _send_webhook(
        self,
        url: str,
        method: str = "POST",
        payload: Dict[str, Any] = None,
        headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Send webhook request."""
        if not url:
            return {"success": False, "error": "No URL provided"}
        
        try:
            request_headers = headers or {}
            if self.auth_header:
                request_headers["Authorization"] = self.auth_header
            
            async with httpx.AsyncClient() as client:
                if method.upper() == "GET":
                    response = await client.get(
                        url,
                        headers=request_headers,
                        params=payload or {},
                        timeout=30.0
                    )
                elif method.upper() == "POST":
                    response = await client.post(
                        url,
                        headers=request_headers,
                        json=payload or {},
                        timeout=30.0
                    )
                elif method.upper() == "PUT":
                    response = await client.put(
                        url,
                        headers=request_headers,
                        json=payload or {},
                        timeout=30.0
                    )
                elif method.upper() == "DELETE":
                    response = await client.delete(
                        url,
                        headers=request_headers,
                        timeout=30.0
                    )
                else:
                    return {"success": False, "error": f"Unsupported method: {method}"}
                
                return {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "response_body": response.text[:1000],  # Limit response size
                    "headers": dict(response.headers)
                }
        except httpx.TimeoutException:
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _verify_signature(self, signature: str, body: str) -> bool:
        """Verify webhook signature."""
        import hmac
        import hashlib
        
        if not self.secret:
            return True
        
        expected = hmac.new(
            self.secret.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
    
    @classmethod
    def get_credentials_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "auth_header": {
                    "type": "string",
                    "title": "Authorization Header",
                    "description": "Authorization header value for outgoing requests"
                },
                "secret": {
                    "type": "string",
                    "title": "Webhook Secret",
                    "description": "Secret for verifying incoming webhook signatures"
                }
            },
            "required": []
        }
    
    @classmethod
    def get_settings_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target_url": {
                    "type": "string",
                    "title": "Target URL",
                    "description": "Default URL for outgoing webhooks"
                }
            },
            "required": []
        }
