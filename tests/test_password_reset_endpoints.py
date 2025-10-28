#!/usr/bin/env python3
"""Tests for password reset endpoints."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

try:
    from reranker.rbac_endpoints import rbac_router
except ImportError:
    from rbac_endpoints import rbac_router  # pragma: no cover - fallback for legacy path

from utils.exceptions import ValidationError
from utils.auth_system import get_auth_manager


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(rbac_router, prefix="/api/auth")
    return TestClient(app)


def test_forgot_password_success(client):
    mock_auth = AsyncMock()
    mock_auth.initiate_password_reset = AsyncMock(return_value=True)

    async def override():
        return mock_auth

    client.app.dependency_overrides[get_auth_manager] = override
    try:
        resp = client.post('/api/auth/forgot-password', json={'email': 'user@example.com'})
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    assert body['data']['email_dispatched'] is True
    mock_auth.initiate_password_reset.assert_awaited_with('user@example.com')


def test_forgot_password_handles_error(client):
    mock_auth = AsyncMock()
    mock_auth.initiate_password_reset = AsyncMock(side_effect=RuntimeError("boom"))

    async def override():
        return mock_auth

    client.app.dependency_overrides[get_auth_manager] = override
    try:
        resp = client.post('/api/auth/forgot-password', json={'email': 'user@example.com'})
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 500
    assert "Failed to process password reset request" in resp.text
    mock_auth.initiate_password_reset.assert_awaited()


def test_reset_password_success(client):
    mock_auth = AsyncMock()
    mock_auth.confirm_password_reset = AsyncMock(return_value=True)

    payload = {
        'token': 'reset-token-123',
        'new_password': 'NewSecurePass123!',
        'confirm_password': 'NewSecurePass123!'
    }

    async def override():
        return mock_auth

    client.app.dependency_overrides[get_auth_manager] = override
    try:
        resp = client.post('/api/auth/reset-password', json=payload)
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    assert body['data']['reset'] is True
    mock_auth.confirm_password_reset.assert_awaited_with(payload['token'], payload['new_password'])


def test_reset_password_validation_error(client):
    mock_auth = AsyncMock()
    mock_auth.confirm_password_reset = AsyncMock(side_effect=ValidationError("Invalid token"))

    payload = {
        'token': 'expired-token',
        'new_password': 'NewSecurePass123!',
        'confirm_password': 'NewSecurePass123!'
    }

    async def override():
        return mock_auth

    client.app.dependency_overrides[get_auth_manager] = override
    try:
        resp = client.post('/api/auth/reset-password', json=payload)
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "Invalid token" in resp.text
    mock_auth.confirm_password_reset.assert_awaited()
