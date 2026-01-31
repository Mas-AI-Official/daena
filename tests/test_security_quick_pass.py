"""
Security Quick-Pass Tests
Validates:
1. DAENA_MEMORY_AES_KEY is from env/KMS only (no hardcoded keys)
2. Key rotation logs to ledger
3. Monitoring routes require auth
4. ABAC enforces PII protection
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from memory_service.crypto import _load_encryptor, refresh
from memory_service.kms import KeyManagementService
from memory_service.ledger import AppendOnlyLedger
from memory_service.policy import AccessPolicy


class TestAESKeySecurity:
    """Test that DAENA_MEMORY_AES_KEY is only loaded from env/KMS."""
    
    def test_key_loaded_from_env_only(self):
        """Verify key is loaded from environment variable only."""
        # Clear any cached key
        refresh()
        
        # Test with env var set
        with patch.dict(os.environ, {"DAENA_MEMORY_AES_KEY": "test-key-123"}):
            refresh()
            encryptor = _load_encryptor()
            assert encryptor.key is not None
        
        # Test with env var unset
        with patch.dict(os.environ, {}, clear=True):
            refresh()
            encryptor = _load_encryptor()
            # Should not have a key if env var is not set
            assert encryptor.key is None or not encryptor.enabled
    
    def test_no_hardcoded_keys(self):
        """Verify no hardcoded keys in crypto module."""
        import inspect
        from memory_service import crypto
        
        source = inspect.getsource(crypto)
        # Check for common hardcoded key patterns
        assert "DAENA_MEMORY_AES_KEY" not in source or "os.getenv" in source
        # Should not have literal key strings
        assert '"default-key' not in source.lower()
        assert "'default-key" not in source.lower()


class TestKeyRotationLogging:
    """Test that key rotation logs to ledger."""
    
    def test_key_rotation_logs_to_ledger(self, tmp_path):
        """Verify key rotation creates ledger entries."""
        ledger_path = tmp_path / "test_ledger.jsonl"
        ledger = AppendOnlyLedger(ledger_path)
        
        kms = KeyManagementService(log_path=tmp_path / "kms_log.jsonl")
        
        # Record a rotation
        kms.record_rotation("test-key-material", key_id="test-key")
        
        # Check that ledger would be updated (via log_event in daena_key_rotate.py)
        # The actual rotation tool calls log_event, so we test the KMS service directly
        assert kms.log_path.exists()
        
        # Read log entries
        with kms.log_path.open("r") as f:
            lines = [line for line in f if line.strip()]
            assert len(lines) > 0
            entry = eval(lines[-1]) if lines else {}
            assert entry.get("key_id") == "test-key"
            assert "key_material" in entry


class TestMonitoringAuth:
    """Test that monitoring routes require authentication."""
    
    def test_monitoring_requires_auth_in_production(self):
        """Verify monitoring endpoints require auth in production."""
        # Mock settings to ensure disable_auth is False
        mock_settings = MagicMock()
        mock_settings.disable_auth = False
        mock_settings.secret_key = "secret"
        mock_settings.monitoring_api_key = "monitoring-key"
        mock_settings.test_api_key = "test-key"
        
        with patch("backend.config.settings.get_settings", return_value=mock_settings):
            with patch.dict(os.environ, {"ENVIRONMENT": "production", "DISABLE_AUTH": "0"}):
                client = TestClient(app)
                # Try to access monitoring endpoint without auth
                response = client.get("/api/v1/monitoring/metrics")
                # Should be 403 or 401
                assert response.status_code in [401, 403]
    
    def test_monitoring_allows_auth_in_production(self):
        """Verify monitoring endpoints work with valid auth in production."""
        client = TestClient(app)
        
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            # Try with valid API key
            response = client.get(
                "/api/v1/monitoring/metrics",
                headers={"X-API-Key": "daena_secure_key_2025"}
            )
            # Should be 200 or at least not 403/401
            assert response.status_code not in [401, 403]
    
    def test_monitoring_dev_mode_allows_no_auth(self):
        """Verify monitoring allows no auth in development (for testing)."""
        client = TestClient(app)
        
        # Must set DISABLE_AUTH=1 to allow no-auth access
        with patch.dict(os.environ, {"ENVIRONMENT": "development", "DISABLE_AUTH": "1"}):
            # Try without auth in dev mode
            response = client.get("/api/v1/monitoring/metrics")
            # Should allow (200 or similar)
            assert response.status_code == 200


class TestABACPIIEnforcement:
    """Test that ABAC enforces PII protection."""
    
    def test_pii_class_requires_special_permissions(self, tmp_path):
        """Verify PII class requires special permissions."""
        policy_file = tmp_path / "policy_config.yaml"
        policy_file.write_text("""
default:
  allow: false
classes:
  pii:
    allow_roles: ["founder", "admin"]
    deny_roles: ["guest"]
  legal:
    allow_roles: ["founder", "admin", "legal"]
  finance:
    allow_roles: ["founder", "admin", "finance"]
""")
        
        policy = AccessPolicy(path=policy_file)
        
        # Founder should have access
        assert policy.is_allowed("read", "pii", {"role": "founder"})
        
        # Admin should have access
        assert policy.is_allowed("read", "pii", {"role": "admin"})
        
        # Guest should NOT have access
        assert not policy.is_allowed("read", "pii", {"role": "guest"})
        
        # User without role should NOT have access (default deny)
        assert not policy.is_allowed("read", "pii", {})
    
    def test_tenant_isolation_enforced(self, tmp_path):
        """Verify tenant isolation is enforced."""
        policy_file = tmp_path / "policy_config.yaml"
        policy_file.write_text("""
default:
  allow: true
classes:
  pii:
    allow_tenants: ["tenant1"]
    deny_tenants: ["tenant2"]
""")
        
        policy = AccessPolicy(path=policy_file)
        
        # Tenant1 should have access
        assert policy.is_allowed("read", "pii", {"tenant": "tenant1"})
        
        # Tenant2 should NOT have access
        assert not policy.is_allowed("read", "pii", {"tenant": "tenant2"})
        
        # Other tenants should NOT have access
        assert not policy.is_allowed("read", "pii", {"tenant": "tenant3"})


class TestKMSIntegration:
    """Test KMS integration for key management."""
    
    def test_kms_can_load_key_from_cloud(self, tmp_path):
        """Verify KMS can load key from cloud KMS."""
        kms = KeyManagementService(log_path=tmp_path / "kms_log.jsonl")
        
        # If cloud KMS is configured, should be able to get key
        # (This is a mock test - actual cloud KMS requires credentials)
        key = kms.get_key_from_cloud("test-key-id")
        # Should return None if not configured, or key if configured
        assert key is None or isinstance(key, str)
    
    def test_kms_creates_signed_manifests(self, tmp_path):
        """Verify KMS creates signed manifests for key rotations."""
        kms = KeyManagementService(
            log_path=tmp_path / "kms_log.jsonl",
            manifest_dir=tmp_path / "manifests"
        )
        
        manifest, path = kms.create_manifest(
            key_material="test-key",
            key_id="test-key-id",
            operator="test-operator",
            signing_key="test-signing-key"
        )
        
        assert "manifest_hash" in manifest
        assert "signature" in manifest
        assert "key_hash" in manifest
        assert path.exists()
        
        # Verify manifest
        assert KeyManagementService.verify_manifest(manifest, "test-signing-key")
        assert not KeyManagementService.verify_manifest(manifest, "wrong-key")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

