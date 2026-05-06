"""Sprint-13 PR-6 -- self-healing service contract.

Pins the cross-brain repair pattern + closed failure set. The
detection function is pure -- callers inject probe outputs. Tests
exercise the deterministic mapping from probe shape to Failure list
to repair workstream payload.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


_CLOSED_SUBSYSTEMS = {
    "backend_health",
    "frontend_health",
    "main_brain_not_ready",
    "cli_runtime_offline",
    "mcp_probe_fail",
    "schema_drift",
    "fe_be_route_404",
    "test_regression",
}


class TestNoFailuresWhenAllGreen:
    async def test_empty_probes_no_failures(self):
        from app.services.self_healing_service import enumerate_failures

        assert enumerate_failures({}) == []

    async def test_all_green_probes_no_failures(self):
        from app.services.self_healing_service import enumerate_failures

        probes = {
            "backend_health": {"reachable": True, "detail": ""},
            "frontend_health": {"reachable": True, "detail": ""},
            "router_readiness": {"main_brain_ready": True},
            "runtime_readiness": {"items": [
                {"id": "cli_claude", "kind": "cli_runtime", "readiness_state": "ready"},
            ]},
            "schema_head": {"alembic_head": "013", "applied_head": "013"},
            "fe_be_routes": {"frontend_calls": ["/system/morning-readiness"],
                             "backend_paths": ["/system/morning-readiness"]},
            "test_regression": {"newly_failing": []},
            "mcp_probe_fail": {"failed": []},
        }
        assert enumerate_failures(probes) == []


class TestDetection:
    async def test_backend_unreachable_blocker(self):
        from app.services.self_healing_service import enumerate_failures

        f = enumerate_failures({"backend_health": {"reachable": False}})
        assert len(f) == 1
        assert f[0].subsystem == "backend_health"
        assert f[0].severity == "blocker"

    async def test_main_brain_not_ready_routes_to_human(self):
        """When no main brain is callable, Daena cannot self-repair
        autonomously -- she must surface the blocker for the
        operator to choose. Suggested brain is 'human'."""
        from app.services.self_healing_service import enumerate_failures

        f = enumerate_failures(
            {"router_readiness": {"main_brain_ready": False}},
        )
        assert len(f) == 1
        assert f[0].subsystem == "main_brain_not_ready"
        assert f[0].suggested_brain == "human"

    async def test_cli_runtime_offline_routes_to_codex(self):
        """Cross-brain rule: mechanical CLI auth/path fixes go to
        Codex (async-native, the right tool for this work class)."""
        from app.services.self_healing_service import enumerate_failures

        f = enumerate_failures({
            "runtime_readiness": {"items": [
                {"id": "cli_codex", "kind": "cli_runtime",
                 "readiness_state": "detected_offline"},
            ]},
        })
        assert len(f) == 1
        assert f[0].subsystem == "cli_runtime_offline"
        assert f[0].suggested_brain == "codex_cli"

    async def test_schema_drift_routes_to_claude_code(self):
        """Schema drift is multi-file reasoning -- model + migration +
        consumers must agree. Claude Code is the right tool."""
        from app.services.self_healing_service import enumerate_failures

        f = enumerate_failures({
            "schema_head": {"alembic_head": "014", "applied_head": "013"},
        })
        assert len(f) == 1
        assert f[0].subsystem == "schema_drift"
        assert f[0].suggested_brain == "claude_code"
        assert f[0].severity == "blocker"

    async def test_fe_be_route_404(self):
        from app.services.self_healing_service import enumerate_failures

        f = enumerate_failures({
            "fe_be_routes": {
                "frontend_calls": ["/foo/missing", "/system/morning-readiness"],
                "backend_paths": ["/system/morning-readiness"],
            },
        })
        assert len(f) == 1
        assert f[0].subsystem == "fe_be_route_404"
        assert "/foo/missing" in f[0].id

    async def test_test_regression_routes_to_claude_code(self):
        from app.services.self_healing_service import enumerate_failures

        f = enumerate_failures({
            "test_regression": {"newly_failing": [
                "tests/test_x.py::TestY::test_z",
                "tests/test_a.py::TestB::test_c",
            ]},
        })
        assert len(f) == 1
        assert f[0].suggested_brain == "claude_code"

    async def test_security_mcp_routes_to_security_ops(self):
        from app.services.self_healing_service import enumerate_failures

        f = enumerate_failures({
            "mcp_probe_fail": {"failed": [
                {"name": "scrapegraph", "security_tagged": False},
                {"name": "shodan_mcp", "security_tagged": True},
            ]},
        })
        assert len(f) == 2
        sec = next(x for x in f if x.evidence["mcp_name"] == "shodan_mcp")
        non_sec = next(x for x in f if x.evidence["mcp_name"] == "scrapegraph")
        assert sec.department_hint == "Security Operations"
        assert non_sec.department_hint == "Engineering"


class TestClosedFailureSet:
    async def test_subsystem_label_is_closed(self):
        """Every Failure produced must carry a subsystem label from
        the closed set -- adding a new label must touch this test
        on purpose."""
        from app.services.self_healing_service import enumerate_failures

        all_probes = {
            "backend_health": {"reachable": False},
            "frontend_health": {"reachable": False},
            "router_readiness": {"main_brain_ready": False},
            "runtime_readiness": {"items": [
                {"id": "cli_x", "kind": "cli_runtime",
                 "readiness_state": "detected_offline"},
            ]},
            "schema_head": {"alembic_head": "a", "applied_head": "b"},
            "fe_be_routes": {"frontend_calls": ["/x"], "backend_paths": []},
            "test_regression": {"newly_failing": ["t::a"]},
            "mcp_probe_fail": {"failed": [{"name": "n"}]},
        }
        for f in enumerate_failures(all_probes):
            assert f.subsystem in _CLOSED_SUBSYSTEMS


class TestRepairWorkstreamPayload:
    async def test_payload_carries_self_repair_namespace(self):
        from app.services.self_healing_service import (
            Failure,
            repair_workstream_payload,
        )

        f = Failure(
            id="x:y",
            subsystem="schema_drift",
            severity="blocker",
            description="head mismatch",
            suggested_brain="claude_code",
            repair_action_class="reconcile_schema_drift",
            department_hint="Engineering",
            evidence={"alembic_head": "014", "applied_head": "013"},
        )
        payload = repair_workstream_payload(f)
        assert "goal" in payload
        assert payload["department_hint"] == "Engineering"
        ic = payload["initial_context"]["self_repair"]
        # Locked guard: every self-repair workstream starts in
        # propose-only mode. PR-4 + PR-6 share the same rule.
        assert ic["delivery"] == "manual_only"
        assert ic["requires_approval"] is True
        assert ic["suggested_brain"] == "claude_code"
        assert ic["subsystem"] == "schema_drift"
        assert ic["evidence"] == {"alembic_head": "014", "applied_head": "013"}

    async def test_no_auto_execute_field(self):
        from app.services.self_healing_service import (
            Failure,
            repair_workstream_payload,
        )

        f = Failure(
            id="x", subsystem="backend_health", severity="blocker",
            description="x", suggested_brain="ollama_backend",
            repair_action_class="restart", department_hint="Engineering",
        )
        payload = repair_workstream_payload(f)

        # Walk the entire payload tree -- no auto_execute / run_now
        # / apply field anywhere.
        forbidden = {"auto_execute", "run_now", "apply", "execute"}

        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    assert k.lower() not in forbidden, (
                        f"self-repair payload exposes forbidden key: {k}"
                    )
                    walk(v)
            elif isinstance(o, list):
                for x in o:
                    walk(x)

        walk(payload)
