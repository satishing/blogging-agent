"""Security primitives: API-key bucket hashing + in-memory rate limiter.

Used by `advanced/api.py` to enforce per-key request quotas without holding
the raw API key in memory keyed-by-itself.
"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque
from threading import Lock


def hash_bucket_key(value: str) -> str:
    """Hash a value (e.g. an API key) before using it as a rate-limit bucket
    key. Avoids storing the secret in memory keyed-by-itself."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class InMemoryRateLimiter:
    """Sliding-window rate limiter with periodic empty-bucket eviction.

    The bucket dict would otherwise grow unbounded as new keys arrive: every
    `_EVICTION_INTERVAL` calls we drop buckets that are empty or whose newest
    timestamp is older than the window.
    """

    _EVICTION_INTERVAL = 1000

    def __init__(self, max_requests: int, window_seconds: int):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._calls_since_evict = 0

    def check(self, key: str) -> tuple[bool, int, int]:
        now = time.time()
        with self._lock:
            # Run eviction before touching the current key so we don't
            # accidentally evict a freshly-created (still empty) bucket
            # for this caller.
            self._calls_since_evict += 1
            if self._calls_since_evict >= self._EVICTION_INTERVAL:
                self._evict_idle_buckets(now)
                self._calls_since_evict = 0

            bucket = self._buckets[key]
            while bucket and now - bucket[0] >= self._window_seconds:
                bucket.popleft()

            if len(bucket) >= self._max_requests:
                retry_after = max(1, int(self._window_seconds - (now - bucket[0])))
                return False, retry_after, 0

            bucket.append(now)
            remaining = max(0, self._max_requests - len(bucket))
            return True, 0, remaining

    def _evict_idle_buckets(self, now: float) -> None:
        stale_keys = [
            key
            for key, bucket in self._buckets.items()
            if not bucket or now - bucket[-1] >= self._window_seconds
        ]
        for key in stale_keys:
            del self._buckets[key]
