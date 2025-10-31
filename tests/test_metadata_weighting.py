import os

from fastapi.testclient import TestClient


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *args, **kwargs):
        pass

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self, *args, **kwargs):
        return FakeCursor(self.rows)

    def close(self):
        pass


class FakeOllamaClient:
    def embeddings(self, model, prompt):
        return {"embedding": [0.0] * 10}


def test_metadata_weighting_reorders_results(monkeypatch):
    os.environ["API_KEY"] = "unit-test-key"
    os.environ["ENABLE_METADATA_WEIGHTING"] = "1"
    os.environ["LOG_DIR"] = "./logs"
    from config import get_settings

    get_settings.cache_clear()  # type: ignore

    from reranker import app as app_module

    # Monkeypatch dependencies
    monkeypatch.setattr(
        app_module,
        "get_db_connection",
        lambda: FakeConnection(
            [
                {"content": "INTRODUCTION:\nOverview of system", "page_number": 1, "chunk_type": "text"},
                {"content": "Detailed configuration parameters and values", "page_number": 12, "chunk_type": "text"},
                {"content": "TABLE: settings list", "page_number": 2, "chunk_type": "table"},
            ]
        ),
    )
    monkeypatch.setattr(app_module, "ollama_client", FakeOllamaClient())

    client = TestClient(app_module.app)

    r = client.post(
        "/search",
        json={"query": "configuration settings", "passages": [], "top_k": 5, "privacy_filter": "all"},
        headers={"X-API-Key": "unit-test-key"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    reranked = data.get("reranked") or []
    # Expect heading/intro page 1 content to appear early due to boost
    assert any("INTRODUCTION" in c for c in reranked[:2])
