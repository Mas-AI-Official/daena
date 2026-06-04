"""Deterministic Daena behavioral evals (offline, no LLM, no paid calls).

Each test drives a REAL Daena code path and asserts an end-behavior contract via
the eval harness. LLM-judge-dependent scenarios (memory recall, governance
refusal semantics) are declared in EVAL_REGISTRY with implemented=False and are
asserted to be visibly pending, not silently missing (ADR-001 honesty).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.evals.eval_harness import EVAL_REGISTRY, EvalCase, run_eval


def _factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_eval_settings_heartbeat_roundtrip(test_engine) -> None:
    """settings: a configured heartbeat survives a simulated restart."""
    from app.services.heartbeat.heartbeat_config_store import (
        extract_persistable,
        save_persisted,
    )
    from app.services.heartbeat.heartbeat_daemon import HeartbeatDaemon

    async def check() -> tuple[bool, str]:
        factory = _factory(test_engine)
        with patch("app.core.database.async_session_factory", factory):
            d1 = HeartbeatDaemon()
            d1.configure({"interval_minutes": 77})
            await save_persisted(extract_persistable(d1.config))
            d2 = HeartbeatDaemon()
            await d2.hydrate_from_db()
        ok = d2.config.interval_minutes == 77
        return ok, f"rehydrated interval={d2.config.interval_minutes}"

    case = next(c for c in EVAL_REGISTRY if c.name == "settings.heartbeat_roundtrip")
    res = await run_eval(case, check)
    assert res.passed, res.detail


@pytest.mark.asyncio
async def test_eval_trace_no_secret_capture() -> None:
    """tool_safety: the tracer strips secret-looking metadata."""
    from app.services.run_tracer import _safe_metadata

    async def check() -> tuple[bool, str]:
        cleaned = _safe_metadata(
            {"api_key": "sk-LEAK", "auth_token": "LEAK", "tries": 2}
        ) or {}
        ok = "api_key" not in cleaned and "auth_token" not in cleaned and cleaned.get("tries") == 2
        return ok, f"cleaned keys={sorted(cleaned)}"

    case = next(c for c in EVAL_REGISTRY if c.name == "tool_safety.trace_no_secret_capture")
    res = await run_eval(case, check)
    assert res.passed, res.detail


@pytest.mark.asyncio
async def test_eval_trace_failopen() -> None:
    """error: a tracing failure never propagates into the chat path."""
    from app.services import run_tracer

    async def check() -> tuple[bool, str]:
        def _boom():
            raise RuntimeError("db down")

        with patch.object(run_tracer, "_TRACE_ENABLED", True), patch(
            "app.core.database.async_session_factory", _boom
        ):
            out = await run_tracer.record_trace_event(
                event_type="chat.end", request_id="eval-failopen"
            )
        return out is None, "record_trace_event swallowed the DB error"

    case = next(c for c in EVAL_REGISTRY if c.name == "error.trace_failopen")
    res = await run_eval(case, check)
    assert res.passed, res.detail


@pytest.mark.asyncio
async def test_eval_ragx_failopen() -> None:
    """fallback: ragx grounding returns empty (no raise) when the service is down."""
    from app.services import ragx_bridge

    async def check() -> tuple[bool, str]:
        # Point at an unreachable port so the call fails fast and deterministically.
        with patch.object(ragx_bridge, "RAGX_URL", "http://127.0.0.1:9"):
            result = await ragx_bridge.query_ragx(query="anything", timeout_s=2.0)
        ok = result is not None and result.citations == []
        return ok, f"citations={len(result.citations) if result else 'None'}"

    case = next(c for c in EVAL_REGISTRY if c.name == "fallback.ragx_failopen")
    res = await run_eval(case, check)
    assert res.passed, res.detail


def test_eval_registry_pending_are_visible() -> None:
    """ADR-001: declared-but-unimplemented evals are visibly pending, not hidden."""
    pending = [c.name for c in EVAL_REGISTRY if not c.implemented]
    # These two need an LLM judge / live pipeline; they must stay declared so the
    # coverage gap is explicit until a future sprint implements them.
    assert "memory.recall_semantic" in pending
    assert "governance.refusal_high_risk" in pending


@pytest.mark.skipif(
    True, reason="LLM-judge eval: opt-in only via DAENA_EVAL_JUDGE (no paid call in CI)",
)
def test_eval_llm_judge_placeholder() -> None:
    """Documents the opt-in judge path; intentionally skipped offline."""
