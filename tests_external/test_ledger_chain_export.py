from __future__ import annotations

import json
import sys
from pathlib import Path

raise RuntimeError('test file loaded')

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import Tools.ledger_chain_export as ledger_chain_export


def test_merkle_root_and_output(tmp_path: Path, monkeypatch):
    ledger_path = tmp_path / "ledger.jsonl"
    entries = [
        {"txid": "a", "payload": 1},
        {"txid": "b", "payload": 2},
        {"txid": "c", "payload": 3},
    ]
    ledger_path.write_text("\n".join(json.dumps(entry) for entry in entries), encoding="utf-8")
    output = tmp_path / "summary.json"
    monkeypatch.setattr("sys.argv", ["ledger_chain_export", "--ledger", str(ledger_path), "--output", str(output)])
    ledger_chain_export.main()
    summary = json.loads(output.read_text(encoding="utf-8"))
    assert summary["entries"] == 3
    assert summary["merkle_root"]


def test_chain_posting(tmp_path: Path, monkeypatch):
    ledger_path = tmp_path / "ledger.jsonl"
    entries = [{"txid": "x", "payload": 1}]
    ledger_path.write_text("\n".join(json.dumps(entry) for entry in entries), encoding="utf-8")

    def fake_post(endpoint, payload, token=None):
        return "ok"

    monkeypatch.setattr("Tools.ledger_chain_export._post_to_chain", fake_post)
    monkeypatch.setattr("sys.argv", ["ledger_chain_export", "--ledger", str(ledger_path), "--chain-endpoint", "https://chain"])
    ledger_chain_export.main()
