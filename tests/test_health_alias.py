import os

from fastapi.testclient import TestClient


def test_health_alias_endpoints_enforced_and_accessible():
    os.environ["API_KEY"] = "unit-test-key"
    os.environ["LOG_DIR"] = "./logs"
    # Clear cached settings so API_KEY is read
    from config import get_settings

    get_settings.cache_clear()  # type: ignore
    from reranker.app import app

    client = TestClient(app)

    # /api/health should be public (200)
    r_public = client.get("/api/health")
    assert r_public.status_code == 200
    assert r_public.json().get("status") == "ok"

    # /api/health/details requires key
    r_protected = client.get("/api/health/details")
    assert r_protected.status_code == 401

    r_protected_auth = client.get("/api/health/details", headers={"X-API-Key": "unit-test-key"})
    assert r_protected_auth.status_code == 200
    assert r_protected_auth.json().get("status") in ("ok", "degraded")

    # Root health remains accessible
    r_root = client.get("/health")
    assert r_root.status_code == 200
