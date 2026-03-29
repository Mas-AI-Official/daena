"""Session Sync -- cross-device session persistence.

Enables starting work on mobile and continuing on desktop with full context.
Tracks which devices have touched a session, serializes state per device
capabilities, and handles device transfers.
"""

from __future__ import annotations

import time
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeviceRecord:
    device_id: str
    device_type: str = "desktop"  # "desktop" | "mobile" | "cli" | "tablet"
    platform: str = "windows"     # "windows" | "ios" | "android" | "macos" | "linux"
    last_seen: float = field(default_factory=time.time)
    capabilities: list[str] = field(default_factory=lambda: ["browser", "file_system"])


@dataclass
class PersistentSession:
    session_id: str
    user_id: str
    devices: list[DeviceRecord] = field(default_factory=list)
    active_tools: list[str] = field(default_factory=list)
    agent_state: dict[str, Any] = field(default_factory=dict)
    primary_device_id: str | None = None
    last_active_at: float = field(default_factory=time.time)
    priority: str = "P1"
    message_count: int = 0
    created_at: float = field(default_factory=time.time)


class SessionSyncService:
    """Manages cross-device session persistence.

    Usage:
        svc = SessionSyncService()
        session = svc.create_session("user-1", "device-desktop-1")
        svc.join_session(session.session_id, device)
        state = svc.sync_state(session.session_id)
    """

    def __init__(self) -> None:
        self._sessions: dict[str, PersistentSession] = {}
        self._lock = threading.Lock()

    def create_session(
        self,
        user_id: str,
        device: DeviceRecord,
    ) -> PersistentSession:
        """Create a new persistent session from a device."""
        session_id = str(uuid.uuid4())
        session = PersistentSession(
            session_id=session_id,
            user_id=user_id,
            devices=[device],
            primary_device_id=device.device_id,
        )
        with self._lock:
            self._sessions[session_id] = session
        return session

    def join_session(
        self,
        session_id: str,
        device: DeviceRecord,
    ) -> PersistentSession | None:
        """Another device joins an existing session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            # Update or add device
            existing = next(
                (d for d in session.devices if d.device_id == device.device_id),
                None,
            )
            if existing:
                existing.last_seen = time.time()
                existing.capabilities = device.capabilities
            else:
                session.devices.append(device)
            session.last_active_at = time.time()
            return session

    def sync_state(self, session_id: str) -> PersistentSession | None:
        """Get the latest session state."""
        with self._lock:
            return self._sessions.get(session_id)

    def transfer_primary(
        self,
        session_id: str,
        to_device_id: str,
    ) -> bool:
        """Transfer the primary (active) device for a session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            device = next(
                (d for d in session.devices if d.device_id == to_device_id),
                None,
            )
            if not device:
                return False
            session.primary_device_id = to_device_id
            device.last_seen = time.time()
            session.last_active_at = time.time()
            return True

    def update_tools(
        self,
        session_id: str,
        active_tools: list[str],
    ) -> bool:
        """Update the active tools list for a session (from TLM)."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            session.active_tools = list(active_tools)
            return True

    def update_agent_state(
        self,
        session_id: str,
        agent_state: dict[str, Any],
    ) -> bool:
        """Update serialized agent context for a session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            session.agent_state = dict(agent_state)
            return True

    def serialize_for_device(
        self,
        session_id: str,
        device_type: str,
    ) -> dict[str, Any] | None:
        """Serialize session state adapted for a device type.

        Mobile gets a truncated version; desktop gets full.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None

            base = {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "primary_device_id": session.primary_device_id,
                "priority": session.priority,
                "active_tools": session.active_tools,
                "message_count": session.message_count,
                "device_count": len(session.devices),
            }

            if device_type == "mobile":
                # Truncated for mobile: no full agent state
                base["agent_state_summary"] = {
                    k: str(v)[:100] for k, v in session.agent_state.items()
                } if session.agent_state else {}
                base["requires_desktop"] = bool(
                    set(session.active_tools) & {"file_system", "terminal", "browser"}
                )
            else:
                # Full state for desktop
                base["agent_state"] = session.agent_state
                base["devices"] = [
                    {
                        "device_id": d.device_id,
                        "type": d.device_type,
                        "platform": d.platform,
                        "capabilities": d.capabilities,
                    }
                    for d in session.devices
                ]

            return base

    def cleanup_stale(self, max_age_seconds: float = 86400) -> int:
        """Remove sessions older than max_age_seconds. Returns count removed."""
        cutoff = time.time() - max_age_seconds
        removed = 0
        with self._lock:
            stale = [
                sid for sid, s in self._sessions.items()
                if s.last_active_at < cutoff
            ]
            for sid in stale:
                del self._sessions[sid]
                removed += 1
        return removed

    def get_user_sessions(self, user_id: str) -> list[PersistentSession]:
        """Get all sessions for a user."""
        with self._lock:
            return [
                s for s in self._sessions.values()
                if s.user_id == user_id
            ]

    def clear_all(self) -> None:
        """Remove all sessions (testing)."""
        with self._lock:
            self._sessions.clear()
