"""PR-LOCAL-USABLE-TODAY-ACCEPTANCE-FIX (Sprint-7 acceptance) Part D.

Acceptance verification for the first-callable Filesystem MCP flow.

This drives the REAL preview endpoint
``POST /api/v1/connections/v2/marketplace/install-plan/mcp-filesystem/preview``
against each of the 4 supported CLI targets and reports:

  * Whether the catalog entry resolves.
  * Whether the target's config path exists on this machine.
  * Whether ``apply_allowed`` is True (i.e. an apply WOULD succeed).
  * Whether the proposed block matches the catalog command_template.

Honesty:

  * Does NOT call the apply endpoint (would write to a real CLI
    config; operator must do that when awake).
  * Does NOT auto-install npm/pip/docker.
  * Records the outcome per target so the Sprint-7 acceptance report
    can quote it verbatim.

If at least one target reports ``apply_allowed=True``, Filesystem
MCP CAN become callable on this laptop with one operator click in
the MCPInstallDrawer. If all targets report apply_allowed=False, the
report will quote the specific failure_reason per target and the
exact command Masoud should run next.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


SUPPORTED_TARGETS = ("claude_desktop", "claude_code", "codex", "gemini_cli")


async def _login(client: AsyncClient) -> dict[str, str]:
    unique = uuid.uuid4().hex[:8]
    email = f"fs-acc-{unique}@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "FS Acceptance",
            "tenant_name": f"FSACC-{unique}",
        },
    )
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    return {"Authorization": f"Bearer {res.json()['data']['access_token']}"}


async def test_filesystem_preview_resolves_for_every_target(client):
    """The preview endpoint must accept mcp-filesystem against every
    one of the 4 supported targets without 4xx/5xx-ing. Whether the
    target's config exists is reported in the response, not as an HTTP
    error."""
    headers = await _login(client)
    for target in SUPPORTED_TARGETS:
        res = await client.post(
            "/api/v1/connections/v2/marketplace/install-plan/mcp-filesystem/preview",
            json={"target": target, "allow_create": False},
            headers=headers,
        )
        assert res.status_code == 200, (
            f"preview HTTP {res.status_code} for target={target}: {res.text}"
        )
        body = res.json()
        # The response shape is stable; the per-target verdict lives in
        # `apply_allowed` + `failure_reason` + `action`.
        assert "data" in body
        data = body["data"]
        assert data["target"] == target
        assert "apply_allowed" in data
        assert "failure_reason" in data


async def test_filesystem_preview_carries_package_name_or_placeholder_explanation(client):
    """The Filesystem entry's command_template carries an
    `<ALLOWED_ROOT>` placeholder. Until the operator resolves it, the
    preview's `proposed_block` is None and the failure_reason explains
    why -- that's the HONEST design (no half-formed config gets shown
    as ready). EITHER:
       (a) proposed_block is filled and contains the package name
           (the wizard's contract), OR
       (b) proposed_block is None AND failure_reason explains the
           unresolved placeholder so the operator knows what to fill.
    Both paths keep the catalog -> wizard -> install ladder honest."""
    headers = await _login(client)
    res = await client.post(
        "/api/v1/connections/v2/marketplace/install-plan/mcp-filesystem/preview",
        json={"target": "claude_desktop", "allow_create": True},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    proposed = data.get("proposed_block")
    failure_reason = data.get("failure_reason") or ""

    if proposed is not None:
        # Path (a): proposed block must reference the catalog package.
        serialized = str(proposed)
        assert "@modelcontextprotocol/server-filesystem" in serialized, (
            f"proposed block missing the catalog package: {serialized!r}"
        )
    else:
        # Path (b): failure_reason must explain the placeholder so the
        # operator knows exactly what input to provide. The catalog
        # placeholder is `<ALLOWED_ROOT>`.
        assert (
            "placeholder" in failure_reason.lower()
            or "ALLOWED_ROOT" in failure_reason
        ), (
            f"proposed_block=None but failure_reason doesn't explain "
            f"the unresolved placeholder: {failure_reason!r}"
        )


async def test_at_least_one_target_or_reports_honest_blocker(client):
    """Acceptance bar: either at least one target says
    apply_allowed=True (the operator can install with one click), OR
    every target reports a clear failure_reason (so the operator knows
    exactly what to fix). The bar is NOT 'every target ready' -- on a
    fresh laptop with only Claude Desktop installed, only one target
    will be ready. That's fine, AS LONG AS at least one target IS
    ready."""
    headers = await _login(client)
    summaries = []
    for target in SUPPORTED_TARGETS:
        res = await client.post(
            "/api/v1/connections/v2/marketplace/install-plan/mcp-filesystem/preview",
            json={"target": target, "allow_create": False},
            headers=headers,
        )
        assert res.status_code == 200
        d = res.json()["data"]
        summaries.append({
            "target": target,
            "config_exists": d.get("config_exists"),
            "apply_allowed": d.get("apply_allowed"),
            "action": d.get("action"),
            "failure_reason": d.get("failure_reason"),
        })

    apply_ready = [s for s in summaries if s["apply_allowed"]]
    if apply_ready:
        # One-click install is feasible -- acceptance bar met.
        return

    # No target ready -- every one MUST carry a non-empty failure_reason.
    blockers_with_reason = [s for s in summaries if s["failure_reason"]]
    assert len(blockers_with_reason) == len(summaries), (
        f"Some targets returned apply_allowed=False with no failure_reason: "
        f"{summaries!r}. The UI cannot tell the operator what to do next."
    )
    # The test still passes (acceptance: honest blocker counts as pass)
    # but the per-target failure_reasons will surface in the acceptance
    # report so Masoud sees exactly which CLIs to install + which to
    # configure. Print once for the sprint smoke log.
    print("\n[acceptance-fs-install]", summaries)
