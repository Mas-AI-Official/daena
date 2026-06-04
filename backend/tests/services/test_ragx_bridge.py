"""Tests for the ragx_bridge module. Uses httpx mocking so no live service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ragx_bridge import (
    RagxCitation,
    RagxResult,
    format_ragx_evidence_block,
    query_ragx,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    def __init__(self, route_map: dict[str, _FakeResponse]) -> None:
        self.route_map = route_map
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, json: dict[str, Any] | None = None) -> _FakeResponse:
        self.calls.append((url, json or {}))
        # The route_map keys match by collection name in the json body
        coll = (json or {}).get("collection", "")
        return self.route_map.get(coll, _FakeResponse(404, {}))


def _patch_client(client: _FakeClient):
    def _factory(*_args: Any, **_kwargs: Any) -> _FakeClient:
        return client

    return patch("app.services.ragx_bridge.httpx.AsyncClient", _factory)


@pytest.mark.asyncio
async def test_query_returns_citations_from_multiple_collections() -> None:
    client = _FakeClient({
        "daena-docs": _FakeResponse(200, {
            "abstained": False,
            "citations": [
                {"chunk_id": "abc:0", "source_path": "Doc/Shield.md",
                 "score": 0.91, "snippet": "Shield is the security pipeline"},
            ],
        }),
        "wiki": _FakeResponse(200, {
            "abstained": False,
            "citations": [
                {"chunk_id": "def:1", "source_path": "wiki/governance.md",
                 "score": 0.74, "snippet": "Governance modes are UNLEASHED, BALANCED, GOVERNED"},
            ],
        }),
    })
    with _patch_client(client):
        result = await query_ragx(
            query="how does Daena enforce security?",
            collections=("daena-docs", "wiki"),
        )
    assert isinstance(result, RagxResult)
    assert result.available is True
    assert len(result.citations) == 2
    # Citations are score-sorted descending
    assert result.citations[0].chunk_id == "abc:0"
    assert result.citations[0].collection == "daena-docs"


@pytest.mark.asyncio
async def test_query_handles_abstention_signal() -> None:
    client = _FakeClient({
        "wiki": _FakeResponse(200, {
            "abstained": True,
            "reason": "no strong evidence",
            "citations": [],
        }),
    })
    with _patch_client(client):
        result = await query_ragx(query="anything", collections=("wiki",))
    assert result.available is True
    assert result.citations == []
    assert "wiki" in result.abstained_collections


@pytest.mark.asyncio
async def test_query_fails_open_when_ragx_down() -> None:
    import httpx

    class _BoomClient(_FakeClient):
        async def post(self, *args: Any, **kwargs: Any):
            raise httpx.RequestError("ragx unreachable")

    client = _BoomClient({})
    with _patch_client(client):
        result = await query_ragx(query="anything", collections=("wiki",))
    assert result.available is False
    assert result.citations == []


def test_format_evidence_block_renders_citations() -> None:
    citations = [
        RagxCitation(
            chunk_id="abc123def456",
            source_path="D:/Ideas/Daena/Doc/Shield.md",
            score=0.91,
            snippet="Shield is the always-on protection layer",
            collection="daena-docs",
        ),
    ]
    result = RagxResult(citations=citations)
    block = format_ragx_evidence_block(result)
    assert "Universal RAG citations" in block
    assert "Shield.md" in block
    assert "daena-docs" in block
    assert "chunk_id abc123def4" in block


def test_format_evidence_block_empty_returns_empty_string() -> None:
    assert format_ragx_evidence_block(RagxResult()) == ""


@pytest.mark.asyncio
async def test_empty_query_returns_unavailable() -> None:
    result = await query_ragx(query="   ", collections=("wiki",))
    assert result.available is False
    assert result.citations == []
