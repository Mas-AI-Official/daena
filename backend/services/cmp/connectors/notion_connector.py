"""
Notion Connector - Integration with Notion workspace.
Supports reading/writing pages, databases, and blocks.
"""

from typing import Dict, Any, List, Optional
import logging
import httpx

from ..connector_base import ConnectorBase, ConnectorConfig, ConnectorEvent

logger = logging.getLogger(__name__)


class NotionConnector(ConnectorBase):
    """Notion workspace connector."""
    
    connector_type = "notion"
    display_name = "Notion"
    description = "Connect to Notion for document and database management"
    icon = "notion"
    category = "productivity"
    
    triggers = [
        "page_created",
        "page_updated",
        "database_updated",
        "comment_added"
    ]
    
    actions = [
        "create_page",
        "update_page",
        "get_page",
        "query_database",
        "create_database",
        "append_block",
        "search"
    ]
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.api_key = config.credentials.get("api_key", "")
        self.base_url = "https://api.notion.com/v1"
        self.notion_version = "2022-06-28"
    
    async def authenticate(self) -> bool:
        """Authenticate with Notion API."""
        if not self.api_key:
            self.last_error = "API key not provided"
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/users/me",
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Notion authenticated as: {data.get('name', 'Integration')}")
                    return True
                else:
                    self.last_error = f"Auth failed: {response.status_code}"
                    return False
        except Exception as e:
            self.last_error = str(e)
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """Get standard headers for Notion API."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": self.notion_version
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Notion connection."""
        if await self.authenticate():
            return {
                "success": True,
                "message": "Connected to Notion successfully"
            }
        return {
            "success": False,
            "error": self.last_error
        }
    
    async def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Notion action."""
        if action == "create_page":
            return await self._create_page(
                parent_id=params.get("parent_id"),
                parent_type=params.get("parent_type", "page"),
                title=params.get("title"),
                properties=params.get("properties", {}),
                children=params.get("children", [])
            )
        elif action == "get_page":
            return await self._get_page(params.get("page_id"))
        elif action == "query_database":
            return await self._query_database(
                database_id=params.get("database_id"),
                filter=params.get("filter"),
                sorts=params.get("sorts")
            )
        elif action == "search":
            return await self._search(
                query=params.get("query"),
                filter=params.get("filter")
            )
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    
    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming Notion webhook (if configured)."""
        # Notion webhooks are handled via polling or custom setup
        event_type = payload.get("type", "unknown")
        
        connector_event = ConnectorEvent(
            event_type=event_type,
            payload=payload,
            source="notion"
        )
        await self.emit(connector_event)
        
        return {"success": True, "event_type": event_type}
    
    async def _create_page(
        self,
        parent_id: str,
        parent_type: str,
        title: str,
        properties: Dict[str, Any],
        children: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create a new page in Notion."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "parent": {
                        f"{parent_type}_id": parent_id
                    },
                    "properties": {
                        "title": {
                            "title": [{"text": {"content": title}}]
                        },
                        **properties
                    }
                }
                
                if children:
                    payload["children"] = children
                
                response = await client.post(
                    f"{self.base_url}/pages",
                    headers=self._get_headers(),
                    json=payload
                )
                
                if response.status_code in (200, 201):
                    data = response.json()
                    return {
                        "success": True,
                        "page_id": data.get("id"),
                        "url": data.get("url")
                    }
                return {"success": False, "error": f"Failed: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_page(self, page_id: str) -> Dict[str, Any]:
        """Get a page by ID."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/pages/{page_id}",
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    return {"success": True, "page": response.json()}
                return {"success": False, "error": f"Failed: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _query_database(
        self,
        database_id: str,
        filter: Optional[Dict] = None,
        sorts: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Query a Notion database."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {}
                if filter:
                    payload["filter"] = filter
                if sorts:
                    payload["sorts"] = sorts
                
                response = await client.post(
                    f"{self.base_url}/databases/{database_id}/query",
                    headers=self._get_headers(),
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "results": data.get("results", []),
                        "has_more": data.get("has_more", False)
                    }
                return {"success": False, "error": f"Failed: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _search(
        self,
        query: str,
        filter: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Search Notion workspace."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {"query": query}
                if filter:
                    payload["filter"] = filter
                
                response = await client.post(
                    f"{self.base_url}/search",
                    headers=self._get_headers(),
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "results": data.get("results", []),
                        "has_more": data.get("has_more", False)
                    }
                return {"success": False, "error": f"Failed: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @classmethod
    def get_credentials_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "api_key": {
                    "type": "string",
                    "title": "Integration Token",
                    "description": "Notion Integration Token (secret_...)"
                },
                "default_database_id": {
                    "type": "string",
                    "title": "Default Database ID",
                    "description": "Optional default database for operations"
                }
            },
            "required": ["api_key"]
        }
