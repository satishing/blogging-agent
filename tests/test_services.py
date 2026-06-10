from datetime import date

from advanced.config.settings import Settings
from advanced.models import BlogDraft, PublishResult, ResearchSource
from advanced.services import CacheService, CrewService, PublishingService
from advanced.services.crew_service import SourceGuardrailError


def _test_settings(tmp_path) -> Settings:
    return Settings(
        OPENROUTER_API_KEY="test",
        SERPER_API_KEY="test",
        DEVTO_API_KEY="test",
        cache_backend="file",
        data_dir=str(tmp_path / "data"),
        cache_dir=str(tmp_path / "data" / "cache"),
        output_dir=str(tmp_path / "data" / "outputs"),
        log_dir=str(tmp_path / "data" / "logs"),
    )


def _sample_blog() -> BlogDraft:
    source = ResearchSource(
        title="Fresh AI update",
        url="https://example.com/source",
        published_date=date(2026, 1, 10),
        evidence="Evidence text about the topic from a credible source.",
    )
    return BlogDraft(
        topic="AI Agents",
        title="AI Agents in 2026: Production patterns",
        summary="A practical guide to building production AI agents with robust patterns.",
        content_markdown="word " * 1600,
        tags=["AI", "agents"],
        estimated_read_minutes=7,
        sources=[source, source],
    )


def _source_for_year(year: int) -> ResearchSource:
    return ResearchSource(
        title=f"AI update {year}",
        url=f"https://example.com/{year}",
        published_date=date(year, 1, 10),
        evidence="Evidence text about the topic from a credible source.",
    )


def test_cache_service_file_backend_roundtrip(tmp_path) -> None:
    settings = _test_settings(tmp_path)
    cache = CacheService(settings=settings)
    key = cache.make_key("test", "topic")
    payload = {"hello": "world"}

    cache.set_json(key, payload, ttl_seconds=100)
    loaded = cache.get_json(key)

    assert loaded == payload


def test_publishing_service_duplicate_guard(monkeypatch, tmp_path) -> None:
    settings = _test_settings(tmp_path)
    cache = CacheService(settings=settings)
    service = PublishingService(settings=settings, cache_service=cache)
    blog = _sample_blog()
    key = service.build_idempotency_key(blog.topic, blog.title)

    mock_result = PublishResult(
        platform="dev.to",
        status="draft_created",
        external_id="123",
        url="https://dev.to/example",
    )

    monkeypatch.setattr(service._devto_client, "publish", lambda blog: mock_result)

    first = service.publish_blog(blog, idempotency_key=key)
    second = service.publish_blog(blog, idempotency_key=key)

    assert first.status == "draft_created"
    assert second.status == "duplicate_skipped"


def test_publish_pipeline_publishes_deterministically(monkeypatch, tmp_path) -> None:
    """Publishing goes straight through PublishingService — no LLM in the loop."""
    settings = _test_settings(tmp_path)
    cache = CacheService(settings=settings)
    publishing = PublishingService(settings=settings, cache_service=cache)
    service = CrewService(
        settings=settings, cache_service=cache, publishing_service=publishing
    )
    blog = _sample_blog()

    expected = PublishResult(
        platform="dev.to",
        status="draft_created",
        external_id="999",
        url="https://dev.to/example-999",
    )
    publish_calls = []
    monkeypatch.setattr(
        publishing._devto_client,
        "publish",
        lambda blog: publish_calls.append(blog) or expected,
    )

    first = service._run_publish_pipeline(blog=blog)
    second = service._run_publish_pipeline(blog=blog)

    assert first.status == "draft_created"
    assert first.external_id == "999"
    # Idempotent: the second call is served from cache, not re-posted.
    assert second.status == "duplicate_skipped"
    assert len(publish_calls) == 1, "Dev.to should be called exactly once"


def test_guardrail_requires_min_sources_total(tmp_path) -> None:
    settings = _test_settings(tmp_path)
    service = CrewService(settings=settings)

    blog = BlogDraft(
        topic="AI Agents",
        title="AI Agents: Practical guide for 2026",
        summary="A practical guide for AI learners building robust production systems.",
        content_markdown="word " * 1600,
        tags=["ai", "agents"],
        estimated_read_minutes=7,
        sources=[
            _source_for_year(2026),
            _source_for_year(2026),
            _source_for_year(2025),
        ],
    )

    try:
        service._require_minimum_sources(blog=blog)
        assert False, "Expected SourceGuardrailError for insufficient 2026+ sources"
    except SourceGuardrailError:
        pass


