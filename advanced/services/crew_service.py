from __future__ import annotations

import json
from datetime import date

from crewai import Crew, LLM
from pydantic import ValidationError

from advanced.agents import (
    build_editor_agent,
    build_publisher_agent,
    build_research_agent,
    build_writer_agent,
)
from advanced.config.settings import Settings
from advanced.models import BlogDraft, PipelineResult, PublishResult, ResearchSource
from advanced.tasks import (
    build_editing_task,
    build_publishing_task,
    build_research_task,
    build_writing_task,
)
from advanced.tools import DevToPublisherTool, SerperSearchTool
from advanced.utils import estimate_read_minutes, extract_json_object, get_logger

from .cache_service import CacheService
from .publishing_service import PublishingService

logger = get_logger(__name__)


class SourceGuardrailError(ValueError):
    """Raised when source freshness/count guardrails are not met."""


class CrewService:
    """Top-level orchestrator for the research → write → edit → publish pipeline.

    Owns one shared LLM instance, the cache, and the publishing service. Builds
    a fresh research crew per topic and a separate publisher crew per publish.

    See:
      - `_run_content_pipeline` for the year-by-year source accumulation strategy
        (the only piece without a demo equivalent).
      - `_run_publish_pipeline` for the multi-agent publish flow that mirrors
        demo Step 06, with idempotency-cache fallback for unparseable agent output.
    """

    def __init__(
        self,
        settings: Settings,
        cache_service: CacheService | None = None,
        publishing_service: PublishingService | None = None,
    ):
        self._settings = settings
        self._cache = cache_service or CacheService(settings=settings)
        self._publishing_service = publishing_service or PublishingService(
            settings=settings,
            cache_service=self._cache,
        )
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
        self._cache.set_json(output_key, result.model_dump(mode="json"), ttl_seconds=86400)
        return result

    def _run_content_pipeline(self, *, topic: str, min_year: int) -> BlogDraft:
        """Run the research/write/edit crew, falling back year-by-year on freshness.

        Why this loop exists: demo Step 03 shows a single research run. In production,
        Serper sometimes returns too few sources from the requested `min_year`. Rather
        than fail, we accumulate sources across `min_year`, `min_year - 1`, ..., down
        to `min_year - source_year_retry_steps`, dedup by URL, and stop as soon as we
        have `min_sources` total. This keeps the freshness guardrail strict at the
        target year while still producing a blog when the world hasn't caught up yet.
        """
        base_blog: BlogDraft | None = None
        source_by_url: dict[str, ResearchSource] = {}
        target_count = self._settings.min_sources
        fallback_year = min_year - self._settings.source_year_retry_steps

        for offset in range(self._settings.source_year_retry_steps + 1):
            attempt_year = min_year - offset
            try:
                attempt_blog = self._run_content_pipeline_for_year(topic=topic, min_year=attempt_year)
            except SourceGuardrailError as error:
                logger.warning(
                    "Year %s attempt failed source guardrail before accumulation: %s",
                    attempt_year,
                    error,
                )
                continue
            if base_blog is None:
                base_blog = attempt_blog

            selected_sources = self._select_sources_for_attempt(
                sources=attempt_blog.sources,
                base_year=min_year,
                attempt_year=attempt_year,
            )
            for source in selected_sources:
                source_by_url.setdefault(str(source.url), source)

            logger.info(
                "Source accumulation for '%s': %s/%s after year %s attempt.",
                topic,
                len(source_by_url),
                target_count,
                attempt_year,
            )
            if len(source_by_url) >= target_count:
                if base_blog is None:
                    raise SourceGuardrailError(
                        "Internal invariant violated: enough sources accumulated but "
                        "no base blog was captured."
                    )
                base_blog.sources = list(source_by_url.values())[:target_count]
                self._require_minimum_sources(blog=base_blog)
                self._clamp_read_minutes(blog=base_blog)
                return base_blog

            logger.warning(
                "Insufficient cumulative sources after %s attempt (%s/%s). Retrying with %s.",
                attempt_year,
                len(source_by_url),
                target_count,
                attempt_year - 1,
            )

        raise SourceGuardrailError(
            "Guardrail failed: insufficient dated sources after cumulative retries. "
            f"Need at least {target_count} total sources while trying years "
            f"{min_year} to {fallback_year}. Found only {len(source_by_url)}."
        )

    def _run_content_pipeline_for_year(self, *, topic: str, min_year: int) -> BlogDraft:
        # Tool/agent/task instances are built fresh per attempt because each
        # year fallback is an independent run; CrewAI doesn't reuse state
        # across kickoffs anyway. The shared expense (the LLM connection) is
        # instantiated once on `self._llm`.
        search_tool = SerperSearchTool(settings=self._settings)

        research_agent = build_research_agent(llm=self._llm, search_tool=search_tool)
        writer_agent = build_writer_agent(llm=self._llm)
        editor_agent = build_editor_agent(llm=self._llm)

        research_task = build_research_task(
            agent=research_agent,
            min_year=min_year,
            min_sources=self._settings.min_sources,
        )
        writing_task = build_writing_task(agent=writer_agent, research_task=research_task)
        editing_task = build_editing_task(
            agent=editor_agent,
            writing_task=writing_task,
            min_read_minutes=self._settings.min_read_minutes,
            max_read_minutes=self._settings.max_read_minutes,
        )

        crew = Crew(
            agents=[research_agent, writer_agent, editor_agent],
            tasks=[research_task, writing_task, editing_task],
            verbose=False,
        )
        crew_result = crew.kickoff(inputs={"topic": topic})
        raw_output = getattr(crew_result, "raw", str(crew_result))

        blog_data = extract_json_object(raw_output)
        blog = BlogDraft.model_validate(blog_data)
        return blog

    def _run_publish_pipeline(self, *, blog: BlogDraft) -> PublishResult:
        publish_tool = DevToPublisherTool(publishing_service=self._publishing_service)
        publisher_agent = build_publisher_agent(llm=self._llm, publish_tool=publish_tool)
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

    @staticmethod
    def _select_sources_for_attempt(
        *, sources: list[ResearchSource], base_year: int, attempt_year: int
    ) -> list[ResearchSource]:
        if attempt_year == base_year:
            cutoff = date(base_year, 1, 1)
            return [source for source in sources if source.published_date >= cutoff]
        return [source for source in sources if source.published_date.year == attempt_year]
