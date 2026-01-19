from __future__ import annotations

import json
from pathlib import Path

import pytest

from Tools import daena_policy_inspector
from memory_service.crypto import refresh as refresh_crypto
from memory_service.edge_sdk import EdgeNBMFClient


def test_edge_sdk_prepare_update_and_delta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    refresh_crypto()
    client = EdgeNBMFClient(root=tmp_path / "edge_cache", edge_id="edge-42")

    pkg1 = client.prepare_update(
        "item-1",
        {"message": "hello"},
        tenant_id="tenant-a",
        fidelity="semantic",
        meta={"tags": ["greeting"]},
    )
    assert pkg1.delta is None
    assert pkg1.base_hash is None

    pkg2 = client.prepare_update(
        "item-1",
        {"message": "hello world"},
        tenant_id="tenant-a",
        fidelity="semantic",
    )
    assert pkg2.delta is not None
    assert pkg2.base_hash == pkg1.nbmf.get("sig")
    assert pkg2.delta  # unified diff string should not be empty

    reconstructed = client.apply_delta({"message": "hello"}, pkg2.delta)
    assert reconstructed == {"message": "hello world"}

    cached = client.load_cached("item-1")
    assert cached is not None
    assert cached["nbmf"]["meta"]["fidelity"] == "semantic"


def test_policy_inspector_cli_outputs_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.chdir(tmp_path)
    policy_cfg = tmp_path / "policy.yaml"
    memory_cfg = tmp_path / "memory.yaml"

    policy_cfg.write_text(
        """
default:
  allow: true
classes:
  chat:
    allow_roles: [agent, admin]
    deny_roles: [guest]
    allow_tenants: [tenant-a]
  legal:
    allow_roles: [legal.officer]
""".strip(),
        encoding="utf-8",
    )

    memory_cfg.write_text(
        json.dumps(
            {
                "memory_policy": {
                    "fidelity": {
                        "chat": {"mode": "semantic"},
                        "legal": {"mode": "lossless"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    exit_code = daena_policy_inspector.main(
        [
            "--policy",
            str(policy_cfg),
            "--memory",
            str(memory_cfg),
        ]
    )
    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["default_allow"] is True
    assert output["classes"]["chat"]["fidelity"] == "semantic"
    assert "tenant-a" in output["classes"]["chat"]["allow_tenants"]
    assert output["classes"]["legal"]["fidelity"] == "lossless"
