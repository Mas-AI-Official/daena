from __future__ import annotations

import os
from pathlib import Path

from memory_service.bridge import MemoryBridge
from memory_service.memory_bootstrap import load_config, save_config
from memory_service.router import MemoryRouter


def _set_config(path: Path, mode: str = "hybrid", dual: bool = True, canary: int = 100) -> None:
    os.environ["DAENA_MEMORY_CONFIG"] = str(path)
    cfg = load_config(path)
    flags = cfg.setdefault("flags", {})
    flags.update(
        {
            "nbmf_enabled": True,
            "dual_write": bool(dual),
            "read_mode": mode,
            "canary_percent": canary,
        }
    )
    cfg.setdefault("memory_policy", {}).setdefault("fidelity", {})["chat"] = {"mode": "semantic"}
    save_config(cfg, path)


def test_dual_write_and_hybrid_read(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "memory_config.yaml"
    _set_config(config_path, mode="hybrid", canary=100)
    monkeypatch.setenv("DAENA_MEMORY_CONFIG", str(config_path))
    monkeypatch.setenv("DAENA_DUAL_WRITE", "true")

    cfg = load_config(config_path)
    router = MemoryRouter(config=cfg)
    bridge = MemoryBridge(router=router)

    flags = router.flags
    assert flags["dual_write"] is True

    bridge.write("k1", "chat", {"msg": "hello"}, meta={"emotion": {"valence": 0.5}})
    legacy_value = router.read_legacy("k1", "chat")
    assert legacy_value is None  # bridge writes directly to NBMF in cutover path

    out = bridge.read("k1", "chat")
    assert out is not None
    assert out["msg"] == "hello"
    assert out["__meta__"]["emotion"]["valence"] == 0.5

