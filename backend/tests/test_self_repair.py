"""Tests for SelfRepair service.

Covers:
- Error location extraction from tracebacks
- Python traceback parsing
- Non-Python error parsing
"""

from __future__ import annotations

import pytest

from app.services.self_repair import extract_error_location, RepairResult


class TestExtractErrorLocation:
    """Tests for traceback parsing."""

    def test_python_traceback(self):
        error = '''Traceback (most recent call last):
  File "/d/Ideas/Daena/backend/app/services/chat_orchestrator.py", line 500, in stream_reply
    result = await self._process()
  File "/d/Ideas/Daena/backend/app/services/tool_use_loop.py", line 150, in _execute_tool
    raise ValueError("bad param")
ValueError: bad param'''
        loc = extract_error_location(error)
        assert loc["file_path"] == "/d/Ideas/Daena/backend/app/services/tool_use_loop.py"
        assert loc["line_number"] == 150
        assert loc["function_name"] == "_execute_tool"
        assert loc["error_type"] == "ValueError"
        assert loc["error_message"] == "bad param"

    def test_import_error(self):
        error = '''Traceback (most recent call last):
  File "app/main.py", line 5, in <module>
    from app.services.missing import something
ImportError: cannot import name 'something' from 'app.services.missing'
'''
        loc = extract_error_location(error)
        assert loc["file_path"] == "app/main.py"
        assert loc["error_type"] == "ImportError"

    def test_no_traceback(self):
        error = "Error: something went wrong"
        loc = extract_error_location(error)
        assert loc["file_path"] == ""
        assert loc["error_message"] == "something went wrong"

    def test_multi_frame_traceback(self):
        error = '''Traceback (most recent call last):
  File "a.py", line 1, in main
  File "b.py", line 2, in helper
  File "c.py", line 3, in inner
TypeError: expected str got int'''
        loc = extract_error_location(error)
        # Should pick the LAST frame (innermost)
        assert loc["file_path"] == "c.py"
        assert loc["line_number"] == 3
        assert loc["error_type"] == "TypeError"


class TestSwarmParallelism:
    """Tests for SwarmExecutor concurrency limits."""

    def test_runtime_concurrency_limits_exist(self):
        from app.services.swarm.executor import RUNTIME_CONCURRENCY_LIMITS
        assert "claude_code" in RUNTIME_CONCURRENCY_LIMITS
        assert "codex" in RUNTIME_CONCURRENCY_LIMITS
        assert RUNTIME_CONCURRENCY_LIMITS["claude_code"] >= 5

    def test_max_parallel_increased(self):
        from app.services.swarm.executor import MAX_PARALLEL_SUBTASKS
        assert MAX_PARALLEL_SUBTASKS >= 20

    def test_per_runtime_semaphores_created(self):
        from unittest.mock import MagicMock
        from app.services.swarm.executor import SwarmExecutor
        registry = MagicMock()
        executor = SwarmExecutor(registry)
        assert len(executor._runtime_semaphores) > 0
        assert "claude_code" in executor._runtime_semaphores


class TestAdaptiveQuintessence:
    """Tests for adaptive QE depth."""

    def test_qe_depth_values(self):
        """Verify the depth mapping exists in the orchestrator."""
        # The mapping is inline in chat_orchestrator.py
        # Just verify the engine accepts the depth param
        from app.services.quintessence_engine import QuintessenceEngine
        import inspect
        sig = inspect.signature(QuintessenceEngine.deliberate)
        assert "depth" in sig.parameters
