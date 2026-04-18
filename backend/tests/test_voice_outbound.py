"""Outbound telephony tests (Phase I.5).

Covers: pipeline registration, VAPI missing-credential graceful error,
DryRun provider happy path, pipeline dispatch, end_call no-crash.
"""

from __future__ import annotations

import uuid

import pytest

from app.services.voice.outbound import (
    CallHandle,
    DryRunProvider,
    OutboundError,
    OutboundPipeline,
    VapiProvider,
)


@pytest.mark.asyncio
async def test_dry_run_provider_returns_handle() -> None:
    pipe = OutboundPipeline()
    handle = await pipe.place_call(
        to_number="+14155550199",
        from_number="+14155550100",
    )
    assert isinstance(handle, CallHandle)
    assert handle.provider == "dry_run"
    assert handle.status == "dry_run"
    assert handle.id.startswith("dry-")


@pytest.mark.asyncio
async def test_vapi_missing_credentials_returns_error() -> None:
    """Without VAPI_API_KEY env, place_call returns structured OutboundError."""
    pipe = OutboundPipeline()
    pipe.register(VapiProvider(api_key="", phone_number_id=""))
    result = await pipe.place_call(
        to_number="+14155550199",
        from_number="+14155550100",
        provider="vapi",
    )
    assert isinstance(result, OutboundError)
    assert result.recoverable is False
    assert "VAPI_API_KEY" in result.reason or "VAPI_PHONE_NUMBER_ID" in result.reason


@pytest.mark.asyncio
async def test_unknown_provider_returns_error() -> None:
    pipe = OutboundPipeline()
    result = await pipe.place_call(
        to_number="+1", from_number="+1", provider="not_registered",
    )
    assert isinstance(result, OutboundError)


@pytest.mark.asyncio
async def test_end_call_no_crash_on_dry_run() -> None:
    pipe = OutboundPipeline()
    handle = await pipe.place_call(
        to_number="+14155550199",
        from_number="+14155550100",
    )
    assert isinstance(handle, CallHandle)
    await pipe.end_call(handle)  # should no-op gracefully


@pytest.mark.asyncio
async def test_pipeline_registers_multiple_providers() -> None:
    pipe = OutboundPipeline()
    pipe.register(VapiProvider(api_key="test", phone_number_id="pn-123"))
    providers = pipe.available()
    assert "dry_run" in providers
    assert "vapi" in providers


@pytest.mark.asyncio
async def test_call_handle_carries_conversation_id() -> None:
    conv_id = uuid.uuid4()
    pipe = OutboundPipeline()
    handle = await pipe.place_call(
        to_number="+14155550199",
        from_number="+14155550100",
        conversation_id=conv_id,
        metadata={"skill_ref": "skill:sales.cold-email.problem-agitate-solve"},
    )
    assert isinstance(handle, CallHandle)
    assert handle.conversation_id == conv_id
    assert handle.metadata.get("skill_ref") == "skill:sales.cold-email.problem-agitate-solve"
