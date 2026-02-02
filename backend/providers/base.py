"""
Common interface for chat-provider adapters (Discord, Telegram, Slack).
Implement: connect(), disconnect(), status(), send_message(), receive_message(), verify_webhook().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProviderStatus:
    provider_id: str
    connected: bool
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InboundMessage:
    provider_id: str
    channel_id: str
    user_id: str
    user_name: Optional[str]
    text: str
    raw: Dict[str, Any]
    message_id: Optional[str] = None


@dataclass
class OutboundMessage:
    channel_id: str
    text: str
    reply_to_id: Optional[str] = None


class ProviderBase(ABC):
    """Abstract base for Discord, Telegram, Slack adapters."""

    def __init__(self, provider_id: str, credentials: Dict[str, Any]):
        self.provider_id = provider_id
        self.credentials = credentials  # from env; never log raw

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection / validate credentials. Raise on failure."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Release connection."""
        pass

    @abstractmethod
    def status(self) -> ProviderStatus:
        """Current connection status (no secrets in details)."""
        pass

    @abstractmethod
    async def send_message(self, msg: OutboundMessage) -> Dict[str, Any]:
        """Send a message. Return { success, message_id?, error? }."""
        pass

    def receive_message(self, payload: Dict[str, Any]) -> Optional[InboundMessage]:
        """
        Parse webhook payload into InboundMessage. Return None if not a valid message.
        Used when webhook is verified and we have the raw body.
        """
        return None

    def verify_webhook(self, payload: bytes, headers: Dict[str, str]) -> bool:
        """
        Verify webhook signature (Discord/Telegram/Slack). Return True if valid.
        """
        return False
