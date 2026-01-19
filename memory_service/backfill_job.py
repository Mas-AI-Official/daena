from __future__ import annotations

from typing import Optional

from .router import MemoryRouter


def backfill(last_n: int = 1000, tenant: Optional[str] = None):
    """
    Re-encode recent legacy writes into NBMF asynchronously (stub implementation).
    """
    router = MemoryRouter()
    return {"status": "queued", "count": last_n, "tenant": tenant, "flags": router.flags()}

