"""Notion REST API client for Daena department agents.

Uses Notion API v1 directly via httpx.
Credentials come from ConnectorInstance (integration token).

Supported tools:
    - search_pages: Search Notion workspace
    - read_page: Read a specific page
    - create_page: Create a new page
    - query_database: Query a Notion database
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionClient:
    """Direct Notion API client using integration token.

    Args:
        credentials: Must contain "token" (Notion integration token).
    """

    def __init__(self, credentials: dict[str, str]) -> None:
        self._token = credentials.get("token", "") or credentials.get("access_token", "")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        }

    def _check_token(self) -> None:
        if not self._token:
            raise ValueError(
                "Notion integration token required. "
                "Connect Notion in Daena Settings > Connections."
            )

    async def search_pages(
        self,
        query: str = "",
        filter_type: str | None = None,
        page_size: int = 10,
    ) -> dict[str, Any]:
        """Search the Notion workspace.

        Args:
            query: Search query string.
            filter_type: "page" or "database" to filter results.
            page_size: Number of results (max 100).

        Returns:
            Dict with "results" list.
        """
        self._check_token()
        body: dict[str, Any] = {
            "query": query,
            "page_size": min(page_size, 100),
        }
        if filter_type in ("page", "database"):
            body["filter"] = {"property": "object", "value": filter_type}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{NOTION_API_BASE}/search",
                headers=self._headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("results", []):
            title = self._extract_title(item)
            results.append({
                "id": item.get("id"),
                "type": item.get("object"),
                "title": title,
                "url": item.get("url", ""),
                "created_time": item.get("created_time", ""),
                "last_edited_time": item.get("last_edited_time", ""),
            })

        return {"results": results, "has_more": data.get("has_more", False)}

    async def read_page(self, page_id: str) -> dict[str, Any]:
        """Read a specific Notion page with its content blocks.

        Args:
            page_id: Notion page ID (UUID format).

        Returns:
            Dict with page properties and content blocks.
        """
        self._check_token()
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Get page metadata
            page_resp = await client.get(
                f"{NOTION_API_BASE}/pages/{page_id}",
                headers=self._headers,
            )
            page_resp.raise_for_status()
            page_data = page_resp.json()

            # Get page content (blocks)
            blocks_resp = await client.get(
                f"{NOTION_API_BASE}/blocks/{page_id}/children",
                headers=self._headers,
                params={"page_size": 100},
            )
            blocks_resp.raise_for_status()
            blocks_data = blocks_resp.json()

        title = self._extract_title(page_data)
        content_blocks = []
        for block in blocks_data.get("results", []):
            block_text = self._extract_block_text(block)
            if block_text:
                content_blocks.append({
                    "type": block.get("type", ""),
                    "text": block_text,
                })

        return {
            "id": page_data.get("id"),
            "title": title,
            "url": page_data.get("url", ""),
            "created_time": page_data.get("created_time", ""),
            "last_edited_time": page_data.get("last_edited_time", ""),
            "content": content_blocks,
            "properties": self._extract_properties(page_data),
        }

    async def create_page(
        self,
        parent_id: str,
        title: str,
        content: str = "",
        parent_type: str = "page",
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new Notion page.

        Args:
            parent_id: Parent page or database ID.
            title: Page title.
            content: Plain text content for the page body.
            parent_type: "page" or "database".
            properties: Additional database properties (for database parents).

        Returns:
            Dict with created page details.
        """
        self._check_token()
        if parent_type == "database":
            parent = {"database_id": parent_id}
            props = properties or {}
            props["Name"] = {"title": [{"text": {"content": title}}]}
        else:
            parent = {"page_id": parent_id}
            props = {"title": [{"text": {"content": title}}]}

        body: dict[str, Any] = {
            "parent": parent,
            "properties": props,
        }

        # Add content blocks if provided
        if content:
            body["children"] = [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content}}],
                    },
                }
            ]

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{NOTION_API_BASE}/pages",
                headers=self._headers,
                json=body,
            )
            resp.raise_for_status()
            result = resp.json()

        logger.info("notion.page_created", title=title, page_id=result.get("id"))
        return {
            "id": result.get("id"),
            "url": result.get("url", ""),
            "title": title,
            "status": "created",
        }

    async def query_database(
        self,
        database_id: str,
        filter_obj: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Query a Notion database.

        Args:
            database_id: Database ID.
            filter_obj: Notion filter object.
            sorts: Notion sort objects.
            page_size: Number of results.

        Returns:
            Dict with "rows" list.
        """
        self._check_token()
        body: dict[str, Any] = {"page_size": min(page_size, 100)}
        if filter_obj:
            body["filter"] = filter_obj
        if sorts:
            body["sorts"] = sorts

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{NOTION_API_BASE}/databases/{database_id}/query",
                headers=self._headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        rows = []
        for item in data.get("results", []):
            rows.append({
                "id": item.get("id"),
                "url": item.get("url", ""),
                "title": self._extract_title(item),
                "properties": self._extract_properties(item),
                "created_time": item.get("created_time", ""),
            })

        return {"rows": rows, "has_more": data.get("has_more", False)}

    # ── Helpers ──

    @staticmethod
    def _extract_title(item: dict) -> str:
        """Extract title from a Notion page or database object."""
        props = item.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                title_parts = prop.get("title", [])
                if title_parts:
                    return "".join(t.get("plain_text", "") for t in title_parts)
        # Fallback for database objects
        title_list = item.get("title", [])
        if isinstance(title_list, list) and title_list:
            return "".join(t.get("plain_text", "") for t in title_list)
        return "(untitled)"

    @staticmethod
    def _extract_block_text(block: dict) -> str:
        """Extract plain text from a Notion block."""
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})
        rich_text = block_data.get("rich_text", [])
        if rich_text:
            return "".join(t.get("plain_text", "") for t in rich_text)
        return ""

    @staticmethod
    def _extract_properties(item: dict) -> dict[str, Any]:
        """Extract simplified properties from a Notion page."""
        result: dict[str, Any] = {}
        for name, prop in item.get("properties", {}).items():
            prop_type = prop.get("type", "")
            if prop_type == "title":
                parts = prop.get("title", [])
                result[name] = "".join(t.get("plain_text", "") for t in parts)
            elif prop_type == "rich_text":
                parts = prop.get("rich_text", [])
                result[name] = "".join(t.get("plain_text", "") for t in parts)
            elif prop_type == "number":
                result[name] = prop.get("number")
            elif prop_type == "select":
                sel = prop.get("select")
                result[name] = sel.get("name") if sel else None
            elif prop_type == "multi_select":
                result[name] = [s.get("name") for s in prop.get("multi_select", [])]
            elif prop_type == "date":
                date = prop.get("date")
                result[name] = date.get("start") if date else None
            elif prop_type == "checkbox":
                result[name] = prop.get("checkbox")
            elif prop_type == "status":
                status = prop.get("status")
                result[name] = status.get("name") if status else None
            elif prop_type == "url":
                result[name] = prop.get("url")
        return result

    # ── Tool dispatch ──

    TOOLS: dict[str, str] = {
        "search_pages": "Search Notion workspace for pages and databases",
        "read_page": "Read a specific Notion page with content",
        "create_page": "Create a new page in Notion",
        "query_database": "Query a Notion database with filters",
    }

    async def execute_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a Notion tool by name."""
        if tool_name == "search_pages":
            return await self.search_pages(**params)
        elif tool_name == "read_page":
            return await self.read_page(**params)
        elif tool_name == "create_page":
            return await self.create_page(**params)
        elif tool_name == "query_database":
            return await self.query_database(**params)
        else:
            raise ValueError(f"Unknown Notion tool: {tool_name}")
