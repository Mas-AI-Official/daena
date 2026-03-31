"""Google Calendar REST API client for Daena department agents.

Uses Google Calendar API v3 directly via httpx.
Credentials come from ConnectorInstance (OAuth2 access token).

Supported tools:
    - list_events: List upcoming events
    - create_event: Create a new calendar event
    - update_event: Update an existing event
    - find_free_time: Find available time slots
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"


class CalendarClient:
    """Direct Google Calendar API client using OAuth2 bearer token.

    Args:
        credentials: Must contain "access_token" (OAuth2).
    """

    def __init__(self, credentials: dict[str, str]) -> None:
        self._access_token = credentials.get("access_token", "")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _check_token(self) -> None:
        if not self._access_token:
            raise ValueError(
                "Google Calendar OAuth2 access_token required. "
                "Connect Google Calendar in Daena Settings > Connections."
            )

    async def list_events(
        self,
        calendar_id: str = "primary",
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 20,
        query: str = "",
    ) -> dict[str, Any]:
        """List upcoming calendar events.

        Args:
            calendar_id: Calendar ID (default "primary").
            time_min: ISO datetime for range start (defaults to now).
            time_max: ISO datetime for range end (defaults to 7 days from now).
            max_results: Maximum events to return.
            query: Free-text search term.

        Returns:
            Dict with "events" list.
        """
        self._check_token()
        now = datetime.now(timezone.utc)
        params: dict[str, Any] = {
            "timeMin": time_min or now.isoformat(),
            "timeMax": time_max or (now + timedelta(days=7)).isoformat(),
            "maxResults": min(max_results, 100),
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if query:
            params["q"] = query

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{CALENDAR_API_BASE}/calendars/{calendar_id}/events",
                headers=self._headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        events = []
        for item in data.get("items", []):
            events.append({
                "id": item.get("id"),
                "summary": item.get("summary", "(no title)"),
                "description": item.get("description", ""),
                "start": item.get("start", {}).get("dateTime", item.get("start", {}).get("date", "")),
                "end": item.get("end", {}).get("dateTime", item.get("end", {}).get("date", "")),
                "location": item.get("location", ""),
                "attendees": [
                    {"email": a.get("email"), "status": a.get("responseStatus", "")}
                    for a in item.get("attendees", [])
                ],
                "status": item.get("status", ""),
                "html_link": item.get("htmlLink", ""),
            })

        return {"events": events, "total": len(events)}

    async def create_event(
        self,
        summary: str,
        start: str,
        end: str,
        description: str = "",
        location: str = "",
        attendees: list[str] | None = None,
        calendar_id: str = "primary",
        timezone_str: str = "America/Toronto",
    ) -> dict[str, Any]:
        """Create a new calendar event.

        Args:
            summary: Event title.
            start: ISO datetime for event start.
            end: ISO datetime for event end.
            description: Event description.
            location: Event location.
            attendees: List of attendee email addresses.
            calendar_id: Calendar ID.
            timezone_str: Timezone for the event.

        Returns:
            Dict with created event details.
        """
        self._check_token()
        event_body: dict[str, Any] = {
            "summary": summary,
            "description": description,
            "location": location,
            "start": {"dateTime": start, "timeZone": timezone_str},
            "end": {"dateTime": end, "timeZone": timezone_str},
        }
        if attendees:
            event_body["attendees"] = [{"email": e} for e in attendees]

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{CALENDAR_API_BASE}/calendars/{calendar_id}/events",
                headers=self._headers,
                json=event_body,
            )
            resp.raise_for_status()
            result = resp.json()

        logger.info("calendar.event_created", summary=summary, event_id=result.get("id"))
        return {
            "id": result.get("id"),
            "summary": result.get("summary"),
            "start": result.get("start", {}).get("dateTime", ""),
            "end": result.get("end", {}).get("dateTime", ""),
            "html_link": result.get("htmlLink", ""),
            "status": "created",
        }

    async def update_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
        **updates: Any,
    ) -> dict[str, Any]:
        """Update an existing calendar event.

        Args:
            event_id: Event ID to update.
            calendar_id: Calendar ID.
            **updates: Fields to update (summary, description, start, end, location).

        Returns:
            Dict with updated event details.
        """
        self._check_token()
        # Build patch body from provided updates
        patch_body: dict[str, Any] = {}
        for key in ("summary", "description", "location"):
            if key in updates:
                patch_body[key] = updates[key]
        if "start" in updates:
            patch_body["start"] = {"dateTime": updates["start"]}
        if "end" in updates:
            patch_body["end"] = {"dateTime": updates["end"]}
        if "attendees" in updates:
            patch_body["attendees"] = [{"email": e} for e in updates["attendees"]]

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.patch(
                f"{CALENDAR_API_BASE}/calendars/{calendar_id}/events/{event_id}",
                headers=self._headers,
                json=patch_body,
            )
            resp.raise_for_status()
            result = resp.json()

        logger.info("calendar.event_updated", event_id=event_id)
        return {
            "id": result.get("id"),
            "summary": result.get("summary"),
            "start": result.get("start", {}).get("dateTime", ""),
            "end": result.get("end", {}).get("dateTime", ""),
            "status": "updated",
        }

    async def find_free_time(
        self,
        calendars: list[str] | None = None,
        time_min: str | None = None,
        time_max: str | None = None,
    ) -> dict[str, Any]:
        """Find free/busy time slots.

        Args:
            calendars: Calendar IDs to check (default ["primary"]).
            time_min: ISO datetime range start (defaults to now).
            time_max: ISO datetime range end (defaults to 3 days from now).

        Returns:
            Dict with busy periods per calendar.
        """
        self._check_token()
        now = datetime.now(timezone.utc)
        cal_ids = calendars or ["primary"]

        body = {
            "timeMin": time_min or now.isoformat(),
            "timeMax": time_max or (now + timedelta(days=3)).isoformat(),
            "items": [{"id": c} for c in cal_ids],
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{CALENDAR_API_BASE}/freeBusy",
                headers=self._headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        result: dict[str, Any] = {"calendars": {}}
        for cal_id, info in data.get("calendars", {}).items():
            result["calendars"][cal_id] = {
                "busy": [
                    {"start": b["start"], "end": b["end"]}
                    for b in info.get("busy", [])
                ],
            }
        return result

    # ── Tool dispatch ──

    TOOLS: dict[str, str] = {
        "list_events": "List upcoming calendar events",
        "create_event": "Create a new calendar event",
        "update_event": "Update an existing calendar event",
        "find_free_time": "Find available time slots across calendars",
    }

    async def execute_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a Calendar tool by name."""
        if tool_name == "list_events":
            return await self.list_events(**params)
        elif tool_name == "create_event":
            return await self.create_event(**params)
        elif tool_name == "update_event":
            return await self.update_event(**params)
        elif tool_name == "find_free_time":
            return await self.find_free_time(**params)
        else:
            raise ValueError(f"Unknown Calendar tool: {tool_name}")
