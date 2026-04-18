"""CMP (Connector Management Protocol) service.

Manages the lifecycle of external integrations:
- Connector catalog: what integrations are available
- Connector instances: user-specific connections with credentials
- Per-tool permissions: ALWAYS_ALLOW / ASK_EACH_TIME / BLOCK

CMP is Daena's governed alternative to MCP. Every tool invocation
through a connector goes through governance evaluation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.core.constants import ConnectorStatus, PermissionLevel
from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.vault import decrypt_dict, encrypt_dict
from app.models.connections import Connector, ConnectorInstance, ConnectorPermission
from app.services._base import BaseService

logger = get_logger(__name__)


class ConnectionService(BaseService):
    """Manages CMP connectors, instances, and permissions.

    Usage::

        svc = ConnectionService(db)

        # List available connectors
        connectors = await svc.list_connectors()

        # Connect to a connector
        instance = await svc.connect(
            connector_id=connector_id,
            user_id=user_id,
            tenant_id=tenant_id,
            credentials={"api_key": "sk-..."},
        )

        # Set tool permission
        await svc.set_tool_permission(
            instance_id=instance.id,
            tenant_id=tenant_id,
            tool_name="send_email",
            permission_level="ASK_EACH_TIME",
        )
    """

    @staticmethod
    def _connector_to_dict(conn: Connector) -> dict:
        """Convert a Connector ORM instance to a JSON-serializable dict."""
        return {
            "id": str(conn.id),
            "name": conn.name,
            "description": conn.description,
            "auth_type": conn.auth_type,
            "config_schema": conn.config_schema,
            "tools": conn.tools,
            "icon_url": conn.icon_url,
            "category": conn.category,
            "created_at": conn.created_at.isoformat() if conn.created_at else None,
            "updated_at": conn.updated_at.isoformat() if conn.updated_at else None,
        }

    @staticmethod
    def _instance_to_dict(
        inst: ConnectorInstance,
        *,
        include_credentials: bool = False,
    ) -> dict:
        """Convert a ConnectorInstance ORM instance to a JSON-serializable dict.

        Credentials are vault-encrypted at rest. When *include_credentials*
        is True, they are decrypted for the owning user. List endpoints
        should pass False (default) to avoid leaking secrets.
        """
        creds = None
        if include_credentials and inst.credentials:
            raw = inst.credentials
            if isinstance(raw, str):
                creds = decrypt_dict(raw)
            elif isinstance(raw, dict):
                # Legacy unencrypted dict still in DB
                creds = raw
        return {
            "id": str(inst.id),
            "connector_id": str(inst.connector_id),
            "user_id": str(inst.user_id),
            "tenant_id": str(inst.tenant_id),
            "status": inst.status,
            "credentials": creds,
            "last_used": inst.last_used.isoformat() if inst.last_used else None,
            "created_at": inst.created_at.isoformat() if inst.created_at else None,
            "updated_at": inst.updated_at.isoformat() if inst.updated_at else None,
        }

    @staticmethod
    def _permission_to_dict(perm: ConnectorPermission) -> dict:
        """Convert a ConnectorPermission ORM instance to a JSON-serializable dict."""
        return {
            "id": str(perm.id),
            "instance_id": str(perm.instance_id),
            "tenant_id": str(perm.tenant_id),
            "tool_name": perm.tool_name,
            "permission_level": perm.permission_level,
            "created_at": perm.created_at.isoformat() if perm.created_at else None,
            "updated_at": perm.updated_at.isoformat() if perm.updated_at else None,
        }

    # ── Connector Catalog (tenant-independent) ────────────────

    async def create_connector(
        self,
        *,
        name: str,
        auth_type: str = "API_KEY",
        description: str | None = None,
        config_schema: dict | None = None,
        tools: list[dict] | None = None,
        icon_url: str | None = None,
        category: str | None = None,
    ) -> Connector:
        """Register a new connector type.

        This defines the template — users create instances to connect.

        Raises:
            ConflictError: If a connector with this name already exists.
        """
        existing = await self.db.execute(
            select(Connector).where(Connector.name == name)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(f"Connector '{name}' already exists")

        connector = Connector(
            name=name,
            description=description,
            auth_type=auth_type,
            config_schema=config_schema or {},
            tools=tools or [],
            icon_url=icon_url,
            category=category,
        )
        self.db.add(connector)
        await self.db.commit()
        await self.db.refresh(connector)

        logger.info(
            "connector_created",
            connector_id=str(connector.id),
            name=name,
        )
        return self._connector_to_dict(connector)

    async def get_connector(self, connector_id: UUID) -> Connector:
        """Get a connector by ID (no tenant filter — catalog is global).

        Returns the raw ORM object for internal use (e.g. existence checks).
        Callers returning to API should use _connector_to_dict().
        """
        stmt = select(Connector).where(Connector.id == connector_id)
        result = await self.db.execute(stmt)
        connector = result.scalar_one_or_none()
        if connector is None:
            raise NotFoundError(f"Connector not found: {connector_id}")
        return connector

    async def list_connectors(
        self,
        *,
        category: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ):
        """List available connector types."""
        from app.schemas.connections import ConnectorResponse

        stmt = select(Connector)
        if category is not None:
            stmt = stmt.where(Connector.category == category)
        stmt = stmt.order_by(Connector.name)

        return await self._paginate(
            stmt, Connector, page, page_size,
            response_schema=ConnectorResponse,
        )

    # ── Connector Instances (per-user) ────────────────────────

    async def connect(
        self,
        *,
        connector_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        credentials: dict | None = None,
    ) -> ConnectorInstance:
        """Create a user connection to a connector.

        Each user can have at most one instance per connector within
        a tenant (enforced by unique constraint).

        Raises:
            ConflictError: If user already connected to this connector.
        """
        # Verify connector exists
        await self.get_connector(connector_id)

        # Check for existing connection
        existing = await self.db.execute(
            select(ConnectorInstance)
            .where(ConnectorInstance.connector_id == connector_id)
            .where(ConnectorInstance.user_id == user_id)
            .where(ConnectorInstance.tenant_id == tenant_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(
                "Already connected to this connector. "
                "Disconnect first to reconnect."
            )

        # Encrypt credentials before storage
        encrypted_creds = encrypt_dict(credentials) if credentials else None

        instance = ConnectorInstance(
            connector_id=connector_id,
            user_id=user_id,
            tenant_id=tenant_id,
            credentials=encrypted_creds,
            status=ConnectorStatus.CONNECTED.value,
        )
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)

        logger.info(
            "connector_connected",
            instance_id=str(instance.id),
            connector_id=str(connector_id),
            user_id=str(user_id),
        )
        return self._instance_to_dict(instance, include_credentials=True)

    async def disconnect(
        self, instance_id: UUID, tenant_id: UUID
    ) -> dict:
        """Disconnect a connector instance (soft — sets status)."""
        instance = await self._get_or_404(
            ConnectorInstance, instance_id, "Connector instance",
            tenant_id=tenant_id,
        )
        instance.status = ConnectorStatus.DISCONNECTED.value
        instance.credentials = None  # Clear credentials on disconnect
        await self.db.commit()
        await self.db.refresh(instance)

        logger.info(
            "connector_disconnected",
            instance_id=str(instance_id),
        )
        return self._instance_to_dict(instance)

    async def get_instance(
        self, instance_id: UUID, tenant_id: UUID
    ) -> dict:
        """Get a connector instance by ID (includes decrypted credentials)."""
        instance = await self._get_or_404(
            ConnectorInstance, instance_id, "Connector instance",
            tenant_id=tenant_id,
        )
        return self._instance_to_dict(instance, include_credentials=True)

    async def list_instances(
        self,
        *,
        user_id: UUID,
        tenant_id: UUID,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ):
        """List a user's connector instances.

        Session 11: post-processes each item to lift ``account_identity``
        out of the credentials JSONB and onto the top-level response so
        the UI can render "Connected as masoud.masoori@mas-ai.co"
        without having to read credentials (which are encrypted + never
        returned on list calls).
        """
        from app.schemas.connections import ConnectorInstanceResponse

        stmt = (
            select(ConnectorInstance)
            .where(ConnectorInstance.user_id == user_id)
            .where(ConnectorInstance.tenant_id == tenant_id)
        )
        if status is not None:
            stmt = stmt.where(ConnectorInstance.status == status)
        stmt = stmt.order_by(ConnectorInstance.created_at.desc())

        result = await self._paginate(
            stmt, ConnectorInstance, page, page_size,
            response_schema=ConnectorInstanceResponse,
        )

        # Post-process: extract account_identity from each instance's
        # credentials JSONB. We look up the ORM rows again (cheap, same
        # page size) so we can read the credentials field without
        # re-running the whole query.
        instance_ids = [UUID(item["id"]) for item in result.data if "id" in item]
        if instance_ids:
            id_stmt = select(ConnectorInstance).where(ConnectorInstance.id.in_(instance_ids))
            rows = (await self.db.execute(id_stmt)).scalars().all()
            identity_by_id = {}
            for row in rows:
                creds = row.credentials
                if isinstance(creds, str):
                    try:
                        creds = decrypt_dict(creds)
                    except Exception:
                        creds = None
                if isinstance(creds, dict):
                    identity_by_id[str(row.id)] = creds.get("account_identity", "") or ""
            for item in result.data:
                item_id = item.get("id")
                if item_id and item_id in identity_by_id:
                    item["account_identity"] = identity_by_id[item_id]

        return result

    async def get_credentials(
        self, instance_id: UUID, tenant_id: UUID
    ) -> dict | None:
        """Get decrypted credentials for internal use (e.g. tool execution).

        Does NOT return the full instance dict -- just the raw credentials.
        """
        instance = await self._get_or_404(
            ConnectorInstance, instance_id, "Connector instance",
            tenant_id=tenant_id,
        )
        if not instance.credentials:
            return None
        raw = instance.credentials
        if isinstance(raw, str):
            return decrypt_dict(raw)
        if isinstance(raw, dict):
            return raw
        return None

    async def touch_last_used(
        self, instance_id: UUID, tenant_id: UUID
    ) -> None:
        """Update last_used timestamp when a connector tool is invoked."""
        instance = await self._get_or_404(
            ConnectorInstance, instance_id, "Connector instance",
            tenant_id=tenant_id,
        )
        instance.last_used = datetime.now(UTC)
        await self.db.commit()

    # ── Per-tool Permissions ──────────────────────────────────

    async def set_tool_permission(
        self,
        *,
        instance_id: UUID,
        tenant_id: UUID,
        tool_name: str,
        permission_level: str = "ASK_EACH_TIME",
    ) -> ConnectorPermission:
        """Set or update permission for a specific tool.

        Creates the permission record if it doesn't exist,
        updates it if it does (upsert pattern).
        """
        # Verify instance exists and belongs to tenant
        await self._get_or_404(
            ConnectorInstance, instance_id, "Connector instance",
            tenant_id=tenant_id,
        )

        # Check for existing permission
        result = await self.db.execute(
            select(ConnectorPermission)
            .where(ConnectorPermission.instance_id == instance_id)
            .where(ConnectorPermission.tool_name == tool_name)
        )
        permission = result.scalar_one_or_none()

        if permission is not None:
            permission.permission_level = permission_level
        else:
            permission = ConnectorPermission(
                instance_id=instance_id,
                tenant_id=tenant_id,
                tool_name=tool_name,
                permission_level=permission_level,
            )
            self.db.add(permission)

        await self.db.commit()
        await self.db.refresh(permission)

        logger.info(
            "tool_permission_set",
            instance_id=str(instance_id),
            tool=tool_name,
            level=permission_level,
        )
        return self._permission_to_dict(permission)

    async def get_tool_permission(
        self, instance_id: UUID, tool_name: str
    ) -> str:
        """Get the effective permission level for a tool.

        Returns "ASK_EACH_TIME" if no explicit permission is set.
        """
        result = await self.db.execute(
            select(ConnectorPermission)
            .where(ConnectorPermission.instance_id == instance_id)
            .where(ConnectorPermission.tool_name == tool_name)
        )
        permission = result.scalar_one_or_none()
        if permission is None:
            return PermissionLevel.ASK_EACH_TIME.value
        return permission.permission_level

    async def list_permissions(
        self, instance_id: UUID, tenant_id: UUID
    ) -> list[dict]:
        """List all tool permissions for a connector instance."""
        # Verify ownership
        await self._get_or_404(
            ConnectorInstance, instance_id, "Connector instance",
            tenant_id=tenant_id,
        )

        result = await self.db.execute(
            select(ConnectorPermission)
            .where(ConnectorPermission.instance_id == instance_id)
            .order_by(ConnectorPermission.tool_name)
        )
        return [
            self._permission_to_dict(p) for p in result.scalars().all()
        ]
