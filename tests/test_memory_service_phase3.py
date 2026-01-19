from __future__ import annotations

import json
from pathlib import Path
import uuid

import pytest

pytest.importorskip("yaml")

from Tools import daena_consistency_scan, daena_memory_switch, daena_replay
from memory_service.legacy_store import LegacyStore
from memory_service.router import MemoryRouter


def _config(tmp_path: Path):
    cfg = {
        "memory_policy": {
            "fidelity": {
                "legal": {"mode": "lossless"},
                "chat": {"mode": "semantic"},
            }
        },
        "flags": {
            "nbmf_enabled": True,
            "dual_write": True,
            "read_mode": "hybrid",
            "canary_percent": 100,
        },
    }
    config_path = tmp_path / "memory_config.yaml"
    config_path.write_text(json.dumps(cfg), encoding="utf-8")
    return cfg


def test_hybrid_readthrough(tmp_path: Path):
    cfg = _config(tmp_path)
    legacy = LegacyStore()
    router = MemoryRouter(config=cfg, legacy_store=legacy, canary_selector=lambda: 0.9)
    router.write("item-1", "chat", {"note": "hello"})
    assert legacy.read("item-1") is not None
    legacy.delete("item-1")
    result = router.read("item-1", "chat")
    assert result is not None
    assert result["note"] == "hello"


def test_dual_write_policy(tmp_path: Path):
    cfg = _config(tmp_path)
    legacy = LegacyStore()
    router = MemoryRouter(config=cfg, legacy_store=legacy, canary_selector=lambda: 0.9)
    key = f"legal-{uuid.uuid4()}"
    response = router.write(key, "legal", {"contract": "text"}, policy_ctx={"role": "legal.officer"})
    assert "legacy" in response["stores"]
    assert "nbmf" in response["stores"]
    assert router.l2.get_record(key, "legal")["contract"] == "text"


def test_canary_routing(tmp_path: Path):
    cfg = _config(tmp_path)
    router = MemoryRouter(config=cfg, canary_selector=lambda: 0.01)
    router.write("item-canary", "chat", {"note": "hi"})
    assert router.l2.get_record("item-canary", "chat")["note"] == "hi"


def test_divergence_abort_on_critical_class(tmp_path: Path):
    cfg = _config(tmp_path)
    cfg["flags"]["divergence_abort"] = True
    router = MemoryRouter(config=cfg)
    key = f"legal-{uuid.uuid4()}"
    router.write(key, "legal", {"contract": "text"}, policy_ctx={"role": "legal.officer"})
    with pytest.raises(RuntimeError):
        router.write(key, "legal", {"contract": "different"}, policy_ctx={"role": "legal.officer"})


def test_switch_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
flags:
  nbmf_enabled: true
  dual_write: true
  canary_percent: 5
  read_mode: hybrid
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    daena_memory_switch.main(["--config", str(config_path), "--mode", "nbmf", "--canary", "80"])
    updated = config_path.read_text(encoding="utf-8")
    assert "nbmf" in updated


def test_replay_and_consistency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cas_dir = tmp_path / ".llm_cas"
    cas_dir.mkdir()
    sample = {
        "request_signature": "abc",
        "model": "gpt",
        "model_version": "v1",
        "params": {},
        "prompt": "p",
        "response_artifact_key": "a",
        "nbmf_key": "b",
        "embedding_meta": {},
        "provenance": {},
    }
    (cas_dir / "record.json").write_text(json.dumps(sample), encoding="utf-8")
    report = daena_replay.main(["--last", "1", "--cas", str(cas_dir), "--inspect"])
    assert report == 0

    l2 = tmp_path / ".l2_store"
    l3 = tmp_path / ".l3_store"
    l2.mkdir()
    l3.mkdir()
    (l2 / "item.json").write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    (l3 / "item.json").write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    result = daena_consistency_scan.main(["--l2", str(l2), "--l3", str(l3)])
    assert result == 0


def test_router_applies_tenant_compression(tmp_path: Path):
    cfg = _config(tmp_path)
    cfg["tenants"] = {
        "default": {
            "compression": {
                "semantic": {"quantization": "fp16", "delta": True},
                "lossless": {"quantization": "fp32", "delta": False},
            }
        },
        "finance_global": {
            "compression": {
                "semantic": {"quantization": "int8", "delta": True},
            },
        },
    }
    router = MemoryRouter(config=cfg)
    router.write("tenant-item", "chat", {"note": "hi"}, policy_ctx={"tenant_id": "finance_global"})
    record = router.l2.get_full_record("tenant-item", "chat")
    assert record is not None
    meta = record.get("meta", {})
    assert meta.get("tenant_id") == "finance_global"
    assert meta.get("compression", {}).get("profile") == "finance_global"
    assert meta.get("compression", {}).get("mode") == "semantic"

