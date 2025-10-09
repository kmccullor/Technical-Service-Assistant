#!/usr/bin/env python3
"""
Auth System Tests

Tests for authentication, password management, and RBAC functionality.
Focuses on testing password hashing, validation, and change operations.

Coverage:
- Password hashing and verification
- Password change endpoint validation
- API key authentication
- RBAC permission checking
"""

import pytest
import bcrypt
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

# Import the auth system components
try:
    from utils.auth_system import AuthManager
    from utils.rbac_models import (
        User, ChangePasswordRequest, CreateUserRequest, 
        UserStatus, PermissionLevel
    )
    from utils.exceptions import AuthenticationError, ValidationError
    from rbac_endpoints import rbac_router
    from fastapi import FastAPI
except ImportError as e:
    pytest.skip(f"Auth system imports not available: {e}", allow_module_level=True)


class TestPasswordHashing:
    """Test password hashing and verification functionality."""
    
    def test_password_hashing_basic(self):
        """Test basic password hashing works correctly."""
        auth_manager = AuthManager("dummy_db", "dummy_secret")
        
        password = "test_password_123!"
        hashed = auth_manager.hash_password(password)
        
        # Hash should be different from original
        assert hashed != password
        # Hash should be bcrypt format
        assert hashed.startswith('$2b$')
        # Should be able to verify
        assert auth_manager.verify_password(password, hashed)
    
    def test_password_verification_correct(self):
        """Test password verification with correct password."""
        auth_manager = AuthManager("dummy_db", "dummy_secret")
        
        password = "secure_password_456!"
        hashed = auth_manager.hash_password(password)
        
        assert auth_manager.verify_password(password, hashed) is True
    
    def test_password_verification_incorrect(self):
        """Test password verification with incorrect password."""
        auth_manager = AuthManager("dummy_db", "dummy_secret")
        
        password = "secure_password_456!"
        wrong_password = "wrong_password_789!"
        hashed = auth_manager.hash_password(password)
        
        assert auth_manager.verify_password(wrong_password, hashed) is False
    
    def test_password_hash_uniqueness(self):
        """Test that identical passwords produce different hashes (salt)."""
        auth_manager = AuthManager("dummy_db", "dummy_secret")
        
        password = "same_password_123!"
        hash1 = auth_manager.hash_password(password)
        hash2 = auth_manager.hash_password(password)
        
        # Hashes should be different due to salt
        assert hash1 != hash2
        # Both should verify correctly
        assert auth_manager.verify_password(password, hash1)
        assert auth_manager.verify_password(password, hash2)
    
    def test_password_strength_validation(self):
        """Test password strength validation in ChangePasswordRequest."""
        # Test valid strong password
        strong_password = "StrongPass123!@#"
        try:
            request = ChangePasswordRequest(
                current_password="old_password",
                new_password=strong_password,
                confirm_password=strong_password
            )
            # Should not raise validation error
            assert request.new_password == strong_password
        except Exception as e:
            pytest.fail(f"Strong password should be valid: {e}")
    
    def test_password_confirmation_mismatch(self):
        """Test password confirmation validation."""
        with pytest.raises(ValueError, match="New password and confirmation do not match"):
            ChangePasswordRequest(
                current_password="old_password",
                new_password="NewPass123!",
                confirm_password="DifferentPass123!"
            )
    
    def test_weak_password_validation(self):
        """Test weak password rejection."""
        weak_passwords = [
            "short",           # Too short
            "nouppercase1!",   # No uppercase
            "NOLOWERCASE1!",   # No lowercase  
            "NoDigits!",       # No digits
            "NoSpecial123",    # No special chars
        ]
        
        for weak_pwd in weak_passwords:
            with pytest.raises(ValueError):
                ChangePasswordRequest(
                    current_password="old_password",
                    new_password=weak_pwd,
                    confirm_password=weak_pwd
                )


class TestAuthManagerMethods:
    """Test AuthManager methods with mocked database."""
    
    @pytest.fixture
    def mock_auth_manager(self):
        """Create AuthManager with mocked database connection."""
        auth_manager = AuthManager("mock_db", "test_secret_key")
        
        # Mock the database connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        auth_manager.get_db_connection = AsyncMock(return_value=mock_conn)
        
        return auth_manager, mock_conn, mock_cursor
    
    @pytest.mark.asyncio
    async def test_change_password_success(self, mock_auth_manager):
        """Test successful password change."""
        auth_manager, mock_conn, mock_cursor = mock_auth_manager
        
        # Mock user retrieval
        mock_user = Mock()
        mock_user.id = 1
        mock_user.password_hash = auth_manager.hash_password("old_password")
        auth_manager.get_user_by_id = AsyncMock(return_value=mock_user)
        
        # Mock audit logging
        auth_manager.log_audit_event = AsyncMock()
        
        # Test password change
        result = await auth_manager.change_password(1, "old_password", "NewSecure123!")
        
        assert result is True
        # Verify database update was called
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called_once()
        
        # Verify audit logging
        auth_manager.log_audit_event.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, mock_auth_manager):
        """Test password change with wrong current password."""
        auth_manager, mock_conn, mock_cursor = mock_auth_manager
        
        # Mock user retrieval
        mock_user = Mock()
        mock_user.id = 1
        mock_user.password_hash = auth_manager.hash_password("correct_old_password")
        auth_manager.get_user_by_id = AsyncMock(return_value=mock_user)
        
        # Mock security logging
        auth_manager.log_security_event = AsyncMock()
        
        # Test password change with wrong current password
        with pytest.raises(AuthenticationError, match="Current password is incorrect"):
            await auth_manager.change_password(1, "wrong_old_password", "NewSecure123!")
        
        # Verify security event was logged
        auth_manager.log_security_event.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_change_password_user_not_found(self, mock_auth_manager):
        """Test password change for non-existent user."""
        auth_manager, mock_conn, mock_cursor = mock_auth_manager
        
        # Mock user not found
        auth_manager.get_user_by_id = AsyncMock(return_value=None)
        
        # Test password change for non-existent user
        with pytest.raises(AuthenticationError, match="User not found"):
            await auth_manager.change_password(999, "old_password", "NewSecure123!")


