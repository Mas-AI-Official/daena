from __future__ import annotations

import json
from pathlib import Path

import pytest

from Tools import ledger_chain_export
from memory_service.audit import ledger_audit
from memory_service.ledger import Ledger


def test_ledger_audit_counts(tmp_path: Path):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger = Ledger(ledger_path)
    ledger.write("write", "id1", "hash1", {"store": "nbmf", "route": "primary"})
    ledger.write("read", "id2", "hash2", {"store": "nbmf", "route": "primary"})
    ledger.write("write", "id3", "hash3", {"store": "legacy", "route": "fallback"})

    summary = ledger_audit(ledger_path, recent=2)
    assert summary["entries"] == 3
    assert summary["actions"]["write"] == 2
    assert summary["stores"]["nbmf"] == 2
    assert len(summary["recent"]) == 2
    assert summary["merkle_root"]


def test_ledger_chain_export_cli_writes_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger = Ledger(ledger_path)
    ledger.write("write", "item1", "hash1", {"store": "nbmf", "route": "primary"})
    ledger.write("write", "item2", "hash2", {"store": "nbmf", "route": "primary"})

    manifest_out = tmp_path / "manifest.json"
    monkeypatch.chdir(tmp_path)
    exit_code = ledger_chain_export.main([
        "--ledger-path",
        str(ledger_path),
        "--out",
        str(manifest_out),
        "--note",
        "nightly",
        "--print",
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "merkle_root" in captured.out
    assert manifest_out.exists()
    manifest = json.loads(manifest_out.read_text(encoding="utf-8"))
    assert manifest["entries"] == 2
    assert manifest["note"] == "nightly"
    assert manifest["merkle_root"]


def test_sec_loop_events_logged(tmp_path: Path):
    """Test that SEC-Loop events are logged to ledger."""
    ledger_path = tmp_path / "ledger.jsonl"
    ledger = Ledger(ledger_path)
    
    # Log SEC promotion event
    ledger.write(
        "sec_promote_abstract",
        "sec_abstract_123",
        "hash_sec_123",
        {
            "store": "nbmf",
            "route": "sec_loop",
            "abstract_id": "abstract_123",
            "decision_id": "decision_456",
            "department": "engineering"
        }
    )
    
    # Log SEC rollback event
    ledger.write(
        "sec_rollback_promotion",
        "sec_abstract_123",
        "hash_sec_123",
        {
            "store": "nbmf",
            "route": "sec_loop",
            "abstract_id": "abstract_123",
            "reverted_at": 1234567890.0
        }
    )
    
    # Verify events are in ledger
    summary = ledger_audit(ledger_path, recent=10)
    assert summary["entries"] == 2
    assert "sec_promote_abstract" in summary.get("actions", {})
    assert "sec_rollback_promotion" in summary.get("actions", {})


def test_sec_loop_merkle_includes_events(tmp_path: Path):
    """Test that SEC-Loop events are included in Merkle root."""
    ledger_path = tmp_path / "ledger.jsonl"
    ledger = Ledger(ledger_path)
    
    # Add regular and SEC events
    ledger.write("write", "item1", "hash1", {"store": "nbmf"})
    ledger.write("sec_promote_abstract", "sec_1", "hash_sec1", {"store": "nbmf", "route": "sec_loop"})
    ledger.write("write", "item2", "hash2", {"store": "nbmf"})
    
    # Export manifest
    manifest_out = tmp_path / "manifest.json"
    exit_code = ledger_chain_export.main([
        "--ledger-path", str(ledger_path),
        "--out", str(manifest_out),
        "--print"
    ])
    
    assert exit_code == 0
    manifest = json.loads(manifest_out.read_text(encoding="utf-8"))
    assert manifest["entries"] == 3  # All entries included
    assert manifest["merkle_root"]  # Merkle root includes SEC events