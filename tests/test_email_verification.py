#!/usr/bin/env python3
"""Tests for email verification endpoint.

Focus: endpoint behavior (success, already used, invalid token) using mocked auth manager.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

try:
    from reranker.rbac_endpoints import rbac_router
except ImportError:
    from rbac_endpoints import rbac_router  # fallback if running inside service root

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(rbac_router, prefix="/api/auth")
    return TestClient(app)

@pytest.mark.asyncio
async def test_verify_email_success(client):
    mock_auth = AsyncMock()
    mock_auth.verify_email_token = AsyncMock(return_value=True)
    with patch('reranker.rbac_endpoints.get_auth_manager', return_value=mock_auth), \
         patch('rbac_endpoints.get_auth_manager', return_value=mock_auth):  # dual patch for path variance
        resp = client.post('/api/auth/verify-email', json={'token': 'abc123TOKEN'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['success'] is True
    assert data['verified'] is True
    mock_auth.verify_email_token.assert_awaited()

@pytest.mark.asyncio
async def test_verify_email_already_used(client):
    mock_auth = AsyncMock()
    mock_auth.verify_email_token = AsyncMock(return_value=False)
    with patch('reranker.rbac_endpoints.get_auth_manager', return_value=mock_auth), \
         patch('rbac_endpoints.get_auth_manager', return_value=mock_auth):
        resp = client.post('/api/auth/verify-email', json={'token': 'PreviouslyUsed'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['success'] is True
    assert data['verified'] is True

@pytest.mark.asyncio
async def test_verify_email_invalid(client):
    mock_auth = AsyncMock()
    from utils.exceptions import ValidationError
    mock_auth.verify_email_token = AsyncMock(side_effect=ValidationError('Invalid verification token'))
    with patch('reranker.rbac_endpoints.get_auth_manager', return_value=mock_auth), \
         patch('rbac_endpoints.get_auth_manager', return_value=mock_auth):
        resp = client.post('/api/auth/verify-email', json={'token': 'bad'})
    assert resp.status_code == 400
    data = resp.json()
    assert 'Invalid verification token' in data['detail']
