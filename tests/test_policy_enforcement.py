from __future__ import annotations

import pytest

from memory_service.router import MemoryRouter


def test_policy_denies_illegal_role_for_legal_class(tmp_path):
    router = MemoryRouter()
    with pytest.raises(PermissionError):
        router.write("case-1", "legal", {"doc": "draft"}, policy_ctx={"role": "finance.analyst"})


def test_policy_allows_authorized_role(tmp_path):
    router = MemoryRouter()
    result = router.write("case-2", "legal", {"doc": "draft"}, policy_ctx={"role": "legal.officer"})
    assert result["status"] == "ok"
    # read should succeed for same role
    payload = router.read("case-2", "legal", policy_ctx={"role": "legal.officer"})
    assert payload["doc"] == "draft"

