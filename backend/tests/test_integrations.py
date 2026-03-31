"""Tests for Phase G: Integration clients, router, and department workflows.

Covers:
- Gmail, Calendar, Notion client tool dispatch
- IntegrationRouter provider resolution
- DaenaBot router integration patterns
- Department workflow definitions and engine
- DepartmentTask model
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.integrations.gmail_client import GmailClient
from app.services.integrations.calendar_client import CalendarClient
from app.services.integrations.notion_client import NotionClient
from app.services.integrations.integration_router import (
    IntegrationRouter,
    IntegrationError,
    NotConnectedError,
    PermissionDeniedError,
    PROVIDER_REGISTRY,
    ALL_TOOLS,
)
from app.services.daenabot.router import DaenaBotRouter, ToolCall
from app.services.department_workflows import (
    DepartmentWorkflowEngine,
    WORKFLOWS,
    WorkflowDef,
    WorkflowResult,
)


# ── Gmail Client Tests ──


class TestGmailClient:
    """Tests for GmailClient."""

    def test_init_with_access_token(self):
        client = GmailClient({"access_token": "test-token"})
        assert client._access_token == "test-token"

    def test_init_with_email_and_password(self):
        client = GmailClient({"email": "test@example.com", "app_password": "pass"})
        assert client._email == "test@example.com"

    def test_headers_include_bearer_token(self):
        client = GmailClient({"access_token": "abc123"})
        headers = client._headers
        assert headers["Authorization"] == "Bearer abc123"
        assert headers["Content-Type"] == "application/json"

    def test_check_token_raises_without_token(self):
        client = GmailClient({})
        with pytest.raises(ValueError, match="access_token required"):
            client._check_token()

    def test_check_token_passes_with_token(self):
        client = GmailClient({"access_token": "valid"})
        client._check_token()  # Should not raise

    def test_tools_defined(self):
        assert "search_emails" in GmailClient.TOOLS
        assert "read_email" in GmailClient.TOOLS
        assert "send_email" in GmailClient.TOOLS
        assert "create_draft" in GmailClient.TOOLS

    @pytest.mark.asyncio
    async def test_execute_tool_unknown_raises(self):
        client = GmailClient({"access_token": "test"})
        with pytest.raises(ValueError, match="Unknown Gmail tool"):
            await client.execute_tool("nonexistent", {})

    def test_extract_body_plain_text(self):
        import base64
        text = "Hello world"
        encoded = base64.urlsafe_b64encode(text.encode()).decode()
        payload = {"mimeType": "text/plain", "body": {"data": encoded}}
        assert GmailClient._extract_body(payload) == "Hello world"

    def test_extract_body_multipart(self):
        import base64
        text = "Body text"
        encoded = base64.urlsafe_b64encode(text.encode()).decode()
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": encoded}},
                {"mimeType": "text/html", "body": {"data": encoded}},
            ],
        }
        assert GmailClient._extract_body(payload) == "Body text"

    def test_extract_attachments(self):
        payload = {
            "parts": [
                {
                    "filename": "report.pdf",
                    "mimeType": "application/pdf",
                    "body": {"size": 1024, "attachmentId": "att-123"},
                },
                {
                    "filename": "",
                    "mimeType": "text/plain",
                    "body": {"data": "content"},
                },
            ],
        }
        attachments = GmailClient._extract_attachments(payload)
        assert len(attachments) == 1
        assert attachments[0]["filename"] == "report.pdf"
        assert attachments[0]["attachment_id"] == "att-123"


# ── Calendar Client Tests ──


class TestCalendarClient:
    """Tests for CalendarClient."""

    def test_init_with_token(self):
        client = CalendarClient({"access_token": "cal-token"})
        assert client._access_token == "cal-token"

    def test_headers(self):
        client = CalendarClient({"access_token": "cal-token"})
        assert client._headers["Authorization"] == "Bearer cal-token"

    def test_check_token_raises_without_token(self):
        client = CalendarClient({})
        with pytest.raises(ValueError, match="access_token required"):
            client._check_token()

    def test_tools_defined(self):
        assert "list_events" in CalendarClient.TOOLS
        assert "create_event" in CalendarClient.TOOLS
        assert "update_event" in CalendarClient.TOOLS
        assert "find_free_time" in CalendarClient.TOOLS

    @pytest.mark.asyncio
    async def test_execute_tool_unknown_raises(self):
        client = CalendarClient({"access_token": "test"})
        with pytest.raises(ValueError, match="Unknown Calendar tool"):
            await client.execute_tool("nonexistent", {})


# ── Notion Client Tests ──


class TestNotionClient:
    """Tests for NotionClient."""

    def test_init_with_token(self):
        client = NotionClient({"token": "ntn_test"})
        assert client._token == "ntn_test"

    def test_init_with_access_token_fallback(self):
        client = NotionClient({"access_token": "ntn_alt"})
        assert client._token == "ntn_alt"

    def test_headers_include_notion_version(self):
        client = NotionClient({"token": "test"})
        assert "Notion-Version" in client._headers
        assert client._headers["Authorization"] == "Bearer test"

    def test_check_token_raises_without_token(self):
        client = NotionClient({})
        with pytest.raises(ValueError, match="integration token required"):
            client._check_token()

    def test_tools_defined(self):
        assert "search_pages" in NotionClient.TOOLS
        assert "read_page" in NotionClient.TOOLS
        assert "create_page" in NotionClient.TOOLS
        assert "query_database" in NotionClient.TOOLS

    @pytest.mark.asyncio
    async def test_execute_tool_unknown_raises(self):
        client = NotionClient({"token": "test"})
        with pytest.raises(ValueError, match="Unknown Notion tool"):
            await client.execute_tool("nonexistent", {})

    def test_extract_title_from_properties(self):
        item = {
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Test Page"}],
                },
            },
        }
        assert NotionClient._extract_title(item) == "Test Page"

    def test_extract_title_fallback(self):
        item = {"properties": {}, "title": [{"plain_text": "DB Title"}]}
        assert NotionClient._extract_title(item) == "DB Title"

    def test_extract_title_untitled(self):
        item = {"properties": {}}
        assert NotionClient._extract_title(item) == "(untitled)"

    def test_extract_block_text(self):
        block = {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"plain_text": "Hello "}, {"plain_text": "world"}],
            },
        }
        assert NotionClient._extract_block_text(block) == "Hello world"

    def test_extract_properties(self):
        item = {
            "properties": {
                "Name": {"type": "title", "title": [{"plain_text": "Item"}]},
                "Status": {"type": "status", "status": {"name": "Done"}},
                "Count": {"type": "number", "number": 42},
                "Active": {"type": "checkbox", "checkbox": True},
                "Tags": {"type": "multi_select", "multi_select": [{"name": "A"}, {"name": "B"}]},
            },
        }
        props = NotionClient._extract_properties(item)
        assert props["Name"] == "Item"
        assert props["Status"] == "Done"
        assert props["Count"] == 42
        assert props["Active"] is True
        assert props["Tags"] == ["A", "B"]


# ── Integration Router Tests ──


class TestIntegrationRouter:
    """Tests for IntegrationRouter."""

    def test_provider_registry_has_expected_providers(self):
        assert "gmail" in PROVIDER_REGISTRY
        assert "google-calendar" in PROVIDER_REGISTRY
        assert "calendar" in PROVIDER_REGISTRY
        assert "notion" in PROVIDER_REGISTRY

    def test_all_tools_has_expected_providers(self):
        assert "gmail" in ALL_TOOLS
        assert "google-calendar" in ALL_TOOLS
        assert "notion" in ALL_TOOLS

    @pytest.mark.asyncio
    async def test_execute_unknown_provider_raises(self):
        import uuid
        db = AsyncMock()
        router = IntegrationRouter(db)
        with pytest.raises(IntegrationError, match="Unknown provider"):
            await router.execute(
                provider="unknown",
                tool_name="test",
                params={},
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_execute_qualified_invalid_format_raises(self):
        import uuid
        db = AsyncMock()
        router = IntegrationRouter(db)
        with pytest.raises(IntegrationError, match="Invalid tool name"):
            await router.execute_qualified(
                qualified_tool="invalid_no_dot",
                params={},
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
            )


# ── DaenaBot Router Integration Pattern Tests ──


class TestDaenaBotRouterIntegrationPatterns:
    """Tests for integration patterns in DaenaBotRouter."""

    def test_gmail_search_pattern(self):
        result = DaenaBotRouter.match("search my emails about project deadline")
        assert result is not None
        assert result.tool_name == "gmail.search_emails"
        assert "project deadline" in result.params["query"]

    def test_gmail_check_inbox(self):
        result = DaenaBotRouter.match("check my inbox")
        assert result is not None
        assert result.tool_name == "gmail.search_emails"
        assert result.params["query"] == "is:unread"

    def test_gmail_send_email(self):
        result = DaenaBotRouter.match("send an email to test@example.com about meeting")
        assert result is not None
        assert result.tool_name == "gmail.send_email"
        assert result.params["to"] == "test@example.com"

    def test_gmail_draft_email(self):
        result = DaenaBotRouter.match("draft an email to boss@company.com about quarterly report")
        assert result is not None
        assert result.tool_name == "gmail.create_draft"
        assert result.params["to"] == "boss@company.com"

    def test_calendar_check(self):
        result = DaenaBotRouter.match("check my calendar")
        assert result is not None
        assert result.tool_name == "calendar.list_events"

    def test_calendar_show_schedule(self):
        result = DaenaBotRouter.match("show my schedule")
        assert result is not None
        assert result.tool_name == "calendar.list_events"

    def test_calendar_schedule_meeting(self):
        result = DaenaBotRouter.match("schedule a meeting with team")
        assert result is not None
        assert result.tool_name == "calendar.create_event"
        assert "team" in result.params["summary"]

    def test_calendar_find_free_time(self):
        result = DaenaBotRouter.match("when am I free")
        assert result is not None
        assert result.tool_name == "calendar.find_free_time"

    def test_notion_search(self):
        result = DaenaBotRouter.match("search notion for project plan")
        assert result is not None
        assert result.tool_name == "notion.search_pages"
        assert "project plan" in result.params["query"]

    def test_notion_create_page(self):
        result = DaenaBotRouter.match("create a notion page called Sprint Backlog")
        assert result is not None
        assert result.tool_name == "notion.create_page"
        assert "Sprint Backlog" in result.params["title"]

    def test_file_patterns_still_work(self):
        """Verify file patterns are not broken by new integration patterns."""
        result = DaenaBotRouter.match("list files in D:\\Ideas\\Daena")
        assert result is not None
        assert result.tool_name == "file.list_directory"

    def test_terminal_patterns_still_work(self):
        """Verify terminal patterns still take priority."""
        result = DaenaBotRouter.match("run 'pytest tests/'")
        assert result is not None
        assert result.tool_name == "terminal.execute_command"


# ── Department Workflow Tests ──


class TestDepartmentWorkflows:
    """Tests for department workflow definitions and engine."""

    def test_workflows_registered(self):
        assert len(WORKFLOWS) > 0

    def test_ops_daily_briefing_exists(self):
        assert "ops.daily_briefing" in WORKFLOWS
        wf = WORKFLOWS["ops.daily_briefing"]
        assert wf.department == "Operations"
        assert len(wf.steps) >= 2
        assert wf.schedule  # Has cron schedule

    def test_mkt_draft_content_exists(self):
        assert "mkt.draft_content" in WORKFLOWS
        wf = WORKFLOWS["mkt.draft_content"]
        assert wf.department == "Marketing"

    def test_sales_lead_research_exists(self):
        assert "sales.lead_research" in WORKFLOWS
        wf = WORKFLOWS["sales.lead_research"]
        assert wf.department == "Sales"

    def test_eng_test_status_exists(self):
        assert "eng.test_status" in WORKFLOWS
        wf = WORKFLOWS["eng.test_status"]
        assert wf.department == "Engineering"

    def test_fin_cost_report_exists(self):
        assert "fin.cost_report" in WORKFLOWS
        assert WORKFLOWS["fin.cost_report"].department == "Finance"

    def test_research_competitive_scan_exists(self):
        assert "research.competitive_scan" in WORKFLOWS

    def test_sec_access_audit_exists(self):
        assert "sec.access_audit" in WORKFLOWS

    def test_list_workflows_all(self):
        results = DepartmentWorkflowEngine.list_workflows()
        assert len(results) >= 8
        assert all("id" in r for r in results)
        assert all("department" in r for r in results)

    def test_list_workflows_by_department(self):
        ops = DepartmentWorkflowEngine.list_workflows("Operations")
        assert all(r["department"] == "Operations" for r in ops)
        assert len(ops) >= 1

    def test_get_scheduled_workflows(self):
        scheduled = DepartmentWorkflowEngine.get_scheduled_workflows()
        assert len(scheduled) >= 1
        assert all(isinstance(wf, WorkflowDef) for wf in scheduled)
        assert all(wf.schedule for wf in scheduled)

    @pytest.mark.asyncio
    async def test_run_unknown_workflow(self):
        import uuid
        db = AsyncMock()
        engine = DepartmentWorkflowEngine(db, uuid.uuid4(), uuid.uuid4())
        result = await engine.run("nonexistent.workflow")
        assert result.status == "failed"
        assert "Unknown workflow" in result.error

    def test_workflow_result_to_dict(self):
        result = WorkflowResult(
            workflow_id="test.wf",
            department="Test",
            status="completed",
            summary="Test passed",
        )
        d = result.to_dict()
        assert d["workflow_id"] == "test.wf"
        assert d["department"] == "Test"
        assert d["status"] == "completed"
        assert d["summary"] == "Test passed"
        assert d["started_at"]  # Auto-set


# ── Department Task Model Tests ──


class TestDepartmentTaskModel:
    """Tests for DepartmentTask ORM model."""

    def test_model_import(self):
        from app.models.department_task import DepartmentTask
        assert DepartmentTask.__tablename__ == "department_tasks"

    def test_model_in_registry(self):
        from app.models import DepartmentTask
        assert DepartmentTask is not None


# ── Execution Service Integration Dispatch Tests ──


class TestExecutionServiceIntegrationDispatch:
    """Tests for integration tool dispatch in ExecutionService."""

    def test_resolve_action_type_read(self):
        from app.services.execution_service import ExecutionService
        assert ExecutionService._resolve_action_type("gmail.search_emails", {}) == "READ_EXTERNAL"
        assert ExecutionService._resolve_action_type("gmail.read_email", {}) == "READ_EXTERNAL"
        assert ExecutionService._resolve_action_type("calendar.list_events", {}) == "READ_EXTERNAL"
        assert ExecutionService._resolve_action_type("notion.search_pages", {}) == "READ_EXTERNAL"

    def test_resolve_action_type_write(self):
        from app.services.execution_service import ExecutionService
        assert ExecutionService._resolve_action_type("gmail.create_draft", {}) == "WRITE_EXTERNAL"
        assert ExecutionService._resolve_action_type("calendar.create_event", {}) == "WRITE_EXTERNAL"
        assert ExecutionService._resolve_action_type("notion.create_page", {}) == "WRITE_EXTERNAL"

    def test_resolve_action_type_send(self):
        from app.services.execution_service import ExecutionService
        assert ExecutionService._resolve_action_type("gmail.send_email", {}) == "SEND_EXTERNAL"

    def test_resolve_action_type_file_still_works(self):
        from app.services.execution_service import ExecutionService
        # Verify file agent dispatch is not broken
        from app.services.daenabot.file_agent import FileAgent
        expected = FileAgent.OPERATION_ACTION_MAP.get("read_file", "EXECUTE")
        assert ExecutionService._resolve_action_type("file.read_file", {}) == expected
