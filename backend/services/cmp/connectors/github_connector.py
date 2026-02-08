"""
GitHub Connector - Integration with GitHub repositories.
Supports issues, PRs, commits, and webhooks.
"""

from typing import Dict, Any, List, Optional
import logging
import httpx

from ..connector_base import ConnectorBase, ConnectorConfig, ConnectorEvent

logger = logging.getLogger(__name__)


class GitHubConnector(ConnectorBase):
    """GitHub repository connector."""
    
    connector_type = "github"
    display_name = "GitHub"
    description = "Connect to GitHub for repository management and automation"
    icon = "github"
    category = "development"
    
    triggers = [
        "push",
        "pull_request",
        "issue_created",
        "issue_comment",
        "release_published",
        "workflow_completed"
    ]
    
    actions = [
        "create_issue",
        "close_issue",
        "add_comment",
        "create_pull_request",
        "merge_pull_request",
        "list_repos",
        "list_issues",
        "get_file_content"
    ]
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.access_token = config.credentials.get("access_token", "")
        self.base_url = "https://api.github.com"
    
    async def authenticate(self) -> bool:
        """Authenticate with GitHub API."""
        if not self.access_token:
            self.last_error = "Access token not provided"
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/user",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/vnd.github+json"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"GitHub authenticated as: {data.get('login')}")
                    return True
                else:
                    self.last_error = f"HTTP {response.status_code}"
                    return False
        except Exception as e:
            self.last_error = str(e)
            return False
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test GitHub connection."""
        if await self.authenticate():
            return {
                "success": True,
                "message": "Connected to GitHub successfully"
            }
        return {
            "success": False,
            "error": self.last_error
        }
    
    async def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GitHub action."""
        if action == "create_issue":
            return await self._create_issue(
                owner=params.get("owner"),
                repo=params.get("repo"),
                title=params.get("title"),
                body=params.get("body"),
                labels=params.get("labels", [])
            )
        elif action == "close_issue":
            return await self._close_issue(
                owner=params.get("owner"),
                repo=params.get("repo"),
                issue_number=params.get("issue_number")
            )
        elif action == "add_comment":
            return await self._add_comment(
                owner=params.get("owner"),
                repo=params.get("repo"),
                issue_number=params.get("issue_number"),
                body=params.get("body")
            )
        elif action == "list_repos":
            return await self._list_repos()
        elif action == "list_issues":
            return await self._list_issues(
                owner=params.get("owner"),
                repo=params.get("repo")
            )
        elif action == "get_file_content":
            return await self._get_file_content(
                owner=params.get("owner"),
                repo=params.get("repo"),
                path=params.get("path"),
                ref=params.get("ref")
            )
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    
    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming GitHub webhook."""
        event_type = payload.get("action", "unknown")
        
        connector_event = ConnectorEvent(
            event_type=event_type,
            payload=payload,
            source="github"
        )
        await self.emit(connector_event)
        
        return {"success": True, "event_type": event_type}
    
    async def _create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        labels: List[str] = []
    ) -> Dict[str, Any]:
        """Create a new issue."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/repos/{owner}/{repo}/issues",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/vnd.github+json"
                    },
                    json={
                        "title": title,
                        "body": body,
                        "labels": labels
                    }
                )
                
                if response.status_code == 201:
                    data = response.json()
                    return {
                        "success": True,
                        "issue_number": data.get("number"),
                        "url": data.get("html_url")
                    }
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _close_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int
    ) -> Dict[str, Any]:
        """Close an issue."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/vnd.github+json"
                    },
                    json={"state": "closed"}
                )
                
                if response.status_code == 200:
                    return {"success": True}
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _add_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str
    ) -> Dict[str, Any]:
        """Add comment to issue or PR."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}/comments",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/vnd.github+json"
                    },
                    json={"body": body}
                )
                
                if response.status_code == 201:
                    data = response.json()
                    return {
                        "success": True,
                        "comment_id": data.get("id"),
                        "url": data.get("html_url")
                    }
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _list_repos(self) -> Dict[str, Any]:
        """List user's repositories."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/user/repos",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/vnd.github+json"
                    },
                    params={"per_page": 100}
                )
                
                if response.status_code == 200:
                    repos = [
                        {
                            "id": r["id"],
                            "name": r["name"],
                            "full_name": r["full_name"],
                            "private": r["private"]
                        }
                        for r in response.json()
                    ]
                    return {"success": True, "repos": repos}
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _list_issues(self, owner: str, repo: str) -> Dict[str, Any]:
        """List repository issues."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/repos/{owner}/{repo}/issues",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/vnd.github+json"
                    }
                )
                
                if response.status_code == 200:
                    issues = [
                        {
                            "number": i["number"],
                            "title": i["title"],
                            "state": i["state"],
                            "url": i["html_url"]
                        }
                        for i in response.json()
                    ]
                    return {"success": True, "issues": issues}
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get file content from repository."""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
                params = {"ref": ref} if ref else {}
                
                response = await client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/vnd.github+json"
                    },
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    import base64
                    content = base64.b64decode(data.get("content", "")).decode("utf-8")
                    return {
                        "success": True,
                        "content": content,
                        "sha": data.get("sha"),
                        "size": data.get("size")
                    }
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @classmethod
    def get_credentials_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "access_token": {
                    "type": "string",
                    "title": "Personal Access Token",
                    "description": "GitHub Personal Access Token with repo scope"
                }
            },
            "required": ["access_token"]
        }