def test_content_pipeline_gathers_then_runs_crew_once(monkeypatch, tmp_path) -> None:
    """Source gathering is delegated to SourceService; the crew runs a single time."""
    settings = _test_settings(tmp_path)
    gathered = [_source_for_year(2026 - offset) for offset in range(4)]

    class FakeSourceService:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def gather(self, *, topic, min_year, min_sources, retry_steps):
            self.calls.append(
                {
                    "topic": topic,
                    "min_year": min_year,
                    "min_sources": min_sources,
                    "retry_steps": retry_steps,
                }
            )
            return gathered

    fake_source_service = FakeSourceService()
    service = CrewService(settings=settings, source_service=fake_source_service)

    crew_runs: list[str] = []

    def fake_run_content_crew(*, topic, sources):
        crew_runs.append(topic)
        # The crew returns a blog whose sources are deliberately wrong/empty to
        # prove the deterministic override below replaces them.
        return BlogDraft(
            topic=topic,
            title="AI Agents: Production patterns",
            summary="A practical guide for AI learners building production systems.",
            content_markdown="word " * 1600,
            tags=["ai", "agents"],
            estimated_read_minutes=7,
            sources=[_source_for_year(1999)],
        )

    monkeypatch.setattr(service, "_run_content_crew", fake_run_content_crew)

    blog = service._run_content_pipeline(topic="AI Agents", min_year=2026)

    assert crew_runs == ["AI Agents"], "crew must run exactly once"
    assert blog.sources == gathered, "blog.sources must be overridden with gathered"
    assert fake_source_service.calls == [
        {
            "topic": "AI Agents",
            "min_year": 2026,
            "min_sources": settings.min_sources,
            "retry_steps": settings.source_year_retry_steps,
        }
    ]


def test_content_pipeline_propagates_guardrail_error(monkeypatch, tmp_path) -> None:
    settings = _test_settings(tmp_path)

    class FailingSourceService:
        def gather(self, *, topic, min_year, min_sources, retry_steps):
            raise SourceGuardrailError("not enough sources")

    service = CrewService(settings=settings, source_service=FailingSourceService())

    def fail_if_called(*, topic, sources):
        raise AssertionError("crew should not run when gathering fails")

    monkeypatch.setattr(service, "_run_content_crew", fail_if_called)

    try:
        service._run_content_pipeline(topic="AI Agents", min_year=2026)
        assert False, "Expected SourceGuardrailError"
    except SourceGuardrailError:
        pass


def test_content_pipeline_falls_back_when_guardrail_exhausted(
    monkeypatch, tmp_path
) -> None:
    """An exhausted writing guardrail degrades to a best-effort draft, not a crash."""
    settings = _test_settings(tmp_path)
    gathered = [_source_for_year(2026 - offset) for offset in range(4)]

    class FakeSourceService:
        def gather(self, **kwargs):
            return gathered

    service = CrewService(settings=settings, source_service=FakeSourceService())
    guardrail_flags: list[bool] = []

    def fake_run_content_crew(*, topic, sources, with_guardrail=True):
        guardrail_flags.append(with_guardrail)
        if with_guardrail:
            raise Exception(
                "Task failed guardrail validation after 2 retries. "
                "Last error: Draft is too short (999 words)."
            )
        return BlogDraft(
            topic=topic,
            title="AI Agents: Best-effort draft",
            summary="A practical guide for AI learners building production systems.",
            content_markdown="word " * 1000,
            tags=["ai"],
            estimated_read_minutes=5,
            sources=[_source_for_year(1999)],
        )

    monkeypatch.setattr(service, "_run_content_crew", fake_run_content_crew)

    blog = service._run_content_pipeline(topic="AI Agents", min_year=2026)

    # Strict run first, then a lenient fallback that succeeds.
    assert guardrail_flags == [True, False]
    assert blog.sources == gathered


def test_content_pipeline_reraises_non_guardrail_errors(monkeypatch, tmp_path) -> None:
    """Non-guardrail failures (network/LLM) propagate; no wasteful fallback run."""
    settings = _test_settings(tmp_path)
    gathered = [_source_for_year(2026 - offset) for offset in range(4)]

    class FakeSourceService:
        def gather(self, **kwargs):
            return gathered

    service = CrewService(settings=settings, source_service=FakeSourceService())
    call_count = 0

    def fake_run_content_crew(*, topic, sources, with_guardrail=True):
        nonlocal call_count
        call_count += 1
        raise RuntimeError("LLM provider unreachable")

    monkeypatch.setattr(service, "_run_content_crew", fake_run_content_crew)

    try:
        service._run_content_pipeline(topic="AI Agents", min_year=2026)
        assert False, "Expected RuntimeError to propagate"
    except RuntimeError:
        pass
    assert call_count == 1, "should not attempt the lenient fallback"
