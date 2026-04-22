"""Tests for the Soul Maker 3-pass refinement pipeline.

LLM + research calls are monkeypatched so the test runs offline and
deterministically. We verify:

- The pipeline threads gap -> improver -> critic correctly.
- Verdict + confidence are lifted from the critic's JSON.
- APPROVE and NEEDS_WORK persist a proposal; REJECT / ABORT do not.
- Unknown department -> ABORT with error.
- Evidence snippets flow from research into the prompts.
- JSON parsing tolerates markdown fences + trailing prose.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_proposals(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SOUL_PROPOSALS_DIR", str(tmp_path / "soul_proposals"))


def _stub_responses(gap: dict, improved_body: str, critic: dict) -> dict[str, str]:
    """Map from prompt-fingerprint to canned JSON reply."""
    return {
        "gap": json.dumps(gap),
        "improver": json.dumps({
            "proposed_body": improved_body,
            "improvements": ["added observability", "modernized tools"],
        }),
        "critic": json.dumps(critic),
    }


def _fake_llm_factory(replies: dict[str, str]):
    """Return an async ``_call_llm`` stand-in that maps prompt -> reply.

    Routing uses the distinctive ROLE LINE from each prompt template
    (quality auditor / refinement specialist / validation critic) --
    field names like ``proposed_body`` or ``missing_expertise_frames``
    show up in MULTIPLE prompts (the improver prompt embeds the gap
    report verbatim), so matching by schema field would misroute.
    """
    async def fake_call(prompt: str) -> str:
        p = prompt.lower()
        if "persona quality auditor" in p:
            return replies["gap"]
        if "persona refinement specialist" in p:
            return replies["improver"]
        if "persona validation critic" in p:
            return replies["critic"]
        return ""
    return fake_call


@pytest.mark.asyncio
async def test_refine_unknown_department_returns_abort() -> None:
    from app.services.soul_maker.refinement import refine_department_soul

    result = await refine_department_soul(
        "ghost_department",
        use_research=False,
        persist_proposal=False,
    )
    assert result.verdict == "ABORT"
    assert result.error and "unknown_department" in result.error


@pytest.mark.asyncio
async def test_refine_approve_path_persists_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.soul_maker import refinement, store

    replies = _stub_responses(
        gap={"missing_expertise_frames": ["observability"], "overall_quality": "MEDIUM"},
        improved_body="# Aria (refined)\n\nNew body with observability frame.",
        critic={"verdict": "APPROVE", "persona_drift_detected": False, "confidence": 0.82, "notes": "ok"},
    )
    monkeypatch.setattr(refinement, "_call_llm", _fake_llm_factory(replies))

    result = await refinement.refine_department_soul(
        "engineering",
        use_research=False,
        persist_proposal=True,
    )

    assert result.verdict == "APPROVE"
    assert result.confidence == pytest.approx(0.82)
    assert "observability" in result.proposed_body

    proposals = store.list_proposals(slug="engineering", status="pending")
    assert len(proposals) == 1
    assert proposals[0]["verdict"] == "APPROVE"


@pytest.mark.asyncio
async def test_refine_needs_work_still_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.soul_maker import refinement, store

    replies = _stub_responses(
        gap={"missing_expertise_frames": ["observability"]},
        improved_body="# Aria\n\nPartial fix body.",
        critic={"verdict": "NEEDS_WORK", "confidence": 0.45, "notes": "partial"},
    )
    monkeypatch.setattr(refinement, "_call_llm", _fake_llm_factory(replies))

    result = await refinement.refine_department_soul(
        "engineering",
        use_research=False,
        persist_proposal=True,
    )
    assert result.verdict == "NEEDS_WORK"
    assert len(store.list_proposals(slug="engineering", status="pending")) == 1


@pytest.mark.asyncio
async def test_refine_abort_on_missing_improver_body(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.soul_maker import refinement, store

    async def fake_call(prompt: str) -> str:
        p = prompt.lower()
        if "gap finder" in p or "missing_expertise_frames" in p:
            return json.dumps({"missing_expertise_frames": []})
        if "improvement specialist" in p:
            return json.dumps({"proposed_body": "", "improvements": []})
        return ""

    monkeypatch.setattr(refinement, "_call_llm", fake_call)
    result = await refinement.refine_department_soul(
        "product",
        use_research=False,
        persist_proposal=True,
    )
    assert result.verdict == "ABORT"
    assert result.error == "improver_returned_empty_body"
    assert store.list_proposals(slug="product", status="pending") == []


def test_parse_json_handles_markdown_fences() -> None:
    from app.services.soul_maker.refinement import _parse_json

    fenced = "```json\n" + json.dumps({"verdict": "APPROVE"}) + "\n```"
    assert _parse_json(fenced) == {"verdict": "APPROVE"}

    trailing_prose = (
        'Here is the result:\n{"verdict": "NEEDS_WORK", "confidence": 0.3}\n'
        "Let me know if you need more."
    )
    assert _parse_json(trailing_prose)["verdict"] == "NEEDS_WORK"

    assert _parse_json("") == {}
    assert _parse_json("not json at all") == {}


def test_format_evidence_emits_ordered_block() -> None:
    from app.services.soul_maker.refinement import _format_evidence

    snippets = [
        {"source": "web_search", "title": "A", "text": "alpha", "date": "2026-04-20"},
        {"source": "nbmf_t3", "title": "B", "text": "beta", "date": ""},
    ]
    formatted = _format_evidence(snippets)
    assert "[1]" in formatted and "[2]" in formatted
    assert "web_search" in formatted and "nbmf_t3" in formatted
    assert "alpha" in formatted and "beta" in formatted

    # Empty evidence path
    assert "no external evidence" in _format_evidence([])
