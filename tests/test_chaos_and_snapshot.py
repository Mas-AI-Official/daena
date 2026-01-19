from __future__ import annotations

import json
from pathlib import Path

from Tools import daena_chaos, daena_snapshot


def test_snapshot_cli(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    records = Path(".l2_store/records")
    records.mkdir(parents=True)
    path = records / "sample.json"
    path.write_text(json.dumps({"payload": {"msg": "hi"}, "meta": {}}), encoding="utf-8")
    result = daena_snapshot.main(["--l2", str(records), "--l3", str(tmp_path / ".l3_store/records"), "--label", "test"])
    assert result == 0


def test_chaos_cli_l2_disconnect(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    records = Path(".l2_store/records")
    records.mkdir(parents=True)
    (records / "item.json").write_text("{}", encoding="utf-8")
    result = daena_chaos.main(["--scenario", "l2_disconnect", "--l2", str(tmp_path / ".l2_store")])
    assert result == 0
    assert records.exists()
    result_execute = daena_chaos.main(["--scenario", "l2_disconnect", "--execute", "--l2", str(tmp_path / ".l2_store")])
    assert result_execute == 0
    assert records.exists()

