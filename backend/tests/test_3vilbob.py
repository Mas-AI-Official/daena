"""Tests for /3vilbob offensive security mode.

Tests evidence capture, proxy management, offensive framework lenses,
and the hidden mode integration in CognitiveScanEngine.
"""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.security.evidence_capture import (
    EvidenceCapture,
    EvidenceChain,
    EvidenceItem,
)
from app.services.security.proxy_manager import (
    ProxyConfig,
    ProxyManager,
    ProxyRequired,
)
from app.services.cognition.cognitive_reasoner import (
    FRAMEWORK_PROMPTS,
    OFFENSIVE_FRAMEWORK_PROMPTS,
    CognitiveReasoner,
)
from app.services.security.cognitive_scan_engine import (
    CognitiveScanEngine,
    CognitiveScanResult,
)


# -----------------------------------------------------------------------
# Evidence Capture
# -----------------------------------------------------------------------

class TestEvidenceCapture:
    """Tests for the evidence capture system."""

    @pytest.fixture
    def tmp_vault(self, tmp_path):
        with patch.dict(os.environ, {"EVIDENCE_VAULT_PATH": str(tmp_path)}):
            yield tmp_path

    @pytest.fixture
    def capture(self, tmp_vault):
        return EvidenceCapture(scan_id="test123", target="example.com", program="test_program")

    @pytest.mark.asyncio
    async def test_initialize_creates_vault_dir(self, capture, tmp_vault):
        # Patch the module-level EVIDENCE_VAULT so initialize() uses tmp_path
        with patch("app.services.security.evidence_capture.EVIDENCE_VAULT", tmp_vault):
            await capture.initialize()
            # Should have created a directory in the vault
            dirs = list(tmp_vault.iterdir())
            assert len(dirs) == 1
            assert "example_com" in dirs[0].name
            assert "test123" in dirs[0].name

    @pytest.mark.asyncio
    async def test_capture_response(self, capture, tmp_vault):
        await capture.initialize()
        item = await capture.capture_response(
            url="https://example.com/api",
            status_code=200,
            headers={"Content-Type": "text/html", "Server": "nginx/1.18"},
            body="<html>sensitive data</html>",
            finding_id="xss_001",
        )
        assert item.evidence_type == "response"
        assert item.target_url == "https://example.com/api"
        assert item.sha256  # Should have a hash
        assert Path(item.file_path).exists()
        content = Path(item.file_path).read_text()
        assert "nginx/1.18" in content
        assert "sensitive data" in content

    @pytest.mark.asyncio
    async def test_capture_screenshot(self, capture, tmp_vault):
        await capture.initialize()
        fake_png = b"\x89PNG\r\n\x1a\nfake_png_data"
        item = await capture.capture_screenshot(
            url="https://example.com/vuln",
            png_bytes=fake_png,
            finding_id="screenshot_001",
        )
        assert item.evidence_type == "screenshot"
        assert Path(item.file_path).exists()
        assert Path(item.file_path).read_bytes() == fake_png

    @pytest.mark.asyncio
    async def test_capture_token_encrypted(self, capture, tmp_vault):
        await capture.initialize()
        item = await capture.capture_token(
            url="https://example.com/.env",
            token_type="aws_access_key",
            token_value="AKIAIOSFODNN7EXAMPLE",
            finding_id="token_001",
        )
        assert item.evidence_type == "token"
        assert item.encrypted is True
        # The file should exist but NOT contain the raw token
        raw_content = Path(item.file_path).read_bytes()
        assert b"AKIAIOSFODNN7EXAMPLE" not in raw_content

    def test_capture_curl(self, capture, tmp_vault):
        # Synchronous method
        capture._vault_dir = tmp_vault / "test_vault"
        capture._vault_dir.mkdir()
        item = capture.capture_curl(
            method="POST",
            url="https://example.com/api/transfer",
            headers={"Content-Type": "application/json", "Authorization": "Bearer secret123"},
            body='{"amount": 0.01}',
            finding_id="idor_001",
        )
        assert item.evidence_type == "curl"
        content = Path(item.file_path).read_text()
        assert "POST" in content
        assert "example.com/api/transfer" in content
        # Auth header should be REDACTED
        assert "secret123" not in content
        assert "REDACTED" in content

    @pytest.mark.asyncio
    async def test_capture_poc(self, capture, tmp_vault):
        await capture.initialize()
        item = await capture.capture_poc(
            url="https://example.com/api/transfer",
            poc_type="unauthorized_read",
            description="Read user data without authentication",
            request_data={"method": "GET", "url": "https://example.com/api/users/1"},
            response_data={"status_code": 200, "body": '{"name": "test"}'},
            finding_id="unauth_001",
        )
        assert item.evidence_type == "poc"
        content = json.loads(Path(item.file_path).read_text())
        assert content["poc_type"] == "unauthorized_read"
        assert content["response"]["status_code"] == 200

    @pytest.mark.asyncio
    async def test_evidence_chain_integrity(self, capture, tmp_vault):
        await capture.initialize()
        # Capture multiple items
        await capture.capture_response(
            url="https://a.com", status_code=200, headers={}, body="a",
        )
        capture.capture_curl(method="GET", url="https://b.com")
        await capture.capture_response(
            url="https://c.com", status_code=404, headers={}, body="c",
        )

        chain = capture.get_chain()
        assert len(chain.items) == 3
        assert chain.chain_hash  # Rolling hash should be populated
        assert chain.scan_id == "test123"

    def test_token_detection_aws(self):
        content = 'AWS_KEY=AKIAIOSFODNN7EXAMPLE and stuff'
        tokens = EvidenceCapture.detect_tokens(content)
        assert any(t["type"] == "aws_access_key" for t in tokens)

    def test_token_detection_jwt(self):
        content = 'token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U'
        tokens = EvidenceCapture.detect_tokens(content)
        assert any(t["type"] == "jwt" for t in tokens)

    def test_token_detection_github(self):
        # GitHub fine-grained PAT format (36+ chars after prefix)
        content = 'GITHUB_TOKEN=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl'
        tokens = EvidenceCapture.detect_tokens(content)
        assert any(t["type"] == "github_token" for t in tokens)

    def test_token_detection_stripe(self):
        content = 'STRIPE_LIVE_PLACEHOLDER_1234567890abcdefghijklmn'
        tokens = EvidenceCapture.detect_tokens(content)
        assert any(t["type"] == "stripe_key" for t in tokens)

    def test_no_false_positives_on_clean_content(self):
        content = "Hello world, this is just normal text with no secrets."
        tokens = EvidenceCapture.detect_tokens(content)
        assert len(tokens) == 0


