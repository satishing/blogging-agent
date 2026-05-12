"""Pipeline runtime: shared service factory + run_pipeline used by CLI and API."""

from __future__ import annotations

from functools import lru_cache

from advanced.config import get_settings
from advanced.services import CacheService, CrewService, PublishingService


@lru_cache(maxsize=1)
def _get_crew_service() -> CrewService:
    settings = get_settings()
    cache_service = CacheService(settings=settings)
    publishing_service = PublishingService(
        settings=settings, cache_service=cache_service
    )
    return CrewService(
        settings=settings,
        cache_service=cache_service,
        publishing_service=publishing_service,
    )


def run_pipeline(
    topic: str,
    publish: bool,
    force_refresh: bool = False,
    min_year: int | None = None,
) -> dict:
    service = _get_crew_service()
    result = service.run_pipeline(
        topic=topic,
        publish=publish,
        force_refresh=force_refresh,
        min_year=min_year,
    )
    return result.model_dump(mode="json")
