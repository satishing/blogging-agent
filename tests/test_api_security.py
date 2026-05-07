from fastapi.testclient import TestClient

import advanced.api as advanced_api
from advanced.config.settings import Settings


def _api_settings(rate_limit_per_minute: int = 30) -> Settings:
    return Settings(
        OPENROUTER_API_KEY="test",
        SERPER_API_KEY="test",
        DEVTO_API_KEY="test",
        API_AUTH_KEY="secret",
        api_auth_enabled=True,
        api_rate_limit_enabled=True,
        api_rate_limit_per_minute=rate_limit_per_minute,
        api_rate_limit_window_seconds=60,
        cache_backend="file",
    )


def test_api_requires_key(monkeypatch) -> None:
    monkeypatch.setattr(advanced_api, "get_settings", lambda: _api_settings())
    monkeypatch.setattr(
        advanced_api,
        "run_pipeline",
        lambda **kwargs: {"topic": kwargs["topic"], "status": "ok"},
    )

    client = TestClient(advanced_api.create_app())
    response = client.post("/v1/blogs/generate", json={"topic": "AI safety", "publish": False})
    assert response.status_code == 401


def test_api_allows_valid_key(monkeypatch) -> None:
    monkeypatch.setattr(advanced_api, "get_settings", lambda: _api_settings())
    monkeypatch.setattr(
        advanced_api,
        "run_pipeline",
        lambda **kwargs: {"topic": kwargs["topic"], "status": "ok"},
    )

    client = TestClient(advanced_api.create_app())
    response = client.post(
        "/v1/blogs/generate",
        headers={"X-API-Key": "secret"},
        json={"topic": "AI safety", "publish": False},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_rate_limit_returns_429(monkeypatch) -> None:
    monkeypatch.setattr(advanced_api, "get_settings", lambda: _api_settings(rate_limit_per_minute=1))
    monkeypatch.setattr(
        advanced_api,
        "run_pipeline",
        lambda **kwargs: {"topic": kwargs["topic"], "status": "ok"},
    )

    client = TestClient(advanced_api.create_app())
    first = client.post(
        "/v1/blogs/generate",
        headers={"X-API-Key": "secret"},
        json={"topic": "AI safety", "publish": False},
    )
    second = client.post(
        "/v1/blogs/generate",
        headers={"X-API-Key": "secret"},
        json={"topic": "AI safety", "publish": False},
    )

    assert first.status_code == 200
    assert second.status_code == 429
