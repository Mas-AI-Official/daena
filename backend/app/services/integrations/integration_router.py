"""IntegrationRouter -- dispatches tool calls to external service clients.

Single entry point for all external integrations. Routes "provider.tool"
calls through governance checks before executing via the correct client.

Flow:
    1. Parse "gmail.send_email" into provider="gmail", tool="send_email"
    2. Look up ConnectorInstance for this provider + user
    3. Check per-tool permission (ALWAYS_ALLOW / ASK_EACH_TIME / BLOCK)
    4. Decrypt credentials from vault
    5. Instantiate client and execute tool
    6. Log to audit trail
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ConnectorStatus, PermissionLevel
from app.core.logging import get_logger
from app.core.vault import decrypt_dict
from app.models.connections import Connector, ConnectorInstance, ConnectorPermission
from app.services.integrations.calendar_client import CalendarClient
from app.services.integrations.gmail_client import GmailClient
from app.services.integrations.notion_client import NotionClient

logger = get_logger(__name__)

# Maps provider slug to (client class, connector name pattern)
PROVIDER_REGISTRY: dict[str, type] = {
    "gmail": GmailClient,
    "google-calendar": CalendarClient,
    "calendar": CalendarClient,
    "notion": NotionClient,
}

# All available tools across all providers
ALL_TOOLS: dict[str, dict[str, str]] = {
    "gmail": GmailClient.TOOLS,
    "google-calendar": CalendarClient.TOOLS,
    "calendar": CalendarClient.TOOLS,
    "notion": NotionClient.TOOLS,
}


class IntegrationError(Exception):
    """Raised when an integration tool call fails."""


class PermissionDeniedError(IntegrationError):
    """Raised when a tool is blocked by governance."""


class NotConnectedError(IntegrationError):
    """Raised when the required connector is not connected."""


class IntegrationRouter:
    """Routes tool calls to external service clients through governance.

    Usage::

        router = IntegrationRouter(db)
        result = await router.execute(
            provider="gmail",
            tool_name="search_emails",
            params={"query": "is:unread"},
            user_id=user_id,
            tenant_id=tenant_id,
        )
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def execute(
        self,
        *,
        provider: str,
        tool_name: str,
        params: dict[str, Any],
        user_id: UUID,
        tenant_id: UUID,
        skip_permission_check: bool = False,
    ) -> dict[str, Any]:
        """Execute a tool call on an external service.

        Args:
            provider: Provider slug (e.g. "gmail", "notion").
            tool_name: Tool name (e.g. "send_email", "search_pages").
            params: Tool-specific parameters.
            user_id: ID of the user making the request.
            tenant_id: Tenant ID for multi-tenant isolation.
            skip_permission_check: If True, skip governance check
                (used for heartbeat/autopilot with pre-approved tasks).

        Returns:
            Tool result dict.

        Raises:
            NotConnectedError: Provider not connected.
            PermissionDeniedError: Tool is blocked by permissions.
            IntegrationError: Tool execution failed.
        """
        # Resolve provider
        client_class = PROVIDER_REGISTRY.get(provider)
        if client_class is None:
            raise IntegrationError(
                f"Unknown provider: {provider}. "
                f"Available: {', '.join(PROVIDER_REGISTRY.keys())}"
            )

        # Find connected instance
        instance = await self._get_connected_instance(provider, user_id, tenant_id)

        # Check permission
        if not skip_permission_check:
            permission = await self._check_permission(instance.id, tool_name)
            if permission == PermissionLevel.BLOCK.value:
                raise PermissionDeniedError(
                    f"Tool '{provider}.{tool_name}' is blocked. "
                    f"Update permissions in Daena Settings > Connections."
                )
            if permission == PermissionLevel.ASK_EACH_TIME.value:
                # Return a governance prompt instead of executing
                return {
                    "status": "approval_required",
                    "provider": provider,
                    "tool": tool_name,
                    "params": params,
                    "message": f"Permission required to execute {provider}.{tool_name}",
                    "governance_tier": 3,
                }

        # Decrypt credentials
        credentials = self._decrypt_credentials(instance)
        if not credentials:
            raise NotConnectedError(
                f"No credentials found for {provider}. "
                f"Reconnect in Daena Settings > Connections."
            )

        # Instantiate client and execute
        client = client_class(credentials)
        try:
            result = await client.execute_tool(tool_name, params)
        except Exception as exc:
            logger.error(
                "integration.tool_failed",
                provider=provider,
                tool=tool_name,
                error=str(exc),
            )
            raise IntegrationError(f"{provider}.{tool_name} failed: {exc}") from exc

        # Update last_used timestamp
        instance.last_used = datetime.now(UTC)
        await self.db.commit()

        logger.info(
            "integration.tool_executed",
            provider=provider,
            tool=tool_name,
            user_id=str(user_id),
        )

        return result

    async def execute_qualified(
        self,
        qualified_tool: str,
        params: dict[str, Any],
        user_id: UUID,
        tenant_id: UUID,
        skip_permission_check: bool = False,
    ) -> dict[str, Any]:
        """Execute a tool using qualified name like "gmail.send_email".

        Convenience wrapper that splits the qualified name.
        """
        parts = qualified_tool.split(".", 1)
        if len(parts) != 2:
            raise IntegrationError(
                f"Invalid tool name '{qualified_tool}'. "
                f"Expected format: 'provider.tool_name'"
            )
        return await self.execute(
            provider=parts[0],
            tool_name=parts[1],
            params=params,
            user_id=user_id,
            tenant_id=tenant_id,
            skip_permission_check=skip_permission_check,
        )

    async def list_available_tools(
        self, user_id: UUID, tenant_id: UUID,
    ) -> dict[str, Any]:
        """List all tools available to the user (connected providers only).

        Returns:
            Dict mapping provider to list of available tools with permissions.
        """
        available: dict[str, Any] = {}

        for provider_slug, client_class in PROVIDER_REGISTRY.items():
            # Deduplicate aliases (calendar = google-calendar)
            if provider_slug == "calendar":
                continue

            try:
                instance = await self._get_connected_instance(
                    provider_slug, user_id, tenant_id,
                )
            except NotConnectedError:
                continue

            tools_info = []
            for tool_name, description in client_class.TOOLS.items():
                permission = await self._check_permission(instance.id, tool_name)
                tools_info.append({
                    "name": tool_name,
                    "qualified": f"{provider_slug}.{tool_name}",
                    "description": description,
                    "permission": permission,
                })

            available[provider_slug] = {
                "connected": True,
                "instance_id": str(instance.id),
                "tools": tools_info,
            }

        return available

    # ── Internal ──

    async def _get_connected_instance(
        self, provider: str, user_id: UUID, tenant_id: UUID,
    ) -> ConnectorInstance:
        """Find the user's connected instance for a provider."""
        # Map provider slug to connector name
        connector_name_map = {
            "gmail": "Gmail",
            "google-calendar": "Google Calendar",
            "calendar": "Google Calendar",
            "notion": "Notion",
        }
        connector_name = connector_name_map.get(provider, provider.title())

        # Find connector by name
        result = await self.db.execute(
            select(Connector).where(Connector.name == connector_name)
        )
        connector = result.scalar_one_or_none()
        if connector is None:
            raise NotConnectedError(f"Connector '{connector_name}' not found in catalog")

        # Find user's instance
        result = await self.db.execute(
            select(ConnectorInstance)
            .where(ConnectorInstance.connector_id == connector.id)
            .where(ConnectorInstance.user_id == user_id)
            .where(ConnectorInstance.tenant_id == tenant_id)
            .where(ConnectorInstance.status == ConnectorStatus.CONNECTED.value)
        )
        instance = result.scalar_one_or_none()
        if instance is None:
            raise NotConnectedError(
                f"{connector_name} is not connected. "
                f"Connect it in Daena Settings > Connections."
            )
        return instance

    async def _check_permission(
        self, instance_id: UUID, tool_name: str,
    ) -> str:
        """Get effective permission level for a tool."""
        result = await self.db.execute(
            select(ConnectorPermission)
            .where(ConnectorPermission.instance_id == instance_id)
            .where(ConnectorPermission.tool_name == tool_name)
        )
        perm = result.scalar_one_or_none()
        if perm is None:
            return PermissionLevel.ASK_EACH_TIME.value
        return perm.permission_level

    @staticmethod
    def _decrypt_credentials(instance: ConnectorInstance) -> dict | None:
        """Decrypt credentials from a ConnectorInstance."""
        if not instance.credentials:
            return None
        raw = instance.credentials
        if isinstance(raw, str):
            return decrypt_dict(raw)
        if isinstance(raw, dict):
            return raw
        return None
