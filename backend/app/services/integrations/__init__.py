"""External service integrations for Daena's department agents.

Provides direct API clients for Gmail, Google Calendar, and Notion.
Each client uses credentials stored in ConnectorInstance (AES-256 encrypted).
All tool calls go through governance before execution.

Clients:
    - GmailClient: read, send, search, draft emails
    - CalendarClient: list, create, update events, find free time
    - NotionClient: search, read, create pages, query databases
    - IntegrationRouter: dispatches tool calls to the correct client
"""

from app.services.integrations.gmail_client import GmailClient
from app.services.integrations.calendar_client import CalendarClient
from app.services.integrations.notion_client import NotionClient
from app.services.integrations.integration_router import IntegrationRouter

__all__ = [
    "GmailClient",
    "CalendarClient",
    "NotionClient",
    "IntegrationRouter",
]
