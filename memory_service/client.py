from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .router import MemoryRouter


@dataclass
class MemoryRecord:
    key: str
    cls: str
    payload: Dict[str, Any]
    meta: Optional[Dict[str, Any]] = None
    policy_context: Optional[Dict[str, Any]] = None


class MemoryClient:
    """Facade used by agents/backends; hides dual-write + read-through logic."""

    def __init__(self, router: Optional[MemoryRouter] = None):
        self.router = router or MemoryRouter()

    def write(self, record: MemoryRecord) -> Dict[str, Any]:
        emotion_meta = (record.meta or {}).get("emotion") if record.meta else None
        policy_context = record.policy_context or ((record.meta or {}).get("policy_context"))
        return self.router.write(
            record.key,
            record.cls,
            record.payload,
            emotion_meta=emotion_meta,
            policy_ctx=policy_context,
        )

    def read(
        self,
        key: str,
        cls: str,
        *,
        tenant: Optional[str] = None,
        policy_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        return self.router.read(key, cls, tenant=tenant, policy_ctx=policy_context)

    def recall(
        self,
        query: str,
        k: int = 8,
        *,
        policy_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return self.router.recall(query, k=k, policy_ctx=policy_context)

