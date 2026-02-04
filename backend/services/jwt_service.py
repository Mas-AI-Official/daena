"""
JWT Service with Token Rotation and Management.

Features:
- JWT token generation with expiration
- Token rotation (refresh tokens)
- Role-based claims (founder/agent/client)
- Token revocation
- Secure token storage
"""

from __future__ import annotations

import os
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Set
from enum import Enum
from collections import defaultdict
from backend.security.credential_vault import CredentialVault

try:
    import jwt
    from jwt import PyJWTError
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    PyJWTError = Exception

logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    """User roles for JWT claims."""
    FOUNDER = "founder"
    ADMIN = "admin"
    AGENT = "agent"
    CLIENT = "client"
    GUEST = "guest"


class JWTService:
    """
    JWT token service with rotation support.
    
    Features:
    - Access token (short-lived, 15 minutes)
    - Refresh token (long-lived, 7 days)
    - Token rotation on refresh
    - Role-based claims
    - Token revocation list
    """
    
    def __init__(self):
        # Get secret from environment (NO hardcoded defaults - must be set via env)
        # Get secret from Credential Vault or environment
        self.secret_key = CredentialVault.get_secret("JWT_SECRET") or os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY")
        if not self.secret_key:
            raise ValueError("JWT_SECRET must be set in CredentialVault or environment.")
        self.algorithm = "HS256"
        
        # Token expiration times
        self.access_token_expiry = timedelta(minutes=15)  # Short-lived access token
        self.refresh_token_expiry = timedelta(days=7)  # Long-lived refresh token
        
        # Revoked tokens (in production, use Redis or database)
        self.revoked_tokens: set = set()
        
        # Token rotation: track last refresh token per user
        self.user_refresh_tokens: Dict[str, str] = {}  # user_id -> refresh_token
        
        # Containment: track tokens by client IP so we can revoke on block
        self._ip_to_tokens: Dict[str, Set[str]] = defaultdict(set)
        self._max_tokens_per_ip = int(os.getenv("JWT_MAX_TOKENS_PER_IP", "50"))
        
        if not JWT_AVAILABLE:
            logger.warning("PyJWT not installed. JWT features will be limited. Install with: pip install PyJWT")
    
    def generate_access_token(
        self,
        user_id: str,
        role: UserRole = UserRole.CLIENT,
        email: Optional[str] = None,
        tenant_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> str:
        """
        Generate a short-lived access token.
        
        Args:
            user_id: User identifier
            role: User role
            email: User email (optional)
            tenant_id: Tenant ID (optional)
            project_id: Project ID (optional)
        
        Returns:
            JWT access token
        """
        if not JWT_AVAILABLE:
            raise RuntimeError("PyJWT not installed. Cannot generate tokens.")
        
        current_time = int(time.time())
        payload = {
            "sub": user_id,  # Subject (user ID)
            "role": role.value,
            "iat": current_time - 1,  # Issued at (leeway)
            "exp": current_time + int(self.access_token_expiry.total_seconds()),  # Expiration
            "type": "access"
        }
        
        if email:
            payload["email"] = email
        if tenant_id:
            payload["tenant_id"] = tenant_id
        if project_id:
            payload["project_id"] = project_id
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.debug(f"Generated access token for user {user_id} (role: {role.value})")
        return token
    
    def generate_refresh_token(self, user_id: str) -> str:
        """
        Generate a long-lived refresh token.
        
        Args:
            user_id: User identifier
        
        Returns:
            JWT refresh token
        """
        if not JWT_AVAILABLE:
            raise RuntimeError("PyJWT not installed. Cannot generate tokens.")
        
        current_time = int(time.time())
        payload = {
            "sub": user_id,
            "iat": current_time - 1,
            "exp": current_time + int(self.refresh_token_expiry.total_seconds()),
            "type": "refresh"
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        # Store refresh token for rotation
        self.user_refresh_tokens[user_id] = token
        
        logger.debug(f"Generated refresh token for user {user_id}")
        return token
    
    def generate_token_pair(
        self,
        user_id: str,
        role: UserRole = UserRole.CLIENT,
        email: Optional[str] = None,
        tenant_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate both access and refresh tokens.
        
        Returns:
            Dict with "access_token" and "refresh_token"
        """
        access_token = self.generate_access_token(user_id, role, email, tenant_id, project_id)
        refresh_token = self.generate_refresh_token(user_id)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": int(self.access_token_expiry.total_seconds())
        }
    
    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict]:
        """
        Verify and decode a JWT token.
        
        Args:
            token: JWT token to verify
            token_type: Expected token type ("access" or "refresh")
        
        Returns:
            Decoded payload if valid, None if invalid
        """
        if not JWT_AVAILABLE:
            logger.warning("PyJWT not installed. Cannot verify tokens.")
            return None
        
        # Check if token is revoked
        if token in self.revoked_tokens:
            logger.warning("Token is revoked")
            return None
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm], leeway=10)
            
            # Verify token type
            if payload.get("type") != token_type:
                logger.warning(f"Token type mismatch: expected {token_type}, got {payload.get('type')}")
                return None
            
            return payload
        except PyJWTError as e:
            logger.warning(f"Token verification failed: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """
        Rotate tokens: generate new access token from refresh token.
        
        Args:
            refresh_token: Valid refresh token
        
        Returns:
            New token pair if refresh token is valid, None otherwise
        """
        payload = self.verify_token(refresh_token, token_type="refresh")
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        # Check if this is the current refresh token for this user (rotation check)
        if user_id in self.user_refresh_tokens:
            if self.user_refresh_tokens[user_id] != refresh_token:
                logger.warning(f"Refresh token mismatch for user {user_id} - possible token reuse")
                # Revoke old token
                self.revoke_token(refresh_token)
                return None
        
        # Revoke old refresh token (rotation)
        self.revoke_token(refresh_token)
        
        # Generate new token pair
        role = UserRole(payload.get("role", UserRole.CLIENT))
        email = payload.get("email")
        tenant_id = payload.get("tenant_id")
        project_id = payload.get("project_id")
        
        return self.generate_token_pair(user_id, role, email, tenant_id, project_id)
    
    def revoke_token(self, token: str):
        """Revoke a token (add to revocation list)."""
        self.revoked_tokens.add(token)
        logger.info(f"Token revoked: {token[:20]}...")
    
    def revoke_user_tokens(self, user_id: str):
        """Revoke all tokens for a user."""
        if user_id in self.user_refresh_tokens:
            self.revoke_token(self.user_refresh_tokens[user_id])
            del self.user_refresh_tokens[user_id]
        logger.info(f"All tokens revoked for user {user_id}")

    def record_tokens_for_ip(self, ip: str, access_token: str, refresh_token: str) -> None:
        """
        Record tokens for a client IP (used at login/refresh).
        Enables revoke_tokens_for_ip(ip) when containment blocks that IP.
        """
        if not ip or ip == "unknown":
            return
        self._ip_to_tokens[ip].add(access_token)
        self._ip_to_tokens[ip].add(refresh_token)
        # Cap size per IP to avoid unbounded growth
        tokens = self._ip_to_tokens[ip]
        if len(tokens) > self._max_tokens_per_ip:
            excess = len(tokens) - self._max_tokens_per_ip
            for _ in range(excess):
                tokens.pop()

    def revoke_tokens_for_ip(self, ip: str) -> int:
        """
        Revoke all tokens that were issued to this IP (containment integration).
        Returns number of tokens revoked.
        """
        if not ip:
            return 0
        ip = ip.strip()
        tokens = self._ip_to_tokens.get(ip)
        if not tokens:
            return 0
        count = 0
        for token in list(tokens):
            self.revoke_token(token)
            count += 1
        self._ip_to_tokens[ip] = set()
        logger.info("[JWT] Revoked %d token(s) for blocked IP %s", count, ip)
        return count


# Global instance
jwt_service = JWTService()


def get_jwt_service() -> JWTService:
    """Return the global JWT service (for routes that import lazily)."""
    return jwt_service

