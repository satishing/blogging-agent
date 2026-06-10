from __future__ import annotations

import json

from crewai import Crew, LLM
from pydantic import ValidationError

from advanced.agents import (
    build_editor_agent,
    build_planner_agent,
    build_publisher_agent,
    build_writer_agent,
)
from advanced.config.settings import Settings
from advanced.models import (
    BlogDraft,
    EditedBlog,
    PipelineResult,
    PublishResult,
    ResearchSource,
)
from advanced.tasks import (
    build_editing_task,
    build_outline_task,
    build_publishing_task,
    build_writing_task,
)
from advanced.tools import DevToPublisherTool
from advanced.utils import (
    WORDS_PER_MINUTE,
    estimate_read_minutes,
    extract_json_object,
    finalize_references,
    get_logger,
)

from .cache_service import CacheService
from .publishing_service import PublishingService

# Re-exported for backwards compatibility — the error now originates in
# SourceService, which owns source gathering.
from .source_service import SourceGuardrailError, SourceService

logger = get_logger(__name__)

__all__ = ["CrewService", "SourceGuardrailError"]


def _is_guardrail_failure(error: Exception) -> bool:
    """True when an exception is CrewAI's exhausted-guardrail error.

    CrewAI raises a plain Exception ("Task failed guardrail validation after N
    retries...") rather than a typed error, so we match on its message. Any
    other failure (LLM/network/parse) is left to propagate.
    """
    return "guardrail validation" in str(error).lower()


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
            api_key=settings.openrouter_api_key.get_secret_value(),
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

        blog = self._generate_blog_resiliently(topic=topic, sources=sources)
        blog.sources = sources
        self._require_minimum_sources(blog=blog)
        self._finalize_references(blog=blog)
        self._finalize_read_minutes(blog=blog)
        return blog

    def _generate_blog_resiliently(
        self, *, topic: str, sources: list[ResearchSource]
    ) -> BlogDraft:
        """Run the content crew, degrading gracefully if the guardrail can't converge.

        The writing guardrail nudges the model toward the target length/structure
        via bounded retries. When the model simply won't hit the band, CrewAI
        raises — rather than crash the whole run over a slightly-short blog, we
        retry once without the strict length guardrail and accept the best-effort
        draft (still gated by the BlogDraft word-count floor). The shortfall is
        surfaced by `_finalize_read_minutes` as a warning, not a failure.
        """
        try:
            return self._run_content_crew(topic=topic, sources=sources)
        except Exception as error:
            if not _is_guardrail_failure(error):
                raise
            logger.warning(
                "Writing guardrail did not converge (%s). Falling back to a "
                "best-effort draft without strict length enforcement.",
                error,
            )
            return self._run_content_crew(
                topic=topic, sources=sources, with_guardrail=False
            )

    def _run_content_crew(
        self,
        *,
        topic: str,
        sources: list[ResearchSource],
        with_guardrail: bool = True,
    ) -> BlogDraft:
        # The shared expense (the LLM connection) lives on `self._llm`; agents and
        # tasks are cheap to build per run and CrewAI doesn't reuse state anyway.
        # Flow: plan an outline → write to a length/structure guardrail → edit and
        # serialize via output_pydantic (CrewAI enforces the schema and retries).
        planner_agent = build_planner_agent(llm=self._llm)
        writer_agent = build_writer_agent(llm=self._llm)
        editor_agent = build_editor_agent(llm=self._llm)

        min_words = self._settings.min_read_minutes * WORDS_PER_MINUTE
        max_words = self._settings.max_read_minutes * WORDS_PER_MINUTE

        outline_task = build_outline_task(agent=planner_agent)
        writing_task = build_writing_task(
            agent=writer_agent,
            min_words=min_words,
            max_words=max_words,
            min_sources=self._settings.min_sources,
            with_guardrail=with_guardrail,
        )
        editing_task = build_editing_task(
            agent=editor_agent,
            writing_task=writing_task,
            min_read_minutes=self._settings.min_read_minutes,
            max_read_minutes=self._settings.max_read_minutes,
        )

        crew = Crew(
            agents=[planner_agent, writer_agent, editor_agent],
            tasks=[outline_task, writing_task, editing_task],
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
        return self._blog_from_crew_result(crew_result)

    @staticmethod
    def _blog_from_crew_result(crew_result) -> BlogDraft:
        """Build a BlogDraft from the editor's (sources-free) EditedBlog output.

        `output_pydantic=EditedBlog` makes CrewAI parse and validate the editor's
        content into an EditedBlog (retrying the agent on malformed output). We
        promote it to a BlogDraft here; sources are attached by the caller. The
        raw-text path is a defensive fallback if only text is returned.
        """
        edited = getattr(crew_result, "pydantic", None)
        if not isinstance(edited, EditedBlog):
            raw_output = getattr(crew_result, "raw", str(crew_result))
            data = extract_json_object(raw_output)
            data.pop("sources", None)  # sources are overridden by the caller
            edited = EditedBlog.model_validate(data)
        return BlogDraft(**edited.model_dump())

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

    def _finalize_references(self, *, blog: BlogDraft) -> None:
        """Rebuild the References section from the authoritative source list.

        The writer's references can drift from the deterministically-overridden
        sources, so we re-render them and surface any inline citation that points
        at a source index we don't have (a quality signal, logged not fatal).
        """
        final_markdown, dangling = finalize_references(
            blog.content_markdown, blog.sources
        )
        if dangling:
            logger.warning(
                "Blog cites source indices with no matching source: %s "
                "(have %s sources).",
                dangling,
                len(blog.sources),
            )
        blog.content_markdown = final_markdown

    def _finalize_read_minutes(self, *, blog: BlogDraft) -> None:
        """Set `estimated_read_minutes` to the true computed value.

        Length is enforced upstream by the writing-task guardrail, so we report
        the honest computed read time rather than fake-clamping the number. A
        value outside the configured window means the guardrail's retries were
        exhausted — we log it as a quality warning instead of hiding it.
        """
        computed_minutes = estimate_read_minutes(blog.content_markdown)
        if not (
            self._settings.min_read_minutes
            <= computed_minutes
            <= self._settings.max_read_minutes
        ):
            logger.warning(
                "Final read-time %s min is outside target window %s-%s; the "
                "content-length guardrail did not converge.",
                computed_minutes,
                self._settings.min_read_minutes,
                self._settings.max_read_minutes,
            )
        blog.estimated_read_minutes = max(1, min(computed_minutes, 20))
