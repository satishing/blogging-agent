from datetime import date, timedelta

from advanced.config.settings import Settings
from advanced.services.source_service import SourceGuardrailError, SourceService
from advanced.tools.search_tool import SerperSearchClient


def _settings() -> Settings:
    return Settings(
        OPENROUTER_API_KEY="test",
        SERPER_API_KEY="test",
        min_sources=4,
        source_year_retry_steps=3,
    )


class _FakeClient:
    """Returns a fixed result set regardless of query (single search semantics)."""

    def __init__(self, results: list[dict]) -> None:
        self._results = results
        self.queries: list[str] = []

    def search(self, query: str, *, max_results=None) -> list[dict]:
        self.queries.append(query)
        return list(self._results)


def _result(url: str, year: int | None, *, snippet: str = "x" * 30) -> dict:
    return {
        "title": f"Source {url}",
        "url": url,
        "snippet": snippet,
        "published_date": date(year, 6, 1).isoformat() if year else None,
    }


def test_gather_returns_freshest_when_plenty() -> None:
    results = [_result(f"https://e.com/{y}", y) for y in (2023, 2026, 2024, 2025, 2026)]
    # two 2026 entries need distinct urls
    results[0]["url"] = "https://e.com/2023"
    results[4]["url"] = "https://e.com/2026b"
    service = SourceService(settings=_settings(), client=_FakeClient(results))

    sources = service.gather(topic="AI", min_year=2026, min_sources=2, retry_steps=3)

    assert len(sources) == 2
    assert all(s.published_date.year == 2026 for s in sources)


def test_gather_relaxes_floor_and_keeps_fresher_first() -> None:
    results = [
        _result("https://e.com/2026", 2026),
        _result("https://e.com/2025", 2025),
        _result("https://e.com/2024a", 2024),
        _result("https://e.com/2024b", 2024),
    ]
    service = SourceService(settings=_settings(), client=_FakeClient(results))

    sources = service.gather(topic="AI", min_year=2026, min_sources=4, retry_steps=3)

    years = [s.published_date.year for s in sources]
    assert years == [2026, 2025, 2024, 2024], "newest-first, floor relaxed to 2024"


def test_gather_backfills_with_undated_as_last_resort() -> None:
    results = [
        _result("https://e.com/2026", 2026),
        _result("https://e.com/2025", 2025),
        _result("https://e.com/undated1", None),
        _result("https://e.com/undated2", None),
    ]
    service = SourceService(settings=_settings(), client=_FakeClient(results))

    sources = service.gather(topic="AI", min_year=2026, min_sources=4, retry_steps=3)

    assert len(sources) == 4
    # Dated sources rank ahead of undated ones.
    assert sources[0].published_date.year == 2026
    assert sources[1].published_date.year == 2025
    assert sources[2].published_date is None
    assert sources[3].published_date is None


def test_gather_raises_when_insufficient_even_with_backfill() -> None:
    results = [
        _result("https://e.com/2026", 2026),
        _result("https://e.com/undated", None),
    ]
    service = SourceService(settings=_settings(), client=_FakeClient(results))

    try:
        service.gather(topic="AI", min_year=2026, min_sources=4, retry_steps=3)
        assert False, "Expected SourceGuardrailError"
    except SourceGuardrailError:
        pass


def test_gather_dedups_by_url() -> None:
    results = [
        _result("https://e.com/dup", 2026),
        _result("https://e.com/dup", 2026),
        _result("https://e.com/2025", 2025),
    ]
    service = SourceService(settings=_settings(), client=_FakeClient(results))

    sources = service.gather(topic="AI", min_year=2026, min_sources=2, retry_steps=3)

    urls = {str(s.url) for s in sources}
    assert len(urls) == 2


def test_extract_date_iso() -> None:
    assert SerperSearchClient._extract_date("2026-03-15") == date(2026, 3, 15)


def test_extract_date_relative_days() -> None:
    expected = date.today() - timedelta(days=3)
    assert SerperSearchClient._extract_date("3 days ago") == expected


def test_extract_date_relative_weeks() -> None:
    expected = date.today() - timedelta(days=14)
    assert SerperSearchClient._extract_date("2 weeks ago") == expected


def test_extract_date_today_and_yesterday() -> None:
    assert SerperSearchClient._extract_date("today") == date.today()
    assert SerperSearchClient._extract_date("Yesterday") == date.today() - timedelta(
        days=1
    )


def test_extract_date_year_only_fallback() -> None:
    assert SerperSearchClient._extract_date("Published in 2024") == date(2024, 1, 1)


def test_extract_date_unparseable_returns_none() -> None:
    assert SerperSearchClient._extract_date("") is None
    assert SerperSearchClient._extract_date("no date here") is None
