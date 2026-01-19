from __future__ import annotations

from pathlib import Path

from Tools import daena_ledger_verify
from memory_service.ledger import log_event


def test_ledger_verify_cli(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_event(action="write", ref="item1", store="nbmf", route="primary", extra={"cls": "chat"})
    log_event(action="read", ref="item1", store="nbmf", route="primary", extra={"cls": "chat"})

    result = daena_ledger_verify.main(["--ledger-path", ".ledger/ledger.jsonl"])
    assert result == 0

