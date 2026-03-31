"""Gmail REST API client for Daena department agents.

Uses Google Gmail API v1 directly via httpx. Credentials come from
ConnectorInstance (OAuth2 access token or app password for SMTP).

Supported tools:
    - search_emails: Search inbox with Gmail query syntax
    - read_email: Read a specific email by ID
    - send_email: Send a new email
    - create_draft: Create a draft email
"""

from __future__ import annotations

import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailClient:
    """Direct Gmail API client using OAuth2 bearer token.

    Args:
        credentials: Must contain "access_token" (OAuth2) or
                     "email" + "app_password" (SMTP fallback).
    """

    def __init__(self, credentials: dict[str, str]) -> None:
        self._access_token = credentials.get("access_token", "")
        self._email = credentials.get("email", "")
        self._app_password = credentials.get("app_password", "")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _check_token(self) -> None:
        if not self._access_token:
            raise ValueError(
                "Gmail OAuth2 access_token required. "
                "Connect Gmail in Daena Settings > Connections."
            )

    async def search_emails(
        self,
        query: str = "",
        max_results: int = 10,
        label_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Search emails using Gmail query syntax.

        Args:
            query: Gmail search query (e.g. "from:user@example.com is:unread")
            max_results: Maximum number of results (1-100)
            label_ids: Filter by label IDs (e.g. ["INBOX", "UNREAD"])

        Returns:
            Dict with "messages" list (id, threadId, snippet).
        """
        self._check_token()
        params: dict[str, Any] = {
            "q": query,
            "maxResults": min(max_results, 100),
        }
        if label_ids:
            params["labelIds"] = ",".join(label_ids)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{GMAIL_API_BASE}/messages",
                headers=self._headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        messages = data.get("messages", [])
        if not messages:
            return {"messages": [], "total": 0}

        # Fetch snippets for each message (batch of first N)
        enriched = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            for msg in messages[:max_results]:
                detail = await client.get(
                    f"{GMAIL_API_BASE}/messages/{msg['id']}",
                    headers=self._headers,
                    params={"format": "metadata", "metadataHeaders": "Subject,From,Date"},
                )
                if detail.status_code == 200:
                    msg_data = detail.json()
                    headers_list = msg_data.get("payload", {}).get("headers", [])
                    header_map = {h["name"]: h["value"] for h in headers_list}
                    enriched.append({
                        "id": msg["id"],
                        "thread_id": msg.get("threadId"),
                        "subject": header_map.get("Subject", "(no subject)"),
                        "from": header_map.get("From", ""),
                        "date": header_map.get("Date", ""),
                        "snippet": msg_data.get("snippet", ""),
                    })

        return {"messages": enriched, "total": data.get("resultSizeEstimate", len(enriched))}

    async def read_email(self, message_id: str) -> dict[str, Any]:
        """Read a specific email by ID.

        Returns full email with headers, body text, and attachment info.
        """
        self._check_token()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{GMAIL_API_BASE}/messages/{message_id}",
                headers=self._headers,
                params={"format": "full"},
            )
            resp.raise_for_status()
            data = resp.json()

        headers_list = data.get("payload", {}).get("headers", [])
        header_map = {h["name"]: h["value"] for h in headers_list}

        body_text = self._extract_body(data.get("payload", {}))
        attachments = self._extract_attachments(data.get("payload", {}))

        return {
            "id": data["id"],
            "thread_id": data.get("threadId"),
            "subject": header_map.get("Subject", ""),
            "from": header_map.get("From", ""),
            "to": header_map.get("To", ""),
            "cc": header_map.get("Cc", ""),
            "date": header_map.get("Date", ""),
            "body": body_text,
            "snippet": data.get("snippet", ""),
            "labels": data.get("labelIds", []),
            "attachments": attachments,
        }

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
        reply_to: str = "",
        html: bool = False,
    ) -> dict[str, Any]:
        """Send an email via Gmail API.

        Args:
            to: Recipient email address(es), comma-separated.
            subject: Email subject line.
            body: Email body (plain text or HTML).
            cc: CC recipients, comma-separated.
            bcc: BCC recipients, comma-separated.
            reply_to: Message-ID to reply to (for threading).
            html: If True, body is treated as HTML.

        Returns:
            Dict with sent message ID and thread ID.
        """
        self._check_token()
        msg = MIMEMultipart("alternative") if html else MIMEText(body, "plain")
        if html:
            msg.attach(MIMEText(body, "html"))

        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc
        if reply_to:
            msg["In-Reply-To"] = reply_to
            msg["References"] = reply_to

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{GMAIL_API_BASE}/messages/send",
                headers=self._headers,
                json={"raw": raw},
            )
            resp.raise_for_status()
            result = resp.json()

        logger.info("gmail.email_sent", to=to, subject=subject, message_id=result.get("id"))
        return {
            "id": result.get("id"),
            "thread_id": result.get("threadId"),
            "status": "sent",
        }

    async def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        html: bool = False,
    ) -> dict[str, Any]:
        """Create a draft email (does not send).

        Returns:
            Dict with draft ID and message info.
        """
        self._check_token()
        msg = MIMEMultipart("alternative") if html else MIMEText(body, "plain")
        if html:
            msg.attach(MIMEText(body, "html"))
        msg["To"] = to
        msg["Subject"] = subject

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{GMAIL_API_BASE}/drafts",
                headers=self._headers,
                json={"message": {"raw": raw}},
            )
            resp.raise_for_status()
            result = resp.json()

        logger.info("gmail.draft_created", to=to, subject=subject)
        return {
            "draft_id": result.get("id"),
            "message_id": result.get("message", {}).get("id"),
            "status": "draft",
        }

    @staticmethod
    def _extract_body(payload: dict) -> str:
        """Extract plain text body from Gmail message payload."""
        if payload.get("mimeType") == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            # Recurse into nested parts
            if part.get("parts"):
                result = GmailClient._extract_body(part)
                if result:
                    return result

        return ""

    @staticmethod
    def _extract_attachments(payload: dict) -> list[dict]:
        """Extract attachment metadata from Gmail message payload."""
        attachments = []
        for part in payload.get("parts", []):
            filename = part.get("filename", "")
            if filename:
                attachments.append({
                    "filename": filename,
                    "mime_type": part.get("mimeType", ""),
                    "size": part.get("body", {}).get("size", 0),
                    "attachment_id": part.get("body", {}).get("attachmentId", ""),
                })
        return attachments

    # ── Tool dispatch ──

    TOOLS: dict[str, str] = {
        "search_emails": "Search inbox with Gmail query syntax",
        "read_email": "Read a specific email by message ID",
        "send_email": "Send a new email",
        "create_draft": "Create a draft email without sending",
    }

    async def execute_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a Gmail tool by name.

        Args:
            tool_name: One of the TOOLS keys.
            params: Tool-specific parameters.

        Returns:
            Tool result dict.
        """
        if tool_name == "search_emails":
            return await self.search_emails(**params)
        elif tool_name == "read_email":
            return await self.read_email(**params)
        elif tool_name == "send_email":
            return await self.send_email(**params)
        elif tool_name == "create_draft":
            return await self.create_draft(**params)
        else:
            raise ValueError(f"Unknown Gmail tool: {tool_name}")
