"""
Discord Connector - Integration with Discord servers.
Supports sending messages, managing channels, and receiving events.
"""

from typing import Dict, Any, List, Optional
import logging
import httpx

from ..connector_base import ConnectorBase, ConnectorConfig, ConnectorEvent

logger = logging.getLogger(__name__)


class DiscordConnector(ConnectorBase):
    """Discord server connector."""
    
    connector_type = "discord"
    display_name = "Discord"
    description = "Connect to Discord servers for messaging and community management"
    icon = "discord"
    category = "communication"
    
    triggers = [
        "message_received",
        "reaction_added",
        "member_joined",
        "member_left",
        "mention"
    ]
    
    actions = [
        "send_message",
        "send_dm",
        "create_channel",
        "add_reaction",
        "list_channels",
        "get_guild_info",
        "get_member_info"
    ]
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.bot_token = config.credentials.get("bot_token", "")
        self.base_url = "https://discord.com/api/v10"
    
    async def authenticate(self) -> bool:
        """Authenticate with Discord API."""
        if not self.bot_token:
            self.last_error = "Bot token not provided"
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/users/@me",
                    headers={"Authorization": f"Bot {self.bot_token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Discord authenticated as: {data.get('username')}")
                    return True
                else:
                    self.last_error = f"Auth failed: {response.status_code}"
                    return False
        except Exception as e:
            self.last_error = str(e)
            return False
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Discord connection."""
        if await self.authenticate():
            return {
                "success": True,
                "message": "Connected to Discord successfully"
            }
        return {
            "success": False,
            "error": self.last_error
        }
    
    async def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Discord action."""
        if action == "send_message":
            return await self._send_message(
                channel_id=params.get("channel_id"),
                content=params.get("content"),
                embed=params.get("embed")
            )
        elif action == "list_channels":
            return await self._list_channels(params.get("guild_id"))
        elif action == "get_guild_info":
            return await self._get_guild_info(params.get("guild_id"))
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    
    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming Discord event (from webhook/gateway)."""
        event_type = payload.get("t")  # Discord event type
        event_data = payload.get("d", {})
        
        if event_type:
            connector_event = ConnectorEvent(
                event_type=event_type.lower(),
                payload=event_data,
                source="discord"
            )
            await self.emit(connector_event)
        
        return {"success": True, "event_type": event_type}
    
    async def _send_message(
        self,
        channel_id: str,
        content: str,
        embed: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Send message to a channel."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {"content": content}
                if embed:
                    payload["embeds"] = [embed]
                
                response = await client.post(
                    f"{self.base_url}/channels/{channel_id}/messages",
                    headers={
                        "Authorization": f"Bot {self.bot_token}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                if response.status_code in (200, 201):
                    data = response.json()
                    return {
                        "success": True,
                        "message_id": data.get("id"),
                        "channel_id": channel_id
                    }
                return {"success": False, "error": f"Failed: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _list_channels(self, guild_id: str) -> Dict[str, Any]:
        """List channels in a guild."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/guilds/{guild_id}/channels",
                    headers={"Authorization": f"Bot {self.bot_token}"}
                )
                
                if response.status_code == 200:
                    channels = response.json()
                    return {
                        "success": True,
                        "channels": [
                            {"id": c["id"], "name": c["name"], "type": c["type"]}
                            for c in channels
                        ]
                    }
                return {"success": False, "error": f"Failed: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_guild_info(self, guild_id: str) -> Dict[str, Any]:
        """Get guild information."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/guilds/{guild_id}",
                    headers={"Authorization": f"Bot {self.bot_token}"}
                )
                
                if response.status_code == 200:
                    guild = response.json()
                    return {
                        "success": True,
                        "guild": {
                            "id": guild.get("id"),
                            "name": guild.get("name"),
                            "member_count": guild.get("approximate_member_count"),
                            "icon": guild.get("icon")
                        }
                    }
                return {"success": False, "error": f"Failed: {response.status_code}"}
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
                    "description": "Discord Bot Token from Developer Portal"
                },
                "guild_id": {
                    "type": "string",
                    "title": "Default Guild ID",
                    "description": "Default server/guild ID for operations"
                }
            },
            "required": ["bot_token"]
        }