# -----------------------------------------------------------------------
# Proxy Manager
# -----------------------------------------------------------------------

class TestProxyManager:
    """Tests for the proxy management system."""

    def test_no_proxy_configured_returns_empty(self):
        pm = ProxyManager(offensive_mode=False)
        pm.initialize()
        assert pm.get_proxy() == ""

    def test_offensive_mode_raises_without_proxy(self):
        pm = ProxyManager(offensive_mode=True)
        pm.initialize()
        with pytest.raises(ProxyRequired):
            pm.require_proxy()

    def test_scan_proxy_env_var(self):
        with patch.dict(os.environ, {"SCAN_PROXY": "http://user:pass@proxy.brightdata.com:22225"}):
            pm = ProxyManager()
            pm.initialize()
            assert pm.get_proxy() == "http://user:pass@proxy.brightdata.com:22225"

    def test_tor_env_var(self):
        with patch.dict(os.environ, {"USE_TOR": "true"}):
            pm = ProxyManager()
            pm.initialize()
            assert "socks5://127.0.0.1:9050" in pm.get_proxy()

    def test_proxy_priority_rotating_over_tor(self):
        with patch.dict(os.environ, {
            "SCAN_PROXY": "http://proxy.brightdata.com:22225",
            "USE_TOR": "true",
        }):
            pm = ProxyManager()
            pm.initialize()
            # Rotating proxy should be selected (higher priority)
            assert "brightdata" in pm.get_proxy()

    def test_offensive_mode_with_proxy_succeeds(self):
        with patch.dict(os.environ, {"SCAN_PROXY": "http://proxy.test:8080"}):
            pm = ProxyManager(offensive_mode=True)
            pm.initialize()
            pm.require_proxy()  # Should not raise
            assert pm.get_proxy() == "http://proxy.test:8080"

    def test_provider_auto_detection(self):
        assert ProxyManager._detect_provider("http://proxy.brightdata.com:22225") == "brightdata"
        assert ProxyManager._detect_provider("http://proxy.oxylabs.io:7777") == "oxylabs"
        assert ProxyManager._detect_provider("http://proxy.smartproxy.com:10000") == "smartproxy"
        assert ProxyManager._detect_provider("http://random.proxy.net:8080") == "custom"

    def test_user_agent_rotation(self):
        pm = ProxyManager()
        ua1 = pm.get_user_agent()
        assert "Mozilla" in ua1

    def test_request_headers_completeness(self):
        pm = ProxyManager()
        headers = pm.get_request_headers()
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert "Sec-Fetch-Dest" in headers  # Real browsers send this

    def test_failure_tracking_and_failover(self):
        pm = ProxyManager()
        pm._proxies = [
            ProxyConfig(url="http://proxy1:8080", proxy_type="rotating", provider="test"),
            ProxyConfig(url="socks5://127.0.0.1:9050", proxy_type="tor", provider="tor"),
        ]
        pm._active_proxy = pm._proxies[0]
        pm._initialized = True

        # Record 5 failures -- should trigger failover
        for _ in range(5):
            pm.record_failure()

        assert pm._active_proxy.proxy_type == "tor"  # Failover to Tor

    def test_status_report(self):
        pm = ProxyManager(offensive_mode=True)
        pm.initialize()
        status = pm.get_status()
        assert status["offensive_mode"] is True
        assert status["proxy_enforced"] is True


