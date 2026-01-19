from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .adapters.l1_embeddings import L1Index
from .adapters.l2_nbmf_store import L2Store
from .adapters.l3_cold_store import L3Store
from .ledger import log_event
from .router import MemoryRouter


@dataclass
class WriteResult:
    status: str
    store: str
    txid: Optional[str] = None


class MemoryBridge:
    """
    Final bridge after cutover. Routes directly to NBMF tiers.
    Legacy reads/writes are disabled by default but can be re-enabled
    by daena_memory_switch --rollback.
    """

    def __init__(self, router: Optional[MemoryRouter] = None) -> None:
        self.router = router or MemoryRouter()
        self.l1: L1Index = self.router.l1
        self.l2: L2Store = self.router.l2
        self.l3: L3Store = self.router.l3

    def write(
        self,
        item_id: str,
        cls: str,
        payload: Dict[str, Any],
        meta: Optional[Dict[str, Any]] = None,
        policy_context: Optional[Dict[str, Any]] = None,
    ) -> WriteResult:
        res = self.router.write_nbmf_only(item_id, cls, payload, meta or {}, policy_ctx=policy_context)
        log_event(action="write", store="nbmf", route="primary", ref=item_id, extra={"cls": cls})
        return WriteResult(status=res.get("status", "ok"), store="nbmf", txid=res.get("txid"))

    def read(self, item_id: str, cls: str, policy_context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        obj = self.router.read_nbmf_only(item_id, cls, policy_ctx=policy_context)
        if obj is not None:
            log_event(action="read", store="nbmf", route="primary", ref=item_id, extra={"cls": cls})
        return obj

    def recall(self, query: str, k: int = 8, policy_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        out = self.router.recall_nbmf_only(query, k=k, policy_ctx=policy_context)
        log_event(action="recall", store="nbmf", route="primary", ref=query)
        return out

