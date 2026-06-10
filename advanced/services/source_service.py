from __future__ import annotations

from datetime import date

from advanced.config.settings import Settings
from advanced.models import ResearchSource
from advanced.tools.search_tool import SerperSearchClient
from advanced.utils import get_logger

logger = get_logger(__name__)


class SourceGuardrailError(ValueError):
    """Raised when source freshness/count guardrails cannot be met."""


# Snippets shorter than this can't satisfy ResearchSource.evidence (min_length 20),
# so we pad them up to a usable length.
_MIN_EVIDENCE_LENGTH = 20


class SourceService:
    """Deterministically gather fresh, recency-ranked sources for a topic.

    Replaces the old per-year crew re-runs in CrewService. The strategy:
    search once, rank dated results newest-first, and keep the freshest sources
    that clear a freshness floor at `min_year`. The floor only relaxes (year by
    year, down to `min_year - retry_steps`) when there aren't enough fresher
    sources, and fresher sources already collected are never discarded. Undated
    results are used last, as a backfill tier, instead of being dropped.
    """

    def __init__(self, settings: Settings, client: SerperSearchClient | None = None):
        self._settings = settings
        self._client = client or SerperSearchClient(settings=settings)

    def gather(
        self,
        *,
        topic: str,
        min_year: int,
        min_sources: int,
        retry_steps: int,
    ) -> list[ResearchSource]:
        candidates = self._collect_candidates(topic=topic)
        dated = sorted(
            (source for source in candidates if source.published_date is not None),
            key=lambda source: source.published_date,
            reverse=True,
        )
        undated = [source for source in candidates if source.published_date is None]

        floor_year = min_year - retry_steps
        # Relaxing the floor only ever widens the accepted set, and `dated` is
        # already newest-first, so the freshest sources are always preferred.
        for year in range(min_year, floor_year - 1, -1):
            selected = [
                source for source in dated if source.published_date.year >= year
            ]
            if len(selected) >= min_sources:
                logger.info(
                    "Gathered %s dated sources for '%s' at freshness floor %s.",
                    len(selected),
                    topic,
                    year,
                )
                return selected[:min_sources]

        # Not enough dated sources even at the lowest floor: keep every dated
        # source we have (newest-first) and backfill with undated ones.
        dated_at_floor = [
            source for source in dated if source.published_date.year >= floor_year
        ]
        combined = dated_at_floor + undated
        if len(combined) >= min_sources:
            logger.warning(
                "Only %s dated sources for '%s' (floor %s); backfilling with "
                "undated sources to reach %s.",
                len(dated_at_floor),
                topic,
                floor_year,
                min_sources,
            )
            return combined[:min_sources]

        raise SourceGuardrailError(
            "Guardrail failed: insufficient sources after recency ranking and "
            f"undated backfill. Need at least {min_sources} sources (freshness "
            f"floor {floor_year}), found only {len(combined)}."
        )

    def _collect_candidates(self, *, topic: str) -> list[ResearchSource]:
        """Run the search(es), dedup by URL, map to ResearchSource candidates."""
        queries = self._build_queries(topic)
        by_url: dict[str, ResearchSource] = {}
        for query in queries:
            for raw in self._client.search(query):
                url = raw.get("url") or ""
                if not url or url in by_url:
                    continue
                source = self._to_source(raw)
                if source is not None:
                    by_url[url] = source
        return list(by_url.values())

    def _build_queries(self, topic: str) -> list[str]:
        variants = max(self._settings.search_query_variants, 1)
        queries = [topic]
        if variants > 1:
            queries.append(f"{topic} latest")
        if variants > 2:
            queries.append(f"{topic} {date.today().year}")
        return queries[:variants]

    @staticmethod
    def _to_source(raw: dict) -> ResearchSource | None:
        published_raw = raw.get("published_date")
        published_date = date.fromisoformat(published_raw) if published_raw else None
        evidence = (raw.get("snippet") or raw.get("title") or "").strip()
        if len(evidence) < _MIN_EVIDENCE_LENGTH:
            evidence = f"{evidence} (source: {raw.get('title', 'untitled')})"
        if len(evidence) < _MIN_EVIDENCE_LENGTH:
            return None
        try:
            return ResearchSource(
                title=raw.get("title") or "Untitled Source",
                url=raw.get("url"),
                published_date=published_date,
                evidence=evidence,
            )
        except ValueError:
            # e.g. invalid URL or title too short; skip rather than fail the run.
            return None
