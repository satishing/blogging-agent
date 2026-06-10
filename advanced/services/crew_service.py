from __future__ import annotations

import json

from crewai import Crew, LLM
from pydantic import ValidationError

from advanced.agents import (
    build_editor_agent,
    build_publisher_agent,
    build_writer_agent,
)
from advanced.config.settings import Settings
from advanced.models import BlogDraft, PipelineResult, PublishResult, ResearchSource
from advanced.tasks import (
    build_editing_task,
    build_publishing_task,
    build_writing_task,
)
from advanced.tools import DevToPublisherTool
from advanced.utils import estimate_read_minutes, extract_json_object, get_logger

from .cache_service import CacheService
from .publishing_service import PublishingService

# Re-exported for backwards compatibility — the error now originates in
# SourceService, which owns source gathering.
from .source_service import SourceGuardrailError, SourceService

logger = get_logger(__name__)

__all__ = ["CrewService", "SourceGuardrailError"]


class CrewService:
    """Top-level orchestrator for the research → write → edit → publish pipeline.

    Owns one shared LLM instance, the cache, and the publishing service. Builds
    a fresh research crew per topic and a separate publisher crew per publish.

    See:
      - `_run_content_pipeline` for the deterministic source-gathering step
        (delegated to SourceService) followed by a single writer→editor crew run.
      - `_run_publish_pipeline` for the multi-agent publish flow that mirrors
        demo Step 06, with idempotency-cache fallback for unparseable agent output.
    """

    def __init__(
        self,
        settings: Settings,
        cache_service: CacheService | None = None,
        publishing_service: PublishingService | None = None,
        source_service: SourceService | None = None,
    ):
        self._settings = settings
        self._cache = cache_service or CacheService(settings=settings)
        self._publishing_service = publishing_service or PublishingService(
            settings=settings,
            cache_service=self._cache,
        )
        self._source_service = source_service or SourceService(settings=settings)
        self._llm = LLM(
            model=settings.model_name,
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
        )

    def run_pipeline(
        self,
        *,
        topic: str,
        publish: bool,
        force_refresh: bool = False,
        min_year: int | None = None,
    ) -> PipelineResult:
        min_year = min_year or self._settings.min_source_year
        cache_key = CacheService.make_key("blog", topic.lower().strip(), str(min_year))

        cached_payload = None if force_refresh else self._cache.get_json(cache_key)
        if cached_payload:
            blog = BlogDraft.model_validate(cached_payload)
            logger.info("Cache hit for topic '%s'", topic)
            result = PipelineResult(topic=topic, blog=blog, cached=True)
        else:
            blog = self._run_content_pipeline(topic=topic, min_year=min_year)
            self._cache.set_json(cache_key, blog.model_dump(mode="json"))
            result = PipelineResult(topic=topic, blog=blog, cached=False)

        if publish:
            publish_result = self._run_publish_pipeline(blog=result.blog)
            result.publish_result = publish_result

        output_key = CacheService.make_key(
            "pipeline-output", topic.lower().strip(), str(min_year)
        )
        self._cache.set_json(
            output_key, result.model_dump(mode="json"), ttl_seconds=86400
        )
        return result

    def _run_content_pipeline(self, *, topic: str, min_year: int) -> BlogDraft:
        """Gather sources deterministically, then run the write→edit crew once.

        Source gathering (recency ranking + freshness-floor relaxation + undated
        backfill) is delegated to SourceService, replacing the old per-year crew
        re-runs. The expensive writer→editor crew runs a single time over the
        validated source set, and `blog.sources` is then overwritten with those
        exact sources so the freshness/count guarantees can't be undone by the
        LLM dropping or hallucinating sources.
        """
        sources = self._source_service.gather(
            topic=topic,
            min_year=min_year,
            min_sources=self._settings.min_sources,
            retry_steps=self._settings.source_year_retry_steps,
        )

        blog = self._run_content_crew(topic=topic, sources=sources)
        blog.sources = sources
        self._require_minimum_sources(blog=blog)
        self._clamp_read_minutes(blog=blog)
        return blog

    def _run_content_crew(
        self, *, topic: str, sources: list[ResearchSource]
    ) -> BlogDraft:
        # The shared expense (the LLM connection) lives on `self._llm`; agents and
        # tasks are cheap to build per run and CrewAI doesn't reuse state anyway.
        writer_agent = build_writer_agent(llm=self._llm)
        editor_agent = build_editor_agent(llm=self._llm)

        writing_task = build_writing_task(agent=writer_agent)
        editing_task = build_editing_task(
            agent=editor_agent,
            writing_task=writing_task,
            min_read_minutes=self._settings.min_read_minutes,
            max_read_minutes=self._settings.max_read_minutes,
        )

        crew = Crew(
            agents=[writer_agent, editor_agent],
            tasks=[writing_task, editing_task],
            verbose=False,
        )
        research_json = json.dumps(
            {
                "topic": topic,
                "sources": [source.model_dump(mode="json") for source in sources],
            },
            ensure_ascii=False,
        )
        crew_result = crew.kickoff(
            inputs={"topic": topic, "research_json": research_json}
        )
        raw_output = getattr(crew_result, "raw", str(crew_result))

        blog_data = extract_json_object(raw_output)
        return BlogDraft.model_validate(blog_data)

    def _run_publish_pipeline(self, *, blog: BlogDraft) -> PublishResult:
        publish_tool = DevToPublisherTool(publishing_service=self._publishing_service)
        publisher_agent = build_publisher_agent(
            llm=self._llm, publish_tool=publish_tool
        )
        publishing_task = build_publishing_task(agent=publisher_agent)

        crew = Crew(
            agents=[publisher_agent],
            tasks=[publishing_task],
            verbose=False,
        )
        blog_json = json.dumps(blog.model_dump(mode="json"), ensure_ascii=False)
        crew_result = crew.kickoff(inputs={"blog_json": blog_json})
        raw_output = getattr(crew_result, "raw", str(crew_result))

        try:
            publish_data = extract_json_object(raw_output)
            return PublishResult.model_validate(publish_data)
        except (ValueError, ValidationError) as error:
            # Agent output was not parseable JSON / didn't match the schema.
            # The tool already wrote the real publish result to the idempotency
            # cache during its actual API call, so recover from there.
            idempotency_key = self._publishing_service.build_idempotency_key(
                blog.topic, blog.title
            )
            cached = self._publishing_service.get_cached_publish(idempotency_key)
            if cached is None:
                raise RuntimeError(
                    "Publisher agent returned unparseable output and no cached "
                    f"publish result was found: {error}"
                ) from error
            logger.warning(
                "Recovered publish result from idempotency cache after unparseable "
                "agent output."
            )
            return cached

    def _require_minimum_sources(self, *, blog: BlogDraft) -> None:
        """Raise if the blog does not meet the configured minimum source count."""
        if len(blog.sources) < self._settings.min_sources:
            raise SourceGuardrailError(
                "Guardrail failed: insufficient cumulative sources. "
                f"Need at least {self._settings.min_sources} total sources "
                f"(got {len(blog.sources)})."
            )

    def _clamp_read_minutes(self, *, blog: BlogDraft) -> None:
        """Clamp the blog's estimated read time into the configured window.

        Mutates `blog.estimated_read_minutes`. Logs a warning when clamping
        is applied so we can spot consistently long/short generations.
        """
        computed_minutes = estimate_read_minutes(blog.content_markdown)
        if computed_minutes < self._settings.min_read_minutes:
            logger.warning(
                "Read-time below target (%s min). Clamping to %s.",
                computed_minutes,
                self._settings.min_read_minutes,
            )
            blog.estimated_read_minutes = self._settings.min_read_minutes
            return
        if computed_minutes > self._settings.max_read_minutes:
            logger.warning(
                "Read-time above target (%s min). Clamping to %s.",
                computed_minutes,
                self._settings.max_read_minutes,
            )
            blog.estimated_read_minutes = self._settings.max_read_minutes
            return
        blog.estimated_read_minutes = computed_minutes
