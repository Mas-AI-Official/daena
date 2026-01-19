"""
Tests for JWT Token Rotation.

Tests:
- Access token creation and expiration
- Refresh token creation
- Token rotation (old refresh token revoked)
- Token revocation
"""

import pytest
from datetime import datetime, timedelta
from backend.services.jwt_service import jwt_service, UserRole


def test_create_access_token():
    """Test that access token is created correctly."""
    data = {
        "sub": "test_user",
        "user_id": "user_123",
        "role": "founder"
    }
    
    token = jwt_service.create_access_token(data)
    
    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_refresh_token():
    """Test that refresh token is created correctly."""
    data = {
        "sub": "test_user",
        "user_id": "user_123",
        "role": "founder"
    }
    
    token = jwt_service.create_refresh_token(data)
    
    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0


def test_verify_access_token():
    """Test that access token can be verified."""
    data = {
        "sub": "test_user",
        "user_id": "user_123",
        "role": "founder"
    }
    
    token = jwt_service.create_access_token(data)
    token_data = jwt_service.verify_token(token)
    
    assert token_data.username == "test_user"
    assert token_data.user_id == "user_123"
    assert token_data.role == "founder"


def test_verify_refresh_token():
    """Test that refresh token can be verified."""
    data = {
        "sub": "test_user",
        "user_id": "user_123",
        "role": "founder"
    }
    
    token = jwt_service.create_refresh_token(data)
    token_data = jwt_service.verify_token(token)
    
    assert token_data.username == "test_user"
    assert token_data.user_id == "user_123"
    assert token_data.role == "founder"


def test_token_rotation():
    """Test that token rotation works (old refresh token revoked)."""
    data = {
        "sub": "test_user",
        "user_id": "user_123",
        "role": "founder"
    }
    
    # Create initial token pair
    access_token_1 = jwt_service.create_access_token(data)
    refresh_token_1 = jwt_service.create_refresh_token(data)
    
    # Verify initial tokens work
    token_data_1 = jwt_service.verify_token(access_token_1)
    assert token_data_1.username == "test_user"
    
    refresh_data_1 = jwt_service.verify_token(refresh_token_1)
    assert refresh_data_1.username == "test_user"
    
    # Rotate: Create new token pair
    access_token_2 = jwt_service.create_access_token(data)
    refresh_token_2 = jwt_service.create_refresh_token(data)
    
    # Revoke old refresh token
    jwt_service.revoke_token(refresh_token_1)
    
    # Old refresh token should be revoked
    with pytest.raises(Exception):  # Should raise HTTPException or similar
        jwt_service.verify_token(refresh_token_1)
    
    # New refresh token should still work
    refresh_data_2 = jwt_service.verify_token(refresh_token_2)
    assert refresh_data_2.username == "test_user"


def test_token_expiration():
    """Test that tokens expire correctly."""
    data = {
        "sub": "test_user",
        "user_id": "user_123",
        "role": "founder"
    }
    
    # Create token with short expiration
    short_expiry = timedelta(seconds=1)
    token = jwt_service.create_access_token(data, expires_delta=short_expiry)
    
    # Token should work immediately
    token_data = jwt_service.verify_token(token)
    assert token_data.username == "test_user"
    
    # Wait for expiration
    import time
    time.sleep(2)
    
    # Token should be expired
    with pytest.raises(Exception):  # Should raise HTTPException for expired token
        jwt_service.verify_token(token)


def test_revoke_user_tokens():
    """Test that all tokens for a user can be revoked."""
    data = {
        "sub": "test_user",
        "user_id": "user_123",
        "role": "founder"
    }
    
    # Create multiple tokens
    token1 = jwt_service.create_access_token(data)
    token2 = jwt_service.create_refresh_token(data)
    token3 = jwt_service.create_access_token(data)
    
    # Verify tokens work
    assert jwt_service.verify_token(token1).username == "test_user"
    assert jwt_service.verify_token(token2).username == "test_user"
    assert jwt_service.verify_token(token3).username == "test_user"
    
    # Revoke all user tokens
    jwt_service.revoke_user_tokens("test_user")
    
    # All tokens should be revoked
    with pytest.raises(Exception):
        jwt_service.verify_token(token1)
    with pytest.raises(Exception):
        jwt_service.verify_token(token2)
    with pytest.raises(Exception):
        jwt_service.verify_token(token3)

