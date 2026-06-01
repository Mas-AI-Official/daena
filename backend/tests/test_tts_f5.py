"""F5-TTS provider chain for /tts/speak + honest /tts/defaults.

Daena's TTS provider order is F5-TTS local (voice clone) -> Edge-TTS -> (then
client-side ElevenLabs -> browser). These tests lock the backend half of that
chain WITHOUT touching the network: the F5 HTTP probe/synthesis and the Edge
stream are monkeypatched at their module seams (app.api.v1.tts._f5_probe,
._f5_synthesize, ._edge_stream_iter, ._edge_available).

They also re-assert that the provider rewrite did NOT drop the auth gate added
earlier (unauthenticated /tts/speak must still 401).
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

TTS = "app.api.v1.tts"


@pytest.mark.asyncio
async def test_speak_unauthenticated_still_blocked(client: AsyncClient) -> None:
    """The F5/provider rewrite must preserve the auth gate."""
    res = await client.post("/api/v1/tts/speak", json={"text": "hello"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_auto_prefers_f5_when_available(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch,
) -> None:
    """provider=auto uses F5 first when the F5 service is healthy."""
    async def fake_probe() -> dict:
        return {"available": True, "reason": "ok", "health": {"device": "cpu"}}

    async def fake_synth(text: str, speed: float) -> bytes:
        return b"F5FAKEMP3" + b"\x00" * 200

    monkeypatch.setattr(f"{TTS}._f5_probe", fake_probe)
    monkeypatch.setattr(f"{TTS}._f5_synthesize", fake_synth)

    res = await client.post(
        "/api/v1/tts/speak",
        json={"text": "hello", "provider": "auto"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.headers.get("X-Daena-TTS-Provider") == "f5"
    assert res.content.startswith(b"F5FAKEMP3")


@pytest.mark.asyncio
async def test_auto_falls_back_to_edge_when_f5_down(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch,
) -> None:
    """provider=auto silently degrades to Edge when F5 is unavailable.

    No real network: both the F5 probe and the Edge stream are stubbed.
    """
    async def fake_probe() -> dict:
        return {"available": False, "reason": "service unreachable", "health": None}

    async def fake_edge_iter(text, voice, rate, pitch, volume):
        yield b"EDGEFAKE"

    monkeypatch.setattr(f"{TTS}._f5_probe", fake_probe)
    monkeypatch.setattr(f"{TTS}._edge_available", lambda: True)
    monkeypatch.setattr(f"{TTS}._edge_stream_iter", fake_edge_iter)

    res = await client.post(
        "/api/v1/tts/speak",
        json={"text": "hello", "provider": "auto"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.headers.get("X-Daena-TTS-Provider") == "edge"
    assert b"EDGEFAKE" in res.content


@pytest.mark.asyncio
async def test_explicit_f5_returns_502_when_unavailable(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch,
) -> None:
    """provider=f5 (explicit) must NOT silently fall back to Edge -> 502."""
    async def fake_probe() -> dict:
        return {"available": False, "reason": "service unreachable at :9101", "health": None}

    monkeypatch.setattr(f"{TTS}._f5_probe", fake_probe)

    res = await client.post(
        "/api/v1/tts/speak",
        json={"text": "hello", "provider": "f5"},
        headers=auth_headers,
    )
    assert res.status_code == 502
    # No stack trace leaks; the detail is a human-readable reason.
    assert "F5-TTS unavailable" in res.json()["detail"]


@pytest.mark.asyncio
async def test_elevenlabs_provider_rejected_clientside(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    """elevenlabs/browser are client-side; the backend rejects them clearly."""
    res = await client.post(
        "/api/v1/tts/speak",
        json={"text": "hello", "provider": "elevenlabs"},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "client-side" in res.json()["detail"]


@pytest.mark.asyncio
async def test_defaults_reports_providers_honestly(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch,
) -> None:
    """/tts/defaults exposes preferred provider, fallback chain, and HONEST
    availability (no fake 'F5 ready' when the service is down)."""
    async def fake_probe() -> dict:
        return {"available": False, "reason": "service unreachable at http://127.0.0.1:9101", "health": None}

    monkeypatch.setattr(f"{TTS}._f5_probe", fake_probe)

    res = await client.get("/api/v1/tts/defaults", headers=auth_headers)
    assert res.status_code == 200
    tts = res.json()["tts"]
    assert tts["preferred_provider"] == "f5"
    assert tts["default_provider"] == "auto"
    assert tts["fallback_chain"] == ["f5", "edge", "elevenlabs", "browser"]
    assert set(tts["providers"]) == {"f5", "edge", "elevenlabs", "browser"}
    # F5 down -> honest false + a reason; active provider is NOT f5.
    assert tts["providers"]["f5"]["available"] is False
    assert tts["providers"]["f5"]["reason"]
    assert tts["active_provider"] in ("edge", "none")


def test_reference_wav_env_override(monkeypatch) -> None:
    """An explicit F5_TTS_REFERENCE_WAV env wins over auto-discovery."""
    from app.api.v1 import tts as tts_mod
    monkeypatch.setenv("F5_TTS_REFERENCE_WAV", "X:/custom/ref.wav")
    assert tts_mod._f5_reference_wav() == "X:/custom/ref.wav"


def test_reference_wav_autodiscovers_or_none(monkeypatch) -> None:
    """With no env override, resolve to the repo's daena_voice.wav if present,
    else None (delegate to the F5 service default) - never a crash, never a
    hardcoded personal path."""
    from app.api.v1 import tts as tts_mod
    monkeypatch.delenv("F5_TTS_REFERENCE_WAV", raising=False)
    ref = tts_mod._f5_reference_wav()
    assert ref is None or ref.replace("\\", "/").endswith("daena_voice.wav")


@pytest.mark.asyncio
async def test_defaults_reports_daena_resolved_reference_not_f5_default(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch, tmp_path,
) -> None:
    """/tts/defaults must report Daena's RESOLVED reference path and whether
    THAT file exists - never the F5 service's internal default path.

    Regression: F5 service /health returns its own hardcoded
    ``default_reference`` and ``default_reference_exists``. On founder
    machines that path may be missing (the service ships with a generic
    default), while Daena's resolved path (env override or repo-relative
    ``daena_voice.wav``) is the one actually used on every synth call. The
    /defaults UI was reading the F5-side flag and showing a misleading
    'reference missing' even when synthesis was working.
    """
    # Make Daena's resolved reference a real file in tmp_path.
    real_ref = tmp_path / "daena_voice.wav"
    real_ref.write_bytes(b"RIFF....fake-wav-for-test")
    monkeypatch.setenv("F5_TTS_REFERENCE_WAV", str(real_ref))

    # F5 service reports its own internal default as missing (the common
    # case after upgrading or moving the repo).
    async def fake_probe() -> dict:
        return {
            "available": True,
            "reason": "ok",
            "health": {
                "default_reference": "C:/some/old/path/daena_voice.wav",
                "default_reference_exists": False,
                "device": "cuda",
                "model_loaded": True,
            },
        }
    monkeypatch.setattr(f"{TTS}._f5_probe", fake_probe)

    res = await client.get("/api/v1/tts/defaults", headers=auth_headers)
    assert res.status_code == 200
    f5 = res.json()["tts"]["providers"]["f5"]
    # Daena reports its OWN resolved path, not the F5 service default.
    assert f5["reference_path"] == str(real_ref)
    # And reports whether THAT file exists - which it does.
    assert f5["reference_exists"] is True
