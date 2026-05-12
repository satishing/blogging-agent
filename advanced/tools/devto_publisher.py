"""Dev.to publishing — HTTP client + CrewAI tool used by the publisher agent."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import requests
from crewai.tools import BaseTool
from pydantic import PrivateAttr

from advanced.config import Settings
from advanced.models import BlogDraft, PublishResult

if TYPE_CHECKING:
    from advanced.services.publishing_service import PublishingService


class DevToPublisherClient:
    """HTTP transport for Dev.to article publishing with retry/backoff.

    Pure transport — no idempotency, no validation, no agent awareness. The
    `published_as_draft` setting controls whether the article goes live or
    stays as a draft (default: draft-first for safety).
    """

    def __init__(self, settings: Settings):
        self._settings = settings

    def publish(self, blog: BlogDraft) -> PublishResult:
        if not self._settings.devto_api_key:
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
            "api-key": self._settings.devto_api_key,
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


class DevToPublisherTool(BaseTool):
    """CrewAI tool wired to PublishingService so idempotency is enforced even
    when an agent invokes publishing. The agent sees a simple `blog_json -> result`
    interface; idempotency, caching, and HTTP retries live behind the service."""

    name: str = "publish_to_devto"
    description: str = (
        "Publishes validated blog JSON to Dev.to. Input must be a JSON object containing "
        "title, summary, content_markdown, tags, topic, estimated_read_minutes, and sources."
    )

    _publishing_service: "PublishingService" = PrivateAttr()

    def __init__(self, publishing_service: "PublishingService", **kwargs: Any):
        super().__init__(**kwargs)
        self._publishing_service = publishing_service

    def _run(self, blog_json: str) -> str:
        blog_data = json.loads(blog_json)
        blog = BlogDraft.model_validate(blog_data)
        idempotency_key = self._publishing_service.build_idempotency_key(
            blog.topic, blog.title
        )
        result = self._publishing_service.publish_blog(
            blog, idempotency_key=idempotency_key
        )
        return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
