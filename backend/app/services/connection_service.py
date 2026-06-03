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
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
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
            # Non-secret presence flag so the UI can render "configured"
            # without ever receiving the raw secret values (SEC-01).
            "has_credentials": bool(inst.credentials),
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

    @staticmethod
    def _auth_type_value(connector: Connector) -> str:
        """Normalize the mixed catalog auth_type spellings."""
        return str(connector.auth_type or "").strip().lower()

    @classmethod
    def _is_no_auth_connector(cls, connector: Connector) -> bool:
        """Return True for connectors that are callable without account auth."""
        if cls._auth_type_value(connector) not in {"none", "no_auth", "no-auth"}:
            return False
        schema = connector.config_schema if isinstance(connector.config_schema, dict) else {}
        return schema.get("callable_without_auth") is True

    @classmethod
    def _status_for_install(cls, connector: Connector, credentials: dict | None = None) -> str:
        """Legacy heuristic: credentials-presence -> 'connected'.

        Phase 4b PR 2 (ADR-002 D-010): when ``USE_CONNECTION_REGISTRY_V2``
        is True, callers MUST instead route through ``_status_via_v2``
        below, which derives status from the V2 truth dimensions
        (callable / authenticated / reachable) rather than just
        "have we stored credentials." This stays as the legacy
        fallback for the soak window.

        OAuth/API-key/token connectors without credentials are only
        installed. They become connected after OAuth/token setup succeeds.
        No-auth connectors only become connected immediately when the
        catalog explicitly says Daena has a callable backend adapter.
        """
        if cls._is_no_auth_connector(connector):
            return ConnectorStatus.CONNECTED.value
        if credentials:
            return ConnectorStatus.CONNECTED.value
        return ConnectorStatus.INSTALLED.value

    async def _status_via_v2(
        self,
        connector: Connector,
        *,
        tenant_id: UUID,
        user_id: UUID,
        credentials: dict | None = None,
    ) -> str:
        """V2-backed status (Phase 4b PR 2, ADR-002 D-010).

        When ``USE_CONNECTION_REGISTRY_V2`` is True, derives the legacy
        status from the V2 row's derived label instead of the
        credential-presence heuristic. Falls back to legacy
        ``_status_for_install`` when:
          * the flag is off
          * no V2 row exists yet (nothing to derive from)
          * any V2 lookup error occurs (legacy stays operational)
        """
        from app.services.connection_v2.legacy_bridge import (
            derive_legacy_status_from_v2,
            is_v2_enabled,
        )

        if not is_v2_enabled():
            return self._status_for_install(connector, credentials)
        v2_status = await derive_legacy_status_from_v2(
            db=self.db,
            connector=connector,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        if v2_status is not None:
            return v2_status
        return self._status_for_install(connector, credentials)

    async def _mirror_to_v2(
        self,
        connector: Connector,
        *,
        tenant_id: UUID,
        user_id: UUID,
    ) -> None:
        """Mirror a legacy install/connect into a V2 ConnectionV2 row.

        No-op when the V2 flag is off. Failure is logged + swallowed
        so the legacy path always succeeds.
        """
        from app.services.connection_v2.legacy_bridge import (
            is_v2_enabled,
            mirror_legacy_install,
        )

        if not is_v2_enabled():
            return
        await mirror_legacy_install(
            db=self.db,
            connector=connector,
            tenant_id=tenant_id,
            user_id=user_id,
        )

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
        connector = await self.get_connector(connector_id)

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

        # Phase 4b PR 2: mirror to V2 BEFORE writing legacy row, so the
        # V2-derived status is queryable when we set instance.status.
        await self._mirror_to_v2(
            connector, tenant_id=tenant_id, user_id=user_id,
        )
        status = await self._status_via_v2(
            connector, tenant_id=tenant_id, user_id=user_id, credentials=credentials,
        )

        instance = ConnectorInstance(
            connector_id=connector_id,
            user_id=user_id,
            tenant_id=tenant_id,
            credentials=encrypted_creds,
            status=status,
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
        # SEC-01: never echo raw decrypted credentials in an HTTP response,
        # even right after the user submits them. has_credentials signals
        # success; internal flows decrypt at the point of use.
        return self._instance_to_dict(instance, include_credentials=False)

    async def install(
        self,
        *,
        connector_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
    ) -> dict:
        """Install a connector locally without asking for auth.

        This is idempotent by design so the frontend can run
        "install recommended" safely. It does not claim the connector is
        connected unless the connector has no auth requirement.
        """
        connector = await self.get_connector(connector_id)

        existing_result = await self.db.execute(
            select(ConnectorInstance)
            .where(ConnectorInstance.connector_id == connector_id)
            .where(ConnectorInstance.user_id == user_id)
            .where(ConnectorInstance.tenant_id == tenant_id)
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            if existing.status == ConnectorStatus.DISCONNECTED.value:
                # Re-install of a previously-disconnected row: route
                # through V2 if the flag is on.
                await self._mirror_to_v2(
                    connector, tenant_id=tenant_id, user_id=user_id,
                )
                existing.status = await self._status_via_v2(
                    connector, tenant_id=tenant_id, user_id=user_id,
                )
                existing.credentials = None
                await self.db.commit()
                await self.db.refresh(existing)
            return self._instance_to_dict(existing)

        # Mirror to V2 first so derive_status_from_v2 has a row to query.
        await self._mirror_to_v2(
            connector, tenant_id=tenant_id, user_id=user_id,
        )
        status = await self._status_via_v2(
            connector, tenant_id=tenant_id, user_id=user_id,
        )

        instance = ConnectorInstance(
            connector_id=connector_id,
            user_id=user_id,
            tenant_id=tenant_id,
            credentials=None,
            status=status,
        )
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)

        logger.info(
            "connector_installed",
            instance_id=str(instance.id),
            connector_id=str(connector_id),
            user_id=str(user_id),
            status=instance.status,
        )
        return self._instance_to_dict(instance)

    async def connect_account(
        self,
        *,
        instance_id: UUID,
        tenant_id: UUID,
        credentials: dict,
    ) -> dict:
        """Attach credentials to an installed connector instance."""
        if not credentials:
            raise ValidationError("Credentials are required to connect this account")

        instance = await self._get_or_404(
            ConnectorInstance, instance_id, "Connector instance",
            tenant_id=tenant_id,
        )
        # Load connector so no-auth rows can still normalize correctly.
        connector = await self.get_connector(instance.connector_id)
        instance.credentials = encrypt_dict(credentials)
        # Phase 4b PR 2: route through V2 if flag is on; legacy fallback otherwise.
        await self._mirror_to_v2(
            connector, tenant_id=tenant_id, user_id=instance.user_id,
        )
        instance.status = await self._status_via_v2(
            connector,
            tenant_id=tenant_id,
            user_id=instance.user_id,
            credentials=credentials,
        )
        await self.db.commit()
        await self.db.refresh(instance)

        logger.info(
            "connector_account_connected",
            instance_id=str(instance.id),
            connector_id=str(instance.connector_id),
        )
        # SEC-01: never echo raw decrypted credentials in an HTTP response,
        # even right after the user submits them. has_credentials signals
        # success; internal flows decrypt at the point of use.
        return self._instance_to_dict(instance, include_credentials=False)

    async def install_recommended(
        self,
        *,
        user_id: UUID,
        tenant_id: UUID,
    ) -> list[dict]:
        """Install the default useful connector set without credentials."""
        recommended_names = [
            "GitHub",
            "Gmail",
            "Google Drive",
            "Google Calendar",
            "Slack",
            "Notion",
            "Figma",
            "Canva",
            "Linear",
            "Vercel",
            "Cloudflare",
            "Sentry",
            "Stripe",
            "HubSpot",
        ]
        rows = (
            await self.db.execute(
                select(Connector).where(Connector.name.in_(recommended_names))
            )
        ).scalars().all()
        by_name = {row.name: row for row in rows}

        installed: list[dict] = []
        for name in recommended_names:
            connector = by_name.get(name)
            if connector is None:
                continue
            installed.append(
                await self.install(
                    connector_id=connector.id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                )
            )
        return installed

    async def disconnect(
        self,
        instance_id: UUID,
        tenant_id: UUID,
        *,
        confirm: bool = False,
        actor_user_id: UUID | None = None,
    ) -> dict:
        """Disconnect a connector instance (soft — sets status).

        PR-CONN-OAUTH-REFRESH-DISCONNECT (2026-05-03):
        ``confirm=True`` is now REQUIRED. The endpoint layer surfaces
        a 400 with reason ``confirmation_required`` if the operator
        attempts to disconnect without explicit consent.

        Best-effort revoke at the provider runs BEFORE local creds are
        cleared. Network or HTTP failure is logged but never blocks
        disconnect (operator intent is "stop using this token", not
        "guarantee server-side revoke" -- the provider may not support
        an RFC-7009 revoke endpoint at all).

        Audit row written either way (with revoke outcome captured).
        """
        if not confirm:
            raise ValueError(
                "confirmation_required: disconnect must be called with "
                "confirm=True. Pass {\"confirm\": true} in the request body."
            )

        instance = await self._get_or_404(
            ConnectorInstance, instance_id, "Connector instance",
            tenant_id=tenant_id,
        )

        # Best-effort provider revoke BEFORE clearing local creds.
        revoke_outcome: dict = {"attempted": False, "reason": "no_token"}
        try:
            from app.core.vault import decrypt_dict
            from app.services.integrations.oauth_service import (
                ConnectorOAuthService,
            )
            decrypted = (
                decrypt_dict(instance.credentials)
                if instance.credentials
                else {}
            )
            access_token = decrypted.get("access_token")
            if access_token:
                provider = (instance.connector_id or "").split("-")[0] or "gmail"
                # Allow exact provider match first.
                if instance.connector_id in ("gmail", "github", "slack",
                                             "figma", "canva",
                                             "google-calendar", "google-drive"):
                    provider = instance.connector_id
                oauth = ConnectorOAuthService(self.db)
                outcome = await oauth.revoke_token(provider, access_token)
                revoke_outcome = {"attempted": True, **outcome}
        except Exception as exc:
            logger.warning(
                "connector_disconnect.revoke_skipped",
                instance_id=str(instance_id),
                error=str(exc),
            )
            revoke_outcome = {"attempted": False, "reason": "exception"}

        instance.status = ConnectorStatus.DISCONNECTED.value
        instance.credentials = None  # Clear credentials on disconnect
        await self.db.commit()
        await self.db.refresh(instance)

        # Audit -- best-effort, failure must not block the disconnect.
        try:
            from app.services.audit import AuditService
            audit = AuditService(self.db)
            await audit.log_decision(
                tenant_id=tenant_id,
                actor_id=actor_user_id,
                actor_type="USER",
                action_type="connector.disconnect",
                action_params={
                    "instance_id": str(instance_id),
                    "connector_id": str(instance.connector_id),
                    "revoke_attempted": revoke_outcome.get("attempted", False),
                    "revoke_reason": revoke_outcome.get("reason", ""),
                    # Never log token values; only outcome metadata.
                },
                result="ALLOWED",
                risk_level="LOW",
                governance_tier=2,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "connector_disconnect.audit_failed",
                instance_id=str(instance_id),
                error=str(exc),
            )

        logger.info(
            "connector_disconnected",
            instance_id=str(instance_id),
            revoke=revoke_outcome,
        )
        return self._instance_to_dict(instance)

    async def archive(
        self,
        instance_id: UUID,
        tenant_id: UUID,
        *,
        confirm: bool = False,
        actor_user_id: UUID | None = None,
    ) -> dict:
        """Archive a connector instance (soft -- preserves the row).

        PR-CONN-OAUTH-REFRESH-DISCONNECT (2026-05-03).

        Like disconnect but moves to ARCHIVED status so default list
        queries hide the instance. Useful for tidying up old OAuth
        connections without losing audit history. Per founder rule
        ``never delete``, archive is the strongest soft-removal lane.
        """
        if not confirm:
            raise ValueError(
                "confirmation_required: archive must be called with "
                "confirm=True."
            )
        instance = await self._get_or_404(
            ConnectorInstance, instance_id, "Connector instance",
            tenant_id=tenant_id,
        )
        instance.status = ConnectorStatus.ARCHIVED.value
        instance.credentials = None
        await self.db.commit()
        await self.db.refresh(instance)
        try:
            from app.services.audit import AuditService
            audit = AuditService(self.db)
            await audit.log_decision(
                tenant_id=tenant_id,
                actor_id=actor_user_id,
                actor_type="USER",
                action_type="connector.archive",
                action_params={
                    "instance_id": str(instance_id),
                    "connector_id": str(instance.connector_id),
                },
                result="ALLOWED",
                risk_level="LOW",
                governance_tier=2,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "connector_archive.audit_failed",
                instance_id=str(instance_id), error=str(exc),
            )
        logger.info("connector_archived", instance_id=str(instance_id))
        return self._instance_to_dict(instance)

    async def refresh_token_for_instance(
        self,
        instance_id: UUID,
        tenant_id: UUID,
        *,
        actor_user_id: UUID | None = None,
    ) -> dict:
        """Operator-triggered OAuth token refresh.

        PR-CONN-OAUTH-REFRESH-DISCONNECT (2026-05-03).

        Loads the instance, decrypts current credentials, asks the
        OAuth service to refresh against the provider, encrypts and
        re-stores. Returns refreshed metadata WITHOUT exposing tokens.

        Returns:
            {"success": bool, "expires_at": iso8601 | None, "reason": str}
        """
        from app.core.vault import decrypt_dict, encrypt_dict
        from app.services.integrations.oauth_service import (
            ConnectorOAuthService,
        )
        from app.services.audit import AuditService

        instance = await self._get_or_404(
            ConnectorInstance, instance_id, "Connector instance",
            tenant_id=tenant_id,
        )
        decrypted = (
            decrypt_dict(instance.credentials)
            if instance.credentials else {}
        )
        refresh_token_value = decrypted.get("refresh_token")
        if not refresh_token_value:
            return {"success": False, "reason": "no_refresh_token"}

        provider = instance.connector_id or "gmail"
        if provider not in (
            "gmail", "github", "slack", "figma", "canva",
            "google-calendar", "google-drive",
        ):
            provider = (instance.connector_id or "").split("-")[0] or "gmail"

        try:
            oauth = ConnectorOAuthService(self.db)
            new_tokens = await oauth.refresh_token(
                refresh_token_value, provider=provider,
            )
            decrypted["access_token"] = new_tokens["access_token"]
            decrypted["expires_at"] = new_tokens["expires_at"]
            instance.credentials = encrypt_dict(decrypted)
            instance.status = ConnectorStatus.CONNECTED.value
            await self.db.commit()
            await self.db.refresh(instance)
            outcome = {
                "success": True,
                "expires_at": new_tokens["expires_at"],
                "reason": "ok",
            }
        except Exception as exc:
            logger.warning(
                "connector_refresh.failed",
                instance_id=str(instance_id),
                provider=provider,
                error=str(exc),
            )
            outcome = {
                "success": False,
                "expires_at": None,
                "reason": f"refresh_failed: {str(exc)[:120]}",
            }

        try:
            audit = AuditService(self.db)
            await audit.log_decision(
                tenant_id=tenant_id,
                actor_id=actor_user_id,
                actor_type="USER",
                action_type="connector.refresh_token",
                action_params={
                    "instance_id": str(instance_id),
                    "connector_id": str(instance.connector_id),
                    "provider": provider,
                    "outcome": outcome["reason"],
                    # Never log token values.
                },
                result="ALLOWED" if outcome["success"] else "BLOCKED",
                risk_level="LOW",
                governance_tier=2,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "connector_refresh.audit_failed",
                instance_id=str(instance_id), error=str(exc),
            )
        return outcome

    async def get_instance(
        self, instance_id: UUID, tenant_id: UUID
    ) -> dict:
        """Get a connector instance by ID.

        SEC-01: does NOT return decrypted credentials. This feeds the
        GET /instances/{id} HTTP response, which any same-tenant
        authenticated user can call; returning raw secrets there leaked
        OAuth/API credentials. The response carries has_credentials
        (non-secret presence flag) instead. Internal flows that genuinely
        need the secret decrypt at the point of use, not via this dict.
        """
        instance = await self._get_or_404(
            ConnectorInstance, instance_id, "Connector instance",
            tenant_id=tenant_id,
        )
        return self._instance_to_dict(instance, include_credentials=False)

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
        else:
            # PR-CONN-OAUTH-REFRESH-DISCONNECT: by default hide ARCHIVED
            # instances. Operator can pass ?status=ARCHIVED explicitly to
            # see them (or "any" via a future ?include_archived=true).
            stmt = stmt.where(
                ConnectorInstance.status != ConnectorStatus.ARCHIVED.value,
            )
        stmt = stmt.order_by(ConnectorInstance.created_at.desc())

        result = await self._paginate(
            stmt, ConnectorInstance, page, page_size,
            response_schema=ConnectorInstanceResponse,
        )

        # Post-process: extract account_identity from each instance's
        # credentials JSONB. We look up the ORM rows again (cheap, same
        # page size) so we can read the credentials field without
        # re-running the whole query.
        def _item_get(item: object, key: str) -> object | None:
            if isinstance(item, dict):
                return item.get(key)
            return getattr(item, key, None)

        def _item_set(item: object, key: str, value: object) -> None:
            if isinstance(item, dict):
                item[key] = value
            else:
                setattr(item, key, value)

        instance_ids = [
            UUID(str(item_id))
            for item in result.data
            if (item_id := _item_get(item, "id")) is not None
        ]
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
                item_id = _item_get(item, "id")
                item_key = str(item_id) if item_id else ""
                if item_key and item_key in identity_by_id:
                    _item_set(item, "account_identity", identity_by_id[item_key])

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