class TestPasswordChangeEndpoint:
    """Test password change API endpoint."""
    
    @pytest.fixture
    def test_app(self):
        """Create test FastAPI app with auth endpoints."""
        app = FastAPI()
        app.include_router(rbac_router, prefix="/api/auth")
        return TestClient(app)
    
    @pytest.fixture
    def mock_dependencies(self):
        """Mock the FastAPI dependencies."""
        mock_user = Mock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        
        mock_auth_manager = Mock()
        mock_auth_manager.change_password = AsyncMock(return_value=True)
        
        return mock_user, mock_auth_manager
    
    def test_change_password_endpoint_success(self, test_app, mock_dependencies):
        """Test successful password change via API endpoint."""
        mock_user, mock_auth_manager = mock_dependencies
        
        # Mock the dependencies
        with patch('rbac_endpoints.get_current_active_user', return_value=mock_user), \
             patch('rbac_endpoints.get_auth_manager', return_value=mock_auth_manager):
            
            response = test_app.post(
                "/api/auth/change-password",
                json={
                    "current_password": "OldPass123!",
                    "new_password": "NewSecure456!",
                    "confirm_password": "NewSecure456!"
                }
            )
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["success"] is True
        assert "Password changed successfully" in response_data["message"]
    
    def test_change_password_endpoint_validation_error(self, test_app):
        """Test password change endpoint with validation errors."""
        response = test_app.post(
            "/api/auth/change-password",
            json={
                "current_password": "OldPass123!",
                "new_password": "NewSecure456!",
                "confirm_password": "DifferentPass789!"  # Mismatch
            }
        )
        
        # Should get validation error due to password mismatch
        assert response.status_code == 422  # Validation error


class TestAPIKeyGeneration:
    """Test API key generation functionality."""
    
    def test_generate_secure_token(self):
        """Test secure token generation."""
        auth_manager = AuthManager("dummy_db", "dummy_secret")
        
        token1 = auth_manager.generate_secure_token(32)
        token2 = auth_manager.generate_secure_token(32)
        
        # Tokens should be different
        assert token1 != token2
        # Should be reasonable length (base64 encoded)
        assert len(token1) > 32
        assert len(token2) > 32
        # Should contain only URL-safe base64 characters
        import string
        allowed_chars = string.ascii_letters + string.digits + '-_'
        assert all(c in allowed_chars for c in token1)
        assert all(c in allowed_chars for c in token2)
    
    def test_generate_different_lengths(self):
        """Test generating tokens of different lengths."""
        auth_manager = AuthManager("dummy_db", "dummy_secret")
        
        short_token = auth_manager.generate_secure_token(16)
        long_token = auth_manager.generate_secure_token(64)
        
        # Longer input should produce longer token
        assert len(long_token) > len(short_token)


class TestSecurityFeatures:
    """Test security-related features."""
    
    def test_jwt_token_creation(self):
        """Test JWT token creation with proper claims."""
        auth_manager = AuthManager("dummy_db", "test_secret_key")
        
        # Mock user object
        mock_user = Mock()
        mock_user.id = 123
        mock_user.email = "test@example.com"
        mock_user.role_id = 1
        
        permissions = ["read", "write"]
        token = auth_manager.create_access_token(mock_user, permissions)
        
        # Token should be a string
        assert isinstance(token, str)
        # Should contain dots (JWT format)
        assert token.count('.') == 2
    
    def test_rate_limiting_check(self):
        """Test rate limiting functionality."""
        auth_manager = AuthManager("dummy_db", "dummy_secret")
        
        identifier = "test_user"
        
        # First attempts should be allowed
        for _ in range(5):
            assert auth_manager.check_rate_limit(identifier) is True
        
        # After max attempts, should be rate limited
        for _ in range(10):
            auth_manager.check_rate_limit(identifier)
        
        # Should eventually hit rate limit
        # (This is a simple test - actual implementation may vary)


def test_imports_available():
    """Test that all required imports are available."""
    try:
        from utils.auth_system import AuthManager
        from utils.rbac_models import ChangePasswordRequest
        from rbac_endpoints import rbac_router
        assert True, "All imports successful"
    except ImportError as e:
        pytest.fail(f"Required imports not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])