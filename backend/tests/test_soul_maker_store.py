"""Tests for the Soul Maker proposal store (founder-gated promotion).

Uses a temp directory for the proposals root so tests don't pollute
``backend/var/soul_proposals/``. Verifies:

- save_proposal writes a readable JSON record.
- list_proposals filters by slug and status.
- approve_proposal writes the live soul file AND preserves frontmatter.
- reject_proposal leaves the live file untouched.
- Re-deciding an already-decided proposal returns the existing record.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.soul_engine import SoulEngine, _DEPARTMENT_SOUL_PATH


@pytest.fixture(autouse=True)
def _isolate_proposals(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Redirect SOUL_PROPOSALS_DIR so each test gets a clean store."""
    proposals = tmp_path / "soul_proposals"
    monkeypatch.setenv("SOUL_PROPOSALS_DIR", str(proposals))
    yield proposals


def _fake_record(slug: str = "engineering") -> dict:
    return {
        "slug": slug,
        "mind_name": "Aria",
        "original_body": "# Aria\n\nOriginal body text.\n",
        "proposed_body": "# Aria\n\nRefined body with new expertise frames.\n",
        "gap_report": {"missing_expertise_frames": ["observability"]},
        "improvement_notes": ["added observability frame"],
        "critic_report": {"verdict": "APPROVE", "confidence": 0.84},
        "evidence_sources": [{"source": "web_search", "title": "t", "text": "x", "date": ""}],
        "confidence": 0.84,
        "verdict": "APPROVE",
    }


def test_save_and_get_proposal_roundtrips() -> None:
    from app.services.soul_maker.store import get_proposal, save_proposal

    pid = save_proposal(**_fake_record())
    rec = get_proposal(pid)
    assert rec is not None
    assert rec["id"] == pid
    assert rec["status"] == "pending"
    assert rec["slug"] == "engineering"
    assert rec["mind_name"] == "Aria"
    assert rec["verdict"] == "APPROVE"


def test_list_proposals_filters_by_slug_and_status() -> None:
    from app.services.soul_maker.store import list_proposals, save_proposal

    save_proposal(**_fake_record("engineering"))
    save_proposal(**_fake_record("product") | {"mind_name": "Nova"})

    all_pending = list_proposals(status="pending")
    assert len(all_pending) == 2

    eng_only = list_proposals(slug="engineering")
    assert len(eng_only) == 1
    assert eng_only[0]["slug"] == "engineering"

    # status=None returns everything
    assert len(list_proposals(status=None)) == 2


def test_reject_proposal_marks_status_and_leaves_live_file(tmp_path: Path) -> None:
    from app.services.soul_maker.store import get_proposal, reject_proposal, save_proposal

    live_path = _DEPARTMENT_SOUL_PATH / "engineering.md"
    before = live_path.read_text(encoding="utf-8")

    pid = save_proposal(**_fake_record())
    updated = reject_proposal(pid, decided_by="founder@test", notes="not yet")
    assert updated is not None
    assert updated["status"] == "rejected"
    assert updated["decided_by"] == "founder@test"

    # Live file must be untouched
    assert live_path.read_text(encoding="utf-8") == before

    # Second reject on the same proposal is a no-op (already decided)
    again = reject_proposal(pid, decided_by="someone", notes="again")
    assert again is not None
    assert again["status"] == "rejected"  # still the original decision
    assert again["decided_by"] == "founder@test"  # original decider preserved


def test_approve_proposal_writes_live_file_preserving_frontmatter() -> None:
    from app.services.soul_maker.store import approve_proposal, save_proposal

    live_path = _DEPARTMENT_SOUL_PATH / "engineering.md"
    original_file = live_path.read_text(encoding="utf-8")
    # Sanity: the live file has YAML frontmatter we need to preserve
    assert original_file.startswith("---")

    # Use a unique proposed body so we can spot the write
    marker = "REFINED-BY-APPROVE-TEST-sentinel-12345"
    record = _fake_record()
    record["proposed_body"] = f"# Aria\n\n{marker}\n"

    pid = save_proposal(**record)
    try:
        updated = approve_proposal(pid, decided_by="founder@test", notes="ok")
        assert updated is not None
        assert updated["status"] in {"approved", "approved_unverified"}

        # Live file updated
        new_file = live_path.read_text(encoding="utf-8")
        assert new_file.startswith("---"), "frontmatter must be preserved"
        assert marker in new_file, "proposed body must be written"
        # Reload flushed the cache; metadata still loads
        meta = SoulEngine.get_department_metadata("engineering")
        assert meta.get("name") == "Aria", "frontmatter metadata still intact"
    finally:
        # Restore the original file so the suite stays deterministic
        live_path.write_text(original_file, encoding="utf-8")
        SoulEngine.reload()


def test_serialize_proposal_maps_store_keys_to_frontend_contract() -> None:
    """The API boundary must rename store keys to the frontend SoulProposal shape.

    Regression guard: the live approve/reject buttons POSTed to
    ``/souls/proposals/undefined/approve`` because the store persists
    ``id`` / ``slug`` / ``original_body`` / ``decision_notes`` but the
    frontend reads ``proposal_id`` / ``department_slug`` / ``current_body``
    / ``notes``. ``_serialize_proposal`` is the translation; if it drifts,
    the UI silently sends ``undefined`` again.
    """
    from app.api.v1.souls import _serialize_proposal

    stored = {
        "id": "prop-abc-123",
        "slug": "engineering",
        "mind_name": "Aria",
        "status": "pending",
        "verdict": "APPROVE",
        "confidence": 0.84,
        "created_at": "2026-07-01T00:00:00Z",
        "decided_at": None,
        "decided_by": None,
        "decision_notes": "founder note",
        "original_body": "# Aria\n\nOriginal.\n",
        "proposed_body": "# Aria\n\nRefined.\n",
        "improvement_notes": ["added observability frame"],
        "gap_report": {"missing_expertise_frames": ["observability"]},
        "evidence_sources": [{"source": "web_search", "title": "t"}],
    }

    out = _serialize_proposal(stored)

    # Renamed keys -- the whole point of the serializer
    assert out.proposal_id == "prop-abc-123"
    assert out.department_slug == "engineering"
    assert out.current_body == "# Aria\n\nOriginal.\n"
    assert out.notes == "founder note"
    # Pass-through keys
    assert out.mind_name == "Aria"
    assert out.status == "pending"
    assert out.verdict == "APPROVE"
    assert out.confidence == 0.84
    assert out.proposed_body == "# Aria\n\nRefined.\n"
    assert out.improvement_notes == ["added observability frame"]
    assert out.gap_report == {"missing_expertise_frames": ["observability"]}
    assert out.evidence_sources == [{"source": "web_search", "title": "t"}]


def test_serialize_proposal_tolerates_missing_optional_keys() -> None:
    """A minimal stored record must not raise; required ids fall back to ''."""
    from app.api.v1.souls import _serialize_proposal

    out = _serialize_proposal({"slug": "product"})
    assert out.proposal_id == ""  # missing id -> empty, never None/KeyError
    assert out.department_slug == "product"
    assert out.current_body is None
    assert out.notes is None
    assert out.improvement_notes == []
    assert out.gap_report == {}
    assert out.evidence_sources == []
