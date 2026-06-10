"""Dev.to publishing — HTTP transport client used by PublishingService."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import requests

from advanced.config import Settings, reveal
from advanced.models import BlogDraft, PublishResult


class DevToPublisherClient:
    """HTTP transport for Dev.to article publishing with retry/backoff.

    Pure transport — no idempotency, no validation, no agent awareness. The
    `published_as_draft` setting controls whether the article goes live or
    stays as a draft (default: draft-first for safety).
    """

    def __init__(self, settings: Settings):
        self._settings = settings

    def publish(self, blog: BlogDraft) -> PublishResult:
        api_key = reveal(self._settings.devto_api_key)
        if not api_key:
            raise ValueError("DEVTO_API_KEY is required for publishing")

        payload = {
            "article": {
                "title": blog.title,
                "body_markdown": blog.content_markdown,
                "tags": blog.tags,
                "published": not self._settings.publish_as_draft,
                "description": blog.summary[:220],
            }
        }
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json",
        }
        response_json = self._post_with_retry(payload=payload, headers=headers)
        return PublishResult(
            platform="dev.to",
            status="published" if response_json.get("published") else "draft_created",
            external_id=(
                str(response_json.get("id")) if response_json.get("id") else None
            ),
            url=response_json.get("url"),
            published_at=datetime.now(timezone.utc),
            raw_response=response_json,
        )

    def _post_with_retry(
        self, payload: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        attempts = 3
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = requests.post(
                    self._settings.devto_api_url,
                    json=payload,
                    headers=headers,
                    timeout=30,
                )
                response.raise_for_status()
                return response.json()
            except requests.RequestException as error:
                last_error = error
                if attempt == attempts:
                    break
                time.sleep(attempt * 2)
        raise RuntimeError("Dev.to publish failed after retries") from last_error
