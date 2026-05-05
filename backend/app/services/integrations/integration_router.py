"""IntegrationRouter -- dispatches tool calls to external service clients.

Single entry point for all external integrations. Routes "provider.tool"
calls through governance checks before executing via the correct client.

Flow:
    1. Parse "gmail.send_email" into provider="gmail", tool="send_email"
    2. **PR-1 phase-2 read-only gate** -- block write tools when
       ``settings.integrations_phase2_readonly`` is True (the supervised
       work operator default).
    3. Look up ConnectorInstance for this provider + user (+ owner_email
       when caller pinned it -- founder vs agent account).
    4. Check per-tool permission (ALWAYS_ALLOW / ASK_EACH_TIME / BLOCK)
    5. Decrypt credentials from vault
    6. Instantiate client and execute tool
    7. Log to audit trail (``integration.tool_invocation``) -- always,
       both on allow and on block.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import ConnectorStatus, PermissionLevel
from app.core.exceptions import ApprovalRequiredError
from app.core.logging import get_logger
from app.core.vault import decrypt_dict
from app.models.connections import Connector, ConnectorInstance, ConnectorPermission
from app.services.audit import AuditService
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

# ── Sprint-11 PR-1 read-only gate ────────────────────────────────────
#
# Per-provider set of tool names that mutate external state. Phase 2
# (the supervised-work-operator floor) blocks every entry in this map.
# Phase 3 (controlled external execution after approval queue lands)
# will enable individual entries through the ApprovalQueue, never by
# flipping the flag wholesale.
#
# Adding a new write tool? Add it here AND add it to the provider's
# client.TOOLS map. If you forget to list it here, the router cannot
# distinguish a read tool from a write tool and will let it through --
# the test_integrations_readonly suite asserts the two stay in sync.
WRITE_TOOLS: dict[str, set[str]] = {
    "gmail": {"send_email", "create_draft"},
    "google-calendar": {"create_event", "update_event"},
    "calendar": {"create_event", "update_event"},  # alias
    "notion": {"create_page"},
}


class IntegrationError(Exception):
    """Raised when an integration tool call fails."""


class PermissionDeniedError(IntegrationError):
    """Raised when a tool is blocked by governance."""


class NotConnectedError(IntegrationError):
    """Raised when the required connector is not connected."""


def _is_write_tool(provider: str, tool_name: str) -> bool:
    """True if ``provider.tool_name`` mutates external state."""
    return tool_name in WRITE_TOOLS.get(provider, set())


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
            owner_email="masoud.masoori@mas-ai.co",  # PR-1 pin
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
        owner_email: str | None = None,
    ) -> dict[str, Any]:
        """Execute a tool call on an external service.

        Args:
            provider: Provider slug (e.g. "gmail", "notion").
            tool_name: Tool name (e.g. "send_email", "search_pages").
            params: Tool-specific parameters.
            user_id: ID of the user making the request.
            tenant_id: Tenant ID for multi-tenant isolation.
            skip_permission_check: If True, skip per-tool ConnectorPermission
                check (heartbeat / autopilot). The phase-2 read-only gate
                is NOT skipped -- write tools are blocked unconditionally
                when the flag is on.
            owner_email: Pin which connected account to dispatch against.
                Required when more than one ConnectorInstance is connected
                for the (provider, user, tenant) triple -- e.g. the founder
                holds both ``masoud.masoori@mas-ai.co`` and
                ``daena@mas-ai.co``. Optional when only one instance is
                connected (legacy callers stay working).

        Returns:
            Tool result dict.

        Raises:
            NotConnectedError: Provider not connected for this owner_email.
            PermissionDeniedError: Tool is blocked by phase-2 gate or by
                ConnectorPermission row.
            IntegrationError: Tool execution failed.
        """
        settings = get_settings()
        audit = AuditService(self.db)

        # 0. Resolve provider / tool early so audit rows always carry it
        client_class = PROVIDER_REGISTRY.get(provider)
        if client_class is None:
            raise IntegrationError(
                f"Unknown provider: {provider}. "
                f"Available: {', '.join(PROVIDER_REGISTRY.keys())}"
            )

        # 1. Phase-2 read-only gate. Fires before any DB lookup so a
        #    misconfigured-but-connected account can't slip a write
        #    through on a transient permission read failure.
        if (
            settings.integrations_phase2_readonly
            and _is_write_tool(provider, tool_name)
        ):
            await audit.log_decision(
                tenant_id=tenant_id,
                actor_id=user_id,
                actor_type="USER",
                action_type="integration.tool_invocation",
                action_params={
                    "provider": provider,
                    "tool_name": tool_name,
                    "owner_email": (owner_email or "").lower() or None,
                    "outcome": "blocked",
                    "blocked_reason": "write_disabled_phase2",
                    "read_only": True,
                    "is_write_tool": True,
                },
                result="BLOCKED",
                risk_level="HIGH",
                governance_tier=3,
            )
            await self.db.commit()
            raise PermissionDeniedError(
                f"write_disabled_phase2: {provider}.{tool_name} cannot be "
                f"dispatched while INTEGRATIONS_PHASE2_READONLY is on. "
                f"Phase 3 will unlock writes through the approval queue."
            )

        # 2. Find connected instance, optionally pinned by owner_email
        try:
            instance = await self._get_connected_instance(
                provider, user_id, tenant_id, owner_email=owner_email,
            )
        except NotConnectedError as exc:
            await audit.log_decision(
                tenant_id=tenant_id,
                actor_id=user_id,
                actor_type="USER",
                action_type="integration.tool_invocation",
                action_params={
                    "provider": provider,
                    "tool_name": tool_name,
                    "owner_email": (owner_email or "").lower() or None,
                    "outcome": "blocked",
                    "blocked_reason": "not_connected",
                    "read_only": not _is_write_tool(provider, tool_name),
                },
                result="BLOCKED",
                risk_level="LOW",
                governance_tier=1,
            )
            await self.db.commit()
            raise

        # 3. Check ConnectorPermission row (per-tool Allow/Ask/Block)
        if not skip_permission_check:
            permission = await self._check_permission(instance.id, tool_name)
            if permission == PermissionLevel.BLOCK.value:
                await audit.log_decision(
                    tenant_id=tenant_id,
                    actor_id=user_id,
                    actor_type="USER",
                    action_type="integration.tool_invocation",
                    action_params={
                        "provider": provider,
                        "tool_name": tool_name,
                        "owner_email": (instance.owner_email or "").lower() or None,
                        "outcome": "blocked",
                        "blocked_reason": "permission_block",
                        "read_only": not _is_write_tool(provider, tool_name),
                    },
                    result="BLOCKED",
                    risk_level="LOW",
                    governance_tier=2,
                )
                await self.db.commit()
                raise PermissionDeniedError(
                    f"Tool '{provider}.{tool_name}' is blocked. "
                    f"Update permissions in Daena Settings > Connections."
                )
            if permission == PermissionLevel.ASK_EACH_TIME.value:
                await audit.log_decision(
                    tenant_id=tenant_id,
                    actor_id=user_id,
                    actor_type="USER",
                    action_type="integration.tool_invocation",
                    action_params={
                        "provider": provider,
                        "tool_name": tool_name,
                        "owner_email": (instance.owner_email or "").lower() or None,
                        "outcome": "approval_required",
                        "read_only": not _is_write_tool(provider, tool_name),
                    },
                    result="APPROVAL_REQUIRED",
                    risk_level="LOW",
                    governance_tier=2,
                )
                await self.db.commit()
                raise ApprovalRequiredError(
                    f"Permission required to execute {provider}.{tool_name}"
                )

        # 4. Decrypt credentials
        credentials = self._decrypt_credentials(instance)
        if not credentials:
            raise NotConnectedError(
                f"No credentials found for {provider}. "
                f"Reconnect in Daena Settings > Connections."
            )

        # 5. Auto-refresh OAuth tokens if expired
        if credentials.get("refresh_token") and credentials.get("expires_at"):
            try:
                from app.services.integrations.oauth_service import ConnectorOAuthService
                oauth_svc = ConnectorOAuthService(self.db)
                refreshed = await oauth_svc.check_and_refresh(credentials)
                if refreshed.get("access_token") != credentials.get("access_token"):
                    instance.credentials = refreshed
                    credentials = refreshed
                    logger.info("integration.token_refreshed", provider=provider)
            except Exception as refresh_exc:
                logger.warning(
                    "integration.token_refresh_failed",
                    provider=provider,
                    error=str(refresh_exc),
                )

        # 6. Instantiate client and execute
        client = client_class(credentials)
        try:
            result = await client.execute_tool(tool_name, params)
        except Exception as exc:
            await audit.log_decision(
                tenant_id=tenant_id,
                actor_id=user_id,
                actor_type="USER",
                action_type="integration.tool_invocation",
                action_params={
                    "provider": provider,
                    "tool_name": tool_name,
                    "owner_email": (instance.owner_email or "").lower() or None,
                    "outcome": "failed",
                    "blocked_reason": str(exc)[:200],
                    "read_only": not _is_write_tool(provider, tool_name),
                },
                result="FAILED",
                risk_level="LOW",
                governance_tier=2,
            )
            await self.db.commit()
            logger.error(
                "integration.tool_failed",
                provider=provider,
                tool=tool_name,
                error=str(exc),
            )
            raise IntegrationError(f"{provider}.{tool_name} failed: {exc}") from exc

        # 7. Update last_used + audit success
        instance.last_used = datetime.now(UTC)
        await audit.log_decision(
            tenant_id=tenant_id,
            actor_id=user_id,
            actor_type="USER",
            action_type="integration.tool_invocation",
            action_params={
                "provider": provider,
                "tool_name": tool_name,
                "owner_email": (instance.owner_email or "").lower() or None,
                "outcome": "executed",
                "read_only": not _is_write_tool(provider, tool_name),
            },
            result="ALLOWED",
            risk_level="LOW",
            governance_tier=1,
        )
        await self.db.commit()

        logger.info(
            "integration.tool_executed",
            provider=provider,
            tool=tool_name,
            owner_email=(instance.owner_email or "").lower() or None,
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
        owner_email: str | None = None,
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
            owner_email=owner_email,
        )

    async def list_available_tools(
        self, user_id: UUID, tenant_id: UUID,
    ) -> dict[str, Any]:
        """List all tools available to the user (connected providers only).

        Returns:
            Dict mapping provider to list of available tools with permissions
            and a ``read_only`` flag (write tools are flagged so the UI can
            grey-out the action when phase-2 is on).
        """
        settings = get_settings()
        readonly = settings.integrations_phase2_readonly
        available: dict[str, Any] = {}

        for provider_slug, client_class in PROVIDER_REGISTRY.items():
            # Deduplicate aliases (calendar = google-calendar)
            if provider_slug == "calendar":
                continue

            # When owner_email is None and the user has multiple instances,
            # we still surface tool availability for the first one -- the
            # actual dispatch will require the caller to pin owner_email.
            try:
                instance = await self._get_connected_instance(
                    provider_slug, user_id, tenant_id, owner_email=None,
                    allow_first_when_ambiguous=True,
                )
            except NotConnectedError:
                continue

            tools_info = []
            for tool_name, description in client_class.TOOLS.items():
                permission = await self._check_permission(instance.id, tool_name)
                is_write = _is_write_tool(provider_slug, tool_name)
                tools_info.append({
                    "name": tool_name,
                    "qualified": f"{provider_slug}.{tool_name}",
                    "description": description,
                    "permission": permission,
                    "is_write": is_write,
                    "blocked_by_phase2_readonly": is_write and readonly,
                })

            available[provider_slug] = {
                "connected": True,
                "instance_id": str(instance.id),
                "owner_email": instance.owner_email,
                "tools": tools_info,
            }

        return available

    # ── Internal ──

    async def _get_connected_instance(
        self,
        provider: str,
        user_id: UUID,
        tenant_id: UUID,
        *,
        owner_email: str | None = None,
        allow_first_when_ambiguous: bool = False,
    ) -> ConnectorInstance:
        """Find the user's connected instance for a provider.

        When ``owner_email`` is provided, we filter by it (case-insensitive).
        If the (provider, user, tenant) triple resolves to multiple
        instances and no owner_email was provided, raise
        ``NotConnectedError`` with an explicit
        ``owner_email_required`` message -- unless
        ``allow_first_when_ambiguous`` is True (used by
        ``list_available_tools`` purely for surface enumeration).
        """
        connector_name_map = {
            "gmail": "Gmail",
            "google-calendar": "Google Calendar",
            "calendar": "Google Calendar",
            "notion": "Notion",
        }
        connector_name = connector_name_map.get(provider, provider.title())

        result = await self.db.execute(
            select(Connector).where(Connector.name == connector_name)
        )
        connector = result.scalar_one_or_none()
        if connector is None:
            raise NotConnectedError(f"Connector '{connector_name}' not found in catalog")

        stmt = (
            select(ConnectorInstance)
            .where(ConnectorInstance.connector_id == connector.id)
            .where(ConnectorInstance.user_id == user_id)
            .where(ConnectorInstance.tenant_id == tenant_id)
            .where(ConnectorInstance.status == ConnectorStatus.CONNECTED.value)
        )
        result = await self.db.execute(stmt)
        instances = list(result.scalars().all())

        if not instances:
            raise NotConnectedError(
                f"{connector_name} is not connected. "
                f"Connect it in Daena Settings > Connections."
            )

        if owner_email:
            target = owner_email.strip().lower()
            matched = [
                i for i in instances
                if (i.owner_email or "").strip().lower() == target
            ]
            if not matched:
                raise NotConnectedError(
                    f"{connector_name} is not connected for owner_email "
                    f"'{owner_email}'. Either connect that account, or pass "
                    f"a different owner_email."
                )
            return matched[0]

        # No owner_email pin. One instance => use it. Multiple => ambiguous.
        if len(instances) == 1:
            return instances[0]
        if allow_first_when_ambiguous:
            return instances[0]
        raise NotConnectedError(
            f"owner_email_required: {connector_name} has "
            f"{len(instances)} connected accounts. Pass owner_email to "
            f"pick which one to dispatch against."
        )

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
