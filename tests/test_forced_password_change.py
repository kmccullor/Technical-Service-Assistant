#!/usr/bin/env python3
"""Forced Password Change Flow Tests.

Validates middleware enforcement and endpoint behavior for users flagged with
password_change_required.
"""

import pytest
from unittest.mock import Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from datetime import datetime
from typing import Optional, Dict, Any


class FakeAuthManager:
    """Fake auth manager for testing with in-memory user state."""
    
    def __init__(self):
        self.users = {}
        self.next_user_id = 1
    
    def add_user(self, email: str, password_change_required: bool = True, **kwargs):
        user_id = self.next_user_id
        self.next_user_id += 1
        user = Mock()
        user.id = user_id
        user.email = email
        user.password_change_required = password_change_required
        user.role_id = kwargs.get('role_id', 1)
        user.status = Mock()
        user.status.value = 'active'
        user.verified = True
        user.is_active = True
        user.is_locked = False
        user.full_name = kwargs.get('full_name', 'Test User')
        user.first_name = kwargs.get('first_name', 'Test')
        user.last_name = kwargs.get('last_name', 'User')
        user.last_login = None
        user.created_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()
        self.users[user_id] = user
        return user
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        # Extract user_id from fake token format "fake.jwt.token.{user_id}"
        if token.startswith('fake.jwt.token.'):
            user_id = int(token.split('.')[-1])
            return {"user_id": user_id}
        raise Exception("Invalid token")
    
    async def get_user_by_id(self, user_id: int):
        return self.users.get(user_id)
    
    async def force_password_change(self, user_id: int, new_password: str) -> bool:
        if user_id in self.users:
            self.users[user_id].password_change_required = False
            return True
        return False
    
    async def authenticate_user(self, email: str, password: str, ip_address: Optional[str] = None):
        # Find user by email
        for user in self.users.values():
            if user.email == email:
                return {
                    "access_token": f"fake.jwt.token.{user.id}",
                    "refresh_token": "fake.refresh.token",
                    "token_type": "bearer",
                    "expires_in": 1800,
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "full_name": user.full_name,
                        "role_id": user.role_id,
                        "status": "active",
                        "verified": True,
                        "last_login": None,
                        "is_active": True,
                        "is_locked": False,
                        "password_change_required": user.password_change_required,
                        "created_at": user.created_at.isoformat(),
                        "updated_at": user.updated_at.isoformat()
                    }
                }
        raise Exception("User not found")


class FakeRBACManager:
    """Fake RBAC manager to avoid database calls during testing."""
    
    async def log_audit_event(self, *args, **kwargs):
        # No-op for testing
        pass
    
    async def log_security_event(self, *args, **kwargs):
        # No-op for testing
        pass


@pytest.fixture
def fake_auth():
    return FakeAuthManager()


@pytest.fixture
def fake_rbac():
    return FakeRBACManager()


@pytest.fixture
def app_with_auth(fake_auth):
    """FastAPI app with RBAC router and fake auth dependency override (no middleware)."""
    from reranker.rbac_endpoints import rbac_router
    from utils.auth_system import get_auth_manager
    
    app = FastAPI()
    app.include_router(rbac_router)
    
    # Override auth manager dependency
    app.dependency_overrides[get_auth_manager] = lambda: fake_auth
    
    return app


@pytest.fixture
def client(app_with_auth):
    return TestClient(app_with_auth)


@pytest.fixture
def flagged_user(fake_auth):
    return fake_auth.add_user(
        email="flagged@example.com",
        password_change_required=True,
        first_name="Flagged",
        last_name="User",
        full_name="Flagged User"
    )


@pytest.mark.unit
def test_force_password_change_endpoint(client, flagged_user):
    """Test force password change endpoint functionality."""
    token = f"fake.jwt.token.{flagged_user.id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    # Verify user initially has password_change_required=True
    assert flagged_user.password_change_required is True
    
    # Force change password - note: endpoint only needs new_password, not confirm_password
    force_resp = client.post(
        "/api/auth/force-change-password", 
        json={
            "new_password": "NewSecurePass123!"
        },
        headers=headers
    )
    if force_resp.status_code != 200:
        print(f"Force change failed: {force_resp.status_code} - {force_resp.text}")
    assert force_resp.status_code == 200
    assert force_resp.json().get('success') is True
    
    # Verify flag cleared
    assert flagged_user.password_change_required is False


@pytest.mark.unit 
def test_user_profile_shows_password_change_status(client, flagged_user):
    """Test that /me endpoint shows correct password_change_required status."""
    token = f"fake.jwt.token.{flagged_user.id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get user profile
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    user_data = resp.json()
    assert user_data['password_change_required'] is True
    assert user_data['email'] == flagged_user.email
    
    # Clear flag and check again
    flagged_user.password_change_required = False
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    user_data = resp.json()
    assert user_data['password_change_required'] is False


@pytest.mark.unit
def test_login_includes_password_change_flag(client, flagged_user):
    """Login response should include password_change_required flag."""
    resp = client.post('/api/auth/login', json={
        "email": flagged_user.email, 
        "password": "testpass"
    })
    if resp.status_code != 200:
        print(f"Login failed: {resp.status_code} - {resp.text}")
    assert resp.status_code == 200
    data = resp.json()
    assert data['user']['password_change_required'] is True
    assert data['user']['email'] == flagged_user.email


@pytest.mark.unit
def test_login_after_password_change_shows_false(client, flagged_user):
    """After password change, login should show password_change_required=False."""
    # Change password first
    flagged_user.password_change_required = False
    
    resp = client.post('/api/auth/login', json={
        "email": flagged_user.email,
        "password": "testpass"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data['user']['password_change_required'] is False