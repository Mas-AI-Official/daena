"""
Slack Connector - Integration with Slack workspace.
Supports sending messages, managing channels, and receiving events.
"""

from typing import Dict, Any, List, Optional
import logging
import httpx

from ..connector_base import ConnectorBase, ConnectorConfig, ConnectorEvent

logger = logging.getLogger(__name__)


class SlackConnector(ConnectorBase):
    """Slack workspace connector."""
    
    connector_type = "slack"
    display_name = "Slack"
    description = "Connect to Slack workspaces for messaging and notifications"
    icon = "slack"
    category = "communication"
    
    triggers = [
        "message_received",
        "reaction_added",
        "channel_created",
        "user_joined",
        "mention"
    ]
    
    actions = [
        "send_message",
        "send_dm",
        "create_channel",
        "upload_file",
        "add_reaction",
        "list_channels",
        "get_user_info"
    ]
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.bot_token = config.credentials.get("bot_token", "")
        self.signing_secret = config.credentials.get("signing_secret", "")
        self.base_url = "https://slack.com/api"
    
    async def authenticate(self) -> bool:
        """Authenticate with Slack API."""
        if not self.bot_token:
            self.last_error = "Bot token not provided"
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/auth.test",
                    headers={"Authorization": f"Bearer {self.bot_token}"}
                )
                data = response.json()
                
                if data.get("ok"):
                    logger.info(f"Slack authenticated as: {data.get('user')}")
                    return True
                else:
                    self.last_error = data.get("error", "Unknown error")
                    return False
        except Exception as e:
            self.last_error = str(e)
            return False
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Slack connection."""
        if await self.authenticate():
            return {
                "success": True,
                "message": "Connected to Slack successfully"
            }
        return {
            "success": False,
            "error": self.last_error
        }
    
    async def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Slack action."""
        if action == "send_message":
            return await self._send_message(
                channel=params.get("channel"),
                text=params.get("text"),
                blocks=params.get("blocks")
            )
        elif action == "send_dm":
            return await self._send_dm(
                user_id=params.get("user_id"),
                text=params.get("text")
            )
        elif action == "list_channels":
            return await self._list_channels()
        elif action == "get_user_info":
            return await self._get_user_info(params.get("user_id"))
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    
    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming Slack event."""
        event_type = payload.get("type")
        
        if event_type == "url_verification":
            return {"challenge": payload.get("challenge")}
        
        if event_type == "event_callback":
            event = payload.get("event", {})
            event_type = event.get("type")
            
            connector_event = ConnectorEvent(
                event_type=event_type,
                payload=event,
                source="slack"
            )
            await self.emit(connector_event)
            
            return {"success": True, "event_type": event_type}
        
        return {"success": True}
    
    async def _send_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Send message to a channel."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "channel": channel,
                    "text": text
                }
                if blocks:
                    payload["blocks"] = blocks
                
                response = await client.post(
                    f"{self.base_url}/chat.postMessage",
                    headers={"Authorization": f"Bearer {self.bot_token}"},
                    json=payload
                )
                data = response.json()
                
                if data.get("ok"):
                    return {
                        "success": True,
                        "ts": data.get("ts"),
                        "channel": data.get("channel")
                    }
                return {"success": False, "error": data.get("error")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _send_dm(self, user_id: str, text: str) -> Dict[str, Any]:
        """Send direct message to user."""
        try:
            async with httpx.AsyncClient() as client:
                # Open DM channel
                conv_response = await client.post(
                    f"{self.base_url}/conversations.open",
                    headers={"Authorization": f"Bearer {self.bot_token}"},
                    json={"users": user_id}
                )
                conv_data = conv_response.json()
                
                if not conv_data.get("ok"):
                    return {"success": False, "error": conv_data.get("error")}
                
                channel = conv_data["channel"]["id"]
                return await self._send_message(channel, text)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _list_channels(self) -> Dict[str, Any]:
        """List available channels."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/conversations.list",
                    headers={"Authorization": f"Bearer {self.bot_token}"}
                )
                data = response.json()
                
                if data.get("ok"):
                    channels = [
                        {"id": c["id"], "name": c["name"]}
                        for c in data.get("channels", [])
                    ]
                    return {"success": True, "channels": channels}
                return {"success": False, "error": data.get("error")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get user information."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/users.info",
                    headers={"Authorization": f"Bearer {self.bot_token}"},
                    params={"user": user_id}
                )
                data = response.json()
                
                if data.get("ok"):
                    user = data.get("user", {})
                    return {
                        "success": True,
                        "user": {
                            "id": user.get("id"),
                            "name": user.get("name"),
                            "real_name": user.get("real_name"),
                            "email": user.get("profile", {}).get("email")
                        }
                    }
                return {"success": False, "error": data.get("error")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @classmethod
    def get_credentials_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "bot_token": {
                    "type": "string",
                    "title": "Bot Token",
                    "description": "Slack Bot User OAuth Token (xoxb-...)"
                },
                "signing_secret": {
                    "type": "string",
                    "title": "Signing Secret",
                    "description": "Slack App Signing Secret for webhook verification"
                }
            },
            "required": ["bot_token"]
        }
