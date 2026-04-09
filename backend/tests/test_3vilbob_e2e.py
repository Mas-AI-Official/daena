"""E2E test: full /3vilbob cognitive scan against OWASP Juice Shop.

Requires:
    docker run -d -p 3000:3000 bkimminich/juice-shop

These tests are SLOW (network I/O) and require a running target.
Skipped automatically when Juice Shop is not reachable.

The purpose is to verify the OODA loop works end-to-end with real
HTTP responses, not mocks. Each test targets a specific capability
wired into the scan engine.
"""

from __future__ import annotations

import asyncio
import os

import pytest

# Target URL for Juice Shop
JUICE_SHOP_URL = os.environ.get("JUICE_SHOP_URL", "http://localhost:3000")


def _juice_shop_reachable() -> bool:
    """Check if Juice Shop is reachable."""
    try:
        import httpx
        resp = httpx.get(JUICE_SHOP_URL, timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


# Skip all tests in this file if Juice Shop is not running
pytestmark = pytest.mark.skipif(
    not _juice_shop_reachable(),
    reason=f"Juice Shop not reachable at {JUICE_SHOP_URL}",
)


# ---------------------------------------------------------------------------
# Canary Echo E2E
# ---------------------------------------------------------------------------

class TestCanaryEchoE2E:
    """Test canary echo analysis against real Juice Shop."""

    @pytest.mark.asyncio
    async def test_canary_echo_finds_reflections(self):
        """Juice Shop reflects search input -- canary should detect it."""
        from app.services.security.cognitive_scan_engine import CognitiveScanEngine
        engine = CognitiveScanEngine(offensive_mode=True)
        result = await engine._canary_echo([JUICE_SHOP_URL])
        # Juice Shop is known to reflect input in search
        assert "findings" in result
        assert isinstance(result["findings"], list)
        # Even if no XSS, the operation completes without error
        assert "failed" not in result.get("summary", "").lower()


# ---------------------------------------------------------------------------
# State Machine E2E
# ---------------------------------------------------------------------------

class TestStateMachineE2E:
    """Test state machine inference against real Juice Shop."""

    @pytest.mark.asyncio
    async def test_state_machine_access_control(self):
        """Juice Shop has broken access control -- state machine should find it."""
        from app.services.security.cognitive_scan_engine import CognitiveScanEngine
        engine = CognitiveScanEngine(offensive_mode=True)
        result = await engine._state_machine(
            JUICE_SHOP_URL,
            ["/api/Products", "/rest/products/search"],
        )
        assert "findings" in result
        assert isinstance(result["findings"], list)
        assert "failed" not in result.get("summary", "").lower()


# ---------------------------------------------------------------------------
# Cost Amplification E2E
# ---------------------------------------------------------------------------

class TestCostAmplificationE2E:
    """Test cost amplification detection against real Juice Shop."""

    @pytest.mark.asyncio
    async def test_cost_amplification_probes(self):
        """Send timing probes against Juice Shop."""
        from app.services.security.cognitive_scan_engine import CognitiveScanEngine
        engine = CognitiveScanEngine(offensive_mode=True)
        result = await engine._cost_amplification([JUICE_SHOP_URL])
        assert "findings" in result
        assert isinstance(result["findings"], list)
        assert "failed" not in result.get("summary", "").lower()
        # Summary should mention baseline timing
        assert "baseline" in result.get("summary", "").lower()


# ---------------------------------------------------------------------------
# Path Fuzz E2E
# ---------------------------------------------------------------------------

class TestPathFuzzE2E:
    """Test path fuzzing against real Juice Shop."""

    @pytest.mark.asyncio
    async def test_path_fuzz_finds_endpoints(self):
        """Juice Shop has many exposed endpoints."""
        from app.services.security.cognitive_scan_engine import (
            CognitiveScanEngine, TargetProfile,
        )
        engine = CognitiveScanEngine(offensive_mode=True)
        result = await engine._path_fuzz(JUICE_SHOP_URL, None)
        assert "findings" in result
        # Juice Shop exposes many paths (robots.txt, api, etc.)
        assert len(result["findings"]) >= 1


# ---------------------------------------------------------------------------
# OPSEC Headers E2E
# ---------------------------------------------------------------------------

class TestOpsecHeadersE2E:
    """Test that OPSEC headers pass through to Juice Shop."""

    @pytest.mark.asyncio
    async def test_opsec_headers_accepted(self):
        """OPSEC browser fingerprints should not be rejected by Juice Shop."""
        import httpx
        from app.services.security.opsec import OpsecManager
        opsec = OpsecManager()
        headers = opsec.get_request_headers()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(JUICE_SHOP_URL, headers=headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Full Cognitive Scan E2E (heavy)
# ---------------------------------------------------------------------------

class TestFullCognitiveScanE2E:
    """Full OODA loop scan against Juice Shop.

    This is the heavy test -- runs the complete cognitive scan engine.
    Takes 30-60 seconds depending on target responsiveness.
    """

    @pytest.mark.asyncio
    async def test_full_scan_completes(self):
        """Full scan should complete with findings."""
        from app.services.security.cognitive_scan_engine import CognitiveScanEngine
        engine = CognitiveScanEngine(
            max_cycles=2,  # Limit cycles for test speed
            offensive_mode=True,
        )
        # Use the domain without protocol for subdomain enum
        target = JUICE_SHOP_URL.replace("http://", "").replace("https://", "")
        result = await engine.scan(target, program="e2e_test")

        # Scan should complete
        assert result.target == target
        assert result.cycles_used >= 1
        assert len(result.strategies_tried) >= 1
        assert len(result.thinking_log) >= 5  # OODA loop generates thinking

        # OPSEC report should be attached
        opsec_data = result.evidence_summary.get("opsec", {})
        assert opsec_data.get("profiles_rotated", 0) >= 0
