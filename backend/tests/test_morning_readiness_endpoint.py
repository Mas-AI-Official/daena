"""Sprint-MORNING PR-4 -- /api/v1/system/morning-readiness contract.

Pure read-only aggregator. Pins:
  1. Endpoint mounted under /system/morning-readiness.
  2. Response shape: cli_runtimes / local_llms / api_providers /
     detected_mcps / blockers / ready_for_morning_work.
  3. NEVER returns secret values. Items expose readiness flags +
     endpoint URL only; detected_mcps drops env entirely.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


class TestEndpointMounted:
    async def test_route_under_v1(self):
        from app.api.v1 import router as api_v1_router
        paths = [getattr(r, "path", "") for r in api_v1_router.routes]
        assert "/system/morning-readiness" in paths


class TestShape:
    async def test_response_shape(self, monkeypatch):
        """Mock get_runtime_readiness so the test doesn't need a live
        truth registry. Confirm every key the frontend reads is present."""
        import app.api.v1.system_self_diagnostic as mod

        async def _fake_runtime(refresh=False):
            return {
                "items": [
                    {
                        "id": "ollama_backend",
                        "display_name": "Ollama (backend)",
                        "kind": "local_llm",
                        "detected": True,
                        "configured": True,
                        "callable": True,
                        "readiness_state": "ready",
                        "cost_class": "free_local",
                        "endpoint": "http://127.0.0.1:11434",
                        "safe_failure_reason": None,
                    },
                    {
                        "id": "cli_claude",
                        "display_name": "Claude Code CLI",
                        "kind": "cli_runtime",
                        "detected": True,
                        "configured": True,
                        "callable": True,
                        "readiness_state": "ready",
                        "cost_class": "subscription",
                        "endpoint": None,
                        "safe_failure_reason": None,
                    },
                    {
                        "id": "provider_openai",
                        "display_name": "OpenAI",
                        "kind": "api_provider",
                        "detected": False,
                        "configured": False,
                        "callable": False,
                        "readiness_state": "not_configured",
                        "cost_class": "metered_api",
                        "endpoint": None,
                        "safe_failure_reason": "no API key",
                    },
                ],
                "router_summary": {},
            }

        # Patch the import at the call site.
        from app.services import runtime_readiness as rr_mod
        monkeypatch.setattr(rr_mod, "get_runtime_readiness", _fake_runtime)

        # Invoke the route handler directly (bypass FastAPI).
        result = await mod.morning_readiness(refresh=False, _user=None)

        data = result["data"]

        # Top-level keys the frontend reads.
        for k in (
            "cli_runtimes",
            "local_llms",
            "api_providers",
            "detected_mcps",
            "blockers",
            "ready_for_morning_work",
        ):
            assert k in data, f"missing top-level key: {k}"

        # Bucket shape.
        for bucket_name in ("cli_runtimes", "local_llms", "api_providers"):
            bucket = data[bucket_name]
            assert "total" in bucket
            assert "ready" in bucket
            assert "items" in bucket

        # ready_for_morning_work must be true here (1 ready CLI + 1 ready LLM).
        assert data["ready_for_morning_work"] is True

        # Each item carries readiness flags only -- no secrets.
        for item in data["local_llms"]["items"]:
            for forbidden in ("api_key", "token", "secret", "password"):
                assert forbidden not in item, (
                    f"morning-readiness leaked {forbidden}"
                )

    async def test_no_brain_marks_blockers(self, monkeypatch):
        import app.api.v1.system_self_diagnostic as mod

        async def _fake_no_brain(refresh=False):
            return {
                "items": [
                    {
                        "id": "provider_openai",
                        "display_name": "OpenAI",
                        "kind": "api_provider",
                        "detected": False,
                        "configured": False,
                        "callable": False,
                        "readiness_state": "not_configured",
                        "cost_class": "metered_api",
                        "endpoint": None,
                        "safe_failure_reason": "no API key",
                    },
                ],
                "router_summary": {},
            }

        from app.services import runtime_readiness as rr_mod
        monkeypatch.setattr(rr_mod, "get_runtime_readiness", _fake_no_brain)

        result = await mod.morning_readiness(refresh=False, _user=None)
        blockers = result["data"]["blockers"]
        assert any("local LLM" in b or "CLI runtime" in b for b in blockers)
        assert result["data"]["ready_for_morning_work"] is False


class TestNoSecretLeak:
    async def test_detected_mcps_drops_env(self, monkeypatch):
        """MCP env values may carry tokens. The aggregator must never
        include them in the response. We verify the response field
        list explicitly."""
        import app.api.v1.system_self_diagnostic as mod

        async def _fake_runtime(refresh=False):
            return {"items": [], "router_summary": {}}

        # Stub the detector to return a fake DetectedMCP-like with env populated.
        class _FakeMCP:
            source_cli = "claude_code"
            config_path = "/x"
            name = "gmail"
            command = "npx"
            args: list = []
            env = {"GMAIL_TOKEN": "secret-shouldnt-leak"}
            url = ""
            notes = ""

        class _FakeDetector:
            async def discover_all(self):
                return [_FakeMCP()]

        from app.services import runtime_readiness as rr_mod
        monkeypatch.setattr(rr_mod, "get_runtime_readiness", _fake_runtime)
        from app.services.mcp_sync import detector as det_mod
        monkeypatch.setattr(det_mod, "CLIMCPDetector", _FakeDetector)

        result = await mod.morning_readiness(refresh=False, _user=None)
        items = result["data"]["detected_mcps"]["items"]
        assert len(items) == 1
        keys = set(items[0].keys())
        assert "env" not in keys, "env values must NEVER appear in the response"
        # Ensure no token-bearing string slipped in
        for v in items[0].values():
            if isinstance(v, str):
                assert "secret-shouldnt-leak" not in v
