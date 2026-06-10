"""Dev.to publishing — HTTP transport client used by PublishingService."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

import requests

from advanced.config import Settings, reveal
from advanced.models import BlogDraft, PublishResult

# Dev.to tags must be alphanumeric (no spaces, hyphens, or punctuation) and an
# article accepts at most four. We strip anything else rather than let the API
# reject the whole publish with a 422.
_MAX_DEVTO_TAGS = 4


class DevToPublishError(RuntimeError):
    """Dev.to rejected or failed the publish request (carries status + body)."""


def _devto_tags(tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    for tag in tags:
        normalized = re.sub(r"[^a-z0-9]", "", tag.lower())
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned[:_MAX_DEVTO_TAGS]


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
                "tags": _devto_tags(blog.tags),
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
            except requests.RequestException as error:
                # Network/transport problem — worth retrying.
                last_error = error
                if attempt == attempts:
                    break
                time.sleep(attempt * 2)
                continue

            if response.status_code < 400:
                return response.json()

            # A 4xx is a client error (bad tags, duplicate, etc.) — retrying
            # won't help, so fail fast and surface what Dev.to actually said.
            if 400 <= response.status_code < 500:
                raise DevToPublishError(
                    f"Dev.to rejected the article ({response.status_code}): "
                    f"{response.text[:500]}"
                )

            # 5xx — server-side, retry.
            last_error = requests.HTTPError(
                f"{response.status_code} from Dev.to: {response.text[:200]}"
            )
            if attempt == attempts:
                break
            time.sleep(attempt * 2)

        raise DevToPublishError(
            f"Dev.to publish failed after {attempts} attempts: {last_error}"
        ) from last_error
