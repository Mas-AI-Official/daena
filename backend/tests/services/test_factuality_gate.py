"""Tests for FactualityGate. Avoids hitting a real ragx by patching httpx."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import pytest

from app.services.factuality_gate import FactualityGate, FactualityVerdict


@dataclass
class _FakeResponse:
    status_code: int
    payload: dict[str, Any]

    def json(self) -> dict[str, Any]:
        return self.payload


class _FakeClient:
    """Stand-in for httpx.AsyncClient. Returns scripted responses keyed by URL suffix."""

    def __init__(self, route_map: dict[str, _FakeResponse], raise_on: set[str] | None = None) -> None:
        self.route_map = route_map
        self.raise_on = raise_on or set()
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        return None

    async def post(self, url: str, json: dict[str, Any] | None = None) -> _FakeResponse:
        self.calls.append((url, json))
        for suffix, resp in self.route_map.items():
            if url.endswith(suffix) or suffix in url:
                if suffix in self.raise_on:
                    import httpx
                    raise httpx.RequestError("simulated outage")
                return resp
        return _FakeResponse(status_code=404, payload={})

    async def get(self, url: str) -> _FakeResponse:
        self.calls.append((url, None))
        for suffix, resp in self.route_map.items():
            if url.endswith(suffix):
                return resp
        return _FakeResponse(status_code=404, payload={})


def _install_fake(monkeypatch: pytest.MonkeyPatch, client: _FakeClient) -> None:
    @asynccontextmanager
    async def _cm(*args: Any, **kwargs: Any):
        async with client as c:
            yield c

    # `httpx.AsyncClient(...)` returns a context manager; we wrap our fake.
    def _factory(*args: Any, **kwargs: Any) -> _FakeClient:
        return client

    monkeypatch.setattr("app.services.factuality_gate.httpx.AsyncClient", _factory)


@pytest.mark.asyncio
async def test_verify_returns_unavailable_when_ragx_down(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient(route_map={"/query": _FakeResponse(500, {})},
                         raise_on={"/query"})
    _install_fake(monkeypatch, client)

    v = await FactualityGate.verify(query="anything", candidate_answer="x",
                                    collections=("daena-code",))
    assert isinstance(v, FactualityVerdict)
    assert v.available is False
    assert v.abstain is True
    assert v.confidence == 0.0
    assert v.candidate == "x"
    assert "ragx unreachable" in v.reasons[0]


@pytest.mark.asyncio
async def test_verify_pass_with_citations(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient(route_map={"/query": _FakeResponse(200, {
        "answer": None,
        "citations": [{"chunk_id": "abc:0", "source_path": "p", "score": 0.91,
                       "snippet": "..."}],
        "confidence": 0.91,
        "abstained": False,
        "reason": None,
        "stats": {},
        "timing_ms": {},
    })})
    _install_fake(monkeypatch, client)

    v = await FactualityGate.verify(query="q", candidate_answer="a",
                                    collections=("daena-code",))
    assert v.available is True
    assert v.abstain is False
    assert v.confidence == pytest.approx(0.91)
    assert len(v.citations) == 1
    assert v.citations[0].source_path == "p"


@pytest.mark.asyncio
async def test_verify_abstains_when_evidence_weak(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient(route_map={"/query": _FakeResponse(200, {
        "answer": None,
        "citations": [],
        "confidence": 0.0,
        "abstained": True,
        "reason": "insufficient evidence: 0 chunk(s) below min_recall=2",
        "stats": {},
        "timing_ms": {},
    })})
    _install_fake(monkeypatch, client)

    v = await FactualityGate.verify(query="q", candidate_answer="a",
                                    collections=("daena-code",))
    assert v.available is True
    assert v.abstain is True
    assert v.citations == []
    assert "insufficient evidence" in v.reasons[0]


@pytest.mark.asyncio
async def test_verify_handles_no_collections() -> None:
    v = await FactualityGate.verify(query="q", candidate_answer="a", collections=[])
    assert v.available is False
    assert v.abstain is True
    assert v.reasons == ["no collections configured"]