# -----------------------------------------------------------------------
# Offensive Framework Lenses
# -----------------------------------------------------------------------

class TestOffensiveLenses:
    """Tests for the offensive framework lenses in CognitiveReasoner."""

    def test_offensive_frameworks_exist(self):
        assert len(OFFENSIVE_FRAMEWORK_PROMPTS) == 7
        required = [
            "defender_assumption_mapping",
            "legitimacy_mimicry",
            "constraint_decomposition",
            "attack_chain_thinking",
            "temporal_analysis",
            "business_logic_exploitation",
            "evidence_maximization",
        ]
        for name in required:
            assert name in OFFENSIVE_FRAMEWORK_PROMPTS

    def test_offensive_frameworks_are_separate_from_standard(self):
        # No overlap between standard and offensive
        for name in OFFENSIVE_FRAMEWORK_PROMPTS:
            assert name not in FRAMEWORK_PROMPTS

    def test_reasoner_creates_with_offensive_mode(self):
        reasoner = CognitiveReasoner(offensive_mode=True)
        assert reasoner._offensive_mode is True

    def test_reasoner_standard_mode_no_offensive(self):
        reasoner = CognitiveReasoner()
        assert reasoner._offensive_mode is False

    def test_framework_extraction_finds_offensive(self):
        response = "Using defender_assumption_mapping, I identified the WAF's blind spots."
        used = CognitiveReasoner._extract_frameworks_used(response)
        assert "defender_assumption_mapping" in used

    def test_framework_extraction_finds_standard(self):
        response = "Applying first_principles analysis to the target."
        used = CognitiveReasoner._extract_frameworks_used(response)
        assert "first_principles" in used


# -----------------------------------------------------------------------
# CognitiveScanEngine /3vilbob Mode
# -----------------------------------------------------------------------

class TestCognitiveScanEngineOffensive:
    """Tests for the /3vilbob mode in CognitiveScanEngine."""

    def test_engine_creates_with_offensive_mode(self):
        engine = CognitiveScanEngine(offensive_mode=True, agi_mode=True)
        assert engine.offensive_mode is True
        assert engine.agi_mode is True

    def test_engine_standard_mode(self):
        engine = CognitiveScanEngine()
        assert engine.offensive_mode is False

    def test_result_includes_evidence_fields(self):
        result = CognitiveScanResult(target="example.com", offensive_mode=True)
        assert result.offensive_mode is True
        assert result.evidence_summary == {}

    def test_proxy_resolve_uses_manager(self):
        engine = CognitiveScanEngine(offensive_mode=True)
        pm = ProxyManager(offensive_mode=True)
        pm._proxies = [
            ProxyConfig(url="http://proxy:8080", proxy_type="rotating", provider="test"),
        ]
        pm._active_proxy = pm._proxies[0]
        pm._initialized = True
        engine._proxy_manager = pm
        assert engine._resolve_proxy() == "http://proxy:8080"

    def test_proxy_resolve_explicit_override(self):
        engine = CognitiveScanEngine(proxy="http://explicit:1234")
        assert engine._resolve_proxy() == "http://explicit:1234"
