def test_policy_allows_authorized_role(tmp_path):
    router = MemoryRouter()
    result = router.write("case-2", "legal", {"doc": "draft"}, policy_ctx={"role": "legal.officer"})
    if result.get("status") != "ok":
        result = router.promote_from_quarantine("case-2", "legal")
    assert result["status"] == "ok"
    # read should succeed for same role
    payload = router.read("case-2", "legal", policy_ctx={"role": "legal.officer"})
    assert payload["doc"] == "draft"
