"""
Honeypot Manager — Decoy Routes and Canary Tokens

Creates and manages deceptive endpoints that look real but are
instrumented to detect and log unauthorized access attempts.

Per DAENA_NEW_BLUEPRINT.html: "Decoy API endpoints that look real"
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json
import secrets
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class CanaryToken:
    """A fake credential that triggers alerts when used."""
    token_id: str
    token_type: str  # api_key, password, database_cred, ssh_key, aws_key
    token_value: str
    description: str
    created_at: str
    triggered: bool = False
    trigger_count: int = 0
    last_triggered: Optional[str] = None


@dataclass
class HoneypotEndpoint:
    """A decoy API endpoint."""
    endpoint_id: str
    path: str
    method: str
    description: str
    response_type: str  # fake_keys, fake_data, fake_admin
    enabled: bool = True
    hits: int = 0
    last_hit: Optional[str] = None


@dataclass
class HoneypotHit:
    """A recorded hit on a honeypot."""
    hit_id: str
    honeypot_id: str
    source_ip: str
    user_agent: str
    path: str
    method: str
    headers: Dict[str, str]
    body: str
    timestamp: str


class HoneypotManager:
    """
    Manages honeypots and canary tokens.
    
    Honeypots:
    - /api/v1/admin/keys - Returns fake API keys
    - /api/v1/internal/vault - Returns fake database dump
    - /api/v1/config/secrets - Returns fake config
    
    Canary Tokens:
    - Fake API keys scattered in code/configs
    - Fake database credentials
    - Fake SSH keys
    
    Any use of these triggers immediate alerts.
    """
    
    def __init__(self):
        self._storage_path = Path(__file__).parent.parent.parent.parent / ".ledger" / "honeypots.json"
        
        self._canaries: Dict[str, CanaryToken] = {}
        self._endpoints: Dict[str, HoneypotEndpoint] = {}
        self._hits: List[HoneypotHit] = []
        
        self._load_state()
        self._initialize_defaults()
    
    def _load_state(self):
        """Load persistent state."""
        if self._storage_path.exists():
            try:
                with open(self._storage_path, "r") as f:
                    data = json.load(f)
                self._canaries = {k: CanaryToken(**v) for k, v in data.get("canaries", {}).items()}
                self._endpoints = {k: HoneypotEndpoint(**v) for k, v in data.get("endpoints", {}).items()}
                self._hits = [HoneypotHit(**h) for h in data.get("hits", [])[-500:]]
            except Exception as e:
                logger.error(f"Honeypot: Failed to load state: {e}")
    
    def _save_state(self):
        """Save persistent state."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._storage_path, "w") as f:
                json.dump({
                    "canaries": {k: v.__dict__ for k, v in self._canaries.items()},
                    "endpoints": {k: v.__dict__ for k, v in self._endpoints.items()},
                    "hits": [h.__dict__ for h in self._hits[-500:]],
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Honeypot: Failed to save state: {e}")
    
    def _initialize_defaults(self):
        """Initialize default honeypots and canaries."""
        now = datetime.now(timezone.utc).isoformat()
        
        # Default honeypot endpoints
        default_endpoints = [
            HoneypotEndpoint(
                endpoint_id="hp_admin_keys",
                path="/api/v1/admin/keys",
                method="GET",
                description="Fake admin API keys endpoint",
                response_type="fake_keys"
            ),
            HoneypotEndpoint(
                endpoint_id="hp_vault",
                path="/api/v1/internal/vault",
                method="GET",
                description="Fake database vault dump",
                response_type="fake_data"
            ),
            HoneypotEndpoint(
                endpoint_id="hp_config",
                path="/api/v1/config/secrets",
                method="GET",
                description="Fake config secrets",
                response_type="fake_config"
            ),
            HoneypotEndpoint(
                endpoint_id="hp_backup",
                path="/api/v1/backup/download",
                method="GET",
                description="Fake backup download",
                response_type="fake_data"
            ),
            HoneypotEndpoint(
                endpoint_id="hp_debug",
                path="/api/v1/debug/env",
                method="GET",
                description="Fake debug environment",
                response_type="fake_config"
            ),
        ]
        
        for ep in default_endpoints:
            if ep.endpoint_id not in self._endpoints:
                self._endpoints[ep.endpoint_id] = ep
        
        # Default canary tokens
        if not self._canaries:
            self._generate_default_canaries()
        
        self._save_state()
    
    def _generate_default_canaries(self):
        """Generate default canary tokens."""
        now = datetime.now(timezone.utc).isoformat()
        
        canary_types = [
            ("api_key", "DAENA_API_", 32),
            ("api_key", "AWS_SECRET_", 40),
            ("api_key", "OPENAI_API_KEY_", 48),
            ("database_cred", "DB_PASSWORD_", 24),
            ("ssh_key", "SSH_PRIVATE_", 64),
            ("bearer_token", "BEARER_", 64),
        ]
        
        for token_type, prefix, length in canary_types:
            token_value = prefix + secrets.token_hex(length // 2)
            token_id = f"canary_{hashlib.md5(token_value.encode()).hexdigest()[:12]}"
            
            self._canaries[token_id] = CanaryToken(
                token_id=token_id,
                token_type=token_type,
                token_value=token_value,
                description=f"Auto-generated {token_type} canary",
                created_at=now
            )
    
    def create_canary(self, token_type: str, description: str = "") -> CanaryToken:
        """Create a new canary token."""
        now = datetime.now(timezone.utc).isoformat()
        
        # Generate based on type
        prefix_map = {
            "api_key": "DAENA_",
            "aws_key": "AKIA",
            "database_cred": "postgres://",
            "ssh_key": "-----BEGIN RSA PRIVATE KEY-----",
            "bearer_token": "eyJ",
        }
        
        prefix = prefix_map.get(token_type, "CANARY_")
        
        if token_type == "aws_key":
            # AWS-like key format
            token_value = "AKIA" + secrets.token_hex(8).upper()
        elif token_type == "database_cred":
            # Connection string format
            token_value = f"postgres://admin:{secrets.token_hex(16)}@canary.internal:5432/secrets"
        elif token_type == "bearer_token":
            # JWT-like format
            token_value = f"eyJ{secrets.token_urlsafe(32)}.{secrets.token_urlsafe(64)}.{secrets.token_urlsafe(32)}"
        else:
            token_value = prefix + secrets.token_hex(24)
        
        token_id = f"canary_{hashlib.md5(token_value.encode()).hexdigest()[:12]}"
        
        canary = CanaryToken(
            token_id=token_id,
            token_type=token_type,
            token_value=token_value,
            description=description or f"Custom {token_type} canary",
            created_at=now
        )
        
        self._canaries[token_id] = canary
        self._save_state()
        
        return canary
    
    def check_canary(self, value: str) -> Optional[CanaryToken]:
        """
        Check if a value matches any canary token.
        
        Should be called when credentials are used.
        """
        for canary in self._canaries.values():
            if canary.token_value in value or value in canary.token_value:
                canary.triggered = True
                canary.trigger_count += 1
                canary.last_triggered = datetime.now(timezone.utc).isoformat()
                self._save_state()
                return canary
        return None
    
    def record_hit(self, endpoint_id: str, request_data: Dict[str, Any]) -> HoneypotHit:
        """Record a hit on a honeypot endpoint."""
        now = datetime.now(timezone.utc).isoformat()
        
        # Update endpoint stats
        if endpoint_id in self._endpoints:
            ep = self._endpoints[endpoint_id]
            ep.hits += 1
            ep.last_hit = now
        
        # Create hit record
        hit = HoneypotHit(
            hit_id=f"hit_{now.replace(':', '').replace('-', '')[:17]}_{secrets.token_hex(4)}",
            honeypot_id=endpoint_id,
            source_ip=request_data.get("ip", "unknown"),
            user_agent=request_data.get("user_agent", "unknown"),
            path=request_data.get("path", ""),
            method=request_data.get("method", "GET"),
            headers=request_data.get("headers", {}),
            body=str(request_data.get("body", ""))[:1000],
            timestamp=now
        )
        
        self._hits.append(hit)
        self._save_state()
        
        # Report to shadow agent
        self._report_to_shadow(endpoint_id, request_data)
        
        return hit
    
    def _report_to_shadow(self, endpoint_id: str, request_data: Dict[str, Any]):
        """Report hit to Shadow agent."""
        try:
            from .shadow_agent import get_shadow_agent
            shadow = get_shadow_agent()
            shadow.report_honeypot_hit(endpoint_id, request_data)
        except Exception as e:
            logger.error(f"Honeypot: Failed to report to shadow: {e}")
    
    def get_fake_response(self, endpoint_id: str) -> Dict[str, Any]:
        """
        Generate fake response for honeypot.
        
        Returns data that looks real but phones home if used.
        """
        if endpoint_id not in self._endpoints:
            return {"error": "Not found"}
        
        ep = self._endpoints[endpoint_id]
        
        if ep.response_type == "fake_keys":
            return {
                "api_keys": [
                    {"name": "production", "key": self._get_canary_by_type("api_key")},
                    {"name": "staging", "key": self._get_canary_by_type("api_key")},
                    {"name": "backup", "key": self._get_canary_by_type("api_key")},
                ],
                "aws": {
                    "access_key": self._get_canary_by_type("aws_key"),
                    "secret_key": self._get_canary_by_type("api_key"),
                },
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        
        elif ep.response_type == "fake_data":
            return {
                "database": {
                    "connection_string": self._get_canary_by_type("database_cred"),
                    "users": [
                        {"id": 1, "email": "admin@daena.internal", "password_hash": secrets.token_hex(32)},
                        {"id": 2, "email": "founder@masai.co", "password_hash": secrets.token_hex(32)},
                    ],
                    "backup_url": f"https://canary-backup.internal/{secrets.token_hex(8)}",
                },
                "exported_at": datetime.now(timezone.utc).isoformat()
            }
        
        elif ep.response_type == "fake_config":
            return {
                "OPENAI_API_KEY": self._get_canary_by_type("api_key"),
                "DATABASE_URL": self._get_canary_by_type("database_cred"),
                "JWT_SECRET": self._get_canary_by_type("bearer_token"),
                "REDIS_PASSWORD": secrets.token_hex(16),
                "STRIPE_SECRET_KEY": "sk_live_" + secrets.token_hex(24),
                "env": "production"
            }
        
        return {"status": "ok"}
    
    def _get_canary_by_type(self, token_type: str) -> str:
        """Get a canary value by type."""
        for canary in self._canaries.values():
            if canary.token_type == token_type:
                return canary.token_value
        # Create new if none exists
        new_canary = self.create_canary(token_type)
        return new_canary.token_value
    
    def get_endpoint(self, path: str) -> Optional[HoneypotEndpoint]:
        """Find endpoint by path."""
        for ep in self._endpoints.values():
            if ep.path == path:
                return ep
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get honeypot statistics."""
        return {
            "endpoints_active": sum(1 for ep in self._endpoints.values() if ep.enabled),
            "canaries_deployed": len(self._canaries),
            "canaries_triggered": sum(1 for c in self._canaries.values() if c.triggered),
            "total_hits": sum(ep.hits for ep in self._endpoints.values()),
            "hits_24h": len([h for h in self._hits if h.timestamp > 
                           (datetime.now(timezone.utc).isoformat()[:10])])
        }
    
    def get_all_endpoints(self) -> List[Dict[str, Any]]:
        """Get all endpoint configurations."""
        return [ep.__dict__ for ep in self._endpoints.values()]
    
    def get_all_canaries(self) -> List[Dict[str, Any]]:
        """Get all canary configurations (redacted values)."""
        result = []
        for canary in self._canaries.values():
            data = canary.__dict__.copy()
            # Redact most of the value
            data["token_value"] = data["token_value"][:8] + "..." + data["token_value"][-4:]
            result.append(data)
        return result


# Singleton
_honeypot: Optional[HoneypotManager] = None


def get_honeypot_manager() -> HoneypotManager:
    """Get the global honeypot manager instance."""
    global _honeypot
    if _honeypot is None:
        _honeypot = HoneypotManager()
    return _honeypot
