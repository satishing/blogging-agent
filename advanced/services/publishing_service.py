from __future__ import annotations

from advanced.config import Settings
from advanced.models import BlogDraft, PublishResult
from advanced.tools import DevToPublisherClient
from .cache_service import CacheService


class PublishingService:
    """Idempotent publish wrapper around DevToPublisherClient.

    The first publish for a (topic, title) pair calls Dev.to and caches the
    `PublishResult`. Subsequent calls with the same idempotency key return
    the cached result with `status="duplicate_skipped"` instead of re-posting.
    Backed by `CacheService`, so duplicate protection survives process restarts
    when Redis is configured.
    """

    def __init__(self, settings: Settings, cache_service: CacheService):
        self._settings = settings
        self._cache = cache_service
        self._devto_client = DevToPublisherClient(settings=settings)

    @staticmethod
    def build_idempotency_key(topic: str, title: str) -> str:
        return CacheService.make_key(
            "publish", topic.lower().strip(), title.lower().strip()
        )

    def get_cached_publish(self, key: str) -> PublishResult | None:
        cached = self._cache.get_json(key)
        if not cached:
            return None
        return PublishResult.model_validate(cached)

    def publish_blog(self, blog: BlogDraft, *, idempotency_key: str) -> PublishResult:
        existing = self.get_cached_publish(idempotency_key)
        if existing:
            return existing.model_copy(update={"status": "duplicate_skipped"})

        result = self._devto_client.publish(blog)
        self._record_publish_result(idempotency_key=idempotency_key, result=result)
        return result

    def _record_publish_result(
        self, *, idempotency_key: str, result: PublishResult
    ) -> None:
        self._cache.set_json(
            idempotency_key, result.model_dump(mode="json"), ttl_seconds=86400
        )
