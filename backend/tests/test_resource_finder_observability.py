"""Rule-17 observability regression tests for ResourceFinder.

Two failure paths used to log at ``debug`` only, so under the app's INFO
root level they were invisible in production (masked-observability /
empty-as-clean): a broken web search or a failed knowledge-persist looked
identical to a clean "no result". Both now log at ``warning`` with the
exception type.

Daena routes structlog to stdout, so we assert on capsys (matching
test_red_team_ops.py / test_cli_runtime_probe.py), not caplog.
"""

from uuid import uuid4

import pytest

from app.services.cognition.resource_finder import Knowledge, ResourceFinder


class TestSearchWebObservability:

    @pytest.mark.asyncio
    async def test_transport_failure_logged_as_warning(self, monkeypatch, capsys):
        """A raising httpx client must surface a warning, not a silent miss.

        The except branch fires on real transport failures / code defects
        (the routine "DDG rejected the query" case is the non-200 branch),
        so it must be visible in production -- a debug-only log is filtered
        at the INFO root level and the failure vanishes.
        """
        import httpx

        class _RaisingClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, *args, **kwargs):
                raise httpx.ConnectError("connection blocked")

        monkeypatch.setattr(httpx, "AsyncClient", _RaisingClient)

        finder = ResourceFinder()
        result = await finder._search_web("what is the capital of france?")

        # A failed probe is NOT a fabricated answer.
        assert result is None

        logged = "".join(capsys.readouterr())
        assert "resource_finder.web_search_failed" in logged
        assert "ConnectError" in logged
        assert "warning" in logged


class TestPersistKnowledgeObservability:

    @pytest.mark.asyncio
    async def test_persist_failure_logged_as_warning(self, monkeypatch, capsys):
        """A failed persist (learned-but-not-remembered) must be a warning.

        The success path logs at INFO; a debug-only failure path is the
        inverted, masked case. Force MemoryService to blow up and assert
        the failure is surfaced.
        """
        class _BoomMemory:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("memory backend down")

        monkeypatch.setattr(
            "app.services.memory.MemoryService", _BoomMemory, raising=False
        )

        finder = ResourceFinder(db=object(), user_id=uuid4(), tenant_id=uuid4())
        knowledge = Knowledge(
            question="what is quantization?",
            answer="reducing numeric precision",
            source="web",
            should_persist=True,
        )

        # Must not raise -- the failure is swallowed for the caller but logged.
        await finder.persist_knowledge(knowledge)

        logged = "".join(capsys.readouterr())
        assert "resource_finder.persist_failed" in logged
        assert "RuntimeError" in logged
        assert "warning" in logged
