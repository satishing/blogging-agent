from advanced.config.settings import Settings
from advanced.tools.devto_publisher import _devto_tags
from advanced.tools.search_tool import SerperSearchClient


def _test_settings() -> Settings:
    return Settings(
        OPENROUTER_API_KEY="test",
        SERPER_API_KEY="test",
        DEVTO_API_KEY="test",
        cache_backend="file",
    )


def test_search_client_normalizes_results(monkeypatch) -> None:
    settings = _test_settings()
    client = SerperSearchClient(settings)

    mock_response = {
        "organic": [
            {
                "title": "AI agents in 2026",
                "link": "https://example.com/ai-agents",
                "snippet": "A quick summary",
                "date": "2026-01-10",
            }
        ]
    }

    monkeypatch.setattr(
        client, "_post_with_retry", lambda payload, headers: mock_response
    )
    results = client.search("ai agents 2026")

    assert len(results) == 1
    assert results[0]["title"] == "AI agents in 2026"
    assert results[0]["url"] == "https://example.com/ai-agents"
    assert results[0]["published_date"].startswith("2026")


def test_devto_tags_are_alphanumeric_and_capped() -> None:
    # Dev.to rejects tags with hyphens/spaces/punctuation and allows at most 4.
    tags = _devto_tags(
        ["Multi-Agent", "AI Agents", "crew.ai", "LLMOps", "ai", "extra-tag"]
    )

    assert tags == ["multiagent", "aiagents", "crewai", "llmops"]
    assert all(tag.isalnum() for tag in tags)
    assert len(tags) <= 4
