from __future__ import annotations

import sys
from pathlib import Path

from memory_service.migration import finalize_backfill
from memory_service.router import MemoryRouter
from Tools import daena_memory_switch


def test_cutover_and_rollback(tmp_path: Path, monkeypatch):
    config_path = Path("config/memory_config.yaml")
    monkeypatch.setenv("DAENA_MEMORY_CONFIG", str(config_path))

    router = MemoryRouter()
    legacy = router.legacy_store
    legacy.put("id1", {"t": "hello"}, "chat")

    summary = finalize_backfill(router)
    assert summary["mismatches"] == 0

    sys.argv = ["", "--mode", "cutover", "--config", str(config_path)]
    daena_memory_switch.main()
    router_after = MemoryRouter()
    assert router_after.flags["read_mode"] == "nbmf"
    try:
        router_after.legacy_write("x", "chat", {"t": "x"})
        assert False, "legacy write must raise after cutover"
    except RuntimeError:
        pass

    sys.argv = ["", "--mode", "rollback", "--config", str(config_path)]
    daena_memory_switch.main()
    router_rollback = MemoryRouter()
    assert router_rollback.flags["read_mode"] == "legacy"
    assert router_rollback.flags["dual_write"] is True
