from __future__ import annotations

from typing import Any, Optional

from .ledger import log_event
from .memory_bootstrap import load_config


class Divergence:
    def __init__(self) -> None:
        self.cfg = load_config()

    def compare_and_log(self, cls: str, legacy: Optional[Any], nbmf: Optional[Any]) -> None:
        if compare_records(legacy, nbmf):
            return
        log_event(action="divergence", store="comparison", route="hybrid", ref=cls, extra={
            "legacy_present": legacy is not None,
            "nbmf_present": nbmf is not None,
        })
        flags = (self.cfg.get("flags") or {})
        if flags.get("divergence_abort", True) and cls in {"legal", "finance", "pii"}:
            raise RuntimeError("DIVERGENCE_ABORT: protected class mismatch")


def compare_records(a: Optional[Any], b: Optional[Any]) -> bool:
    return a == b

