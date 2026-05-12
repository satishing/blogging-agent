from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from advanced.config import Settings
from advanced.utils import get_logger

logger = get_logger(__name__)


class CacheService:
    """Key-value cache with Redis preferred and a JSON-on-disk fallback.

    Initialization tries to ping Redis; on any failure it logs a warning and
    transparently downgrades to file-backed storage rooted at `settings.cache_dir`.
    Used by `CrewService` to memoize blog drafts and pipeline outputs, and by
    `PublishingService` to enforce idempotent publish.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._cache_dir = Path(settings.cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._redis = None
        self._backend = "file"
        self._initialize_backend()

    def _initialize_backend(self) -> None:
        if self._settings.cache_backend != "redis":
            return
        try:
            import redis

            self._redis = redis.Redis.from_url(
                self._settings.redis_url, decode_responses=True
            )
            self._redis.ping()
            self._backend = "redis"
        except Exception as error:
            self._redis = None
            self._backend = "file"
            logger.warning(
                "Redis cache backend unavailable (%s). Falling back to file cache at %s.",
                error,
                self._cache_dir,
            )

    @property
    def backend(self) -> str:
        return self._backend

    @staticmethod
    def make_key(*parts: str) -> str:
        raw = "::".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_json(self, key: str) -> dict[str, Any] | None:
        if self._backend == "redis" and self._redis is not None:
            value = self._redis.get(key)
            return json.loads(value) if value else None
        return self._get_file_value(key)

    def set_json(
        self, key: str, value: dict[str, Any], ttl_seconds: int | None = None
    ) -> None:
        ttl = ttl_seconds or self._settings.cache_ttl_seconds
        if self._backend == "redis" and self._redis is not None:
            self._redis.setex(key, ttl, json.dumps(value, ensure_ascii=False))
            return
        self._set_file_value(key, value, ttl)

    def _file_path(self, key: str) -> Path:
        return self._cache_dir / f"{key}.json"

    def _get_file_value(self, key: str) -> dict[str, Any] | None:
        path = self._file_path(key)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        expires_at = payload.get("expires_at", 0)
        if expires_at and expires_at < time.time():
            path.unlink(missing_ok=True)
            return None
        return payload.get("value")

    def _set_file_value(
        self, key: str, value: dict[str, Any], ttl_seconds: int
    ) -> None:
        # Note: this write is not atomic. Two processes writing the same key
        # concurrently can corrupt the JSON file. Single-process and the
        # Redis backend are both safe — this only matters for multi-process
        # deployments using the file fallback.
        payload = {
            "expires_at": int(time.time()) + ttl_seconds,
            "value": value,
        }
        self._file_path(key).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
