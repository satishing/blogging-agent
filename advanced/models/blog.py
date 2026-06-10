from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .research import ResearchSource

# Absolute floor for a publishable article, independent of the configurable
# read-time band (which the writing-task guardrail enforces). This is the hard
# backstop that makes BlogDraft validation reject stub-length content — and,
# via output_pydantic, triggers an editor retry when it fails.
MIN_CONTENT_WORDS = 400


class BlogDraft(BaseModel):
    topic: str = Field(min_length=3)
    title: str = Field(min_length=12, max_length=130)
    summary: str = Field(min_length=40)
    content_markdown: str = Field(min_length=500)
    tags: list[str] = Field(default_factory=list)
    estimated_read_minutes: int = Field(ge=1, le=20)
    sources: list[ResearchSource] = Field(default_factory=list)

    @field_validator("content_markdown")
    @classmethod
    def enforce_min_words(cls, value: str) -> str:
        word_count = len(value.split())
        if word_count < MIN_CONTENT_WORDS:
            raise ValueError(
                f"content_markdown has {word_count} words; needs at least "
                f"{MIN_CONTENT_WORDS} words for a substantive article."
            )
        return value

    @field_validator("tags")
    @classmethod
    def sanitize_tags(cls, value: list[str]) -> list[str]:
        cleaned = [tag.lower().replace(" ", "") for tag in value if tag]
        deduped: list[str] = []
        for tag in cleaned:
            if tag not in deduped:
                deduped.append(tag)
        return deduped[:4] or ["ai", "learning"]


class PublishResult(BaseModel):
    platform: str
    status: str
    external_id: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    raw_response: dict[str, Any] | str | None = None


class PipelineResult(BaseModel):
    topic: str
    blog: BlogDraft
    publish_result: PublishResult | None = None
    cached: bool = False
